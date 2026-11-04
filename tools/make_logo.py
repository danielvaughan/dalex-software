#!/usr/bin/env python3
"""The website's smooth vector logo (D-34): the Dalex disc, the DALEX SOFTWARE wordmark and the Spectrum stripe.

The website's logo is smooth and modern; the pixel-art lockup from the toolkit's house style stays with the Studio
and the games. This draws the same parts (a yellow disc with a red D, the name, the four-colour stripe) as vectors,
with the letters taken as outlines from Ubuntu Sans (Ubuntu Font Licence), so the SVGs need no font to show.

Writes static/assets/dalex-logo.svg (the masthead lockup), static/assets/dalex-mark.svg (the footer mark) and
static/favicon.svg. The PNG and ICO favicons are rendered from favicon.svg by a browser (see the commit). Needs
fontTools, which the site's build does not:

    python3 tools/make_logo.py [path/to/UbuntuSans[wdth,wght].ttf]
"""
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
FONT = Path(sys.argv[1] if len(sys.argv) > 1 else '/usr/share/fonts/truetype/ubuntu/UbuntuSans[wdth,wght].ttf')
RED, YELLOW, GREEN, CYAN, WHITE = '#ff2d2d', '#ffe600', '#12d84a', '#10d8e6', '#ffffff'
STRIPE = (RED, YELLOW, GREEN, CYAN)


class Face:
    def __init__(self, weight):
        self.font = instantiateVariableFont(TTFont(FONT), {'wght': weight, 'wdth': 100})
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.cap = self.font['OS/2'].sCapHeight

    def advance(self, ch):
        return self.glyphs[self.cmap[ord(ch)]].width

    def width(self, text, tracking=0.0):
        """Advance width of text in font units, with tracking (a fraction of the em) between letters."""
        em = self.font['head'].unitsPerEm
        return sum(self.advance(c) for c in text) + tracking * em * (len(text) - 1)

    def path(self, text, x, baseline, cap_px, tracking=0.0):
        """SVG path data for text with its left at x and its baseline at baseline, capitals cap_px tall."""
        s = cap_px / self.cap
        em = self.font['head'].unitsPerEm
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f'{v:.2f}'.rstrip('0').rstrip('.'))
        cursor = 0.0
        for c in text:
            name = self.cmap[ord(c)]
            self.glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, x + cursor * s, baseline)))
            cursor += self.glyphs[name].width + tracking * em
        return pen.getCommands()

    def bounds(self, ch):
        from fontTools.pens.boundsPen import BoundsPen
        bp = BoundsPen(self.glyphs)
        self.glyphs[self.cmap[ord(ch)]].draw(bp)
        return bp.bounds


def disc_with_d(face, cx, cy, r):
    """The disc and its red D, the D's bounding box centred in the disc (a touch right, where it looks centred)."""
    cap = r * 1.06
    x0, y0, x1, y1 = face.bounds('D')
    s = cap / face.cap
    w, h = (x1 - x0) * s, (y1 - y0) * s
    x = cx - w / 2 - x0 * s + r * 0.07
    baseline = cy + h / 2 + y0 * s
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{YELLOW}"/>'
            f'<path fill="{RED}" d="{face.path("D", x, baseline, cap)}"/>')


def stripe(x, y, width, height, slant):
    """Four parallelograms, red to cyan, leaning right, edge to edge across width."""
    seg = (width - slant) / 4
    out = []
    for i, col in enumerate(STRIPE):
        a, b = x + i * seg, x + (i + 1) * seg
        out.append(f'<path fill="{col}" d="M{a + slant:.2f} {y}H{b + slant:.2f}L{b:.2f} {y + height}H{a:.2f}Z"/>')
    return ''.join(out)


def svg(width, height, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" role="img" aria-label="{label}"><title>{label}</title>{body}</svg>\n')


def main():
    heavy, medium = Face(800), Face(600)
    # the masthead lockup, 160 tall (shown 64 tall); its width follows the name
    left, name_cap, gap = 160, 56, 14
    name_w = heavy.width('DALEX') * name_cap / heavy.cap
    track = 0.24                                   # SOFTWARE's letter spacing, a fraction of the em
    soft_cap = name_w * medium.cap / medium.width('SOFTWARE', track)    # sized so it spans the name
    width = round(left + name_w + gap)
    body = (disc_with_d(heavy, 76, 80, 66)
            + f'<path fill="{WHITE}" d="{heavy.path("DALEX", left, 80, name_cap)}"/>'
            + f'<path fill="{WHITE}" d="{medium.path("SOFTWARE", left, 80 + 14 + soft_cap, soft_cap, track)}"/>'
            + stripe(left, 80 + 14 + soft_cap + 12, name_w, 14, 9))
    (ROOT / 'static/assets/dalex-logo.svg').write_text(svg(width, 160, body, 'Dalex Software'))
    print(f'lockup {width} x 160: show at {round(width * 64 / 160)} x 64; SOFTWARE cap {soft_cap:.1f}')
    # the footer mark, 72 x 24 (shown at 48 x 16): the disc and the stripe
    mark = disc_with_d(heavy, 12, 12, 11) + stripe(27, 6, 45, 12, 6)
    (ROOT / 'static/assets/dalex-mark.svg').write_text(svg(72, 24, mark, 'Dalex Software'))
    # the favicon, 64 x 64
    (ROOT / 'static/favicon.svg').write_text(svg(64, 64, disc_with_d(heavy, 32, 32, 31), 'Dalex Software'))
    print('wrote dalex-logo.svg, dalex-mark.svg, favicon.svg')


if __name__ == '__main__':
    main()
