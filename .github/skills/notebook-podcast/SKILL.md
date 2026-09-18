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

1. Select a few substantive changes, not a list of new version tags. Check prior
   episode coverage. For research, inspect full methods and limitations.
2. Prepare a short editorial brief: change versus before, affected audience,
   practical consequence, next step, and essential caveat. Preserve eligibility
   limits and distinguish recommendations from measured results.
3. Use the existing shared browser page. Inspect accessible controls before acting.
   Configure a concise English Deep Dive and request 5-8 minutes.
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
3. If the user reports saving the file, inspect that exact file. In WSL, resolve
   the Windows Downloads known folder rather than assuming the Linux Downloads
   folder, username casing, or a path inferred from a screenshot.

   ```bash
   powershell.exe -NoProfile -NonInteractive -Command \
     "[Environment]::ExpandEnvironmentVariables((Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders').'{374DE290-123F-4565-9164-39C4925E467B}')"
   ```

4. Convert the returned Windows path with `wslpath`, then inspect only the expected
   filename. Avoid broad searches of unrelated user files.
5. Signed media links may expire or be IP-bound. An unauthenticated request may
   return a sign-in HTML page with HTTP 200. Do not save that as a successful audio
   artifact, extract cookies, or keep retrying protected URLs.

## Validate the actual recording

- Preserve the original. Record size, codec, measured duration, and SHA-256.
- Full-decode with FFmpeg, fail on errors, and assert 300-480 seconds explicitly.
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
- The publisher currently requires MP3: perform a documented conversion once,
  then validate the final bytes. Do not rename M4A to MP3.
- Use a new episode identity and immutable release. Resume from stored release
  bytes after a failure, never regenerate or replace an existing enclosure.
- Use the shared `podcast-publisher` workflow lock. Require remote HEAD, byte
  ranges, checksum, candidate RSS, and subscriber-facing GUID verification.
- Advance novelty state only after public delivery. Feed delivery does not prove
  that Apple has refreshed every listener's app.
- Record the result and the manual Save step honestly. Native-dialog involvement
  means this is operator-assisted, not unattended browser automation.
