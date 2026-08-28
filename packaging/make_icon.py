"""Build the application icon from the logo.

    python packaging/make_icon.py

Produces packaging/app_icon.ico for the Windows build. Kept as a script rather
than a checked-in binary nobody can regenerate: when the logo changes, this is
the one command that brings the icon along with it.

Two things the source artwork cannot do on its own:

  * It is white on transparent, which vanishes against a light taskbar or a
    light Explorer background, so it is composited onto the app's own dark
    rounded square.
  * It is a stacked lockup, drone over wordmark, at roughly 3:2. An icon is
    square, and below about 64px the wordmark is a grey smudge that only
    muddies the silhouette, so the small sizes carry the drone mark alone.
"""

import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))

SOURCE = os.path.join(ROOT, "assets", "logo_white.png")
TARGET = os.path.join(HERE, "app_icon.ico")

BACKGROUND = (13, 17, 23, 255)      # #0d1117, the app background
SIZES = [16, 24, 32, 48, 64, 128, 256]

# Below this, drop the wordmark and keep only the drone.
WORDMARK_FLOOR = 64
# Fraction of the drone-over-wordmark image that is the drone.
MARK_FRACTION = 0.56


def _trimmed(image: Image.Image) -> Image.Image:
    """Crop away transparent margin, so padding is measured from real ink."""
    bbox = image.split()[3].getbbox()
    return image.crop(bbox) if bbox else image


def render(art: Image.Image, mark: Image.Image, size: int) -> Image.Image:
    source = mark if size <= WORDMARK_FLOOR else art
    # The mark alone can sit larger; the full lockup needs more air.
    padding = 0.72 if size <= WORDMARK_FLOOR else 0.82

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=max(2, int(size * 0.18)), fill=BACKGROUND)

    scaled = source.copy()
    scaled.thumbnail((int(size * padding), int(size * padding)), Image.LANCZOS)
    canvas.alpha_composite(
        scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2))
    return canvas


def main() -> int:
    if not os.path.exists(SOURCE):
        print(f"missing {SOURCE}", file=sys.stderr)
        return 1

    logo = _trimmed(Image.open(SOURCE).convert("RGBA"))
    mark = _trimmed(logo.crop((0, 0, logo.width, int(logo.height * MARK_FRACTION))))

    frames = [render(logo, mark, size) for size in SIZES]
    frames[-1].save(TARGET, format="ICO",
                    sizes=[(f.width, f.height) for f in frames],
                    append_images=frames[:-1])
    print(f"wrote {TARGET} ({', '.join(str(s) for s in SIZES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
