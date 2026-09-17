"""Collect stable public releases from explicitly curated GitHub repositories."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List

import requests

from ..github_api import GITHUB_API, build_github_headers
from ..schema import SourceEvent
from .detail import DetailEnricher, RequestBudget
from .text import clean_source_text


def _iso(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _evidence(body: str, fallback: str) -> str:
    return clean_source_text(body or "") or fallback.strip()


def collect_github_releases(
    sources: Iterable[Dict],
    *,
    lookback_hours: int = 36,
    session: requests.Session | None = None,
    now: datetime | None = None,
) -> tuple[List[SourceEvent], Dict[str, str]]:
    """Collect public releases; each source may opt into bounded ``enrichment``."""
    session = session or requests.Session()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=lookback_hours)
    fetched_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    headers = build_github_headers()
    events: List[SourceEvent] = []
    health: Dict[str, str] = {}
    detail_budget = RequestBudget(10)

    for config in sources:
        repo = str(config["repo"])
        source_key = f"github:{repo}"
        try:
            enricher = DetailEnricher(
                config.get("enrichment") or {}, session=session, shared_budget=detail_budget,
            )
            meta_resp = session.get(f"{GITHUB_API}/repos/{repo}", headers=headers, timeout=15)
            meta_resp.raise_for_status()
            meta = meta_resp.json()
            if meta.get("private") is True or meta.get("visibility", "public") != "public":
                health[source_key] = "rejected_private"
                continue

            response = session.get(
                f"{GITHUB_API}/repos/{repo}/releases?per_page=20",
                headers=headers,
                timeout=20,
            )
            response.raise_for_status()
            accepted = 0
            detail_failures = 0
            for release in response.json():
                if release.get("draft"):
                    continue
                published_raw = release.get("published_at") or release.get("created_at")
                if not published_raw:
                    continue
                published = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                if published < cutoff or published > now:
                    continue
                url = str(release.get("html_url") or "")
                version = str(release.get("tag_name") or release.get("name") or "release")
                title = f"{config.get('product', repo)} {version}"
                digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
                body = str(release.get("body") or "")
                evidence, detail_metadata, detail_error = enricher.enrich(body, url, prefer_body_url=True)
                if detail_error:
                    health[f"{source_key}:detail:{digest}"] = f"error:{detail_error}"
                    detail_failures += 1
                event = SourceEvent(
                    event_id=f"ghrel:{digest}",
                    source_type="github_release",
                    title=title,
                    url=url,
                    product=str(config.get("product") or repo),
                    topic=str(config.get("topic") or "AI developer tools"),
                    published_at=_iso(published_raw),
                    fetched_at=fetched_at,
                    evidence=evidence or _evidence("", f"Published {version}."),
                    authority="primary",
                    channel="prerelease" if release.get("prerelease") else "stable",
                    metadata={
                        "repo": repo,
                        "version": version,
                        "priority": int(config.get("priority", 10)),
                        "stars": int(meta.get("stargazers_count") or 0),
                        "private": False,
                        "draft": False,
                        "evidence_status": "release_body" if evidence else "insufficient",
                        **detail_metadata,
                    },
                ).validate()
                events.append(event)
                accepted += 1
            health[source_key] = f"{'degraded' if detail_failures else 'ok'}:{accepted}"
        except Exception as exc:  # network health is data, not a fabricated quiet day
            health[source_key] = f"error:{type(exc).__name__}"

    return events, health
