# Daily AI Developer Brief — 2026-09-14

A concise, source-backed daily podcast for AI agent developers: what changed, why it matters, what is worth learning, and whether to act, watch, or skip.

## Podcast

Intended subscriber feed: `https://johnsirmon.github.io/daily-ai-docs/podcast.xml`

Publication is confirmed only after the subscriber feed, audio, and artwork pass delivery checks.

Once the feed is live, open Apple Podcasts on iPhone → Library → Follow a Show by URL and paste it. CarPlay uses the followed show through Apple Podcasts; device playback still requires verification.

See [operations and setup](docs/OPERATIONS.md#github-setup) for deployment status and setup.

## Today's signal

### Hermes Agent v2026.9.14

**What changed:** Hermes Agent v0.21.3 (v2026.9.14) Release Date: September 14, 2026 > Patch release. This tag rolls up the ~338 PRs merged since v0.21.2 into a stable tagged release for downstream consumers (Docker images, Hermes Cloud, hosted deployments). It exists so the remote-gateway sign-in fixes below reach Cloud agents, which auto-update to the newest release tag. … [Excerpt; see source for full details.]

**Why it matters:** This is relevant to developers tracking AI agents.

**Recommendation:** WATCH — Read the primary source and assess applicability before changing your workflow.

Sources: [1](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.9.14)

### OpenAI Codex rust-v0.155.0-alpha.4

**What changed:** Release 0.155.0-alpha.4

**Why it matters:** This is prerelease information; avoid changing production workflows without a specific need.

**Recommendation:** SKIP — Evaluate only in an isolated test environment if the cited change addresses a current need.

Sources: [1](https://github.com/openai/codex/releases/tag/rust-v0.155.0-alpha.4)

## High noise / low signal

- Skipped Gemini CLI: below threshold after routine/prerelease penalties.

## Editorial contract

- Scheduled daily at **10:17 UTC**; GitHub Actions timing is best-effort.
- Up to seven actionable stories, with shorter alerts and healthy quiet-day editions.
- Product-change claims require public primary evidence.
- Every story ends with an `ACT`, `WATCH`, or `SKIP` recommendation.
- Routine patches, repeated announcements, unsupported adoption claims, and engagement-only rankings are filtered out.
- At most one transcript-backed YouTube learning pick may appear; it never replaces vendor evidence.

## Tracked areas

The active `daily.sources` configuration in [`topics/topics.yaml`](topics/topics.yaml) monitors public releases and feeds for GitHub Copilot, VS Code, OpenAI Codex, Claude Code, Gemini CLI, Hermes Agent, MCP, and Agent Skills. Evaluation and observability are covered through bounded YouTube learning discovery rather than dedicated primary-source collectors.

## Source health

- `feed:https://github.blog/changelog/feed/`: ok:0
- `github:NousResearch/hermes-agent`: ok:1
- `github:agentskills/agentskills`: ok:0
- `github:anthropics/claude-code`: ok:0
- `github:google-gemini/gemini-cli`: ok:1
- `github:microsoft/vscode`: ok:0
- `github:microsoft/vscode-copilot-release`: ok:0
- `github:modelcontextprotocol/specification`: ok:0
- `github:openai/codex`: ok:1
- `youtube:weekly-digest`: degraded:0

Each edition manifest distinguishes healthy no-news results from source outages.

## Publication flow

`collect → select → manifest → narrate/audio → validate → publish → verify delivery → confirm`

The versioned episode manifest is the source of truth for narration, show notes, and this README. Preparation and failed delivery do not advance novelty state.

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
