"""Convert a README.md string into a clean spoken-word script for TTS.

Strips markdown tables, link syntax, and decorators; retains topic headings,
AI-generated blurbs (Why / What to learn), Overview narrative, Repo Deep Dive
prose, Community Pulse, and Action Items — which together form the full
~1-hour narration script.
"""

import re
from typing import List


def _strip_markdown(text: str) -> str:
    """Remove markdown syntax that would sound bad when spoken aloud."""
    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Remove tables (lines containing |)
    text = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("|")
    )
    # Remove horizontal rules
    text = re.sub(r"^\s*---+\s*$", "", text, flags=re.MULTILINE)
    # Unwrap links: [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Remove inline code backticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove blockquote markers but keep content
    text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Sub-headings to include as spoken transitions
_NARRATED_SUBHEADINGS = {
    "### Overview": "Overview.",
    "### 🔍 Repo Deep Dives": "Repository deep dives.",
    "### 📊 Community Pulse": "Community pulse.",
    "### ✅ Action Items This Week": "Action items for this week.",
    "### 🚀 Recent Releases": "Recent releases.",
}

# Sub-headings that introduce tables we should skip prose under
_TABLE_SUBHEADINGS = {"### 🌱 New & Rising Repos", "### 📋 Quick Reference"}

# Stat callout lines emitted by render.py under each #### repo heading
_STAT_LINE_RE = re.compile(r"^_[⭐📈📉➡️].*_$")


def _extract_sections(readme: str) -> List[str]:
    """Return a list of spoken paragraphs from README content.

    Keeps:
    - The date heading
    - Per-topic headings
    - Why/Learn blurbs
    - Overview narrative paragraphs
    - Repo deep-dive prose (prose paragraphs, skipping stat callout lines)
    - Community Pulse paragraphs
    - Action Items bullet text
    - Recent Releases (notes prose only, not table rows)

    Skips:
    - TOC list
    - Table rows (lines starting with |)
    - Stat callout lines (_⭐ 1,234 · Python · ..._)
    - Repo sub-headings (#### `org/name`) — spoken inline via repo name
    - Footer links
    """
    paragraphs: List[str] = []
    in_toc = False
    in_table_section = False
    in_narrated_section = False
    current_subheading = ""

    for line in readme.splitlines():
        stripped = line.strip()

        # ── Top-level date heading ──────────────────────────────────────────
        if stripped.startswith("# AI Skills Radar"):
            date_part = stripped.lstrip("# ").strip()
            paragraphs.append(f"AI Skills Radar. {date_part}.")
            continue

        # ── TOC block ───────────────────────────────────────────────────────
        if stripped == "## Topics":
            in_toc = True
            continue
        if in_toc:
            if stripped.startswith("## ") and stripped != "## Topics":
                in_toc = False
            else:
                continue

        # ── Topic section headings (## …) ───────────────────────────────────
        if stripped.startswith("## ") and not stripped.startswith("## Topics"):
            topic_name = stripped.lstrip("# ").strip()
            paragraphs.append(f"Next topic: {topic_name}.")
            in_table_section = False
            in_narrated_section = False
            current_subheading = ""
            continue

        # ── Sub-heading: narrated transition ────────────────────────────────
        if stripped in _NARRATED_SUBHEADINGS:
            paragraphs.append(_NARRATED_SUBHEADINGS[stripped])
            in_table_section = False
            in_narrated_section = True
            current_subheading = stripped
            continue

        # ── Sub-heading: table section (skip content) ───────────────────────
        if stripped in _TABLE_SUBHEADINGS:
            in_table_section = True
            in_narrated_section = False
            current_subheading = stripped
            continue

        # ── Per-repo #### heading — announce the repo name ──────────────────
        if stripped.startswith("#### `") and stripped.endswith("`"):
            repo_name = stripped.strip("#### `").strip("`")
            paragraphs.append(f"Repository: {repo_name}.")
            continue

        # ── Stat callout lines (_⭐ … _) — skip for audio ───────────────────
        if _STAT_LINE_RE.match(stripped):
            continue

        # ── Table rows — always skip ────────────────────────────────────────
        if stripped.startswith("|"):
            continue

        # ── Blurb lines (Why / What to learn) ───────────────────────────────
        if "Why it matters:" in stripped or "What to learn:" in stripped:
            clean = _strip_markdown(stripped)
            if clean:
                paragraphs.append(clean)
            continue

        # ── Skip footer, auto-generated notice, metadata ────────────────────
        if (
            "Pipeline source" in stripped
            or "update-radar.yml" in stripped
            or stripped.startswith("> Auto-generated")
            or stripped.startswith("_Updated:")
        ):
            continue

        # ── Prose content in narrated sections ──────────────────────────────
        if in_narrated_section and stripped and not stripped.startswith("#"):
            clean = _strip_markdown(stripped)
            if clean:
                paragraphs.append(clean)
            continue

        # ── Action items bullet points ───────────────────────────────────────
        if current_subheading == "### ✅ Action Items This Week" and stripped.startswith("- "):
            clean = _strip_markdown(stripped.lstrip("- ").strip())
            if clean:
                paragraphs.append(clean)
            continue

    return [p for p in paragraphs if p.strip()]


def readme_to_narration(readme_content: str) -> str:
    """Convert README markdown content to a clean spoken-word script.

    Returns a plain string suitable for passing directly to a TTS API.
    """
    sections = _extract_sections(readme_content)
    return "\n\n".join(sections)
