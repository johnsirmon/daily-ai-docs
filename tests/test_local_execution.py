"""Offline consumer-browser boundaries, not live browser or publication tests."""

from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image
import pytest

from pipeline import local_execution as local
from pipeline.audio import AudioValidationError, analyze_audio, file_sha256
from pipeline.reviewed_audio import prepare_reviewed_audio, validate_local_handoff
from pipeline.schema import EpisodeManifest
from tests.test_adhoc import request
from tests.test_reviewed_audio import draft


@pytest.fixture(autouse=True)
def local_host(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


def image_request(**changes):
    return replace(local.LocalRequest(
        identity="daily-2026-09-21-art-v1", kind="chatgpt-image",
        purpose="Episode image source, no text or logos.",
        prompt="Create a square abstract illustration of parallel coding agents. No text or logos.",
        artifact_name="source.png", width=32, height=32,
    ), **changes)


def saved_image(tmp_path):
    path = local.create(tmp_path, image_request())
    image = path.parent / "source.png"
    Image.new("RGB", (32, 32), (10, 20, 50)).save(image)
    return path, image


def ready_image(tmp_path):
    path, image = saved_image(tmp_path)
    for action in ("observe", "validate", "resume"):
        local.advance(path, action, execution="local")
    return path, image


def test_cloud_stops_with_exact_portable_prompt_and_no_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("cloud handoff must be offline"))
    path = local.create(Path(".cache") / "image", image_request())
    before = path.read_bytes()
    for action in ("generate", "generated", "download", "observe", "validate", "resume"):
        result = local.advance(path, action)
        assert result["outcome"] == "local-required"
        assert not result["perform_browser_action"]
        assert result["request"] == asdict(image_request())
        assert not result["publication_authorized"]
        assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == [local.FILENAME]
    assert not Path("data").exists() and not Path("podcast.xml").exists()


def test_generation_download_and_native_save_are_distinct_idempotent_milestones(tmp_path):
    path = local.create(tmp_path, image_request())
    assert local.advance(path, "generate", execution="local")["perform_browser_action"]
    assert not local.advance(path, "generate", execution="local")["perform_browser_action"]
    assert local.load(path)["artifact"] is None
    local.advance(path, "generated", execution="local")
    assert local.advance(path, "download", execution="local")["perform_browser_action"]
    local.advance(path, "wait", execution="local", reason="save-file")
    for action in ("generate", "download"):
        assert not local.advance(path, action, execution="local")["perform_browser_action"]
    pending = local.load(path)
    assert pending["status"] == "waiting-for-operator"
    assert pending["operator_action"] == "save-file"
    assert not pending["operator_save_confirmed"]
    Image.new("RGB", (32, 32)).save(tmp_path / "source.png")
    created = local.advance(path, "observe", execution="local", operator_saved=True)
    assert created["status"] == "local-artifact-created"
    assert created["operator_save_confirmed"]
    assert not created["artifact"]["measurements"]
    validated = local.advance(path, "validate", execution="local")
    assert validated["status"] == "local-artifact-validated"
    assert validated["outcome"] != "artifact-ready"
    resumed = local.advance(path)
    assert resumed["outcome"] == "artifact-ready"
    assert resumed["artifact"]["sha256"] == file_sha256(tmp_path / "source.png")


def test_existing_artifact_wins_even_without_browser_download_event(tmp_path, monkeypatch):
    path, image = saved_image(tmp_path)
    for action in ("generate", "download"):
        assert not local.advance(path, action, execution="local")["perform_browser_action"]
    local.advance(path, "observe", execution="local")
    local.advance(path, "validate", execution="local")
    before = image.read_bytes()
    monkeypatch.setattr(local, "_measure", lambda *a: pytest.fail("must reuse validated bytes"))
    for _ in range(2):
        assert local.advance(path)["outcome"] == "artifact-ready"
        local.advance(path, "validate", execution="local")
        assert local.create(tmp_path, image_request()) == path
    assert image.read_bytes() == before
    assert local.load(path)["attempts"] == {"generation": 0, "download": 0, "validation": 1}


def test_failed_action_recovery_never_reissues_ambiguous_browser_click(tmp_path):
    path = local.create(tmp_path, image_request())
    local.advance(path, "generate", execution="local")
    local.advance(path, "fail", execution="local", reason="generation-failed")
    assert local.advance(path)["outcome"] == "failed"
    local.advance(path, "recover", execution="local")
    assert not local.advance(path, "generate", execution="local")["perform_browser_action"]
    local.advance(path, "generated", execution="local")
    local.advance(path, "download", execution="local")
    local.advance(path, "fail", execution="local", reason="download-unconfirmed")
    local.advance(path, "recover", execution="local")
    assert not local.advance(path, "download", execution="local")["perform_browser_action"]


def test_validation_prerequisite_failure_recovers_without_generation(tmp_path, monkeypatch):
    path, image = saved_image(tmp_path)
    local.advance(path, "observe", execution="local")
    measure = local._measure
    def fail(*args):
        raise RuntimeError("Authorization: Bearer PRIVATE_PROVIDER_ERROR")
    monkeypatch.setattr(local, "_measure", fail)
    with pytest.raises(ValueError, match="local handoff failed") as error:
        local.advance(path, "validate", execution="local")
    assert "PRIVATE_PROVIDER_ERROR" not in str(error.value) + path.read_text()
    assert local.load(path)["status"] == "failed"
    local.advance(path, "recover", execution="local")
    monkeypatch.setattr(local, "_measure", measure)
    local.advance(path, "validate", execution="local")
    assert local.advance(path)["outcome"] == "artifact-ready"
    assert local.load(path)["attempts"] == {"generation": 0, "download": 0, "validation": 2}
    assert local.load(path)["artifact"]["sha256"] == file_sha256(image)


def test_validation_retries_are_bounded_and_do_not_replace_bad_bytes(tmp_path):
    path = local.create(tmp_path, image_request())
    source = tmp_path / "source.png"
    source.write_text("<html>Sign in</html>")
    local.advance(path, "observe", execution="local")
    for _ in range(local.MAX_VALIDATIONS + 1):
        with pytest.raises(ValueError, match="failed"):
            local.advance(path, "validate", execution="local")
        local.advance(path, "recover", execution="local")
    assert local.load(path)["attempts"]["validation"] == local.MAX_VALIDATIONS
    assert source.read_text() == "<html>Sign in</html>"


def test_missing_file_is_not_created_or_successful_and_can_be_recovered(tmp_path):
    path = local.create(tmp_path, image_request())
    with pytest.raises(ValueError, match="failed"):
        local.advance(path, "observe", execution="local")
    assert local.load(path)["artifact"] is None
    assert local.advance(path)["outcome"] == "failed"
    Image.new("RGB", (32, 32)).save(tmp_path / "source.png")
    local.advance(path, "recover", execution="local")
    local.advance(path, "observe", execution="local")
    local.advance(path, "validate", execution="local")
    assert local.advance(path)["outcome"] == "artifact-ready"


@pytest.mark.parametrize("change", ["delete", "replace"])
@pytest.mark.parametrize("action,execution", [("resume", "cloud"), ("generate", "cloud"), ("download", "local")])
def test_resume_and_consumers_recheck_actual_bytes(tmp_path, change, action, execution):
    path, image = ready_image(tmp_path)
    if change == "delete":
        image.unlink()
    else:
        image.write_bytes(b"changed")
    with pytest.raises(ValueError):
        local.require_artifact(path, image, identity=image_request().identity, kind="chatgpt-image")
    with pytest.raises(ValueError):
        local.advance(path, action, execution=execution)
    assert local.load(path)["status"] == "failed"


@pytest.mark.parametrize("change", [
    {"width": 33, "height": 33}, {"prompt": "A different approved prompt"},
    {"identity": "other-request"}, {"artifact_name": "different.png"},
])
def test_changed_request_cannot_reset_attempts_or_overwrite_state(tmp_path, change):
    path = local.create(tmp_path, image_request())
    local.advance(path, "generate", execution="local")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="different intent"):
        local.create(tmp_path, image_request(**change))
    assert path.read_bytes() == before


@pytest.mark.parametrize("field", ["cookies", "session", "headers", "profile", "download_url", "metadata"])
def test_unknown_secret_storage_fields_rejected_before_write(tmp_path, field):
    with pytest.raises(ValueError, match="fields"):
        local.LocalRequest.from_dict({**asdict(image_request()), field: "DO_NOT_STORE"})
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("prompt", [
    "Cookie: session=PRIVATE", "Authorization: Bearer PRIVATE", "api_key=PRIVATE",
    "browser_profile=C:\\private", "storage_state=PRIVATE",
    "Download https://media.example.com/file?token=PRIVATE",
    "Use https://notebooklm.google.com/notebook/private-id",
    "Use https://chatgpt.com/c/private-conversation",
    "Use https://name:PRIVATE@example.com/file",
])
def test_sensitive_prompt_material_rejected_without_echo_or_persistence(tmp_path, prompt):
    with pytest.raises(ValueError) as error:
        local.create(tmp_path, image_request(prompt=prompt))
    assert "PRIVATE" not in str(error.value)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", ["../source.png", "C:\\private.png", "sub/source.png", "local-execution.json"])
def test_artifact_path_cannot_escape_or_overwrite_control_state(tmp_path, name):
    with pytest.raises(ValueError):
        local.create(tmp_path, image_request(artifact_name=name))


def test_concurrent_or_interrupted_transition_fails_closed(tmp_path):
    path = local.create(tmp_path, image_request())
    lock = path.with_suffix(".lock")
    lock.touch()
    with pytest.raises(FileExistsError):
        local.advance(path, "generate", execution="local")
    assert local.load(path)["attempts"]["generation"] == 0
    lock.unlink()
    assert local.advance(path, "generate", execution="local")["perform_browser_action"]


def test_actions_cannot_claim_local_execution(tmp_path, monkeypatch):
    path = local.create(tmp_path, image_request())
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(ValueError, match="cannot assert"):
        local.advance(path, "generate", execution="local")
    assert not local.advance(path, "generate")["perform_browser_action"]


@pytest.mark.parametrize("fault", ["wrong-size", "nonsquare", "transparent", "html", "truncated"])
def test_real_image_validation_rejects_wrong_or_incomplete_artifacts(tmp_path, fault):
    path = local.create(tmp_path, image_request())
    source = tmp_path / "source.png"
    if fault == "html":
        source.write_text("<html>Login</html>")
    else:
        mode = "RGBA" if fault == "transparent" else "RGB"
        size = (64, 64) if fault == "wrong-size" else (32, 31) if fault == "nonsquare" else (32, 32)
        Image.new(mode, size).save(source)
        if fault == "truncated":
            source.write_bytes(source.read_bytes()[:40])
    local.advance(path, "observe", execution="local")
    with pytest.raises(ValueError):
        local.advance(path, "validate", execution="local")
    assert local.load(path)["status"] == "failed"


def test_artwork_cli_consumes_only_ready_source(tmp_path, monkeypatch):
    from scripts.generate_artwork import main
    path, image = saved_image(tmp_path)
    output = tmp_path / "export.jpg"
    monkeypatch.setattr(sys, "argv", ["artwork", "--episode-source", str(image),
                                     "--output", str(output), "--local-execution", str(path)])
    with pytest.raises(ValueError, match="not ready"):
        main()
    assert not output.exists()
    for action in ("observe", "validate", "resume"):
        local.advance(path, action, execution="local")
    main()
    with Image.open(output) as exported:
        assert exported.size == (3000, 3000) and exported.mode == "RGB"


def test_brief_creates_same_request_handoff_without_resubmission(tmp_path):
    from pipeline.adhoc import write_brief
    from pipeline.podcast_request import save_request
    req = request()
    request_path = save_request(req, tmp_path)
    brief = write_brief(req, draft(), request_path.parent)
    handoff = brief.parent / local.FILENAME
    state = local.load(handoff)
    assert state["request"]["prompt"] == brief.read_text(encoding="utf-8")
    assert state["request"]["parent_request_sha256"] == req.revision
    assert state["request"]["identity"] == req.episode_id
    local.advance(handoff, "generate", execution="local")
    before = handoff.read_bytes()
    assert write_brief(req, draft(), request_path.parent) == brief
    assert handoff.read_bytes() == before


def test_old_edge_brief_does_not_create_browser_work(tmp_path):
    from pipeline.adhoc import write_brief
    from pipeline.podcast_request import save_request
    req = request(provider="edge")
    request_path = save_request(req, tmp_path)
    write_brief(req, draft(), request_path.parent)
    assert not (request_path.parent / local.FILENAME).exists()


def test_reviewed_import_rejects_pending_browser_handoff_before_conversion(tmp_path):
    data = draft()
    path = local.create(tmp_path, local.LocalRequest(
        identity=data["episode_id"], kind="notebook-daily", purpose="Daily review",
        prompt="English Deep Dive Short, 5-8 minutes. Approved public evidence only.",
        artifact_name="original.m4a",
    ))
    audio = tmp_path / "original.m4a"
    audio.write_bytes(b"not yet reviewed")
    manifest = tmp_path / "draft.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="not ready"):
        prepare_reviewed_audio(manifest, audio, tmp_path / "prepared")
    assert not (tmp_path / "prepared").exists()
    assert local.load(path)["artifact"] is None


def test_correction_keeps_original_handoff_separate_from_composite(tmp_path, monkeypatch):
    from tests.test_reviewed_audio import corrected_draft
    data = corrected_draft()
    original = tmp_path / "original.m4a"
    original.write_bytes(b"original recording")
    path = local.create(tmp_path, local.LocalRequest(
        identity=data["episode_id"], kind="notebook-daily", purpose="Daily review",
        prompt="English Deep Dive Short", artifact_name=original.name,
    ))
    monkeypatch.setattr(local, "_measure", lambda *a: {
        "duration_secs": 360, "codec": "aac", "sample_rate": 44100, "channels": 2,
    })
    for action in ("observe", "validate", "resume"):
        local.advance(path, action, execution="local")
    data["generation"]["editing"]["original_audio_sha256"] = file_sha256(original)
    validate_local_handoff(path, tmp_path / "composite.wav", EpisodeManifest.from_dict(data))
    data["generation"]["editing"]["original_audio_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="original"):
        validate_local_handoff(path, tmp_path / "composite.wav", EpisodeManifest.from_dict(data))


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="media tools unavailable")
def test_original_notebook_aac_is_decoded_without_transcoding_or_relaxing_mp3_contract(tmp_path):
    path = local.create(tmp_path, local.LocalRequest(
        identity="adhoc-sample", kind="notebook-adhoc", purpose="Source recording for review",
        prompt="English Deep Dive Longer", artifact_name="original.m4a",
    ))
    audio = tmp_path / "original.m4a"
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=2", "-c:a", "aac", "-b:a", "128k", str(audio),
    ], check=True, timeout=30)
    before = audio.read_bytes()
    with pytest.raises(AudioValidationError, match="supported recording"):
        analyze_audio(audio, min_duration_secs=1, max_duration_secs=3)
    for action in ("observe", "validate", "resume"):
        result = local.advance(path, action, execution="local")
    assert result["outcome"] == "artifact-ready"
    assert result["artifact"]["measurements"]["codec"] == "aac"
    assert audio.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == [local.FILENAME, "original.m4a"]


def test_cli_pending_is_not_reported_as_completed(tmp_path, capsys):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(asdict(image_request())), encoding="utf-8")
    assert local.main(["prepare", "--spec", str(spec), "--directory", str(tmp_path / "staged")]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["outcome"] == "local-required" and not result["perform_browser_action"]
    path = tmp_path / "staged" / local.FILENAME
    assert local.main(["step", "--state", str(path), "--action", "observe", "--execution", "local"]) == 1
    assert json.loads(capsys.readouterr().out)["outcome"] == "failed"


def test_portable_handoff_requires_transferred_bytes_then_reuses_them(tmp_path):
    path, image = ready_image(tmp_path / "local")
    cloud = tmp_path / "cloud"
    cloud.mkdir()
    moved = cloud / local.FILENAME
    shutil.copyfile(path, moved)
    assert str(tmp_path) not in path.read_text()
    with pytest.raises(ValueError):
        local.advance(moved)
    shutil.copyfile(image, cloud / image.name)
    local.advance(moved, "recover", execution="local")
    local.advance(moved, "validate", execution="local")
    assert local.advance(moved)["outcome"] == "artifact-ready"
    assert local.load(moved)["attempts"]["generation"] == 0


@pytest.mark.parametrize("mutate", [
    lambda state: state.update(headers={"Authorization": "DO_NOT_STORE"}),
    lambda state: state.update(updated_at={"cookie": "DO_NOT_STORE"}),
    lambda state: state["validation"].update(session="DO_NOT_STORE"),
    lambda state: state["artifact"]["measurements"].update(profile="DO_NOT_STORE"),
    lambda state: state["attempts"].update(generation=2),
    lambda state: state.update(generation_completed=True),
])
def test_unknown_or_tampered_state_is_not_forwarded_or_rewritten(tmp_path, mutate, capsys):
    path, _ = ready_image(tmp_path)
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    before = path.read_bytes()
    assert local.main(["step", "--state", str(path)]) == 1
    assert "DO_NOT_STORE" not in capsys.readouterr().out
    assert path.read_bytes() == before


@pytest.mark.parametrize("duration,accepted", [(299.9, False), (300, True), (480, True), (480.1, False),
                                              (float("inf"), False), (float("nan"), False)])
def test_notebook_daily_keeps_measured_duration_gate(tmp_path, monkeypatch, duration, accepted):
    path = local.create(tmp_path, local.LocalRequest(
        identity="daily-example", kind="notebook-daily", purpose="Source recording for daily review",
        prompt="English Deep Dive Short", artifact_name="original.m4a",
    ))
    (tmp_path / "original.m4a").write_bytes(b"x" * 12000)
    monkeypatch.setattr("pipeline.audio.shutil.which", lambda name: name)
    def run(command, **kwargs):
        assert "-protocol_whitelist" in command
        payload = {"format": {"duration": duration}, "streams": [
            {"codec_name": "aac", "sample_rate": 44100, "channels": 2},
        ]}
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")
    monkeypatch.setattr("pipeline.audio.subprocess.run", run)
    local.advance(path, "observe", execution="local")
    if accepted:
        local.advance(path, "validate", execution="local")
        assert local.advance(path)["outcome"] == "artifact-ready"
    else:
        with pytest.raises(ValueError):
            local.advance(path, "validate", execution="local")
        assert local.load(path)["status"] == "failed"


def test_adhoc_prepare_cannot_bypass_its_request_handoff(tmp_path):
    from pipeline.adhoc import prepare, write_brief
    from tests.test_adhoc import prepare_inputs

    inputs = prepare_inputs(tmp_path)
    request_path, packet, _, _, _, output = inputs
    req = request(publish_now=True)
    write_brief(req, json.loads(packet.read_text()), request_path.parent)
    with pytest.raises(ValueError, match="not ready"):
        prepare(*inputs)
    assert not output.exists()
