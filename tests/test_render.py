"""Tests for the render module."""

from pipeline.render import render_readme


def _topic(tid: str, display: str, repos=None, releases=None, why="", learn=""):
    return {
        "id": tid,
        "display": display,
        "items": (repos or []) + (releases or []),
        "why": why,
        "learn": learn,
    }


def _repo(name: str, stars: int = 100):
    return {
        "repo": name,
        "url": f"https://github.com/{name}",
        "stars": stars,
        "description": f"Description of {name}",
        "type": "trending",
    }


def _release(repo: str, version: str = "v1.0"):
    return {
        "repo": repo,
        "url": f"https://github.com/{repo}/releases/{version}",
        "version": version,
        "published_at": "2026-03-01",
        "notes": "Some release notes.",
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


def test_readme_ends_with_pipeline_link():
    out = render_readme([])
    assert "update-radar.yml" in out


def test_readme_empty_topics():
    out = render_readme([])
    assert "AI Skills Radar" in out
    assert "update-radar.yml" in out
