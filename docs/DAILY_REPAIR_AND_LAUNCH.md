# Daily delivery repair and launch checklist

## Verified incident

Inspection date: 2026-10-06. Base: `a16efcb32288c310ca49277f210080dc33e205ac`.
The subscriber feed has 51 items, newest dated October 3. It is not a one-item feed.
October 4 and 5 publisher jobs failed at Gemini editorial generation, before audio,
release upload or candidate RSS. The October 5 [failed run](https://github.com/johnsirmon/daily-ai-docs/actions/runs/37362392417)
reports HTTP 503 service unavailable/high demand. This is not evidence of insufficient news.
The October 6 schedule was not yet listed at the researcher's 11:18 UTC check;
GitHub's 10:17 UTC cron target is best effort. No repair has been deployed.

## Changed behavior and contracts

- Production config enables `quiet_news_research`. Selection permits one fresh,
  uncovered full-text paper without a product story; preparation accepts a verified
  research-only edition. A review includes question, method, bounded author-reported
  result, limitations, and a developer experiment. It must not imply reproduction.
- `service_retries: 2` retries explicit HTTP 503 and typed SDK timeout errors on the same Gemini model and
  endpoint, after 10 and 20 seconds. SDK retries remain disabled. No retries for
  quota/429, credentials, other connection errors, incomplete output, or factual rejection.
  Default outside production config remains zero. No live requests were made for testing.
- Schema 2 editorial generation version 1 retains exactly two calls. Version 2
  records actual attempted calls (2–6), with matching `request_attempts`, including
  failed requests; draft and independent verification remain separate stages.
  Worst-case configured editorial budget is 420 seconds at the production 60-second timeout.
  Two successful outputs are required; there is no provider or deterministic fallback.
- New daily IDs use the UTC publication date, independently of source dates.
  Existing immutable IDs, bytes, dates and checksums are preserved. Duplicate-day
  checks normalize stored offsets to UTC. Pending candidates still resume first.
- Feed history is retained by default. Explicit positive `PODCAST_MAX_EPISODES`
  remains an operator opt-in retention cap. Local feed validation requires HTTPS
  MP3 enclosures; existing remote byte/hash checks remain in the publisher.
- Health checks no longer excuse a stale feed using an intentional editorial skip.
  `--require-daily-delivery` checks daily cadence independently of a newer special
  and retains exact feed-head verification and daily evaluation receipt validation.
  Existing failure-issue reporting remains; no new messaging integration is introduced.
- Unpublished previews retain their separately authorized two-request ceiling, even
  when production config enables service retries. Exact-byte test fixtures disable
  checkout newline conversion; the one-release test writes explicit LF bytes on Windows.

The full paper is transient provider context, not saved episode content. Bounded
claim quotes and evidence hashes remain the publication audit. No historical
manifest, RSS item, released audio, runtime credential or Hermes installation changed.

## Episode format

Open with the useful developer consequence, then state the source briefly. Explain
the change or research question, the mechanism/method, evidence, boundaries, and a
concrete practical check. End with what to test or defer. Keep versions, URLs and
detailed citations in linked show notes. Avoid generic headline reading, forced
urgency and padded paper summaries. A research-only edition can recommend `watch`
without manufacturing an unrelated `skip` story. Every consequential statement
still needs claim-local support and independent verification.

## Unpublished example: RecreationWorld

[RecreationWorld](https://arxiv.org/abs/2609.22000v2), Shuai Bai and colleagues:
first submitted September 18, revised September 21, 2026. Both dates are verified;
the revision is not presented as a new first publication. A search of committed
episode manifests found no prior coverage on October 6.

The authors ask whether agents can alternate between inspecting an application,
coding a recreation, and checking its behavior. Their framework spans desktop,
mobile and web environments. Held-out testing uses reference-validated visual and
programmatic assertions. They report stronger recreation of static interfaces than
interactions and computed results. These are author-reported findings, not independently
reproduced here. The pinned environments exclude much live-service and real-user
behavior; finite hidden tests cannot prove complete equivalence, and contamination
screening cannot rule out memorization. See [full methods and limitations](https://arxiv.org/html/2609.22000v2).

Suggested original developer exercise: give Copilot or Codex a small local UI task,
then require a runnable artifact, interaction tests, and a final rendered check after
the last edit. Record failures separately for appearance, behavior and verification.
This is a proposed experiment, not a measured improvement or an endorsement based
on product-specific performance. This example has no generated audio and has not
passed the production independent model review.

## Before formal release or monetization

1. Merge review and authorization are still required. Merging enables changed behavior
   on the next scheduled publisher; generating/releasing today's episode needs separate
   publication authorization. Persistent provider outages can still prevent delivery.
2. Review a real unpublished recording: sources, pronunciation, pacing, repetition,
   full decode, checksum, duration, and measured mastering. Existing optional
   `PODCAST_AUDIO_POLISH=1` performs measured polish; enable it only after auditioning.
   Target approximately -16 LKFS with true peak at or below -1 dBFS, following
   [Apple audio guidance](https://podcasters.apple.com/support/893-audio-requirements).
   Automated measurements are not a listening review.
3. Keep prominent spoken and written AI disclosure, already present in current
   production rendering. Check the final published audio and description against
   [Apple content guidelines](https://podcasters.apple.com/support/891-content-and-subscription-guidelines).
4. Resolve commercial rights for voices, artwork and any future music. Current
   Edge voice clearance is unresolved; the wrapper's license does not grant voice
   rights. Existing generated artwork needs its original provider terms and creation
   provenance reviewed. No music is added. See `media-rights.json`; do not infer clearance.
5. Validate RSS, measured enclosure bytes, unique GUIDs, dates and 3000×3000 RGB
   artwork, then verify actual Apple/device playback and directory acceptance.
   [Apple requirements](https://podcasters.apple.com/support/823-podcast-requirements)
   and [validation](https://podcasters.apple.com/support/829-validate-your-podcast)
   do not establish monetization eligibility or income.
6. Select the brand before changing feed identity or artwork. The proposed names
   remain unselected; no historical feed rename is performed in this repair.

## Video groundwork and safe demo

Offline commands using the existing Python environment:

```sh
python -m pipeline.daily prepare --dry-run --no-audio
python -m pipeline.video_bundle --manifest .cache/episode-manifest.json --output .cache/video-plan.json
python -m pipeline.publish_check
```

The dry-run uses synthetic fixtures, not current news or an independently verified
production paper review. The video plan binds the exact script hash, source URLs,
research caveats, description/disclosure, untimed caption text, and visual beats.
It does not generate a video, invent timestamps, upload, or create a YouTube schedule.
Real captions require alignment to final audio; chapters require measured timings.
Create original explanatory visuals and editorial value before applying for
[YouTube monetization](https://support.google.com/youtube/answer/1311392).
Daily video publication and its credentials/monitoring remain future authorized work.
