"""Remote publication verification primitives."""

from __future__ import annotations

import email.utils
import hashlib
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import requests
from PIL import Image

_ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


class PublicationError(RuntimeError):
    pass


def verify_remote_audio(
    url: str,
    *,
    expected_size: int,
    expected_sha256: str | None = None,
    session: requests.Session | None = None,
) -> Dict[str, Any]:
    session = session or requests.Session()
    head = session.head(url, allow_redirects=True, timeout=30)
    if head.status_code != 200:
        raise PublicationError(f"audio HEAD returned {head.status_code}")
    size = int(head.headers.get("Content-Length") or 0)
    if size != int(expected_size):
        raise PublicationError(f"audio size mismatch: expected {expected_size}, got {size}")
    ranged = session.get(
        url,
        headers={"Range": "bytes=0-1023"},
        allow_redirects=True,
        timeout=30,
    )
    if ranged.status_code != 206 or not ranged.headers.get("Content-Range", "").startswith("bytes 0-"):
        raise PublicationError("audio host does not honor byte-range requests")
    content_type = head.headers.get("Content-Type", "").split(";", 1)[0].lower()
    if content_type not in {"audio/mpeg", "audio/mp3", "application/octet-stream"}:
        raise PublicationError(f"unexpected audio content type: {content_type}")
    if expected_sha256:
        complete = session.get(url, allow_redirects=True, timeout=60)
        if complete.status_code != 200:
            raise PublicationError(f"full audio verification returned {complete.status_code}")
        actual_sha256 = hashlib.sha256(complete.content).hexdigest()
        if actual_sha256 != expected_sha256:
            raise PublicationError("remote audio checksum does not match the manifest")
    return {
        "status": "ok",
        "size_bytes": size,
        "content_type": content_type,
        "accept_ranges": ranged.headers.get("Accept-Ranges", ""),
        "sha256_verified": bool(expected_sha256),
    }


def validate_feed_file(path: str | Path) -> Dict[str, Any]:
    try:
        root = ET.parse(path)
    except ET.ParseError as exc:
        raise PublicationError("candidate feed is not valid XML") from exc
    document = root.getroot()
    channel = document.find("channel") if document.tag == "rss" else None
    if channel is None:
        raise PublicationError("candidate feed must contain an RSS channel")
    items = channel.findall("item")
    if not items:
        raise PublicationError("candidate feed must retain at least one episode")
    guids: set[str] = set()
    urls: set[str] = set()
    for item in items:
        guid = item.findtext("guid") or ""
        enclosure = item.find("enclosure")
        if not guid or guid in guids or enclosure is None:
            raise PublicationError("feed has missing/duplicate GUID or enclosure")
        url = enclosure.get("url", "")
        if not url or url in urls or int(enclosure.get("length") or 0) <= 0:
            raise PublicationError("feed has missing/duplicate/zero-length enclosure")
        pub_date = item.findtext("pubDate") or ""
        try:
            parsed = email.utils.parsedate_to_datetime(pub_date)
        except (TypeError, ValueError) as exc:
            raise PublicationError(f"invalid RFC publication date: {pub_date}") from exc
        if parsed is None or parsed.tzinfo is None:
            raise PublicationError(f"publication date lacks timezone: {pub_date}")
        guids.add(guid)
        urls.add(url)
    return {"episodes": len(items), "latest_guid": items[0].findtext("guid") if items else ""}


def verify_remote_feed(
    url: str,
    *,
    expected_guid: str | None = None,
    max_age_hours: float = 36,
    session: requests.Session | None = None,
) -> Dict[str, Any]:
    session = session or requests.Session()
    response = session.get(url, headers={"Cache-Control": "no-cache"}, timeout=30)
    if response.status_code != 200:
        raise PublicationError(f"feed GET returned {response.status_code}")
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise PublicationError("remote feed is not valid XML") from exc
    channel = root.find("channel") if root.tag == "rss" else None
    if channel is None:
        raise PublicationError("remote feed has no RSS channel")
    items = channel.findall("item")
    if not items:
        raise PublicationError("remote feed has no episodes")
    latest_guid = items[0].findtext("guid") or ""
    if expected_guid and latest_guid != expected_guid:
        raise PublicationError(f"remote feed latest GUID is {latest_guid}, expected {expected_guid}")
    pub_date = email.utils.parsedate_to_datetime(items[0].findtext("pubDate") or "")
    if pub_date is None:
        raise PublicationError("latest episode has no valid publication date")
    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - pub_date.astimezone(timezone.utc)).total_seconds() / 3600
    if age > max_age_hours:
        raise PublicationError(f"remote feed is stale ({age:.1f} hours)")
    enclosure = items[0].find("enclosure")
    if enclosure is None:
        raise PublicationError("latest remote episode has no enclosure")
    enclosure_url = enclosure.get("url", "")
    enclosure_size = int(enclosure.get("length") or 0)
    verify_remote_audio(enclosure_url, expected_size=enclosure_size, session=session)
    image_node = channel.find(f"{{{_ITUNES_NS}}}image")
    image_url = image_node.get("href", "") if image_node is not None else ""
    if not image_url:
        raise PublicationError("remote feed has no show artwork")
    image_response = session.get(image_url, timeout=30)
    if image_response.status_code != 200:
        raise PublicationError(f"show artwork returned {image_response.status_code}")
    try:
        artwork = Image.open(io.BytesIO(image_response.content))
        width, height = artwork.size
    except Exception as exc:
        raise PublicationError("show artwork is not a decodable image") from exc
    if width != height or not 1400 <= width <= 3000 or artwork.mode not in {"RGB", "L"}:
        raise PublicationError(f"show artwork is not Apple-compatible: {width}x{height} {artwork.mode}")
    return {
        "status": "ok",
        "latest_guid": latest_guid,
        "episode_count": len(items),
        "age_hours": round(age, 2),
        "cache_control": response.headers.get("Cache-Control", ""),
        "audio_verified": True,
        "artwork": f"{width}x{height} {artwork.mode}",
    }
