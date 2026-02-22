# AI Governance

This document records the governance decisions and policies for AI tooling in this
repository. Update it whenever policies, tools, or workflows change.

## 1. Approved AI tools

| Tool | Approved use | Notes |
|------|-------------|-------|
| GitHub Copilot | Code completion, Chat, Agent Mode, Coding Agent | Requires Copilot plan |
| Claude (Anthropic) | Long-context analysis, documentation drafting | Via API or claude.ai |
| OpenAI GPT-4 / o3 | Reasoning tasks, structured output | Via API |
| GitHub MCP Server | Copilot tool integration (issues, PRs, code search) | Remote mode preferred |

## 2. Data classification

- **Do not** send proprietary business data, PII, or credentials to any AI model.
- Code in this repository is open-source (MIT); it may be used in AI prompts.
- Pipeline outputs (`reports/`, `data/`) are generated and may be shared freely.

## 3. Secret management

- API keys are stored in environment variables or GitHub Actions secrets — never
  committed to source.
- The `security-check` job in `quality-check.yml` scans for leaked tokens on every push.

## 4. Human review requirements

- All AI-generated content that will be published must pass the quality gate in
  `quality-check.yml` before merging.
- The `HUMAN-REVIEW-GUIDE.md` defines the review checklist for documentation changes.
- Copilot Coding Agent PRs must be reviewed by at least one human before merging.

## 5. Pipeline integrity

- The pipeline is deterministic: same inputs produce the same outputs (`--dry-run`
  is idempotent).
- `data/trends.json` schema is validated in CI after every pipeline run.
- All ranking weights, thresholds, and half-life values are in `topics/topics.yaml`
  (no magic numbers in Python source).

## 6. Dependency management

- Dependencies are pinned in `requirements.txt`; update only when there is a known
  security fix or required feature.
- Run `pip install -r requirements.txt` in a virtual environment before contributing.

## 7. Drift management

- **Monthly:** review `reports/watchlist.md` for high-signal items; update guides as
  needed.
- **Quarterly:** re-validate all comparison matrices in guide documents; update the
  "Last validated" dates in the Guidance Obsolescence tables.
- **On new Copilot release:** update `GitHub-Copilot-Methodology-Guide.md` and the
  Guidance Obsolescence table.

## 8. Modern Copilot workflow (2025+)

- Maintain `.github/copilot-instructions.md` as the canonical always-on context for
  Copilot Chat. Keep it up to date when the tech stack or conventions change.
- Store task-specific instructions as Agent Skills in `.github/skills/` (project) or
  `~/.copilot/skills/` (personal). Skills are picked up automatically by the agent
  based on task description.
- Prefer MCP servers over raw SDK/REST calls for AI tool integrations; reuse community
  MCP servers where available (see [GitHub MCP Server](https://github.com/github/github-mcp-server)).
- Use Copilot Coding Agent for routine backlog tasks (test coverage, docs, minor
  refactors); use local agent mode for exploratory/interactive coding sessions.
- Distinguish clearly between:
  - **Agent mode** (local, synchronous, VS Code Insiders) — edits your workspace,
    iterates in real time.
  - **Coding agent** (cloud, async, GitHub Actions) — opens a PR; you steer via
    review comments.
- Review skill files (`.github/skills/`) and instruction files
  (`.github/copilot-instructions.md`) in the monthly drift scan.
- The Agent Skills spec and MCP are open standards; skills written for Copilot also
  work with Claude via `.claude/skills/`. Invest in standards, not tool-specific APIs.

## 9. Incident response

If an AI-generated change introduces a regression:

1. Revert the merge commit immediately (`git revert <sha>`).
2. Open an issue describing the regression with logs.
3. Investigate root cause before re-attempting with the coding agent.
4. Update the relevant Agent Skill or custom instructions to prevent recurrence.
