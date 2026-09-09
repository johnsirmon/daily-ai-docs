import json
from datetime import datetime, timezone

import pytest

from pipeline.daily import collect_events, confirm, finalize, prepare
from pipeline.publish import PublicationError
from pipeline.schema import EpisodeManifest


_CONFIG = """
daily:
  lookback_hours: 36
  max_stories: 7
  minimum_score: 0
  sources:
    github_releases: []
    feeds: []
"""


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
    assert "Daily AI Developer Brief" in (tmp_path / "README.md").read_text()
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
