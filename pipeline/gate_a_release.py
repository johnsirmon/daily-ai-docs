"""Fail-closed importer for the one authorized Gate A personal release.

This module is deliberately not a general preview-to-publication converter.  It accepts
only the exact hash-bound Gate A preview and mastered MP3 authorized by John on
2026-09-23, preserves the MP3 bytes, and emits the one schema-3 manifest accepted by
the existing reviewed-release publisher.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from .audio import analyze_audio, file_sha256
from .schema import EpisodeManifest, SchemaError

EPISODE_ID = "daily-2026-09-23-gate-a-f518254"
PREVIEW_EPISODE_ID = "gate-a-2026-09-23-f518254"
AUTHORIZED_AT = "2026-09-23T15:24:10Z"
PREVIEW_MANIFEST_SHA256 = "3ecef0a7bd3a7aa6f4a87040bac30526f8f000ec769400aca1e96fdf85269eb5"
AUDIO_SHA256 = "9b66721d363721a1aef0c0154c6c05117d1ba1db42a27132185e43c88f196a7b"
ORIGINAL_PROVIDER_AUDIO_SHA256 = "a5a1fb08408d60b604d77ce9e48515226f4c7ed3ad19bf1cfb9c96ac62787e16"
SCRIPT_SHA256 = "14461847571b704ad0fca509c16b025bc583a9f8d8c73545ee345998c72c5385"
NARRATION_SHA256 = "b93e06eb3ab31197e3dc9d8ab4d49d1c01376349e680234c9d25bbbab9e4ab39"
IMPLEMENTATION_SHA = "f51825452c36f22d51db097af2acd5b3cc05dd86"
EDITION = "gate-a-one-release-waiver"
# These two independent pins bind both the authorized semantic manifest and the
# exact JSON asset uploaded by the publisher. They are updated only when the
# one-release contract itself is re-authorized and independently reviewed.
AUTHORIZED_MANIFEST_CONTENT_SHA256 = "4be2b50e9cd6d8d89a411f0336a4db0d04ef62731b24e65fd40f44d8ae6b43cf"
AUTHORIZED_MANIFEST_SHA256 = "ef0d867772b4e2434866f1c8abaade366a02378436b77310dfaaf3f275ea2874"
SOURCE_HASHES = {
    "https://github.blog/changelog/2026-09-22-opentelemetry-in-the-github-copilot-app/":
        "9cc1bc0183c1fe83fd677d0ec188131bb5465adfa31452490d53b82892c4338d",
    "https://github.blog/changelog/2026-09-22-security-improvements-for-ssh":
        "bfa7caad199dfd48727b93526bbc4d5d2b007d6200daea59f7ba85a48ac1dae7",
    "https://github.blog/changelog/2026-09-22-deprecation-notice-all-platform-codeql-bundle/":
        "888f0674ef9cf9e5b1168042431c8693ea29c8da23d02919f330abf9f19303a9",
}
CLAIM_TEXT = {
    "github-copilot-app-otel-2026-09-22":
        "GitHub has added OpenTelemetry configuration through enterprise-managed settings.",
    "github-ssh-crypto-transition-2026-09-22":
        "First, H-T-T-P-S remotes are unaffected.",
    "codeql-all-platform-bundle-deprecation-2026-09-22":
        "GitHub says it will remove the combined bundle in mid-March twenty twenty-seven and directs users to operating-system and architecture-specific downloads.",
}
VOICE = {"name": "en-US-AriaNeural", "rate": "+0%", "pitch": "+0Hz"}
WAIVER = {
    "scope": "exact_personal_release_only",
    "authorized_by": "John",
    "authorized_at": AUTHORIZED_AT,
    "preview_episode_id": PREVIEW_EPISODE_ID,
    "preview_manifest_sha256": PREVIEW_MANIFEST_SHA256,
    "script_sha256": SCRIPT_SHA256,
    "implementation_sha": IMPLEMENTATION_SHA,
    "original_provider_audio_sha256": ORIGINAL_PROVIDER_AUDIO_SHA256,
    "listening_decision": "board_comment_substitutes_for_missing_ui_record",
    "audible_disclosure": "waived_for_this_release_only",
    "coverage_policy": "required_exact_frozen_gate_a_evidence",
    "source_sha256": SOURCE_HASHES,
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _semantic_digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return _digest(canonical)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def validate_exact_publication_manifest(
    manifest: EpisodeManifest, *, manifest_sha256: str | None = None,
) -> None:
    """Validate the immutable one-release waiver without weakening other schemas."""
    generation = manifest.generation
    if (
        manifest.schema_version != 3
        or manifest.episode_id != EPISODE_ID
        or generation.get("edition") != EDITION
        or generation.get("provider") != "edge"
        or generation.get("approved_at") != AUTHORIZED_AT
        or generation.get("voice") != VOICE
        or generation.get("waiver") != WAIVER
        or generation.get("source_audio_sha256") != AUDIO_SHA256
        or manifest.audio.get("sha256") != AUDIO_SHA256
        or _digest(manifest.narration.encode("utf-8")) != NARRATION_SHA256
        or _digest((manifest.narration + "\n").encode("utf-8")) != SCRIPT_SHA256
        or _semantic_digest(asdict(manifest)) != AUTHORIZED_MANIFEST_CONTENT_SHA256
    ):
        raise SchemaError("Gate A one-release manifest does not match its exact authorization")
    if manifest_sha256 is not None and manifest_sha256 != AUTHORIZED_MANIFEST_SHA256:
        raise SchemaError("Gate A one-release manifest bytes are not the exact authorized asset")
    observed = {event.url: event.metadata.get("source_document_sha256") for event in manifest.source_events}
    if observed != SOURCE_HASHES or any(
        event.metadata.get("evidence_status") != "reviewed_excerpts"
        or set(event.metadata) != {"source_document_sha256", "evidence_status"}
        for event in manifest.source_events
    ):
        raise SchemaError("Gate A one-release sources do not match the frozen required evidence")
    if set(CLAIM_TEXT) != {event.event_id for event in manifest.source_events}:
        raise SchemaError("Gate A one-release source identities do not match the frozen evidence")


def _validate_preview(preview_bytes: bytes, audio_path: Path) -> EpisodeManifest:
    if _digest(preview_bytes) != PREVIEW_MANIFEST_SHA256:
        raise SchemaError("Gate A preview manifest SHA-256 is not authorized")
    preview = EpisodeManifest.from_dict(json.loads(preview_bytes.decode("utf-8")))
    if (
        preview.schema_version != 1
        or preview.episode_id != PREVIEW_EPISODE_ID
        or preview.status != "ready"
        or preview.generation.get("preview_only") is not True
        or preview.generation.get("implementation_sha") != IMPLEMENTATION_SHA
        or preview.generation.get("script_sha256") != SCRIPT_SHA256
        or preview.generation.get("voice") != VOICE
        or preview.audio.get("sha256") != AUDIO_SHA256
        or {event.url: event.metadata.get("content_sha256") for event in preview.source_events}
        != SOURCE_HASHES
        or set(CLAIM_TEXT) != {event.event_id for event in preview.source_events}
    ):
        raise SchemaError("Gate A preview identity or frozen evidence is not authorized")
    if file_sha256(audio_path) != AUDIO_SHA256:
        raise SchemaError("Gate A audio SHA-256 is not authorized")
    return preview


def _publication_manifest_data(preview: EpisodeManifest) -> dict[str, Any]:
    """Build the sole authorized semantic manifest before schema validation."""
    data = deepcopy(preview.to_dict())
    data.update(
        schema_version=3,
        episode_id=EPISODE_ID,
        published_at=AUTHORIZED_AT,
        status="ready",
        show_notes=(
            "Production disclosure: AI-generated narration from Edge en-US-AriaNeural. "
            "John waived an audible disclosure only for this exact personal release after full listening.\n\n"
            "Coverage is required and limited to the three hash-bound official GitHub sources frozen in "
            "the Gate A evidence. Exa returned HTTP 401 and broader Hermes, MCP, and open-source coverage "
            "remains incomplete; this episode does not claim a comprehensive quiet-news scan."
        ),
    )
    claims = []
    for event in data["source_events"]:
        event["metadata"] = {
            "source_document_sha256": SOURCE_HASHES[event["url"]],
            "evidence_status": "reviewed_excerpts",
        }
        claims.append({
            "text": CLAIM_TEXT[event["event_id"]],
            "event_id": event["event_id"],
            "quote": event["evidence"],
        })
    for story in data["stories"]:
        story["editorial"] = {}
    data["generation"] = {
        "edition": EDITION,
        "provider": "edge",
        "approved_at": AUTHORIZED_AT,
        "source_audio_sha256": AUDIO_SHA256,
        "transcript": {
            "engine": "faster-whisper",
            "model": "Systran/faster-whisper-small.en",
            "sha256": NARRATION_SHA256,
        },
        "review": {
            "method": "transcript_source_comparison",
            "reviewed_at": AUTHORIZED_AT,
            "reviewer": "assistant",
            "claims": claims,
            "notes": [
                "John approved the exact fully listened audio by board comment; the missing UI record is substituted only for this release.",
                "Audible AI disclosure is waived only for this exact personal release; the written disclosure remains in show notes.",
                "Local ASR measured WER 0.148256; exact script, source excerpts, and material caveats were separately reviewed.",
            ],
        },
        "quality": deepcopy(preview.generation["quality"]),
        "voice": deepcopy(VOICE),
        "waiver": deepcopy(WAIVER),
    }
    data["audio"]["url"] = (
        f"https://github.com/johnsirmon/daily-ai-docs/releases/download/{EPISODE_ID}/daily-ai-brief.mp3"
    )
    return data


def build_publication_manifest(preview: EpisodeManifest) -> EpisodeManifest:
    """Create the truthful non-preview schema-3 contract for the exact frozen bytes."""
    data = _publication_manifest_data(preview)
    manifest = EpisodeManifest.from_dict(data)
    manifest.validate(require_audio=True)
    return manifest


def prepare_authorized_release(
    preview_manifest_path: str | Path,
    audio_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Prepare one immutable reviewed-release bundle without changing audio bytes."""
    preview_path, source_audio = Path(preview_manifest_path).resolve(), Path(audio_path).resolve()
    requested_output = Path(output_dir)
    if requested_output.exists() or requested_output.is_symlink():
        raise FileExistsError("Gate A release output directory must be new and unused")
    if not preview_path.is_file() or not source_audio.is_file():
        raise FileNotFoundError("Gate A release requires the frozen preview manifest and MP3")
    output = requested_output.resolve()
    if any(source == output or output in source.parents for source in (preview_path, source_audio)):
        raise ValueError("Gate A release inputs and output must not collide")

    preview_bytes = preview_path.read_bytes()
    preview = _validate_preview(preview_bytes, source_audio)
    manifest = build_publication_manifest(preview)
    output.mkdir(parents=True, exist_ok=False)
    destination = output / "daily-ai-brief.mp3"
    with source_audio.open("rb") as source, destination.open("xb") as target:
        shutil.copyfileobj(source, target)
    if file_sha256(source_audio) != AUDIO_SHA256 or file_sha256(destination) != AUDIO_SHA256:
        raise SchemaError("Gate A audio changed during immutable import")
    measured = analyze_audio(
        destination, min_duration_secs=300, max_duration_secs=480,
        full_decode=True, expected_word_count=len(manifest.narration.split()),
    )
    for field in ("size_bytes", "sha256", "codec", "sample_rate", "channels"):
        if measured[field] != manifest.audio[field]:
            raise SchemaError(f"Gate A measured audio {field} does not match the frozen manifest")
    if abs(float(measured["duration_secs"]) - float(manifest.audio["duration_secs"])) > 0.055:
        raise SchemaError("Gate A measured duration does not match the frozen manifest")

    manifest_path = output / "episode-manifest.json"
    _write_json(manifest_path, manifest.to_dict())
    if file_sha256(manifest_path) != AUTHORIZED_MANIFEST_SHA256:
        raise SchemaError("Gate A generated manifest bytes are not the exact authorized asset")
    (output / "narration.txt").write_text(manifest.narration + "\n", encoding="utf-8")
    (output / "show-notes.txt").write_text(manifest.show_notes + "\n", encoding="utf-8")
    waiver_record = {
        "schema_version": 1,
        "purpose": "one_release_board_approval_substitution",
        "episode_id": EPISODE_ID,
        "authorized_at": AUTHORIZED_AT,
        "authorized_by": "John",
        "audio_sha256": AUDIO_SHA256,
        "manifest_sha256": AUTHORIZED_MANIFEST_SHA256,
        "script_sha256": SCRIPT_SHA256,
        "audible_disclosure": "waived_for_this_release_only",
        "publication_authorized": True,
    }
    _write_json(output / "listening-waiver.json", waiver_record)
    return waiver_record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-manifest", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(prepare_authorized_release(
        args.preview_manifest, args.audio, args.output_dir,
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
