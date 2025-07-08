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

| **Tool** | **Best For** | **Pricing** | **Offline** | **File Access** |
|----------|--------------|-------------|-------------|-----------------|
| **Claude Code** | Development, debugging | Free tier + paid | ❌ | ✅ Direct |
| **OpenAI CLI** | API automation, scripting | Pay-per-use | ❌ | ⚠️ Via upload |
| **GitHub Copilot CLI** | Git workflows, commands | $10/month | ❌ | ✅ Repo context |
| **Cursor IDE** | AI-powered coding | Free + Pro | ✅ | ✅ Full IDE |

## 🚀 ADVANCED WORKFLOWS

### **Automated Code Review**
```bash
#!/bin/bash
# review-pr.sh
git diff main..HEAD > changes.diff
claude-code review --file changes.diff --output review.md
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
