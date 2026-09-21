import hashlib
from pathlib import Path
import shutil
import subprocess
import json

import pytest

from pipeline.audio import AudioValidationError, analyze_audio, file_sha256, narration_duration_bounds


@pytest.mark.parametrize("size", [0, 1, 262144, 1048577])
def test_file_sha256_streams_exact_bytes(monkeypatch, tmp_path, size):
    content = (b"audio\x00\xff" * (size // 7 + 1))[:size]
    path = tmp_path / "audio.mp3"
    path.write_bytes(content)
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("audio must be streamed"))
    assert file_sha256(path) == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize("full_decode,returncode,stderr,error", [
    (False, 0, "", None),
    (True, 0, "", None),
    (True, 1, "decode failure", "full decode"),
    (True, 1, "filter failure", "silence measurement"),
    (True, 0, "silence_duration: 29", "effectively silent"),
    (True, 0, "silence_duration: 2", None),
])
def test_audio_decode_and_silence_share_one_pass(monkeypatch, tmp_path, full_decode, returncode, stderr, error):
    path = tmp_path / "measured.mp3"
    content = b"x" * 12000
    path.write_bytes(content)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if command[0] == "ffprobe":
            payload = {"format": {"duration": "30"}, "streams": [
                {"codec_name": "mp3", "sample_rate": "24000", "channels": 1},
            ]}
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload))
        assert "-xerror" in command
        assert command[command.index("-v") + 1] == "info"
        assert command[command.index("-af") + 1] == "silencedetect=noise=-50dB:d=2"
        return subprocess.CompletedProcess(command, returncode, stderr=stderr)

    monkeypatch.setattr("pipeline.audio.shutil.which", lambda name: name)
    monkeypatch.setattr("pipeline.audio.subprocess.run", run)
    if error:
        with pytest.raises(AudioValidationError, match=error):
            analyze_audio(path, full_decode=full_decode)
    else:
        assert analyze_audio(path, full_decode=full_decode)["sha256"] == hashlib.sha256(content).hexdigest()
    assert [command[0] for command in commands] == (["ffprobe", "ffmpeg"] if full_decode else ["ffprobe"])


@pytest.mark.parametrize("words,feasible", [(211, False), (258, False), (259, True), (407, True)])
def test_normal_edition_feasibility_uses_existing_plausibility_bounds(words, feasible):
    minimum, maximum = narration_duration_bounds(words)
    assert minimum == words / 155 * 60 * 0.55
    assert maximum == words / 155 * 60 * 1.8
    assert (max(minimum, 180) <= min(maximum, 600)) is feasible


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
