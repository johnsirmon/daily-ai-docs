# Copilot Instructions for daily-ai-docs

## Purpose

This repo is a **personal AI skills tracker** — a GitHub Actions pipeline that scans
GitHub for new/trending AI repositories and recent releases, then publishes a single
`README.md` summarising what changed in the last 2 weeks and what skills are worth
learning. Anyone can fork and follow it.

---

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run full test suite
python -m pytest tests/ -v

# Run a single test
python -m pytest tests/test_dedupe.py::test_duplicate_keeps_higher_stars -v

# Local dry-run (no network calls, writes placeholder README.md)
python -m pipeline.main --dry-run

# Use a custom config file
python -m pipeline.main --config path/to/topics.yaml

# Regenerate podcast from existing README.md (no pipeline re-run)
python -m pipeline.main --podcast-only

# Podcast-only dry-run (skips TTS, writes placeholder podcast.xml entry)
python -m pipeline.main --podcast-only --dry-run

# Live run (requires GITHUB_TOKEN in environment)
python -m pipeline.main
```

---

## Target Architecture

### Trigger

A `workflow_dispatch` GitHub Actions workflow so the report can be regenerated on
demand from the GitHub mobile app or web UI. Optionally also runs on a weekly `schedule`.

### Pipeline stages

```
search_trending()        →  fetch GitHub Search API for new/rising repos per topic
fetch_releases()         →  fetch recent releases from pinned repos in topics/topics.yaml
                            (dedupe.py exists as a utility but is NOT called in main;
                             repos and releases stay in per-topic lists)
enrich_items()           →  per-repo stats for top-4 per topic (forks, commit velocity,
                            PRs, contributors); cached .cache/enrich/; max 3 concurrent

run_research_summary()   →  NEW — receives ALL collected items across topics; single
                            gpt-4o-mini call; produces ResearchReport with week_story,
                            narrative_hook, topic_insights; cached .cache/research_YYYY-MM-DD.json;
                            fail-open (returns empty report on any API error)

generate_repo_deepdive() →  gpt-4o prose per repo (~200 words)
generate_topic_meta()    →  gpt-4o-mini JSON (why, learn, community_pulse, action_items)
                            + optional context= string injected from research report
_save_checkpoint()       →  write .cache/pipeline_checkpoint.json (dict with topics + research_report)
render_readme()          →  narrative sections + tables + "## 🗞️ This Week's Story" block
commit_readme()          →  git commit + push via actions/checkout or gh CLI

# Podcast path (PUBLISH_PODCAST=1 or --podcast flag):
readme_to_narration()    →  spoken script; prepends cold-open from research_report.narrative_hook
generate_audio()         →  edge-tts primary → OpenAI TTS fallback → radar.mp3
prepend_episode()        →  update podcast.xml (RSS 2.0 + iTunes namespace)
gh release create        →  upload radar.mp3 to dated GitHub Release
commit podcast.xml       →  subscribers auto-get new episodes
```

### ResearchReport schema

```python
{
  "week_story":     str,   # 100-150 word narrative: the big theme across all topics
  "narrative_hook": str,   # 1-2 sentence spoken cold-open ("This week in AI…")
  "topic_insights": dict,  # optional per-topic-id extra context string
}
```

All fields default to `""` / `{}` when the API is unavailable — pipeline continues
unchanged (fail-open). Cache key: `.cache/research_YYYY-MM-DD.json`.

All stages are pure Python functions in `pipeline/`. The orchestrator is
`pipeline/main.py`. Config lives entirely in `topics/topics.yaml`.

### Authentication

Use the built-in `GITHUB_TOKEN` (automatically available in every GitHub Actions run)
for **both** the GitHub Search/REST API and the **GitHub Models API**
(`https://models.inference.ai.azure.com`). No extra secrets or API keys are needed.

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ["GITHUB_TOKEN"],
)
```

### Output: README.md

The README is the only output. Structure:

```
# AI Skills Radar — <date>
_Updated: <ISO datetime> | Covers last 14 days_

## Topics
- [Topic Name](#topic-name)

---

## <Topic Name>
> Why it matters: <AI-generated blurb>
> What to learn: <AI-generated skill recommendation>

### New & Rising Repos
| Repo | Stars | Description |
...

### Recent Releases
| Repo | Version | Date | Notes |
...
```

---

## Config: topics/topics.yaml

This is the only file you edit to control what the pipeline tracks.

```yaml
settings:
  lookback_days: 14       # how far back to scan
  min_stars: 10           # ignore repos below this threshold
  top_n_per_topic: 8      # max repos shown per topic in README
  enrich_stats: true      # fetch enriched stats (forks, commits, PRs) for top-4 repos

topics:
  - id: mcp               # slug used in code; must be unique, lowercase-kebab
    display: "MCP Ecosystem"
    keywords:             # used in GitHub search queries (capped at 3 per topic to avoid rate limits)
      - "model context protocol"
      - "mcp server"
    pinned_repos:         # always fetch releases from these
      - modelcontextprotocol/specification
      - modelcontextprotocol/servers
```

---

## Item schema

All pipeline data flows as plain `dict` lists. Two item types share the same list:

**`trending`** (from `search.py`):
```python
{
  "repo": "org/name", "url": "...", "stars": 123,
  "description": "full description (no truncation)",
  "language": "Python", "forks": 45, "open_issues": 12,
  "topics": ["ai", "llm"],
  "pushed_at": "...", "type": "trending",
  # after enrich_items():
  "watchers": 89, "created_at": "2023-06-01", "homepage": "...", "license": "MIT",
  "commit_trend": "rising",          # "rising" | "falling" | "flat"
  "weekly_commits": [5, 8, 12, 18],  # last 4 weeks
  "contributor_count": 34,
  "prs_merged_14d": 8,
}
```

**`release`** (from `releases.py`):
```python
{
  "repo": "org/name", "url": "...", "version": "v1.2",
  "name": "...", "published_at": "2026-01-01",
  "notes": "full release notes up to 3000 chars",
  "reactions": 42,
  "type": "release"
}
```

`render.py` splits on `item["type"]` to build the two separate tables. `blurbs.py` uses both types in the prompt.

`dedupe.py` deduplicates by `item["repo"]`, keeping highest-starred.

---

## render.py section order

Per-topic section order in README:

```
## <Topic>
> Why it matters / What to learn blurb

### Overview          ← summary paragraph (from topic_meta "why")
### 🔍 Repo Deep Dives  ← per-repo #### heading + stat line + 200w prose
### 📊 Community Pulse  ← community_pulse paragraph
### ✅ Action Items This Week
### 🌱 New & Rising Repos  ← quick reference table with forks/issues/language/trend cols
### 🚀 Recent Releases     ← table with Highlights column (first 120 chars of notes)
```

`render_readme(topics_data, lookback_days) -> str` builds the content string (used in tests).
`write_readme(topics_data, lookback_days, path="README.md") -> Path` calls `render_readme` and writes to disk.

TOC anchors use `topic["id"]` (the YAML slug), not `topic["display"]`. Keep `id` values stable.

---

## blurbs.py functions

Two generation functions replace the old single `generate_blurb()`:

- **`generate_topic_meta(topic_display, repos, releases) -> dict`** — uses `gpt-4o-mini` + `response_format=json_object`; returns `{why, learn, community_pulse, action_items}`. Quality gate: retries once if `why` word count < 40.
- **`generate_repo_deepdive(item, topic_display) -> str`** — uses `gpt-4o`; returns ~200-word Markdown prose (no JSON wrapper). Quality gate: retries once if word count < 150.
- **`generate_blurb()`** is kept as a backward-compat shim wrapping `generate_topic_meta`.

Both fall back to empty string/dict if the API is unavailable.

---

## Podcast modules

`pipeline/narrate.py` — `readme_to_narration(readme_content: str) -> str`: strips markdown tables, links, and TOC; retains topic headings + "Why it matters" / "What to learn" blurbs for speech.

`pipeline/tts.py` — `generate_audio(text: str) -> bytes | None`: tries `edge-tts` (Microsoft Edge neural TTS, no API key needed, voice `en-US-AriaNeural`) first; falls back to OpenAI TTS via GitHub Models (`tts-1`, voice `alloy`) if edge-tts fails. `write_audio(text, path)` writes the bytes to disk. Returns `None` and logs a warning if both methods fail.

`pipeline/podcast.py` — `render_feed(episodes) -> str`, `write_feed(...)`, `prepend_episode(episode, path="podcast.xml")`. Feed is RSS 2.0 + iTunes namespace. Episodes are newest-first; deduped by `guid`.

`podcast.xml` in repo root is the subscriber feed. Commit it to keep episode history.

### Enabling the podcast
- CLI: `python -m pipeline.main --podcast`
- Env var: `PUBLISH_PODCAST=1 python -m pipeline.main`
- Dry-run: `python -m pipeline.main --dry-run --podcast` (skips TTS, writes placeholder entry)

### Subscriber URL
```
https://raw.githubusercontent.com/{owner}/{repo}/main/podcast.xml
```
Paste into Apple Podcasts, Overcast, Pocket Casts, or any app that supports Apple CarPlay.

### Audio file URL pattern
```
https://github.com/{owner}/{repo}/releases/download/radar-YYYY-MM-DD/radar.mp3
```

---

## Coding conventions

- Python 3.9+; follow PEP 8; keep functions small and single-purpose
- All public pipeline functions must have docstrings
- Use `yaml.safe_load` (never `yaml.load`)
- Prefer `pathlib.Path` over `os.path`
- Do not hardcode dates — use `--date` CLI flag or `datetime.date.today()`
- Pass an explicit `now: datetime` parameter in tests for determinism
- Use `tempfile.TemporaryDirectory()` for file-output tests

### Test conventions

Each test file defines its own local factory helpers (e.g., `_repo()`, `_release()`, `_topic()`, `_ep()`) — there are no shared pytest fixtures. Follow this pattern when adding new tests.

### Markdownlint

A `.markdownlint.json` config enforces ATX headings, 2-space list indent, and 120-char line length. `README.md` is excluded via `.markdownlintignore` (it's pipeline output). If you add new generated output files or directories, add them to `.markdownlintignore`.

### GitHub Actions workflow permissions

`update-radar.yml` only needs `contents: write` (to commit README.md). The GitHub
Models API is authenticated via `GITHUB_TOKEN` without any additional permission
declaration — `models: read` is **not** a valid Actions permission key and will
cause workflow YAML validation to fail.

## Adding a new topic

Edit only `topics/topics.yaml`. Do not hardcode topic IDs anywhere in Python source.

## What to avoid

- Do not commit API keys or secrets — `GITHUB_TOKEN` is the only credential needed
- Do not manually edit `README.md` — it is pipeline output; run the workflow instead
- Do not add new output files/directories without updating `.markdownlintignore`

## Agent Skills

Skills live in `.github/skills/`. Each skill is a directory with a `SKILL.md` file
containing YAML front matter and Markdown instructions. The agent picks up the
relevant skill automatically based on the task being performed.
