import argparse
from datetime import date
import json
import logging
import os
from lead_intelligence.llm import LLMClient
from lead_intelligence.pipeline import run, write_reports


def main():
    parser = argparse.ArgumentParser(description='Batch lead qualification and draft outreach')
    parser.add_argument('--input', default='leads.csv')
    parser.add_argument('--output', default='output')
    parser.add_argument('--mode', choices=['live', 'demo'], default='live')
    parser.add_argument('--as-of', type=date.fromisoformat, default=date.today())
    parser.add_argument('--batch-size', type=int, default=10)
    parser.add_argument('--model', default=os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b'))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    client = None

    if args.mode == 'live':
        key = os.getenv('GROQ_API_KEY', '').strip()
        if not key:
            parser.error('Set GROQ_API_KEY for live mode, or explicitly select --mode demo.')
        client = LLMClient(key, args.model)
    try:
        report = run(args.input, args.as_of, args.mode, args.batch_size, client)
        write_reports(report, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Input/output error: {exc}\n')

    print(json.dumps(report['stats'], indent=2))
    print(f'Reports written to {args.output}; mode={args.mode}')

    return 2 if report['metadata']['failed_batches'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
