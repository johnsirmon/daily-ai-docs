---
name: adhoc-podcast
description: >
  Queue, research, review, and publish an operator-assisted long-form podcast on a requested topic.
  Use for ad-hoc specials, publish-now requests, or processing a podcast request issue.
---

# Ad-hoc podcast

Use the current `pipeline.adhoc` commands and `docs/OPERATIONS.md`. Never use the legacy
`pipeline.main --adhoc-topic` publication path.

## Intake

Normalize the user's public topic and audience into `pipeline.adhoc request`, or use
`pipeline.adhoc issue --number N`. Default to 60 days and 20-30 minutes; only an explicit
window override changes recency. Pass `--publish-now` only when the user requested publication.
Both entry points check GitHub write permission. An issue is a queue, not an unattended browser worker.
An edited issue is a changed request and invalidates the earlier authorization.

Keep all source material and media in the request's `.cache/adhoc/<id>/` directory.
Do not overwrite daily staging or clean up an unresolved request.

## Research and outline

1. Freeze the request's UTC evidence window. Discover public primary URLs, then inspect their actual content.
2. Verify original publication dates, not search snippets, page-update timestamps, or an old paper's revision date.
3. Use `source-onboarding` retrieval boundaries and `evidence-led-review` claim worksheets. Research requires
   full-text method/limitations review; archive no more than the allowed excerpts and provenance hashes.
4. Inspect confirmed episode history. Same-topic coverage is allowed only when the special adds substantive
   explanation. Avoid repeated announcements and stock openings; outline one hook and one closing.
5. Build a packet with `source_events`, `stories`, `source_health`, `show_notes`, and optional `noise_notes`.
   These use the existing schema contracts. Run `pipeline.adhoc brief` to validate the window and prepare
   the Notebook instructions. Do not pad insufficient evidence to satisfy the duration request.

## Generate and review

Use `notebook-podcast` for signed-in generation and the native Save handoff. Choose English Deep Dive / Longer.
The duration preference is not a promise. Generate/download once, preserve the original, and measure actual bytes.
Allow at most one deliberate regeneration inside the authorized account allowance; then report the blocker.

Use an approved local ASR environment and retain the exact UTF-8 transcript. Do not fabricate transcription or
listening results. Review all consequential spoken claims, numbers, scope, research limitations, and repetition.
The review JSON contains `transcript` (engine and model), `review` (the schema's transcript/source comparison),
and `voice` (`{}` for Notebook). Claims must quote exact source excerpts and occur in the transcript.
Resolve uncertainties before marking ready. A plain schema pass is not semantic review.

Use `pipeline.adhoc prepare` with the request, packet, transcript, review, original audio, and a new output directory.
It checks the long-form contract, masters final audio with FFmpeg, and writes the sealed publication bundle.
An unchanged successful bundle can be resumed; failed outputs are preserved for diagnosis, not overwritten.

## Publish and report

Only a publish-now request may run `pipeline.adhoc publish`. This explicitly creates a draft transport release
and dispatches the existing shared publisher. It is not yet subscriber-confirmed.
Publication uses current `main`, rechecks issue authorization, promotes immutable media, deploys Pages inline,
and confirms exact delivery before recording request completion.

If upload/dispatch fails after the draft release exists, resume its tag through `update-radar.yml`; never regenerate
or upload with `--clobber`. Use `publication-recovery` for a pending candidate.
Report the release/episode identity and feed receipt. Apple app refresh and device acceptance are separate.

## Voice alternatives

Notebook is the default. Edge presets and optional Kokoro/Piper auditions synthesize a newly reviewed script;
they do not secretly change Notebook hosts. Local providers require approved installed packages, licensed
hash-pinned assets, and actual listening/platform evaluation. Never install around an IT block or silently
switch providers. Record unavailable prerequisites as blockers.
