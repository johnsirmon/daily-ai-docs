"""Generate review artifacts without publishing or modifying confirmed state."""

from __future__ import annotations

import argparse
from contextlib import chdir
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import tempfile

import requests
import yaml

from . import daily
from .models_client import EditorialConfigurationError, EditorialProviderError, editorial_model_config
from .schema import MAX_PUBLIC_EXCERPT_WORDS, EpisodeManifest

logger = logging.getLogger(__name__)


class PreviewError(RuntimeError):
    """An unpublished preview failed; safe diagnostics are available in its report."""


def verify_model_access(config: dict | None = None) -> dict:
    settings = editorial_model_config(config)
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise EditorialConfigurationError("preview requires the dedicated GEMINI_API_KEY")
    try:
        with requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.model}",
            headers={"x-goog-api-key": key}, timeout=(5, 30), allow_redirects=False,
        ) as response:
            if response.status_code != 200:
                raise EditorialProviderError(f"Gemini model preflight returned HTTP {response.status_code}")
            metadata = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise EditorialProviderError("Gemini model preflight failed without making a generation request") from exc
    methods = metadata.get("supportedGenerationMethods") if isinstance(metadata, dict) else None
    if (not isinstance(metadata, dict) or metadata.get("name") != f"models/{settings.model}"
            or not isinstance(methods, list) or "generateContent" not in methods):
        raise EditorialProviderError("configured Gemini model does not advertise content generation")
    return {"model": settings.model, "metadata_access_verified": True}


def _safe_error(exc: Exception) -> str:
    message = str(exc)
    for name, value in os.environ.items():
        if value and (name.endswith("_KEY") or name.endswith("_TOKEN")):
            message = message.replace(value, "[redacted]")
    return re.sub(r"AIza[0-9A-Za-z_-]{30,}", "[redacted]", message)[:500]


def _export_script(root: Path, output: Path) -> EpisodeManifest | None:
    path = root / ".cache/episode-manifest.json"
    if not path.exists():
        return None
    manifest = EpisodeManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if manifest.schema_version != 2 or manifest.generation.get("verified") is not True:
        raise PreviewError("preview refuses unverified or legacy narration")
    if any("full_text" in event.metadata or len(event.evidence.split()) > MAX_PUBLIC_EXCERPT_WORDS
           for event in manifest.source_events):
        raise PreviewError("preview artifacts must contain short archived excerpts, not full documents")
    manifest.generation["preview_only"] = True
    (output / "episode-manifest.json").write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    (output / "narration.txt").write_text(manifest.narration + "\n", encoding="utf-8")
    (output / "show-notes.txt").write_text(
        "UNPUBLISHED LISTENING PREVIEW - not a published episode\n\n" + manifest.show_notes + "\n",
        encoding="utf-8",
    )
    return manifest


def run_preview(
    *, config_path: Path, history_root: Path, output_dir: Path, free_tier_confirmed: bool = False,
) -> dict:
    config_path, history_root, output_dir = (
        path.resolve() for path in (config_path, history_root, output_dir)
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": 1, "purpose": "unpublished_preview", "status": "started",
        "evaluated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "free_tier_confirmed_by_operator": free_tier_confirmed,
        "generation_request_limit": 2, "automatic_retries": 0,
    }
    try:
        if not free_tier_confirmed:
            raise PreviewError("confirm the project's unbilled free tier and model quota before previewing")
        if os.environ.get("AI_EDITORIAL") != "required" or os.environ.get("TTS_PROVIDER") != "edge":
            raise PreviewError("preview requires AI_EDITORIAL=required and TTS_PROVIDER=edge")
        if not (history_root / "data/state.json").is_file() or not (history_root / "data/episodes").is_dir():
            raise PreviewError("preview requires confirmed publication history, not an empty novelty state")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        report.update(verify_model_access(config.get("daily", {}).get("editorial", {})))
        with tempfile.TemporaryDirectory(prefix="daily-editorial-preview-") as directory:
            root = Path(directory)
            shutil.copytree(history_root / "data", root / "data")
            with chdir(root):
                report["history_last_episode_id"] = daily.load_state().get("last_episode_id")
                try:
                    publication = daily.prepare(config_path, force=True)
                finally:
                    manifest = _export_script(root, output_dir)
                if publication["outcome"] == "skipped":
                    report.update(status="skipped", reason=publication["reason"],
                                  selection_notes=publication["selection_notes"])
                    report["evaluation"] = json.loads(daily.RUN_PATH.read_text(encoding="utf-8"))
                else:
                    if manifest is None or manifest.status != "ready":
                        raise PreviewError("preview preparation did not produce validated audio")
                    manifest.validate(require_audio=True)
                    audio = Path(publication["audio_path"]).read_bytes()
                    if (len(audio) != manifest.audio["size_bytes"]
                            or hashlib.sha256(audio).hexdigest() != manifest.audio["sha256"]):
                        raise PreviewError("preview audio does not match its validated manifest")
                    (output_dir / "daily-ai-brief.mp3").write_bytes(audio)
                    report.update(
                        status="ready", episode_id=manifest.episode_id,
                        word_count=len(manifest.narration.split()),
                        duration_secs=manifest.audio["duration_secs"],
                        audio_sha256=manifest.audio["sha256"], generation=manifest.generation,
                        source_health=manifest.source_health,
                    )
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__, reason=_safe_error(exc))
        logger.error("Unpublished preview failed: %s: %s", report["error_type"], report["reason"])
        raise PreviewError(report["reason"]) from None
    finally:
        (output_dir / "preview-report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
        )
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("topics/topics.yaml"))
    parser.add_argument("--history-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path(".cache/preview"))
    parser.add_argument("--free-tier-confirmed", action="store_true")
    args = parser.parse_args()
    try:
        report = run_preview(
            config_path=args.config, history_root=args.history_root, output_dir=args.output_dir,
            free_tier_confirmed=args.free_tier_confirmed,
        )
    except PreviewError:
        raise SystemExit(1) from None
    print(json.dumps({key: report[key] for key in ("status", "model", "history_last_episode_id")}))


if __name__ == "__main__":
    main()
