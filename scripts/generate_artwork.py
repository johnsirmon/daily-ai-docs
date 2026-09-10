"""Generate the deterministic 3000×3000 podcast show cover."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 3000
OUTPUT = Path("assets/podcast-cover.jpg")
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(path: str, size: int):
    return ImageFont.truetype(path, size)


def main() -> None:
    image = Image.new("RGB", (SIZE, SIZE))
    pixels = image.load()
    for y in range(SIZE):
        t = y / (SIZE - 1)
        for x in range(SIZE):
            side = abs(x - SIZE / 2) / (SIZE / 2)
            glow = max(0.0, 1.0 - ((x - 1500) ** 2 + (y - 1150) ** 2) ** 0.5 / 1900)
            pixels[x, y] = (
                int(7 + 8 * glow + 4 * t),
                int(15 + 27 * glow + 12 * t),
                int(31 + 35 * glow + 15 * t - 5 * side),
            )

    draw = ImageDraw.Draw(image)
    cyan = (49, 226, 210)
    blue = (58, 133, 255)
    white = (244, 250, 255)
    muted = (157, 182, 207)

    # Radar field: quiet enough to support the title while signaling live updates.
    center = (1500, 1120)
    for radius, width, alpha_color in [
        (920, 8, (35, 80, 113)),
        (690, 7, (32, 103, 128)),
        (460, 6, (28, 122, 138)),
        (230, 5, (34, 142, 148)),
    ]:
        draw.ellipse(
            (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
            outline=alpha_color,
            width=width,
        )
    draw.line((center[0], 140, center[0], 2050), fill=(29, 90, 119), width=5)
    draw.line((520, center[1], 2480, center[1]), fill=(29, 90, 119), width=5)
    draw.pieslice((580, 200, 2420, 2040), 302, 338, fill=(13, 73, 91), outline=cyan, width=10)
    draw.ellipse((1465, 1085, 1535, 1155), fill=cyan)
    for x, y, r in [(2180, 670, 30), (940, 550, 23), (2020, 1430, 18), (760, 1510, 15)]:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=blue, outline=white, width=5)

    # Dark title plate preserves small-icon legibility.
    draw.rounded_rectangle((260, 620, 2740, 1815), radius=95, fill=(5, 18, 35), outline=(31, 116, 139), width=8)
    draw.text((1500, 790), "DAILY AI", font=_font(BOLD, 330), anchor="mm", fill=white, stroke_width=3)
    draw.rectangle((650, 1035, 2350, 1055), fill=cyan)
    draw.text((1500, 1280), "DEVELOPER", font=_font(BOLD, 245), anchor="mm", fill=cyan)
    draw.text((1500, 1540), "BRIEF", font=_font(BOLD, 245), anchor="mm", fill=white)

    # Audio waveform and promise line.
    baseline = 2220
    heights = [50, 100, 165, 260, 140, 80, 210, 330, 185, 95, 145, 260, 360, 220, 120, 70, 170, 285, 150, 80, 45]
    start = 420
    step = 108
    for index, height in enumerate(heights):
        x = start + index * step
        color = cyan if index % 3 else blue
        draw.rounded_rectangle((x, baseline - height, x + 34, baseline + height), radius=17, fill=color)
    draw.text((1500, 2660), "WHAT CHANGED  •  WHY IT MATTERS  •  ACT / WATCH / SKIP", font=_font(REGULAR, 80), anchor="mm", fill=muted)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, format="JPEG", quality=88, optimize=True, progressive=True, subsampling=1)
    print(f"wrote {OUTPUT} ({image.width}x{image.height}, RGB)")


if __name__ == "__main__":
    main()
