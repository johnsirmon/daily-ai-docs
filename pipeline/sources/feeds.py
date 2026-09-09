"""Collect items from explicitly curated official RSS/Atom feeds."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, List

import requests

from ..schema import SourceEvent


def _first_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(node):
        local = child.tag.rsplit("}", 1)[-1]
        if local in names and child.text:
            return child.text.strip()
    return ""


def _entry_url(node: ET.Element) -> str:
    for child in list(node):
        if child.tag.rsplit("}", 1)[-1] == "link":
            href = child.get("href")
            if href:
                return href
            if child.text:
                return child.text.strip()
    return ""


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def collect_official_feeds(
    sources: Iterable[Dict],
    *,
    lookback_hours: int = 36,
    session: requests.Session | None = None,
    now: datetime | None = None,
) -> tuple[List[SourceEvent], Dict[str, str]]:
    session = session or requests.Session()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=lookback_hours)
    fetched = now.isoformat().replace("+00:00", "Z")
    events: List[SourceEvent] = []
    health: Dict[str, str] = {}

    for config in sources:
        url = str(config["url"])
        key = f"feed:{url}"
        try:
            response = session.get(url, timeout=20, headers={"User-Agent": "daily-ai-docs/1.0"})
            response.raise_for_status()
            root = ET.fromstring(response.content)
            root_name = root.tag.rsplit("}", 1)[-1].lower()
            if root_name not in {"rss", "feed"}:
                raise ValueError("official feed response is not RSS or Atom")
            nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] in {"item", "entry"}]
            if not nodes:
                raise ValueError("official feed contains no entries")
            accepted = 0
            include = [term.lower() for term in config.get("include", [])]
            for node in nodes:
                title = _first_text(node, ("title",))
                item_url = _entry_url(node) or _first_text(node, ("link", "id", "guid"))
                date_text = _first_text(node, ("published", "updated", "pubDate", "date"))
                summary = _first_text(node, ("summary", "description", "content"))
                haystack = f"{title} {summary}".lower()
                if include and not any(term in haystack for term in include):
                    continue
                if not title or not item_url.startswith("https://") or not date_text:
                    continue
                published = _parse_time(date_text)
                if published < cutoff:
                    continue
                clean = re.sub(r"<[^>]+>", " ", summary)
                clean = " ".join(clean.split())[:900] or f"Official announcement: {title}."
                digest = hashlib.sha256(item_url.encode("utf-8")).hexdigest()[:20]
                events.append(SourceEvent(
                    event_id=f"feed:{digest}",
                    source_type="official_feed",
                    title=title,
                    url=item_url,
                    product=str(config.get("product") or title),
                    topic=str(config.get("topic") or "AI developer tools"),
                    published_at=published.isoformat().replace("+00:00", "Z"),
                    fetched_at=fetched,
                    evidence=clean,
                    authority="primary",
                    channel="announcement",
                    metadata={"priority": int(config.get("priority", 10)), "feed_url": url},
                ).validate())
                accepted += 1
            health[key] = f"ok:{accepted}"
        except Exception as exc:
            health[key] = f"error:{type(exc).__name__}"
    return events, health
