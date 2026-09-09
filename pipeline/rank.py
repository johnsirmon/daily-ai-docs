"""Deterministic novelty, relevance, and noise scoring for source events."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Iterable, List, Sequence, Tuple

from .schema import SourceEvent, Story

_HIGH_IMPACT = re.compile(
    r"\b(security|vulnerab|breaking|deprecated|deprecat|retir|removed|migration|"
    r"major|general availability|\bga\b|pricing|rate limit|model|agent)\b",
    re.IGNORECASE,
)
_NOISE = re.compile(
    r"\b(chore|dependency bump|bump dependencies|signed docker images|typo|"
    r"readme|documentation|docs-only|release candidate|\brc\d*\b|dev build|nightly)\b",
    re.IGNORECASE,
)


def score_event(event: SourceEvent, seen_event_ids: Iterable[str] = ()) -> Dict[str, float]:
    """Return transparent component scores; total is higher-is-better."""
    event.validate()
    seen = set(seen_event_ids)
    # Score relative to the recorded fetch time so replaying a manifest is deterministic.
    now = datetime.fromisoformat(event.fetched_at.replace("Z", "+00:00"))
    published = datetime.fromisoformat(event.published_at.replace("Z", "+00:00"))
    age_hours = max(0.0, (now - published).total_seconds() / 3600)

    authority = 25.0 if event.authority == "primary" else 8.0
    relevance = float(max(0, min(20, int(event.metadata.get("priority", 10)))))
    novelty = 0.0 if event.event_id in seen else 25.0
    recency = max(0.0, 20.0 - age_hours / 3.0)
    text = f"{event.title} {event.evidence}"
    impact = 15.0 if _HIGH_IMPACT.search(text) else 6.0
    penalty = 0.0
    if event.channel == "prerelease":
        penalty += 12.0
    if _NOISE.search(text):
        penalty += 18.0
    velocity = float(event.metadata.get("star_velocity", 0) or 0)
    youtube_trend = float(event.metadata.get("trend_score", 0) or 0)
    momentum = min(10.0, max(0.0, velocity / 10.0, youtube_trend / 10.0))
    total = authority + relevance + novelty + recency + impact + momentum - penalty
    return {
        "authority": round(authority, 2),
        "relevance": round(relevance, 2),
        "novelty": round(novelty, 2),
        "recency": round(recency, 2),
        "impact": round(impact, 2),
        "momentum": round(momentum, 2),
        "noise_penalty": round(penalty, 2),
        "total": round(total, 2),
    }


def _identity(event: SourceEvent) -> Tuple[str, str]:
    version = str(event.metadata.get("version") or event.metadata.get("canonical_event") or event.title)
    version = re.sub(r"\s+", " ", version.strip().lower())
    return event.product.strip().lower(), version


def dedupe_events(events: Sequence[SourceEvent]) -> List[SourceEvent]:
    """Dedupe event-level coverage while preserving distinct product versions."""
    chosen: Dict[Tuple[str, str], SourceEvent] = {}
    for event in events:
        event.validate()
        key = _identity(event)
        current = chosen.get(key)
        if current is None:
            chosen[key] = event
            continue
        if current.authority != "primary" and event.authority == "primary":
            chosen[key] = event
            continue
        if event.published_at > current.published_at:
            chosen[key] = event
    return list(chosen.values())


def is_noise(event: SourceEvent) -> bool:
    return bool(_NOISE.search(f"{event.title} {event.evidence}"))


def select_events(
    events: Sequence[SourceEvent],
    seen_event_ids: Iterable[str] = (),
    *,
    limit: int = 7,
    minimum_score: float = 45.0,
    max_per_source_type: Dict[str, int] | None = None,
) -> Tuple[List[SourceEvent], List[str]]:
    """Select novel high-signal events and return human-readable skipped notes."""
    seen = set(seen_event_ids)
    ranked = []
    noise_notes: List[str] = []
    for event in dedupe_events(events):
        scores = score_event(event, seen)
        if event.event_id in seen:
            continue
        if is_noise(event):
            noise_notes.append(f"Skipped {event.product}: routine or prerelease-only update.")
            continue
        if scores["total"] >= minimum_score:
            ranked.append((scores["total"], event))
    ranked.sort(key=lambda pair: (pair[0], pair[1].published_at), reverse=True)
    selected: List[SourceEvent] = []
    counts: Dict[str, int] = {}
    limits = max_per_source_type or {}
    for _, event in ranked:
        source_limit = limits.get(event.source_type, limit)
        if counts.get(event.source_type, 0) >= source_limit:
            continue
        selected.append(event)
        counts[event.source_type] = counts.get(event.source_type, 0) + 1
        if len(selected) == limit:
            break
    return selected, noise_notes[:3]


def event_to_story(event: SourceEvent, seen_event_ids: Iterable[str] = ()) -> Story:
    scores = score_event(event, seen_event_ids)
    impact_text = f"This is relevant to developers tracking {event.topic}."
    action = "watch"
    combined = f"{event.title} {event.evidence}".lower()
    if any(term in combined for term in ("security", "deprecated", "retired", "removed", "migration")):
        action = "act"
        impact_text = "Check your current tooling or upgrade path because this may require a change."
    elif event.source_type == "youtube_video":
        action = "watch"
        impact_text = (
            "Use this as a focused learning recommendation, not as evidence that every claim in the video is true."
        )
    elif event.channel == "prerelease":
        action = "skip"
        impact_text = "This is prerelease information; avoid changing production workflows without a specific need."
    return Story(
        story_id=f"story:{event.event_id}",
        event_ids=[event.event_id],
        headline=event.title,
        what_changed=event.evidence,
        why_it_matters=impact_text,
        action=action,
        rationale=(
            "Transcript-backed weekly trend, normalized against comparable recent videos."
            if event.source_type == "youtube_video"
            else f"{event.authority.capitalize()} source; relevance score {scores['relevance']:.0f}."
        ),
        source_urls=list(dict.fromkeys([event.url, *event.metadata.get("corroboration_urls", [])])),
        scores=scores,
    ).validate()
