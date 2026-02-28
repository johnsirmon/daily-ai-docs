# Repository Status — johnsirmon/daily-ai-docs

> Snapshot generated: 2026-02-28

## Overall Health: ✅ Green

| Area | Status | Detail |
|------|--------|--------|
| Tests | ✅ 48 / 48 passing | `python -m pytest tests/ -v` |
| Pipeline (dry-run) | ✅ Working | 10 topics ingested, 0 duplicates |
| Open Issues | ✅ 0 | No backlog |
| Open PRs | ⚠️ 5 | See table below |
| Active Branches | ℹ️ 13 | Most are Copilot agent branches |
| CI Workflows | ⚠️ Pending approval | GitHub Advanced Security gate on PR runs |
| Last `main` commit | ✅ 2026-02-28 | `chore: daily AI pipeline run 2026-02-28` |

---

## Pipeline Dry-Run Output

```
date: 2026-02-28
week: 2026-08
items_ingested: 10
items_after_dedupe: 10
outputs:
  daily:     reports/daily/2026-02-28.md
  weekly:    reports/weekly/2026-08.md
  trends:    data/trends.json
  watchlist: reports/watchlist.md
```

---

## Open Pull Requests

| PR | Title | Branch |
|----|-------|--------|
| #16 | [WIP] Check status of johnsirmon repository | `copilot/check-repo-status` |
| #15 | Review and address issues in PR #12 | `copilot/review-pull-request-12-issues` |
| #14 | Update vscode insiders AI tools | `copilot/update-vscode-insiders-ai-tools` |
| #13 | Self-tune documentation process | `copilot/self-tune-documentation-process` |
| #12 | Fix action step issue | `copilot/fix-action-step-issue` |

---

## Active Branches (13)

- `main` — production branch, last updated 2026-02-28
- `copilot/check-repo-status` — this PR
- `copilot/review-pull-request-12-issues`
- `copilot/build-daily-ai-pipeline`
- `copilot/build-daily-trend-pipeline`
- `copilot/enhance-narrative-update-feature`
- `copilot/fix-action-step-issue`
- `copilot/remove-rewrite-stale-guidance`
- `copilot/self-tune-documentation-process`
- `copilot/update-daily-workflow-info`
- `copilot/update-primary-guide-analysis`
- `copilot/update-readme-content`
- `copilot/update-readme-documentation`
- `copilot/update-vscode-insiders-ai-tools`

---

## CI Workflow Notes

The most recent workflow runs show `action_required` — this is the standard
GitHub Advanced Security gate that fires when a Copilot agent opens a PR. It
is **not** a test failure; it requires a repository maintainer to approve the
workflow run before jobs execute.

No actual test failures or lint errors have been detected.

---

## Guidance Obsolescence

| Section | Review Trigger | Next Review |
|---------|----------------|-------------|
| Open PRs table | Whenever a PR is merged or opened | On next agent run |
| Branch list | Whenever a branch is deleted or created | On next agent run |
| Pipeline dry-run | Whenever `pipeline/` code changes | After each pipeline release |
