"""Validate and import a reviewed offline Forward Observer evidence packet."""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from ..schema import SourceEvent
from .detail import DetailError, allowed_hosts, validate_public_url
from .text import article_text, clean_source_text

MAX_PACKET_BYTES = 256 * 1024
MAX_SOURCE_BYTES = 1024 * 1024
MAX_TEXT_CHARS = 8192
MAX_FINDINGS = 3
MAX_SOURCES = 9
MAX_REDIRECTS = 3
REQUEST_TIMEOUT_SECONDS = 10
PACKET_MAX_AGE = timedelta(hours=48)
ORDINARY_LOOKBACK = timedelta(hours=36)

_PACKET_FIELDS = {
    "schema_version", "generated_at", "cutoff_at", "status", "coverage", "findings", "noise_notes",
}
_COVERAGE_FIELDS = {"source", "status", "detail"}
_FINDING_FIELDS = {
    "finding_id", "product", "topic", "what_changed", "developer_consequence", "applicability",
    "suggested_action", "caveats", "confidence", "claim_type", "novelty_basis", "sources",
}
_SOURCE_FIELDS = {
    "url", "title", "published_at", "retrieved_at", "supporting_excerpt", "content_sha256",
}
_PACKET_STATUS = {"ok", "no_material_change", "degraded", "error"}
_COVERAGE_STATUS = {"ok", "error", "degraded", "incomplete", "no_qualifying_change_found"}
_CONFIDENCE = {"high", "medium", "low"}
_CLAIM_TYPE = {"documented_fact", "maintainer_claim", "practitioner_observation", "inference"}
_REDIRECTS = {301, 302, 303, 307, 308}
_INJECTION = re.compile(
    r"\b(?:ignore|disregard|override|forget)\s+(?:(?:all|any)\s+)?(?:the\s+)?"
    r"(?:previous|prior|system|developer)\s+instructions?\b|"
    r"\b(?:system|developer|assistant)\s+prompt\s*:|\bdo\s+not\s+read\s+this\s+aloud\b",
    re.IGNORECASE,
)
_PRIVATE = re.compile(
    r"(?:^|[^\w/])(?:/home/|/Users/|[A-Za-z]:\\\\|~/(?:\S+))|"
    r"\b(?:api[_ -]?key|access[_ -]?token|authorization|cookie|session[_ -]?token)\s*[:=]\s*\S+|"
    r"https://[^\s/@]+:[^\s/@]+@",
    re.IGNORECASE,
)


class ObserverError(ValueError):
    """Observer input failed a bounded validation or retrieval requirement."""


@dataclass(frozen=True)
class ObserverDiagnostics:
    attempts: int
    redirects: int
    bytes_fetched: int


class _UniqueObject(dict):
    pass


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str):
        context = ssl.create_default_context()
        super().__init__(host, timeout=REQUEST_TIMEOUT_SECONDS, context=context)
        self._address = address
        self._tls_context = context

    def connect(self) -> None:
        sock = socket.create_connection((self._address, 443), timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            self.sock = self._tls_context.wrap_socket(sock, server_hostname=self.host)
            self.sock.settimeout(REQUEST_TIMEOUT_SECONDS)
        except (OSError, ValueError):
            sock.close()
            raise


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = _UniqueObject()
    for key, value in pairs:
        if key in result:
            raise ObserverError("observer packet contains duplicate JSON keys")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> None:
    raise ObserverError("observer packet contains a non-finite number")


def _exact(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ObserverError(f"{name} has missing or unknown fields")
    return value


def _text(value: Any, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ObserverError(f"{name} must be a string")
    value = value.strip()
    if (not allow_empty and not value) or len(value) > MAX_TEXT_CHARS:
        raise ObserverError(f"{name} is empty or exceeds {MAX_TEXT_CHARS} characters")
    if _INJECTION.search(value):
        raise ObserverError(f"{name} contains an instruction-like directive")
    if _PRIVATE.search(value):
        raise ObserverError(f"{name} contains private or credential-bearing data")
    return value


def _timestamp(value: Any, name: str) -> datetime:
    text = _text(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObserverError(f"{name} must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise ObserverError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _read_packet(path_value: Any) -> dict[str, Any]:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ObserverError("observer packet_path must be an explicit local path")
    path = Path(path_value).expanduser()
    if path.is_symlink():
        raise ObserverError("observer packet_path must not be a symlink")
    try:
        stat = path.stat()
    except OSError as exc:
        raise ObserverError("observer packet is unavailable") from exc
    if not path.is_file() or stat.st_size > MAX_PACKET_BYTES:
        raise ObserverError("observer packet must be a regular file no larger than 256 KiB")
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_PACKET_BYTES:
            raise ObserverError("observer packet exceeds 256 KiB")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObserverError("observer packet is not valid UTF-8 JSON") from exc
    return _exact(value, _PACKET_FIELDS, "observer packet")


def _response_bytes(response: Any) -> bytes:
    chunks = []
    size = 0
    for chunk in response.iter_content(chunk_size=8192):
        if not isinstance(chunk, (bytes, bytearray)):
            raise ObserverError("observer source returned a non-byte response")
        size += len(chunk)
        if size > MAX_SOURCE_BYTES:
            raise ObserverError("observer source exceeds 1 MiB")
        chunks.append(bytes(chunk))
    return b"".join(chunks)


def _fetch_source(url: str, hosts: frozenset[str], *, session: Any = None) -> tuple[bytes, str, int, int]:
    current = url
    attempts = 0
    redirects = 0
    for redirect in range(MAX_REDIRECTS + 1):
        try:
            safe_url, addresses = validate_public_url(current, hosts)
        except DetailError as exc:
            raise ObserverError(f"observer source URL rejected: {exc}") from exc
        attempts += 1
        response = None
        connection = None
        try:
            if session is not None and not isinstance(session, requests.Session):
                response = session.get(
                    safe_url,
                    headers={"User-Agent": "daily-ai-docs/1.0", "Accept": "text/html, application/xhtml+xml"},
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    allow_redirects=False,
                    stream=True,
                )
                status = response.status_code
                headers = {key.lower(): value for key, value in response.headers.items()}
            else:
                parsed = urlsplit(safe_url)
                host = parsed.hostname
                if host is None:
                    raise ObserverError("observer source URL has no hostname")
                connection = _PinnedHTTPSConnection(host, addresses[0])
                target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
                connection.request("GET", target, headers={
                    "Host": host, "User-Agent": "daily-ai-docs/1.0",
                    "Accept": "text/html, application/xhtml+xml",
                })
                response = connection.getresponse()
                status = response.status
                headers = {key.lower(): value for key, value in response.getheaders()}
            if status in _REDIRECTS:
                if redirect == MAX_REDIRECTS:
                    raise ObserverError("observer source redirect limit exceeded")
                location = headers.get("location")
                if not location:
                    raise ObserverError("observer source redirect is missing a location")
                current = urljoin(safe_url, location)
                redirects += 1
                continue
            if status != 200:
                raise ObserverError(f"observer source returned HTTP {status}")
            if headers.get("content-encoding", "identity").lower() != "identity":
                raise ObserverError("observer source content encoding is unsupported")
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                raise ObserverError("observer source content type is unsupported")
            length = headers.get("content-length")
            if length is not None:
                try:
                    if type(int(length)) is not int or not 0 <= int(length) <= MAX_SOURCE_BYTES:
                        raise ObserverError("observer source exceeds 1 MiB")
                except ValueError as exc:
                    raise ObserverError("observer source has invalid content length") from exc
            if connection is None:
                body = _response_bytes(response)
            else:
                chunks = []
                size = 0
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_SOURCE_BYTES:
                        raise ObserverError("observer source exceeds 1 MiB")
                    chunks.append(chunk)
                body = b"".join(chunks)
            return body, safe_url, attempts, redirects
        except ObserverError:
            raise
        except (OSError, http.client.HTTPException, requests.RequestException) as exc:
            raise ObserverError(f"observer source fetch failed ({type(exc).__name__})") from exc
        finally:
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()
    raise ObserverError("observer source redirect limit exceeded")


def _excerpt_segments(excerpt: str) -> list[str]:
    return [segment for segment in (
        " ".join(part.split()) for part in re.split(r"(?:\.\.\.|\u2026)", excerpt)
    ) if segment]


def _excerpt_supported(excerpt: str, body: bytes) -> bool:
    try:
        decoded = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ObserverError("observer source is not valid UTF-8") from exc
    visible = article_text(decoded) or clean_source_text(decoded, limit=MAX_SOURCE_BYTES)
    haystacks = [" ".join(decoded.split()).casefold(), " ".join(visible.split()).casefold()]
    # Ellipses are omission markers. Every nonempty contiguous segment must independently occur.
    segments = [segment.casefold() for segment in _excerpt_segments(excerpt)]
    return bool(segments) and all(any(segment in haystack for haystack in haystacks) for segment in segments)


def _validate_config(config: Any) -> tuple[str, Any, frozenset[str]]:
    if config is None:
        config = {"mode": "off", "packet_path": None, "allowed_hosts": []}
    config = _exact(config, {"mode", "packet_path", "allowed_hosts"}, "daily.observer")
    mode = config["mode"]
    if not isinstance(mode, str) or mode not in {"off", "optional", "required"}:
        raise ObserverError("daily.observer.mode must be off, optional, or required")
    packet_path = config["packet_path"]
    if packet_path is not None and not isinstance(packet_path, str):
        raise ObserverError("daily.observer.packet_path must be null or a string")
    raw_hosts = config["allowed_hosts"]
    if not isinstance(raw_hosts, list) or not all(isinstance(host, str) for host in raw_hosts):
        raise ObserverError("daily.observer.allowed_hosts must be a string list")
    hosts = frozenset() if not raw_hosts else allowed_hosts(raw_hosts)
    return mode, packet_path, hosts


def collect_observer_packet(
    config: Any,
    *,
    now: datetime | None = None,
    session: Any = None,
) -> tuple[list[SourceEvent], dict[str, str]]:
    """Return validated SourceEvents and explicit Observer health diagnostics.

    Optional mode reports failures as supplementary health and returns no unvalidated
    event. Required mode raises so the publication state machine fails closed.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        mode, packet_path, hosts = _validate_config(config)
        if mode == "off":
            return [], {}
        if packet_path is None or not hosts:
            raise ObserverError("observer packet_path and allowed_hosts are required when enabled")
        packet = _read_packet(packet_path)
        if type(packet["schema_version"]) is not int or packet["schema_version"] != 1:
            raise ObserverError("observer schema_version must be integer 1")
        generated = _timestamp(packet["generated_at"], "generated_at")
        cutoff = _timestamp(packet["cutoff_at"], "cutoff_at")
        if generated > now or cutoff > generated or now - generated > PACKET_MAX_AGE:
            raise ObserverError("observer packet is stale or has invalid future/order timestamps")
        status = packet["status"]
        if not isinstance(status, str) or status not in _PACKET_STATUS:
            raise ObserverError("observer packet status is invalid")
        coverage = packet["coverage"]
        if not isinstance(coverage, list):
            raise ObserverError("observer coverage must be a list")
        coverage_states = []
        for index, row in enumerate(coverage):
            row = _exact(row, _COVERAGE_FIELDS, f"coverage[{index}]")
            _text(row["source"], f"coverage[{index}].source")
            detail = _text(row["detail"], f"coverage[{index}].detail", allow_empty=True)
            state = row["status"]
            if not isinstance(state, str) or state not in _COVERAGE_STATUS:
                raise ObserverError("observer coverage status is invalid")
            coverage_states.append(state)
            _ = detail
        findings = packet["findings"]
        if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
            raise ObserverError("observer findings must contain at most three entries")
        notes = packet["noise_notes"]
        if not isinstance(notes, list):
            raise ObserverError("observer noise_notes must be a list")
        notes = [_text(note, f"noise_notes[{index}]") for index, note in enumerate(notes)]
        unhealthy = any(state in {"error", "degraded", "incomplete"} for state in coverage_states)
        if status == "ok" and unhealthy:
            raise ObserverError("observer status ok cannot hide incomplete coverage")
        if status == "no_material_change" and (findings or unhealthy):
            raise ObserverError("observer no_material_change requires empty findings and healthy coverage")
        if status == "error" and findings:
            raise ObserverError("observer error packets cannot supply eligible findings")
        if mode == "required" and (status in {"degraded", "error"} or unhealthy):
            raise ObserverError("required observer coverage is degraded or incomplete")

        source_rows: dict[str, tuple[bytes, str, int, int]] = {}
        finding_ids: set[str] = set()
        events: list[SourceEvent] = []
        total_attempts = total_redirects = total_bytes = 0
        for index, finding in enumerate(findings):
            finding = _exact(finding, _FINDING_FIELDS, f"findings[{index}]")
            finding_id = _text(finding["finding_id"], f"findings[{index}].finding_id")
            if finding_id in finding_ids:
                raise ObserverError("observer finding IDs must be unique")
            finding_ids.add(finding_id)
            values = {
                name: _text(finding[name], f"findings[{index}].{name}")
                for name in _FINDING_FIELDS - {"sources"}
            }
            if values["confidence"] not in _CONFIDENCE or values["claim_type"] not in _CLAIM_TYPE:
                raise ObserverError("observer finding enum value is invalid")
            sources = finding["sources"]
            if not isinstance(sources, list) or not 1 <= len(sources) <= 3:
                raise ObserverError("observer findings require one to three sources")
            source_urls = []
            source_hashes = []
            evidence_segments = []
            publication_times = []
            for source_index, source in enumerate(sources):
                source = _exact(source, _SOURCE_FIELDS, f"finding source {source_index}")
                url = _text(source["url"], "source.url")
                title = _text(source["title"], "source.title")
                excerpt = _text(source["supporting_excerpt"], "source.supporting_excerpt")
                digest = _text(source["content_sha256"], "source.content_sha256")
                if not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise ObserverError("observer source content_sha256 is invalid")
                retrieved = _timestamp(source["retrieved_at"], "source.retrieved_at")
                if retrieved > generated:
                    raise ObserverError("observer source retrieved_at is after generated_at")
                if source["published_at"] is None:
                    raise ObserverError("observer source with unknown published_at is ineligible")
                published = _timestamp(source["published_at"], "source.published_at")
                if published > cutoff or published < cutoff - ORDINARY_LOOKBACK:
                    raise ObserverError("observer source is outside the ordinary 36-hour window")
                if url not in source_rows:
                    if len(source_rows) >= MAX_SOURCES:
                        raise ObserverError("observer packet exceeds nine distinct source URLs")
                    fetched = _fetch_source(url, hosts, session=session)
                    source_rows[url] = fetched
                    total_attempts += fetched[2]
                    total_redirects += fetched[3]
                    total_bytes += len(fetched[0])
                body, final_url, _attempts, _redirects = source_rows[url]
                if final_url != url:
                    # Redirect destinations are validated, but producer evidence must name exact fetched identity.
                    raise ObserverError("observer source redirected; producer evidence must use the final approved URL")
                if hashlib.sha256(body).hexdigest() != digest:
                    raise ObserverError("observer source bytes do not match content_sha256")
                if not _excerpt_supported(excerpt, body):
                    raise ObserverError("observer supporting excerpt is not present in fetched source bytes")
                _ = title
                source_urls.append(url)
                source_hashes.append(digest)
                evidence_segments.extend(_excerpt_segments(excerpt))
                publication_times.append(published)
            evidence = "\n".join(dict.fromkeys(evidence_segments))
            if not evidence or len(evidence) > MAX_TEXT_CHARS:
                raise ObserverError("observer finding excerpts exceed the SourceEvent evidence bound")
            metadata = {
                "priority": 20,
                "observer_finding_id": finding_id,
                "observer_claim_type": values["claim_type"],
                "observer_confidence": values["confidence"],
                "observer_novelty_basis": values["novelty_basis"],
                "observer_source_sha256": source_hashes,
                "observer_noise_notes": notes,
                "observer_diagnostics": {
                    "attempts": total_attempts, "redirects": total_redirects,
                    "bytes_fetched": total_bytes,
                },
                "observer_packet": {
                    "schema_version": packet["schema_version"],
                    "generated_at": packet["generated_at"],
                    "cutoff_at": packet["cutoff_at"],
                    "status": packet["status"],
                    "coverage": packet["coverage"],
                    "noise_notes": packet["noise_notes"],
                },
                "observer_finding": finding,
            }
            if len(source_urls) > 1:
                metadata["corroboration_urls"] = source_urls[1:]
            events.append(SourceEvent(
                event_id=f"observer:{finding_id}",
                source_type="announcement",
                title=f"{values['product']}: {values['topic']}",
                url=source_urls[0],
                product=values["product"],
                topic=values["topic"],
                published_at=max(publication_times).isoformat().replace("+00:00", "Z"),
                fetched_at=now.isoformat().replace("+00:00", "Z"),
                evidence=evidence,
                authority="primary",
                channel="announcement",
                metadata=metadata,
            ).validate())
        health_state = "ok" if status in {"ok", "no_material_change"} and not unhealthy else "degraded"
        return events, {"observer:packet": f"{health_state}:{len(events)}"}
    except ObserverError as exc:
        if isinstance(config, dict) and config.get("mode") == "optional":
            return [], {"observer:packet": f"degraded:{str(exc)}"}
        raise
