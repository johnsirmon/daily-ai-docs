"""Versioned, public-safe requests shared by local and issue-driven podcasts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


PROVIDERS = ("gemini-notebook-web", "edge", "kokoro", "piper")
STATUSES = (
    "queued", "researching", "awaiting-notebook", "awaiting-download", "reviewing",
    "ready", "publishing", "published", "blocked", "cancelled",
)


def utc_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be text")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timestamp requires a timezone")
    return stamp.astimezone(timezone.utc)


def content_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PodcastRequest:
    topic: str
    audience: str
    cutoff: str
    lookback_days: int = 60
    provider: str = "gemini-notebook-web"
    publish_now: bool = False
    actor: str = ""
    issue: int | None = None
    schema_version: int = 1

    def validate(self) -> "PodcastRequest":
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported request schema")
        for name, maximum in (("topic", 500), ("audience", 300)):
            text = getattr(self, name)
            if (not isinstance(text, str) or not text.strip() or len(text) > maximum
                    or any(ord(char) < 32 for char in text)):
                raise ValueError(f"invalid request {name}")
        utc_timestamp(self.cutoff)
        if type(self.lookback_days) is not int or not 1 <= self.lookback_days <= 365:
            raise ValueError("lookback_days must be between 1 and 365")
        if self.provider not in PROVIDERS:
            raise ValueError("unsupported requested audio provider")
        if type(self.publish_now) is not bool:
            raise ValueError("publish_now must be boolean")
        if not isinstance(self.actor, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", self.actor):
            raise ValueError("request actor must identify the authorizing GitHub user")
        if self.issue is not None and (type(self.issue) is not int or self.issue <= 0):
            raise ValueError("issue must be a positive integer")
        return self

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PodcastRequest":
        if not isinstance(value, dict):
            raise ValueError("request must be an object")
        try:
            return cls(**value).validate()
        except TypeError as exc:
            raise ValueError("invalid request fields") from exc

    @property
    def revision(self) -> str:
        return content_hash(self.to_dict())

    @property
    def request_id(self) -> str:
        return f"adhoc-{self.revision[:24]}"

    @property
    def episode_id(self) -> str:
        return f"adhoc-{utc_timestamp(self.cutoff):%Y-%m-%d}-{self.revision[:24]}"

    def validate_sources(self, events) -> None:
        end = utc_timestamp(self.cutoff)
        start = end - timedelta(days=self.lookback_days)
        if not events:
            raise ValueError("request has insufficient primary evidence")
        for event in events:
            published = utc_timestamp(event.published_at)
            if event.authority != "primary" or not start <= published <= end:
                raise ValueError(f"source outside primary evidence window: {event.event_id}")
            if event.source_type == "research_paper":
                first = utc_timestamp(event.metadata["first_published_at"])
                if first != published or not start <= first <= end:
                    raise ValueError("paper first publication is outside request window")


def save_request(request: PodcastRequest, root: Path = Path(".cache/adhoc")) -> Path:
    request.validate()
    directory = root / request.request_id
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "request.json"
    if target.exists():
        if json.loads(target.read_text(encoding="utf-8")) != request.to_dict():
            raise ValueError("existing request must not be overwritten")
    else:
        with target.open("x", encoding="utf-8") as output:
            json.dump(request.to_dict(), output, indent=2, ensure_ascii=False)
        record_status(directory, request, "queued")
    return target


def record_status(directory: Path, request: PodcastRequest, status: str, *, reason: str = "") -> None:
    if status not in STATUSES or len(reason) > 200:
        raise ValueError("invalid request status")
    target = directory / "status.json"
    if target.exists():
        previous = json.loads(target.read_text(encoding="utf-8"))
        if previous["request_sha256"] != request.revision:
            raise ValueError("status belongs to another request revision")
        if previous["status"] in {"published", "cancelled"} and status != previous["status"]:
            raise ValueError("terminal requests cannot be restarted")
    payload = {
        "schema_version": 1, "request_id": request.request_id, "request_sha256": request.revision,
        "status": status, "reason": reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def request_from_issue(issue: dict[str, Any]) -> PodcastRequest:
    """Parse only the structured form; issue prose is never executable instruction."""
    fields = {}
    for section in (issue.get("body") or "").split("### ")[1:]:
        heading, _, text = section.partition("\n")
        heading = heading.strip()
        if heading in fields:
            raise ValueError("duplicate request form field")
        fields[heading] = text.strip()
    if set(fields) != {"Topic", "Audience", "Evidence window (days)", "Audio provider", "Publication"}:
        raise ValueError("issue must contain exactly the podcast request fields")
    intent = fields.get("Publication", "")
    if intent not in {"Preview only", "Publish when all gates pass"}:
        raise ValueError("issue must use the podcast request form")
    try:
        days = int(fields.get("Evidence window (days)", "60"))
    except ValueError as exc:
        raise ValueError("issue evidence window must be an integer") from exc
    return PodcastRequest(
        topic=fields.get("Topic", ""), audience=fields.get("Audience", "AI developers"),
        cutoff=issue["created_at"], lookback_days=days,
        provider=fields.get("Audio provider", "gemini-notebook-web"),
        publish_now=intent == "Publish when all gates pass",
        actor=issue["user"]["login"], issue=issue["number"],
    ).validate()
