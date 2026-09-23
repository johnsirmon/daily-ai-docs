"""Validated data contracts for daily source events and podcast episodes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import hashlib
import ipaddress
import math
import re
from typing import Any, Dict, List
from urllib.parse import urlparse, urlsplit

from .disclosure import AI_NARRATION_DISCLOSURE


class SchemaError(ValueError):
    """Raised when pipeline data does not satisfy the publication contract."""


MAX_PUBLIC_EXCERPT_WORDS = 180
MAX_LONG_FORM_NARRATION_WORDS = 10000
MAX_LONG_FORM_NARRATION_CHARS = 60000


MAX_FULL_TEXT_CHARS = 80000
MAX_EVERGREEN_SNAPSHOT_BYTES = 80000
# Evergreen evidence is an exceptional, offline-reviewed date exemption. Keep
# this allowlist narrower than general editorial URL validation: adding a new
# documentation surface requires a code review and positive/negative fixtures.
_EVERGREEN_DOCUMENTATION_PREFIXES = {
    "docs.github.com": ("/en/copilot",),
}
_EVERGREEN_DOCUMENTATION_EXACT_PATHS = {
    "docs.typesafe.ai": frozenset({
        "/introduction", "/introduction.md",
        "/introduction/coding-agents", "/introduction/coding-agents.md",
        "/models", "/models.md",
        "/model-jaggedness/jev-1.13", "/model-jaggedness/jev-1.13.md",
        "/api", "/api.md",
        "/agent-skill", "/agent-skill.md",
        "/legal", "/legal.md",
    }),
    "code.visualstudio.com": frozenset({
        "/docs/agent-customization/language-models",
        "/docs/copilot/customization/mcp-servers",
    }),
    "typesafe.ai": frozenset({
        "/privacy-policy",
        "/legal/privacy-policy",
    }),
}
_SPOKEN_DEBRIS = re.compile(
    r"https?://|www\.|\b[a-z0-9.-]+\.(?:com|org|net|io|dev|ai|edu|gov)(?:/|\b)|"
    r"&(?:#\d+|#x[0-9a-f]+|[a-z][a-z0-9]+);|<[^>]+>|"
    r"`|\*\*|\[[^\]]+\]\(|^\s*(?:[#>|]|[-*+]\s)|"
    r"full (?:release )?notes? (?:were |was )?not (?:available|included)|"
    r"extraction (?:failed|notice)|\[(?:truncated|excerpt|extraction)[^\]]*\]|"
    r"(?:summary|excerpt) unavailable|read more|click here|"
    r"the call is (?:act|watch|skip)|"
    r"this (?:update|release|change) (?:matters|is relevant) (?:because|for)|"
    r"keep (?:an eye on|building)|worth (?:your attention|watching)|"
    r"ignore (?:all |the |previous |prior )*instructions|system prompt",
    re.IGNORECASE | re.MULTILINE,
)
_GENERIC_UTILITY = re.compile(
    r"^(?:this is relevant to developers tracking\b.*|read the (?:primary source|release notes?)[.!]?|"
    r"assess applicability[.!]?|a new version was released[.!]?)$",
    re.IGNORECASE,
)
_QUANTITIES = re.compile(
    r"\d+(?:[.,]\d+)*(?:\s*(?:%|percent|million|billion|trillion))?|"
    r"\b(?:zero|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
    r"million|billion|trillion)\b",
    re.IGNORECASE,
)


def validate_editorial_source_url(value: Any) -> None:
    try:
        _https_url(value, "editorial source URL")
        parsed = urlparse(value)
        port = parsed.port
    except ValueError as exc:
        raise SchemaError("editorial source URL is invalid") from exc
    host = parsed.hostname or ""
    if parsed.username or parsed.password or port not in {None, 443}:
        raise SchemaError("editorial sources must use public HTTPS URLs without credentials")
    if "." not in host or host.endswith((".localhost", ".local", ".internal", ".test")):
        raise SchemaError("editorial sources must use public hosts")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise SchemaError("editorial sources must not use private addresses")


def validate_spoken_text(value: Any, name: str, *, limit: int = 12000) -> str:
    """Reject debris rather than silently rewriting already verified narration."""
    text = _text(value, name, limit=limit)
    if _SPOKEN_DEBRIS.search(text):
        raise SchemaError(f"{name} contains URLs, markup, instructions, or editorial boilerplate")
    return text


def validate_specific_utility(value: Any, name: str) -> str:
    """Reject explanations that name a topic but establish no consequence."""
    text = validate_spoken_text(value, name, limit=1600)
    if _GENERIC_UTILITY.fullmatch(" ".join(text.split())):
        raise SchemaError(f"{name} must state a specific developer consequence or decision")
    return text


def _quantities(text: str) -> set[str]:
    return {
        re.sub(r"\s+", "", match.lower().replace(",", "").replace("percent", "%"))
        for match in _QUANTITIES.findall(text)
    }


def validate_quantities(text: str, evidence: str, name: str) -> None:
    missing = sorted(_quantities(text) - _quantities(evidence))
    if missing:
        detail = ", ".join(quantity[:32] for quantity in missing[:8])
        raise SchemaError(f"{name} contains an unsupported quantitative claim (unsupported: {detail})")


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


def _utc_timestamp(value: Any, name: str) -> datetime:
    value = _timestamp(value, name)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise SchemaError(f"{name} must be a UTC timestamp")
    return parsed


def validate_evergreen_snapshot(event: "SourceEvent") -> None:
    """Validate an exact, human-reviewed capture of undated public documentation."""
    if event.published_at != "":
        raise SchemaError("evergreen documentation published_at must be empty")
    if event.authority != "primary":
        raise SchemaError("evergreen documentation must be public primary documentation")
    validate_editorial_source_url(event.url)
    # urlparse() moves a final segment's semicolon parameters out of .path,
    # which can make an unreviewed resource such as /models;draft appear to be
    # the reviewed /models page. urlsplit() preserves the request path exactly.
    parsed = urlsplit(event.url)
    host = (parsed.hostname or "").casefold()
    raw_path = parsed.path
    path = raw_path[:-1] if raw_path.endswith("/") else raw_path
    prefixes = _EVERGREEN_DOCUMENTATION_PREFIXES.get(host, ())
    exact_paths = _EVERGREEN_DOCUMENTATION_EXACT_PATHS.get(host, frozenset())
    # Browsers and HTTP clients normalize dot segments and treat backslashes as
    # separators for HTTPS URLs. Percent-encoding can hide either form from a
    # raw prefix check. Evergreen admission is intentionally narrower than the
    # general URL contract, so reject non-canonical path syntax rather than
    # rewriting the reviewed source identity.
    path_segments = path.split("/")
    if (re.search(r"[\x00-\x20\x7f]", event.url)
            or not path.startswith("/") or "%" in path or "\\" in path or ";" in path
            or any(segment in {"", ".", ".."} for segment in path_segments[1:])
            or not (path in exact_paths
                    or any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes))):
        raise SchemaError("evergreen documentation URL is not an approved official documentation path")
    snapshot = event.metadata.get("evergreen_snapshot")
    _exact_fields(snapshot, {
        "captured_at", "content_sha256", "content", "reviewer", "reviewed_at", "review_note",
    }, "evergreen_snapshot")
    captured_at = _utc_timestamp(snapshot["captured_at"], "evergreen_snapshot.captured_at")
    reviewed_at = _utc_timestamp(snapshot["reviewed_at"], "evergreen_snapshot.reviewed_at")
    if reviewed_at < captured_at:
        raise SchemaError("evergreen snapshot review cannot predate capture")
    content = snapshot["content"]
    if not isinstance(content, str) or not content.strip():
        raise SchemaError("evergreen_snapshot.content must be nonempty captured text")
    if len(content.encode("utf-8")) > MAX_EVERGREEN_SNAPSHOT_BYTES:
        raise SchemaError(f"evergreen_snapshot.content exceeds {MAX_EVERGREEN_SNAPSHOT_BYTES} UTF-8 bytes")
    _sha256(snapshot["content_sha256"], "evergreen_snapshot.content_sha256")
    if snapshot["content_sha256"] != hashlib.sha256(content.encode("utf-8")).hexdigest():
        raise SchemaError("evergreen_snapshot.content_sha256 must hash the exact UTF-8 content")
    if event.evidence not in content:
        raise SchemaError("evergreen documentation evidence must be an exact excerpt of snapshot content")
    _text(snapshot["reviewer"], "evergreen_snapshot.reviewer", limit=200)
    note = _text(snapshot["review_note"], "evergreen_snapshot.review_note", limit=1600)
    normalized_note = " ".join(note.casefold().split())
    if ("original publication date" not in normalized_note
            or not re.search(r"\b(?:unavailable|unknown|not (?:available|provided|published|shown|stated))\b",
                             normalized_note)
            or not re.search(r"\b(?:because|since|page|metadata|does not|no date)\b", normalized_note)):
        raise SchemaError("evergreen snapshot review_note must explain why the original publication date is unavailable")


def source_display_label(event: "SourceEvent") -> str:
    """Return the required user-facing evidence label without changing old source copy."""
    if event.source_type != "evergreen_documentation":
        return ""
    reviewed = _utc_timestamp(
        event.metadata["evergreen_snapshot"]["reviewed_at"], "evergreen_snapshot.reviewed_at",
    )
    return f"Evergreen documentation; original publication date unavailable; snapshot reviewed {reviewed:%Y-%m-%d}"


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
            "github_release", "official_feed", "announcement", "security", "community", "youtube_video",
            "research_paper", "evergreen_documentation",
        }:
            raise SchemaError("unsupported source_type")
        _text(self.title, "title", limit=500)
        _https_url(self.url, "url")
        _text(self.product, "product", limit=200)
        _text(self.topic, "topic", limit=100)
        _text(self.evidence, "evidence", limit=8192)
        if not isinstance(self.metadata, dict):
            raise SchemaError("metadata must be an object")
        if self.source_type == "evergreen_documentation":
            validate_evergreen_snapshot(self)
        else:
            _timestamp(self.published_at, "published_at")
        _timestamp(self.fetched_at, "fetched_at")
        if self.authority not in {"primary", "secondary"}:
            raise SchemaError("authority must be primary or secondary")
        if self.channel not in {"stable", "prerelease", "announcement", "security"}:
            raise SchemaError("unsupported channel")
        if self.metadata.get("private") is True or self.metadata.get("draft") is True:
            raise SchemaError("private repositories and draft releases are not publishable")
        if "full_text" in self.metadata:
            _text(self.metadata["full_text"], "full_text", allow_empty=True, limit=MAX_FULL_TEXT_CHARS)
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
    kind: str = "product"
    editorial: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> "Story":
        _text(self.story_id, "story_id", limit=200)
        if not isinstance(self.event_ids, list) or not self.event_ids or not all(isinstance(x, str) and x for x in self.event_ids):
            raise SchemaError("event_ids must be a non-empty string list")
        _text(self.headline, "headline", limit=500)
        _text(self.what_changed, "what_changed", limit=1600)
        _text(self.why_it_matters, "why_it_matters", limit=1600)
        if not isinstance(self.action, str) or self.action not in {"act", "watch", "skip"}:
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
        if not isinstance(self.kind, str) or self.kind not in {"product", "research"}:
            raise SchemaError("kind must be product or research")
        if not isinstance(self.editorial, dict):
            raise SchemaError("editorial must be an object")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        data = asdict(self)
        # Default fields must not change immutable pre-editorial release manifests.
        if self.kind == "product" and not self.editorial:
            data.pop("kind")
            data.pop("editorial")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Story":
        if not isinstance(data, dict):
            raise SchemaError("story must be an object")
        try:
            return cls(**data).validate()
        except TypeError as exc:
            raise SchemaError(f"invalid story fields: {exc}") from exc


def source_urls_for_events(events: List[SourceEvent]) -> List[str]:
    urls = []
    for event in events:
        urls.append(event.url)
        corroboration = event.metadata.get("corroboration_urls", [])
        if not isinstance(corroboration, list):
            raise SchemaError("corroboration_urls must be a list")
        for url in corroboration:
            _https_url(url, "corroboration URL")
        urls.extend(corroboration)
    return list(dict.fromkeys(urls))


def validate_editorial_stories(events: List[SourceEvent], stories: List[Story]) -> None:
    """Check citations and structure; semantic entailment requires independent verification."""
    by_id = {event.event_id: event.validate() for event in events}
    if len(by_id) != len(events):
        raise SchemaError("source event IDs must be unique")
    if not stories or len(stories) > 7:
        raise SchemaError("editorial publication requires one to seven stories")
    seen_events: set[str] = set()
    seen_stories: set[str] = set()
    sentences: set[str] = set()
    research_count = 0
    for story in stories:
        story.validate()
        if story.story_id in seen_stories:
            raise SchemaError("editorial story IDs must be unique")
        seen_stories.add(story.story_id)
        if len(set(story.event_ids)) != len(story.event_ids) or seen_events.intersection(story.event_ids):
            raise SchemaError("editorial stories duplicate evidence")
        seen_events.update(story.event_ids)
        if not set(story.event_ids).issubset(by_id):
            raise SchemaError("story references an unknown source event")
        referenced = [by_id[event_id] for event_id in story.event_ids]
        if not all(event.authority == "primary" for event in referenced):
            raise SchemaError("editorial claims require public primary evidence")
        if story.source_urls != source_urls_for_events(referenced):
            raise SchemaError("story source URLs must match referenced evidence")
        for url in story.source_urls:
            validate_editorial_source_url(url)
        if set(story.editorial) - {"spoken_text", "claims", "paper_review"}:
            raise SchemaError("unknown editorial fields")
        spoken = validate_spoken_text(story.editorial.get("spoken_text"), "spoken_text")
        claims = story.editorial.get("claims")
        if not isinstance(claims, list) or not 1 <= len(claims) <= 40:
            raise SchemaError("editorial claims must be a bounded non-empty list")
        claim_events = set()
        claim_keys = set()
        quotes = []
        for claim in claims:
            if not isinstance(claim, dict) or set(claim) != {"text", "event_id", "quote"}:
                raise SchemaError("claim requires only text, event_id, and quote")
            claim_id = _text(claim["event_id"], "claim.event_id", limit=200)
            if claim_id not in story.event_ids:
                raise SchemaError("claim references an unknown or unrelated source event")
            claim_events.add(claim_id)
            text = validate_spoken_text(claim["text"], "claim.text", limit=1600)
            _text(claim["quote"], "claim.quote", limit=4000)
            quote = claim["quote"]
            event = by_id[claim_id]
            if quote not in event.evidence and quote not in event.metadata.get("full_text", ""):
                raise SchemaError("claim quote must exactly match known evidence")
            key = (claim_id, text.casefold())
            if key in claim_keys:
                raise SchemaError("duplicate editorial claim")
            claim_keys.add(key)
            validate_quantities(text, quote, "claim.text")
            quotes.append(quote)
        if claim_events != set(story.event_ids):
            raise SchemaError("claims must account for every grouped event")
        support = "\n".join(quotes)
        for name in ("headline", "what_changed", "why_it_matters", "rationale"):
            text = validate_spoken_text(getattr(story, name), name)
            validate_quantities(text, support, name)
        validate_quantities(spoken, support, "spoken_text")
        for sentence in re.split(r"(?<=[.!?])\s+", spoken):
            normalized = " ".join(sentence.casefold().split())
            if len(normalized.split()) >= 6:
                if normalized in sentences:
                    raise SchemaError("repeated spoken sentence is editorial boilerplate")
                sentences.add(normalized)
        papers = [event for event in referenced if event.source_type == "research_paper"]
        if bool(papers) != (story.kind == "research"):
            raise SchemaError("research evidence must be clearly classified as research")
        if story.kind == "research":
            research_count += 1
            if len(papers) != 1 or len(referenced) != 1 or research_count > 1:
                raise SchemaError("an episode supports at most one distinct research paper")
            paper = papers[0]
            metadata = paper.metadata
            if metadata.get("full_text_available") is not True:
                raise SchemaError("research requires reviewed full-text evidence, not an abstract")
            if metadata.get("full_text_retained") is False:
                if "full_text" in metadata or metadata.get("evidence_status") != "reviewed_excerpts":
                    raise SchemaError("archived research must retain only reviewed excerpts")
                full_text = _text(metadata.get("reviewed_excerpts"), "research.reviewed_excerpts", limit=4000)
                if len(full_text.split()) > MAX_PUBLIC_EXCERPT_WORDS or full_text != papers[0].evidence:
                    raise SchemaError("archived research exceeds the supporting-excerpt contract")
            else:
                full_text = _text(metadata.get("full_text"), "research.full_text", limit=MAX_FULL_TEXT_CHARS)
            _text(metadata.get("paper_id"), "paper_id", limit=100)
            if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})", metadata["paper_id"]):
                raise SchemaError("paper_id must be a canonical base arXiv ID")
            version = metadata.get("version")
            if not ((type(version) is int and version > 0) or
                    (isinstance(version, str) and re.fullmatch(r"v?[1-9]\d*", version))):
                raise SchemaError("research version must identify a positive paper revision")
            _timestamp(metadata.get("first_published_at"), "first_published_at")
            _timestamp(metadata.get("updated_at"), "updated_at")
            if any(claim["quote"].strip() not in full_text for claim in claims):
                raise SchemaError("research claims require exact full-text quotes")
            review = story.editorial.get("paper_review")
            required = {"question", "method", "result", "limitations", "takeaway", "evidence_status"}
            if not isinstance(review, dict) or set(review) != required:
                raise SchemaError("paper_review requires question, method, result, limitations, takeaway, evidence_status")
            for name in required - {"evidence_status"}:
                text = validate_spoken_text(review[name], f"paper_review.{name}", limit=1600)
                validate_quantities(text, support, f"paper_review.{name}")
            if review["evidence_status"] != "author_reported_not_reproduced":
                raise SchemaError("research evidence_status must be author_reported_not_reproduced")
            if not re.search(r"\bresearch\b", spoken, re.IGNORECASE):
                raise SchemaError("spoken research must be labeled as research")
            if not re.search(r"\bauthor[- ]reported\b", spoken, re.IGNORECASE):
                raise SchemaError("spoken research must identify author-reported evidence")
            if not re.search(r"\bnot (?:independently )?reproduced\b", spoken, re.IGNORECASE):
                raise SchemaError("spoken research must disclose that results are not reproduced")
            if review["limitations"].strip() not in spoken:
                raise SchemaError("spoken research must retain the reviewed limitations verbatim")
        elif "paper_review" in story.editorial:
            raise SchemaError("product stories must not contain a paper_review")


def editorial_narration(stories: List[Story], generation: Dict[str, Any]) -> str:
    """Assemble verified prose without introducing new, unverified narrator text."""
    if not isinstance(generation, dict):
        raise SchemaError("generation must be an object")
    if (generation.get("provider") != "gemini" or generation.get("verified") is not True
            or generation.get("editorial_version") != 1 or generation.get("calls") != 2):
        raise SchemaError("editorial narration requires independently verified Gemini generation")
    model = _text(generation.get("model"), "generation.model", limit=120)
    if not model.startswith("gemini-"):
        raise SchemaError("editorial model must be a Gemini model")
    opening = validate_spoken_text(generation.get("opening"), "generation.opening", limit=2000)
    closing = validate_spoken_text(generation.get("closing"), "generation.closing", limit=2000)
    support = "\n".join(claim["quote"] for story in stories for claim in story.editorial["claims"])
    validate_quantities(opening, support, "generation.opening")
    validate_quantities(closing, support, "generation.closing")
    disclosure = generation.get("production_disclosure")
    if disclosure is not None and disclosure != AI_NARRATION_DISCLOSURE:
        raise SchemaError("generation.production_disclosure must use the approved production disclosure")
    text = "\n\n".join([
        *([AI_NARRATION_DISCLOSURE] if disclosure else []),
        opening,
        *(story.editorial["spoken_text"] for story in stories),
        closing,
    ])
    _text(text, "editorial narration", limit=16000)
    if len(text.split()) > 1500:
        raise SchemaError("editorial narration exceeds the 1500-word budget")
    return text


def _sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SchemaError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _exact_fields(value: Any, fields: set[str], name: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise SchemaError(f"{name} requires only {', '.join(sorted(fields))}")


def _reviewed_public_url(value: str) -> None:
    validate_editorial_source_url(value)
    parsed = urlparse(value)
    host = parsed.hostname or ""
    private_hosts = {
        "notebooklm.google", "notebooklm.google.com", "gemini.google.com",
        "notebook.google", "notebook.google.com",
        "accounts.google.com", "docs.google.com", "drive.google.com", "aistudio.google.com",
    }
    if (parsed.query or parsed.fragment
            or any(host == private or host.endswith("." + private) for private in private_hosts)):
        raise SchemaError("reviewed audio artifacts require public URLs without account links or query data")


def _reviewed_public_values(value: Any) -> None:
    """Check embedded links too, including transcript and review-note links."""
    if isinstance(value, dict):
        for key, item in value.items():
            _reviewed_public_values(key)
            _reviewed_public_values(item)
    elif isinstance(value, list):
        for item in value:
            _reviewed_public_values(item)
    elif isinstance(value, str):
        # Require a host character so prose such as “remotes start with https://”
        # is not misclassified as a URL. Actual embedded URLs remain validated.
        for url in re.findall(r"https?://[A-Za-z0-9][^\s<>\"']*", value):
            _reviewed_public_url(url.rstrip(".,;!)]}"))


def validate_reviewed_audio(manifest: "EpisodeManifest") -> None:
    """Validate explicit human-authorized, locally transcribed audio provenance.

    This records a transcript/source comparison, not Gemini API verification.
    Semantic entailment and any ASR limitations remain the reviewer's responsibility.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", manifest.episode_id):
        raise SchemaError("reviewed audio requires a safe episode_id")
    if manifest.status not in {"draft", "ready", "candidate", "published"}:
        raise SchemaError("reviewed audio requires a publication status")
    generation = manifest.generation
    long_form = manifest.schema_version == 4
    one_release_waiver = (
        manifest.schema_version == 3
        and generation.get("edition") == "gate-a-one-release-waiver"
    )
    if generation.get("preview_only") is True:
        raise SchemaError("preview-only audio cannot be published")
    generation_fields = {
        "edition", "provider", "approved_at", "source_audio_sha256", "transcript", "review",
    }
    if long_form:
        generation_fields |= {"request", "request_sha256", "quality", "voice"}
    elif one_release_waiver:
        generation_fields |= {"quality", "voice", "waiver"}
    elif "quality" in generation:
        generation_fields.add("quality")
    if "editing" in generation:
        generation_fields.add("editing")
    _exact_fields(generation, generation_fields, "reviewed generation")
    if (not long_form and not one_release_waiver
            and (generation["edition"] != "notebook"
                 or generation["provider"] != "gemini-notebook-web")):
        raise SchemaError("reviewed audio requires the gemini-notebook-web notebook provider")
    if one_release_waiver:
        # Import lazily to keep the exceptional fixed contract out of general
        # schema initialization and to avoid making it a reusable provider mode.
        from .gate_a_release import validate_exact_publication_manifest
        validate_exact_publication_manifest(manifest)
    if long_form:
        from .podcast_request import PodcastRequest, utc_timestamp
        try:
            request = PodcastRequest.from_dict(generation["request"])
            request.validate_sources(manifest.source_events)
        except (ValueError, KeyError) as exc:
            raise SchemaError(f"invalid ad-hoc request: {exc}") from exc
        if (generation["edition"] != "adhoc" or generation["provider"] != request.provider
                or generation["request_sha256"] != request.revision
                or manifest.episode_id != request.episode_id):
            raise SchemaError("ad-hoc identity must match the exact requested revision and provider")
        if utc_timestamp(request.cutoff) > utc_timestamp(manifest.published_at):
            raise SchemaError("request research cutoff cannot be after publication")
        if not isinstance(generation["voice"], dict):
            raise SchemaError("voice provenance must be an object")
        voice = generation["voice"]
        if request.provider == "gemini-notebook-web":
            _exact_fields(voice, set(), "Notebook voice")
        elif request.provider == "edge":
            _exact_fields(voice, {"name", "rate", "pitch"}, "Edge voice")
            for key in voice:
                _text(voice[key], f"voice.{key}", limit=120)
        from .audio_quality import repetition_findings, validate_quality_report
        if repetition_findings(manifest.narration):
            raise SchemaError("adjacent repeated speech requires editorial review")
        validate_quality_report(generation["quality"], final=manifest.status != "draft",
                                audio_sha256=manifest.audio.get("sha256"))
        if manifest.status in {"candidate", "published"} and not request.publish_now:
            raise SchemaError("preview request cannot be published")
    elif "quality" in generation:
        from .audio_quality import validate_quality_report
        validate_quality_report(generation["quality"], final=manifest.status != "draft",
                                audio_sha256=manifest.audio.get("sha256"))
    _timestamp(generation["approved_at"], "generation.approved_at")
    _sha256(generation["source_audio_sha256"], "generation.source_audio_sha256")
    if "editing" in generation:
        editing = generation["editing"]
        _exact_fields(editing, {
            "method", "original_audio_sha256", "correction_text",
            "correction_audio_sha256", "correction_provider",
        }, "generation.editing")
        if (editing["method"] != "prefixed_editorial_correction"
                or editing["correction_provider"] != "edge"):
            raise SchemaError("editing requires a prefixed_editorial_correction from edge")
        _sha256(editing["original_audio_sha256"], "editing.original_audio_sha256")
        _sha256(editing["correction_audio_sha256"], "editing.correction_audio_sha256")
        _text(editing["correction_text"], "editing.correction_text", limit=1600)
        correction = editing["correction_text"]
        if not manifest.narration.startswith(correction):
            raise SchemaError("editing.correction_text must be the exact narration prefix")
        if not manifest.narration[len(correction):].strip():
            raise SchemaError("edited narration must retain the conversation after the correction")
    transcript = generation["transcript"]
    _exact_fields(transcript, {"engine", "model", "sha256"}, "transcript")
    if transcript["engine"] not in ("faster-whisper", "whisper", "openai-whisper", "whisper.cpp"):
        raise SchemaError("transcript.engine must identify a supported local ASR engine")
    _text(transcript["model"], "transcript.model", limit=120)
    _sha256(transcript["sha256"], "transcript.sha256")
    if transcript["sha256"] != hashlib.sha256(manifest.narration.encode("utf-8")).hexdigest():
        raise SchemaError("transcript.sha256 must hash the exact UTF-8 narration")
    character_limit = MAX_LONG_FORM_NARRATION_CHARS if long_form else 16000
    if len(manifest.narration) > character_limit:
        raise SchemaError(f"narration exceeds {character_limit} characters")
    review = generation["review"]
    _exact_fields(review, {"method", "reviewed_at", "reviewer", "claims", "notes"}, "review")
    if review["method"] != "transcript_source_comparison" or review["reviewer"] != "assistant":
        raise SchemaError("review must identify the assistant transcript_source_comparison")
    _timestamp(review["reviewed_at"], "review.reviewed_at")
    if not isinstance(review["notes"], list) or not 1 <= len(review["notes"]) <= 20:
        raise SchemaError("review.notes must be a bounded non-empty list of review and ASR limitations")
    for note in review["notes"]:
        _text(note, "review.note", limit=1600)
    if not isinstance(review["claims"], list) or not 1 <= len(review["claims"]) <= (300 if long_form else 100):
        raise SchemaError("review.claims must be a bounded non-empty list")
    events = {event.event_id: event for event in manifest.source_events}
    paper_fields = {
        "paper_id", "version", "first_published_at", "updated_at", "full_text_available",
        "full_text_retained", "evidence_status", "reviewed_excerpts",
    }
    for event in manifest.source_events:
        if event.authority != "primary":
            raise SchemaError("reviewed audio requires public primary evidence")
        _reviewed_public_url(event.url)
        if "full_text" in event.metadata or len(event.evidence.split()) > MAX_PUBLIC_EXCERPT_WORDS:
            raise SchemaError("reviewed audio must archive short excerpts, not full source documents")
        hash_fields = {"source_text_sha256", "source_document_sha256", "source_evidence_sha256"}
        allowed = {"corroboration_urls", "evidence_status"} | hash_fields
        if event.source_type == "research_paper":
            allowed |= paper_fields
        if event.source_type == "evergreen_documentation":
            if not long_form:
                raise SchemaError("evergreen documentation is supporting evidence for ad-hoc requests only")
            allowed |= {"evergreen_snapshot"}
        if set(event.metadata) - allowed:
            raise SchemaError("unsupported reviewed source metadata; retain only public provenance")
        for name in hash_fields & event.metadata.keys():
            _sha256(event.metadata[name], name)
        if "evidence_status" in event.metadata and event.metadata["evidence_status"] != "reviewed_excerpts":
            raise SchemaError("reviewed source evidence_status must identify reviewed_excerpts")
    if not 1 <= len(manifest.stories) <= 7:
        raise SchemaError("reviewed audio requires one to seven stories")
    mapped_events: set[str] = set()
    for story in manifest.stories:
        if (len(set(story.event_ids)) != len(story.event_ids)
                or (not long_form and mapped_events.intersection(story.event_ids))):
            raise SchemaError("reviewed stories must map each source exactly once")
        mapped_events.update(story.event_ids)
        papers = [events[event_id] for event_id in story.event_ids
                  if events[event_id].source_type == "research_paper"]
        if bool(papers) != (story.kind == "research"):
            raise SchemaError("research evidence must be clearly classified as research")
        if story.kind == "research":
            if len(papers) != 1 or len(story.event_ids) != 1:
                raise SchemaError("each research story requires one distinct paper")
            paper = papers[0]
            metadata = paper.metadata
            if (metadata.get("full_text_available") is not True
                    or metadata.get("full_text_retained") is not False
                    or metadata.get("evidence_status") != "reviewed_excerpts"
                    or metadata.get("reviewed_excerpts") != paper.evidence):
                raise SchemaError("research requires archived reviewed excerpts from the full paper")
            paper_id = _text(metadata.get("paper_id"), "paper_id", limit=100)
            if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})", paper_id):
                raise SchemaError("paper_id must be a canonical base arXiv ID")
            version = metadata.get("version")
            if not ((type(version) is int and version > 0) or
                    (isinstance(version, str) and re.fullmatch(r"v?[1-9]\d*", version))):
                raise SchemaError("research version must identify a positive paper revision")
            if paper.url != f"https://arxiv.org/abs/{paper_id}":
                raise SchemaError("research URL must match the canonical paper_id")
            _timestamp(metadata.get("first_published_at"), "first_published_at")
            _timestamp(metadata.get("updated_at"), "updated_at")
            _exact_fields(story.editorial, {"paper_review"}, "research editorial")
            paper_review = story.editorial["paper_review"]
            _exact_fields(paper_review, {
                "question", "method", "result", "limitations", "takeaway", "evidence_status",
            }, "paper_review")
            for name in ("question", "method", "result", "limitations", "takeaway"):
                text = validate_spoken_text(paper_review[name], f"paper_review.{name}", limit=1600)
                validate_quantities(text, paper.evidence, f"paper_review.{name}")
            if paper_review["evidence_status"] != "author_reported_not_reproduced":
                raise SchemaError("paper_review evidence_status must be author_reported_not_reproduced")
        elif story.editorial:
            raise SchemaError("reviewed product stories store claims in generation.review, not editorial")
    if mapped_events != set(events):
        raise SchemaError("reviewed stories must account for every source event")
    claimed_events: set[str] = set()
    claim_keys: set[tuple[str, str]] = set()
    for claim in review["claims"]:
        _exact_fields(claim, {"text", "event_id", "quote"}, "review claim")
        event_id = _text(claim["event_id"], "claim.event_id", limit=200)
        _text(claim["text"], "claim.text", limit=1600)
        _text(claim["quote"], "claim.quote", limit=4000)
        if event_id not in events or event_id not in mapped_events:
            raise SchemaError("claim references an unknown or unmapped source event")
        if claim["text"] not in manifest.narration:
            raise SchemaError("claim.text must occur verbatim in the ASR narration")
        if claim["quote"] not in events[event_id].evidence:
            raise SchemaError("claim.quote must occur verbatim in the referenced event evidence")
        if long_form:
            validate_quantities(claim["text"], claim["quote"], "reviewed claim")
        key = (event_id, claim["text"])
        if key in claim_keys:
            raise SchemaError("duplicate reviewed claim")
        claim_keys.add(key)
        claimed_events.add(event_id)
    if claimed_events != set(events):
        raise SchemaError("review claims must account for every source event")
    url = manifest.audio.get("url")
    if not isinstance(url, str) or not re.fullmatch(
        r"https://github\.com/[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*/"
        r"releases/download/" + re.escape(manifest.episode_id) + r"/daily-ai-brief\.mp3", url,
    ):
        raise SchemaError("audio.url must be the canonical GitHub release MP3 for this episode")
    if manifest.status == "draft":
        _exact_fields(manifest.audio, {"url"}, "draft audio")
    else:
        _exact_fields(manifest.audio, {
            "url", "sha256", "size_bytes", "duration_secs", "codec", "sample_rate", "channels",
        }, "reviewed audio")
        _sha256(manifest.audio["sha256"], "audio.sha256")
        if type(manifest.audio["size_bytes"]) is not int or manifest.audio["size_bytes"] < 10_000:
            raise SchemaError("reviewed audio size must be a measured positive integer")
        duration = manifest.audio["duration_secs"]
        if (type(duration) not in (int, float) or not math.isfinite(duration)
                or duration <= 0):
            raise SchemaError("reviewed audio duration must be a finite positive number")
        if not long_form and not 300 <= duration <= 480:
            raise SchemaError("reviewed audio duration must be within 300-480 seconds")
        if (manifest.audio["codec"] != "mp3" or type(manifest.audio["sample_rate"]) is not int
                or manifest.audio["sample_rate"] != 44100
                or type(manifest.audio["channels"]) is not int or manifest.audio["channels"] != 2):
            raise SchemaError("reviewed audio must be a 44100 Hz stereo MP3")
    _reviewed_public_values(asdict(manifest))


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
        if self.schema_version not in {1, 2, 3, 4}:
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
            if event.source_type == "evergreen_documentation" and self.schema_version != 4:
                raise SchemaError("evergreen documentation is supporting evidence for ad-hoc requests only")
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
            if story.source_urls != source_urls_for_events(referenced):
                raise SchemaError("story source URLs must match referenced evidence")
        if not isinstance(self.noise_notes, list) or not all(isinstance(x, str) for x in self.noise_notes):
            raise SchemaError("noise_notes must be a string list")
        long_form = self.schema_version == 4
        narration = _text(self.narration, "narration", limit=MAX_LONG_FORM_NARRATION_CHARS if long_form else 16000)
        if len(narration.split()) > (MAX_LONG_FORM_NARRATION_WORDS if long_form else 1500):
            if long_form:
                raise SchemaError(f"narration exceeds the {MAX_LONG_FORM_NARRATION_WORDS}-word long-form budget")
            raise SchemaError("narration exceeds the ten-minute word budget")
        _text(self.show_notes, "show_notes", limit=24000)
        if not isinstance(self.generation, dict) or not isinstance(self.audio, dict):
            raise SchemaError("generation and audio must be objects")
        if self.schema_version in {1, 2} and "quality" in self.generation:
            from .audio_quality import validate_quality_report
            validate_quality_report(self.generation["quality"], final=True,
                                    audio_sha256=self.audio.get("sha256"))
        if self.schema_version in {3, 4}:
            validate_reviewed_audio(self)
        if self.schema_version == 2:
            validate_editorial_stories(self.source_events, self.stories)
            expected_narration = editorial_narration(self.stories, self.generation)
            if self.narration != expected_narration:
                raise SchemaError("v2 narration must exactly match verified editorial prose")
            if require_audio or self.status in {"ready", "candidate", "published"}:
                for event in self.source_events:
                    if "full_text" in event.metadata or len(event.evidence.split()) > MAX_PUBLIC_EXCERPT_WORDS:
                        raise SchemaError("publication must archive short excerpts, not full source documents")
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
        if self.schema_version == 1:
            data["stories"] = [story.to_dict() for story in self.stories]
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
