# Daily podcast operations

## Runtime contract

The daily workflow runs at `10:17 UTC` (06:17 EDT / 05:17 EST). GitHub Actions schedules are best-effort, so the
independent feed-health workflow checks the subscriber URL later. A run is not considered published merely because
Actions is green: the new audio must support HEAD and byte ranges, the candidate RSS must validate, and the Pages feed
must expose the expected GUID.

The repository and feed are public. Do not add private repositories, internal topics, credentials, or private source
excerpts.

## GitHub setup

1. In repository Settings → Pages, select **GitHub Actions** as the source.
2. Let the initial Pages workflow complete before dispatching the daily publisher. The publisher preflights the
canonical feed and will not emit migration metadata while the destination is unavailable.
3. Keep Actions read/write workflow permissions enabled so the publisher can commit generated state and create releases.
4. Optional repository variables:
   - `TTS_PROVIDER`: `edge` (default, no key) or `openai`.
   - `AI_SYNTHESIS`: `off` (default deterministic), `optional`, or `required`.
   - `AI_MODEL`: model name for the configured OpenAI-compatible endpoint.
5. Optional secrets:
   - `OPENAI_API_KEY`: required when `TTS_PROVIDER=openai`; can also back synthesis.
   - `AI_API_KEY`: dedicated synthesis key when it should differ from TTS.
   - `EXA_API_KEY`: only for public ad-hoc research.
6. Weekly video discovery secret:
   - `YOUTUBE_API_KEY`: a Google Cloud key with YouTube Data API v3 enabled. Restrict it to that API. The four
configured searches use roughly 400 search quota units per weekly run, plus low-cost detail requests.
   - Store it only as a GitHub Actions secret. Never paste it into source, workflow YAML, issue text, logs, or command
examples with a real value. CI rejects tracked Google API-key patterns.
   - If a key is pasted into chat or another retained system, rotate it in Google Cloud Console, update the Actions
secret, and delete the old key. Repository-side controls cannot revoke a disclosed Google credential.

The retired GitHub Models endpoint and `GITHUB_TOKEN` are not used for inference. `GITHUB_TOKEN` is limited to GitHub
collection and publication.

For lowest maintenance, use `TTS_PROVIDER=openai` with a supported audio API and set `OPENAI_API_KEY`. The default Edge
path keeps the existing no-key deployment working, but it is treated as best-effort and still must pass full decode,
duration, and size checks before publication.

## Local commands

```bash
# Reproducible environment and tests
uv run --with-requirements requirements.lock pytest -q

# Network-free manifest generation; no model or TTS call
uv run --with-requirements requirements.lock \
  python -m pipeline.daily prepare --dry-run --no-audio

# Live preparation (collects sources and writes a validated MP3 under .cache/)
GITHUB_TOKEN=... uv run --with-requirements requirements.lock \
  python -m pipeline.daily prepare

# Finalize only after the release asset has been uploaded
uv run --with-requirements requirements.lock python -m pipeline.daily finalize

# Check the public feed
uv run --with-requirements requirements.lock python -m pipeline.health

# Refresh the weekly transcript-backed YouTube digest
YOUTUBE_API_KEY=... uv run --with-requirements requirements.lock \
  python -m pipeline.youtube

# Recreate show artwork
uv run --with pillow python scripts/generate_artwork.py
```

Preparation does not modify `podcast.xml`. Finalization verifies the remote audio first, then writes a candidate
RSS/manifest/README without advancing novelty state. After Pages deployment and subscriber-facing audio/artwork checks
pass, `python -m pipeline.daily confirm` marks the manifest published, advances state, and writes a delivery receipt.

## Source and ranking policy

- Add primary release repositories and official feeds under `daily.sources` in `topics/topics.yaml`.
- Source responses marked private and draft releases are rejected.
- Source errors are recorded separately from healthy no-news results.
- Event IDs are derived from canonical URLs; accepted IDs are retained in `data/state.json` to prevent replay.
- Ranking combines primary-source authority, personal relevance, recency, novelty, impact, and measured velocity.
  Lifetime stars alone never mean “rising.”
- Routine/docs keywords subtract 24 points; prereleases subtract another 12. The production threshold is 75, not an
  unconditional keyword ban: a substantive primary-source change mentioning documentation can still qualify. Labeled
  editorial fixtures exercise the production threshold, including counterexamples.
- ACT is reserved for explicit primary-source security/compatibility notices, with affected-version checks rather than
  automatic upgrade advice. Generic security discussion and removed logging are WATCH; prereleases remain SKIP and
  YouTube remains WATCH. Short deterministic excerpts preserve sentence/word boundaries, label omissions, and retain
  links to complete evidence. Repeated penalty notes are collapsed per product.
- Weekly YouTube discovery is bounded to four searches and five stored candidates. It uses age-adjusted views, a
  channel/global velocity baseline, and like rate rather than lifetime views. Full transcripts are processed in memory
  and discarded; only short extractive takeaways are committed.
- A daily edition may contain at most one YouTube learning pick. Treat it as a watch recommendation; product-change
  claims still require direct vendor/repository evidence.
- YouTube discovery records search/detail/candidate counts, transcript attempts/successes, selected/usable/unattempted
  counts, and fixed drop-reason counters. Missing/invalid details, transcript errors, or empty takeaways mark discovery
  degraded rather than a healthy empty result. Zero search results are healthy no-news; reaching the selection cap is
  not a failure.
- Weekly discovery saves safe counters/status to `.cache/youtube-discovery-health.json`, including on request failures,
  and the workflow retains that diagnostic artifact. It contains no transcripts, queries, keys, or raw errors.
  Degraded/error runs exit nonzero without replacing the last good digest. The daily adapter discloses degraded
  artifacts as coverage gaps, including legacy artifacts with candidates but no usable videos; useful partial events can
  still be read if such an artifact is supplied manually.

## Model policy

Deterministic stories are always available from validated source evidence. Optional AI synthesis performs at most one
call over the selected events. External source text is labeled untrusted in the prompt, output must reference known
event IDs, and all output is schema-validated. `AI_SYNTHESIS=required` fails closed if the provider or schema fails.

## Audio and RSS policy

- Final audio must be an MP3, at least 10 KB, free of decode errors/effective silence, and plausible for the narration
  word count. Quiet editions must be 30–120 seconds, one/two-story alerts 30–300 seconds, and normal editions 180–600
  seconds.
- Size, duration, codec, sample rate, channels, and SHA-256 are measured before upload.
- Published release assets are immutable. The accepted manifest is stored beside the MP3; a retry downloads and resumes
  those exact assets instead of regenerating them.
- Existing GUIDs and enclosure URLs are preserved. Candidate feeds reject duplicate GUIDs, duplicate URLs, malformed
  dates, and zero-length enclosures.
- The show cover is a 3000×3000 RGB JPEG generated by `scripts/generate_artwork.py`.
- The mutable RSS document is served through GitHub Pages rather than the week-long jsDelivr branch cache.

## Failure recovery

- Collection: if every source fails or health falls below the configured threshold, do not publish. Partial coverage is
  disclosed; healthy no-news runs publish a quiet-day edition.
- Model: deterministic mode continues; required mode fails without changing the feed.
- TTS/audio: fail before release or RSS changes.
- Release upload: an orphaned release is safe; reruns download and resume the accepted manifest/audio from that release.
- Candidate feed: fix locally and rerun; the public feed remains the last known good version.
- Git push: do not blindly rebase generated feed changes. Re-run from current `main` under the shared
  `podcast-publisher` concurrency group.
- Concurrency: daily publication, weekly digest writes, and the standalone Pages workflow share `podcast-publisher` with
  `cancel-in-progress: false`. The daily job keeps its inline Pages deployment (do not wait on another workflow holding
  the same lock). Standalone Pages push/manual recovery remains available; recover from current `main`, not an older
  run. Actions concurrency is not a FIFO queue and can replace pending runs; it protects active publication, not
  guaranteed execution of every queued run.
- Pages/delivery: the publication job deploys Pages directly, retries the exact subscriber URL, verifies its latest
  audio and artwork, and only then confirms state. Transport failures participate in bounded retries.
- Aged candidate: rerun the daily job without `--force`. A pending candidate resumes before collection, synthesis, or
  TTS, even after 48 hours. The release download must match the prepared episode ID/tag/enclosure, local audio checksum,
  and any accepted candidate manifest (except status). Mismatches fail before candidate writes; do not edit timestamps
  or regenerate media to get past a failure.
- Delivery and freshness are separate: `pipeline.health --candidate "data/episodes/${EPISODE_ID}.json"` and
  `pipeline.daily confirm --episode-id "$EPISODE_ID"` use the same exact-candidate checks. Only age rejection is
  omitted: latest GUID, original publication date, enclosure URL/length, remote checksum, range support, and artwork
  must still match/pass. A successful repeat confirmation leaves an existing receipt/state unchanged.
- Independent health checks remain age-sensitive (the scheduled workflow uses 25 hours). An aged recovery can succeed
  while freshness still alarms; the next scheduled run should collect a new edition. Do not raise the monitoring
  deadline or use a candidate for routine freshness monitoring.

Ad-hoc publication is intentionally paused. It must be migrated to the same evidence manifest and transactional
confirmation flow before it can publish again.

Rollback: revert the generated feed/manifest/state commit. Do not delete or overwrite release assets that may already be
referenced by podcast clients.

## Apple Podcasts and CarPlay acceptance

Direct feed following is the first release path; Apple directory submission is optional.

1. Wait for the Pages workflow and confirm the feed URL returns HTTP 200.
2. On iPhone: Podcasts → Library → Follow a Show by URL.
3. Verify cover art, show notes, latest date, duration, streaming, download, seeking, speed control, and offline
playback.
4. Connect CarPlay and verify discovery, play/pause, rewind, forward, resume after reconnect, and next-day discovery.
5. Record subscriber-visible publication time for seven consecutive days, including one quiet day or simulated missed
run.
6. Submit the feed through Apple Podcasts Connect only after this pilot if public directory listing is desired.

## Current limitations requiring owner action

- GitHub Pages must be enabled with **GitHub Actions** as its source before the first subscriber-facing publication.
- A supported paid TTS provider requires an owner-supplied API key; consumer ChatGPT/Copilot subscriptions do not supply
  a general workflow API key.
- Apple Podcasts, CarPlay, automatic downloads, and the seven-day pilot require the owner's iPhone and vehicle.
