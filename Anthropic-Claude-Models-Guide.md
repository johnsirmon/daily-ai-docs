# Anthropic Claude Complete Guide (Print Version)

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
| **Model**         | **Best For**                  | **Prompt Tip**                                      |
|-------------------|-------------------------------|---------------------------------------------------|
| **Claude 4 Opus** | Complex reasoning, analysis   | Use detailed prompts. Excellent for nuanced tasks. |
| **Claude 3.7 Sonnet** | Balanced performance, coding | Great all-rounder. Include examples for consistency. |
| **Claude 3.5 Haiku** | Fast responses, simple tasks | Keep prompts concise. Ideal for quick iterations. |
| **Claude Code** | Software development, debugging | Provide full context, file structures, error logs. |

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
- **Few-shot prompting:** Show 2-3 input→output examples to guide the model.
- **Chain-of-thought:** Use "Let's think step by step" for reasoning tasks.
- **Tool-calling:** Pass tools via the API's `tools` field for better accuracy.
- **Planning prompts:** Induce explicit step-by-step plans for complex workflows.
- **Agentic workflows:** Use persistence, tool-calling, and planning reminders for autonomous tasks.

## ✅ QUICK CHECKLIST
- [ ] SYSTEM block first with clear delimiters.
- [ ] Context = only essential info.
- [ ] Explicit output format specified.
- [ ] Descriptive file names used.
- [ ] Right model for the task.
- [ ] Unnecessary words removed.
- [ ] Step-by-step only when needed.
- [ ] Use tools via API for better accuracy.

## 🎯 COMMON PATTERNS

**Analysis:** `Analyze [data] for [specific aspect]. Format as [table/bullets].`

**Writing:** `Write [type] for [audience]. Tone: [professional/casual]. Length: [X words].`

**Code:** `Create [language] function that [does X]. Include error handling and comments.`

**Comparison:** `Compare A vs B on [criteria]. Show pros/cons table.`

---
**💡 Pro Tip:** Start broad, then refine. Use "Think step-by-step" only when you need to see the reasoning process.

**🔄 Keep Current:** Run monthly updates using AI to check for new techniques and model capabilities.

*Reference Sheet v2025.07.07 • anthropic.com*
