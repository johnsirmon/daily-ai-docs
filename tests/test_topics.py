"""Tests for self-learning loop and local agent orchestration topic configuration."""

from pathlib import Path

import pytest
import yaml

TOPICS_PATH = Path(__file__).parent.parent / "topics" / "topics.yaml"

NEW_TOPIC_IDS = ["self-learning-loops", "local-agent-orchestration"]
NEW_SOURCE_REPOS = [
    ("microsoft", "autogen"),
    ("langchain-ai", "langgraph"),
    ("crewAIInc", "crewAI"),
]


@pytest.fixture(scope="module")
def config():
    with open(TOPICS_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_new_topics_present(config):
    topic_ids = [t["id"] for t in config["topics"]]
    for tid in NEW_TOPIC_IDS:
        assert tid in topic_ids, f"Missing topic id: {tid}"


def test_new_topics_have_required_fields(config):
    required = {"id", "display", "keywords", "why_matters_template", "action_template"}
    for topic in config["topics"]:
        if topic["id"] in NEW_TOPIC_IDS:
            for field in required:
                assert field in topic, f"Topic '{topic['id']}' missing field '{field}'"


def test_self_learning_loops_keywords(config):
    topic = next(t for t in config["topics"] if t["id"] == "self-learning-loops")
    keywords = [kw.lower() for kw in topic["keywords"]]
    assert any("loop" in kw for kw in keywords), "Expected 'loop' keyword in self-learning-loops"
    assert any("feedback" in kw for kw in keywords), "Expected 'feedback' keyword"


def test_local_agent_orchestration_keywords(config):
    topic = next(t for t in config["topics"] if t["id"] == "local-agent-orchestration")
    keywords = [kw.lower() for kw in topic["keywords"]]
    assert any("handoff" in kw for kw in keywords), "Expected 'handoff' keyword"
    assert any("orchestration" in kw for kw in keywords), "Expected 'orchestration' keyword"


def test_new_github_sources_present(config):
    releases = config.get("sources", {}).get("github_releases", [])
    tracked = {(s["owner"], s["repo"]) for s in releases}
    for owner, repo in NEW_SOURCE_REPOS:
        assert (owner, repo) in tracked, f"Missing GitHub source: {owner}/{repo}"


def test_new_sources_reference_new_topics(config):
    """Each new source must include at least one of the new topic IDs."""
    releases = config.get("sources", {}).get("github_releases", [])
    source_map = {(s["owner"], s["repo"]): s.get("topics", []) for s in releases}
    for owner, repo in NEW_SOURCE_REPOS:
        topics = source_map.get((owner, repo), [])
        overlap = set(topics) & set(NEW_TOPIC_IDS)
        assert overlap, (
            f"{owner}/{repo} source does not reference any new topic "
            f"({NEW_TOPIC_IDS}); got {topics}"
        )


def test_pipeline_dry_run_includes_new_topics(config):
    """Dry-run sample items must include items for the new topics."""
    from pipeline.main import _sample_items

    date = "2026-02-28"
    items = _sample_items(config, date)
    topic_ids_in_items = {tid for item in items for tid in item.get("topics", [])}
    for tid in NEW_TOPIC_IDS:
        assert tid in topic_ids_in_items, (
            f"Dry-run sample items missing topic '{tid}'"
        )
