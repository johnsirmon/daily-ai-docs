"""Offline video planning from the exact podcast manifest; never uploads media."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .disclosure import episode_metadata_disclosure
from .schema import EpisodeManifest


def build_bundle(manifest: EpisodeManifest) -> dict:
    manifest.validate(require_audio=False)
    return {
        "schema_version": 1,
        "episode_id": manifest.episode_id,
        "published_at": manifest.published_at,
        "status": "unpublished_video_plan",
        "script_sha256": hashlib.sha256(manifest.narration.encode("utf-8")).hexdigest(),
        "transcript": manifest.narration,
        "captions": {"text": manifest.narration, "timing_status": "requires_alignment_to_final_audio"},
        "description": episode_metadata_disclosure(manifest.schema_version, manifest.generation)
                       + "\n\n" + manifest.show_notes,
        "chapters": [
            {"title": story.headline, "timestamp": None,
             "source_urls": story.source_urls,
             "visual_beats": [story.what_changed, story.why_it_matters, story.rationale],
             "research_review": story.editorial.get("paper_review") if story.kind == "research" else None}
            for story in manifest.stories
        ],
        "rights_status": "requires_voice_artwork_and_visual_clearance",
        "release_blockers": ["Align captions and chapters to final audio", "Create original useful visuals",
                             "Review spoken claims and final video", "Clear commercial media rights",
                             "Obtain upload authorization and platform access"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = build_bundle(EpisodeManifest.from_dict(json.loads(args.manifest.read_text(encoding="utf-8"))))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
