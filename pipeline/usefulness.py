"""Fail-closed checks for a publishable, human-useful spoken briefing."""

from __future__ import annotations

import re

from .schema import EpisodeManifest


_GENERIC_FILLER = (
    "no additional workflow change is supported beyond the cited evidence",
    "no workflow change is supported beyond the cited evidence",
    "no additional action is supported beyond the cited evidence",
    "monitor the upstream release notes for more information",
)
_RAW_SPOKEN_PATTERNS = (
    ("raw URL", re.compile(r"https?://", re.IGNORECASE)),
    ("Markdown heading", re.compile(r"(?m)^\s{0,3}#{1,6}\s+")),
    ("Markdown link", re.compile(r"\[[^\]]+\]\([^\)]+\)")),
    ("code fence or inline code", re.compile(r"`{1,3}")),
    ("pull-request or issue identifier", re.compile(
        r"(?:#\d+\b|\bPR\s*#?\d+\b|\b(?:pull[- ]request|issue)\s+#?\d+\b)", re.IGNORECASE,
    )),
    ("commit hash", re.compile(
        r"(?:\b(?:commit|revision|sha)\s+[0-9a-f]{7,40}\b|\b[0-9a-f]{12,40}\b)", re.IGNORECASE,
    )),
)


class PublicationUsefulnessError(ValueError):
    """The script is factual-looking but not suitable for human publication."""


def spoken_quality_findings(narration: str) -> list[str]:
    """Syntax checks are defects, not a substitute for factual/listening review."""
    narration = narration.strip()
    lowered = " ".join(narration.lower().split())
    findings: list[str] = []
    if not narration:
        findings.append("empty narration")
    for phrase in _GENERIC_FILLER:
        if phrase in lowered:
            findings.append("generic no-value workflow filler")
            break
    for label, pattern in _RAW_SPOKEN_PATTERNS:
        if pattern.search(narration):
            findings.append(f"spoken {label}")
    if narration.startswith("(") and re.match(r"^\(?#?\d+", narration):
        findings.append("script opens with a repository identifier")
    if len(re.findall(r"\b(?:v|version\s+)?\d+\.\d+\.\d+\b", narration, re.I)) > 2:
        findings.append("repeated spoken build numbers")
    if "primary source coverage remained sufficient" in lowered or "supplementary learning coverage" in lowered:
        findings.append("internal coverage diagnostics in speech")
    return list(dict.fromkeys(findings))


def publication_usefulness_findings(manifest: EpisodeManifest) -> list[str]:
    """Preserve the production API-verification gate for newly generated briefs."""
    findings = spoken_quality_findings(manifest.narration)
    if manifest.schema_version != 2:
        findings.append("fresh briefing is not grounded independently verified editorial")
    else:
        if manifest.generation.get("verified") is not True:
            findings.append("grounded editorial script lacks independent model verification")
        if not any(story.action == "skip" for story in manifest.stories):
            findings.append("briefing does not identify anything that is not worth chasing")
    return list(dict.fromkeys(findings))


def validate_publication_usefulness(manifest: EpisodeManifest) -> None:
    findings = publication_usefulness_findings(manifest)
    if findings:
        raise PublicationUsefulnessError("publication usefulness gate failed: " + "; ".join(findings))
