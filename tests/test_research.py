"""Tests for pipeline/research.py."""

from datetime import date

from pipeline.research import run_research_summary, dry_run_report, _build_item_summary


def _repo(name: str, topic_display: str = "MCP Ecosystem", stars: int = 500) -> dict:
    return {
        "repo": name,
        "url": f"https://github.com/{name}",
        "stars": stars,
        "description": f"A tool for {name}",
        "language": "Python",
        "forks": 20,
        "open_issues": 5,
        "topics": ["ai"],
        "pushed_at": "2026-03-01",
        "type": "trending",
        "topic_display": topic_display,
    }


def _release(repo: str, version: str = "v1.0", topic_display: str = "MCP Ecosystem") -> dict:
    return {
        "repo": repo,
        "url": f"https://github.com/{repo}/releases/{version}",
        "version": version,
        "published_at": "2026-03-01",
        "notes": "New feature added.",
        "reactions": 5,
        "type": "release",
        "topic_display": topic_display,
    }


# ── run_research_summary fail-open ───────────────────────────────────────────

def test_empty_items_returns_empty_report():
    report = run_research_summary([], topic_ids=["mcp"], _force=True)
    assert report["week_story"] == ""
    assert report["narrative_hook"] == ""
    assert report["topic_insights"] == {}


def test_no_token_returns_empty_report(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    items = [_repo("org/repo")]
    report = run_research_summary(items, topic_ids=["mcp"], _force=True)
    assert report["week_story"] == ""
    assert isinstance(report["topic_insights"], dict)


# ── dry_run_report ───────────────────────────────────────────────────────────

def test_dry_run_report_has_all_fields():
    report = dry_run_report(["mcp", "azure-ai"])
    assert "[dry-run]" in report["week_story"]
    assert "[dry-run]" in report["narrative_hook"]
    assert "mcp" in report["topic_insights"]
    assert "azure-ai" in report["topic_insights"]


def test_dry_run_report_empty_topics():
    report = dry_run_report([])
    assert report["topic_insights"] == {}


# ── _build_item_summary ──────────────────────────────────────────────────────

def test_build_item_summary_includes_repos():
    items = [_repo("org/myrepo", stars=1000)]
    text = _build_item_summary(items)
    assert "org/myrepo" in text
    assert "1,000" in text


def test_build_item_summary_includes_releases():
    items = [_release("org/tool", "v2.0")]
    text = _build_item_summary(items)
    assert "RELEASE" in text
    assert "org/tool" in text
    assert "v2.0" in text


def test_build_item_summary_caps_at_40():
    items = [_repo(f"org/repo-{i}") for i in range(50)]
    text = _build_item_summary(items)
    count = text.count("org/repo-")
    assert count <= 40


# ── cache ────────────────────────────────────────────────────────────────────

def test_cache_is_written_on_api_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import json

    fake_report = {
        "week_story": " ".join(["word"] * 60),
        "narrative_hook": "This week in AI, things happened.",
        "topic_insights": {"mcp": "Active topic."},
    }

    def fake_client_factory():
        class FakeChoice:
            message = type("M", (), {"content": json.dumps(fake_report)})()
        class FakeResp:
            choices = [FakeChoice()]
        class FakeClient:
            def chat(self):
                pass
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        return FakeResp()
        return FakeClient()

    import pipeline.research as research_mod
    monkeypatch.setattr(research_mod, "_get_client", fake_client_factory)

    today = date(2026, 3, 1)
    result = run_research_summary([_repo("org/r")], topic_ids=["mcp"], today=today, _force=True)

    assert result["week_story"] != ""
    cache_file = tmp_path / ".cache" / "research_2026-03-01.json"
    assert cache_file.exists()
