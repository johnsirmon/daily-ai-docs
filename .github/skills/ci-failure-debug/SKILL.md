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
   - Use the GitHub MCP server tool `list_workflow_runs` with `status=failure` to find
     the most recent failed run.
   - Note the `run_id` and the workflow file name (e.g., `pipeline-ci.yml`).

2. **Fetch the failure logs**
   - Call `get_job_logs` with `run_id=<id>` and `failed_only=true`.
   - Scan for the first `Error`, `FAILED`, or `exit code` line to locate the root cause.

3. **Map the error to source**

   | Error pattern | Likely cause | Where to look |
   |---------------|-------------|---------------|
   | `ModuleNotFoundError` | Missing dependency | `requirements.txt` |
   | `AssertionError` in `tests/` | Logic regression | `pipeline/` module matching test file |
   | `yaml.YAMLError` | Bad syntax in `topics/topics.yaml` | `topics/topics.yaml` |
   | `json.JSONDecodeError` | Corrupt `config.json` | `config.json` |
   | `Missing required elements` | Guide missing obsolescence section | New `*-Guide.md` file |
   | `Broken internal links` | Link target renamed or deleted | `README.md` or guide files |

4. **Apply the fix**
   - Make the minimal change required (prefer editing one file over many).
   - If a test broke, update the test only if the behaviour change is intentional.
   - If a guide is missing an obsolescence section, add the standard table (see
     `GitHub-Copilot-Methodology-Guide.md` for the canonical format).

5. **Verify locally**

   ```bash
   python -m pytest tests/ -v
   python -m pipeline.main --dry-run
   ```

6. **Commit and push** — the `pipeline-ci.yml` workflow re-runs automatically on push.

## Notes

- The `quality-check.yml` workflow checks every file matching `*guide*.md` (case-insensitive)
  for a `## Guidance Obsolescence` section. New guide files must include this section.
- `reports/` and `data/` are excluded from markdownlint via `.markdownlintignore`.
- The pipeline dry-run uses sample data; no `GITHUB_TOKEN` is required for `--dry-run`.
