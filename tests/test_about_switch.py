"""The About page's photo switch (D-39): pixel art by default, a hidden button the script reveals, every photo it
names present in the built site with its own alt text, and a script that stores nothing.

Run: python3 -m unittest discover -s tests
"""
import re, shutil, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

JS = (ROOT / 'static/assets/people-switch.js').read_text(encoding='utf-8')


class PhotoSwitch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='dalex-about-'))
        cls.out = build.build(ROOT, ROOT / 'site.json', cls.tmp / 'site')
        cls.html = (cls.out / 'about' / 'index.html').read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_pixel_art_by_default_and_the_button_starts_hidden(self):
        self.assertRegex(self.html, r'<button id="people-switch"[^>]*aria-pressed="false"[^>]*hidden')
        for img in re.findall(r'<img [^>]*data-photo="[^"]*"[^>]*>', self.html):
            self.assertNotRegex(re.search(r' src="([^"]+)"', img).group(1), r'/photos/|-photo')

    def test_the_script_is_loaded(self):
        self.assertIn('assets/people-switch.js', self.html)

    def test_every_photo_exists_and_has_alt_text(self):
        imgs = re.findall(r'<img [^>]*data-photo="[^"]*"[^>]*>', self.html)
        self.assertGreaterEqual(len(imgs), 17)   # the group, fifteen cards and the critic
        page = self.out / 'about'
        for img in imgs:
            photo = re.search(r'data-photo="([^"]+)"', img).group(1)
            self.assertTrue((page / photo).resolve().is_file(), photo)
            self.assertRegex(img, r'data-photo-alt="[^"]{10,}"')
            for m in re.finditer(r'(\S+) \d+w', re.search(r'data-photo-srcset="([^"]*)"', img).group(1)
                                 if 'data-photo-srcset' in img else ''):
                self.assertTrue((page / m.group(1)).resolve().is_file(), m.group(1))

    def test_no_storage_or_cookies(self):
        for word in ('cookie', 'localStorage', 'sessionStorage', 'indexedDB', 'fetch(', 'eval('):
            self.assertNotIn(word, re.sub(r'//.*', '', JS), word)


if __name__ == '__main__':
    unittest.main()
