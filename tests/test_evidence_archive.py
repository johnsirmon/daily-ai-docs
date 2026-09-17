import hashlib
import json
from dataclasses import replace

import pytest

from pipeline.daily import finalize
from pipeline.evidence_archive import publication_evidence
from pipeline.models_client import EditorialValidationError
from pipeline.rank import select_editorial_events
from pipeline.schema import EpisodeManifest, SchemaError, Story
from pipeline.synthesis import refine_editorial
from tests.test_grounded_editorial import base_story, event, manifest, research_case, run_editorial, story_row


@pytest.fixture(autouse=True)
def clean_provider_environment(monkeypatch):
    for name in ("AI_BASE_URL", "AI_MODEL", "AI_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GEMINI_MODEL", "AI_PROVIDER"):
        monkeypatch.delenv(name, raising=False)


def test_full_paper_is_removed_before_manifest_storage_and_recovery():
    item, row, proposal = research_case()
    item = replace(item, metadata={**item.metadata, "full_text": (
        item.metadata["full_text"] + " This unquoted source paragraph must never be archived."
    )})
    (stories, generation), _ = run_editorial(proposal, items=[item], bases=[base_story([item])])
    archived = publication_evidence([item], stories)
    assert "full_text" not in archived[0].metadata
    assert archived[0].metadata["full_text_retained"] is False
    assert archived[0].metadata["source_text_sha256"] == hashlib.sha256(
        item.metadata["full_text"].encode()
    ).hexdigest()
    assert "unquoted source paragraph" not in json.dumps(archived[0].to_dict())
    ready = manifest(stories, generation, archived)
    ready.status = "ready"
    ready.audio = {"url": "https://example.com/audio.mp3", "size_bytes": 10000,
                   "duration_secs": 400, "sha256": "a" * 64}
    restored = EpisodeManifest.from_dict(ready.to_dict())
    restored.validate(require_audio=True)
    assert restored.narration == ready.narration
    assert restored.stories[0].editorial["paper_review"] == row["editorial"]["paper_review"]
    with pytest.raises(EditorialValidationError, match="complete collected full text"):
        refine_editorial(archived, [base_story(archived)], [])
    restored.source_events = [replace(archived[0], metadata={
        **archived[0].metadata, "reviewed_excerpts": archived[0].evidence + " Added material.",
    })]
    with pytest.raises(SchemaError, match="supporting-excerpt contract"):
        restored.validate(require_audio=True)


@pytest.mark.parametrize("status", ["draft", "ready", "candidate", "published"])
def test_publishable_research_cannot_bypass_full_text_redaction(status):
    item, _, proposal = research_case()
    (stories, generation), _ = run_editorial(proposal, items=[item], bases=[base_story([item])])
    ready = manifest(stories, generation, [item])
    ready.status = status
    with pytest.raises(SchemaError, match="short excerpts"):
        ready.validate(require_audio=True)


def test_finalize_rejects_unredacted_draft_before_touching_feed(tmp_path):
    item, _, proposal = research_case()
    (stories, generation), _ = run_editorial(proposal, items=[item], bases=[base_story([item])])
    draft = manifest(stories, generation, [item])
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(draft.to_dict()))
    feed = tmp_path / "podcast.xml"
    feed.write_text("last confirmed feed")
    with pytest.raises(SchemaError, match="short excerpts"):
        finalize(manifest_path=path, feed_path=feed, verify_remote=False)
    assert feed.read_text() == "last confirmed feed"


def test_archiving_preserves_original_evidence_digest_for_novelty():
    item = event()
    row = story_row([item])
    story = Story(**row, source_urls=[item.url], scores={"total": 85})
    archived = publication_evidence([item], [story])[0]
    assert archived.metadata["source_evidence_sha256"] == hashlib.sha256(
        " ".join(item.evidence.casefold().split()).encode()
    ).hexdigest()
    history = [{
        "canonical_event_id": item.event_id, "product": item.product, "channel": item.channel,
        "published_at": item.published_at, "normalized_evidence": "only a short archived excerpt",
        "evidence_sha256": archived.metadata["source_evidence_sha256"],
    }]
    new_tag = replace(item, event_id="new-tag")
    assert not select_editorial_events([new_tag], published_events=history)[0]


def test_overlong_quotes_and_verbatim_speech_are_rejected():
    text = " ".join(f"term{index}" for index in range(181))
    item = event(evidence=text)
    row = story_row([item])
    story = Story(**row, source_urls=[item.url], scores={"total": 85})
    with pytest.raises(SchemaError, match="source-excerpt budget"):
        publication_evidence([item], [story])
    short_quote = " ".join(text.split()[:10])
    story = replace(story, editorial={
        "spoken_text": text,
        "claims": [{"event_id": item.event_id, "text": short_quote, "quote": short_quote}],
    })
    with pytest.raises(SchemaError, match="overlong source passage"):
        publication_evidence([item], [story])


@pytest.mark.parametrize("unknown", [True, False])
def test_unknown_or_unmatched_source_excerpts_fail(unknown):
    item = event()
    row = story_row([item])
    story = Story(**row, source_urls=[item.url], scores={"total": 85})
    claim = {
        "event_id": "unknown" if unknown else item.event_id, "text": "A claim.",
        "quote": item.evidence if unknown else "Not contained in the original evidence.",
    }
    story = replace(story, editorial={"spoken_text": "A useful explanation.", "claims": [claim]})
    with pytest.raises(SchemaError, match="must match reviewed source"):
        publication_evidence([item], [story])


def test_exact_quote_and_verbatim_limits_are_allowed():
    text = " ".join(f"term{index}" for index in range(180))
    item = event(evidence=text)
    row = story_row([item])
    story = Story(**row, source_urls=[item.url], scores={"total": 85})
    story = replace(story, editorial={
        "spoken_text": " ".join(text.split()[:50]),
        "claims": [{"event_id": item.event_id, "text": "A bounded claim.", "quote": f"  {text}  "}],
    })
    archived = publication_evidence([item], [story])[0]
    assert archived.evidence == text


def test_verbatim_guard_also_checks_summary_when_full_text_differs():
    text = " ".join(f"term{index}" for index in range(51))
    item = event(evidence=text, metadata={"full_text": "A different full source body."})
    row = story_row([item])
    story = Story(**row, source_urls=[item.url], scores={"total": 85})
    story = replace(story, editorial={
        "spoken_text": text,
        "claims": [{"event_id": item.event_id, "text": "A claim.", "quote": "term0 term1"}],
    })
    with pytest.raises(SchemaError, match="overlong source passage"):
        publication_evidence([item], [story])
