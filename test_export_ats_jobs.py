import contextlib
import csv
from decimal import Decimal
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).parent))
import export_ats_jobs as client

ROOT = Path(__file__).parent


class AtsCsvTest(unittest.TestCase):
    def test_both_offline_exports_never_use_token_or_network(self):
        for provider in ('lever', 'ashby'):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'jobs.csv'
                sample = ROOT / f'sample_{provider}_jobs.json'
                with patch.dict(client.os.environ, {}, clear=True), patch.object(client, 'build_opener') as network, contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(client.main(['--provider', provider, '--from-json', str(sample), '--output', str(output)]), 0)
                network.assert_not_called()
                self.assertTrue(output.read_bytes().startswith(b'\xef\xbb\xbf'))
                with output.open(encoding='utf-8-sig', newline='') as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]['provider'], provider)
                self.assertEqual(rows[0]['jobUrl'], json.loads(sample.read_text())[0]['jobUrl'])

    def test_source_dates_salary_units_and_nested_locations_are_preserved(self):
        lever = json.loads((ROOT / 'sample_lever_jobs.json').read_text())[0]
        ashby = json.loads((ROOT / 'sample_ashby_jobs.json').read_text())[0]
        a, b = client.csv_row('lever', lever), client.csv_row('ashby', ashby)
        self.assertEqual(a['createdAt'], lever['createdAt'])
        self.assertEqual(a['publishedAt'], '')
        self.assertEqual(b['publishedAt'], ashby['publishedAt'])
        self.assertEqual(b['createdAt'], '')
        self.assertEqual(json.loads(a['salaryRangeJson']), lever['salaryRange'])
        self.assertEqual(json.loads(b['compensationJson']), ashby['compensation'])
        self.assertEqual(json.loads(b['secondaryLocationsJson']), ashby['secondaryLocations'])
        self.assertEqual(b['locations'], 'Example City; Example Remote')
        self.assertEqual(b['isRemote'], 'True')

    def test_one_capped_post_targets_selected_actor_with_no_public_token(self):
        for provider in ('lever', 'ashby'):
            with self.subTest(provider=provider), patch.object(client, 'build_opener') as factory:
                payload = client.make_input(provider, ['example-company'], title='engineer', department='data')
                factory.return_value.open.return_value.__enter__.return_value = io.BytesIO((ROOT / f'sample_{provider}_jobs.json').read_bytes())
                self.assertEqual(len(client.run_actor(provider, payload, 'synthetic-test-token', Decimal('0.02'))), 2)
                factory.return_value.open.assert_called_once()
                req = factory.return_value.open.call_args.args[0]
                self.assertEqual(req.get_method(), 'POST')
                self.assertIn(client.ACTORS[provider], req.full_url)
                self.assertNotIn('synthetic-test-token', req.full_url)
                self.assertEqual(req.get_header('Authorization'), 'Bearer synthetic-test-token')
                self.assertEqual(parse_qs(urlsplit(req.full_url).query)['maxTotalChargeUsd'], ['0.02'])
                self.assertEqual(json.loads(req.data)['departmentContains'], 'data')
                self.assertFalse(json.loads(req.data)['onlyNew'])
                self.assertIs(factory.call_args.args[0], client.NoRedirect)

    def test_uncertain_paid_creation_is_never_retried(self):
        with patch.object(client, 'build_opener') as factory:
            factory.return_value.open.side_effect = socket.timeout('synthetic timeout')
            with self.assertRaises(socket.timeout):
                client.run_actor('lever', client.make_input('lever', ['example']), 'synthetic-test-token', Decimal('0.02'))
            factory.return_value.open.assert_called_once()

    def test_board_validation_prevents_cross_provider_and_credential_urls(self):
        self.assertEqual(client.board_token('lever', 'https://jobs.eu.lever.co/Example'), 'eu:Example')
        self.assertEqual(client.board_token('lever', 'eu:Example'), 'eu:Example')
        self.assertEqual(client.board_token('ashby', 'https://jobs.ashbyhq.com/Example/'), 'Example')
        for provider, value in [('lever', 'https://jobs.ashbyhq.com/Example'), ('ashby', 'https://jobs.lever.co/Example'),
                                ('lever', 'https://secret@jobs.lever.co/Example'), ('lever', 'https://jobs.lever.co/Example?id=secret'),
                                ('lever', 'https://jobs.lever.co/Example/job-id'), ('ashby', 'https://127.0.0.1/Example')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                client.make_input(provider, [value])
        with self.assertRaises(ValueError):
            client.make_input('lever', ['example-' + str(i) for i in range(26)])

    def test_invalid_caps_or_empty_auth_never_start_network(self):
        with patch.object(client, 'build_opener') as network:
            for cap in ('0', '-1', 'NaN', 'Infinity'):
                with self.assertRaises(ValueError):
                    client.run_actor('ashby', {}, 'synthetic-test-token', Decimal(cap))
            with self.assertRaises(ValueError):
                client.run_actor('lever', {}, '', Decimal('0.02'))
            network.assert_not_called()

    def test_invalid_record_or_wrong_provider_preserves_existing_output(self):
        ashby = json.loads((ROOT / 'sample_ashby_jobs.json').read_text())
        bad = [{**ashby[0], 'compensation': 'wrong shape'}]
        for provider, value in [('lever', ashby), ('ashby', bad), ('ashby', {'jobs': ashby})]:
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'existing.csv'
                output.write_text('keep data')
                with self.assertRaises(ValueError):
                    client.write_csv(provider, value, output)
                self.assertEqual(output.read_text(), 'keep data')

    def test_empty_dataset_writes_header_and_formula_titles_are_neutralized(self):
        row = json.loads((ROOT / 'sample_lever_jobs.json').read_text())[1]
        self.assertEqual(client.csv_row('lever', row)['title'], "'" + row['title'])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'empty.csv'
            client.write_csv('lever', [], output)
            with output.open(encoding='utf-8-sig', newline='') as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(tuple(reader.fieldnames), client.FIELDS)
                self.assertEqual(list(reader), [])

    def test_history_is_source_and_filter_specific(self):
        a = client.make_input('lever', ['example'], title='engineer')
        self.assertEqual(a['stateKey'], client.make_input('lever', ['example'], title='engineer', only_new=True)['stateKey'])
        self.assertNotEqual(a['stateKey'], client.make_input('ashby', ['example'], title='engineer')['stateKey'])
        self.assertNotEqual(a['stateKey'], client.make_input('lever', ['example'], title='analyst')['stateKey'])
        self.assertNotEqual(a['stateKey'], client.make_input('lever', ['eu:example'], title='engineer')['stateKey'])


if __name__ == '__main__':
    unittest.main()
