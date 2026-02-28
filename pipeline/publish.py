"""Publish ranked, enriched items to markdown reports and data files."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

# Emoji labels by source type for narrative output
_SOURCE_EMOJI = {
    "github_release": "🚀",
    "rss": "📰",
}
_DEFAULT_EMOJI = "📌"


# ---------------------------------------------------------------------------
# Enrichment helpers
# ---------------------------------------------------------------------------

def _why_it_matters(item: Dict, topics_config: List[Dict]) -> str:
    topic_map = {t["id"]: t for t in topics_config}
    for tid in item.get("topics", []):
        tpl = topic_map.get(tid, {}).get("why_matters_template", "")
        if tpl:
            return tpl
    src_type = item.get("source_type", "")
    if "release" in src_type:
        return "New release detected — review for breaking changes or new capabilities."
    if "rss" in src_type:
        return "Official announcement — may signal an upcoming feature or deprecation."
    return "Monitor for downstream impact on your AI stack."


def _action(item: Dict, topics_config: List[Dict]) -> str:
    topic_map = {t["id"]: t for t in topics_config}
    for tid in item.get("topics", []):
        tpl = topic_map.get(tid, {}).get("action_template", "")
        if tpl:
            return tpl
    src_type = item.get("source_type", "")
    if "release" in src_type:
        return "Review the release notes and update your integration if needed."
    return "Evaluate for impact; add to watchlist if actionable."


def enrich(items: List[Dict], topics_config: List[Dict]) -> List[Dict]:
    """Fill `why_it_matters` and `action` fields based on topic templates."""
    for item in items:
        if not item.get("why_it_matters"):
            item["why_it_matters"] = _why_it_matters(item, topics_config)
        if not item.get("action"):
            item["action"] = _action(item, topics_config)
    return items


# ---------------------------------------------------------------------------
# Markdown formatting helpers
# ---------------------------------------------------------------------------

def _fmt_item_md(item: Dict, idx: int) -> str:
    topics_str = ", ".join(item.get("topics", [])) or "—"
    snippet = (item.get("snippet") or "").strip()
    snippet_line = f"> {snippet[:200]}\n\n" if snippet else ""
    return (
        f"### {idx}. {item['title']}\n\n"
        f"- **Source:** {item['source']} (`{item['source_type']}`)\n"
        f"- **Published:** {item['published_at'][:10]}\n"
        f"- **Topics:** {topics_str}\n"
        f"- **Score:** {item['score']:.4f}\n"
        f"- **URL:** {item['url']}\n\n"
        f"{snippet_line}"
        f"**Why it matters:** {item['why_it_matters']}\n\n"
        f"**Action:** {item['action']}\n\n"
        "---\n\n"
    )


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_daily(items: List[Dict], date: str, out_dir: str = "reports/daily") -> Path:
    """Write the daily markdown report."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = Path(out_dir) / f"{date}.md"

    unique_topics = {t for i in items for t in i.get("topics", [])}
    unique_sources = {i["source"] for i in items}

    lines = [
        f"# Daily AI Intelligence Report — {date}\n",
        f"_Generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f" | Items: {len(items)}_\n",
        "## Summary\n",
        f"Tracking **{len(unique_topics)} topics** across **{len(unique_sources)} sources**.\n",
        "## Top Items\n",
    ]
    for idx, item in enumerate(items, 1):
        lines.append(_fmt_item_md(item, idx))

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_weekly(items: List[Dict], week: str, out_dir: str = "reports/weekly") -> Path:
    """Write the weekly markdown report grouped by topic."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = Path(out_dir) / f"{week}.md"

    topic_groups: Dict[str, List[Dict]] = {}
    for item in items:
        for t in item.get("topics", []):
            topic_groups.setdefault(t, []).append(item)

    lines = [
        f"# Weekly AI Intelligence Report — Week {week}\n",
        f"_Generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f" | Items: {len(items)}_\n",
        "## This Week by Topic\n",
    ]
    for topic_id, topic_items in sorted(topic_groups.items()):
        display = topic_id.replace("-", " ").title()
        lines.append(f"### {display}\n")
        for item in topic_items[:5]:
            lines.append(f"- [{item['title']}]({item['url']}) ({item['published_at'][:10]})")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_trends(items: List[Dict], trends_path: str = "data/trends.json") -> Path:
    """Update the rolling trends JSON with today's topic counts."""
    out_path = Path(trends_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    existing: Dict = {}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    today_counts: Dict[str, int] = {}
    for item in items:
        for t in item.get("topics", []):
            today_counts[t] = today_counts.get(t, 0) + 1

    topics_data: Dict = existing.get("topics", {})
    for topic_id, count in today_counts.items():
        if topic_id not in topics_data:
            topics_data[topic_id] = {"total_items": 0, "daily": {}}
        topics_data[topic_id].setdefault("daily", {})[today] = count
        # Recalculate total from the daily history so re-runs are idempotent
        topics_data[topic_id]["total_items"] = sum(topics_data[topic_id]["daily"].values())

    trends = {
        "last_updated": today,
        "schema_version": "1",
        "topics": topics_data,
    }
    out_path.write_text(json.dumps(trends, indent=2, sort_keys=True), encoding="utf-8")
    return out_path


def write_watchlist(
    items: List[Dict],
    threshold: float = 0.70,
    watchlist_path: str = "reports/watchlist.md",
) -> Path:
    """Write the high-signal watchlist markdown report."""
    Path(watchlist_path).parent.mkdir(parents=True, exist_ok=True)
    path = Path(watchlist_path)

    watch_items = [i for i in items if i.get("score", 0) >= threshold]

    lines = [
        "# AI Intelligence Watchlist\n",
        f"_Updated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f" | High-signal items (score ≥ {threshold})_\n",
        "Items that warrant immediate attention based on recency, source quality, and topic relevance.\n",
        "| Title | Source | Topics | Score | Date |",
        "|-------|--------|--------|-------|------|",
    ]
    for item in watch_items:
        title_link = f"[{item['title'][:60]}]({item['url']})"
        topics = ", ".join(item.get("topics", []))
        lines.append(
            f"| {title_link} | {item['source']} | {topics}"
            f" | {item['score']:.3f} | {item['published_at'][:10]} |"
        )

    if not watch_items:
        lines.append("| _No high-signal items today_ | — | — | — | — |")

    lines.extend([
        "",
        "---",
        "",
        "_Threshold and scoring weights are configurable in `topics/topics.yaml`._",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Narrative report
# ---------------------------------------------------------------------------

def _fmt_item_narrative(item: Dict, idx: int, collapse: bool = True) -> str:
    """Format a single item as a narrative block, optionally collapsible."""
    emoji = _SOURCE_EMOJI.get(item.get("source_type", ""), _DEFAULT_EMOJI)
    title = item["title"]
    url = item["url"]
    date = item["published_at"][:10]
    snippet = (item.get("snippet") or "").strip()
    snippet_text = f"\n\n> {snippet[:300]}" if snippet else ""
    why = item.get("why_it_matters", "")
    action = item.get("action", "")
    topics_str = ", ".join(item.get("topics", [])) or "—"

    detail_body = (
        f"{emoji} **[{title}]({url})**  \n"
        f"_{date} · {item['source']} · Topics: {topics_str}_"
        f"{snippet_text}\n\n"
        f"**Why it matters:** {why}\n\n"
        f"**Action:** {action}\n"
    )

    if not collapse:
        return detail_body + "\n---\n\n"

    # Wrap secondary items in a collapsible <details> block for mobile-friendly reading.
    summary_line = f"{emoji} {title} _{date}_"
    return (
        f"<details>\n<summary>{summary_line}</summary>\n\n"
        f"{detail_body}\n"
        "</details>\n\n"
    )


def write_narrative(
    items: List[Dict],
    date: str,
    out_dir: str = "reports/narrative",
) -> Path:
    """Write a human-readable narrative report optimised for mobile viewing.

    The first item is shown fully expanded; subsequent items are wrapped in
    HTML ``<details>`` collapsible blocks so the page stays short on small
    screens.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = Path(out_dir) / f"{date}.md"

    generated = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: List[str] = [
        f"# AI Updates — {date}\n",
        f"_Generated: {generated} | {len(items)} item(s)_\n",
        (
            "Tap any item below to expand. "
            "Top story is shown in full; the rest are collapsible.\n"
        ),
        "---\n",
    ]

    if not items:
        lines.append("_No updates to report for this date._\n")
    else:
        # First item: fully visible (no collapse)
        lines.append("## 🌟 Top Story\n")
        lines.append(_fmt_item_narrative(items[0], 1, collapse=False))

        if len(items) > 1:
            lines.append("## More Updates\n")
            for idx, item in enumerate(items[1:], 2):
                lines.append(_fmt_item_narrative(item, idx, collapse=True))

    lines.extend([
        "---\n",
        "_[View full daily report](../daily/) · "
        "[View watchlist](../watchlist.md) · "
        "[Pipeline config](../../topics/topics.yaml)_\n",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
