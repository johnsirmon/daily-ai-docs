import shutil
import subprocess
import json

import pytest

from pipeline.audio import AudioValidationError, analyze_audio


@pytest.mark.parametrize("duration,accepted", [(299.999, False), (300, True), (480, True), (480.001, False)])
def test_grounded_brief_measured_duration_boundaries(monkeypatch, tmp_path, duration, accepted):
    path = tmp_path / "measured.mp3"
    path.write_bytes(b"x" * 12000)
    monkeypatch.setattr("pipeline.audio.shutil.which", lambda name: f"/usr/bin/{name}")
    payload = {"format": {"duration": str(duration)}, "streams": [
        {"codec_name": "mp3", "sample_rate": 24000, "channels": 1},
    ]}
    monkeypatch.setattr(
        "pipeline.audio.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload)),
    )
    if accepted:
        assert analyze_audio(path, min_duration_secs=300, max_duration_secs=480,
                             full_decode=False)["duration_secs"] == duration
    else:
        with pytest.raises(AudioValidationError, match="outside 300-480"):
            analyze_audio(path, min_duration_secs=300, max_duration_secs=480, full_decode=False)


def test_audio_validation_rejects_small_file(tmp_path):
    path = tmp_path / "bad.mp3"
    path.write_bytes(b"not audio")
    with pytest.raises(AudioValidationError, match="small"):
        analyze_audio(path)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg unavailable")
def test_audio_validation_measures_decodable_mp3(tmp_path):
    path = tmp_path / "sample.mp3"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-q:a", "5", str(path),
    ], check=True)
    result = analyze_audio(path, min_duration_secs=1, max_duration_secs=3, min_size_bytes=1000)
    assert result["codec"] == "mp3"
    assert 1.9 <= result["duration_secs"] <= 2.2
    assert len(result["sha256"]) == 64


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg unavailable")
def test_audio_validation_rejects_effectively_silent_mp3(tmp_path):
    path = tmp_path / "silent.mp3"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "anullsrc=r=24000:cl=mono", "-t", "35", str(path),
    ], check=True)
    with pytest.raises(AudioValidationError, match="silent"):
        analyze_audio(path, min_duration_secs=30, max_duration_secs=60)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg unavailable")
def test_audio_validation_rejects_implausible_narration_duration(tmp_path):
    path = tmp_path / "sample.mp3"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-q:a", "5", str(path),
    ], check=True)
    with pytest.raises(AudioValidationError, match="implausible"):
        analyze_audio(
            path,
            min_duration_secs=1,
            max_duration_secs=3,
            min_size_bytes=1000,
            expected_word_count=500,
        )
