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
`pipeline.adhoc issue --number N`. Default to 60 days and an editorial target of 20-30 minutes, not a publication
limit. Shorter or longer specials are allowed; only an explicit window override changes recency.
Pass `--publish-now` only when the user requested publication.
Both entry points check GitHub write permission. An issue is a queue, not an unattended browser worker.
An edited issue is a changed request and invalidates the earlier authorization.

Keep all source material and media in the request's `.cache/adhoc/<id>/` directory.
Do not overwrite daily staging or clean up an unresolved request.

## Command boundaries

Consult [operations](../../../docs/OPERATIONS.md#adhoc-long-form-specials) for invocation examples.
With the repository's installed interpreter, these discovery commands only print help:

```sh
python -m pipeline.adhoc request --help
python -m pipeline.adhoc issue --help
python -m pipeline.adhoc brief --help
python -m pipeline.adhoc prepare --help
python -m pipeline.adhoc publish --help
python -m pipeline.adhoc status --help
python -m pipeline.adhoc verify --help
python -m pipeline.adhoc papers --help
python -m pipeline.adhoc synthesize --help
```

The commands without `--help` have different effects:

| Command | Network and write boundary |
|---|---|
| `request` | GitHub identity/permission reads; writes a request-local queue record. |
| `issue` | GitHub issue/permission reads; writes local staging and posts an intake comment. |
| `brief` | Offline validation and request-local brief/status writes; reads local episode history. |
| `prepare` | Offline schema/media validation and mastering; writes a new sealed bundle and local status. |
| `status` | Local read only: confirmed request receipt if present, otherwise local status. Does not refresh GitHub. |
| `verify` | GitHub authorization reads plus manifest validation; not a full decode, media check, or delivery check. |
| `papers` | Networked public paper collection; writes transient research under untracked staging. |
| `synthesize` | Networked Edge TTS; writes new unpublished audio and a `.voice.json` sidecar. |
| `publish` | GitHub authorization reads, draft release upload, live publisher dispatch, and local status writes. |

Use `papers` with the frozen request window and a new output file in its staging directory.
The collector output is research input, not a publication-ready packet: review methods,
limitations, and bounded excerpts before archiving. Use `synthesize` only for an explicit
Edge request, never to silently replace Notebook. No generation, collection, or publishing
command is a routine validation command.

## Research and outline

1. Freeze the request's UTC evidence window. Discover public primary URLs, then inspect their actual content.
   Exa may be supplied as an MCP tool by the active agent host (including VS Code or Hermes); it is discovery
   assistance, not a Python pipeline dependency or evidence authority. Do not require Exa when another bounded
   discovery path is available, and never treat search snippets as approved evidence.
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
The duration preference is not a promise or a fixed gate. Generate/download once, preserve the original,
and measure actual bytes. Require a finite positive duration plausible for the reviewed transcript.
Allow at most one deliberate regeneration inside the authorized account allowance; then report the blocker.

Follow [audio-production-review](../audio-production-review/SKILL.md) for approved local ASR,
the review-packet example, mastering gates, and listening evidence. Retain the exact UTF-8 transcript.
Do not fabricate transcription or listening results. Review all consequential spoken claims,
numbers, scope, research limitations, and repetition.
The review JSON contains `transcript` (engine and model), `review` (the schema's transcript/source comparison),
and `voice` (`{}` for Notebook). Claims must quote exact source excerpts and occur in the transcript.
Resolve uncertainties before marking ready. A plain schema pass is not semantic review.

Use `pipeline.adhoc prepare` with the request, packet, transcript, review, original audio, and a new output directory.
Supply the original recording, not a manually preconverted MP3. Preparation owns conversion/mastering,
checks the long-form contract, and writes the sealed publication bundle.
An unchanged successful bundle can be resumed; failed outputs are preserved for diagnosis, not overwritten.

## Publish and report

Only a publish-now request may run `pipeline.adhoc publish`. This explicitly creates a draft transport release
and dispatches the existing shared publisher. It is not yet subscriber-confirmed.
Publication uses current `main`, rechecks issue authorization, promotes immutable media, deploys Pages inline,
and confirms exact delivery before recording request completion.

If upload/dispatch fails after the draft release exists, resume its tag through `update-radar.yml`; never regenerate
or upload with `--clobber`. Use `publication-recovery` for a pending candidate.
Refresh production history before calling `status`; a stale checkout can report an old local stage.
Report the release/episode identity, exact delivery receipt, and confirmed
`data/requests/<request-id>.json` matching the request revision. An intake comment or local
`publishing` status is not completion. Apple app refresh and device acceptance are separate.

## Voice alternatives

Notebook is the default. Edge presets can synthesize a newly reviewed script; they do not secretly change
Notebook hosts. Review the actual recording and never silently switch providers.
