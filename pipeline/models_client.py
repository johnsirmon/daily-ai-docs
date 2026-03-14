"""Shared helpers for GitHub Models client access."""

import logging
import os


logger = logging.getLogger(__name__)

GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"


def get_github_models_client():
    """Return an OpenAI-compatible GitHub Models client or None."""
    try:
        from openai import OpenAI  # noqa: PLC0415

        return OpenAI(
            base_url=GITHUB_MODELS_ENDPOINT,
            api_key=os.environ["GITHUB_TOKEN"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("GitHub Models client unavailable: %s", exc)
        return None