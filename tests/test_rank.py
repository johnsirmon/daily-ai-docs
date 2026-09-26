from pipeline.rank import assess_utility, canonical_product, dedupe_events, event_to_story, score_event, select_events
from pipeline.schema import SourceEvent


def event(event_id, *, product="Tool", version="v1", priority=10, velocity=0, channel="stable",
          evidence="Added permission checks before tool execution in coding sessions."):
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


def test_prerelease_boilerplate_is_filtered_at_production_threshold():
    selected, notes = select_events(
        [event("rc", channel="prerelease", evidence="Release candidate dependency bump")],
    )
    assert selected == []
    assert notes


def test_stable_typo_or_chore_is_filtered_at_production_threshold():
    selected, notes = select_events(
        [event("typo", priority=20, evidence="Chore: fixes a documentation typo")],
    )
    assert selected == []
    assert notes == ["Excluded Tool: no substantive change evidence."]


def test_deterministic_selection_requires_substantive_evidence_even_with_momentum():
    filler = event("filler", priority=20, velocity=10000, evidence="Published 1.2.3.")
    selected, notes = select_events([filler])
    assert selected == []
    assert notes == ["Excluded Tool: no substantive change evidence."]


def test_documentation_sentence_does_not_penalize_a_substantive_fix():
    fixed = event(
        "fixed",
        priority=20,
        evidence="Fixed a crash when the tool host disconnects. Documentation explains recovery.",
    )
    assert score_event(fixed)["noise_penalty"] == 0
    assert select_events([fixed])[0] == [fixed]


def test_dedupe_prefers_primary_source():
    secondary = event("secondary")
    secondary = SourceEvent(**{**secondary.to_dict(), "authority": "secondary"})
    primary = event("primary")
    result = dedupe_events([secondary, primary])
    assert len(result) == 1
    assert result[0].event_id == "primary"


def test_dedupe_keeps_stable_and_prerelease_channels_distinct():
    stable = event("stable", version="v2", channel="stable")
    preview = event("preview", version="v2", channel="prerelease")
    assert {item.event_id for item in dedupe_events([preview, stable])} == {"preview", "stable"}


def test_dedupe_tie_break_is_deterministic_and_prefers_better_evidence():
    weak = event("z-weak", evidence="Added support.")
    strong = event("a-strong", evidence="Added support for scoped tool approvals in shared coding sessions.")
    assert dedupe_events([weak, strong]) == [strong]
    assert dedupe_events([strong, weak]) == [strong]


def test_selection_caps_weekly_video_recommendations():
    videos = []
    for index in range(3):
        base = event(f"video-{index}", product=f"Channel {index}", priority=20, velocity=100)
        videos.append(SourceEvent(**{
            **base.to_dict(),
            "source_type": "youtube_video",
            "title": f"Weekly watch: video {index}",
            "evidence": "A tutorial explains how to inspect tool-call traces before changing agent memory.",
            "metadata": {**base.metadata, "trend_score": 100},
        }))
    selected, _ = select_events(
        videos,
        minimum_score=0,
        max_per_source_type={"youtube_video": 1},
    )
    assert len(selected) == 1


def test_selection_caps_same_product_for_daily_diversity():
    sources = [
        event(f"tool-{index}", version=f"v{index}", priority=20,
              evidence=f"Added support for scoped tool workflow {index} in coding sessions.")
        for index in range(3)
    ]
    other = event(
        "other", product="Other", priority=20,
        evidence="Added support for verified agent traces in development sessions.",
    )
    selected, notes = select_events(
        [*sources, other], minimum_score=0, limit=4, max_per_product=2,
    )
    assert len([item for item in selected if item.product == "Tool"]) == 2
    assert other in selected
    assert "additional same-product updates omitted" in " ".join(notes)


def test_popularity_cannot_rescue_release_hype_without_utility():
    hype = event("hype", priority=20, velocity=10000,
                 evidence="Our latest release delivers an amazing developer experience.")
    assert assess_utility(hype)["demonstrated"] == 0
    assert score_event(hype)["total"] == 0
    assert select_events([hype])[0] == []


def test_canonical_aliases_share_product_cap_but_codeql_remains_distinct():
    assert canonical_product("GitHub") == canonical_product("GitHub Platform")
    assert canonical_product("CodeQL CLI") != canonical_product("GitHub")


def test_event_to_story_bounds_rationale_from_a_long_action_sentence():
    # A single run-on "sentence" (no internal terminators) containing an
    # action keyword must not overflow the story's 1200-character rationale
    # limit; event_to_story previously used it verbatim and raised SchemaError.
    long_sentence = (
        "You must update every one of the following configuration keys across all affected "
        "environments and services before the next scheduled deployment window closes, review "
        "each dependent workflow, replace deprecated call sites, upgrade any pinned client "
        "libraries, and inspect downstream consumers for compatibility " + ("issues " * 250)
    ).strip() + "."
    story = event_to_story(event("long-action", evidence=long_sentence))
    assert len(story.rationale) <= 1200
    story.validate()
