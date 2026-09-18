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

Keep `TTS_PROVIDER=edge` for the existing no-key deployment. It is treated as best-effort and must pass full decode,
duration, and size checks before publication. `TTS_PROVIDER=openai` is an optional paid alternative requiring a supported
audio API and `OPENAI_API_KEY`; enabling it is a separate cost decision, never an automatic fallback.

## Grounded editorial mode

The new mode is **opt-in**: `AI_EDITORIAL=off` remains the workflow default so that deploying code without a Gemini
key does not break the existing publisher. The legacy `AI_SYNTHESIS` setting only prioritizes action labels; enabling
it alone does not produce better explanations.

With `AI_EDITORIAL=required`, the publisher:

- Rejects version-only releases, generic maintenance notes, and insufficient evidence before scoring.
- Groups related product releases rather than reading a segment for every tag.
- Compares evidence with confirmed publication history. Rejected candidates are not marked published.
- Uses a dedicated Gemini key for a bounded editorial draft and verification, with no paid, alternate-provider,
  or deterministic publication fallback on failure.
- Explains the actual change, affected workflow, practical consequence, and justified next step.
- Optionally includes one research-paper takeaway inside the same listening budget. Papers require available
  full-text evidence, method, result, limitations, and a practical experiment; collection alone is not review.
- Requires normal audio to measure **300-480 seconds**. Word budgets guide preparation but do not replace measured
  duration. Short scripts are skipped, not padded; an unexpected audio duration is a validation failure.

### Free-tier-only activation

1. Create or choose a Gemini API project whose selected model has free-tier access, without paid billing enabled.
   Check the actual project's model availability and quotas: a Google AI/Notebook subscription is separate from API
   access, and a cost alert is not a hard spending cap.
2. Store the dedicated key as the `GEMINI_API_KEY` GitHub Actions secret. Never paste a real key into chat, source,
   issue text, logs, or example commands. Do not reuse an OpenAI key or export consumer-account cookies.
3. Set `GEMINI_MODEL` to a verified free-tier model. The default is `gemini-3.8-flash`, using Google's documented
   OpenAI-compatible endpoint. No NotebookLM wrapper package is required.
4. Validate an unpublished sample and its grounded claims before activation. Browser generation and live publishing
   are separate operational actions; ordinary tests mock providers and do not consume account quotas.
5. Set repository variable `AI_EDITORIAL=required`. Keep `TTS_PROVIDER=edge` for the existing no-key audio path.
   Setting another TTS provider is a separate cost decision, not an automatic fallback.

The free Gemini API tier may use submitted content to improve Google's products. Only approved public source material
and public episode history may be sent. Authentication, quota, timeout, schema, grounding, or verification failures stop
publication and retain the last good feed.

Both Gemini requests explicitly use the documented `reasoning_effort=low` setting rather than inheriting the model's
default thinking level. Draft and verification output remain capped at 4,000 and 2,500 tokens respectively, with no
automatic retries. Incomplete responses still fail; diagnostics record only allowlisted finish reasons and numeric
HTTP statuses, never raw provider responses or credentials.
Quantitative validation requires each claim's numbers to be supported by its own quoted evidence, not merely by a
release title or a different claim. Rejections expose only bounded numeric tokens for diagnosis, not rejected drafts.

`daily.editorial` in [topics.yaml](../topics/topics.yaml) controls grouping and script budgets. Daily evaluation does
not promise daily audio. A short urgent-alert exception and research-only editions are not enabled.

### Research evidence

The first-party paper collector uses bounded primary arXiv metadata and available HTML full text. Initial eligibility
requires first publication within the last 30 days. An updated timestamp alone does not make an old paper new.
Unavailable or oversized full text is explicitly rejected rather than summarized from an abstract as though fully
reviewed. Paper identities are checked against confirmed episodes so the same paper is not repeated each day.

Numerical results must retain their evaluation setting and important limitations. Label author-reported/preprint
findings honestly; do not describe benchmark results as independently reproduced or as shipped product capabilities.

Paper `queries` are literal topic phrases, not raw arXiv query expressions. Discovery, full-text attempts, response
sizes, and model context are bounded. Recent model context is capped independently from confirmed novelty history.
Full text is used in memory for review, then removed before any episode manifest is saved. Publication retains only
short supporting excerpts (at most 180 quoted words per source), provenance hashes, and independently verified
paraphrases. Long verbatim spoken passages are rejected. Archived research excerpts can validate immutable recovery
but cannot stand in for full text during a new paper review.

Public article enrichment is configured per GitHub/feed source through `enrichment.enabled` and exact `allowed_hosts`.
The daily orchestrator disables these extra fetches outside grounded mode. VS Code release-note links and GitHub Blog
excerpts have curated allowlists. Failed enrichment records degraded health and summary-only evidence; it does not
invent article content. Per-candidate/detail diagnostics remain visible without counting as additional configured
sources in the health quorum.

### Intentional skips and monitoring

A healthy run with insufficient new information writes `data/runs/latest.json` and a skipped preparation outcome.
It does not synthesize audio, create a release, modify RSS, deploy Pages, or advance published-event history. A script
rejected for insufficient material can also skip after editorial evaluation but before TTS.

The independent monitor runs `pipeline.health --max-age-hours 25 --allow-editorial-skips`. A fresh healthy skip
receipt must reference the exact last confirmed episode and its delivery receipt. Monitoring still checks that
subscriber-facing GUID, enclosure, media checksum, and artwork. A stale, failed, malformed, or mismatched run receipt
does not bypass feed checks. The publisher records downstream workflow failures with `pipeline.daily fail-run`;
pending immutable candidates remain recoverable.

### Unpublished listening preview

`pipeline.preview` runs the real grounded preparation stage in a temporary directory with a copy of confirmed
publication history. It requires explicit confirmation that the project is unbilled and the chosen model has usable
free-tier quota. Its model-metadata request verifies access, not billing eligibility. It makes at most two generation
requests with no retries, uses Edge TTS only, and never finalizes or confirms an episode.

The `Unpublished Editorial Preview` workflow has read-only repository permissions, checks out current `main` publication
history separately from feature code, and uploads only the preview report, verified script/manifest, show notes, and
validated audio. A thin-news skip is a valid reported outcome; provider or validation failures fail the run. Verified
scripts can remain available when audio fails, but unvalidated audio is never uploaded. Preview manifests are explicitly
marked and cannot be passed to publication finalization. The planned enclosure URL in a preview manifest is not uploaded.

During feature development, a push to `feature/grounded-daily-ai-brief` runs generation only when its commit message
contains `[editorial-preview]`; ordinary pushes skip the job. Manual dispatch is also supported once GitHub recognizes
the workflow. Confirm free-tier eligibility before every dispatch or marked push: the flag records operator confirmation,
not an automatic spending cap. This workflow neither enables billing nor changes the scheduled publisher's settings.
Artifacts contain public-source material and are not a private sharing channel.

For a local preview, provide the key through a secure environment, not command-line arguments, and use a new output
directory for each run:

```bash
AI_EDITORIAL=required TTS_PROVIDER=edge GEMINI_MODEL=gemini-3.8-flash \
  uv run --with-requirements requirements.lock python -m pipeline.preview \
  --history-root . --output-dir .cache/preview --free-tier-confirmed
```

### Notebook references, not dependencies

[notebooklm-py](https://github.com/teng-lin/notebooklm-py) and
[notebooklm-mcp](https://github.com/roomi-fields/notebooklm-mcp) are useful references for asynchronous audio generation,
source readiness, polling, and download. Their consumer integrations depend on undocumented endpoints and full-account
sessions. Reimplementing them locally would not remove those protocol and credential risks.

No wrapper dependency, copied implementation, or cookie-based production adapter is included. A separately authorized
Notebook audio comparison may be useful later. The official Google Cloud Podcast API is a different service; its cost
eligibility must be established separately and is not implied by a consumer subscription or Gemini API key.

### Browser-created Notebook listening samples

An explicitly authorized sample can instead be authored in the signed-in Gemini Notebook web UI using the account's
existing allowance. This does not use `GEMINI_API_KEY` and does not authorize a subscription upgrade or paid billing.
Consumer quotas and supported formats can change; check the current UI rather than assuming a fixed daily allowance.

Create a dedicated notebook and import only selected public primary URLs. Verify that a research source contains its
methods and limitations, not just an abstract. In Audio Overview, use English, Deep Dive, Short, and a custom briefing
targeting 5-8 minutes. Ask for concrete changes, affected workflows, practical implications, and essential caveats;
exclude routine version lists, generic product introductions, invented measurements, and long verbatim excerpts.
Length selection is only a request: verify the actual generated duration and review the spoken claims before approval.

Keep the notebook and audio unpublished during listening review. Download through the normal UI when available. A native
Save As dialog may require the operator to click Save; browser automation may not expose that dialog or capture the
download event. Do not retry downloads while confirmation is pending. Verify the saved file itself with full decoding
and measured duration, not just the Notebook's displayed length. This is an operator-assisted workflow.

Do not export browser cookies, copy private notebooks, or depend on undocumented consumer endpoints. A Notebook audio overview
does not satisfy the manifest's two-call Gemini verification contract by itself. Never invent API-call counts or mark it
verified to bypass the publisher. Use the reviewed-audio handoff below after explicit publication approval.
Unattended browser scheduling is not implemented.

### Publishing approved Notebook audio

Schema 3 is the separate reviewed-audio contract. It retains public source events and stories, an exact transcript hash,
the input audio hash, publication-authorization time, and transcript-to-source review claims. It does not claim two
Gemini API calls or independent model verification. Research still requires full-text review, archived supporting excerpts,
methods, limitations, and an author-reported/not-reproduced qualification. Full papers, private notebook identifiers,
account details, and browser cookies must not enter the release manifest.

Review the actual recording before preparing the draft manifest. Local ASR can assist, but disclose its uncertainties.
Correct material errors before publication. An optional, explicitly recorded spoken editorial prefix can clarify an error
in the otherwise intact conversation; its exact text and audio hash are retained separately from the original recording.
Keep the original download unchanged. The final audio must remain within 300-480 seconds.

Import a schema-3 draft and the reviewed source recording into a **new, unused** output directory:

```bash
uv run --with-requirements requirements.lock python -m pipeline.reviewed_audio \
  --manifest /absolute/path/to/reviewed-draft.json \
  --audio /absolute/path/to/reviewed-recording.m4a \
  --output-dir .cache/reviewed-release
```

The importer validates provenance, converts to MP3 once, performs full media checks, and writes `daily-ai-brief.mp3`,
`episode-manifest.json`, and local `publication.json`. It makes no model, TTS, upload, feed, or state changes. It refuses
preview flags, mismatched source hashes, and reused output directories, including directories from failed imports.

After all tests pass and the reviewed-audio code is on `main`, create a **new** public release named exactly as the
manifest's episode ID, attaching only the prepared MP3 and manifest. Never use `gh release upload --clobber`. If the
release already exists, download and reconcile its existing assets rather than regenerating them.

Run **Actions -> Daily AI Developer Brief -> Run workflow** on `main`, setting `reviewed_episode` to that release tag.
Equivalently:

```bash
gh workflow run update-radar.yml --ref main -f reviewed_episode="$EPISODE_ID"
```

The existing workflow shares `podcast-publisher` concurrency. It rejects draft/prerelease assets, downloads the exact
manifest/MP3, verifies identity and local media again, then uses the normal remote verification, candidate RSS, Pages,
subscriber GUID, and confirmation steps. An empty input retains the normal daily preparation path. This manual import
does not activate scheduled Notebook generation or change the configured model/TTS provider.

For recovery, rerun the same workflow with the same release tag. Do not rebuild or replace its media. A pending different
candidate blocks the import until recovered. A confirmed episode must not be promoted again as a new episode.

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

In legacy mode, deterministic stories are available from validated source evidence. Optional AI synthesis performs at most one
call over the selected events. External source text is labeled untrusted in the prompt, output must reference known
event IDs, and all output is schema-validated. `AI_SYNTHESIS=required` fails closed if the provider or schema fails.
Grounded editorial mode has a different, versioned contract with a bounded draft and independent verification.
It never publishes the legacy deterministic fallback when a required editorial stage fails.

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
