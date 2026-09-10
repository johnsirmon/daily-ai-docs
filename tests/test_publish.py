import hashlib

import pytest

from pipeline.publish import PublicationError, validate_feed_file, verify_remote_audio


class Response:
    def __init__(self, status, headers=None, content=b""):
        self.status_code = status
        self.headers = headers or {}
        self.content = content


class Session:
    def __init__(self, range_status=206):
        self.range_status = range_status

    def head(self, *args, **kwargs):
        return Response(200, {"Content-Length": "12345", "Content-Type": "audio/mpeg"})

    def get(self, *args, **kwargs):
        if "headers" not in kwargs:
            return Response(200, content=b"verified-audio")
        return Response(self.range_status, {"Content-Range": "bytes 0-1023/12345", "Accept-Ranges": "bytes"})


def test_verify_remote_audio_requires_range_support():
    with pytest.raises(PublicationError, match="byte-range"):
        verify_remote_audio("https://example.com/a.mp3", expected_size=12345, session=Session(200))


def test_verify_remote_audio_accepts_measured_asset():
    checksum = hashlib.sha256(b"verified-audio").hexdigest()
    result = verify_remote_audio(
        "https://example.com/a.mp3",
        expected_size=12345,
        expected_sha256=checksum,
        session=Session(),
    )
    assert result["status"] == "ok"
    assert result["sha256_verified"] is True


def test_verify_remote_audio_rejects_checksum_mismatch():
    with pytest.raises(PublicationError, match="checksum"):
        verify_remote_audio(
            "https://example.com/a.mp3",
            expected_size=12345,
            expected_sha256="0" * 64,
            session=Session(),
        )


def test_validate_feed_rejects_zero_length(tmp_path):
    path = tmp_path / "podcast.xml"
    path.write_text(
        '<rss><channel><item><guid>x</guid><pubDate>Mon, 07 Sep 2026 12:00:00 +0000</pubDate>'
        '<enclosure url="https://example.com/x.mp3" length="0" type="audio/mpeg"/>'
        '</item></channel></rss>',
        encoding="utf-8",
    )
    with pytest.raises(PublicationError, match="zero-length"):
        validate_feed_file(path)


def test_validate_feed_rejects_html_or_empty_rss(tmp_path):
    html = tmp_path / "html.xml"
    html.write_text("<html><body>maintenance</body></html>", encoding="utf-8")
    with pytest.raises(PublicationError, match="RSS channel"):
        validate_feed_file(html)
    empty = tmp_path / "empty.xml"
    empty.write_text("<rss version='2.0'><channel /></rss>", encoding="utf-8")
    with pytest.raises(PublicationError, match="at least one episode"):
        validate_feed_file(empty)
