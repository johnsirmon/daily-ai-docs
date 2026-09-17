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


def test_legacy_manifest_serialization_does_not_add_editorial_defaults():
    manifest = EpisodeManifest(
        1, "daily-1", "2026-09-07T12:00:00Z", "candidate", {"source": "ok:1"},
        [event()], [story()], [], "Immutable released narration.", "Immutable notes.", {}, {},
    )
    original = manifest.to_dict()
    assert "kind" not in original["stories"][0]
    assert "editorial" not in original["stories"][0]
    loaded = EpisodeManifest.from_dict(original)
    assert loaded.stories[0].kind == "product"
    assert loaded.stories[0].editorial == {}
    assert loaded.to_dict() == original
    assert loaded.stories[0].to_dict() == original["stories"][0]


def test_research_source_type_and_bounded_full_text():
    event(source_type="research_paper", metadata={"full_text": "Bounded public evidence."}).validate()
    with pytest.raises(SchemaError, match="full_text exceeds"):
        event(source_type="research_paper", metadata={"full_text": "x" * 80001}).validate()