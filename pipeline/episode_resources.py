"""Stage measured-audio chapters, an ASR transcript, and episode art; never upload."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from .audio import file_sha256
from .podcast import set_episode_image
from .publish import validate_episode_artwork, validate_feed_file
from .schema import EpisodeManifest

NAMESPACE = "https://podcastindex.org/namespace/1.0"
BASE = "https://johnsirmon.github.io/daily-ai-docs/"
ET.register_namespace("podcast", NAMESPACE)


def _time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


def stage_resources(bundle: Path, timings: Path, feed: Path, artwork: Path, output: Path) -> dict:
    """Timings must explicitly identify the final encoded MP3 SHA-256."""
    if output.exists() or output.is_symlink():
        raise ValueError("resource output must be new")
    manifest = EpisodeManifest.from_dict(json.loads((bundle / "episode-manifest.json").read_text()))
    digest = file_sha256(bundle / "daily-ai-brief.mp3")
    data = json.loads(timings.read_text())
    if digest != manifest.audio["sha256"] or data.get("audio_sha256") != digest:
        raise ValueError("timings must bind the exact final audio")
    segments = data.get("segments")
    duration = manifest.audio["duration_secs"]
    if not isinstance(segments, list) or not 1 <= len(segments) <= 1000:
        raise ValueError("bounded measured segments required")
    previous = 0.0
    clipped_ends = 0
    vtt = ["WEBVTT", "", "NOTE Automatically transcribed; listening correction pending.", ""]
    for row in segments:
        start, end, text = row.get("start"), row.get("end"), row.get("text")
        if type(start) in (float, int) and type(end) in (float, int):
            start, end = round(start, 3), round(end, 3)
            if duration < end <= duration + 0.5:
                end = duration
                clipped_ends += 1
        if (type(start) not in (float, int) or type(end) not in (float, int)
                or not previous <= start < end <= duration
                or not isinstance(text, str) or not text.strip() or len(text) > 2000):
            raise ValueError("segments must be ordered within measured audio duration")
        vtt += [f"{_time(start)} --> {_time(end)}", html.escape(" ".join(text.split())), ""]
        previous = end
    chapters = data.get("chapters", [])
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= 12:
        raise ValueError("one to twelve measured chapters required")
    last = -1.0
    starts = {row["start"] for row in segments} | {0}
    for row in chapters:
        if (set(row) != {"startTime", "title"} or type(row["startTime"]) not in (int, float)
                or row["startTime"] not in starts or not last < row["startTime"] < duration
                or not isinstance(row["title"], str) or not 1 <= len(row["title"]) <= 44):
            raise ValueError("chapter starts must be measured segment boundaries with short titles")
        last = row["startTime"]
    if chapters[0]["startTime"] != 0:
        raise ValueError("first chapter must begin at zero")
    validate_episode_artwork(artwork.read_bytes())
    tree = ET.parse(feed)
    items = [item for item in tree.getroot().findall("channel/item")
             if item.findtext("guid") == manifest.episode_id]
    if len(items) != 1:
        raise ValueError("candidate feed must contain exactly the bound episode")
    name = manifest.episode_id
    relative = "assets/episodes/" + name
    output.mkdir(parents=True)
    assets = output / "assets/episodes"
    assets.mkdir(parents=True)
    (assets / f"{name}.vtt").write_text("\n".join(vtt), encoding="utf-8")
    chapter_data = {"version": "1.2.0", "chapters": chapters}
    (assets / f"{name}.chapters.json").write_text(json.dumps(chapter_data, indent=2) + "\n")
    shutil.copyfile(artwork, assets / f"{name}.jpg")
    item = items[0]
    for tag in (f"{{{NAMESPACE}}}chapters", f"{{{NAMESPACE}}}transcript"):
        for child in list(item.findall(tag)):
            item.remove(child)
    ET.SubElement(item, f"{{{NAMESPACE}}}chapters", {"url": BASE + relative + ".chapters.json", "type": "application/json+chapters"})
    ET.SubElement(item, f"{{{NAMESPACE}}}transcript", {"url": BASE + relative + ".vtt", "type": "text/vtt", "language": "en"})
    set_episode_image(item, BASE + relative + ".jpg")
    tree.write(output / "podcast.xml", encoding="utf-8", xml_declaration=True)
    validate_feed_file(output / "podcast.xml")
    receipt = {"status": "staged_not_published", "audio_sha256": digest,
               "transcript_status": "raw_ASR_needs_listening_correction", "episode_id": name,
               "asr_ends_clipped_to_measured_duration": clipped_ends,
               "resources": {str(path.relative_to(output)): file_sha256(path)
                             for path in output.rglob("*") if path.is_file()},
               "remote_verified": False}
    (output / "resources-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "timings", "feed", "artwork", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    print(json.dumps(stage_resources(**vars(parser.parse_args())), indent=2))


if __name__ == "__main__":
    main()
