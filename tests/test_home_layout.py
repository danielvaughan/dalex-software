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

    def test_the_best_reviewed_game_is_featured_unless_one_is_pinned(self):
        cfg = __import__('json').loads((ROOT / 'site.json').read_text())
        if any(g.get('featured') and g['visible'] for g in cfg['games']):
            self.skipTest('a game is pinned in site.json')
        site, games, featured = build.load(ROOT, ROOT / 'site.json')
        best = max((g.get('review') or {}).get('overall') or 0 for g in games)
        self.assertEqual((featured.get('review') or {}).get('overall'), best)
        self.assertIn(f'<h2 id="hero-title" class="hero-title">{build.e(featured["title"])}</h2>', self.html)

    def test_best_reviewed_breaks_ties_by_newer_release_and_skips_unreviewed(self):
        g = lambda slug, o, date, order: {'slug': slug, 'review': {'overall': o} if o is not None else {},
                                          'release': {'date': date}, '_entry': {'order': order}}
        self.assertEqual(build.best_reviewed([g('a', 70, '2026-10-01', 1), g('b', 70, '2026-11-01', 2),
                                              g('c', None, '2026-12-01', 3)])['slug'], 'b')
        self.assertEqual(build.best_reviewed([g('a', None, '', 2), g('b', None, '', 1)])['slug'], 'b')
        self.assertIsNone(build.best_reviewed([]))

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
