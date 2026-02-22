"""Ingest module: fetch items from GitHub releases and RSS/Atom feeds."""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
_SESSION_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _github_headers() -> Dict[str, str]:
    headers = _SESSION_HEADERS.copy()
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str, **kwargs) -> Optional[requests.Response]:
    try:
        resp = requests.get(url, timeout=10, **kwargs)
        resp.raise_for_status()
        return resp
    except Exception as exc:  # noqa: BLE001
        logger.warning("GET %s failed: %s", url, exc)
        return None


def fetch_github_releases(owner: str, repo: str, topics: List[str]) -> List[Dict]:
    """Fetch the latest GitHub releases for a repository."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases?per_page=10"
    resp = _get(url, headers=_github_headers())
    if not resp:
        return []
    items = []
    for rel in resp.json():
        items.append({
            "raw_id": str(rel.get("id", "")),
            "title": (rel.get("name") or rel.get("tag_name", "")).strip(),
            "url": rel.get("html_url", ""),
            "published_at": rel.get("published_at") or rel.get("created_at", ""),
            "source": f"{owner}/{repo}",
            "source_type": "github_release",
            "topics": list(topics),
            "snippet": (rel.get("body") or "")[:400],
        })
    return items


def _parse_rss_date(raw: str) -> str:
    """Parse RSS pubDate into ISO 8601; fall back to now on failure."""
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            return datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            continue
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_atom_date(raw: str) -> str:
    """Parse Atom/ISO date into ISO 8601; fall back to now on failure."""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except (ValueError, AttributeError):
        return datetime.now(tz=timezone.utc).isoformat()


def fetch_rss(url: str, name: str, topics: List[str]) -> List[Dict]:
    """Fetch and parse an RSS 2.0 or Atom feed."""
    resp = _get(url)
    if not resp:
        return []
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        logger.warning("RSS parse error for %s: %s", url, exc)
        return []

    items: List[Dict] = []

    # RSS 2.0
    for item in root.findall(".//item"):
        link = (item.findtext("link") or "").strip()
        if not link:
            continue
        desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "")
        items.append({
            "raw_id": link,
            "title": (item.findtext("title") or "").strip(),
            "url": link,
            "published_at": _parse_rss_date((item.findtext("pubDate") or "").strip()),
            "source": name,
            "source_type": "rss",
            "topics": list(topics),
            "snippet": desc[:400].strip(),
        })

    # Atom 1.0
    atom_ns = "http://www.w3.org/2005/Atom"
    for entry in root.findall(f".//{{{atom_ns}}}entry"):
        link_el = entry.find(f"{{{atom_ns}}}link")
        link = (link_el.get("href") if link_el is not None else "").strip()
        if not link:
            continue
        title_el = entry.find(f"{{{atom_ns}}}title")
        pub_el = entry.find(f"{{{atom_ns}}}published") or entry.find(f"{{{atom_ns}}}updated")
        summary_el = entry.find(f"{{{atom_ns}}}summary")
        snippet = re.sub(r"<[^>]+>", "", (summary_el.text if summary_el is not None else ""))[:400]
        items.append({
            "raw_id": link,
            "title": (title_el.text if title_el is not None else "").strip(),
            "url": link,
            "published_at": _parse_atom_date((pub_el.text if pub_el is not None else "").strip()),
            "source": name,
            "source_type": "rss",
            "topics": list(topics),
            "snippet": snippet.strip(),
        })

    return items


def ingest_all(config: Dict) -> List[Dict]:
    """Ingest items from all configured sources."""
    sources = config.get("sources", {})
    items: List[Dict] = []

    for src in sources.get("github_releases", []):
        logger.info("Fetching GitHub releases: %s/%s", src["owner"], src["repo"])
        items.extend(fetch_github_releases(src["owner"], src["repo"], src.get("topics", [])))

    for src in sources.get("rss_feeds", []):
        logger.info("Fetching RSS: %s", src["name"])
        items.extend(fetch_rss(src["url"], src["name"], src.get("topics", [])))

    return items
