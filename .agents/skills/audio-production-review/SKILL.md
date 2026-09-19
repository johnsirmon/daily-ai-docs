---
name: audio-production-review
description: >
  Prepare and review unpublished podcast audio using local ASR, exact transcript
  provenance, measured mastering, and honest listening evidence. Use for recording
  handoffs, audio polish, loudness checks, or same-script voice comparisons.
---

# Audio production review

This skill owns the local recording-to-reviewed-bundle handoff, not browser generation
or publication. Use [notebook-podcast](../notebook-podcast/SKILL.md) for browser controls,
[adhoc-podcast](../adhoc-podcast/SKILL.md) for request authorization, and
[evidence-led-review](../evidence-led-review/SKILL.md#claim-level-editorial-acceptance)
for claim adjudication. Recover released media through
[publication-recovery](../publication-recovery/SKILL.md), never by remastering it.

Read [operations](../../../docs/OPERATIONS.md#voice-and-delivery-polish) and the current
[importer](../../../pipeline/reviewed_audio.py) before preparing a recording.

## Establish the recording and tools

1. Identify the schema, request/episode, authorization scope, original recording, and
   new request-local output directory. Preserve unresolved staging and the original bytes.
2. Record original size and SHA-256, probe codec/duration, and perform a full decode.
   A Notebook duration label, filename extension, or successful HTTP response is not media proof.
3. Confirm local `ffmpeg` and `ffprobe` availability and record versions. Use the selected
   interpreter and existing approved ASR environment, not an arbitrary shell Python.
4. Supported transcript engine labels are `faster-whisper`, `whisper`, `openai-whisper`,
   and `whisper.cpp`. Check that the chosen executable/package and model are actually
   available; an engine label alone proves nothing. Record the real engine/model used.
   ASR is an optional operator dependency, not installed by this repository's lockfile.
5. If ASR/model files are missing, report the prerequisite and obtain approval for the
   chosen installation/model download. Do not silently send recordings to cloud ASR,
   switch providers, enable billing, or assume a GPU/runtime is available.

Local file probes, hashing, decode, and installed-model transcription need no provider
quota. Package/model downloads and Edge synthesis are networked and require separate
authorization. No step here grants publication permission.

## Transcribe and assemble the review

1. Transcribe the exact input locally into a new UTF-8 file in the request's staging
   directory. Retain raw ASR output and any timing data locally; do not commit it.
2. Freeze the transcript used for review. Do not silently rewrite ASR mistakes or polish
   speech into claims that were not spoken. Record uncertain names/numbers and resolve
   consequential uncertainty against the recording before acceptance. A changed transcript
   requires a fresh review and hash, not reuse of prior approval.
3. Populate exact spoken claim text, its source-event ID, and the supporting source quote.
   Apply the linked claim worksheet to scope, quantities, eligibility, dates, and research
   limitations. Syntactic quote matching is not factual entailment.
4. Keep the standalone ad-hoc review file to `transcript`, `review`, and `voice`.
   `pipeline.adhoc prepare` binds the UTF-8 narration hash and original-audio hash.
   For schema 3, put transcript/review provenance in the draft's `generation` object;
   do not add schema-4-only request or voice fields.
5. Material corrections require the explicit editing contract, not a rewritten transcript
   concealing the original error. Preserve original/component hashes, exact audible prefix,
   combined transcript, and composite-input hash. The schema-3 importer accepts that reviewed
   composite; it does not synthesize or assemble corrections. The current ad-hoc preparation
   command does not expose editing provenance in its three-field review input. If a special
   needs that handoff, stop for an explicit contract change rather than silently dropping
   provenance or adding unsupported review fields.

### Minimal review example

This fictional schema fixture matches event `e1` in the repository's
[reviewed-audio test fixture](../../../tests/test_reviewed_audio.py).
It demonstrates shape only: no transcription, source verification, or listening occurred.
Never submit it as an actual review. Replace every example value using the real recording
and approved evidence; [skill tests](../../../tests/test_skills.py) validate it as a draft,
not as publishable media.

```json
{
  "transcript": {"engine": "faster-whisper", "model": "small.en"},
  "review": {
    "method": "transcript_source_comparison",
    "reviewed_at": "2026-09-17T20:00:00Z",
    "reviewer": "assistant",
    "claims": [
      {
        "text": "The tool adds sandboxed command previews.",
        "event_id": "e1",
        "quote": "The tool adds sandboxed command previews."
      }
    ],
    "notes": ["Synthetic schema example; no audio was transcribed or listened to."]
  },
  "voice": {}
}
```

Notebook requires `voice: {}`. For an explicit Edge request, use the actual `name`,
`rate`, and `pitch` from the synthesis `.voice.json` sidecar. The schema does not record
volume in that object; do not invent extra fields or listening approval. Preserve any
other synthesis settings in local operator notes.

## Let preparation own conversion and mastering

Pass the preserved original directly to `pipeline.reviewed_audio` for schema 3 or
`pipeline.adhoc prepare` for schema 4. The schema-3 importer also accepts an explicitly
reviewed correction composite with editing provenance. Do not preconvert to MP3 or
run a separate mastering pass first.

Safe offline CLI discovery with the repository's installed interpreter:

```sh
python -m pipeline.reviewed_audio --help
```

The import command without `--help` writes a new bundle; it is not a read-only check.
See [operating commands](../../../docs/OPERATIONS.md#publishing-approved-notebook-audio)
for the required inputs.

- Schema 4 always uses the existing two-pass FFmpeg mastering gate and requires
  1200-1800 measured seconds.
- New schema-3 imports and daily generated TTS opt in only with
  `PODCAST_AUDIO_POLISH=1` for that invocation. Do not persistently change the environment
  or workflow defaults. Schema 3 remains 300-480 seconds; schema-1/2 edition budgets stay unchanged.
- The importer targets -16 LUFS and measures the final MP3 again. Acceptance is inclusive
  -17 to -15 LUFS and true peak at most -1 dBTP. Require finite values, processing/version
  provenance, and a quality-report hash equal to the final MP3 hash.
- Require full decode, schema-specific duration, byte length, codec, sample rate/channels,
  and SHA-256. A mastering report is not a substitute for these media checks.
- Output directories are single-use even after failed import. Preserve failures for diagnosis;
  an unchanged successful ad-hoc bundle may resume through its existing preparation path.
  Never remaster or replace released bytes.

The authoritative gate is [audio_quality.py](../../../pipeline/audio_quality.py);
exercise [test_audio_quality.py](../../../tests/test_audio_quality.py) and
[test_adhoc.py](../../../tests/test_adhoc.py) for mastering changes, plus
[test_reviewed_audio.py](../../../tests/test_reviewed_audio.py) for import behavior.

## Listening and voice comparisons

Use the same reviewed script for unpublished voice comparisons. Request permission
before networked synthesis; a re-voiced episode is a new reviewed recording, not a
replacement for an existing enclosure or a change to Notebook hosts.

Record who actually listened, the exact file/hash, listened time ranges, and findings:
time to the first useful point, actionable takeaways, repetition, pronunciation, pacing,
joins, clipping, and source fidelity. If no listening occurred, say so explicitly.
Do not infer pronunciation defects from ASR spelling or declare a whole recording
reviewed from a short sample. Automated repetition checks only detect a limited class
of adjacent repeated passages, not all repeated ideas or long-form padding.

Report original/final identity, transcript engine/model/hash, claim-review outcome,
decode/duration/loudness results, actual listening scope, and remaining blockers.
Hand the accepted bundle back to the authorized workflow; neither this report nor
passing tests confirms subscriber delivery.
