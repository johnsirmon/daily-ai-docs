"""Tests for the dedupe module."""

from pipeline.dedupe import dedupe


def _repo(name: str, stars: int = 10) -> dict:
    return {"repo": name, "url": f"https://github.com/{name}", "stars": stars, "type": "trending"}


def test_no_duplicates_returns_all():
    items = [_repo("a/x"), _repo("b/y")]
    assert len(dedupe(items)) == 2


def test_duplicate_keeps_higher_stars():
    items = [_repo("a/x", stars=5), _repo("a/x", stars=50)]
    result = dedupe(items)
    assert len(result) == 1
    assert result[0]["stars"] == 50


def test_first_wins_on_equal_stars():
    items = [_repo("a/x", stars=10), _repo("a/x", stars=10)]
    result = dedupe(items)
    assert len(result) == 1


def test_preserves_order():
    items = [_repo("a/x"), _repo("b/y"), _repo("c/z")]
    assert [r["repo"] for r in dedupe(items)] == ["a/x", "b/y", "c/z"]


def test_empty_input():
    assert dedupe([]) == []


def test_items_without_repo_field_all_kept():
    items = [{"url": "https://a.com", "type": "release"}, {"url": "https://b.com", "type": "release"}]
    assert len(dedupe(items)) == 2
