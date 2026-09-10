# Contributing to daily-ai-docs

This repository publishes the **Daily AI Developer Brief**, a public, source-backed daily podcast and written digest
for AI agent developers. A separate weekly YouTube digest supplies at most one learning pick per daily edition.
The subscriber RSS feed is served through GitHub Pages; immutable audio and episode manifests live in GitHub Releases.

See [operations and setup](docs/OPERATIONS.md) for deployment, credentials, publication checks, and recovery.

## What to contribute

- **Sources and ranking:** edit `daily` and `daily.sources` in [`topics/topics.yaml`](topics/topics.yaml).
  Add public primary release repositories or official feeds, or improve the bounded YouTube discovery configuration.
  The top-level `settings` and `topics` sections belong to the legacy weekly radar, not the daily source configuration.
- **Pipeline behavior:** improve the manifest-driven daily pipeline and add tests in [`tests/`](tests/).
- **Documentation:** keep operational guidance and examples aligned with the implementation and workflows.
- **Bugs and feature requests:** open an [issue](https://github.com/johnsirmon/daily-ai-docs/issues) with expected behavior,
  actual behavior, and safe reproduction steps. For security concerns, follow [SECURITY.md](SECURITY.md) instead.

## Local development

Install Git, Python 3.11 (the version used in CI), and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Run these commands from the repository root; use your fork's clone URL if you do not have write access upstream.

```bash
git clone https://github.com/johnsirmon/daily-ai-docs.git
cd daily-ai-docs
git switch -c docs/my-change

# Full test suite with the locked dependencies and CI's Python version
uv run --python 3.11 --with-requirements requirements.lock python -m pytest -q

# Network-free pipeline preparation; no model, TTS, or publication calls
uv run --python 3.11 --with-requirements requirements.lock \
  python -m pipeline.daily prepare --dry-run --no-audio

# Offline production-artifact and README contract checks used by CI
uv run --python 3.11 --with-requirements requirements.lock python -m pipeline.publish_check
uv run --python 3.11 --with-requirements requirements.lock python -m pipeline.drift_check
```

Dependency installation may access the network. Once dependencies are installed, the tests and dry-run need no API
credentials. Preparation writes `.cache/episode-manifest.json` and `.cache/publication.json`; it does not rewrite
`README.md`, `podcast.xml`, or publication state. Do not use the legacy `pipeline.main --dry-run` as the daily smoke test.

Install `ffmpeg` and `ffprobe` for live audio preparation. Live source collection, synthesis, TTS, and delivery checks
can make external requests; they are not part of the network-free dry-run. Do not run `finalize`, `confirm`, or publisher
workflows as a routine contribution check. Ad-hoc publication is currently paused.

Use [`requirements.lock`](requirements.lock) for reproducible environments, not just the unpinned requirements file.
If changing dependencies, update [`requirements.txt`](requirements.txt), regenerate the lock, and rerun the checks:

```bash
uv pip compile requirements.txt --output-file requirements.lock
```

## Where changes belong

- `pipeline/sources/`: public GitHub releases, official feeds, and the stored weekly YouTube digest.
- `pipeline/schema.py`, `pipeline/rank.py`, `pipeline/synthesis.py`: validated evidence, selection, and optional synthesis.
- `pipeline/narrate.py`, `pipeline/render.py`: narration and README derived from the episode manifest.
- `pipeline/tts.py`, `pipeline/audio.py`, `pipeline/podcast.py`: speech generation, audio validation, and RSS.
- `pipeline/daily.py`, `pipeline/publish.py`, `pipeline/health.py`: preparation, candidate publication, delivery, confirmation.
- `pipeline/youtube.py`: bounded weekly transcript-backed discovery; full transcripts are not committed.
- `.github/workflows/update-radar.yml`: the daily publisher despite its historical filename.
- `.github/workflows/youtube-trends.yml` and `.github/workflows/pages.yml`: weekly discovery and Pages deployment.

Legacy weekly radar modules remain for compatibility. New product behavior belongs in the daily pipeline.

## Pull request checks and boundaries

- Keep each PR focused and explain the change and verification performed.
- Add or update tests for pipeline logic changes and run the complete suite before committing.
- Run the offline artifact and README checks above. CI also validates source configuration, RSS, and cover artwork.
- For Markdown changes, use the repository's `.markdownlint.json` and `.markdownlintignore` configuration.
- For generated README changes, update `pipeline/render.py` and its tests rather than only editing generated output.
- Do not commit `.cache/`, credentials, private source material, or full YouTube transcripts.
- Do not hand-edit publication state or episode history as part of unrelated changes. Keep existing GUIDs and enclosure
  URLs stable, and never overwrite published release media. Follow the operations guide for recovery work.
- Preserve the evidence contract: public primary sources support product-change claims, fetched text is untrusted, and
  publication state advances only after subscriber-facing verification. A green PR check is not proof of live delivery.

## Credentials for live workflows

The built-in Actions `GITHUB_TOKEN` is used for GitHub collection and publication, **not inference**. Local public GitHub
collection can run without authentication, subject to lower API rate limits. Supply your own `GITHUB_TOKEN` for
authenticated collection; Actions does not automatically provide one to your shell.

- Weekly discovery uses `YOUTUBE_API_KEY`, restricted to YouTube Data API v3.
- The default Edge TTS path needs no key but is best-effort. `TTS_PROVIDER=openai` requires `OPENAI_API_KEY`.
- Synthesis is off by default. Optional or required synthesis uses a dedicated `AI_API_KEY` or `OPENAI_API_KEY`.
- `EXA_API_KEY` is only for public ad-hoc research, not the scheduled daily pipeline.

Store workflow credentials in GitHub Actions secrets, never in tracked files, issues, logs, or command examples with real
values. See [GitHub setup](docs/OPERATIONS.md#github-setup) and [SECURITY.md](SECURITY.md) for permissions and key rotation.
