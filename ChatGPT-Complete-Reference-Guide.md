# ChatGPT Prompt Layers & Placement (Ref Sheet · 2025-07-07)

> **🔄 DAILY MAINTENANCE PROMPT**  
> *Copy this prompt and run it daily to keep this document current:*
> 
> ```
> ### SYSTEM
> You are an expert in AI prompt engineering and ChatGPT usage patterns. You stay current with the latest research, model updates, and best practices.
> 
> ### CONTEXT
> I have a ChatGPT prompt engineering reference sheet dated 2025-07-07. It covers prompt structure, model selection, file formats, and optimization techniques.
> 
> ### TASK
> 1. Review the attached document for outdated information
> 2. Check if any new ChatGPT models, features, or techniques have emerged since July 7, 2025
> 3. Identify any deprecated practices or changed recommendations
> 4. Suggest specific updates with exact wording for any sections that need changes
> 5. Note if the document is still current and accurate
> 
> Focus on: model capabilities, token limits, new prompting techniques, file format support, and research findings.
> ```

---

## 1️⃣ Prompt Layers
- **SYSTEM ("role & rules")** – Sets persona, boundaries, format.  
- **CONTEXT** – Facts, excerpts, examples, file/image references.  
- **USER TASK** – Plain-language instruction + constraints.

## 2️⃣ Where to Put Them in ChatGPT (Web)
| Goal | Location | How |
|------|----------|-----|
| Persist across *all* chats | **Settings → Custom Instructions**<br>• Top box = long-term CONTEXT<br>• Bottom box = default SYSTEM/style | Edit once; auto-prepended to new chats. |
| Persist *inside one project* | **Projects → Project Instructions** | Overrides Custom Instructions in that project. |
| One-off message | Put the three blocks in your very first prompt, separated by `###` or `"""`. |

> **Template** (paste as one message):  
> ```
> ### SYSTEM
> You are an <expert>. Respond in … style.
> ### CONTEXT
> • Facts…  
> • file:budget_2025.xlsx Sheet "Q1" cell D12 shows 1.2 M.  
> • images: front_view.jpg, rear_view.jpg
> ### USER
> Compare the corrosion in the two images and update the budget note.
> ```

## 3️⃣ Referencing Files & Images
- **Name files descriptively before upload** ⇒ use those names in prompts.  
- Quote small text snippets in ``` triple-backticks ```.  
- For images, describe region: "upper-left corner of `front_view.jpg`".  
- More than 5–10 small files? Zip them; describe the folder layout once.

## 4️⃣ Efficient File Types
| Task | Best format | Reason |
|------|-------------|--------|
| Pure text/code | `.txt`, `.md`, `.csv`, `.json` | No OCR, lowest tokens, direct parsing. |
| Rich docs | Tagged `.pdf` or `.docx` | Preserves structure & formatting. |
| Data tables | `.csv` > `.xlsx` > `.pdf` | CSV = lowest tokens, direct processing. |
| Presentations | `.pptx` or exported `.pdf` | Maintains slide structure. |
| Images | `.png`, `.jpg`, `.webp` ≤ 20 MB | Vision models handle all common formats. |
| Code projects | `.zip` with clear structure | Preserves file relationships. |
| Mixed content | `.zip` + manifest file | Include a README describing contents. |

## 5️⃣ Model-Specific Hints

> **⚠️ Architecture First:** Model selection is a downstream decision. Identify your workflow requirements—memory, tool use, multi-step execution, verification—before choosing a model. Orchestration and context engineering are the durable differentiators, not model choice alone.

| Model | Extra prompt tip |
|-------|------------------|
| **GPT-4o** | Add explicit "Think step-by-step" for complex reasoning. Supports multimodal input. 128k context window. |
| **o3 / o4-mini** | Extended internal reasoning; state desired output format clearly. Best for hard logic and planning tasks. |
| **GPT-4.1 / GPT-4.1-mini** | Strong for long-context coding and analysis. Use structured system prompts with concrete examples. |
| **GPT-4.5** | Optimized for writing, brainstorming, and exploration. Use open-ended, generative prompts. |

## 6️⃣ Token Optimization
- **Remove redundant words**: "Please analyze" → "Analyze"
- **Use bullet points** instead of full sentences for lists
- **Compress examples**: Show 1-2 quality examples vs. many mediocre ones
- **Smart context**: Only include relevant background info
- **Abbreviate when clear**: "documentation" → "docs", "application" → "app"

## 7️⃣ Advanced Techniques

> **Beyond Prompts:** For production workflows, prompting is the entry point—not the architecture. Persistent state, memory layers, tool use, and agent orchestration are now the primary design concerns.

### Prompt-Level Techniques
- **Few-shot prompting**: 2-3 input→output examples for consistency
- **Chain-of-thought**: Add "Let's think step by step" for complex reasoning
- **Tree of thoughts**: "Consider 3 different approaches, then choose the best"
- **Self-consistency**: "Give me 3 solutions, then pick the most reliable one"
- **Prompt chaining**: Break complex tasks into sequential prompt steps

### Agent & Orchestration Patterns (Modern Approach)
- **Persistent memory**: Maintain state across sessions using vector stores or structured memory tools
- **Tool/function calling**: Connect models to APIs, databases, code execution, and external systems
- **Multi-step agent loops**: Plan → execute → verify → retry cycles without human intervention
- **Context engineering**: Dynamically assemble the right context (RAG, summaries, tool results) rather than static prompt templates
- **Multi-agent systems**: Coordinate specialized agents (planner, executor, critic) for complex workflows

## 8️⃣ Research-Backed Tips
- Putting SYSTEM at the very top and delimiting sections boosts accuracy and lowers hallucinations (OpenAI API guide, 2025).  
- Chain-of-Thought ("think step-by-step") raises reasoning scores on math & logic benchmarks; use it **only when needed** to save tokens (Chang et al., 2024 survey).  
- Role-specific system prompts outperform plain ones in dialogue quality (Liu et al., 2024 Role-Playing Framework).  
- Automatic prompt optimizers (APE, EvoPrompting) now match or beat expert-written prompts on 19 / 24 tasks—use them for high-volume work.  

---

### Quick Checklist
- [ ] SYSTEM first, clear delimiters (`###` or `"""`).  
- [ ] Context = only what the model *must* know to complete the task.  
- [ ] Explicit output format and constraints.  
- [ ] Descriptive file names & specific references (page/cell/region).  
- [ ] Define workflow requirements (memory? tools? multi-step?) before selecting a model.
- [ ] Remove unnecessary words to optimize tokens.
- [ ] Use step-by-step only when you need visible reasoning process.  
- [ ] Prefer structured formats (CSV/JSON) over unstructured (PDF scans).
- [ ] For persistent or multi-step tasks, consider an agent/orchestration layer.
