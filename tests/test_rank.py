"""Tests for the ranking module."""

from datetime import datetime, timezone

import pytest

from pipeline.rank import (
    DEFAULT_SOURCE_QUALITY,
    rank,
    recency_score,
    score_item,
    source_quality_score,
    topic_relevance_score,
)

NOW = datetime(2026, 1, 10, 0, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# recency_score
# ---------------------------------------------------------------------------

def test_recency_score_fresh():
    score = recency_score("2026-01-10T00:00:00+00:00", now=NOW)
    assert score == pytest.approx(1.0)


def test_recency_score_half_life():
    """Item published exactly one half-life ago should score ≈ 0.5."""
    score = recency_score("2026-01-07T00:00:00+00:00", half_life_days=3.0, now=NOW)
    assert score == pytest.approx(0.5, abs=0.01)


def test_recency_score_old():
    score = recency_score("2025-12-01T00:00:00+00:00", half_life_days=3.0, now=NOW)
    assert score < 0.01


def test_recency_score_future_clamps_to_one():
    """Items with a future timestamp should not produce a score > 1."""
    score = recency_score("2026-01-11T00:00:00+00:00", now=NOW)
    assert score == pytest.approx(1.0, abs=0.01)


def test_recency_score_bad_date_returns_fallback():
    score = recency_score("not-a-date", now=NOW)
    assert score == 0.5


# ---------------------------------------------------------------------------
# source_quality_score
# ---------------------------------------------------------------------------

def test_source_quality_known_types():
    assert source_quality_score("github_release") == pytest.approx(0.90)
    assert source_quality_score("reddit") == pytest.approx(0.50)


def test_source_quality_unknown_type():
    assert source_quality_score("mystery_source") == pytest.approx(0.5)


def test_source_quality_custom_map():
    custom = {"special": 0.99}
    assert source_quality_score("special", quality_map=custom) == pytest.approx(0.99)


# ---------------------------------------------------------------------------
# topic_relevance_score
# ---------------------------------------------------------------------------

def test_topic_relevance_no_all_topics():
    assert topic_relevance_score(["a"], []) == pytest.approx(0.5)


def test_topic_relevance_no_item_topics():
    assert topic_relevance_score([], ["a", "b"]) == pytest.approx(0.0)


def test_topic_relevance_partial():
    all_t = ["a", "b", "c", "d"]
    assert topic_relevance_score(["a"], all_t) == pytest.approx(0.25)
    assert topic_relevance_score(["a", "b"], all_t) == pytest.approx(0.50)


def test_topic_relevance_clamps_at_one():
    all_t = ["a", "b"]
    assert topic_relevance_score(["a", "b", "c", "d"], all_t) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# rank
# ---------------------------------------------------------------------------

def _make_item(id_: str, published_at: str, source_type: str, topics: list) -> dict:
    return {
        "id": id_,
        "title": f"Item {id_}",
        "url": f"https://example.com/{id_}",
        "published_at": published_at,
        "source": "test",
        "source_type": source_type,
        "topics": topics,
        "snippet": "",
        "score": 0.0,
        "why_it_matters": "",
        "action": "",
    }


_BASE_CONFIG = {
    "topics": [{"id": "mcp"}, {"id": "vscode-insiders"}],
    "ranking": {
        "weights": {"recency": 0.4, "source_quality": 0.4, "topic_relevance": 0.2},
        "recency_half_life_days": 3,
    },
    "source_quality": {"github_release": 0.9, "reddit": 0.5, "rss": 0.75},
}


def test_rank_fresh_beats_old():
    items = [
        _make_item("old", "2026-01-01T00:00:00+00:00", "reddit", []),
        _make_item("new", "2026-01-10T00:00:00+00:00", "github_release", ["mcp"]),
    ]
    ranked = rank(items, _BASE_CONFIG, now=NOW)
    assert ranked[0]["id"] == "new"
    assert ranked[0]["score"] > ranked[1]["score"]


def test_rank_scores_assigned():
    items = [_make_item("x", "2026-01-09T00:00:00+00:00", "rss", ["mcp"])]
    ranked = rank(items, _BASE_CONFIG, now=NOW)
    assert ranked[0]["score"] > 0


def test_rank_deterministic():
    """Identical inputs must always produce identical output order."""
    items = [
        _make_item(str(i), "2026-01-09T00:00:00+00:00", "rss", ["mcp"])
        for i in range(5)
    ]
    r1 = rank(list(items), _BASE_CONFIG, now=NOW)
    r2 = rank(list(items), _BASE_CONFIG, now=NOW)
    assert [i["id"] for i in r1] == [i["id"] for i in r2]


def test_rank_empty_input():
    assert rank([], _BASE_CONFIG, now=NOW) == []
