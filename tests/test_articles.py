"""Articles (D-29, D-30): INK & PAPER features, out of character. The index, pages and feed are built, the Blog's
old addresses send readers on, each article keeps the shared vocabulary the magazine prints, and none names
anything private.

Run: python3 -m unittest discover -s tests
"""
import json, re, shutil, sys, tempfile, unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

# Never in an article: a customer or the child the spoken help was made for, a hidden project, how the demos are
# obfuscated (the key or the scheme), the machines that run CI, Suno (not used for the games), credentials, or taking
# apart other people's games (disassembly and the archives and tools for it), which reads as dubious copyright-wise.
# Daniel Vaughan may be named (D-25).
DENY = (r'blackstone', r'husqvarna', r'tech\s*day', r'leaders', r'\balex\b', r'mi-?jung', r'\bkang\b', r'megawatt',
        r'DEMO_KEY', r'xorshift', r'fnv-?1a', r'DLXDEMO', r'\bgb10\b', r'quixote', r'\bsuno\b', r'game-factories',
        r'@codetaming', r'disassembl', r'sna2skool', r'tap2sna', r'\btosec\b', r'\bzxdb\b',
        r'commercial games')
# The magazine's own pages (contents, cover) print cover_title and tease, so they keep its banned-terms rule
# (zx-media-kit check_review.py): no agents, AI, tests, tools or anything after 1990. A small copy of that list.
MAGAZINE_BANNED = re.compile(r'\bagents?\b|(?-i:\bA\.?I\b)|\bemulat\w*|\btest\w*|\bverif\w*|\bpipeline\b|\bbuilds?\b'
                             r'|\bweb\w*|\bonline\b|\binternet\b|\bowners?\b|\bretro\w*|\bscripted\b', re.I)
ATOM = '{http://www.w3.org/2005/Atom}'


class Articles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='dalex-articles-'))
        cls.out = build.build(ROOT, ROOT / 'site.json', cls.tmp / 'site')
        cls.arts = json.loads((ROOT / 'content/articles/articles.json').read_text(encoding='utf-8'))
        cls.base = json.loads((ROOT / 'site.json').read_text())['site']['base_url']

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_studio_page_lists_every_article_as_learn_more_and_there_is_no_articles_section(self):
        """D-33: no Articles in the navigation; the articles are the Studio page's Learn more."""
        studio = (self.out / 'studio/index.html').read_text(encoding='utf-8')
        self.assertIn('<h2 id="learn-more">Learn more</h2>', studio)
        for a in self.arts:
            self.assertIn(f'href="{a["slug"]}/"', studio)
            self.assertIn(build.e(a['tease']), studio)
        for page in sorted(self.out.rglob('*.html')):
            text = page.read_text(encoding='utf-8')
            self.assertNotRegex(text, r'<li><a href="[./]*articles/"', page)   # not in the nav
            self.assertNotIn('>Articles<', text, page)
        home = (self.out / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('href="articles/"', home)
        self.assertNotIn('href="blog/"', home)

    def test_each_article_is_a_feature_with_byline_and_says_it_is_out_of_character(self):
        for a in self.arts:
            html = (self.out / 'studio' / a['slug'] / 'index.html').read_text(encoding='utf-8')
            self.assertIn('<article class="feature">', html)
            self.assertIn(f'<p class="kicker">{build.e(a["kicker"])}</p>', html)
            self.assertIn(f'<p class="standfirst">{build.e(a["standfirst"])}</p>', html)
            self.assertIn(f'Words: {a["byline"]}', html)
            self.assertIn(f'<time datetime="{a["date"]}">', html)
            self.assertRegex(html, r'\d+ min read')
            self.assertIn('Out of character.', html)
            self.assertIn('href="../../studio/feed.xml"', html)
            self.assertIn('<a href="../">The Studio</a>', html)                 # the breadcrumb
            self.assertIn(f'<link rel="canonical" href="{self.base}studio/{a["slug"]}/">', html)

    def test_the_old_addresses_send_readers_to_the_studio(self):
        """The Blog's (D-30) and the Articles section's (D-33) old addresses are stubs, in no sitemap or feed."""
        for old, to in (('blog/index.html', '../studio/'), ('articles/index.html', '../studio/')):
            stub = (self.out / old).read_text(encoding='utf-8')
            self.assertIn(f'<meta http-equiv="refresh" content="0; url={to}">', stub)
            self.assertIn(f'<link rel="canonical" href="{self.base}studio/">', stub)
        for a in self.arts:
            stub = (self.out / 'articles' / a['slug'] / 'index.html').read_text(encoding='utf-8')
            self.assertIn(f'url=../../studio/{a["slug"]}/"', stub)
            if a.get('moved_from_blog'):
                stub = (self.out / 'blog' / a['slug'] / 'index.html').read_text(encoding='utf-8')
                self.assertIn(f'url=../../studio/{a["slug"]}/"', stub)
        sm = (self.out / 'sitemap.xml').read_text(encoding='utf-8')
        self.assertNotIn('/blog/', sm)
        self.assertNotIn('/articles/', sm)

    def test_feed_and_sitemap_list_exactly_the_articles(self):
        for where in ('studio/feed.xml', 'articles/feed.xml'):     # the old address stays for its subscribers
            feed = ET.parse(self.out / where).getroot()
            links = sorted(x.find(ATOM + 'link').get('href') for x in feed.findall(ATOM + 'entry'))
            self.assertEqual(links, sorted(f'{self.base}studio/{a["slug"]}/' for a in self.arts))
            ids = sorted(x.find(ATOM + 'id').text for x in feed.findall(ATOM + 'entry'))
            self.assertEqual(ids, sorted(f'{self.base}articles/{a["slug"]}/' for a in self.arts))  # unchanged ids
        sm = (self.out / 'sitemap.xml').read_text(encoding='utf-8')
        for a in self.arts:
            self.assertIn(f'{self.base}studio/{a["slug"]}/</loc>', sm)
        self.assertNotIn('blog/feed.xml', ''.join(p.read_text() for p in self.out.rglob('*.html')))

    def test_magazine_lines_keep_the_magazines_rules(self):
        for a in self.arts:
            for k in ('cover_title', 'tease'):
                self.assertIsNone(MAGAZINE_BANNED.search(a[k]), f'{a["slug"]} {k}: {a[k]!r}')

    def test_articles_name_nothing_private(self):
        files = [self.out / 'studio/feed.xml'] + sorted((self.out / 'articles').rglob('*.*'))
        files += [self.out / 'studio' / a['slug'] / 'index.html' for a in self.arts] + sorted((self.out / 'blog').rglob('*.html'))
        for f in files:
            text = f.read_text(encoding='utf-8')
            hits = sorted({m.group(0) for d in DENY for m in re.finditer(d, text, re.I)})
            self.assertEqual(hits, [], f)

    def test_markup_outside_the_shared_vocabulary_is_refused(self):
        build.check_fragment('ok.html', '<h2 id="a">A</h2><aside class="boxout"><h3>B</h3><p>c</p></aside>'
                                        '<blockquote class="pull"><p>d</p></blockquote>')
        for bad in ('<img src="x.png" alt="">', '<div>x</div>', '<p style="color:red">x</p>',
                    '<aside class="sidebar">x</aside>', '<script>x</script>'):
            with self.assertRaises(build.BuildError, msg=bad):
                build.check_fragment('bad.html', bad)

    def test_an_article_without_its_metadata_is_refused(self):
        root = self.tmp / 'bad'
        (root / 'content/articles').mkdir(parents=True)
        (root / 'content/articles/articles.json').write_text(json.dumps([{'slug': 'x', 'title': 'X'}]))
        with self.assertRaises(build.BuildError):
            build.load_articles(root)


if __name__ == '__main__':
    unittest.main()
