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
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent))
import export_jobs as client

SAMPLE = Path(__file__).parent / 'sample_jobs.json'


class ExportJobsTest(unittest.TestCase):
    def test_offline_command_has_no_token_or_network_and_preserves_records(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'jobs.csv'
            with patch.dict(client.os.environ, {}, clear=True), patch.object(client, 'build_opener') as network, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(client.main(['--from-json', str(SAMPLE), '--output', str(output)]), 0)
            network.assert_not_called()
            self.assertTrue(output.read_bytes().startswith(b'\xef\xbb\xbf'))
            with output.open(encoding='utf-8-sig', newline='') as handle:
                rows = list(csv.DictReader(handle))
            original = json.loads(SAMPLE.read_text())
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['descriptionText'], original[0]['descriptionText'])
            self.assertEqual(rows[0]['departments'], 'Engineering; Data')
            self.assertEqual(rows[1]['title'], "'" + original[1]['title'])
            self.assertEqual(rows[0]['jobUrl'], original[0]['jobUrl'])

    def test_hosted_request_is_one_post_with_private_auth_and_server_filters(self):
        payload = client.make_input(['anthropic'], title='engineer', description='python', only_new=True)
        with patch.object(client, 'build_opener') as factory:
            opener = factory.return_value
            opener.open.return_value.__enter__.return_value = io.BytesIO(SAMPLE.read_bytes())
            rows = client.run_actor(payload, 'synthetic-test-token', Decimal('0.02'))
        self.assertEqual(len(rows), 2)
        opener.open.assert_called_once()
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-test-token')
        self.assertNotIn('synthetic-test-token', request.full_url)
        self.assertEqual(parse_qs(urlparse(request.full_url).query)['maxTotalChargeUsd'], ['0.02'])
        self.assertEqual(json.loads(request.data)['descriptionContains'], 'python')
        self.assertTrue(json.loads(request.data)['includeDescription'])
        self.assertTrue(json.loads(request.data)['onlyNew'])
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 150)
        self.assertIs(factory.call_args.args[0], client.NoRedirect)
        self.assertIsNone(client.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))

    def test_interrupted_paid_post_is_not_retried(self):
        with patch.object(client, 'build_opener') as factory:
            factory.return_value.open.side_effect = socket.timeout('synthetic timeout')
            with self.assertRaises(socket.timeout):
                client.run_actor(client.make_input(['anthropic']), 'synthetic-test-token', Decimal('0.02'))
            factory.return_value.open.assert_called_once()

    def test_invalid_amount_or_board_never_starts_a_request(self):
        for value in ['0', '-1', 'NaN', 'Infinity', 'bad']:
            with self.assertRaises(client.argparse.ArgumentTypeError):
                client.positive_usd(value)
        with patch.object(client, 'build_opener') as network:
            with self.assertRaises(ValueError):
                client.make_input(['https://example.com/board'])
            with self.assertRaises(ValueError):
                client.run_actor(client.make_input(['anthropic']), '', Decimal('0.02'))
            network.assert_not_called()

    def test_history_is_stable_and_separated_by_filters(self):
        a = client.make_input(['anthropic'], description='python')
        self.assertEqual(a['stateKey'], client.make_input(['anthropic'], description='python')['stateKey'])
        self.assertNotEqual(a['stateKey'], client.make_input(['anthropic'], description='java')['stateKey'])
        self.assertNotEqual(a['stateKey'], client.make_input(['another-board'], description='python')['stateKey'])

    def test_invalid_dataset_does_not_overwrite_a_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'existing.csv'
            output.write_text('keep existing data')
            with self.assertRaises(ValueError):
                client.write_csv({'error': 'not a dataset'}, output)
            self.assertEqual(output.read_text(), 'keep existing data')

    def test_formula_like_cells_are_prefixed(self):
        for value in ['=1+1', '\u2003=1+1', '\ufeff+1', '@SUM(1)', '\ttext', '＝formula']:
            self.assertEqual(client.spreadsheet_cell(value), "'" + value)
        self.assertEqual(client.spreadsheet_cell('Backend Engineer'), 'Backend Engineer')


if __name__ == '__main__':
    unittest.main()
