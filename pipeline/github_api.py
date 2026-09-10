"""Shared helpers for GitHub REST API access."""

import os


GITHUB_API = "https://api.github.com"


def build_github_headers() -> dict[str, str]:
    """Return standard GitHub REST API headers with optional auth."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers