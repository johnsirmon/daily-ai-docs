"""Update README.md with latest GitHub release info for tracked AI projects.

Usage:
    python update_readme.py           # update README.md in place
    python update_readme.py --dry-run # preview without writing
"""

import argparse
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

README_PATH = Path(__file__).parent / "README.md"

SECTION_START = "<!-- LATEST-UPDATES-START -->"
SECTION_END = "<!-- LATEST-UPDATES-END -->"

# Repositories to check for new releases (owner, repo, friendly label)
TRACKED_REPOS = [
    ("microsoft", "vscode-copilot-release", "GitHub Copilot"),
    ("github", "github-mcp-server", "GitHub MCP Server"),
    ("modelcontextprotocol", "servers", "MCP Servers"),
    ("modelcontextprotocol", "specification", "MCP Specification"),
    ("microsoft", "vscode", "VS Code"),
    ("openai", "openai-python", "OpenAI Python SDK"),
    ("anthropics", "anthropic-sdk-python", "Anthropic Python SDK"),
    ("BerriAI", "litellm", "LiteLLM"),
]

GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    return {"Accept": "application/vnd.github+json"}


def fetch_latest_release(owner: str, repo: str) -> dict | None:
    """Return the latest GitHub release dict or None on error."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/latest"
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            return None  # repo has no releases yet
        # Log unexpected status codes but still return None gracefully
        print(f"  ⚠ {owner}/{repo}: HTTP {resp.status_code}")
    except requests.RequestException as exc:
        print(f"  ⚠ {owner}/{repo}: {exc}")
    return None


def _format_date(iso_str: str) -> str:
    """Return a short YYYY-MM-DD string from an ISO-8601 timestamp."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return iso_str[:10]


def build_section(releases: list) -> str:
    """Build the markdown block that goes between the sentinel markers."""
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "## 🆕 Latest AI Updates",
        "",
        f"> Auto-updated {now} · [source repos]({GITHUB_API})",
        "",
        "| Project | Latest Release | Date | Notes |",
        "|---------|---------------|------|-------|",
    ]

    for label, release in releases:
        if release is None:
            lines.append(f"| {label} | — | — | No release found |")
        else:
            tag = release.get("tag_name", "—")
            date = _format_date(release.get("published_at", ""))
            url = release.get("html_url", "#")
            # Keep the note short: first sentence of the release body, capped at 80 chars
            body = re.sub(r"\s+", " ", (release.get("body") or "").strip())
            note = (body[:80] + "…") if len(body) > 80 else body
            note = note or "—"
            lines.append(f"| {label} | [{tag}]({url}) | {date} | {note} |")

    return "\n".join(lines) + "\n"


def update_readme(section_text: str, readme_path: Path, dry_run: bool) -> None:
    """Replace the sentinel block in the README with *section_text*."""
    content = readme_path.read_text(encoding="utf-8")

    pattern = re.compile(
        rf"{re.escape(SECTION_START)}.*?{re.escape(SECTION_END)}",
        re.DOTALL,
    )

    replacement = f"{SECTION_START}\n{section_text}{SECTION_END}"

    if pattern.search(content):
        new_content = pattern.sub(replacement, content)
    else:
        # Sentinels not present — insert after the first blank line following line 1
        first_newline = content.find("\n")
        insert_at = first_newline + 1 if first_newline != -1 else 0
        new_content = (
            content[:insert_at]
            + f"\n{SECTION_START}\n{section_text}{SECTION_END}\n\n"
            + content[insert_at:]
        )

    if dry_run:
        print("=== DRY RUN — README would be updated as follows ===")
        print(new_content)
        return

    if new_content == content:
        print("✅ README already up to date — no changes written.")
        return

    readme_path.write_text(new_content, encoding="utf-8")
    print(f"✅ README updated: {readme_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update README with latest AI releases")
    parser.add_argument("--dry-run", action="store_true", help="Print output; do not write")
    parser.add_argument("--readme", default=str(README_PATH), help="Path to README.md")
    args = parser.parse_args()

    readme_path = Path(args.readme)

    print("Fetching latest releases…")
    releases = []
    for owner, repo, label in TRACKED_REPOS:
        release = fetch_latest_release(owner, repo)
        status = release.get("tag_name", "unknown") if release else "not found"
        print(f"  {label}: {status}")
        releases.append((label, release))

    section_text = build_section(releases)
    update_readme(section_text, readme_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
