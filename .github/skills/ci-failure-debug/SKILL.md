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
   | `Missing required elements` | Guide missing obsolescence section | New `*-Guide.md` file |
   | `Broken internal links` | Link target renamed or deleted | `README.md` or guide files |

4. **Apply the fix**
   - Make the minimal change required (prefer editing one file over many).
   - If a test broke, update the test only if the behaviour change is intentional.
   - If a guide is missing an obsolescence section, add the standard table (see
     `GitHub-Copilot-Methodology-Guide.md` for the canonical format).

5. **Verify locally**

   ```bash
   uv run --with-requirements requirements.lock pytest -q tests/test_affected.py
   uv run --with-requirements requirements.lock python -m pipeline.daily prepare --dry-run --no-audio
   ```

   Replace the illustrative test selector with the actual affected tests, then run
   the complete suite before committing.

6. **Commit and push when authorized** — inspect `ci.yml` triggers first; CI runs
   for main pushes and pull requests, not every feature-branch push. Never add a
   preview-trigger marker merely to rerun tests: it can spend provider quota.

## Notes

- The `quality-check.yml` workflow checks every file matching `*guide*.md` (case-insensitive)
  for a `## Guidance Obsolescence` section. New guide files must include this section.
- `reports/` and `data/` are excluded from markdownlint via `.markdownlintignore`.
- The pipeline dry-run uses sample data; no `GITHUB_TOKEN` is required for `--dry-run`.
