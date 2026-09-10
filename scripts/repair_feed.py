"""One-time safe migration for legacy podcast dates, durations, and broken URLs."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from pipeline.podcast import load_episodes, write_feed
from pipeline.publish import validate_feed_file

_BROKEN_TAG = "adhoc-github-copilot-chat-updated-from-last-2-2026-03-02"
_REAL_TAG = "adhoc-github-copilot-chat-updated-from-last-2--2026-03-02"


def _probe_duration(url: str) -> int:
    for attempt in range(2):
        probe_url = url
        if attempt:
            parts = urlsplit(url)
            query = parse_qsl(parts.query, keep_blank_values=True) + [("feed-repair", "1")]
            probe_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", probe_url],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if result.returncode == 0:
            duration = float(json.loads(result.stdout)["format"]["duration"])
            if duration > 0:
                return int(round(duration))
    raise RuntimeError(f"could not measure legacy episode: {url}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", default="podcast.xml")
    parser.add_argument("--probe-durations", action="store_true")
    args = parser.parse_args()
    feed = Path(args.feed)
    episodes = load_episodes(str(feed))
    repaired = 0
    for episode in episodes:
        if _BROKEN_TAG in episode["mp3_url"]:
            episode["mp3_url"] = episode["mp3_url"].replace(_BROKEN_TAG, _REAL_TAG)
            repaired += 1
        if args.probe_durations and not episode.get("duration_secs"):
            episode["duration_secs"] = _probe_duration(episode["mp3_url"])
            print(f"{episode['guid']}: {episode['duration_secs']}s")
    write_feed(episodes, path=str(feed))
    result = validate_feed_file(feed)
    print({**result, "repaired_urls": repaired})


if __name__ == "__main__":
    main()
