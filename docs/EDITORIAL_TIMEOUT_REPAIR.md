# Gemini editorial timeout repair — October 8, 2026

Base commit: `901c153177576527d46e80fd95a61f2a96e1e270`.

## Verified failure

[October 8 scheduled run](https://github.com/johnsirmon/daily-ai-docs/actions/runs/37816331225/job/113445798474) passed 1,618 tests, then failed during the editorial draft, before audio generation or publication. The selected provider was Gemini (`gemini-3.8-flash`) through Google's OpenAI-compatible endpoint. The legacy `AI_MODEL` value does not select the editorial provider.

At 17:27:42.998 UTC the request received HTTP 503. After the configured ten-second backoff, the second attempt ended with an SDK `APITimeoutError` caused by a 45-second read timeout at approximately 17:28:38 UTC. The existing policy retried only HTTP 503, so the timeout ended preparation with one permitted attempt unused. [October 7](https://github.com/johnsirmon/daily-ai-docs/actions/runs/37659007980) also ended in an SDK read timeout. These logs establish a retry-policy gap; they do not establish why Gemini was unavailable or how much output it had generated.

The latest receipt reports workflow failure, retaining special episode `adhoc-2026-10-06-c17b23bc738114f59cceba4b`. A read-only check of the subscriber RSS on October 8 found 52 items, headed by that desktop-pets special (publication date October 6 at 23:57:16 UTC). The newest daily item is October 1; the October 3 item is another special. There is no evidence that these failed daily runs generated audio which was then lost from the feed.

## Repair and boundaries

Production uses the already-supported 60-second request timeout. Explicit SDK timeout errors now share the same two-retry ceiling as HTTP 503, with ten- and twenty-second backoffs. SDK automatic retries stay disabled. The model, endpoint, input limit (120,000 characters), draft/verification output limits (4,000/2,500 tokens), low reasoning effort and factual acceptance rules remain unchanged. Generic connection failures, credentials, quota errors and invalid or incomplete output still stop preparation.

Draft and independent verification each allow at most three attempts, six total. A shared 420-second editorial budget prevents new attempts/backoffs after the budget is depleted and caps request timeouts to remaining time. SDK I/O timeouts are not a hard wall-clock cancellation mechanism; late results are rejected by the existing final budget check. Unpublished previews retain their two-request ceiling, and other callers retain the default 45-second timeout and zero service retries.

A timed-out request may already have been processed by the provider. Retries could therefore consume additional provider quota in production, but cannot bypass independent verification or repeat publication: preparation must finish both stages successfully before any audio or feed write. No live model requests, audio generation or publication were performed for this repair.

## Validation and production verification

Offline tests exercise SDK timeouts in either stage, mixed 503/timeouts, opt-in retry ceilings, no retry for generic connection failures, deadline/backoff bounds, six-attempt provenance, and prevention of audio/feed/publication-state writes after exhausted timeouts. Validation completed: 216 focused tests passed; the complete suite passed 1,630 tests in 192.36 seconds. Offline publication validation confirmed 52 retained episodes and valid artwork; README drift and git whitespace checks passed. All model requests were mocked.

This feature branch requires an approved merge before production changes. The next scheduled production run must confirm actual Gemini availability, both editorial stages and delivery checks. This repair does not claim the live daily feed is fixed.
