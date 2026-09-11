"""Offline publication fault injection; no release, Pages, model, or TTS calls."""
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

from pipeline import daily, health
from pipeline.publish import PublicationError, verify_remote_feed
from pipeline.schema import EpisodeManifest


class Response:
    def __init__(self, content=b"", status=200, headers=None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}


class Delivery:
    def __init__(self, feed, audio):
        self.feed = feed
        self.audio = audio
        self.range_status = 206
        self.head_status = 200
        image = io.BytesIO()
        Image.new("RGB", (1400, 1400)).save(image, format="JPEG")
        self.artwork = image.getvalue()

    def head(self, url, **kwargs):
        return Response(status=self.head_status, headers={
            "Content-Length": str(len(self.audio)), "Content-Type": "audio/mpeg",
        })

    def get(self, url, **kwargs):
        if kwargs.get("headers", {}).get("Cache-Control"):
            return Response(self.feed)
        if kwargs.get("headers", {}).get("Range"):
            return Response(status=self.range_status, headers={"Content-Range": "bytes 0-1023/12000"})
        if url.endswith(".mp3"):
            return Response(self.audio)
        return Response(self.artwork)


@pytest.fixture
def recovery(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    stamp = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    audio = b"offline-audio" * 1000
    manifest = EpisodeManifest(
        1, "daily-recovery-test", stamp, "ready", {"test": "ok:0"}, [], [], [],
        "A quiet daily brief with enough words to be valid narration.", "No updates.",
        {"edition": "quiet"}, {"url": "https://example.com/test.mp3", "size_bytes": len(audio),
        "duration_secs": 60, "sha256": hashlib.sha256(audio).hexdigest()},
    )
    cache = Path(".cache")
    cache.mkdir()
    path = cache / "episode-manifest.json"
    path.write_text(json.dumps(manifest.to_dict()))
    (cache / "daily-ai-brief.mp3").write_bytes(audio)
    candidate = daily.finalize(path, verify_remote=False)
    delivery = Delivery(Path("podcast.xml").read_bytes(), audio)
    return candidate, delivery, path


def test_48_hour_resume_delivery_confirm_is_idempotent(recovery, monkeypatch):
    candidate, delivery, path = recovery
    config = Path("topics.yaml")
    config.write_text("daily: {}")
    for name in ("collect_events", "refine_stories", "write_audio", "analyze_audio"):
        monkeypatch.setattr(daily, name, Mock(side_effect=AssertionError(f"must not call {name}")))
    original_feed = Path("podcast.xml").read_bytes()
    publication = daily.prepare(config)
    assert publication["resumed"] is True
    assert publication["episode_id"] == candidate.episode_id
    # Downloaded release is ready; only its status differs from the accepted candidate.
    released = candidate.to_dict()
    released["status"] = "ready"
    path.write_text(json.dumps(released))
    daily.finalize(path, verify_remote=False, publication_path=Path(".cache/publication.json"))
    assert Path("podcast.xml").read_bytes() == original_feed
    assert not Path("data/state.json").exists()
    with pytest.raises(PublicationError, match="stale"):
        verify_remote_feed("https://example.com/feed", expected_guid=candidate.episode_id, session=delivery)
    checked = verify_remote_feed("https://example.com/feed", candidate=candidate, session=delivery)
    assert checked["age_hours"] >= 48
    assert checked["sha256_verified"] is True
    monkeypatch.setattr(daily, "verify_remote_feed", lambda url, **kw: verify_remote_feed(url, session=delivery, **kw))
    assert daily.confirm(candidate.episode_id).status == "published"
    paths = [Path("data/state.json"), Path(f"data/receipts/{candidate.episode_id}.json"),
             Path(f"data/episodes/{candidate.episode_id}.json"), Path("podcast.xml")]
    before = [p.read_bytes() for p in paths]
    daily.confirm(candidate.episode_id)
    assert [p.read_bytes() for p in paths] == before
    accepted = json.loads(paths[2].read_text())
    assert accepted["published_at"] == candidate.published_at
    assert accepted["audio"] == candidate.audio


@pytest.mark.parametrize("fault", ["guid", "date", "url", "length", "bad-length", "checksum", "range", "head", "artwork", "xml"])
def test_aged_candidate_still_fails_closed(recovery, monkeypatch, fault):
    candidate, delivery, _ = recovery
    root = ET.fromstring(delivery.feed)
    item = root.find("channel/item")
    if fault == "guid":
        item.find("guid").text = "wrong-guid"
    elif fault == "date":
        item.find("pubDate").text = "Mon, 07 Sep 2026 12:00:00 +0000"
    elif fault in {"url", "length", "bad-length"}:
        field = "url" if fault == "url" else "length"
        item.find("enclosure").set(field, {"url": "https://example.com/other.mp3", "length": "1", "bad-length": "no"}[fault])
    elif fault == "checksum":
        delivery.audio = b"x" * len(delivery.audio)
    elif fault == "range":
        delivery.range_status = 200
    elif fault == "head":
        delivery.head_status = 503
    elif fault == "artwork":
        delivery.artwork = b"not-an-image"
    delivery.feed = b"bad XML" if fault == "xml" else ET.tostring(root)
    before = Path(f"data/episodes/{candidate.episode_id}.json").read_bytes()
    monkeypatch.setattr(daily, "verify_remote_feed", lambda url, **kw: verify_remote_feed(url, session=delivery, **kw))
    with pytest.raises(PublicationError):
        daily.confirm(candidate.episode_id)
    assert not Path("data/state.json").exists()
    assert not Path("data/receipts").exists()
    assert Path(f"data/episodes/{candidate.episode_id}.json").read_bytes() == before


@pytest.mark.parametrize("fault", ["episode_id", "tag", "audio_url", "audio", "published_at", "narration", "sha256"])
def test_downloaded_release_mismatch_precedes_candidate_writes(recovery, fault):
    candidate, _, path = recovery
    publication = {"episode_id": candidate.episode_id, "tag": candidate.episode_id,
                   "audio_url": candidate.audio["url"], "audio_path": ".cache/daily-ai-brief.mp3"}
    if fault in publication:
        publication[fault] = "wrong"
    elif fault == "audio":
        Path(publication["audio_path"]).write_bytes(b"wrong")
    else:
        changed = candidate.to_dict()
        if fault == "sha256":
            changed["audio"]["sha256"] = "0" * 64
        else:
            changed[fault] = "2026-01-01T12:00:00Z" if fault == "published_at" else "Changed narration."
        path.write_text(json.dumps(changed))
    publication_path = Path(".cache/publication.json")
    publication_path.write_text(json.dumps(publication))
    before = Path("podcast.xml").read_bytes(), Path("README.md").read_bytes()
    with pytest.raises(RuntimeError, match="does not match"):
        daily.finalize(path, verify_remote=False, publication_path=publication_path)
    assert (Path("podcast.xml").read_bytes(), Path("README.md").read_bytes()) == before
    assert not Path("data/state.json").exists()


def test_candidate_must_be_valid_and_bound_to_expected_guid(recovery):
    candidate, delivery, _ = recovery
    with pytest.raises(PublicationError, match="expected GUID"):
        verify_remote_feed("https://example.com/feed", candidate=candidate, expected_guid="other", session=delivery)
    candidate.status = "ready"
    with pytest.raises(PublicationError, match="requires a candidate"):
        verify_remote_feed("https://example.com/feed", candidate=candidate, session=delivery)
    candidate.status = "candidate"
    candidate.audio.pop("sha256")
    with pytest.raises(ValueError):
        verify_remote_feed("https://example.com/feed", candidate=candidate, session=delivery)


@pytest.mark.parametrize("error", [requests.Timeout, requests.ConnectionError, PublicationError])
@pytest.mark.parametrize("recovers", [True, False])
def test_health_retries_transport_and_delivery_failures(monkeypatch, error, recovers):
    effects = [error("temporary"), {"status": "ok"}] if recovers else [error("temporary")] * 3
    verify = Mock(side_effect=effects)
    sleep = Mock()
    monkeypatch.setattr(health, "verify_remote_feed", verify)
    monkeypatch.setattr(health.time, "sleep", sleep)
    monkeypatch.setattr("sys.argv", ["health", "--retries", "3", "--delay-seconds", "0"])
    if recovers:
        health.main()
        assert verify.call_count == 2
        assert sleep.call_count == 1
    else:
        with pytest.raises(SystemExit, match="feed health failed"):
            health.main()
        assert verify.call_count == 3
        assert sleep.call_count == 2


def test_health_cli_passes_validated_candidate(recovery, monkeypatch, capsys):
    candidate, delivery, _ = recovery
    monkeypatch.setattr(health, "verify_remote_feed", lambda url, **kw: verify_remote_feed(url, session=delivery, **kw))
    monkeypatch.delenv("EXPECTED_GUID", raising=False)
    monkeypatch.setattr("sys.argv", ["health", "--candidate", f"data/episodes/{candidate.episode_id}.json"])
    health.main()
    assert json.loads(capsys.readouterr().out)["candidate_verified"] is True
