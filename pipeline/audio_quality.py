"""Measured audio mastering and reproducible editorial checks; no provider calls."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from .audio import AudioValidationError, file_sha256


def repetition_findings(text: str) -> list[str]:
    tokens = re.findall(r"\b[\w'-]+\b", text.casefold())
    for size in range(12, min(200, len(tokens) // 2) + 1):
        matched = 0
        # A run of size equal tokens at this offset is two adjacent copies.
        for index in range(size, len(tokens)):
            if tokens[index] == tokens[index - size]:
                matched += 1
                if matched == size:
                    return ["adjacent_repeated_passage"]
            else:
                matched = 0
    return []


def _ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise AudioValidationError("ffmpeg is required for mastering and loudness measurement")
    return executable


def loudness(path: Path) -> dict[str, float]:
    result = subprocess.run(
        [_ffmpeg(), "-nostdin", "-hide_banner", "-protocol_whitelist", "file", "-i", str(path),
         "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, timeout=900, check=False,
    )
    if result.returncode:
        raise AudioValidationError("loudness measurement failed")
    matches = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", result.stderr, re.DOTALL)
    try:
        data = json.loads(matches[-1])
        measured = {name: float(data[name]) for name in (
            "input_i", "input_tp", "input_lra", "input_thresh", "target_offset",
        )}
    except (ValueError, KeyError, IndexError) as exc:
        raise AudioValidationError("missing or invalid loudness measurements") from exc
    if not all(math.isfinite(value) for value in measured.values()):
        raise AudioValidationError("audio has nonfinite loudness")
    return measured


def master_audio(source: Path, destination: Path) -> dict:
    if source.resolve() == destination.resolve() or destination.exists():
        raise AudioValidationError("mastering requires a new output file")
    measured = loudness(source)
    filters = (
        "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}"
    )
    subprocess.run(
        [_ffmpeg(), "-nostdin", "-hide_banner", "-v", "error", "-xerror", "-n",
         "-protocol_whitelist", "file", "-i", str(source), "-map", "0:a:0",
         "-vn", "-sn", "-dn", "-map_metadata", "-1", "-map_chapters", "-1",
         "-af", filters, "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame",
         "-b:a", "128k", str(destination)],
        check=True, capture_output=True, timeout=900,
    )
    final = loudness(destination)
    version = subprocess.run(
        [_ffmpeg(), "-version"], capture_output=True, text=True, check=True, timeout=15,
    ).stdout.splitlines()[0]
    report = {
        "method": "ffmpeg_loudnorm_two_pass", "ffmpeg": version,
        "integrated_lufs": final["input_i"], "true_peak_dbtp": final["input_tp"],
        "audio_sha256": file_sha256(destination),
    }
    validate_quality_report(report, final=True, audio_sha256=report["audio_sha256"])
    return report


def polish_generated_audio(path: Path) -> dict:
    """Preserve the newly generated input and replace only its unpublished working output."""
    import tempfile
    digest = file_sha256(path)
    original = path.with_name(f"{path.stem}.source-{digest[:16]}{path.suffix}")
    if original.exists():
        if file_sha256(original) != digest:
            raise AudioValidationError("preserved source identity collision")
    else:
        with path.open("rb") as source, original.open("xb") as stream:
            shutil.copyfileobj(source, stream)
    with tempfile.TemporaryDirectory(dir=path.parent) as directory:
        mastered = Path(directory) / "mastered.mp3"
        report = master_audio(original, mastered)
        mastered.replace(path)
    return report


def validate_quality_report(report, *, final: bool, audio_sha256: str | None) -> None:
    if not final:
        if report != {}:
            raise AudioValidationError("draft quality report must be empty until final measurement")
        return
    if not isinstance(report, dict) or set(report) != {
        "method", "ffmpeg", "integrated_lufs", "true_peak_dbtp", "audio_sha256",
    }:
        raise AudioValidationError("incomplete final quality report")
    if report["method"] != "ffmpeg_loudnorm_two_pass" or not isinstance(report["ffmpeg"], str):
        raise AudioValidationError("unsupported audio processing provenance")
    for name in ("integrated_lufs", "true_peak_dbtp"):
        if type(report[name]) not in (int, float) or not math.isfinite(report[name]):
            raise AudioValidationError("audio quality measurements must be finite")
    if not -17 <= report["integrated_lufs"] <= -15 or report["true_peak_dbtp"] > -1:
        raise AudioValidationError("final audio does not meet loudness/true-peak targets")
    if not audio_sha256 or report["audio_sha256"] != audio_sha256:
        raise AudioValidationError("audio quality report is not bound to final bytes")
