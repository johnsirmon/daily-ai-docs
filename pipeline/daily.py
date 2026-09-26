"""Prepare and finalize the evidence-backed daily podcast publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

from .audio import AudioDurationError, analyze_audio, file_sha256, narration_duration_bounds
from .disclosure import AI_NARRATION_DISCLOSURE
from .evidence_archive import publication_evidence
from .narrate import EXPLANATORY_NARRATION_STYLES, manifest_to_narration
from .podcast import prepend_episode
from .podcast_metadata import manifest_presentation
from .publish import validate_feed_file, validate_local_episode_artwork, verify_remote_audio, verify_remote_feed
from .rank import event_to_story, group_editorial_stories, select_editorial_events, select_events
from .render import write_manifest_readme
from .schema import EpisodeManifest, SourceEvent
from .sources import (
    collect_github_releases,
    collect_official_feeds,
    collect_observer_packet,
    collect_research_papers,
    collect_youtube_digest,
)
from .synthesis import refine_editorial, refine_stories
from .tts import write_audio
from .run_health import RUN_PATH
from .source_health import failed_source_health, primary_source_health

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
    if not isinstance(state, dict) or state.get("schema_version") not in {1, 2}:
        raise ValueError("invalid daily state file")
    seen = state.get("seen_event_ids")
    if not isinstance(seen, list) or not all(isinstance(item, str) for item in seen):
        raise ValueError("state seen_event_ids must be a string list")
    if state["schema_version"] == 2:
        for field in ("last_daily_episode_id", "last_daily_publication"):
            if field not in state or (state[field] is not None and not isinstance(state[field], str)):
                raise ValueError(f"mixed-feed state requires {field}")
    return state


def editorial_enabled(config: Dict[str, Any]) -> bool:
    mode = os.environ.get("AI_EDITORIAL")
    if mode is not None:
        if mode not in {"off", "required"}:
            raise ValueError("AI_EDITORIAL must be off or required")
        return mode == "required"
    return config.get("daily", {}).get("editorial", {}).get("enabled", False) is True


def _publication_history(now: datetime) -> tuple[list[dict], set[str], list[dict]]:
    history, paper_ids, published_events = [], set(), []
    for path in sorted(Path("data/episodes").glob("*.json")):
        manifest = EpisodeManifest.from_dict(_load_json(path, {}))
        if manifest.status != "published":
            continue
        stamp = datetime.fromisoformat(manifest.published_at.replace("Z", "+00:00"))
        for event in manifest.source_events:
            if event.source_type == "research_paper" and event.metadata.get("paper_id"):
                paper_ids.add(str(event.metadata["paper_id"]))
        if not now - timedelta(days=30) <= stamp <= now:
            continue
        for event in manifest.source_events:
            published_events.append({
                "canonical_event_id": event.metadata.get("canonical_event_id", event.event_id),
                "product": event.product, "channel": event.channel,
                "published_at": manifest.published_at,
                "normalized_evidence": " ".join(event.evidence.casefold().split()),
                "evidence_sha256": event.metadata.get("source_evidence_sha256") or hashlib.sha256(
                    " ".join(event.evidence.casefold().split()).encode("utf-8")
                ).hexdigest(),
            })
        for story in manifest.stories:
            history.append({
                "episode_id": manifest.episode_id,
                "published_at": manifest.published_at,
                "event_ids": story.event_ids,
                "headline": story.headline,
                "what_changed": story.what_changed,
                "why_it_matters": story.why_it_matters,
            })
    history.sort(key=lambda row: row["published_at"])
    bounded_history = []
    chars = 0
    for row in reversed(history):
        size = len(json.dumps(row, ensure_ascii=False))
        if chars + size > 12000:
            break
        bounded_history.append(row)
        chars += size
    return list(reversed(bounded_history)), paper_ids, published_events


def _record_run(status: str, *, now: datetime, reason: str, health: Dict[str, str],
                minimum_health: float = 0.6) -> None:
    state = load_state()
    _save_json(RUN_PATH, {
        "schema_version": 1,
        "status": status,
        "evaluated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reason": reason,
        "source_health": health,
        "minimum_source_health": minimum_health,
        "last_episode_id": state.get("last_episode_id"),
    })


def _skip(*, now: datetime, reason: str, health: Dict[str, str],
          minimum_health: float, notes: List[str]) -> Dict[str, Any]:
    _record_run("skipped", now=now, reason=reason, health=health, minimum_health=minimum_health)
    publication = {
        "outcome": "skipped", "reason": reason, "selection_notes": notes,
        "episode_id": "", "tag": "", "manifest_path": "", "audio_path": "", "audio_url": "",
        "dry_run": False,
    }
    _save_json(_PUBLICATION_PATH, publication)
    logger.info("Daily run skipped: %s", reason)
    return publication


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
        evidence="A deterministic fixture adds a permission check before tool execution without network access.",
        metadata={"priority": 20, "version": "dry-run-1"},
    ).validate()
    return [event], {"dry-run": "ok:1"}


def collect_events(
    config: Dict[str, Any], *, dry_run: bool, now: datetime,
    covered_paper_ids: Iterable[str] = (),
) -> tuple[List[SourceEvent], Dict[str, str]]:
    if dry_run:
        return _dry_events(now)
    daily = config.get("daily", {})
    source_config = daily.get("sources", {})
    lookback = int(daily.get("lookback_hours", 36))
    def source_options(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {**item, "enrichment": {
                **(item.get("enrichment") or {}),
                "enabled": (item.get("enrichment") or {}).get("enabled") is True,
            }}
            for item in items
        ]
    github_events, github_health = collect_github_releases(
        source_options(source_config.get("github_releases", [])), lookback_hours=lookback, now=now
    )
    feed_events, feed_health = collect_official_feeds(
        source_options(source_config.get("feeds", [])), lookback_hours=lookback, now=now
    )
    youtube_events, youtube_health = collect_youtube_digest(source_config.get("youtube", {}), now=now)
    paper_events, paper_health = ([], {})
    observer_events, observer_health = ([], {})
    if editorial_enabled(config):
        paper_events, paper_health = collect_research_papers(
            source_config.get("papers", {}), now=now, covered_paper_ids=covered_paper_ids,
        )
        observer_events, observer_health = collect_observer_packet(daily.get("observer"), now=now)
    else:
        observer_events, observer_health = collect_observer_packet(daily.get("observer"), now=now)
        if observer_health:
            raise ValueError("Observer ingestion requires grounded editorial mode")
    health = {**github_health, **feed_health, **youtube_health, **paper_health, **observer_health}
    if not health:
        raise RuntimeError("no daily sources are configured")
    source_health = primary_source_health(health)
    if not source_health:
        raise RuntimeError("no daily primary sources are configured")
    healthy = sum(status.startswith("ok:") for status in source_health.values())
    if not healthy:
        raise RuntimeError("all configured sources failed; refusing to call this a quiet day")
    minimum_ratio = float(daily.get("minimum_source_health", 0.6))
    if healthy / len(source_health) < minimum_ratio:
        raise RuntimeError(
            f"source health {healthy}/{len(source_health)} is below the required {minimum_ratio:.0%}"
        )
    return github_events + feed_events + youtube_events + paper_events + observer_events, health


def _show_notes(stories, noise_notes: Iterable[str], source_health: Dict[str, str]) -> str:
    failed_primary, failed_supplementary = failed_source_health(source_health)
    if not stories:
        if failed_primary:
            return (
                "No update cleared the threshold, but primary-source coverage was incomplete. "
                "Failed primary sources: " + ", ".join(failed_primary)
            )
        if failed_supplementary:
            return (
                "Primary sources were healthy and no update cleared the actionability threshold today. "
                "Unavailable supplementary sources: " + ", ".join(failed_supplementary)
            )
        return "Tracked sources were healthy, but no item established enough developer utility for an episode."
    sections = []
    for story in stories:
        section = (
            f"{story.headline}\nWhat to know: {story.what_changed}\n"
            f"What changes for developers: {story.why_it_matters}\n"
            f"Recommendation: {story.action.upper()} — {story.rationale}\n"
            + "Sources: " + ", ".join(story.source_urls)
        )
        if story.kind == "research":
            review = story.editorial["paper_review"]
            section += (
                f"\nResearch evidence: {review['evidence_status']}\n"
                f"Question: {review['question']}\nMethod: {review['method']}\n"
                f"Result: {review['result']}\nLimitations: {review['limitations']}\n"
                f"Experiment to try: {review['takeaway']}"
            )
        sections.append(section)
    notes = list(noise_notes)
    if notes:
        sections.append("High noise / low signal\n" + "\n".join(f"- {note}" for note in notes))
    if failed_primary:
        sections.append("Primary-source coverage gaps\n" + "\n".join(f"- {name}" for name in failed_primary))
    if failed_supplementary:
        sections.append(
            "Supplementary coverage gaps\n" + "\n".join(f"- {name}" for name in failed_supplementary)
        )
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


def _prepare(
    config_path: Path = Path("topics/topics.yaml"),
    *,
    dry_run: bool = False,
    no_audio: bool = False,
    force: bool = False,
    now: datetime | None = None,
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    use_editorial = editorial_enabled(config) and not dry_run
    state = load_state()
    if not dry_run and not force:
        pending = _pending_candidate()
        if pending is not None:
            _save_json(_MANIFEST_PATH, pending.to_dict())
            publication = {
                "outcome": "publish",
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
    last_publication = str(state.get(
        "last_daily_publication", state.get("last_publication"),
    ) or "")
    if not dry_run and not force and last_publication[:10] == now.astimezone(timezone.utc).date().isoformat():
        raise RuntimeError(f"a daily episode was already published on {last_publication[:10]}")
    history, paper_ids, published_events = ([], set(), [])
    if use_editorial:
        history, paper_ids, published_events = _publication_history(now)
    events, health = collect_events(
        config, dry_run=dry_run, now=now, covered_paper_ids=paper_ids,
    )
    _apply_measured_momentum(events, state, now)
    daily = config.get("daily", {})
    editorial = daily.get("editorial", {})
    if use_editorial:
        minimum_words = int(editorial.get("minimum_words", 600))
        maximum_words = int(editorial.get("maximum_words", 1100))
        if not 100 <= minimum_words <= maximum_words <= 1500:
            raise ValueError("invalid editorial word budget")
        selected, noise_notes = select_editorial_events(
            events, state.get("seen_event_ids", []), covered_paper_ids=paper_ids,
            published_events=published_events,
            max_products=int(editorial.get("max_products", 3)),
            max_events_per_product=int(editorial.get("max_events_per_product", 1)),
            max_research=int(editorial.get("max_research", 1)), now=now,
        )
        if not selected:
            return _skip(now=now, reason="insufficient_new_information", health=health,
                         minimum_health=float(daily.get("minimum_source_health", 0.6)), notes=noise_notes)
        stories, generation = refine_editorial(
            selected, group_editorial_stories(selected), history, config={
                **editorial, "target_min_words": minimum_words, "target_max_words": maximum_words,
            },
        )
        if not stories or all(story.kind == "research" for story in stories):
            return _skip(now=now, reason="insufficient_substantive_material", health=health,
                         minimum_health=float(daily.get("minimum_source_health", 0.6)), notes=noise_notes)
        used_ids = {event_id for story in stories for event_id in story.event_ids}
        selected = [event for event in selected if event.event_id in used_ids]
        selected = publication_evidence(selected, stories)
    else:
        selected, noise_notes = select_events(
            events,
            state.get("seen_event_ids", []),
            limit=int(daily.get("max_stories", 7)),
            minimum_score=float(daily.get("minimum_score", 75)),
            max_per_source_type={"youtube_video": int(daily.get("max_youtube_stories", 1))},
            max_per_product=int(daily.get("max_stories_per_product", 2)),
        )
        if not selected:
            return _skip(
                now=now, reason="insufficient_new_information", health=health,
                minimum_health=float(daily.get("minimum_source_health", 0.6)), notes=noise_notes,
            )
        deterministic = [event_to_story(event, state.get("seen_event_ids", [])) for event in selected]
    observer_notes = list(dict.fromkeys(
        note for event in events for note in event.metadata.get("observer_noise_notes", [])
        if isinstance(note, str)
    ))
    noise_notes = list(dict.fromkeys([*noise_notes, *observer_notes]))
    if dry_run:
        stories, generation = deterministic, {"provider": "deterministic", "calls": 0, "dry_run": True}
    elif not use_editorial:
        stories, generation = refine_stories(selected, deterministic)
    if use_editorial:
        generation = {**generation, "production_disclosure": AI_NARRATION_DISCLOSURE}
    else:
        generation = {**generation, "narration_style": "explanatory-v3"}
    identity_material = "\n".join(event.event_id for event in selected) or "quiet"
    if use_editorial:
        identity_material = "editorial-v2\n" + identity_material
    suffix = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()[:8]
    episode_date = (
        max(event.published_at for event in selected)[:10]
        if selected and not use_editorial
        else now.astimezone(timezone.utc).date().isoformat()
    )
    episode_id = f"daily-{episode_date}-{suffix}"
    repository = os.environ.get("GITHUB_REPOSITORY", "johnsirmon/daily-ai-docs")
    audio_url = f"https://github.com/{repository}/releases/download/{episode_id}/daily-ai-brief.mp3"
    manifest = EpisodeManifest(
        schema_version=2 if use_editorial else 1,
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
    if os.environ.get("PODCAST_AUDIO_POLISH", "0") == "1":
        from .audio_quality import repetition_findings
        if repetition_findings(manifest.narration):
            raise ValueError("adjacent repeated narration requires editorial review")
    if use_editorial:
        if len(manifest.narration.split()) < minimum_words:
            return _skip(now=now, reason="insufficient_substantive_material", health=health,
                         minimum_health=float(daily.get("minimum_source_health", 0.6)), notes=noise_notes)
        if len(manifest.narration.split()) > maximum_words:
            raise ValueError("editorial narration exceeds the configured word budget")
    manifest.validate(require_audio=False)
    edition = manifest.generation["edition"]
    minimum_duration = 300 if use_editorial else {"quiet": 30, "alert": 30, "normal": 180}[edition]
    maximum_duration = 480 if use_editorial else {"quiet": 120, "alert": 300, "normal": 600}[edition]
    is_explanatory_narration = manifest.generation.get("narration_style") in EXPLANATORY_NARRATION_STYLES
    if not dry_run and is_explanatory_narration:
        plausible_minimum, plausible_maximum = narration_duration_bounds(len(manifest.narration.split()))
        if plausible_maximum < minimum_duration:
            return _skip(
                now=now, reason="insufficient_substantive_material", health=health,
                minimum_health=float(daily.get("minimum_source_health", 0.6)), notes=noise_notes,
            )
        if plausible_minimum > maximum_duration:
            raise ValueError("narration cannot fit the edition's maximum audio duration")
    _save_json(_MANIFEST_PATH, manifest.to_dict())

    # The basename must match the immutable enclosure URL used by GitHub Releases.
    audio_path = _CACHE_DIR / "daily-ai-brief.mp3"
    if not dry_run and not no_audio:
        produced = write_audio(manifest.narration, path=str(audio_path))
        if produced is None:
            raise RuntimeError("TTS failed; candidate feed was not modified")
        if os.environ.get("PODCAST_AUDIO_POLISH", "0") == "1":
            from .audio_quality import polish_generated_audio
            manifest.generation["source_audio_sha256"] = file_sha256(produced)
            manifest.generation["quality"] = polish_generated_audio(produced)
        try:
            analysis = analyze_audio(
                produced,
                min_duration_secs=minimum_duration,
                max_duration_secs=maximum_duration,
                expected_word_count=len(manifest.narration.split()),
            )
        except AudioDurationError as exc:
            # The preemptive plausibility check above is a heuristic; measured
            # TTS output can still land just short of the edition's minimum.
            # Treat that as thin content rather than an unrecoverable failure,
            # but only for the deterministic explanatory narration path: this
            # audio call is not nested under the preemptive check above, so
            # editorial narration (which never sets an explanatory
            # narration_style) can still reach here and must keep failing hard.
            if exc.too_short and is_explanatory_narration:
                _MANIFEST_PATH.unlink(missing_ok=True)
                Path(produced).unlink(missing_ok=True)
                return _skip(
                    now=now, reason="insufficient_substantive_material", health=health,
                    minimum_health=float(daily.get("minimum_source_health", 0.6)), notes=noise_notes,
                )
            raise
        manifest.audio.update(analysis)
        manifest.audio.pop("path", None)
        manifest.status = "ready"
        manifest.validate(require_audio=True)
        _save_json(_MANIFEST_PATH, manifest.to_dict())

    publication = {
        "outcome": "publish",
        "episode_id": episode_id,
        "tag": episode_id,
        "manifest_path": str(_MANIFEST_PATH),
        "audio_path": str(audio_path) if not (dry_run or no_audio) else "",
        "audio_url": audio_url,
        "dry_run": dry_run,
    }
    _save_json(_PUBLICATION_PATH, publication)
    return publication


def prepare(
    config_path: Path = Path("topics/topics.yaml"), *,
    dry_run: bool = False, no_audio: bool = False, force: bool = False,
    now: datetime | None = None,
) -> Dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    enabled = editorial_enabled(config) and not dry_run
    now = now or datetime.now(timezone.utc)
    try:
        return _prepare(config_path, dry_run=dry_run, no_audio=no_audio, force=force, now=now)
    except Exception as exc:
        if enabled:
            logger.error("Editorial preparation failed: %s", type(exc).__name__)
            _record_run("failed", now=now, reason=type(exc).__name__, health={})
        raise


def _validate_reviewed_audio_file(manifest: EpisodeManifest, path: Path) -> None:
    word_count = len(manifest.narration.split())
    minimum, maximum = (
        narration_duration_bounds(word_count) if manifest.schema_version == 4 else (300, 480)
    )
    measured = analyze_audio(
        path, min_duration_secs=minimum, max_duration_secs=maximum,
        expected_word_count=word_count,
    )
    for field in ("size_bytes", "sha256", "codec", "sample_rate", "channels"):
        if manifest.audio.get(field) != measured[field]:
            raise RuntimeError(f"reviewed release audio {field} does not match its manifest")
    # FFprobe versions differ in whether MP3 priming/padding frames count toward duration.
    tolerance = 2 * 1152 / measured["sample_rate"] + 0.001
    expected, actual = manifest.audio["duration_secs"], measured["duration_secs"]
    if not math.isclose(expected, actual, rel_tol=0, abs_tol=tolerance):
        raise RuntimeError(
            f"reviewed release audio duration_secs does not match its manifest: "
            f"expected {expected:.3f}s, measured {actual:.3f}s"
        )
    logger.info("Reviewed MP3 duration: manifest %.3fs, decoded metadata %.3fs", expected, actual)
    if "quality" in manifest.generation:
        from .audio_quality import loudness
        levels = loudness(path)
        if not -17 <= levels["input_i"] <= -15 or levels["input_tp"] > -1:
            raise RuntimeError("reviewed release fails measured loudness/peak gate")


def resume_reviewed_release(episode_id: str, directory: Path = _CACHE_DIR) -> Dict[str, Any]:
    """Resume approved external audio from downloaded immutable release assets."""
    manifest_path = directory / "episode-manifest.json"
    manifest = EpisodeManifest.from_dict(_load_json(manifest_path, {}))
    if manifest.schema_version not in {3, 4} or manifest.episode_id != episode_id:
        raise RuntimeError("reviewed release identity or schema does not match the requested episode")
    if manifest.status not in {"ready", "candidate"} or manifest.generation.get("preview_only"):
        raise RuntimeError("reviewed release must be approved publication media, not a preview")
    manifest.validate(require_audio=True)
    if manifest.generation.get("edition") == "gate-a-one-release-waiver":
        from .gate_a_release import validate_exact_publication_manifest
        validate_exact_publication_manifest(
            manifest, manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        )
    pending = _pending_candidate()
    if pending is not None and pending.episode_id != episode_id:
        raise RuntimeError("another publication candidate requires recovery first")
    audio_path = directory / "daily-ai-brief.mp3"
    repository = os.environ.get("GITHUB_REPOSITORY", "johnsirmon/daily-ai-docs")
    expected_url = f"https://github.com/{repository}/releases/download/{episode_id}/daily-ai-brief.mp3"
    if manifest.audio["url"] != expected_url:
        raise RuntimeError("reviewed release audio URL does not match the requested repository and tag")
    _validate_reviewed_audio_file(manifest, audio_path)
    publication = {
        "outcome": "publish", "episode_id": episode_id, "tag": episode_id,
        "manifest_path": str(manifest_path), "audio_path": str(audio_path),
        "audio_url": expected_url, "dry_run": False, "resumed": True,
    }
    _save_json(directory / "publication.json", publication)
    return publication


def finalize(
    manifest_path: Path = _MANIFEST_PATH,
    *,
    verify_remote: bool = True,
    feed_path: Path = Path("podcast.xml"),
    publication_path: Path | None = None,
) -> EpisodeManifest:
    manifest = EpisodeManifest.from_dict(_load_json(manifest_path, {}))
    if manifest.generation.get("preview_only") is True:
        raise RuntimeError("unpublished preview artifacts cannot be finalized")
    manifest.validate(require_audio=True)
    if manifest.schema_version in {3, 4} and publication_path is None:
        raise RuntimeError("reviewed audio finalization requires downloaded release reconciliation")
    if manifest.schema_version == 4:
        from .podcast_request import PodcastRequest
        request = PodcastRequest.from_dict(manifest.generation["request"])
        if not request.publish_now:
            raise RuntimeError("preview request cannot be finalized")
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
        if manifest.schema_version in {3, 4}:
            _validate_reviewed_audio_file(manifest, Path(publication["audio_path"]))
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
        **manifest_presentation(manifest),
        "guid": manifest.episode_id,
        "pub_date": manifest.published_at,
        "mp3_url": manifest.audio["url"],
        "file_size_bytes": int(manifest.audio["size_bytes"]),
        "duration_secs": float(manifest.audio["duration_secs"]),
    }
    if feed_path.exists():
        validate_feed_file(feed_path, artwork_root=feed_path.parent)
    if "image_url" in episode:
        validate_local_episode_artwork(episode["image_url"], feed_path.parent)
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
        if manifest.schema_version != 4:
            _record_run("published", now=datetime.now(timezone.utc), reason="subscriber_confirmed",
                        health=manifest.source_health)
        else:
            _record_adhoc_confirmation(manifest, _load_json(receipt_path, {})["confirmed_at"])
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
    next_state = {
        "schema_version": 1,
        "seen_event_ids": seen[-2000:],
        "last_publication": manifest.published_at,
        "last_episode_id": manifest.episode_id,
        "repo_snapshots": snapshots,
    }
    if manifest.schema_version == 4 or state["schema_version"] == 2:
        next_state["schema_version"] = 2
        next_state["last_daily_episode_id"] = (
            state.get("last_daily_episode_id", state.get("last_episode_id"))
            if manifest.schema_version == 4 else manifest.episode_id
        )
        next_state["last_daily_publication"] = (
            state.get("last_daily_publication", state.get("last_publication"))
            if manifest.schema_version == 4 else manifest.published_at
        )
    _save_json(_STATE_PATH, next_state)
    _save_json(Path("data/receipts") / f"{episode_id}.json", {
        "episode_id": episode_id,
        "confirmed_at": confirmed_at,
        "feed": feed_result,
        "audio_sha256": manifest.audio["sha256"],
    })
    if manifest.schema_version == 4:
        _record_adhoc_confirmation(manifest, confirmed_at)
    else:
        _record_run("published", now=datetime.now(timezone.utc), reason="subscriber_confirmed",
                    health=manifest.source_health)
    return manifest


def _record_adhoc_confirmation(manifest: EpisodeManifest, confirmed_at: str) -> None:
    from .podcast_request import PodcastRequest
    request = PodcastRequest.from_dict(manifest.generation["request"])
    _save_json(Path("data/requests") / f"{request.request_id}.json", {
        "schema_version": 1, "request": request.to_dict(), "request_sha256": request.revision,
        "status": "published", "episode_id": manifest.episode_id, "confirmed_at": confirmed_at,
        "audio_sha256": manifest.audio["sha256"],
    })


def _print_github_output(publication: Dict[str, Any]) -> None:
    for key in ("outcome", "episode_id", "tag", "manifest_path", "audio_path", "audio_url"):
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
    resume_parser = sub.add_parser("resume-reviewed", help="Validate downloaded reviewed-audio release assets")
    resume_parser.add_argument("--episode-id", required=True)
    resume_parser.add_argument("--directory", type=Path, default=_CACHE_DIR)
    resume_parser.add_argument("--github-output", action="store_true")
    finalize_parser = sub.add_parser("finalize")
    finalize_parser.add_argument("--manifest", default=str(_MANIFEST_PATH))
    finalize_parser.add_argument("--publication", type=Path, help="Reconcile downloaded release with prepare outputs")
    finalize_parser.add_argument("--skip-remote-verification", action="store_true")
    confirm_parser = sub.add_parser("confirm")
    confirm_parser.add_argument("--episode-id", default=os.environ.get("EXPECTED_GUID"))
    confirm_parser.add_argument("--skip-remote-verification", action="store_true")
    sub.add_parser("fail-run", help="Persist a safe failed-workflow receipt without modifying the feed")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(Path(args.config), dry_run=args.dry_run, no_audio=args.no_audio, force=args.force)
        if args.github_output:
            _print_github_output(result)
        else:
            print(json.dumps(result, indent=2))
    elif args.command == "resume-reviewed":
        result = resume_reviewed_release(args.episode_id, args.directory)
        if args.github_output:
            _print_github_output(result)
        else:
            print(json.dumps(result, indent=2))
    elif args.command == "finalize":
        result = finalize(Path(args.manifest), verify_remote=not args.skip_remote_verification,
                          publication_path=args.publication)
        print(json.dumps({"episode_id": result.episode_id, "status": result.status}, indent=2))
    elif args.command == "fail-run":
        _record_run("failed", now=datetime.now(timezone.utc), reason="workflow_failure", health={})
    else:
        if not args.episode_id:
            raise SystemExit("confirm requires --episode-id or EXPECTED_GUID")
        result = confirm(args.episode_id, verify_remote=not args.skip_remote_verification)
        print(json.dumps({"episode_id": result.episode_id, "status": result.status}, indent=2))


if __name__ == "__main__":
    main()
