"""Tests that pipeline prompts contain narrative quality guardrails.

Validates that the text of the prompts sent to the AI models includes explicit
instructions to avoid introductory narration, repetitive openers, and canned
phrases that degrade the quality of generated content.
"""

import json
from unittest.mock import MagicMock

import pipeline.blurbs as _blurbs_mod
import pipeline.narrate as _narrate_mod


# ── Helpers ───────────────────────────────────────────────────────────────────

def _repo_item():
    return {
        "repo": "org/my-tool",
        "stars": 1500,
        "description": "A great AI tool",
        "language": "Python",
        "forks": 200,
        "open_issues": 12,
        "commit_trend": "rising",
        "weekly_commits": [5, 8, 10, 14],
        "contributor_count": 30,
        "prs_merged_14d": 6,
        "created_at": "2024-01-01",
        "topics": ["ai", "llm"],
    }


def _make_fake_client(response_content: str):
    """Return a mock OpenAI-compatible client that records the prompt and returns a fixed response."""
    captured = {}

    completion = MagicMock()
    completion.choices[0].message.content = response_content

    client = MagicMock()

    def _create(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return completion

    client.chat.completions.create.side_effect = _create
    return client, captured


def _capture_deepdive_prompt(monkeypatch):
    """Return the prompt string that generate_repo_deepdive would send."""
    client, captured = _make_fake_client("word " * 160)
    monkeypatch.setattr(_blurbs_mod, "_get_client", lambda: client)
    _blurbs_mod.generate_repo_deepdive(_repo_item(), "AI Tools")
    return captured["prompt"]


def _capture_topic_meta_prompt(monkeypatch):
    """Return the prompt string that generate_topic_meta would send."""
    response = json.dumps({
        "why": "word " * 45,
        "learn": "skill description",
        "community_pulse": "pulse info",
        "action_items": ["do this"],
    })
    client, captured = _make_fake_client(response)
    monkeypatch.setattr(_blurbs_mod, "_get_client", lambda: client)
    _blurbs_mod.generate_topic_meta("AI Tools", [_repo_item()], [])
    return captured["prompt"]


# ── Deep-dive prompt quality tests ───────────────────────────────────────────

def test_deepdive_prompt_bans_this_repository_opener(monkeypatch):
    prompt = _capture_deepdive_prompt(monkeypatch)
    assert "Do NOT open with 'This repository'" in prompt


def test_deepdive_prompt_bans_this_project_opener(monkeypatch):
    prompt = _capture_deepdive_prompt(monkeypatch)
    assert "'This project'" in prompt


def test_deepdive_prompt_bans_welcome_phrases(monkeypatch):
    prompt = _capture_deepdive_prompt(monkeypatch)
    assert "Welcome to" in prompt


def test_deepdive_prompt_bans_in_this_segment(monkeypatch):
    prompt = _capture_deepdive_prompt(monkeypatch)
    assert "In this segment" in prompt


def test_deepdive_prompt_requires_varied_sentence_structure(monkeypatch):
    prompt = _capture_deepdive_prompt(monkeypatch)
    assert "Vary sentence structure" in prompt


def test_deepdive_prompt_requires_engaging_start(monkeypatch):
    prompt = _capture_deepdive_prompt(monkeypatch)
    assert "engaging observation" in prompt


def test_deepdive_prompt_no_system_role_intro(monkeypatch):
    """The prompt should not contain a 'You are writing...' preamble that encourages intro narration."""
    prompt = _capture_deepdive_prompt(monkeypatch)
    assert "You are writing a spoken podcast segment" not in prompt


# ── Topic-meta prompt quality tests ──────────────────────────────────────────

def test_topic_meta_prompt_bans_this_topic_opener(monkeypatch):
    prompt = _capture_topic_meta_prompt(monkeypatch)
    assert "Do NOT start with 'This topic'" in prompt


def test_topic_meta_prompt_bans_this_week_opener(monkeypatch):
    prompt = _capture_topic_meta_prompt(monkeypatch)
    assert "'This week'" in prompt


def test_topic_meta_prompt_requires_specific_names(monkeypatch):
    prompt = _capture_topic_meta_prompt(monkeypatch)
    assert "name tools or trends" in prompt or "Name the exact" in prompt


# ── Narrate transition variety tests ─────────────────────────────────────────

def test_topic_transitions_has_at_least_five_phrases():
    assert len(_narrate_mod._TOPIC_TRANSITIONS) >= 5


def test_repo_introductions_has_at_least_three_phrases():
    assert len(_narrate_mod._REPO_INTRODUCTIONS) >= 3


def test_topic_transitions_all_contain_name_placeholder():
    for phrase in _narrate_mod._TOPIC_TRANSITIONS:
        assert "{name}" in phrase, f"Phrase missing {{name}}: {phrase!r}"


def test_repo_introductions_all_contain_repo_placeholder():
    for phrase in _narrate_mod._REPO_INTRODUCTIONS:
        assert "{repo}" in phrase, f"Phrase missing {{repo}}: {phrase!r}"
