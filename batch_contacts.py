#!/usr/bin/env python3
"""Plan, then explicitly execute a website-CSV export with an aggregate Actor-run cap."""
import argparse
from contextlib import contextmanager
import csv
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import uuid

from export_contacts import positive_usd, write_csv

ACTOR = 'signalfoundryhq~website-contact-extractor'
ACTOR_ID = '4BOaPLj5wYUOKek3Z'
API = 'https://api.apify.com/v2'
TERMINAL = {'SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'}
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000


def usd(value):
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def website_url(value):
    text = value.strip()
    if not text or any(c.isspace() or ord(c) < 32 for c in text) or text.startswith('//'):
        raise ValueError('Use a public domain or HTTP(S) URL without whitespace.')
    parsed = urlsplit(text if '://' in text else 'https://' + text)
    if parsed.scheme not in ('http', 'https') or parsed.username is not None or parsed.password is not None:
        raise ValueError('Only public HTTP(S) URLs without credentials are supported.')
    host = (parsed.hostname or '').rstrip('.').encode('idna').decode('ascii').lower()
    if parsed.port not in (None, 443 if parsed.scheme == 'https' else 80):
        raise ValueError('Custom ports are not supported.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if '.' not in host or host.endswith(('.localhost', '.local', '.internal')) or any(
            not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
            for label in host.split('.')
        ):
            raise ValueError('Use a public website hostname.')
    else:
        if not address.is_global:
            raise ValueError('Private or reserved IP addresses are not supported.')
        if address.version == 6:
            host = '[' + host + ']'
    return urlunsplit((parsed.scheme, host, parsed.path or '/', parsed.query, ''))


def read_websites(path, column):
    with Path(path).open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('The input CSV exceeds 5 MiB.')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    if not reader.fieldnames or reader.fieldnames.count(column) != 1:
        raise ValueError('The selected website column must occur exactly once in the CSV header.')
    sites, seen, nonempty = [], set(), 0
    for row in reader:
        if not any(value for value in row.values()):
            continue
        nonempty += 1
        if nonempty > MAX_ROWS:
            raise ValueError('The input CSV exceeds 10,000 nonempty rows.')
        try:
            if None in row or not (row.get(column) or '').strip():
                raise ValueError('Missing website or extra CSV fields.')
            normalized = website_url(row[column])
        except (ValueError, UnicodeError):
            raise ValueError(f'Invalid website or CSV width at input line {reader.line_num}.') from None
        if normalized not in seen:
            sites.append(normalized)
            seen.add(normalized)
    if not sites:
        raise ValueError('The CSV has no websites to process.')
    return sites, nonempty - len(sites)


def json_request(method, path, token, *, query=None, payload=None):
    address = API + path + ('?' + urlencode(query) if query else '')
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    request = Request(address, data=data, method=method,
                      headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    # There is deliberately no retry of POST, including after an ambiguous response.
    with urlopen(request, timeout=75) as response:
        return json.load(response)


def atomic_json(path, document):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.checkpoint-')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def checkpoint_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = path.with_name(path.name + '.lock')
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Checkpoint is locked. Confirm the original process has exited before removing its stale .lock file.') from None
    try:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        os.unlink(lock)


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9]{1,64}', value) is not None


def run_data(response, expected_id=None):
    data = response.get('data') if isinstance(response, dict) else None
    if not isinstance(data, dict) or not valid_id(data.get('id')) or (expected_id is not None and data['id'] != expected_id):
        raise ValueError('Invalid run response. Inspect Console before retrying; a run may exist.')
    return data


def validate_run(run, cap):
    if run.get('actId') != ACTOR_ID:
        raise ValueError('The run belongs to a different Actor; no further batch was started.')
    options = run.get('options')
    if not isinstance(options, dict):
        raise ValueError('Run charge cap could not be confirmed; inspect the existing run in Console.')
    try:
        actual_cap = Decimal(str(options.get('maxTotalChargeUsd')))
    except InvalidOperation:
        raise ValueError('Run charge cap could not be confirmed; inspect the existing run in Console.') from None
    if not actual_cap.is_finite() or actual_cap <= 0 or actual_cap > cap:
        raise ValueError('Run charge cap differs from the approved bound; inspect the existing run in Console.')


def batch_input(job, index):
    batch = job['batches'][index]
    options = job['plan']
    return {'websiteUrls': batch['websites'], 'maxPagesPerSite': options['maxPages'],
            'maxItems': len(batch['websites']) * options['maxPages'],
            'requireEmail': options['requireEmail'], 'includeEmptyPages': False,
            'onlyNew': False, 'stateKey': f"csv-batch-{job['jobId']}-{index + 1}"}


def export_cached(job, output):
    rows = [row for batch in job['batches'] if batch['status'] == 'DONE' for row in batch['rows']]
    descriptor, temporary = tempfile.mkstemp(dir=output.parent, prefix='.contacts-')
    os.close(descriptor)
    try:
        write_csv(rows, temporary)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(rows)


def validate_checkpoint(job, plan, signature):
    if not isinstance(job, dict) or job.get('version') != 1 or job.get('planHash') != signature or job.get('plan') != plan:
        raise ValueError('CSV or batch settings changed. Restore the original inputs before resuming.')
    expected = [plan['websites'][i:i + plan['batchSize']]
                for i in range(0, len(plan['websites']), plan['batchSize'])]
    batches = job.get('batches')
    if not isinstance(batches, list) or len(batches) != len(expected) or not re.fullmatch(r'[a-f0-9]{32}', str(job.get('jobId', ''))):
        raise ValueError('Checkpoint structure does not match the approved batch plan.')
    for batch, websites in zip(batches, expected):
        if not isinstance(batch, dict) or batch.get('websites') != websites or batch.get('status') not in {'PENDING', 'STARTING', 'DONE'}:
            raise ValueError('Checkpoint batch does not match the approved inputs.')
        if batch.get('runId') is not None and not valid_id(batch['runId']):
            raise ValueError('Checkpoint contains an invalid run ID.')
        if batch['status'] == 'PENDING' and batch.get('runId'):
            raise ValueError('Checkpoint has an inconsistent pending run.')
        if batch['status'] == 'DONE':
            if not batch.get('runId') or not isinstance(batch.get('rows'), list) or any(not isinstance(r, dict) for r in batch['rows']):
                raise ValueError('Completed checkpoint batch is missing its saved data.')


def execute(plan, checkpoint, output, token, *, resume=False, recover_run=None):
    signature = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    cap = Decimal(plan['batchCapUsd'])
    with checkpoint_lock(checkpoint):
        if checkpoint.exists():
            if not resume:
                raise ValueError('Checkpoint already exists. Use --resume for this job; do not recreate its paid runs.')
            job = json.loads(checkpoint.read_text(encoding='utf-8'))
            validate_checkpoint(job, plan, signature)
            if output.exists() and job.get('outputPath') != str(output):
                raise ValueError('Refusing to overwrite an existing output not owned by this checkpoint.')
        else:
            if resume:
                raise ValueError('No checkpoint exists to resume.')
            job = {'version': 1, 'planHash': signature, 'plan': plan, 'jobId': uuid.uuid4().hex,
                   'outputPath': str(output),
                   'batches': [{'websites': plan['websites'][i:i + plan['batchSize']], 'status': 'PENDING'}
                               for i in range(0, len(plan['websites']), plan['batchSize'])]}
            atomic_json(checkpoint, job)
        job['outputPath'] = str(output)
        atomic_json(checkpoint, job)
        if recover_run:
            unknown = [i for i, b in enumerate(job['batches']) if b['status'] == 'STARTING' and not b.get('runId')]
            if len(unknown) != 1 or not re.fullmatch(r'[A-Za-z0-9]{1,64}', recover_run):
                raise ValueError('--recover-run needs exactly one interrupted start without a saved run ID.')
            index = unknown[0]
            recovered = run_data(json_request('GET', '/actor-runs/' + recover_run, token), recover_run)
            validate_run(recovered, cap)
            store_id = recovered.get('defaultKeyValueStoreId')
            if not valid_id(store_id):
                raise ValueError('Recovered input store could not be verified.')
            actual_input = json_request('GET', '/key-value-stores/' + store_id + '/records/INPUT', token)
            expected_input = batch_input(job, index)
            if not isinstance(actual_input, dict) or any(actual_input.get(k) != v for k, v in expected_input.items()):
                raise ValueError('Recovered run input does not match the interrupted batch.')
            job['batches'][index]['runId'] = recovered['id']
            atomic_json(checkpoint, job)
        export_cached(job, output)
        for index, batch in enumerate(job['batches']):
            if batch['status'] == 'DONE':
                continue
            if not batch.get('runId'):
                if batch['status'] != 'PENDING':
                    raise ValueError('A start response was interrupted. Find that run in Console and use --resume --recover-run RUN_ID; do not start a replacement.')
                batch['status'] = 'STARTING'
                atomic_json(checkpoint, job)  # Durable before the paid POST, including a crash before its response.
                run = run_data(json_request('POST', '/actors/' + ACTOR + '/runs', token,
                    query={'maxTotalChargeUsd': usd(cap), 'memory': 256, 'timeout': 120,
                           'restartOnError': 'false', 'waitForFinish': 0}, payload=batch_input(job, index)))
                batch['runId'] = run['id']
                atomic_json(checkpoint, job)
            else:
                run = run_data(json_request('GET', '/actor-runs/' + batch['runId'], token), batch['runId'])
            for poll in range(4):
                validate_run(run, cap)
                if run.get('status') in TERMINAL:
                    break
                if poll == 3:
                    raise ValueError('Run is still in progress. Use --resume to inspect the same saved run ID.')
                run = run_data(json_request('GET', '/actor-runs/' + batch['runId'], token,
                                             query={'waitForFinish': 60}), batch['runId'])
            if run.get('status') != 'SUCCEEDED':
                raise ValueError('A batch did not succeed. Inspect its saved run ID in Console; no replacement run was started.')
            dataset = run.get('defaultDatasetId')
            if not valid_id(dataset):
                raise ValueError('The completed run has no valid default dataset ID.')
            rows = json_request('GET', '/datasets/' + dataset + '/items', token,
                                query={'format': 'json', 'clean': 'true', 'limit': 251})
            if not isinstance(rows, list) or len(rows) > len(batch['websites']) * plan['maxPages']:
                raise ValueError('Unexpected dataset length; inspect the existing run.')
            for row in rows:
                if not isinstance(row, dict) or website_url(str(row.get('websiteUrl', ''))) not in batch['websites']:
                    raise ValueError('A dataset record does not match this batch.')
                if not isinstance(row.get('pageUrl'), str):
                    raise ValueError('A dataset record is missing its source-page URL.')
                website_url(row['pageUrl'])
                if plan['requireEmail'] and not row.get('emails'):
                    raise ValueError('The dataset violates the email-only filter; inspect the existing run.')
            batch.update(status='DONE', rows=rows, datasetId=dataset)
            atomic_json(checkpoint, job)
            export_cached(job, output)
        return export_cached(job, output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-csv', type=Path, required=True)
    parser.add_argument('--column', default='website', help='Exact website column header')
    parser.add_argument('--batch-size', type=int, default=25)
    parser.add_argument('--max-pages', type=int, default=1)
    parser.add_argument('--batch-cap', type=positive_usd, default=Decimal('0.08'))
    parser.add_argument('--max-total-charge', type=positive_usd,
                        help='Maximum sum of this checkpoint job\'s Actor-run caps; required with --execute')
    parser.add_argument('--require-email', action='store_true')
    parser.add_argument('--execute', action='store_true', help='Opt in to new paid runs; default is offline plan only')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--recover-run', help='Known Console run ID for one interrupted start; requires --resume')
    parser.add_argument('--checkpoint', type=Path, default=Path('.private/contact-batch-state.json'))
    parser.add_argument('--output', type=Path, default=Path('contacts.csv'))
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.batch_size <= 25 or not 1 <= args.max_pages <= 10:
            raise ValueError('Use a batch size of 1–25 and 1–10 pages per website.')
        if args.recover_run and not args.resume:
            raise ValueError('--recover-run requires --resume.')
        sites, duplicates = read_websites(args.input_csv, args.column)
        batches = (len(sites) + args.batch_size - 1) // args.batch_size
        with localcontext() as context:
            context.prec = max(28, len(args.batch_cap.as_tuple().digits) + len(str(batches)) + 2)
            ceiling = batches * args.batch_cap
        print(f'{len(sites)} unique websites; {duplicates} duplicates removed; {batches} batches. '
              f'Sum of server-side run caps: ${usd(ceiling)} (${usd(args.batch_cap)} each).')
        if not args.execute:
            print('Offline plan only. No API call, token access, checkpoint or paid run.')
            return 0
        if args.max_total_charge is None or ceiling > args.max_total_charge:
            raise ValueError('Before any API call, authorize --max-total-charge at least equal to the sum of all batch caps, or reduce the input/caps.')
        checkpoint, output, source = args.checkpoint.resolve(), args.output.resolve(), args.input_csv.resolve()
        if len({checkpoint, output, source}) != 3:
            raise ValueError('Input, output and checkpoint must be different files.')
        if output.exists() and not args.resume:
            raise ValueError('Output already exists. Choose a new output or resume its original checkpoint.')
        if not output.parent.is_dir():
            raise ValueError('Create the output directory before execution.')
        token = os.environ.get('APIFY_TOKEN', '').strip()
        if not token:
            raise ValueError('Set APIFY_TOKEN to your own token before --execute.')
        plan = {'websites': sites, 'batchSize': args.batch_size, 'maxPages': args.max_pages,
                'requireEmail': args.require_email, 'batchCapUsd': usd(args.batch_cap)}
        count = execute(plan, checkpoint, output, token, resume=args.resume, recover_run=args.recover_run)
        print(f'Wrote {count} page records. Charge caps are not invoices or a guarantee of contacts.')
        return 0
    except (HTTPError, URLError, TimeoutError):
        print('API request interrupted. Keep the checkpoint; a paid run may exist. Use --resume for saved IDs; inspect Console before recovering an unknown start. No automatic POST retry.', file=sys.stderr)
    except (OSError, ValueError, csv.Error) as error:
        print(str(error), file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
