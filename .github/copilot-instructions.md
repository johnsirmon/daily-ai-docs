# Copilot Instructions for daily-ai-docs

This repository is an always-current AI documentation resource covering AI platforms,
models, and developer tooling. The pipeline ingests, deduplicates, ranks, and publishes
daily/weekly reports from official sources.

## Repository purpose

- Track and publish AI platform updates (GitHub Copilot, OpenAI, Anthropic, Azure AI,
  MCP ecosystem, agentic workflows)
- Provide human-readable guides on prompt engineering, model selection, and AI
  developer tooling
- Run a Python pipeline (`pipeline/`) that produces `reports/` and `data/` outputs

## Tech stack

- **Language:** Python 3.9+
- **Pipeline:** `pipeline/main.py` orchestrates ingest → normalize → dedupe → rank → publish
- **Config:** `topics/topics.yaml` — edit to add topics and sources
- **Tests:** `pytest` — run with `python -m pytest tests/ -v`
- **Docs:** Markdown files at repo root; quality-checked by `.github/workflows/quality-check.yml`

## Coding conventions

- Follow PEP 8; keep functions small and single-purpose
- All public pipeline functions have docstrings
- Tests live in `tests/`; new logic must have corresponding tests
- Guide documents must include a `## Guidance Obsolescence` section with a review table
- Prefer `pathlib.Path` over `os.path` for new code
- Use `yaml.safe_load` (never `yaml.load`) for YAML parsing

## Preferred patterns

- When adding a new pipeline stage, model it on existing stages (`ingest.py`,
  `normalize.py`, etc.)
- When adding a new topic, edit `topics/topics.yaml` — do not hardcode topic IDs in
  Python source
- When writing a new guide document, copy the structure of `GitHub-Copilot-Methodology-Guide.md`
  (feature hierarchy → comparison → gap analysis → adoption path → governance)
- MCP is the preferred integration pattern for external tool calls; avoid raw REST
  calls in prompts

## Agent Skills

Project skills live in `.github/skills/`. Each skill directory contains a `SKILL.md`
with YAML front matter and Markdown instructions. The agent picks up the relevant skill
automatically based on task description.

## What to avoid

- Do not commit API keys, tokens, or secrets
- Do not hardcode dates — use `--date` CLI flag or `datetime.date.today()`
- Do not modify files in `reports/` or `data/` directly; they are pipeline outputs
- Do not change `.markdownlintignore` unless adding a new generated-output directory
