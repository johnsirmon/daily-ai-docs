import json
import re
from dataclasses import replace
from pathlib import Path

from pipeline.narrate import manifest_to_narration
from pipeline.rank import event_to_story, select_events
from pipeline.schema import EpisodeManifest, SourceEvent


_VERSION = re.compile(r"(?<![\w.-])v?\d+(?:\.\d+)+(?![\w.-])", re.IGNORECASE)


def test_latest_subscriber_regression_is_measured_and_replayed_without_release_dump():
    root = Path(__file__).resolve().parents[1]
    path = root / "data/episodes/daily-2026-09-21-6d54e8e9.json"
    manifest = EpisodeManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    original_tokens = _VERSION.findall(
        "\n".join([
            manifest.narration,
            *(story.headline for story in manifest.stories),
            *(story.what_changed for story in manifest.stories),
        ])
    )
    assert len(manifest.narration.split()) == 327
    assert len(original_tokens) == 12
    assert "1,812 merged PRs" in manifest.narration
    assert "4b8a8134009a8727a289bcabeb0019fedd353128" in manifest.narration

    selected, notes = select_events(
        manifest.source_events, limit=3, minimum_score=75, max_per_product=1,
    )
    assert [event.product for event in selected] == ["Hermes Agent"]
    assert notes == []
    replay = replace(
        manifest,
        status="draft",
        stories=[event_to_story(event) for event in selected],
        generation={"provider": "deterministic", "calls": 0,
                    "narration_style": "explanatory-v3", "edition": "alert"},
        narration="pending",
        audio={"url": manifest.audio["url"]},
    )
    replay.narration = manifest_to_narration(replay)
    assert "1,812 merged PRs" not in replay.narration
    assert "4b8a8134009a8727a289bcabeb0019fedd353128" not in replay.narration
    assert "host-wide gateway singleton lock" in replay.narration
    assert "Source links and written recommendations are in the episode notes" in replay.narration


def test_utility_narration_retains_negation_eligibility_and_compatibility_version():
    evidence = (
        "Tool clients before version 2.4 must update before the API removal. "
        "HTTPS users are unaffected and should ignore this migration. "
        "Existing RSA keys remain supported only when clients use RSA-SHA2."
    )
    event = SourceEvent(
        "compat", "announcement", "Client compatibility change", "https://example.com/compat",
        "Tool", "compatibility", "2026-09-22T10:00:00Z", "2026-09-22T11:00:00Z",
        evidence, metadata={"priority": 20},
    )
    selected, _ = select_events([event], minimum_score=75, max_per_product=1)
    assert selected == [event]
    story = event_to_story(event)
    manifest = EpisodeManifest(
        1, "daily-compat", "2026-09-22T12:00:00Z", "draft", {"source": "ok:1"},
        [event], [story], [], "pending", "notes",
        {"narration_style": "explanatory-v3", "edition": "alert"}, {},
    )
    narration = manifest_to_narration(manifest)
    assert "version 2.4" in narration
    assert "HTTPS users are unaffected" in narration
    assert "only when clients use RSA-SHA2" in narration


def test_alias_product_cap_and_research_cap_are_independent():
    base = SourceEvent(
        "github", "announcement", "GitHub SSH change", "https://example.com/github",
        "GitHub", "security", "2026-09-22T10:00:00Z", "2026-09-22T11:00:00Z",
        "SSH clients must update before algorithm removal.", metadata={"priority": 20},
    )
    alias = replace(base, event_id="platform", product="GitHub Platform", url="https://example.com/platform")
    codeql = replace(
        base, event_id="codeql", product="CodeQL CLI", url="https://example.com/codeql",
        evidence="CodeQL bundle installers must select a platform-specific download before removal.",
    )
    selected, _ = select_events([base, alias, codeql], minimum_score=75, limit=3, max_per_product=1)
    assert len(selected) == 2
    assert {event.product for event in selected} & {"GitHub", "GitHub Platform"}
    assert any(event.product == "CodeQL CLI" for event in selected)

