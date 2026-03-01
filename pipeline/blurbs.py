"""Generate narrative content for the AI Skills Radar via GitHub Models API.

Two generation modes:
- generate_topic_meta()   → structured JSON (why, learn, community_pulse, action_items)
                            uses gpt-4o-mini for cost efficiency
- generate_repo_deepdive() → free-form Markdown prose per repo (~200 words)
                             uses gpt-4o for quality

Both use the built-in GITHUB_TOKEN — no extra API keys required.
Model endpoint: https://models.inference.ai.azure.com
"""

import json
import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)

_ENDPOINT = "https://models.inference.ai.azure.com"
_META_MODEL = "gpt-4o-mini"
_DEEPDIVE_MODEL = "gpt-4o"
_DEEPDIVE_MIN_WORDS = 150
_META_MIN_WORDS = 40


def _get_client():
    """Lazily initialise the OpenAI-compatible client for GitHub Models."""
    try:
        from openai import OpenAI  # noqa: PLC0415
        return OpenAI(base_url=_ENDPOINT, api_key=os.environ["GITHUB_TOKEN"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("GitHub Models client unavailable: %s", exc)
        return None


def _word_count(text: str) -> int:
    return len(text.split())


def _repo_summary_line(item: Dict) -> str:
    """Build a compact stats line for a repo item."""
    parts = [f"{item['repo']} ({item['stars']:,} ⭐)"]
    if item.get("language"):
        parts.append(item["language"])
    if item.get("forks"):
        parts.append(f"{item['forks']:,} forks")
    if item.get("open_issues"):
        parts.append(f"{item['open_issues']} open issues")
    if item.get("commit_trend") and item["commit_trend"] != "flat":
        parts.append(f"commits {item['commit_trend']}")
    if item.get("prs_merged_14d"):
        parts.append(f"{item['prs_merged_14d']} PRs merged")
    if item.get("contributor_count"):
        parts.append(f"{item['contributor_count']} contributors")
    desc = (item.get("description") or "").replace("\n", " ")
    return f"- {', '.join(parts)} — {desc}"


def generate_topic_meta(
    topic_display: str,
    repos: List[Dict],
    releases: List[Dict],
) -> Dict:
    """Return structured topic metadata as a dict.

    Keys: why, learn, community_pulse, action_items.
    Falls back to empty values if the API is unavailable.
    """
    client = _get_client()
    if not client:
        return {"why": "", "learn": "", "community_pulse": "", "action_items": []}

    repo_lines = [_repo_summary_line(r) for r in repos[:8]]
    release_lines = []
    for rel in releases[:4]:
        notes = (rel.get("notes") or "")[:400].replace("\n", " ")
        release_lines.append(
            f"- Release {rel['repo']} {rel['version']} ({rel['published_at']}): {notes}"
        )

    if not repo_lines and not release_lines:
        return {"why": "", "learn": "", "community_pulse": "", "action_items": []}

    activity = "\n".join(repo_lines + release_lines)
    prompt = (
        f"Topic: {topic_display}\n"
        f"Recent GitHub activity (last 2 weeks):\n{activity}\n\n"
        "Reply ONLY with valid JSON. Fill all four fields:\n"
        "{\n"
        '  "why": "2-3 sentences: why this topic matters right now for a developer",\n'
        '  "learn": "2-3 sentences: the most important specific skill worth learning this week",\n'
        '  "community_pulse": "2-3 sentences: momentum signals — star growth, commit trends, '
        'notable contributor activity, PR throughput",\n'
        '  "action_items": ["3-5 concrete hands-on things a developer can do this week"]\n'
        "}"
    )

    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=_META_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=600,
                temperature=0.4,
            )
            data = json.loads(resp.choices[0].message.content)
            # Quality gate
            if _word_count(data.get("why", "")) >= _META_MIN_WORDS:
                return data
            logger.info("Meta quality gate failed (attempt %d), retrying", attempt + 1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Topic meta failed for %r (attempt %d): %s", topic_display, attempt + 1, exc)

    return {"why": "", "learn": "", "community_pulse": "", "action_items": []}


def generate_repo_deepdive(item: Dict, topic_display: str) -> str:
    """Return ~200-word Markdown prose analysing a single repo.

    Returns empty string if the API is unavailable.
    """
    client = _get_client()
    if not client:
        return ""

    stats_lines = [
        f"- **Stars:** {item.get('stars', 0):,}",
        f"- **Language:** {item.get('language') or 'unknown'}",
        f"- **Forks:** {item.get('forks', 0):,}",
        f"- **Open issues:** {item.get('open_issues', 0)}",
        f"- **Commit trend (4 wk):** {item.get('commit_trend', 'unknown')}",
        f"- **Weekly commits:** {item.get('weekly_commits', [])}",
        f"- **Contributors:** {item.get('contributor_count', 'unknown')}",
        f"- **PRs merged (14d):** {item.get('prs_merged_14d', 0)}",
        f"- **Created:** {item.get('created_at', 'unknown')}",
        f"- **Topics:** {', '.join(item.get('topics') or [])}",
    ]

    prompt = (
        f"You are writing a spoken podcast segment about a GitHub repository.\n\n"
        f"Topic area: {topic_display}\n"
        f"Repository: {item['repo']}\n"
        f"Description: {(item.get('description') or '').strip()}\n"
        f"Stats:\n" + "\n".join(stats_lines) + "\n\n"
        "Write approximately 200 words of engaging, informative Markdown prose about this "
        "repository. Include: what problem it solves, what the stats tell us about its momentum "
        "and community health, any notable technical aspects, and why a developer should pay "
        "attention to it. Write in second person ('you'). Do NOT use bullet points or headers — "
        "write flowing paragraphs only. Do not repeat the repo name in the first word."
    )

    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=_DEEPDIVE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.6,
            )
            text = (resp.choices[0].message.content or "").strip()
            if _word_count(text) >= _DEEPDIVE_MIN_WORDS:
                return text
            logger.info("Deep-dive quality gate failed for %r (attempt %d)", item["repo"], attempt + 1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Deep-dive failed for %r (attempt %d): %s", item["repo"], attempt + 1, exc)

    return ""


# ---------------------------------------------------------------------------
# Backward-compat shim — kept so existing tests and any callers still work
# ---------------------------------------------------------------------------

def generate_blurb(
    topic_display: str,
    repos: List[Dict],
    releases: List[Dict],
) -> Dict[str, str]:
    """Return {'why': ..., 'learn': ...} — thin wrapper around generate_topic_meta."""
    meta = generate_topic_meta(topic_display, repos, releases)
    return {"why": meta.get("why", ""), "learn": meta.get("learn", "")}

