"""Read the bounded weekly YouTube discovery artifact as daily learning signals."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..schema import SourceEvent


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def collect_youtube_digest(
    config: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[list[SourceEvent], dict[str, str]]:
    """Load recent transcript-backed videos; discovery itself runs only weekly."""
    if not config or config.get("enabled", True) is False:
        return [], {}

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    path = Path(str(config.get("digest_path", "data/youtube-trends.json")))
    source_key = "youtube:weekly-digest"
    if not path.is_file():
        status = "error:missing" if config.get("required", False) else "ok:0"
        return [], {source_key: status}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValueError("unsupported YouTube digest schema")
        generated_at = _timestamp(str(payload["generated_at"]))
        maximum_digest_age = timedelta(days=int(config.get("max_digest_age_days", 9)))
        if now - generated_at > maximum_digest_age:
            raise ValueError("stale digest")
        videos = payload.get("videos")
        if not isinstance(videos, list):
            raise TypeError("videos must be a list")

        cutoff = now - timedelta(days=int(config.get("max_video_age_days", 14)))
        priority = int(config.get("priority", 16))
        events: list[SourceEvent] = []
        for video in videos:
            if not isinstance(video, dict):
                raise TypeError("video must be an object")
            published_at = _timestamp(str(video["published_at"]))
            if published_at < cutoff:
                continue
            video_id = str(video["video_id"])
            takeaway = str(video.get("takeaway") or "").strip()
            if not takeaway:
                continue
            primary_urls = video.get("primary_urls", [])
            if not isinstance(primary_urls, list) or not all(
                isinstance(url, str) and url.startswith("https://") for url in primary_urls
            ):
                raise ValueError("primary_urls must contain public HTTPS URLs")
            events.append(
                SourceEvent(
                    event_id=f"youtube:{video_id}",
                    source_type="youtube_video",
                    title=f"Weekly watch: {video['title']}",
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    product=str(video.get("channel_title") or "YouTube learning signal"),
                    topic="AI agent development",
                    published_at=published_at.isoformat().replace("+00:00", "Z"),
                    fetched_at=now.isoformat().replace("+00:00", "Z"),
                    evidence=(
                        f"Selected from a bounded weekly sample using age-adjusted views and engagement. "
                        f"Transcript excerpt: {takeaway}"
                    )[:4000],
                    authority="primary",
                    channel="announcement",
                    metadata={
                        "priority": priority,
                        "trend_score": float(video.get("trend_score", 0)),
                        "views_per_day": float(video.get("views_per_day", 0)),
                        "channel_velocity_ratio": float(video.get("channel_velocity_ratio", 0)),
                        "corroboration_urls": primary_urls,
                        "learning_signal": True,
                    },
                ).validate()
            )
        discovery = payload.get("discovery_health")
        if discovery is not None:
            if not isinstance(discovery, dict) or discovery.get("status") not in {"ok", "degraded", "error"}:
                raise ValueError("invalid discovery health")
            if discovery["status"] != "ok":
                return events, {source_key: f"degraded:{len(events)}"}
        # Legacy artifacts may lack counters. Do not call known unusable results healthy no-news.
        if not events and (videos or int(payload.get("candidate_count", 0)) > 0):
            return [], {source_key: "degraded:0"}
        return events, {source_key: f"ok:{len(events)}"}
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return [], {source_key: f"error:{type(exc).__name__}"}
