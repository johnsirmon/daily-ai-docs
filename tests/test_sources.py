from datetime import datetime, timezone

import socket

from pipeline.sources.github import collect_github_releases


class Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self.payload


class Session:
    def __init__(self, private=False, draft=False):
        self.private = private
        self.draft = draft

    def get(self, url, **kwargs):
        if url.endswith("/repos/org/tool"):
            return Response({"private": self.private, "visibility": "private" if self.private else "public"})
        return Response([{
            "draft": self.draft,
            "prerelease": False,
            "published_at": "2026-09-07T11:00:00Z",
            "html_url": "https://github.com/org/tool/releases/tag/v2",
            "tag_name": "v2",
            "body": "Adds a supported migration path.",
        }])


def test_github_source_collects_public_primary_release():
    events, health = collect_github_releases(
        [{"repo": "org/tool", "product": "Tool", "topic": "Agents", "priority": 20}],
        session=Session(),
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert len(events) == 1
    assert events[0].authority == "primary"
    assert events[0].metadata["private"] is False
    assert health["github:org/tool"] == "ok:1"


def test_github_source_rejects_private_repository():
    events, health = collect_github_releases(
        [{"repo": "org/tool"}],
        session=Session(private=True),
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert events == []
    assert health["github:org/tool"] == "rejected_private"


def test_github_source_excludes_draft_release():
    events, health = collect_github_releases(
        [{"repo": "org/tool"}],
        session=Session(draft=True),
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert events == []
    assert health["github:org/tool"] == "ok:0"


def test_github_body_cleanup_is_bounded_and_readable():
    class LongBody(Session):
        def get(self, url, **kwargs):
            response = super().get(url, **kwargs)
            if isinstance(response.payload, list):
                response.payload[0]["body"] = (
                    "## Agent **permissions** &amp; execution\n"
                    + "Checks `tool.run` before each execution. " * 130
                )
            return response

    events, health = collect_github_releases(
        [{"repo": "org/tool"}], session=LongBody(),
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert health["github:org/tool"] == "ok:1"
    assert 3500 < len(events[0].evidence) <= 4000
    assert events[0].evidence.startswith("Agent permissions & execution\nChecks tool.run")
    assert events[0].evidence.endswith(".")


def test_github_url_only_release_enrichment_preserves_release_provenance(monkeypatch):
    monkeypatch.setattr(
        "pipeline.sources.detail.socket.getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    monkeypatch.setattr("pipeline.sources.github.build_github_headers", lambda: {"Authorization": "Bearer private-token"})

    class Article:
        status_code = 200
        headers = {"Content-Type": "text/html"}

        def iter_content(self, chunk_size):
            yield b"<main><h1>Agent approvals</h1><p>" + b"Approvals are checked before each tool call. " * 10 + b"</p></main>"

        def close(self):
            pass

    class URLOnly(Session):
        def __init__(self):
            super().__init__()
            self.detail_calls = []

        def get(self, url, **kwargs):
            if url.startswith("https://code.visualstudio.com"):
                self.detail_calls.append((url, kwargs))
                return Article()
            response = super().get(url, **kwargs)
            if isinstance(response.payload, list):
                response.payload[0]["body"] = "https://code.visualstudio.com/updates/v1_120"
            return response

    session = URLOnly()
    events, health = collect_github_releases(
        [{"repo": "org/tool", "enrichment": {"enabled": True}}],
        session=session, now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert health["github:org/tool"] == "ok:1"
    assert events[0].url == "https://github.com/org/tool/releases/tag/v2"
    assert events[0].published_at == "2026-09-07T11:00:00Z"
    assert events[0].evidence.startswith("Agent approvals\n")
    assert events[0].metadata["corroboration_urls"] == ["https://code.visualstudio.com/updates/v1_120"]
    assert events[0].metadata["evidence_status"] == "article_text"
    assert len(session.detail_calls) == 1
    assert "Authorization" not in session.detail_calls[0][1]["headers"]


def test_github_does_not_fetch_url_body_without_opt_in():
    class URLOnly(Session):
        def get(self, url, **kwargs):
            assert url.startswith("https://api.github.com/")
            response = super().get(url, **kwargs)
            if isinstance(response.payload, list):
                response.payload[0]["body"] = "https://code.visualstudio.com/updates/v1_120"
            return response

    events, health = collect_github_releases(
        [{"repo": "org/tool"}], session=URLOnly(),
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
    )
    assert len(events) == 1
    assert health["github:org/tool"] == "ok:1"
