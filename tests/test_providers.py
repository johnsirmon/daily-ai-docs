from unittest.mock import MagicMock, patch

import pytest

from pipeline.models_client import (
    EditorialConfigurationError, GEMINI_BASE_URL, editorial_model_config,
    configured_model, get_editorial_client, get_model_client,
)
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


def clear_editorial_environment(monkeypatch):
    for name in ("AI_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "AI_BASE_URL",
                 "AI_MODEL", "GEMINI_MODEL", "AI_PROVIDER", "AI_TIMEOUT_SECONDS", "AI_MAX_RETRIES"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("key_name", ["AI_API_KEY", "GEMINI_API_KEY"])
def test_editorial_uses_only_dedicated_gemini_boundary(monkeypatch, key_name):
    clear_editorial_environment(monkeypatch)
    monkeypatch.setenv(key_name, "mock-dedicated-key")
    if key_name == "AI_API_KEY":
        monkeypatch.setenv("AI_PROVIDER", "gemini")
    with patch("openai.OpenAI") as constructor:
        assert get_editorial_client() is constructor.return_value
    assert constructor.call_args.kwargs == {
        "api_key": "mock-dedicated-key", "base_url": GEMINI_BASE_URL,
        "timeout": 45.0, "max_retries": 0,
    }
    assert editorial_model_config().model == "gemini-3.8-flash"


def test_editorial_never_falls_back_to_openai_or_github_credentials(monkeypatch):
    clear_editorial_environment(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "other-provider-key")
    monkeypatch.setenv("GITHUB_TOKEN", "github-key")
    with patch("openai.OpenAI") as constructor:
        with pytest.raises(EditorialConfigurationError, match="requires GEMINI_API_KEY"):
            get_editorial_client()
    constructor.assert_not_called()


@pytest.mark.parametrize("provider", [None, "", "openai", "anthropic"])
def test_legacy_ai_api_key_requires_explicit_gemini_provider_opt_in(monkeypatch, provider):
    clear_editorial_environment(monkeypatch)
    monkeypatch.setenv("AI_API_KEY", "legacy-other-provider-key")
    if provider is not None:
        monkeypatch.setenv("AI_PROVIDER", provider)
    with patch("openai.OpenAI") as constructor:
        with pytest.raises(EditorialConfigurationError, match="explicit AI_PROVIDER=gemini"):
            get_editorial_client()
    constructor.assert_not_called()


def test_gemini_key_takes_precedence_over_legacy_key_even_with_provider_opt_in(monkeypatch):
    clear_editorial_environment(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "dedicated-gemini-key")
    monkeypatch.setenv("AI_API_KEY", "legacy-other-provider-key")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    with patch("openai.OpenAI") as constructor:
        get_editorial_client()
    assert constructor.call_args.kwargs["api_key"] == "dedicated-gemini-key"


@pytest.mark.parametrize("gemini_model,expected", [
    (None, "gemini-3.8-flash"), ("gemini-configured-flash", "gemini-configured-flash"),
])
def test_editorial_model_never_uses_legacy_ai_model(monkeypatch, gemini_model, expected):
    clear_editorial_environment(monkeypatch)
    monkeypatch.setenv("AI_MODEL", "gpt-5-mini")
    if gemini_model is not None:
        monkeypatch.setenv("GEMINI_MODEL", gemini_model)
    assert editorial_model_config().model == expected
    assert configured_model() == "gpt-5-mini"
    assert editorial_model_config({"model": "gemini-explicit-flash"}).model == "gemini-explicit-flash"


@pytest.mark.parametrize("url", [
    "https://api.openai.com/v1",
    "https://generativelanguage.googleapis.com.attacker.example/v1beta/openai/",
    "http://generativelanguage.googleapis.com/v1beta/openai/",
    "https://user@generativelanguage.googleapis.com/v1beta/openai/",
    "https://generativelanguage.googleapis.com/v1beta/openai/?key=test",
    "https://generativelanguage.googleapis.com/v1beta/openai/#fragment",
])
def test_editorial_rejects_non_gemini_or_ambiguous_endpoints(monkeypatch, url):
    clear_editorial_environment(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "mock-dedicated-key")
    with patch("openai.OpenAI") as constructor:
        with pytest.raises(EditorialConfigurationError, match="Gemini-compatible endpoint"):
            get_editorial_client({"base_url": url})
    constructor.assert_not_called()


def test_editorial_explicit_config_overrides_legacy_settings_safely(monkeypatch):
    clear_editorial_environment(monkeypatch)
    monkeypatch.setenv("AI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("AI_MODEL", "gpt-5-mini")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-dedicated-key")
    with pytest.raises(EditorialConfigurationError):
        get_editorial_client()
    config = {"base_url": GEMINI_BASE_URL, "model": "gemini-configured-flash", "timeout_seconds": 20}
    with patch("openai.OpenAI") as constructor:
        get_editorial_client(config)
    assert constructor.call_args.kwargs["base_url"] == GEMINI_BASE_URL
    assert constructor.call_args.kwargs["timeout"] == 20
    assert editorial_model_config(config).model == "gemini-configured-flash"


@pytest.mark.parametrize("model", ["gpt-5-mini", "models/gemini-3.8-flash", "gemini-3.8-flash?key=x", None])
def test_editorial_rejects_non_gemini_models(monkeypatch, model):
    clear_editorial_environment(monkeypatch)
    with pytest.raises(EditorialConfigurationError, match="Gemini model"):
        editorial_model_config({"model": model})
