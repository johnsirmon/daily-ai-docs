"""Discover recent first-party arXiv preprints with bounded actual HTML text.

Disabled unless enabled is exactly true. Config defaults: lookback_days=30,
max_results=5, max_papers=3, max_full_text_chars=60000, and three developer-tool
queries. One API request discovers at most max_results candidates; at most
max_papers full-text candidates are attempted, with two redirects per request.
Only first publication in the window qualifies: a later version is not evidence
of a substantive revision. Full-text collection does not constitute peer review.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List
from urllib.parse import urlencode, urlsplit

from ..schema import SourceEvent
from .detail import DetailError, RequestBudget, bounded_int, fetch_public
from .text import arxiv_full_text, bounded_text, clean_source_text


_ATOM = "{http://www.w3.org/2005/Atom}"
_DEFAULT_QUERIES = ["coding agents", "evaluation", "developer workflow"]
_PAPER_ID = re.compile(r"(?P<base>(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7}))(?:v(?P<version>[1-9]\d{0,3}))?")


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("paper_timestamp_without_timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _identity(value: str) -> tuple[str, int]:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"} or parsed.hostname != "arxiv.org"
        or parsed.username is not None or parsed.password is not None
        or parsed.port is not None or parsed.query or parsed.fragment
        or not parsed.path.startswith("/abs/")
    ):
        raise ValueError("invalid_paper_id")
    match = _PAPER_ID.fullmatch(parsed.path.removeprefix("/abs/"))
    if not match:
        raise ValueError("invalid_paper_id")
    # API entries normally carry an explicit version. Do not guess one otherwise.
    if match["version"] is None:
        raise ValueError("missing_paper_version")
    return match["base"], int(match["version"])


def _value(entry: ET.Element, name: str) -> str:
    child = entry.find(f"{_ATOM}{name}")
    return "".join(child.itertext()).strip() if child is not None else ""


def collect_research_papers(
    config: dict,
    *,
    covered_paper_ids: Iterable[str] = (),
    session=None,
    now: datetime | None = None,
    max_lookback_days: int = 30,
) -> tuple[List[SourceEvent], Dict[str, str]]:
    """Return unreviewed full-text candidates and explicit discovery/rejection health."""
    if config.get("enabled") is not True:
        return [], {}
    key = "research:arxiv"
    events: List[SourceEvent] = []
    health: Dict[str, str] = {}
    covered = set(covered_paper_ids)
    try:
        if type(max_lookback_days) is not int or max_lookback_days not in {30, 365}:
            raise DetailError("invalid_lookback_policy")
        days = bounded_int(config, "lookback_days", 30, 1, max_lookback_days)
        max_results = bounded_int(config, "max_results", 5, 1, 20)
        max_papers = bounded_int(config, "max_papers", 3, 1, 5)
        max_chars = bounded_int(config, "max_full_text_chars", 60000, 1000, 60000)
        queries = config.get("queries", _DEFAULT_QUERIES)
        if (
            not isinstance(queries, list) or not 1 <= len(queries) <= 8
            or any(not isinstance(query, str) or not query.strip() or len(query) > 150 for query in queries)
        ):
            raise DetailError("invalid_queries")
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        cutoff = now - timedelta(days=days)
        terms = []
        for query in queries:
            # Queries are literal topic phrases, not arbitrary arXiv query syntax.
            if any(character in query for character in ['"', "\\", "\n", "\r"]):
                raise DetailError("invalid_queries")
            terms.append(f'all:"{query.strip()}"')
        search = (
            f"({' OR '.join(terms)}) AND "
            f"submittedDate:[{cutoff:%Y%m%d%H%M} TO {now:%Y%m%d%H%M}]"
        )
        api_url = "https://export.arxiv.org/api/query?" + urlencode({
            "search_query": search, "start": 0, "max_results": max_results,
            "sortBy": "submittedDate", "sortOrder": "descending",
        })
        budget = RequestBudget(3 * (1 + max_papers))
        payload, _, media_type = fetch_public(
            api_url, hosts=frozenset({"export.arxiv.org", "arxiv.org"}),
            budget=budget, session=session,
        )
        if media_type not in {"application/atom+xml", "application/xml", "text/xml"}:
            raise DetailError("not_atom")
        root = ET.fromstring(payload)
        if root.tag != f"{_ATOM}feed":
            raise DetailError("not_atom")
        attempted = 0
        seen = set()
        rejected = 0
        for index, entry in enumerate(root.findall(f"{_ATOM}entry")[:max_results]):
            candidate_key = f"{key}:candidate:{index}"
            try:
                paper_id, version = _identity(_value(entry, "id"))
                candidate_key = f"{key}:{paper_id}"
                if paper_id in seen:
                    continue
                seen.add(paper_id)
                published = _timestamp(_value(entry, "published"))
                updated = _timestamp(_value(entry, "updated"))
                if published > now or updated > now or updated < published:
                    raise ValueError("invalid_paper_dates")
                if published < cutoff:
                    health[candidate_key] = "rejected:outside_first_publication_window"
                    continue
                if paper_id in covered:
                    health[candidate_key] = "not_fetched:already_covered"
                    continue
                if attempted >= max_papers:
                    health[candidate_key] = "not_fetched:candidate_limit"
                    continue
                attempted += 1
                title = clean_source_text(_value(entry, "title"), limit=500)
                authors = [
                    clean_source_text(_value(author, "name"), limit=200)
                    for author in entry.findall(f"{_ATOM}author")
                ]
                if not title or not authors or not all(authors):
                    raise ValueError("missing_paper_metadata")
                identity = f"{paper_id}v{version}"
                html_url = f"https://arxiv.org/html/{identity}"
                body, final_url, media_type = fetch_public(
                    html_url, hosts=frozenset({"arxiv.org"}), budget=budget,
                    max_bytes=2 * 1024 * 1024, session=session,
                )
                if (
                    media_type not in {"text/html", "application/xhtml+xml"}
                    or urlsplit(final_url).path.rstrip("/") != f"/html/{identity}"
                    or urlsplit(final_url).query
                ):
                    raise DetailError("not_paper_html")
                full_text = arxiv_full_text(body, max_chars=max_chars)
                events.append(SourceEvent(
                    event_id=f"arxiv:{paper_id}",
                    source_type="research_paper",
                    title=title,
                    url=f"https://arxiv.org/abs/{identity}",
                    product="arXiv research",
                    topic="AI developer research",
                    published_at=_iso(published),
                    fetched_at=_iso(now),
                    evidence=bounded_text(full_text),
                    authority="primary",
                    channel="announcement",
                    metadata={
                        "paper_id": paper_id,
                        "version": version,
                        "first_published_at": _iso(published),
                        "updated_at": _iso(updated),
                        "authors": authors,
                        "full_text": full_text,
                        "full_text_available": True,
                        "review_status": "unreviewed",
                        "evidence_status": "full_text",
                        "claim_origin": "author_reported_preprint",
                        "independently_reproduced": False,
                        "corroboration_urls": [final_url],
                        "priority": int(config.get("priority", 16)),
                    },
                ).validate())
                health[candidate_key] = "ok:full_text_unreviewed"
            except (ValueError, TypeError, KeyError) as exc:
                rejected += 1
                health[candidate_key] = f"rejected:{exc}"
        health[key] = f"{'degraded' if rejected else 'ok'}:{len(events)}"
    except (ValueError, TypeError, KeyError, ET.ParseError) as exc:
        health[key] = f"error:{exc}"
    return events, health
