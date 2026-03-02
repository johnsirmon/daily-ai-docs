"""Tests for pipeline/adhoc.py ad-hoc podcast episode generator."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from pipeline.adhoc import (
    research_topic,
    generate_adhoc_narration,
    run_adhoc,
    _fallback_narration,
    _slugify,
)


# ── research_topic ──────────────────────────────────────────────────────────


def test_research_topic_dry_run():
    result = research_topic("test topic", dry_run=True)
    assert result["topic"] == "test topic"
    assert result["exa_results"] == []
    assert "[dry-run]" in result["ai_summary"]


def test_research_topic_no_exa_key(monkeypatch):
    """Without EXA_API_KEY, exa_results should be empty and AI fallback used."""
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = research_topic("test topic", dry_run=False)
    assert result["exa_results"] == []
    # AI summary is empty because no GITHUB_TOKEN
    assert result["ai_summary"] == ""


def test_research_topic_with_exa_results(monkeypatch):
    """When Exa returns results, they should appear in the output."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    fake_exa_results = [
        {"title": "Article 1", "url": "https://example.com/1", "text": "Content 1"},
        {"title": "Article 2", "url": "https://example.com/2", "text": "Content 2"},
    ]
    with patch("pipeline.adhoc._exa_search", return_value=fake_exa_results), \
         patch("pipeline.adhoc._ai_research_with_context", return_value="synthesis"):
        result = research_topic("test topic", dry_run=False)
    assert len(result["exa_results"]) == 2
    assert result["ai_summary"] == "synthesis"


# ── generate_adhoc_narration ────────────────────────────────────────────────


def test_generate_adhoc_narration_fallback_when_no_client(monkeypatch):
    """When AI client is unavailable, falls back to simple narration."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    research = {"topic": "LLMs", "exa_results": [], "ai_summary": "Summary about LLMs."}
    result = generate_adhoc_narration("LLMs", research)
    assert "LLMs" in result
    assert "AI Skills Radar" in result


def test_generate_adhoc_narration_with_mock_ai(monkeypatch):
    """When AI client works, returns AI-generated narration."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="AI-generated narration about the topic."))
    ]
    with patch("pipeline.adhoc._get_ai_client", return_value=mock_client):
        result = generate_adhoc_narration(
            "AI Agents",
            {"topic": "AI Agents", "exa_results": [], "ai_summary": "Summary."},
        )
    assert result == "AI-generated narration about the topic."


# ── _fallback_narration ─────────────────────────────────────────────────────


def test_fallback_narration_contains_topic():
    research = {"ai_summary": "Some research text.", "exa_results": []}
    result = _fallback_narration("MLOps", research)
    assert "MLOps" in result
    assert "AI Skills Radar" in result
    assert "Some research text." in result


def test_fallback_narration_without_summary():
    result = _fallback_narration("Kubernetes", {"exa_results": []})
    assert "Kubernetes" in result


# ── _slugify ─────────────────────────────────────────────────────────────────


def test_slugify_basic():
    assert _slugify("Hello World") == "hello-world"


def test_slugify_special_chars():
    assert _slugify("AI/ML & NLP!") == "ai-ml-nlp"


def test_slugify_max_len():
    result = _slugify("a" * 100, max_len=10)
    assert len(result) == 10


def test_slugify_strips_leading_trailing_hyphens():
    assert _slugify("  --test-- ") == "test"


# ── run_adhoc ────────────────────────────────────────────────────────────────


def test_run_adhoc_dry_run(monkeypatch, tmp_path):
    """Dry run skips TTS and podcast.xml but returns valid episode dict."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    result = run_adhoc(
        topic="test topic",
        dry_run=True,
        mp3_url_template="https://example.com/{tag}/ep.mp3",
    )
    assert result["topic"] == "test topic"
    assert result["episode"]["mp3_url"] == "DRY_RUN"
    assert result["episode"]["title"] == "AI Skills Radar — test topic"
    assert result["episode"]["guid"].startswith("adhoc-test-topic-")
    assert len(result["narration"]) > 0

    # Narration script should be saved to cache
    assert (tmp_path / ".cache" / "adhoc_narration.txt").exists()


def test_run_adhoc_live_calls_tts_and_podcast(monkeypatch, tmp_path):
    """Live run calls write_audio and prepend_episode."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    tts_calls = []
    podcast_calls = []

    def fake_write_audio(text, path="adhoc-episode.mp3"):
        tts_calls.append(text)
        return None

    def fake_prepend_episode(episode, path="podcast.xml"):
        podcast_calls.append(episode)
        return Path(path)

    with patch("pipeline.tts.write_audio", side_effect=fake_write_audio), \
         patch("pipeline.podcast.prepend_episode", side_effect=fake_prepend_episode):
        result = run_adhoc(
            topic="Test AI",
            dry_run=False,
            mp3_url_template="https://x/{tag}/ep.mp3",
        )

    assert len(tts_calls) == 1
    assert len(podcast_calls) == 1
    assert podcast_calls[0]["guid"].startswith("adhoc-test-ai-")


def test_run_adhoc_episode_guid_is_deterministic(monkeypatch, tmp_path):
    """Same topic on same day should produce the same guid."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    r1 = run_adhoc(topic="Model Context Protocol", dry_run=True, mp3_url_template="")
    r2 = run_adhoc(topic="Model Context Protocol", dry_run=True, mp3_url_template="")
    assert r1["episode"]["guid"] == r2["episode"]["guid"]
    assert r1["episode"]["guid"].startswith("adhoc-model-context-protocol-")
