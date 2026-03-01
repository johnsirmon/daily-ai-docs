"""Render the README.md from collected pipeline data."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def _trend_emoji(trend: str) -> str:
    return {"rising": "📈", "falling": "📉", "flat": "➡️"}.get(trend, "")


def render_readme(topics_data: List[Dict], lookback_days: int = 14) -> str:
    """Build the full README content string from processed topic data."""
    now = datetime.now(tz=timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    generated = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: List[str] = [
        f"# AI Skills Radar — {date_str}",
        "",
        f"_Updated: {generated} | Covers last {lookback_days} days_",
        "",
        "> Auto-generated. To refresh, go to **Actions → Update AI Skills Radar → Run workflow**.",
        "",
        "## Topics",
        "",
    ]

    # TOC
    for t in topics_data:
        anchor = t["id"]
        lines.append(f"- [{t['display']}](#{anchor})")
    lines += ["", "---", ""]

    # Per-topic sections
    for t in topics_data:
        lines.append(f"## {t['display']}")
        lines.append("")

        repos = [r for r in t.get("items", []) if r["type"] == "trending"]
        releases = [r for r in t.get("items", []) if r["type"] == "release"]
        deep_dives: List[Dict] = t.get("deep_dives", [])  # list of {repo, prose}
        action_items: List[str] = t.get("action_items", [])
        community_pulse: str = t.get("community_pulse", "")

        # --- Why / Learn header ---
        if t.get("why"):
            lines += [
                f"> **Why it matters:** {t['why']}",
                ">",
                f"> **What to learn:** {t['learn']}",
                "",
            ]

        # --- Overview narrative ---
        if t.get("summary"):
            lines += ["### Overview", "", t["summary"], ""]

        # --- Repo Deep Dives ---
        if deep_dives:
            lines += ["### 🔍 Repo Deep Dives", ""]
            for dd in deep_dives:
                repo_name = dd.get("repo", "")
                prose = dd.get("prose", "")
                # Find matching stats from repos list
                stats = next((r for r in repos if r["repo"] == repo_name), {})
                lines.append(f"#### `{repo_name}`")
                lines.append("")
                if stats:
                    trend = stats.get("commit_trend", "")
                    trend_icon = _trend_emoji(trend)
                    stat_parts = [f"⭐ {stats.get('stars', 0):,}"]
                    if stats.get("language"):
                        stat_parts.append(stats["language"])
                    if stats.get("forks"):
                        stat_parts.append(f"{stats['forks']:,} forks")
                    if stats.get("open_issues") is not None:
                        stat_parts.append(f"{stats['open_issues']} issues")
                    if stats.get("prs_merged_14d"):
                        stat_parts.append(f"{stats['prs_merged_14d']} PRs merged")
                    if trend:
                        stat_parts.append(f"{trend_icon} {trend}")
                    lines.append(f"_{' · '.join(stat_parts)}_")
                    lines.append("")
                if prose:
                    lines += [prose, ""]

        # --- Community Pulse ---
        if community_pulse:
            lines += ["### 📊 Community Pulse", "", community_pulse, ""]

        # --- Action Items ---
        if action_items:
            lines += ["### ✅ Action Items This Week", ""]
            for item in action_items:
                lines.append(f"- {item}")
            lines.append("")

        # --- Quick Reference table ---
        if repos:
            lines += [
                "### 🌱 New & Rising Repos",
                "",
                "| Repo | Stars | Forks | Issues | Language | Trend |",
                "|------|-------|-------|--------|----------|-------|",
            ]
            for r in repos:
                trend = r.get("commit_trend", "")
                trend_icon = _trend_emoji(trend)
                desc = (r.get("description") or "—").replace("|", "\\|")
                lines.append(
                    f"| [{r['repo']}]({r['url']}) "
                    f"| ⭐ {r['stars']:,} "
                    f"| {r.get('forks', '—')} "
                    f"| {r.get('open_issues', '—')} "
                    f"| {r.get('language') or '—'} "
                    f"| {trend_icon} {trend} |"
                )
            lines.append("")

        # --- Releases table ---
        if releases:
            lines += [
                "### 🚀 Recent Releases",
                "",
                "| Repo | Version | Date | Highlights |",
                "|------|---------|------|------------|",
            ]
            for r in releases:
                highlights = (r.get("notes") or "—")[:120].replace("\n", " ").replace("|", "\\|")
                reactions = r.get("reactions", 0)
                react_str = f" ({reactions} 👍)" if reactions else ""
                lines.append(
                    f"| [{r['repo']}]({r['url']}) "
                    f"| `{r['version']}` "
                    f"| {r['published_at']}{react_str} "
                    f"| {highlights} |"
                )
            lines.append("")

        if not repos and not releases:
            lines += ["_No recent activity detected._", ""]

        lines += ["---", ""]

    lines.append(
        "_[Pipeline source](.github/workflows/update-radar.yml) · "
        "[Config](topics/topics.yaml)_"
    )

    return "\n".join(lines) + "\n"


def write_readme(
    topics_data: List[Dict],
    lookback_days: int = 14,
    path: str = "README.md",
) -> Path:
    """Write rendered README.md and return its Path."""
    content = render_readme(topics_data, lookback_days)
    out = Path(path)
    out.write_text(content, encoding="utf-8")
    return out
