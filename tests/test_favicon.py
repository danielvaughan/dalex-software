"""The favicons show the Dalex mark: a yellow disc with a red D. The PNG and every size in the ICO are decoded with
the standard library and their middle and edge pixels checked, because a capture once shipped a picture of the
browser's broken-image icon instead.

Run: python3 -m unittest discover -s tests
"""
import struct, unittest, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def png_pixels(data: bytes):
    """(width, height, rows of RGBA tuples) for an 8-bit RGBA or RGB, non-interlaced PNG."""
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'not a PNG'
    pos, idat, w, h, bpp = 8, b'', 0, 0, 4
    while pos < len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b'IHDR':
            w, h, depth, colour, _, _, interlace = struct.unpack('>IIBBBBB', body)
            assert depth == 8 and colour in (2, 6) and interlace == 0, (depth, colour, interlace)
            bpp = 4 if colour == 6 else 3
        elif kind == b'IDAT':
            idat += body
        pos += 12 + n
    raw, stride, rows, prev = zlib.decompress(idat), w * bpp, [], bytes(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = bytes(line)
        rows.append([tuple(line[x * bpp:x * bpp + bpp]) + ((255,) if bpp == 3 else ()) for x in range(w)])
    return w, h, rows


def ico_pngs(data: bytes):
    reserved, kind, count = struct.unpack('<HHH', data[:6])
    assert (reserved, kind) == (0, 1), 'not an ICO'
    for i in range(count):
        size, offset = struct.unpack('<II', data[6 + 16 * i + 8:6 + 16 * i + 16])
        yield data[offset:offset + size]


class Favicon(unittest.TestCase):
    def assert_mark(self, png: bytes, name: str):
        w, h, rows = png_pixels(png)
        disc = rows[h // 6][w // 2]              # the top of the disc, above the D
        corner = rows[0][0]
        self.assertGreater(disc[3], 200, f'{name}: the disc is transparent')
        self.assertTrue(disc[0] > 200 and disc[1] > 170 and disc[2] < 90, f'{name}: the disc is not yellow: {disc}')
        self.assertLess(corner[3], 60, f'{name}: the corner is not transparent: {corner}')
        reds = sum(1 for row in rows for p in row if p[3] > 200 and p[0] > 200 and p[1] < 90)
        self.assertGreater(reds, w * h // 20, f'{name}: no red D')

    def test_png(self):
        self.assert_mark((ROOT / 'static/favicon.png').read_bytes(), 'favicon.png')

    def test_every_ico_size(self):
        pngs = list(ico_pngs((ROOT / 'static/favicon.ico').read_bytes()))
        self.assertGreaterEqual(len(pngs), 2)
        for i, png in enumerate(pngs):
            self.assert_mark(png, f'favicon.ico image {i}')

    def test_svg_is_the_mark(self):
        svg = (ROOT / 'static/favicon.svg').read_text(encoding='utf-8')
        self.assertIn('#ffe600', svg)
        self.assertIn('#ff2d2d', svg)


if __name__ == '__main__':
    unittest.main()
