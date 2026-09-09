import shutil
import subprocess

import pytest

from pipeline.audio import AudioValidationError, analyze_audio


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
