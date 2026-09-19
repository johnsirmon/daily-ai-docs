"""Generate the deterministic 3000x3000 podcast show cover."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

SIZE = 3000
SOURCE = Path("assets/ai-update-wave.png")
OUTPUT = Path("assets/podcast-cover.jpg")
BOLD = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
)
REGULAR = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)


def _font(candidates: tuple[Path, ...], size: int):
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        raise FileNotFoundError(f"no supported artwork font found: {candidates}")
    return ImageFont.truetype(path, size)


def main() -> None:
    with Image.open(SOURCE) as source:
        image = source.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.08)

    overlay = Image.new("RGBA", image.size)
    shade = ImageDraw.Draw(overlay)
    for y in range(1050):
        alpha = int(225 * (1 - y / 1050) ** 1.7)
        shade.line((0, y, SIZE, y), fill=(3, 12, 27, alpha))
    for y in range(2320, SIZE):
        alpha = int(190 * ((y - 2320) / (SIZE - 2320)) ** 1.4)
        shade.line((0, y, SIZE, y), fill=(3, 12, 27, alpha))
    image = Image.alpha_composite(image.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(image)
    cyan = (49, 226, 210, 255)
    white = (244, 250, 255, 255)
    muted = (185, 207, 226, 255)
    shadow = (2, 8, 18, 230)

    draw.text(
        (1500, 225), "DAILY AI", font=_font(BOLD, 300), anchor="mm",
        fill=white, stroke_fill=shadow, stroke_width=14,
    )
    draw.rounded_rectangle((610, 410, 2390, 433), radius=11, fill=cyan)
    draw.text(
        (1500, 630), "DEVELOPER BRIEF", font=_font(BOLD, 190), anchor="mm",
        fill=cyan, stroke_fill=shadow, stroke_width=10,
    )
    draw.text(
        (1500, 2760), "KEEP UP WITHOUT DROWNING", font=_font(REGULAR, 88), anchor="mm",
        fill=muted, stroke_fill=shadow, stroke_width=6,
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(
        OUTPUT, format="JPEG", quality=70, optimize=True, progressive=True, subsampling=2,
    )
    print(f"wrote {OUTPUT} ({image.width}x{image.height}, RGB)")


if __name__ == "__main__":
    main()
