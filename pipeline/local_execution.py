"""Offline, request-local handoffs for authenticated browser work; never a publisher."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import urlsplit

from .audio import analyze_audio, file_sha256
from .podcast_request import content_hash, utc_timestamp

FILENAME = "local-execution.json"
KINDS = ("chatgpt-image", "notebook-daily", "notebook-adhoc")
STATUSES = (
    "ready-for-local-execution", "waiting-for-operator", "local-artifact-created",
    "local-artifact-validated", "ready-to-resume-automation", "failed",
)
REASONS = ("browser-unavailable", "sign-in-required", "generation-pending", "save-file",
           "download-unconfirmed", "generation-failed", "validation-failed", "artifact-missing")
MAX_VALIDATIONS = 3


def _requirements(request: LocalRequest) -> dict[str, Any]:
    if request.kind == "chatgpt-image":
        return {"formats": ["PNG", "JPEG"], "width": request.width, "height": request.height,
                "single_frame": True, "opaque": True, "full_decode": True, "sha256": True}
    return {"full_decode": True, "sha256": True, "reject_effective_silence": True,
            "minimum_bytes": 10_000, "duration_policy": (
                "300-480 seconds" if request.kind == "notebook-daily" else
                "finite positive; transcript plausibility remains a reviewed-import gate"
            )}


def _public_text(value: str, maximum: int) -> None:
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(char) < 32 and char not in "\n\r\t" for char in value)):
        raise ValueError("handoff text must be bounded public text")
    if re.search(
        r"(?i)(?:cookie|authorization|session[_ -]?token|access[_ -]?token|api[_ -]?key"
        r"|browser[_ -]?profile|storage[_ -]?state)\s*[:=]"
        r"|\bBearer\s+\S+|__Secure-|__Host-|\bsk-[A-Za-z0-9_-]{16,}|\bAIza[A-Za-z0-9_-]{20,}",
        value,
    ):
        raise ValueError("authentication material is forbidden in handoffs")
    for url in re.findall(r"https?://[^\s<>]+", value):
        parsed = urlsplit(url.rstrip(").,"))
        if (parsed.query or parsed.fragment or parsed.username or parsed.password
                or parsed.hostname in {"chatgpt.com", "chat.openai.com", "gemini.google.com",
                                       "notebooklm.google.com", "accounts.google.com"}):
            raise ValueError("persist only public source URLs, not session or signed download links")


@dataclass(frozen=True)
class LocalRequest:
    identity: str
    kind: str
    purpose: str
    prompt: str
    artifact_name: str
    width: int = 0
    height: int = 0
    parent_request_sha256: str = ""

    def validate(self) -> "LocalRequest":
        if not isinstance(self.identity, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,119}", self.identity):
            raise ValueError("handoff requires a safe episode/request identity")
        if self.kind not in KINDS:
            raise ValueError("unsupported local browser operation")
        _public_text(self.purpose, 500)
        _public_text(self.prompt, 60_000)
        if (not isinstance(self.artifact_name, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,100}\.(png|jpg|jpeg|mp3|m4a|wav|ogg)", self.artifact_name)):
            raise ValueError("artifact must be a request-local media filename")
        if type(self.width) is not int or type(self.height) is not int:
            raise ValueError("image dimensions must be integers")
        if self.kind == "chatgpt-image":
            if not 1 <= self.width == self.height <= 8192 or Path(self.artifact_name).suffix not in {".png", ".jpg", ".jpeg"}:
                raise ValueError("image handoff requires exact square source dimensions and PNG/JPEG")
        elif self.width or self.height or Path(self.artifact_name).suffix not in {".mp3", ".m4a", ".wav", ".ogg"}:
            raise ValueError("Notebook handoff requires audio, not image dimensions")
        if (not isinstance(self.parent_request_sha256, str)
                or self.parent_request_sha256 and not re.fullmatch(r"[a-f0-9]{64}", self.parent_request_sha256)):
            raise ValueError("invalid parent request hash")
        return self

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "LocalRequest":
        if not isinstance(value, dict):
            raise ValueError("handoff request must be an object")
        try:
            return cls(**value).validate()
        except TypeError as exc:
            raise ValueError("unknown or missing handoff request fields") from exc


@contextmanager
def _lock(path: Path):
    # Exclusive ownership also prevents two local agents from claiming the same click.
    lock = path.with_suffix(".lock")
    with lock.open("x", encoding="utf-8"):
        pass
    try:
        yield
    finally:
        lock.unlink()


def _save(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


def load(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("handoff record must not be a symlink")
    state = json.loads(path.read_text(encoding="utf-8"))
    fields = {"schema_version", "request", "request_sha256", "validation", "status", "attempts", "generation_completed",
              "operator_action", "operator_save_confirmed", "failure", "artifact", "updated_at"}
    if (not isinstance(state, dict) or set(state) != fields
            or type(state["schema_version"]) is not int or state["schema_version"] != 1):
        raise ValueError("invalid handoff state fields")
    request = LocalRequest.from_dict(state["request"])
    utc_timestamp(state["updated_at"])
    if state["validation"] != _requirements(request):
        raise ValueError("handoff validation requirements changed")
    if state["request_sha256"] != content_hash(asdict(request)) or state["status"] not in STATUSES:
        raise ValueError("handoff identity or status changed")
    attempts = state["attempts"]
    if not isinstance(attempts, dict) or set(attempts) != {"generation", "download", "validation"}:
        raise ValueError("invalid handoff attempts")
    for name, limit in (("generation", 1), ("download", 1), ("validation", MAX_VALIDATIONS)):
        if type(attempts[name]) is not int or not 0 <= attempts[name] <= limit:
            raise ValueError("invalid handoff attempt budget")
    if (type(state["generation_completed"]) is not bool or type(state["operator_save_confirmed"]) is not bool
            or state["operator_action"] not in ("", *REASONS)
            or state["failure"] not in ("", *REASONS)):
        raise ValueError("invalid handoff milestone")
    if ((state["generation_completed"] and not attempts["generation"])
            or (attempts["download"] and not state["generation_completed"])):
        raise ValueError("browser milestones are out of order")
    artifact = state["artifact"]
    if artifact is not None:
        if (not isinstance(artifact, dict) or set(artifact) != {"sha256", "size_bytes", "measurements"}
                or not re.fullmatch(r"[a-f0-9]{64}", str(artifact["sha256"]))
                or type(artifact["size_bytes"]) is not int or artifact["size_bytes"] <= 0):
            raise ValueError("invalid handoff artifact identity")
        measurements = artifact["measurements"]
        allowed = ({"width", "height", "format"} if request.kind == "chatgpt-image"
                   else {"duration_secs", "codec", "sample_rate", "channels"})
        if not isinstance(measurements, dict) or measurements and set(measurements) != allowed:
            raise ValueError("invalid handoff measurements")
        for name, value in measurements.items():
            if name in {"format", "codec"}:
                if not isinstance(value, str) or value not in {
                    "PNG", "JPEG", "mp3", "aac", "opus", "vorbis", "pcm_s16le", "pcm_s24le", "pcm_f32le",
                }:
                    raise ValueError("invalid media format")
            elif type(value) not in {int, float} or not 0 < value < float("inf"):
                raise ValueError("invalid media measurement")
    if state["status"] in STATUSES[2:5] and artifact is None:
        raise ValueError("artifact milestone requires measured file identity")
    if state["status"] in STATUSES[3:5] and not artifact["measurements"]:
        raise ValueError("validated milestone requires media measurements")
    return state


def create(directory: Path, request: LocalRequest) -> Path:
    request.validate()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / FILENAME
    with _lock(path):
        if path.exists():
            if load(path)["request"] != asdict(request):
                raise ValueError("handoff already exists with different intent; preserve it and revise explicitly")
            return path
        _save(path, {
            "schema_version": 1, "request": asdict(request), "request_sha256": content_hash(asdict(request)),
            "validation": _requirements(request),
            "status": STATUSES[0], "attempts": {"generation": 0, "download": 0, "validation": 0},
            "generation_completed": False, "operator_action": "", "operator_save_confirmed": False,
            "failure": "", "artifact": None,
        })
    return path


def _artifact_path(path: Path, state: dict[str, Any]) -> Path:
    artifact = path.parent / state["request"]["artifact_name"]
    if artifact.is_symlink() or not artifact.is_file():
        raise ValueError("expected artifact is missing or is a symlink")
    return artifact


def _identity(artifact: Path) -> dict[str, Any]:
    size = artifact.stat().st_size
    if size <= 0:
        raise ValueError("expected artifact is empty")
    return {"size_bytes": size, "sha256": file_sha256(artifact)}


def _check_bytes(path: Path, state: dict[str, Any]) -> Path:
    artifact = _artifact_path(path, state)
    if state["artifact"] is None or any(
        state["artifact"][key] != value for key, value in _identity(artifact).items()
    ):
        raise ValueError("artifact differs from the recorded bytes; do not regenerate or replace it")
    return artifact


def require_artifact(path: Path, source: Path, *, identity: str, kind: str,
                     parent_request_sha256: str = "") -> dict[str, Any]:
    """Consumer guard, not publication or editorial approval."""
    state = load(path)
    request = state["request"]
    if (request["identity"] != identity or request["kind"] != kind
            or request["parent_request_sha256"] != parent_request_sha256):
        raise ValueError("artifact handoff does not match the consuming request")
    if state["status"] != "ready-to-resume-automation":
        raise ValueError("local artifact is not ready to resume automation")
    if _check_bytes(path, state).resolve() != source.resolve():
        raise ValueError("consumer must reuse the validated artifact path")
    return state


def _measure(artifact: Path, request: dict[str, Any]) -> dict[str, Any]:
    if request["kind"] == "chatgpt-image":
        from PIL import Image
        from scripts.generate_artwork import create_episode_artwork

        with Image.open(artifact) as image:
            if image.size != (request["width"], request["height"]):
                raise ValueError("image does not match requested source dimensions")
            measured = {"width": image.width, "height": image.height, "format": image.format}
        # Reuse the existing single-frame, full-decode, square and opacity gates.
        create_episode_artwork(artifact).close()
        return measured
    daily = request["kind"] == "notebook-daily"
    measured = analyze_audio(
        artifact, min_duration_secs=300 if daily else 0.001,
        max_duration_secs=480 if daily else float("inf"), full_decode=True,
        allowed_codecs=("mp3", "aac", "opus", "vorbis", "pcm_s16le", "pcm_s24le", "pcm_f32le"),
    )
    if measured["sample_rate"] <= 0 or measured["channels"] <= 0 or measured["duration_secs"] <= 0:
        raise ValueError("recording requires positive media measurements")
    return {key: measured[key] for key in ("duration_secs", "codec", "sample_rate", "channels")}


def advance(path: Path, action: str = "resume", *, execution: str = "cloud",
            reason: str = "", operator_saved: bool = False) -> dict[str, Any]:
    if execution not in {"cloud", "local"}:
        raise ValueError("execution must be cloud or local")
    if execution == "local" and os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise ValueError("GitHub Actions cannot assert a local authenticated browser")
    if action not in {"resume", "generate", "generated", "download", "wait", "observe", "validate", "fail", "recover"}:
        raise ValueError("unknown handoff action")
    if action in {"wait", "fail"} and reason not in REASONS:
        raise ValueError("a fixed, non-secret reason code is required")
    with _lock(path):
        state = load(path)
        perform = False
        if execution == "cloud" and state["status"] not in STATUSES[3:5]:
            return _result(path, state, perform)
        if execution == "cloud":
            action = "resume"
        try:
            if state["status"] in STATUSES[3:5]:
                _check_bytes(path, state)
            if action == "resume":
                if state["status"] in STATUSES[3:5]:
                    state["status"] = "ready-to-resume-automation"
            elif execution != "local":
                raise ValueError("only local execution may record browser or artifact milestones")
            elif action == "recover":
                if state["status"] == "failed":
                    state["failure"] = ""
                    state["status"] = ("local-artifact-created" if state["artifact"] else
                                       "waiting-for-operator" if any(state["attempts"].values()) else STATUSES[0])
                    if state["artifact"] and state["artifact"]["measurements"]:
                        _check_bytes(path, state)
                        state["status"] = "local-artifact-validated"
            elif state["status"] == "failed":
                raise ValueError("recover the failed handoff explicitly; attempt counts will not reset")
            elif action in {"generate", "download"}:
                # An existing file wins over any missing browser event.
                if (path.parent / state["request"]["artifact_name"]).exists() or state["artifact"]:
                    return _result(path, state, perform)
                if action == "download" and not state["generation_completed"]:
                    raise ValueError("confirm persisted generation before requesting a download")
                counter = "generation" if action == "generate" else "download"
                if not state["attempts"][counter]:
                    state["attempts"][counter] = 1
                    state["status"] = "waiting-for-operator"
                    state["operator_action"] = "generation-pending" if action == "generate" else "download-unconfirmed"
                    perform = True
            elif action == "generated":
                if not state["attempts"]["generation"]:
                    raise ValueError("generation was not claimed")
                state["generation_completed"] = True
            elif action in {"wait", "fail"}:
                state["operator_action"] = reason
                if action == "fail":
                    state["failure"], state["status"] = reason, "failed"
                elif state["status"] not in STATUSES[2:5]:
                    state["status"] = "waiting-for-operator"
            elif action == "observe":
                artifact = _artifact_path(path, state)
                if state["artifact"]:
                    _check_bytes(path, state)
                else:
                    state["artifact"] = {**_identity(artifact), "measurements": {}}
                    state["status"] = "local-artifact-created"
                state["operator_save_confirmed"] |= operator_saved
                state["operator_action"] = ""
            elif action == "validate":
                artifact = _check_bytes(path, state)
                if state["status"] not in STATUSES[3:5]:
                    if state["attempts"]["validation"] >= MAX_VALIDATIONS:
                        raise ValueError("local validation attempt budget exhausted")
                    state["attempts"]["validation"] += 1
                    _save(path, state)
                    state["artifact"]["measurements"] = _measure(artifact, state["request"])
                    _check_bytes(path, state)
                    state["status"] = "local-artifact-validated"
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError):
            state["status"], state["failure"] = "failed", "validation-failed"
            _save(path, state)
            raise ValueError("local handoff failed; inspect the expected artifact or prerequisites, then recover") from None
        _save(path, state)
        return _result(path, state, perform)


def _result(path: Path, state: dict[str, Any], perform: bool) -> dict[str, Any]:
    return {
        **state, "outcome": ("artifact-ready" if state["status"] == STATUSES[4] else
                            "failed" if state["status"] == "failed" else "local-required"),
        "perform_browser_action": perform,
        "expected_path": str(path.parent / state["request"]["artifact_name"]),
        "publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="freeze a public request; no browser or API calls")
    prepare.add_argument("--spec", type=Path, required=True)
    prepare.add_argument("--directory", type=Path, required=True)
    step = sub.add_parser("step", help="record a milestone; browser clicks remain local agent actions")
    step.add_argument("--state", type=Path, required=True)
    step.add_argument("--action", default="resume", choices=[
        "resume", "generate", "generated", "download", "wait", "observe", "validate", "fail", "recover",
    ])
    step.add_argument("--execution", choices=["cloud", "local"], default="cloud")
    step.add_argument("--reason", choices=REASONS, default="")
    step.add_argument("--operator-saved", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            path = create(args.directory, LocalRequest.from_dict(json.loads(args.spec.read_text(encoding="utf-8"))))
            result = advance(path)
        else:
            result = advance(args.state, args.action, execution=args.execution,
                             reason=args.reason, operator_saved=args.operator_saved)
    except (ValueError, OSError):
        # Never echo raw browser/provider errors, supplied prompt text, or media metadata.
        print(json.dumps({"outcome": "failed", "error": "handoff rejected; check state, inputs and local prerequisites"}))
        return 1
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 1 if result["outcome"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
