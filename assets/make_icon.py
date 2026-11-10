"""Draw the app logo and save icon.ico + icon.png next to this file.

Run (from the video-downloader folder):  uv run --with pillow assets/make_icon.py

The geometry matches the inline SVG logo in ui/index.html (a 100x100 grid):
a rounded tile with a violet->pink gradient, and a white "play button turned
downward" that reads as a download arrow, resting on a tray bar.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
S = 1024  # draw big, scale down for smooth edges
U = S / 100  # one grid unit

TOP_LEFT = (139, 92, 246)  # #8B5CF6 violet
BOTTOM_RIGHT = (236, 72, 153)  # #EC4899 pink


def gradient() -> Image.Image:
    img = Image.new("RGB", (S, S))
    px = img.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * (S - 1))
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(TOP_LEFT, BOTTOM_RIGHT))
    return img


def rounded_outline(pts: list[tuple[float, float]], r: float, steps: int = 48) -> list[tuple[float, float]]:
    """Outline of a convex polygon expanded by radius r (smooth arcs at corners)."""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)

    def normal(a: tuple[float, float], b: tuple[float, float]) -> float:
        nx, ny = b[1] - a[1], a[0] - b[0]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if nx * (mx - cx) + ny * (my - cy) < 0:  # point it away from the centre
            nx, ny = -nx, -ny
        return math.atan2(ny, nx)

    out: list[tuple[float, float]] = []
    n = len(pts)
    for i in range(n):
        prev, cur, nxt = pts[i - 1], pts[i], pts[(i + 1) % n]
        a1, a2 = normal(prev, cur), normal(cur, nxt)
        span = (a2 - a1) % (2 * math.pi)
        if span > math.pi:
            span -= 2 * math.pi
        for k in range(steps + 1):
            a = a1 + span * k / steps
            out.append((cur[0] + r * math.cos(a), cur[1] + r * math.sin(a)))
    return out


def u(*vals: float) -> list[float]:
    return [v * U for v in vals]


def draw() -> Image.Image:
    # Tile: gradient clipped to a rounded square.
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(u(0, 0, 100, 100), radius=24 * U, fill=255)
    tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    tile.paste(gradient(), (0, 0), mask)

    # Glyph.
    d = ImageDraw.Draw(tile)
    fill = (255, 255, 255, 255)
    d.rounded_rectangle(u(43.5, 17, 56.5, 46), radius=6.5 * U, fill=fill)  # stem
    # Arrowhead: the triangle grown outward by r, so every corner is a true arc.
    tri = [(33 * U, 42 * U), (67 * U, 42 * U), (50 * U, 62 * U)]
    d.polygon(rounded_outline(tri, 6 * U), fill=fill)
    d.rounded_rectangle(u(28, 76, 72, 83), radius=3.5 * U, fill=fill)  # tray
    return tile


def main() -> None:
    img = draw()
    img.resize((512, 512), Image.LANCZOS).save(HERE / "icon.png")
    img.resize((256, 256), Image.LANCZOS).save(
        HERE / "icon.ico", sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print("wrote", HERE / "icon.png", "and", HERE / "icon.ico")


if __name__ == "__main__":
    main()
