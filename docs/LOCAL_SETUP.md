# Local implementation guide (Windows / VS Code)

## 1. Get the code

Install Python 3.10 or later with Python on PATH and Git. Open VS Code → Terminal → New Terminal (PowerShell).

```powershell
git clone https://github.com/yogesharya061/Lead-Intelligence-System.git
cd Lead-Intelligence-System
py --version
py -m venv .venv
.\.venv\Scripts\python.exe --version
```

If already cloned, enter the folder and run `git pull --ff-only` first. No activation or PowerShell execution-policy change is needed. Select `.venv\Scripts\python.exe` through VS Code's Python interpreter selector. No pip dependencies or Docker are required.

On macOS/Linux, use `python3 -m venv .venv` then `.venv/bin/python` instead of the Windows executable below.

## 2. Run offline first

```powershell
.\.venv\Scripts\python.exe main.py --mode demo --input leads.csv --as-of 2024-01-20 --output output/demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Open the JSON and CSV in `output/demo`. Offline messages are deterministic templates and clearly marked `not_called_demo`. This validates local setup without an account or API charges; it does not satisfy the LLM requirement by itself.

## 3. Configure a live LLM

Create your own Groq API key in the [Groq console](https://console.groq.com/keys). Check your account's available models and usage limits. In the same PowerShell terminal, enter the key without echoing it:

```powershell
$secret = Read-Host "Groq API key" -AsSecureString
$env:GROQ_API_KEY = [System.Net.NetworkCredential]::new("", $secret).Password
$env:GROQ_MODEL = "openai/gpt-oss-20b"
```

On macOS/Linux:

```bash
read -s -p 'Groq API key: ' GROQ_API_KEY; echo
export GROQ_API_KEY
export GROQ_MODEL=openai/gpt-oss-20b
```

The `.env.example` file documents variable names only; the application does not auto-load `.env`. Do not paste your key into Python files, reports, git commits or screenshots. Live mode sends the selected lead records to Groq. Use approved data; the included files are assignment samples.

## 4. Test the prompt on five leads

```powershell
.\.venv\Scripts\python.exe main.py --mode live --input data/prompt_check.csv --as-of 2024-01-20 --output output/prompt_check
$LASTEXITCODE
```

Check `metadata.mode=live`, `failed_batches=0`, and each record's `llm_status=success`. Review message specificity, tone, factual accuracy and review flags. If you refine the prompt, edit `SYSTEM` in `lead_intelligence/llm.py`, rerun tests, then repeat this check before scaling. Never adjust rules solely to get a desired percentage.

## 5. Develop → edge cases → full-scale run

```powershell
.\.venv\Scripts\python.exe main.py --mode live --input data/leads_training.csv --as-of 2024-01-20 --output output/training
.\.venv\Scripts\python.exe main.py --mode live --input data/leads_testing.csv --as-of 2024-01-20 --output output/testing
.\.venv\Scripts\python.exe main.py --mode live --input data/leads_full_scale_100.csv --as-of 2024-01-20 --batch-size 10 --output output/full_scale
```

Each command makes new API calls and may incur usage charges. Testing data is expected to produce review/rejection decisions; these are not software failures. For new current leads, omit `--as-of` to use today. The 2024 demo date exists only because the supplied data is historical.

## 6. Read the sales report

- `stats`: processed count, qualified/rejected/review counts, qualified percentage, rejection reasons and flag counts.
- `priority_queue`: qualified lead IDs in outreach order. Match IDs against `leads` for details.
- `flagged_leads`: manual-review queue. Correct source data or investigate missing facts, then rerun into a new output folder.
- `score`, `factor_scores`, `rule_decision`: reproducible policy result.
- `decision`, `flags`, `llm_note`: final result after LLM review or API failure.
- `outreach`, `sequence`: first-message draft and suggested relative follow-up actions; never automatic sends.
- `metadata`: mode, model, input hash, as-of date, elapsed seconds, API call count and failed batches.

JSON is the full-fidelity report. CSV is a flat sales worksheet; cells beginning with formula markers are prefixed with an apostrophe for safer spreadsheet viewing. Qualified percentage is a rubric output, not conversion prediction or accuracy.

## 7. Demonstrate and submit

Explain the assumed product and four-factor rubric using `docs/DESIGN.md`. Show one qualified, one rejected, and one review lead. Show a 100-lead **live** report with zero failed batches and all 100 LLM statuses successful. Show three to five message examples and the test suite. Record actual runtime from metadata; compare it with the brief's manual baseline of 800–1,200 minutes for 100 leads, without claiming conversion improvement.

For a clean ZIP containing committed source, samples and docs:

```powershell
git archive --format=zip --output=../Lead-Intelligence-System.zip HEAD
```

Add `output/full_scale/output_report.json` and `leads_report.csv` to that ZIP through File Explorer after a successful live run. Exclude `.venv`, `.env`, keys and logs. Committed `examples/` reports are offline reference artifacts and must stay labelled as such.

## Troubleshooting

| Symptom | Action |
|---|---|
| `python` not found | Use `py` on Windows or reinstall Python with PATH enabled |
| Missing API key | Set the environment variable in the same terminal; use explicit demo mode for offline tests |
| HTTP 401/403 | Verify key/account permissions; permanent errors do not retry within a batch |
| HTTP 400/404 | Check model availability and JSON-mode support; use `--model MODEL_ID` |
| HTTP 429 | Bounded retries honor Retry-After; wait for account quota reset if exhausted |
| Invalid API response | Review flags preserve all rows; retry with a smaller batch (minimum 2) or another supported model |
| Exit code 2 | Reports exist but at least one batch failed; fix the cause and rerun before submitting |
| Most leads stale/rejected | Use `--as-of 2024-01-20` for this historical assignment data |
| CSV missing columns | Preserve the six exact header names; inspect extra delimiters or malformed rows |
| Cannot write CSV | Close the file in Excel or choose a different output directory |

Retries can incur additional usage. The tool has no checkpoint/resume cache; rerunning repeats the whole file. It is a mini-project, not a production CRM, delivery engine or trained conversion model.
