"""Normalize raw ingested items to a common schema."""

import hashlib
import re
from datetime import datetime, timezone
from typing import Dict, List

SCHEMA_VERSION = "1"

# Tracking / referral query params to strip for canonical URLs
_TRACKING_RE = re.compile(
    r"[?&]("
    r"utm_source|utm_medium|utm_campaign|utm_content|utm_term"
    r"|ref|s|src|from"
    r")=[^&]*",
    re.IGNORECASE,
)


def canonical_url(url: str) -> str:
    """Strip common tracking query parameters from a URL."""
    cleaned = _TRACKING_RE.sub("", url)
    return cleaned.rstrip("?&")


def item_id(url: str) -> str:
    """Derive a short stable ID from a canonical URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def normalize(raw: Dict) -> Dict:
    """Map a raw ingested item to the standard pipeline schema."""
    url = canonical_url(raw.get("url", ""))
    published_at = raw.get("published_at", "")
    if not published_at:
        published_at = datetime.now(tz=timezone.utc).isoformat()

    return {
        "id": item_id(url),
        "title": raw.get("title", "").strip(),
        "url": url,
        "published_at": published_at,
        "source": raw.get("source", ""),
        "source_type": raw.get("source_type", ""),
        "topics": list(raw.get("topics", [])),
        "snippet": raw.get("snippet", "").strip(),
        "score": 0.0,
        "why_it_matters": "",
        "action": "",
        "_schema_version": SCHEMA_VERSION,
    }


def normalize_all(raw_items: List[Dict]) -> List[Dict]:
    """Normalize a list of raw items."""
    return [normalize(item) for item in raw_items]
