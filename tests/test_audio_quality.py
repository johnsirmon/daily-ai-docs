import hashlib
from pathlib import Path
import random
import re
import shutil
import subprocess

import pytest

from pipeline.audio import AudioValidationError
from pipeline.audio_quality import master_audio, polish_generated_audio, repetition_findings


@pytest.mark.parametrize("size", [11, 12, 13, 51, 199, 200, 201])
@pytest.mark.parametrize("padding", [("", ""), ("intro ", ""), ("intro ", " ending")])
def test_repetition_detection_preserves_exact_passage_limits(size, padding):
    passage = " ".join(f"word{index}" for index in range(size))
    text = padding[0] + passage + " " + passage.upper() + padding[1]
    assert bool(repetition_findings(text)) == (12 <= size <= 200)


def test_repetition_detection_matches_original_search():
    rng = random.Random(0)
    texts = [
        "", "short", "word " * 23, "word " * 24,
        ("Élan can't re-enter the team's naïve café with co-workers today before noon. " * 2),
    ]
    for _ in range(40):
        tokens = [f"word{rng.randrange(10)}" for _ in range(rng.randrange(24, 450))]
        if rng.choice([True, False]):
            size = rng.randrange(11, min(201, len(tokens) // 2) + 1)
            start = rng.randrange(len(tokens) - 2 * size + 1)
            tokens[start + size:start + 2 * size] = tokens[start:start + size]
        texts.append(" ".join(tokens))
    for text in texts:
        tokens = re.findall(r"\b[\w'-]+\b", text.casefold())
        expected = any(
            tokens[start:start + size] == tokens[start + size:start + 2 * size]
            for size in range(12, min(200, len(tokens) // 2) + 1)
            for start in range(len(tokens) - 2 * size + 1)
        )
        assert repetition_findings(text) == (["adjacent_repeated_passage"] if expected else [])


@pytest.mark.parametrize("preserved", [False, True])
def test_polish_streams_and_preserves_original_audio(monkeypatch, tmp_path, preserved):
    path = tmp_path / "generated.mp3"
    content = b"original audio" * 100000
    digest = hashlib.sha256(content).hexdigest()
    path.write_bytes(content)
    original = path.with_name(f"generated.source-{digest[:16]}.mp3")
    if preserved:
        original.write_bytes(content)
    report = {"audio_sha256": "mastered"}

    def master(source, destination):
        assert source == original
        destination.write_bytes(b"mastered audio")
        return report

    with monkeypatch.context() as patch:
        patch.setattr("pipeline.audio_quality.master_audio", master)
        patch.setattr(Path, "read_bytes", lambda self: pytest.fail("audio must be streamed"))
        assert polish_generated_audio(path) == report
    assert original.read_bytes() == content
    assert path.read_bytes() == b"mastered audio"


def test_polish_rejects_preserved_source_collision(monkeypatch, tmp_path):
    path = tmp_path / "generated.mp3"
    path.write_bytes(b"original audio")
    digest = hashlib.sha256(b"original audio").hexdigest()
    original = path.with_name(f"generated.source-{digest[:16]}.mp3")
    original.write_bytes(b"different audio")
    monkeypatch.setattr("pipeline.audio_quality.master_audio", lambda *args: pytest.fail("must not master"))
    with pytest.raises(AudioValidationError, match="collision"):
        polish_generated_audio(path)
    assert path.read_bytes() == b"original audio"
    assert original.read_bytes() == b"different audio"


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
