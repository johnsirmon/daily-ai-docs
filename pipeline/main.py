"""Main pipeline orchestrator.

Usage:
    python -m pipeline.main [--dry-run] [--date YYYY-MM-DD] [--week YYYY-WW]

Options:
    --dry-run   Use deterministic sample data; no network calls.
    --date      Override the report date (default: today UTC).
    --week      Override the report week (default: current ISO week, YYYY-WW).
    --config    Path to topics YAML (default: topics/topics.yaml).
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .dedupe import dedupe
from .ingest import ingest_all
from .normalize import normalize_all
from .publish import enrich, write_daily, write_trends, write_watchlist, write_weekly
from .rank import rank

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

DEFAULT_TOPICS_PATH = Path("topics/topics.yaml")


def load_config(path: Path = DEFAULT_TOPICS_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _sample_items(config: dict, date: str) -> list:
    """Return deterministic sample items for dry-run / CI mode."""
    topics = config.get("topics", [])
    items = []
    for i, topic in enumerate(topics):
        items.append({
            "raw_id": f"sample-{i}",
            "title": f"[Sample] {topic['display']} — update {date}",
            "url": f"https://example.com/{topic['id']}/update-{date}",
            "published_at": f"{date}T00:00:00+00:00",
            "source": "sample-source",
            "source_type": "github_release",
            "topics": [topic["id"]],
            "snippet": (
                f"Sample pipeline item for topic '{topic['display']}' generated in dry-run mode. "
                "No live data was fetched."
            ),
        })
    return items


def run(config: dict, date: str, week: str, dry_run: bool = False) -> dict:
    """Execute the full pipeline and return a summary dict."""
    if dry_run:
        logger.info("Dry-run mode: using sample data")
        raw = _sample_items(config, date)
    else:
        raw = ingest_all(config)

    logger.info("Ingested %d raw items", len(raw))

    normalized = normalize_all(raw)
    deduped = dedupe(normalized)
    logger.info("After dedupe: %d items", len(deduped))

    ranked = rank(deduped, config)
    enriched = enrich(ranked, config.get("topics", []))

    ranking_cfg = config.get("ranking", {})
    top_n_daily = int(ranking_cfg.get("top_n_daily", 20))
    top_n_weekly = int(ranking_cfg.get("top_n_weekly", 50))
    watchlist_threshold = float(ranking_cfg.get("watchlist_threshold", 0.70))

    daily_path = write_daily(enriched[:top_n_daily], date)
    weekly_path = write_weekly(enriched[:top_n_weekly], week)
    trends_path = write_trends(enriched)
    watchlist_path = write_watchlist(enriched, threshold=watchlist_threshold)

    return {
        "date": date,
        "week": week,
        "items_ingested": len(raw),
        "items_after_dedupe": len(deduped),
        "outputs": {
            "daily": str(daily_path),
            "weekly": str(weekly_path),
            "trends": str(trends_path),
            "watchlist": str(watchlist_path),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily AI Intelligence Pipeline")
    parser.add_argument(
        "--config", default=str(DEFAULT_TOPICS_PATH), help="Path to topics YAML config"
    )
    parser.add_argument("--date", default=None, help="Report date override (YYYY-MM-DD)")
    parser.add_argument("--week", default=None, help="Report week override (YYYY-WW)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Use sample data; no network calls"
    )
    args = parser.parse_args()

    config = load_config(Path(args.config))

    now = datetime.now(tz=timezone.utc)
    date = args.date or now.strftime("%Y-%m-%d")
    week = args.week or now.strftime("%Y-%W")

    result = run(config, date=date, week=week, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
