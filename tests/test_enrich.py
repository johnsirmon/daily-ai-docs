"""Tests for pipeline/enrich.py."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from pipeline.enrich import _commit_trend, enrich_items, _enrich_one


# ---------------------------------------------------------------------------
# _commit_trend
# ---------------------------------------------------------------------------

def test_commit_trend_rising():
    assert _commit_trend([5, 5, 15, 20]) == "rising"


def test_commit_trend_falling():
    assert _commit_trend([20, 15, 5, 4]) == "falling"


def test_commit_trend_flat():
    assert _commit_trend([10, 10, 11, 10]) == "flat"


def test_commit_trend_short_list():
    # Single value → flat
    assert _commit_trend([10]) == "flat"


def test_commit_trend_empty():
    assert _commit_trend([]) == "flat"


# ---------------------------------------------------------------------------
# _enrich_one — mocked HTTP
# ---------------------------------------------------------------------------

def _make_meta_resp():
    return {
        "forks_count": 55,
        "open_issues_count": 12,
        "watchers_count": 300,
        "language": "Python",
        "topics": ["ai", "llm"],
        "created_at": "2023-06-01T00:00:00Z",
        "homepage": "https://example.com",
        "license": {"spdx_id": "MIT"},
    }


def _make_activity_resp():
    return [{"total": t} for t in [5, 8, 12, 18]]  # rising


def _make_contributors_resp(n=20):
    return [{"login": f"user{i}"} for i in range(n)]


def _make_prs_resp():
    from datetime import datetime, timedelta, timezone
    recent = (datetime.now(tz=timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = "2020-01-01T00:00:00Z"
    return [
        {"merged_at": recent},
        {"merged_at": recent},
        {"merged_at": old},
        {"merged_at": None},  # not merged
    ]


@patch("pipeline.enrich.requests.get")
def test_enrich_one_merges_fields(mock_get, tmp_path):
    """enrich_items populates all expected fields on the item."""
    responses = [
        _make_meta_resp(),
        _make_activity_resp(),
        _make_contributors_resp(),  # page-1 probe
        _make_contributors_resp(),  # full page
        _make_prs_resp(),
    ]

    def side_effect(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = responses.pop(0)
        resp.raise_for_status = MagicMock()
        return resp

    mock_get.side_effect = side_effect

    with patch("pipeline.enrich._CACHE_DIR", tmp_path / "cache"):
        item = {"repo": "org/myrepo", "stars": 100, "type": "trending"}
        enrich_items([item], top_n=1)

    assert item["forks"] == 55
    assert item["open_issues"] == 12
    assert item["language"] == "Python"
    assert item["topics"] == ["ai", "llm"]
    assert item["commit_trend"] == "rising"
    assert item["contributor_count"] == 20
    assert item["prs_merged_14d"] == 2


@patch("pipeline.enrich.requests.get")
def test_enrich_one_handles_202_gracefully(mock_get, tmp_path):
    """Stats endpoints returning 202 fall back to empty weekly_commits."""
    call_count = 0

    def side_effect(url, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        # meta → 200, activity → 202 both retries, rest → 200 empty
        if "commit_activity" in url:
            resp.status_code = 202
        else:
            resp.status_code = 200
            resp.json.return_value = {} if "repos/org" in url and call_count == 1 else []
        resp.raise_for_status = MagicMock()
        return resp

    mock_get.side_effect = side_effect

    with patch("pipeline.enrich._CACHE_DIR", tmp_path / "cache"):
        item = {"repo": "org/repo2", "stars": 50, "type": "trending"}
        enrich_items([item], top_n=1)

    assert item.get("weekly_commits") == []
    assert item.get("commit_trend") == "flat"


@patch("pipeline.enrich.requests.get")
def test_enrich_cache_hit_skips_api(mock_get, tmp_path):
    """A cached result is returned without any HTTP calls."""
    cached_data = {"forks": 9, "language": "Go", "commit_trend": "flat",
                   "weekly_commits": [], "open_issues": 1, "watchers": 10,
                   "topics": [], "created_at": "2022-01-01", "homepage": "",
                   "license": "", "contributor_count": 5, "prs_merged_14d": 0}

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    today = "2026-03-01"
    cache_file = cache_dir / "org__cached__2026-03-01.json"
    cache_file.write_text(json.dumps(cached_data), encoding="utf-8")

    with patch("pipeline.enrich._CACHE_DIR", cache_dir):
        item = {"repo": "org/cached", "stars": 20, "type": "trending"}
        enrich_items([item], top_n=1, today=today)

    mock_get.assert_not_called()
    assert item["forks"] == 9
    assert item["language"] == "Go"


@patch("pipeline.enrich.requests.get")
def test_enrich_graceful_on_error(mock_get, tmp_path):
    """Enrich does not raise on network error; item keeps original fields."""
    mock_get.side_effect = Exception("network down")

    with patch("pipeline.enrich._CACHE_DIR", tmp_path / "cache"):
        item = {"repo": "org/broken", "stars": 5, "type": "trending"}
        enrich_items([item], top_n=1)

    # Should not raise; original fields preserved
    assert item["stars"] == 5


def test_enrich_items_only_enriches_top_n(tmp_path):
    """Only the first top_n trending items are enriched."""
    items = [
        {"repo": f"org/repo{i}", "stars": 100 - i, "type": "trending"}
        for i in range(5)
    ]
    with patch("pipeline.enrich._enrich_one", return_value={}) as mock_enrich:
        with patch("pipeline.enrich._CACHE_DIR", tmp_path / "cache"):
            enrich_items(items, top_n=2)
    assert mock_enrich.call_count == 2


def test_enrich_items_skips_release_type():
    """Release items are never enriched."""
    items = [{"repo": "org/rel", "type": "release", "version": "v1"}]
    with patch("pipeline.enrich._enrich_one", return_value={}) as mock_enrich:
        enrich_items(items, top_n=4)
    mock_enrich.assert_not_called()
