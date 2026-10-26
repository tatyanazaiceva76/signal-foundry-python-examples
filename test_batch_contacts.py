import contextlib
import csv
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import batch_contacts as bulk


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / 'websites.csv'
        self.checkpoint = self.directory / '.private' / 'job.json'
        self.output = self.directory / 'contacts.csv'
        self.make_csv(26)
        self.arguments = ['--input-csv', str(self.source), '--checkpoint', str(self.checkpoint),
                          '--output', str(self.output)]

    def make_csv(self, count):
        with self.source.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['company', 'website'])
            writer.writerows((f'Synthetic {i}', f'company-{i}.example.com') for i in range(count))

    def main(self, *arguments):
        with patch.dict(os.environ, {'APIFY_TOKEN': 'dummy-test-token'}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return bulk.main(self.arguments + list(arguments))

    def run_response(self, run_id='R1', status='SUCCEEDED', cap='0.08'):
        return {'data': {'id': run_id, 'actId': bulk.ACTOR_ID, 'status': status,
                         'options': {'maxTotalChargeUsd': float(cap)},
                         'defaultDatasetId': 'D' + run_id[1:], 'defaultKeyValueStoreId': 'K' + run_id[1:]}}

    def test_default_plan_and_insufficient_aggregate_cap_make_no_api_calls(self):
        with patch.object(bulk, 'json_request') as request:
            self.assertEqual(self.main(), 0)
            self.assertEqual(self.main('--execute', '--max-total-charge', '0.15'), 1)
        request.assert_not_called()
        self.assertFalse(self.checkpoint.exists())
        self.assertFalse(self.output.exists())

    def test_sixty_sites_are_merged_from_three_bounded_runs_and_completed_resume_makes_no_calls(self):
        self.make_csv(60)
        payloads, calls = {}, []

        def request(method, path, token, **options):
            calls.append((method, path, options))
            self.assertEqual(token, 'dummy-test-token')
            if method == 'POST':
                number = len(payloads) + 1
                payloads['D' + str(number)] = options['payload']
                self.assertEqual(options['query']['maxTotalChargeUsd'], '0.08')
                self.assertFalse(options['payload']['onlyNew'])
                return self.run_response('R' + str(number))
            dataset = path.split('/')[2]
            return [{'websiteUrl': url, 'pageUrl': url, 'emails': ['info@example.com'],
                     'phones': ['+12025550123']} for url in payloads[dataset]['websiteUrls']]

        with patch.object(bulk, 'json_request', side_effect=request):
            self.assertEqual(self.main('--execute', '--max-total-charge', '0.24'), 0)
        posts = [call for call in calls if call[0] == 'POST']
        self.assertEqual([len(call[2]['payload']['websiteUrls']) for call in posts], [25, 25, 10])
        self.assertEqual(sum(Decimal(call[2]['query']['maxTotalChargeUsd']) for call in posts), Decimal('0.24'))
        with self.output.open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 60)
        self.assertEqual(len({row['websiteUrl'] for row in rows}), 60)
        self.assertTrue(rows[0]['phones'].startswith("'"))
        self.assertNotIn('dummy-test-token', self.checkpoint.read_text())
        if os.name != 'nt':
            self.assertEqual(self.checkpoint.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.checkpoint.parent.stat().st_mode & 0o777, 0o700)
        with patch.object(bulk, 'json_request') as request:
            self.assertEqual(self.main('--execute', '--resume', '--max-total-charge', '0.24'), 0)
        request.assert_not_called()

    def test_ambiguous_create_is_not_retried_and_recovery_checks_actual_run_input(self):
        calls = []
        first_payload = {}

        def interrupted(method, path, token, **options):
            calls.append(method)
            first_payload.update(options['payload'])
            raise TimeoutError('response lost')

        with patch.object(bulk, 'json_request', side_effect=interrupted):
            self.assertEqual(self.main('--execute', '--max-total-charge', '0.16'), 1)
        self.assertEqual(calls, ['POST'])
        self.assertEqual(json.loads(self.checkpoint.read_text())['batches'][0]['status'], 'STARTING')
        with patch.object(bulk, 'json_request') as request:
            self.assertEqual(self.main('--execute', '--resume', '--max-total-charge', '0.16'), 1)
        request.assert_not_called()
        job = json.loads(self.checkpoint.read_text())
        first_payload = bulk.batch_input(job, 0)

        def mismatch(method, path, token, **options):
            self.assertEqual(method, 'GET')
            return {'wrong': 'input'} if path.endswith('/INPUT') else self.run_response()

        with patch.object(bulk, 'json_request', side_effect=mismatch):
            self.assertEqual(self.main('--execute', '--resume', '--recover-run', 'R1', '--max-total-charge', '0.16'), 1)
        self.assertNotIn('runId', json.loads(self.checkpoint.read_text())['batches'][0])
        # Reduce this fixture to one batch through the original input, then check recovery without any POST.
        self.checkpoint.unlink()
        self.output.unlink()
        self.make_csv(2)
        with patch.object(bulk, 'json_request', side_effect=interrupted):
            self.assertEqual(self.main('--execute', '--max-total-charge', '0.08'), 1)
        job = json.loads(self.checkpoint.read_text())

        def recover(method, path, token, **options):
            self.assertEqual(method, 'GET')
            if path.endswith('/INPUT'):
                return bulk.batch_input(job, 0)
            if '/datasets/' in path:
                return []
            return self.run_response()

        with patch.object(bulk, 'json_request', side_effect=recover):
            self.assertEqual(self.main('--execute', '--resume', '--recover-run', 'R1', '--max-total-charge', '0.08'), 0)
        self.assertEqual(json.loads(self.checkpoint.read_text())['batches'][0]['status'], 'DONE')

    def test_known_live_run_is_read_again_after_timeout_instead_of_recreated(self):
        self.make_csv(1)

        def first(method, path, token, **options):
            if method == 'POST':
                return self.run_response(status='RUNNING')
            raise TimeoutError('status read interrupted')

        with patch.object(bulk, 'json_request', side_effect=first):
            self.assertEqual(self.main('--execute', '--max-total-charge', '0.08'), 1)
        self.assertEqual(json.loads(self.checkpoint.read_text())['batches'][0]['runId'], 'R1')

        def resume(method, path, token, **options):
            self.assertEqual(method, 'GET')
            return [] if '/datasets/' in path else self.run_response()

        with patch.object(bulk, 'json_request', side_effect=resume):
            self.assertEqual(self.main('--execute', '--resume', '--max-total-charge', '0.08'), 0)

    def test_corrupted_extra_batch_and_changed_input_cannot_expand_the_approved_job(self):
        with patch.object(bulk, 'json_request', side_effect=TimeoutError):
            self.assertEqual(self.main('--execute', '--max-total-charge', '0.16'), 1)
        document = json.loads(self.checkpoint.read_text())
        document['batches'].append({'websites': ['https://extra.example.com/'], 'status': 'PENDING'})
        self.checkpoint.write_text(json.dumps(document))
        with patch.object(bulk, 'json_request') as request:
            self.assertEqual(self.main('--execute', '--resume', '--max-total-charge', '0.16'), 1)
        request.assert_not_called()
        document['batches'].pop()
        self.checkpoint.write_text(json.dumps(document))
        self.make_csv(27)
        with patch.object(bulk, 'json_request') as request:
            self.assertEqual(self.main('--execute', '--resume', '--max-total-charge', '0.16'), 1)
        request.assert_not_called()

    def test_failed_run_or_unconfirmed_cap_never_starts_the_next_batch(self):
        for mode in ('failed', 'cap', 'missing-id'):
            with self.subTest(mode=mode):
                if self.checkpoint.exists():
                    self.checkpoint.unlink()
                if self.output.exists():
                    self.output.unlink()
                response = self.run_response(status='FAILED') if mode == 'failed' else self.run_response(cap='0.09')
                if mode == 'missing-id':
                    response = self.run_response()
                    response['data']['id'] = None
                with patch.object(bulk, 'json_request', return_value=response) as request:
                    self.assertEqual(self.main('--execute', '--max-total-charge', '0.16'), 1)
                self.assertEqual(request.call_count, 1)

    def test_csv_normalization_deduplication_and_invalid_values(self):
        self.source.write_text('company,website\nA,EXAMPLE.com\nB,https://example.com/#fragment\nC,https://example.org/contact\n', encoding='utf-8-sig')
        sites, duplicates = bulk.read_websites(self.source, 'website')
        self.assertEqual(sites, ['https://example.com/', 'https://example.org/contact'])
        self.assertEqual(duplicates, 1)
        for value in ['http://127.0.0.1/', 'https://user:password@example.com', 'https://example.com:8443/', 'http://localhost/', 'http://printer.local/', 'javascript:alert(1)']:
            with self.assertRaises(ValueError):
                bulk.website_url(value)
        self.source.write_text('company,website\nA\n')
        with self.assertRaises(ValueError):
            bulk.read_websites(self.source, 'website')

    def test_a_second_process_cannot_use_the_same_checkpoint(self):
        self.checkpoint.parent.mkdir(mode=0o700)
        self.checkpoint.with_name('job.json.lock').write_text('123')
        with patch.object(bulk, 'json_request') as request:
            self.assertEqual(self.main('--execute', '--max-total-charge', '0.16'), 1)
        request.assert_not_called()

    def test_serialized_request_keeps_token_out_of_url_and_passes_the_server_cap(self):
        seen = []

        def receive(request, **options):
            seen.append(request)
            return io.BytesIO(b'{"data":{}}')

        with patch.object(bulk, 'urlopen', side_effect=receive):
            bulk.json_request('POST', '/actors/' + bulk.ACTOR + '/runs', 'dummy-test-token',
                              query={'maxTotalChargeUsd': '0.08'}, payload={'websiteUrls': ['https://example.com/']})
        self.assertEqual(len(seen), 1)
        self.assertNotIn('dummy-test-token', seen[0].full_url)
        self.assertEqual(seen[0].get_header('Authorization'), 'Bearer dummy-test-token')
        self.assertEqual(parse_qs(urlsplit(seen[0].full_url).query)['maxTotalChargeUsd'], ['0.08'])
        self.assertEqual(json.loads(seen[0].data)['websiteUrls'], ['https://example.com/'])


if __name__ == '__main__':
    unittest.main()
