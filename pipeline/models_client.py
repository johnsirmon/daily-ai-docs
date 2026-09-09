"""Supported, explicitly configured model-provider access."""

import logging
import os

logger = logging.getLogger(__name__)


def get_model_client():
    """Return an OpenAI-compatible client when a dedicated model key is configured.

    Production synthesis never reuses GITHUB_TOKEN. Set AI_API_KEY (or
    OPENAI_API_KEY), and optionally AI_BASE_URL and AI_MODEL.
    """
    api_key = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.info("No dedicated AI_API_KEY/OPENAI_API_KEY; deterministic synthesis only")
        return None
    try:
        from openai import OpenAI  # noqa: PLC0415

        return OpenAI(
            base_url=os.environ.get("AI_BASE_URL", "https://api.openai.com/v1"),
            api_key=api_key,
            timeout=float(os.environ.get("AI_TIMEOUT_SECONDS", "45")),
            max_retries=int(os.environ.get("AI_MAX_RETRIES", "1")),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Configured model client unavailable: %s", exc)
        return None


def configured_model() -> str:
    return os.environ.get("AI_MODEL", "gpt-5-mini")


def get_github_models_client():
    """Backward-compatible alias; GitHub Models itself is retired."""
    return get_model_client()
