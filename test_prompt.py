import os
import json
from openai import OpenAI

# Mock README section
readme_mock = """
## Machine Learning Frameworks
> Why it matters: The ecosystem is moving fast, and new frameworks are making model training easier.
> What to learn: Focus on PyTorch Lightning.

### Overview
Machine learning is evolving rapidly, with a huge emphasis on developer experience.

### 🔍 Repo Deep Dives
#### `pytorch/pytorch`
**Stats:** 80k stars, 10k forks
PyTorch continues to be the dominant force in AI research. It provides native support for dynamic computation graphs, making it a favorite for researchers and production engineers alike. This week, we saw a massive surge in contributors discussing distributed backend features.

#### `keras-team/lightning`
**Stats:** 25k stars, 3k forks
Lightning abstracts away the boilerplate of PyTorch. It helps you focus on the core logic. Recent commits indicate a push towards better multi-node training stability. You should pay attention to this if you run large clusters.

### 📊 Community Pulse
We are seeing a 15% increase in PRs merged across these frameworks, indicating a healthy and thriving contributor base.

### ✅ Action Items This Week
- Try PyTorch 2.0's compile feature.
- Migrate a small script to Lightning.

### 🚀 Recent Releases
| Repo | Version | Notes |
|---|---|---|
| pytorch | 2.1 | Big performance boosts |
"""

prompt = f"""
You are an expert tech podcast host.
Turn the following markdown notes for a weekly AI newsletter topic into a single, cohesive, engaging spoken segment.

Guidelines:
1. Write directly as spoken word (no stage directions, no header tags, no Markdown).
2. Weave the repositories and insights together naturally into a unified story.
3. Avoid repetitive list-like transitions (e.g., Do NOT say "First let's look at PyTorch. Next is Lightning.").
4. Integrate the "Why it matters" and "What to learn" naturally into your commentary.
5. Do NOT use bullet points or numbered lists.
6. Do NOT introduce yourself or end the podcast, as this is just one segment of many.
7. Focus on readability and natural phrasing for Text-to-Speech (e.g. spell out acronyms if needed, use punctuation for pausing).

Markdown Notes:
{readme_mock}
"""

try:
    client = OpenAI(base_url="https://models.inference.ai.azure.com", api_key=os.environ["GITHUB_TOKEN"])
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
