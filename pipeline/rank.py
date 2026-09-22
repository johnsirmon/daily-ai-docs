"""Deterministic novelty, relevance, and noise scoring for source events."""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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

_UTILITY_CONTEXT = re.compile(
    r"\b(?:permissions?|approvals?|previews?|sandbox|tool (?:calls?|calling|execution|arguments?)|mcp|sessions?|context|memory|"
    r"worktrees?|containers?|gateways?|backends?|connectors?|telemetry|traces?|evaluations?|benchmarks?|workflows?|runners?|"
    r"authentication|authorization|tokens?|credentials?|network|ssh|https|keys?|bundles?|"
    r"dependencies|budgets?|pricing|rate limits?|structured outputs?|plugins?|api|endpoint|"
    r"clients?|automation|ci|installers?|downloads?|platforms?|architectures?)\b",
    re.IGNORECASE,
)
_UTILITY_CHANGE = re.compile(
    r"\b(?:added|adds?|fixed|fixes|enabled?|introduced|removed|requires?|supports?|blocks?|"
    r"allows?|prevents?|records?|reports?|attach(?:es|ing)?|spawn(?:s|ing)?|configurable|"
    r"deprecat(?:ed|ion)|retir(?:ed|ement)|migrat(?:e|ion)|"
    r"must|will stop|no longer|unaffected|affected|only|ignore|update|upgrade|replace|review|"
    r"inspect|select|download|install)\b",
    re.IGNORECASE,
)
_UTILITY_RISK = re.compile(
    r"\b(?:security|vulnerabilit(?:y|ies)|breaking changes?|compatibility|regression|crash|"
    r"data loss|corrupt(?:ion|ed)?|stop working|fail(?:ure|ed)?|migrat(?:e|ion)|deprecat(?:ed|ion)|"
    r"retir(?:ed|ement)|brownout|removal)\b",
    re.IGNORECASE,
)
_UTILITY_HYPE = re.compile(
    r"\b(?:amazing|exciting|game[- ]changing|revolutionary|best[- ]in[- ]class|powerful new|"
    r"next generation|developer experience)\b",
    re.IGNORECASE,
)
_COSMETIC = re.compile(r"\b(?:spinner|alignment|spacing|colors?|icons?|wording|typo|cosmetic|visual polish)\b", re.I)
_PRODUCT_ALIASES = {
    "vscode": "visual studio code",
    "visual studio code": "visual studio code",
    "github developer tools": "github platform",
    "github": "github platform",
    "github platform": "github platform",
    "model context protocol": "model context protocol",
    "mcp": "model context protocol",
    "hermes": "hermes agent",
    "hermes agent": "hermes agent",
    "codeql": "codeql cli",
    "codeql cli": "codeql cli",
}


def canonical_product(product: str) -> str:
    key = re.sub(r"\s+", " ", product.strip().casefold())
    return _PRODUCT_ALIASES.get(key, key)


def utility_sentences(event: SourceEvent) -> List[str]:
    """Return source sentences that establish a concrete developer consequence."""
    useful = []
    clean = " ".join(event.evidence.split())
    for sentence in re.split(r"(?<=[.!?])\s+|;\s+|\n+", clean):
        sentence = sentence.strip()
        if not sentence or _UTILITY_HYPE.search(sentence) or _COSMETIC.search(sentence):
            continue
        if re.search(r"\b(?:no|not|without)\s+(?:known\s+)?breaking changes?\b", sentence, re.I):
            continue
        if re.search(r"\bmigration guide\b.*\boptional\b", sentence, re.I):
            continue
        context = bool(_UTILITY_CONTEXT.search(sentence))
        change = bool(_UTILITY_CHANGE.search(sentence))
        risk = bool(_UTILITY_RISK.search(sentence))
        if len(sentence.split()) >= 5 and ((context and change) or risk):
            useful.append(sentence)
    return useful


def assess_utility(event: SourceEvent) -> Dict[str, float]:
    useful = utility_sentences(event)
    text = " ".join(useful)
    workflow = 30.0 if _UTILITY_CONTEXT.search(text) and _UTILITY_CHANGE.search(text) else 0.0
    risk = 25.0 if _UTILITY_RISK.search(text) else 0.0
    action = 20.0 if re.search(
        r"\b(?:must|requires?|update|upgrade|replace|review|inspect|ignore|unaffected)\b", text, re.I,
    ) else 0.0
    specificity = 10.0 if useful else 0.0
    return {
        "workflow_impact": workflow,
        "risk_or_compatibility": risk,
        "actionability": action,
        "specificity": specificity,
        "demonstrated": 1.0 if useful else 0.0,
        "utility_total": workflow + risk + action + specificity,
    }


def score_event(event: SourceEvent, seen_event_ids: Iterable[str] = ()) -> Dict[str, float]:
    """Return transparent scores; metadata cannot rescue unsupported utility."""
    event.validate()
    seen = set(seen_event_ids)
    utility = assess_utility(event)
    # Score relative to the recorded fetch time so replaying a manifest is deterministic.
    now = datetime.fromisoformat(event.fetched_at.replace("Z", "+00:00"))
    published = datetime.fromisoformat(event.published_at.replace("Z", "+00:00"))
    age_hours = max(0.0, (now - published).total_seconds() / 3600)

    authority = 20.0 if event.authority == "primary" else 0.0
    relevance = float(max(0, min(5, int(event.metadata.get("priority", 10)) / 4)))
    novelty = 0.0 if event.event_id in seen else 15.0
    recency = max(0.0, 5.0 - age_hours / 24.0)
    penalty = 0.0
    if event.channel == "prerelease":
        penalty += 12.0
    if is_noise(event) and not utility["demonstrated"]:
        penalty += 24.0
    velocity = float(event.metadata.get("star_velocity", 0) or 0)
    youtube_trend = float(event.metadata.get("trend_score", 0) or 0)
    momentum = min(3.0, max(0.0, velocity / 100.0, youtube_trend / 100.0))
    total = (
        utility["utility_total"] + authority + relevance + novelty + recency + momentum - penalty
        if utility["demonstrated"] and authority else 0.0
    )
    return {
        **utility,
        "authority": round(authority, 2),
        "relevance": round(relevance, 2),
        "novelty": round(novelty, 2),
        "recency": round(recency, 2),
        "impact": round(max(utility["workflow_impact"], utility["risk_or_compatibility"]), 2),
        "momentum": round(momentum, 2),
        "noise_penalty": round(penalty, 2),
        "total": round(total, 2),
    }


def _identity(event: SourceEvent) -> Tuple[str, str, str]:
    if event.source_type == "research_paper":
        return event.source_type, str(event.metadata.get("paper_id") or event.event_id), "research"
    version = str(event.metadata.get("version") or event.metadata.get("canonical_event") or event.title)
    version = re.sub(r"\s+", " ", version.strip().lower())
    return canonical_product(event.product), version, event.channel


def dedupe_events(events: Sequence[SourceEvent]) -> List[SourceEvent]:
    """Dedupe event-level coverage while preserving distinct product versions."""
    chosen: Dict[Tuple[str, str, str], SourceEvent] = {}
    for event in events:
        event.validate()
        key = _identity(event)
        current = chosen.get(key)
        if current is None:
            chosen[key] = event
            continue
        current_quality = (
            current.authority == "primary", assess_utility(current)["utility_total"], has_substantive_evidence(current),
            len(" ".join(current.evidence.split())), current.published_at, current.event_id,
        )
        event_quality = (
            event.authority == "primary", assess_utility(event)["utility_total"], has_substantive_evidence(event),
            len(" ".join(event.evidence.split())), event.published_at, event.event_id,
        )
        if event_quality > current_quality:
            chosen[key] = event
    return list(chosen.values())


def is_noise(event: SourceEvent) -> bool:
    text = f"{event.title}. {event.evidence}"
    sentences = [sentence.strip() for sentence in re.split(r"[.!?\n]+", text) if sentence.strip()]
    noisy = [sentence for sentence in sentences if _NOISE.search(sentence)]
    if not noisy:
        return False
    substantive = any(
        not _NOISE.search(sentence)
        and re.search(r"\b(?:added|adds?|fixed|fixes|enables?|introduced|improved|removed)\b", sentence, re.I)
        and len(sentence.split()) >= 5
        for sentence in sentences
    )
    return not substantive


def select_events(
    events: Sequence[SourceEvent],
    seen_event_ids: Iterable[str] = (),
    *,
    limit: int = 7,
    minimum_score: float = 75.0,
    max_per_source_type: Dict[str, int] | None = None,
    max_per_product: int | None = None,
) -> Tuple[List[SourceEvent], List[str]]:
    """Select novel high-signal events and return human-readable skipped notes."""
    seen = set(seen_event_ids)
    ranked = []
    noise_notes: List[str] = []
    for event in dedupe_events(events):
        scores = score_event(event, seen)
        if event.event_id in seen:
            continue
        if event.authority != "primary":
            noise_notes.append(f"Excluded {event.product}: spoken claims require primary evidence.")
            continue
        if event.source_type != "youtube_video" and not has_substantive_evidence(event):
            noise_notes.append(f"Excluded {event.product}: no substantive change evidence.")
            continue
        if not scores["demonstrated"]:
            noise_notes.append(f"Excluded {event.product}: no specific developer consequence was established.")
            continue
        if scores["total"] >= minimum_score:
            ranked.append((scores["total"], event))
        elif scores["noise_penalty"]:
            noise_notes.append(f"Skipped {event.product}: below threshold after routine/prerelease penalties.")
    ranked.sort(key=lambda pair: (pair[0], pair[1].published_at), reverse=True)
    selected: List[SourceEvent] = []
    counts: Dict[str, int] = {}
    product_counts: Dict[str, int] = {}
    limits = max_per_source_type or {}
    for _, event in ranked:
        source_limit = limits.get(event.source_type, limit)
        if counts.get(event.source_type, 0) >= source_limit:
            continue
        product_key = canonical_product(event.product)
        if max_per_product is not None and product_counts.get(product_key, 0) >= max_per_product:
            noise_notes.append(f"Limited {event.product}: additional same-product updates omitted.")
            continue
        selected.append(event)
        counts[event.source_type] = counts.get(event.source_type, 0) + 1
        product_counts[product_key] = product_counts.get(product_key, 0) + 1
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
    useful = utility_sentences(event)
    useful_text = ". ".join(sentence.rstrip(".;") for sentence in useful)
    if useful_text:
        useful_text += "."
    impact_text = _bounded_excerpt(useful_text, words=150, chars=1600, sentences=4)
    if not impact_text:
        impact_text = "The evidence does not establish a specific developer consequence."
    action = "watch"
    action_sentences = [
        sentence for sentence in useful
        if re.search(r"\b(?:must|requires?|update|upgrade|replace|review|inspect|ignore|unaffected)\b", sentence, re.I)
    ]
    rationale = action_sentences[0] if action_sentences else "No workflow change is supported beyond the cited evidence."
    if rationale in impact_text:
        rationale = "No additional workflow change is supported beyond the cited evidence."
    combined = f"{event.title} {event.evidence}"
    # Learning videos and prereleases never become production ACT advice via keywords.
    if event.source_type == "youtube_video":
        impact_text = "This is a learning pick, not verified evidence of a product change. " + impact_text
        rationale = "The bounded discovery ranking does not establish adoption or verify the video's claims."
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


def has_substantive_evidence(event: SourceEvent) -> bool:
    """Distinguish a source-backed change from a newly numbered release."""
    text = re.sub(r"^(?:what(?:'s| is) changed|release notes)\s*[-:]*\s*", "", event.evidence.strip(), flags=re.I)
    if re.fullmatch(r"https://\S+", text):
        return False
    if re.fullmatch(r"(?:(?:published|release|version)\s+)?[vr]?\d[\w.+-]*[.!]?", text, re.I):
        return False
    if re.fullmatch(
        r"(?:minor )?(?:bug fixes?(?: and reliability improvements)?|"
        r"maintenance(?: release)?|performance improvements|"
        r"various fixes(?: and improvements)?)[.!]?", text, re.I,
    ):
        return False
    if len(text.split()) < 4:
        return False
    if event.channel == "prerelease":
        return bool(_HIGH_IMPACT.search(text) or _requires_action(text))
    substantive_sentence = any(
        not _NOISE.search(sentence)
        and re.search(r"\b(?:added|adds?|fixed|fixes|enables?|introduced|improved|removed)\b", sentence, re.I)
        and len(sentence.split()) >= 5
        for sentence in re.split(r"[.!?\n]+", text)
    )
    return not is_noise(event) or bool(_HIGH_IMPACT.search(text) or _requires_action(text) or substantive_sentence)


def select_editorial_events(
    events: Sequence[SourceEvent],
    seen_event_ids: Iterable[str] = (),
    *,
    covered_paper_ids: Iterable[str] = (),
    published_events: Sequence[dict] = (),
    max_products: int = 3,
    max_events_per_product: int = 1,
    max_research: int = 1,
    now: datetime | None = None,
) -> Tuple[List[SourceEvent], List[str]]:
    """Apply editorial eligibility before ranking, without marking rejects published."""
    if not 1 <= max_products <= 5 or not 1 <= max_events_per_product <= 3 or max_research not in {0, 1}:
        raise ValueError("editorial selection limits are outside the supported budget")
    now = now or datetime.now(timezone.utc)
    seen, papers_seen = set(seen_event_ids), set(covered_paper_ids)
    products: Dict[str, List[SourceEvent]] = {}
    papers: List[SourceEvent] = []
    reasons: List[str] = []
    def prior_digest(row: dict) -> str:
        return row.get("evidence_sha256") or hashlib.sha256(row["normalized_evidence"].encode("utf-8")).hexdigest()
    for event in dedupe_events(events):
        normalized = " ".join(event.evidence.casefold().split())
        evidence_digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        previous = [
            row for row in published_events
            if row["canonical_event_id"] == event.metadata.get("canonical_event_id", event.event_id)
        ]
        if event.event_id in seen:
            if not previous or not event.metadata.get("updated_at"):
                continue
            prior = max(previous, key=lambda row: row["published_at"])
            updated = datetime.fromisoformat(str(event.metadata["updated_at"]).replace("Z", "+00:00"))
            covered_at = datetime.fromisoformat(prior["published_at"].replace("Z", "+00:00"))
            if not covered_at < updated <= now or evidence_digest == prior_digest(prior):
                continue
            revision = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
            event = replace(event, event_id=f"{event.event_id}:rev:{revision}", metadata={
                **event.metadata, "canonical_event_id": event.event_id,
            })
            if event.event_id in seen:
                continue
        if event.source_type != "research_paper" and any(
            row["product"].casefold() == event.product.casefold()
            and row["channel"] == event.channel
            and prior_digest(row) == evidence_digest
            for row in published_events
        ):
            reasons.append(f"Excluded {event.product}: unchanged previously published evidence.")
            continue
        if event.source_type == "research_paper":
            first = datetime.fromisoformat(str(event.metadata.get("first_published_at", event.published_at)).replace("Z", "+00:00"))
            if (not event.metadata.get("full_text_available")
                    or not str(event.metadata.get("full_text", "")).strip()
                    or not event.metadata.get("paper_id")
                    or event.metadata["paper_id"] in papers_seen
                    or not now - timedelta(days=30) <= first <= now):
                reasons.append(f"Excluded {event.product}: stale, already covered, or insufficient paper evidence.")
                continue
            papers.append(event)
        elif event.source_type == "youtube_video":
            reasons.append(f"Excluded {event.product}: learning discovery is not a verified new product change.")
        elif has_substantive_evidence(event) and assess_utility(event)["demonstrated"]:
            products.setdefault(canonical_product(event.product), []).append(event)
        else:
            reasons.append(f"Excluded {event.product}: no specific developer consequence was established.")
    ranked_groups = []
    for group in products.values():
        group.sort(key=lambda event: (score_event(event, seen)["total"], event.published_at), reverse=True)
        ranked_groups.append(group[:max_events_per_product])
    ranked_groups.sort(key=lambda group: (score_event(group[0], seen)["total"], group[0].published_at), reverse=True)
    selected = [event for group in ranked_groups[:max_products] for event in group]
    # Research is a distinct optional segment, not an automatic no-news edition.
    if selected and max_research:
        papers.sort(key=lambda event: (score_event(event, seen)["relevance"], event.published_at), reverse=True)
        selected.extend(papers[:max_research])
    return selected, list(dict.fromkeys(reasons))


def group_editorial_stories(events: Sequence[SourceEvent]) -> List[Story]:
    """Keep related release evidence together instead of reading one segment per tag."""
    groups: Dict[str, List[SourceEvent]] = {}
    for event in events:
        key = event.event_id if event.source_type == "research_paper" else canonical_product(event.product)
        groups.setdefault(key, []).append(event)
    stories = []
    for group in groups.values():
        first = group[0]
        base = event_to_story(first)
        urls = list(dict.fromkeys(url for event in group for url in [
            event.url, *event.metadata.get("corroboration_urls", []),
        ]))
        stories.append(Story(
            story_id=base.story_id,
            event_ids=[event.event_id for event in group],
            headline=base.headline if len(group) == 1 else f"{first.product}: recent changes",
            what_changed=_bounded_excerpt(" ".join(event.evidence for event in group)),
            why_it_matters=base.why_it_matters,
            action=base.action,
            rationale=base.rationale,
            source_urls=urls,
            scores=base.scores,
            kind="research" if first.source_type == "research_paper" else "product",
        ).validate())
    return stories
