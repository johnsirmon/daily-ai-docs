"""Supported, explicitly configured model-provider access."""

import logging
import os
from dataclasses import dataclass
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class EditorialError(RuntimeError):
    """A required grounded-editorial stage failed; publication must stop."""


class EditorialConfigurationError(EditorialError):
    """The dedicated Gemini provider or its request budget is not configured safely."""


class EditorialProviderError(EditorialError):
    """The provider failed, timed out, or returned an incomplete response."""


class EditorialValidationError(EditorialError):
    """Model output did not satisfy the grounded editorial schema."""


class EditorialVerificationError(EditorialError):
    """Independent verification did not approve all proposed editorial content."""


@dataclass(frozen=True)
class EditorialModelConfig:
    base_url: str
    model: str
    timeout_seconds: float


def editorial_model_config(config: dict | None = None) -> EditorialModelConfig:
    """Resolve only the explicitly supported Gemini boundary, never a provider fallback."""
    if config is not None and not isinstance(config, dict):
        raise EditorialConfigurationError("editorial config must be an object")
    values = config or {}
    base_url = values.get("base_url", os.environ.get("AI_BASE_URL", GEMINI_BASE_URL))
    model = values.get("model", os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"))
    if not isinstance(base_url, str):
        raise EditorialConfigurationError("Gemini base_url must be a string")
    try:
        parsed = urlparse(base_url)
    except ValueError as exc:
        raise EditorialConfigurationError("Gemini base_url is invalid") from exc
    if (parsed.scheme != "https" or parsed.netloc != "generativelanguage.googleapis.com"
            or parsed.path.rstrip("/") != "/v1beta/openai" or parsed.query or parsed.fragment):
        raise EditorialConfigurationError("grounded editorial requires Google's Gemini-compatible endpoint")
    if not isinstance(model, str) or not re.fullmatch(r"gemini-[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", model):
        raise EditorialConfigurationError("grounded editorial requires an explicit Gemini model")
    raw_timeout = values.get("timeout_seconds", os.environ.get("AI_TIMEOUT_SECONDS", "45"))
    if isinstance(raw_timeout, bool):
        raise EditorialConfigurationError("editorial timeout_seconds must be numeric")
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise EditorialConfigurationError("editorial timeout_seconds must be numeric") from exc
    if not 1 <= timeout <= 60:
        raise EditorialConfigurationError("editorial timeout_seconds must be between 1 and 60")
    retries = values.get("max_retries", os.environ.get("AI_MAX_RETRIES", "0"))
    if str(retries) != "0":
        raise EditorialConfigurationError("grounded editorial does not permit automatic retries")
    return EditorialModelConfig(GEMINI_BASE_URL, model, timeout)


def get_editorial_client(config: dict | None = None):
    """Create a fail-closed Gemini client with zero retries and a bounded timeout.

    Prefer GEMINI_API_KEY. AI_API_KEY is accepted only with AI_PROVIDER=gemini.
    Model selection uses config model, then GEMINI_MODEL, never legacy AI_MODEL.
    AI_BASE_URL (or config base_url) must identify Google's supported endpoint;
    an existing OpenAI credential is never silently sent to Google.
    """
    settings = editorial_model_config(config)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and os.environ.get("AI_PROVIDER", "").strip().lower() == "gemini":
        api_key = os.environ.get("AI_API_KEY")
    if not api_key or not api_key.strip():
        raise EditorialConfigurationError(
            "grounded editorial requires GEMINI_API_KEY, or AI_API_KEY with explicit AI_PROVIDER=gemini"
        )
    try:
        from openai import OpenAI  # noqa: PLC0415
    except ImportError as exc:
        raise EditorialConfigurationError("grounded editorial requires the existing OpenAI client dependency") from exc
    try:
        return OpenAI(
            base_url=settings.base_url,
            api_key=api_key,
            timeout=settings.timeout_seconds,
            max_retries=0,
        )
    except (TypeError, ValueError) as exc:
        raise EditorialConfigurationError("Gemini client initialization failed") from exc


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
