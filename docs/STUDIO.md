# Portable production and the shared research handoff

The private production command reuses `pipeline.reviewed_audio`, schema 3, existing
FFmpeg mastering, media validation and RSS primitives. It does not create a second
publisher. Notebook and the explicit `reviewed-edge` route both enter the same
reviewed bundle and local listening UI. Scheduled schema-2 API generation keeps its
independent two-call verification and fail-closed behavior; it is not a fallback.

## Private run

```sh
# Networked, free/best-effort Edge synthesis; no API key or paid fallback.
python -m pipeline.studio synthesize --script script.txt --output recording --free-edge-confirmed
# Preserve source.mp3; transcribe with an already approved local ASR installation.
# Independently compare actual transcript/claims to primary evidence and create draft.json.
# Offline, one command to import/master/validate and build the candidate feed/site:
python -m pipeline.studio build --draft draft.json --audio recording/source.mp3 --feed podcast.xml --artwork assets/studio/signal-desk.jpg --output candidate --title "A concrete editorial headline"
# Existing loopback-only listening review. No publication permission implied:
python -m pipeline.review_ui --directory candidate/bundle
```

`reviewed-edge` identifies provider `edge` and exact name/rate/pitch, actual source
MP3 hash, frozen local-ASR transcript hash, transcript/source comparison and mandatory
final mastering report. It cannot be labeled Notebook or API-verified. Disclosure
words remain mandatory; ASR punctuation differences alone do not justify rewriting
the transcript. Input recordings are preserved. Human listening remains necessary.

Synthesis retries at most three times with 1/2-second backoff, only on the explicit
free Edge route. Attempts persist across resume; no automatic switch to a paid
provider or repetition of failed Gemini model calls. A successful identical run
reuses bytes. Changed input/voice, tampered output, concurrent ownership or unrelated
output fails closed. Build receipts bind draft, audio, feed, artwork and renderer.
Interrupted imports preserve partial artifacts and require inspection rather than
silently regenerating an uncertain recording. No daemon or schedule is installed.

## Final-audio resources

```sh
python -m pipeline.episode_resources --bundle candidate/bundle --timings final-timings.json --feed candidate/feed-preview.xml --artwork candidate/episode.jpg --output resources
```

The timing packet has `audio_sha256`, `segments` (`start`, `end`, `text`) and
`chapters` (`startTime`, `title`). Transcribe the **final encoded audio**, never
estimate times from word counts. Chapters must begin on measured segment boundaries.
Millisecond rounding and at most 0.5 seconds of ASR end overrun are normalized to the
measured media end and disclosed in the receipt. Raw ASR requires listening correction.
The resulting local RSS uses `podcast:chapters`, `podcast:transcript`, and episode art;
existing items, GUIDs, enclosures and extension elements are retained. No public URL
has been uploaded or verified by this command. Only the feed/site copy is modified.

## Shared research: Sirmon owns collection

The version-1 consumer is `python -m pipeline.editorial_bundle --bundle public.json
--output drafting-packet.json`. Pass repeated `--seen-item-id` values from confirmed
podcast consumption to avoid repeating articles; preparing a packet does not advance
novelty state. This is a file handoff, not another service or collection backend.
The exact producer contract must be agreed with the Sirmon owner before connecting it
as the production source. The initial consumer rejects unknown fields to keep private
metadata out, and never promotes a bundle into verified narration.

Contract: root `schema_version: 1`, `bundle_id`, `generated_at`, `items`.
Each item: stable `id`, `published_at`, `canonical_url`, `title`, `narration_summary`,
`why_it_matters`, `affected_workflow`, `decision` (keep/try/replace/watch), `claims`,
optional `experiment` and `caveat`. Each claim: `text`, public primary `source_url`,
exact supporting `quote`, `source_published_at`. Timestamps are timezone-aware ISO8601.
The article URL is attribution, not primary support. A quote-shaped string is not
proof of entailment: the existing source/claim and audio review remain required.
No Sirmon repository, deployment or backend is changed here.

## Quality rubric and current diagnosis

| Dimension | Acceptance evidence |
| --- | --- |
| Novelty | Dated sources; compare event IDs and claims with confirmed history; do not confuse tags with changes. |
| Support | Every product assertion has a primary URL and claim-local quote; qualifications travel with the claim. |
| Relevance | Explain affected workflow, useful decision, bounded experiment, cost/caveat only where supported. |
| Narrative | Concrete payoff first, group changes by problem, transition into synthesis, no headline/ID recital. |
| Delivery | Full normal-speed audition: names, transitions, pauses, intelligibility, no clipping or repetitive padding. |
| Technical | Exact bytes/hash, full decode, plausible 300–480 seconds, -17 to -15 LUFS and peak <= -1 dBTP. |
| Integrity | Frozen transcript, honest provider/disclosure, no ads, public-safe notes separate from diagnostics. |

These are evidence requirements, not a numeric automated claim of editorial quality.
Fixtures catch known defects; passing tests does not establish interestingness or
naturalness. The September 29 actual recording's local ASR contained spoken PR numbers,
release fragments, generic no-change filler and internal coverage diagnostics. Its
56-second runtime offers little explanatory space. Scheduler delay, provider failure
and editorial failure are distinct. Switching voices alone cannot fix that script.

## Hosting and ownership boundary

Current GitHub Pages is configured as `build_type: workflow`. This branch makes
private production independent of Actions, but **does not claim Actions-free public
delivery**. The existing URL cannot gain a new deployment mechanism without an
explicit hosting/configuration decision and release authorization. No Pages setting,
GitHub workflow, credentials or service is changed. Do not publish the private RSS
before its audio, art, transcript and chapter URLs exist and pass remote checks.
Any local schedule needs a running, connected machine; always-on hosting is separate.
Apple indexing is external and may take time after successful feed publication.

Chief of Staff coordinates native Hermes ownership: podcast-producer owns actual
script/audio review; forward-observer independently checks claims; release-engineer
receives only an accepted exact bundle and explicit publication grant. This branch
neither starts model-backed agents nor changes their runtime. No listening approval,
independent reviewer verdict or subscriber delivery is fabricated. Parent coordination
must bind those remaining handoffs to the exact candidate hashes.

Apple references: [RSS](https://podcasters.apple.com/support/823-podcast-requirements),
[audio](https://podcasters.apple.com/support/893-audio-requirements),
[AI disclosure](https://podcasters.apple.com/support/891-content-and-subscription-guidelines),
[chapters](https://podcasters.apple.com/support/5482-using-chapters-on-apple-podcasts).
