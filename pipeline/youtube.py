"""Weekly, quota-bounded YouTube discovery for AI-agent learning signals."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml
from youtube_transcript_api import YouTubeTranscriptApi, YouTubeTranscriptApiException

_API = "https://www.googleapis.com/youtube/v3"
_URL_RE = re.compile(r"https://[^\s<>\])}]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_USEFUL_TERMS = {
    "agent", "benchmark", "coding", "context", "debug", "deploy", "evaluation",
    "framework", "implementation", "memory", "model", "prompt", "release", "security",
    "skill", "test", "tool", "trace", "workflow",
}


def _iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _chunks(values: list[str], size: int = 50) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _get_json(session: requests.Session, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    response = session.get(f"{_API}/{endpoint}", params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("YouTube API response must be an object")
    return payload


def _extract_primary_urls(description: str, allowed_domains: Iterable[str]) -> list[str]:
    domains = {domain.lower().strip(".") for domain in allowed_domains if domain}
    urls: list[str] = []
    for candidate in _URL_RE.findall(description):
        candidate = candidate.rstrip(".,;:!?\"'")
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower()
        if not host or not any(host == domain or host.endswith(f".{domain}") for domain in domains):
            continue
        if candidate not in urls:
            urls.append(candidate)
    return urls[:5]


def _default_transcript(video_id: str) -> str:
    transcript = YouTubeTranscriptApi().fetch(video_id, languages=("en",))
    return " ".join(snippet.text for snippet in transcript if snippet.text).strip()


def _takeaway(transcript: str, title: str, limit: int = 700) -> str:
    clean = " ".join(transcript.replace("\n", " ").split())
    if not clean:
        return ""
    title_terms = {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9-]+", title) if len(word) > 3}
    scored = []
    for index, sentence in enumerate(_SENTENCE_RE.split(clean)):
        sentence = sentence.strip()
        if not 35 <= len(sentence) <= 320:
            continue
        words = {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9-]+", sentence)}
        score = 2 * len(words & _USEFUL_TERMS) + len(words & title_terms)
        scored.append((score, -index, sentence))
    selected = sorted(scored, reverse=True)[:3]
    selected.sort(key=lambda row: -row[1])
    result = " ".join(row[2] for row in selected) or clean[:limit]
    return result[:limit].rstrip()


def discover_videos(
    config: dict[str, Any],
    *,
    api_key: str,
    now: datetime | None = None,
    session: Any = None,
    transcript_fetcher: Callable[[str], str] = _default_transcript,
) -> dict[str, Any]:
    """Discover and rank recent videos without treating raw lifetime views as trend."""
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is required")
    queries = config.get("queries")
    if not isinstance(queries, list) or not queries or not all(isinstance(q, str) and q.strip() for q in queries):
        raise ValueError("youtube queries must be a non-empty string list")
    if len(queries) > 6:
        raise ValueError("youtube discovery is capped at six quota-heavy searches")

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    session = session or requests.Session()
    lookback_days = int(config.get("lookback_days", 8))
    published_after = (now - timedelta(days=lookback_days)).isoformat().replace("+00:00", "Z")
    per_query = min(25, max(1, int(config.get("max_results_per_query", 12))))

    discovered: dict[str, dict[str, Any]] = {}
    for query in queries:
        payload = _get_json(session, "search", {
            "part": "snippet",
            "type": "video",
            "order": "viewCount",
            "publishedAfter": published_after,
            "maxResults": per_query,
            "q": query,
            "relevanceLanguage": "en",
            "safeSearch": "moderate",
            "key": api_key,
        })
        for item in payload.get("items", []):
            video_id = item.get("id", {}).get("videoId") if isinstance(item, dict) else None
            if video_id:
                discovered.setdefault(str(video_id), {"matched_queries": []})["matched_queries"].append(query)

    ids = list(discovered)
    details: list[dict[str, Any]] = []
    for group in _chunks(ids):
        payload = _get_json(session, "videos", {
            "part": "snippet,statistics",
            "id": ",".join(group),
            "maxResults": len(group),
            "key": api_key,
        })
        details.extend(item for item in payload.get("items", []) if isinstance(item, dict))

    candidates: list[dict[str, Any]] = []
    for item in details:
        video_id = str(item.get("id") or "")
        snippet = item.get("snippet") or {}
        statistics_data = item.get("statistics") or {}
        if video_id not in discovered or not snippet.get("publishedAt"):
            continue
        published = _iso(str(snippet["publishedAt"]))
        age_days = max((now - published).total_seconds() / 86400, 0.25)
        views = int(statistics_data.get("viewCount") or 0)
        likes = int(statistics_data.get("likeCount") or 0)
        candidates.append({
            "video_id": video_id,
            "title": str(snippet.get("title") or "Untitled video"),
            "channel_id": str(snippet.get("channelId") or ""),
            "channel_title": str(snippet.get("channelTitle") or "Unknown channel"),
            "published_at": published.isoformat().replace("+00:00", "Z"),
            "description": str(snippet.get("description") or "")[:4000],
            "view_count": views,
            "like_count": likes,
            "views_per_day": round(views / age_days, 2),
            "matched_queries": discovered[video_id]["matched_queries"],
        })

    by_channel: dict[str, list[float]] = {}
    for candidate in candidates:
        by_channel.setdefault(candidate["channel_id"], []).append(candidate["views_per_day"])
    global_baseline = statistics.median([row["views_per_day"] for row in candidates]) if candidates else 1.0
    for candidate in candidates:
        own_values = by_channel[candidate["channel_id"]]
        baseline = statistics.median(own_values) if len(own_values) > 1 else global_baseline
        ratio = candidate["views_per_day"] / max(baseline, 1.0)
        like_rate = candidate["like_count"] / max(candidate["view_count"], 1)
        velocity_component = 45 * min(ratio, 2.0) / 2.0
        scale_component = 35 * min(1.0, math.log1p(candidate["views_per_day"]) / math.log1p(100_000))
        engagement_component = 20 * min(1.0, like_rate / 0.05)
        candidate["channel_velocity_ratio"] = round(ratio, 3)
        candidate["trend_score"] = round(velocity_component + scale_component + engagement_component, 2)

    candidates.sort(key=lambda row: (row["trend_score"], row["views_per_day"]), reverse=True)
    maximum = min(10, max(1, int(config.get("max_selected", 5))))
    allowed_domains = config.get("primary_domains", [])
    require_transcript = bool(config.get("require_transcript", True))
    selected = []
    for candidate in candidates:
        try:
            transcript = transcript_fetcher(candidate["video_id"])
        except (YouTubeTranscriptApiException, requests.RequestException):
            transcript = ""
        takeaway = _takeaway(transcript, candidate["title"])
        if require_transcript and not takeaway:
            continue
        candidate["takeaway"] = takeaway
        candidate["transcript_chars"] = len(transcript)
        candidate["primary_urls"] = _extract_primary_urls(candidate.pop("description"), allowed_domains)
        selected.append(candidate)
        if len(selected) == maximum:
            break

    return {
        "schema_version": 1,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "lookback_days": lookback_days,
        "query_count": len(queries),
        "candidate_count": len(candidates),
        "videos": selected,
    }


def write_digest(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="topics/topics.yaml")
    parser.add_argument("--output")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    youtube = config.get("daily", {}).get("sources", {}).get("youtube", {})
    if not youtube:
        raise SystemExit("daily.sources.youtube is not configured")
    output = Path(args.output or youtube.get("digest_path", "data/youtube-trends.json"))
    payload = discover_videos(youtube, api_key=os.environ.get("YOUTUBE_API_KEY", ""))
    write_digest(payload, output)
    print(f"Wrote {len(payload['videos'])} transcript-backed videos to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
