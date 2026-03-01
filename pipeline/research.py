"""Research summariser stage — synthesises a cross-topic narrative from collected items.

Runs after all topic search/fetch data is collected, before per-topic blurb generation.
Produces a ResearchReport that enriches both the README and podcast narration.

ResearchReport schema:
    week_story      — 100-150 word narrative: the big theme across all topics this week
    narrative_hook  — 1-2 sentence spoken cold-open ("This week in AI…")
    topic_insights  — dict[topic_id, str] of optional extra context per topic

All fields fall back to empty values if the API is unavailable.
"""

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

_ENDPOINT = "https://models.inference.ai.azure.com"
_MODEL = "gpt-4o-mini"
_CACHE_DIR = Path(".cache")
_WEEK_STORY_MIN_WORDS = 50

# Typed alias
ResearchReport = Dict  # {week_story: str, narrative_hook: str, topic_insights: dict}

_EMPTY_REPORT: ResearchReport = {
    "week_story": "",
    "narrative_hook": "",
    "topic_insights": {},
}


def _get_client():
    """Lazily initialise the OpenAI-compatible client for GitHub Models."""
    try:
        from openai import OpenAI  # noqa: PLC0415
        return OpenAI(base_url=_ENDPOINT, api_key=os.environ["GITHUB_TOKEN"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("GitHub Models client unavailable: %s", exc)
        return None


def _cache_path(today: date) -> Path:
    return _CACHE_DIR / f"research_{today.isoformat()}.json"


def _load_cache(today: date) -> ResearchReport | None:
    """Return cached report for today if it exists."""
    path = _cache_path(today)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _save_cache(report: ResearchReport, today: date) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(today).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _build_item_summary(items: List[Dict]) -> str:
    """Build a compact text listing of repo/release items for the prompt."""
    lines = []
    for item in items[:40]:  # cap to avoid token overflow
        if item.get("type") == "trending":
            desc = (item.get("description") or "").replace("\n", " ")[:120]
            lines.append(
                f"- [{item.get('topic_display', '')}] {item['repo']} "
                f"({item.get('stars', 0):,}★) — {desc}"
            )
        elif item.get("type") == "release":
            notes = (item.get("notes") or "").replace("\n", " ")[:80]
            lines.append(
                f"- [{item.get('topic_display', '')}] RELEASE {item['repo']} "
                f"{item.get('version', '')} — {notes}"
            )
    return "\n".join(lines)


def run_research_summary(
    all_items: List[Dict],
    topic_ids: List[str],
    today: date | None = None,
    _force: bool = False,
) -> ResearchReport:
    """Synthesise a cross-topic ResearchReport from all collected repo/release items.

    Args:
        all_items:  Flat list of all trending + release items across all topics.
                    Each item should have a 'topic_display' key added by the caller.
        topic_ids:  Ordered list of topic IDs (used for topic_insights keys).
        today:      Date for cache key; defaults to today.
        _force:     If True, skip cache and re-run (used in tests).

    Returns:
        ResearchReport dict (fail-open: empty report on any error).
    """
    today = today or date.today()

    if not _force:
        cached = _load_cache(today)
        if cached is not None:
            logger.info("Research report loaded from cache (%s)", _cache_path(today))
            return cached

    if not all_items:
        return dict(_EMPTY_REPORT)

    client = _get_client()
    if not client:
        return dict(_EMPTY_REPORT)

    item_text = _build_item_summary(all_items)
    topic_list = ", ".join(topic_ids)

    prompt = (
        f"You are writing for a weekly AI developer newsletter and podcast.\n\n"
        f"Topics covered this week: {topic_list}\n\n"
        f"New repos and releases found on GitHub this week:\n{item_text}\n\n"
        "Reply ONLY with valid JSON. Fill all three fields:\n"
        "{\n"
        '  "week_story": "100-150 words: the single most important trend or theme '
        'you see across ALL topics this week. Be specific — name repos and versions. '
        'Write for a developer audience. No bullet points.",\n'
        '  "narrative_hook": "1-2 sentences: a punchy spoken opening for a podcast. '
        'Start with This week or This week in AI.",\n'
        '  "topic_insights": {\n'
        + "".join(f'    "{tid}": "1 sentence of extra context for this topic",\n' for tid in topic_ids)
        + "  }\n"
        "}"
    )

    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=800,
                temperature=0.4,
            )
            data = json.loads(resp.choices[0].message.content)
            word_count = len((data.get("week_story") or "").split())
            if word_count >= _WEEK_STORY_MIN_WORDS:
                report: ResearchReport = {
                    "week_story": data.get("week_story", ""),
                    "narrative_hook": data.get("narrative_hook", ""),
                    "topic_insights": data.get("topic_insights", {}),
                }
                _save_cache(report, today)
                return report
            logger.info("Research quality gate failed (attempt %d, words=%d)", attempt + 1, word_count)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Research summary failed (attempt %d): %s", attempt + 1, exc)

    return dict(_EMPTY_REPORT)


def dry_run_report(topic_ids: List[str]) -> ResearchReport:
    """Return a deterministic placeholder report for --dry-run mode."""
    return {
        "week_story": "[dry-run] This week the AI ecosystem shows strong momentum across all tracked topics.",
        "narrative_hook": "[dry-run] This week in AI, several significant new tools and releases emerged.",
        "topic_insights": {tid: f"[dry-run] Active development in {tid}." for tid in topic_ids},
    }
