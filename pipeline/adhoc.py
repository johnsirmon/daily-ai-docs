"""Ad-hoc podcast episode generator — research a topic on demand and publish.

Triggered from GitHub Mobile via the 'Ad Hoc Podcast' workflow_dispatch.

Usage:
    python -m pipeline.main --adhoc-topic "some topic" --podcast
    python -m pipeline.main --adhoc-topic "some topic" --dry-run

Flow: Exa search (optional) → AI research → narration script → TTS → podcast.xml
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .models_client import get_github_models_client

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_CACHE_DIR = Path(".cache")


def _get_ai_client():
    """Lazily initialise the OpenAI-compatible client for GitHub Models."""
    return get_github_models_client()


def _exa_search(topic: str, num_results: int = 5) -> List[Dict]:
    """Search for topic using Exa API. Returns list of {title, url, text} dicts.

    Requires EXA_API_KEY environment variable. Returns empty list if unavailable.
    """
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        logger.info("EXA_API_KEY not set — skipping Exa search")
        return []

    try:
        from exa_py import Exa  # noqa: PLC0415
        exa = Exa(api_key=api_key)
        results = exa.search_and_contents(
            topic,
            type="auto",
            num_results=num_results,
            text=True,
        )
        return [
            {
                "title": r.title or "",
                "url": r.url or "",
                "text": (r.text or "")[:2000],
            }
            for r in results.results
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Exa search failed: %s", exc)
        return []


def _ai_research(topic: str) -> str:
    """Use AI model to generate research content about a topic."""
    client = _get_ai_client()
    if not client:
        return ""

    prompt = (
        f"Research the following AI/tech topic thoroughly: {topic}\n\n"
        "Provide a comprehensive briefing covering:\n"
        "1. What it is and why it matters right now\n"
        "2. Key players, tools, or projects in this space\n"
        "3. Recent developments or trends\n"
        "4. What developers should know or learn\n"
        "5. Practical takeaways and action items\n\n"
        "Write 300-500 words. Be specific — name tools, repos, versions. "
        "Write for an audience of experienced developers."
    )

    try:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.5,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI research failed: %s", exc)
        return ""


def _ai_research_with_context(topic: str, exa_results: List[Dict]) -> str:
    """Use AI model to synthesise research with Exa search context."""
    client = _get_ai_client()
    if not client:
        return ""

    context_lines = []
    for r in exa_results[:5]:
        context_lines.append(
            f"### {r['title']}\nURL: {r['url']}\n{r['text'][:500]}\n"
        )
    context = "\n".join(context_lines)

    prompt = (
        f"Topic: {topic}\n\n"
        f"Here are recent search results about this topic:\n\n{context}\n\n"
        "Based on these sources, write a comprehensive 300-500 word briefing covering:\n"
        "1. What it is and why it matters right now\n"
        "2. Key players, tools, or projects\n"
        "3. Recent developments highlighted in the sources\n"
        "4. What developers should know or learn\n"
        "5. Practical takeaways\n\n"
        "Be specific — name tools, repos, versions. Write for experienced developers."
    )

    try:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.5,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI research with context failed: %s", exc)
        return ""


def research_topic(topic: str, dry_run: bool = False) -> Dict:
    """Research a topic using Exa search and/or AI model.

    Returns dict with keys: topic, exa_results, ai_summary.
    """
    if dry_run:
        return {
            "topic": topic,
            "exa_results": [],
            "ai_summary": f"[dry-run] Research summary for: {topic}",
        }

    exa_results = _exa_search(topic)

    if exa_results:
        ai_summary = _ai_research_with_context(topic, exa_results)
    else:
        ai_summary = _ai_research(topic)

    return {
        "topic": topic,
        "exa_results": exa_results,
        "ai_summary": ai_summary,
    }


def generate_adhoc_narration(topic: str, research: Dict) -> str:
    """Generate a podcast narration script from research results.

    Returns a plain text script suitable for TTS.
    """
    client = _get_ai_client()
    if not client:
        return _fallback_narration(topic, research)

    ai_summary = research.get("ai_summary", "")
    exa_snippets = ""
    for r in research.get("exa_results", [])[:3]:
        exa_snippets += f"- {r['title']}: {r['text'][:200]}\n"

    prompt = (
        f"You are writing a podcast script for a special episode about: {topic}\n\n"
        f"Research summary:\n{ai_summary}\n\n"
    )
    if exa_snippets:
        prompt += f"Additional sources:\n{exa_snippets}\n\n"

    prompt += (
        "Write a 3-5 minute podcast narration script (approximately 500-800 words). "
        "Rules:\n"
        "- Open with a compelling hook that names the topic\n"
        "- Use a conversational, engaging tone — second person ('you')\n"
        "- Structure: Hook → Context → Key Points → What to Learn → "
        "Actionable Takeaways → Sign-off\n"
        "- Be specific — name tools, libraries, projects, and versions\n"
        "- End with a brief sign-off mentioning 'AI Skills Radar'\n"
        "- Do NOT include any markdown formatting, headers, or bullet points\n"
        "- Write flowing paragraphs suitable for text-to-speech\n"
        "- Do NOT include stage directions or speaker labels\n"
    )

    try:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.6,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Narration generation failed: %s", exc)
        return _fallback_narration(topic, research)


def _fallback_narration(topic: str, research: Dict) -> str:
    """Simple fallback narration when AI is unavailable."""
    summary = research.get("ai_summary", f"Today we're exploring {topic}.")
    return (
        f"Welcome to a special episode of AI Skills Radar. "
        f"Today, we're doing a deep dive into {topic}.\n\n"
        f"{summary}\n\n"
        f"That's your AI Skills Radar special episode on {topic}. "
        f"Check back for more episodes, and keep building."
    )


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug[:max_len].strip("-")


def run_adhoc(
    topic: str,
    dry_run: bool = False,
    mp3_url_template: str = "",
) -> Dict:
    """Execute the ad-hoc podcast pipeline: research → narrate → TTS → podcast.xml.

    Returns dict with keys: topic, narration, episode.
    """
    from .podcast import prepend_episode  # noqa: PLC0415
    from .tts import write_audio  # noqa: PLC0415

    logger.info("Ad-hoc podcast: researching topic %r", topic)
    research = research_topic(topic, dry_run=dry_run)

    logger.info("Ad-hoc podcast: generating narration")
    narration = generate_adhoc_narration(topic, research)

    # Save narration script to cache
    script_path = _CACHE_DIR / "adhoc_narration.txt"
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    script_path.write_text(narration, encoding="utf-8")
    logger.info("Ad-hoc narration saved to %s", script_path)

    # Build episode metadata
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(topic)
    tag = f"adhoc-{slug}-{today}"
    mp3_url = (
        mp3_url_template.format(tag=tag)
        if "{tag}" in mp3_url_template
        else mp3_url_template
    )

    episode = {
        "title": f"AI Skills Radar — {topic}",
        "guid": tag,
        "pub_date": today,
        "description": f"Special episode: {topic}. Auto-generated ad-hoc deep dive.",
        "mp3_url": mp3_url,
        "file_size_bytes": 0,
        "duration_secs": 0,
    }

    if dry_run:
        logger.info("[dry-run] Skipping TTS and podcast.xml update")
        episode["mp3_url"] = "DRY_RUN"
    else:
        audio_path = write_audio(narration, path="adhoc-episode.mp3")
        if audio_path:
            episode["file_size_bytes"] = audio_path.stat().st_size
            prepend_episode(episode, path="podcast.xml")
            logger.info("podcast.xml updated (episode: %s)", tag)
        else:
            logger.warning("TTS failed; skipping podcast.xml update for ad-hoc episode")

    return {"topic": topic, "narration": narration, "episode": episode}
