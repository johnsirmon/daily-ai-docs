# Anthropic Claude Complete Guide (Print Version)

## Guidance Obsolescence

| Section | Review trigger | Last validated |
|---------|----------------|----------------|
| Model lineup | New Claude model release | 2025-06 |
| Prompt structure | Anthropic API update | 2025-06 |
| Context window limits | Model capability update | 2025-06 |
| Pricing and tiers | Anthropic pricing change | 2025-06 |

## 🏗️ PROMPT STRUCTURE
```
### SYSTEM
You are [role]. [Rules/style/constraints]

### CONTEXT  
• Key facts only
• file:name.ext Sheet "Tab" Cell A1
• image:photo.jpg (describe region)

### USER
[Clear instruction + output format]
```

## 📍 WHERE TO PUT PROMPTS
| **Scope** | **Location** | **Use When** |
|-----------|--------------|--------------|
| All chats | Claude.ai Settings | Default behavior for web/app |
| One project | Anthropic Console API | Developer/API usage |
| Single chat | First message with ### delimiters | One-time use |

## 🌐 USING CLAUDE: WEB VS APP VS TERMINAL
| **Platform** | **Best For** | **Features** |
|--------------|--------------|--------------|
| **Claude.ai Web** | Complex workflows, long documents | Full feature set, file uploads, Projects |
| **Claude Mobile App** | Quick tasks, on-the-go | Chat sync, notifications, mobile optimized |
| **Claude Code (Terminal)** | Coding, local development | Direct file access, terminal integration, coding focus |
| **Anthropic API** | Custom integrations | Full programmatic control, enterprise features |

## 🤖 MODEL SELECTION

> **⚠️ Architecture First:** Model selection is a downstream decision. Define your workflow requirements—single-turn, multi-step, persistent state, tool use—before picking a model. Orchestration and context engineering deliver more durable value than model swapping alone.

| **Model**         | **Best For**                  | **Prompt Tip**                                      |
|-------------------|-------------------------------|---------------------------------------------------|
| **Claude 4 Opus** | Complex reasoning, analysis   | Use detailed prompts. Excellent for nuanced tasks. |
| **Claude 3.7 Sonnet** | Balanced performance, coding | Great all-rounder. Include examples for consistency. |
| **Claude 3.5 Haiku** | Fast responses, simple tasks | Keep prompts concise. Ideal for quick iterations. |
| **Claude Code** | Software development, debugging | Provide full context, file structures, error logs. Supports multi-file reasoning and agentic coding workflows. |

## 📁 FILE FORMATS (Best → Worst)
- **Text/Code:** `.txt` `.md` `.csv` `.json` 
- **Documents:** `.pdf` (tagged) > `.docx` > scanned PDF
- **Data:** `.csv` > `.xlsx` > `.pdf`
- **Images:** `.png` `.jpg` `.webp` (≤20MB)
- **Projects:** `.zip` + README

## ⚡ TOKEN OPTIMIZATION
- Remove "please", "kindly", "I would like"
- Use bullets instead of sentences
- Abbreviate: docs, app, config, auth
- Include only essential context
- 1-2 quality examples > many mediocre ones

## 🧠 ADVANCED TECHNIQUES

### Prompt-Level Techniques
- **Few-shot prompting:** Show 2-3 input→output examples to guide the model.
- **Chain-of-thought:** Use "Let's think step by step" for reasoning tasks.
- **Tool-calling:** Pass tools via the API's `tools` field for better accuracy.
- **Planning prompts:** Induce explicit step-by-step plans for complex workflows.

### Agent & Orchestration Patterns (Modern Approach)
- **Persistent memory:** Maintain state across sessions using memory tools or vector stores—not just prompt context.
- **Multi-step agent loops:** Plan → execute → verify → retry without human intervention.
- **Context engineering:** Dynamically assemble context (retrieval, summaries, tool outputs) rather than relying on static prompt templates.
- **Agentic workflows:** Combine persistence, tool-calling, memory, and execution loops for autonomous, production-grade tasks.
- **Claude Code for agentic coding:** Claude Code goes beyond single-shot completion—it can read/write files, run tests, refactor across a codebase, and iterate in an execution loop.

## ✅ QUICK CHECKLIST
- [ ] SYSTEM block first with clear delimiters.
- [ ] Context = only essential info.
- [ ] Explicit output format specified.
- [ ] Descriptive file names used.
- [ ] Workflow requirements defined (single-turn, multi-step, persistent, agentic?).
- [ ] Right model for the task (after workflow is defined).
- [ ] Unnecessary words removed.
- [ ] Step-by-step only when needed.
- [ ] Use tools via API for better accuracy.
- [ ] For multi-step or persistent tasks, consider an agent/orchestration layer.

## 🎯 COMMON PATTERNS

**Analysis:** `Analyze [data] for [specific aspect]. Format as [table/bullets].`

**Writing:** `Write [type] for [audience]. Tone: [professional/casual]. Length: [X words].`

**Code:** `Create [language] function that [does X]. Include error handling and comments.`

**Comparison:** `Compare A vs B on [criteria]. Show pros/cons table.`

---
**💡 Pro Tip:** Start broad, then refine. Use "Think step-by-step" only when you need to see the reasoning process.

**🔄 Keep Current:** Run monthly updates using AI to check for new techniques and model capabilities.

*Reference Sheet v2025.07.07 • anthropic.com*
