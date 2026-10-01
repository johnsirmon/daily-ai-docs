"""Explicit reviewed short-brief approval; never a fallback for truncated audio."""
from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher
import hashlib
import re

from .audio import narration_duration_bounds


def reviewed_duration_bounds(manifest) -> tuple[float, float]:
    policy = manifest.generation.get("duration_policy")
    if "duration_policy" not in manifest.generation:
        return (narration_duration_bounds(len(manifest.narration.split()))
                if manifest.schema_version == 4 else (300, 480))
    if manifest.schema_version != 3 or manifest.generation.get("edition") != "reviewed-edge":
        raise ValueError("short brief approval is limited to reviewed Edge daily episodes")
    fields = {"class", "rationale", "approved_at", "script", "script_sha256",
              "source_audio_sha256", "transcript_sha256"}
    if not isinstance(policy, dict) or set(policy) != fields or policy["class"] != "short_brief":
        raise ValueError("duration_policy requires an explicit short_brief approval")
    rationale = policy["rationale"]
    if not isinstance(rationale, str) or not 40 <= len(rationale.strip()) <= 1200:
        raise ValueError("short brief requires a bounded substantive editorial rationale")
    stamp = policy["approved_at"]
    if not isinstance(stamp, str) or datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("short brief approval requires a timezone-aware timestamp")
    script = policy["script"]
    if not isinstance(script, str) or len(script) > 16000 or not 450 <= len(script.split()) <= 750:
        raise ValueError("short brief requires a complete approved 450-750 word script")
    if policy["script_sha256"] != hashlib.sha256(script.encode()).hexdigest():
        raise ValueError("short brief approved script hash mismatch")
    if policy["source_audio_sha256"] != manifest.generation.get("source_audio_sha256"):
        raise ValueError("short brief approval belongs to different source audio")
    transcript_hash = hashlib.sha256(manifest.narration.encode()).hexdigest()
    if (policy["transcript_sha256"] != transcript_hash
            or manifest.generation.get("transcript", {}).get("sha256") != transcript_hash):
        raise ValueError("short brief approval belongs to a different transcript")
    words = lambda text: re.findall(r"[a-z0-9]+", text.casefold())
    intended, actual = words(script), words(manifest.narration)
    from .disclosure import AI_NARRATION_DISCLOSURE
    disclosure = " ".join(words(AI_NARRATION_DISCLOSURE))
    if any(disclosure not in " ".join(tokens) for tokens in (intended, actual)):
        raise ValueError("short brief requires spoken disclosure in script and transcript")
    if intended[:8] != actual[:8] or intended[-8:] != actual[-8:]:
        raise ValueError("short brief transcript must retain the approved opening and ending")
    matches = SequenceMatcher(None, intended, actual, autojunk=False)
    coverage = sum(block.size for block in matches.get_matching_blocks()) / len(intended)
    if coverage < 0.97 or not 0.95 <= len(actual) / len(intended) <= 1.05:
        raise ValueError("short brief transcript omits or changes approved script content")
    # A bounded 3-5 minute class, with a tighter script-derived lower bound:
    # no more than 190 intended words/minute. Existing decode/silence checks remain.
    return max(180, len(script.split()) / 190 * 60), 300
