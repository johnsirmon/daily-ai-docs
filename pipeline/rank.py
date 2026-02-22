"""Rank normalized items by recency, source quality, and topic relevance."""

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional

DEFAULT_SOURCE_QUALITY: Dict[str, float] = {
    "github_release": 0.90,
    "github_issue": 0.60,
    "github_commit": 0.55,
    "rss_official": 0.85,
    "rss": 0.75,
    "reddit": 0.50,
}

DEFAULT_WEIGHTS: Dict[str, float] = {
    "recency": 0.40,
    "source_quality": 0.40,
    "topic_relevance": 0.20,
}


def recency_score(
    published_at: str,
    half_life_days: float = 3.0,
    now: Optional[datetime] = None,
) -> float:
    """Exponential decay score based on item age.

    Returns 1.0 for a brand-new item, approaching 0 for very old items.
    Exactly one half-life old → 0.5.
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return 0.5

    age_days = max((now - dt).total_seconds() / 86400, 0)
    return math.exp(-age_days * math.log(2) / half_life_days)


def source_quality_score(
    source_type: str,
    quality_map: Optional[Dict[str, float]] = None,
) -> float:
    """Return the configured quality weight for a source type."""
    qmap = quality_map if quality_map is not None else DEFAULT_SOURCE_QUALITY
    return qmap.get(source_type, 0.5)


def topic_relevance_score(topics: List[str], all_topics: List[str]) -> float:
    """Score based on number of matching topics (more = higher relevance).

    Returns a value in [0, 1].
    """
    if not all_topics:
        return 0.5
    if not topics:
        return 0.0
    return min(len(topics) / len(all_topics), 1.0)


def score_item(
    item: Dict,
    all_topics: List[str],
    weights: Optional[Dict[str, float]] = None,
    quality_map: Optional[Dict[str, float]] = None,
    half_life_days: float = 3.0,
    now: Optional[datetime] = None,
) -> float:
    """Compute a composite score for a single item."""
    w = weights if weights is not None else DEFAULT_WEIGHTS
    r = recency_score(item.get("published_at", ""), half_life_days=half_life_days, now=now)
    q = source_quality_score(item.get("source_type", ""), quality_map)
    t = topic_relevance_score(item.get("topics", []), all_topics)
    return r * w.get("recency", 0.4) + q * w.get("source_quality", 0.4) + t * w.get("topic_relevance", 0.2)


def rank(
    items: List[Dict],
    config: Dict,
    now: Optional[datetime] = None,
) -> List[Dict]:
    """Score every item and return them sorted by score descending."""
    ranking_cfg = config.get("ranking", {})
    weights = ranking_cfg.get("weights", DEFAULT_WEIGHTS)
    quality_map = config.get("source_quality", DEFAULT_SOURCE_QUALITY)
    half_life = float(ranking_cfg.get("recency_half_life_days", 3.0))
    all_topics = [t["id"] for t in config.get("topics", [])]

    for item in items:
        item["score"] = round(
            score_item(
                item,
                all_topics,
                weights=weights,
                quality_map=quality_map,
                half_life_days=half_life,
                now=now,
            ),
            4,
        )

    return sorted(items, key=lambda x: x["score"], reverse=True)
