"""Build an offline, static listening companion from accepted RSS and manifests."""

from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from .disclosure import episode_metadata_disclosure
from .podcast import _parse_duration
from .podcast_metadata import load_catalog
from .schema import EpisodeManifest

_ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
_CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".test", ".invalid")
_DNS_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_CANONICAL_FEED = "https://johnsirmon.github.io/daily-ai-docs/podcast.xml"


class ListeningSiteError(ValueError):
    """Raised for invalid inputs or a safely contained build/finalization failure."""


@dataclass(frozen=True)
class FeedEpisode:
    guid: str
    title: str
    description: str
    published_at: datetime
    enclosure_url: str
    enclosure_length: int
    enclosure_type: str
    duration_seconds: int


@dataclass(frozen=True)
class SiteEpisode:
    feed: FeedEpisode
    manifest: EpisodeManifest | None
    title: str
    summary: str
    evidence_url: str | None
    filename: str
    anchor: str
    edition: str
    acceptance: str
    correction: str | None


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _public_url(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ListeningSiteError(f"{name} must be a bounded public HTTP(S) URL")
    if (not value.isascii() or any(ord(char) <= 32 or ord(char) == 127 for char in value)
            or "\\" in value):
        raise ListeningSiteError(f"{name} contains an unsafe or ambiguous character")
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError as exc:
        raise ListeningSiteError(f"{name} is invalid") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise ListeningSiteError(f"{name} must be a public HTTP(S) URL")
    expected_port = 443 if parsed.scheme == "https" else 80
    if parsed.username or parsed.password or port not in {None, expected_port}:
        raise ListeningSiteError(f"{name} must not contain credentials or a nonstandard port")
    authority = parsed.netloc.rsplit("@", 1)[-1]
    if "%" in authority or re.search(r"%(?:0[0-9A-Fa-f]|1[0-9A-Fa-f]|7[Ff])", value):
        raise ListeningSiteError(f"{name} contains an encoded authority or control character")
    host = parsed.hostname.lower()
    if host.endswith(".") or len(host) > 253 or host.endswith(_BLOCKED_SUFFIXES):
        raise ListeningSiteError(f"{name} must use a public host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        labels = host.split(".")
        if (len(labels) < 2 or not all(_DNS_LABEL.fullmatch(label) for label in labels)
                or not any(char.isalpha() for char in labels[-1])
                or any(re.fullmatch(r"0[xX][0-9A-Fa-f]*", label) for label in labels)):
            raise ListeningSiteError(f"{name} has an invalid or ambiguous host")
        return value
    if host != address.compressed:
        raise ListeningSiteError(f"{name} must use a canonical IP address")
    if not address.is_global:
        raise ListeningSiteError(f"{name} must not use a private address")
    return value


def _safe_input(path: Path, name: str, *, directory: bool = False) -> Path:
    if path.is_symlink():
        raise ListeningSiteError(f"{name} must not be a symlink")
    if directory and not path.is_dir():
        raise ListeningSiteError(f"{name} must be an existing directory")
    if not directory and not path.is_file():
        raise ListeningSiteError(f"{name} must be an existing file")
    return path.resolve()


def _duration_text(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _date_text(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    return f"{value:%B} {value.day}, {value:%Y at %H:%M UTC}"


def _parse_feed(raw: bytes) -> list[FeedEpisode]:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw:
        raise ListeningSiteError("RSS must use UTF-8 encoding")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ListeningSiteError("RSS must use UTF-8 encoding") from exc
    declaration = re.match(r"\s*<\?xml\s+[^>]*encoding=[\"']([^\"']+)[\"']", text, re.I)
    if declaration and declaration.group(1).lower() not in {"utf-8", "utf8"}:
        raise ListeningSiteError("RSS must declare UTF-8 encoding")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
        raise ListeningSiteError("RSS must not contain a DTD or entity declaration")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ListeningSiteError("RSS is not valid XML") from exc
    channel = root.find("channel") if root.tag == "rss" else None
    if channel is None:
        raise ListeningSiteError("RSS must contain a channel")
    items = channel.findall("item")
    if not items:
        raise ListeningSiteError("RSS must contain at least one episode")
    episodes: list[FeedEpisode] = []
    guids: set[str] = set()
    enclosures: set[str] = set()
    for item in items:
        guid = (item.findtext("guid") or "").strip()
        if not guid or guid in guids or len(guid) > 500:
            raise ListeningSiteError("RSS contains a missing, duplicate, or oversized GUID")
        enclosure = item.find("enclosure")
        if enclosure is None:
            raise ListeningSiteError(f"{guid}: RSS item has no enclosure")
        url = _public_url(enclosure.get("url", ""), f"{guid} enclosure")
        if url in enclosures:
            raise ListeningSiteError(f"{guid}: duplicate enclosure URL")
        try:
            length = int(enclosure.get("length", ""))
        except ValueError as exc:
            raise ListeningSiteError(f"{guid}: invalid enclosure length") from exc
        media_type = enclosure.get("type", "")
        if length <= 0 or media_type != "audio/mpeg":
            raise ListeningSiteError(f"{guid}: enclosure must be a measured audio/mpeg file")
        date_value = item.findtext("pubDate") or ""
        try:
            published_at = parsedate_to_datetime(date_value)
        except (TypeError, ValueError) as exc:
            raise ListeningSiteError(f"{guid}: invalid RSS publication date") from exc
        if published_at is None or published_at.tzinfo is None:
            raise ListeningSiteError(f"{guid}: RSS publication date must include a timezone")
        duration = _parse_duration(item.findtext(f"{{{_ITUNES_NS}}}duration"))
        if duration <= 0:
            raise ListeningSiteError(f"{guid}: RSS duration is required")
        description = item.findtext("description") or item.findtext(f"{{{_CONTENT_NS}}}encoded") or ""
        episodes.append(FeedEpisode(
            guid=guid,
            title=(item.findtext("title") or guid).strip(),
            description=description.strip(),
            published_at=published_at.astimezone(timezone.utc),
            enclosure_url=url,
            enclosure_length=length,
            enclosure_type=media_type,
            duration_seconds=duration,
        ))
        guids.add(guid)
        enclosures.add(url)
    return episodes


def _load_manifests(directory: Path) -> dict[str, EpisodeManifest]:
    manifests: dict[str, EpisodeManifest] = {}
    for path in sorted(directory.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            raise ListeningSiteError(f"manifest input must not be a symlink: {path.name}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            manifest = EpisodeManifest.from_dict(data)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ListeningSiteError(f"invalid manifest {path.name}: {exc}") from exc
        if manifest.episode_id in manifests:
            raise ListeningSiteError(f"duplicate manifest episode_id: {manifest.episode_id}")
        manifests[manifest.episode_id] = manifest
    return manifests


def _match_manifest(feed: FeedEpisode, manifest: EpisodeManifest) -> None:
    manifest.validate(require_audio=True)
    if manifest.status not in {"candidate", "published"}:
        raise ListeningSiteError(f"{feed.guid}: feed manifest is not candidate or published")
    try:
        manifest_date = datetime.fromisoformat(manifest.published_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ListeningSiteError(f"{feed.guid}: invalid manifest publication date") from exc
    audio = manifest.audio
    mismatches = []
    if manifest.episode_id != feed.guid:
        mismatches.append("GUID")
    if manifest_date.astimezone(timezone.utc).replace(microsecond=0) != feed.published_at.replace(microsecond=0):
        mismatches.append("publication date")
    if audio.get("url") != feed.enclosure_url:
        mismatches.append("enclosure URL")
    if int(audio.get("size_bytes", 0)) != feed.enclosure_length:
        mismatches.append("enclosure length")
    if feed.enclosure_type != "audio/mpeg":
        mismatches.append("enclosure type")
    if _parse_duration(audio.get("duration_secs")) != feed.duration_seconds:
        mismatches.append("duration")
    if mismatches:
        raise ListeningSiteError(f"{feed.guid}: manifest/feed mismatch: {', '.join(mismatches)}")


def _episode_identity(guid: str) -> tuple[str, str]:
    digest = hashlib.sha256(guid.encode("utf-8")).hexdigest()
    return f"episode-{digest}.html", f"episode-{digest}"


def _edition(manifest: EpisodeManifest | None, guid: str) -> str:
    if manifest is None or guid.startswith("radar-"):
        return "Archive"
    if manifest.schema_version == 4 or guid.startswith("adhoc-"):
        return "Special"
    return "Daily"


def _acceptance(manifest: EpisodeManifest | None) -> str:
    if manifest is None:
        return "Limited historical record"
    if manifest.status == "candidate":
        return "Candidate — not confirmed"
    return "Published record"


def _prepare_episodes(
    feed_episodes: Iterable[FeedEpisode],
    manifests: dict[str, EpisodeManifest],
    catalog: dict[str, dict[str, str]],
) -> tuple[list[SiteEpisode], list[str]]:
    result: list[SiteEpisode] = []
    skipped_drafts: list[str] = []
    for feed in feed_episodes:
        manifest = manifests.get(feed.guid)
        if manifest is not None and manifest.status == "draft":
            skipped_drafts.append(feed.guid)
            continue
        if manifest is not None:
            _match_manifest(feed, manifest)
        entry = catalog.get(feed.guid, {})
        title = entry.get("title", feed.title).strip() or feed.guid
        summary = entry.get("summary", feed.description).strip()
        evidence_url = entry.get("evidence_url")
        if evidence_url is not None:
            _public_url(evidence_url, f"{feed.guid} archive evidence")
        filename, anchor = _episode_identity(feed.guid)
        result.append(SiteEpisode(
            feed=feed,
            manifest=manifest,
            title=title,
            summary=summary,
            evidence_url=evidence_url,
            filename=filename,
            anchor=anchor,
            edition=_edition(manifest, feed.guid),
            acceptance=_acceptance(manifest),
            correction=(manifest.generation.get("editing") or {}).get("correction_text")
            if manifest is not None else None,
        ))
    return result, skipped_drafts


def _link(url: str, label: str | None = None) -> str:
    safe = _public_url(url, "rendered link")
    return f'<a href="{_escape(safe)}" rel="noreferrer">{_escape(label or safe)}</a>'


def _page(title: str, body: str, *, stylesheet: str = "assets/listening-site.css") -> str:
    return "\n".join([
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        "  <meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; "
        "style-src 'self'; img-src 'self'; media-src https: http:; connect-src 'none'; "
        "script-src 'none'; base-uri 'none'; form-action 'none'\">",
        f"  <title>{_escape(title)}</title>",
        f'  <link rel="stylesheet" href="{_escape(stylesheet)}">',
        "</head>",
        "<body>",
        '  <a class="skip-link" href="#content">Skip to content</a>',
        body,
        "</body>",
        "</html>",
        "",
    ])


def _index(episodes: list[SiteEpisode], skipped_drafts: list[str], artwork_name: str | None) -> str:
    rows = []
    for episode in episodes:
        correction = ""
        if episode.correction:
            correction = (
                '<p class="correction compact"><strong>Recorded correction:</strong> '
                f"{_escape(episode.correction)}</p>"
            )
        rows.append("\n".join([
            f'<li id="{episode.anchor}">',
            f'  <h2><a href="{_escape(episode.filename)}">{_escape(episode.title)}</a></h2>',
            '  <p class="meta">'
            f'<span class="badge">{_escape(episode.edition)}</span> '
            f'<span class="badge status">{_escape(episode.acceptance)}</span> '
            f'<time datetime="{episode.feed.published_at.isoformat()}">'
            f'{_escape(_date_text(episode.feed.published_at))}</time> '
            f'· {_escape(_duration_text(episode.feed.duration_seconds))}</p>',
            correction,
            '  <details><summary>Accepted episode description</summary>',
            f'    <p class="preserve-lines">{_escape(episode.summary)}</p>',
            "  </details>",
            "</li>",
        ]))
    image = (
        f'<img class="cover" src="assets/{_escape(artwork_name)}" '
        'alt="Daily AI Developer Brief cover">'
        if artwork_name else ""
    )
    draft_note = ""
    if skipped_drafts:
        draft_note = (
            f'<p class="notice">{len(skipped_drafts)} RSS-listed draft record(s) '
            "were withheld; drafts receive no page.</p>"
        )
    body = "\n".join([
        '<header class="site-header">',
        image,
        "  <div>",
        "    <p class=\"eyebrow\">Unpublished offline preview</p>",
        "    <h1>Daily AI Developer Brief listening companion</h1>",
        "    <p>Generated only from the accepted RSS record, matching manifests, "
        "and optional reviewed catalog copy. Workflow integration and production approval are deferred.</p>",
        f"    <p>{_link(_CANONICAL_FEED, 'Existing public podcast feed (subscription RSS)')}</p>",
        "  </div>",
        "</header>",
        '<main id="content">',
        '  <aside class="notice" aria-label="Preview status"><strong>Offline preview.</strong> '
        "This site is not the live Pages root and is not publication or delivery evidence.</aside>",
        draft_note,
        '  <ol class="episode-list">',
        *rows,
        "  </ol>",
        "</main>",
        "<footer><p>No JavaScript, tracking, transcript archive, or network-generated content "
        "is included.</p></footer>",
    ])
    return _page("Listening companion — offline preview", body)


def _research(story) -> str:
    review = story.editorial.get("paper_review") if isinstance(story.editorial, dict) else None
    if not isinstance(review, dict):
        return ""
    fields = (
        ("Experiment / question", "question"),
        ("Method", "method"),
        ("Author-reported result", "result"),
        ("Limitations", "limitations"),
        ("Practical takeaway", "takeaway"),
        ("Evidence status", "evidence_status"),
    )
    items = "".join(f"<dt>{_escape(label)}</dt><dd>{_escape(review.get(key, ''))}</dd>" for label, key in fields)
    return f'<section class="research"><h3>Research context</h3><dl>{items}</dl></section>'


def _story(story, index: int) -> str:
    urls = "".join(f"<li>{_link(url)}</li>" for url in story.source_urls)
    return "\n".join([
        f'<article class="story" id="story-{index}">',
        f"  <h2>{_escape(story.headline)}</h2>",
        f'  <p class="action"><strong>{_escape(story.action.upper())}</strong> — {_escape(story.rationale)}</p>',
        "  <dl>",
        f"    <dt>Accepted change</dt><dd>{_escape(story.what_changed)}</dd>",
        f"    <dt>Why it matters</dt><dd>{_escape(story.why_it_matters)}</dd>",
        "  </dl>",
        _research(story),
        "  <h3>Cited sources</h3>",
        f"  <ul>{urls}</ul>",
        "</article>",
    ])


def _episode_page(episode: SiteEpisode) -> str:
    feed = episode.feed
    manifest = episode.manifest
    correction = ""
    stories = ""
    details = ""
    if manifest is not None:
        editing = manifest.generation.get("editing")
        if isinstance(editing, dict) and editing.get("correction_text"):
            correction = "\n".join([
                '<section class="correction" aria-labelledby="recorded-correction">',
                '  <h2 id="recorded-correction">Recorded correction — hear this first</h2>',
                f"  <p>{_escape(editing['correction_text'])}</p>",
                "</section>",
            ])
        stories = "\n".join(_story(story, index) for index, story in enumerate(manifest.stories, 1))
        gaps = "".join(f"<li>{_escape(note)}</li>" for note in manifest.noise_notes)
        gaps_section = f'<section><h2>Coverage gaps and exclusions</h2><ul>{gaps}</ul></section>' if gaps else ""
        details = "\n".join([
            _source_health(manifest),
            gaps_section,
            '<section><h2>Accepted show notes</h2>',
            f'<p class="preserve-lines">{_escape(manifest.show_notes)}</p></section>',
            f'<p class="disclosure">{_escape(episode_metadata_disclosure(manifest.schema_version))}</p>',
        ])
    else:
        archive_link = (
            f"<p>Accepted archive evidence: {_link(episode.evidence_url)}</p>"
            if episode.evidence_url else ""
        )
        details = "\n".join([
            '<section class="limited"><h2>Limited historical record</h2>',
            "<p>No accepted manifest is present in this baseline. Claims and recommendations "
            "are not reconstructed.</p>",
            archive_link,
            f'<h3>Accepted archive copy</h3><p class="preserve-lines">{_escape(episode.summary)}</p></section>',
        ])
    body = "\n".join([
        '<header class="episode-header">',
        '  <p><a href="index.html">← All episodes</a></p>',
        '  <p class="eyebrow">Unpublished offline preview</p>',
        f"  <h1>{_escape(episode.title)}</h1>",
        '  <p class="meta">'
        f'<span class="badge">{_escape(episode.edition)}</span> '
        f'<span class="badge status">{_escape(episode.acceptance)}</span> '
        f'<time datetime="{feed.published_at.isoformat()}">{_escape(_date_text(feed.published_at))}</time> '
        f'· {_escape(_duration_text(feed.duration_seconds))}</p>',
        f"  <p>{_link(_CANONICAL_FEED, 'Existing public podcast feed (subscription RSS)')}</p>",
        "</header>",
        '<main id="content">',
        '<section class="player" aria-labelledby="listen-heading">',
        '  <h2 id="listen-heading">Listen</h2>',
        f'  <audio controls preload="none" src="{_escape(feed.enclosure_url)}">'
        "Your browser does not support audio playback.</audio>",
        f"  <p>{_link(feed.enclosure_url, 'Open the MP3 enclosure')}</p>",
        "</section>",
        correction,
        stories,
        '<section><h2>Accepted episode description</h2>',
        f'<p class="preserve-lines">{_escape(episode.summary)}</p></section>',
        details,
        "</main>",
        '<footer><p><a href="index.html">Return to episode list</a></p></footer>',
    ])
    return _page(f"{episode.title} — listening companion", body)


def _source_health(manifest: EpisodeManifest) -> str:
    counts = {"ok_zero": 0, "ok_updates": 0, "degraded": 0, "error": 0, "other": 0}
    for status in manifest.source_health.values():
        if re.fullmatch(r"ok:0", status):
            counts["ok_zero"] += 1
        elif re.fullmatch(r"ok:[1-9]\d*", status):
            counts["ok_updates"] += 1
        elif status.startswith("degraded:"):
            counts["degraded"] += 1
        elif status.startswith("error:"):
            counts["error"] += 1
        else:
            counts["other"] += 1
    rows = (
        ("Healthy, no updates", counts["ok_zero"]),
        ("Healthy, updates found", counts["ok_updates"]),
        ("Degraded", counts["degraded"]),
        ("Error", counts["error"]),
        ("Other recorded status", counts["other"]),
    )
    items = "".join(f"<dt>{label}</dt><dd>{count}</dd>" for label, count in rows if count)
    return f'<section><h2>Source coverage status</h2><dl class="health">{items}</dl></section>'


def _assert_output_boundary(output: Path, inputs: Iterable[Path]) -> Path:
    if output.exists() or output.is_symlink():
        raise ListeningSiteError("output must be a new path; existing output is never replaced")
    resolved = output.resolve(strict=False)
    for source in inputs:
        candidate = source.resolve()
        if resolved == candidate or resolved.is_relative_to(candidate):
            raise ListeningSiteError("output must be outside every source input")
    parent = output.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ListeningSiteError("output parent must be an existing, non-symlink directory")
    return resolved


def _reserve_output(output: Path) -> tuple[int, int]:
    try:
        output.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise ListeningSiteError("output was created by another owner; refusing to replace it") from exc
    stat = output.stat()
    return stat.st_dev, stat.st_ino


def _remove_owned_output(output: Path, identity: tuple[int, int]) -> None:
    try:
        stat = output.stat()
    except FileNotFoundError:
        return
    if (stat.st_dev, stat.st_ino) == identity:
        shutil.rmtree(output)


def build_site(
    *,
    feed_path: Path,
    manifest_dir: Path,
    stylesheet_path: Path,
    output_dir: Path,
    metadata_path: Path | None = None,
    artwork_path: Path | None = None,
    copy_feed: bool = False,
) -> dict[str, object]:
    """Build without mutating inputs into an exclusively reserved new output."""
    feed = _safe_input(feed_path, "feed")
    manifests_path = _safe_input(manifest_dir, "manifest directory", directory=True)
    stylesheet = _safe_input(stylesheet_path, "stylesheet")
    inputs = [feed, manifests_path, stylesheet]
    metadata = None
    if metadata_path is not None:
        metadata = _safe_input(metadata_path, "metadata catalog")
        inputs.append(metadata)
    artwork = None
    if artwork_path is not None:
        artwork = _safe_input(artwork_path, "artwork")
        inputs.append(artwork)
    output = _assert_output_boundary(output_dir, inputs)

    feed_bytes = feed.read_bytes()
    feed_episodes = _parse_feed(feed_bytes)
    manifests = _load_manifests(manifests_path)
    catalog = load_catalog(metadata) if metadata is not None else {}
    episodes, skipped_drafts = _prepare_episodes(feed_episodes, manifests, catalog)
    if not episodes:
        raise ListeningSiteError("no accepted RSS episodes are eligible for output")
    if skipped_drafts and copy_feed:
        raise ListeningSiteError("cannot copy RSS while withholding a draft episode")

    identity = _reserve_output(output)
    staging = output / ".build"
    try:
        staging.mkdir()
        assets = staging / "assets"
        assets.mkdir()
        css_target = assets / "listening-site.css"
        css_target.write_bytes(stylesheet.read_bytes())
        artwork_name = None
        if artwork is not None:
            artwork_name = artwork.name
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", artwork_name):
                raise ListeningSiteError("artwork filename is unsafe")
            (assets / artwork_name).write_bytes(artwork.read_bytes())
        if copy_feed:
            (assets / "source-feed.xml").write_bytes(feed_bytes)
        (staging / "index.html").write_text(_index(episodes, skipped_drafts, artwork_name), encoding="utf-8")
        for episode in episodes:
            (staging / episode.filename).write_text(_episode_page(episode), encoding="utf-8")
        for child in staging.iterdir():
            os.replace(child, output / child.name)
        staging.rmdir()
        output.chmod(0o755)
    except Exception:
        _remove_owned_output(output, identity)
        raise
    return {
        "episodes": len(episodes),
        "detailed": sum(episode.manifest is not None for episode in episodes),
        "legacy": sum(episode.manifest is None for episode in episodes),
        "drafts_skipped": len(skipped_drafts),
        "output": str(output),
        "feed_sha256": hashlib.sha256(feed_bytes).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--manifests", type=Path, required=True)
    parser.add_argument("--stylesheet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new output directory outside all source inputs")
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--artwork", type=Path, help="optional existing local artwork copied byte-for-byte")
    parser.add_argument(
        "--copy-feed", action="store_true",
        help="copy the source RSS bytes into assets/source-feed.xml",
    )
    args = parser.parse_args()
    report = build_site(
        feed_path=args.feed,
        manifest_dir=args.manifests,
        stylesheet_path=args.stylesheet,
        output_dir=args.output,
        metadata_path=args.metadata,
        artwork_path=args.artwork,
        copy_feed=args.copy_feed,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
