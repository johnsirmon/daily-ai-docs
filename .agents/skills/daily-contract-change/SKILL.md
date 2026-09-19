---
name: daily-contract-change
description: >
  Change Daily AI Developer Brief manifests and editorial contracts compatibly.
  Use for schema, prompt, verification, evidence archive, narration, rendering,
  publication, or reviewed-audio provenance changes.
---

# Daily contract change

Treat the episode manifest as the source of truth. Trace every contract field through
its complete lifecycle and preserve compatibility unless a deliberate migration is
specified and tested.

## Identify affected contracts

Classify each change before editing:

- schema 1: legacy/deterministic episodes;
- schema 2: independently drafted and verified grounded editorial episodes;
- schema 3: reviewed Notebook audio with transcript/source review provenance;
- schema 4: request-bound long-form specials with measured mastering and explicit audio-provider provenance.

Do not relabel one contract as another. In particular, reviewed browser audio is not a
two-call Gemini API result, and legacy deterministic output is not a fallback for failed
required editorial mode.

## Trace every changed field

Build a field map covering all applicable stages:

```text
collector/source event
  -> selection/ranking
  -> draft/verification
  -> schema validation
  -> evidence archive
  -> narration/show notes/README
  -> audio/publication metadata
  -> release manifest
  -> candidate feed
  -> delivery receipt/state
  -> recovery read path
```

For each stage, record whether the field is created, normalized, validated, rendered,
hashed, omitted, or required to round-trip. Search all schema versions, serializers,
fixtures, and recovery paths before deleting or renaming a field.

## Evidence and privacy invariants

- Every narrated product claim maps to known source-event IDs and public primary URLs.
- Quantities require claim-local quoted support, not a title or another claim's quote.
- Research retains method, result, limitations, experiment, and the
  author-reported/not-independently-reproduced qualification.
- Full papers and model context may be used transiently but must not enter saved
  manifests. Preserve only bounded supporting excerpts, provenance hashes, and verified
  paraphrases.
- Schemas 3 and 4 preserve exact transcript, input-audio, final-audio, and correction identity
  as required by the reviewed-audio contract.
- Schema 4 also binds the exact request revision, provider/voice settings, and final-byte
  mastering report. Preserve the request receipt and separate daily cadence fields when
  tracing confirmation and recovery. Use
  [audio-production-review](../audio-production-review/SKILL.md) for measured media acceptance.
- Existing episode IDs, GUIDs, enclosure URLs, timestamps, and media checksums remain
  immutable.

## Required scenario matrix

Test the changed contract against:

1. accepted deterministic/legacy serialization and rendering;
2. accepted grounded draft plus independent verification;
3. accepted reviewed-audio import and recovery;
4. thin-news/intentional skip;
5. provider timeout/unavailability with no publication fallback;
6. malformed schema and unknown IDs;
7. unsupported or quantitatively mismatched claim;
8. tampered excerpt, transcript, manifest, media, or archived evidence;
9. old confirmed manifest/release read and repeat recovery;
10. privacy boundary: no full paper, private metadata, raw provider response, or secret;
11. accepted schema-4 preparation, 1200-1800-second media, and unchanged-bundle recovery;
12. changed/closed issue, revoked write permission, wrong actor, or tampered request/provider;
13. preview-only request rejected before candidate or publication writes;
14. mixed-feed confirmation preserving daily cadence/evaluation and creating a request receipt,
    including repeat confirmation after an interrupted request-receipt write;
15. mastering report tampering, checksum mismatch, nonfinite measurements, and out-of-range
    loudness/peak; unchanged defaults for daily audio unless polish is explicitly enabled.

The daily dry-run explicitly disables grounded editorial mode. It is useful, but it does
not satisfy grounded-contract acceptance by itself.

## Focused verification

```sh
uv run --python 3.11 --with-requirements requirements.lock python -m pytest -q \
  tests/test_schema.py tests/test_grounded_editorial.py tests/test_editorial.py \
  tests/test_evidence_archive.py tests/test_selective_publication.py \
  tests/test_reviewed_audio.py tests/test_reviewed_delivery.py \
  tests/test_adhoc.py tests/test_audio_quality.py \
  tests/test_narrate.py tests/test_render.py tests/test_daily.py tests/test_recovery.py
```

Use isolated temporary fixtures and mocked providers. Never regenerate historical
publication artifacts to make tests pass. After focused checks, run the complete suite,
`pipeline.publish_check`, `pipeline.drift_check`, compileall, and `git diff --check`.

## Documentation and migration

Update schema documentation, operating commands, workflow expectations, examples, and
fixtures in the same change. If compatibility cannot be preserved, provide an explicit
migration and rollback boundary; never hand-edit confirmed history as a migration.

## Completion report

List affected schema versions and fields, lifecycle stages inspected, scenario matrix
coverage, focused/full results, compatibility result, privacy result, generated artifacts
changed, and any migration or recovery limitation.
