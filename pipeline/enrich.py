"""Enrich trending repo items with additional GitHub stats.

Fetches forks, open issues, commit velocity, contributor count, and merged PRs
for the top-N repos in a topic. Results are cached per repo+date to avoid
re-fetching on pipeline restarts and to survive GitHub's 202 warmup responses
on the stats endpoints.
"""

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

from .github_api import GITHUB_API, build_github_headers

logger = logging.getLogger(__name__)
_CACHE_DIR = Path(".cache/enrich")
_MAX_CONCURRENT = 3  # stay within GitHub secondary rate limits


def _headers() -> Dict[str, str]:
    return build_github_headers()


def _cache_path(repo: str, today: str) -> Path:
    slug = repo.replace("/", "__")
    return _CACHE_DIR / f"{slug}__{today}.json"


def _load_cache(repo: str, today: str) -> Optional[Dict]:
    path = _cache_path(repo, today)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return None


def _save_cache(repo: str, today: str, data: Dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(repo, today).write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )


def _get_json(url: str, retries: int = 2) -> Optional[Dict | List]:
    """GET a GitHub API URL, retrying once on 202 (stats computing)."""
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=_headers(), timeout=10)
            if resp.status_code == 202:
                if attempt < retries:
                    time.sleep(2)
                    continue
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("GET %s failed (attempt %d): %s", url, attempt + 1, exc)
    return None


def _commit_trend(weekly_commits: List[int]) -> str:
    """Classify trend from last 4 weekly commit counts."""
    if len(weekly_commits) < 2:
        return "flat"
    half = len(weekly_commits) // 2
    recent = sum(weekly_commits[half:])
    older = sum(weekly_commits[:half])
    if recent > older * 1.25:
        return "rising"
    if recent < older * 0.75:
        return "falling"
    return "flat"


def _enrich_one(repo: str, today: str) -> Dict:
    """Fetch and return enrichment dict for a single repo."""
    cached = _load_cache(repo, today)
    if cached is not None:
        return cached

    owner, name = repo.split("/", 1)
    result: Dict = {}

    # Basic repo metadata (already partly in search payload, but get fresh copy)
    meta = _get_json(f"{GITHUB_API}/repos/{owner}/{name}")
    if meta and isinstance(meta, dict):
        result["forks"] = meta.get("forks_count", 0)
        result["open_issues"] = meta.get("open_issues_count", 0)
        result["watchers"] = meta.get("watchers_count", 0)
        result["language"] = meta.get("language") or ""
        result["topics"] = meta.get("topics") or []
        result["created_at"] = (meta.get("created_at") or "")[:10]
        result["homepage"] = meta.get("homepage") or ""
        license_info = meta.get("license") or {}
        result["license"] = license_info.get("spdx_id") or ""

    # Weekly commit activity (last 4 weeks)
    activity = _get_json(f"{GITHUB_API}/repos/{owner}/{name}/stats/commit_activity")
    weekly_commits: List[int] = []
    if activity and isinstance(activity, list):
        weekly_commits = [w.get("total", 0) for w in activity[-4:]]
    result["weekly_commits"] = weekly_commits
    result["commit_trend"] = _commit_trend(weekly_commits)

    # Contributor count (capped at 100)
    all_contributors = _get_json(
        f"{GITHUB_API}/repos/{owner}/{name}/contributors?per_page=100&anon=false"
    )
    result["contributor_count"] = (
        len(all_contributors) if isinstance(all_contributors, list) else 0
    )

    # Merged PRs in last 14 days
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=14)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    prs = _get_json(
        f"{GITHUB_API}/repos/{owner}/{name}/pulls"
        f"?state=closed&sort=updated&direction=desc&per_page=30"
    )
    prs_merged = 0
    if prs and isinstance(prs, list):
        for pr in prs:
            merged_at = pr.get("merged_at")
            if merged_at and merged_at >= cutoff:
                prs_merged += 1
    result["prs_merged_14d"] = prs_merged

    _save_cache(repo, today, result)
    return result


def enrich_items(items: List[Dict], top_n: int = 4, today: Optional[str] = None) -> List[Dict]:
    """Enrich the top_n trending items with GitHub stats.

    Mutates items in place (adds enrichment fields) and returns the list.
    Processes up to _MAX_CONCURRENT repos before sleeping briefly to respect
    GitHub secondary rate limits.
    """
    if today is None:
        today = date.today().isoformat()

    trending = [it for it in items if it.get("type") == "trending"][:top_n]

    for i, item in enumerate(trending):
        repo = item.get("repo", "")
        if not repo:
            continue
        stats = _enrich_one(repo, today)
        item.update(stats)
        # Pace requests: brief pause every _MAX_CONCURRENT calls
        if (i + 1) % _MAX_CONCURRENT == 0:
            time.sleep(1)

    return items
