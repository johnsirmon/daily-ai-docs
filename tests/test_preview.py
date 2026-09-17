import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from pipeline import daily, preview
from pipeline.models_client import EditorialProviderError
from pipeline.schema import EpisodeManifest
from tests.test_grounded_editorial import manifest, run_editorial


@pytest.fixture
def setup(tmp_path, monkeypatch):
    for name in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL", "AI_PROVIDER", "OPENAI_API_KEY",
                 "AI_MAX_RETRIES", "AI_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI_EDITORIAL", "required")
    monkeypatch.setenv("TTS_PROVIDER", "edge")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-not-a-real-key")
    history = tmp_path / "history"
    (history / "data/episodes").mkdir(parents=True)
    (history / "data/state.json").write_text(json.dumps({
        "schema_version": 1, "seen_event_ids": ["already-published"],
        "last_episode_id": "last-confirmed",
    }))
    (history / "podcast.xml").write_text("unchanged feed")
    config = tmp_path / "topics.yaml"
    config.write_text("daily: {}")
    monkeypatch.setattr(preview, "verify_model_access", lambda config=None: {
        "model": "gemini-3.8-flash", "metadata_access_verified": True,
    })
    return {"config_path": config, "history_root": history, "output_dir": tmp_path / "output",
            "free_tier_confirmed": True}


def write_prepared(*, ready=True):
    (stories, generation), _ = run_editorial()
    result = manifest(stories, generation)
    audio = b"validated-audio-fixture"
    result.audio = {"url": "https://example.com/planned.mp3"}
    if ready:
        result.status = "ready"
        result.audio.update(size_bytes=len(audio), duration_secs=400,
                            sha256=hashlib.sha256(audio).hexdigest())
    cache = Path(".cache")
    cache.mkdir()
    (cache / "episode-manifest.json").write_text(json.dumps(result.to_dict()))
    (cache / "daily-ai-brief.mp3").write_bytes(audio)
    return {"outcome": "publish", "audio_path": str(cache / "daily-ai-brief.mp3")}


def test_ready_preview_is_isolated_and_cannot_be_finalized(setup, monkeypatch):
    original_cwd = Path.cwd()
    original_state = (setup["history_root"] / "data/state.json").read_bytes()

    def prepare(config_path, *, force):
        assert config_path == setup["config_path"]
        assert force is True
        assert Path.cwd() != original_cwd
        assert daily.load_state()["seen_event_ids"] == ["already-published"]
        return write_prepared()

    monkeypatch.setattr(daily, "prepare", prepare)
    result = preview.run_preview(**setup)
    assert result["status"] == "ready"
    assert result["generation"]["calls"] == 2
    assert result["history_last_episode_id"] == "last-confirmed"
    assert Path.cwd() == original_cwd
    assert (setup["history_root"] / "data/state.json").read_bytes() == original_state
    assert (setup["history_root"] / "podcast.xml").read_text() == "unchanged feed"
    assert not (setup["history_root"] / "data/runs").exists()
    output = setup["output_dir"]
    assert (output / "daily-ai-brief.mp3").read_bytes() == b"validated-audio-fixture"
    path = output / "episode-manifest.json"
    saved = EpisodeManifest.from_dict(json.loads(path.read_text()))
    assert saved.generation["preview_only"] is True
    assert (output / "narration.txt").read_text().strip() == saved.narration
    with pytest.raises(RuntimeError, match="preview artifacts cannot be finalized"):
        daily.finalize(path, verify_remote=False, feed_path=setup["history_root"] / "podcast.xml")


def test_skip_preserves_receipt_without_audio_or_published_state_changes(setup, monkeypatch):
    def prepare(*args, **kwargs):
        return daily._skip(
            now=preview.datetime.now(preview.timezone.utc),
            reason="insufficient_new_information", health={"public": "ok:0"},
            minimum_health=0.6, notes=["Routine version-only releases omitted."],
        )

    monkeypatch.setattr(daily, "prepare", prepare)
    result = preview.run_preview(**setup)
    assert result["status"] == "skipped"
    assert result["evaluation"]["last_episode_id"] == "last-confirmed"
    assert not (setup["output_dir"] / "daily-ai-brief.mp3").exists()
    assert not (setup["output_dir"] / "episode-manifest.json").exists()
    assert not (setup["history_root"] / "data/runs").exists()


def test_audio_failure_retains_only_verified_script_and_safe_error(setup, monkeypatch, caplog):
    original_cwd = Path.cwd()

    def prepare(*args, **kwargs):
        write_prepared(ready=False)
        raise RuntimeError("TTS failed test-only-not-a-real-key")

    monkeypatch.setattr(daily, "prepare", prepare)
    with pytest.raises(preview.PreviewError, match="TTS failed"):
        preview.run_preview(**setup)
    assert Path.cwd() == original_cwd
    assert (setup["output_dir"] / "narration.txt").is_file()
    assert not (setup["output_dir"] / "daily-ai-brief.mp3").exists()
    report = (setup["output_dir"] / "preview-report.json").read_text()
    assert "test-only-not-a-real-key" not in report + caplog.text
    assert json.loads(report)["status"] == "failed"


@pytest.mark.parametrize("change", ["no-confirmation", "paid-tts", "legacy-mode", "missing-history"])
def test_preview_preconditions_fail_before_any_provider_call(setup, monkeypatch, change):
    if change == "no-confirmation":
        setup["free_tier_confirmed"] = False
    elif change == "paid-tts":
        monkeypatch.setenv("TTS_PROVIDER", "openai")
    elif change == "legacy-mode":
        monkeypatch.setenv("AI_EDITORIAL", "off")
    else:
        setup["history_root"] = setup["output_dir"]
    monkeypatch.setattr(preview, "verify_model_access", lambda config=None: pytest.fail("provider must not be called"))
    with pytest.raises(preview.PreviewError):
        preview.run_preview(**setup)
    assert json.loads((setup["output_dir"] / "preview-report.json").read_text())["status"] == "failed"


def test_existing_output_is_not_reused_or_overwritten(setup):
    setup["output_dir"].mkdir()
    marker = setup["output_dir"] / "daily-ai-brief.mp3"
    marker.write_bytes(b"earlier preview")
    with pytest.raises(FileExistsError):
        preview.run_preview(**setup)
    assert marker.read_bytes() == b"earlier preview"


def test_mismatched_audio_is_not_exported(setup, monkeypatch):
    def prepare(*args, **kwargs):
        publication = write_prepared()
        Path(publication["audio_path"]).write_bytes(b"different bytes")
        return publication

    monkeypatch.setattr(daily, "prepare", prepare)
    with pytest.raises(preview.PreviewError, match="does not match"):
        preview.run_preview(**setup)
    assert not (setup["output_dir"] / "daily-ai-brief.mp3").exists()


@pytest.mark.parametrize("response_status,metadata", [
    (403, {}),
    (302, {}),
    (200, {"name": "models/another-model", "supportedGenerationMethods": ["generateContent"]}),
    (200, {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": None}),
])
def test_model_preflight_rejects_unusable_access(monkeypatch, response_status, metadata):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    response = MagicMock(status_code=response_status)
    response.__enter__.return_value = response
    response.json.return_value = metadata
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)
    with pytest.raises(EditorialProviderError):
        preview.verify_model_access()


@pytest.mark.parametrize("config,model", [(None, "gemini-3.8-flash"), ({"model": "gemini-3.7-flash"}, "gemini-3.7-flash")])
def test_model_preflight_uses_actual_model_and_header_only(monkeypatch, config, model):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    response = MagicMock(status_code=200)
    response.__enter__.return_value = response
    response.json.return_value = {
        "name": f"models/{model}", "supportedGenerationMethods": ["generateContent"],
    }
    get = MagicMock(return_value=response)
    monkeypatch.setattr(requests, "get", get)
    result = preview.verify_model_access(config)
    args, kwargs = get.call_args
    assert args == (f"https://generativelanguage.googleapis.com/v1beta/models/{model}",)
    assert kwargs["headers"] == {"x-goog-api-key": "test-only-not-a-real-key"}
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"] == (5, 30)
    assert result == {"model": model, "metadata_access_verified": True}
