# Gemini draft truncation repair — October 9, 2026

Base: receipt commit `5e9e931`, after approved timeout repair `3b8aa2c14a5acfaac5724d72a986dc53082bad3d`.

## Observed failure

[Scheduled run](https://github.com/johnsirmon/daily-ai-docs/actions/runs/37963145796/job/113930764235) passed 1,630 tests. Preparation began at 17:03:16 UTC; the Gemini OpenAI-compatible endpoint returned HTTP 200 at 17:04:24.493. The draft call then failed at `pipeline/synthesis.py` with `finish_reason=length`. Independent verification, audio, release and feed publication did not run. The failure receipt at 17:04:24.980 retains the desktop-pets special as last episode.

Production did not explicitly configure `max_output_tokens`, so the draft used 4,000 tokens. Its output includes narration (600–1,100 target words), story summaries, claim text and exact quotations, and potentially research-review fields. The failure establishes exhausted output allowance, not a timeout or insufficient news. The provider response body and token usage were not logged; the exact visible-output/reasoning split and source packet size cannot be reconstructed. Google's [compatibility documentation](https://ai.google.dev/gemini-api/docs/openai) documents low reasoning effort, already supplied by this client. This repair does not change thinking parameters or claim that reasoning caused this incident.

## Bounded correction

Set production draft `max_output_tokens: 6000`, the existing validated ceiling, providing 50% more allowance for structured output. The global ceiling and non-production 4,000-token default remain unchanged. Verification remains 2,500 tokens. Model, endpoint, low reasoning effort, 60-second timeout, shared 420-second budget, attempt ceilings, spoken-word targets and factual verification remain unchanged.

Incomplete responses still fail closed, including syntactically valid JSON marked `length`. No continuation, retry for truncation, token auto-escalation or provider fallback is introduced. Add incomplete-response diagnostics containing only known finish reasons, requested output allowance and bounded integer usage counters when provided; no response text, credentials or provider exception bodies are logged.

A larger requested allowance can permit higher production token usage; no paid or live generation has been performed here. 6,000 tokens may still be insufficient for some responses, and a larger allowance does not guarantee completion within the existing time budget. Actual success requires a reviewed merge and subsequent scheduled production verification.

## Validation

Offline fixtures cover production draft/verification limits, independent verification, truncation in either stage with and without usage data, no truncation retries, rejection of even valid partial JSON, and exclusion of untrusted diagnostic values. Existing timeout and preview limits remain covered. Validation passed: 174 focused tests and all 1,636 repository tests (168.17 seconds), offline publication validation (52 retained episodes), README drift and whitespace checks. No audio or feed content is changed.

The default sandbox process launcher reported a setup-refresh error; the authorized escalated execution path succeeded, allowing edits and tests to continue. No remaining environment blocker was observed.
