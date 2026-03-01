"""Generate spoken-word MP3 audio from text via Microsoft Edge TTS.

Uses the edge-tts package (Microsoft Edge's neural TTS, no API key needed).
Falls back to OpenAI TTS via GitHub Models if edge-tts is unavailable.
Voice: en-US-AriaNeural (same engine as Edge Read Aloud).
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_EDGE_VOICE = "en-US-AriaNeural"
_OPENAI_MODEL = "tts-1"
_OPENAI_ENDPOINT = "https://models.inference.ai.azure.com"


def _generate_edge_tts(text: str) -> Optional[bytes]:
    """Generate MP3 bytes using Microsoft Edge TTS (no API key required)."""
    try:
        import edge_tts  # noqa: PLC0415

        async def _run() -> bytes:
            communicate = edge_tts.Communicate(text, _EDGE_VOICE)
            chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            return b"".join(chunks)

        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        logger.warning("edge-tts failed: %s", exc)
        return None


def _generate_openai_tts(text: str) -> Optional[bytes]:
    """Fallback: generate MP3 bytes via OpenAI TTS through GitHub Models."""
    try:
        from openai import OpenAI  # noqa: PLC0415

        client = OpenAI(base_url=_OPENAI_ENDPOINT, api_key=os.environ["GITHUB_TOKEN"])
        response = client.audio.speech.create(
            model=_OPENAI_MODEL,
            voice="alloy",
            input=text,
            response_format="mp3",
        )
        return response.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI TTS fallback failed: %s", exc)
        return None


def generate_audio(text: str) -> Optional[bytes]:
    """Convert text to MP3 bytes. Tries edge-tts first, then OpenAI TTS.

    Returns MP3 bytes on success, None if all methods fail.
    """
    audio = _generate_edge_tts(text)
    if audio:
        return audio
    logger.info("Falling back to OpenAI TTS via GitHub Models")
    return _generate_openai_tts(text)


def write_audio(text: str, path: str = "radar.mp3") -> Optional[Path]:
    """Generate audio from text and write to path. Returns Path or None on failure."""
    audio_bytes = generate_audio(text)
    if audio_bytes is None:
        return None
    out = Path(path)
    out.write_bytes(audio_bytes)
    logger.info("Audio written to %s (%d bytes)", out, len(audio_bytes))
    return out
