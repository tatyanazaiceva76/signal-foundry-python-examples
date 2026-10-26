import argparse
import csv
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import export_contacts as client


class ExportTests(unittest.TestCase):
    def test_budget_and_token_stay_in_the_correct_parts_of_one_request(self):
        calls = []

        def receive(request, **options):
            calls.append((request, options))
            return io.BytesIO(b'[]')

        with patch.object(client, 'urlopen', side_effect=receive):
            self.assertEqual(client.run_actor(['example.com/contact'], 'dummy-secret', Decimal('0.03')), [])
        self.assertEqual(len(calls), 1)
        request, options = calls[0]
        self.assertNotIn('dummy-secret', request.full_url)
        self.assertEqual(request.get_header('Authorization'), 'Bearer dummy-secret')
        self.assertIn('maxTotalChargeUsd=0.03', request.full_url)
        self.assertEqual(request.method, 'POST')
        self.assertEqual(json.loads(request.data)['websiteUrls'], ['example.com/contact'])
        self.assertFalse(json.loads(request.data)['onlyNew'])
        self.assertEqual(options['timeout'], 150)

    def test_ambiguous_timeout_never_resubmits_a_paid_post(self):
        with patch.object(client, 'urlopen', side_effect=TimeoutError('Interrupted')) as send:
            with self.assertRaises(TimeoutError):
                client.run_actor(['example.com'], 'dummy-secret', Decimal('0.03'))
            self.assertEqual(send.call_count, 1)

    def test_untrusted_formulas_and_international_contacts_stay_in_separate_csv_cells(self):
        rows = [{'websiteUrl': 'https://example.com/', 'pageUrl': 'https://example.com/contact',
                 'pageTitle': ' =HYPERLINK("https://example.org")',
                 'emails': ['hello@example.com', 'support@example.com'], 'phones': ['+4930123456'],
                 'socialLinks': ['https://github.com/example']},
                {'pageTitle': 'München 東京', 'emails': [], 'phones': [], 'socialLinks': []}]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'contacts.csv'
            client.write_csv(rows, path)
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            with path.open(encoding='utf-8-sig', newline='') as handle:
                actual = list(csv.DictReader(handle))
        self.assertEqual(len(actual), 2)
        self.assertEqual(actual[0]['emails'], 'hello@example.com; support@example.com')
        self.assertTrue(actual[0]['pageTitle'].startswith("'"))
        self.assertTrue(actual[0]['phones'].startswith("'"))
        self.assertEqual(actual[1]['pageTitle'], 'München 東京')
        self.assertEqual(actual[1]['emails'], '')
        for value in ['=1+2', '+1+2', '-1+2', '@example', '＝1+2', '＋1+2', '－1+2', '＠example', '\t=1+2']:
            self.assertTrue(client.spreadsheet_cell(value).startswith("'"), value)

    def test_offline_conversion_needs_neither_token_nor_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'rows.json', Path(temporary) / 'out.csv'
            source.write_text('[{"pageTitle":"A company","emails":["info@example.com"]}]')
            with patch.dict(client.os.environ, {}, clear=True), patch.object(client, 'urlopen') as send:
                self.assertEqual(client.main(['--from-json', str(source), '--output', str(output)]), 0)
            send.assert_not_called()
            self.assertTrue(output.exists())

    def test_nonpositive_or_nonfinite_budgets_are_not_accepted(self):
        for value in ['NaN', 'Infinity', '-0.01', '0', 'not-a-number']:
            with self.assertRaises(argparse.ArgumentTypeError):
                client.positive_usd(value)

    def test_email_filter_is_sent_before_charging_and_does_not_hide_a_server_mismatch(self):
        def receive(request, **options):
            self.assertTrue(json.loads(request.data)['requireEmail'])
            self.assertIn('build=email-filter-candidate', request.full_url)
            return io.BytesIO(b'[{"emails":[],"socialLinks":["https://github.com/example"]}]')

        with patch.object(client, 'urlopen', side_effect=receive) as send:
            with self.assertRaisesRegex(ValueError, 'without email despite requireEmail'):
                client.run_actor(['example.com'], 'dummy-secret', Decimal('0.03'),
                                 require_email=True, build='email-filter-candidate')
            self.assertEqual(send.call_count, 1)

    def test_email_only_offline_conversion_does_not_start_a_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'rows.json', Path(temporary) / 'out.csv'
            source.write_text(json.dumps([{'pageUrl': 'https://example.com/social', 'emails': []},
                                         {'pageUrl': 'https://example.com/contact', 'emails': ['info@example.com']}]))
            with patch.dict(client.os.environ, {}, clear=True), patch.object(client, 'urlopen') as send:
                self.assertEqual(client.main(['--from-json', str(source), '--require-email', '--output', str(output)]), 0)
            send.assert_not_called()
            with output.open(encoding='utf-8-sig', newline='') as handle:
                actual = list(csv.DictReader(handle))
            self.assertEqual(len(actual), 1)
            self.assertEqual(actual[0]['pageUrl'], 'https://example.com/contact')

    def test_empty_filtered_dataset_still_creates_a_usable_csv_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'empty.csv'
            client.write_csv([], path)
            with path.open(encoding='utf-8-sig', newline='') as handle:
                actual = csv.DictReader(handle)
                self.assertEqual(actual.fieldnames, list(client.FIELDS))
                self.assertEqual(list(actual), [])


if __name__ == '__main__':
    unittest.main()
