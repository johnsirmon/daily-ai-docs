from datetime import datetime, timezone

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
