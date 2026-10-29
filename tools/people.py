#!/usr/bin/env python3
"""Build the About page's standing cast sprites from their generated source sheets (D-15).

Every figure is cut from a raw image-tool sheet on flat magenta in `assets/source/people/`, listed with its target
height in `assets/source/people/people.json`. For each one the tool:

1. keys flat magenta and its anti-aliased fringe to transparent (the key rule of the Dalex Studio's
   `scummvm-character-art/scripts/prepare_generated_atlas.py`), then peels magenta-tinted outline pixels off the
   silhouette edge and pulls leftover tint back (the Studio's `cast_art.keyed()`, #61);
2. takes the figure's cell (the sheet split into equal columns) or an explicit box, recolouring a tinted glass dome
   when the entry asks (`glass`);
3. keeps the figure's largest connected shape and any shape at least a fiftieth its size (a held prop), dropping specks;
4. scales the figure with nearest-neighbour so its height is exactly the manifest's `height`, and hardens alpha;
5. centres it on the shared canvas with its lowest pixel on the shared baseline (the floor line).

Output: `static/assets/people/<id>.png`, all the same canvas size. Deterministic for the same sources.

Needs Pillow and NumPy (not part of the site build): run with the Studio's interpreter, e.g.
`../dalex-studio/.venv/bin/python tools/people.py`. Commit the PNGs it writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'assets/source/people'


def keyed(path: Path) -> Image.Image:
    rgb = np.asarray(Image.open(path).convert('RGB')).astype(int)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    key = ((r > 200) & (b > 200) & (g < 90) & (np.abs(r - b) < 70)) | ((r > 150) & (b > 150) & (g < 120))
    key |= (r - g > 90) & (b - g > 90)
    alpha = np.where(key, 0, 255).astype('uint8')
    alpha[:4, :] = 0; alpha[-4:, :] = 0; alpha[:, :4] = 0; alpha[:, -4:] = 0   # generators leave a thin border
    tint = (np.minimum(r, b) - g > 25) & (np.abs(r - b) < np.maximum(r, b) * 0.5)
    for _ in range(3):
        clear = alpha == 0
        edge = np.zeros_like(clear)
        edge[1:] |= clear[:-1]; edge[:-1] |= clear[1:]; edge[:, 1:] |= clear[:, :-1]; edge[:, :-1] |= clear[:, 1:]
        alpha[edge & tint & ~clear] = 0
    near = alpha == 0
    for _ in range(3):
        near = near | np.roll(near, 1, 0) | np.roll(near, -1, 0) | np.roll(near, 1, 1) | np.roll(near, -1, 1)
    spill = near & tint & (alpha > 0)
    rgb[..., 0] = np.where(spill, np.minimum(r, g + 20), r)
    rgb[..., 2] = np.where(spill, np.minimum(b, g + 20), b)
    return Image.fromarray(np.dstack([rgb.astype('uint8'), alpha]), 'RGBA')


def labels(mask: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """8-connected component labels (1-based) and each label's size."""
    height, width = mask.shape
    lab = np.zeros(mask.shape, dtype=np.int32)
    sizes = [0]
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        n = len(sizes); lab[y0, x0] = n; stack = [(y0, x0)]; size = 0
        while stack:
            y, x = stack.pop(); size += 1
            for ny in (y - 1, y, y + 1):
                for nx in (x - 1, x, x + 1):
                    if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = n; stack.append((ny, nx))
        sizes.append(size)
    return lab, sizes


def glass(region: Image.Image) -> Image.Image:
    """Recolour a violet-tinted transparent part (Omnibot's dome, tinted against the key) to blue-grey glass at equal
    luminance, sparing red lamps (prepare_generated_atlas.py --glass)."""
    rgba = np.asarray(region).astype(float)
    r, g, b, a = rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3]
    tinted = (a > 0) & (r > g + 20) & (b > g + 20) & ~((r > 180) & (g < 110) & (b < 110))
    luminance = .3 * r + .59 * g + .11 * b
    tone = np.clip(np.dstack([luminance * .88, luminance, luminance * 1.12]) + 18, 0, 255)
    rgb = np.where(tinted[..., None], tone, rgba[..., :3])
    return Image.fromarray(np.dstack([rgb, a]).astype('uint8'), 'RGBA')


def figure(sheet: Image.Image, entry: dict) -> Image.Image:
    if 'box' in entry:
        region = sheet.crop(tuple(entry['box']))
    else:
        cell = sheet.width / entry['cells']
        region = sheet.crop((round(entry['cell'] * cell), 0, round((entry['cell'] + 1) * cell), sheet.height))
    if entry.get('glass'):
        region = glass(region)
    alpha = np.asarray(region.getchannel('A')) > 0
    lab, sizes = labels(alpha)
    biggest = max(sizes)
    keep = np.isin(lab, [i for i, s in enumerate(sizes) if i and s * 50 >= biggest])
    region.putalpha(Image.fromarray(np.where(keep, 255, 0).astype('uint8')))
    region = region.crop(region.getbbox())
    scale = entry['height'] / region.height
    size = (max(1, round(region.width * scale)), entry['height'])
    small = region.resize(size, Image.Resampling.NEAREST)
    small.putalpha(Image.fromarray(np.where(np.asarray(small.getchannel('A')) >= 128, 255, 0).astype('uint8')))
    return small.crop(small.getbbox())


def build(manifest: dict, out: Path) -> dict[str, list[int]]:
    width, height = manifest['canvas']; baseline = manifest['baseline']
    out.mkdir(parents=True, exist_ok=True)
    sheets: dict[str, Image.Image] = {}
    report = {}
    for entry in manifest['figures']:
        source = entry['source']
        if source not in sheets:
            sheets[source] = keyed(SOURCES / source)
        sprite = figure(sheets[source], entry)
        if sprite.width > width or sprite.height > baseline + 1:
            raise SystemExit(f"{entry['id']}: {sprite.width}x{sprite.height} does not fit the {width}x{height} canvas")
        canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(sprite, ((width - sprite.width) // 2, baseline + 1 - sprite.height))
        canvas.save(out / f"{entry['id']}.png", optimize=True)
        report[entry['id']] = [sprite.width, sprite.height]
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--manifest', type=Path, default=SOURCES / 'people.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'static/assets/people')
    args = parser.parse_args()
    for person, (w, h) in build(json.loads(args.manifest.read_text()), args.out).items():
        print(f'{person}: figure {w}x{h}')


if __name__ == '__main__':
    main()
