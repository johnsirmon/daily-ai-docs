# Copilot Instructions for daily-ai-docs

## Purpose

This repo is a **personal AI skills tracker** — a GitHub Actions pipeline that scans
GitHub for new/trending AI repositories and recent releases, then publishes a single
`README.md` summarising what changed in the last 2 weeks and what skills are worth
learning. Anyone can fork and follow it.

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
topics:
  - id: mcp               # slug used in code; must be unique, lowercase-kebab
    display: "MCP Ecosystem"
    keywords:             # used in GitHub search queries
      - "model context protocol"
      - "mcp server"
    pinned_repos:         # always fetch releases from these
      - modelcontextprotocol/specification
      - modelcontextprotocol/servers

ranking:
  min_stars: 50           # ignore repos below this threshold
  lookback_days: 14       # how far back to scan
  top_n_per_topic: 5      # max repos shown per topic in README
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
