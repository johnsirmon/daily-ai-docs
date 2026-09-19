"""Network-free request, recency, long-form, and mixed-feed contracts."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

from pipeline import daily
from pipeline.adhoc import authorize, write_brief
from pipeline.audio_quality import repetition_findings, validate_quality_report
from pipeline.podcast_request import PodcastRequest, record_status, request_from_issue, save_request
from pipeline.schema import EpisodeManifest, SchemaError, SourceEvent
from tests.test_reviewed_audio import draft, TIMESTAMP, CLAIM


def request(**changes):
    return PodcastRequest(
        **{"topic": "Agent evaluation", "audience": "Developers", "cutoff": TIMESTAMP,
           "actor": "maintainer", **changes},
    ).validate()


def long_draft(*, ready=False, **changes):
    item = draft()
    req = request(**changes)
    item["schema_version"] = 4
    item["episode_id"] = req.episode_id
    item["narration"] = CLAIM
    item["generation"].update(
        edition="adhoc", provider=req.provider, request=req.to_dict(), request_sha256=req.revision,
        quality={}, voice={},
    )
    item["generation"]["transcript"]["sha256"] = hashlib.sha256(CLAIM.encode()).hexdigest()
    item["audio"]["url"] = (
        f"https://github.com/johnsirmon/daily-ai-docs/releases/download/{req.episode_id}/daily-ai-brief.mp3"
    )
    if ready:
        item["status"] = "ready"
        item["audio"].update(
            size_bytes=12000, duration_secs=1200, sha256="a" * 64,
            codec="mp3", sample_rate=44100, channels=2,
        )
        item["generation"]["quality"] = {
            "method": "ffmpeg_loudnorm_two_pass", "ffmpeg": "ffmpeg test",
            "integrated_lufs": -16, "true_peak_dbtp": -1.1, "audio_sha256": "a" * 64,
        }
    return item


@pytest.mark.parametrize("days", [0, 366, True, 1.5, "60"])
def test_request_rejects_invalid_window(days):
    with pytest.raises(ValueError, match="lookback"):
        request(lookback_days=days)


def test_request_identity_binds_intent_provider_and_revision(tmp_path):
    original = request()
    assert request(publish_now=True).request_id != original.request_id
    assert request(provider="edge").request_id != original.request_id
    assert request(lookback_days=90).request_id != original.request_id
    path = save_request(original, tmp_path)
    assert save_request(original, tmp_path) == path
    record_status(path.parent, original, "cancelled")
    with pytest.raises(ValueError, match="terminal"):
        record_status(path.parent, original, "ready")


@pytest.mark.parametrize("days", [60, 90])
@pytest.mark.parametrize("offset,accepted", [(0, True), (-0.001, True), (0.001, False)])
def test_exact_recency_boundary(days, offset, accepted):
    req = request(lookback_days=days)
    event = SourceEvent.from_dict(draft()["source_events"][0])
    end = datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00"))
    event = replace(event, published_at=(end - timedelta(days=days, seconds=offset)).isoformat())
    if accepted:
        req.validate_sources([event])
    else:
        with pytest.raises(ValueError, match="window"):
            req.validate_sources([event])


def test_recency_rejects_future_unknown_and_secondary():
    req = request()
    event = SourceEvent.from_dict(draft()["source_events"][0])
    for stamp in ("", "2030-01-01T00:00:00Z"):
        event = replace(event, published_at=stamp)
        with pytest.raises(ValueError):
            req.validate_sources([event])
    event = replace(event, published_at=TIMESTAMP, authority="secondary")
    with pytest.raises(ValueError):
        req.validate_sources([event])


def test_long_form_does_not_change_old_serialization():
    legacy = EpisodeManifest.from_dict(draft())
    assert legacy.to_dict() == EpisodeManifest.from_dict(legacy.to_dict()).to_dict()
    current = EpisodeManifest.from_dict(long_draft())
    assert current.to_dict() == EpisodeManifest.from_dict(current.to_dict()).to_dict()


@pytest.mark.parametrize("seconds,accepted", [(1199.999, False), (1200, True), (1800, True), (1800.001, False)])
def test_long_form_measured_duration_contract(seconds, accepted):
    data = long_draft(ready=True)
    data["audio"]["duration_secs"] = seconds
    if accepted:
        EpisodeManifest.from_dict(data)
    else:
        with pytest.raises(SchemaError, match="1200-1800"):
            EpisodeManifest.from_dict(data)


def test_long_form_request_and_provider_cannot_be_tampered():
    for key, value in (("request_sha256", "b" * 64), ("provider", "edge"), ("edition", "notebook")):
        data = long_draft()
        data["generation"][key] = value
        with pytest.raises(SchemaError):
            EpisodeManifest.from_dict(data)


def test_preview_cannot_finalize_before_any_feed_write(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(long_draft(ready=True)))
    with pytest.raises(RuntimeError, match="preview"):
        daily.finalize(path, verify_remote=False, publication_path=tmp_path / "unused.json")
    assert not Path("podcast.xml").exists()


def test_issue_parsing_does_not_execute_text(monkeypatch):
    body = """### Topic
$(touch injected); evaluation
### Audience
Developers
### Evidence window (days)
90
### Audio provider
gemini-notebook-web
### Publication
Publish when all gates pass
"""
    issue = {"number": 10, "body": body, "created_at": TIMESTAMP, "user": {"login": "maintainer"}}
    req = request_from_issue(issue)
    assert req.topic.startswith("$(touch")
    assert req.lookback_days == 90 and req.publish_now
    monkeypatch.setattr("pipeline.adhoc.github", lambda *args: '{"permission":"read"}')
    with pytest.raises(PermissionError):
        authorize(req, publishing=True)


def test_issue_edit_invalidates_authorization(monkeypatch):
    req = request(issue=5, publish_now=True)
    monkeypatch.setattr("pipeline.adhoc.github", lambda *args: (
        '{"permission":"write"}' if args[1].endswith("/permission") else '{"state":"closed"}'
    ))
    with pytest.raises(PermissionError, match="closed"):
        authorize(req, publishing=True)


def test_brief_is_source_bounded_and_request_local(tmp_path):
    req = request()
    path = save_request(req, tmp_path)
    brief = write_brief(req, draft(), path.parent)
    assert "20-30 measured minutes" in brief.read_text()
    assert "2026-07-19" in brief.read_text()
    assert not (tmp_path / "episode-manifest.json").exists()


def test_adjacent_repeat_detection_and_natural_reuse():
    passage = "one two three four five six seven eight nine ten eleven twelve"
    assert repetition_findings(passage + " " + passage)
    assert not repetition_findings("The tool changed. Another tool changed in a different way.")


@pytest.mark.parametrize("field,value", [
    ("integrated_lufs", -17.01), ("integrated_lufs", -14.99),
    ("true_peak_dbtp", -0.99), ("integrated_lufs", float("nan")),
    ("audio_sha256", "b" * 64),
])
def test_quality_report_fails_closed(field, value):
    report = long_draft(ready=True)["generation"]["quality"]
    report[field] = value
    with pytest.raises(ValueError):
        validate_quality_report(report, final=True, audio_sha256="a" * 64)


def test_adhoc_confirmation_preserves_daily_cadence_and_run(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    state = {
        "schema_version": 1, "seen_event_ids": [], "last_episode_id": "daily-previous",
        "last_publication": "2026-09-16T00:00:00Z", "repo_snapshots": {},
    }
    daily._save_json(Path("data/state.json"), state)
    daily._save_json(Path("data/runs/latest.json"), {"unchanged": True})
    manifest = EpisodeManifest.from_dict(long_draft(ready=True, publish_now=True))
    manifest.status = "candidate"
    daily._save_json(Path("data/episodes") / f"{manifest.episode_id}.json", manifest.to_dict())
    daily.confirm(manifest.episode_id, verify_remote=False)
    after = daily.load_state()
    assert after["schema_version"] == 2
    assert after["last_daily_publication"] == state["last_publication"]
    assert after["last_daily_episode_id"] == state["last_episode_id"]
    assert after["last_episode_id"] == manifest.episode_id
    assert json.loads(Path("data/runs/latest.json").read_text()) == {"unchanged": True}
    req = request(publish_now=True)
    receipt = Path("data/requests") / f"{req.request_id}.json"
    assert json.loads(receipt.read_text())["status"] == "published"
    daily.confirm(manifest.episode_id, verify_remote=False)
    assert len(list(Path("data/receipts").glob("*.json"))) == 1


def test_local_voice_requires_explicit_setup(monkeypatch):
    from pipeline.local_voice import load_profile
    monkeypatch.delenv("TTS_LOCAL_PROFILE", raising=False)
    with pytest.raises(ValueError, match="TTS_LOCAL_PROFILE"):
        load_profile("kokoro")


def mixed_history(tmp_path, *, status="skipped"):
    previous = draft()
    previous["status"] = "published"
    previous["audio"].update(
        size_bytes=12000, duration_secs=400, sha256="b" * 64,
        codec="mp3", sample_rate=44100, channels=2,
    )
    old = EpisodeManifest.from_dict(previous)
    special = EpisodeManifest.from_dict(long_draft(ready=True, publish_now=True))
    special.status = "published"
    for manifest in (old, special):
        daily._save_json(Path("data/episodes") / f"{manifest.episode_id}.json", manifest.to_dict())
        daily._save_json(Path("data/receipts") / f"{manifest.episode_id}.json", {
            "episode_id": manifest.episode_id, "audio_sha256": manifest.audio["sha256"],
        })
    daily._save_json(Path("data/state.json"), {
        "schema_version": 2, "seen_event_ids": ["e1"],
        "last_episode_id": special.episode_id, "last_publication": special.published_at,
        "last_daily_episode_id": old.episode_id, "last_daily_publication": old.published_at,
    })
    daily._save_json(Path("data/runs/latest.json"), {
        "schema_version": 1, "status": status, "evaluated_at": TIMESTAMP,
        "reason": "insufficient_new_information", "source_health": {"manual:source": "ok:1"},
        "minimum_source_health": 0.6, "last_episode_id": old.episode_id,
    })
    return old, special


@pytest.mark.parametrize("status", ["skipped", "published"])
def test_mixed_feed_monitors_latest_special_and_daily_evaluation(monkeypatch, tmp_path, status):
    from pipeline.run_health import skip_candidate
    monkeypatch.chdir(tmp_path)
    _, special = mixed_history(tmp_path, status=status)
    result = skip_candidate(now=datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00")))
    assert result.episode_id == special.episode_id


def test_fresh_special_cannot_hide_failed_daily(monkeypatch, tmp_path):
    from pipeline.run_health import skip_candidate
    monkeypatch.chdir(tmp_path)
    mixed_history(tmp_path, status="failed")
    with pytest.raises(RuntimeError, match="failed"):
        skip_candidate(now=datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00")))


def test_paper_daily_policy_is_not_widened():
    from pipeline.sources.papers import collect_research_papers
    events, health = collect_research_papers({"enabled": True, "lookback_days": 60})
    assert not events and health["research:arxiv"].startswith("error:")


def test_duplicate_issue_form_fields_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        request_from_issue({"body": "### Topic\nA\n### Topic\nB"})


def test_daily_cadence_uses_daily_timestamp_not_special(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    mixed_history(tmp_path)
    state = daily.load_state()
    state["last_daily_publication"] = "2026-09-16T00:00:00Z"
    daily._save_json(Path("data/state.json"), state)
    config = Path("topics.yaml")
    config.write_text("daily: {}\n", encoding="utf-8")
    def collected(*args, **kwargs):
        raise RuntimeError("collector reached")
    monkeypatch.setattr(daily, "collect_events", collected)
    monkeypatch.setenv("AI_EDITORIAL", "off")
    with pytest.raises(RuntimeError, match="collector reached"):
        daily.prepare(config, now=datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00")))


def test_request_receipt_recovers_after_confirmation_interruption(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    manifest = EpisodeManifest.from_dict(long_draft(ready=True, publish_now=True))
    manifest.status = "candidate"
    daily._save_json(Path("data/episodes") / f"{manifest.episode_id}.json", manifest.to_dict())
    daily.confirm(manifest.episode_id, verify_remote=False)
    receipt = Path("data/requests") / f"{request(publish_now=True).request_id}.json"
    receipt.unlink()
    daily.confirm(manifest.episode_id, verify_remote=False)
    assert json.loads(receipt.read_text())["status"] == "published"


def test_prepare_import_and_exact_bundle_resume(monkeypatch, tmp_path):
    from pipeline.adhoc import prepare
    monkeypatch.chdir(tmp_path)
    req = request(publish_now=True)
    request_path = save_request(req, tmp_path)
    source = tmp_path / "source.m4a"
    source.write_bytes(b"original")
    data = draft(source=b"original")
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps({key: data[key] for key in (
        "source_events", "source_health", "stories", "show_notes",
    )}), encoding="utf-8")
    transcript = tmp_path / "transcript.txt"
    transcript.write_text(CLAIM, encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(json.dumps({
        "transcript": {"engine": "faster-whisper", "model": "small.en"},
        "review": data["generation"]["review"], "voice": {},
    }), encoding="utf-8")
    content = b"x" * 12000
    digest = hashlib.sha256(content).hexdigest()
    report = {**long_draft(ready=True)["generation"]["quality"], "audio_sha256": digest}
    def master(source, target):
        target.write_bytes(content)
        return report
    metrics = {
        "size_bytes": len(content), "duration_secs": 1200.0, "sha256": digest,
        "codec": "mp3", "sample_rate": 44100, "channels": 2,
    }
    monkeypatch.setattr("pipeline.audio_quality.master_audio", master)
    monkeypatch.setattr("pipeline.reviewed_audio.analyze_audio", lambda *args, **kwargs: metrics)
    monkeypatch.setattr("pipeline.daily.analyze_audio", lambda *args, **kwargs: metrics)
    monkeypatch.setattr("pipeline.audio_quality.loudness", lambda *args: {"input_i": -16, "input_tp": -1.1})
    target = tmp_path / "prepared"
    first = prepare(request_path, packet, transcript, review, source, target)
    second = prepare(request_path, packet, transcript, review, source, target)
    assert first["episode_id"] == second["episode_id"] == req.episode_id
    assert second["resumed"]
    assert source.read_bytes() == b"original"
    assert not Path("podcast.xml").exists()


def test_explicit_voice_synthesis_preserves_provider_and_cannot_publish(monkeypatch, tmp_path):
    from pipeline.adhoc import synthesize
    req = request(provider="edge")
    script = tmp_path / "script.txt"
    script.write_text(CLAIM, encoding="utf-8")
    output = tmp_path / "source.mp3"
    monkeypatch.setenv("TTS_PROVIDER", "openai")
    monkeypatch.setattr("pipeline.tts.generate_audio", lambda text: b"x" * 12000)
    synthesize(req, script, output)
    import os
    assert os.environ["TTS_PROVIDER"] == "openai"
    assert output.with_suffix(".voice.json").exists()
    assert not (tmp_path / "podcast.xml").exists()
    with pytest.raises(FileExistsError):
        synthesize(req, script, output)
    with pytest.raises(ValueError, match="browser"):
        synthesize(request(), script, tmp_path / "other.mp3")
