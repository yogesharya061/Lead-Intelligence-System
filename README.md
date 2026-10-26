# Lead Intelligence System

Python CLI for explainable lead qualification, batched LLM review, personalized outreach **drafts**, and a ranked sales queue. Runs locally with Python 3.10+; no Docker or pip dependencies.

## Run

```bash
git clone https://github.com/yogesharya061/Lead-Intelligence-System.git
cd Lead-Intelligence-System
python main.py --mode demo --input data/leads_full_scale_100.csv --as-of 2024-01-20
python -m unittest discover -s tests -v
```

For the **required live LLM run**, set `GROQ_API_KEY` in your terminal, then run:

```bash
python main.py --mode live --input data/leads_full_scale_100.csv --as-of 2024-01-20 --output output/live
```

Start with a 5-lead prompt check using `data/prompt_check.csv`. See **[full Windows/VS Code setup and walkthrough](docs/LOCAL_SETUP.md)** for API-key commands, all three datasets, troubleshooting, submission steps, and output interpretation.

## Qualification rubric

Assumed product: FlowPilot, B2B workflow automation for 50–2,000-person organizations, especially software/data businesses. Four factors total 10 points: size (3), industry (3), source engagement (2), and recency (2); scores >=7 qualify, 5–6 require review, and <5 reject, with a minimum displayed score of 1. Missing/invalid/unknown fields require review; complete records below 10 employees or inactive for >365 days reject; LLM concerns or API failure route to review without changing the score ([exact rules](docs/DESIGN.md)).

## Outputs and limits

`output/output_report.json` and `output/leads_report.csv` contain each score, factor explanation, decision, review flags, priority rank, message, aggregate statistics and five message samples where available. JSON includes a suggested day 0/3/7 sequence; nothing is sent. Exit codes: 0 complete, 1 input/output failure, 2 API-degraded report.

[Included 100-lead demo report](examples/full_scale_demo/output_report.json) is **offline**, not evidence of a live API run. Live integration has mocked tests but requires your key and local verification. Historical CSV dates require the explicit demo date above; omitting it uses today and rejects stale leads. No conversion labels exist, so this is rubric evaluation, not trained ML or measured accuracy. Originals are preserved: training actually has **29**, testing 20, scale 100; `leads.csv` supplies 30 unique examples. LLM drafts require human review; model availability, limits and output quality vary.
