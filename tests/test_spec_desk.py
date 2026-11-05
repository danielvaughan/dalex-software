"""The spec desk page (D-37, dalex-software #1): opening soon until spec_desk_api is set, no third-party code, no
cookies or storage.

Run: python3 -m unittest discover -s tests
"""
import json, re, shutil, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

JS = (ROOT / 'static/assets/spec-desk.js').read_text(encoding='utf-8')
CODE = re.sub(r'/\*.*?\*/', '', JS, flags=re.S)   # the script without its comments


def built(api):
    tmp = Path(tempfile.mkdtemp(prefix='dalex-desk-'))
    cfg = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
    cfg['site']['spec_desk_api'] = api
    (tmp / 'site.json').write_text(json.dumps(cfg), encoding='utf-8')
    out = build.build(ROOT, tmp / 'site.json', tmp / 'site')
    return tmp, out


class OpeningSoon(unittest.TestCase):
    """SD-W1"""

    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.out = built(None)
        cls.page = (cls.out / 'studio/spec-desk/index.html').read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_page_says_the_desk_opens_soon_and_loads_no_script(self):
        self.assertIn('The spec desk opens soon', self.page)
        self.assertNotIn('<script', self.page)
        self.assertNotIn('data-api', self.page)

    def test_nothing_links_to_it_or_lists_it_while_it_is_closed(self):
        self.assertNotIn('spec-desk/', (self.out / 'studio/index.html').read_text(encoding='utf-8'))
        self.assertNotIn('spec-desk', (self.out / 'sitemap.xml').read_text(encoding='utf-8'))

    def test_the_page_is_honest_about_ai_and_the_brief(self):
        for words in ('written by an AI model', 'deleted after 30 days', 'sets no cookies', 'fictional'):
            self.assertIn(words, self.page)


class Open(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.out = built('https://desk.dalex-software.co.uk/')
        cls.page = (cls.out / 'studio/spec-desk/index.html').read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_page_loads_the_sites_own_script_with_the_desks_address(self):
        self.assertIn('data-api="https://desk.dalex-software.co.uk"', self.page)
        self.assertEqual(re.findall(r'<script[^>]*src="([^"]+)"', self.page), ['../../assets/spec-desk.js'])
        self.assertTrue((self.out / 'assets/spec-desk.js').is_file())
        self.assertIn('aria-live="polite"', self.page)

    def test_the_studio_page_and_sitemap_open_the_door(self):
        self.assertIn('href="spec-desk/"', (self.out / 'studio/index.html').read_text(encoding='utf-8'))
        self.assertIn('studio/spec-desk/', (self.out / 'sitemap.xml').read_text(encoding='utf-8'))

    def test_no_third_party_resource_and_no_cookie_or_storage(self):
        """SD-W4"""
        loaded = re.findall(r'<(?:script|img|link|iframe|source|video|audio)\b[^>]*\b(?:src|href)="([^"]+)"', self.page)
        self.assertEqual([u for u in loaded if re.match(r'(https?:)?//', u) and 'dalex-software.co.uk' not in u], [])
        self.assertIsNone(re.search(r'https?://', CODE))
        for word in ('cookie', 'localStorage', 'sessionStorage', 'indexedDB', 'eval(', "credentials: 'include'"):
            self.assertFalse(word in CODE, word)
        self.assertIn("credentials: 'omit'", CODE)

    def test_replies_carry_a_named_portrait_and_a_real_list(self):
        """SD-W5 (the browser check in tools/spec_desk_check.mjs sees it rendered)"""
        self.assertIn("img.alt = 'Portrait of '", JS)
        self.assertIn("el('ol', 'questions')", JS)
        for who in ('malcolm', 'colin', 'mo'):
            self.assertTrue((ROOT / f'static/assets/people/{who}.png').is_file(), who)

    def test_visitor_and_model_text_is_never_written_as_html(self):
        """Replies and the visitor's words go in as text; innerHTML only carries the page's own fixed links."""
        for m in re.finditer(r'\.innerHTML = (.+);', JS):
            self.assertTrue(m.group(1).startswith(("'", '"')), m.group(0))


class BadAddress(unittest.TestCase):
    def test_only_https_or_a_loopback_check(self):
        for api in ('http://desk.example.com', 'ftp://127.0.0.1', 'javascript:alert(1)'):
            with self.subTest(api=api):
                with self.assertRaises(build.BuildError):
                    build.spec_desk_api({'spec_desk_api': api})
        self.assertEqual(build.spec_desk_api({'spec_desk_api': 'http://127.0.0.1:18790/'}), 'http://127.0.0.1:18790')


if __name__ == '__main__':
    unittest.main()
