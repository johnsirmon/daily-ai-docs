---
name: ci-failure-debug
description: >
  Debug a failing GitHub Actions CI run for this repository. Use when asked to
  investigate why a workflow failed, interpret test output, or suggest a fix.
triggers:
  - "ci fail"
  - "pipeline fail"
  - "workflow fail"
  - "tests fail"
  - "debug ci"
  - "fix the build"
---

# Skill: CI Failure Debug

## What this skill does

Guides the agent through diagnosing and fixing a failing CI run in this repository.

## Steps

1. **Identify the failing workflow run**
   - Prefer `gh run list` and `gh run view` to identify the relevant failing run.
   - Inspect the actual workflow under `.github/workflows/`; do not assume a
     remembered workflow filename or inspect an unrelated historical failure.

2. **Fetch the failure logs**
   - Run `gh run view <run-id> --log-failed`.
   - Scan for the first `Error`, `FAILED`, or `exit code` line to locate the root cause.

3. **Map the error to source**

   | Error pattern | Likely cause | Where to look |
   |---------------|-------------|---------------|
   | `ModuleNotFoundError` | Missing dependency | `requirements.lock` and the failing workflow |
   | `AssertionError` in `tests/` | Logic regression | `pipeline/` module matching test file |
   | `yaml.YAMLError` | Bad syntax in `topics/topics.yaml` | `topics/topics.yaml` |
   | `json.JSONDecodeError` | Malformed JSON artifact | The exact path in the traceback |
   | README contract failure | Generated overview drift | `pipeline/render.py` and `pipeline/drift_check.py` |
   | Audio/enclosure | Media/delivery | `pipeline/audio.py`, `pipeline/publish.py`, manifest |

4. **Choose the focused test set by failure class**

   | Failure class | Focused checks |
   |---------------|----------------|
   | Source/health/ranking | `test_sources`, `test_source_text`, `test_rank`, `test_selective_publication` |
   | Provider availability or schema | `test_providers`, `test_synthesis`, `test_grounded_editorial`, `test_preview` |
   | Evidence/claim rejection | `test_editorial`, `test_grounded_editorial`, `test_evidence_archive` |
   | Audio or reviewed import | `test_audio`, `test_audio_quality`, `test_reviewed_audio`, `test_reviewed_delivery` |
   | Ad-hoc/request authorization | `test_adhoc`, `test_workflows`, `test_audio_quality` |
   | Candidate/recovery/delivery | `test_daily`, `test_publish`, `test_recovery`, `test_podcast`, `test_adhoc` |
   | Workflow/skill/configuration | `test_workflows`, `test_skills`, `pipeline.drift_check`, YAML/shell syntax |

   Provider outage, grounding rejection, media mismatch, workflow syntax, generated
   drift, and live delivery failure are distinct classes. Do not cure one by changing
   the policy for another. Use `publication-recovery` for any incident that reached
   release, candidate, deployment, or subscriber-facing state.
   For local ASR, mastering, or listening evidence, follow
   [audio-production-review](../audio-production-review/SKILL.md).

5. **Apply the fix**
   - Make the minimal change required (prefer editing one file over many).
   - If a test broke, update the test only if the behaviour change is intentional.
   - Fix the generating source when a generated README or manifest is wrong; do
     not patch a generated file in a way that the next run will undo.

6. **Respect generated-artifact ownership**

   | Artifact | Owner / safe reproduction | Prohibited shortcut |
   |----------|---------------------------|---------------------|
   | `README.md` | `pipeline/render.py` from accepted manifest/configuration | Hand-edit generated story content |
   | `podcast.xml` | podcast/finalization pipeline | Do not use legacy `repair_feed.py` for general recovery |
   | `data/episodes/*.json` | validated candidate/finalization path | Rewrite confirmed history |
   | `data/state.json` | confirmation after subscriber delivery | Advance novelty state during preparation |
   | `data/receipts/*.json` | successful exact delivery confirmation | Fabricate or copy a receipt |
   | `data/runs/latest.json` | editorial run/skip/failure recording | Treat a fresh skip as a new episode |
   | `.cache/*` | isolated preparation/preview output | Treat cache files as publication proof |

   Reproduce generated output in a temporary checkout first. `publish_check` validates
   feed/artwork contracts and `drift_check` validates bounded README/configuration
   properties; neither alone proves complete manifest/state/receipt consistency.

7. **Verify locally in an isolated CI-equivalent environment**

   Use Python 3.11, the locked requirements, and a temporary working directory for
   commands that write `.cache/` artifacts:

   ```bash
   uv run --python 3.11 --with-requirements requirements.lock \
     python -m pytest -q tests/test_daily.py
   tmp=$(mktemp -d)
   trap 'rm -rf "$tmp"' EXIT
   mkdir "$tmp/repo"
   tar --exclude=.git --exclude=.venv --exclude=.cache \
     --exclude=.pytest_cache --exclude=.ruff_cache -cf - . | tar -xf - -C "$tmp/repo"
   (
     cd "$tmp/repo"
     uv run --python 3.11 --with-requirements requirements.lock \
       python -m pipeline.daily prepare --dry-run --no-audio
   )
   ```

   Replace the illustrative selector with the affected tests. Never run publication
   commands during diagnosis. After focused checks, run the complete canonical gate:

   ```bash
   uv run --python 3.11 --with-requirements requirements.lock python -m pytest -q
   uv run --python 3.11 --with-requirements requirements.lock python -m pipeline.publish_check
   uv run --python 3.11 --with-requirements requirements.lock python -m pipeline.drift_check
   uv run --python 3.11 --with-requirements requirements.lock python -m compileall -q pipeline tests
   git diff --check
   ```

8. **Commit and push when authorized** — inspect `ci.yml` triggers first; CI runs
   for main pushes and pull requests, not every feature-branch push. Never add a
   preview-trigger marker merely to rerun tests: it can spend provider quota.

## Notes

- The current quality workflow validates topics, the README contract, committed
  RSS, and artwork. Read its steps before diagnosing a failure.
- The daily dry-run uses sample data; no `GITHUB_TOKEN` is required.
- A provider 503, a malformed model response, and an unsupported factual claim
  are different failure classes. Do not weaken validation or retry indefinitely.
