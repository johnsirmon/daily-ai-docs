"""Bind an intentional quiet run to the last subscriber-confirmed episode."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .publish import PublicationError
from .schema import EpisodeManifest
from .source_health import primary_source_health

RUN_PATH = Path("data/runs/latest.json")


def _confirmed(episode_id: str) -> EpisodeManifest:
    if not isinstance(episode_id, str) or not re_safe_id(episode_id):
        raise ValueError("invalid confirmed episode identity")
    manifest = EpisodeManifest.from_dict(json.loads(
        (Path("data/episodes") / f"{episode_id}.json").read_text(encoding="utf-8")
    ))
    receipt = json.loads((Path("data/receipts") / f"{episode_id}.json").read_text(encoding="utf-8"))
    if (manifest.status != "published" or manifest.episode_id != episode_id
            or receipt["episode_id"] != episode_id or receipt["audio_sha256"] != manifest.audio["sha256"]):
        raise ValueError("confirmed episode lacks matching delivery evidence")
    manifest.validate(require_audio=True)
    return manifest


def re_safe_id(value: str) -> bool:
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}", value))


def skip_candidate(
    path: Path = RUN_PATH, *, max_age_hours: float = 25, now: datetime | None = None,
) -> EpisodeManifest | None:
    if not math.isfinite(max_age_hours) or max_age_hours <= 0:
        raise PublicationError("editorial freshness budget must be positive and finite")
    if not path.exists():
        state_path = Path("data/state.json")
        if (state_path.exists()
                and json.loads(state_path.read_text(encoding="utf-8")).get("schema_version") == 2):
            raise PublicationError("mixed-feed monitoring requires a daily evaluation receipt")
        return None
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt["schema_version"] != 1:
            raise ValueError("unsupported run receipt")
        status = receipt["status"]
        if status not in {"skipped", "published", "failed"}:
            raise ValueError("invalid run status")
        if status == "failed":
            raise ValueError("latest editorial run failed")
        stamp = datetime.fromisoformat(receipt["evaluated_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("run receipt lacks timezone")
        age = ((now or datetime.now(timezone.utc)) - stamp).total_seconds() / 3600
        if age < 0 or age > max_age_hours:
            raise ValueError("editorial run receipt is stale or future-dated")
        state_path = Path("data/state.json")
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        mixed = state.get("schema_version") == 2
        if status == "published" and not mixed:
            return None
        if mixed:
            for candidate_path in Path("data/episodes").glob("*.json"):
                if json.loads(candidate_path.read_text(encoding="utf-8")).get("status") == "candidate":
                    raise ValueError("pending publication requires recovery")
            head = _confirmed(state["last_episode_id"])
            if state["last_publication"] != head.published_at:
                raise ValueError("feed-head state does not match the confirmed manifest")
            if status == "published":
                daily = _confirmed(state["last_daily_episode_id"])
                if (daily.schema_version == 4 or state["last_daily_publication"] != daily.published_at
                        or receipt["last_episode_id"] != daily.episode_id):
                    raise ValueError("daily evaluation is not bound to the last daily publication")
                return head
        if receipt["reason"] not in {"insufficient_new_information", "insufficient_substantive_material"}:
            raise ValueError("unrecognized skip reason")
        health = receipt["source_health"]
        if not isinstance(health, dict) or not health:
            raise ValueError("skip receipt has no source health")
        sources = primary_source_health(health)
        healthy = sum(isinstance(value, str) and value.startswith("ok:") for value in sources.values())
        if not sources or healthy / len(sources) < max(0.6, float(receipt["minimum_source_health"])):
            raise ValueError("source outage is not an intentional skip")
        if mixed:
            _confirmed(receipt["last_episode_id"])
            return head
        for candidate_path in Path("data/episodes").glob("*.json"):
            if json.loads(candidate_path.read_text(encoding="utf-8")).get("status") == "candidate":
                raise ValueError("a pending publication cannot be hidden by a skip receipt")
        state = json.loads(Path("data/state.json").read_text(encoding="utf-8"))
        episode_id = state["last_episode_id"]
        if receipt["last_episode_id"] != episode_id:
            raise ValueError("skip receipt is not bound to the last publication")
        if not isinstance(episode_id, str) or Path(episode_id).name != episode_id or "/" in episode_id:
            raise ValueError("invalid publication identity")
        manifest = EpisodeManifest.from_dict(json.loads(
            (Path("data/episodes") / f"{episode_id}.json").read_text(encoding="utf-8")
        ))
        if manifest.status != "published" or manifest.episode_id != episode_id:
            raise ValueError("skip receipt requires a confirmed publication")
        if state["last_publication"] != manifest.published_at:
            raise ValueError("publication state and manifest disagree")
        delivered = json.loads((Path("data/receipts") / f"{episode_id}.json").read_text(encoding="utf-8"))
        if delivered["episode_id"] != episode_id or delivered["audio_sha256"] != manifest.audio["sha256"]:
            raise ValueError("skip receipt lacks matching delivery evidence")
        manifest.validate(require_audio=True)
        return manifest
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise PublicationError(f"invalid editorial run receipt: {exc}") from exc
