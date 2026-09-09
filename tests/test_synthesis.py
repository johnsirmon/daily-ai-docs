import json
from unittest.mock import MagicMock, patch

import pytest

from pipeline.rank import event_to_story
from pipeline.schema import SourceEvent
from pipeline.synthesis import refine_stories


def event(event_id="e1"):
    return SourceEvent(
        event_id=event_id,
        source_type="announcement",
        title="Tool update",
        url=f"https://example.com/{event_id}",
        product="Tool",
        topic="Agents",
        published_at="2026-09-07T10:00:00Z",
        fetched_at="2026-09-07T11:00:00Z",
        evidence="Fixes a typo.",
        metadata={"priority": 20},
    )


def client_response(payload):
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps(payload)))
    ]
    return client


def test_required_synthesis_rejects_empty_omission(monkeypatch):
    item = event()
    monkeypatch.setenv("AI_SYNTHESIS", "required")
    with patch("pipeline.synthesis.get_model_client", return_value=client_response({"decisions": []})):
        with pytest.raises(Exception, match="every selected event"):
            refine_stories([item], [event_to_story(item)])


def test_synthesis_cannot_replace_extractive_facts(monkeypatch):
    item = event()
    monkeypatch.setenv("AI_SYNTHESIS", "required")
    response = {"decisions": [{
        "event_id": "e1",
        "action": "watch",
        "what_changed": "One million users and private prompts were sold.",
    }]}
    with patch("pipeline.synthesis.get_model_client", return_value=client_response(response)):
        stories, _ = refine_stories([item], [event_to_story(item)])
    assert stories[0].what_changed == "Fixes a typo."
    assert "million" not in stories[0].what_changed


def test_required_synthesis_rejects_duplicate_or_unknown_ids(monkeypatch):
    items = [event("e1"), event("e2")]
    monkeypatch.setenv("AI_SYNTHESIS", "required")
    response = {"decisions": [{"event_id": "e1", "action": "watch"}, {"event_id": "e1", "action": "skip"}]}
    with patch("pipeline.synthesis.get_model_client", return_value=client_response(response)):
        with pytest.raises(Exception, match="omitted, duplicated, or invented"):
            refine_stories(items, [event_to_story(item) for item in items])
