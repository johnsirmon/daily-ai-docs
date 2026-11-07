# Editorial attempt diagnostics - October 12, 2026

## Verified incident

The October 12 scheduled publisher run 38300096387 passed 1,630 tests, then failed during
preparation with an HTTP 503 and a typed SDK timeout. Release, candidate, Pages, delivery and
confirmation steps were skipped. Current production base is `1c82af8`; the run's recorded
head SHA is `a320846e4d307ca013bc81f5c0e04f8230361e45`.

The already-deployed timeout repair allows three attempts per stage, ten/twenty-second
backoffs, a sixty-second I/O timeout, disabled SDK retries and a shared 420-second budget.
The observed failure ends at that boundary. Existing logs do not identify every attempt,
so they do not support blaming an unused retry or claiming the provider is repaired.

## Change and limits

Add stage, attempt/ceiling, effective timeout, safe transport-error category, backoff and
terminal-reason logs. Successful transport is explicitly distinct from editorial acceptance.
Only allowlisted stages and bounded HTTP status values are logged; exception text, prompts,
provider content, credentials and source data are excluded. No persisted schema changes.
Retry policy, provider/model, output budgets, independent verification, factual acceptance
and publication behavior remain unchanged. This makes future failures diagnosable; it does
not establish or restore Gemini availability. No live generation or publication was run.

## Separate findings

- Existing branch `fix/gemini-editorial-output-budget` remains at `89bc7bd` and is not merged
  into this repair. It raises only configured draft headroom from 4,000 to 6,000 tokens and
  adds sanitized usage counters for incomplete output. It plausibly addresses truncation,
  not the October 12 transport failure; no verified CI or production result was available.
- October 10 run 38065381688 rejected quantity 529 in `what_changed` after HTTP 200.
  October 11 run 38154989873 rejected quantity 10698 in `claim.text` after HTTP 200.
  No artifacts were listed for either run. Without the exact sanitized proposed claim and
  its supporting evidence, logs cannot distinguish fabricated quantities from normalization
  mismatches. Validation stays intact; fresh source collection would not reproduce historical
  evidence reliably.
- YouTube artifact 11708651417 from run 38156426545 reports 48 candidates, 48 transcript
  attempts, zero successes and 48 `transcript_error` drops. It lacks typed error detail;
  no bounded adapter repair is justified by that evidence alone. The prior digest is retained.

## Validation

New regressions cover mixed 503/timeout recovery in both stages, mandatory independent
verification, safe terminal classifications, unknown status/stage sanitization and unchanged
attempt ceilings. Existing timeout tests cover deadline and prevention of publication writes.
The Windows sandbox cannot create pytest fixtures reliably; use the existing Python 3.11
interpreter with an absolute host temporary directory. Report only the successful host gate
as validation, separately from sandbox fixture errors.

Approval needed after review: merge the diagnostics PR if desired. Production verification
requires a later successful scheduled run through independent verification and delivery.
Any manually requested generation/recovery remains a separate owner decision. Assess the
output-budget patch independently before approving its integration.

Final validation: 16 focused tests passed; full final suite passed 1,635 tests in 173.17 seconds.
The prior full gate passed 1,634 tests before the last budget-stop test was added. Offline
publication validation retained 52 episodes and valid 3000x3000 RGB artwork; README drift,
compilation and git whitespace checks passed. The separate output-budget checkout passed
its six regression tests. No production generation or publication was performed.
