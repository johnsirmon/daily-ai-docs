"""Tests for pipeline/podcast.py."""

import tempfile
from pathlib import Path

from pipeline.podcast import render_feed, load_episodes, write_feed, prepend_episode


def _ep(n: int = 1) -> dict:
    return {
        "title": f"AI Skills Weekly — 2026-03-0{n}",
        "guid": f"radar-2026-03-0{n}",
        "mp3_url": f"https://github.com/owner/repo/releases/download/radar-2026-03-0{n}/radar.mp3",
        "pub_date": f"2026-03-0{n}",
        "duration_secs": 300,
        "file_size_bytes": 1024000,
        "description": f"Episode {n} description.",
    }


def test_render_feed_contains_rss_root():
    xml = render_feed([])
    assert "<rss" in xml
    assert 'version="2.0"' in xml


def test_render_feed_contains_channel_title():
    xml = render_feed([])
    assert "Daily AI Developer Brief" in xml


def test_render_feed_single_episode():
    xml = render_feed([_ep(1)])
    assert "2026-03-01" in xml
    assert "radar-2026-03-01" in xml
    assert "radar.mp3" in xml


def test_render_feed_episode_enclosure():
    xml = render_feed([_ep(1)])
    assert "enclosure" in xml
    assert "audio/mpeg" in xml


def test_render_feed_declares_content_namespace_and_migration_url(monkeypatch):
    monkeypatch.setenv("PODCAST_MIGRATE_FEED", "1")
    xml = render_feed([_ep(1)])
    assert "xmlns:content=" in xml
    assert "content:encoded" in xml
    assert "itunes:new-feed-url" in xml
    assert "johnsirmon.github.io/daily-ai-docs/podcast.xml" in xml


def test_feed_migration_is_absent_until_destination_is_provisioned(monkeypatch):
    monkeypatch.delenv("PODCAST_MIGRATE_FEED", raising=False)
    assert "itunes:new-feed-url" not in render_feed([_ep(1)])


def test_render_feed_itunes_duration():
    xml = render_feed([_ep(1)])
    assert "itunes" in xml
    assert "5:00" in xml  # 300 seconds = 5:00


def test_render_feed_multiple_episodes():
    xml = render_feed([_ep(1), _ep(2)])
    assert xml.count("<item>") == 2


def test_write_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "podcast.xml")
        write_feed([_ep(1), _ep(2)], path=path)
        loaded = load_episodes(path)
        assert len(loaded) == 2
        assert loaded[0]["guid"] == "radar-2026-03-01"
        assert loaded[0]["duration_secs"] == 300
        assert loaded[0]["pub_date"] == "Sun, 01 Mar 2026 00:00:00 +0000"


def test_repeated_roundtrip_preserves_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "podcast.xml")
        write_feed([_ep(1)], path=path)
        first = load_episodes(path)
        write_feed(first, path=path)
        second = load_episodes(path)
        assert second == first


def test_malformed_existing_feed_fails_closed(tmp_path):
    path = tmp_path / "podcast.xml"
    path.write_text("<rss><broken>", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="refusing to overwrite"):
        load_episodes(str(path))


def test_structurally_invalid_existing_feed_fails_closed(tmp_path):
    path = tmp_path / "podcast.xml"
    path.write_text("<html><body>maintenance</body></html>", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="structurally invalid"):
        load_episodes(str(path))


def test_existing_empty_rss_feed_cannot_erase_archive(tmp_path):
    path = tmp_path / "podcast.xml"
    path.write_text("<rss version='2.0'><channel /></rss>", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="no episodes"):
        load_episodes(str(path))


def test_load_episodes_missing_file():
    loaded = load_episodes("/nonexistent/path/podcast.xml")
    assert loaded == []


def test_prepend_episode_adds_to_front():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "podcast.xml")
        write_feed([_ep(1)], path=path)
        prepend_episode(_ep(2), path=path)
        loaded = load_episodes(path)
        assert len(loaded) == 2
        assert loaded[0]["guid"] == "radar-2026-03-02"  # newest first


def test_prepend_episode_deduplicates_by_guid():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "podcast.xml")
        write_feed([_ep(1)], path=path)
        prepend_episode(_ep(1), path=path)  # same guid, re-run scenario
        loaded = load_episodes(path)
        assert len(loaded) == 1


def test_write_feed_creates_xml_declaration():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "podcast.xml")
        write_feed([], path=path)
        content = Path(path).read_text(encoding="utf-8")
        assert content.startswith("<?xml")
