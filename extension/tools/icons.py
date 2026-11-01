"""Draws the extension's icons into static/icons/: a spool of thread on a teal tile, after the product's name (an
iplikçi makes thread, and is a skinflint). Drawn eight times larger and scaled down, so the edges stay smooth.

    uv run python -I extension/tools/icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZES = (16, 32, 48, 128)
SCALE = 8
TEAL = (15, 118, 110, 255)
AMBER = (251, 191, 36, 255)
THREAD = (248, 250, 252, 255)


def icon(size: int) -> Image.Image:
    unit = 128 * SCALE / 128  # the drawing is laid out on a 128 grid

    def box(x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
        return (x0 * unit, y0 * unit, x1 * unit, y1 * unit)

    canvas = Image.new("RGBA", (128 * SCALE, 128 * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box(0, 0, 128, 128), radius=26 * unit, fill=TEAL)
    draw.rectangle(box(40, 38, 88, 90), fill=THREAD)  # the thread wound on the spool
    for y in (52, 64, 76):  # its turns
        draw.line([(40 * unit, (y + 5) * unit), (88 * unit, (y - 5) * unit)], fill=TEAL, width=int(4 * unit))
    draw.rounded_rectangle(box(28, 26, 100, 40), radius=5 * unit, fill=AMBER)  # the flanges
    draw.rounded_rectangle(box(28, 88, 100, 102), radius=5 * unit, fill=AMBER)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    folder = Path(__file__).resolve().parent.parent / "static" / "icons"
    folder.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        icon(size).save(folder / f"icon-{size}.png", optimize=True)


if __name__ == "__main__":
    main()
