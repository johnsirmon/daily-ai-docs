"""Tests for pipeline/main.py CLI entry point."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline.main import main


def _write_readme(directory: str, content: str = "# AI Skills Radar\nSome content.") -> Path:
    p = Path(directory) / "README.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_podcast_only_calls_publish_podcast(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_readme(str(tmp_path))

    with patch("pipeline.main._publish_podcast") as mock_pub, \
         patch("pipeline.main.run") as mock_run:
        monkeypatch.setattr("sys.argv", ["pipeline.main", "--podcast-only"])
        main()

    mock_pub.assert_called_once()
    mock_run.assert_not_called()


def test_podcast_only_dry_run_passes_flag(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_readme(str(tmp_path))

    with patch("pipeline.main._publish_podcast") as mock_pub, \
         patch("pipeline.main.run"):
        monkeypatch.setattr("sys.argv", ["pipeline.main", "--podcast-only", "--dry-run"])
        main()

    _, kwargs = mock_pub.call_args
    assert kwargs.get("dry_run") is True or mock_pub.call_args[0][1] is True


def test_podcast_only_missing_readme_exits(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # No README.md created

    with patch("pipeline.main._publish_podcast"), \
         patch("pipeline.main.run"):
        monkeypatch.setattr("sys.argv", ["pipeline.main", "--podcast-only"])
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1


def test_podcast_only_skips_run(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_readme(str(tmp_path))

    run_called = []

    def fake_run(*args, **kwargs):
        run_called.append(True)
        return tmp_path / "README.md"

    with patch("pipeline.main._publish_podcast"), \
         patch("pipeline.main.run", side_effect=fake_run):
        monkeypatch.setattr("sys.argv", ["pipeline.main", "--podcast-only"])
        main()

    assert not run_called
