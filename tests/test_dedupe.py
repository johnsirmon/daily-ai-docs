"""Tests for the deduplication module."""

import pytest

from pipeline.dedupe import dedupe


def _item(id_: str, title: str, url: str, score: float = 0.5) -> dict:
    return {
        "id": id_,
        "title": title,
        "url": url,
        "score": score,
        "published_at": "2026-01-01T00:00:00+00:00",
        "source": "test",
        "source_type": "rss",
        "topics": [],
        "snippet": "",
        "why_it_matters": "",
        "action": "",
    }


def test_no_duplicates_returns_all():
    items = [_item("a", "Alpha", "https://a.com"), _item("b", "Beta", "https://b.com")]
    assert len(dedupe(items)) == 2


def test_url_duplicate_keeps_higher_score():
    url = "https://example.com/post"
    items = [
        _item("low", "Post", url, score=0.3),
        _item("high", "Post (copy)", url, score=0.8),
    ]
    result = dedupe(items)
    assert len(result) == 1
    assert result[0]["id"] == "high"


def test_title_duplicate_keeps_higher_score():
    items = [
        _item("low", "Same Title", "https://a.com", score=0.4),
        _item("high", "Same Title", "https://b.com", score=0.9),
    ]
    result = dedupe(items)
    assert len(result) == 1
    assert result[0]["id"] == "high"


def test_title_dedupe_case_insensitive():
    items = [
        _item("a", "AI Update", "https://a.com"),
        _item("b", "ai update", "https://b.com"),
    ]
    result = dedupe(items)
    assert len(result) == 1


def test_url_duplicate_first_wins_when_scores_equal():
    url = "https://example.com/same"
    items = [_item("first", "Item", url, score=0.5), _item("second", "Item 2", url, score=0.5)]
    result = dedupe(items)
    assert len(result) == 1
    # First item stays when scores are tied
    assert result[0]["id"] == "first"


def test_empty_input():
    assert dedupe([]) == []


def test_single_item():
    items = [_item("a", "Alpha", "https://a.com")]
    assert dedupe(items) == items


def test_preserves_order_of_unique_items():
    items = [
        _item("a", "Alpha", "https://a.com"),
        _item("b", "Beta", "https://b.com"),
        _item("c", "Gamma", "https://c.com"),
    ]
    result = dedupe(items)
    assert [i["id"] for i in result] == ["a", "b", "c"]


def test_items_with_empty_url_not_url_deduped():
    """Items with empty URLs should still be deduped by title if titles match."""
    items = [
        _item("a", "Same", "", score=0.3),
        _item("b", "Same", "", score=0.8),
    ]
    result = dedupe(items)
    assert len(result) == 1
    assert result[0]["id"] == "b"
