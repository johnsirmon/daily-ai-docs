# ChatGPT Quick Reference (Print Version)

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
| All chats | Settings → Custom Instructions | Default behavior |
| One project | Projects → Instructions | Override defaults |
| Single chat | First message with ### delimiters | One-time use |

## 🤖 MODEL SELECTION

> **⚠️ Architecture First:** Prompting alone doesn't scale to production. Define your workflow—single turn, multi-step, persistent, or agentic—before optimizing for a specific model. See [Advanced Techniques](#-advanced-techniques) for orchestration patterns.

| **Model**         | **Best For**                  | **Prompt Tip**                                      |
|-------------------|-------------------------------|---------------------------------------------------|
| **GPT-4o**        | Multimodal tasks, vision, reasoning | Use "step-by-step" for complex reasoning. Supports multimodal inputs. |
| **o3**            | Advanced reasoning tasks      | Use concise instructions for logical tasks. Avoid verbosity. |
| **o4-mini**       | Fast advanced reasoning       | Ideal for quick iterative tasks. Use short prompts. |
| **o4-mini-high**  | Coding and visual reasoning   | Include code snippets and visual references for best results. |
| **GPT-4.5**       | Writing and exploring ideas   | Use creative and exploratory prompts. Ideal for brainstorming. |
| **GPT-4.1**       | Long context, coding, analysis | Use structured prompts for coding tasks. Include examples. |
| **GPT-4.1-mini**  | Everyday tasks                | Use simple, direct instructions for efficiency. |

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

## 🌐 USING CHATGPT APP VS WEB
- **App Features:**
  - Offline access for saved chats.
  - Push notifications for updates.
  - Optimized for mobile devices.
- **Web Features:**
  - Full access to advanced settings.
  - Easier integration with external tools.
  - Best for long-form content creation.

**Recommendation:** Use the app for quick tasks and notifications, and the web for detailed workflows and integrations.

*Reference Sheet v2025.07.07 • github.com/johnsirmon/daily-ai-docs*
