"""Validate and measure final podcast audio before publication."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict


class AudioValidationError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def narration_duration_bounds(word_count: int) -> tuple[float, float]:
    """Return the existing plausible duration interval for a spoken word count."""
    expected_duration = word_count / 155 * 60
    return expected_duration * 0.55, expected_duration * 1.8


def analyze_audio(
    path: str | Path,
    *,
    min_duration_secs: float = 20.0,
    max_duration_secs: float = 600.0,
    full_decode: bool = True,
    min_size_bytes: int = 10_000,
    expected_word_count: int | None = None,
    allowed_codecs: tuple[str, ...] = ("mp3",),
) -> Dict[str, Any]:
    audio = Path(path)
    if not audio.is_file() or audio.stat().st_size < min_size_bytes:
        raise AudioValidationError("audio is missing or implausibly small")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise AudioValidationError("ffprobe is required for production audio validation")
    result = subprocess.run(
        [
            ffprobe,
            "-v", "error",
            "-protocol_whitelist", "file",
            "-show_entries", "format=duration,size,format_name:stream=codec_name,sample_rate,channels",
            "-of", "json",
            str(audio),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AudioValidationError(f"ffprobe rejected audio: {result.stderr.strip()}")
    try:
        payload = json.loads(result.stdout)
        duration = float(payload["format"]["duration"])
        streams = payload.get("streams") or []
        stream = next(item for item in streams if item.get("codec_name") in allowed_codecs)
    except (ValueError, KeyError, StopIteration, TypeError) as exc:
        raise AudioValidationError("audio is not a measurable supported recording") from exc
    if not math.isfinite(duration) or not min_duration_secs <= duration <= max_duration_secs:
        raise AudioValidationError(
            f"duration {duration:.1f}s is outside {min_duration_secs:.0f}-{max_duration_secs:.0f}s"
        )
    if expected_word_count:
        plausible_minimum, plausible_maximum = narration_duration_bounds(expected_word_count)
        if duration < plausible_minimum or duration > plausible_maximum:
            raise AudioValidationError(
                f"duration {duration:.1f}s is implausible for {expected_word_count} narration words"
            )
    if full_decode:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise AudioValidationError("ffmpeg is required for full decode validation")
        silence = subprocess.run(
            [
                ffmpeg, "-nostdin", "-v", "info", "-xerror", "-protocol_whitelist", "file", "-i", str(audio),
                "-af", "silencedetect=noise=-50dB:d=2", "-f", "null", "-",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(120, min(900, int(duration * 2))),
        )
        if silence.returncode:
            raise AudioValidationError("audio failed full decode or silence measurement")
        silence_durations = [
            float(value)
            for value in re.findall(r"silence_duration:\s*([0-9.]+)", silence.stderr)
        ]
        if silence_durations and max(silence_durations) >= duration * 0.9:
            raise AudioValidationError("audio is effectively silent")
    return {
        "path": str(audio),
        "size_bytes": audio.stat().st_size,
        "duration_secs": round(duration, 3),
        "sha256": file_sha256(audio),
        "codec": stream.get("codec_name"),
        "sample_rate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
    }
