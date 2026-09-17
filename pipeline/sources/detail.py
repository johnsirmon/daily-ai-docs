"""Opt-in official detail retrieval with explicit public-network boundaries.

Enrichment config: enabled (default false), allowed_hosts (exact hostnames),
max_requests (default 3, maximum 5), min_chars (default 180), and
max_response_bytes (default 1 MiB, maximum 2 MiB). Redirects consume requests.
The collectors additionally cap all enrichment requests at ten per invocation.
"""

from __future__ import annotations

import html
import http.client
import ipaddress
import re
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from .text import article_text, bounded_text, clean_source_text


DEFAULT_DETAIL_HOSTS = frozenset({"github.com", "code.visualstudio.com", "github.blog"})
_HEADERS = {"User-Agent": "daily-ai-docs/1.0", "Accept": "text/html, application/atom+xml"}


class DetailError(ValueError):
    """A bounded public source could not be safely retrieved or used."""


@dataclass
class RequestBudget:
    remaining: int

    def consume(self) -> None:
        if self.remaining <= 0:
            raise DetailError("request_limit")
        self.remaining -= 1


def bounded_int(config: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    value = config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise DetailError(f"invalid_{key}")
    return value


def allowed_hosts(value: object) -> frozenset[str]:
    if not isinstance(value, (list, tuple, set, frozenset)) or not value:
        raise DetailError("invalid_allowed_hosts")
    hosts = set()
    for host in value:
        if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", host):
            raise DetailError("invalid_allowed_hosts")
        hosts.add(host.lower())
    return frozenset(hosts)


def validate_public_url(url: str, hosts: frozenset[str]) -> tuple[str, list[str]]:
    if len(url) > 2048 or re.search(r"[\x00-\x20\x7f\\]", url):
        raise DetailError("invalid_url")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https" or host not in hosts
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in {None, 443}
        ):
            raise DetailError("disallowed_url")
        addresses = list(dict.fromkeys(
            answer[4][0] for answer in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ))
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise DetailError("non_public_address")
    except (OSError, ValueError) as exc:
        if isinstance(exc, DetailError):
            raise
        raise DetailError("invalid_destination") from exc
    return urlunsplit(("https", parsed.netloc, parsed.path or "/", parsed.query, "")), addresses


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect only to an already-validated IP, verifying TLS against the host."""

    def __init__(self, host: str, address: str):
        super().__init__(host, timeout=20, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        sock = socket.create_connection((self.address, 443), timeout=5)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
            self.sock.settimeout(20)
        except (OSError, ValueError):
            sock.close()
            raise


def fetch_public(
    url: str,
    *,
    hosts: frozenset[str],
    budget: RequestBudget,
    max_bytes: int = 1024 * 1024,
    max_redirects: int = 2,
    session=None,
    shared_budget: RequestBudget | None = None,
) -> tuple[str, str, str]:
    """Return UTF-8 source, final URL and media type; never forward credentials.

    Real sessions are intentionally not reused: GitHub sessions may hold tokens,
    cookies, netrc auth, or proxy credentials. The stdlib transport pins validated
    DNS results and does not inherit any of those. Non-Session test doubles expose
    get/iter_content/close for network-free adapter tests.
    """
    deadline = time.monotonic() + 60
    for redirect in range(max_redirects + 1):
        if time.monotonic() >= deadline:
            raise DetailError("fetch_deadline")
        if budget.remaining <= 0 or (shared_budget is not None and shared_budget.remaining <= 0):
            raise DetailError("request_limit")
        current, addresses = validate_public_url(url, hosts)
        budget.consume()
        if shared_budget is not None:
            shared_budget.consume()
        connection = None
        response = None
        try:
            if session is not None and not isinstance(session, requests.Session):
                response = session.get(
                    current, headers=dict(_HEADERS), timeout=(5, 20),
                    allow_redirects=False, stream=True,
                )
                status = response.status_code
                headers = {key.lower(): value for key, value in response.headers.items()}
            else:
                parsed = urlsplit(current)
                connection = _PinnedHTTPSConnection(parsed.hostname, addresses[0])
                path = urlunsplit(("", "", parsed.path, parsed.query, ""))
                connection.request("GET", path, headers=_HEADERS)
                response = connection.getresponse()
                status = response.status
                headers = {key.lower(): value for key, value in response.getheaders()}
            if status in {301, 302, 303, 307, 308}:
                if redirect == max_redirects:
                    raise DetailError("redirect_limit")
                location = headers.get("location")
                if not location:
                    raise DetailError("missing_redirect_location")
                url = urljoin(current, location)
                continue
            if status != 200:
                raise DetailError(f"http_{status}")
            if headers.get("content-encoding", "identity").lower() != "identity":
                raise DetailError("unsupported_content_encoding")
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type not in {"text/html", "application/xhtml+xml", "application/atom+xml", "application/xml", "text/xml"}:
                raise DetailError("unsupported_content_type")
            length = headers.get("content-length")
            if length is not None:
                try:
                    if int(length) < 0 or int(length) > max_bytes:
                        raise DetailError("response_too_large")
                except ValueError as exc:
                    if isinstance(exc, DetailError):
                        raise
                    raise DetailError("invalid_content_length") from exc
            chunks = []
            size = 0
            if connection is None:
                iterator = response.iter_content(chunk_size=8192)
            else:
                iterator = iter(lambda: response.read(8192), b"")
            for chunk in iterator:
                if time.monotonic() >= deadline:
                    raise DetailError("fetch_deadline")
                size += len(chunk)
                if size > max_bytes:
                    raise DetailError("response_too_large")
                chunks.append(chunk)
            try:
                return b"".join(chunks).decode("utf-8-sig"), current, content_type
            except UnicodeDecodeError as exc:
                raise DetailError("invalid_utf8") from exc
        except (requests.RequestException, OSError, http.client.HTTPException) as exc:
            raise DetailError(f"fetch_{type(exc).__name__}") from exc
        finally:
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()
    raise DetailError("redirect_limit")


class DetailEnricher:
    def __init__(self, config: dict, *, session=None, shared_budget: RequestBudget):
        self.enabled = config.get("enabled") is True
        self.session = session
        self.shared_budget = shared_budget
        self.hosts = allowed_hosts(config.get("allowed_hosts", DEFAULT_DETAIL_HOSTS))
        self.budget = RequestBudget(bounded_int(config, "max_requests", 3, 1, 5))
        self.min_chars = bounded_int(config, "min_chars", 180, 40, 1000)
        self.max_bytes = bounded_int(config, "max_response_bytes", 1024 * 1024, 1024, 2 * 1024 * 1024)

    def enrich(self, raw: str, url: str, *, prefer_body_url: bool = False) -> tuple[str, dict, str | None]:
        text = clean_source_text(raw)
        if not self.enabled:
            return text, {}, None
        without_urls = re.sub(r"https?://\S+", "", text).strip()
        excerpt = bool(re.search(r"(?i)(?:read (?:the )?(?:full|more)|continue reading|\.\.\.|\u2026)", html.unescape(raw)))
        if len(without_urls) >= self.min_chars and not excerpt:
            return text, {}, None
        target = url
        if prefer_body_url:
            links = re.findall(r'https://[^\s<>"\')]+', html.unescape(raw))
            for link in links:
                candidate = link.rstrip(".,;")
                try:
                    if urlsplit(candidate).hostname in self.hosts:
                        target = candidate
                        break
                except ValueError:
                    continue
        try:
            body, final_url, content_type = fetch_public(
                target, hosts=self.hosts, budget=self.budget, max_bytes=self.max_bytes,
                session=self.session, shared_budget=self.shared_budget,
            )
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise DetailError("not_article_html")
            detail = article_text(body)
            if len(detail) < self.min_chars or re.search(
                r"(?i)(?:captcha|access denied|verify (?:that )?you are human|"
                r"sign in to (?:read|continue)|enable javascript and cookies)", detail[:1000]
            ):
                raise DetailError("insufficient_article")
            metadata = {"detail_url": final_url, "evidence_status": "article_text"}
            if final_url != url:
                metadata["corroboration_urls"] = [final_url]
            return bounded_text(detail), metadata, None
        except DetailError as exc:
            return text, {"evidence_status": "summary_only", "detail_error": str(exc)}, str(exc)
