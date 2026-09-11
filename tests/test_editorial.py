"""Labeled policy cases run against the real production selection threshold."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from pipeline.narrate import manifest_to_narration
from pipeline.rank import dedupe_events, event_to_story, score_event, select_events
from pipeline.schema import EpisodeManifest
from tests.test_rank import event

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/fixtures/editorial.json").read_text())
THRESHOLD = yaml.safe_load((ROOT / "topics/topics.yaml").read_text())["daily"]["minimum_score"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["label"])
def test_editorial_labels_at_production_threshold(case):
    source = event(case["label"], evidence=case["evidence"], priority=case.get("priority", 20),
                   channel=case.get("channel", "stable"))
    now = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
    source = replace(source, authority=case.get("authority", "primary"),
                     source_type=case.get("source_type", "github_release"),
                     published_at=(now - timedelta(hours=case.get("age_hours", 0))).isoformat(),
                     fetched_at=now.isoformat(),
                     metadata={**source.metadata, "trend_score": case.get("trend_score", 0)})
    selected, _ = select_events([source], minimum_score=THRESHOLD)
    assert bool(selected) is case["selected"], score_event(source)
    assert event_to_story(source).action == case["action"]
    assert bool(select_events([source])[0]) is case["selected"]


def test_noise_penalty_is_not_a_hidden_veto():
    source = event("noise", evidence="Documentation typo.")
    assert score_event(source)["noise_penalty"] == 24
    assert select_events([source], minimum_score=0) == ([source], [])


def test_noise_notes_are_deduplicated_before_limit():
    sources = [event(f"a-{i}", version=f"v{i}", evidence="Documentation typo.") for i in range(5)]
    sources.append(event("b", product="Other", evidence="Documentation typo."))
    selected, notes = select_events(sources)
    assert not selected
    assert len(notes) == 2
    assert "Tool" in notes[0] and "Other" in notes[1]
    assert all("below threshold" in note for note in notes)


def test_newer_secondary_never_displaces_primary():
    primary = event("primary")
    secondary = replace(event("secondary"), authority="secondary", published_at="2026-09-07T12:01:00Z")
    assert dedupe_events([primary, secondary]) == [primary]
    assert dedupe_events([secondary, primary]) == [primary]


@pytest.mark.parametrize("evidence", [
    "A full sentence describes the new feature. " * 90,
    "word " * 700,
    "x" * 4000,
    "Check the tool behavior. " + "longword " * 400,
])
def test_valid_long_evidence_is_bounded_without_schema_expansion(evidence):
    source = event("long", evidence=evidence)
    story = event_to_story(source)
    assert len(story.what_changed) <= 1600
    assert len(story.what_changed.split()) <= 118
    assert "Excerpt; see source for full details." in story.what_changed
    assert source.evidence == evidence
    assert story.source_urls == [source.url]
    events = [replace(source, event_id=f"event-{i}") for i in range(7)]
    stories = [event_to_story(row) for row in events]
    manifest = EpisodeManifest(1, "bounded", source.published_at, "draft", {"test": "ok:7"},
                               events, stories, [], "pending", "notes", {}, {})
    manifest.narration = manifest_to_narration(manifest)
    manifest.validate()
    assert len(manifest.narration.split()) <= 1500


def test_short_evidence_is_not_reworded_or_truncated():
    source = event("short", evidence="Adds typed arguments. Existing calls remain compatible.")
    assert event_to_story(source).what_changed == source.evidence


def test_act_rationale_requires_applicability_not_blind_upgrade():
    story = event_to_story(event("security", evidence="Security patch fixes a vulnerability."))
    assert story.action == "act"
    assert "only if" in story.rationale
    assert "affected versions" in story.rationale


def test_video_rationale_does_not_claim_adoption_or_per_channel_baseline():
    story = event_to_story(replace(event("video"), source_type="youtube_video"))
    assert story.action == "watch"
    assert "does not establish adoption" in story.rationale
    assert "normalized against comparable" not in story.rationale
