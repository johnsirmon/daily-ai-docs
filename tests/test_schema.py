"""Tests for output schema, normalization, and publish functions."""

import json
import tempfile
from pathlib import Path

import pytest

from pipeline.normalize import canonical_url, item_id, normalize, normalize_all
from pipeline.publish import (
    enrich,
    write_daily,
    write_narrative,
    write_trends,
    write_watchlist,
    write_weekly,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_ITEMS = [
    {
        "id": "abc0000000000001",
        "title": "MCP Server v2.0 Released",
        "url": "https://github.com/modelcontextprotocol/servers/releases/tag/v2.0",
        "published_at": "2026-02-22T10:00:00+00:00",
        "source": "modelcontextprotocol/servers",
        "source_type": "github_release",
        "topics": ["mcp"],
        "snippet": "New MCP server release with improved tool calling.",
        "score": 0.85,
        "why_it_matters": "MCP update affects tool integrations.",
        "action": "Update MCP server dependencies.",
        "_schema_version": "1",
    },
    {
        "id": "def0000000000002",
        "title": "VS Code Insiders 1.90 Ships AI Features",
        "url": "https://code.visualstudio.com/updates/v1_90",
        "published_at": "2026-02-21T08:00:00+00:00",
        "source": "VS Code Blog",
        "source_type": "rss",
        "topics": ["vscode-insiders", "github-copilot-chat"],
        "snippet": "New AI editing features in VS Code Insiders.",
        "score": 0.75,
        "why_it_matters": "VS Code Insiders ships new AI coding features.",
        "action": "Update to latest Insiders build.",
        "_schema_version": "1",
    },
]


# ---------------------------------------------------------------------------
# normalize module
# ---------------------------------------------------------------------------

def test_normalize_required_fields():
    raw = {
        "title": "Test Item",
        "url": "https://example.com/test",
        "published_at": "2026-02-22T10:00:00+00:00",
        "source": "test",
        "source_type": "rss",
        "topics": ["mcp"],
        "snippet": "A test snippet.",
    }
    item = normalize(raw)
    required = ["id", "title", "url", "published_at", "source", "source_type",
                "topics", "snippet", "score", "why_it_matters", "action", "_schema_version"]
    for field in required:
        assert field in item, f"Missing required field: {field}"


def test_normalize_id_is_16_hex_chars():
    raw = {"url": "https://example.com/x", "title": "", "topics": []}
    item = normalize(raw)
    assert len(item["id"]) == 16
    assert all(c in "0123456789abcdef" for c in item["id"])


def test_normalize_score_starts_at_zero():
    raw = {"url": "https://example.com/x", "title": "", "topics": []}
    assert normalize(raw)["score"] == 0.0


def test_normalize_topics_is_list():
    raw = {"url": "https://x.com", "topics": ["a", "b"]}
    assert isinstance(normalize(raw)["topics"], list)


def test_normalize_all():
    raws = [{"url": f"https://example.com/{i}", "title": f"Item {i}"} for i in range(3)]
    result = normalize_all(raws)
    assert len(result) == 3
    for item in result:
        assert "id" in item


def test_canonical_url_strips_utm():
    url = "https://example.com/page?utm_source=github&utm_medium=email"
    assert "utm_source" not in canonical_url(url)
    assert "utm_medium" not in canonical_url(url)


def test_canonical_url_preserves_path():
    url = "https://example.com/path/to/page"
    assert canonical_url(url) == url


def test_item_id_is_deterministic():
    assert item_id("https://example.com") == item_id("https://example.com")


def test_item_id_differs_for_different_urls():
    assert item_id("https://a.com") != item_id("https://b.com")


# ---------------------------------------------------------------------------
# enrich
# ---------------------------------------------------------------------------

def test_enrich_fills_why_it_matters():
    items = [{"topics": ["mcp"], "source_type": "github_release",
               "why_it_matters": "", "action": ""}]
    topics_cfg = [{"id": "mcp", "why_matters_template": "MCP matters!", "action_template": "Do X."}]
    result = enrich(items, topics_cfg)
    assert result[0]["why_it_matters"] == "MCP matters!"
    assert result[0]["action"] == "Do X."


def test_enrich_does_not_overwrite_existing():
    items = [{"topics": ["mcp"], "source_type": "rss",
               "why_it_matters": "Custom note", "action": "Custom action"}]
    topics_cfg = [{"id": "mcp", "why_matters_template": "MCP matters!", "action_template": "Do X."}]
    result = enrich(items, topics_cfg)
    assert result[0]["why_it_matters"] == "Custom note"


# ---------------------------------------------------------------------------
# write_daily
# ---------------------------------------------------------------------------

def test_write_daily_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_daily(SAMPLE_ITEMS, "2026-02-22", out_dir=tmpdir)
        assert path.exists()


def test_write_daily_contains_date_and_titles():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_daily(SAMPLE_ITEMS, "2026-02-22", out_dir=tmpdir)
        content = path.read_text()
        assert "2026-02-22" in content
        assert "MCP Server v2.0 Released" in content
        assert "Why it matters" in content
        assert "Action" in content


def test_write_daily_empty_items():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_daily([], "2026-02-22", out_dir=tmpdir)
        assert path.exists()
        assert "2026-02-22" in path.read_text()


# ---------------------------------------------------------------------------
# write_weekly
# ---------------------------------------------------------------------------

def test_write_weekly_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_weekly(SAMPLE_ITEMS, "2026-08", out_dir=tmpdir)
        assert path.exists()


def test_write_weekly_contains_week_and_topics():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_weekly(SAMPLE_ITEMS, "2026-08", out_dir=tmpdir)
        content = path.read_text()
        assert "2026-08" in content
        # Topics should appear as section headers
        assert "Mcp" in content or "mcp" in content


# ---------------------------------------------------------------------------
# write_trends
# ---------------------------------------------------------------------------

def test_write_trends_creates_valid_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        trends_path = str(Path(tmpdir) / "trends.json")
        path = write_trends(SAMPLE_ITEMS, trends_path=trends_path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert "last_updated" in data
        assert "topics" in data
        assert "schema_version" in data


def test_write_trends_tracks_topics():
    with tempfile.TemporaryDirectory() as tmpdir:
        trends_path = str(Path(tmpdir) / "trends.json")
        write_trends(SAMPLE_ITEMS, trends_path=trends_path)
        data = json.loads(Path(trends_path).read_text())
        assert "mcp" in data["topics"]
        assert "vscode-insiders" in data["topics"]
        assert data["topics"]["mcp"]["total_items"] >= 1


def test_write_trends_preserves_history():
    """Existing daily history from a previous day is retained."""
    with tempfile.TemporaryDirectory() as tmpdir:
        trends_path = str(Path(tmpdir) / "trends.json")
        initial = {
            "last_updated": "2026-02-20",
            "schema_version": "1",
            "topics": {
                "mcp": {"total_items": 5, "daily": {"2026-02-20": 5}},
            },
        }
        Path(trends_path).write_text(json.dumps(initial), encoding="utf-8")

        write_trends(SAMPLE_ITEMS, trends_path=trends_path)
        data = json.loads(Path(trends_path).read_text())

        assert "2026-02-20" in data["topics"]["mcp"]["daily"]
        assert data["topics"]["mcp"]["total_items"] >= 5


def test_write_trends_reruns_are_idempotent():
    """Running twice on the same day should not double-count."""
    with tempfile.TemporaryDirectory() as tmpdir:
        trends_path = str(Path(tmpdir) / "trends.json")
        write_trends(SAMPLE_ITEMS, trends_path=trends_path)
        data1 = json.loads(Path(trends_path).read_text())

        write_trends(SAMPLE_ITEMS, trends_path=trends_path)
        data2 = json.loads(Path(trends_path).read_text())

        assert data1["topics"]["mcp"]["total_items"] == data2["topics"]["mcp"]["total_items"]


# ---------------------------------------------------------------------------
# write_watchlist
# ---------------------------------------------------------------------------

def test_write_watchlist_filters_by_threshold():
    with tempfile.TemporaryDirectory() as tmpdir:
        wl_path = str(Path(tmpdir) / "watchlist.md")
        path = write_watchlist(SAMPLE_ITEMS, threshold=0.80, watchlist_path=wl_path)
        content = path.read_text()
        # Only the 0.85-score MCP item should appear
        assert "MCP Server v2.0 Released" in content
        # The 0.75-score VS Code item should NOT appear
        assert "VS Code Insiders 1.90" not in content


def test_write_watchlist_empty_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        wl_path = str(Path(tmpdir) / "watchlist.md")
        path = write_watchlist([], threshold=0.70, watchlist_path=wl_path)
        assert "No high-signal items" in path.read_text()


def test_write_watchlist_contains_table_header():
    with tempfile.TemporaryDirectory() as tmpdir:
        wl_path = str(Path(tmpdir) / "watchlist.md")
        path = write_watchlist(SAMPLE_ITEMS, threshold=0.50, watchlist_path=wl_path)
        content = path.read_text()
        assert "| Title |" in content
        assert "| Score |" in content


# ---------------------------------------------------------------------------
# write_narrative
# ---------------------------------------------------------------------------

def test_write_narrative_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_narrative(SAMPLE_ITEMS, "2026-02-22", out_dir=tmpdir)
        assert path.exists()


def test_write_narrative_contains_date_and_titles():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_narrative(SAMPLE_ITEMS, "2026-02-22", out_dir=tmpdir)
        content = path.read_text()
        assert "2026-02-22" in content
        assert "MCP Server v2.0 Released" in content
        assert "VS Code Insiders 1.90 Ships AI Features" in content


def test_write_narrative_top_story_not_collapsed():
    """The first item must be fully visible (not inside <details>)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_narrative(SAMPLE_ITEMS, "2026-02-22", out_dir=tmpdir)
        content = path.read_text()
        # Top story section appears before any <details> block
        top_story_pos = content.find("Top Story")
        first_details_pos = content.find("<details>")
        assert top_story_pos != -1
        # The top story heading must come before the first collapsible block
        assert top_story_pos < first_details_pos


def test_write_narrative_secondary_items_collapsed():
    """Items after the first are wrapped in <details> for mobile-friendly display."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_narrative(SAMPLE_ITEMS, "2026-02-22", out_dir=tmpdir)
        content = path.read_text()
        assert "<details>" in content
        assert "</details>" in content
        # Second item title appears inside a <details> block
        details_block_start = content.find("<details>")
        assert "VS Code Insiders" in content[details_block_start:]


def test_write_narrative_contains_why_and_action():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_narrative(SAMPLE_ITEMS, "2026-02-22", out_dir=tmpdir)
        content = path.read_text()
        assert "Why it matters" in content
        assert "Action" in content


def test_write_narrative_empty_items():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_narrative([], "2026-02-22", out_dir=tmpdir)
        assert path.exists()
        content = path.read_text()
        assert "2026-02-22" in content
        assert "No updates" in content


def test_write_narrative_single_item_no_details():
    """A single item should have no collapsible <details> block."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_narrative(SAMPLE_ITEMS[:1], "2026-02-22", out_dir=tmpdir)
        content = path.read_text()
        assert "<details>" not in content
