"""Offline handoff for user-authorized, transcript/source-reviewed Notebook audio.

Run ``python -m pipeline.reviewed_audio --manifest draft.json --audio source.m4a
--output-dir NEW_DIRECTORY``. The schema-3 or schema-4 draft records the exact UTF-8 ASR
transcript hash, source audio hash, authorization timestamp and bounded public
review evidence. No model, TTS, network, feed or novelty-state writes occur.
Optional ``generation.editing`` records a parent-produced composite with an Edge
editorial correction prefixed to the intact Notebook recording. Its component
hashes are review provenance; this importer verifies the composite input hash
and preserves its content through conversion/mastering, without assembling or
regenerating either component.

The output directory is single-use, including after failure. Recovery of released
episodes must reuse their immutable manifest and MP3, never rerun this importer.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .audio import analyze_audio, file_sha256, narration_duration_bounds
from .disclosure import AI_NARRATION_DISCLOSURE
from .schema import EpisodeManifest, SchemaError


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(data, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write("\n")


def validate_local_handoff(path: Path, audio: Path, manifest: EpisodeManifest) -> None:
    from .local_execution import load, require_artifact

    state = load(path)
    original_hash = manifest.generation.get("editing", {}).get("original_audio_sha256")
    original = path.parent / state["request"]["artifact_name"]
    require_artifact(
        path, original if original_hash else audio, identity=manifest.episode_id,
        kind="notebook-adhoc" if manifest.schema_version == 4 else "notebook-daily",
        parent_request_sha256=manifest.generation.get("request_sha256", ""),
    )
    if original_hash and state["artifact"]["sha256"] != original_hash:
        raise ValueError("correction provenance must retain the validated original recording")


def prepare_reviewed_audio(
    manifest_path: str | Path, audio_path: str | Path, output_dir: str | Path,
    *, local_execution_path: Path | None = None,
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
    if manifest.schema_version not in {3, 4} or manifest.status != "draft":
        raise SchemaError("reviewed audio import requires a schema-3 or schema-4 draft, not a reusable release")
    from .local_execution import FILENAME
    handoff = local_execution_path or audio_path.parent / FILENAME
    if local_execution_path is not None or handoff.exists():
        validate_local_handoff(handoff, audio_path, manifest)
    if AI_NARRATION_DISCLOSURE not in manifest.narration:
        raise SchemaError("reviewed audio narration must contain the approved production disclosure")
    expected_hash = manifest.generation["source_audio_sha256"]
    if manifest.schema_version == 4 or os.environ.get("PODCAST_AUDIO_POLISH", "0") == "1":
        from .audio_quality import repetition_findings
        if repetition_findings(manifest.narration):
            raise SchemaError("adjacent repeated narration requires editorial review")
    if file_sha256(audio_path) != expected_hash:
        raise SchemaError("source audio SHA-256 does not match reviewed provenance")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for reviewed audio import")
    output.mkdir(parents=False, exist_ok=False)
    destination = output / "daily-ai-brief.mp3"
    if manifest.schema_version == 4 or os.environ.get("PODCAST_AUDIO_POLISH", "0") == "1":
        from .audio_quality import master_audio
        manifest.generation["quality"] = master_audio(audio_path, destination)
    else:
        _transcode(ffmpeg, audio_path, destination)
    if file_sha256(audio_path) != expected_hash:
        raise SchemaError("source audio changed during import")
    word_count = len(manifest.narration.split())
    minimum, maximum = (
        narration_duration_bounds(word_count) if manifest.schema_version == 4 else (300, 480)
    )
    analysis = analyze_audio(
        destination, min_duration_secs=minimum, max_duration_secs=maximum,
        full_decode=True, expected_word_count=word_count,
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


def _transcode(ffmpeg: str, audio_path: Path, destination: Path) -> None:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--local-execution", type=Path, help="validated handoff when not beside the original audio")
    args = parser.parse_args(argv)
    publication = prepare_reviewed_audio(
        args.manifest, args.audio, args.output_dir, local_execution_path=args.local_execution,
    )
    print(json.dumps(publication, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
