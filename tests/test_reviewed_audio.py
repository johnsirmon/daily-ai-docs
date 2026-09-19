"""Offline reviewed-recording contracts, including real FFmpeg handoff coverage."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest

from pipeline.audio import AudioValidationError
from pipeline.disclosure import AI_NARRATION_DISCLOSURE
from pipeline.narrate import manifest_to_narration
from pipeline.render import render_manifest_readme
from pipeline.reviewed_audio import main, prepare_reviewed_audio
from pipeline.schema import EpisodeManifest, SchemaError


CLAIM = "The tool adds sandboxed command previews."
TIMESTAMP = "2026-09-17T20:00:00Z"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def draft(source=b"original recording"):
    narration = "\n  " + AI_NARRATION_DISCLOSURE + "\n\n" + CLAIM + " " + (
        "Review the command before granting execution in your workspace. " * 80
    ) + "\n"
    return {
        "schema_version": 3,
        "episode_id": "daily-2026-09-17-notebook",
        "published_at": TIMESTAMP,
        "status": "draft",
        "source_health": {"reviewed_primary": "ok:1"},
        "source_events": [{
            "event_id": "e1", "source_type": "announcement", "title": "Command previews",
            "url": "https://example.com/releases/preview", "product": "Tool", "topic": "Coding agents",
            "published_at": TIMESTAMP, "fetched_at": TIMESTAMP, "evidence": CLAIM,
            "authority": "primary", "metadata": {},
        }],
        "stories": [{
            "story_id": "s1", "event_ids": ["e1"], "headline": "Command previews",
            "what_changed": CLAIM, "why_it_matters": "Inspect commands before execution.",
            "action": "watch", "rationale": "Review the preview in a test workspace.",
            "source_urls": ["https://example.com/releases/preview"], "scores": {"total": 85},
        }],
        "noise_notes": [],
        "narration": narration,
        "show_notes": "Command preview guidance with public primary evidence.",
        "generation": {
            "edition": "notebook", "provider": "gemini-notebook-web", "approved_at": TIMESTAMP,
            "source_audio_sha256": digest(source),
            "transcript": {"engine": "faster-whisper", "model": "small.en", "sha256": digest(narration.encode())},
            "review": {
                "method": "transcript_source_comparison", "reviewed_at": TIMESTAMP,
                "reviewer": "assistant",
                "claims": [{"text": CLAIM, "event_id": "e1", "quote": CLAIM}],
                "notes": ["Local ASR may misrecognize names; transcript retained without rewriting."],
            },
        },
        "audio": {
            "url": "https://github.com/owner/repo/releases/download/daily-2026-09-17-notebook/daily-ai-brief.mp3",
        },
    }


def paper_draft():
    data = draft()
    event = data["source_events"][0]
    event.update({
        "source_type": "research_paper",
        "url": "https://arxiv.org/abs/2609.12345",
        "metadata": {
            "paper_id": "2609.12345", "version": "v1", "first_published_at": TIMESTAMP,
            "updated_at": TIMESTAMP, "full_text_available": True, "full_text_retained": False,
            "evidence_status": "reviewed_excerpts", "reviewed_excerpts": CLAIM,
        },
    })
    data["stories"][0].update({
        "kind": "research", "source_urls": [event["url"]],
        "editorial": {"paper_review": {
            "question": "Can command previews make execution review practical?",
            "method": "The authors evaluated sandboxed command previews.",
            "result": CLAIM, "limitations": "The findings exclude production deployment.",
            "takeaway": "Evaluate previews in a test workspace.",
            "evidence_status": "author_reported_not_reproduced",
        }},
    })
    return data


def corrected_draft():
    data = draft()
    correction = "Editorial correction: approval changes the member's budget, not the organization's budget."
    data["generation"]["editing"] = {
        "method": "prefixed_editorial_correction",
        "original_audio_sha256": digest(b"original Notebook M4A"),
        "correction_text": correction,
        "correction_audio_sha256": digest(b"Edge correction MP3"),
        "correction_provider": "edge",
    }
    data["narration"] = correction + "\n\n" + data["narration"]
    data["generation"]["transcript"]["sha256"] = digest(data["narration"].encode())
    return data


def test_valid_manifest_preserves_exact_transcript_and_explicit_provenance():
    data = draft()
    manifest = EpisodeManifest.from_dict(data)
    assert manifest_to_narration(manifest) == data["narration"]
    assert EpisodeManifest.from_dict(manifest.to_dict()).to_dict() == manifest.to_dict()
    assert "verified" not in manifest.generation
    assert "calls" not in manifest.generation
    rendered = render_manifest_readme(manifest)
    assert "not independently verified Gemini API generation" in rendered
    assert "preserves a conversational format" in rendered
    assert "Every story ends with" not in rendered
    assert "### Editorial correction" not in rendered


def test_prefixed_correction_provenance_preserves_combined_transcript():
    data = corrected_draft()
    manifest = EpisodeManifest.from_dict(data)
    assert manifest_to_narration(manifest) == data["narration"]
    assert manifest.narration.endswith(draft()["narration"])
    assert manifest.to_dict()["generation"]["editing"] == data["generation"]["editing"]
    rendered = render_manifest_readme(manifest)
    assert "An Edge-TTS editorial correction" in rendered
    correction = data["generation"]["editing"]["correction_text"]
    assert correction in rendered
    assert rendered.index(correction) < rendered.index("## Today's signal")
    assert "An Edge-TTS editorial correction" not in render_manifest_readme(EpisodeManifest.from_dict(draft()))


@pytest.mark.parametrize("field,value", [
    ("method", "trimmed_conversation"), ("method", []), ("correction_provider", "gemini"),
    ("original_audio_sha256", "invalid"), ("original_audio_sha256", "A" * 64),
    ("correction_audio_sha256", None), ("correction_audio_sha256", "f" * 63),
    ("correction_text", ""), ("correction_text", None), ("correction_text", "x" * 1601),
    ("correction_text", "A correction that was not prefixed."),
    ("verified", True), ("calls", 2), ("notebook_url", "https://notebooklm.google.com/private"),
])
def test_rejects_invalid_correction_provenance(field, value):
    data = corrected_draft()
    data["generation"]["editing"][field] = value
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("editing", [None, [], {}, {"method": "prefixed_editorial_correction"}])
def test_correction_provenance_requires_complete_typed_object(editing):
    data = corrected_draft()
    data["generation"]["editing"] = editing
    with pytest.raises(SchemaError, match="generation.editing"):
        EpisodeManifest.from_dict(data)


def test_correction_must_be_a_prefix_not_merely_present_in_transcript():
    data = corrected_draft()
    correction = data["generation"]["editing"]["correction_text"]
    data["narration"] = draft()["narration"] + correction
    data["generation"]["transcript"]["sha256"] = digest(data["narration"].encode())
    with pytest.raises(SchemaError, match="exact narration prefix"):
        EpisodeManifest.from_dict(data)


def test_correction_cannot_replace_entire_conversation():
    data = corrected_draft()
    data["narration"] = data["generation"]["editing"]["correction_text"] + "\n "
    data["generation"]["transcript"]["sha256"] = digest(data["narration"].encode())
    with pytest.raises(SchemaError, match="retain the conversation"):
        EpisodeManifest.from_dict(data)


def test_correction_requires_hash_of_complete_combined_transcript():
    data = corrected_draft()
    data["generation"]["transcript"]["sha256"] = draft()["generation"]["transcript"]["sha256"]
    with pytest.raises(SchemaError, match="exact UTF-8 narration"):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("path,value", [
    (("generation", "provider"), "gemini"),
    (("generation", "edition"), "normal"),
    (("generation", "verified"), True),
    (("generation", "calls"), 2),
    (("generation", "approved_at"), ""),
    (("generation", "approved_at"), "2026-09-17T20:00:00"),
    (("generation", "source_audio_sha256"), "ABC"),
    (("generation", "source_audio_sha256"), "A" * 64),
    (("generation", "transcript"), None),
    (("generation", "transcript", "engine"), "cloud-asr"),
    (("generation", "transcript", "engine"), []),
    (("generation", "transcript", "model"), ""),
    (("generation", "transcript", "sha256"), "0" * 64),
    (("generation", "review"), {}),
    (("generation", "review", "reviewer"), "gemini"),
    (("generation", "review", "method"), "independent_verification"),
    (("generation", "review", "reviewed_at"), ""),
    (("generation", "review", "notes"), []),
    (("generation", "review", "notes"), ["x" * 1601]),
    (("generation", "review", "notes"), ["note"] * 21),
    (("generation", "review", "claims"), []),
    (("generation", "review", "claims"), [{}] * 101),
    (("generation", "review", "claims"), [None]),
    (("generation", "account"), "private account"),
    (("episode_id",), "../escape"),
    (("episode_id",), "daily/path"),
    (("status",), "quiet"),
    (("audio", "url"), "https://github.com/owner/repo/releases/download/other/daily-ai-brief.mp3"),
    (("audio", "url"), "https://github.com/owner/repo/releases/download/daily-2026-09-17-notebook/audio.mp3"),
    (("audio", "url"), "https://github.com/owner/repo/releases/download/daily-2026-09-17-notebook/daily-ai-brief.mp3?token=secret"),
])
def test_rejects_malformed_provenance(path, value):
    data = draft()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("field", ["approved_at", "review", "transcript", "source_audio_sha256"])
def test_rejects_missing_provenance(field):
    data = draft()
    del data["generation"][field]
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("field,value,match", [
    ("text", "A claim absent from the recording.", "ASR narration"),
    ("quote", "A quote absent from the evidence.", "event evidence"),
    ("event_id", "missing", "unknown or unmapped"),
    ("event_id", [], "must be a string"),
])
def test_rejects_unbound_claims(field, value, match):
    data = draft()
    data["generation"]["review"]["claims"][0][field] = value
    with pytest.raises(SchemaError, match=match):
        EpisodeManifest.from_dict(data)


def test_every_source_requires_story_and_claim_mapping():
    data = draft()
    second = deepcopy(data["source_events"][0])
    second["event_id"] = "e2"
    data["source_events"].append(second)
    with pytest.raises(SchemaError, match="stories must account"):
        EpisodeManifest.from_dict(data)
    data["stories"][0]["event_ids"].append("e2")
    with pytest.raises(SchemaError, match="claims must account"):
        EpisodeManifest.from_dict(data)
    data["generation"]["review"]["claims"].append({"text": CLAIM, "event_id": "e2", "quote": CLAIM})
    EpisodeManifest.from_dict(data)


def test_rejects_repeated_story_evidence_and_duplicate_claims():
    data = draft()
    data["stories"].append({**deepcopy(data["stories"][0]), "story_id": "s2"})
    with pytest.raises(SchemaError, match="each source exactly once"):
        EpisodeManifest.from_dict(data)
    data["stories"].pop()
    data["generation"]["review"]["claims"] *= 2
    with pytest.raises(SchemaError, match="duplicate reviewed claim"):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("metadata", [
    {"full_text": "A full source document."}, {"full_text": ""},
    {"cookie": "session-data"}, {"api_key": "private"},
    {"notebook_url": "https://notebooklm.google.com/notebook/private"},
    {"private": True}, {"draft": True}, {"reviewed_excerpts": "Unarchived product document."},
])
def test_rejects_unarchived_documents_and_private_source_metadata(metadata):
    data = draft()
    data["source_events"][0]["metadata"] = metadata
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("field", ["source_text_sha256", "source_document_sha256", "source_evidence_sha256"])
def test_reviewed_source_retains_only_valid_provenance_hashes(field):
    data = draft()
    data["source_events"][0]["metadata"] = {field: digest(b"public source"), "evidence_status": "reviewed_excerpts"}
    EpisodeManifest.from_dict(data)
    data["source_events"][0]["metadata"][field] = "not-a-digest"
    with pytest.raises(SchemaError, match="SHA-256"):
        EpisodeManifest.from_dict(data)


def test_reviewed_source_status_must_be_reviewed():
    data = draft()
    data["source_events"][0]["metadata"] = {"evidence_status": "unreviewed"}
    with pytest.raises(SchemaError, match="reviewed_excerpts"):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("url", [
    "http://example.com/release", "https://localhost/release", "https://127.0.0.1/release",
    "https://10.0.0.1/release", "https://example.internal/release",
    "https://user:password@example.com/release", "https://example.com:8443/release",
    "https://notebooklm.google.com/notebook/private", "https://gemini.google.com/app/private",
    "https://notebook.google.com/notebook/private", "https://notebook.google/notebook/private",
    "https://drive.google.com/file/private", "https://example.com/release?api_key=private",
])
def test_rejects_nonpublic_urls_in_sources_and_notes(url):
    data = draft()
    data["source_events"][0]["url"] = url
    data["stories"][0]["source_urls"] = [url]
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)
    data = draft()
    data["generation"]["review"]["notes"] = [url]
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)


def test_rejects_secondary_sources_and_overlong_evidence():
    data = draft()
    data["source_events"][0]["authority"] = "secondary"
    with pytest.raises(SchemaError, match="primary"):
        EpisodeManifest.from_dict(data)
    data = draft()
    data["source_events"][0]["evidence"] = "evidence " * 181
    with pytest.raises(SchemaError, match="short excerpts"):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("narration", ["word " * 1501, "x" * 16001, " " * 16000 + CLAIM])
def test_rejects_overlong_transcript(narration):
    data = draft()
    data["narration"] = narration
    data["generation"]["transcript"]["sha256"] = digest(narration.encode())
    with pytest.raises(SchemaError, match="narration exceeds"):
        EpisodeManifest.from_dict(data)


def test_research_is_rendered_as_reviewed_author_reported_research():
    manifest = EpisodeManifest.from_dict(paper_draft())
    rendered = render_manifest_readme(manifest)
    assert "author_reported_not_reproduced" in rendered
    assert "The findings exclude production deployment." in rendered
    assert "The authors evaluated sandboxed command previews." in rendered


@pytest.mark.parametrize("field,value", [
    ("full_text_available", False), ("full_text_retained", True),
    ("evidence_status", "abstract_only"), ("reviewed_excerpts", "Unreviewed text"),
    ("paper_id", "2609.12345v1"), ("version", 0), ("version", True),
    ("first_published_at", ""), ("updated_at", "yesterday"),
])
def test_rejects_unreviewed_or_noncanonical_papers(field, value):
    data = paper_draft()
    data["source_events"][0]["metadata"][field] = value
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)


def test_rejects_paper_reclassified_as_product_and_missing_review():
    data = paper_draft()
    data["stories"][0]["kind"] = "product"
    with pytest.raises(SchemaError, match="classified as research"):
        EpisodeManifest.from_dict(data)
    data = paper_draft()
    del data["stories"][0]["editorial"]["paper_review"]["limitations"]
    with pytest.raises(SchemaError, match="paper_review"):
        EpisodeManifest.from_dict(data)
    data = paper_draft()
    data["source_events"][0]["metadata"]["paper_id"] = "2609.99999"
    with pytest.raises(SchemaError, match="canonical paper_id"):
        EpisodeManifest.from_dict(data)


@pytest.fixture
def inputs(tmp_path):
    source = tmp_path / "source.m4a"
    source.write_bytes(b"original recording")
    manifest = tmp_path / "draft.json"
    manifest.write_text(json.dumps(draft()), encoding="utf-8")
    return manifest, source, tmp_path / "prepared"


@pytest.fixture
def mocked_audio(monkeypatch):
    def transcode(command, **kwargs):
        Path(command[-1]).write_bytes(b"measured mp3" * 1200)
        return subprocess.CompletedProcess(command, 0)

    def analyze(path, **kwargs):
        return {
            "path": str(path), "sha256": digest(path.read_bytes()), "size_bytes": path.stat().st_size,
            "duration_secs": 320.125, "codec": "mp3", "sample_rate": 44100, "channels": 2,
        }

    runner, analyzer = Mock(side_effect=transcode), Mock(side_effect=analyze)
    monkeypatch.setattr("pipeline.reviewed_audio.shutil.which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr("pipeline.reviewed_audio.subprocess.run", runner)
    monkeypatch.setattr("pipeline.reviewed_audio.analyze_audio", analyzer)
    return runner, analyzer


def test_import_binds_measured_audio_without_mutating_sources(inputs, mocked_audio):
    manifest_path, source, output = inputs
    original_source, original_manifest = source.read_bytes(), manifest_path.read_bytes()
    publication = prepare_reviewed_audio(*inputs)
    runner, analyzer = mocked_audio
    assert source.read_bytes() == original_source
    assert manifest_path.read_bytes() == original_manifest
    assert json.loads((output / "publication.json").read_text()) == publication
    assert set(publication) == {
        "outcome", "episode_id", "tag", "manifest_path", "audio_path", "audio_url", "dry_run",
    }
    assert publication["outcome"] == "publish"
    assert publication["dry_run"] is False
    assert publication["tag"] == publication["episode_id"]
    manifest = EpisodeManifest.from_dict(json.loads(Path(publication["manifest_path"]).read_text()))
    manifest.validate(require_audio=True)
    assert manifest.status == "ready"
    assert manifest.audio["sha256"] == digest(Path(publication["audio_path"]).read_bytes())
    assert manifest.audio["size_bytes"] == Path(publication["audio_path"]).stat().st_size
    assert manifest.audio["duration_secs"] == 320.125
    assert "path" not in manifest.audio
    assert str(output) not in Path(publication["manifest_path"]).read_text()
    assert str(source) not in Path(publication["manifest_path"]).read_text()
    assert manifest.narration == draft()["narration"]
    runner.assert_called_once()
    command = runner.call_args.args[0]
    assert "-n" in command and "-y" not in command
    assert not {"-ss", "-t", "-to", "-af", "-filter:a", "-filter_complex"} & set(command)
    assert command[command.index("-map_metadata") + 1] == "-1"
    analyzer.assert_called_once_with(
        output / "daily-ai-brief.mp3", min_duration_secs=300, max_duration_secs=480,
        full_decode=True, expected_word_count=len(manifest.narration.split()),
    )
    assert set(path.name for path in output.iterdir()) == {
        "daily-ai-brief.mp3", "episode-manifest.json", "publication.json",
    }


def test_import_rejects_audio_without_spoken_production_disclosure(inputs, mocked_audio):
    manifest_path, _, output = inputs
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["narration"] = data["narration"].replace(AI_NARRATION_DISCLOSURE + "\n\n", "")
    data["generation"]["transcript"]["sha256"] = digest(data["narration"].encode("utf-8"))
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(SchemaError, match="production disclosure"):
        prepare_reviewed_audio(*inputs)

    assert not output.exists()


def test_import_transcodes_supplied_composite_without_assembling_components(inputs, mocked_audio):
    manifest_path, source, _ = inputs
    composite = b"parent-produced correction plus intact Notebook recording"
    source.write_bytes(composite)
    data = corrected_draft()
    data["generation"]["source_audio_sha256"] = digest(composite)
    manifest_path.write_text(json.dumps(data))
    publication = prepare_reviewed_audio(*inputs)
    ready = EpisodeManifest.from_dict(json.loads(Path(publication["manifest_path"]).read_text()))
    assert ready.generation == data["generation"]
    assert ready.narration == data["narration"]
    assert source.read_bytes() == composite
    mocked_audio[0].assert_called_once()
    command = mocked_audio[0].call_args.args[0]
    assert command.count("-i") == 1
    assert command[command.index("-i") + 1] == str(source)
    assert not {"concat", "-af", "-filter_complex"} & set(command)


@pytest.mark.parametrize("conflict", ["directory", "file", "symlink"])
def test_import_refuses_existing_output(inputs, mocked_audio, conflict):
    _, source, output = inputs
    if conflict == "directory":
        output.mkdir()
    elif conflict == "file":
        output.write_text("existing")
    else:
        output.symlink_to(output.parent / "missing")
    with pytest.raises(FileExistsError, match="new and unused"):
        prepare_reviewed_audio(*inputs)
    mocked_audio[0].assert_not_called()
    assert source.read_bytes() == b"original recording"


def test_import_rejects_source_output_collision(inputs, mocked_audio):
    manifest, source, _ = inputs
    with pytest.raises(FileExistsError):
        prepare_reviewed_audio(manifest, source, source)
    mocked_audio[0].assert_not_called()


@pytest.mark.parametrize("change", ["preview", "hash", "legacy", "ready"])
def test_import_rejects_invalid_handoff_before_writing(inputs, mocked_audio, change):
    path, _, output = inputs
    data = draft()
    if change == "preview":
        data["generation"]["preview_only"] = True
    elif change == "hash":
        data["generation"]["source_audio_sha256"] = "0" * 64
    elif change == "legacy":
        data["schema_version"] = 1
    else:
        data["status"] = "ready"
    path.write_text(json.dumps(data))
    with pytest.raises(SchemaError):
        prepare_reviewed_audio(*inputs)
    assert not output.exists()
    mocked_audio[0].assert_not_called()


@pytest.mark.parametrize("failure", [
    subprocess.CalledProcessError(1, ["ffmpeg"]),
    subprocess.TimeoutExpired(["ffmpeg"], 600),
    AudioValidationError("audio failed full decode"),
    AudioValidationError("duration 299.9s is outside 300-480s"),
])
def test_failure_never_produces_publish_receipt_or_reuses_output(inputs, mocked_audio, failure):
    _, source, output = inputs
    if isinstance(failure, AudioValidationError):
        mocked_audio[1].side_effect = failure
    else:
        mocked_audio[0].side_effect = failure
    with pytest.raises(type(failure)):
        prepare_reviewed_audio(*inputs)
    assert source.read_bytes() == b"original recording"
    assert not (output / "publication.json").exists()
    assert not (output / "episode-manifest.json").exists()
    with pytest.raises(FileExistsError):
        prepare_reviewed_audio(*inputs)
    mocked_audio[0].assert_called_once()


def test_missing_ffmpeg_fails_before_creating_output(inputs, monkeypatch):
    monkeypatch.setattr("pipeline.reviewed_audio.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="ffmpeg is required"):
        prepare_reviewed_audio(*inputs)
    assert not inputs[2].exists()


def test_cli_outputs_publication_json(inputs, mocked_audio, capsys):
    manifest, source, output = inputs
    assert main(["--manifest", str(manifest), "--audio", str(source), "--output-dir", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["outcome"] == "publish"


@pytest.mark.parametrize("key,value", [
    ("sha256", "invalid"), ("size_bytes", True), ("size_bytes", "12000"),
    ("duration_secs", float("nan")), ("duration_secs", 299.99), ("duration_secs", 480.01),
    ("codec", "aac"), ("sample_rate", 0), ("channels", True),
    ("path", "/home/private-account/recording.mp3"),
])
def test_ready_manifest_requires_typed_measured_audio(inputs, mocked_audio, key, value):
    publication = prepare_reviewed_audio(*inputs)
    data = json.loads(Path(publication["manifest_path"]).read_text())
    data["audio"][key] = value
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)


def test_legacy_and_verified_editorial_contracts_are_unchanged():
    data = draft()
    data.update(schema_version=1, generation={}, audio={})
    legacy = EpisodeManifest.from_dict(data)
    assert manifest_to_narration(legacy) != data["narration"]
    assert "Every story ends with" in render_manifest_readme(legacy)
    data["schema_version"] = 2
    data["stories"][0]["editorial"] = {
        "spoken_text": CLAIM,
        "claims": [{"text": CLAIM, "event_id": "e1", "quote": CLAIM}],
    }
    data["generation"] = {
        "provider": "gemini", "model": "gemini-3-flash-preview", "verified": True,
        "calls": 2, "editorial_version": 1, "opening": "Command previews.",
        "closing": "Review the preview.",
    }
    data["narration"] = "Command previews.\n\n" + CLAIM + "\n\nReview the preview."
    verified = EpisodeManifest.from_dict(data)
    assert manifest_to_narration(verified) == data["narration"]
    data["generation"]["calls"] = 1
    with pytest.raises(SchemaError, match="independently verified"):
        EpisodeManifest.from_dict(data)


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="FFmpeg unavailable")
@pytest.mark.parametrize("seconds,accepted", [(2, False), (320, True)])
def test_real_transcode_and_full_decode(tmp_path, seconds, accepted):
    source = tmp_path / "recording.m4a"
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        f"sine=frequency=440:duration={seconds}", "-c:a", "aac", str(source),
    ], check=True, capture_output=True, timeout=120)
    original = source.read_bytes()
    manifest = tmp_path / "draft.json"
    manifest.write_text(json.dumps(draft(original)), encoding="utf-8")
    output = tmp_path / "handoff"
    if accepted:
        result = prepare_reviewed_audio(manifest, source, output)
        ready = EpisodeManifest.from_dict(json.loads(Path(result["manifest_path"]).read_text()))
        assert 319 <= ready.audio["duration_secs"] <= 321
        assert ready.audio["sha256"] == digest(Path(result["audio_path"]).read_bytes())
        assert ready.status == "ready"
    else:
        with pytest.raises(AudioValidationError, match="outside 300-480"):
            prepare_reviewed_audio(manifest, source, output)
        assert not (output / "publication.json").exists()
    assert source.read_bytes() == original
