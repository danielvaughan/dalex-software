"""The home page's music video (D-41): between the games and the doors, the site's own poster, nothing loaded from
YouTube until the visitor presses play, a plain link without the script, and a script that stores nothing.

Run: python3 -m unittest discover -s tests
"""
import re, shutil, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

JS = (ROOT / 'static/assets/video-embed.js').read_text(encoding='utf-8')
CODE = re.sub(r'(?m)^\s*//[^\n]*', '', JS)   # the script without its comments


class HomeVideo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='dalex-home-'))
        cls.out = build.build(ROOT, ROOT / 'site.json', cls.tmp / 'site')
        cls.html = (cls.out / 'index.html').read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_after_the_games_and_before_the_doors(self):
        shelf, music, doors = (self.html.index(s) for s in ('id="shelf-title"', 'id="music-title"', 'id="doors-title"'))
        self.assertLess(shelf, music)
        self.assertLess(music, doors)

    def test_the_poster_is_the_sites_own_and_exists(self):
        box = re.search(r'<div class="video-embed"[^>]*>.*?</div>', self.html, re.S).group(0)
        src = re.search(r'<img [^>]*src="([^"]+)"[^>]*alt="[^"]+"', box).group(1)
        self.assertTrue((self.out / src).is_file(), src)

    def test_nothing_is_loaded_from_another_site(self):
        loaded = re.findall(r'<(?:script|img|link|iframe|source|video|audio)\b[^>]*\b(?:src|href)="([^"]+)"', self.html)
        self.assertEqual([u for u in loaded if re.match(r'(https?:)?//', u) and 'dalex-software.co.uk' not in u], [])
        self.assertNotIn('<iframe', self.html)

    def test_a_plain_link_works_without_the_script(self):
        vid = build.MUSIC_VIDEO['youtube']
        self.assertRegex(vid, r'^[A-Za-z0-9_-]{11}$')
        self.assertIn(f'<a href="https://www.youtube.com/watch?v={vid}">', self.html)
        self.assertIn('assets/video-embed.js', self.html)

    def test_the_player_is_youtube_nocookie_and_nothing_is_stored(self):
        self.assertIn('https://www.youtube-nocookie.com/embed/', CODE)
        self.assertNotRegex(CODE, r'cookie\s*=|localStorage|sessionStorage|indexedDB')
        self.assertIsNone(re.search(r'https?://(?!www\.youtube-nocookie\.com/)', CODE))


if __name__ == '__main__':
    unittest.main()
