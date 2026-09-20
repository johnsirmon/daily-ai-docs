"""Offline production-artifact validation used by CI and local review."""

from pathlib import Path

import yaml
from PIL import Image

from .podcast_metadata import load_catalog
from .publish import validate_feed_file, validate_local_episode_artwork


def main() -> None:
    config = yaml.safe_load(Path("topics/topics.yaml").read_text(encoding="utf-8"))
    daily_sources = (config.get("daily") or {}).get("sources") or {}
    if not daily_sources.get("github_releases") and not daily_sources.get("feeds"):
        raise SystemExit("no authoritative daily sources configured")
    result = validate_feed_file("podcast.xml", artwork_root=Path("."))
    for entry in load_catalog(Path("data/podcast-metadata.json")).values():
        if "image_url" in entry:
            validate_local_episode_artwork(entry["image_url"], Path("."))
    image = Image.open("assets/podcast-cover-v3.jpg")
    if image.size != (3000, 3000) or image.mode != "RGB" or image.format != "JPEG":
        raise SystemExit("podcast cover must be a 3000x3000 RGB JPEG")
    if Path("assets/podcast-cover-v3.jpg").stat().st_size > 1_000_000:
        raise SystemExit("podcast cover is unexpectedly large")
    print({**result, "artwork": f"{image.width}x{image.height} {image.mode}"})


if __name__ == "__main__":
    main()
