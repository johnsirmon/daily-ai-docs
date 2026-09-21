"""Export reviewed show and episode artwork as square RGB JPEGs."""

import argparse
import io
from pathlib import Path

from PIL import Image

SIZE = 3000
OUTPUT = Path("assets/podcast-cover-v4.jpg")
SOURCE = Path(__file__).resolve().parents[1] / "assets/podcast-source-v4.png"


def create_cover() -> Image.Image:
    return create_episode_artwork(SOURCE)


def create_episode_artwork(source_path: Path) -> Image.Image:
    """Resize an operator-reviewed square export without adding cover typography."""
    with Image.open(source_path) as source:
        if source.format not in {"PNG", "JPEG"} or getattr(source, "n_frames", 1) != 1:
            raise ValueError("episode source must be a single PNG or JPEG image")
        if source.width != source.height:
            raise ValueError("episode source must be square; crop and review it before export")
        source.load()
        if "A" in source.getbands() or "transparency" in source.info:
            if source.convert("RGBA").getchannel("A").getextrema()[0] != 255:
                raise ValueError("episode source must not contain transparent pixels")
        image = source.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    # Do not propagate EXIF, prompts, or other source metadata into public artwork.
    image.info.clear()
    return image


def export_episode_artwork(source_path: Path, output: Path) -> None:
    if output.suffix != ".jpg":
        raise ValueError("episode output must use the .jpg extension")
    image = create_episode_artwork(source_path)
    encoded = io.BytesIO()
    image.save(encoded, format="JPEG", quality=85, optimize=True, subsampling=2)
    content = encoded.getvalue()
    if len(content) >= 1_000_000:
        raise ValueError("episode export exceeds 1 MB; simplify the source and review again")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Public filenames are immutable; corrections must use a new versioned name.
    with output.open("xb") as handle:
        handle.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--episode-source", type=Path, help="reviewed square PNG/JPEG; no cover text is added")
    parser.add_argument("--local-execution", type=Path, help="validated browser source handoff (use python -m)")
    args = parser.parse_args()
    if args.local_execution is not None:
        if args.episode_source is None:
            parser.error("--local-execution requires --episode-source")
        from pipeline.local_execution import load, require_artifact
        state = load(args.local_execution)
        require_artifact(
            args.local_execution, args.episode_source,
            identity=state["request"]["identity"], kind="chatgpt-image",
            parent_request_sha256=state["request"]["parent_request_sha256"],
        )
    if args.episode_source is not None:
        if args.output == OUTPUT:
            parser.error("--episode-source requires an explicit episode --output, not the show cover")
        export_episode_artwork(args.episode_source, args.output)
        print(f"wrote {args.output} ({SIZE}x{SIZE}, RGB JPEG, under 1 MB)")
        return
    image = create_cover()
    encoded = io.BytesIO()
    image.save(encoded, format="JPEG", quality=80, optimize=True, subsampling=2)
    content = encoded.getvalue()
    if len(content) >= 1_000_000:
        raise ValueError("show export exceeds 1 MB; simplify the source and review again")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(content)
    print(f"wrote {args.output} ({image.width}x{image.height}, RGB JPEG, under 1 MB)")


if __name__ == "__main__":
    main()
