#!/usr/bin/env python3
"""Export Greenhouse watchlist job versions to CSV, offline or through Apify."""
import argparse
import csv
import hashlib
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ACTOR = 'signalfoundryhq~greenhouse-hiring-radar'
FIELDS = ('boardToken', 'jobId', 'companyName', 'title', 'location', 'departments',
          'firstPublished', 'updatedAt', 'jobUrl', 'descriptionText', 'signalId')


def positive_usd(text):
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError('Use a positive USD amount.')
    if not value.is_finite() or value <= 0:
        raise argparse.ArgumentTypeError('Use a positive USD amount.')
    return value


def make_input(boards, *, title='', location='', description='', max_items=10,
               max_scanned=1000, only_new=False, state_key=None):
    boards = list(dict.fromkeys(boards))
    if not 1 <= len(boards) <= 25 or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', b) for b in boards):
        raise ValueError('Provide 1 to 25 Greenhouse board tokens, one per line; not full URLs.')
    if not 1 <= max_items <= 5000 or not 1 <= max_scanned <= 10000:
        raise ValueError('Use 1–5,000 delivered jobs and 1–10,000 scanned listings.')
    filters = {'boardTokens': boards, 'titleContains': title, 'locationContains': location,
               'descriptionContains': description, 'includeDescription': True}
    if state_key is None:
        fingerprint = hashlib.sha256(json.dumps(filters, sort_keys=True).encode()).hexdigest()[:16]
        state_key = 'python-csv-' + fingerprint
    if not state_key.strip():
        raise ValueError('The history key cannot be empty.')
    return {**filters, 'maxItems': max_items, 'maxJobsScanned': max_scanned,
            'onlyNew': only_new, 'stateKey': state_key}


def dataset_rows(value):
    if not isinstance(value, list) or any(
        not isinstance(row, dict) or not isinstance(row.get('jobUrl'), str)
        or not isinstance(row.get('title'), str) or not isinstance(row.get('jobId'), (str, int))
        for row in value
    ):
        raise ValueError('Expected a JSON array of job dataset records; no CSV was written.')
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def run_actor(payload, token, max_charge):
    if not token:
        raise ValueError('Set APIFY_TOKEN to your own Apify API token.')
    if not max_charge.is_finite() or max_charge <= 0:
        raise ValueError('Use a positive USD amount.')
    query = urlencode({'maxTotalChargeUsd': format(max_charge, 'f'), 'memory': 256, 'timeout': 120})
    request = Request(f'https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?{query}',
        data=json.dumps(payload).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    # One paid POST, with no redirect or automatic retry. A lost response may hide a live run.
    with build_opener(NoRedirect).open(request, timeout=150) as response:
        return dataset_rows(json.load(response))


def spreadsheet_cell(value):
    text = '; '.join(map(str, value)) if isinstance(value, list) else '' if value is None else str(value)
    visible = re.sub(r'^[\s\ufeff]+', '', text)
    if visible.startswith(('=', '+', '-', '@', '＝', '＋', '－', '＠')) or text.startswith(('\t', '\r', '\n')):
        return "'" + text
    return text


def write_csv(rows, output):
    rows = dataset_rows(rows)
    with Path(output).open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows({field: spreadsheet_cell(row.get(field)) for field in FIELDS} for row in rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--boards', type=Path, help='UTF-8 file: one employer board token per line')
    source.add_argument('--from-json', type=Path, help='Convert an existing dataset without a new run or token')
    parser.add_argument('--output', type=Path, default=Path('jobs.csv'))
    parser.add_argument('--title-contains', default='')
    parser.add_argument('--location-contains', default='')
    parser.add_argument('--description-contains', default='')
    parser.add_argument('--max-charge', type=positive_usd, default=Decimal('0.02'))
    parser.add_argument('--max-items', type=int, default=10)
    parser.add_argument('--max-scanned', type=int, default=1000)
    parser.add_argument('--only-new', action='store_true', help='Skip versions previously delivered for this feed')
    parser.add_argument('--state-key', help='Optional explicit history key; otherwise derived from boards and filters')
    args = parser.parse_args(argv)
    try:
        if args.from_json:
            if args.only_new or args.state_key or any([args.title_contains, args.location_contains, args.description_contains]):
                raise ValueError('Filters and history options apply to --boards only; offline mode converts the existing rows unchanged.')
            rows = dataset_rows(json.loads(args.from_json.read_text(encoding='utf-8-sig')))
        else:
            boards = [s.strip() for s in args.boards.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
            payload = make_input(boards, title=args.title_contains, location=args.location_contains,
                description=args.description_contains, max_items=args.max_items,
                max_scanned=args.max_scanned, only_new=args.only_new, state_key=args.state_key)
            rows = run_actor(payload, os.environ.get('APIFY_TOKEN', '').strip(), args.max_charge)
        write_csv(rows, args.output)
    except (HTTPError, URLError, TimeoutError, socket.timeout) as error:
        status = f' (HTTP {error.code})' if isinstance(error, HTTPError) else ''
        print(f'Request did not finish{status}. Check this Actor in Apify Console before retrying; a run may already exist. No automatic retry.', file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f'Wrote {len(rows)} job versions to {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
