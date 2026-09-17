"""Persist short supporting excerpts, not complete third-party documents."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import List

from .schema import MAX_PUBLIC_EXCERPT_WORDS, SchemaError, SourceEvent, Story

MAX_VERBATIM_WORDS = 50


def publication_evidence(events: List[SourceEvent], stories: List[Story]) -> List[SourceEvent]:
    archived = []
    for event in events:
        original = event.metadata.get("full_text", event.evidence)
        quotes = list(dict.fromkeys(
            claim["quote"].strip() for story in stories for claim in story.editorial["claims"]
            if claim["event_id"] == event.event_id
        ))
        if not quotes or any(quote not in original and quote not in event.evidence for quote in quotes):
            raise SchemaError("publication excerpts must match reviewed source evidence")
        excerpts = "\n\n".join(quotes)
        if len(excerpts.split()) > MAX_PUBLIC_EXCERPT_WORDS:
            raise SchemaError("publication exceeds the short source-excerpt budget")
        normalized_sources = [" ".join(text.casefold().split()) for text in (original, event.evidence)]
        for story in stories:
            if event.event_id not in story.event_ids:
                continue
            words = story.editorial["spoken_text"].casefold().split()
            if any(
                " ".join(words[index:index + MAX_VERBATIM_WORDS + 1]) in source
                for index in range(len(words) - MAX_VERBATIM_WORDS)
                for source in normalized_sources
            ):
                raise SchemaError("spoken explanation copies an overlong source passage")
        metadata = {key: value for key, value in event.metadata.items() if key != "full_text"}
        metadata["source_text_sha256"] = hashlib.sha256(original.encode("utf-8")).hexdigest()
        metadata["source_evidence_sha256"] = hashlib.sha256(
            " ".join(event.evidence.casefold().split()).encode("utf-8")
        ).hexdigest()
        metadata["evidence_status"] = "reviewed_excerpts"
        if event.source_type == "research_paper":
            metadata["full_text_retained"] = False
            metadata["reviewed_excerpts"] = excerpts
        archived.append(replace(event, evidence=excerpts, metadata=metadata).validate())
    return archived
