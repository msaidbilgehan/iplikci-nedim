"""Draws every icon of the product from its logo, the line drawing of İplikçi Nedim in packaging/logo/:
the interface's (web/public), the browser extension's (extension/static/icons) and the installers'
(packaging/assets). The face is filled white inside its outline with its lines in teal, on a teal tile: a line
drawing alone thins to nothing at 16 px, a light face still reads there. Small icons get thicker lines. Beside the
logo, his face in the colour of his word on the money (app.sayings): amber, red or grey where the logo is teal.

    uv run python -I packaging/icons.py
"""

from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "packaging" / "logo" / "white.png"  # white lines on a transparent ground
WEB = ROOT / "web" / "public"
EXTENSION = ROOT / "extension" / "static" / "icons"
ASSETS = ROOT / "packaging" / "assets"

TEAL = (15, 118, 110, 255)  # the interface's teal-700 and the PWA's theme colour
WHITE = (255, 255, 255, 255)
# His face as his word on the money colours it, Tailwind's 700s as the interface's verdicts: a white face keeps 3:1
# against each. A good word is the logo itself.
MOODS = {
    "warning": (180, 83, 9, 255),  # amber-700
    "critical": (185, 28, 28, 255),  # red-700
    "neutral": (82, 82, 91, 255),  # zinc-600
}
SUPERSAMPLE = 4  # shapes are drawn this many times larger and scaled down, so their edges stay smooth


def _lines() -> Image.Image:
    """The drawing's lines as a mask, cut to the face."""
    mask = Image.open(LOGO).convert("RGBA").getchannel("A")
    box = mask.getbbox()
    if box is None:
        raise SystemExit(f"{LOGO} is empty")
    return mask.crop(box)


def _inside(lines: Image.Image) -> Image.Image:
    """Everything within the face's outer line: the ground the outside flood fill does not reach."""
    height = 400  # the shape needs no more detail than this; the fill is fast at this size
    width = round(lines.width * height / lines.height)
    small = lines.resize((width, height), Image.Resampling.LANCZOS).point([255 if v > 60 else 0 for v in range(256)])
    closed = small.filter(ImageFilter.MaxFilter(5))  # closes the small gaps where two lines nearly meet
    pad = 8  # the outline touches the cut's edges: the fill goes round it, and the edge never stops the shrinking
    ground = Image.new("L", (width + 2 * pad, height + 2 * pad), 0)
    ground.paste(closed, (pad, pad))
    ImageDraw.floodfill(ground, (0, 0), 128)
    inside = ground.point([0 if v == 128 else 255 for v in range(256)])
    # Pulled in to the middle of the outline, so no white edge shows outside it.
    inside = inside.filter(ImageFilter.MinFilter(7)).crop((pad, pad, width + pad, height + pad))
    return inside.resize(lines.size, Image.Resampling.LANCZOS)


LINES = _lines()
INSIDE = _inside(LINES)


def _scaled(mask: Image.Image, height: int, grow: int) -> Image.Image:
    """mask at the given height; its lines grown by `grow` pixels of an eight times larger copy first."""
    work = min(height * 8, mask.height)
    big = mask.resize((round(mask.width * work / mask.height), work), Image.Resampling.LANCZOS)
    if grow > 1:
        big = big.filter(ImageFilter.MaxFilter(grow))
    return big.resize((round(mask.width * height / mask.height), height), Image.Resampling.LANCZOS)


def _grow(size: int) -> int:
    """How much the lines grow at a size: the smaller the icon, the thicker its lines."""
    if size <= 24:
        return 7
    if size <= 48:
        return 5
    if size <= 128:
        return 3
    return 1


def face(height: int, grow: int | None = None, color: tuple[int, int, int, int] = TEAL) -> Image.Image:
    """The face alone, `height` pixels tall, its lines in `color` on a transparent ground."""
    lines = _scaled(LINES, height, _grow(height) if grow is None else grow)
    inside = _scaled(INSIDE, height, 1)
    image = Image.new("RGBA", lines.size, (0, 0, 0, 0))
    image.paste(Image.new("RGBA", lines.size, WHITE), (0, 0), inside)
    image.paste(Image.new("RGBA", lines.size, color), (0, 0), lines)
    return image


def icon(
    size: int,
    *,
    share: float = 0.84,
    corner: float = 0.22,
    margin: float = 0.0,
    color: tuple[int, int, int, int] = TEAL,
) -> Image.Image:
    """The face on a tile of `color`, its lines in it: `share` of the tile's height, the tile's corners rounded by
    `corner` of its side (0 for a full square), and `margin` of the canvas left empty around the tile (macOS's icon
    grid)."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    side = round(size * (1 - 2 * margin))
    big = side * SUPERSAMPLE
    tile = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, big - 1, big - 1), radius=round(big * corner), fill=color)
    tile = tile.resize((side, side), Image.Resampling.LANCZOS)
    drawn = face(round(side * share), _grow(size), color)
    tile.alpha_composite(drawn, ((side - drawn.width) // 2, (side - drawn.height) // 2))
    offset = (size - side) // 2
    canvas.alpha_composite(tile, (offset, offset))
    return canvas


def _save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    print(f"{path.relative_to(ROOT)} ({image.width}×{image.height})")


def _save_many(images: Sequence[Image.Image], path: Path) -> None:
    """An .ico or .icns holding each size as drawn for it, not one size scaled by the format."""
    largest, *rest = sorted(images, key=lambda image: -image.width)
    if path.suffix == ".ico":
        largest.save(path, sizes=[(image.width, image.height) for image in images], append_images=rest)
    else:
        largest.save(path, append_images=rest)
    print(f"{path.relative_to(ROOT)} ({', '.join(str(image.width) for image in images)})")


def main() -> None:
    # The interface: the tab's icon, the header's mark, and the PWA's icons (ADR-0008). The maskable icon fills its
    # square and keeps the face inside the middle 80 % circle a launcher may cut it to; iOS rounds the touch icon
    # itself.
    _save(icon(16), WEB / "favicon-16.png")
    _save(icon(32), WEB / "favicon-32.png")
    _save(icon(128), WEB / "logo.png")
    _save(icon(180, corner=0, share=0.78), WEB / "apple-touch-icon.png")
    _save(icon(192), WEB / "pwa-192x192.png")
    _save(icon(512), WEB / "pwa-512x512.png")
    _save(icon(512, corner=0, share=0.62), WEB / "pwa-maskable-512x512.png")
    # The browser extension: its toolbar button and its line on the extensions page.
    for size in (16, 32, 48, 128):
        _save(icon(size), EXTENSION / f"icon-{size}.png")
    # His face beside his word on the money: on the Pano and in the extension's window, the logo where it is good.
    for mood, color in MOODS.items():
        _save(icon(128, color=color), WEB / f"face-{mood}.png")
        _save(icon(128, color=color), EXTENSION / f"face-{mood}.png")
    # The installers: the Linux AppImage's icon, the Windows installer's and the macOS app's (the macOS grid leaves a
    # margin around the tile, as the system's own icons do).
    _save(icon(512), ASSETS / "iplikci.png")
    _save_many([icon(size) for size in (16, 24, 32, 48, 64, 128, 256)], ASSETS / "iplikci.ico")
    _save_many([icon(size, margin=0.1) for size in (16, 32, 64, 128, 256, 512, 1024)], ASSETS / "iplikci.icns")


if __name__ == "__main__":
    main()
