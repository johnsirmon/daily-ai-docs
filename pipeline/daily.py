"""Prepare and finalize the evidence-backed daily podcast publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

from .audio import analyze_audio
from .narrate import manifest_to_narration
from .podcast import prepend_episode
from .publish import validate_feed_file, verify_remote_audio, verify_remote_feed
from .rank import event_to_story, select_events
from .render import write_manifest_readme
from .schema import EpisodeManifest, SourceEvent
from .sources import (
    collect_github_releases,
    collect_official_feeds,
    collect_youtube_digest,
)
from .synthesis import refine_stories
from .tts import write_audio

logger = logging.getLogger(__name__)
_CACHE_DIR = Path(".cache")
_MANIFEST_PATH = _CACHE_DIR / "episode-manifest.json"
_PUBLICATION_PATH = _CACHE_DIR / "publication.json"
_STATE_PATH = Path("data/state.json")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_state(path: Path = _STATE_PATH) -> Dict[str, Any]:
    state = _load_json(path, {"schema_version": 1, "seen_event_ids": [], "last_publication": None})
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise ValueError("invalid daily state file")
    seen = state.get("seen_event_ids")
    if not isinstance(seen, list) or not all(isinstance(item, str) for item in seen):
        raise ValueError("state seen_event_ids must be a string list")
    return state


def _dry_events(now: datetime) -> tuple[List[SourceEvent], Dict[str, str]]:
    stamp = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    event = SourceEvent(
        event_id="dry-run:copilot-1",
        source_type="announcement",
        title="GitHub Copilot dry-run update",
        url="https://github.blog/changelog/",
        product="GitHub Copilot",
        topic="AI coding agents",
        published_at=stamp,
        fetched_at=stamp,
        evidence="A deterministic source-backed fixture demonstrates the daily pipeline without network access.",
        metadata={"priority": 20, "version": "dry-run-1"},
    ).validate()
    return [event], {"dry-run": "ok:1"}


def collect_events(config: Dict[str, Any], *, dry_run: bool, now: datetime) -> tuple[List[SourceEvent], Dict[str, str]]:
    if dry_run:
        return _dry_events(now)
    daily = config.get("daily", {})
    source_config = daily.get("sources", {})
    lookback = int(daily.get("lookback_hours", 36))
    github_events, github_health = collect_github_releases(
        source_config.get("github_releases", []), lookback_hours=lookback, now=now
    )
    feed_events, feed_health = collect_official_feeds(
        source_config.get("feeds", []), lookback_hours=lookback, now=now
    )
    youtube_events, youtube_health = collect_youtube_digest(source_config.get("youtube", {}), now=now)
    health = {**github_health, **feed_health, **youtube_health}
    if not health:
        raise RuntimeError("no daily sources are configured")
    healthy = sum(status.startswith("ok:") for status in health.values())
    if not healthy:
        raise RuntimeError("all configured sources failed; refusing to call this a quiet day")
    minimum_ratio = float(daily.get("minimum_source_health", 0.6))
    if healthy / len(health) < minimum_ratio:
        raise RuntimeError(
            f"source health {healthy}/{len(health)} is below the required {minimum_ratio:.0%}"
        )
    return github_events + feed_events + youtube_events, health


def _show_notes(stories, noise_notes: Iterable[str], source_health: Dict[str, str]) -> str:
    failed = [name for name, status in source_health.items() if not status.startswith("ok:")]
    if not stories:
        if failed:
            return "No update cleared the threshold, but coverage was incomplete. Failed sources: " + ", ".join(failed)
        return "Tracked sources were healthy, but no update cleared the actionability threshold today."
    sections = []
    for story in stories:
        sections.append(
            f"{story.headline}\nWhat changed: {story.what_changed}\n"
            f"Why it matters: {story.why_it_matters}\n"
            f"Recommendation: {story.action.upper()} — {story.rationale}\n"
            + "Sources: " + ", ".join(story.source_urls)
        )
    notes = list(noise_notes)
    if notes:
        sections.append("High noise / low signal\n" + "\n".join(f"- {note}" for note in notes))
    if failed:
        sections.append("Coverage gaps\n" + "\n".join(f"- {name}" for name in failed))
    return "\n\n".join(sections)


def _apply_measured_momentum(events: List[SourceEvent], state: Dict[str, Any], now: datetime) -> None:
    """Annotate release events with measured star velocity from prior snapshots."""
    snapshots = state.get("repo_snapshots") or {}
    for event in events:
        repo = event.metadata.get("repo")
        stars = int(event.metadata.get("stars") or 0)
        previous = snapshots.get(repo) if repo else None
        if not previous or not stars:
            continue
        try:
            prior_time = datetime.fromisoformat(str(previous["fetched_at"]).replace("Z", "+00:00"))
            elapsed_days = max((now - prior_time).total_seconds() / 86400, 1 / 24)
            delta = stars - int(previous["stars"])
            event.metadata["star_delta"] = delta
            event.metadata["star_velocity"] = round(delta / elapsed_days, 2)
            event.metadata["momentum_window_days"] = round(elapsed_days, 2)
        except (KeyError, TypeError, ValueError):
            continue


def _pending_candidate() -> EpisodeManifest | None:
    candidates = []
    for path in Path("data/episodes").glob("*.json"):
        try:
            manifest = EpisodeManifest.from_dict(_load_json(path, {}))
        except Exception:
            continue
        if manifest.status == "candidate":
            candidates.append(manifest)
    if len(candidates) > 1:
        raise RuntimeError("multiple pending publication candidates require manual recovery")
    return candidates[0] if candidates else None


def prepare(
    config_path: Path = Path("topics/topics.yaml"),
    *,
    dry_run: bool = False,
    no_audio: bool = False,
    force: bool = False,
    now: datetime | None = None,
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    state = load_state()
    if not dry_run and not force:
        pending = _pending_candidate()
        if pending is not None:
            _save_json(_MANIFEST_PATH, pending.to_dict())
            publication = {
                "episode_id": pending.episode_id,
                "tag": pending.episode_id,
                "manifest_path": str(_MANIFEST_PATH),
                "audio_path": str(_CACHE_DIR / "daily-ai-brief.mp3"),
                "audio_url": pending.audio["url"],
                "dry_run": False,
                "resumed": True,
            }
            _save_json(_PUBLICATION_PATH, publication)
            return publication
    last_publication = str(state.get("last_publication") or "")
    if not dry_run and not force and last_publication[:10] == now.astimezone(timezone.utc).date().isoformat():
        raise RuntimeError(f"a daily episode was already published on {last_publication[:10]}")
    events, health = collect_events(config, dry_run=dry_run, now=now)
    _apply_measured_momentum(events, state, now)
    daily = config.get("daily", {})
    selected, noise_notes = select_events(
        events,
        state.get("seen_event_ids", []),
        limit=int(daily.get("max_stories", 7)),
        minimum_score=float(daily.get("minimum_score", 45)),
        max_per_source_type={"youtube_video": int(daily.get("max_youtube_stories", 1))},
    )
    deterministic = [event_to_story(event, state.get("seen_event_ids", [])) for event in selected]
    if dry_run:
        stories, generation = deterministic, {"provider": "deterministic", "calls": 0, "dry_run": True}
    else:
        stories, generation = refine_stories(selected, deterministic)
    identity_material = "\n".join(event.event_id for event in selected) or "quiet"
    suffix = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()[:8]
    episode_date = (
        max(event.published_at for event in selected)[:10]
        if selected
        else now.astimezone(timezone.utc).date().isoformat()
    )
    episode_id = f"daily-{episode_date}-{suffix}"
    repository = os.environ.get("GITHUB_REPOSITORY", "johnsirmon/daily-ai-docs")
    audio_url = f"https://github.com/{repository}/releases/download/{episode_id}/daily-ai-brief.mp3"
    manifest = EpisodeManifest(
        schema_version=1,
        episode_id=episode_id,
        published_at=now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        status="draft",
        source_health=health,
        source_events=selected,
        stories=stories,
        noise_notes=noise_notes,
        narration="pending",
        show_notes=_show_notes(stories, noise_notes, health),
        generation={
            **generation,
            "edition": "quiet" if not stories else ("alert" if len(stories) < 3 else "normal"),
        },
        audio={"url": audio_url},
    )
    manifest.narration = manifest_to_narration(manifest)
    manifest.validate(require_audio=False)
    _save_json(_MANIFEST_PATH, manifest.to_dict())

    # The basename must match the immutable enclosure URL used by GitHub Releases.
    audio_path = _CACHE_DIR / "daily-ai-brief.mp3"
    if not dry_run and not no_audio:
        produced = write_audio(manifest.narration, path=str(audio_path))
        if produced is None:
            raise RuntimeError("TTS failed; candidate feed was not modified")
        edition = manifest.generation["edition"]
        minimum_duration = {"quiet": 30, "alert": 30, "normal": 180}[edition]
        maximum_duration = {"quiet": 120, "alert": 300, "normal": 600}[edition]
        analysis = analyze_audio(
            produced,
            min_duration_secs=minimum_duration,
            max_duration_secs=maximum_duration,
            expected_word_count=len(manifest.narration.split()),
        )
        manifest.audio.update(analysis)
        manifest.audio.pop("path", None)
        manifest.status = "ready"
        manifest.validate(require_audio=True)
        _save_json(_MANIFEST_PATH, manifest.to_dict())

    publication = {
        "episode_id": episode_id,
        "tag": episode_id,
        "manifest_path": str(_MANIFEST_PATH),
        "audio_path": str(audio_path) if not (dry_run or no_audio) else "",
        "audio_url": audio_url,
        "dry_run": dry_run,
    }
    _save_json(_PUBLICATION_PATH, publication)
    return publication


def finalize(
    manifest_path: Path = _MANIFEST_PATH,
    *,
    verify_remote: bool = True,
    feed_path: Path = Path("podcast.xml"),
    publication_path: Path | None = None,
) -> EpisodeManifest:
    manifest = EpisodeManifest.from_dict(_load_json(manifest_path, {}))
    manifest.validate(require_audio=True)
    if publication_path is not None:
        publication = _load_json(publication_path, {})
        if (publication.get("episode_id") != manifest.episode_id
                or publication.get("tag") != manifest.episode_id
                or publication.get("audio_url") != manifest.audio["url"]):
            raise RuntimeError("downloaded release identity does not match prepared publication")
        audio = Path(publication["audio_path"]).read_bytes()
        if (len(audio) != int(manifest.audio["size_bytes"])
                or hashlib.sha256(audio).hexdigest() != manifest.audio["sha256"]):
            raise RuntimeError("downloaded release audio does not match manifest")
    existing_path = Path("data/episodes") / f"{manifest.episode_id}.json"
    if existing_path.exists():
        existing = EpisodeManifest.from_dict(_load_json(existing_path, {}))
        accepted, downloaded = existing.to_dict(), manifest.to_dict()
        accepted.pop("status")
        downloaded.pop("status")
        if accepted != downloaded:
            raise RuntimeError("downloaded release manifest does not match accepted candidate")
        if existing.status == "published":
            raise RuntimeError("episode is already published; use confirm to recheck delivery")
    if verify_remote:
        verify_remote_audio(
            manifest.audio["url"],
            expected_size=int(manifest.audio["size_bytes"]),
            expected_sha256=manifest.audio["sha256"],
        )
    episode = {
        "title": f"Daily AI Developer Brief — {manifest.published_at[:10]}",
        "guid": manifest.episode_id,
        "pub_date": manifest.published_at,
        "description": manifest.show_notes,
        "mp3_url": manifest.audio["url"],
        "file_size_bytes": int(manifest.audio["size_bytes"]),
        "duration_secs": float(manifest.audio["duration_secs"]),
    }
    prepend_episode(episode, path=str(feed_path))
    validate_feed_file(feed_path)
    manifest.status = "candidate"
    manifest.validate(require_audio=True)
    final_manifest = Path("data/episodes") / f"{manifest.episode_id}.json"
    _save_json(final_manifest, manifest.to_dict())
    write_manifest_readme(
        manifest,
        feed_url=os.environ.get("PODCAST_FEED_URL", "https://johnsirmon.github.io/daily-ai-docs/podcast.xml"),
    )
    return manifest


def confirm(episode_id: str, *, verify_remote: bool = True) -> EpisodeManifest:
    """Advance novelty state only after subscriber-facing delivery succeeds."""
    path = Path("data/episodes") / f"{episode_id}.json"
    manifest = EpisodeManifest.from_dict(_load_json(path, {}))
    if manifest.episode_id != episode_id or manifest.status not in {"candidate", "published"}:
        raise RuntimeError("publication candidate is missing or has the wrong state")
    manifest.validate(require_audio=True)
    state = load_state()
    receipt_path = Path("data/receipts") / f"{episode_id}.json"
    feed_result = {"status": "skipped"}
    if verify_remote:
        feed_result = verify_remote_feed(
            os.environ.get("PODCAST_FEED_URL", "https://johnsirmon.github.io/daily-ai-docs/podcast.xml"),
            expected_guid=episode_id,
            candidate=manifest,
        )
    if (manifest.status == "published" and receipt_path.exists()
            and set(e.event_id for e in manifest.source_events).issubset(state["seen_event_ids"])):
        return manifest
    manifest.status = "published"
    manifest.validate(require_audio=True)
    _save_json(path, manifest.to_dict())
    state = load_state()
    seen = list(dict.fromkeys(state.get("seen_event_ids", []) + [e.event_id for e in manifest.source_events]))
    snapshots = dict(state.get("repo_snapshots") or {})
    for event in manifest.source_events:
        repo = event.metadata.get("repo")
        stars = int(event.metadata.get("stars") or 0)
        if repo and stars:
            snapshots[repo] = {"stars": stars, "fetched_at": event.fetched_at}
    confirmed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _save_json(_STATE_PATH, {
        "schema_version": 1,
        "seen_event_ids": seen[-2000:],
        "last_publication": manifest.published_at,
        "last_episode_id": manifest.episode_id,
        "repo_snapshots": snapshots,
    })
    _save_json(Path("data/receipts") / f"{episode_id}.json", {
        "episode_id": episode_id,
        "confirmed_at": confirmed_at,
        "feed": feed_result,
        "audio_sha256": manifest.audio["sha256"],
    })
    return manifest


def _print_github_output(publication: Dict[str, Any]) -> None:
    for key in ("episode_id", "tag", "manifest_path", "audio_path", "audio_url"):
        print(f"{key}={publication[key]}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Daily AI Developer Brief publisher")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--config", default="topics/topics.yaml")
    prepare_parser.add_argument("--dry-run", action="store_true")
    prepare_parser.add_argument("--no-audio", action="store_true")
    prepare_parser.add_argument("--github-output", action="store_true")
    prepare_parser.add_argument("--force", action="store_true", help="Allow a second same-day episode")
    finalize_parser = sub.add_parser("finalize")
    finalize_parser.add_argument("--manifest", default=str(_MANIFEST_PATH))
    finalize_parser.add_argument("--publication", type=Path, help="Reconcile downloaded release with prepare outputs")
    finalize_parser.add_argument("--skip-remote-verification", action="store_true")
    confirm_parser = sub.add_parser("confirm")
    confirm_parser.add_argument("--episode-id", default=os.environ.get("EXPECTED_GUID"))
    confirm_parser.add_argument("--skip-remote-verification", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(Path(args.config), dry_run=args.dry_run, no_audio=args.no_audio, force=args.force)
        if args.github_output:
            _print_github_output(result)
        else:
            print(json.dumps(result, indent=2))
    elif args.command == "finalize":
        result = finalize(Path(args.manifest), verify_remote=not args.skip_remote_verification,
                          publication_path=args.publication)
        print(json.dumps({"episode_id": result.episode_id, "status": result.status}, indent=2))
    else:
        if not args.episode_id:
            raise SystemExit("confirm requires --episode-id or EXPECTED_GUID")
        result = confirm(args.episode_id, verify_remote=not args.skip_remote_verification)
        print(json.dumps({"episode_id": result.episode_id, "status": result.status}, indent=2))


if __name__ == "__main__":
    main()
