from datetime import datetime, timezone

import socket

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


def test_feed_cleanup_decodes_entities_and_removes_known_blog_trailer():
    rss = b"""<rss><channel><item><title>Agent &amp;amp; approvals</title>
      <link>https://github.blog/update</link><pubDate>Mon, 07 Sep 2026 11:00:00 GMT</pubDate>
      <description><![CDATA[<p>Agents &amp; tools use &quot;scoped&quot; approvals.</p>
      <p>The post <a href="https://github.blog/update">Agent approvals</a>
      appeared first on <a href="https://github.blog">The GitHub Blog</a>.</p>]]></description>
      </item></channel></rss>"""
    events, _ = collect_official_feeds(
        [{"url": "https://github.blog/feed"}], session=Session(rss),
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert events[0].title == "Agent & approvals"
    assert events[0].evidence == 'Agents & tools use "scoped" approvals.'


def test_feed_atom_prefers_original_publication_and_alternate_url():
    atom = b"""<feed xmlns='http://www.w3.org/2005/Atom'><entry>
      <title>Agent workflow</title>
      <link rel='self' href='https://example.com/api'/>
      <link rel='alternate' href='https://example.com/article'/>
      <updated>2026-09-07T11:30:00Z</updated><published>2026-09-07T10:00:00Z</published>
      <summary>Summary</summary><content type='xhtml'>
      <div xmlns='http://www.w3.org/1999/xhtml'><p>Detailed supported workflow.</p></div>
      </content></entry></feed>"""
    events, _ = collect_official_feeds(
        [{"url": "https://example.com/feed"}], session=Session(atom),
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert events[0].published_at == "2026-09-07T10:00:00Z"
    assert events[0].metadata["updated_at"] == "2026-09-07T11:30:00Z"
    assert events[0].url == "https://example.com/article"
    assert events[0].evidence == "Detailed supported workflow."


def test_excerpt_feed_fetches_allowlisted_official_article(monkeypatch):
    monkeypatch.setattr(
        "pipeline.sources.detail.socket.getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    atom = b"""<feed xmlns='http://www.w3.org/2005/Atom'><entry>
      <title>Agent workflow</title><link href='https://github.blog/article'/>
      <published>2026-09-07T10:00:00Z</published>
      <summary>Read the full article...</summary></entry></feed>"""

    class Article:
        status_code = 200
        headers = {"Content-Type": "text/html"}

        def iter_content(self, chunk_size):
            yield b"<article><p>" + b"Scoped approval now runs before every tool call. " * 10 + b"</p></article>"

        def close(self):
            pass

    class ArticleSession(Session):
        def __init__(self):
            super().__init__(atom)
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append(url)
            if url.endswith("/article"):
                return Article()
            return super().get(url, **kwargs)

    session = ArticleSession()
    events, health = collect_official_feeds(
        [{"url": "https://github.blog/feed", "enrichment": {"enabled": True}}],
        session=session, now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert health["feed:https://github.blog/feed"] == "ok:1"
    assert session.calls == ["https://github.blog/feed", "https://github.blog/article"]
    assert events[0].evidence.startswith("Scoped approval now runs before every tool call.")
    assert events[0].metadata["evidence_status"] == "article_text"
    assert events[0].metadata["feed_url"] == "https://github.blog/feed"
    assert events[0].published_at == "2026-09-07T10:00:00Z"


def test_feed_enrichment_failure_is_degraded_without_fabricating_detail():
    atom = b"""<feed xmlns='http://www.w3.org/2005/Atom'><entry>
      <title>Agent workflow</title><link href='https://127.0.0.1/private'/>
      <published>2026-09-07T10:00:00Z</published>
      <summary>Original short summary.</summary></entry></feed>"""
    events, health = collect_official_feeds(
        [{"url": "https://example.com/feed", "enrichment": {"enabled": True}}],
        session=Session(atom), now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert health["feed:https://example.com/feed"] == "degraded:1"
    assert "error:disallowed_url" in health.values()
    assert events[0].evidence == "Original short summary."
    assert events[0].metadata["evidence_status"] == "summary_only"
    assert events[0].metadata["detail_error"] == "disallowed_url"
