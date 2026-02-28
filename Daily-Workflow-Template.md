# Daily AI Workflow Template

> **Two-section daily briefing:** Part 1 covers general AI updates relevant to any practitioner.
> Part 2 is filtered to your personal domains (configured in `config.json` → `user_profile`).

---

<!-- ============================================================
     PART 1 — GENERAL AI UPDATES
     Broadly applicable to any AI/software practitioner.
     ============================================================ -->

# Part 1 — General AI Updates — YYYY-MM-DD

## 1) Critical Changes (must-read, 3-7 items)

For each item include:

- **What changed** (1 sentence)
- **Why it matters** (1 sentence)
- **Action:** Monitor / Experiment / Adopt / Ignore
- **Confidence:** High / Med / Low
- **Source:** [link]()

*Example:*

- **OpenAI released GPT-4o-mini-audio preview**
  New low-cost audio I/O model with 128 k context.
  **Why it matters:** Drop-in upgrade for voice pipelines.
  **Action:** Experiment | **Confidence:** High
  **Source:** [OpenAI blog](https://openai.com/blog)

## 2) Security & CVE Watch

- New/updated CVEs in common AI/ML dependencies
- Exploit maturity signals (PoC, active exploitation, CISA KEV)
- Practical impact vs scanner noise
- Source links

## 3) Tooling & Automation Watch

- New capabilities in LLM frameworks, SDKs, agent runtimes
- Breaking changes, deprecations, migration risks
- Source links

## 4) Release Engineering & Supply Chain Watch

- SBOM, provenance, artifact integrity best practices
- CI/CD policy-gate improvements
- Source links

## 5) AI Workflow Upgrades (general)

- **Quick win** (<30 min): _e.g., enable structured outputs in your API calls_
- **Medium** (half-day): _e.g., wire an OpenTelemetry span around each LLM call_
- **Strategic** (multi-week): _e.g., adopt a model-routing layer for cost/quality trade-offs_

## 6) Noise Filter — what NOT to chase today

- 3-5 items that are hype, redundant, low-signal, or not yet actionable

## Recommended Focus for Today (General)

1. Read first — _title_ (add URL)
2. Read second — _title_ (add URL)
3. Read third — _title_ (add URL)

**Top experiment:** _description_

---

<!-- ============================================================
     PART 2 — PERSONALIZED DOMAIN UPDATES
     Filtered to the domains defined in config.json → user_profile.
     Scoring: include only items with relevance >= 7 unless critical.
     ============================================================ -->

# Part 2 — Personalized Domain Updates — YYYY-MM-DD

> **Domains in scope:**
>
> 1. Azure Monitor Agent (AMA) — Windows/Linux operations & release engineering
> 2. CVE/security response — OpenSSL, Fluent Bit, Go/runtime libs
> 3. Supply chain security — SBOM, SLSA, provenance, artifact scanning, policy-as-gate
> 4. Incident operations — IcM-style workflows, triage automation, on-call productivity
> 5. Browser & auth automation — Edge CDP, Playwright `connectOverCDP`, enterprise auth
> 6. AI agent tooling & workflows — MCP ecosystem, agent orchestration, prompt/runtime reliability
>
> **Research sources:** Microsoft Learn · Azure updates · OpenSSL · Fluent Bit · Chromium/Edge ·
> Playwright · GitHub trending & advisories · r/azure · r/devops · r/cybersecurity · r/netsec ·
> Hacker News · CVE/NVD + vendor advisories
>
> **Time horizon:** Last 24 h first; last 7 days if high-impact.

## 1) Critical Changes (must-read, 3-7 items)

For each item include:

- **What changed** (1 sentence)
- **Why it matters to my workflows** (1 sentence)
- **Action:** Monitor / Experiment / Adopt / Ignore
- **Confidence:** High / Med / Low
- **Relevance:** _n_/10
- **Source:** [link]()

*Example:*

- **AMA 1.31 released — Linux DCR schema change**
  The `syslog` stream type now requires explicit `facility` field in DCR JSON.
  **Why it matters:** Existing Linux AMA deployments without the field will silently drop events after auto-upgrade.
  **Action:** Adopt | **Confidence:** High | **Relevance:** 10/10
  **Source:** [Azure Monitor Agent release notes](https://learn.microsoft.com/azure/azure-monitor/agents/azure-monitor-agent-release-notes)

## 2) Security & CVE Watch

- New/updated CVEs likely to affect AMA-like agent stacks or common dependencies
- Exploit maturity signals (PoC, active exploitation, CISA KEV, etc.)
- Practical impact vs scanner noise
- Source links

## 3) Tooling & Automation Watch

- New capabilities/changes in Edge CDP, Playwright, auth automation, MCP/agent tooling
- Breaking changes, deprecations, migration risks
- Source links

## 4) Release Engineering & Supply Chain Watch

- New best practices on SBOM, SLSA/provenance, artifact integrity, policy gates
- Concrete controls portable into CI/CD checks
- Source links

## 5) AI Workflow Upgrades (for my daily process)

- **Quick win** (<30 min): _e.g., add `--sbom` flag to existing container build step_
- **Medium** (half-day): _e.g., wire Playwright `connectOverCDP` into existing auth-test suite_
- **Strategic** (multi-week): _e.g., implement SLSA level 2 provenance for all AMA release artifacts_

## 6) Noise Filter — what NOT to chase today

- 3-5 items that are hype, redundant, low-signal, or not yet actionable in these domains

## Recommended Focus for Today (Personalized)

1. Read first — _title_ (add URL)
2. Read second — _title_ (add URL)
3. Read third — _title_ (add URL)

**Top experiment:** _description_

---

## How to Use This Template

### Prerequisites

Before generating a briefing, add your OpenAI API key to `config.json`:

```json
{
  "openai_api_key": "YOUR_OPENAI_API_KEY_HERE"
}
```

See [AUTO-UPDATER-README.md](AUTO-UPDATER-README.md) for full setup instructions.

### Generating your daily briefing

```bash
# Generate both sections (requires API keys in config.json)
python doc_updater.py --daily-workflow

# Generate general section only
python doc_updater.py --daily-workflow --section general

# Generate personalized section only
python doc_updater.py --daily-workflow --section personalized
```

### Customizing your profile

Edit `config.json` → `user_profile` to update your domains, research sources, and relevance threshold:

```json
{
  "user_profile": {
    "domains": ["Your domain 1", "Your domain 2"],
    "research_sources": ["Source 1", "Source 2"],
    "relevance_threshold": 7
  }
}
```

### Scoring rules

- Relevance-score each finding 1–10 based on fit to your domains
- Only include items with relevance ≥ 7 (set via `relevance_threshold`) unless it is a critical security item
- Prefer concrete changes (release note, patch, advisory, API change) over opinion posts

### Style rules

- Be concise, specific, and action-oriented
- No fluff, no generic AI news unless directly actionable to your stack
- Include links for every claim
- If uncertainty exists, state it explicitly
