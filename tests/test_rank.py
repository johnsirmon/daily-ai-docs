from pipeline.rank import dedupe_events, score_event, select_events
from pipeline.schema import SourceEvent


def event(event_id, *, product="Tool", version="v1", priority=10, velocity=0, channel="stable", evidence="Important update"):
    return SourceEvent(
        event_id=event_id,
        source_type="github_release",
        title=f"{product} {version}",
        url=f"https://example.com/{event_id}",
        product=product,
        topic="AI coding agents",
        published_at="2026-09-07T12:00:00Z",
        fetched_at="2026-09-07T12:01:00Z",
        evidence=evidence,
        channel=channel,
        metadata={"version": version, "priority": priority, "star_velocity": velocity},
    )


def test_measured_velocity_beats_large_flat_repo():
    rising = score_event(event("rising", velocity=100))
    flat = score_event(event("flat", velocity=0))
    assert rising["total"] > flat["total"]


def test_seen_event_is_not_selected():
    selected, _ = select_events([event("seen")], seen_event_ids=["seen"], minimum_score=0)
    assert selected == []


def test_prerelease_boilerplate_is_filtered():
    selected, notes = select_events(
        [event("rc", channel="prerelease", evidence="Release candidate dependency bump")],
        minimum_score=0,
    )
    assert selected == []
    assert notes


def test_stable_typo_or_chore_is_filtered_even_with_high_priority():
    selected, notes = select_events(
        [event("typo", priority=20, evidence="Chore: fixes a documentation typo")],
        minimum_score=0,
    )
    assert selected == []
    assert notes == ["Skipped Tool: routine or prerelease-only update."]


def test_dedupe_prefers_primary_source():
    secondary = event("secondary")
    secondary = SourceEvent(**{**secondary.to_dict(), "authority": "secondary"})
    primary = event("primary")
    result = dedupe_events([secondary, primary])
    assert len(result) == 1
    assert result[0].event_id == "primary"


def test_selection_caps_weekly_video_recommendations():
    videos = []
    for index in range(3):
        base = event(f"video-{index}", product=f"Channel {index}", priority=20, velocity=100)
        videos.append(SourceEvent(**{
            **base.to_dict(),
            "source_type": "youtube_video",
            "title": f"Weekly watch: video {index}",
            "metadata": {**base.metadata, "trend_score": 100},
        }))
    selected, _ = select_events(
        videos,
        minimum_score=0,
        max_per_source_type={"youtube_video": 1},
    )
    assert len(selected) == 1