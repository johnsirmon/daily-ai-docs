from unittest.mock import MagicMock, patch

from pipeline.models_client import get_model_client
from pipeline.tts import _chunk_text, generate_audio


def test_model_client_does_not_reuse_github_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "github-only")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert get_model_client() is None


def test_model_client_uses_dedicated_key(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "dedicated")
    with patch("openai.OpenAI") as constructor:
        expected = MagicMock()
        constructor.return_value = expected
        assert get_model_client() is expected
    assert constructor.call_args.kwargs["api_key"] == "dedicated"
    assert "api.openai.com" in constructor.call_args.kwargs["base_url"]


def test_tts_provider_does_not_silently_fallback(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "edge")
    with patch("pipeline.tts._generate_edge_tts", return_value=None), \
         patch("pipeline.tts._generate_openai_tts") as openai_tts:
        assert generate_audio("This narration is long enough for a provider contract test.") is None
    openai_tts.assert_not_called()


def test_tts_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "unknown")
    assert generate_audio("This narration is long enough for a provider contract test.") is None


def test_openai_tts_chunks_stay_below_provider_limit():
    chunks = _chunk_text(("A sentence with useful developer context. " * 400).strip())
    assert len(chunks) > 1
    assert all(len(chunk) <= 3500 for chunk in chunks)
