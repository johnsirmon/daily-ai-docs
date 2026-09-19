import hashlib
import json

import pytest

from pipeline.local_voice import audition, load_profile


def profile_file(tmp_path, *, provider="piper"):
    profile = {
        "provider": provider, "name": "test-voice", "version": "test-version",
        "license_reviewed": True,
    }
    for key in ("model", "config", *(("voice",) if provider == "kokoro" else ())):
        path = tmp_path / f"{key}.bin"
        path.write_bytes(key.encode())
        profile[key] = str(path)
        profile[f"{key}_sha256"] = hashlib.sha256(key.encode()).hexdigest()
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    return path, profile


@pytest.mark.parametrize("provider", ["kokoro", "piper"])
def test_profile_requires_exact_installed_version_and_asset_hashes(monkeypatch, tmp_path, provider):
    path, profile = profile_file(tmp_path, provider=provider)
    monkeypatch.setenv("TTS_LOCAL_PROFILE", str(path))
    monkeypatch.setattr("pipeline.local_voice.importlib.metadata.version", lambda name: "test-version")
    assert load_profile(provider) == profile
    path.with_name("model.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_profile(provider)


@pytest.mark.parametrize("field,value", [("license_reviewed", False), ("version", "other-version")])
def test_unapproved_voice_profile_fails_before_inference(monkeypatch, tmp_path, field, value):
    path, profile = profile_file(tmp_path)
    profile[field] = value
    path.write_text(json.dumps(profile), encoding="utf-8")
    monkeypatch.setenv("TTS_LOCAL_PROFILE", str(path))
    monkeypatch.setattr("pipeline.local_voice.importlib.metadata.version", lambda name: "test-version")
    with pytest.raises(ValueError):
        load_profile("piper")


def test_audition_records_only_measured_acceptance(monkeypatch, tmp_path):
    _, profile = profile_file(tmp_path)
    monkeypatch.setattr("pipeline.local_voice.load_profile", lambda provider: profile)
    monkeypatch.setattr("pipeline.local_voice.generate_local_audio", lambda text, **kwargs: b"test audio")
    monkeypatch.setattr("pipeline.audio.analyze_audio", lambda *args, **kwargs: {
        "duration_secs": 30.0, "sha256": "a" * 64, "size_bytes": 12000,
    })
    script = tmp_path / "script.txt"
    script.write_text("An original public technical audition script.", encoding="utf-8")
    output = tmp_path / "audition.mp3"
    report = audition(script, output, provider="piper")
    assert report["real_time_factor"] >= 0
    assert report["listening_review"] == "not_performed"
    assert report["publication"] == "not_authorized_by_audition"
    assert output.with_suffix(".audition.json").exists()
    with pytest.raises(FileExistsError):
        audition(script, output, provider="piper")
