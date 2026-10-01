from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline.audio import analyze_audio, AudioDurationError
from pipeline.disclosure import AI_NARRATION_DISCLOSURE
from pipeline.reviewed_duration import reviewed_duration_bounds
from pipeline.schema import EpisodeManifest, SchemaError
from tests.test_studio import edge_draft
from tests.test_reviewed_audio import CLAIM, TIMESTAMP


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def short_draft():
    data = edge_draft()
    text = AI_NARRATION_DISCLOSURE + " " + CLAIM + " " + " ".join(
        f"For example {i}, inspect the proposed change in a disposable workspace before approving execution."
        for i in range(40)) + " Keep the current setup until the comparison is complete."
    data["narration"] = text
    data["generation"]["transcript"]["sha256"] = digest(text)
    data["generation"]["duration_policy"] = {
        "class": "short_brief", "rationale": "The complete reviewed explanation is concise; extra material would add repetition rather than useful evidence.",
        "approved_at": TIMESTAMP, "script": text, "script_sha256": digest(text),
        "source_audio_sha256": data["generation"]["source_audio_sha256"],
        "transcript_sha256": digest(text)}
    return data


def rebind_transcript(data, text):
    data["narration"] = text
    data["generation"]["transcript"]["sha256"] = digest(text)
    data["generation"]["duration_policy"]["transcript_sha256"] = digest(text)


def ready(data, duration=266):
    data = deepcopy(data); data["status"] = "ready"
    data["audio"].update(sha256="a" * 64, size_bytes=4000000, duration_secs=duration,
                         codec="mp3", sample_rate=44100, channels=2)
    data["generation"]["quality"] = {"method": "ffmpeg_loudnorm_two_pass", "ffmpeg": "ffmpeg test",
                                     "integrated_lufs": -16, "true_peak_dbtp": -2, "audio_sha256": "a" * 64}
    return data


def test_explicit_concise_approval_round_trips_and_keeps_old_default():
    draft = short_draft()
    manifest = EpisodeManifest.from_dict(ready(draft))
    assert manifest.to_dict()["generation"]["duration_policy"] == draft["generation"]["duration_policy"]
    assert reviewed_duration_bounds(manifest) == (len(draft["narration"].split()) / 190 * 60, 300)
    unapproved = ready(draft); unapproved["generation"].pop("duration_policy")
    with pytest.raises(SchemaError, match="300-480"):
        EpisodeManifest.from_dict(unapproved)


@pytest.mark.parametrize("change", [
    lambda d: d["generation"].update(duration_policy=None),
    lambda d: d["generation"]["duration_policy"].update(rationale=""),
    lambda d: d["generation"]["duration_policy"].update(approved_at="2026-10-01"),
    lambda d: d["generation"]["duration_policy"].update(**{"class": "bypass"}),
    lambda d: d["generation"]["duration_policy"].update(script_sha256="0" * 64),
    lambda d: d["generation"]["duration_policy"].update(source_audio_sha256="0" * 64),
    lambda d: d["generation"]["duration_policy"].update(transcript_sha256="0" * 64),
    lambda d: d["generation"]["duration_policy"].update(approved=True),
    lambda d: d["generation"].update(edition="notebook", provider="gemini-notebook-web"),
])
def test_short_class_cannot_bypass_approval_or_provenance(change):
    data = short_draft(); change(data)
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("cut", ["opening", "ending", "middle"])
def test_truncated_transcript_fails_even_after_rehashing_it(cut):
    data = short_draft(); words = data["narration"].split()
    words = words[30:] if cut == "opening" else words[:-30] if cut == "ending" else words[:160] + words[220:]
    rebind_transcript(data, " ".join(words))
    with pytest.raises(SchemaError, match="opening|ending|omits|disclosure"):
        EpisodeManifest.from_dict(data)


def test_short_approval_never_removes_disclosure_requirement():
    data = short_draft(); policy = data["generation"]["duration_policy"]
    text = data["narration"].replace(AI_NARRATION_DISCLOSURE, "")
    rebind_transcript(data, text); policy.update(script=text, script_sha256=digest(text))
    with pytest.raises(SchemaError, match="disclosure"):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("duration", [180, 301, float("nan")])
def test_ready_media_must_match_approved_word_length_and_short_window(duration):
    with pytest.raises(SchemaError, match="duration"):
        EpisodeManifest.from_dict(ready(short_draft(), duration))


def test_real_audio_analyzer_rejects_short_truncated_render(monkeypatch, tmp_path):
    # Bytes are probed through the real analyzer; a 180s render is too short for
    # this approved script even though it meets the class's absolute floor.
    data = short_draft(); minimum, maximum = reviewed_duration_bounds(EpisodeManifest.from_dict(data))
    audio = tmp_path / "truncated.mp3"; audio.write_bytes(b"x" * 20000)
    monkeypatch.setattr("pipeline.audio.shutil.which", lambda _: "/bin/ffprobe")
    monkeypatch.setattr("pipeline.audio.subprocess.run", lambda *a, **k: SimpleNamespace(
        returncode=0, stderr="", stdout=json.dumps({"format": {"duration": "180"},
        "streams": [{"codec_name": "mp3", "sample_rate": "44100", "channels": 2}]})))
    with pytest.raises(AudioDurationError) as error:
        analyze_audio(audio, min_duration_secs=minimum, max_duration_secs=maximum,
                      expected_word_count=len(data["narration"].split()))
    assert error.value.too_short


def test_import_and_delivery_reuse_short_bounds_and_full_audio_checks(monkeypatch, tmp_path):
    from pipeline.reviewed_audio import prepare_reviewed_audio
    from pipeline.daily import _validate_reviewed_audio_file
    data = short_draft(); source = tmp_path / "source.mp3"; source.write_bytes(b"original recording")
    draft = tmp_path / "draft.json"; draft.write_text(json.dumps(data))
    def master(src, dst):
        dst.write_bytes(b"final" * 4000)
        return {"method": "ffmpeg_loudnorm_two_pass", "ffmpeg": "ffmpeg test", "integrated_lufs": -16,
                "true_peak_dbtp": -2, "audio_sha256": hashlib.sha256(dst.read_bytes()).hexdigest()}
    calls = []
    def analyze(path, **kwargs):
        calls.append(kwargs)
        assert kwargs["min_duration_secs"] == len(data["narration"].split()) / 190 * 60
        assert kwargs["max_duration_secs"] == 300
        assert kwargs.get("full_decode", True) is True
        assert kwargs["expected_word_count"] == len(data["narration"].split())
        return dict(path=str(path), sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    size_bytes=Path(path).stat().st_size, duration_secs=266, codec="mp3", sample_rate=44100, channels=2)
    monkeypatch.setattr("pipeline.reviewed_audio.shutil.which", lambda _: "/bin/ffmpeg")
    monkeypatch.setattr("pipeline.audio_quality.master_audio", master)
    monkeypatch.setattr("pipeline.reviewed_audio.analyze_audio", analyze)
    monkeypatch.setattr("pipeline.daily.analyze_audio", analyze)
    monkeypatch.setattr("pipeline.audio_quality.loudness", lambda _: {"input_i": -16, "input_tp": -2})
    receipt = prepare_reviewed_audio(draft, source, tmp_path / "bundle")
    manifest = EpisodeManifest.from_dict(json.loads(Path(receipt["manifest_path"]).read_text()))
    _validate_reviewed_audio_file(manifest, Path(receipt["audio_path"]))
    assert len(calls) == 2
    changed = deepcopy(manifest); changed.audio["sha256"] = "f" * 64
    with pytest.raises(RuntimeError, match="sha256"):
        _validate_reviewed_audio_file(changed, Path(receipt["audio_path"]))


def test_short_audio_still_requires_successful_full_decode(monkeypatch, tmp_path):
    data = short_draft(); minimum, maximum = reviewed_duration_bounds(EpisodeManifest.from_dict(data))
    audio = tmp_path / "broken.mp3"; audio.write_bytes(b"x" * 20000)
    monkeypatch.setattr("pipeline.audio.shutil.which", lambda name: "/bin/" + name)
    def run(command, **kwargs):
        if command[0].endswith("ffprobe"):
            return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps({"format": {"duration": "266"},
                "streams": [{"codec_name": "mp3", "sample_rate": "44100", "channels": 2}]}))
        return SimpleNamespace(returncode=1, stderr="corrupt audio frame", stdout="")
    monkeypatch.setattr("pipeline.audio.subprocess.run", run)
    from pipeline.audio import AudioValidationError
    with pytest.raises(AudioValidationError, match="full decode"):
        analyze_audio(audio, min_duration_secs=minimum, max_duration_secs=maximum,
                      expected_word_count=len(data["narration"].split()))
