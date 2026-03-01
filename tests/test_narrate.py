"""Tests for pipeline/narrate.py."""

from pipeline.narrate import readme_to_narration, _strip_markdown


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


def test_narration_contains_date_heading():
    result = readme_to_narration(_SAMPLE_README)
    assert "AI Skills Radar" in result
    assert "2026-03-01" in result


def test_narration_contains_topic_headings():
    result = readme_to_narration(_SAMPLE_README)
    assert "MCP Ecosystem" in result
    assert "Azure AI" in result


def test_narration_contains_blurbs():
    result = readme_to_narration(_SAMPLE_README)
    assert "MCP is reshaping how AI tools connect" in result
    assert "Build your first MCP server" in result
    assert "Azure AI Foundry is centralising AI deployments" in result


def test_narration_omits_table_rows():
    result = readme_to_narration(_SAMPLE_README)
    assert "org/repo" not in result
    assert "⭐ 500" not in result


def test_narration_omits_toc():
    result = readme_to_narration(_SAMPLE_README)
    # TOC list items should not appear as raw bullet points
    assert "- [MCP Ecosystem]" not in result


def test_narration_omits_footer():
    result = readme_to_narration(_SAMPLE_README)
    assert "Pipeline source" not in result
    assert "update-radar.yml" not in result


def test_narration_omits_auto_generated_line():
    result = readme_to_narration(_SAMPLE_README)
    assert "Auto-generated" not in result


def test_narration_strips_markdown_links():
    result = _strip_markdown("[some link](https://example.com)")
    assert "some link" in result
    assert "https://example.com" not in result


def test_narration_strips_bold():
    result = _strip_markdown("**Why it matters:** Something important.")
    assert "**" not in result
    assert "Why it matters:" in result


def test_empty_readme():
    result = readme_to_narration("")
    assert result == ""
