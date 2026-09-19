"""Generate high-contrast show artwork with a small-screen-safe title."""

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    image = create_cover()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, format="JPEG", quality=90, optimize=True, subsampling=0)
    print(f"wrote {args.output} ({image.width}x{image.height}, RGB)")


if __name__ == "__main__":
    main()
