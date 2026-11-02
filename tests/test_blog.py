"""The Blog (D-29): its index, posts and feed are built, each post has its byline, and posts stay public-safe.

Run: python3 -m unittest discover -s tests
"""
import json, re, shutil, sys, tempfile, unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

# Never on the Blog: a customer or the child the spoken help was made for, a hidden project, how the demos are
# obfuscated (the key or the scheme), the machines that run CI, or credentials. Daniel Vaughan may be named (D-25).
DENY = (r'blackstone', r'husqvarna', r'tech\s*day', r'leaders', r'\balex\b', r'mi-?jung', r'\bkang\b', r'megawatt', r'DEMO_KEY', r'xorshift',
        r'fnv-?1a', r'DLXDEMO', r'\bgb10\b', r'quixote', r'\bsuno\b', r'game-factories', r'@codetaming')
ATOM = '{http://www.w3.org/2005/Atom}'


class Blog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='dalex-blog-'))
        cls.out = build.build(ROOT, ROOT / 'site.json', cls.tmp / 'site')
        cls.posts = json.loads((ROOT / 'content/blog/posts.json').read_text(encoding='utf-8'))
        cls.base = json.loads((ROOT / 'site.json').read_text())['site']['base_url']

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_index_lists_every_post_and_the_nav_links_the_blog(self):
        index = (self.out / 'blog/index.html').read_text(encoding='utf-8')
        for p in self.posts:
            self.assertIn(f'href="{p["slug"]}/"', index)
        self.assertIn('href="blog/"', (self.out / 'index.html').read_text(encoding='utf-8'))
        self.assertIn('<a href="../"', index)

    def test_each_post_has_byline_date_reading_time_and_says_it_is_out_of_character(self):
        for p in self.posts:
            html = (self.out / 'blog' / p['slug'] / 'index.html').read_text(encoding='utf-8')
            self.assertIn(f'By {", ".join(p["authors"])}', html)
            self.assertIn(f'<time datetime="{p["date"]}">', html)
            self.assertRegex(html, r'\d+ min read')
            self.assertIn('Out of character.', html)
            self.assertIn('href="../../blog/feed.xml"', html)

    def test_feed_and_sitemap_list_exactly_the_posts(self):
        feed = ET.parse(self.out / 'blog/feed.xml').getroot()
        links = sorted(e.find(ATOM + 'link').get('href') for e in feed.findall(ATOM + 'entry'))
        self.assertEqual(links, sorted(f'{self.base}blog/{p["slug"]}/' for p in self.posts))
        sm = (self.out / 'sitemap.xml').read_text(encoding='utf-8')
        for p in self.posts:
            self.assertIn(f'{self.base}blog/{p["slug"]}/</loc>', sm)

    def test_posts_name_nothing_private(self):
        for f in [self.out / 'blog/index.html', self.out / 'blog/feed.xml'] + sorted((self.out / 'blog').glob('*/index.html')):
            text = f.read_text(encoding='utf-8')
            hits = sorted({m.group(0) for d in DENY for m in re.finditer(d, text, re.I)})
            self.assertEqual(hits, [], f)

    def test_a_post_without_metadata_is_refused(self):
        root = self.tmp / 'bad'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('_site', '.git', 'static', 'games'))
        (root / 'content/blog/posts.json').write_text(json.dumps([{'slug': 'x', 'title': 'X'}]))
        with self.assertRaises(build.BuildError):
            build.load_posts(root)


if __name__ == '__main__':
    unittest.main()
