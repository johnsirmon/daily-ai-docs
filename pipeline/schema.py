"""Validated data contracts for daily source events and podcast episodes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse


class SchemaError(ValueError):
    """Raised when pipeline data does not satisfy the publication contract."""


def _text(value: Any, name: str, *, allow_empty: bool = False, limit: int = 8000) -> str:
    if not isinstance(value, str):
        raise SchemaError(f"{name} must be a string")
    value = value.strip()
    if not allow_empty and not value:
        raise SchemaError(f"{name} must not be empty")
    if len(value) > limit:
        raise SchemaError(f"{name} exceeds {limit} characters")
    return value


def _https_url(value: Any, name: str) -> str:
    value = _text(value, name, limit=2048)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SchemaError(f"{name} must be a public https URL")
    return value


def _timestamp(value: Any, name: str) -> str:
    value = _text(value, name, limit=64)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchemaError(f"{name} must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise SchemaError(f"{name} must include a timezone")
    return value


@dataclass(frozen=True)
class SourceEvent:
    event_id: str
    source_type: str
    title: str
    url: str
    product: str
    topic: str
    published_at: str
    fetched_at: str
    evidence: str
    authority: str = "primary"
    channel: str = "stable"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> "SourceEvent":
        _text(self.event_id, "event_id", limit=200)
        if self.source_type not in {
            "github_release", "official_feed", "announcement", "security", "community", "youtube_video"
        }:
            raise SchemaError("unsupported source_type")
        _text(self.title, "title", limit=500)
        _https_url(self.url, "url")
        _text(self.product, "product", limit=200)
        _text(self.topic, "topic", limit=100)
        _timestamp(self.published_at, "published_at")
        _timestamp(self.fetched_at, "fetched_at")
        _text(self.evidence, "evidence", limit=4000)
        if self.authority not in {"primary", "secondary"}:
            raise SchemaError("authority must be primary or secondary")
        if self.channel not in {"stable", "prerelease", "announcement", "security"}:
            raise SchemaError("unsupported channel")
        if not isinstance(self.metadata, dict):
            raise SchemaError("metadata must be an object")
        if self.metadata.get("private") is True or self.metadata.get("draft") is True:
            raise SchemaError("private repositories and draft releases are not publishable")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceEvent":
        if not isinstance(data, dict):
            raise SchemaError("source event must be an object")
        try:
            return cls(**data).validate()
        except TypeError as exc:
            raise SchemaError(f"invalid source event fields: {exc}") from exc


@dataclass(frozen=True)
class Story:
    story_id: str
    event_ids: List[str]
    headline: str
    what_changed: str
    why_it_matters: str
    action: str
    rationale: str
    source_urls: List[str]
    scores: Dict[str, float]

    def validate(self) -> "Story":
        _text(self.story_id, "story_id", limit=200)
        if not isinstance(self.event_ids, list) or not self.event_ids or not all(isinstance(x, str) and x for x in self.event_ids):
            raise SchemaError("event_ids must be a non-empty string list")
        _text(self.headline, "headline", limit=500)
        _text(self.what_changed, "what_changed", limit=1600)
        _text(self.why_it_matters, "why_it_matters", limit=1600)
        if self.action not in {"act", "watch", "skip"}:
            raise SchemaError("action must be act, watch, or skip")
        _text(self.rationale, "rationale", limit=1200)
        if not isinstance(self.source_urls, list) or not self.source_urls:
            raise SchemaError("source_urls must be non-empty")
        for index, url in enumerate(self.source_urls):
            _https_url(url, f"source_urls[{index}]")
        if not isinstance(self.scores, dict) or not self.scores:
            raise SchemaError("scores must be an object")
        for key, value in self.scores.items():
            if not isinstance(key, str) or not isinstance(value, (int, float)):
                raise SchemaError("scores must contain numeric values")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Story":
        if not isinstance(data, dict):
            raise SchemaError("story must be an object")
        try:
            return cls(**data).validate()
        except TypeError as exc:
            raise SchemaError(f"invalid story fields: {exc}") from exc


@dataclass
class EpisodeManifest:
    schema_version: int
    episode_id: str
    published_at: str
    status: str
    source_health: Dict[str, str]
    source_events: List[SourceEvent]
    stories: List[Story]
    noise_notes: List[str]
    narration: str
    show_notes: str
    generation: Dict[str, Any]
    audio: Dict[str, Any]

    def validate(self, *, require_audio: bool | None = None) -> "EpisodeManifest":
        if self.schema_version != 1:
            raise SchemaError("unsupported manifest schema_version")
        _text(self.episode_id, "episode_id", limit=200)
        _timestamp(self.published_at, "published_at")
        if self.status not in {"draft", "ready", "candidate", "published", "quiet"}:
            raise SchemaError("unsupported manifest status")
        if not isinstance(self.source_health, dict) or not self.source_health:
            raise SchemaError("source_health must be a non-empty object")
        if len(self.stories) > 7:
            raise SchemaError("an episode may contain at most seven stories")
        for event in self.source_events:
            event.validate()
        for story in self.stories:
            story.validate()
        event_ids = {event.event_id for event in self.source_events}
        if len(event_ids) != len(self.source_events):
            raise SchemaError("source event IDs must be unique")
        story_ids = {story.story_id for story in self.stories}
        if len(story_ids) != len(self.stories):
            raise SchemaError("story IDs must be unique")
        events_by_id = {event.event_id: event for event in self.source_events}
        for story in self.stories:
            if not set(story.event_ids).issubset(event_ids):
                raise SchemaError("story references an unknown source event")
            referenced = [events_by_id[event_id] for event_id in story.event_ids]
            if not any(event.authority == "primary" for event in referenced):
                raise SchemaError("every story requires a primary source")
            expected_urls = []
            for event in referenced:
                expected_urls.append(event.url)
                corroboration = event.metadata.get("corroboration_urls", [])
                if not isinstance(corroboration, list):
                    raise SchemaError("corroboration_urls must be a list")
                expected_urls.extend(corroboration)
            expected_urls = list(dict.fromkeys(expected_urls))
            if story.source_urls != expected_urls:
                raise SchemaError("story source URLs must match referenced evidence")
        if not isinstance(self.noise_notes, list) or not all(isinstance(x, str) for x in self.noise_notes):
            raise SchemaError("noise_notes must be a string list")
        narration = _text(self.narration, "narration", limit=16000)
        if len(narration.split()) > 1500:
            raise SchemaError("narration exceeds the ten-minute word budget")
        _text(self.show_notes, "show_notes", limit=24000)
        if not isinstance(self.generation, dict) or not isinstance(self.audio, dict):
            raise SchemaError("generation and audio must be objects")
        if require_audio is None:
            require_audio = self.status in {"ready", "published"}
        if require_audio:
            _https_url(self.audio.get("url"), "audio.url")
            if int(self.audio.get("size_bytes", 0)) <= 0:
                raise SchemaError("audio size must be positive")
            if float(self.audio.get("duration_secs", 0)) <= 0:
                raise SchemaError("audio duration must be positive")
            _text(self.audio.get("sha256", ""), "audio.sha256", limit=128)
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate(require_audio=False)
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodeManifest":
        if not isinstance(data, dict):
            raise SchemaError("manifest must be an object")
        try:
            values = dict(data)
            values["source_events"] = [SourceEvent.from_dict(x) for x in data.get("source_events", [])]
            values["stories"] = [Story.from_dict(x) for x in data.get("stories", [])]
            return cls(**values).validate(require_audio=False)
        except TypeError as exc:
            raise SchemaError(f"invalid manifest fields: {exc}") from exc
