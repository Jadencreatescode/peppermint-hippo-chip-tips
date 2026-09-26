"""Build the Peppermint Hippo Chip Tips app icons from the uploaded CAGE sign.

The club sign is a black CAGE wordmark on a white background.  It is cropped to
the glyphs, cleaned of JPEG noise, and centred on a white square at a size that
survives the Android circular mask.

Run with:  uv run --with pillow python scripts/build_icons.py
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "brand" / "cage-sign-source.jpeg"
OUTPUT = ROOT / "static" / "icons"

BACKGROUND = 255
# Fraction of the icon width the wordmark occupies.  Android maskable icons only
# guarantee the centre circle, so they get more breathing room than the legacy
# and Apple icons, which are shown almost unmasked.
LAYOUTS = {
    "icon-192.png": (192, 0.78),
    "icon-512.png": (512, 0.78),
    "icon-maskable-192.png": (192, 0.66),
    "icon-maskable-512.png": (512, 0.66),
    "apple-touch-icon-180.png": (180, 0.76),
}
# Map the scanned sign back to solid ink and clean white, keeping the smoothed
# edge pixels in between so the small icons stay smooth.
CONTRAST = [0 if value <= 60 else 255 if value >= 235 else round((value - 60) * 255 / 175) for value in range(256)]


def wordmark():
    source = Image.open(SOURCE).convert("L")
    width, height = source.size
    ink = source.point(lambda value: 255 if value < 100 else 0)
    pixels = ink.load()
    # Blank scan border lines, which are dark across the whole width or height,
    # so the glyph bounding box below measures the letters only.
    for y in range(height):
        if sum(1 for x in range(width) if pixels[x, y]) >= width * 0.9:
            for x in range(width):
                pixels[x, y] = 0
    for x in range(width):
        if sum(1 for y in range(height) if pixels[x, y]) >= height * 0.9:
            for y in range(height):
                pixels[x, y] = 0
    box = ink.getbbox()
    return source.crop(box).point(CONTRAST), box


def build():
    glyphs, box = wordmark()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {"source": str(SOURCE.relative_to(ROOT)), "glyph_box": box, "glyph_size": glyphs.size, "icons": {}}
    for name, (size, fraction) in sorted(LAYOUTS.items()):
        target_width = max(1, round(size * fraction))
        target_height = max(1, round(glyphs.height * target_width / glyphs.width))
        canvas = Image.new("L", (size, size), BACKGROUND)
        canvas.paste(
            glyphs.resize((target_width, target_height), Image.LANCZOS),
            ((size - target_width) // 2, (size - target_height) // 2),
        )
        image = canvas.convert("RGB")
        image.save(OUTPUT / name, format="PNG", optimize=False)
        report["icons"][name] = {
            "size": size,
            "wordmark": [target_width, target_height],
            "half_diagonal": round(0.5 * (target_width ** 2 + target_height ** 2) ** 0.5 / size, 4),
        }
    for name, details in report["icons"].items():
        limit = "<= 0.40" if "maskable" in name else "unmasked"
        print(f"{name:28s} {details['size']:>4}px  wordmark {details['wordmark'][0]}x{details['wordmark'][1]}  half diagonal {details['half_diagonal']} {limit}")
    return report


if __name__ == "__main__":
    build()
