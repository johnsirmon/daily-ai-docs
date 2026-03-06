# Copilot Instructions for daily-ai-docs

## Purpose

This repository runs the AI Skills Radar pipeline: gather recent GitHub repo/release activity by topic, generate narrative summaries, publish `README.md`, and optionally publish podcast episodes.

## Build, test, and validation commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run full test suite
python -m pytest tests/ -v

# Run a single test
python -m pytest tests/test_dedupe.py::test_duplicate_keeps_higher_stars -v

# Local dry-run of full pipeline (no network calls)
python -m pipeline.main --dry-run

# Full run (requires GITHUB_TOKEN)
python -m pipeline.main

# Podcast from existing README only
python -m pipeline.main --podcast-only

# Narration-only flow for narrator-polish agent
python -m pipeline.main --narrate-only --dry-run

# Ad-hoc topic episode (skips full radar pipeline)
python -m pipeline.main --adhoc-topic "Model Context Protocol"
```

CI also runs these repository checks from workflows:

```bash
python -c "import yaml; yaml.safe_load(open('topics/topics.yaml'))"
python -c "open('requirements.txt')"
```

## High-level architecture

`pipeline/main.py` is the orchestrator and has three execution paths:

1. **Full radar path** (`run()`):
   - Load config from `topics/topics.yaml`.
   - For each topic: `search.search_repos()` for trending repos and `releases.fetch_releases()` for pinned repos.
   - Add `topic_display` to all collected items and run cross-topic synthesis via `research.run_research_summary()`.
   - Per topic: optional `enrich.enrich_items()` (top 4 repos), `blurbs.generate_repo_deepdive()`, and `blurbs.generate_topic_meta()`.
   - Save checkpoint to `.cache/pipeline_checkpoint.json`.
   - Render and write `README.md` via `render.write_readme()`.

2. **Podcast path** (`--podcast`, `--podcast-only`, or `--narrate-only`):
   - Convert README to narration with `narrate.readme_to_narration()`.
   - Save raw script to `.cache/narration_script.txt`.
   - If present, use `.cache/narration_polished.txt` as TTS input.
   - Generate audio via `tts.write_audio()` and prepend episode in `podcast.xml` via `podcast.prepend_episode()`.

3. **Ad-hoc path** (`--adhoc-topic`):
   - Run `adhoc.run_adhoc()` (optional Exa search + AI research + narration + TTS + `podcast.xml` prepend).
   - Output audio file is `adhoc-episode.mp3`.

## Key repository conventions

- **`topics/topics.yaml` is the control plane.** Add/modify tracked topics there; do not hardcode topic lists in Python.
- **Topic `id` stability matters.** `render.py` uses `topic["id"]` for README TOC anchors, and `research.py` uses topic IDs as keys in `topic_insights`.
- **Unified item contract.** Topic items are dicts with `type` set to `"trending"` or `"release"`; downstream modules branch on this field.
- **Fail-open behavior is intentional.** API/model failures generally log warnings and return empty/default data so pipeline output still completes.
- **Caching is part of normal flow.** Enrichment caches per-repo JSON under `.cache/enrich/`; research summary caches to `.cache/research_YYYY-MM-DD.json`.
- **Generated artifacts are pipeline-owned.** `README.md`, `podcast.xml`, `radar.mp3`, and `adhoc-episode.mp3` are outputs from pipeline/workflows, not hand-maintained docs.
- **GitHub token usage is shared.** `GITHUB_TOKEN` is used for both GitHub REST calls and GitHub Models (`https://models.inference.ai.azure.com`); `EXA_API_KEY` is optional only for ad-hoc Exa search.
- **Test style is file-local factory helpers.** Tests commonly define local builders (for example `_repo`, `_release`, `_topic`) in each test module rather than shared fixtures.
