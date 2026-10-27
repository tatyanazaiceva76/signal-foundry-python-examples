#!/usr/bin/env python3
"""Export existing Lever/Ashby Actor job records to CSV, offline or with one capped run."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener

from export_jobs import NoRedirect, positive_usd, spreadsheet_cell

ACTORS = {
    'lever': 'signalfoundryhq~lever-hiring-radar',
    'ashby': 'signalfoundryhq~ashby-hiring-radar',
}
FIELDS = ('provider', 'boardToken', 'region', 'jobId', 'title', 'location',
          'locations', 'department', 'team', 'employmentType', 'workplaceType',
          'isRemote', 'createdAt', 'publishedAt', 'salaryRangeJson',
          'compensationJson', 'secondaryLocationsJson', 'jobUrl', 'applyUrl',
          'sourceApiUrl', 'signalId')


def board_token(provider, text):
    if provider not in ACTORS:
        raise ValueError('Choose lever or ashby.')
    value = text.strip()
    region = 'us'
    if provider == 'lever' and value.startswith('eu:'):
        region, value = 'eu', value[3:]
    if '://' in value:
        parsed = urlsplit(value)
        hosts = {'jobs.lever.co', 'jobs.eu.lever.co'} if provider == 'lever' else {'jobs.ashbyhq.com'}
        if (parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.username
                or parsed.password or parsed.port not in (None, 443) or parsed.query or parsed.fragment):
            raise ValueError('Use an HTTPS job-board URL for the selected provider, without credentials or query parameters.')
        if region == 'eu' and parsed.hostname != 'jobs.eu.lever.co':
            raise ValueError('An eu: prefix cannot change the region of a supplied URL.')
        region = 'eu' if parsed.hostname == 'jobs.eu.lever.co' else 'us'
        parts = parsed.path.strip('/').split('/')
        if len(parts) != 1:
            raise ValueError('Use the employer board URL, not an individual job or application URL.')
        value = parts[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('Use a valid employer board token, one per line.')
    return ('eu:' if provider == 'lever' and region == 'eu' else '') + value


def make_input(provider, boards, *, title='', location='', department='', max_items=10,
               max_scanned=1000, only_new=False, state_key=None):
    boards = list(dict.fromkeys(board_token(provider, value) for value in boards))
    if not 1 <= len(boards) <= 25:
        raise ValueError('Provide 1 to 25 employer boards.')
    if not 1 <= max_items <= 5000 or not 1 <= max_scanned <= 10000:
        raise ValueError('Use 1–5,000 delivered jobs and 1–10,000 scanned listings.')
    filters = {'boardTokens': boards, 'titleContains': title.strip(),
               'locationContains': location.strip(), 'departmentContains': department.strip()}
    if provider == 'ashby':
        filters['includeCompensation'] = True
    if state_key is None:
        digest = hashlib.sha256(json.dumps([provider, filters], sort_keys=True).encode()).hexdigest()[:16]
        state_key = 'csv-' + provider + '-' + digest
    if not state_key.strip():
        raise ValueError('The history key cannot be empty.')
    return {**filters, 'maxItems': max_items, 'maxJobsScanned': max_scanned,
            'onlyNew': only_new, 'stateKey': state_key}


def dataset_rows(value):
    if not isinstance(value, list) or any(
        not isinstance(row, dict) or not isinstance(row.get('title'), str)
        or not isinstance(row.get('jobUrl'), str) or not isinstance(row.get('jobId'), (str, int))
        or isinstance(row.get('jobId'), bool) for row in value
    ):
        raise ValueError('Expected an array of this Actor\'s normalized job records; no CSV was written.')
    return value


def run_actor(provider, payload, token, max_charge):
    if provider not in ACTORS:
        raise ValueError('Choose lever or ashby.')
    if not token:
        raise ValueError('Set APIFY_TOKEN to your own Apify API token.')
    if not max_charge.is_finite() or max_charge <= 0:
        raise ValueError('Use a positive USD amount.')
    query = urlencode({'maxTotalChargeUsd': format(max_charge, 'f'), 'memory': 256, 'timeout': 120})
    request = Request(f'https://api.apify.com/v2/acts/{ACTORS[provider]}/run-sync-get-dataset-items?{query}',
        data=json.dumps(payload).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    # One paid POST; never redirect or retry an interrupted creation request.
    with build_opener(NoRedirect).open(request, timeout=150) as response:
        return dataset_rows(json.load(response))


def json_cell(value):
    return '' if value is None else json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def csv_row(provider, row):
    if provider == 'lever' and (row.get('region') not in ('us', 'eu') or not isinstance(row.get('locations'), list)):
        raise ValueError('Lever export requires normalized Lever Actor records, including region and locations.')
    if provider == 'ashby' and not isinstance(row.get('secondaryLocations'), list):
        raise ValueError('Ashby export requires normalized Ashby Actor records, including secondaryLocations.')
    for key in ('salaryRange', 'compensation'):
        if row.get(key) is not None and not isinstance(row[key], dict):
            raise ValueError(f'{key} must be an object or null; no CSV was written.')
    result = {field: row.get(field) for field in FIELDS}
    result['provider'] = provider
    if provider == 'ashby':
        secondary = row.get('secondaryLocations') or []
        result['locations'] = list(dict.fromkeys(str(x) for x in [row.get('location')] + [
            x if isinstance(x, str) else x.get('location') if isinstance(x, dict) else None
            for x in secondary] if x))
    result['salaryRangeJson'] = json_cell(row.get('salaryRange'))
    result['compensationJson'] = json_cell(row.get('compensation'))
    result['secondaryLocationsJson'] = json_cell(row.get('secondaryLocations'))
    return {field: spreadsheet_cell(result[field]) for field in FIELDS}


def write_csv(provider, rows, output):
    if provider not in ACTORS:
        raise ValueError('Choose lever or ashby.')
    # Validate and serialize every row before opening an existing output file.
    records = [csv_row(provider, row) for row in dataset_rows(rows)]
    with Path(output).open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(records)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=ACTORS, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--boards', type=Path, help='UTF-8 file: one token or HTTPS employer board URL per line')
    source.add_argument('--from-json', type=Path, help='Convert an existing normalized Actor dataset; no run or token')
    parser.add_argument('--output', type=Path, default=Path('jobs.csv'))
    parser.add_argument('--title-contains', default='')
    parser.add_argument('--location-contains', default='')
    parser.add_argument('--department-contains', default='')
    parser.add_argument('--max-charge', type=positive_usd, default=positive_usd('0.02'))
    parser.add_argument('--max-items', type=int, default=10)
    parser.add_argument('--max-scanned', type=int, default=1000)
    parser.add_argument('--only-new', action='store_true')
    parser.add_argument('--state-key')
    args = parser.parse_args(argv)
    try:
        if args.from_json:
            if args.only_new or args.state_key or any([args.title_contains, args.location_contains, args.department_contains]):
                raise ValueError('Filters and history options apply to --boards only; offline mode converts existing rows.')
            rows = dataset_rows(json.loads(args.from_json.read_text(encoding='utf-8-sig')))
        else:
            boards = [x.strip() for x in args.boards.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
            payload = make_input(args.provider, boards, title=args.title_contains, location=args.location_contains,
                department=args.department_contains, max_items=args.max_items, max_scanned=args.max_scanned,
                only_new=args.only_new, state_key=args.state_key)
            rows = run_actor(args.provider, payload, os.environ.get('APIFY_TOKEN', '').strip(), args.max_charge)
        write_csv(args.provider, rows, args.output)
    except (HTTPError, URLError, TimeoutError, socket.timeout) as error:
        status = f' (HTTP {error.code})' if isinstance(error, HTTPError) else ''
        print(f'Request did not finish{status}. Check this Actor in Apify Console before retrying; a paid run may already exist. No automatic retry.', file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f'Wrote {len(rows)} {args.provider} job versions to {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
