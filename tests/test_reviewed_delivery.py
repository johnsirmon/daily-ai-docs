import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from pipeline import daily
from pipeline.schema import EpisodeManifest, SourceEvent, Story


@pytest.fixture
def release(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "johnsirmon/daily-ai-docs")
    text = "The editor now retains the project's session context."
    event = SourceEvent(
        "feed:context", "official_feed", "Persistent session context",
        "https://code.visualstudio.com/updates/", "VS Code", "Developer tools",
        "2026-09-17T00:00:00Z", "2026-09-18T00:59:00Z", text,
    )
    story = Story(
        "context", [event.event_id], "Retain session context", text,
        "Continue work without restarting the conversation.", "act",
        "Try it on a noncritical project.", [event.url], {"review": 1},
    )
    audio = tmp_path / ".cache/daily-ai-brief.mp3"
    audio.parent.mkdir()
    audio.write_bytes(b"audio" * 2400)
    metrics = {
        "size_bytes": audio.stat().st_size, "duration_secs": 400.0,
        "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "codec": "mp3", "sample_rate": 44100, "channels": 2,
    }
    manifest = EpisodeManifest(
        3, "daily-2026-09-18-notebook-1234abcd", "2026-09-18T01:00:00Z", "ready",
        {"manual:source": "ok:1"}, [event], [story], [], text, "Reviewed source-backed audio.",
        {
            "provider": "gemini-notebook-web", "edition": "notebook",
            "approved_at": "2026-09-18T00:43:35Z", "source_audio_sha256": "a" * 64,
            "transcript": {
                "engine": "faster-whisper", "model": "base.en",
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
            },
            "review": {
                "method": "transcript_source_comparison", "reviewer": "assistant",
                "reviewed_at": "2026-09-18T00:59:00Z",
                "claims": [{"text": text, "event_id": event.event_id, "quote": text}],
                "notes": ["Local ASR reviewed against the public source."],
            },
        },
        {
            **metrics,
            "url": "https://github.com/johnsirmon/daily-ai-docs/releases/download/"
                   "daily-2026-09-18-notebook-1234abcd/daily-ai-brief.mp3",
        },
    )
    calls = []

    def analyze(path, **kwargs):
        calls.append(kwargs)
        content = Path(path).read_bytes()
        return {**metrics, "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}

    monkeypatch.setattr(daily, "analyze_audio", analyze)
    path = audio.parent / "episode-manifest.json"
    path.write_text(json.dumps(manifest.to_dict()))
    return manifest, path, audio, calls


def test_resume_reviewed_validates_bytes_without_changing_publication(release):
    manifest, _, _, calls = release
    result = daily.resume_reviewed_release(manifest.episode_id)
    assert result["outcome"] == "publish" and result["resumed"]
    assert result["tag"] == manifest.episode_id
    assert calls == [{
        "min_duration_secs": 300, "max_duration_secs": 480,
        "expected_word_count": len(manifest.narration.split()),
    }]
    assert not Path("podcast.xml").exists()
    assert not Path("data/state.json").exists()


def test_resume_reviewed_rejects_wrong_identity(release):
    with pytest.raises(RuntimeError, match="identity"):
        daily.resume_reviewed_release("daily-2026-09-18-wrong")
    assert not Path(".cache/publication.json").exists()


def test_resume_reviewed_rejects_wrong_repository(release, monkeypatch):
    manifest, _, _, _ = release
    monkeypatch.setenv("GITHUB_REPOSITORY", "different/repository")
    with pytest.raises(RuntimeError, match="repository and tag"):
        daily.resume_reviewed_release(manifest.episode_id)


def test_resume_reviewed_rejects_swapped_bytes(release):
    manifest, _, audio, _ = release
    audio.write_bytes(b"other" * 2400)
    with pytest.raises(RuntimeError, match="sha256"):
        daily.resume_reviewed_release(manifest.episode_id)
    assert not Path(".cache/publication.json").exists()


def test_resume_reviewed_rejects_wrong_measured_duration(release):
    manifest, path, _, _ = release
    manifest.audio["duration_secs"] = 420.0
    path.write_text(json.dumps(manifest.to_dict()))
    with pytest.raises(RuntimeError, match="duration_secs"):
        daily.resume_reviewed_release(manifest.episode_id)


@pytest.mark.parametrize("delta", [0.026, -0.026, 0.052, -0.052])
def test_resume_accepts_bounded_mp3_frame_estimation_difference(release, delta):
    manifest, path, _, _ = release
    manifest.audio["duration_secs"] += delta
    path.write_text(json.dumps(manifest.to_dict()))
    assert daily.resume_reviewed_release(manifest.episode_id)["outcome"] == "publish"


@pytest.mark.parametrize("delta", [0.055, -0.055])
def test_resume_rejects_duration_difference_beyond_frame_tolerance(release, delta):
    manifest, path, _, _ = release
    manifest.audio["duration_secs"] += delta
    path.write_text(json.dumps(manifest.to_dict()))
    with pytest.raises(RuntimeError, match="duration_secs"):
        daily.resume_reviewed_release(manifest.episode_id)


def test_resume_reviewed_rejects_another_pending_candidate(release):
    manifest, _, _, _ = release
    pending_id = "daily-2026-09-18-notebook-abcdef12"
    pending = replace(
        manifest, episode_id=pending_id, status="candidate",
        audio={**manifest.audio, "url": manifest.audio["url"].replace(manifest.episode_id, pending_id)},
    )
    path = Path("data/episodes") / f"{pending_id}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(pending.to_dict()))
    with pytest.raises(RuntimeError, match="recovery first"):
        daily.resume_reviewed_release(manifest.episode_id)


def test_finalize_reviewed_requires_local_release_reconciliation(release):
    _, path, _, _ = release
    with pytest.raises(RuntimeError, match="requires downloaded release reconciliation"):
        daily.finalize(path, verify_remote=False)
    assert not Path("podcast.xml").exists()


def test_finalize_reviewed_rechecks_audio_and_does_not_advance_state(release):
    manifest, path, _, calls = release
    daily.resume_reviewed_release(manifest.episode_id)
    result = daily.finalize(path, verify_remote=False, publication_path=Path(".cache/publication.json"))
    assert result.status == "candidate"
    assert len(calls) == 2
    assert "Notebook edition" in Path("podcast.xml").read_text()
    from pipeline.podcast import load_episodes
    episode = load_episodes()[0]
    assert episode["title"] == "Retain session context"
    assert episode["description"].endswith(manifest.show_notes)
    assert not Path("data/state.json").exists()
