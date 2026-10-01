# Portable production and the shared research handoff

The private production command reuses `pipeline.reviewed_audio`, schema 3, existing
FFmpeg mastering, media validation and RSS primitives. It does not create a second
publisher. Notebook and the explicit `reviewed-edge` route both enter the same
reviewed bundle and local listening UI. Scheduled schema-2 API generation keeps its
independent two-call verification and fail-closed behavior; it is not a fallback.

## Editorial ownership and default operator path

Sirmon.ai and its curated research own the dated journal, articles and corrections.
Daily AI Developer Brief owns spoken adaptation, audio, cover, chapters and RSS.
The default operator path is the journal packet below, primary-claim review, then
the private build command. Do not run a second discovery pass just to fill an episode.
A changed article revision reopens review under the same article ID; it never silently
replaces released audio, GUIDs or historical feed entries. Publish an explicit corrected
episode through the existing approved publisher when needed.

The existing scheduled collector remains a compatibility path; this branch does not
disable or reroute a live workflow. Retiring that schedule requires an explicit
operational cutover after the replacement's hosting and review handoffs work.

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

The producer owns [the public journal feed](https://sirmon.ai/updates/feed.json)
and its [v1 contract](https://github.com/johnsirmon/sirmon-ai/blob/main/AI_JOURNAL_OPERATIONS.md).
Save that public JSON locally, then consume it offline:

```sh
python -m pipeline.editorial_bundle --bundle feed.json --output drafting-packet.json
# Only after a successful output has consumed that exact revision:
python -m pipeline.editorial_bundle --bundle feed.json --output next-packet.json --seen-revision hydrafusion-workflows:1
```

The actual contract uses `schemaVersion: 1`, date-only `updatedAt`, `events` and
`articles`. Events preserve announcement `date`, `verifiedAt`, named primary `source`,
`maturity` and `confidence`. Articles preserve stable `id`, positive `revision`,
publication/update/verification dates, `eventIds`, `canonicalUrl`, `sources`,
`narrationSummary`, `importance`, `audience`, practical `action`, `takeaway` and sections.
Date-only values remain date-only; article publication is not announcement recency.
Older supporting events remain historical context, not fresh news.

The consumer replaces the provisional unpublished bundle format. It validates linked
published evidence, rejects unknown major versions, and ignores additive v1 fields
by projecting only known public fields. Unchanged `(id, revision)` pairs are skipped;
a changed revision updates the same article identity. Preparation never advances
consumption state. The caller must persist processed pairs only after successful output.
No scheduler, network collector, second backend or automatic audio regeneration is added.

The packet remains **untrusted drafting context**, not a source-verified episode.
Preserve canonical attribution and primary links; fetch and review primary support
before turning narration summaries into product claims. The feed does not carry
claim-local quotes, and the consumer does not invent them or independent verification.
Existing source/claim review, novelty and actual listening gates still apply.

## Required context for every entry

Before approving either an API-generated or reviewed-audio entry, check the actual
spoken text against all of these requirements:

1. Explain the unfamiliar tool or concept plainly on first mention, including
   necessary acronyms. Experienced listeners should not need a second tab.
2. Place it in the larger AI workflow: what goes in, what job it performs, and
   what useful result comes out, only as far as primary evidence establishes.
3. Give a concrete use case or a useful analogy and explain its limits. Mark
   hypothetical examples; an analogy is not evidence of results or safety.
4. Explain why this change matters to that workflow, who should care, and who
   can skip it or defer action. Keep eligibility and installed versions conditional.
5. Retain preview status, caveats and source limitations. Obtain missing primary
   background evidence or defer the entry instead of inventing an introduction.

Review each entry separately; a general opening or closing does not satisfy it.
The shared context requirement is passed to journal handoffs, drafting and the
independent audit. Missing context must produce an audit issue and rejection through
the existing two-call gate. No extra model call or keyword-based semantic approval
is added. Reviewed Edge/Notebook audio requires the same human editorial checklist;
ASR and automated syntax/loudness checks cannot certify explanation or naturalness.

The frozen October 1 private candidate predates this rule and is **not approved**
against it: Copilot CLI/MCP need plain definitions and workflow placement; Codex and
Bedrock need orientation or removal where irrelevant. Both entries need a clear
conditional who-can-skip boundary. The practical recovery/permission experiments and
model acceptance check are useful existing context, but do not close those gaps.
Keep the current recording and transcript intact. Source the missing definitions,
review a revised script, and create a separate candidate before any new recording.

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


## Deliberately concise reviewed daily audio

The default reviewed daily window remains 300-480 seconds, originally introduced
with the reviewed-audio importer (94258fbb). It is an editorial format target,
not an Apple Podcasts minimum. A reviewed Edge daily may explicitly opt into
`generation.duration_policy` with these exact fields:

```json
{
  "class": "short_brief",
  "rationale": "A concrete editorial reason this complete episode should stay concise.",
  "approved_at": "<timezone-aware approval timestamp>",
  "script": "<complete approved spoken script>",
  "script_sha256": "<exact UTF-8 script hash>",
  "source_audio_sha256": "<same source audio hash as generation>",
  "transcript_sha256": "<same exact ASR hash as generation.transcript>"
}
```

This class is restricted to 450-750 approved words and 180-300 measured seconds,
with a stronger lower duration bound of script words / 190 * 60 seconds. It is not
an automatic response to failed synthesis. Script and ASR must contain disclosure,
retain the same opening/ending eight normalized words, and preserve at least 97%
ordered word coverage with a transcript length within 5% of the approved script.
That tolerates small ASR spelling differences, not missing sections. It cannot
prove every word was spoken correctly: actual listening remains necessary.

Schema validation, import, private build and release-byte verification use the
same rule. Source/transcript/final-media hashes, primary-claim review, mastering,
full decode, silence and speech-duration plausibility checks remain mandatory.
Existing manifests without this policy retain their old behavior. Schema-2 model
generation, Notebook imports, special requests and fixed waivers are unchanged.
Approval metadata is an operator-reviewed record, not a cryptographic signature or
publication grant. The revision-4 recording remains private and on listening hold;
its original duration-failure receipt remains preserved as historical evidence.


Reviewed Edge dailies may retain snapshot-reviewed undated official documentation
as background in a story that also cites a dated primary event. Background-only
stories remain rejected. Original publication dates remain empty; capture/review
timestamps describe provenance, not news recency. The existing snapshot hash,
bounded excerpts and exact official-page allowlist apply. No source collector,
daily ranking eligibility or schema-2 evidence rule changes. Feed descriptions
identify this route as Edge narration rather than mislabeling it Notebook.
