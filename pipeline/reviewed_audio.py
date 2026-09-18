"""Offline handoff for user-authorized, transcript/source-reviewed Notebook audio.

Run ``python -m pipeline.reviewed_audio --manifest draft.json --audio source.m4a
--output-dir NEW_DIRECTORY``. The schema-3 draft records the exact UTF-8 ASR
transcript hash, source audio hash, authorization timestamp and bounded public
review evidence. No model, TTS, network, feed or novelty-state writes occur.

The output directory is single-use, including after failure. Recovery of released
episodes must reuse their immutable manifest and MP3, never rerun this importer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .audio import analyze_audio
from .schema import EpisodeManifest, SchemaError


def _file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(data, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write("\n")


def prepare_reviewed_audio(
    manifest_path: str | Path, audio_path: str | Path, output_dir: str | Path,
) -> dict[str, Any]:
    """Transcode an existing recording once and return the daily publication receipt."""
    manifest_path, audio_path = Path(manifest_path).resolve(), Path(audio_path).resolve()
    requested_output = Path(output_dir)
    if requested_output.exists() or requested_output.is_symlink():
        raise FileExistsError("reviewed audio output directory must be new and unused")
    output = requested_output.resolve()
    for source in (manifest_path, audio_path):
        if source == output or output in source.parents:
            raise ValueError("source and output paths must not collide")
        if not source.is_file():
            raise FileNotFoundError(f"reviewed audio input is missing: {source}")
    if manifest_path == audio_path:
        raise ValueError("manifest and source audio must be distinct files")
    manifest = EpisodeManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
    if manifest.schema_version != 3 or manifest.status != "draft":
        raise SchemaError("reviewed audio import requires a schema-3 draft, not a reusable release")
    expected_hash = manifest.generation["source_audio_sha256"]
    if _file_sha256(audio_path) != expected_hash:
        raise SchemaError("source audio SHA-256 does not match reviewed provenance")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for reviewed audio import")
    output.mkdir(parents=False, exist_ok=False)
    destination = output / "daily-ai-brief.mp3"
    subprocess.run(
        [
            ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror", "-n",
            "-protocol_whitelist", "file", "-i", str(audio_path),
            "-map", "0:a:0", "-vn", "-sn", "-dn", "-map_metadata", "-1", "-map_chapters", "-1",
            "-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-f", "mp3", str(destination),
        ],
        check=True, capture_output=True, text=True, timeout=600,
    )
    if _file_sha256(audio_path) != expected_hash:
        raise SchemaError("source audio changed during import")
    analysis = analyze_audio(
        destination, min_duration_secs=300, max_duration_secs=480,
        full_decode=True, expected_word_count=len(manifest.narration.split()),
    )
    manifest.audio.update({key: value for key, value in analysis.items() if key != "path"})
    manifest.status = "ready"
    manifest.validate(require_audio=True)
    prepared_manifest = output / "episode-manifest.json"
    publication = {
        "outcome": "publish",
        "episode_id": manifest.episode_id,
        "tag": manifest.episode_id,
        "manifest_path": str(prepared_manifest),
        "audio_path": str(destination),
        "audio_url": manifest.audio["url"],
        "dry_run": False,
    }
    _write_json(prepared_manifest, manifest.to_dict())
    _write_json(output / "publication.json", publication)
    return publication


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    publication = prepare_reviewed_audio(args.manifest, args.audio, args.output_dir)
    print(json.dumps(publication, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
