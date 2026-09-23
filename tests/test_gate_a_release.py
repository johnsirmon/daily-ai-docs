"""Regression coverage for the exact, non-reusable Gate A release waiver."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from pipeline import daily, gate_a_release
from pipeline.gate_a_release import build_publication_manifest, validate_exact_publication_manifest
from pipeline.review_ui import _load_approval, load_review_bundle, queue_publication
from pipeline.schema import EpisodeManifest, SchemaError


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _synthetic_contract(monkeypatch, audio: bytes = b"exact-audio" * 1000):
    narration = (
        "The tool adds a reviewed trace. "
        "Operators can inspect the trace before changing production. " * 50
    ).strip()
    narration_sha = _digest(narration.encode())
    script_sha = _digest((narration + "\n").encode())
    audio_sha = _digest(audio)
    url = "https://example.com/change"
    event_id = "exact-event"
    voice = {"name": "ExactVoice", "rate": "+0%", "pitch": "+0Hz"}
    source_hashes = {url: "a" * 64}
    claim_text = {event_id: "The tool adds a reviewed trace."}

    monkeypatch.setattr(gate_a_release, "EPISODE_ID", "daily-2026-09-23-exact")
    monkeypatch.setattr(gate_a_release, "PREVIEW_EPISODE_ID", "gate-a-preview-exact")
    monkeypatch.setattr(gate_a_release, "AUTHORIZED_AT", "2026-09-23T15:24:10Z")
    monkeypatch.setattr(gate_a_release, "AUDIO_SHA256", audio_sha)
    monkeypatch.setattr(gate_a_release, "SCRIPT_SHA256", script_sha)
    monkeypatch.setattr(gate_a_release, "NARRATION_SHA256", narration_sha)
    monkeypatch.setattr(gate_a_release, "IMPLEMENTATION_SHA", "f" * 40)
    monkeypatch.setattr(gate_a_release, "ORIGINAL_PROVIDER_AUDIO_SHA256", "b" * 64)
    monkeypatch.setattr(gate_a_release, "SOURCE_HASHES", source_hashes)
    monkeypatch.setattr(gate_a_release, "CLAIM_TEXT", claim_text)
    monkeypatch.setattr(gate_a_release, "VOICE", voice)
    waiver = {
        "scope": "exact_personal_release_only",
        "authorized_by": "John",
        "authorized_at": gate_a_release.AUTHORIZED_AT,
        "preview_episode_id": gate_a_release.PREVIEW_EPISODE_ID,
        "preview_manifest_sha256": gate_a_release.PREVIEW_MANIFEST_SHA256,
        "script_sha256": script_sha,
        "implementation_sha": "f" * 40,
        "original_provider_audio_sha256": "b" * 64,
        "listening_decision": "board_comment_approves_exact_recording_and_one_release_disclosure_waiver",
        "audible_disclosure": "waived_for_this_release_only",
        "coverage_policy": "required_exact_frozen_gate_a_evidence",
        "source_sha256": source_hashes,
    }
    monkeypatch.setattr(gate_a_release, "WAIVER", waiver)

    preview = EpisodeManifest.from_dict({
        "schema_version": 1,
        "episode_id": gate_a_release.PREVIEW_EPISODE_ID,
        "published_at": "2026-09-23T10:00:00Z",
        "status": "ready",
        "source_health": {"observer": "degraded: exact source only"},
        "source_events": [{
            "event_id": event_id,
            "source_type": "announcement",
            "title": "Reviewed trace",
            "url": url,
            "product": "Tool",
            "topic": "Agents",
            "published_at": "2026-09-23T09:00:00Z",
            "fetched_at": "2026-09-23T09:30:00Z",
            "evidence": "The tool adds a reviewed trace with operator controls.",
            "authority": "primary",
            "metadata": {"content_sha256": source_hashes[url], "observer_finding": event_id},
        }],
        "stories": [{
            "story_id": event_id,
            "event_ids": [event_id],
            "headline": "Reviewed trace",
            "what_changed": "The tool adds a reviewed trace.",
            "why_it_matters": "Operators can inspect agent behavior.",
            "action": "watch",
            "rationale": "Inspect a trace before changing production.",
            "source_urls": [url],
            "scores": {"total": 90},
            "kind": "product",
            "editorial": {"claims": []},
        }],
        "noise_notes": ["Coverage remains intentionally bounded."],
        "narration": narration,
        "show_notes": "Unpublished exact preview.",
        "generation": {
            "preview_only": True,
            "provider": "edge",
            "voice": voice,
            "implementation_sha": "f" * 40,
            "script_sha256": script_sha,
            "source_audio_sha256": "b" * 64,
            "quality": {
                "method": "ffmpeg_loudnorm_two_pass",
                "ffmpeg": "ffmpeg test",
                "integrated_lufs": -16.0,
                "true_peak_dbtp": -2.0,
                "audio_sha256": audio_sha,
            },
        },
        "audio": {
            "url": "https://example.com/unpublished.mp3",
            "size_bytes": len(audio),
            "duration_secs": 320.0,
            "sha256": audio_sha,
            "codec": "mp3",
            "sample_rate": 44100,
            "channels": 2,
        },
    })
    expected = gate_a_release._publication_manifest_data(preview)
    monkeypatch.setattr(
        gate_a_release, "AUTHORIZED_MANIFEST_CONTENT_SHA256",
        gate_a_release._semantic_digest(expected),
    )
    raw = (json.dumps(expected, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    monkeypatch.setattr(gate_a_release, "AUTHORIZED_MANIFEST_SHA256", _digest(raw))
    return preview, audio, waiver


def test_builds_only_exact_schema3_contract_and_preserves_audio_identity(monkeypatch):
    preview, audio, waiver = _synthetic_contract(monkeypatch)
    manifest = build_publication_manifest(preview)

    assert manifest.schema_version == 3
    assert manifest.status == "ready"
    assert manifest.audio["sha256"] == _digest(audio)
    assert manifest.generation["waiver"] == waiver
    assert manifest.generation["source_audio_sha256"] == _digest(audio)
    assert manifest.source_events[0].metadata == {
        "source_document_sha256": "a" * 64,
        "evidence_status": "reviewed_excerpts",
    }
    release_claims = " ".join([
        manifest.show_notes,
        *manifest.generation["review"]["notes"],
    ])
    assert "approved this exact hash-bound recording" in manifest.show_notes
    assert "one-release audible-disclosure waiver by board comment" in release_claims
    assert "no playback-coverage or detailed audio-quality finding is claimed" in release_claims
    assert " ".join(("after", "full", "listening")) not in release_claims
    assert " ".join(("fully", "listened")) not in release_claims
    assert "Audible AI disclosure is waived only" in manifest.generation["review"]["notes"][1]
    validate_exact_publication_manifest(manifest)


@pytest.mark.parametrize("mutation", [
    lambda data: data["generation"]["waiver"].update({"scope": "reusable"}),
    lambda data: data["generation"]["voice"].update({"name": "OtherVoice"}),
    lambda data: data["audio"].update({"sha256": "0" * 64}),
    lambda data: data["source_events"][0]["metadata"].update({"source_document_sha256": "0" * 64}),
    lambda data: data.update({"episode_id": "daily-other"}),
])
def test_exact_contract_fails_closed_on_reuse_or_identity_drift(monkeypatch, mutation):
    preview, _, _ = _synthetic_contract(monkeypatch)
    data = build_publication_manifest(preview).to_dict()
    mutation(data)
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)


def test_board_comment_substitution_requires_exact_waiver_record(monkeypatch, tmp_path):
    preview, audio, _ = _synthetic_contract(monkeypatch)
    manifest = build_publication_manifest(preview)
    manifest_path = tmp_path / "episode-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "daily-ai-brief.mp3").write_bytes(audio)
    (tmp_path / "narration.txt").write_text(manifest.narration + "\n", encoding="utf-8")
    bundle = load_review_bundle(tmp_path)

    with pytest.raises(ValueError, match="substitution record"):
        _load_approval(bundle)
    record = {
        "schema_version": 1,
        "purpose": "one_release_board_approval_substitution",
        "episode_id": gate_a_release.EPISODE_ID,
        "authorized_at": gate_a_release.AUTHORIZED_AT,
        "authorized_by": "John",
        "audio_sha256": gate_a_release.AUDIO_SHA256,
        "manifest_sha256": bundle.manifest_sha256,
        "script_sha256": gate_a_release.SCRIPT_SHA256,
        "audible_disclosure": "waived_for_this_release_only",
        "publication_authorized": True,
    }
    (tmp_path / "listening-waiver.json").write_text(json.dumps(record), encoding="utf-8")
    assert _load_approval(bundle)["decision"] == "approved_by_board_comment_substitution"

    changed = deepcopy(record)
    changed["publication_authorized"] = False
    (tmp_path / "listening-waiver.json").write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        _load_approval(bundle)


@pytest.mark.parametrize("mutation", [
    lambda data: data.update(show_notes="Mutated publication notes."),
    lambda data: data["stories"][0].update(rationale="Mutated release rationale."),
    lambda data: data["generation"]["review"]["notes"].append("Mutated review claim."),
])
@pytest.mark.parametrize("indent,sort_keys", [(None, True), (4, False)])
def test_board_substitution_rejects_every_manifest_field_mutation(
    monkeypatch, tmp_path, mutation, indent, sort_keys,
):
    preview, audio, _ = _synthetic_contract(monkeypatch)
    manifest = build_publication_manifest(preview)
    data = manifest.to_dict()
    mutation(data)
    manifest_bytes = (json.dumps(data, indent=indent, sort_keys=sort_keys) + "\n").encode()
    with pytest.raises(SchemaError, match="exact authorization"):
        EpisodeManifest.from_dict(json.loads(manifest_bytes))
    (tmp_path / "episode-manifest.json").write_bytes(manifest_bytes)
    (tmp_path / "daily-ai-brief.mp3").write_bytes(audio)
    (tmp_path / "narration.txt").write_text(manifest.narration + "\n", encoding="utf-8")
    record = {
        "schema_version": 1,
        "purpose": "one_release_board_approval_substitution",
        "episode_id": gate_a_release.EPISODE_ID,
        "authorized_at": gate_a_release.AUTHORIZED_AT,
        "authorized_by": "John",
        "audio_sha256": gate_a_release.AUDIO_SHA256,
        "manifest_sha256": _digest(manifest_bytes),
        "script_sha256": gate_a_release.SCRIPT_SHA256,
        "audible_disclosure": "waived_for_this_release_only",
        "publication_authorized": True,
    }
    (tmp_path / "listening-waiver.json").write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises((SchemaError, ValueError), match="exact|authorized|authorization"):
        _load_approval(load_review_bundle(tmp_path))


def test_review_and_resume_require_exact_authorized_manifest_bytes(monkeypatch, tmp_path):
    preview, audio, _ = _synthetic_contract(monkeypatch)
    manifest = build_publication_manifest(preview)
    directory = tmp_path / "bundle"
    directory.mkdir()
    (directory / "episode-manifest.json").write_text(
        json.dumps(manifest.to_dict(), sort_keys=True, separators=(",", ":")), encoding="utf-8",
    )
    (directory / "daily-ai-brief.mp3").write_bytes(audio)
    (directory / "narration.txt").write_text(manifest.narration + "\n", encoding="utf-8")

    with pytest.raises((SchemaError, ValueError), match="exact|authorized|authorization"):
        load_review_bundle(directory)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "johnsirmon/daily-ai-docs")
    monkeypatch.setattr(daily, "_validate_reviewed_audio_file", lambda *_: None)
    with pytest.raises((RuntimeError, SchemaError, ValueError), match="exact|authorized|authorization"):
        daily.resume_reviewed_release(manifest.episode_id, directory)


def test_reviewed_release_resume_rejects_semantic_manifest_mutation(monkeypatch, tmp_path):
    preview, audio, _ = _synthetic_contract(monkeypatch)
    manifest = build_publication_manifest(preview)
    data = manifest.to_dict()
    data["show_notes"] = "Mutated after review."
    directory = tmp_path / "bundle"
    directory.mkdir()
    (directory / "episode-manifest.json").write_text(json.dumps(data), encoding="utf-8")
    (directory / "daily-ai-brief.mp3").write_bytes(audio)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "johnsirmon/daily-ai-docs")
    monkeypatch.setattr(daily, "_validate_reviewed_audio_file", lambda *_: None)

    with pytest.raises((RuntimeError, SchemaError, ValueError), match="exact|authorized|authorization"):
        daily.resume_reviewed_release(manifest.episode_id, directory)


def test_existing_queue_record_is_bound_to_exact_manifest(monkeypatch, tmp_path):
    preview, audio, _ = _synthetic_contract(monkeypatch)
    manifest = build_publication_manifest(preview)
    manifest_bytes = (
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()
    (tmp_path / "episode-manifest.json").write_bytes(manifest_bytes)
    (tmp_path / "daily-ai-brief.mp3").write_bytes(audio)
    (tmp_path / "narration.txt").write_text(manifest.narration + "\n", encoding="utf-8")
    waiver = {
        "schema_version": 1,
        "purpose": "one_release_board_approval_substitution",
        "episode_id": gate_a_release.EPISODE_ID,
        "authorized_at": gate_a_release.AUTHORIZED_AT,
        "authorized_by": "John",
        "audio_sha256": gate_a_release.AUDIO_SHA256,
        "manifest_sha256": gate_a_release.AUTHORIZED_MANIFEST_SHA256,
        "script_sha256": gate_a_release.SCRIPT_SHA256,
        "audible_disclosure": "waived_for_this_release_only",
        "publication_authorized": True,
    }
    (tmp_path / "listening-waiver.json").write_text(json.dumps(waiver), encoding="utf-8")
    (tmp_path / "publication-queue.json").write_text(json.dumps({
        "episode_id": gate_a_release.EPISODE_ID,
        "audio_sha256": gate_a_release.AUDIO_SHA256,
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="queue record"):
        queue_publication(load_review_bundle(tmp_path), allow_publish=True)
