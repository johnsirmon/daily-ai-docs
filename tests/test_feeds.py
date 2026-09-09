from datetime import datetime, timezone

from pipeline.sources.feeds import collect_official_feeds


class Response:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


class Session:
    def __init__(self, content):
        self.content = content

    def get(self, *args, **kwargs):
        return Response(self.content)


def test_feed_adapter_rejects_html_maintenance_page():
    events, health = collect_official_feeds(
        [{"url": "https://example.com/feed", "product": "Tool"}],
        session=Session(b"<html><body>maintenance</body></html>"),
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert events == []
    assert health["feed:https://example.com/feed"] == "error:ValueError"


def test_feed_adapter_accepts_recent_atom_entry():
    atom = b"""<feed xmlns='http://www.w3.org/2005/Atom'>
      <entry><title>Copilot agent update</title>
      <link href='https://example.com/update'/><published>2026-09-07T11:00:00Z</published>
      <summary>Adds a supported agent workflow.</summary></entry></feed>"""
    events, health = collect_official_feeds(
        [{"url": "https://example.com/feed", "product": "Copilot", "include": ["agent"]}],
        session=Session(atom),
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert len(events) == 1
    assert events[0].url == "https://example.com/update"
    assert health["feed:https://example.com/feed"] == "ok:1"
