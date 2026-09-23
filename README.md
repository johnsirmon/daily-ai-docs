# Daily AI Developer Brief — 2026-09-23

<p align="center">
  <img src="assets/ai-update-wave.png" width="560" alt="An exhausted developer outrunning a tidal wave of AI tools and updates">
</p>
<p align="center"><em>Keep up with AI developer technology without being flattened by the update wave.</em></p>

A source-backed briefing for AI developers: what changes your work, what is worth trying, and what to ignore.

## Podcast

Intended subscriber feed: `https://johnsirmon.github.io/daily-ai-docs/podcast.xml`

Publication is confirmed only after the subscriber feed, audio, and artwork pass delivery checks.

Once the feed is live, open Apple Podcasts on iPhone → Library → Follow a Show by URL and paste it. CarPlay uses the followed show through Apple Podcasts; device playback still requires verification.

See [operations and setup](docs/OPERATIONS.md#github-setup) for deployment status and setup.

## How it works

1. Public primary sources are collected with per-source health reporting.
2. Ranking and editorial checks reject repeats, routine noise, and unsupported claims.
3. The episode manifest binds every selected story to its evidence and becomes the source of truth.
4. Narration or reviewed browser audio is validated before an immutable release is created.
5. Publication is confirmed only after the feed serves the exact expected episode and media bytes.

A healthy thin-news day can intentionally skip publication. Failures before candidate publication leave the existing subscriber feed untouched. A delivery failure after deployment can leave an unconfirmed candidate visible; it must be recovered without replacing its audio or advancing novelty state.

```mermaid
flowchart TD
    schedule["Daily schedule or manual run"] --> prepare["Collect and select public evidence"]
    config["topics/topics.yaml"] --> prepare
    weekly["Weekly YouTube digest"] --> prepare
    prepare -->|Healthy thin-news day| skip["Record skip; keep existing feed"]
    prepare -->|Selected stories| script["Episode manifest and narration"]
    script -->|Text to speech| validate["Validate media, duration and checksum"]
    reviewed["Operator-reviewed Notebook audio or special"] --> validate
    validate --> release["GitHub Release: immutable MP3 and manifest"]
    release --> candidate["Verify release; commit candidate RSS, README and manifest"]
    candidate --> pages["Deploy RSS and artwork to GitHub Pages"]
    pages -->|Discover episodes| clients["Apple Podcasts and other RSS apps"]
    release -->|Stream or download MP3| clients
    clients --> carplay["CarPlay through the iPhone app"]
    pages --> delivery["Check exact public GUID, audio bytes and artwork"]
    release --> delivery
    delivery --> confirmed["Confirm receipt and advance novelty state"]
```

Approved manual imports join the same serialized publisher; issue intake and unpublished previews do not publish episodes. The diagram shows the successful publication path and intentional skip; validation failures stop the run. HTTP delivery checks do not certify iPhone or CarPlay playback.

## When and where it publishes

| Process | Trigger / target time | Result |
| --- | --- | --- |
| [Daily publisher](.github/workflows/update-radar.yml) | Daily **10:17 UTC** (06:17 EDT / 05:17 EST), or manual | Evaluates new evidence; publishes only when gates pass. |
| [Reviewed imports and specials](docs/OPERATIONS.md#publishing-approved-notebook-audio) | Manual, after review and authorization | Uses the daily publisher with a `reviewed_episode` release tag. |
| [Pages recovery](.github/workflows/pages.yml) | Relevant pushes to `main`, or manual | Redeploys the existing feed and artwork; does not generate audio. |
| [Feed health](.github/workflows/feed-health.yml) | Daily **12:47 UTC** (08:47 EDT / 07:47 EST), or manual | Checks delivery and a 25-hour freshness budget; accepts verified intentional skips and reports failures in an issue. |
| [YouTube discovery](.github/workflows/youtube-trends.yml) | Sunday **11:23 UTC** (07:23 EDT / 06:23 EST), or manual | Updates an input digest, not a standalone podcast episode. |

These are GitHub Actions schedule targets, not guaranteed release times. Publication requires preparation, release upload, Pages deployment, and subscriber-facing verification. Apple Podcasts refreshes and downloads independently; there is no scheduled push directly to Apple or CarPlay.

- **Discovery:** [RSS feed](https://johnsirmon.github.io/daily-ai-docs/podcast.xml) and show artwork on GitHub Pages. The Pages site does not host episode MP3s or the rendered README.
- **Audio:** [GitHub Releases](https://github.com/johnsirmon/daily-ai-docs/releases), using a permanent, unique enclosure URL for each episode. Released bytes and GUIDs are never replaced.
- **Written brief:** this README on the repository's `main` branch, generated from the episode manifest.
- **Audit trail:** [`data/episodes`](data/episodes), [`data/receipts`](data/receipts), [`data/runs/latest.json`](data/runs/latest.json), and [`data/state.json`](data/state.json). The manifest/RSS timestamp is assigned before delivery; `confirmed_at` records successful verification.

Daily publishing, standalone Pages deployment, and weekly digest writes share the non-cancelling `podcast-publisher` lock. The daily job deploys Pages inline rather than waiting on another locked job. See [publishing review and optimization priorities](docs/OPERATIONS.md#publishing-review-and-optimization-priorities).

## Try the Notebook browser pilot

1. Sign in to Gemini Notebook and create a dedicated notebook for the pilot.
2. Add only the selected public primary-source URLs; include full methods and limitations for research.
3. Configure an English Deep Dive targeting 5–8 minutes with concrete changes, implications, and caveats.
4. Generate once, download once, and complete the native Save dialog manually if the browser cannot.
5. Preserve the original file, fully decode it, measure its duration, and record its size and SHA-256.
6. Review the transcript and consequential spoken claims against the imported primary sources.

The pilot uses the signed-in account's existing allowance. It does not authorize a paid upgrade, cookie export, unattended browser automation, or publication. Approved recordings use the separate [reviewed-audio handoff](docs/OPERATIONS.md#publishing-approved-notebook-audio).

## Today's signal

### OpenTelemetry in the GitHub Copilot app

**What to know:** GitHub added OpenTelemetry configuration for the GitHub Copilot app through enterprise-managed settings, allowing administrators to export agent activity to compatible monitoring tools.

**What changes for developers:** Enterprise teams can follow model and tool activity through an agent session, inspect step-by-step traces when behavior is unexpected, and apply the monitoring configuration centrally.

**Recommendation:** WATCH — Pilot export from a limited group to a secured existing OpenTelemetry backend, validate trace usefulness and access controls, and keep prompt and response capture disabled unless a reviewed need justifies enabling it.

Sources: [1](https://github.blog/changelog/2026-09-22-opentelemetry-in-the-github-copilot-app/)

### Security improvements for SSH

**What to know:** GitHub announced removal of RSA/SHA-1 SSH signatures and diffie-hellman-group-exchange-sha256, a 3072-bit minimum for newly uploaded RSA keys after October 14, 2026, and support for ML-KEM hybrid key exchange on most GitHub cloud SSH sessions.

**What changes for developers:** Older Git clients, embedded SSH libraries, build servers, or automation can lose Git-over-SSH connectivity during brownouts and eventual removal if they still negotiate the retired algorithms.

**Recommendation:** ACT — Inventory Git-over-SSH clients before the November 4 and December 9 brownouts. Confirm RSA uses SHA-2 or move new keys to Ed25519; upgrade clients that lack modern signature and key-exchange support. Ignore this item if every relevant remote uses HTTPS.

Sources: [1](https://github.blog/changelog/2026-09-22-security-improvements-for-ssh)

### Deprecation notice: All-platform CodeQL bundle

**What to know:** GitHub deprecated the combined all-platform CodeQL bundle starting with CodeQL CLI 2.27.0 and says it will remove the bundle in mid-March 2027.

**What changes for developers:** Bootstrap scripts, offline mirrors, CI images, or internal installers that hard-code the combined archive names must select an operating-system and architecture-specific artifact instead.

**Recommendation:** ACT — Search automation for codeql-bundle.tar.gz and codeql-bundle.tar.zst, make platform and architecture selection explicit, and test replacement artifacts before March 2027.

Sources: [1](https://github.blog/changelog/2026-09-22-deprecation-notice-all-platform-codeql-bundle/)

## High noise / low signal

- High noise / low signal: same-day Copilot model-availability announcements establish catalog access but provide no reproducible evidence that switching models improves a concrete developer workflow; they were excluded.
- High noise / low signal: the Copilot for JetBrains page was fresh, but the available extracted body was incomplete and mostly exposed a feature list without enough directly verified consequence and caveat detail for this edition.
- High noise / low signal: current VS Code results in the bounded sample were outside the 36-hour window, so older automation and Agents-window changes were not recycled.
- Coverage warning: configured Exa authentication returned HTTP 401 and broader Hermes, MCP, and open-source ecosystem coverage is incomplete. This is a source-verified but degraded scan, not a comprehensive no-news claim.

## Editorial contract

- This edition uses user-authorized Gemini Notebook web audio, a local-ASR transcript, and an assistant transcript/source comparison; it is not independently verified Gemini API generation.

- Scheduled daily at **10:17 UTC**; GitHub Actions timing is best-effort.
- One to three useful stories, at most one per canonical product and one research item; thin-news runs skip instead of padding.
- Opt-in grounded editorial mode groups meaningful changes into 5–8-minute briefs without changing the feed on thin-news days.
- Grounded mode can include one reviewed recent-paper takeaway, with its method, limitations, and practical experiment; it does not repeat papers as filler.
- Product-change claims require public primary evidence.
- This edition preserves a conversational format; `ACT`, `WATCH`, or `SKIP` recommendations appear in the written story notes, not as required spoken endings.
- Routine patches, repeated announcements, unsupported adoption claims, and engagement-only rankings are filtered out.
- At most one transcript-backed YouTube learning pick may appear; it never replaces vendor evidence.

## Tracked areas

The active `daily.sources` configuration in [`topics/topics.yaml`](topics/topics.yaml) monitors public releases and feeds for GitHub Copilot, VS Code, OpenAI Codex, Claude Code, Gemini CLI, Hermes Agent, MCP, and Agent Skills. Evaluation and observability are covered through bounded YouTube learning discovery rather than dedicated primary-source collectors.

## Source health

- `observer`: degraded:3 source-verified findings; Exa 401; broader coverage incomplete

Each edition manifest distinguishes healthy no-news results from source outages.

## Publication flow

`collect → select → manifest → narrate/audio → validate → publish → verify delivery → confirm`

The versioned episode manifest is the source of truth for narration, show notes, and this README. Preparation and failed delivery do not advance novelty state.
All intentional skips have durable run receipts. Monitoring still verifies the last confirmed feed, audio, and artwork and rejects failed or stale evaluations.

## Weekly YouTube signal

The Sunday **11:23 UTC** workflow runs four focused searches and retains up to five videos with short transcript-derived takeaways. Full transcripts are never committed, and at most one deduplicated learning pick may enter a daily edition.

## Development

```bash
# Reproducible test suite
uv run --with-requirements requirements.lock pytest -q

# Network-free manifest preparation; writes only under .cache/
uv run --with-requirements requirements.lock \
  python -m pipeline.daily prepare --dry-run --no-audio
```

Preparation does not publish or modify the subscriber feed. See [operations and setup](docs/OPERATIONS.md) for credentials, deployment, recovery, and manual commands.
