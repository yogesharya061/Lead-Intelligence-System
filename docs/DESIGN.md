# Design, assumptions and requirement traceability

## Business problem and proposed policy

The brief describes 1,200 monthly leads with only 60 reached. The remaining 95% is unprocessed volume, not proven lost revenue. Assume a fictional B2B workflow automation product, FlowPilot, with an ideal customer size of 50–2,000. Qualification means worth a sales discovery conversation, not known budget or purchase intent. Size is fit, never a claim about budget. Source is a weak engagement proxy; it does not establish consent to contact.

There are no outcome labels, so no model training, train/test accuracy, or claimed conversion uplift. The supplied “training” set is for rubric development. Validate consistency with boundary tests and ask a sales owner to review representative decisions.

## Exact rubric v1.0

| Factor | Points | Rule |
|---|---|---|
| Company size | 0–3 | 50–2000: 3; 10–49 or 2001–5000: 1; other positive sizes: 0 |
| Industry | 0–3 | Core software/data: 3; adjacent operational businesses: 2; other known industries: 0 |
| Source | 0–2 | Inbound demo/referral: 2; sales call/webinar: 1; download/LinkedIn: 0 |
| Recency | 0–2 | 0–30 days: 2; 31–90: 1; >90: 0 |

Exact category sets live in `lead_intelligence/scoring.py` (`CORE`, `ADJACENT`, `OTHER`, `SOURCES`). Case and outer whitespace are normalized. Unmapped categories are review, not silently classified. Sum is clamped to a minimum of 1 to satisfy the 1–10 requirement.

Decision precedence:
1. Missing, malformed or unknown fields, future dates, and duplicate records → review.
2. Otherwise company size <10 or recency >365 days → reject.
3. Otherwise score >=7 → qualified, 5–6 → review, <5 → rejected.
4. LLM may request review of any record, but cannot qualify/reject or change arithmetic. API failure routes the entire affected batch to review. `rule_decision` preserves the original result.

Qualified leads rank by descending score, then shortest age, then stable input ID. Scores 9–10 are high priority, 7–8 medium. Other rows have null rank and priority. Duplicates are retained, with later exact normalized copies flagged; this is not fuzzy entity resolution. A malformed CSV structure fails clearly rather than silently shifting columns.

## Architecture

CSV intake → normalize/validate → deterministic score → batches of 10 → LLM evidence review + qualified draft → response validation → rank → JSON/CSV.

- `scoring.py`: business policy and field validation.
- `llm.py`: prompt, Groq HTTP integration, output contract, bounded retries.
- `pipeline.py`: batching, human-review routing, outreach sequence, export.
- `main.py`: CLI and environment configuration.
- `tests/test_system.py`: business, transport and reporting tests.

Use 2–20 records per batch; a final singleton joins the previous batch (maximum 21). One-record files fail rather than making a one-lead API call. For 100 leads/default size, 10 initial calls; retries add calls. API payload contains lead data and rubric results, never local paths or secrets. Validated output must cover every ID exactly once, contain boolean review flags, and provide bounded personalized messages for qualified leads. A model cannot return outreach for review/rejected records. Invalid batches retry as a unit, then go to review.

HTTP 408/429/5xx and transport failures retry up to three attempts, exponential backoff with jitter, honoring Retry-After. Waits beyond 120 seconds fail the batch for later rerun. Authentication/other permanent HTTP errors do not retry within the batch. Logs contain counts/status, not API keys or payloads. Each output file uses atomic replacement, but the two-file report is not a transactional bundle. Do not run concurrent processes into the same output directory.

## Outreach and human loop

Friendly, concrete, low-pressure language. Three suggested approaches: workflow discovery, short demo invitation, process review. Mention company and industry; do not fabricate needs, ROI, budget, prior contact, or permission. Day 0 review draft, day 3 consider follow-up if permitted and no reply, day 7 close if no reply. Timing is relative to an actual approved send, not the historical scoring date. No email address is supplied and there is no sender integration. Human approval is necessary; semantic hallucinations cannot be fully eliminated by structural checks.

## Source-data audit

Original CSV files are byte-preserved in `data/`. The supplied instruction documents are not redistributed in this public repository; the implementation requirements are summarized here. Training has 29 rows despite the supplied notes claiming 30. `leads.csv` adds the first distinct full-scale record to those 29; no invented label or altered original. The datasets overlap, so their totals are not counts of unique people. `data/prompt_check.csv` contains five training records for inexpensive prompt testing. Demo date is explicitly 2024-01-20; actual usage defaults to current local calendar date. No dates are rewritten.

## Requirements mapped to evidence

| Brief requirement | Implementation/evidence |
|---|---|
| CLI and CSV intake | `main.py`, `load_leads` |
| 3–5 factors, 1–10 score | Four-factor `scoring.py` and boundary tests |
| LLM API + batches | `LLMClient`, `batches`, mocked 100-lead test |
| Failure/rate-limit handling | HTTP retry tests and review routing |
| Missing fields and ambiguity | Flags, testing CSV, decision precedence |
| 30 diverse sample leads | Root `leads.csv` |
| 100 leads without intervention | `examples/full_scale_demo/`; live command in setup guide |
| Decisions/reasoning/rank/stats | Both reports; JSON includes full factor breakdown |
| 3–5 outreach samples and sequence | JSON samples and per-qualified-lead sequence |
| Short README + full implementation guide | Root README and `docs/LOCAL_SETUP.md` |

## Validation limits

Included outputs are generated in offline demo mode. API calls, malformed responses, retries and failures are simulated in automated tests. No live LLM output or live latency/cost has been measured in this environment. For assignment submission, run the five-lead live prompt check, review it, then run 100 live leads and include that report. Do not submit an offline report as an LLM-generated result.

Provider references used for the adapter: [Groq API reference](https://console.groq.com/docs/api-reference), [rate limits](https://console.groq.com/docs/rate-limits), [JSON response formats](https://console.groq.com/docs/structured-outputs). Model and account limits can change; configure `--model` or `GROQ_MODEL`.
