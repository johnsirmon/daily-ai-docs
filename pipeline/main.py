"""AI Skills Radar — pipeline orchestrator.

Usage:
    python -m pipeline.main [--dry-run] [--podcast] [--config PATH]

Options:
    --dry-run   Skip all network calls; write a placeholder README.
    --podcast   Also generate audio (radar.mp3) and update podcast.xml.
                Reads PUBLISH_PODCAST=1 env var as an alternative to the flag.
    --config    Path to topics YAML (default: topics/topics.yaml).
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .blurbs import generate_topic_meta, generate_repo_deepdive
from .enrich import enrich_items
from .narrate import readme_to_narration
from .podcast import prepend_episode
from .releases import fetch_releases
from .render import write_readme
from .research import run_research_summary, dry_run_report
from .search import search_repos
from .tts import write_audio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = Path("topics/topics.yaml")
_CHECKPOINT_PATH = Path(".cache/pipeline_checkpoint.json")


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    """Load and return the topics YAML config."""
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _dry_run_items(topic_id: str, topic_display: str) -> list:
    """Return deterministic sample items for --dry-run mode."""
    return [
        {
            "repo": f"sample/repo-{topic_id}",
            "url": "https://github.com",
            "stars": 42,
            "description": f"Sample trending repo for {topic_display}",
            "language": "Python",
            "forks": 10,
            "open_issues": 3,
            "topics": ["ai"],
            "pushed_at": "",
            "type": "trending",
        }
    ]


def _save_checkpoint(data: dict | list) -> None:
    """Persist pipeline data so TTS/render can resume without re-fetching."""
    _CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CHECKPOINT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Checkpoint saved to %s", _CHECKPOINT_PATH)


def run(config: dict, dry_run: bool = False, publish_podcast: bool = False) -> Path:
    """Execute the full pipeline and return the path to the written README."""
    settings = config.get("settings", {})
    lookback = int(settings.get("lookback_days", 14))
    min_stars = int(settings.get("min_stars", 10))
    top_n = int(settings.get("top_n_per_topic", 8))
    enrich_stats = bool(settings.get("enrich_stats", True))

    # ── Phase 1: collect raw data for all topics ──────────────────────────────
    raw_topics = []  # list of {topic, repos, releases}
    all_items_flat = []  # used by research summariser

    for topic in config.get("topics", []):
        tid = topic["id"]
        display = topic["display"]
        keywords = topic.get("keywords", [])
        pinned = topic.get("pinned_repos", [])

        logger.info("Fetching data for topic: %s", display)

        if dry_run:
            repos = _dry_run_items(tid, display)
            releases = []
        else:
            repos = search_repos(keywords, lookback_days=lookback, min_stars=min_stars, top_n=top_n)
            releases = []
            for pinned_repo in pinned:
                releases.extend(fetch_releases(pinned_repo, lookback_days=lookback))

        raw_topics.append({"topic": topic, "repos": repos, "releases": releases})

        # Tag each item with topic context for the research summariser
        for item in repos + releases:
            item["topic_display"] = display
        all_items_flat.extend(repos + releases)

    # ── Research summary: cross-topic narrative (after fetch, before blurbs) ──
    topic_ids = [t["topic"]["id"] for t in raw_topics]
    if dry_run:
        research_report = dry_run_report(topic_ids)
    else:
        research_report = run_research_summary(all_items_flat, topic_ids)
    logger.info("Research report ready (week_story words: %d)",
                len(research_report.get("week_story", "").split()))

    # ── Phase 2: enrich, generate blurbs, assemble topics_data ──────────────
    topics_data = []

    for raw in raw_topics:
        topic = raw["topic"]
        repos = raw["repos"]
        releases = raw["releases"]
        tid = topic["id"]
        display = topic["display"]

        logger.info("Enriching and generating blurbs for topic: %s", display)

        if dry_run:
            meta = {
                "why": f"[dry-run] {display} is actively evolving on GitHub.",
                "learn": "[dry-run] Review the latest repos and release notes.",
                "community_pulse": "[dry-run] Strong momentum across the ecosystem.",
                "action_items": ["[dry-run] Explore the top repos for this topic."],
            }
            deep_dives = []
        else:
            if enrich_stats and repos:
                enrich_items(repos, top_n=min(4, len(repos)))

            deep_dives = []
            for repo_item in repos[:4]:
                prose = generate_repo_deepdive(repo_item, display)
                if prose:
                    deep_dives.append({"repo": repo_item["repo"], "prose": prose})

            # Inject per-topic research insight into blurb prompt
            topic_context = research_report.get("topic_insights", {}).get(tid, "")
            meta = generate_topic_meta(display, repos, releases, context=topic_context)

        topics_data.append({
            "id": tid,
            "display": display,
            "items": repos + releases,
            "why": meta.get("why", ""),
            "learn": meta.get("learn", ""),
            "summary": meta.get("why", ""),  # overview uses why as lead paragraph
            "community_pulse": meta.get("community_pulse", ""),
            "action_items": meta.get("action_items", []),
            "deep_dives": deep_dives,
        })

    # Checkpoint enriched data before render/TTS
    _save_checkpoint({"topics": topics_data, "research_report": research_report})

    return write_readme(topics_data, lookback_days=lookback, research_report=research_report)


def _publish_podcast(readme_path: Path, dry_run: bool, mp3_url_template: str) -> None:
    """Narrate the README, generate audio, and update podcast.xml."""
    readme_content = readme_path.read_text(encoding="utf-8")
    script = readme_to_narration(readme_content)

    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    tag = f"radar-{today}"
    mp3_url = mp3_url_template.format(tag=tag) if "{tag}" in mp3_url_template else mp3_url_template

    episode = {
        "title": f"AI Skills Weekly — {today}",
        "guid": tag,
        "pub_date": today,
        "description": f"Weekly AI skills digest for {today}. Auto-generated.",
        "mp3_url": mp3_url,
        "file_size_bytes": 0,
        "duration_secs": 0,
    }

    if dry_run:
        logger.info("[dry-run] Skipping TTS — podcast.xml updated with placeholder URL")
        episode["mp3_url"] = "DRY_RUN"
    else:
        audio_path = write_audio(script, path="radar.mp3")
        if audio_path:
            episode["file_size_bytes"] = audio_path.stat().st_size
        else:
            logger.warning("TTS failed; podcast.xml will have 0-byte placeholder")

    prepend_episode(episode, path="podcast.xml")
    logger.info("podcast.xml updated (episode: %s)", tag)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Skills Radar pipeline")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to topics YAML")
    parser.add_argument("--dry-run", action="store_true", help="Skip network calls")
    parser.add_argument(
        "--podcast",
        action="store_true",
        default=os.environ.get("PUBLISH_PODCAST", "") == "1",
        help="Generate audio and update podcast.xml (also via PUBLISH_PODCAST=1 env var)",
    )
    parser.add_argument(
        "--podcast-only",
        action="store_true",
        help="Regenerate podcast from existing README.md without re-running the full pipeline",
    )
    args = parser.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "owner/repo")
    mp3_url_template = f"https://github.com/{repo}/releases/download/{{tag}}/radar.mp3"

    if args.podcast_only:
        readme_path = Path("README.md")
        if not readme_path.exists():
            logger.error("README.md not found — run the full pipeline first or provide one")
            sys.exit(1)
        _publish_podcast(readme_path, dry_run=args.dry_run, mp3_url_template=mp3_url_template)
        return

    config = load_config(Path(args.config))
    readme_path = run(config, dry_run=args.dry_run)
    logger.info("README written to %s", readme_path)

    if args.podcast:
        _publish_podcast(readme_path, dry_run=args.dry_run, mp3_url_template=mp3_url_template)


if __name__ == "__main__":
    main()

