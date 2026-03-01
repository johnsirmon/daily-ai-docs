"""Fetch recent releases from pinned repos."""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"


def _headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_releases(owner_repo: str, lookback_days: int = 14) -> List[Dict]:
    """Fetch releases from a pinned repo published within lookback_days.

    Returns a list of release dicts.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)
    owner, repo = owner_repo.split("/", 1)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases?per_page=10"
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        results = []
        for rel in resp.json():
            pub = rel.get("published_at") or rel.get("created_at", "")
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if dt < cutoff:
                    continue
            except (ValueError, AttributeError):
                continue  # skip releases with unparseable dates
            results.append({
                "repo": owner_repo,
                "url": rel.get("html_url", ""),
                "version": rel.get("tag_name", ""),
                "name": (rel.get("name") or rel.get("tag_name", "")).strip(),
                "published_at": pub[:10] if pub else "",
                "notes": (rel.get("body") or "")[:3000].strip(),
                "reactions": (rel.get("reactions") or {}).get("total_count", 0),
                "type": "release",
            })
        return results
    except Exception as exc:  # noqa: BLE001
        logger.warning("Releases failed for %s: %s", owner_repo, exc)
        return []
