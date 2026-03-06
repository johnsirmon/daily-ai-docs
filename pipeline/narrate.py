"""Convert README markdown into a spoken-word podcast script for TTS.

Retains topic headings, blurbs, deep-dive prose, and selected table signals
(repo momentum + release highlights) so audio episodes stay concrete and
compelling without reading raw markdown artifacts aloud.
"""

import re
from typing import List

# Rotating spoken phrases for topic and repo transitions (deterministic — index
# is incremented per call so repeated topics don't all sound identical).
_TOPIC_TRANSITIONS = [
    "Now let's look at {name}.",
    "Moving on to {name}.",
    "Let's turn to {name}.",
    "Next up: {name}.",
    "Time for {name}.",
    "Let's shift to {name}.",
]
_REPO_INTRODUCTIONS = [
    "Let's dive into {repo}.",
    "Up next is {repo}.",
    "Here's a closer look at {repo}.",
    "Now let's talk about {repo}.",
]

# Counters for rotation (module-level so they survive within a single run).
_topic_idx = 0
_repo_idx = 0


def _next_topic_phrase(name: str) -> str:
    global _topic_idx
    phrase = _TOPIC_TRANSITIONS[_topic_idx % len(_TOPIC_TRANSITIONS)].format(name=name)
    _topic_idx += 1
    return phrase


def _next_repo_phrase(repo: str) -> str:
    global _repo_idx
    # Convert "owner/repo" → "repo by owner" for natural TTS pronunciation.
    if "/" in repo:
        owner, _, name = repo.partition("/")
        spoken = f"{name} by {owner}"
    else:
        spoken = repo
    phrase = _REPO_INTRODUCTIONS[_repo_idx % len(_REPO_INTRODUCTIONS)].format(repo=spoken)
    _repo_idx += 1
    return phrase


def _normalise_sentence(s: str) -> str:
    """Capitalise first character and ensure the sentence ends with punctuation."""
    s = s.strip()
    if not s:
        return s
    s = s[0].upper() + s[1:]
    if s[-1] not in ".!?":
        s += "."
    return s


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


# Sub-headings to include as spoken transitions (more conversational phrasing)
_NARRATED_SUBHEADINGS = {
    "### Overview": "Here's the overview.",
    "### 🔍 Repo Deep Dives": "Let's go deeper on a few repositories.",
    "### 📊 Community Pulse": "Here's what the community has been up to.",
    "### ✅ Action Items This Week": "Here are your action items for the week.",
    "### 🚀 Recent Releases": "And here are some notable recent releases.",
}

# Sub-headings that introduce tables we should skip prose under
_TABLE_SUBHEADINGS = {"### 🌱 New & Rising Repos", "### 📋 Quick Reference"}

# Stat callout lines emitted by render.py under each #### repo heading
_STAT_LINE_RE = re.compile(r"^_[⭐📈📉➡️].*_$")


def _table_cells(line: str) -> List[str]:
    """Split a markdown table row into cell values."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _parse_repo_from_cell(cell: str) -> str:
    """Extract repo text from markdown link cell."""
    m = re.match(r"\[([^\]]+)\]\([^)]*\)", cell)
    return m.group(1).strip() if m else cell.strip()


def _parse_int_cell(cell: str) -> int | None:
    """Parse integer-like markdown table cell values (e.g. ⭐ 1,234, 42, —)."""
    digits = re.sub(r"[^\d]", "", cell or "")
    return int(digits) if digits else None


def _repo_row_to_spoken(row: str) -> List[str]:
    """Convert a New & Rising Repos table row into spoken narration lines."""
    cells = _table_cells(row)
    if len(cells) < 3:
        return []

    repo = _parse_repo_from_cell(cells[0])
    if not repo or repo.lower() == "repo":
        return []

    stars = _parse_int_cell(cells[1]) if len(cells) > 1 else None
    forks = _parse_int_cell(cells[2]) if len(cells) > 2 else None
    issues = _parse_int_cell(cells[3]) if len(cells) > 3 else None
    language = cells[4] if len(cells) > 4 and cells[4] not in {"—", ""} else ""
    trend_cell = (cells[5] if len(cells) > 5 else "").lower()

    lines = [_next_repo_phrase(repo)]
    details = []
    if stars is not None:
        details.append(f"it's sitting at about {stars:,} stars")
    if forks is not None:
        details.append(f"{forks:,} forks")
    if issues is not None:
        details.append(f"{issues} open issues")
    if language:
        details.append(f"primarily {language}")

    if details:
        lines.append(_normalise_sentence("Right now " + ", ".join(details)))

    if "rising" in trend_cell:
        lines.append("Commit momentum is rising, which usually signals growing real-world usage.")
    elif "falling" in trend_cell:
        lines.append("Commit momentum has cooled recently, so it's worth checking whether activity is shifting elsewhere.")
    elif "flat" in trend_cell:
        lines.append("Commit momentum looks steady, which can indicate a stable phase for adopters.")

    return lines


def _release_row_to_spoken(row: str) -> str:
    """Convert a Recent Releases table row into a short spoken update."""
    cells = _table_cells(row)
    if len(cells) < 4:
        return ""

    repo = _parse_repo_from_cell(cells[0])
    version = cells[1].strip("` ")
    date = cells[2]
    highlights = _strip_markdown(cells[3])
    if not repo or repo.lower() == "repo":
        return ""

    sentence = f"{repo} shipped {version} on {date}"
    if highlights and highlights not in {"—", "-"}:
        sentence += f", with highlights including {highlights[:180]}"
    return _normalise_sentence(sentence)


def build_cold_open(research_report: dict | None) -> str:
    """Return a 1-2 sentence spoken cold-open from the research report's narrative_hook.

    Falls back to a generic opening if the hook is empty or report is None.
    """
    hook = (research_report or {}).get("narrative_hook", "").strip()
    if not hook:
        hook = "This week in AI, there's a lot to cover across the ecosystem."
    return _normalise_sentence(hook)


def build_closing() -> str:
    """Return a standard podcast sign-off sentence."""
    return (
        "That's your AI Skills Radar for the week. "
        "Check the README for the full breakdown, links, and this week's action items. "
        "See you next week."
    )


def _extract_sections(readme: str) -> List[str]:
    """Return a list of spoken paragraphs from README content.

    Keeps:
    - The date heading
    - Per-topic headings
    - Why/Learn blurbs
    - Overview narrative paragraphs
    - Repo deep-dive prose (prose paragraphs, skipping stat callout lines)
    - Repo context synthesized from "New & Rising Repos" table rows
    - Community Pulse paragraphs
    - Action Items bullet text
    - Release context synthesized from "Recent Releases" table rows

    Skips:
    - TOC list
    - Raw table rows (converted to spoken summaries instead)
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
            paragraphs.append(_next_topic_phrase(topic_name))
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
            paragraphs.append(_next_repo_phrase(repo_name))
            continue

        # ── Stat callout lines (_⭐ … _) — skip for audio ───────────────────
        if _STAT_LINE_RE.match(stripped):
            continue

        # ── Table rows — narrate selected rows for richer podcast context ───
        if stripped.startswith("|"):
            if set(stripped.replace("|", "").strip()) <= {"-", ":"}:
                continue
            if current_subheading == "### 🌱 New & Rising Repos":
                paragraphs.extend(_repo_row_to_spoken(stripped))
                continue
            if current_subheading == "### 🚀 Recent Releases":
                spoken = _release_row_to_spoken(stripped)
                if spoken:
                    paragraphs.append(spoken)
                continue
            continue

        # ── Blurb lines (Why / What to learn) ───────────────────────────────
        if "Why it matters:" in stripped or "What to learn:" in stripped:
            clean = _strip_markdown(stripped)
            # Replace written-word labels with conversational spoken bridges.
            clean = re.sub(
                r"Why it matters:\s*",
                "Here's why this matters. ",
                clean,
                flags=re.IGNORECASE,
            )
            clean = re.sub(
                r"What to learn:\s*",
                "Here's what to focus on learning. ",
                clean,
                flags=re.IGNORECASE,
            )
            clean = _normalise_sentence(clean)
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
            clean = _normalise_sentence(_strip_markdown(stripped))
            if clean:
                paragraphs.append(clean)
            continue

        # ── Action items bullet points ───────────────────────────────────────
        if current_subheading == "### ✅ Action Items This Week" and stripped.startswith("- "):
            clean = _normalise_sentence(_strip_markdown(stripped.lstrip("- ").strip()))
            if clean:
                paragraphs.append(clean)
            continue

    return [p for p in paragraphs if p.strip()]


def readme_to_narration(readme_content: str, research_report: dict | None = None) -> str:
    """Convert README markdown content to a clean spoken-word script.

    If research_report is provided, prepends a cold open and appends a closing.
    Returns a plain string suitable for passing directly to a TTS API.
    """
    sections = _extract_sections(readme_content)
    if research_report is not None:
        sections = [build_cold_open(research_report)] + sections + [build_closing()]
    return "\n\n".join(sections)
