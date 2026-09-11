"""Deterministic novelty, relevance, and noise scoring for source events."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Iterable, List, Sequence, Tuple

from .schema import SourceEvent, Story

_HIGH_IMPACT = re.compile(
    r"\b(security (?:fix|patch|advisory)|vulnerabilit(?:y|ies)|breaking change|"
    r"deprecat(?:ed|ion)|retir(?:ed|ement)|migration|general availability|"
    r"pricing|rate limit|tool calling|structured outputs?|adds? support)\b",
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
        penalty += 24.0
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
        if event.authority == current.authority and event.published_at > current.published_at:
            chosen[key] = event
    return list(chosen.values())


def is_noise(event: SourceEvent) -> bool:
    return bool(_NOISE.search(f"{event.title} {event.evidence}"))


def select_events(
    events: Sequence[SourceEvent],
    seen_event_ids: Iterable[str] = (),
    *,
    limit: int = 7,
    minimum_score: float = 75.0,
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
        if scores["total"] >= minimum_score:
            ranked.append((scores["total"], event))
        elif scores["noise_penalty"]:
            noise_notes.append(f"Skipped {event.product}: below threshold after routine/prerelease penalties.")
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
    return selected, list(dict.fromkeys(noise_notes))[:3]


_ACTION_REQUIRED = re.compile(
    r"\b(?:security (?:fix|patch|advisory)|CVE-\d{4}-\d{4,}|"
    r"(?:fix(?:es|ed)?|patch(?:es|ed)?) (?:a |the )?(?:critical |security )?vulnerability|"
    r"breaking changes?|migration (?:is )?required|must (?:migrate|upgrade)|"
    r"(?:api|endpoint|model|support|feature) (?:\S+ )?(?:(?:is|was|will be) )?"
    r"(?:deprecated|retired|removed)|"
    r"(?:deprecat(?:ed|es)|retir(?:ed|es)|removed) (?:the )?(?:api|endpoint|model|support|feature))\b",
    re.IGNORECASE,
)


def _requires_action(text: str) -> bool:
    # Conservative sentence-level suppression: discussion/negation is not a notice.
    for sentence in re.split(r"[.!?\n]+", text):
        if re.search(r"\b(no|not|without|tutorial|guide|docs-only)\b|"
                     r"\b(?:adds?|updates?) (?:the )?(?:documentation|docs)\b", sentence, re.I):
            continue
        if _ACTION_REQUIRED.search(sentence):
            return True
    return False


def _bounded_excerpt(text: str, *, words: int = 110, chars: int = 1200, sentences: int = 3) -> str:
    """Keep source wording, prefer sentence/word boundaries, and label omissions."""
    clean = " ".join(text.split())
    selected = []
    for sentence in re.split(r"(?<=[.!?])\s+", clean)[:sentences]:
        proposed = " ".join([*selected, sentence])
        if len(proposed) > chars or len(proposed.split()) > words:
            if not selected:
                tokens = []
                for token in sentence.split()[:words]:
                    if len(" ".join([*tokens, token])) > chars:
                        break
                    tokens.append(token)
                selected = [" ".join(tokens)] if tokens else []
            break
        selected.append(sentence)
    excerpt = " ".join(selected)
    if excerpt == clean:
        return excerpt
    return (excerpt + " … [Excerpt; see source for full details.]").strip()


def event_to_story(event: SourceEvent, seen_event_ids: Iterable[str] = ()) -> Story:
    scores = score_event(event, seen_event_ids)
    impact_text = f"This is relevant to developers tracking {event.topic}."
    action = "watch"
    rationale = "Read the primary source and assess applicability before changing your workflow."
    combined = f"{event.title} {event.evidence}"
    # Learning videos and prereleases never become production ACT advice via keywords.
    if event.source_type == "youtube_video":
        impact_text = "Use this as a focused learning pick, not verified product-change evidence."
        rationale = "Ranked within a bounded weekly discovery sample; the ranking does not establish adoption or verify video claims."
    elif event.channel == "prerelease":
        action = "skip"
        impact_text = "This is prerelease information; avoid changing production workflows without a specific need."
        rationale = "Evaluate only in an isolated test environment if the cited change addresses a current need."
    elif event.authority == "primary" and _requires_action(combined):
        action = "act"
        impact_text = "The source flags a security or compatibility change that may affect existing users."
        rationale = "Check affected versions and the cited notice first; act only if your tooling is affected."
    return Story(
        story_id=f"story:{event.event_id}",
        event_ids=[event.event_id],
        headline=event.title,
        what_changed=_bounded_excerpt(event.evidence),
        why_it_matters=impact_text,
        action=action,
        rationale=rationale,
        source_urls=list(dict.fromkeys([event.url, *event.metadata.get("corroboration_urls", [])])),
        scores=scores,
    ).validate()
