"""Bounded, non-executing cleanup of public source prose."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser


_BLOCKS = {
    "address", "article", "blockquote", "br", "dd", "div", "dl", "dt", "h1", "h2",
    "h3", "h4", "h5", "h6", "hr", "li", "main", "ol", "p", "pre", "section", "ul",
}
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
_SKIP = {"script", "style", "nav", "footer", "noscript", "svg", "form", "button", "template"}
_TRAILERS = (
    r"\s*The post\s+.{1,800}?\s+appeared\s+first\s+on\s+.{1,200}?[.!]?\s*$",
    r"\s*(?:Read (?:the )?(?:full|original) (?:article|post)|Continue reading)"
    r"(?:\s*(?:at|on)\s+https?://\S+)?[.\u2026]*\s*$",
)


class SourceHTMLParser(HTMLParser):
    """Read text without scripts, navigation, hidden nodes, or HTML execution."""

    def __init__(self, *, article_only: bool = False, arxiv: bool = False):
        super().__init__(convert_charrefs=True)
        self.article_only = article_only
        self.arxiv = arxiv
        self.stack: list[tuple[str, bool, bool]] = []
        self.parts: list[str] = []
        self.sections = 0
        self.paragraphs = 0
        self.has_document = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.rsplit(":", 1)[-1]
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        parent_skip = bool(self.stack and self.stack[-1][1])
        parent_selected = bool(self.stack and self.stack[-1][2])
        style = re.sub(r"\s+", "", attributes.get("style") or "").lower()
        skipped = (
            parent_skip or tag in _SKIP or "hidden" in attributes
            or attributes.get("aria-hidden") == "true"
            or "display:none" in style or "visibility:hidden" in style
        )
        if self.arxiv and classes.intersection({"ltx_abstract", "ltx_bibliography"}):
            skipped = True
        selected = parent_selected
        if self.arxiv:
            if tag == "article" and "ltx_document" in classes and not skipped:
                selected = self.has_document = True
        elif tag in {"article", "main"} or attributes.get("role") == "main":
            selected = True
        if selected and not skipped:
            self.sections += int(tag == "section" and "ltx_section" in classes)
            self.paragraphs += int(tag == "p")
        if tag not in _VOID:
            self.stack.append((tag, skipped, selected))
        if not skipped and tag in _BLOCKS and (selected or not self.article_only):
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.rsplit(":", 1)[-1]
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.rsplit(":", 1)[-1]
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                _, skipped, selected = self.stack[index]
                if not skipped and tag in _BLOCKS and (selected or not self.article_only):
                    self.parts.append("\n")
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        skipped = bool(self.stack and self.stack[-1][1])
        selected = bool(self.stack and self.stack[-1][2])
        if not skipped and (selected or not self.article_only):
            self.parts.append(re.sub(r"\s+", " ", data) if self.stack else data)

    def text(self) -> str:
        return "\n".join(
            line for part in "".join(self.parts).splitlines()
            if (line := " ".join(part.split()))
        ).strip()


def bounded_text(text: str, limit: int = 4000) -> str:
    """Prefer a sentence or paragraph boundary over cutting a word in half."""
    if len(text) <= limit:
        return text.strip()
    prefix = text[:limit]
    boundaries = [match.end() for match in re.finditer(r"[.!?](?=\s)|\n", prefix)]
    if boundaries and boundaries[-1] >= limit // 2:
        return prefix[:boundaries[-1]].strip()
    last_space = prefix.rfind(" ")
    return prefix[:last_space if last_space >= limit // 2 else limit].rstrip()


def clean_source_text(value: str, *, limit: int | None = 4000) -> str:
    """Decode feed HTML/entities and common Markdown while retaining prose."""
    parser = SourceHTMLParser()
    parser.feed(re.sub(r"<(https?://[^>\s]+)>", r"\1", value))
    parser.close()
    return _clean_prose(parser.text(), limit=limit)


def _clean_prose(text: str, *, limit: int | None) -> str:
    # Some feeds double-escape entities; two passes are bounded and leave prose intact.
    text = html.unescape(html.unescape(text))
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*\[[^\]\n]+\]:\s*\S+.*$", "", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|>\s*)", "", text)
    text = re.sub(r"(?m)^\s*```[^\n]*$", "", text)
    text = re.sub(r"(`+)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<!\w)([*_])(\S(?:.*?\S)?)\1(?!\w)", r"\2", text)
    text = "\n".join(line for part in text.splitlines() if (line := " ".join(part.split())))
    for pattern in _TRAILERS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL).rstrip()
    return bounded_text(text, limit) if limit is not None else text.strip()


def article_text(value: str) -> str:
    parser = SourceHTMLParser(article_only=True)
    parser.feed(value)
    parser.close()
    return _clean_prose(parser.text(), limit=None)


def arxiv_full_text(value: str, *, max_chars: int) -> str:
    """Require recognizable arXiv section content, not an abstract/error page."""
    parser = SourceHTMLParser(article_only=True, arxiv=True)
    parser.feed(value)
    parser.close()
    text = _clean_prose(parser.text(), limit=None)
    if (
        not parser.has_document or parser.sections < 2 or parser.paragraphs < 3
        or len(text) < 1000
    ):
        raise ValueError("full_text_unavailable")
    if len(text) > max_chars:
        raise ValueError("full_text_too_large")
    if re.search(
        r"(?i)(?:captcha|access denied|verify (?:that )?you are human|"
        r"sign in to (?:read|continue)|enable javascript and cookies)", text[:1000]
    ):
        raise ValueError("full_text_interstitial")
    return text
