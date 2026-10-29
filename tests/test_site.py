"""Site build checks: determinism, hidden games, demos (obfuscated, decoding to their recorded sha256),
no tapes or prices anywhere, links and basic HTML health.

Run: python3 -m unittest discover -s tests
"""
import hashlib, json, re, shutil, sys, tempfile, unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

# The same algorithm as static/assets/player.js, written out again here so the test does not trust
# build.py's copy: 'DLXDEMO1' + XOR with an xorshift32 keystream seeded by FNV-1a of DEMO_KEY.
MAGIC = b'DLXDEMO1'
# Currency amounts: £2.99, £ 3, $5, €4, 99p, 7.95 p, 3 pence, 2 quid, 5 pounds, 3/6d, &pound;.
PRICE = re.compile(r'[£$€]\s?\d|(?<![\w.#-])\d+(?:\.\d+)?\s?p\b(?!x)|\b\d+(?:\.\d+)?\s?(?:pence|quid|pounds?)\b'
                   r'|\b\d+/\d+d\b|&pound;', re.I)
TEXT = {'.html', '.xml', '.txt', '.css', '.js', '.json', '.vtt', '.md', '.svg'}


def key() -> str:
    js = (ROOT / 'static/assets/player.js').read_text(encoding='utf-8')
    return re.search(r"const DEMO_KEY = '([0-9a-f]+)';", js).group(1)


def decode(blob: bytes, k: str) -> bytes:
    assert blob[:len(MAGIC)] == MAGIC, 'no demo header'
    h = 0x811C9DC5
    for c in k.encode():
        h = ((h ^ c) * 0x01000193) % 2**32
    s, out = h or 1, bytearray()
    for b in blob[len(MAGIC):]:
        s = (s ^ (s << 13)) % 2**32
        s ^= s >> 17
        s = (s ^ (s << 5)) % 2**32
        out.append(b ^ (s >> 24))
    return bytes(out)


def text_files(out: Path):
    """Every built text file except the vendored JSSpeccy build (minified code, GPL notices)."""
    return [p for p in sorted(out.rglob('*'))
            if p.is_file() and p.suffix.lower() in TEXT and 'jsspeccy' not in p.relative_to(out).parts]


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

    def test_every_demo_decodes_to_its_recorded_sha256(self):
        k = key()
        played = 0
        for g in self.cfg['games']:
            if not g['visible']:
                continue
            slug = g['slug']
            game = json.loads((ROOT / 'games' / slug / 'game.json').read_text())
            html = (self.out / 'games' / slug / 'index.html').read_text()
            demo = game.get('demo') if g.get('demo', True) is not None else None
            built = self.out / 'games' / slug / 'demo.bin'
            if not demo:
                self.assertFalse(built.exists(), slug)
                self.assertIn('Demo coming soon', html, slug)
                self.assertNotIn('id="play"', html, slug)
                self.assertNotIn('player.js', html, slug)
                continue
            played += 1
            tape = decode(built.read_bytes(), k)
            self.assertEqual(hashlib.sha256(tape).hexdigest(), demo['sha256'], slug)
            self.assertEqual(g['demo']['sha256'], demo['sha256'], f'{slug}: site.json and game.json disagree')
            self.assertEqual(tape[:2], b'\x13\x00', f'{slug}: decoded demo is not a tape')
            self.assertNotEqual(demo['sha256'], game['release']['sha256'], f'{slug}: the demo is the full release')
            self.assertNotIn(tape[:64], built.read_bytes(), f'{slug}: demo.bin holds the plain tape')
            self.assertIn('data-demo="demo.bin"', html, slug)
            self.assertIn('&#9654; Play the demo</button>', html, slug)
            self.assertIn('<strong>The demo:</strong> ' + build.e(g['demo']['contains']), html, slug)
        self.assertGreaterEqual(played, 2)

    def test_no_tape_or_download_anywhere(self):
        for p in self.out.rglob('*'):
            self.assertNotIn(p.suffix.lower(), ('.tap', '.tzx', '.z80', '.sna', '.pdf'), p)
        for p in text_files(self.out):
            if p.suffix == '.js':
                continue          # player.js names "demo.tap" only to pick JSSpeccy's loader for the decoded bytes
            text = p.read_text(encoding='utf-8')
            self.assertIsNone(re.search(r'\.(tap|tzx)\b', text, re.I), f'{p}: names a tape file')
            if p.suffix == '.html':
                for m in re.finditer(r'<a [^>]*\bdownload\b[^>]*>', text):
                    self.assertIn('.mp4"', m.group(0), f'{p}: download link {m.group(0)}')

    def test_no_price_kit_art_or_review_pdf(self):
        for slug in self.visible:
            names = {p.name for p in (self.out / 'games' / slug).rglob('*')}
            for bad in ('inlay.jpg', 'advert.jpg', 'poster.jpg', 'review.pdf'):
                self.assertNotIn(bad, names, slug)

    def test_no_currency_amounts_in_any_built_text(self):
        files = text_files(self.out)
        self.assertGreater(len(files), 10)
        for p in files:
            text = p.read_text(encoding='utf-8')
            m = PRICE.search(text)
            self.assertIsNone(m, f'{p.relative_to(self.out)}: price {text[max(0, m.start() - 40):m.end() + 20]!r}'
                              if m else '')
        for slug in self.visible:
            self.assertIn('Price to be confirmed', (self.out / 'games' / slug / 'index.html').read_text(), slug)

    def test_price_regex_catches_prices_and_spares_dates(self):
        for bad in ('£2.99', '£ 3', '$5', '€4.50', '99p', 'only 7.95p', '3 pence', '2 quid', '5 pounds', '3/6d'):
            self.assertIsNotNone(PRICE.search(bad), bad)
        for ok in ('29 October 2026', '2026-10-29', '128K', '16px', '1.5em', '#3p', 'A4p', 'level 2 of 4'):
            self.assertIsNone(PRICE.search(ok), ok)

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


class Player(unittest.TestCase):
    """The keyboard contract of static/assets/player.js (D-21) and the touch pad (D-22), checked statically."""

    @classmethod
    def setUpClass(cls):
        cls.js = (ROOT / 'static/assets/player.js').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static/assets/site.css').read_text(encoding='utf-8')
        cls.tmp = Path(tempfile.mkdtemp(prefix='dalex-player-'))
        cls.out = build.build(ROOT, ROOT / 'site.json', cls.tmp / 'a')
        cls.cfg = json.loads((ROOT / 'site.json').read_text())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def fn(self, name):
        m = re.search(rf'function {name}\(event\) \{{(.*?)\n  \}}', self.js, re.S)
        self.assertIsNotNone(m, name)
        return m.group(1)

    def test_game_keys_are_kept_from_the_page_in_the_capture_phase(self):
        self.assertRegex(self.js, r"for \(const type of \['keydown', 'keyup', 'keypress'\]\) "
                                  r"host\.addEventListener\(type, onKey, true\)")
        body = self.fn('onKey')
        self.assertIn('event.preventDefault()', body)
        self.assertIn('loading || running()', body)          # from the moment Play is pressed
        self.assertIn('if (!hasFocus()) return;', body)       # only while the game has focus

    def test_tab_and_escape_are_left_to_the_page(self):
        body = self.fn('onKey')
        tab = body.index("event.key === 'Tab' || event.key === 'Escape'")
        first_prevent = body.index('event.preventDefault()')
        self.assertLess(tab, first_prevent, 'Tab/Escape must be handled before any preventDefault')
        branch = body[tab:body.index('return;', tab)]
        self.assertIn('event.stopPropagation()', branch)      # JSSpeccy would preventDefault them
        self.assertNotIn('.preventDefault(', branch)
        self.assertIn('host.blur()', branch)                  # Escape releases the keyboard
        self.assertIn("event.key === 'Tab'", self.fn('passThrough'))
        self.assertIn('Press Tab to leave the game', self.js)

    def test_play_focuses_and_shows_the_screen_before_loading(self):
        m = re.search(r'async function loadGame\(\) \{(.*?)\n  \}', self.js, re.S)
        body = m.group(1)
        self.assertLess(body.index('focusGame()'), body.index('play.disabled = true'))
        self.assertLess(body.index('showScreen()'), body.index('play.disabled = true'))

    def test_full_screen_takes_the_stage_with_the_pad(self):
        self.assertIn('stage.requestFullscreen', self.js)
        self.assertNotIn('toggleFullscreen', self.js)

    def test_focus_ring_is_visible(self):
        self.assertIn('.screen:focus-within { outline: 3px solid var(--focus)', self.css)

    def test_every_playable_game_has_a_touch_layout_from_its_own_controls(self):
        playable = 0
        for g in self.cfg['games']:
            if not g['visible'] or not g.get('demo'):
                continue
            playable += 1
            slug = g['slug']
            game = json.loads((ROOT / 'games' / slug / 'game.json').read_text())
            allowed = build.control_keys(game['controls'])
            t = g.get('touch')
            self.assertTrue(t, f'{slug}: no touch layout')
            used = set((t.get('dpad') or {}).values()) | {k for b in t['buttons'] for k in b['keys'].split()}
            self.assertTrue(used, slug)
            self.assertLessEqual(used, allowed, f'{slug}: touch keys not in its controls')
            self.assertIn('SPACE', used, f'{slug}: no start/fire button')
            html = (self.out / 'games' / slug / 'index.html').read_text()
            self.assertIn('<div id="stage" class="stage">', html, slug)
            self.assertIn('<div id="pad" class="pad" role="group" aria-label="Touch controls" hidden>', html, slug)
            self.assertIn('id="pad-toggle"', html, slug)
            buttons = re.findall(r'<button type="button" class="(?:dir \w+|pad-btn[^"]*)"[^>]*>', html)
            self.assertEqual(len(buttons), len(t.get('dpad') or {}) + len(t['buttons']), slug)
            for b in buttons:
                self.assertRegex(b, r'aria-label="[^"]+"', slug)
                keys = re.search(r'data-keys="([^"]+)"', b).group(1).split()
                self.assertLessEqual(set(keys), allowed, slug)
        self.assertGreaterEqual(playable, 4)

    def test_control_keys(self):
        self.assertEqual(build.control_keys([['Q / A / O / P', 'Walk'], ['SPACE', 'x'], ['Q (paused)', 'Quit'],
                                             ['O and P in turn', 'Pump'], ['Two keys together', 'Diagonal'],
                                             ['D (title)', 'Mode'], ['S / A', 'Down']]),
                         {'Q', 'A', 'O', 'P', 'SPACE', 'D', 'S'})

    def test_pad_is_not_scrolled_selected_or_zoomed(self):
        pad = re.search(r'\n\.pad \{([^}]*)\}', self.css).group(1)
        self.assertIn('touch-action: none', pad)
        self.assertIn('user-select: none', pad)
        self.assertRegex(self.css, r'\.pad button \{[^}]*min-width: (4[89]|[5-9]\d)px; min-height: (4[89]|[5-9]\d)px')
        for t in ('pointerup', 'pointercancel', 'lostpointercapture', 'setPointerCapture', "'contextmenu'",
                  '(pointer: coarse)', 'navigator.vibrate'):
            self.assertIn(t, self.js)

    def test_every_demo_is_a_single_level_demo_build(self):
        for g in self.cfg['games']:
            if g['visible'] and g.get('demo'):
                game = json.loads((ROOT / 'games' / g['slug'] / 'game.json').read_text())
                self.assertTrue(game['demo']['source_tape'].endswith('-demo.tap'), g['slug'])


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
                    self.assertNotIn(f'{hidden}/demo.bin', text, p)
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
                tape = b'\x13\x00' + slug.encode()
                (d / 'demo.bin').write_bytes(MAGIC + decode(MAGIC + tape, key()))   # XOR is its own inverse
                (d / 'shots/shot-1.png').write_bytes(b'png')
                (d / 'game.json').write_text(json.dumps({
                    'slug': slug, 'title': title, 'machine': 'ZX Spectrum 128K', 'tagline': 't', 'blurb': 'b',
                    'controls': [['Q', 'Up']], 'jsspeccy_machine': 128,
                    'release': {'sha256': hashlib.sha256(slug.encode()).hexdigest(), 'date': '2026-10-01'},
                    'demo': {'src': 'demo.bin', 'sha256': hashlib.sha256(tape).hexdigest(), 'milestone': 1,
                             'contains': 'Level 1 of 2.'},
                    'review': {'overall': 70, 'scores': {'overall': 70}, 'quote': {}},
                    'images': {'shots': [{'src': 'shots/shot-1.png', 'size': [256, 192], 'alt': 'a', 'caption': ''}]},
                    'credits': []}))
            (t / 'site.json').write_text(json.dumps({
                'site': {'name': 'Fixture', 'base_url': 'https://example.test/'},
                'games': [{'slug': 'shown-game', 'visible': True, 'order': 1, 'featured': True},
                          {'slug': 'secret-game', 'visible': False, 'order': 2, 'featured': False}]}))
            out = build.build(t, t / 'site.json', t / '_site')
            self.assertTrue((out / 'games/shown-game/demo.bin').is_file())
            self.assertFalse((out / 'games/secret-game').exists())
            blob = ''.join(p.read_text(errors='replace') for p in out.rglob('*')
                           if p.is_file() and p.suffix in ('.html', '.xml', '.txt'))
            self.assertNotIn('secret-game', blob)
            self.assertNotIn('Secret Game', blob)
            self.assertIn('Shown Game', blob)

    def _fixture(self, t: Path, **game):
        shutil.copytree(ROOT / 'static', t / 'static')
        shutil.copytree(ROOT / 'content', t / 'content')
        d = t / 'games' / 'fx'
        (d / 'shots').mkdir(parents=True)
        tape = b'\x13\x00fixture'
        (d / 'demo.bin').write_bytes(MAGIC + decode(MAGIC + tape, key()))
        data = {'slug': 'fx', 'title': 'Fx', 'machine': 'ZX Spectrum 128K', 'tagline': 't', 'blurb': 'b',
                'controls': [], 'release': {'sha256': '0' * 64},
                'demo': {'src': 'demo.bin', 'sha256': hashlib.sha256(tape).hexdigest(), 'contains': 'All of it.'},
                'review': {}, 'images': {'shots': [{'src': 'shots/s.png', 'size': [256, 192], 'alt': 'a'}]}}
        data.update(game)
        (d / 'game.json').write_text(json.dumps(data))
        entry = {'slug': 'fx', 'visible': True, 'order': 1, 'demo': {'sha256': data['demo'] and data['demo']['sha256'],
                                                                    'contains': 'Level 1.'}}
        return data, entry

    def _build(self, t: Path, entry):
        conf = t / 'site.json'
        conf.write_text(json.dumps({'site': {'name': 'x', 'base_url': 'https://x.test/'}, 'games': [entry]}))
        return build.build(t, conf, t / 'out')

    def test_price_in_game_text_is_refused(self):
        for field in ({'tagline': 'Lovely value at £2.99'}, {'review': {'quote': {'text': 'Only 99p!'}}}):
            with tempfile.TemporaryDirectory() as t:
                _, entry = self._fixture(Path(t), **field)
                with self.assertRaises(build.BuildError):
                    self._build(Path(t), entry)

    def test_demo_must_match_its_record(self):
        with tempfile.TemporaryDirectory() as t:
            _, entry = self._fixture(Path(t))
            out = self._build(Path(t), entry)
            self.assertIn('Level 1.', (out / 'games/fx/index.html').read_text())    # site.json's note wins
            entry['demo']['sha256'] = 'f' * 64
            with self.assertRaises(build.BuildError):
                self._build(Path(t), entry)
            (Path(t) / 'games/fx/demo.bin').write_bytes(MAGIC + b'\x00' * 9)
            entry['demo'] = {'sha256': json.loads((Path(t) / 'games/fx/game.json').read_text())['demo']['sha256']}
            with self.assertRaises(build.BuildError):                              # does not decode to it
                self._build(Path(t), entry)

    def test_null_demo_shows_coming_soon(self):
        with tempfile.TemporaryDirectory() as t:
            _, entry = self._fixture(Path(t))
            entry['demo'] = None
            out = self._build(Path(t), entry)
            page = (out / 'games/fx/index.html').read_text()
            self.assertIn('Demo coming soon', page)
            self.assertNotIn('Play the demo', page)
            self.assertFalse((out / 'games/fx/demo.bin').exists())
            self.assertNotIn('Play the demo', (out / 'index.html').read_text())

    def test_touch_key_not_in_controls_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            _, entry = self._fixture(Path(t), controls=[['O / P', 'Left / right'], ['SPACE', 'Fire']])
            entry['touch'] = {'dpad': {'left': 'O', 'right': 'P'}, 'buttons': [{'keys': 'SPACE', 'label': 'Fire'}]}
            out = self._build(Path(t), entry)
            self.assertIn('data-keys="SPACE"', (out / 'games/fx/index.html').read_text())
            entry['touch']['buttons'].append({'keys': '2', 'label': 'Keyboard'})
            with self.assertRaises(build.BuildError):
                self._build(Path(t), entry)

    def test_bad_config_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            conf = Path(t) / 'site.json'
            conf.write_text(json.dumps({'site': {'name': 'x', 'base_url': 'https://x.test/'},
                                        'games': [{'slug': 'nope', 'visible': True, 'order': 1}]}))
            with self.assertRaises(build.BuildError):
                build.build(ROOT, conf, Path(t) / 'out')


if __name__ == '__main__':
    unittest.main()
