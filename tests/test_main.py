"""Tests for pipeline/main.py CLI entry point."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline.main import main, _publish_podcast, _NARRATION_RAW_PATH, _NARRATION_POLISHED_PATH


def _write_readme(directory: str, content: str = "# AI Skills Radar\nSome content.") -> Path:
    p = Path(directory) / "README.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_podcast_only_calls_publish_podcast(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_readme(str(tmp_path))

    with patch("pipeline.main._publish_podcast") as mock_pub, \
         patch("pipeline.main.run") as mock_run:
        mock_run.return_value = (tmp_path / "README.md", {})
        monkeypatch.setattr("sys.argv", ["pipeline.main", "--podcast-only"])
        main()

    mock_pub.assert_called_once()
    mock_run.assert_not_called()


def test_podcast_only_dry_run_passes_flag(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_readme(str(tmp_path))

    with patch("pipeline.main._publish_podcast") as mock_pub, \
         patch("pipeline.main.run") as mock_run:
        mock_run.return_value = (tmp_path / "README.md", {})
        monkeypatch.setattr("sys.argv", ["pipeline.main", "--podcast-only", "--dry-run"])
        main()

    _, kwargs = mock_pub.call_args
    assert kwargs.get("dry_run") is True or mock_pub.call_args[0][1] is True


def test_podcast_only_missing_readme_exits(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # No README.md created

    with patch("pipeline.main._publish_podcast"), \
         patch("pipeline.main.run") as mock_run:
        mock_run.return_value = (tmp_path / "README.md", {})
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
        return tmp_path / "README.md", {}

    with patch("pipeline.main._publish_podcast"), \
         patch("pipeline.main.run", side_effect=fake_run):
        monkeypatch.setattr("sys.argv", ["pipeline.main", "--podcast-only"])
        main()

    assert not run_called


# ── Narration script persistence tests ──────────────────────────────────────


def test_publish_podcast_writes_raw_narration(monkeypatch, tmp_path):
    """_publish_podcast always persists the raw narration to .cache/narration_script.txt."""
    monkeypatch.chdir(tmp_path)
    readme = _write_readme(str(tmp_path), "# AI Skills Radar — 2026-03-01\nContent here.")

    raw_path = tmp_path / ".cache" / "narration_script.txt"
    monkeypatch.setattr("pipeline.main._NARRATION_RAW_PATH", raw_path)
    monkeypatch.setattr("pipeline.main._NARRATION_POLISHED_PATH", tmp_path / ".cache" / "polished.txt")

    with patch("pipeline.main.write_audio", return_value=None), \
         patch("pipeline.main.prepend_episode"):
        _publish_podcast(readme, dry_run=True, mp3_url_template="http://x/{tag}/r.mp3")

    assert raw_path.exists()
    assert len(raw_path.read_text(encoding="utf-8")) > 0


def test_publish_podcast_uses_polished_when_present(monkeypatch, tmp_path):
    """When .cache/narration_polished.txt exists, TTS receives the polished script."""
    monkeypatch.chdir(tmp_path)
    readme = _write_readme(str(tmp_path))

    raw_path = tmp_path / ".cache" / "narration_script.txt"
    polished_path = tmp_path / ".cache" / "narration_polished.txt"
    polished_path.parent.mkdir(parents=True, exist_ok=True)
    polished_path.write_text("Polished narration text.", encoding="utf-8")

    monkeypatch.setattr("pipeline.main._NARRATION_RAW_PATH", raw_path)
    monkeypatch.setattr("pipeline.main._NARRATION_POLISHED_PATH", polished_path)

    captured_scripts = []

    def fake_write_audio(text, path="radar.mp3"):
        captured_scripts.append(text)
        return None

    with patch("pipeline.main.write_audio", side_effect=fake_write_audio), \
         patch("pipeline.main.prepend_episode"):
        _publish_podcast(readme, dry_run=False, mp3_url_template="http://x/{tag}/r.mp3")

    assert captured_scripts[0] == "Polished narration text."


def test_publish_podcast_falls_back_to_raw(monkeypatch, tmp_path):
    """When no polished file exists, TTS receives the raw narration."""
    monkeypatch.chdir(tmp_path)
    readme = _write_readme(str(tmp_path), "# AI Skills Radar — 2026-03-01\nContent.")

    raw_path = tmp_path / ".cache" / "narration_script.txt"
    polished_path = tmp_path / ".cache" / "narration_polished.txt"

    monkeypatch.setattr("pipeline.main._NARRATION_RAW_PATH", raw_path)
    monkeypatch.setattr("pipeline.main._NARRATION_POLISHED_PATH", polished_path)

    captured_scripts = []

    def fake_write_audio(text, path="radar.mp3"):
        captured_scripts.append(text)
        return None

    with patch("pipeline.main.write_audio", side_effect=fake_write_audio), \
         patch("pipeline.main.prepend_episode"):
        _publish_podcast(readme, dry_run=False, mp3_url_template="http://x/{tag}/r.mp3")

    # Should have used the raw narration (not empty, not polished)
    assert len(captured_scripts) == 1
    assert "Polished" not in captured_scripts[0]


def test_narrate_only_stops_before_tts(monkeypatch, tmp_path):
    """--narrate-only writes narration_script.txt but does not call write_audio or prepend_episode."""
    monkeypatch.chdir(tmp_path)
    readme = _write_readme(str(tmp_path), "# AI Skills Radar — 2026-03-01\nContent.")

    raw_path = tmp_path / ".cache" / "narration_script.txt"
    monkeypatch.setattr("pipeline.main._NARRATION_RAW_PATH", raw_path)
    monkeypatch.setattr("pipeline.main._NARRATION_POLISHED_PATH", tmp_path / ".cache" / "polished.txt")

    with patch("pipeline.main.write_audio") as mock_audio, \
         patch("pipeline.main.prepend_episode") as mock_episode:
        _publish_podcast(readme, dry_run=False, mp3_url_template="http://x/{tag}/r.mp3",
                         narrate_only=True)

    assert raw_path.exists()
    mock_audio.assert_not_called()
    mock_episode.assert_not_called()


def test_narrate_only_cli_triggers_publish_podcast(monkeypatch, tmp_path):
    """The --narrate-only flag triggers _publish_podcast even without --podcast."""
    monkeypatch.chdir(tmp_path)

    with patch("pipeline.main._publish_podcast") as mock_pub, \
         patch("pipeline.main.run") as mock_run:
        mock_run.return_value = (tmp_path / "README.md", {"narrative_hook": ""})
        monkeypatch.setattr("sys.argv", ["pipeline.main", "--narrate-only", "--dry-run"])
        main()

    mock_pub.assert_called_once()
    _, kwargs = mock_pub.call_args
    assert kwargs.get("narrate_only") is True
