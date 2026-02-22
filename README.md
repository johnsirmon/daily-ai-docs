# Daily AI Docs 📚

> **Always-current AI documentation sourced daily from official model docs**

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Daily Updates](https://img.shields.io/badge/updated-daily-brightgreen.svg)](CHANGELOG.md)
[![Source Verified](https://img.shields.io/badge/source-official%20docs-blue.svg)](AUTO-UPDATER-README.md)
[![Multi Platform](https://img.shields.io/badge/platforms-OpenAI%20%7C%20Anthropic%20%7C%20More-orange.svg)](#-what-sources-we-monitor)

## 🎯 What's Included

### 📚 Core Documentation
- **[AI Platform Comparison](AI-Platform-Comparison-Guide.md)** - When to use which platform
- **[Claude Models Guide](Anthropic-Claude-Models-Guide.md)** - Claude model lineup and strategies
- **[ChatGPT Prompt Engineering Guide](Quick-Reference-Print.md)** - ChatGPT reference with rating system
- **[ChatGPT Complete Reference](ChatGPT-Complete-Reference-Guide.md)** - Full OpenAI model guide
- **[Terminal & CLI Guide](AI-Terminal-CLI-Guide.md)** - Command-line AI tools
- **[Daily Workflow Template](Daily-Workflow-Template.md)** - Dual-section daily briefing (general + personalized)

#### 🔧 Automation System
- **[Auto-Updater](AUTO-UPDATER-README.md)** - Daily documentation maintenance
- **[Batch Scripts](setup.bat)** - One-click setup and execution
- **[Python Updater](doc_updater.py)** - AI-powered change detection and daily workflow generation

### 🤖 Daily AI Intelligence Pipeline

Automated pipeline that ingests, ranks, deduplicates, and publishes operator-relevant AI updates every day.

| Output | Description |
|--------|-------------|
| `reports/daily/YYYY-MM-DD.md` | Top-ranked items for the day |
| `reports/weekly/YYYY-WW.md` | Weekly summary grouped by topic |
| `reports/watchlist.md` | High-signal items (score ≥ 0.70) |
| `data/trends.json` | Rolling topic-frequency time series |

**Tracked topics:** OpenClaw · VS Code Insiders · GitHub Copilot Chat/Agent ·
MCP Ecosystem · Agentic Workflows · Self-Improving Agent Patterns ·
Agent Evals & Reliability · Azure AI Foundry / Azure OpenAI

### 📊 What Sources We Monitor
- **OpenAI Documentation**: API docs, model guides, best practices
- **Anthropic Documentation**: Claude guides, API updates, capabilities
- **GitHub Repositories**: openai-cookbook, anthropic-sdk-python, modelcontextprotocol/servers, microsoft/vscode
- **Official Blogs**: VS Code Blog, Azure AI Blog, GitHub Blog, Semantic Kernel Blog
- **Community Resources**: Verified techniques and patterns

## 🚀 Quick Start

### Modern AI Architecture Approach
AI systems have evolved beyond prompt engineering alone. Use this library as a starting point—then layer in the architecture that matches your workflow:

| **Workflow Type** | **Architecture Pattern** | **Starting Point** |
|------------------|--------------------------|-------------------|
| One-off tasks | Single-turn prompt | [Prompt Guide](Quick-Reference-Print.md) |
| Multi-step pipelines | Prompt chaining | [Advanced Techniques](Quick-Reference-Print.md#-advanced-techniques) |
| Knowledge-intensive | RAG + context engineering | [Platform Comparison](AI-Platform-Comparison-Guide.md) |
| Autonomous execution | Agentic loop (tools + memory + verification) | [Terminal & CLI Guide](AI-Terminal-CLI-Guide.md) |
| Production systems | Multi-agent orchestration | [Platform Comparison](AI-Platform-Comparison-Guide.md#️-modern-ai-architecture-patterns) |

### For Prompt Engineering
1. **Platform Comparison**: Start with [AI Platform Comparison](AI-Platform-Comparison-Guide.md) to pick the right tool
2. **ChatGPT Reference**: Use [ChatGPT Prompt Guide](Quick-Reference-Print.md) for OpenAI models
3. **Claude Reference**: Use [Claude Models Guide](Anthropic-Claude-Models-Guide.md) for Anthropic models
4. **Rate Your Prompts**: Follow the [rating system](#-prompt-rating-system) 
5. **Define Your Architecture**: Identify workflow type before model selection

### For Automated Maintenance
1. **Setup**: Run `setup.bat` for one-click installation
2. **Configure**: Add API keys to `config.json`
3. **Run Daily**: Use `run_updater.bat` for automatic updates
4. **Stay Current**: System monitors AI platform changes automatically

### For Daily Workflow Briefings
1. **Template**: Review [Daily-Workflow-Template.md](Daily-Workflow-Template.md) for the dual-section format
2. **Customize**: Edit `user_profile` in `config.json` with your specific domains and sources
3. **Generate**: Run `python doc_updater.py --daily-workflow` for a full general + personalized briefing
4. **Scope**: Use `--section general` or `--section personalized` to generate individual sections

## 🌟 Key Features

### � Prompt Rating System
- **10-point rating scale** for prompt quality assessment
- **Model-specific optimization** recommendations  
- **Before/after examples** with improvement suggestions
- **Self-assessment checklist** for rapid iteration

### 🤖 Multi-Platform Coverage
- **ChatGPT**: All models from GPT-4o to o3
- **Claude**: Anthropic's full model lineup
- **Comparison matrices**: When to use which platform
- **Terminal tools**: CLI integration guides

### 🔄 Auto-Maintenance
- **Daily change detection** using AI analysis
- **Version control** with timestamped backups
- **Obsolescence tracking** for evolving guidance  
- **GitHub integration** ready for repository publishing

## 🎯 USE CASE EXAMPLES

> **Architecture-First:** Each example below starts with the workflow pattern, then maps to tools and models. This reflects the modern direction: orchestration and context engineering first, model selection second.

### **Data Analysis Project**
1. **Define workflow**: Multi-step pipeline with persistent context
2. **Ingest & analyze** → Claude Web (200k context for long documents)
3. **Generate insights** → Claude Sonnet
4. **Create visualizations** → ChatGPT GPT-4o (if images needed)
5. **Automate reports** → OpenAI CLI scripts or agentic pipeline

### **Software Development**
1. **Define workflow**: Agentic loop with codebase awareness
2. **Planning** → ChatGPT o3 (deep reasoning)
3. **Coding + refactoring** → Claude Code (multi-file, test-aware) or GPT-4.1 (web)
4. **Review + CI/CD integration** → GitHub Copilot CLI
5. **Documentation** → Claude Sonnet

### **Content Creation**
1. **Define workflow**: Sequential stages with handoffs
2. **Research** → Claude Opus (long context, nuanced analysis)
3. **Outline** → ChatGPT GPT-4.5 (brainstorming)
4. **Writing** → Claude Sonnet
5. **Editing** → Both platforms for comparison

## 🤖 AI Intelligence Pipeline — Runbook

### Architecture

The pipeline follows clear module boundaries inside `pipeline/`:

| Module | Responsibility |
|--------|---------------|
| `ingest.py` | Fetch from GitHub releases and RSS/Atom feeds |
| `normalize.py` | Map raw items to a common JSON schema |
| `dedupe.py` | Remove duplicates by URL and title |
| `rank.py` | Score items (recency × source quality × topic relevance) |
| `publish.py` | Write daily/weekly/watchlist/trends outputs |
| `main.py` | CLI orchestrator |

### Running Manually

```bash
# Install dependencies
pip install -r requirements.txt

# Dry-run (no network calls, uses sample data)
python -m pipeline.main --dry-run

# Live run (requires GITHUB_TOKEN env var for higher rate limits)
export GITHUB_TOKEN=ghp_...
python -m pipeline.main

# Override the date / week
python -m pipeline.main --date 2026-02-22 --week 2026-08

# Run tests
python -m pytest tests/ -v
```

### Adding Topics

Edit `topics/topics.yaml` — add an entry to the `topics` list:

```yaml
- id: my-new-topic
  display: "My New Topic"
  keywords: ["keyword one", "keyword two"]
  why_matters_template: "Short note on why this topic matters."
  action_template: "What the operator should do when this fires."
```

### Adding Sources

Edit `topics/topics.yaml` — add an entry to the appropriate source list:

```yaml
sources:
  github_releases:
    - owner: some-org
      repo: some-repo
      topics: [my-new-topic]

  rss_feeds:
    - url: "https://example.com/feed.xml"
      name: "Example Blog"
      quality: 0.80
      topics: [my-new-topic]
```

### Scoring Tuning

Adjust weights, half-life, and thresholds under `ranking:` in `topics/topics.yaml`:

```yaml
ranking:
  weights:
    recency: 0.40        # 0-1: higher = prefer newer items
    source_quality: 0.40 # 0-1: higher = prefer high-quality sources
    topic_relevance: 0.20
  recency_half_life_days: 3   # items halve in score every N days
  watchlist_threshold: 0.70   # minimum score to appear in watchlist
```

### GitHub Actions Schedules

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `daily-pipeline.yml` | 06:00 UTC daily + `workflow_dispatch` | Daily report |
| `weekly-pipeline.yml` | 07:00 UTC Mondays + `workflow_dispatch` | Weekly summary |
| `pipeline-ci.yml` | Push/PR to `pipeline/`, `topics/`, `tests/` | Unit tests + dry-run |

### CI / Quality Gates

- All unit tests cover ranking, deduplication, schema, and output formats
- `--dry-run` validates the full pipeline without network access
- `data/trends.json` schema is validated in CI after every run

## 👥 Contributing to the Pipeline

1. Fork and create a feature branch.
2. Add/update tests in `tests/` for any logic change.
3. Run `python -m pytest tests/ -v` — all tests must pass.
4. Run `python -m pipeline.main --dry-run` — pipeline must produce valid output.
5. Open a PR; the `pipeline-ci.yml` workflow runs automatically.

Topic requests and source suggestions are welcome — just edit `topics/topics.yaml`.

## 🔄 MAINTENANCE SCHEDULE

- **Weekly:** Check for new model releases
- **Monthly:** Run update prompts on all guides
- **Quarterly:** Review and update comparison matrices

## 📖 GETTING STARTED

1. **Read:** [AI Platform Comparison Guide](AI-Platform-Comparison-Guide.md) first
2. **Reference:** [Claude Models Guide](Anthropic-Claude-Models-Guide.md) for Anthropic • [ChatGPT Models & Prompting Guide](ChatGPT-Models-Prompting-Guide.md) for OpenAI
3. **Bookmark:** This index for quick navigation
4. **Setup:** [AI Terminal & CLI Guide](AI-Terminal-CLI-Guide.md) for development workflow

---

**💡 Pro Tip:** Keep multiple tools in your toolkit. Each has unique strengths that complement the others.

**🔗 Quick Links:**
- [ChatGPT Web](https://chat.openai.com) | [Claude Web](https://claude.ai)
- [OpenAI API Docs](https://platform.openai.com/docs) | [Anthropic API Docs](https://docs.anthropic.com)
- [GitHub Copilot](https://github.com/features/copilot)

*AI Prompt Library Index v2025.07.07*
