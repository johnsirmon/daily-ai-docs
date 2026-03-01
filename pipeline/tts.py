"""Generate spoken-word MP3 audio from text via GitHub Models / OpenAI TTS.

Uses the built-in GITHUB_TOKEN — no extra API keys required.
Model: tts-1 (OpenAI), voice: alloy
Endpoint: https://models.inference.ai.azure.com
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL = "tts-1"
_VOICE = "alloy"
_ENDPOINT = "https://models.inference.ai.azure.com"


def generate_audio(text: str) -> Optional[bytes]:
    """Convert text to MP3 bytes using OpenAI TTS via GitHub Models endpoint.

    Returns MP3 bytes on success, None if the API is unavailable.
    """
    try:
        from openai import OpenAI  # noqa: PLC0415

        client = OpenAI(
            base_url=_ENDPOINT,
            api_key=os.environ["GITHUB_TOKEN"],
        )
        response = client.audio.speech.create(
            model=_MODEL,
            voice=_VOICE,
            input=text,
            response_format="mp3",
        )
        return response.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("TTS generation failed: %s", exc)
        return None


def write_audio(text: str, path: str = "radar.mp3") -> Optional[Path]:
    """Generate audio from text and write to path. Returns Path or None on failure."""
    audio_bytes = generate_audio(text)
    if audio_bytes is None:
        return None
    out = Path(path)
    out.write_bytes(audio_bytes)
    logger.info("Audio written to %s (%d bytes)", out, len(audio_bytes))
    return out
