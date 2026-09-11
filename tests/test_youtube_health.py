"""Offline YouTube outcome diagnostics and last-good-digest fault tests."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
from youtube_transcript_api import YouTubeTranscriptApiException

from pipeline import youtube
from pipeline.daily import _show_notes
from pipeline.sources.youtube import collect_youtube_digest
from tests.test_youtube import Response, Session, transcript

NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def discover(fetcher=transcript, session=None, **config):
    return youtube.discover_videos({"queries": ["coding agents"], **config}, api_key="fake-test-key",
                                   now=NOW, session=session or Session(), transcript_fetcher=fetcher)


def test_success_counters_are_bounded_by_selection_cap():
    payload = discover(max_selected=1)
    assert payload["discovery_health"] == {
        "status": "ok", "search_result_count": 2, "detail_count": 2, "candidate_count": 2,
        "transcript_attempts": 1, "transcript_successes": 1, "selected_count": 1,
        "usable_count": 1, "unattempted_count": 1,
        "drop_reasons": {"missing_details": 0, "invalid_details": 0, "transcript_error": 0,
                         "empty_transcript": 0, "empty_takeaway": 0},
    }


class EmptySearch:
    def get(self, url, **kwargs):
        assert url.endswith("/search"), "No detail requests needed for an empty search"
        return Response({"items": []})


def test_zero_search_results_are_healthy_not_transcript_outage(tmp_path):
    payload = discover(session=EmptySearch())
    health = payload["discovery_health"]
    assert health["status"] == "ok"
    assert health["search_result_count"] == health["transcript_attempts"] == 0
    assert not any(health["drop_reasons"].values())
    path = tmp_path / "digest.json"
    youtube.write_digest(payload, path)
    assert collect_youtube_digest({"digest_path": str(path)}, now=NOW) == ([], {"youtube:weekly-digest": "ok:0"})


@pytest.mark.parametrize("fault", ["empty", "transport", "unavailable", "no_takeaway"])
def test_candidates_with_no_usable_transcripts_are_degraded(fault, monkeypatch, tmp_path):
    def fetch(_):
        if fault == "transport":
            raise requests.Timeout("private raw exception must never be persisted")
        if fault == "unavailable":
            raise YouTubeTranscriptApiException("private raw exception must never be persisted")
        return "" if fault == "empty" else transcript("video-a")
    if fault == "no_takeaway":
        monkeypatch.setattr(youtube, "_takeaway", lambda *args: "")
    payload = discover(fetch)
    health = payload["discovery_health"]
    assert health["status"] == "degraded"
    assert health["transcript_attempts"] == 2
    assert health["selected_count"] == health["usable_count"] == 0
    reason = {"empty": "empty_transcript", "transport": "transcript_error",
              "unavailable": "transcript_error", "no_takeaway": "empty_takeaway"}[fault]
    assert health["drop_reasons"][reason] == 2
    assert sum(health["drop_reasons"].values()) == 2
    assert "private raw exception" not in json.dumps(payload)
    path = tmp_path / "digest.json"
    youtube.write_digest(payload, path)
    events, statuses = collect_youtube_digest({"digest_path": str(path)}, now=NOW)
    assert events == [] and statuses == {"youtube:weekly-digest": "degraded:0"}
    assert "coverage was incomplete" in _show_notes(events, [], statuses)


def test_partial_transcript_failure_preserves_usable_events_and_reports_gap(tmp_path):
    def fetch(video_id):
        if video_id == "video-b":
            raise requests.ConnectionError("raw-error-with-key")
        return transcript(video_id)
    payload = discover(fetch)
    health = payload["discovery_health"]
    assert health["status"] == "degraded"
    assert health["transcript_attempts"] == 2
    assert health["transcript_successes"] == health["selected_count"] == 1
    assert health["drop_reasons"]["transcript_error"] == 1
    path = tmp_path / "digest.json"
    youtube.write_digest(payload, path)
    events, statuses = collect_youtube_digest({"digest_path": str(path)}, now=NOW)
    assert len(events) == 1
    assert statuses == {"youtube:weekly-digest": "degraded:1"}


@pytest.mark.parametrize("fault", ["missing", "invalid"])
def test_unusable_video_details_do_not_masquerade_as_no_news(fault):
    class DetailsFault(Session):
        def get(self, url, **kwargs):
            result = super().get(url, **kwargs)
            if url.endswith("/videos"):
                if fault == "missing":
                    return Response({"items": []})
                for item in result._payload["items"]:
                    item["snippet"]["publishedAt"] = "invalid"
            return result
    payload = discover(session=DetailsFault())
    health = payload["discovery_health"]
    assert health["status"] == "degraded"
    assert health["candidate_count"] == health["transcript_attempts"] == 0
    assert health["drop_reasons"][f"{fault}_details"] == 2


@pytest.mark.parametrize("legacy", [True, False])
def test_adapter_rejects_empty_usable_result_despite_success_label(tmp_path, legacy):
    payload = {"schema_version": 1, "generated_at": NOW.isoformat(), "candidate_count": 2, "videos": []}
    if not legacy:
        payload["discovery_health"] = {"status": "ok"}
    path = tmp_path / "digest.json"
    youtube.write_digest(payload, path)
    assert collect_youtube_digest({"digest_path": str(path)}, now=NOW) == ([], {"youtube:weekly-digest": "degraded:0"})


@pytest.mark.parametrize("fault", ["degraded", "request", "invalid-response", "success"])
def test_cli_persists_only_safe_diagnostics_and_preserves_last_good_digest(fault, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-private-key")
    config = Path("topics.yaml")
    config.write_text("daily:\n  sources:\n    youtube:\n      queries: ['coding agents']\n")
    output = Path("digest.json")
    previous = '{"previous": "last-good"}\n'
    output.write_text(previous)
    payload = discover((lambda _: "") if fault == "degraded" else transcript)
    def discovery(*args, **kwargs):
        if fault == "request":
            raise requests.HTTPError("https://example.com?key=fake-private-key&raw-error")
        if fault == "invalid-response":
            raise ValueError("raw-error fake-private-key")
        return payload
    monkeypatch.setattr(youtube, "discover_videos", discovery)
    monkeypatch.setattr("sys.argv", ["youtube", "--config", str(config), "--output", str(output)])
    assert youtube.main() == (0 if fault == "success" else 1)
    diagnostics_text = Path(".cache/youtube-discovery-health.json").read_text()
    diagnostics = json.loads(diagnostics_text)
    assert diagnostics["status"] == {"success": "ok", "degraded": "degraded"}.get(fault, "error")
    if fault == "success":
        assert json.loads(output.read_text()) == payload
    else:
        assert output.read_text() == previous
    logs = capsys.readouterr().out + diagnostics_text
    for forbidden in ("fake-private-key", "raw-error", transcript("video-a"), "coding agents", "https://"):
        assert forbidden not in logs
    assert "videos" not in diagnostics and "takeaway" not in diagnostics
