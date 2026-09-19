"""Health CLI input-boundary regressions."""

import json
import sys

import pytest

from pipeline import health
from pipeline.schema import EpisodeManifest, SourceEvent, Story


def _candidate():
    event = SourceEvent(
        "e1", "announcement", "Résumé support", "https://example.com/resume",
        "Tool", "Agents", "2026-09-19T10:00:00Z", "2026-09-19T10:01:00Z",
        "The tool adds résumé-aware matching.",
    )
    story = Story(
        "s1", ["e1"], "Résumé support", event.evidence, "Developers can match accented names.",
        "watch", "Test matching with representative names.", [event.url], {"total": 80},
    )
    return EpisodeManifest(
        1, "daily-test", "2026-09-19T10:02:00Z", "candidate", {"source": "ok:1"},
        [event], [story], [], "Narration text.", "Résumé details.", {"edition": "alert"},
        {
            "url": "https://example.com/audio.mp3", "size_bytes": 12000,
            "duration_secs": 60, "sha256": "a" * 64,
        },
    )


def test_candidate_manifest_is_read_as_utf8(monkeypatch, tmp_path, capsys):
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(_candidate().to_dict(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(
        health, "verify_remote_feed",
        lambda *args, **kwargs: {"guid": kwargs["candidate"].episode_id},
    )
    monkeypatch.setattr(sys, "argv", ["pipeline.health", "--candidate", str(candidate)])

    health.main()

    assert json.loads(capsys.readouterr().out) == {"guid": "daily-test"}


def test_malformed_candidate_still_fails(monkeypatch, tmp_path):
    candidate = tmp_path / "candidate.json"
    candidate.write_text('{"description": "résumé"', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pipeline.health", "--candidate", str(candidate)])

    with pytest.raises(json.JSONDecodeError):
        health.main()
