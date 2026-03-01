"""AI Skills Radar — pipeline orchestrator.

Usage:
    python -m pipeline.main [--dry-run] [--config PATH]

Options:
    --dry-run   Skip all network calls; write a placeholder README.
    --config    Path to topics YAML (default: topics/topics.yaml).
"""

import argparse
import logging
import sys
from pathlib import Path

import yaml

from .blurbs import generate_blurb
from .releases import fetch_releases
from .render import write_readme
from .search import search_repos

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


def run(config: dict, dry_run: bool = False) -> Path:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Skills Radar pipeline")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to topics YAML")
    parser.add_argument("--dry-run", action="store_true", help="Skip network calls")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    path = run(config, dry_run=args.dry_run)
    logger.info("README written to %s", path)


if __name__ == "__main__":
    main()

