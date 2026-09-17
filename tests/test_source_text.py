import socket

import pytest
import requests

from pipeline.sources.detail import (
    DetailEnricher,
    DetailError,
    RequestBudget,
    fetch_public,
    validate_public_url,
)
from pipeline.sources.text import article_text, bounded_text, clean_source_text


class Response:
    def __init__(self, body=b"", *, status=200, headers=None):
        self.body = body
        self.status_code = status
        self.headers = headers if headers is not None else {"Content-Type": "text/html"}
        self.closed = False

    def iter_content(self, chunk_size):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start:start + chunk_size]

    def close(self):
        self.closed = True


class Session:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(
        "pipeline.sources.detail.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )


def test_entities_markdown_sentences_and_known_blog_footer():
    text = clean_source_text(
        '<h2>Agents &amp; workflows</h2><p>Use <strong>scoped permissions</strong> '
        'and &quot;approval&quot; checks.</p><p>Fixes **duplicate** calls in `tool.run`.</p>'
        '<p>The post <a href="https://github.blog/change">Agents &amp; workflows</a> '
        'appeared first on <a href="https://github.blog">The GitHub Blog</a>.</p>'
    )
    assert text == (
        'Agents & workflows\nUse scoped permissions and "approval" checks.\n'
        'Fixes duplicate calls in tool.run.'
    )


def test_cleanup_retains_more_than_old_900_chars_and_bounds_sentences():
    text = "A specific migration avoids duplicate agent calls. " * 150
    clean = clean_source_text(text)
    assert 3500 < len(clean) <= 4000
    assert clean.endswith(".")
    assert bounded_text("A" * 4100) == "A" * 4000


def test_cleanup_does_not_remove_legitimate_post_mentions():
    text = "The post describes scoped access. A later paragraph explains recovery."
    assert clean_source_text(text) == text


def test_html_cleanup_ignores_hidden_and_executable_content():
    raw = (
        "<main><nav>Sign in</nav><h1>Agent update</h1>"
        "<script>run_untrusted_code()</script><style>.hidden {}</style>"
        "<div hidden>secret</div><p aria-hidden='true'>not evidence</p>"
        "<p style='display: none'>hidden note</p><p>Visible <em>change</em>.</p>"
        "<footer>Subscribe to our newsletter</footer></main>"
    )
    assert article_text(raw) == "Agent update\nVisible change."


def test_xhtml_feed_content_namespaces_are_cleaned():
    assert clean_source_text(
        '<html:div xmlns:html="http://www.w3.org/1999/xhtml">'
        "<html:p>One sentence.</html:p><html:script>bad()</html:script>"
        "<html:p>Next sentence.</html:p></html:div>"
    ) == "One sentence.\nNext sentence."


def test_markdown_autolinks_and_reference_links_are_readable():
    assert clean_source_text(
        "See <https://github.blog/post>.\nUse [scoped access][scope].\n\n"
        "[scope]: https://github.blog/access"
    ) == "See https://github.blog/post.\nUse scoped access."


def test_article_does_not_reparse_escaped_technical_identifiers_as_html():
    assert article_text("<article><p>Set &lt;scope&gt; to public.</p></article>") == "Set <scope> to public."


@pytest.mark.parametrize("url", [
    "http://github.blog/post", "https://user:password@github.blog/post",
    "https://github.blog:444/post", "https://github.blog.evil.example/post",
    "https://127.0.0.1/post", "https://[::1]/post",
    "https://github.blog\\@evil.example/post", "https://github.blog/\npost",
    "https://github.blog/post with spaces", "file:///etc/passwd",
])
def test_public_url_rejects_disallowed_destinations(url, public_dns):
    with pytest.raises(DetailError):
        validate_public_url(url, frozenset({"github.blog"}))


@pytest.mark.parametrize("address", ["127.0.0.1", "10.2.3.4", "169.254.169.254", "::1", "fe80::1", "100.64.0.1"])
def test_public_url_rejects_private_dns_even_on_allowlisted_host(address, monkeypatch):
    monkeypatch.setattr(
        "pipeline.sources.detail.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
    )
    with pytest.raises(DetailError, match="non_public_address"):
        validate_public_url("https://github.blog/post", frozenset({"github.blog"}))


def test_redirect_validates_each_destination_and_never_sends_to_private(public_dns):
    redirect = Response(status=302, headers={"Location": "https://127.0.0.1/private"})
    session = Session(redirect)
    with pytest.raises(DetailError, match="disallowed_url"):
        fetch_public(
            "https://github.blog/post", hosts=frozenset({"github.blog"}),
            budget=RequestBudget(3), session=session,
        )
    assert len(session.calls) == 1
    assert redirect.closed


def test_redirect_credentials_are_rejected(public_dns):
    session = Session(Response(status=302, headers={"Location": "https://token:secret@github.blog/next"}))
    with pytest.raises(DetailError, match="disallowed_url"):
        fetch_public(
            "https://github.blog/post", hosts=frozenset({"github.blog"}),
            budget=RequestBudget(3), session=session,
        )
    assert len(session.calls) == 1


def test_relative_redirects_are_bounded_and_disable_automatic_following(public_dns):
    redirects = [Response(status=302, headers={"Location": "/next"}) for _ in range(3)]
    session = Session(*redirects)
    with pytest.raises(DetailError, match="redirect_limit"):
        fetch_public(
            "https://github.blog/post", hosts=frozenset({"github.blog"}),
            budget=RequestBudget(3), session=session,
        )
    assert len(session.calls) == 3
    assert all(response.closed for response in redirects)
    assert all(call[1]["allow_redirects"] is False for call in session.calls)
    assert session.calls[1][0] == "https://github.blog/next"


@pytest.mark.parametrize(("response", "error"), [
    (Response(b"x" * 100, headers={"Content-Type": "text/html", "Content-Length": "100"}), "response_too_large"),
    (Response(b"x" * 100), "response_too_large"),
    (Response(status=403), "http_403"),
    (Response(headers={"Content-Type": "application/pdf"}), "unsupported_content_type"),
    (Response(headers={"Content-Type": "text/html", "Content-Encoding": "gzip"}), "unsupported_content_encoding"),
    (Response(b"\xff"), "invalid_utf8"),
])
def test_rejects_oversize_error_or_non_text_responses(response, error, public_dns):
    with pytest.raises(DetailError, match=error):
        fetch_public(
            "https://github.blog/post", hosts=frozenset({"github.blog"}),
            budget=RequestBudget(1), max_bytes=50, session=Session(response),
        )
    assert response.closed


def test_request_caps_include_redirects(public_dns):
    session = Session(Response(status=302, headers={"Location": "/next"}))
    with pytest.raises(DetailError, match="request_limit"):
        fetch_public(
            "https://github.blog/post", hosts=frozenset({"github.blog"}),
            budget=RequestBudget(1), session=session,
        )
    assert len(session.calls) == 1


def test_shared_request_cap_applies_across_sources(public_dns):
    session = Session(Response(b"<article><p>" + b"Scoped approvals are checked. " * 10 + b"</p></article>"))
    budget = RequestBudget(1)
    first = DetailEnricher({"enabled": True}, session=session, shared_budget=budget)
    second = DetailEnricher({"enabled": True}, session=session, shared_budget=budget)
    assert first.enrich("Short.", "https://github.blog/first")[2] is None
    assert second.enrich("Short.", "https://github.blog/second")[2] == "request_limit"
    assert len(session.calls) == 1


def test_timeout_is_explicit(public_dns):
    class TimeoutSession:
        def get(self, *args, **kwargs):
            raise requests.Timeout("not exposed")

    enricher = DetailEnricher({"enabled": True}, session=TimeoutSession(), shared_budget=RequestBudget(10))
    _, metadata, error = enricher.enrich("Short.", "https://github.blog/post")
    assert error == "fetch_Timeout"
    assert metadata["evidence_status"] == "summary_only"


def test_url_only_detail_and_safe_headers(public_dns):
    raw = b"<article><h1>Scoped agent approvals</h1><p>" + b"Approvals apply to each tool call. " * 12 + b"</p></article>"
    session = Session(Response(raw))
    enricher = DetailEnricher(
        {"enabled": True}, session=session, shared_budget=RequestBudget(10),
    )
    evidence, metadata, error = enricher.enrich(
        "https://code.visualstudio.com/updates/v1_120",
        "https://github.com/microsoft/vscode/releases/tag/1.120.0",
        prefer_body_url=True,
    )
    assert error is None
    assert evidence.startswith("Scoped agent approvals\n")
    assert metadata["corroboration_urls"] == ["https://code.visualstudio.com/updates/v1_120"]
    assert metadata["evidence_status"] == "article_text"
    headers = session.calls[0][1]["headers"]
    assert set(headers) == {"User-Agent", "Accept"}
    assert session.calls[0][1]["timeout"] == (5, 20)


def test_real_authenticated_session_is_not_reused(public_dns, monkeypatch):
    calls = []

    class Connection:
        def __init__(self, host, address):
            calls.append((host, address))

        def request(self, method, path, headers):
            calls.append((method, path, headers))

        def getresponse(self):
            return self

        status = 200

        def getheaders(self):
            return [("Content-Type", "text/html")]

        def read(self, size):
            return b""

        def close(self):
            pass

    monkeypatch.setattr("pipeline.sources.detail._PinnedHTTPSConnection", Connection)
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy:secret@127.0.0.1")
    with requests.Session() as session:
        session.auth = ("private", "password")
        session.headers["Authorization"] = "Bearer private-token"
        session.cookies.set("secret", "cookie", domain="github.blog")
        monkeypatch.setattr(session, "get", lambda *a, **k: pytest.fail("reused authenticated session"))
        fetch_public(
            "https://github.blog/post", hosts=frozenset({"github.blog"}),
            budget=RequestBudget(1), session=session,
        )
    assert calls[0] == ("github.blog", "93.184.216.34")
    assert set(calls[1][2]) == {"User-Agent", "Accept"}


def test_opt_in_and_sufficient_summaries_make_no_requests():
    session = Session()
    disabled = DetailEnricher({}, session=session, shared_budget=RequestBudget(10))
    assert disabled.enrich("https://github.blog/post", "https://github.blog/post")[2] is None
    enabled = DetailEnricher({"enabled": True}, session=session, shared_budget=RequestBudget(10))
    enabled.enrich("A meaningful supported workflow change. " * 10, "https://github.blog/post")
    assert session.calls == []


@pytest.mark.parametrize("ending", ["&#8230;", "&hellip;", "..."])
def test_long_truncated_summaries_still_fetch_full_article(ending, public_dns):
    detail = "Scoped approvals now prevent a tool from retrying an already denied operation. " * 5
    session = Session(Response(f"<article><p>{detail}</p></article>".encode()))
    enricher = DetailEnricher({"enabled": True}, session=session, shared_budget=RequestBudget(10))
    raw = "The introductory explanation is longer than the minimum evidence threshold. " * 4 + ending
    evidence, metadata, error = enricher.enrich(raw, "https://github.blog/post")
    assert error is None
    assert metadata["evidence_status"] == "article_text"
    assert evidence == detail.strip()
    assert len(session.calls) == 1


def test_article_failure_is_explicit_and_keeps_only_original_summary(public_dns):
    session = Session(Response(b"<html><nav>Sign in</nav><p>No article available</p></html>"))
    enricher = DetailEnricher({"enabled": True}, session=session, shared_budget=RequestBudget(10))
    evidence, metadata, error = enricher.enrich("Original summary.", "https://github.blog/post")
    assert evidence == "Original summary."
    assert metadata["evidence_status"] == "summary_only"
    assert error == "insufficient_article"
