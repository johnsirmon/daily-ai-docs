"""Tests for pipeline/narrate.py."""

import pipeline.narrate as _narrate_mod
from pipeline.narrate import readme_to_narration, _strip_markdown, _normalise_sentence


_SAMPLE_README = """\
# AI Skills Radar — 2026-03-01

_Updated: 2026-03-01T00:00:00Z | Covers last 14 days_

> Auto-generated. To refresh, go to **Actions → Update AI Skills Radar → Run workflow**.

## Topics

- [MCP Ecosystem](#mcp)
- [Azure AI](#azure-ai)

---

## MCP Ecosystem

> **Why it matters:** MCP is reshaping how AI tools connect.
>
> **What to learn:** Build your first MCP server.

### 🌱 New & Rising Repos

| Repo | Stars | Description |
|------|-------|-------------|
| [org/repo](https://github.com) | ⭐ 500 | A great repo |

---

## Azure AI

> **Why it matters:** Azure AI Foundry is centralising AI deployments.
>
> **What to learn:** Prompt flow and evaluation pipelines.

---

_[Pipeline source](.github/workflows/update-radar.yml) · [Config](topics/topics.yaml)_
"""

# README with a repo deep-dive section to test slash-pronunciation and introductions.
_DEEPDIVE_README = """\
# AI Skills Radar — 2026-03-01

## MCP Ecosystem

### 🔍 Repo Deep Dives

#### `microsoft/semantic-kernel`

_⭐ 22,000 · Python · 1,234 forks_

This is a great framework for orchestrating AI.

"""


def _reset_counters():
    """Reset rotation counters so each test starts from index 0."""
    _narrate_mod._topic_idx = 0
    _narrate_mod._repo_idx = 0


def test_narration_contains_date_heading():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "AI Skills Radar" in result
    assert "2026-03-01" in result


def test_narration_contains_topic_headings():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "MCP Ecosystem" in result
    assert "Azure AI" in result


def test_narration_topic_transition_is_conversational():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    # Should NOT use the old mechanical label.
    assert "Next topic:" not in result
    # Should use one of the conversational rotation phrases.
    assert any(
        phrase in result
        for phrase in ("Now let's look at", "Moving on to", "Let's turn to")
    )


def test_narration_contains_blurbs_without_labels():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    # Blurb content should be present.
    assert "MCP is reshaping how AI tools connect" in result
    assert "Build your first MCP server" in result
    assert "Azure AI Foundry is centralising AI deployments" in result
    # Written-word labels should NOT appear in the spoken output.
    assert "Why it matters:" not in result
    assert "What to learn:" not in result


def test_narration_blurb_uses_spoken_bridge():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    # Conversational bridges should be present.
    assert "Here's why this matters" in result
    assert "Here's what to focus on learning" in result


def test_narration_omits_table_rows():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "org/repo" not in result
    assert "⭐ 500" not in result


def test_narration_omits_toc():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "- [MCP Ecosystem]" not in result


def test_narration_omits_footer():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "Pipeline source" not in result
    assert "update-radar.yml" not in result


def test_narration_omits_auto_generated_line():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "Auto-generated" not in result


def test_narration_repo_introduction_no_slash():
    _reset_counters()
    result = readme_to_narration(_DEEPDIVE_README)
    # Repo announced without a slash.
    assert "slash" not in result.lower()
    assert "/" not in result or "Here's" in result  # bridge text may contain apostrophe
    # Should use "by" to separate org and repo.
    assert "semantic-kernel by microsoft" in result.lower()


def test_narration_repo_introduction_is_conversational():
    _reset_counters()
    result = readme_to_narration(_DEEPDIVE_README)
    assert "Repository:" not in result
    assert any(
        phrase in result
        for phrase in ("Let's dive into", "Up next is")
    )


def test_narration_strips_markdown_links():
    result = _strip_markdown("[some link](https://example.com)")
    assert "some link" in result
    assert "https://example.com" not in result


def test_narration_strips_bold():
    result = _strip_markdown("**Why it matters:** Something important.")
    assert "**" not in result
    assert "Why it matters:" in result


def test_normalise_sentence_capitalises():
    assert _normalise_sentence("hello world") == "Hello world."


def test_normalise_sentence_adds_period():
    assert _normalise_sentence("already good") == "Already good."


def test_normalise_sentence_preserves_existing_punctuation():
    assert _normalise_sentence("Is this right?") == "Is this right?"
    assert _normalise_sentence("Yes!") == "Yes!"


def test_empty_readme():
    _reset_counters()
    result = readme_to_narration("")
    assert result == ""

