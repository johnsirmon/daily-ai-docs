"""Generate high-contrast show artwork with a small-screen-safe title."""

import argparse
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

SIZE = 3000
OUTPUT = Path("assets/podcast-cover-v3.jpg")
BACKGROUND = Path(__file__).resolve().parents[1] / "assets/podcast-background-v3.png"
BOLD = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
)
def _font(candidates: tuple[Path, ...], size: int) -> ImageFont.FreeTypeFont:
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        raise FileNotFoundError(f"no supported artwork font found: {candidates}")
    return ImageFont.truetype(path, size)


def create_cover() -> Image.Image:
    with Image.open(BACKGROUND) as source:
        image = ImageOps.fit(source.convert("RGB"), (SIZE, SIZE))
    draw = ImageDraw.Draw(image)
    mint = (60, 235, 200)
    white = (245, 249, 252)
    draw.rounded_rectangle((250, 280, 830, 340), radius=30, fill=mint)
    for text, top, maximum, color in (
        ("DAILY AI", 520, 480, white),
        ("DEVELOPER", 1120, 340, mint),
        ("BRIEF", 1530, 660, white),
    ):
        font = _font(BOLD, maximum)
        while draw.textbbox((0, 0), text, font=font)[2] > 2500:
            maximum -= 2
            font = _font(BOLD, maximum)
        draw.text((250, top), text, font=font, anchor="lt", fill=color)
    return image


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
    args = parser.parse_args()
    if args.episode_source is not None:
        if args.output == OUTPUT:
            parser.error("--episode-source requires an explicit episode --output, not the show cover")
        export_episode_artwork(args.episode_source, args.output)
        print(f"wrote {args.output} ({SIZE}x{SIZE}, RGB JPEG, under 1 MB)")
        return
    image = create_cover()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, format="JPEG", quality=90, optimize=True, subsampling=0)
    print(f"wrote {args.output} ({image.width}x{image.height}, RGB)")


if __name__ == "__main__":
    main()
