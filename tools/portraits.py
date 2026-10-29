#!/usr/bin/env python3
"""Render the About page's staff portraits from the Dalex Studio's packed cast art.

Each person is their front-facing talking pose (`cast-<id>-talk-0.pix`, the Studio's tour frames, #67); Percy is his
sitting pose and Omnibot his close-up. Pixels are palette indices into the Studio's `palette.bin` (index 0 is
transparent). Stray specks are dropped by keeping only the figure's largest connected shape, and the result is
cropped to it. Output: `static/assets/people/<id>.png` at native size; the page scales them with pixelated rendering.

Needs Pillow (not part of the site build): run with the Studio's interpreter, e.g.
`../dalex-studio/.venv/bin/python tools/portraits.py`. Commit the PNGs it writes.
"""
from __future__ import annotations

import argparse
import struct
from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FRAMES = {**{name: f'cast-{name}-talk-0' for name in (
    'malcolm', 'colin', 'mo', 'gareth', 'yvonne', 'neil', 'hyunjoo', 'simon', 'dez', 'vik', 'emeka', 'derek', 'ken')},
    'percy': 'percy-14', 'omnibot': 'omnibot-big-front-0'}


def read_pix(path: Path) -> tuple[int, int, bytes]:
    raw = path.read_bytes()
    width, height = struct.unpack('<HH', raw[:4])
    return width, height, raw[4:4 + width * height]


def largest_shape(width: int, height: int, pixels: bytes) -> set[int]:
    """Indices of the largest 8-connected set of opaque pixels."""
    seen, best = set(), set()
    for start in range(width * height):
        if not pixels[start] or start in seen:
            continue
        shape, queue = {start}, deque([start])
        seen.add(start)
        while queue:
            i = queue.popleft()
            y, x = divmod(i, width)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    j = ny * width + nx
                    if 0 <= ny < height and 0 <= nx < width and pixels[j] and j not in seen:
                        seen.add(j)
                        shape.add(j)
                        queue.append(j)
        if len(shape) > len(best):
            best = shape
    return best


def portrait(path: Path, palette: bytes) -> Image.Image:
    width, height, pixels = read_pix(path)
    keep = largest_shape(width, height, pixels)
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    for i in keep:
        y, x = divmod(i, width)
        p = pixels[i] * 3
        image.putpixel((x, y), (palette[p], palette[p + 1], palette[p + 2], 255))
    return image.crop(image.getbbox())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio', type=Path, default=ROOT.parent / 'dalex-studio', help='Dalex Studio checkout')
    parser.add_argument('--out', type=Path, default=ROOT / 'static/assets/people')
    args = parser.parse_args()
    packed = args.studio / 'dists/dalex'
    palette = (packed / 'palette.bin').read_bytes()
    args.out.mkdir(parents=True, exist_ok=True)
    for person, frame in FRAMES.items():
        image = portrait(packed / f'{frame}.pix', palette)
        image.save(args.out / f'{person}.png', optimize=True)
        print(f'{person}: {image.width}x{image.height}')


if __name__ == '__main__':
    main()
