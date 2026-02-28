"""Tests for the update_readme.py script."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from update_readme import (
    SECTION_END,
    SECTION_START,
    _format_date,
    build_section,
    fetch_latest_release,
    update_readme,
)


# ---------------------------------------------------------------------------
# _format_date
# ---------------------------------------------------------------------------

def test_format_date_iso_with_z():
    assert _format_date("2026-02-15T12:34:56Z") == "2026-02-15"


def test_format_date_iso_with_offset():
    assert _format_date("2026-02-15T12:34:56+00:00") == "2026-02-15"


def test_format_date_short_string():
    # Falls back to first 10 chars when parsing fails
    assert _format_date("2026-02-15") == "2026-02-15"


def test_format_date_empty():
    assert _format_date("") == ""


# ---------------------------------------------------------------------------
# build_section
# ---------------------------------------------------------------------------

def test_build_section_contains_table_header():
    section = build_section([])
    assert "| Project |" in section
    assert "| Latest Release |" in section


def test_build_section_none_release_shows_dash():
    releases = [("My SDK", None)]
    section = build_section(releases)
    assert "| My SDK | — | — | No release found |" in section


def test_build_section_with_release_shows_tag_and_date():
    release = {
        "tag_name": "v1.2.3",
        "published_at": "2026-01-10T08:00:00Z",
        "html_url": "https://github.com/org/repo/releases/tag/v1.2.3",
        "body": "Bug fixes.",
    }
    releases = [("Test SDK", release)]
    section = build_section(releases)
    assert "v1.2.3" in section
    assert "2026-01-10" in section
    assert "Bug fixes." in section


def test_build_section_truncates_long_body():
    long_body = "A" * 100
    release = {
        "tag_name": "v1.0",
        "published_at": "2026-01-01T00:00:00Z",
        "html_url": "#",
        "body": long_body,
    }
    releases = [("SDK", release)]
    section = build_section(releases)
    assert "…" in section


def test_build_section_empty_body_shows_dash():
    release = {
        "tag_name": "v2.0",
        "published_at": "2026-01-01T00:00:00Z",
        "html_url": "#",
        "body": "",
    }
    releases = [("SDK", release)]
    section = build_section(releases)
    assert "| SDK | [v2.0](#) | 2026-01-01 | — |" in section


# ---------------------------------------------------------------------------
# update_readme — sentinel replacement
# ---------------------------------------------------------------------------

README_WITH_SENTINELS = (
    "# My Repo\n\n"
    f"{SECTION_START}\n"
    "## 🆕 Old content\n"
    f"{SECTION_END}\n\n"
    "## Other section\n"
)

README_WITHOUT_SENTINELS = "# My Repo\n\nSome content.\n"


def test_update_readme_replaces_existing_sentinel(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(README_WITH_SENTINELS, encoding="utf-8")

    update_readme("## New content\n", readme, dry_run=False)

    result = readme.read_text(encoding="utf-8")
    assert "## New content" in result
    assert "## 🆕 Old content" not in result
    assert SECTION_START in result
    assert SECTION_END in result


def test_update_readme_inserts_sentinels_when_missing(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(README_WITHOUT_SENTINELS, encoding="utf-8")

    update_readme("## Inserted content\n", readme, dry_run=False)

    result = readme.read_text(encoding="utf-8")
    assert SECTION_START in result
    assert SECTION_END in result
    assert "## Inserted content" in result


def test_update_readme_dry_run_does_not_write(tmp_path, capsys):
    readme = tmp_path / "README.md"
    readme.write_text(README_WITH_SENTINELS, encoding="utf-8")

    update_readme("## New content\n", readme, dry_run=True)

    # File should be unchanged
    assert readme.read_text(encoding="utf-8") == README_WITH_SENTINELS
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out


def test_update_readme_no_change_skips_write(tmp_path, capsys):
    section = "## 🆕 Latest\n"
    content = f"{SECTION_START}\n{section}{SECTION_END}\n"
    readme = tmp_path / "README.md"
    readme.write_text(content, encoding="utf-8")

    update_readme(section, readme, dry_run=False)

    captured = capsys.readouterr()
    assert "already up to date" in captured.out


# ---------------------------------------------------------------------------
# fetch_latest_release — error handling
# ---------------------------------------------------------------------------

def test_fetch_latest_release_returns_dict_on_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"tag_name": "v1.0.0"}

    with patch("update_readme.requests.get", return_value=mock_resp):
        result = fetch_latest_release("org", "repo")

    assert result == {"tag_name": "v1.0.0"}


def test_fetch_latest_release_returns_none_on_404():
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("update_readme.requests.get", return_value=mock_resp):
        result = fetch_latest_release("org", "repo")

    assert result is None


def test_fetch_latest_release_returns_none_on_request_exception():
    import requests as req

    with patch("update_readme.requests.get", side_effect=req.RequestException("timeout")):
        result = fetch_latest_release("org", "repo")

    assert result is None


def test_fetch_latest_release_returns_none_on_unexpected_status(capsys):
    mock_resp = MagicMock()
    mock_resp.status_code = 403

    with patch("update_readme.requests.get", return_value=mock_resp):
        result = fetch_latest_release("org", "repo")

    assert result is None
    captured = capsys.readouterr()
    assert "403" in captured.out
