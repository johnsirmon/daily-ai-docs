# ChatGPT Prompt Engineering Guide 📝

> **Version:** 2025.07.07 | **Status:** ✅ Current | **Next Review:** 2025.08.07  
> **Source:** OpenAI Documentation | **Last Verified:** Today | **Auto-Updated:** Daily

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Daily Updates](https://img.shields.io/badge/updated-daily-brightgreen.svg)](CHANGELOG.md)
[![Source Verified](https://img.shields.io/badge/source-OpenAI%20docs-blue.svg)](https://platform.openai.com/docs)
[![Prompt Rating](https://img.shields.io/badge/prompt%20rating-enabled-orange.svg)](#-prompt-rating-system)

## 📖 Table of Contents
- [Prompt Structure](#️-prompt-structure)
- [Model Selection](#-model-selection)  
- [Prompt Rating System](#-prompt-rating-system)
- [Advanced Techniques](#-advanced-techniques)
- [Common Patterns](#-common-patterns)
- [App vs Web Usage](#-using-chatgpt-app-vs-web)
- [Obsolescence Notes](#️-guidance-obsolescence-tracker)

---

## 🏗️ PROMPT STRUCTURE

### Basic Template
```markdown
### SYSTEM
You are [role]. [Rules/style/constraints]

### CONTEXT  
• Key facts only
• file:name.ext Sheet "Tab" Cell A1
• image:photo.jpg (describe region)

### USER
[Clear instruction + output format]
```

### Quality Checklist ✅
- [ ] **Role Definition**: Clear system role specified
- [ ] **Context Minimalism**: Only essential information included
- [ ] **Output Format**: Explicit format requirements
- [ ] **File Naming**: Descriptive names for uploads
- [ ] **Model Match**: Appropriate model for task complexity

## 📍 WHERE TO PUT PROMPTS
| **Scope** | **Location** | **Use When** |
|-----------|--------------|--------------|
| All chats | Settings → Custom Instructions | Default behavior |
| One project | Projects → Instructions | Override defaults |
| Single chat | First message with ### delimiters | One-time use |

## 🤖 MODEL SELECTION

> **💡 Pro Tip**: Model capabilities change frequently. Use the [Prompt Rating System](#-prompt-rating-system) to optimize for your chosen model.

| **Model**         | **Best For**                  | **Prompt Strategy**                                      | **Rating Weight** |
|-------------------|-------------------------------|-----------------------------------------------------|------------------|
| **GPT-4o**        | Multimodal, vision, reasoning | Step-by-step for complex reasoning. Multimodal inputs. | High complexity  |
| **o3**            | Advanced reasoning tasks      | Concise instructions. Avoid verbosity.             | Logic-focused    |
| **o4-mini**       | Fast advanced reasoning       | Quick iterative tasks. Short prompts.              | Speed-optimized  |
| **o4-mini-high**  | Coding and visual reasoning   | Include code snippets and visual references.       | Technical depth  |
| **GPT-4.5**       | Writing and exploring ideas   | Creative and exploratory prompts. Brainstorming.   | Creative tasks   |
| **GPT-4.1**       | Long context, coding, analysis | Structured prompts. Include examples.              | Context-heavy    |
| **GPT-4.1-mini**  | Everyday tasks                | Simple, direct instructions for efficiency.        | General purpose  |

### Model Selection Decision Tree
```
Complex reasoning? → o3/GPT-4o
Quick task? → o4-mini/GPT-4.1-mini  
Coding focus? → o4-mini-high/GPT-4.1
Creative work? → GPT-4.5
Multimodal? → GPT-4o
Long context? → GPT-4.1
```

## � PROMPT RATING SYSTEM

### How to Rate Your Prompts
Copy this template and paste it after your prompt to get AI feedback:

```markdown
---
**PROMPT EVALUATION REQUEST**
Please rate this prompt on a scale of 1-10 for:

1. **Clarity** (1-10): How clear and unambiguous is the instruction?
2. **Specificity** (1-10): How well does it specify the desired output?
3. **Context** (1-10): Is the right amount of context provided?
4. **Model Fit** (1-10): How well-suited is this for the chosen model?
5. **Efficiency** (1-10): How token-efficient is the prompt?

**Current Model:** [GPT-4o/o3/etc.]
**Task Type:** [Analysis/Writing/Code/etc.]
**Expected Output:** [Format/Length/Style]

Provide specific improvement suggestions and a revised version if score <8.
---
```

### Rating Criteria

| **Score** | **Clarity** | **Specificity** | **Context** | **Model Fit** | **Efficiency** |
|-----------|-------------|-----------------|-------------|---------------|----------------|
| **9-10**  | Crystal clear, no ambiguity | Exact format specified | Perfect amount | Leverages model strengths | Minimal tokens, max impact |
| **7-8**   | Clear intent, minor gaps | Good format guidance | Mostly right | Good model match | Efficient with minor waste |
| **5-6**   | Generally clear | Some format guidance | Too much/little | Adequate match | Some unnecessary words |
| **3-4**   | Somewhat unclear | Vague expectations | Poor context | Suboptimal model | Verbose or missing key info |
| **1-2**   | Confusing/vague | No format guidance | Wrong/missing | Wrong model choice | Very inefficient |

### Quick Self-Assessment
Before submitting, ask yourself:
- [ ] Would a stranger understand exactly what I want?
- [ ] Have I specified the output format clearly?
- [ ] Is my context essential and sufficient?
- [ ] Am I using the right model for this task?
- [ ] Could I remove any words without losing meaning?

### Sample Rated Prompts

#### ⭐ High-Rated Prompt (Score: 9/10)
```
Analyze the Q3 sales data. Create a table with: Product, Revenue, % Change from Q2, Top Issue. 
Rank by revenue desc. Flag products with >20% decline in red.

Data: [attach Q3_sales.csv]
```
**Why it works:** Clear task, exact format, specific criteria, perfect for GPT-4.1

#### ❌ Low-Rated Prompt (Score: 3/10)  
```
Please help me understand my sales data and maybe make it look better or something
```
**Issues:** Vague task, no format, unclear output, any model would struggle
## 📁 FILE FORMATS & OPTIMIZATION

### File Format Priority (Best → Worst)
- **Text/Code:** `.txt` `.md` `.csv` `.json` 
- **Documents:** `.pdf` (tagged) > `.docx` > scanned PDF
- **Data:** `.csv` > `.xlsx` > `.pdf`
- **Images:** `.png` `.jpg` `.webp` (≤20MB)
- **Projects:** `.zip` + README

### ⚡ Token Optimization Strategies
| **Instead of** | **Use** | **Savings** |
|----------------|---------|-------------|
| "Please analyze this document" | "Analyze:" | 4 tokens |
| "I would like you to create" | "Create" | 5 tokens |
| "documentation, application, configuration" | "docs, app, config" | 8 tokens |
| Long explanations | Bullet points | 30-50% |
| Multiple examples | 1-2 quality examples | 40-60% |

### File Naming Best Practices
```
❌ document.pdf, image.jpg, data.csv
✅ Q3_sales_report.pdf, error_screenshot.jpg, customer_data_Jan2025.csv
```

## 🧠 ADVANCED TECHNIQUES

### Core Techniques
| **Technique** | **When to Use** | **Example** | **Model Fit** |
|---------------|-----------------|-------------|---------------|
| **Few-shot prompting** | Pattern learning | Show 2-3 input→output examples | All models |
| **Chain-of-thought** | Complex reasoning | "Let's think step by step" | o3, GPT-4o |
| **Tool-calling** | API integrations | Use API `tools` field | GPT-4.1, 4o |
| **Planning prompts** | Multi-step workflows | "Create a plan, then execute" | o3, GPT-4.1 |
| **Agentic workflows** | Autonomous tasks | Persistence + tools + planning | GPT-4o, 4.1 |

### Advanced Prompt Patterns

#### 🎯 The CLEAR Pattern
```
C - Context: What's the situation?
L - Limitation: What constraints exist?
E - Example: Show desired output
A - Action: What specific task?
R - Result: What format do you want?
```

#### 🔄 The RACE Pattern  
```
R - Role: You are a [expert type]
A - Action: Your task is to [specific action]
C - Context: Given this information: [data]
E - Example: Format like this: [sample]
```

### Experimental Techniques (2025)
- **Meta-prompting**: Having AI improve your prompts
- **Constitutional AI**: Adding ethical constraints
- **Retrieval augmentation**: Combining with knowledge bases
- **Multi-agent conversations**: Multiple AI perspectives

## ✅ QUICK CHECKLIST
- [ ] SYSTEM block first with clear delimiters.
- [ ] Context = only essential info.
- [ ] Explicit output format specified.
- [ ] Descriptive file names used.
- [ ] Right model for the task.
- [ ] Unnecessary words removed.
- [ ] Step-by-step only when needed.
- [ ] Use tools via API for better accuracy.

## 🎯 COMMON PATTERNS & TEMPLATES

### Analysis Tasks
```markdown
**Template:** Analyze [data] for [specific aspect]. Format as [table/bullets].

**Rated Example (9/10):**
Analyze customer_feedback.csv for sentiment trends. 
Create table: Month, Positive%, Negative%, Key Themes, Action Items.
Include trend analysis and 3 priority recommendations.
```

### Writing Tasks  
```markdown
**Template:** Write [type] for [audience]. Tone: [professional/casual]. Length: [X words].

**Rated Example (8/10):**
Write product launch email for existing customers. 
Tone: excited but professional. Length: 150 words.
Include: benefit highlight, launch date, exclusive offer, CTA button text.
```

### Coding Tasks
```markdown
**Template:** Create [language] function that [does X]. Include error handling and comments.

**Rated Example (9/10):**
Create Python function that validates email addresses using regex.
Include: input validation, clear error messages, docstring, type hints.
Handle edge cases: empty strings, special characters, international domains.
```

### Comparison Tasks
```markdown
**Template:** Compare A vs B on [criteria]. Show pros/cons table.

**Rated Example (8/10):**
Compare React vs Vue for mid-size team project.
Criteria: learning curve, performance, ecosystem, hiring.
Format: side-by-side table + recommendation with reasoning.
```

---

## 💡 PRO TIPS & BEST PRACTICES

### Iterative Improvement
1. **Start broad, then refine** - Begin with general prompts, then add specificity
2. **Use "Think step-by-step"** only when you need to see the reasoning process  
3. **Test with multiple models** - Same prompt may work differently across models
4. **Rate every prompt** - Use the rating system to build better prompting habits

### Common Mistakes to Avoid
- ❌ Asking for multiple unrelated tasks in one prompt
- ❌ Providing too much irrelevant context
- ❌ Using vague words like "better", "good", "nice"
- ❌ Not specifying output format
- ❌ Forgetting to match prompt complexity to model capability

### Monthly Maintenance
- [ ] Check for new model releases and capabilities
- [ ] Update model selection based on performance changes  
- [ ] Review and rate your most-used prompts
- [ ] Archive obsolete techniques (see bottom section)

## 🌐 USING CHATGPT APP VS WEB

### App Advantages
- ✅ **Offline access** for saved chats
- ✅ **Push notifications** for updates  
- ✅ **Mobile-optimized** interface
- ✅ **Voice input/output** capabilities
- ✅ **Quick access** from anywhere

### Web Advantages  
- ✅ **Advanced settings** and configuration
- ✅ **Plugin integrations** and tools
- ✅ **File upload handling** (larger files)
- ✅ **Copy/paste efficiency** for code
- ✅ **Multiple tab management**

### Recommendation Matrix
| **Task Type** | **Recommended Platform** | **Why** |
|---------------|-------------------------|---------|
| Quick questions | App | Speed and convenience |
| Code development | Web | Better formatting and tools |
| Long documents | Web | Easier file management |
| On-the-go tasks | App | Mobile accessibility |
| Complex workflows | Web | Advanced features |

---

## ⚠️ GUIDANCE OBSOLESCENCE TRACKER

> **Last Updated:** July 7, 2025 | **Review Frequency:** Monthly

### 🔴 Likely to Become Obsolete (6-12 months)
- **Token counting strategies** - Models becoming more efficient
- **Specific model version recommendations** - Rapid model evolution  
- **Chain-of-thought necessity** - Built-in reasoning improvements
- **Manual file format optimization** - Better parsing capabilities

### 🟡 May Change (12-18 months)  
- **App vs Web feature differences** - Platform convergence
- **Basic prompt structure templates** - AI getting better at understanding intent
- **Model selection decision trees** - Fewer specialized models needed
- **Manual prompt rating** - Automated prompt optimization tools

### 🟢 Likely to Remain Relevant (18+ months)
- **Clear communication principles** - Fundamental to human-AI interaction
- **Context minimalism** - Efficiency will always matter
- **Output format specification** - Structure requirements persist
- **Iterative improvement methodology** - Core learning approach
- **Role-based prompting** - Context setting remains important

### 📅 Obsolescence Check Schedule
- **Monthly:** Model capability changes, new features
- **Quarterly:** Platform differences, tool updates  
- **Annually:** Fundamental prompting approaches, industry standards

### 🔄 Auto-Update Integration
This document is monitored by our [automated updater system](AUTO-UPDATER-README.md). 
Changes in AI capabilities are automatically detected and flagged for review.

---

*ChatGPT Prompt Engineering Guide v2025.07.07*  
*📍 Repository: [daily-ai-docs](https://github.com/yourusername/daily-ai-docs)*  
*📊 Source: [OpenAI Documentation](https://platform.openai.com/docs) - Verified Daily*  
*📧 Issues & Suggestions: [Open an Issue](https://github.com/yourusername/daily-ai-docs/issues)*  
*⭐ Rate this guide: Use the [Prompt Rating System](#-prompt-rating-system)*
