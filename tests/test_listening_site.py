from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from typing import cast

import pytest

import pipeline.listening_site as site
from pipeline.listening_site import ListeningSiteError, build_site
from pipeline.schema import EpisodeManifest, SourceEvent, Story, editorial_narration
from tests.test_adhoc import long_draft
from tests.test_reviewed_audio import corrected_draft


ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ROOT = Path(__file__).resolve().parents[1]


def _audio(url: str, *, duration: float = 125.0, size: int = 12345) -> dict:
    return {
        "url": url,
        "size_bytes": size,
        "duration_secs": duration,
        "sha256": "a" * 64,
        "codec": "mp3",
        "sample_rate": 24000,
        "channels": 1,
    }


def _manifest(
    guid: str,
    url: str,
    *,
    status: str = "published",
    published_at: str = "2026-09-22T14:58:41Z",
    title: str = "Accepted <change>",
) -> EpisodeManifest:
    event = SourceEvent(
        event_id="event-1",
        source_type="announcement",
        title="Source title",
        url="https://example.com/source",
        product="Tool",
        topic="Agents",
        published_at="2026-09-22T12:00:00Z",
        fetched_at="2026-09-22T13:00:00Z",
        evidence="Accepted evidence.",
    )
    story = Story(
        story_id="story-1",
        event_ids=[event.event_id],
        headline=title,
        what_changed="The accepted change shipped.",
        why_it_matters="It changes a documented workflow.",
        action="watch",
        rationale="Read the source before changing anything.",
        source_urls=[event.url],
        scores={"authority": 1.0},
    )
    return EpisodeManifest(
        schema_version=1,
        episode_id=guid,
        published_at=published_at,
        status=status,
        source_health={"synthetic": "ok:1"},
        source_events=[event],
        stories=[story],
        noise_notes=["A coverage <gap> remains."],
        narration="Accepted narration is deliberately not rendered.",
        show_notes="Accepted show notes <not HTML>.",
        generation={"provider": "deterministic", "calls": 0},
        audio=_audio(url),
    )


def _schema2_manifest(guid: str, url: str) -> EpisodeManifest:
    evidence = "The authors used a paired repository evaluation. The sample is narrow and results were not reproduced."
    event = SourceEvent(
        event_id="paper-1",
        source_type="research_paper",
        title="A bounded agent evaluation",
        url="https://arxiv.org/abs/2609.12345",
        product="Research",
        topic="Agent evaluation",
        published_at="2026-09-21T00:00:00Z",
        fetched_at="2026-09-22T00:00:00Z",
        evidence=evidence,
        metadata={
            "paper_id": "2609.12345",
            "version": 1,
            "first_published_at": "2026-09-21T00:00:00Z",
            "updated_at": "2026-09-21T00:00:00Z",
            "full_text_available": True,
            "full_text_retained": False,
            "reviewed_excerpts": evidence,
            "evidence_status": "reviewed_excerpts",
        },
    )
    limitation = "The sample is narrow and results were not reproduced."
    story = Story(
        story_id="research-1",
        event_ids=[event.event_id],
        headline="A bounded agent evaluation",
        what_changed="A research paper reports a paired repository evaluation.",
        why_it_matters="The design may help compare agent setups.",
        action="watch",
        rationale="Treat the result as a hypothesis until it is reproduced.",
        source_urls=[event.url],
        scores={"authority": 1.0},
        kind="research",
        editorial={
            "spoken_text": (
                "This research is author-reported and not independently reproduced. " + limitation
            ),
            "claims": [{
                "text": "The authors used a paired repository evaluation.",
                "event_id": event.event_id,
                "quote": "The authors used a paired repository evaluation.",
            }],
            "paper_review": {
                "question": "Can paired repository tasks compare agent setups?",
                "method": "The authors used a paired repository evaluation.",
                "result": "The paper reports a bounded comparison.",
                "limitations": limitation,
                "takeaway": "Repeat representative tasks before choosing a setup.",
                "evidence_status": "author_reported_not_reproduced",
            },
        },
    )
    generation = {
        "provider": "gemini",
        "verified": True,
        "editorial_version": 1,
        "calls": 2,
        "model": "gemini-synthetic",
        "opening": "A bounded research review follows.",
        "closing": "Read the primary paper before acting.",
    }
    return EpisodeManifest(
        schema_version=2,
        episode_id=guid,
        published_at="2026-09-22T14:58:41Z",
        status="published",
        source_health={"research": "ok:1"},
        source_events=[event],
        stories=[story],
        noise_notes=[],
        narration=editorial_narration([story], generation),
        show_notes="Synthetic schema-two show notes.",
        generation=generation,
        audio=_audio(url),
    )


def _schema3_manifest() -> EpisodeManifest:
    data = corrected_draft()
    data["status"] = "published"
    data["audio"].update({
        "size_bytes": 12345,
        "duration_secs": 400.0,
        "sha256": "b" * 64,
        "codec": "mp3",
        "sample_rate": 44100,
        "channels": 2,
    })
    return EpisodeManifest.from_dict(data)


def _schema4_manifest() -> EpisodeManifest:
    data = long_draft(ready=True, publish_now=True)
    data["status"] = "published"
    data["stories"][0]["what_changed"] = "The accepted source records a command-preview change."
    data["stories"][0]["rationale"] = (
        "A paper-only evaluation is proposed, not a verified shipped workflow or measured benefit."
    )
    data["show_notes"] = (
        "The command-preview change is accepted evidence. The evaluation workflow is a proposal, "
        "not a verified shipped feature."
    )
    return EpisodeManifest.from_dict(data)


def _record_for_manifest(manifest: EpisodeManifest) -> dict:
    published = datetime.fromisoformat(manifest.published_at.replace("Z", "+00:00"))
    return {
        "guid": manifest.episode_id,
        "url": manifest.audio["url"],
        "date": format_datetime(published),
        "length": manifest.audio["size_bytes"],
        "duration": str(round(manifest.audio["duration_secs"])),
    }


def _write_feed(path: Path, records: list[dict]) -> None:
    ET.register_namespace("itunes", ITUNES)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    for record in records:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = record.get("title", "Episode <title>")
        ET.SubElement(item, "guid").text = record["guid"]
        ET.SubElement(item, "pubDate").text = record.get("date", "Tue, 22 Sep 2026 14:58:41 +0000")
        ET.SubElement(item, "description").text = record.get("description", "Accepted archive <copy>.")
        ET.SubElement(item, "enclosure", {
            "url": record["url"],
            "length": str(record.get("length", 12345)),
            "type": record.get("type", "audio/mpeg"),
        })
        ET.SubElement(item, f"{{{ITUNES}}}duration").text = record.get("duration", "2:05")
    path.write_bytes(ET.tostring(rss, encoding="utf-8", xml_declaration=True))


def _write_manifest(directory: Path, manifest: EpisodeManifest) -> None:
    directory.mkdir(exist_ok=True)
    (directory / (hashlib.sha256(manifest.episode_id.encode()).hexdigest() + ".json")).write_text(
        json.dumps(manifest.to_dict()), encoding="utf-8"
    )


def _fixture(tmp_path: Path, *, manifest: EpisodeManifest | None = None, record: dict | None = None):
    source = tmp_path / "source"
    source.mkdir()
    feed = source / "feed.xml"
    manifests = source / "manifests"
    manifests.mkdir()
    css = source / "site.css"
    css.write_text("body { color: black; }\n", encoding="utf-8")
    url = "https://example.com/audio.mp3"
    record = record or {"guid": "episode-1", "url": url}
    _write_feed(feed, [record])
    if manifest is None:
        manifest = _manifest(record["guid"], url)
    _write_manifest(manifests, manifest)
    return feed, manifests, css


def _tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(item.relative_to(path).as_posix().encode())
            digest.update(item.read_bytes())
    return digest.hexdigest()


def test_build_is_deterministic_escapes_content_and_preserves_inputs(tmp_path: Path) -> None:
    feed, manifests, css = _fixture(tmp_path)
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (feed, css, *manifests.iterdir())}
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=first)
    build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=second)
    assert report["episodes"] == 1
    assert _tree_hash(first) == _tree_hash(second)
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
    page = next(first.glob("episode-*.html")).read_text(encoding="utf-8")
    assert "Accepted &lt;change&gt;" in page
    assert "Accepted show notes &lt;not HTML&gt;" in page
    assert "<script" not in page
    assert 'preload="none"' in page and "autoplay" not in page
    assert "Accepted narration is deliberately not rendered" not in page


@pytest.mark.parametrize("field,value", [
    ("url", "file:///private/audio.mp3"),
    ("url", "http://127.0.0.1/audio.mp3"),
    ("url", "https://127.1/audio.mp3"),
    ("url", "https://0177.0.0.1/audio.mp3"),
    ("url", "https://%31%32%37.0.0.1/audio.mp3"),
    ("url", "https://127.0.0.1\\.example.com/audio.mp3"),
    ("url", "https://127.0.0.0x1/audio.mp3"),
    ("url", "https://0x7f.0x0.0x0.0x1/audio.mp3"),
    ("url", "https://127.0.0.0x/audio.mp3"),
    ("url", "https://127.0.0X/audio.mp3"),
    ("url", "https://example.com/audio%0a.mp3"),
    ("url", "https://example.com/audio file.mp3"),
    ("type", "text/html"),
    ("length", 0),
    ("duration", "0:00"),
])
def test_rejects_unsafe_or_malformed_feed_media(tmp_path: Path, field: str, value: object) -> None:
    record = {"guid": "episode-1", "url": "https://example.com/audio.mp3", field: value}
    feed, manifests, css = _fixture(tmp_path, record=record)
    output = tmp_path / "output"
    with pytest.raises(ListeningSiteError):
        build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    assert not output.exists()


@pytest.mark.parametrize("url", [
    "https://127.0.0.0x1/source",
    "https://0x7f.0x0.0x0.0x1/source",
    "https://127.0.0.0x/source",
    "https://127.0.0X/source",
])
def test_rejects_hex_numeric_rendered_links_and_cleans_output(tmp_path: Path, url: str) -> None:
    manifest = _manifest("episode-1", "https://example.com/audio.mp3")
    manifest.source_events[0] = replace(manifest.source_events[0], url=url)
    manifest.stories[0].source_urls[:] = [url]
    manifest.validate(require_audio=True)
    feed, manifests, css = _fixture(tmp_path, manifest=manifest)
    output = tmp_path / "output"
    with pytest.raises(ListeningSiteError, match="ambiguous host"):
        build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    assert not output.exists()


@pytest.mark.parametrize("url", [
    "https://example.com/a%20b.mp3?download=1&x=2",
    "https://8.8.8.8/audio.mp3",
    "https://[2606:4700:4700::1111]/audio.mp3",
])
def test_public_url_validation_preserves_accepted_bytes(url: str) -> None:
    assert site._public_url(url, "test") == url


@pytest.mark.parametrize("change", ["url", "length", "duration", "date"])
def test_rejects_manifest_media_mismatch_without_output(tmp_path: Path, change: str) -> None:
    url = "https://example.com/audio.mp3"
    manifest = _manifest("episode-1", url)
    record = {"guid": "episode-1", "url": url}
    if change == "url":
        record["url"] = "https://example.com/other.mp3"
    elif change == "length":
        record["length"] = "99999"
    elif change == "duration":
        record["duration"] = "2:06"
    else:
        record["date"] = "Wed, 23 Sep 2026 14:58:41 +0000"
    feed, manifests, css = _fixture(tmp_path, manifest=manifest, record=record)
    output = tmp_path / "output"
    with pytest.raises(ListeningSiteError, match="mismatch"):
        build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    assert not output.exists()


def test_traversal_guid_uses_deterministic_encoded_filename(tmp_path: Path) -> None:
    guid = "../../outside<script>"
    url = "https://example.com/audio.mp3"
    feed, manifests, css = _fixture(tmp_path, manifest=_manifest(guid, url), record={"guid": guid, "url": url})
    output = tmp_path / "output"
    build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    pages = list(output.glob("episode-*.html"))
    assert len(pages) == 1
    assert pages[0].name == f"episode-{hashlib.sha256(guid.encode()).hexdigest()}.html"
    assert not (tmp_path / "outside<script>").exists()


def test_rejects_symlink_input_and_output_overlap(tmp_path: Path) -> None:
    feed, manifests, css = _fixture(tmp_path)
    linked_feed = tmp_path / "linked.xml"
    linked_feed.symlink_to(feed)
    with pytest.raises(ListeningSiteError, match="symlink"):
        build_site(feed_path=linked_feed, manifest_dir=manifests, stylesheet_path=css, output_dir=tmp_path / "out")
    with pytest.raises(ListeningSiteError, match="outside"):
        build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=manifests / "out")


def test_existing_output_is_untouched(tmp_path: Path) -> None:
    feed, manifests, css = _fixture(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_bytes(b"do-not-replace")
    with pytest.raises(ListeningSiteError, match="new path"):
        build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    assert marker.read_bytes() == b"do-not-replace"


def test_draft_gets_no_page_and_candidate_is_not_confirmed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    feed = source / "feed.xml"
    manifests = source / "manifests"
    manifests.mkdir()
    css = source / "site.css"
    css.write_text("body{}", encoding="utf-8")
    url1 = "https://example.com/draft.mp3"
    url2 = "https://example.com/candidate.mp3"
    _write_feed(feed, [
        {"guid": "draft-1", "url": url1},
        {"guid": "candidate-1", "url": url2},
    ])
    _write_manifest(manifests, _manifest("draft-1", url1, status="draft"))
    _write_manifest(manifests, _manifest("candidate-1", url2, status="candidate"))
    output = tmp_path / "output"
    report = build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    assert report["drafts_skipped"] == 1 and report["episodes"] == 1
    combined = "\n".join(path.read_text(encoding="utf-8") for path in output.glob("*.html"))
    assert "draft-1" not in combined
    assert "Candidate — not confirmed" in combined
    assert "Confirmed" not in combined
    copy_output = tmp_path / "copy-output"
    with pytest.raises(ListeningSiteError, match="cannot copy RSS"):
        build_site(
            feed_path=feed,
            manifest_dir=manifests,
            stylesheet_path=css,
            output_dir=copy_output,
            copy_feed=True,
        )
    assert not copy_output.exists()


def test_missing_receipt_is_irrelevant_and_legacy_copy_is_limited(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    feed = source / "feed.xml"
    manifests = source / "manifests"
    manifests.mkdir()
    css = source / "site.css"
    css.write_text("body{}", encoding="utf-8")
    _write_feed(feed, [{"guid": "legacy-1", "url": "https://example.com/legacy.mp3"}])
    catalog = source / "catalog.json"
    catalog.write_text(json.dumps({
        "schema_version": 1,
        "episodes": {
            "legacy-1": {
                "title": "Reviewed archive title",
                "summary": "Reviewed accepted archive copy.",
                "evidence_url": "https://github.com/johnsirmon/daily-ai-docs/blob/" + "a" * 40 + "/podcast.xml",
            }
        },
    }), encoding="utf-8")
    output = tmp_path / "output"
    report = build_site(
        feed_path=feed,
        manifest_dir=manifests,
        stylesheet_path=css,
        metadata_path=catalog,
        output_dir=output,
    )
    assert report["legacy"] == 1
    page = next(output.glob("episode-*.html")).read_text(encoding="utf-8")
    assert "Limited historical record" in page
    assert "Claims and recommendations are not reconstructed" in page
    assert "Reviewed accepted archive copy" in page


def test_schema2_research_fields_are_rendered(tmp_path: Path) -> None:
    guid = "schema2-episode"
    url = "https://example.com/audio.mp3"
    manifest = _schema2_manifest(guid, url)
    feed, manifests, css = _fixture(tmp_path, manifest=manifest, record={"guid": guid, "url": url})
    output = tmp_path / "output"
    build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    page = next(output.glob("episode-*.html")).read_text(encoding="utf-8")
    for expected in ("Experiment / question", "Method", "Author-reported result", "Limitations", "Evidence status"):
        assert expected in page
    assert "author_reported_not_reproduced" in page


@pytest.mark.parametrize("schema", [1, 2, 3, 4])
def test_isolated_schema_semantics(schema: int, tmp_path: Path) -> None:
    url = "https://example.com/audio.mp3"
    manifests_by_schema = {
        1: _manifest("schema-1", url),
        2: _schema2_manifest("schema-2", url),
        3: _schema3_manifest(),
        4: _schema4_manifest(),
    }
    manifest = manifests_by_schema[schema]
    feed, manifests, css = _fixture(
        tmp_path, manifest=manifest, record=_record_for_manifest(manifest)
    )
    output = tmp_path / "output"
    build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    page = next(output.glob("episode-*.html")).read_text(encoding="utf-8")
    assert "Cited sources" in page and "Primary sources" not in page
    assert "Existing public podcast feed (subscription RSS)" in page
    if schema == 1:
        assert "<strong>WATCH</strong>" in page
        assert "September 22, 2026 at 14:58 UTC" in page
    elif schema == 2:
        assert "The sample is narrow and results were not reproduced" in page
        assert "author_reported_not_reproduced" in page
    elif schema == 3:
        correction = "member&#x27;s budget, not the organization&#x27;s budget"
        assert page.index(correction) < page.index("<strong>WATCH</strong>")
    else:
        assert "proposed, not a verified shipped workflow or measured benefit" in page
        assert "proposal, not a verified shipped feature" in page


def test_current_repository_smoke_uses_derived_invariants(tmp_path: Path) -> None:
    output = tmp_path / "current"
    channel = ET.parse(ROOT / "podcast.xml").getroot().find("channel")
    assert channel is not None
    feed_items = channel.findall("item")
    feed_guids = {item.findtext("guid") for item in feed_items}
    accepted = 0
    drafts = 0
    for path in (ROOT / "data" / "episodes").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["episode_id"] not in feed_guids:
            continue
        if data["status"] == "draft":
            drafts += 1
        elif data["status"] in {"candidate", "published"}:
            accepted += 1
    report = build_site(
        feed_path=ROOT / "podcast.xml",
        manifest_dir=ROOT / "data" / "episodes",
        stylesheet_path=ROOT / "assets" / "listening-site.css",
        metadata_path=ROOT / "data" / "podcast-metadata.json",
        output_dir=output,
    )
    assert report["episodes"] == len(feed_items) - drafts
    assert report["detailed"] == accepted
    assert cast(int, report["detailed"]) + cast(int, report["legacy"]) == report["episodes"]


def test_publication_rollover_adds_episode_without_invalidating_prior_output(tmp_path: Path) -> None:
    first = _manifest("daily-first", "https://example.com/first.mp3")
    feed, manifests, css = _fixture(
        tmp_path, manifest=first, record=_record_for_manifest(first)
    )
    initial = tmp_path / "initial"
    initial_report = build_site(
        feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=initial
    )
    second = _manifest(
        "daily-next", "https://example.com/next.mp3", published_at="2026-09-23T14:58:41Z"
    )
    _write_manifest(manifests, second)
    _write_feed(feed, [_record_for_manifest(second), _record_for_manifest(first)])
    rollover = tmp_path / "rollover"
    rollover_report = build_site(
        feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=rollover
    )
    assert rollover_report["episodes"] == cast(int, initial_report["episodes"]) + 1
    first_name = f"episode-{hashlib.sha256(first.episode_id.encode()).hexdigest()}.html"
    assert (rollover / first_name).is_file()


def test_feed_snapshot_is_coherent_when_source_changes_mid_build(tmp_path: Path, monkeypatch) -> None:
    feed, manifests, css = _fixture(tmp_path)
    original = feed.read_bytes()
    loader = site._load_manifests

    def changing_loader(directory: Path):
        loaded = loader(directory)
        tree = ET.parse(feed)
        title = tree.find("./channel/item/title")
        assert title is not None
        title.text = "CHANGED-AFTER-SNAPSHOT"
        tree.write(feed, encoding="utf-8", xml_declaration=True)
        return loaded

    monkeypatch.setattr(site, "_load_manifests", changing_loader)
    output = tmp_path / "output"
    report = build_site(
        feed_path=feed,
        manifest_dir=manifests,
        stylesheet_path=css,
        output_dir=output,
        copy_feed=True,
    )
    assert (output / "assets/source-feed.xml").read_bytes() == original
    assert report["feed_sha256"] == hashlib.sha256(original).hexdigest()
    assert "CHANGED-AFTER-SNAPSHOT" not in (output / "index.html").read_text(encoding="utf-8")


def test_output_reservation_loses_race_without_clobbering(tmp_path: Path, monkeypatch) -> None:
    feed, manifests, css = _fixture(tmp_path)
    output = tmp_path / "output"
    original_mkdir = Path.mkdir
    raced = False

    def racing_mkdir(path: Path, *args, **kwargs):
        nonlocal raced
        if path == output and not raced:
            raced = True
            original_mkdir(path, *args, **kwargs)
            (path / "other-owner.txt").write_bytes(b"preserve")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", racing_mkdir)
    with pytest.raises(ListeningSiteError, match="another owner"):
        build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    assert (output / "other-owner.txt").read_bytes() == b"preserve"
    assert not (output / "index.html").exists()


def test_utf16_entity_feed_is_rejected_before_xml_parse(tmp_path: Path) -> None:
    feed, manifests, css = _fixture(tmp_path)
    tree = ET.parse(feed)
    title = tree.find("./channel/item/title")
    assert title is not None
    title.text = "ENTITY_PLACEHOLDER"
    xml = ET.tostring(tree.getroot(), encoding="unicode").replace("ENTITY_PLACEHOLDER", "&review;")
    xml = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        '<!DOCTYPE rss [<!ENTITY review "EXPANDED">]>' + xml
    )
    feed.write_bytes(xml.encode("utf-16"))
    output = tmp_path / "output"
    with pytest.raises(ListeningSiteError, match="UTF-8"):
        build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    assert not output.exists()


def test_cited_sources_do_not_upgrade_secondary_or_corroboration(tmp_path: Path) -> None:
    manifest = _manifest("episode-1", "https://example.com/audio.mp3")
    secondary = replace(
        manifest.source_events[0],
        event_id="secondary-event",
        authority="secondary",
        url="https://secondary.example.com/report",
        metadata={},
    )
    manifest.source_events[0].metadata["corroboration_urls"] = [
        "https://corroboration.example.com/report"
    ]
    manifest.source_events.append(secondary)
    manifest.stories[0].event_ids.append(secondary.event_id)
    manifest.stories[0].source_urls[:] = [
        manifest.source_events[0].url,
        "https://corroboration.example.com/report",
        secondary.url,
    ]
    manifest.validate(require_audio=True)
    feed, manifests, css = _fixture(tmp_path, manifest=manifest)
    output = tmp_path / "output"
    build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    page = next(output.glob("episode-*.html")).read_text(encoding="utf-8")
    assert "Cited sources" in page and "Primary sources" not in page
    assert secondary.url in page and "corroboration.example.com" in page


def test_source_health_projects_compact_statuses_without_raw_details(tmp_path: Path) -> None:
    manifest = _manifest("episode-1", "https://example.com/audio.mp3")
    manifest.source_health = {
        "healthy-empty": "ok:0",
        "healthy-updates": "ok:2",
        "private-path": "error:/home/private/cache",
        "provider": "degraded:SECRET-CANARY",
    }
    manifest.noise_notes = []
    feed, manifests, css = _fixture(tmp_path, manifest=manifest)
    output = tmp_path / "output"
    build_site(feed_path=feed, manifest_dir=manifests, stylesheet_path=css, output_dir=output)
    page = next(output.glob("episode-*.html")).read_text(encoding="utf-8")
    for label in ("Healthy, no updates", "Healthy, updates found", "Degraded", "Error"):
        assert label in page
    for hidden in ("SECRET-CANARY", "/home/private/cache", "private-path"):
        assert hidden not in page
    assert "Coverage gaps and exclusions" not in page


def test_index_is_collapsed_and_episode_header_has_independent_layout(tmp_path: Path) -> None:
    record = {
        "guid": "episode-1",
        "url": "https://example.com/audio.mp3",
        "description": "Qualified complete description. " * 200,
    }
    feed, manifests, _ = _fixture(tmp_path, record=record)
    output = tmp_path / "output"
    build_site(
        feed_path=feed,
        manifest_dir=manifests,
        stylesheet_path=ROOT / "assets/listening-site.css",
        output_dir=output,
    )
    index = (output / "index.html").read_text(encoding="utf-8")
    page = next(output.glob("episode-*.html")).read_text(encoding="utf-8")
    css = (output / "assets/listening-site.css").read_text(encoding="utf-8")
    assert "<details><summary>Accepted episode description</summary>" in index
    assert "Existing public podcast feed (subscription RSS)" in index and page
    assert '<header class="episode-header">' in page
    assert ".site-header" in css and ".episode-header" in css


def test_optional_feed_and_artwork_copies_preserve_exact_bytes(tmp_path: Path) -> None:
    feed, manifests, css = _fixture(tmp_path)
    artwork = feed.parent / "cover.jpg"
    artwork.write_bytes(b"synthetic-artwork-bytes")
    output = tmp_path / "output"
    build_site(
        feed_path=feed,
        manifest_dir=manifests,
        stylesheet_path=css,
        artwork_path=artwork,
        copy_feed=True,
        output_dir=output,
    )
    assert (output / "assets" / "source-feed.xml").read_bytes() == feed.read_bytes()
    assert (output / "assets" / "cover.jpg").read_bytes() == artwork.read_bytes()
    assert (output / "assets" / "listening-site.css").read_bytes() == css.read_bytes()
