"""Build and safely round-trip an Apple-compatible RSS 2.0 podcast feed."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from typing import Dict, List

_ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
_CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
_CHANNEL_TITLE = "Daily AI Developer Brief"
_CHANNEL_DESCRIPTION = (
    "A concise daily briefing of source-backed AI developer-tool changes, "
    "with clear act, watch, or skip guidance."
)
_CHANNEL_IMAGE = "https://johnsirmon.github.io/daily-ai-docs/assets/podcast-cover.jpg"
_CHANNEL_LINK = "https://github.com/johnsirmon/daily-ai-docs"

ET.register_namespace("itunes", _ITUNES_NS)
ET.register_namespace("content", _CONTENT_NS)


def _itunes(tag: str) -> str:
    return f"{{{_ITUNES_NS}}}{tag}"


def _content(tag: str) -> str:
    return f"{{{_CONTENT_NS}}}{tag}"


def _parse_duration(value: str | int | float | None) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(round(value)))
    text = str(value).strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    parts = text.split(":")
    try:
        nums = [int(part) for part in parts]
    except ValueError:
        return 0
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0


def _duration_text(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _coerce_pubdate(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError("episode pub_date is required")
    try:
        if len(text) == 10 and text[4] == "-":
            parsed = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        elif len(text) == 16 and text[3] == ",":
            # Repair the legacy feed format produced by the old truncating loader.
            parsed = datetime.strptime(text, "%a, %d %b %Y").replace(tzinfo=timezone.utc)
        else:
            parsed = parsedate_to_datetime(text)
            if parsed is None:
                raise ValueError
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except ValueError as inner:
            raise ValueError(f"invalid episode pub_date: {text}") from inner
    return format_datetime(parsed.astimezone(timezone.utc), usegmt=False)


def render_feed(episodes: List[Dict], channel_link: str = _CHANNEL_LINK) -> str:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = _CHANNEL_TITLE
    ET.SubElement(channel, "link").text = channel_link
    ET.SubElement(channel, "description").text = _CHANNEL_DESCRIPTION
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "generator").text = "daily-ai-docs"
    ET.SubElement(channel, _itunes("author")).text = "John Sirmon"
    ET.SubElement(channel, _itunes("summary")).text = _CHANNEL_DESCRIPTION
    ET.SubElement(channel, _itunes("explicit")).text = "false"
    ET.SubElement(channel, _itunes("type")).text = "episodic"
    ET.SubElement(channel, _itunes("category"), {"text": "Technology"})
    ET.SubElement(channel, _itunes("image"), {"href": os.environ.get("PODCAST_IMAGE_URL", _CHANNEL_IMAGE)})
    if os.environ.get("PODCAST_MIGRATE_FEED") == "1":
        ET.SubElement(channel, _itunes("new-feed-url")).text = os.environ.get(
            "PODCAST_FEED_URL", "https://johnsirmon.github.io/daily-ai-docs/podcast.xml"
        )

    seen_guids: set[str] = set()
    seen_urls: set[str] = set()
    for episode in episodes:
        guid = str(episode.get("guid") or "").strip()
        url = str(episode.get("mp3_url") or "").strip()
        if not guid or guid in seen_guids:
            raise ValueError(f"missing or duplicate episode GUID: {guid}")
        if not url or url in seen_urls:
            raise ValueError(f"missing or duplicate enclosure URL: {url}")
        length = int(episode.get("file_size_bytes", 0))
        if length <= 0:
            raise ValueError(f"episode {guid} has no measured enclosure length")
        seen_guids.add(guid)
        seen_urls.add(url)

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = str(episode.get("title") or "")
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = guid
        description = str(episode.get("description") or "")
        ET.SubElement(item, "description").text = description
        ET.SubElement(item, _itunes("summary")).text = description
        ET.SubElement(item, _content("encoded")).text = description
        ET.SubElement(item, "pubDate").text = _coerce_pubdate(str(episode.get("pub_date") or ""))
        ET.SubElement(item, "enclosure", {
            "url": url,
            "length": str(length),
            "type": "audio/mpeg",
        })
        duration = _parse_duration(episode.get("duration_secs") or episode.get("duration_str"))
        if duration > 0:
            ET.SubElement(item, _itunes("duration")).text = _duration_text(duration)

    return ET.tostring(rss, encoding="unicode", xml_declaration=False)


def load_episodes(path: str = "podcast.xml") -> List[Dict]:
    feed = Path(path)
    if not feed.exists():
        return []
    try:
        tree = ET.parse(feed)
    except ET.ParseError as exc:
        raise ValueError(f"refusing to overwrite malformed podcast feed: {feed}") from exc
    root = tree.getroot()
    channel = root.find("channel") if root.tag == "rss" else None
    if root.tag != "rss" or channel is None:
        raise ValueError(f"refusing to overwrite structurally invalid podcast feed: {feed}")
    items = channel.findall("item")
    if not items:
        raise ValueError(f"refusing to overwrite existing podcast feed with no episodes: {feed}")
    episodes: List[Dict] = []
    for item in items:
        enclosure = item.find("enclosure")
        if enclosure is None:
            raise ValueError("existing podcast item has no enclosure")
        episodes.append({
            "title": item.findtext("title") or "",
            "guid": item.findtext("guid") or "",
            "mp3_url": enclosure.get("url", ""),
            "file_size_bytes": int(enclosure.get("length") or 0),
            "pub_date": item.findtext("pubDate") or "",
            "duration_secs": _parse_duration(item.findtext(_itunes("duration"))),
            "description": item.findtext("description") or "",
        })
    return episodes


def write_feed(episodes: List[Dict], path: str = "podcast.xml", channel_link: str = _CHANNEL_LINK) -> Path:
    xml = render_feed(episodes, channel_link=channel_link)
    output = Path(path)
    output.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + xml + "\n", encoding="utf-8")
    return output


def prepend_episode(episode: Dict, path: str = "podcast.xml", channel_link: str = _CHANNEL_LINK) -> Path:
    existing = load_episodes(path)
    for current in existing:
        if current.get("guid") == episode.get("guid"):
            if current.get("mp3_url") != episode.get("mp3_url"):
                raise ValueError("refusing to change the enclosure behind an existing GUID")
            return Path(path)
    maximum = int(os.environ.get("PODCAST_MAX_EPISODES", "60"))
    return write_feed([episode] + existing[: max(0, maximum - 1)], path=path, channel_link=channel_link)
