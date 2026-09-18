import socket
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from xml.sax.saxutils import escape

import pytest

from pipeline.sources import collect_research_papers


NOW = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)


class Response:
    def __init__(self, content, *, status=200, content_type="application/atom+xml", headers=None):
        self.content = content.encode() if isinstance(content, str) else content
        self.status_code = status
        self.headers = {"Content-Type": content_type, **(headers or {})}
        self.closed = False

    def iter_content(self, chunk_size):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start:start + chunk_size]

    def close(self):
        self.closed = True


class Session:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(
        "pipeline.sources.detail.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )


def entry(paper_id="2609.12345v2", published="2026-09-01T11:00:00Z", updated="2026-09-16T11:00:00Z"):
    return f"""<entry><id>http://arxiv.org/abs/{escape(paper_id)}</id>
      <title>Agent evaluation &amp; workflow reliability</title>
      <published>{published}</published><updated>{updated}</updated>
      <author><name>First Author</name></author><author><name>Second Author</name></author>
      <summary>An abstract is not the reviewed method or result.</summary></entry>"""


def atom(*entries):
    return Response("<feed xmlns='http://www.w3.org/2005/Atom'>" + "".join(entries) + "</feed>")


def fulltext(*, repeats=8):
    method = "We evaluate tool approval boundaries in an isolated benchmark with a fixed tool set. "
    result = "The authors report fewer unauthorized calls in this setting, not production reliability. "
    limit = "The evaluation uses simulated services and does not establish generalization to live deployments. "
    return Response(
        '<html><body><nav>Account login</nav><article class="ltx_document">'
        '<h1>Agent evaluation &amp; workflow reliability</h1>'
        '<div class="ltx_abstract">Abstract-only wording must not be used as full text.</div>'
        '<section class="ltx_section"><h2>1 Method</h2>'
        f'<p class="ltx_p">{method * repeats}</p></section>'
        '<section class="ltx_section"><h2>2 Results</h2>'
        f'<p class="ltx_p">{result * repeats}</p></section>'
        '<section class="ltx_section"><h2>3 Limitations</h2>'
        f'<p class="ltx_p">{limit * repeats}</p></section>'
        '</article><footer>Account links</footer></body></html>',
        content_type="text/html",
    )


def test_research_collection_disabled_by_default_without_network():
    session = Session()
    for config in [{}, {"enabled": False}, {"enabled": "true"}]:
        assert collect_research_papers(config, session=session, now=NOW) == ([], {})
    assert session.calls == []


def test_papers_preserve_identity_dates_authors_and_unreviewed_full_text():
    session = Session(atom(entry()), fulltext())
    events, health = collect_research_papers({"enabled": True}, session=session, now=NOW)
    assert health["research:arxiv"] == "ok:1"
    assert len(events) == 1
    event = events[0]
    assert event.source_type == "research_paper"
    assert event.event_id == "arxiv:2609.12345"
    assert event.url == "https://arxiv.org/abs/2609.12345v2"
    assert event.published_at == "2026-09-01T11:00:00Z"
    assert event.fetched_at == "2026-09-17T12:00:00Z"
    assert event.metadata["paper_id"] == "2609.12345"
    assert event.metadata["version"] == 2
    assert event.metadata["first_published_at"] == event.published_at
    assert event.metadata["updated_at"] == "2026-09-16T11:00:00Z"
    assert event.metadata["authors"] == ["First Author", "Second Author"]
    assert event.metadata["full_text_available"] is True
    assert event.metadata["review_status"] == "unreviewed"
    assert event.metadata["claim_origin"] == "author_reported_preprint"
    assert event.metadata["independently_reproduced"] is False
    assert event.metadata["corroboration_urls"] == ["https://arxiv.org/html/2609.12345v2"]
    assert 1000 < len(event.metadata["full_text"]) <= 60000
    assert len(event.evidence) <= 4000
    assert event.evidence in event.metadata["full_text"]
    assert "ltx_" not in event.evidence
    assert "&amp;" not in event.evidence
    assert "Abstract-only" not in event.metadata["full_text"]
    assert "Account login" not in event.metadata["full_text"]
    query = parse_qs(urlsplit(session.calls[0][0]).query)
    assert query["max_results"] == ["5"]
    assert query["sortBy"] == ["submittedDate"]
    assert "submittedDate:[202608181200 TO 202609171200]" in query["search_query"][0]


@pytest.mark.parametrize(("published", "updated", "diagnostic"), [
    ("2026-08-18T11:59:59Z", "2026-09-16T11:00:00Z", "outside_first_publication_window"),
    ("2025-09-01T11:00:00Z", "2026-09-16T11:00:00Z", "outside_first_publication_window"),
    ("2026-09-18T11:00:00Z", "2026-09-18T11:00:00Z", "invalid_paper_dates"),
    ("2026-09-01T11:00:00Z", "2026-09-18T11:00:00Z", "invalid_paper_dates"),
    ("2026-09-01T11:00:00Z", "2026-08-31T11:00:00Z", "invalid_paper_dates"),
])
def test_dates_use_first_publication_not_recent_version(published, updated, diagnostic):
    session = Session(atom(entry(published=published, updated=updated)))
    events, health = collect_research_papers({"enabled": True}, session=session, now=NOW)
    assert events == []
    assert health["research:arxiv:2609.12345"] == f"rejected:{diagnostic}"
    assert len(session.calls) == 1


def test_exact_30_day_boundary_is_eligible():
    session = Session(atom(entry(published="2026-08-18T12:00:00Z")), fulltext())
    events, _ = collect_research_papers({"enabled": True}, session=session, now=NOW)
    assert len(events) == 1


def test_duplicate_versions_keep_stable_identity_and_fetch_once():
    session = Session(atom(entry(), entry("2609.12345v1")), fulltext())
    events, _ = collect_research_papers({"enabled": True}, session=session, now=NOW)
    assert [event.event_id for event in events] == ["arxiv:2609.12345"]
    assert len(session.calls) == 2
    other = Session(atom(entry("2609.12345v3")), fulltext())
    updated, _ = collect_research_papers({"enabled": True}, session=other, now=NOW)
    assert updated[0].event_id == events[0].event_id


@pytest.mark.parametrize("page", [
    "<html><body>Sign in to continue</body></html>",
    "<article><p>Abstract: just a summary</p></article>",
    '<article class="ltx_document"><div class="ltx_abstract"><p>Abstract.</p></div></article>',
    "<html><h1>Captcha</h1><nav>Human verification</nav></html>",
])
def test_abstract_only_or_interstitial_is_not_a_full_source_review(page):
    session = Session(atom(entry()), Response(page, content_type="text/html"))
    events, health = collect_research_papers({"enabled": True}, session=session, now=NOW)
    assert events == []
    assert health["research:arxiv"] == "degraded:0"
    assert health["research:arxiv:2609.12345"] == "rejected:full_text_unavailable"


def test_unavailable_html_is_not_replaced_with_abstract_or_pdf():
    session = Session(atom(entry()), Response("Not found", status=404, content_type="text/html"))
    events, health = collect_research_papers({"enabled": True}, session=session, now=NOW)
    assert events == []
    assert health["research:arxiv:2609.12345"] == "rejected:http_404"
    assert len(session.calls) == 2
    assert all("/pdf/" not in url for url, _ in session.calls)


def test_oversize_full_text_is_rejected_not_truncated_and_claimed_complete():
    session = Session(atom(entry()), fulltext())
    events, health = collect_research_papers(
        {"enabled": True, "max_full_text_chars": 1000}, session=session, now=NOW,
    )
    assert events == []
    assert health["research:arxiv:2609.12345"] == "rejected:full_text_too_large"


def test_fulltext_redirect_cannot_substitute_another_paper():
    redirect = Response("", status=302, headers={"Location": "/html/2609.99999v1"})
    session = Session(atom(entry()), redirect, fulltext())
    events, health = collect_research_papers({"enabled": True}, session=session, now=NOW)
    assert events == []
    assert health["research:arxiv:2609.12345"] == "rejected:not_paper_html"


def test_fulltext_request_cap_counts_failed_candidates():
    session = Session(
        atom(entry(), entry("2609.12346v1"), entry("2609.12347v1")),
        Response("", status=404), Response("", status=404),
    )
    events, health = collect_research_papers(
        {"enabled": True, "max_papers": 2}, session=session, now=NOW,
    )
    assert events == []
    assert len(session.calls) == 3
    assert health["research:arxiv:2609.12347"] == "not_fetched:candidate_limit"


def test_covered_paper_does_not_consume_full_text_attempt_budget():
    session = Session(atom(entry(), entry("2609.12346v1")), fulltext())
    events, health = collect_research_papers(
        {"enabled": True, "max_papers": 1},
        covered_paper_ids={"2609.12345"},
        session=session,
        now=NOW,
    )
    assert [item.metadata["paper_id"] for item in events] == ["2609.12346"]
    assert health["research:arxiv:2609.12345"] == "not_fetched:already_covered"
    assert len(session.calls) == 2


@pytest.mark.parametrize("config", [
    {"lookback_days": 31}, {"max_results": 1000}, {"max_papers": 0},
    {"max_full_text_chars": 60001}, {"queries": []}, {"queries": ["x\" OR all:*"]},
])
def test_invalid_config_is_explicit_and_makes_no_requests(config):
    session = Session()
    events, health = collect_research_papers({"enabled": True, **config}, session=session, now=NOW)
    assert events == []
    assert health["research:arxiv"].startswith("error:invalid_")
    assert session.calls == []


def test_discovery_error_is_explicit():
    session = Session(Response("<html>maintenance</html>", content_type="text/html"))
    events, health = collect_research_papers({"enabled": True}, session=session, now=NOW)
    assert events == []
    assert health["research:arxiv"] == "error:not_atom"


@pytest.mark.parametrize("paper_id", ["2609.12345", "2609.12345v0", "../private", "2609.12345v2?token=secret"])
def test_invalid_or_unversioned_identity_is_not_guessed(paper_id):
    session = Session(atom(entry(paper_id)))
    events, health = collect_research_papers({"enabled": True}, session=session, now=NOW)
    assert events == []
    assert health["research:arxiv"] == "degraded:0"
    assert len(session.calls) == 1
