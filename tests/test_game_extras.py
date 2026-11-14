"""Game page extras (D-47, proposed, dev preview): at a glance, the screen-shot lightbox, original documents, the
milestone timeline, From the archive and More from Dalex.

Run: python3 -m unittest discover -s tests
"""
import json, re, shutil, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
import build  # noqa: E402
import podcast  # noqa: E402
from test_site import Page, MAGIC, decode, key  # noqa: E402

JS = (ROOT / 'static/assets/lightbox.js').read_text(encoding='utf-8')


def parse(path: Path) -> Page:
    pg = Page()
    pg.feed(path.read_text(encoding='utf-8'))
    return pg


def section(html: str, heading_id: str) -> str:
    """The <section> whose heading has this id."""
    m = re.search(r'<section[^>]*aria-labelledby="' + heading_id + r'"[^>]*>(.*?)</section>', html, re.S)
    return m.group(1) if m else ''


class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = build.build(ROOT, ROOT / 'site.json', Path(cls.tmp.name) / '_site')
        cls.cfg = json.loads((ROOT / 'site.json').read_text())
        cls.visible = [g['slug'] for g in sorted(cls.cfg['games'], key=lambda g: g['order']) if g['visible']]
        cls.pages = {s: (cls.out / 'games' / s / 'index.html').read_text(encoding='utf-8') for s in cls.visible}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def game(self, slug):
        return json.loads((ROOT / 'games' / slug / 'game.json').read_text())

    def test_every_game_page_keeps_its_sections_and_adds_the_new_ones(self):
        for slug, html in self.pages.items():
            for hid in ('glance-h', 'play-h', 'about-h', 'controls-h', 'shots-h', 'docs-h', 'review-h', 'tape-h',
                        'credits-h', 'more-h'):
                self.assertIn(f'id="{hid}"', html, (slug, hid))

    def test_at_a_glance_holds_only_recorded_facts(self):
        for slug, html in self.pages.items():
            g, box = self.game(slug), section(html, 'glance-h')
            self.assertIn(f'<dd>{build.e(g["machine"])}</dd>', box, slug)
            self.assertIn('<dt>Developer</dt><dd>Dalex Software</dd>', box, slug)
            self.assertIn(build.nice_date(g['release']['date']), box, slug)
            genre = json.loads((ROOT / 'content/extras' / slug / 'milestones.json').read_text()).get('genre')
            if genre:
                self.assertIn(f'<dt>Genre</dt><dd>{build.e(genre["text"])}</dd>', box, slug)
            else:
                self.assertNotIn('Genre', box, slug)
        self.assertNotIn('Genre', section(self.pages['wolf'], 'glance-h'))   # WOLF has no specification

    def test_screen_shots_open_full_size_with_alt_text(self):
        for slug, html in self.pages.items():
            shots = section(html, 'shots-h')
            links = re.findall(r'<a class="zoom" href="([^"]+)" data-gallery="shots" aria-label="([^"]+)">'
                               r'<img [^>]*src="([^"]+)"[^>]*alt="([^"]+)"', shots)
            n = len(self.game(slug)['images']['shots'])
            self.assertEqual(len(links), n, slug)
            for i, (href, label, src, alt) in enumerate(links, 1):
                self.assertEqual(href, src, slug)
                self.assertTrue((self.out / 'games' / slug / href).is_file(), (slug, href))
                self.assertTrue(label.startswith(f'Image {i} of {n}'), (slug, label))
                self.assertGreater(len(alt), 10, (slug, src))
            self.assertIn('assets/lightbox.js', html, slug)

    def test_lightbox_script_counts_moves_closes_and_stores_nothing(self):
        for needle in ("'Image ' + (at + 1) + ' of ' + group.length", 'ArrowRight', 'ArrowLeft', 'showModal',
                       "addEventListener('close'", 'opener.focus()', 'img.alt = thumb'):
            self.assertIn(needle, JS)
        for bad in ('localStorage', 'sessionStorage', 'document.cookie', 'fetch(', 'http'):
            self.assertNotIn(bad, JS)

    def test_the_review_is_printed_from_the_kit_only(self):
        for slug, html in self.pages.items():
            rev = self.game(slug)['review']
            mag = re.search(r'<article class="mag".*?</article>', html, re.S).group(0)
            self.assertIn(f'<span class="overall-num">{rev["overall"]}%</span>', mag, slug)
            if (rev.get('quote') or {}).get('text'):
                self.assertIn(build.e(rev['quote']['text']), mag, slug)
            self.assertEqual(len(re.findall(r'class="num">', mag)),
                             len([k for k, _ in build.SCORE_NAMES if k in rev['scores']]), slug)

    def test_the_timeline_is_the_milestone_plan_in_order(self):
        html = self.pages['wolf']
        made = section(html, 'made-h')
        self.assertEqual(re.findall(r'<span class="tl-m">M(\d+)</span>', made), [str(n) for n in range(1, 8)])
        self.assertIn('<strong>Vertical slice</strong>', made)
        self.assertIn('<time class="tl-date" datetime="2026-10-19">19 October 2026</time>', made)
        for slug, html in self.pages.items():
            data = json.loads((ROOT / 'content/extras' / slug / 'milestones.json').read_text())
            made = section(html, 'made-h')
            self.assertEqual(len(re.findall(r'class="tl-m"', made)), len(data['milestones']), slug)
            release = self.game(slug)['release']['milestone']
            self.assertTrue(all(m['milestone'] <= release for m in data['milestones']), slug)
            self.assertNotRegex(made, r'(?i)\bowner\b|issue #|\bD-\d+', slug)    # notes for the team stay out
            for m in data['milestones']:
                if m['shot']:
                    self.assertTrue((self.out / 'games' / slug / 'milestones' / m['shot']['src']).is_file(), slug)

    def test_archive_cards_lead_somewhere_real(self):
        released = {ep['slug'] for ep in podcast.load(ROOT)[1]}
        for slug, html in self.pages.items():
            box = section(html, 'archive-h')
            for href in re.findall(r'<a class="card-link" href="([^"#]+)', box):
                target = (self.out / 'games' / slug / href).resolve()
                self.assertTrue((target / 'index.html').is_file(), (slug, href))
            for ep in re.findall(r'href="\.\./\.\./podcast/([^/]+)/"', box):
                self.assertIn(ep, released, slug)
        book = (ROOT / 'content/book.html').read_text()
        for f in sorted((ROOT / 'content/extras').glob('*/extras.json')):
            for a in json.loads(f.read_text())['archive']:
                if a['kind'] == 'book' and len(a['chapters']) == 1:
                    self.assertIn(f'<li>{a["title"]} &mdash; {a["by"]}</li>', book, f)

    def test_more_from_dalex_lists_the_other_shown_games(self):
        for slug, html in self.pages.items():
            more = section(html, 'more-h')
            linked = re.findall(r'href="\.\./\.\./games/([a-z0-9-]+)/"', more)
            self.assertEqual(linked, [s for s in self.visible if s != slug], slug)

    def test_every_page_still_parses_cleanly(self):
        for slug in self.pages:
            pg = parse(self.out / 'games' / slug / 'index.html')
            self.assertEqual(pg.problems, [], slug)
            self.assertEqual(pg.stack, [], slug)
            for img in pg.imgs:
                self.assertIn('alt', img, (slug, img.get('src')))

    def test_footer_still_says_what_is_real(self):
        for html in self.pages.values():
            self.assertIn('Dalex Software and INK &amp; PAPER are fictional; the games are real.', html)


class Fixture(unittest.TestCase):
    """A hidden game with extras of its own never reaches the site, not even in More from Dalex."""

    def test_hidden_game_and_its_extras_stay_out(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            shutil.copytree(ROOT / 'static', t / 'static')
            shutil.copytree(ROOT / 'content', t / 'content')
            for slug, title in (('shown-game', 'Shown Game'), ('other-game', 'Other Game'),
                                ('secret-game', 'Secret Game')):
                d = t / 'games' / slug
                (d / 'shots').mkdir(parents=True)
                tape = b'\x13\x00' + slug.encode()
                (d / 'demo.bin').write_bytes(MAGIC + decode(MAGIC + tape, key()))
                (d / 'shots/shot-1.png').write_bytes(b'png')
                (d / 'cover.jpg').write_bytes(b'jpg')
                (d / 'game.json').write_text(json.dumps({
                    'slug': slug, 'title': title, 'machine': 'ZX Spectrum 128K', 'tagline': 't', 'blurb': 'b',
                    'controls': [['Q', 'Up']], 'jsspeccy_machine': 128,
                    'release': {'sha256': '0' * 64, 'date': '2026-10-01', 'milestone': 2},
                    'demo': {'src': 'demo.bin', 'sha256': __import__('hashlib').sha256(tape).hexdigest()},
                    'review': {'overall': 70, 'scores': {'overall': 70}, 'quote': {}},
                    'images': {'cover': {'src': 'cover.jpg', 'size': [1200, 1500], 'alt': f'{title} cover'},
                               'shots': [{'src': 'shots/shot-1.png', 'size': [256, 192], 'alt': f'{title} shot',
                                          'caption': ''}]},
                    'credits': [{'role': 'Cover art', 'name': 'A Painter'}]}))
                ex = t / 'content/extras' / slug
                ex.mkdir(parents=True)
                (ex / 'm1.png').write_bytes(b'png')
                (ex / 'milestones.json').write_text(json.dumps({'genre': None, 'milestones': [
                    {'milestone': 1, 'title': f'{slug} first', 'date': '2026-09-01',
                     'shot': {'src': 'm1.png', 'size': [256, 192], 'caption': 'The first one.'}},
                    {'milestone': 2, 'title': 'final', 'date': None, 'shot': None}]}))
            (t / 'site.json').write_text(json.dumps({
                'site': {'name': 'Fixture', 'base_url': 'https://example.test/'},
                'games': [{'slug': 'shown-game', 'visible': True, 'order': 1, 'featured': True},
                          {'slug': 'other-game', 'visible': True, 'order': 2},
                          {'slug': 'secret-game', 'visible': False, 'order': 3}]}))
            out = build.build(t, t / 'site.json', t / '_site')
            html = (out / 'games/shown-game/index.html').read_text()
            self.assertIn('href="../../games/other-game/"', section(html, 'more-h'))
            self.assertNotIn('shown-game/"', section(html, 'more-h'))
            self.assertIn('<figcaption>The front of the tape box. Cover art: A Painter.</figcaption>', html)
            self.assertIn('<strong>Final</strong>', html)
            self.assertTrue((out / 'games/shown-game/milestones/m1.png').is_file())
            self.assertFalse((out / 'games/secret-game').exists())
            blob = ''.join(p.read_text(errors='replace') for p in out.rglob('*')
                           if p.is_file() and p.suffix in ('.html', '.xml', '.txt'))
            for bad in ('secret-game', 'Secret Game'):
                self.assertNotIn(bad, blob)

    def test_a_price_in_the_extras_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            shutil.copytree(ROOT / 'static', t / 'static')
            shutil.copytree(ROOT / 'content', t / 'content')
            d = t / 'games/fx'
            (d / 'shots').mkdir(parents=True)
            (d / 'game.json').write_text(json.dumps({
                'slug': 'fx', 'title': 'Fx', 'machine': 'ZX Spectrum 128K', 'controls': [], 'release': {},
                'demo': None, 'review': {}, 'images': {'shots': [{'src': 'shots/s.png', 'size': [256, 192],
                                                                  'alt': 'a'}]}}))
            ex = t / 'content/extras/fx'
            ex.mkdir(parents=True)
            (ex / 'milestones.json').write_text(json.dumps({'milestones': [
                {'milestone': 1, 'title': 'Yours for £2.99', 'date': None, 'shot': None}]}))
            (t / 'site.json').write_text(json.dumps({'site': {'name': 'x', 'base_url': 'https://x.test/'},
                                                     'games': [{'slug': 'fx', 'visible': True, 'order': 1,
                                                                'demo': None}]}))
            with self.assertRaises(build.BuildError):
                build.build(t, t / 'site.json', t / 'out')


if __name__ == '__main__':
    unittest.main()
