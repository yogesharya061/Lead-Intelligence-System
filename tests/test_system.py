import csv
from datetime import date
from email.message import Message
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from lead_intelligence.scoring import score_lead
from lead_intelligence.llm import LLMClient, LLMError, validate_response
from lead_intelligence.pipeline import run, batches, demo_message, write_reports, load_leads, safe_cell

AS_OF = date(2024, 1, 20)
BASE = dict(name='Alice', company='Example Co', company_size='100', industry='SaaS', source='Inbound demo request', last_interaction_date='2024-01-20')


def scored(**overrides):
    return score_lead({**BASE, **overrides}, 1, AS_OF)


def payload(batch):
    return {'leads': [dict(lead_id=r['lead_id'], needs_review=False,
                           evidence_note='Company size and industry match stated target.',
                           message=demo_message(r) if r['decision'] == 'qualified' else '') for r in batch]}


class FakeClient:
    model = 'test-double'
    calls = 0
    def analyze(self, batch):
        self.calls += 1
        return validate_response(payload(batch), batch)


class SystemTests(unittest.TestCase):
    def test_top_score(self):
        row = scored()
        self.assertEqual((row['score'], row['decision']), (10, 'qualified'))

    def test_size_boundaries(self):
        for size, points in [(9, 0), (10, 1), (49, 1), (50, 3), (2000, 3), (2001, 1), (5000, 1), (5001, 0)]:
            self.assertEqual(scored(company_size=str(size))['factor_scores']['company_size'], points)
        self.assertEqual(scored(company_size='9')['decision'], 'rejected')

    def test_recency_boundaries(self):
        from datetime import timedelta
        for days, points in [(0, 2), (30, 2), (31, 1), (90, 1), (91, 0), (365, 0), (366, 0)]:
            row = scored(last_interaction_date=(AS_OF - timedelta(days=days)).isoformat())
            self.assertEqual(row['factor_scores']['recency'], points)
            if days == 366:
                self.assertEqual(row['decision'], 'rejected')

    def test_missing_invalid_future(self):
        for change in [dict(company_size='NA'), dict(company_size='-2'), dict(name=''), dict(industry='mystery'), dict(source='?'), dict(last_interaction_date='bad'), dict(last_interaction_date='2025-01-01')]:
            self.assertEqual(scored(**change)['decision'], 'review')

    def test_score_thresholds(self):
        self.assertEqual(scored(industry='Agriculture')['score'], 7)
        self.assertEqual(scored(industry='Agriculture', source='Content download')['decision'], 'review')
        self.assertEqual(scored(industry='Agriculture', source='Content download', company_size='20')['decision'], 'rejected')

    def test_singleton_merge(self):
        self.assertEqual([len(x) for x in batches(list(range(21)), 10)], [10, 11])
        with self.assertRaises(ValueError):
            batches([1], 10)

    def test_all_datasets(self):
        for name, count in [('leads_training', 29), ('leads_testing', 20), ('leads_full_scale_100', 100)]:
            result = run(f'data/{name}.csv', AS_OF)
            self.assertEqual(result['stats']['total_processed'], count)
            self.assertEqual(sum(result['stats'][k] for k in ('qualified', 'review', 'rejected')), count)
            self.assertTrue(all(1 <= r['score'] <= 10 for r in result['leads']))
            ranks = [r['priority_rank'] for r in result['leads'] if r['decision'] == 'qualified']
            self.assertEqual(sorted(ranks), list(range(1, len(ranks) + 1)))

    def test_live_mock_batches(self):
        client = FakeClient()
        result = run('data/leads_full_scale_100.csv', AS_OF, 'live', 10, client)
        self.assertEqual(client.calls, 10)
        self.assertEqual(len(result['sample_outreach_messages']), 5)
        self.assertTrue(all(r['llm_status'] == 'success' for r in result['leads']))

    def test_failure_routes_to_review(self):
        client = FakeClient()
        with patch.object(client, 'analyze', side_effect=LLMError('offline')):
            result = run('data/leads_testing.csv', AS_OF, 'live', 10, client)
        self.assertEqual(result['stats']['review'], 20)
        self.assertEqual(result['metadata']['failed_batches'], 2)
        self.assertFalse(result['priority_queue'])

    def test_response_contract(self):
        batch = [scored()]
        good = payload(batch)
        self.assertIn('L0001', validate_response(good, batch))
        for bad in [{}, {'leads': []}, {'leads': good['leads'] * 2}, {'leads': [{**good['leads'][0], 'needs_review': 'false'}]}, {'leads': [{**good['leads'][0], 'message': 'Generic hello'}]}]:
            with self.assertRaises(ValueError):
                validate_response(bad, batch)

    def test_http_retry(self):
        batch = [scored()]
        headers = Message()
        headers['Retry-After'] = '0'
        error = HTTPError('https://example.test', 429, 'limited', headers, None)
        response = io.BytesIO(json.dumps({'choices': [{'message': {'content': json.dumps(payload(batch))}}]}).encode())
        client = LLMClient('fake', 'fake')
        with patch('lead_intelligence.llm.urlopen', side_effect=[error, response]), patch('lead_intelligence.llm.time.sleep') as sleep:
            self.assertIn('L0001', client.analyze(batch))
        self.assertEqual(client.calls, 2)
        sleep.assert_called_once_with(0)

    def test_auth_not_retried(self):
        error = HTTPError('https://example.test', 401, 'auth', Message(), None)
        client = LLMClient('fake', 'fake')
        with patch('lead_intelligence.llm.urlopen', side_effect=error):
            with self.assertRaises(LLMError):
                client.analyze([scored()])
        self.assertEqual(client.calls, 1)

    def test_network_exhaustion(self):
        client = LLMClient('fake', 'fake')
        with patch('lead_intelligence.llm.urlopen', side_effect=URLError('offline')), patch('lead_intelligence.llm.time.sleep'):
            with self.assertRaises(LLMError):
                client.analyze([scored()])
        self.assertEqual(client.calls, 3)

    def test_bad_json_retries(self):
        client = LLMClient('fake', 'fake', attempts=2)
        with patch('lead_intelligence.llm.urlopen', side_effect=lambda *a, **k: io.BytesIO(b'not json')), patch('lead_intelligence.llm.time.sleep'):
            with self.assertRaises(LLMError):
                client.analyze([scored()])
        self.assertEqual(client.calls, 2)

    def test_report_roundtrip(self):
        report = run('data/leads_full_scale_100.csv', AS_OF)
        with tempfile.TemporaryDirectory() as folder:
            write_reports(report, folder)
            self.assertEqual(json.loads((Path(folder) / 'output_report.json').read_text())['stats']['total_processed'], 100)
            with (Path(folder) / 'leads_report.csv').open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 100)
        self.assertEqual(safe_cell(' =SUM(A1)'), "' =SUM(A1)")

    def test_bad_csv_and_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.csv'
            path.write_text('wrong\nvalue\n')
            with self.assertRaises(ValueError):
                load_leads(path)
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(BASE))
                writer.writeheader()
                writer.writerows([BASE, BASE])
            result = run(path, AS_OF)
            self.assertIn('duplicate_record', result['leads'][1]['flags'])
            self.assertEqual(result['leads'][1]['decision'], 'review')


if __name__ == '__main__':
    unittest.main()
