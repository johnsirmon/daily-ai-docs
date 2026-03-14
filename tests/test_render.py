"""Tests for the render module."""

from pipeline.render import render_readme, topic_anchor_markup


def _topic(tid: str, display: str, repos=None, releases=None, why="", learn="",
           summary="", community_pulse="", action_items=None, deep_dives=None):
    return {
        "id": tid,
        "display": display,
        "items": (repos or []) + (releases or []),
        "why": why,
        "learn": learn,
        "summary": summary,
        "community_pulse": community_pulse,
        "action_items": action_items or [],
        "deep_dives": deep_dives or [],
    }


def _repo(name: str, stars: int = 100, language: str = "", forks: int = 0,
          open_issues: int = 0, commit_trend: str = "flat"):
    return {
        "repo": name,
        "url": f"https://github.com/{name}",
        "stars": stars,
        "description": f"Description of {name}",
        "language": language,
        "forks": forks,
        "open_issues": open_issues,
        "commit_trend": commit_trend,
        "type": "trending",
    }


def _release(repo: str, version: str = "v1.0"):
    return {
        "repo": repo,
        "url": f"https://github.com/{repo}/releases/{version}",
        "version": version,
        "published_at": "2026-03-01",
        "notes": "Some release notes.",
        "reactions": 0,
        "type": "release",
    }


def test_readme_contains_date():
    out = render_readme([])
    # Date appears in the heading
    assert "AI Skills Radar" in out


def test_readme_contains_topic_heading():
    topics = [_topic("mcp", "MCP Ecosystem", repos=[_repo("org/repo")])]
    out = render_readme(topics)
    assert "## MCP Ecosystem" in out


def test_readme_contains_repo_table():
    topics = [_topic("mcp", "MCP Ecosystem", repos=[_repo("org/myrepo", stars=999)])]
    out = render_readme(topics)
    assert "org/myrepo" in out
    assert "999" in out


def test_readme_contains_release_table():
    topics = [_topic("mcp", "MCP Ecosystem", releases=[_release("org/myrepo", "v2.0")])]
    out = render_readme(topics)
    assert "v2.0" in out
    assert "Recent Releases" in out


def test_readme_shows_blurbs_when_present():
    topics = [_topic("mcp", "MCP", why="Very important.", learn="Learn X.")]
    out = render_readme(topics)
    assert "Very important." in out
    assert "Learn X." in out


def test_readme_no_activity_fallback():
    topics = [_topic("mcp", "MCP Ecosystem")]
    out = render_readme(topics)
    assert "No recent activity" in out


def test_readme_toc_links():
    topics = [_topic("mcp", "MCP Ecosystem"), _topic("azure-ai", "Azure AI")]
    out = render_readme(topics)
    assert "[MCP Ecosystem]" in out
    assert "[Azure AI]" in out


def test_readme_topic_sections_include_explicit_anchor():
    topics = [_topic("mcp", "MCP Ecosystem", repos=[_repo("org/repo")])]
    out = render_readme(topics)
    assert f"{topic_anchor_markup('mcp')}\n## MCP Ecosystem" in out


def test_readme_ends_with_pipeline_link():
    out = render_readme([])
    assert "update-radar.yml" in out


def test_readme_empty_topics():
    out = render_readme([])
    assert "AI Skills Radar" in out
    assert "update-radar.yml" in out


# ---------------------------------------------------------------------------
# New narrative sections
# ---------------------------------------------------------------------------

def test_readme_deep_dive_prose_appears():
    dives = [{"repo": "org/myrepo", "prose": "This repo solves a hard problem."}]
    topics = [_topic("mcp", "MCP", repos=[_repo("org/myrepo")], deep_dives=dives)]
    out = render_readme(topics)
    assert "This repo solves a hard problem." in out
    assert "🔍 Repo Deep Dives" in out


def test_readme_deep_dive_shows_repo_heading():
    dives = [{"repo": "org/myrepo", "prose": "Some prose."}]
    topics = [_topic("mcp", "MCP", repos=[_repo("org/myrepo")], deep_dives=dives)]
    out = render_readme(topics)
    assert "org/myrepo" in out


def test_readme_community_pulse_appears():
    topics = [_topic("mcp", "MCP", repos=[_repo("org/r")],
                     community_pulse="Stars are growing fast this week.")]
    out = render_readme(topics)
    assert "📊 Community Pulse" in out
    assert "Stars are growing fast this week." in out


def test_readme_action_items_appear():
    topics = [_topic("mcp", "MCP", repos=[_repo("org/r")],
                     action_items=["Try building an MCP server.", "Read the spec."])]
    out = render_readme(topics)
    assert "✅ Action Items This Week" in out
    assert "Try building an MCP server." in out
    assert "Read the spec." in out


def test_readme_quick_reference_has_enriched_columns():
    repos = [_repo("org/myrepo", stars=500, language="Python", forks=42,
                   open_issues=7, commit_trend="rising")]
    topics = [_topic("mcp", "MCP", repos=repos)]
    out = render_readme(topics)
    # enriched columns present
    assert "Python" in out
    assert "42" in out
    assert "rising" in out


def test_readme_release_shows_reactions():
    rel = _release("org/repo", "v2.0")
    rel["reactions"] = 15
    topics = [_topic("mcp", "MCP", releases=[rel])]
    out = render_readme(topics)
    assert "15" in out


def test_readme_release_shows_highlights():
    rel = _release("org/repo", "v2.0")
    rel["notes"] = "Added new feature X and fixed critical bug Y."
    topics = [_topic("mcp", "MCP", releases=[rel])]
    out = render_readme(topics)
    assert "Added new feature X" in out


# ── This Week's Story section ────────────────────────────────────────────────

def test_readme_week_story_shown_when_present():
    report = {"week_story": "Agents dominated the AI landscape this week.", "narrative_hook": "", "topic_insights": {}}
    out = render_readme([], research_report=report)
    assert "This Week's Story" in out
    assert "Agents dominated the AI landscape this week." in out


def test_readme_week_story_absent_when_empty():
    report = {"week_story": "", "narrative_hook": "", "topic_insights": {}}
    out = render_readme([], research_report=report)
    assert "This Week's Story" not in out


def test_readme_week_story_absent_without_report():
    out = render_readme([])
    assert "This Week's Story" not in out


def test_readme_week_story_appears_before_first_topic():
    report = {"week_story": "Big news this week.", "narrative_hook": "", "topic_insights": {}}
    topics = [_topic("mcp", "MCP Ecosystem", repos=[_repo("org/r")])]
    out = render_readme(topics, research_report=report)
    story_pos = out.index("Big news this week.")
    topic_pos = out.index("## MCP Ecosystem")
    assert story_pos < topic_pos
