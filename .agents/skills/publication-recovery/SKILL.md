---
name: publication-recovery
description: >
  Diagnose and safely recover Daily AI Developer Brief publication incidents.
  Use for failed publisher runs, stale-feed alarms, pending candidates, release
  mismatches, reviewed-audio retries, Pages failures, or publication branch integration.
---

# Publication recovery

Recover by evidence and stage. Diagnosis is read-only; workflow dispatch, release creation,
pushes, publication, rollback, and state changes require explicit authorization.

## Establish the incident identity

1. Read `docs/OPERATIONS.md`, especially failure recovery, before acting. Inspect the
   current workflow file rather than relying on remembered step names.
2. Record the repository, branch, commit, workflow run ID/attempt, event, and conclusion.
   Use `gh run view <id> --json ...` and `gh run view <id> --log-failed`.
3. Identify the expected episode ID and gather only its relevant evidence:
   - release tag and asset metadata;
   - `.cache/publication.json` when locally available;
   - `data/episodes/<episode>.json`;
   - `data/receipts/<episode>.json`;
   - `data/runs/latest.json` and `data/state.json`;
   - subscriber-facing feed GUID and enclosure.
   For schema 4, also gather the embedded request/revision, current issue authorization
   when applicable, `data/requests/<request-id>.json`, and the request-local status.
4. Treat workflow success, release existence, candidate commit, Pages deployment,
   delivery confirmation, and freshness as separate states. Do not infer a later state
   from an earlier one.

## Classify before choosing an action

- Collection/source health: distinguish a healthy empty result from an outage before
  fixing or retrying the collector.
- Editorial provider: use the bounded HTTP/error category. A provider outage is not a
  prompt defect; do not weaken validators or silently fall back.
- Grounding/schema: use rejected claim IDs, schema errors, and safe diagnostics to
  correct evidence, prompt, or contract before unpublished validation.
- TTS/media validation: preserve the original and use local probe/decode evidence. Fix
  failures before creating a release.
- Existing release reconciliation: compare the exact tag, asset names, bytes, and
  manifest identity. Never regenerate or upload with `--clobber`.
- Candidate generation/commit: rebuild from the accepted release and current production
  history without advancing novelty state.
- Pages/deployment: retry deployment or recovery from current `main` while retaining
  publisher serialization.
- Subscriber delivery: verify latest GUID, enclosure, HEAD/range, checksum, and artwork
  before confirmation.
- Freshness monitoring: use the last run receipt and latest confirmed episode. Keep it
  separate from exact-candidate recovery and do not relax the 25-hour monitor.

## Exact identity checklist

Before candidate writes or confirmation, require all applicable values to agree:

- episode ID, release tag, GUID, and enclosure URL;
- manifest schema and status transition;
- audio byte length and SHA-256 exactly;
- full media decode and duration budget;
- reviewed-audio input/transcript/correction hashes for schemas 3 and 4;
- schema-4 request revision/hash, requested provider and voice provenance, and
  final-byte-bound mastering report;
- publication timestamp and accepted candidate identity;
- subscriber-visible latest GUID, enclosure, range support, checksum, and artwork.

FFprobe duration may use only the repository's tested MP3-frame-sized tolerance. It
never permits replacing released bytes or relaxing checksum identity.

## Schema-4 special recovery

1. Read the request from the stored manifest, not a newly generated request. Recheck
   current write permission and the exact open issue revision, or the authorizing actor
   for local requests. Closed/edited issues, revoked permission, or preview-only intent
   block publication; do not edit authorization fields in an existing bundle.
2. Ad-hoc transport releases may still be drafts. The shared publisher validates and
   authorizes them before promotion; schema-3 daily imports require public releases.
   After upload/dispatch failure, dispatch `update-radar.yml` on current `main` with
   the same `reviewed_episode` tag only when recovery is authorized.
3. Resume immutable manifest/MP3 bytes. Require a finite positive duration plausible for the reviewed
   transcript, exact hashes, and re-measured loudness/peak acceptance, not a fixed minute range. Follow
   [audio-production-review](../audio-production-review/SKILL.md) for media gates;
   never remaster an existing release to make recovery pass.
4. Confirm both the episode delivery receipt and `data/requests/<request-id>.json`.
   An intake comment, draft release, or local `publishing` status is not completion.
   Refresh production history before using `pipeline.adhoc status`.
5. Inspect feed-head state separately from `last_daily_episode_id`,
   `last_daily_publication`, and the daily evaluation receipt. A confirmed special
   must not consume the daily slot or mask failed/stale daily evaluation. Do not
   hand-edit state or create a request receipt to repair an interrupted confirmation;
   use the existing idempotent confirmation path.

## Targeted reproduction

Use CI's interpreter and locked dependencies. Begin with the tests matching the stage:

```sh
uv run --python 3.11 --with-requirements requirements.lock python -m pytest -q \
  tests/test_recovery.py tests/test_reviewed_delivery.py tests/test_publish.py \
  tests/test_audio.py tests/test_podcast.py tests/test_daily.py \
  tests/test_adhoc.py tests/test_audio_quality.py
```

Use temporary-directory fixtures and mocked HTTP/provider sessions. Never regenerate
historical manifests or media as a test. On success run the complete repository gate.

## Safe integration with publication history

1. Fetch remote refs and identify the actual production tip; local branch names may be stale.
2. Preserve user-authored commits and separate code changes from generated publication
   commits. Inspect `README.md`, `podcast.xml`, episode manifests, state, receipts, and run
   receipts individually.
3. Integrate against current production history. Never blindly rebase generated feed
   changes or resolve them as ordinary text conflicts.
4. All publisher workflows must retain the shared `podcast-publisher` concurrency group
   with `cancel-in-progress: false`. Actions concurrency is not FIFO.
5. After recovery, read back the exact release/feed/receipt target before claiming success.

## Completion report

State the incident identity, classified stage, immutable evidence checked, command or
workflow used, targeted/full test results, public delivery result, freshness result, and
any remaining owner action. If no external action was authorized, stop at a precise
recovery recommendation.
