"""Generate spoken-word MP3 audio through an explicit TTS provider."""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_EDGE_VOICE = "en-US-AriaNeural"
_OPENAI_MODEL = "gpt-4o-mini-tts"


def _chunk_text(text: str, limit: int = 3500) -> list[str]:
    """Split narration below provider character limits at paragraph/sentence boundaries."""
    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        parts = [paragraph]
        if len(paragraph) > limit:
            parts = [part.strip() + "." for part in paragraph.split(".") if part.strip()]
        for part in parts:
            candidate = f"{current}\n\n{part}".strip()
            if current and len(candidate) > limit:
                chunks.append(current)
                current = part
            else:
                current = candidate
            while len(current) > limit:
                chunks.append(current[:limit])
                current = current[limit:]
    if current:
        chunks.append(current)
    return chunks


def _concat_mp3(parts: list[bytes]) -> bytes:
    if len(parts) == 1:
        return parts[0]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to combine TTS chunks")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        paths = []
        for index, content in enumerate(parts):
            path = root / f"part-{index:03d}.mp3"
            path.write_bytes(content)
            paths.append(path)
        listing = root / "parts.txt"
        listing.write_text("".join(f"file '{path}'\n" for path in paths), encoding="utf-8")
        output = root / "combined.mp3"
        result = subprocess.run(
            [ffmpeg, "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(output)],
            capture_output=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("failed to combine TTS chunks")
        return output.read_bytes()


def _generate_edge_tts(text: str) -> Optional[bytes]:
    """Best-effort Edge TTS, retained for local/no-key operation."""
    try:
        import edge_tts  # noqa: PLC0415

        async def _run() -> bytes:
            communicate = edge_tts.Communicate(
                text,
                os.environ.get("EDGE_TTS_VOICE", _EDGE_VOICE),
            )
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
    """Generate MP3 through the supported OpenAI audio API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY is not configured for OpenAI TTS")
        return None
    try:
        from openai import OpenAI  # noqa: PLC0415

        client = OpenAI(
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=api_key,
            timeout=float(os.environ.get("TTS_TIMEOUT_SECONDS", "90")),
            max_retries=int(os.environ.get("TTS_MAX_RETRIES", "1")),
        )
        parts = []
        for chunk in _chunk_text(text):
            response = client.audio.speech.create(
                model=os.environ.get("OPENAI_TTS_MODEL", _OPENAI_MODEL),
                voice=os.environ.get("OPENAI_TTS_VOICE", "alloy"),
                input=chunk,
                response_format="mp3",
            )
            parts.append(response.content)
        return _concat_mp3(parts)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI TTS failed: %s", exc)
        return None


def generate_audio(text: str) -> Optional[bytes]:
    """Convert text to MP3 using the configured provider, without silent fallback."""
    if not isinstance(text, str) or len(text.strip()) < 20:
        logger.warning("Refusing to synthesize empty or implausibly short narration")
        return None
    provider = os.environ.get("TTS_PROVIDER", "edge").strip().lower()
    if provider == "edge":
        audio = _generate_edge_tts(text)
    elif provider == "openai":
        audio = _generate_openai_tts(text)
    else:
        logger.error("Unsupported TTS_PROVIDER: %s", provider)
        return None
    if not audio or len(audio) < int(os.environ.get("TTS_MIN_BYTES", "10000")):
        logger.warning("TTS provider returned empty or implausibly small audio")
        return None
    return audio


def write_audio(text: str, path: str = "radar.mp3") -> Optional[Path]:
    audio_bytes = generate_audio(text)
    if audio_bytes is None:
        return None
    out = Path(path)
    out.write_bytes(audio_bytes)
    logger.info("Audio written to %s (%d bytes)", out, len(audio_bytes))
    return out
