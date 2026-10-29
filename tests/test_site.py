"""Site build checks: determinism, hidden games, tapes and hashes, links and basic HTML health.

Run: python3 -m unittest discover -s tests
"""
import hashlib, json, re, shutil, sys, tempfile, unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}


def tree(out: Path) -> dict:
    return {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(out.rglob('*')) if p.is_file()}


class Page(HTMLParser):
    """Collects links, ids, images and tag balance problems for one HTML file."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.ids, self.imgs, self.problems, self.stack = [], set(), [], [], []
        self.h1 = 0
        self.title = ''
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            if a['id'] in self.ids:
                self.problems.append(f'duplicate id {a["id"]}')
            self.ids.add(a['id'])
        for k in ('href', 'src'):
            if a.get(k) is not None:
                self.links.append((tag, k, a[k]))
        if tag == 'img':
            self.imgs.append(a)
        if tag == 'h1':
            self.h1 += 1
        if tag == 'title':
            self._in_title = True
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f'unbalanced </{tag}> (open: {self.stack[-3:]})')
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()
        if tag == 'title':
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def parse(p: Path) -> Page:
    pg = Page()
    pg.feed(p.read_text(encoding='utf-8'))
    pg.close()
    return pg


class Built(unittest.TestCase):
    """Builds the real site.json once into a temporary folder."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='dalex-site-'))
        cls.out = build.build(ROOT, ROOT / 'site.json', cls.tmp / 'a')
        cls.cfg = json.loads((ROOT / 'site.json').read_text())
        cls.visible = [g['slug'] for g in cls.cfg['games'] if g['visible']]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_build_is_deterministic(self):
        again = build.build(ROOT, ROOT / 'site.json', self.tmp / 'b')
        self.assertEqual(tree(self.out), tree(again))

    def test_core_pages_exist(self):
        for rel in ('index.html', 'games/index.html', 'about/index.html', '404.html', 'sitemap.xml',
                    'robots.txt', 'feed.xml', 'favicon.ico', 'favicon.png', 'CNAME',
                    'jsspeccy/COPYING', 'jsspeccy/jsspeccy.js', 'assets/player.js', 'assets/site.css'):
            self.assertTrue((self.out / rel).is_file(), rel)
        self.assertEqual((self.out / 'CNAME').read_text().strip(), 'dalex-software.co.uk')

    def test_every_visible_game_links_its_tape_with_the_right_sha256(self):
        for slug in self.visible:
            game = json.loads((ROOT / 'games' / slug / 'game.json').read_text())
            tape = game['release']['tape']
            built_tape = self.out / 'games' / slug / tape
            self.assertTrue(built_tape.is_file(), built_tape)
            sha = hashlib.sha256(built_tape.read_bytes()).hexdigest()
            self.assertEqual(sha, game['release']['sha256'], slug)
            html = (self.out / 'games' / slug / 'index.html').read_text()
            self.assertIn(f'href="{tape}" download', html, slug)
            self.assertIn(f'data-tap="{tape}"', html, slug)
            self.assertIn(f'<code id="tape-sha">{sha}</code>', html, slug)

    def test_game_json_is_not_deployed(self):
        self.assertEqual(sorted(self.out.rglob('game.json')), [])

    def test_no_broken_internal_links_and_basic_html(self):
        pages = sorted(self.out.rglob('*.html'))
        self.assertGreaterEqual(len(pages), 4)
        site_base = self.cfg['site']['base_url']
        base_path = urlsplit(site_base).path
        for p in pages:
            if p.parent.name == 'jsspeccy':
                continue
            pg = parse(p)
            rel = p.relative_to(self.out)
            text = p.read_text(encoding='utf-8')
            self.assertTrue(text.startswith('<!doctype html>'), rel)
            self.assertIn('<html lang="en-GB">', text, rel)
            self.assertTrue(pg.title.strip(), f'{rel}: empty <title>')
            self.assertEqual(pg.h1, 1, f'{rel}: expected one <h1>')
            self.assertEqual(pg.problems, [], rel)
            self.assertEqual(pg.stack, [], f'{rel}: unclosed {pg.stack}')
            for img in pg.imgs:
                self.assertIn('alt', img, f'{rel}: <img src={img.get("src")}> has no alt')
                self.assertTrue(img.get('width') and img.get('height'), f'{rel}: {img.get("src")} size')
            for tag, attr, url in pg.links:
                u = urlsplit(url)
                if u.scheme in ('http', 'https', 'mailto'):
                    if url.startswith(site_base):
                        continue          # canonical URLs on the real domain
                    continue
                if url.startswith('#'):
                    self.assertIn(url[1:], pg.ids, f'{rel}: anchor {url}')
                    continue
                path = unquote(u.path)
                if p.name == '404.html' and path.startswith(base_path):
                    target = self.out / path[len(base_path):]
                else:
                    target = (p.parent / path).resolve()
                if path.endswith('/') or target.is_dir():
                    target = target / 'index.html'
                self.assertTrue(target.is_file(), f'{rel}: broken {attr}="{url}" -> {target}')
                if u.fragment and target.suffix == '.html':
                    self.assertIn(u.fragment, parse(target).ids, f'{rel}: anchor {url}')

    def test_css_and_js_references_resolve(self):
        css = (self.out / 'assets/site.css').read_text()
        for url in re.findall(r'url\(["\']?([^"\')]+)', css):
            if not url.startswith(('data:', 'http')):
                self.assertTrue((self.out / 'assets' / url).is_file(), url)

    def test_sitemap_and_feed_list_exactly_the_visible_games(self):
        sm = (self.out / 'sitemap.xml').read_text()
        feed = (self.out / 'feed.xml').read_text()
        for g in self.cfg['games']:
            url = f'{self.cfg["site"]["base_url"]}games/{g["slug"]}/'
            self.assertEqual(url in sm, g['visible'], g['slug'])
            self.assertEqual(url in feed, g['visible'], g['slug'])

    def test_one_featured_game_on_home(self):
        featured = [g for g in self.cfg['games'] if g.get('featured') and g['visible']]
        self.assertLessEqual(len(featured), 1)
        if featured:
            home = (self.out / 'index.html').read_text()
            title = json.loads((ROOT / 'games' / featured[0]['slug'] / 'game.json').read_text())['title']
            self.assertIn(f'<h2 id="hero-title" class="hero-title">{build.e(title)}</h2>', home)

    def test_no_tracking(self):
        for p in self.out.rglob('*.html'):
            text = p.read_text(encoding='utf-8').lower()
            for bad in ('google-analytics', 'googletagmanager', 'gtag(', 'plausible', 'fonts.googleapis'):
                self.assertNotIn(bad, text, p)


class HiddenGames(unittest.TestCase):
    """A hidden game is in no page, sitemap or feed, and none of its files are deployed."""

    def test_hidden_game_is_not_deployed(self):
        cfg = json.loads((ROOT / 'site.json').read_text())
        if len(cfg['games']) < 2:
            self.skipTest('needs two published games')
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            hidden = cfg['games'][0]['slug']
            for g in cfg['games']:
                g['visible'] = g['slug'] != hidden
                if g['slug'] == hidden:
                    g['featured'] = False
            conf = t / 'site.json'
            conf.write_text(json.dumps(cfg))
            out = build.build(ROOT, conf, t / 'out')
            title = json.loads((ROOT / 'games' / hidden / 'game.json').read_text())['title']
            self.assertFalse((out / 'games' / hidden).exists())
            for p in out.rglob('*'):
                if p.is_file() and p.suffix in ('.html', '.xml', '.txt'):
                    text = p.read_text(encoding='utf-8')
                    self.assertNotIn(f'games/{hidden}/', text, p)
                    self.assertNotIn(f'{hidden}.tap', text, p)
                    if p.suffix == '.html' or p.suffix == '.xml':
                        self.assertNotIn(f'>{build.e(title)}<', text, p)
            self.assertNotIn(hidden, ' '.join(str(p) for p in out.rglob('*')))

    def test_fixture_config_with_hidden_game(self):
        """The same rule on a two-game fixture site, independent of the real games."""
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            shutil.copytree(ROOT / 'static', t / 'static')
            shutil.copytree(ROOT / 'content', t / 'content')
            for slug, title in (('shown-game', 'Shown Game'), ('secret-game', 'Secret Game')):
                d = t / 'games' / slug
                (d / 'shots').mkdir(parents=True)
                (d / f'{slug}.tap').write_bytes(slug.encode())
                (d / 'shots/shot-1.png').write_bytes(b'png')
                (d / 'game.json').write_text(json.dumps({
                    'slug': slug, 'title': title, 'machine': 'ZX Spectrum 128K', 'tagline': 't', 'blurb': 'b',
                    'controls': [['Q', 'Up']], 'jsspeccy_machine': 128,
                    'release': {'tape': f'{slug}.tap', 'sha256': hashlib.sha256(slug.encode()).hexdigest(),
                                'size': len(slug), 'date': '2026-10-01'},
                    'review': {'overall': 70, 'scores': {'overall': 70}, 'quote': {}},
                    'images': {'shots': [{'src': 'shots/shot-1.png', 'size': [256, 192], 'alt': 'a', 'caption': ''}]},
                    'credits': []}))
            (t / 'site.json').write_text(json.dumps({
                'site': {'name': 'Fixture', 'base_url': 'https://example.test/'},
                'games': [{'slug': 'shown-game', 'visible': True, 'order': 1, 'featured': True},
                          {'slug': 'secret-game', 'visible': False, 'order': 2, 'featured': False}]}))
            out = build.build(t, t / 'site.json', t / '_site')
            self.assertTrue((out / 'games/shown-game/shown-game.tap').is_file())
            self.assertFalse((out / 'games/secret-game').exists())
            blob = ''.join(p.read_text(errors='replace') for p in out.rglob('*')
                           if p.is_file() and p.suffix in ('.html', '.xml', '.txt'))
            self.assertNotIn('secret-game', blob)
            self.assertNotIn('Secret Game', blob)
            self.assertIn('Shown Game', blob)

    def test_bad_config_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            conf = Path(t) / 'site.json'
            conf.write_text(json.dumps({'site': {'name': 'x', 'base_url': 'https://x.test/'},
                                        'games': [{'slug': 'nope', 'visible': True, 'order': 1}]}))
            with self.assertRaises(build.BuildError):
                build.build(ROOT, conf, Path(t) / 'out')


if __name__ == '__main__':
    unittest.main()
