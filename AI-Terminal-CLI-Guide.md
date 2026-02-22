# AI Terminal & CLI Tools Guide

## 🖥️ CLAUDE CODE (TERMINAL)

### **Installation & Setup**
```bash
# Install Claude Code (when available)
curl -fsSL https://claude.ai/install | sh
# or via package manager
brew install claude-code
```

### **Basic Usage**
```bash
# Analyze code files
claude-code analyze myfile.py

# Debug with context
claude-code debug --file app.js --error "TypeError on line 42"

# Code review
claude-code review --diff main..feature-branch

# Interactive coding session
claude-code chat --project ./my-app
```

### **Best Practices**
- Provide full file context for better analysis
- Include error logs and stack traces
- Use project-level commands for consistency
- Set up configuration files for team settings

## 🤖 OPENAI CLI

### **Installation & Setup**
```bash
# Install OpenAI CLI
pip install openai-cli
# or
npm install -g openai-cli

# Set API key
export OPENAI_API_KEY="your-api-key"
```

### **Basic Usage**
```bash
# Chat completion
openai api chat.completions.create \
  -m gpt-4o \
  --message "user" "Explain Python decorators"

# Code generation
openai api chat.completions.create \
  -m gpt-4.1 \
  --message "system" "You are a Python expert" \
  --message "user" "Create a REST API with FastAPI"

# Batch processing
openai api chat.completions.create \
  -m gpt-4o-mini \
  --file prompts.jsonl
```

## 🐙 GITHUB COPILOT CLI

### **Installation & Setup**
```bash
# Install GitHub CLI extension
gh extension install github/gh-copilot

# Authenticate
gh auth login
```

### **Usage Examples**
```bash
# Get command suggestions
gh copilot suggest "compress all images in directory"

# Explain existing commands
gh copilot explain "docker run -d -p 8080:80 nginx"

# Git workflow help
gh copilot suggest "undo last commit but keep changes"
```

## 🔧 COMPARISON TABLE

| **Tool** | **Best For** | **Pricing** | **Offline** | **File Access** | **Agentic / Multi-file** |
|----------|--------------|-------------|-------------|-----------------|--------------------------|
| **Claude Code** | Development, debugging, agentic coding | Free tier + paid | ❌ | ✅ Direct | ✅ Full codebase, test execution |
| **OpenAI CLI** | API automation, scripting | Pay-per-use | ❌ | ⚠️ Via upload | ⚠️ Manual chaining |
| **GitHub Copilot CLI** | Git workflows, commands, repo-aware suggestions | $10/month | ❌ | ✅ Repo context | ✅ Multi-file reasoning |
| **Cursor IDE** | AI-powered coding with integrated agent | Free + Pro | ✅ | ✅ Full IDE | ✅ Multi-file, CI/CD hooks |

## 🚀 ADVANCED WORKFLOWS

> **Agentic Coding Note:** Modern AI coding tools go beyond single-shot command suggestions. Claude Code, GitHub Copilot, and similar tools can operate in agentic loops—reading and writing files, running tests, refactoring across multiple files, and iterating until a goal is met. Design your workflows to leverage this capability rather than treating them as one-shot autocomplete.

### **Automated Code Review (CI/CD Integration)**
```bash
#!/bin/bash
# review-pr.sh — Run in CI pipeline (e.g., GitHub Actions)
git diff main..HEAD > changes.diff
claude-code review --file changes.diff --output review.md
# Optionally post review.md as a PR comment via gh CLI
```

### **Batch Documentation**
```bash
# Generate docs for all Python files
find . -name "*.py" -exec claude-code document {} \;
```

### **Error Analysis Pipeline**
```bash
# Capture error and analyze
npm test 2>&1 | tee error.log
claude-code debug --log error.log --suggest-fix
```

### **Multi-File Refactoring (Agentic Loop)**
```bash
# Let Claude Code reason across the codebase, run tests, and iterate
claude-code refactor --goal "migrate deprecated API calls to v2" \
  --run-tests --max-iterations 5
```

## ⚡ PRODUCTIVITY TIPS

1. **Set up aliases:**
```bash
alias cc='claude-code'
alias oai='openai api chat.completions.create -m gpt-4o'
alias cop='gh copilot suggest'
```

2. **Create configuration files:**
```yaml
# .claude-config.yml
default_model: "claude-3.7-sonnet"
include_context: true
max_tokens: 4000
```

3. **Use environment variables:**
```bash
export CLAUDE_MODEL="claude-code"
export OPENAI_MODEL="gpt-4.1"
export GITHUB_TOKEN="your-token"
```

---
**💡 Pro Tip:** Combine tools! Use GitHub Copilot CLI for git commands, Claude Code for analysis, and OpenAI CLI for batch processing.

**🔒 Security:** Never expose API keys in scripts. Use environment variables or secure credential managers.

*Terminal Guide v2025.07.07*
