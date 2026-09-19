"""Opt-in local voice auditions using operator-installed, hash-pinned assets.

No packages or models are installed by this module. These providers remain experimental
until an operator has reviewed licensing and auditioned the actual voice on their machine.
"""

from __future__ import annotations

import hashlib
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import wave


def load_profile(provider: str) -> dict:
    if provider not in {"kokoro", "piper"}:
        raise ValueError("unsupported local provider")
    location = os.environ.get("TTS_LOCAL_PROFILE")
    if not location:
        raise ValueError("TTS_LOCAL_PROFILE must identify an approved local voice profile")
    profile = json.loads(Path(location).read_text(encoding="utf-8"))
    required = {"provider", "version", "name", "license_reviewed", "model", "config", "model_sha256",
                "config_sha256"}
    if provider == "kokoro":
        required |= {"voice", "voice_sha256"}
    if not isinstance(profile, dict) or set(profile) != required or profile["provider"] != provider:
        raise ValueError("invalid local voice profile")
    if profile["license_reviewed"] is not True:
        raise ValueError("voice model licensing must be reviewed before synthesis")
    package = "kokoro" if provider == "kokoro" else "piper-tts"
    try:
        version = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(f"{package} is not installed in the approved voice environment") from exc
    if version != profile["version"]:
        raise ValueError("installed local provider version differs from the approved profile")
    for name in ("model", "config", *(("voice",) if provider == "kokoro" else ())):
        path = Path(profile[name])
        expected = profile[f"{name}_sha256"]
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError(f"invalid {name} checksum")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"local voice {name} checksum mismatch")
    return profile


def generate_local_audio(text: str, *, provider: str) -> bytes:
    if provider not in {"kokoro", "piper"}:
        raise ValueError("unsupported local provider")
    profile = load_profile(provider)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for local TTS encoding")
    with tempfile.TemporaryDirectory() as directory:
        raw = Path(directory) / "voice.wav"
        if provider == "piper":
            from piper import PiperVoice
            voice = PiperVoice.load(profile["model"], config_path=profile["config"], use_cuda=False)
            with wave.open(str(raw), "wb") as output:
                voice.synthesize_wav(text, output)
        else:
            # Model, config, and voice are supplied locally; Hub downloads are prohibited.
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            from kokoro import KModel, KPipeline
            import soundfile
            import torch
            import spacy.util
            if not spacy.util.is_package("en_core_web_sm"):
                raise RuntimeError("Kokoro English G2P requires a preinstalled en_core_web_sm package")
            model = KModel(config=profile["config"], model=profile["model"]).to("cpu").eval()
            pipeline = KPipeline(lang_code="a", model=model, device="cpu")
            embedding = torch.load(profile["voice"], map_location="cpu", weights_only=True)
            with soundfile.SoundFile(str(raw), "w", samplerate=24000, channels=1, subtype="PCM_16") as output:
                for _, _, audio in pipeline(text, voice=embedding, speed=1, split_pattern=r"\n+"):
                    output.write(audio)
        result = Path(directory) / "voice.mp3"
        subprocess.run(
            [ffmpeg, "-nostdin", "-v", "error", "-xerror", "-n", "-i", str(raw),
             "-c:a", "libmp3lame", "-b:a", "128k", str(result)],
            check=True, capture_output=True, timeout=900,
        )
        return result.read_bytes()


def audition(script: Path, output: Path, *, provider: str) -> dict:
    """Measure an unpublished audition without claiming listening acceptance."""
    from .audio import analyze_audio
    text = script.read_text(encoding="utf-8")
    report_path = output.with_suffix(".audition.json")
    if output.exists() or report_path.exists():
        raise FileExistsError("audition media and report must be new")
    if not text.strip() or len(text) > 60000:
        raise ValueError("audition script must contain 1-60000 characters")
    started = time.perf_counter()
    profile = load_profile(provider)
    content = generate_local_audio(text, provider=provider)
    elapsed = time.perf_counter() - started
    with output.open("xb") as stream:
        stream.write(content)
    measured = analyze_audio(
        output, min_duration_secs=1, max_duration_secs=1800,
        expected_word_count=len(text.split()),
    )
    report = {
        "provider": provider, "voice": profile["name"], "version": profile["version"],
        "model_sha256": profile["model_sha256"],
        "script_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "generation_seconds": round(elapsed, 3),
        "real_time_factor": round(elapsed / measured["duration_secs"], 4),
        "audio": {key: value for key, value in measured.items() if key != "path"},
        "listening_review": "not_performed", "peak_memory": "not_measured",
        "publication": "not_authorized_by_audition",
    }
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure an unpublished, operator-provisioned local voice audition")
    parser.add_argument("--provider", required=True, choices=("kokoro", "piper"))
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audition(args.script, args.output, provider=args.provider), indent=2))


if __name__ == "__main__":
    main()
