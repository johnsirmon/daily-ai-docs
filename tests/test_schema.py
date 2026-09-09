import pytest

from pipeline.schema import EpisodeManifest, SchemaError, SourceEvent, Story


def event(**changes):
    data = {
        "event_id": "event-1",
        "source_type": "github_release",
        "title": "Tool v2",
        "url": "https://example.com/tool/v2",
        "product": "Tool",
        "topic": "AI coding agents",
        "published_at": "2026-09-07T10:00:00Z",
        "fetched_at": "2026-09-07T11:00:00Z",
        "evidence": "Tool v2 added a supported migration path.",
        "metadata": {"priority": 20},
    }
    data.update(changes)
    return SourceEvent(**data)


def story():
    return Story(
        story_id="story-1",
        event_ids=["event-1"],
        headline="Tool v2",
        what_changed="Tool v2 added a supported migration path.",
        why_it_matters="Existing users need to review the migration.",
        action="act",
        rationale="Primary source.",
        source_urls=["https://example.com/tool/v2"],
        scores={"total": 90},
    )


def test_source_event_rejects_private_data():
    with pytest.raises(SchemaError, match="private"):
        event(metadata={"private": True}).validate()


def test_source_event_requires_timezone():
    with pytest.raises(SchemaError, match="timezone"):
        event(published_at="2026-09-07T10:00:00").validate()


def test_manifest_rejects_unknown_evidence_reference():
    valid = story()
    bad = Story(**{**valid.to_dict(), "event_ids": ["missing"]})
    manifest = EpisodeManifest(
        1, "daily-1", "2026-09-07T12:00:00Z", "draft", {"source": "ok:1"},
        [event()], [bad], [], "Narration long enough for validation.", "Notes.", {}, {},
    )
    with pytest.raises(SchemaError, match="unknown source event"):
        manifest.validate(require_audio=False)


def test_manifest_roundtrip():
    manifest = EpisodeManifest(
        1, "daily-1", "2026-09-07T12:00:00Z", "draft", {"source": "ok:1"},
        [event()], [story()], [], "Narration long enough for validation.", "Notes.", {}, {},
    )
    loaded = EpisodeManifest.from_dict(manifest.to_dict())
    assert loaded.source_events[0].event_id == "event-1"
    assert loaded.stories[0].action == "act"