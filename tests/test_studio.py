"""The Studio page: the documentary film, its poster and captions are deployed, and the captions are public-safe.

Run: python3 -m unittest discover -s tests
"""
import re, shutil, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

# The film is public: no customer, client event or real person, no former cast name, and not the child the spoken
# help was made for. "Dalex" itself must not trip the last pattern.
DENY = (r'blackstone', r'husqvarna', r'tech\s*day', r'leaders', r'mi-?jung', r'\bkang\b', r'\balex\b', r'daniel',
        r'vaughan', r'megawatt')
FILM = 'media/studio-documentary'


def deny_hits(text):
    return sorted({m.group(0).lower() for p in DENY for m in re.finditer(p, text, re.I)})


class StudioFilm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='dalex-studio-'))
        cls.out = build.build(ROOT, ROOT / 'site.json', cls.tmp / 'site')
        cls.page = (cls.out / 'studio/index.html').read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_film_poster_and_captions_are_deployed(self):
        mp4 = self.out / (FILM + '.mp4')
        self.assertTrue(mp4.is_file())
        self.assertLess(mp4.stat().st_size, 100 * 1024 * 1024)            # GitHub's file limit
        head = mp4.read_bytes()[:1 << 16]
        self.assertIn(b'ftyp', head[:16])
        self.assertIn(b'moov', head)                                        # +faststart: playable before it has all loaded
        self.assertTrue((self.out / (FILM + '-poster.jpg')).read_bytes().startswith(b'\xff\xd8'))
        self.assertTrue((self.out / (FILM + '.vtt')).read_text(encoding='utf-8').startswith('WEBVTT'))

    def test_page_has_an_accessible_video_with_captions_and_no_autoplay(self):
        video = re.search(r'<video[^>]*>', self.page).group(0)
        self.assertIn('controls', video)
        self.assertIn('preload="none"', video)
        self.assertIn(f'poster="../{FILM}-poster.jpg"', video)
        self.assertNotIn('autoplay', self.page)
        self.assertIn(f'<source src="../{FILM}.mp4" type="video/mp4">', self.page)
        track = re.search(r'<track[^>]*>', self.page).group(0)
        for part in ('kind="captions"', 'srclang="en"', f'src="../{FILM}.vtt"', 'default'):
            self.assertIn(part, track)
        self.assertIn('Read the transcript', self.page)
        self.assertIn('Gold Master', self.page)

    def test_home_about_and_sitemap_link_the_studio(self):
        self.assertIn('href="studio/"', (self.out / 'index.html').read_text(encoding='utf-8'))
        self.assertIn('href="../studio/"', (self.out / 'about/index.html').read_text(encoding='utf-8'))
        self.assertIn('studio/</loc>', (self.out / 'sitemap.xml').read_text(encoding='utf-8'))

    def test_captions_page_and_transcript_name_no_customer_or_real_person(self):
        self.assertEqual(deny_hits('Dalex Software'), [])
        self.assertTrue(deny_hits('Husqvarna tech day'))
        self.assertEqual(deny_hits((self.out / (FILM + '.vtt')).read_text(encoding='utf-8')), [])
        self.assertEqual(deny_hits(self.page), [])

    def test_captions_cover_the_film_in_order(self):
        times = re.findall(r'(\d\d):(\d\d):(\d\d\.\d\d\d) --> (\d\d):(\d\d):(\d\d\.\d\d\d)',
                           (self.out / (FILM + '.vtt')).read_text(encoding='utf-8'))
        secs = [(int(a) * 3600 + int(b) * 60 + float(c), int(d) * 3600 + int(e) * 60 + float(f)) for a, b, c, d, e, f in times]
        self.assertGreater(len(secs), 40)
        self.assertTrue(all(a < b for a, b in secs))
        self.assertTrue(all(secs[i][0] <= secs[i + 1][0] for i in range(len(secs) - 1)))
        self.assertTrue(285 <= secs[-1][1] <= 315)


if __name__ == '__main__':
    unittest.main()
