"""CSV intake, qualification, LLM review, ranking and sales reporting."""
import csv
import hashlib
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter, sleep
from .scoring import FIELDS, score_lead
from .llm import LLMError


def load_leads(path):
    with open(path, encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('Missing or duplicate CSV headers')
        missing = set(FIELDS) - set(reader.fieldnames)
        if missing:
            raise ValueError('Missing CSV columns: ' + ', '.join(sorted(missing)))
        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError('CSV row has more cells than headers')
        if not rows:
            raise ValueError('CSV has no lead records')
        return rows


def batches(rows, size):
    # Merge a final singleton into the preceding batch; never one API call per lead.
    if len(rows) < 2:
        raise ValueError('At least two leads required for batch processing')
    chunks = [rows[i:i + size] for i in range(0, len(rows), size)]
    if len(chunks) > 1 and len(chunks[-1]) == 1:
        chunks[-2].extend(chunks.pop())
    return chunks


def demo_message(row):
    lead = row['lead']
    asks = ['Would a short workflow discovery conversation be useful?',
            'Would you like a brief demo focused on a workflow you choose?',
            'Is there a repetitive team process you would like to review together?']
    return (f"Hi {lead['name']}, I’m reaching out about {lead['company']} in {lead['industry']}. "
            f"With a team of {lead['company_size']}, your company fits the team size we focus on. "
            'FlowPilot is a workflow automation product. '
            + asks[(row['input_row'] - 2) % 3])


def run(input_path, as_of, mode='demo', batch_size=10, client=None):
    started = perf_counter()
    if not 2 <= batch_size <= 20:
        raise ValueError('batch-size must be between 2 and 20')
    raw = load_leads(input_path)
    rows = [score_lead(r, i + 1, as_of) for i, r in enumerate(raw)]
    seen = set()
    for row in rows:
        identity = tuple(row['lead'][k].casefold() for k in FIELDS)
        if identity in seen:
            row['flags'].append('duplicate_record')
            row['decision'] = row['rule_decision'] = 'review'
            row['reasoning'] += '; duplicate_record'
            row['rejection_reasons'] = []
        seen.add(identity)
    failed_batches = 0
    for batch_number, batch in enumerate(batches(rows, batch_size), start=1):
        if mode == "live" and batch_number > 1:
            logging.info("Waiting 15 seconds before batch %d", batch_number)
            sleep(15)

        if mode == 'demo':
            for row in batch:
                row['llm_status'] = 'not_called_demo'
                row['llm_note'] = 'Offline template; not LLM-generated.'
                if row['decision'] == 'qualified':
                    row['outreach'] = demo_message(row)
            continue
        if mode != 'live' or client is None:
            raise ValueError('Live mode requires an API client')
        try:
            results = client.analyze(batch)
            for row in batch:
                item = results[row['lead_id']]
                row['llm_status'], row['llm_note'] = 'success', item['evidence_note']
                if item['needs_review']:
                    row['flags'].append('llm_requested_review')
                    row['decision'] = 'review'
                if row['decision'] == 'qualified':
                    row['outreach'] = item['message']
        except LLMError as exc:
            failed_batches += 1
            logging.error('Batch failed; routing %d leads to review: %s', len(batch), exc)
            for row in batch:
                row['llm_status'], row['llm_note'] = 'failed', str(exc)
                row['flags'].append('llm_unavailable')
                row['decision'] = 'review'
    queue = sorted((r for r in rows if r['decision'] == 'qualified'),
                   key=lambda r: (-r['score'], r['days_since_interaction'], r['lead_id']))
    for rank, row in enumerate(queue, 1):
        row['priority_rank'] = rank
        row['priority'] = 'high' if row['score'] >= 9 else 'medium'
        row['sequence'] = [
            {'day_offset': 0, 'action': 'Sales rep reviews and approves first-message draft'},
            {'day_offset': 3, 'action': 'If no reply and contact permitted, consider one follow-up'},
            {'day_offset': 7, 'action': 'If no reply, close sequence; stop immediately on opt-out/reply'}]
    counts = Counter(r['decision'] for r in rows)
    rejections = Counter(reason for r in rows if r['decision'] == 'rejected' for reason in r['rejection_reasons'])
    return {'metadata': {'mode': mode, 'as_of': as_of.isoformat(), 'rubric_version': '1.0',
                         'input_file': Path(input_path).name,
                         'input_sha256': hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
                         'generated_at': datetime.now(timezone.utc).isoformat(),
                         'model': client.model if client else None,
                         'api_calls': client.calls if client else 0, 'failed_batches': failed_batches,
                         'elapsed_seconds': round(perf_counter() - started, 4)},
            'stats': {'total_processed': len(rows), **{k: counts[k] for k in ('qualified', 'rejected', 'review')},
                      'qualified_percent': round(100 * counts['qualified'] / len(rows), 2),
                      'common_rejection_reasons': dict(rejections),
                      'flag_counts': dict(Counter(f for r in rows for f in r['flags']))},
            'priority_queue': [r['lead_id'] for r in queue],
            'flagged_leads': [r['lead_id'] for r in rows if r['decision'] == 'review'],
            'disqualified_leads': [r['lead_id'] for r in rows if r['decision'] == 'rejected'],
            'sample_outreach_messages': [{'lead_id': r['lead_id'], 'message': r['outreach']} for r in queue[:5]],
            'leads': rows}


def safe_cell(value):
    text = str(value) if value is not None else ''
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


def write_reports(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Atomic replace per report prevents half-written files on interrupted writes.
    target = output / 'output_report.json'
    temp = target.with_suffix('.json.tmp')
    temp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(target)
    target = output / 'leads_report.csv'
    temp = target.with_suffix('.csv.tmp')
    with temp.open('w', encoding='utf-8', newline='') as handle:
        fields = ['lead_id', *FIELDS, 'score', 'rule_decision', 'decision', 'priority', 'priority_rank', 'reasoning', 'flags', 'llm_status', 'llm_note', 'outreach']
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report['leads']:
            values = {**row, **row['lead'], 'flags': '; '.join(row['flags'])}
            writer.writerow({key: safe_cell(values.get(key)) for key in fields})
    temp.replace(target)
