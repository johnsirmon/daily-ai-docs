"""Search GitHub for new/rising repos matching topic keywords."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import requests

from .github_api import GITHUB_API, build_github_headers

logger = logging.getLogger(__name__)


def _headers() -> Dict[str, str]:
    return build_github_headers()


def search_repos(
    keywords: List[str],
    lookback_days: int = 14,
    min_stars: int = 10,
    top_n: int = 5,
) -> List[Dict]:
    """Search GitHub for repos matching keywords pushed in the last lookback_days.

    Returns a deduplicated list sorted by stars descending.
    """
    since = (
        datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)
    ).strftime("%Y-%m-%d")

    raw: List[Dict] = []
    for kw in keywords[:3]:  # cap to avoid rate limits
        query = f"{kw} pushed:>{since} stars:>={min_stars}"
        url = (
            f"{GITHUB_API}/search/repositories"
            f"?q={requests.utils.quote(query)}&sort=updated&order=desc&per_page=10"
        )
        try:
            resp = requests.get(url, headers=_headers(), timeout=10)
            resp.raise_for_status()
            for item in resp.json().get("items", []):
                raw.append({
                    "repo": item["full_name"],
                    "url": item["html_url"],
                    "stars": item["stargazers_count"],
                    "description": (item.get("description") or "").strip(),
                    "pushed_at": item.get("pushed_at", ""),
                    "language": item.get("language") or "",
                    "forks": item.get("forks_count", 0),
                    "open_issues": item.get("open_issues_count", 0),
                    "topics": item.get("topics") or [],
                    "type": "trending",
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Search failed for %r: %s", kw, exc)

    # Dedupe by repo name, keep highest-starred entry
    seen: Dict[str, Dict] = {}
    for r in raw:
        name = r["repo"]
        if name not in seen or r["stars"] > seen[name]["stars"]:
            seen[name] = r

    return sorted(seen.values(), key=lambda x: x["stars"], reverse=True)[:top_n]
