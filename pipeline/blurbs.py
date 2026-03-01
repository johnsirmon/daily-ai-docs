"""Generate 'why it matters' and 'what to learn' blurbs via GitHub Models API.

Uses the built-in GITHUB_TOKEN — no extra API keys required.
Model endpoint: https://models.inference.ai.azure.com
"""

import json
import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_ENDPOINT = "https://models.inference.ai.azure.com"


def _get_client():
    """Lazily initialise the OpenAI-compatible client for GitHub Models."""
    try:
        from openai import OpenAI  # noqa: PLC0415
        return OpenAI(base_url=_ENDPOINT, api_key=os.environ["GITHUB_TOKEN"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("GitHub Models client unavailable: %s", exc)
        return None


def generate_blurb(
    topic_display: str,
    repos: List[Dict],
    releases: List[Dict],
) -> Dict[str, str]:
    """Return {'why': ..., 'learn': ...} blurb for a topic.

    Falls back to empty strings if the API is unavailable.
    """
    client = _get_client()
    if not client:
        return {"why": "", "learn": ""}

    summary_lines = []
    for item in (repos + releases)[:8]:
        if item["type"] == "trending":
            summary_lines.append(
                f"- Repo: {item['repo']} ({item['stars']} ⭐) — {item['description']}"
            )
        else:
            notes = item["notes"][:120].replace("\n", " ")
            summary_lines.append(
                f"- Release: {item['repo']} {item['version']} — {notes}"
            )

    if not summary_lines:
        return {"why": "", "learn": ""}

    prompt = (
        f"Topic: {topic_display}\n"
        f"Recent GitHub activity (last 2 weeks):\n"
        + "\n".join(summary_lines)
        + "\n\n"
        "Reply ONLY with valid JSON (no markdown). Answer two questions in 2-3 sentences each:\n"
        '{"why": "<why this topic matters right now for a developer>", '
        '"learn": "<specific skill or concept worth learning this week>"}'
    )

    try:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=300,
            temperature=0.4,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Blurb generation failed for %r: %s", topic_display, exc)
        return {"why": "", "learn": ""}
