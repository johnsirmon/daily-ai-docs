"""Local listening-review UI contracts."""

import hashlib
import json
from pathlib import Path
import threading
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pytest

from pipeline import review_ui
from pipeline.review_ui import (
    REQUIRED_CHECKS,
    create_server,
    load_review_bundle,
    queue_publication,
    record_approval,
    review_payload,
)
from pipeline.schema import EpisodeManifest, SourceEvent, Story
from tests.test_reviewed_audio import draft


def _bundle(tmp_path: Path):
    audio = b"review-audio" * 1000
    event = SourceEvent(
        "e1", "announcement", "Command preview", "https://example.com/preview",
        "Tool", "Agents", "2026-09-19T10:00:00Z", "2026-09-19T10:01:00Z",
        "The tool shows commands before execution.",
    )
    story = Story(
        "s1", ["e1"], "Command preview", event.evidence,
        "Developers can inspect commands before execution.", "watch",
        "Test the preview in a representative workspace.", [event.url], {"total": 80},
    )
    narration = "Production note: This episode uses AI-generated narration. Command previews are now available."
    manifest = EpisodeManifest(
        1, "daily-review", "2026-09-19T10:02:00Z", "ready", {"source": "ok:1"},
        [event], [story], [], narration, "Source-backed preview notes.",
        {"edition": "alert", "preview_only": True},
        {
            "url": "https://example.com/audio.mp3", "size_bytes": len(audio),
            "duration_secs": 100, "sha256": hashlib.sha256(audio).hexdigest(),
        },
    )
    tmp_path.joinpath("episode-manifest.json").write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False), encoding="utf-8",
    )
    tmp_path.joinpath("daily-ai-brief.mp3").write_bytes(audio)
    tmp_path.joinpath("narration.txt").write_text(narration + "\n", encoding="utf-8")
    tmp_path.joinpath("show-notes.txt").write_text("Unpublished résumé notes.", encoding="utf-8")
    return load_review_bundle(tmp_path), audio


def _submission(**changes):
    return {
        "reviewer": "John Sirmon",
        "checks": {name: True for name in REQUIRED_CHECKS},
        "playback_complete": True,
        "listened_seconds": 99,
        "notes": "Complete listening review.",
        **changes,
    }


def _reviewed_bundle(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    audio = b"reviewed-final-mp3" * 1000
    data = draft()
    data["status"] = "ready"
    data["audio"].update({
        "size_bytes": len(audio),
        "duration_secs": 320,
        "sha256": hashlib.sha256(audio).hexdigest(),
        "codec": "mp3",
        "sample_rate": 44100,
        "channels": 2,
    })
    tmp_path.joinpath("episode-manifest.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8",
    )
    tmp_path.joinpath("daily-ai-brief.mp3").write_bytes(audio)
    bundle = load_review_bundle(tmp_path)
    record_approval(bundle, _submission(listened_seconds=319))
    return bundle


def test_approval_binds_exact_bundle_and_never_authorizes_publication(tmp_path):
    bundle, _ = _bundle(tmp_path)
    approval = record_approval(bundle, _submission())
    saved = json.loads(bundle.approval_path.read_text(encoding="utf-8"))

    assert saved == approval
    assert approval["audio_sha256"] == bundle.manifest.audio["sha256"]
    assert approval["manifest_sha256"] == bundle.manifest_sha256
    assert approval["transcript_sha256"] == bundle.transcript_sha256
    assert approval["coverage_percent"] == 99
    assert approval["publication_authorized"] is False
    assert review_payload(bundle)["already_approved"] is True
    with pytest.raises(FileExistsError):
        record_approval(bundle, _submission())


@pytest.mark.parametrize("changes", [
    {"playback_complete": False},
    {"listened_seconds": 97},
    {"checks": {name: name != "claims" for name in REQUIRED_CHECKS}},
    {"reviewer": " "},
])
def test_approval_rejects_incomplete_review(tmp_path, changes):
    bundle, _ = _bundle(tmp_path)
    with pytest.raises(ValueError):
        record_approval(bundle, _submission(**changes))
    assert not bundle.approval_path.exists()


def test_bundle_rejects_audio_hash_mismatch(tmp_path):
    _bundle(tmp_path)
    tmp_path.joinpath("daily-ai-brief.mp3").write_bytes(b"changed")
    with pytest.raises(ValueError, match="byte length|SHA-256"):
        load_review_bundle(tmp_path)


def test_local_server_serves_ui_and_audio_ranges(tmp_path):
    bundle, audio = _bundle(tmp_path)
    server = create_server(bundle, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = server.review_url
        with urlopen(url, timeout=5) as response:
            page = response.read().decode("utf-8")
        assert "Approve this exact recording" in page
        assert "Publish approved recording" in page
        assert "hash-bound local record" in page
        assert review_payload(bundle, allow_publish=True)["publish_reason"] == (
            "Preview-only bundles cannot be published."
        )

        parsed = urlparse(url)
        audio_url = f"http://{parsed.netloc}/audio?{parsed.query}"
        request = Request(audio_url, headers={"Range": "bytes=4-12"})
        with urlopen(request, timeout=5) as response:
            assert response.status == 206
            assert response.headers["Content-Range"] == f"bytes 4-12/{len(audio)}"
            assert response.read() == audio[4:13]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_reviewed_bundle_publication_uploads_exact_assets_and_dispatches(monkeypatch, tmp_path):
    bundle = _reviewed_bundle(tmp_path)
    commands = []
    monkeypatch.setattr(review_ui, "_verify_publication_environment", lambda repository: None)
    monkeypatch.setattr(review_ui, "_release_matches", lambda bundle, repository: False)
    monkeypatch.setattr(
        review_ui, "_run",
        lambda command, **kwargs: commands.append(command) or "",
    )

    queued = queue_publication(bundle, allow_publish=True)

    assert queued["status"] == "queued"
    assert queued["subscriber_confirmed"] is False
    release, workflow = commands
    assert release[:3] == ["gh", "release", "create"]
    assert f"{bundle.audio_path}#daily-ai-brief.mp3" in release
    assert f"{bundle.directory / 'episode-manifest.json'}#episode-manifest.json" in release
    assert "--draft" not in release
    assert workflow[-1] == f"reviewed_episode={bundle.manifest.episode_id}"
    assert (tmp_path / "publication-authorization.json").is_file()
    assert (tmp_path / "publication-queue.json").is_file()


def test_publication_refuses_preview_and_missing_explicit_flag(monkeypatch, tmp_path):
    bundle, _ = _bundle(tmp_path)
    monkeypatch.setattr(
        review_ui, "_run",
        lambda *args, **kwargs: pytest.fail("preview must fail before GitHub commands"),
    )
    with pytest.raises(ValueError, match="Preview-only"):
        queue_publication(bundle, allow_publish=True)

    reviewed = _reviewed_bundle(tmp_path / "reviewed")
    with pytest.raises(ValueError, match="--allow-publish"):
        queue_publication(reviewed, allow_publish=False)
