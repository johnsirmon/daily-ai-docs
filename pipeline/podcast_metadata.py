"""Listener-facing copy derived from accepted evidence, without rewriting history."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .disclosure import episode_metadata_disclosure
from .podcast import _coerce_pubdate, _parse_duration, set_episode_presentation, set_show_presentation
from .publish import validate_feed_file
from .schema import EpisodeManifest, Story
from .sources.text import bounded_text, clean_source_text

TITLE_LIMIT = 90
SUMMARY_LIMIT = 480


def _preview(text: str, limit: int) -> str:
    clean = " ".join(clean_source_text(text, limit=None).split())
    if len(clean) <= limit:
        return clean
    return bounded_text(clean, limit - 3).rstrip(" .") + "..."


def _change(story: Story) -> str:
    text = clean_source_text(story.what_changed, limit=None)
    text = re.sub(
        r"^(?:(?:what(?:'s| is) changed|new features|bug fixes(?!\s+and\b)|release notes)\s*[:\-]?\s*)+",
        "", text, flags=re.I,
    )
    return text.lstrip("- ").strip()


def manifest_presentation(manifest: EpisodeManifest) -> dict[str, str]:
    """Use extractive previews; all qualifications remain in the complete notes."""
    manifest.validate(require_audio=False)
    disclosure = episode_metadata_disclosure(manifest.schema_version)
    if not manifest.stories:
        return {
            "title": "No actionable updates in this brief",
            "description": "\n\n".join(part for part in (disclosure, manifest.show_notes) if part),
        }
    lead = manifest.stories[0]
    headline = lead.headline
    by_id = {event.event_id: event for event in manifest.source_events}
    event = by_id[lead.event_ids[0]]
    change = _change(lead)
    if (event.source_type == "github_release" and headline == event.title
            and change and not re.fullmatch(r"https://\S+", change)):
        headline = f"{event.product}: {change}"
    if manifest.schema_version == 4:
        headline = manifest.generation["request"]["topic"]
    if lead.kind == "research":
        headline = "Research: " + headline
    title = _preview(headline, TITLE_LIMIT)
    summary = _preview(f"{lead.headline}: {change}", 300)
    if summary and summary[-1] not in ".!?":
        summary += "."
    other = list(dict.fromkeys(story.headline for story in manifest.stories[1:]))
    if other:
        summary += " Also covered: " + _preview("; ".join(other), 145)
        if summary[-1] not in ".!?":
            summary += "."
    if manifest.schema_version == 4:
        summary = _preview(manifest.generation["request"]["topic"], 120) + ". " + summary
    if lead.kind == "research":
        summary = "Research, author-reported and not independently reproduced. " + summary
    summary = _preview(summary, SUMMARY_LIMIT)
    edition = {
        3: "Notebook edition. Reviewed AI-generated conversation.",
        4: "Special episode. Reviewed long-form audio.",
    }.get(manifest.schema_version, "")
    parts = [summary, disclosure, edition, manifest.show_notes]
    return {"title": title, "description": "\n\n".join(part for part in parts if part)}


def load_catalog(path: Path) -> dict[str, dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"schema_version", "episodes"} or data["schema_version"] != 1:
        raise ValueError("podcast metadata requires schema_version 1 and episodes")
    entries = data["episodes"]
    if not isinstance(entries, dict) or not entries:
        raise ValueError("podcast metadata episodes must be a nonempty object")
    for guid, entry in entries.items():
        if not isinstance(guid, str) or not guid or not isinstance(entry, dict):
            raise ValueError("invalid podcast metadata entry")
        if set(entry) != {"title", "summary", "evidence_url"}:
            raise ValueError(f"{guid}: title, summary and evidence_url are required")
        for key, limit in (("title", TITLE_LIMIT), ("summary", SUMMARY_LIMIT), ("evidence_url", 500)):
            value = entry[key]
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"{guid}: invalid {key}")
            if "\n" in value or "<" in value or ">" in value:
                raise ValueError(f"{guid}: {key} must be plain single-line text")
        if not re.fullmatch(
            r"https://github\.com/johnsirmon/daily-ai-docs/blob/[0-9a-f]{40}/"
            r"(?:README\.md|data/episodes/[\w.-]+\.json|podcast\.xml)",
            entry["evidence_url"],
        ):
            raise ValueError(f"{guid}: evidence_url must be an immutable public archive permalink")
    return entries


def refresh_catalog(
    feed_path: Path,
    metadata_path: Path,
    manifest_dir: Path,
    *,
    write: bool = False,
) -> dict[str, int]:
    """Explicit, atomic, idempotent display-only migration of the retained feed."""
    validate_feed_file(feed_path)
    entries = load_catalog(metadata_path)
    original = feed_path.read_bytes()
    root = ET.fromstring(original)
    channel = root.find("channel")
    assert channel is not None  # Validated above.
    count = 0
    for item in channel.findall("item"):
        guid = item.findtext("guid") or ""
        # Only use the GUID as an index, never as an unchecked filesystem path.
        manifest = None
        if re.fullmatch(r"[\w.-]+", guid):
            path = manifest_dir / f"{guid}.json"
            if path.exists():
                manifest = EpisodeManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
                manifest.validate(require_audio=True)
                if manifest.status not in {"candidate", "published"}:
                    raise ValueError(f"{guid}: metadata refresh requires an accepted publication")
                enclosure = item.find("enclosure")
                assert enclosure is not None
                if (
                    manifest.episode_id != guid
                    or _coerce_pubdate(manifest.published_at) != _coerce_pubdate(item.findtext("pubDate") or "")
                    or manifest.audio["url"] != enclosure.get("url")
                    or int(manifest.audio["size_bytes"]) != int(enclosure.get("length", "0"))
                    or _parse_duration(manifest.audio["duration_secs"]) != _parse_duration(
                        item.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration")
                    )
                ):
                    raise ValueError(f"{guid}: accepted manifest does not match feed media or date")
        if guid in entries:
            entry = entries[guid]
            notes = manifest.show_notes if manifest else "Original publication: " + entry["evidence_url"]
            presentation = {"title": entry["title"], "description": entry["summary"] + "\n\n" + notes}
        elif manifest is not None:
            presentation = manifest_presentation(manifest)
        else:
            raise ValueError(f"{guid}: no accepted manifest or reviewed catalog copy; feed unchanged")
        set_episode_presentation(item, **presentation)
        count += 1
    set_show_presentation(channel, channel.findtext("link") or "https://github.com/johnsirmon/daily-ai-docs")
    xml = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8") + b"\n"
    if write:
        # Validate the complete replacement before swapping; never leave a partial feed.
        with tempfile.NamedTemporaryFile(dir=feed_path.parent, suffix=".xml", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(xml)
        try:
            validate_feed_file(temporary)
            if feed_path.read_bytes() != original:
                raise RuntimeError("feed changed during metadata refresh; retry from current feed")
            temporary.replace(feed_path)
        finally:
            temporary.unlink(missing_ok=True)
    return {"episodes": count, "changed": int(original != xml), "written": int(write)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, default=Path("podcast.xml"))
    parser.add_argument("--metadata", type=Path, default=Path("data/podcast-metadata.json"))
    parser.add_argument("--manifests", type=Path, default=Path("data/episodes"))
    parser.add_argument("--write", action="store_true", help="apply display-only changes; default is validation only")
    args = parser.parse_args()
    print(refresh_catalog(args.feed, args.metadata, args.manifests, write=args.write))


if __name__ == "__main__":
    main()
