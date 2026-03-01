"""Render the README.md from collected pipeline data."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


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

        if t.get("why"):
            lines += [
                f"> **Why it matters:** {t['why']}",
                ">",
                f"> **What to learn:** {t['learn']}",
                "",
            ]

        repos = [r for r in t.get("items", []) if r["type"] == "trending"]
        releases = [r for r in t.get("items", []) if r["type"] == "release"]

        if repos:
            lines += [
                "### 🌱 New & Rising Repos",
                "",
                "| Repo | Stars | Description |",
                "|------|-------|-------------|",
            ]
            for r in repos:
                desc = (r["description"] or "—").replace("|", "\\|")
                lines.append(
                    f"| [{r['repo']}]({r['url']}) | ⭐ {r['stars']:,} | {desc} |"
                )
            lines.append("")

        if releases:
            lines += [
                "### 🚀 Recent Releases",
                "",
                "| Repo | Version | Date |",
                "|------|---------|------|",
            ]
            for r in releases:
                lines.append(
                    f"| [{r['repo']}]({r['url']}) | `{r['version']}` | {r['published_at']} |"
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
