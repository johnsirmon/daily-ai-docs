"""Convert a README.md string into a clean spoken-word script for TTS.

Strips markdown tables, link syntax, and decorators; retains topic headings
and AI-generated blurbs (Why / What to learn) which are the meaningful content.
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


def _extract_sections(readme: str) -> List[str]:
    """Return a list of spoken paragraphs from README content.

    Keeps:
    - The date heading (## AI Skills Radar — YYYY-MM-DD)
    - Per-topic headings (## Topic Name)
    - "Why it matters" and "What to learn" blurbs

    Skips:
    - The Topics TOC list
    - New & Rising Repos / Recent Releases tables
    - Footer links
    """
    paragraphs: List[str] = []
    current_topic: str = ""
    in_toc = False
    skip_next_table = False

    for line in readme.splitlines():
        stripped = line.strip()

        # Top-level date heading
        if stripped.startswith("# AI Skills Radar"):
            date_part = stripped.lstrip("# ").strip()
            paragraphs.append(f"AI Skills Radar. {date_part}.")
            continue

        # "## Topics" block — skip until we hit a real topic heading
        if stripped == "## Topics":
            in_toc = True
            continue
        if in_toc:
            if stripped.startswith("## ") and stripped != "## Topics":
                in_toc = False
            else:
                continue

        # Topic section headings
        if stripped.startswith("## ") and not stripped.startswith("## Topics"):
            current_topic = stripped.lstrip("# ").strip()
            paragraphs.append(current_topic + ".")
            skip_next_table = False
            continue

        # Sub-headings like "### New & Rising Repos" — skip, signal table follows
        if stripped.startswith("### "):
            skip_next_table = True
            continue

        # Skip table rows
        if stripped.startswith("|"):
            continue

        # Blurb lines: "**Why it matters:**" and "**What to learn:**"
        if "Why it matters:" in stripped or "What to learn:" in stripped:
            clean = _strip_markdown(stripped)
            if clean:
                paragraphs.append(clean)
            skip_next_table = False
            continue

        # Skip footer / pipeline-source line
        if "Pipeline source" in stripped or "update-radar.yml" in stripped:
            continue

        # Skip the auto-generated notice line
        if stripped.startswith("> Auto-generated"):
            continue

        # Skip _Updated:_ metadata line
        if stripped.startswith("_Updated:"):
            continue

    return [p for p in paragraphs if p.strip()]


def readme_to_narration(readme_content: str) -> str:
    """Convert README markdown content to a clean spoken-word script.

    Returns a plain string suitable for passing directly to a TTS API.
    """
    sections = _extract_sections(readme_content)
    return "\n\n".join(sections)
