import shutil
import subprocess

import pytest

from pipeline.audio_quality import master_audio


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg unavailable")
def test_real_two_pass_mastering_measures_final_bytes(tmp_path):
    source = tmp_path / "source.wav"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
         "sine=frequency=440:duration=4", str(source)],
        check=True, capture_output=True,
    )
    original = source.read_bytes()
    target = tmp_path / "mastered.mp3"
    report = master_audio(source, target)
    assert -17 <= report["integrated_lufs"] <= -15
    assert report["true_peak_dbtp"] <= -1
    assert target.stat().st_size > 10000
    assert source.read_bytes() == original
    with pytest.raises(ValueError, match="new output"):
        master_audio(source, target)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="media tools unavailable")
def test_real_twenty_minute_media_gate(tmp_path):
    """Synthetic signal tests long-form processing, not speech or listening quality."""
    from pipeline.audio import analyze_audio
    source = tmp_path / "long-form.flac"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
         "sine=frequency=440:duration=1200", "-c:a", "flac", str(source)],
        check=True, capture_output=True, timeout=120,
    )
    target = tmp_path / "long-form.mp3"
    report = master_audio(source, target)
    measured = analyze_audio(target, min_duration_secs=1200, max_duration_secs=1800)
    assert 1200 <= measured["duration_secs"] < 1201
    assert measured["sha256"] == report["audio_sha256"]
    assert measured["codec"] == "mp3"
    assert measured["sample_rate"] == 44100 and measured["channels"] == 2
