"""Presentation changes must not republish audio or rewrite accepted evidence."""

import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from pipeline.podcast import description_html, load_episodes, prepend_episode, write_feed
from pipeline.podcast_metadata import load_catalog, manifest_presentation, refresh_catalog
from pipeline.schema import EpisodeManifest, SourceEvent, Story
from scripts.generate_artwork import create_cover

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
ROOT = Path(__file__).resolve().parents[1]


def _manifest():
    event = SourceEvent(
        "event-1", "github_release", "Tool v1.2.3", "https://example.com/releases/v1.2.3",
        "Tool", "Coding", "2026-09-19T10:00:00Z", "2026-09-19T10:01:00Z",
        "What's changed\nAdded a visible warning when memory usage is critical.",
        "primary", "stable", {"version": "v1.2.3"},
    )
    story = Story(
        "story-1", ["event-1"], event.title, event.evidence,
        "Check the warning before starting large tasks.", "watch", "Assess applicability first.",
        [event.url], {"total": 80},
    )
    return EpisodeManifest(
        1, "daily-test", "2026-09-19T10:02:00Z", "published", {"source": "ok:1"},
        [event], [story], [], "A source-backed narration that stays unchanged.",
        "Editorial correction: approval affects member budgets only.\n\n"
        "Research results are author-reported, not independently reproduced.\n"
        "Sources: https://example.com/releases/v1.2.3\n\nCoverage gaps: source-b",
        {"edition": "brief"},
        {"url": "https://example.com/audio.mp3", "size_bytes": 12345, "duration_secs": 61, "sha256": "abc"},
    )


def _setup(tmp_path):
    manifest = _manifest()
    manifests = tmp_path / "episodes"
    manifests.mkdir()
    path = manifests / "daily-test.json"
    path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    feed = tmp_path / "podcast.xml"
    write_feed([{
        "guid": manifest.episode_id, "title": "Daily AI Developer Brief - 2026-09-19",
        "pub_date": manifest.published_at, "mp3_url": manifest.audio["url"],
        "file_size_bytes": 12345, "duration_secs": 61, "description": manifest.show_notes,
    }], str(feed))
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"schema_version": 1, "episodes": {
        "daily-test": {
            "title": "Tool memory warnings: know when to restart",
            "summary": "Tool now warns when memory usage is critical. Check before running large tasks.",
            "evidence_url": "https://github.com/johnsirmon/daily-ai-docs/blob/"
                            + "a" * 40 + "/data/episodes/daily-test.json",
        },
    }}), encoding="utf-8")
    return feed, metadata, manifests


def test_future_copy_is_topic_first_and_does_not_mutate_manifest():
    manifest = _manifest()
    before = copy.deepcopy(manifest.to_dict())
    result = manifest_presentation(manifest)
    assert result["title"] == "Tool: Added a visible warning when memory usage is critical."
    assert "What's changed" not in result["description"].split("\n\n")[0]
    assert result["description"].endswith(manifest.show_notes)
    assert manifest.to_dict() == before


def test_long_copy_is_bounded_without_truncating_complete_notes():
    manifest = _manifest()
    manifest.stories[0] = Story(
        **{**manifest.stories[0].__dict__, "headline": "Agent workflows " * 25,
           "what_changed": "A long source-backed change with important qualifications. " * 20},
    )
    result = manifest_presentation(manifest)
    assert len(result["title"]) <= 90 and result["title"].endswith("...")
    assert len(result["description"].split("\n\n")[0]) <= 480
    assert result["description"].endswith(manifest.show_notes)


def test_quiet_historical_episode_keeps_coverage_disclosure():
    manifest = _manifest()
    manifest.stories = []
    manifest.show_notes = "No update cleared the threshold, but coverage was incomplete."
    result = manifest_presentation(manifest)
    assert result["description"] == manifest.show_notes


def test_link_only_evidence_does_not_become_a_title():
    manifest = _manifest()
    manifest.stories[0] = Story(
        **{**manifest.stories[0].__dict__, "what_changed": "https://example.com/release-notes"},
    )
    assert manifest_presentation(manifest)["title"] == "Tool v1.2.3"


def test_research_preview_keeps_evidence_qualification():
    manifest = _manifest()
    manifest.stories[0] = Story(
        **{**manifest.stories[0].__dict__, "kind": "research"},
    )
    result = manifest_presentation(manifest)
    assert result["title"].startswith("Research:")
    intro = result["description"].split("\n\n")[0]
    assert "author-reported and not independently reproduced" in intro
    assert len(intro) <= 480


def test_description_html_escapes_untrusted_prose_and_links():
    result = description_html('Memory < 8 GB & <script>alert(1)</script>\n\nSource: https://example.com/?a=1&b=2.')
    assert "<script>" not in result
    assert "&lt;script&gt;" in result and "Memory &lt; 8 GB &amp;" in result
    assert '<a href="https://example.com/?a=1&amp;b=2">' in result
    assert result.count("<p>") == 2


def test_migration_preserves_identity_unknown_tags_and_accepted_manifest(tmp_path):
    feed, metadata, manifests = _setup(tmp_path)
    tree = ET.parse(feed)
    item = tree.find("./channel/item")
    assert item is not None
    ET.SubElement(item, "{https://podcastindex.org/namespace/1.0}transcript", {
        "url": "https://example.com/transcript.vtt", "type": "text/vtt",
    })
    ET.SubElement(item, ITUNES + "title").text = "Old Apple title"
    tree.write(feed, encoding="utf-8")
    before = load_episodes(str(feed))[0]
    manifest_bytes = (manifests / "daily-test.json").read_bytes()
    original = feed.read_bytes()
    assert refresh_catalog(feed, metadata, manifests)["written"] == 0
    assert feed.read_bytes() == original
    assert refresh_catalog(feed, metadata, manifests, write=True)["episodes"] == 1
    after = load_episodes(str(feed))[0]
    for key in ("guid", "mp3_url", "file_size_bytes", "pub_date", "duration_secs"):
        assert after[key] == before[key]
    assert (manifests / "daily-test.json").read_bytes() == manifest_bytes
    assert "Editorial correction" in after["description"]
    assert "not independently reproduced" in after["description"]
    assert "Coverage gaps" in after["description"]
    item = ET.parse(feed).find("./channel/item")
    assert item is not None
    assert item.find("{https://podcastindex.org/namespace/1.0}transcript") is not None
    assert item.findtext(ITUNES + "title") == after["title"]
    assert item.findtext(CONTENT + "encoded").startswith("<p>Tool now warns")
    migrated = feed.read_bytes()
    assert refresh_catalog(feed, metadata, manifests, write=True)["changed"] == 0
    assert feed.read_bytes() == migrated


def test_later_prepends_keep_catalog_copy_and_rich_notes(tmp_path):
    feed, metadata, manifests = _setup(tmp_path)
    refresh_catalog(feed, metadata, manifests, write=True)
    old = load_episodes(str(feed))[0]
    prepend_episode({**old, "guid": "daily-next", "mp3_url": "https://example.com/next.mp3"}, str(feed))
    assert load_episodes(str(feed))[1] == old
    channel = ET.parse(feed).find("channel")
    assert channel is not None
    assert channel.find(ITUNES + "image").get("href").endswith("podcast-cover-v3.jpg")
    assert channel.findtext("image/url") == channel.find(ITUNES + "image").get("href")
    assert channel.findall("item")[1].findtext(CONTENT + "encoded").startswith("<p>")


def test_missing_legacy_evidence_fails_without_writing(tmp_path):
    feed, metadata, manifests = _setup(tmp_path)
    tree = ET.parse(feed)
    tree.find("./channel/item/guid").text = "unknown-legacy"
    tree.write(feed)
    before = feed.read_bytes()
    with pytest.raises(ValueError, match="no accepted manifest"):
        refresh_catalog(feed, metadata, manifests, write=True)
    assert feed.read_bytes() == before


@pytest.mark.parametrize("field,value", [
    ("url", "https://example.com/wrong.mp3"), ("size_bytes", 12346), ("duration_secs", 62),
])
def test_mismatched_accepted_media_fails_closed(tmp_path, field, value):
    feed, metadata, manifests = _setup(tmp_path)
    path = manifests / "daily-test.json"
    data = json.loads(path.read_text())
    data["audio"][field] = value
    path.write_text(json.dumps(data))
    before = feed.read_bytes()
    with pytest.raises(ValueError, match="does not match feed media"):
        refresh_catalog(feed, metadata, manifests, write=True)
    assert feed.read_bytes() == before


def test_mismatched_accepted_date_fails_closed(tmp_path):
    feed, metadata, manifests = _setup(tmp_path)
    path = manifests / "daily-test.json"
    data = json.loads(path.read_text())
    data["published_at"] = "2026-09-20T10:02:00Z"
    path.write_text(json.dumps(data))
    before = feed.read_bytes()
    with pytest.raises(ValueError, match="does not match"):
        refresh_catalog(feed, metadata, manifests, write=True)
    assert feed.read_bytes() == before


def test_draft_is_not_accepted_as_catalog_evidence(tmp_path):
    feed, metadata, manifests = _setup(tmp_path)
    path = manifests / "daily-test.json"
    data = json.loads(path.read_text())
    data["status"] = "draft"
    path.write_text(json.dumps(data))
    before = feed.read_bytes()
    with pytest.raises(ValueError, match="requires an accepted publication"):
        refresh_catalog(feed, metadata, manifests, write=True)
    assert feed.read_bytes() == before


@pytest.mark.parametrize("field,value", [
    ("title", ""), ("title", "x" * 91), ("summary", "x" * 481),
    ("summary", "<script>unsafe</script>"), ("evidence_url", "https://example.com/unreviewed"),
])
def test_catalog_rejects_invalid_copy(tmp_path, field, value):
    _, metadata, _ = _setup(tmp_path)
    data = json.loads(metadata.read_text())
    data["episodes"]["daily-test"][field] = value
    metadata.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_catalog(metadata)


def test_new_manifest_not_in_backfill_uses_future_presentation(tmp_path):
    feed, metadata, manifests = _setup(tmp_path)
    data = json.loads(metadata.read_text())
    data["episodes"]["older-guid"] = data["episodes"].pop("daily-test")
    metadata.write_text(json.dumps(data))
    refresh_catalog(feed, metadata, manifests, write=True)
    assert load_episodes(str(feed))[0]["title"].startswith("Tool: Added")


def test_committed_catalog_covers_retained_history():
    catalog = load_catalog(ROOT / "data/podcast-metadata.json")
    episodes = load_episodes(str(ROOT / "podcast.xml"))
    for episode in episodes:
        if episode["guid"] in catalog:
            entry = catalog[episode["guid"]]
            assert episode["title"] == entry["title"]
            assert episode["description"].startswith(entry["summary"] + "\n\n")
        else:
            assert (ROOT / "data/episodes" / f"{episode['guid']}.json").exists()


def test_show_artwork_has_small_screen_safe_format_and_quiet_background():
    image = create_cover()
    assert image.size == (3000, 3000) and image.mode == "RGB"
    assert max(image.getpixel((0, 0))) < 60
    with Image.open(ROOT / "assets/podcast-cover-v3.jpg") as saved:
        assert saved.format == "JPEG" and saved.mode == "RGB" and saved.size == image.size
        assert saved.getpixel((0, 0))[0] < 12
    assert (ROOT / "assets/podcast-cover-v3.jpg").stat().st_size < 1_000_000
    assert (ROOT / "assets/podcast-cover-v2.jpg").is_file()
