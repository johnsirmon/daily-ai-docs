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
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .blurbs import generate_blurb
from .narrate import readme_to_narration
from .podcast import prepend_episode
from .releases import fetch_releases
from .render import write_readme
from .search import search_repos
from .tts import write_audio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = Path("topics/topics.yaml")


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
            "pushed_at": "",
            "type": "trending",
        }
    ]


def run(config: dict, dry_run: bool = False, publish_podcast: bool = False) -> Path:
    """Execute the full pipeline and return the path to the written README."""
    settings = config.get("settings", {})
    lookback = int(settings.get("lookback_days", 14))
    min_stars = int(settings.get("min_stars", 10))
    top_n = int(settings.get("top_n_per_topic", 5))

    topics_data = []

    for topic in config.get("topics", []):
        tid = topic["id"]
        display = topic["display"]
        keywords = topic.get("keywords", [])
        pinned = topic.get("pinned_repos", [])

        logger.info("Processing topic: %s", display)

        if dry_run:
            repos = _dry_run_items(tid, display)
            releases = []
            blurb = {
                "why": f"[dry-run] {display} is actively evolving on GitHub.",
                "learn": "[dry-run] Review the latest repos and release notes.",
            }
        else:
            repos = search_repos(keywords, lookback_days=lookback, min_stars=min_stars, top_n=top_n)
            releases = []
            for pinned_repo in pinned:
                releases.extend(fetch_releases(pinned_repo, lookback_days=lookback))
            blurb = generate_blurb(display, repos, releases)

        topics_data.append({
            "id": tid,
            "display": display,
            "items": repos + releases,
            "why": blurb.get("why", ""),
            "learn": blurb.get("learn", ""),
        })

    return write_readme(topics_data, lookback_days=lookback)


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
    args = parser.parse_args()

    config = load_config(Path(args.config))
    readme_path = run(config, dry_run=args.dry_run)
    logger.info("README written to %s", readme_path)

    if args.podcast:
        repo = os.environ.get("GITHUB_REPOSITORY", "owner/repo")
        mp3_url_template = (
            f"https://github.com/{repo}/releases/download/{{tag}}/radar.mp3"
        )
        _publish_podcast(readme_path, dry_run=args.dry_run, mp3_url_template=mp3_url_template)


if __name__ == "__main__":
    main()

