"""The home page's layout (D-42): the new release once, the other games in a carousel that works without script and
never moves by itself, and the fluid scale and layout primitives the page is built on.

Run: python3 -m unittest discover -s tests
"""
import re, shutil, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

JS = (ROOT / 'static/assets/reel.js').read_text(encoding='utf-8')
CSS = (ROOT / 'static/assets/site.css').read_text(encoding='utf-8')


class HomeLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='dalex-home-layout-'))
        cls.out = build.build(ROOT, ROOT / 'site.json', cls.tmp / 'site')
        cls.html = (cls.out / 'index.html').read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_the_featured_game_is_not_repeated_in_the_carousel(self):
        featured = re.search(r'<section class="feature[^"]*".*?href="games/([^/]+)/"', self.html, re.S).group(1)
        reel = re.search(r'<ul class="shelf reel".*?</ul>', self.html, re.S).group(0)
        self.assertNotIn(f'href="games/{featured}/"', reel)
        self.assertGreater(reel.count('<li>'), 1)

    def test_the_carousel_works_without_script(self):
        self.assertRegex(self.html, r'<ul class="shelf reel" id="shelf" tabindex="0" aria-label="[^"]+"')
        self.assertRegex(self.html, r'<div class="reel-buttons" hidden>')
        self.assertIn('assets/reel.js', self.html)

    def test_the_carousel_never_moves_by_itself_and_stores_nothing(self):
        code = re.sub(r'(?m)^\s*//[^\n]*', '', JS)
        self.assertNotRegex(code, r'setInterval|setTimeout|requestAnimationFrame|cookie|Storage')
        self.assertIn('prefers-reduced-motion', code)

    def test_the_page_uses_the_fluid_scale(self):
        for token in ('--step-0:', '--step-5:', '--space-s:', '--space-l-2xl:'):
            self.assertIn(token, CSS)


if __name__ == '__main__':
    unittest.main()
