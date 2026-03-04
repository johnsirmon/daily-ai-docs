# Contributing to daily-ai-docs

Thank you for your interest in contributing! This project is an automated AI Skills Radar
that generates a weekly digest of trending AI repositories and releases.

## 🎯 How to Contribute

### 1. **Add or Improve Topics**

The easiest way to contribute is by editing [`topics/topics.yaml`](topics/topics.yaml):

- Add a new topic with relevant keywords
- Add `pinned_repos` to always track releases from a specific repository
- Adjust `min_stars` or `top_n_per_topic` settings

### 2. **Improve the Pipeline**

The pipeline lives in [`pipeline/`](pipeline/):

- `search.py` — GitHub Search API integration
- `releases.py` — fetches recent releases from pinned repos
- `blurbs.py` — AI-generated topic summaries and repo deep-dives
- `render.py` — renders the README from collected data
- `narrate.py` / `tts.py` / `podcast.py` — podcast generation

### 3. **Report Bugs or Suggest Features**

Open an [issue](https://github.com/johnsirmon/daily-ai-docs/issues) describing:

- What you expected to happen
- What actually happened
- Steps to reproduce (if a bug)

## 🚀 Getting Started

```bash
git clone https://github.com/johnsirmon/daily-ai-docs.git
cd daily-ai-docs
pip install -r requirements.txt

# Dry-run (no network calls, writes placeholder README.md)
python -m pipeline.main --dry-run

# Run tests
python -m pytest tests/ -v
```

## 📋 Pull Request Guidelines

- Keep changes focused — one logical change per PR
- Add or update tests in `tests/` for any pipeline logic changes
- Run `python -m pytest tests/ -v` and confirm all tests pass
- Follow [PEP 8](https://peps.python.org/pep-0008/) for Python code
- Document public functions with docstrings

## 🔑 Credentials

No extra secrets are needed for development or dry-runs. For live runs, only the
built-in `GITHUB_TOKEN` is required — it is available automatically in GitHub Actions.

---

*Contributing Guide — [johnsirmon/daily-ai-docs](https://github.com/johnsirmon/daily-ai-docs)*
