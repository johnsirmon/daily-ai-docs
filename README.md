# Daily AI Developer Brief — 2026-09-28

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

### OpenAI Codex rust-v0.158.0

**What to know:** New Features Configure copy-on-select and right-click paste in the fullscreen TUI. Copied transcript selections now preserve Markdown formatting. (#47639, #47896, #48118) Connect to MCP servers that require pre-registered OAuth client secrets, including through codex mcp add --oauth-client-secret. … [Excerpt; see source for full details.]

**What changes for developers:** (#47639, #47896, #48118) Connect to MCP servers that require pre-registered OAuth client secrets, including through codex mcp add --oauth-client-secret. (#47484, #47956) Terminal input approval is enabled by default for commands running with elevated permissions. (#47799, #48073) Bug Fixes Fixed Windows sandbox failures involving ordinary Windows 10 paths, rejected stored credentials, and large permission policies. (#47672, #47695, #47919) Fixed Linux sandbox startup with nested writable roots and preserved Git metadata protections across writable roots on Linux and macOS. … [Excerpt; see source for full details.]

**Recommendation:** WATCH — No additional workflow change is supported beyond the cited evidence.

Sources: [1](https://github.com/openai/codex/releases/tag/rust-v0.158.0)

### Claude Code v2.1.284

**What to know:** What's changed Added Claude Sonnet 5.5 (claude-sonnet-5-5), now the default Sonnet model on the Anthropic API — 1M context, $2/$10 per Mtok with $0.20/Mtok cache reads Added a "Yes, but ask again next time" answer to auto mode's prompt before a read outside the working directories, so you can allow that one read and still be asked about later ones Added dollar amounts to the Claude apps gateway spend limit in /usage and the status line (for example "$271.40 / $500.00 spent this month") when the gateway runs this version or later; the status line's rate_limits.spend_limit also gains used_usd, limit_usd and period Added effortSlider:decreaseEffort, increaseEffort and toggleUltracode keybinding actions, so … [Excerpt; see source for full details.]

**What changes for developers:** What's changed Added Claude Sonnet 5.5 (claude-sonnet-5-5), now the default Sonnet model on the Anthropic API — 1M context, $2/$10 per Mtok with $0.20/Mtok cache reads Added a "Yes, but ask again next time" answer to auto mode's prompt before a read outside the working directories, so you can allow that one read and still be asked about later ones Added dollar amounts to the Claude apps gateway spend limit in /usage and the status line (for example "$271.40 / $500.00 spent this month") when the gateway runs this version or later. … [Excerpt; see source for full details.]

**Recommendation:** WATCH — No workflow change is supported beyond the cited evidence.

Sources: [1](https://github.com/anthropics/claude-code/releases/tag/v2.1.284)

## High noise / low signal

- Excluded OpenAI Codex: no substantive change evidence.
- Excluded Gemini CLI: no substantive change evidence.

## Editorial contract

- Scheduled daily at **10:17 UTC**; GitHub Actions timing is best-effort.
- One to three useful stories, at most one per canonical product and one research item; thin-news runs skip instead of padding.
- Opt-in grounded editorial mode groups meaningful changes into 5–8-minute briefs without changing the feed on thin-news days.
- Grounded mode can include one reviewed recent-paper takeaway, with its method, limitations, and practical experiment; it does not repeat papers as filler.
- Product-change claims require public primary evidence.
- Every story ends with an `ACT`, `WATCH`, or `SKIP` recommendation.
- Routine patches, repeated announcements, unsupported adoption claims, and engagement-only rankings are filtered out.
- At most one transcript-backed YouTube learning pick may appear; it never replaces vendor evidence.

## Tracked areas

The active `daily.sources` configuration in [`topics/topics.yaml`](topics/topics.yaml) monitors public releases and feeds for GitHub Copilot, VS Code, OpenAI Codex, Claude Code, Gemini CLI, Hermes Agent, MCP, and Agent Skills. Evaluation and observability are covered through bounded YouTube learning discovery rather than dedicated primary-source collectors.

## Source health

- `feed:https://github.blog/changelog/feed/`: ok:0
- `github:NousResearch/hermes-agent`: ok:0
- `github:agentskills/agentskills`: ok:0
- `github:anthropics/claude-code`: ok:1
- `github:google-gemini/gemini-cli`: ok:1
- `github:microsoft/vscode`: ok:0
- `github:microsoft/vscode-copilot-release`: ok:0
- `github:modelcontextprotocol/specification`: ok:0
- `github:openai/codex`: ok:8
- `youtube:weekly-digest`: error:ValueError

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
