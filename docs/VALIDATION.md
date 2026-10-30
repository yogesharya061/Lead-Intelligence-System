# Validation results

Executed 2026-10-31 in the workspace using Python standard-library `unittest`.

- 21 tests passed.
- Original datasets processed: 29 development, 20 edge-case, 100 full-scale.
- 100-lead offline demo: 56 qualified, 19 rejected, 25 review.
- 20-lead offline edge-case demo: 7 qualified, 6 rejected, 7 review.
- Mock live pipeline: 100 leads in 10 batch calls.
- HTTP 429 retry, permanent authentication failure, transport exhaustion, malformed JSON, response ID/schema checks, correction feedback after validation failures, 15-second inter-batch pacing, score boundaries, CSV roundtrip, duplicate handling and formula escaping tested.
- Live external LLM call: NOT executed; requires a user-provided Groq API key.

These counts describe the documented rubric on the explicit 2024-01-20 reference date, not ground truth. Simulated API tests are not evidence of provider availability or real message quality. Run the live prompt check and full-scale command in LOCAL_SETUP.md before final assignment submission.
