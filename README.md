# Daily AI Docs 📚

> **Always-current AI documentation sourced daily from official model docs**

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Daily Updates](https://img.shields.io/badge/updated-daily-brightgreen.svg)](CHANGELOG.md)
[![Source Verified](https://img.shields.io/badge/source-official%20docs-blue.svg)](AUTO-UPDATER-README.md)
[![Multi Platform](https://img.shields.io/badge/platforms-OpenAI%20%7C%20Anthropic-orange.svg)](#-what-sources-we-monitor)

## 🎯 What's Included

### 📚 Core Documentation
- **[ChatGPT Prompt Engineering Guide](Quick-Reference-Print.md)** - Complete reference with rating system
- **[ChatGPT Complete Reference](ChatGPT-Complete-Reference-Guide.md)** - Comprehensive model guide
- **[Anthropic Claude Guide](Anthropic-Claude-Models-Guide.md)** - Claude-specific strategies
- **[AI Platform Comparison](AI-Platform-Comparison-Guide.md)** - When to use which platform
- **[Terminal & CLI Guide](AI-Terminal-CLI-Guide.md)** - Command-line AI tools

### 🔧 Automation System
- **[Auto-Updater](AUTO-UPDATER-README.md)** - Daily documentation maintenance
- **[Batch Scripts](setup.bat)** - One-click setup and execution
- **[Python Updater](doc_updater.py)** - AI-powered change detection

### 📊 What Sources We Monitor
- **OpenAI Documentation**: API docs, model guides, best practices
- **Anthropic Documentation**: Claude guides, API updates, capabilities
- **GitHub Repositories**: openai-cookbook, anthropic-sdk-python
- **Official Blogs**: Release announcements, feature updates
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
1. **Print Reference**: Use [ChatGPT Prompt Guide](Quick-Reference-Print.md) for daily reference
2. **Rate Your Prompts**: Follow the [rating system](#-prompt-rating-system) 
3. **Define Your Architecture**: Identify workflow type before model selection
4. **Compare Platforms**: Check [platform comparison](AI-Platform-Comparison-Guide.md)

### For Automated Maintenance
1. **Setup**: Run `setup.bat` for one-click installation
2. **Configure**: Add API keys to `config.json`
3. **Run Daily**: Use `run_updater.bat` for automatic updates
4. **Stay Current**: System monitors AI platform changes automatically

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

## 🔄 MAINTENANCE SCHEDULE

- **Weekly:** Check for new model releases
- **Monthly:** Run update prompts on all guides
- **Quarterly:** Review and update comparison matrices

## 📖 GETTING STARTED

1. **Read:** [AI Platform Comparison Guide](AI-Platform-Comparison-Guide.md) first
2. **Print:** [ChatGPT Models & Prompting Guide](ChatGPT-Models-Prompting-Guide.md) for desk reference
3. **Bookmark:** This index for quick navigation
4. **Setup:** [AI Terminal & CLI Guide](AI-Terminal-CLI-Guide.md) for development workflow

---

**💡 Pro Tip:** Keep multiple tools in your toolkit. Each has unique strengths that complement the others.

**🔗 Quick Links:**
- [ChatGPT Web](https://chat.openai.com) | [Claude Web](https://claude.ai)
- [OpenAI API Docs](https://platform.openai.com/docs) | [Anthropic API Docs](https://docs.anthropic.com)
- [GitHub Copilot](https://github.com/features/copilot)

*AI Prompt Library Index v2025.07.07*
