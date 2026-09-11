# Daily AI Developer Brief — 2026-09-11

A concise, source-backed daily podcast for AI agent developers: what changed, why it matters, what is worth learning, and whether to act, watch, or skip.

## Podcast

Intended subscriber feed: `https://johnsirmon.github.io/daily-ai-docs/podcast.xml`

Publication is confirmed only after the subscriber feed, audio, and artwork pass delivery checks.

Once the feed is live, open Apple Podcasts on iPhone → Library → Follow a Show by URL and paste it. CarPlay uses the followed show through Apple Podcasts; device playback still requires verification.

See [operations and setup](docs/OPERATIONS.md#github-setup) for deployment status and setup.

## Today's signal

### OpenAI Codex python-v0.154.0

**What changed:** Install with pip install --upgrade openai-codex==0.154.0 (Python 3.10 or later). This release includes the matching openai-codex-cli-bin==0.154.0 runtime. - Add max and ultra reasoning-effort values. 39662 - Add ExternalMessage to synchronous and asynchronous run() and turn() calls. External content can start a turn or join an active regular turn with tool-level authority; it does not grant user authorization. Consumers receive independent event streams. 44086 - Add include_turns on resume/fork, turn_service_tier for one newly started turn, and source metadata. History selection changes the returned response, not model context. Existing defaults are preserved when these options are omitted. 44084 - Refresh generated protocol models and notifications, and preserve completion events that arrive before a turn-start response. 44032, 44400 Check these migrations when upgrading: - HookMetadata

**Why it matters:** Check your current tooling or upgrade path because this may require a change.

**Recommendation:** ACT — Primary source; relevance score 20.

Sources: [1](https://github.com/openai/codex/releases/tag/python-v0.154.0)

### Claude Code v2.1.268

**What changed:** What's changed - Added to the Claude apps gateway: with pricing: set in gateway.yaml, signed-in Claude Code clients receive the same rates through managed settings, so /cost and telemetry match the spend meter - Added a startup warning for gateways when access_control.allow_cidrs is empty, and a one-time warning the first time a request arrives from a public address - Added the gatewayInternalNetworks managed setting, letting administrators allow /login to a Claude apps gateway on their organization's own public IPv4 block - Added claude self-hosted-runner --remove-session-state (default off): delete each session's per-session directories under /_sessions/ when the session ends - Added configDirectory to the output of claude auth status --json - Added --json to claude plugin install, uninstall, update, enable and disable, and errorDetails/noteDetails to each row of claude plugin list --j

**Why it matters:** This is relevant to developers tracking AI coding agents.

**Recommendation:** WATCH — Primary source; relevance score 18.

Sources: [1](https://github.com/anthropics/claude-code/releases/tag/v2.1.268)

### MAI-Code-1-Flash deprecated

**What changed:** We have deprecated MAI-Code-1-Flash across all GitHub Copilot experiences (including Copilot Chat, inline edits, ask and agent modes, and code completions) today, September 10, 2026. Model Deprecation date Suggested alternative&#8230; The post MAI-Code-1-Flash deprecated appeared first on The GitHub Blog .

**Why it matters:** Check your current tooling or upgrade path because this may require a change.

**Recommendation:** ACT — Primary source; relevance score 20.

Sources: [1](https://github.blog/changelog/2026-09-10-mai-code-1-flash-deprecated)

### OpenAI Codex rust-v0.155.0-alpha.3.9

**What changed:** Release 0.155.0-alpha.3.9

**Why it matters:** This is prerelease information; avoid changing production workflows without a specific need.

**Recommendation:** SKIP — Primary source; relevance score 20.

Sources: [1](https://github.com/openai/codex/releases/tag/rust-v0.155.0-alpha.3.9)

### OpenAI Codex rust-v0.155.0-alpha.3.8

**What changed:** Release 0.155.0-alpha.3.8

**Why it matters:** This is prerelease information; avoid changing production workflows without a specific need.

**Recommendation:** SKIP — Primary source; relevance score 20.

Sources: [1](https://github.com/openai/codex/releases/tag/rust-v0.155.0-alpha.3.8)

### OpenAI Codex rust-v0.155.0-alpha.3.7

**What changed:** Release 0.155.0-alpha.3.7

**Why it matters:** This is prerelease information; avoid changing production workflows without a specific need.

**Recommendation:** SKIP — Primary source; relevance score 20.

Sources: [1](https://github.com/openai/codex/releases/tag/rust-v0.155.0-alpha.3.7)

### OpenAI Codex rust-v0.155.0-alpha.3

**What changed:** Release 0.155.0-alpha.3

**Why it matters:** This is prerelease information; avoid changing production workflows without a specific need.

**Recommendation:** SKIP — Primary source; relevance score 20.

Sources: [1](https://github.com/openai/codex/releases/tag/rust-v0.155.0-alpha.3)

## High noise / low signal

- Skipped Gemini CLI: routine or prerelease-only update.

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

- `feed:https://github.blog/changelog/feed/`: ok:1
- `github:NousResearch/hermes-agent`: ok:0
- `github:agentskills/agentskills`: ok:0
- `github:anthropics/claude-code`: ok:1
- `github:google-gemini/gemini-cli`: ok:1
- `github:microsoft/vscode`: ok:0
- `github:microsoft/vscode-copilot-release`: ok:0
- `github:modelcontextprotocol/specification`: ok:0
- `github:openai/codex`: ok:10
- `youtube:weekly-digest`: ok:0

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
