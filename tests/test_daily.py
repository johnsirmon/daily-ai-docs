import json
from datetime import datetime, timezone

import pytest

from pipeline.daily import collect_events, confirm, finalize, prepare
from pipeline.publish import PublicationError
from pipeline.schema import EpisodeManifest, SourceEvent


_CONFIG = """
daily:
  lookback_hours: 36
  max_stories: 7
  minimum_score: 0
  sources:
    github_releases: []
    feeds: []
"""


def _deterministic_sources(count, *, substantive=False):
    evidence = "Tool adds a command approval preview. Existing approvals remain required."
    if substantive:
        evidence += (
            " Only explicitly approved commands execute in the workspace."
            " Remote execution remains disabled for projects without an existing permission grant."
            " The command preview lists the requested arguments and target directory before approval."
            " Administrators can retain existing project settings while reviewing the proposed operation."
            " Denied requests do not launch a process or change files."
            " Audit entries record the requested command and its approval outcome."
        )
    return [
        SourceEvent(
            f"e{index}", "announcement", f"Tool {index} approval update",
            f"https://example.com/change-{index}", f"Tool {index}", "Coding",
            "2026-09-19T10:00:00Z", "2026-09-19T11:00:00Z", evidence,
        )
        for index in range(count)
    ]


@pytest.mark.parametrize("count", range(3, 8))
def test_short_marked_editions_skip_before_tts_and_preserve_publication_state(monkeypatch, tmp_path, count):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_EDITORIAL", "off")
    monkeypatch.setenv("AI_SYNTHESIS", "off")
    monkeypatch.setenv("PODCAST_AUDIO_POLISH", "0")
    config = tmp_path / "topics.yaml"
    config.write_text(_CONFIG, encoding="utf-8")
    (tmp_path / "podcast.xml").write_text("last-good-feed")
    state = {"schema_version": 1, "seen_event_ids": [], "last_publication": None}
    (tmp_path / "data").mkdir()
    state_path = tmp_path / "data/state.json"
    state_path.write_text(json.dumps(state))
    monkeypatch.setattr(
        "pipeline.daily.collect_events",
        lambda *args, **kwargs: (_deterministic_sources(count), {"source": f"ok:{count}"}),
    )
    monkeypatch.setattr(
        "pipeline.daily.write_audio",
        lambda *args, **kwargs: pytest.fail("infeasible narration must not reach TTS"),
    )
    result = prepare(config, now=datetime(2026, 9, 19, 12, tzinfo=timezone.utc))
    assert result["outcome"] == "skipped"
    assert result["reason"] == "insufficient_substantive_material"
    receipt = json.loads((tmp_path / "data/runs/latest.json").read_text())
    assert receipt["status"] == "skipped" and receipt["reason"] == result["reason"]
    assert receipt["source_health"] == {"source": f"ok:{count}"}
    assert json.loads(state_path.read_text()) == state
    assert (tmp_path / "podcast.xml").read_text() == "last-good-feed"
    assert not (tmp_path / ".cache/episode-manifest.json").exists()
    assert not (tmp_path / "data/episodes").exists()


def test_short_utility_script_skips_instead_of_padding_or_calling_tts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_EDITORIAL", "off")
    monkeypatch.setenv("AI_SYNTHESIS", "off")
    monkeypatch.setenv("PODCAST_AUDIO_POLISH", "0")
    config = tmp_path / "topics.yaml"
    config.write_text(_CONFIG, encoding="utf-8")
    monkeypatch.setattr("pipeline.daily.collect_events",
                        lambda *args, **kwargs: (_deterministic_sources(4, substantive=True), {"source": "ok:4"}))
    monkeypatch.setattr(
        "pipeline.daily.write_audio",
        lambda *args, **kwargs: pytest.fail("insufficient script must not call TTS"),
    )
    result = prepare(config, now=datetime(2026, 9, 19, 12, tzinfo=timezone.utc))
    assert result["outcome"] == "skipped"
    assert result["reason"] == "insufficient_substantive_material"


def test_prepare_dry_run_is_network_and_audio_free(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_SYNTHESIS", "off")
    config = tmp_path / "topics.yaml"
    config.write_text(_CONFIG, encoding="utf-8")
    publication = prepare(
        config,
        dry_run=True,
        no_audio=True,
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    manifest = EpisodeManifest.from_dict(json.loads((tmp_path / publication["manifest_path"]).read_text()))
    assert manifest.stories
    assert manifest.generation["narration_style"] == "explanatory-v3"
    assert "This episode uses AI-generated narration" in manifest.narration
    assert "The call is" not in manifest.narration
    assert "What changed" not in manifest.narration
    assert "http" not in manifest.narration
    assert publication["audio_path"] == ""


def test_prepare_dry_run_never_calls_model_even_with_credentials(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_SYNTHESIS", "required")
    monkeypatch.setenv("AI_API_KEY", "must-not-be-used")
    config = tmp_path / "topics.yaml"
    config.write_text(_CONFIG, encoding="utf-8")
    with monkeypatch.context() as context:
        context.setattr("pipeline.daily.refine_stories", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network model called")))
        result = prepare(config, dry_run=True, no_audio=True)
    assert result["dry_run"] is True


def test_collection_outage_is_not_published_as_quiet_day(monkeypatch):
    monkeypatch.setattr("pipeline.daily.collect_github_releases", lambda *args, **kwargs: ([], {"a": "error:Timeout"}))
    monkeypatch.setattr("pipeline.daily.collect_official_feeds", lambda *args, **kwargs: ([], {"b": "error:Timeout"}))
    with pytest.raises(RuntimeError, match="all configured sources failed"):
        collect_events(
            {"daily": {"sources": {"github_releases": [{}], "feeds": [{}]}}},
            dry_run=False,
            now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
        )


def test_show_notes_distinguish_supplementary_and_primary_outages():
    from pipeline.daily import _show_notes
    from pipeline.rank import event_to_story

    story = event_to_story(_deterministic_sources(1)[0])
    supplementary = _show_notes(
        [story], [], {"github:tool": "ok:1", "youtube:weekly": "error:stale"},
    )
    assert "Supplementary coverage gaps" in supplementary
    assert "Primary-source coverage gaps" not in supplementary

    primary = _show_notes(
        [story], [], {"github:tool": "error:timeout", "youtube:weekly": "ok:1"},
    )
    assert "Primary-source coverage gaps" in primary
    assert "Supplementary coverage gaps" not in primary


def test_prepare_refuses_second_same_day_publication(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "topics.yaml"
    config.write_text(_CONFIG, encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/state.json").write_text(
        json.dumps({"schema_version": 1, "seen_event_ids": [], "last_publication": "2026-09-07T08:00:00Z"}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="already published"):
        prepare(config, no_audio=True, now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc))


def test_prepare_resumes_pending_candidate_without_collection(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "topics.yaml"
    config.write_text(_CONFIG, encoding="utf-8")
    manifest = EpisodeManifest(
        1, "daily-2026-09-06-pending", "2026-09-06T12:00:00Z", "candidate",
        {"source": "ok:0"}, [], [], [], "A valid pending narration for recovery.",
        "Pending notes.", {"edition": "quiet"},
        {"url": "https://example.com/a.mp3", "size_bytes": 12345, "duration_secs": 60, "sha256": "abc"},
    )
    path = tmp_path / "data/episodes/daily-2026-09-06-pending.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    monkeypatch.setattr(
        "pipeline.daily.collect_events",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("collection should not run")),
    )
    result = prepare(config, now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc))
    assert result["episode_id"] == manifest.episode_id
    assert result["resumed"] is True
    resumed = json.loads((tmp_path / result["manifest_path"]).read_text())
    assert resumed == manifest.to_dict()
    assert "narration_style" not in resumed["generation"]


def test_finalize_writes_feed_manifest_state_and_readme(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    manifest = EpisodeManifest(
        schema_version=1,
        episode_id="daily-2026-09-07-test",
        published_at="2026-09-07T12:00:00Z",
        status="ready",
        source_health={"dry-run": "ok:0"},
        source_events=[],
        stories=[],
        noise_notes=[],
        narration="A quiet daily brief with enough words to be a valid narration.",
        show_notes="No actionable updates today.",
        generation={"edition": "quiet"},
        audio={
            "url": "https://example.com/audio.mp3",
            "size_bytes": 12345,
            "duration_secs": 60,
            "sha256": "abc123",
        },
    )
    path = tmp_path / ".cache" / "episode-manifest.json"
    path.parent.mkdir()
    path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    published = finalize(path, verify_remote=False)
    assert published.status == "candidate"
    assert (tmp_path / "data/episodes/daily-2026-09-07-test.json").exists()
    assert not (tmp_path / "data/state.json").exists()
    readme = (tmp_path / "README.md").read_text()
    assert "Daily AI Developer Brief" in readme
    assert "## Podcast" in readme
    assert "## Today's signal" in readme
    assert "## Tracked areas" in readme
    assert "## Source health" in readme
    assert "## Publication flow" in readme
    assert "## Weekly YouTube signal" in readme
    assert "## Development" in readme
    assert "10:17 UTC" in readme
    assert "11:23 UTC" in readme
    assert "pytest -q" in readme
    assert published.episode_id in (tmp_path / "podcast.xml").read_text()
    with monkeypatch.context() as context:
        context.setattr(
            "pipeline.daily.verify_remote_feed",
            lambda *args, **kwargs: (_ for _ in ()).throw(PublicationError("not delivered")),
        )
        with pytest.raises(PublicationError, match="not delivered"):
            confirm(published.episode_id, verify_remote=True)
    assert not (tmp_path / "data/state.json").exists()
    confirmed = confirm(published.episode_id, verify_remote=False)
    assert confirmed.status == "published"
    assert json.loads((tmp_path / "data/state.json").read_text())["last_episode_id"] == published.episode_id
    assert (tmp_path / "data/receipts/daily-2026-09-07-test.json").exists()
