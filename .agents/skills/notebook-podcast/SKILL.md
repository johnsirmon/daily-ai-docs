---
name: notebook-podcast
description: >
  Create or publish a source-backed Gemini Notebook podcast through the signed-in
  browser, including native Save As handoff, local media checks, transcript review,
  and immutable publication. Use for Notebook audio previews and imported episodes.
---

# Notebook podcast workflow

## Boundaries

- Inspect the current publication contract in `docs/OPERATIONS.md` before acting.
- A consumer subscription is not API credit. Existing Notebook allowance is not
  unlimited free automation. Do not enable billing or export browser cookies.
- Use only a dedicated notebook and approved public primary sources. Leave other
  notebooks, account data, and private material alone.
- Preview creation, file validation, factual review, and permission to publish are
  separate milestones. Never claim a milestone merely because an earlier one passed.

## Prepare and generate once

First use the [local/cloud handoff](../../../docs/OPERATIONS.md#local--cloud-authenticated-execution-boundary).
`pipeline.adhoc brief` creates `local-execution.json` beside the existing request and brief for Notebook requests.
For daily schema 3, prepare a `notebook-daily` handoff in a new staging directory with the exact approved prompt,
episode identity, and original recording filename. Do not modify the scheduled daily provider to do this.
Cloud stops on `local-required` and reports the handoff location; it must not assert local execution.
Only a local agent using the current signed-in browser may pass `--execution local`.
Before clicking Generate or Download, claim the corresponding action. Click only if the returned
`perform_browser_action` is true; record `generated` only after inspecting persisted generation.
These commands record milestones, not browser automation or proof of generation.

Safe offline CLI discovery:

```sh
python -m pipeline.local_execution --help
python -m pipeline.local_execution prepare --help
python -m pipeline.local_execution step --help
```

1. Select a few substantive changes, not a list of new version tags. Check prior
   episode coverage. For research, inspect full methods and limitations.
2. Prepare a short editorial brief: change versus before, affected audience,
   practical consequence, next step, and essential caveat. Preserve eligibility
   limits and distinguish recommendations from measured results.
3. Use the existing shared browser page. Inspect accessible controls before acting.
   Choose the contract before configuring English Deep Dive:
   - Daily schema 3: select Short and request 5-8 minutes.
   - Request-bound schema 4: start with [adhoc-podcast](../adhoc-podcast/SKILL.md),
     select Longer, and target 20-30 minutes using its validated brief; this is not a publication limit.
   Length controls express preferences, not guaranteed output durations.
4. Submit once. While generation runs, do independent preparation. Reuse pending
   tool operation IDs rather than repeating the action. Inspect completion once
   the generation state changes.
5. Confirm that the completed artifact persists after reload and retains the
   intended prompt and sources. A duration label is not a measured audio file.

## Download: web controls are not native dialogs

1. Click Download once. If a native Windows Save As dialog appears, the operator
   may need to click Save. Browser tools may not expose or capture that dialog.
2. A missing Playwright download event is not proof of a failed download. Do not
   generate again, click Download repeatedly, or overwrite an existing file.
3. If the user reports saving the file, inspect that exact file. Prefer the operator's
   exact saved path. Otherwise resolve the Windows Downloads known folder rather than
   assuming a username or a path inferred from a screenshot. This is local read-only
   discovery, not permission to enumerate unrelated downloads.

   In native Windows PowerShell:

   ```powershell
   $folders = Get-ItemProperty -LiteralPath `
     'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
   [Environment]::ExpandEnvironmentVariables($folders.'{374DE290-123F-4565-9164-39C4925E467B}')
   ```

4. On native Windows, use the returned Windows path directly; do not run `wslpath`.
   Only in WSL, invoke the same read-only query through `powershell.exe`, then translate
   the returned path with `wslpath`. Inspect only the expected filename in either shell.
5. Signed media links may expire or be IP-bound. An unauthenticated request may
   return a sign-in HTML page with HTTP 200. Do not save that as a successful audio
   artifact, extract cookies, or keep retrying protected URLs.

Record an exposed native-dialog boundary with `wait --reason save-file`, then stop for the operator.
After the operator confirms Save, use `observe --operator-saved`, `validate`, then `resume` on the handoff.
Do not mark Save confirmed just because a dialog appeared. The exact request-local recording must exist.
If saved elsewhere, ask for the exact path and copy only that recording into the expected path without overwriting;
preserve the original and do not enumerate unrelated downloads.
The handoff stores relative filenames, not account paths.

## Validate the actual recording

Use [audio-production-review](../audio-production-review/SKILL.md) for the local ASR
handoff, review-packet example, mastering, and listening record.

- Preserve the original. Record size, codec, measured duration, and SHA-256.
- Handoff validation checks the original recording without conversion. `ready-to-resume-automation`
  permits the next review step, not import or publication by itself. Transcript and source reviews remain required.
- Full-decode with FFmpeg and fail on errors. Daily schema-3 audio must measure 300-480 seconds.
  Schema-4 specials have no fixed minute range: require finite positive duration plausible for the reviewed
  transcript. Do not change a daily contract to fit a longer recording.
- Bind media bytes with exact size and checksum. Cross-version FFprobe duration
  estimates may differ by MP3 priming/padding frames; use the publisher's bounded
  tested tolerance, not exact floating-point equality or an unbounded exception.
- Transcribe locally when needed; do not send unpublished recordings to an
  unapproved service. Mark automatic transcription as such, including its errors.
- Compare spoken claims with primary evidence. The saved prompt is not proof of
  compliance. Check scope, quantities, eligibility, historical dates, and research
  limitations. Do not infer equal capability from non-significant comparisons.
- Treat ASR uncertainties as uncertainties. Do not claim a human listening review
  or independent model verification that did not happen.
- Correct material errors before publication. Make corrections audible and record
  prepublication edits; never quietly mislabel an erroneous claim as supported.

## Publish only with authorization

- Use the repository's explicit reviewed-audio contract and import commands.
  Do not relabel Notebook output as legacy deterministic narration or two verified
  Gemini API calls.
- The publisher requires MP3. Pass the preserved original recording to
  `pipeline.reviewed_audio` for schema 3, or `pipeline.adhoc prepare` for schema 4.
  The importer owns conversion/mastering and final-byte validation; do not manually
  convert first or rename M4A to MP3. Explicit correction composites are documented
  inputs, not permission for an extra encoding pass.
- Use a new episode identity and immutable release. Resume from stored release
  bytes after a failure, never regenerate or replace an existing enclosure.
- Use the shared `podcast-publisher` workflow lock. Require remote HEAD, byte
  ranges, checksum, candidate RSS, and subscriber-facing GUID verification.
- Advance novelty state only after public delivery. Feed delivery does not prove
  that Apple has refreshed every listener's app.
- Record the result and the manual Save step honestly. Native-dialog involvement
  means this is operator-assisted, not unattended browser automation.

The ad-hoc skill owns long-form request authorization, recency, staging, and the shared-publisher
handoff. Notebook does not guarantee exact duration or selectable voices.
