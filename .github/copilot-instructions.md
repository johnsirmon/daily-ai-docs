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
search_trending()   →  fetch GitHub Search API for new/rising repos matching topic keywords
fetch_releases()    →  fetch recent releases from pinned repos in topics/topics.yaml
dedupe()            →  remove overlap by canonical URL / repo name
generate_blurbs()   →  call GitHub Models API (GPT-4o-mini via GITHUB_TOKEN) for each item
render_readme()     →  group by topic, write README.md
commit_readme()     →  git commit + push via actions/checkout or gh CLI

# Podcast path (PUBLISH_PODCAST=1 or --podcast flag):
readme_to_narration()  →  strip markdown tables/links; extract blurbs into spoken script
generate_audio()       →  OpenAI TTS (tts-1) via GitHub Models endpoint → radar.mp3
prepend_episode()      →  update podcast.xml (RSS 2.0 + iTunes namespace)
gh release create      →  upload radar.mp3 to dated GitHub Release
commit podcast.xml     →  subscribers auto-get new episodes
```

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
  top_n_per_topic: 5      # max repos shown per topic in README

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
{"repo": "org/name", "url": "...", "stars": 123, "description": "...", "pushed_at": "...", "type": "trending"}
```

**`release`** (from `releases.py`):
```python
{"repo": "org/name", "url": "...", "version": "v1.2", "name": "...", "published_at": "2026-01-01", "notes": "...", "type": "release"}
```

`render.py` splits on `item["type"]` to build the two separate tables. `blurbs.py` uses both types in the prompt.

`dedupe.py` deduplicates by `item["repo"]`, keeping highest-starred. Items with no `repo` key (shouldn't happen normally) are all kept.

---

## render.py split

`render_readme(topics_data, lookback_days) -> str` builds the content string (used in tests).
`write_readme(topics_data, lookback_days, path="README.md") -> Path` calls `render_readme` and writes to disk.

TOC anchors use `topic["id"]` (the YAML slug), not `topic["display"]`. Keep `id` values stable.

---

## Podcast modules

`pipeline/narrate.py` — `readme_to_narration(readme_content: str) -> str`: strips markdown tables, links, and TOC; retains topic headings + "Why it matters" / "What to learn" blurbs for speech.

`pipeline/tts.py` — `generate_audio(text: str) -> bytes | None`: calls `client.audio.speech.create(model="tts-1", voice="alloy")` via GitHub Models endpoint with `GITHUB_TOKEN`. Returns `None` and logs a warning if unavailable.

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
