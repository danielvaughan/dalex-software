"""The Kit page (D-47, D-48): the range with retail prices, nothing for sale, every picture present and described."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class MerchPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / '_site'
        subprocess.run([sys.executable, str(ROOT / 'build.py'), '--out', str(cls.out)], check=True, cwd=ROOT,
                       capture_output=True)
        cls.html = (cls.out / 'kit' / 'index.html').read_text(encoding='utf-8')

    def test_old_merch_address_sends_readers_to_kit(self):
        old = (self.out / 'merch' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('url=../kit/', old)
        self.assertNotIn('&pound;', old)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_shows_every_item_with_its_price(self):
        for name, price in (('The Dalex mug', 6), ('T-shirt', 15), ('Sweatshirt', 21), ('Polo shirt', 31), ('Cap', 17),
                            ('Softshell jacket', 35), ('Tote bag', 8), ('Sticker sheet', 4),
                            ('The 1987 staff calendar', 14)):
            self.assertRegex(self.html, re.escape(name) + r'</h[23]>[\s\S]{0,400}?&pound;' + str(price) + '<', name)

    def test_nothing_is_for_sale(self):
        self.assertIn('Not on sale yet', self.html)
        for bad in ('Buy', 'Add to basket', 'checkout', '"offers"', 'shopify'):
            self.assertNotIn(bad, self.html)

    def test_pictures_exist_and_have_alt_text(self):
        imgs = re.findall(r'<img [^>]*>', self.html)
        self.assertGreaterEqual(len(imgs), 11)
        for tag in imgs:
            self.assertRegex(tag, r'alt="[^"]{3,}"' if 'dalex-mark' not in tag else r'alt=', tag)
            for src in re.findall(r'(?:src="|, |srcset=")(\.\./assets/[^" ,]+)', tag):
                self.assertTrue((self.out / src[3:]).is_file(), src)

    def test_in_the_navigation_and_sitemap(self):
        self.assertIn('<a href="../kit/" aria-current="page">Kit</a>', self.html)
        self.assertIn('/kit/</loc>', (self.out / 'sitemap.xml').read_text(encoding='utf-8'))
        self.assertIn('href="kit/">Kit</a>', (self.out / 'index.html').read_text(encoding='utf-8'))

    def test_games_still_state_no_price(self):
        for page in (self.out / 'games').rglob('index.html'):
            self.assertNotIn('&pound;', page.read_text(encoding='utf-8'), page)


if __name__ == '__main__':
    unittest.main()

