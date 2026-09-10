"""CLI health check for the subscriber-facing podcast feed."""

from __future__ import annotations

import argparse
import json
import os
import time

from .publish import PublicationError, verify_remote_feed


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the public daily podcast feed")
    parser.add_argument(
        "--feed-url",
        default=os.environ.get("PODCAST_FEED_URL", "https://johnsirmon.github.io/daily-ai-docs/podcast.xml"),
    )
    parser.add_argument("--expected-guid", default=os.environ.get("EXPECTED_GUID"))
    parser.add_argument("--max-age-hours", type=float, default=36)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--delay-seconds", type=float, default=15)
    args = parser.parse_args()
    last_error = None
    for attempt in range(max(1, args.retries)):
        try:
            result = verify_remote_feed(
                args.feed_url,
                expected_guid=args.expected_guid,
                max_age_hours=args.max_age_hours,
            )
            print(json.dumps(result, indent=2))
            return
        except PublicationError as exc:
            last_error = exc
            if attempt + 1 < max(1, args.retries):
                time.sleep(max(0, args.delay_seconds))
    raise SystemExit(f"feed health failed: {last_error}")


if __name__ == "__main__":
    main()
