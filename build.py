#!/usr/bin/env python3
"""Build the Dalex Software website into _site/ (Python 3 standard library only).

    python3 build.py [--config site.json] [--out _site]

Reads site.json (which games exist and which are shown), games/<slug>/game.json (written by the
toolkit's zx-website skill), content/about.html, static/ (with the studio film in static/media/) and
content/studio.html and the articles (content/articles/articles.json and one HTML fragment each, D-29, D-30; the
Studio's Learn more, D-33). Only
games with "visible": true are
built into any page, the sitemap or the feed, and only their files are copied to the output, so a
hidden game is not deployed at all. The output is deterministic: the same inputs give the same bytes.

Only the free demo is played and nothing is downloadable (D-16): a game's demo is games/<slug>/demo.bin,
the demo tape obfuscated with DEMO_KEY from static/assets/player.js (D-18), decoded in the browser and
checked here against the sha256 recorded in site.json and game.json. No tape, review PDF or price-bearing
kit image (inlay, advert, poster) is copied, and no page may show a price (D-19).
"""
import argparse, hashlib, html, json, re, shutil, sys
from html.parser import HTMLParser
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
import podcast  # Dalex After Hours: pages and feed (D-31)

ROOT = Path(__file__).resolve().parent
# The only game files deployed: the cover, screen shots, licences and the obfuscated demo (D-16, D-19).
GAME_FILES = re.compile(r'^(cover\.jpg|shots/[\w.-]+\.png|licenses/[^/]+)$')
DEMO_FILE = 'demo.bin'
DEMO_MAGIC = b'DLXDEMO1'
NO_PRICE = 'Price to be confirmed'
# A price in built text: £2.99, £ 3, $5, €4, 99p, 7.95p, 3 pence, 2 quid, 5 pounds, 3/6d (D-19).
PRICE_RE = re.compile(r'[£$€]\s?\d|(?<![\w.#-])\d+(?:\.\d+)?\s?p\b(?!x)|\b\d+(?:\.\d+)?\s?(?:pence|quid|pounds?)\b'
                      r'|\b\d+/\d+d\b|&pound;', re.I)
CURRENT = ' aria-current="page"'
LAZY = ' loading="lazy"'
SCORE_NAMES = [('presentation', 'Presentation'), ('graphics', 'Graphics'), ('sound', 'Sound'),
               ('playability', 'Playability'), ('addictive_qualities', 'Addictive qualities')]


class BuildError(RuntimeError):
    pass


def e(s) -> str:
    return html.escape('' if s is None else str(s), quote=True)


# ------------------------------------------------------------------ loading

def load(root: Path, config: Path):
    cfg = json.loads(config.read_text(encoding='utf-8'))
    site = cfg.get('site') or {}
    if not site.get('base_url', '').endswith('/'):
        raise BuildError('site.base_url must be an absolute URL ending in /')
    entries, seen = [], set()
    for g in cfg.get('games') or []:
        slug = g.get('slug')
        if not slug or slug in seen:
            raise BuildError(f'site.json: missing or duplicate slug {slug!r}')
        seen.add(slug)
        if not isinstance(g.get('visible'), bool):
            raise BuildError(f'site.json: {slug}: "visible" must be true or false')
        if not isinstance(g.get('order'), int):
            raise BuildError(f'site.json: {slug}: "order" must be a whole number')
        gj = root / 'games' / slug / 'game.json'
        if not gj.is_file():
            raise BuildError(f'site.json lists {slug} but games/{slug}/game.json is missing '
                             '(publish it with the zx-website skill)')
        data = json.loads(gj.read_text(encoding='utf-8'))
        if data.get('slug') != slug:
            raise BuildError(f'games/{slug}/game.json has slug {data.get("slug")!r}')
        if g.get('blurb'):
            data['blurb'] = g['blurb']
        data.pop('price', None)                      # prices are never shown (D-19)
        data['_demo'] = demo_of(root, slug, g, data)
        data['_touch'] = touch_of(slug, g, data)    # checked now, shown only with a demo
        data['_entry'] = g
        if g['visible']:
            check_no_price(slug, data)
        entries.append(data)
    visible = sorted((d for d in entries if d['_entry']['visible']),
                     key=lambda d: (d['_entry']['order'], d['slug']))
    featured = [d for d in visible if d['_entry'].get('featured')]
    if len(featured) > 1:
        raise BuildError('site.json: more than one visible game is featured: '
                         + ', '.join(d['slug'] for d in featured))
    return site, visible, (featured[0] if featured else (visible[0] if visible else None))


# ------------------------------------------------------------------ demo tapes

def demo_key(root: Path) -> str:
    """The demo obfuscation key, read from the one place it lives: static/assets/player.js."""
    js = (Path(root) / 'static' / 'assets' / 'player.js').read_text(encoding='utf-8')
    m = re.search(r"const DEMO_KEY = '([0-9a-f]{16,})';", js)
    if not m:
        raise BuildError('static/assets/player.js has no DEMO_KEY')
    return m.group(1)


def demo_xor(data: bytes, key: str) -> bytes:
    """XOR with an xorshift32 keystream seeded by FNV-1a of the key; the same call encodes and decodes.
    player.js does the same in the browser (D-18). A deterrent against casual copying, not protection."""
    h = 0x811C9DC5
    for c in key.encode('ascii'):
        h = ((h ^ c) * 0x01000193) & 0xFFFFFFFF
    s = h or 1
    out = bytearray(len(data))
    for i, b in enumerate(data):
        s ^= (s << 13) & 0xFFFFFFFF
        s ^= s >> 17
        s ^= (s << 5) & 0xFFFFFFFF
        out[i] = b ^ (s >> 24)
    return bytes(out)


def decode_demo(blob: bytes, key: str) -> bytes:
    if not blob.startswith(DEMO_MAGIC):
        raise BuildError('demo.bin does not start with the demo header')
    return demo_xor(blob[len(DEMO_MAGIC):], key)


def demo_of(root: Path, slug: str, entry: dict, data: dict):
    """The game's playable demo as {'sha256', 'contains', 'milestone'}, or None for "Demo coming soon".
    site.json "demo": null switches it off; otherwise game.json's demo must be published, decode to the
    recorded sha256, and agree with site.json's."""
    if 'demo' in entry and entry['demo'] is None:
        return None
    gd, sd = data.get('demo'), entry.get('demo')
    if not gd:
        if sd:
            raise BuildError(f'site.json: {slug}: has a demo but games/{slug}/game.json has none '
                             '(publish it with the zx-website skill)')
        return None
    if sd and str(sd.get('sha256', '')).lower() != str(gd.get('sha256', '')).lower():
        raise BuildError(f'site.json: {slug}: demo sha256 {str(sd.get("sha256"))[:8]} differs from '
                         f'games/{slug}/game.json {str(gd.get("sha256"))[:8]}')
    f = Path(root) / 'games' / slug / DEMO_FILE
    if gd.get('src') != DEMO_FILE or not f.is_file():
        raise BuildError(f'games/{slug}/{DEMO_FILE} is missing')
    tape = decode_demo(f.read_bytes(), demo_key(root))
    if hashlib.sha256(tape).hexdigest() != str(gd.get('sha256', '')).lower():
        raise BuildError(f'games/{slug}/{DEMO_FILE} does not decode to the recorded demo sha256')
    return {'sha256': gd['sha256'], 'milestone': gd.get('milestone'),
            'contains': (sd or {}).get('contains') or gd.get('contains') or ''}


# ------------------------------------------------------------------ touch controls (D-22)

TOUCH_DIRS = ('up', 'down', 'left', 'right')
_KEY_TOKEN = re.compile(r'^(?:[A-Z0-9]|SPACE|ENTER)$')


def control_keys(controls) -> set:
    """The Spectrum keys a game's controls list names: "Q / A / O / P" -> Q A O P, "Q (paused)" -> Q,
    "O and P in turn" -> O P, "SPACE" -> SPACE; descriptions such as "Two keys together" name none."""
    keys = set()
    for k, _v in controls or []:
        text = re.sub(r'\([^)]*\)', ' ', str(k or '')).upper()
        for tok in re.split(r'[\s/,+]+|\bAND\b|\bOR\b', text):
            if _KEY_TOKEN.match(tok.strip()):
                keys.add(tok.strip())
    return keys


def touch_of(slug: str, entry: dict, data: dict):
    """The game's on-screen controls from site.json "touch": {"dpad": {dir: key}, "diagonals": bool,
    "buttons": [{"keys": "SPACE", "label": "Fire"}]}, or None. Every key must be one the game's own
    controls list names: the pad never invents a control."""
    t = entry.get('touch')
    if not t:
        return None
    allowed = control_keys(data.get('controls'))
    dpad = {d: str(k).upper() for d, k in (t.get('dpad') or {}).items()}
    bad = [d for d in dpad if d not in TOUCH_DIRS]
    if bad:
        raise BuildError(f'site.json: {slug}: touch dpad has unknown directions {bad}')
    buttons = []
    for b in t.get('buttons') or []:
        keys = str(b.get('keys', '')).upper().split()
        if not keys or not b.get('label'):
            raise BuildError(f'site.json: {slug}: every touch button needs "keys" and a "label"')
        buttons.append({'keys': keys, 'label': str(b['label'])})
    used = set(dpad.values()) | {k for b in buttons for k in b['keys']}
    extra = sorted(used - allowed)
    if extra:
        raise BuildError(f'site.json: {slug}: touch keys {extra} are not in the game\'s controls '
                         f'({" ".join(sorted(allowed))})')
    return {'dpad': dpad, 'diagonals': bool(t.get('diagonals')), 'buttons': buttons}


def pad_html(touch, controls) -> str:
    if not touch:
        return ''
    say = {}
    for k, v in controls or []:
        ks = control_keys([[k, v]])
        if len(ks) == 1:                 # "Walk up / down / left / right" describes four keys: say none
            say.setdefault(ks.pop(), v)
    arrow = {'up': '&#9650;', 'down': '&#9660;', 'left': '&#9664;', 'right': '&#9654;'}
    dirs = ''.join(
        f'<button type="button" class="dir {d}" data-dir="{d}" data-keys="{e(k)}" '
        f'aria-label="{e(d.capitalize())}: key {e(k)}{(", " + e(say[k])) if say.get(k) else ""}">'
        f'<span aria-hidden="true">{arrow[d]}</span><small aria-hidden="true">{e(k)}</small></button>'
        for d, k in ((d, touch['dpad'].get(d)) for d in TOUCH_DIRS) if k)
    dpad = (f'<div class="dpad{" eight" if touch["diagonals"] else ""}" data-diagonals="{str(touch["diagonals"]).lower()}" '
            f'role="group" aria-label="Direction pad{" (slide to a corner for a diagonal)" if touch["diagonals"] else ""}">{dirs}</div>'
            if dirs else '')
    btns = ''.join(
        f'<button type="button" class="pad-btn{" main" if i == 0 else ""}" data-keys="{e(" ".join(b["keys"]))}" '
        f'aria-label="{e(b["label"])}: key {e(" and ".join(b["keys"]))}">'
        f'<span aria-hidden="true">{e(b["label"])}</span><small aria-hidden="true">{e(" ".join(b["keys"]))}</small></button>'
        for i, b in enumerate(touch['buttons']))
    return (f'\n    <div id="pad" class="pad" role="group" aria-label="Touch controls" hidden>{dpad}'
            f'<div class="pad-actions" role="group" aria-label="Buttons">{btns}</div></div>')


def check_no_price(slug: str, data: dict):
    """Refuse a game whose shown text states a price; the zx-website skill cuts such sentences first."""
    rev = data.get('review') or {}
    texts = [data.get('title'), data.get('tagline'), data.get('blurb'), rev.get('verdict'), rev.get('award'),
             (rev.get('quote') or {}).get('text'), ((data.get('_demo') or {}).get('contains'))]
    texts += [s.get('caption') for s in (data.get('images') or {}).get('shots') or []]
    for t in texts:
        if t and PRICE_RE.search(str(t)):
            raise BuildError(f'games/{slug}/game.json: text states a price ({t!r}); republish with the zx-website skill')


# ------------------------------------------------------------------ page chrome

def nice_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ''
    return f'{d.day} {d.strftime("%B")} {d.year}'


# The picture a page shows when it is shared (Open Graph, D-36), as (path below the site root, alt, width, height).
DEFAULT_IMAGE = ('media/studio-documentary-poster.jpg', 'A frame from the studio film: the production room in pixel '
                 'art, the team at their desks around the milestone board', 1280, 960)


def ld_json(*things) -> str:
    """schema.org structured data, one <script type="application/ld+json"> each (D-36). <, > and & are escaped so
    the JSON can never close the script element."""
    out = ''
    for t in things:
        s = json.dumps({'@context': 'https://schema.org', **t}, ensure_ascii=False, separators=(',', ':'))
        s = s.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
        out += f'<script type="application/ld+json">{s}</script>\n'
    return out


def publisher(site) -> dict:
    return {'@type': 'Organization', 'name': site['name'], 'url': site['base_url'],
            'logo': site['base_url'] + 'assets/dalex-logo.svg'}


def breadcrumbs(site, *trail) -> dict:
    """BreadcrumbList for (name, path below the site root) pairs, starting from the home page."""
    items = [(site['name'], '')] + list(trail)
    return {'@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i, 'name': n, 'item': site['base_url'] + u}
        for i, (n, u) in enumerate(items, 1)]}


def social(site, *, path, title, description, image, og_type) -> str:
    """Open Graph and card tags, so a shared link shows a title, summary and picture (D-36)."""
    src, alt, w, h = image or DEFAULT_IMAGE
    tags = [('og:type', og_type), ('og:site_name', site['name']), ('og:locale', 'en_GB'), ('og:title', title),
            ('og:description', description), ('og:url', site['base_url'] + path),
            ('og:image', site['base_url'] + src), ('og:image:width', w), ('og:image:height', h), ('og:image:alt', alt)]
    return (''.join(f'<meta property="{k}" content="{e(v)}">\n' for k, v in tags)
            + '<meta name="twitter:card" content="summary_large_image">\n')


def page(site, *, root, path, title, body, description='', current='', extra_head='', scripts='',
         head_title='', image=None, og_type='website', ld=''):
    """A whole HTML page. root is the relative prefix back to the site root ('' / '../' / ...);
    path is this page's path below the site root, for the canonical URL. head_title, when given, is the <title>
    in place of 'title · site name' (D-36); image is the shared picture (see DEFAULT_IMAGE); ld is structured data."""
    full_title = head_title or (f'{title} · {site["name"]}' if title != site['name'] else title)
    description = description or site.get('description', '')
    nav = [('', 'Home', 'home'), ('games/', 'Games', 'games'), ('studio/', 'Studio', 'studio'), ('book/', 'Book', 'book'),
           ('podcast/', 'Podcast', 'podcast'), ('about/', 'About', 'about')]
    links = ''.join(
        f'<li><a href="{root}{href}"{CURRENT if key == current else ""}>{label}</a></li>'
        for href, label, key in nav)
    return f'''<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(description)}">
<meta name="color-scheme" content="dark light">
<link rel="canonical" href="{e(site['base_url'] + path)}">
<link rel="icon" href="{root}favicon.ico" sizes="any">
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="icon" href="{root}favicon.png" type="image/png">
<link rel="alternate" type="application/atom+xml" title="{e(site['name'])} releases" href="{root}feed.xml">
<link rel="stylesheet" href="{root}assets/site.css">
{social(site, path=path, title=title, description=description, image=image, og_type=og_type)}{ld}{extra_head}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="masthead">
  <div class="wrap masthead-in">
    <a class="brand" href="{root or './'}"><img src="{root}assets/dalex-logo.svg" width="176" height="64" alt="Dalex Software"></a>
    <nav aria-label="Main"><ul>{links}</ul></nav>
  </div>
  <div class="rainbow" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
</header>
<main id="main" class="wrap">
{body}
</main>
<footer class="foot">
  <div class="wrap">
    <p><img src="{root}assets/dalex-mark.svg" width="48" height="16" alt=""> <strong>{e(site['name'])}</strong>. {e(site.get('footer', ''))}</p>
    <p>Play in the browser with <a href="https://jsspeccy.zxdemo.org/">JSSpeccy</a> by Matt Westcott,
    used under the <a href="{root}jsspeccy/COPYING">GPL-3.0</a> (<a href="{root}jsspeccy/README.md">source and changes</a>).
    No cookies, no tracking. <a href="{root}feed.xml">Releases feed</a>.</p>
  </div>
</footer>
{scripts}</body>
</html>
'''


def score_badge(game, small=False):
    o = (game.get('review') or {}).get('overall')
    if o is None:
        return ''
    cls = 'badge small' if small else 'badge'
    return (f'<span class="{cls}" title="INK &amp; PAPER Overall rating">'
            f'<span class="badge-num">{e(o)}%</span><span class="badge-lbl">INK &amp; PAPER</span></span>')


def cover_img(game, root_to_game, cls='', lazy=True, sizes=''):
    c = (game.get('images') or {}).get('cover')
    if not c:
        s = game['images']['shots'][0]
        return (f'<img class="{cls} px" src="{root_to_game}{e(s["src"])}" width="{s["size"][0]}" '
                f'height="{s["size"][1]}" alt="{e(s["alt"])}"{LAZY if lazy else ""}>')
    return (f'<img class="{cls}" src="{root_to_game}{e(c["src"])}" width="{c["size"][0]}" '
            f'height="{c["size"][1]}" alt="{e(c["alt"])}"{LAZY if lazy else ""}>')


def card(game, root):
    g = f'{root}games/{game["slug"]}/'
    return f'''<li class="card">
  <a class="card-link" href="{g}">
    <div class="card-art">{cover_img(game, g)}</div>
    <div class="card-body">
      <h3>{e(game["title"])}</h3>
      <p class="meta"><span>{e(game["machine"])}</span><span>{NO_PRICE}</span>{'<span>Free demo</span>' if game['_demo'] else ''}</p>
      <p>{e(game.get("tagline", ""))}</p>
    </div>
  </a>
  {score_badge(game, small=True)}
</li>'''


# ------------------------------------------------------------------ pages

# The music video on the home page (D-41): played from YouTube only when the visitor presses play
MUSIC_VIDEO = {'youtube': '-_4-1W9eWcM', 'making_of': 'g5PJrlRBw9k', 'title': 'Press Play on Tape',
               'poster': 'assets/home/press-play-on-tape.jpg'}


def home(site, games, featured, episodes=()):
    """The front door: what Dalex is, the new release, the shelf of games, and a way into each section (D-35)."""
    root = ''
    hero = ''
    if featured:
        g = f'games/{featured["slug"]}/'
        rel = featured.get('release') or {}
        q = (featured.get('review') or {}).get('quote') or {}
        quote = (f'<blockquote><p>&ldquo;{e(q["text"])}&rdquo;</p><footer>{e(q.get("reviewer", ""))}, '
                 f'INK &amp; PAPER</footer></blockquote>' if q.get('text') else '')
        hero = f'''<section class="hero" aria-labelledby="hero-title">
  <div class="hero-art"><a href="{g}" tabindex="-1">{cover_img(featured, g, lazy=False)}</a></div>
  <div class="hero-copy">
    <p class="kicker">New release{(' · ' + e(nice_date(rel.get('date', '')))) if rel.get('date') else ''}</p>
    <h2 id="hero-title" class="hero-title">{e(featured["title"])}</h2>
    <p class="lede">{e(featured.get("tagline", ""))}</p>
    <p class="meta"><span>{e(featured["machine"])}</span><span>{NO_PRICE}</span></p>
    {score_badge(featured)}
    {quote}
    <p class="actions">{(f'<a class="button primary" href="{g}#play-now">Play the demo</a> ') if featured['_demo'] else ''}<a class="button{'' if featured['_demo'] else ' primary'}" href="{g}">About the game</a></p>
  </div>
</section>'''
    shelf = '\n'.join(f'''  <li><a href="games/{e(x["slug"])}/">{cover_img(x, f'games/{x["slug"]}/', cls='shelf-art')}<span>{e(x["title"])}</span></a></li>'''
                      for x in games)
    latest = episodes[0] if episodes else None
    listen = (f'Latest: episode {e(latest["number"])}, <em>{e(latest["title"])}</em>.' if latest
              else 'Bev and Gareth talk to the team about how the games were made.')
    team = ''.join(f'<img class="px" src="assets/people/{who}.png" width="48" height="96" alt=""{LAZY}>'
                   for who in ('malcolm', 'mo', 'gareth', 'hyunjoo', 'dez'))
    mv = MUSIC_VIDEO
    music = f'''<section class="music" aria-labelledby="music-title">
  <div class="video-embed" data-youtube="{e(mv['youtube'])}" data-title="{e(mv['title'])}: the music video">
    <a href="https://www.youtube.com/watch?v={e(mv['youtube'])}"><img src="{e(mv['poster'])}" width="960" height="540" alt="Dez and Hyun-joo at the microphone in the courtyard, the whole team clapping behind them"{LAZY}><span class="play">Play the video</span></a>
  </div>
  <div>
    <p class="kicker">Music video</p>
    <h2 id="music-title">{e(mv['title'])}</h2>
    <p class="lede">Dez and Hyun-joo sing the studio's own song, and the whole team joins in. Every game you see on screen is a real Dalex game.</p>
    <p class="small">Playing it loads the video from YouTube. <a href="https://www.youtube.com/watch?v={e(mv['making_of'])}">How it was made, with no camera: Hyun-joo explains</a></p>
  </div>
</section>'''
    body = f'''<section class="welcome" aria-labelledby="welcome-title">
  <p class="kicker">A Manchester software house</p>
  <h1 id="welcome-title" class="welcome-title">New games for the ZX Spectrum, and how to make your own</h1>
  <p class="lede">{e(site.get("intro", ""))}</p>
  <p class="actions"><a class="button primary" href="games/">Play the games</a> <a class="button" href="book/">Learn how they were made</a></p>
</section>
{hero}
<section aria-labelledby="shelf-title">
  <h2 id="shelf-title">The games</h2>
  <ul class="shelf">
{shelf}
  </ul>
  <p><a href="games/">All the games, with their free demos and reviews</a></p>
</section>
{music}
<section aria-labelledby="doors-title">
  <h2 id="doors-title">How they are made</h2>
  <ul class="doors">
  <li class="door"><a href="studio/"><img src="assets/home/studio.jpg" width="480" height="360" alt="A frame from the studio film: the production room in pixel art, the team at their desks around the milestone board"{LAZY}><span class="kicker">Studio</span><strong>Watch the studio at work</strong><span>A five-minute film of a game going from the first idea to the magazine review.</span></a></li>
  <li class="door"><a href="book/"><img src="{BOOK_COVER}" width="300" height="450" alt="The cover of Machine Code Mayhem"{LAZY}><span class="kicker">Book</span><strong>Machine Code Mayhem</strong><span>Learn to write Spectrum games in Z80 assembly from these six complete games, then make your own.</span></a></li>
  <li class="door"><a href="podcast/"><img src="assets/home/podcast.jpg" width="360" height="360" alt="The cover of Dalex After Hours"{LAZY}><span class="kicker">Podcast · new on Thursdays</span><strong>Dalex After Hours</strong><span>{listen}</span></a></li>
  <li class="door"><a href="about/"><span class="team">{team}</span><span class="kicker">About</span><strong>Meet the team</strong><span>The people who make the games, from commissioning to the review, and the cat.</span></a></li>
  </ul>
</section>'''
    ld = ld_json({'@type': 'WebSite', 'name': site['name'], 'url': site['base_url'],
                  'description': site.get('description', ''), 'inLanguage': 'en-GB'}, publisher(site))
    return page(site, root=root, path='', title=site['name'], body=body, current='home', ld=ld,
                scripts='<script src="assets/video-embed.js" defer></script>\n',
                head_title=f'{site["name"]}: new ZX Spectrum games to play in your browser')


def games_index(site, games):
    root = '../'
    rows = []
    for x in games:
        g = f'{x["slug"]}/'
        rel = x.get('release') or {}
        rows.append(f'''<li class="row">
  <a class="row-art" href="{g}" tabindex="-1">{cover_img(x, g)}</a>
  <div>
    <h2><a href="{g}">{e(x["title"])}</a></h2>
    <p class="meta"><span>{e(x["machine"])}</span><span>{NO_PRICE}</span>{('<span>Released ' + e(nice_date(rel.get("date"))) + '</span>') if rel.get("date") else ''}</p>
    <p>{e(x.get("blurb", ""))}</p>
    <p class="actions">{(f'<a class="button primary" href="{g}#play-now">Play the demo</a>') if x['_demo'] else '<span class="soon">Demo coming soon</span>'}</p>
  </div>
  {score_badge(x)}
</li>''')
    body = f'''<h1>Games</h1>
<p class="intro">Every Dalex release. Free demos play in your browser; more are on the way.</p>
<ul class="rows">{''.join(rows)}</ul>'''
    ld = ld_json(breadcrumbs(site, ('Games', 'games/')), {
        '@type': 'ItemList', 'itemListElement': [
            {'@type': 'ListItem', 'position': i, 'url': f'{site["base_url"]}games/{x["slug"]}/', 'name': x['title']}
            for i, x in enumerate(games, 1)]})
    return page(site, root=root, path='games/', title='Games', body=body, current='games', ld=ld,
                head_title=f'ZX Spectrum games · {site["name"]}',
                description='All Dalex Software games for the ZX Spectrum, each with a free demo to play in your '
                            'browser.' if any(x['_demo'] for x in games) else
                            'All Dalex Software games for the ZX Spectrum.')


def game_page(site, game):
    root = '../../'
    imgs = game.get('images') or {}
    rel = game.get('release') or {}
    rev = game.get('review') or {}
    demo = game['_demo']
    cover = imgs.get('cover')
    cover_style = (f' style="background-image:url(\'{e(cover["src"])}\')"' if cover else '')
    controls = ''.join(f'<div><dt>{"<kbd>" + e(k) + "</kbd>" if k else ""}</dt><dd>{e(v)}</dd></div>'
                       for k, v in game.get('controls') or [])
    shots = ''.join(f'''<figure><img class="px" src="{e(s["src"])}" width="{s["size"][0]}" height="{s["size"][1]}" alt="{e(s["alt"])}" loading="lazy">{('<figcaption>' + e(s["caption"]) + '</figcaption>') if s.get("caption") else ''}</figure>'''
                    for s in imgs.get('shots') or [])
    scores = rev.get('scores') or {}
    score_rows = ''.join(
        f'<tr><th scope="row">{label}</th><td><span class="bar" style="--pct:{int(scores[k])}%"></span></td>'
        f'<td class="num">{int(scores[k])}%</td></tr>'
        for k, label in SCORE_NAMES if isinstance(scores.get(k), (int, float)))
    q = rev.get('quote') or {}
    quote = (f'<blockquote><p>&ldquo;{e(q["text"])}&rdquo;</p><footer>{e(q.get("reviewer", ""))}</footer></blockquote>'
             if q.get('text') else '')
    award = f'<p class="award">{e(rev["award"])}</p>' if rev.get('award') else ''
    review = ''
    if rev.get('overall') is not None:
        review = f'''<section class="panel review" aria-labelledby="review-h">
  <h2 id="review-h">What INK &amp; PAPER said</h2>
  <div class="review-grid">
    <div class="overall"><span class="overall-num">{e(rev["overall"])}%</span><span>Overall</span>{award}</div>
    <div>
      {quote}
      {('<p class="verdict">' + e(rev["verdict"]) + '</p>') if rev.get("verdict") else ''}
      <table class="scores"><caption>Ratings</caption><tbody>{score_rows}</tbody></table>
    </div>
  </div>
</section>'''
    credits = ''.join(f'<div><dt>{e(c["role"])}</dt><dd>{e(c["name"])}</dd></div>' for c in game.get('credits') or [])
    igc = game.get('in_game_credits') or []
    igc_html = (f'<div class="screen-credits"><p class="kicker">From the game&rsquo;s credits page</p><pre>{e(chr(10).join(igc))}</pre></div>'
                if igc else '')
    lic = ''.join(f'<li><a href="{e(x["src"])}">{e(x["name"])}</a></li>' for x in game.get('licenses') or [])
    lic_html = f'<p class="kicker">Licences</p><ul class="plain">{lic}</ul>' if lic else ''
    machine_n = int(game.get('jsspeccy_machine') or 128)
    contains = (f'<p class="demo-contains"><strong>The demo:</strong> {e(demo["contains"])}</p>'
                if demo and demo.get('contains') else '')
    if demo:
        touch = game.get('_touch')
        pad = pad_html(touch, game.get('controls'))
        pad_toggle = ('\n    <button id="pad-toggle" type="button" class="button" aria-controls="pad" aria-pressed="false">'
                      'Show touch controls</button>') if touch else ''
        keyboard_line = ('Play with a keyboard, or with the on-screen controls on a phone or tablet.' if touch
                         else 'You will need a keyboard.')
        earlier = ('The demo is an earlier milestone build of the game, so it may differ from the finished tape.'
                   if demo.get('milestone') else
                   'The demo is the first level of the game; the finished tape has more.')
        player = f'''<section id="play-now" class="player" aria-labelledby="play-h">
  <h2 id="play-h" class="sr-only">Play the {e(game["title"])} demo</h2>
  <div id="stage" class="stage">
  <div class="screen">
    <div id="emulator" tabindex="0" role="application" aria-label="The {e(game["title"])} demo running on an emulated ZX Spectrum. Click here, then use the keys listed under Controls. Press Tab to leave the game."
      data-demo="{DEMO_FILE}" data-machine="{machine_n}" data-title="{e(game["title"])}" data-jsspeccy="{root}jsspeccy/jsspeccy.js"></div>
    <div id="cover" class="cover"{cover_style}>
      <div class="cover-in">
        <p>{e(game.get("tagline", ""))}</p>
        <button id="play" type="button" class="button primary big">&#9654; Play the demo</button>
        <p class="small">Free. Loads the demo in a {machine_n}K Spectrum, with sound. {keyboard_line}</p>
      </div>
    </div>
  </div>{pad}
  </div>
  <div class="toolbar">
    <button id="pause" type="button" class="button" disabled>Pause</button>
    <button id="fullscreen" type="button" class="button" disabled>Full screen</button>
    <button id="restart" type="button" class="button" disabled>Restart</button>{pad_toggle}
  </div>
  {contains}
  <p class="small">{earlier}</p>
  <p id="status" role="status">Press Play to load the demo. Nothing plays until you do.</p>
  <noscript><p>The in-browser Spectrum needs JavaScript.</p></noscript>
</section>'''
        scripts = f'<script src="{root}assets/player.js" defer></script>\n'
    else:
        player = f'''<section id="play-now" class="player" aria-labelledby="play-h">
  <h2 id="play-h" class="sr-only">{e(game["title"])} demo</h2>
  <div class="screen">
    <div class="cover"{cover_style}>
      <div class="cover-in">
        <p>{e(game.get("tagline", ""))}</p>
        <p class="soon big">Demo coming soon</p>
        <p class="small">A free demo to play in your browser is on its way. Meanwhile, see the screen shots and the review below.</p>
      </div>
    </div>
  </div>
</section>'''
        scripts = ''
    body = f'''<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Games</a> <span aria-hidden="true">/</span> <span aria-current="page">{e(game["title"])}</span></nav>
<div class="title-row">
  <div>
    <h1>{e(game["title"])}</h1>
    <p class="meta"><span>{e(game["machine"])}</span><span>{NO_PRICE}</span>{('<span>Released ' + e(nice_date(rel.get("date"))) + '</span>') if rel.get("date") else ''}</p>
  </div>
  {score_badge(game)}
</div>
{player}
<div class="two-col">
  <section aria-labelledby="about-h">
    <h2 id="about-h">The game</h2>
    <p class="lede">{e(game.get("blurb", ""))}</p>
  </section>
  <section class="panel" aria-labelledby="controls-h">
    <h2 id="controls-h">Controls</h2>
    <dl class="keys">{controls}</dl>
  </section>
</div>
<section aria-labelledby="shots-h">
  <h2 id="shots-h">Screen shots</h2>
  <div class="gallery">{shots}</div>
</section>
{review}
<div class="two-col">
  <section class="panel tape" aria-labelledby="tape-h">
    <h2 id="tape-h">The tape</h2>
    <p>The full {e(game["title"])} tape for the {e(game["machine"])}: {NO_PRICE.lower()}.</p>
    <p>{'The free demo above plays in your browser.' if demo else 'A free demo to play in your browser is coming soon.'}</p>
  </section>
  <section class="panel" aria-labelledby="credits-h">
    <h2 id="credits-h">Credits</h2>
    <dl class="credits">{credits}</dl>
    {igc_html}
    {lic_html}
  </section>
</div>'''
    path = f'games/{game["slug"]}/'
    art = cover or (imgs.get('shots') or [None])[0]
    image = (path + art['src'], art['alt'], art['size'][0], art['size'][1]) if art else None
    description = (f'{game["title"]} for the {game["machine"]}: {game.get("tagline") or ""}'
                   + (' Play the free demo in your browser.' if demo else '')).strip()
    vg = {'@type': 'VideoGame', 'name': game['title'], 'url': site['base_url'] + path,
          'description': game.get('blurb') or description, 'gamePlatform': game['machine'],
          'applicationCategory': 'Game', 'operatingSystem': 'ZX Spectrum', 'inLanguage': 'en',
          'publisher': publisher(site)}
    if image:
        vg['image'] = site['base_url'] + image[0]
    if rel.get('date'):
        vg['datePublished'] = rel['date']
    shot_urls = [site['base_url'] + path + s['src'] for s in imgs.get('shots') or []]
    if shot_urls:
        vg['screenshot'] = shot_urls
    return page(site, root=root, path=path, title=game['title'], body=body, current='games',
                head_title=(f'{game["title"]}: play the free ZX Spectrum demo · {site["name"]}' if demo
                            else f'{game["title"]} for the ZX Spectrum · {site["name"]}'),
                description=description, image=image, ld=ld_json(vg, breadcrumbs(
                    site, ('Games', 'games/'), (game['title'], path))),
                scripts=scripts)


def about(site, root_dir: Path):
    frag = (root_dir / 'content' / 'about.html').read_text(encoding='utf-8')
    scripts = '<script src="../assets/people-switch.js" defer></script>\n'   # the photo switch (D-39)
    return page(site, root='../', path='about/', title='About Dalex Software', body=frag, current='about', scripts=scripts,
                ld=ld_json(breadcrumbs(site, ('About', 'about/'))),
                description='Dalex Software, a small Spectrum games house in a Manchester mill, and the people who make its games.')


BOOK_COVER = 'assets/book/machine-code-mayhem.jpg'   # the book's cover, 600 x 900
BOOK_PRICE = {'minimum': 19, 'suggested': 29}   # US dollars, as set on Leanpub (D-28); change both there and here


def book(site, root_dir: Path, games):
    """The Book: the studio's book, Machine Code Mayhem, out now on Leanpub, linking to its Leanpub page (D-26, D-27).
    A link to a game that is hidden in site.json becomes plain text, as on the Studio page."""
    root = '../'
    shown = {g['slug'] for g in games}
    frag = (root_dir / 'content' / 'book.html').read_text(encoding='utf-8')
    frag = re.sub(r'<a href="\.\./games/([a-z0-9-]+)/">(.*?)</a>',
                  lambda m: m.group(0) if m.group(1) in shown else m.group(2), frag)
    cover = f'''<figure class="book-cover">
  <img src="{root}{BOOK_COVER}" width="300" height="450" alt="Cover of Machine Code Mayhem: in a pixel-art 1987 studio at night, Gareth types at a small black computer while Hyun-joo points at the screen, Dez listens on headphones and Percy the cat sits by a stack of cassettes. By Daniel Vaughan, with the Dalex Software team.">
  <figcaption>Out now on <a href="https://leanpub.com/machinecodemayhem">Leanpub</a>.</figcaption>
</figure>'''
    p = BOOK_PRICE
    price = (f'<p class="price"><strong>You choose the price:</strong> from <strong>${p["minimum"]}</strong>, '
             f'suggested ${p["suggested"]}.</p>')
    words = (f'the minimum is ${p["minimum"]} and the suggested price ${p["suggested"]}, and anything above the '
             f'minimum is up to you.')
    body = frag.replace('<!-- cover -->', cover).replace('<!-- price -->', price).replace('<!-- price-words -->', words)
    book_ld = {'@type': 'Book', 'name': 'Machine Code Mayhem', 'url': site['base_url'] + 'book/',
               'image': site['base_url'] + BOOK_COVER, 'author': {'@type': 'Person', 'name': 'Daniel Vaughan'},
               'inLanguage': 'en-GB', 'sameAs': 'https://leanpub.com/machinecodemayhem',
               'about': 'Writing ZX Spectrum games in Z80 assembly'}
    return page(site, root=root, path='book/', title='Machine Code Mayhem', body=body, current='book',
                head_title=f'Machine Code Mayhem: write ZX Spectrum games in Z80 assembly · {site["name"]}',
                image=(BOOK_COVER, 'The cover of Machine Code Mayhem', 600, 900), og_type='book',
                ld=ld_json(book_ld, breadcrumbs(site, ('Book', 'book/'))),
                description='Machine Code Mayhem, the Dalex Software book on writing ZX Spectrum games in Z80 assembly '
                            'from six complete games. Out now on Leanpub.')


FILM = 'media/studio-documentary'   # the studio documentary's MP4, poster (-poster.jpg) and captions (.vtt)


def transcript(vtt: str) -> str:
    """The film's captions as a readable transcript: one paragraph per turn, the speaker named once."""
    turns = []
    for block in vtt.replace('\r', '').split('\n\n'):
        rows = block.strip().split('\n')
        if '-->' not in ''.join(rows[:2]):
            continue
        text = ' '.join(rows[[i for i, r in enumerate(rows) if '-->' in r][0] + 1:])
        m = re.match(r'<v ([^>]+)>(.*)', text)
        who, said = (m.group(1), m.group(2)) if m else ('', text)
        if turns and turns[-1][0] == who and who:
            turns[-1][1].append(said)
        else:
            turns.append((who, [said]))
    return '\n'.join(f'<p>{"<strong>" + e(w) + ":</strong> " if w else ""}{e(" ".join(t))}</p>' for w, t in turns)


def studio(site, root_dir: Path, games, arts=()):
    """The Studio: the documentary film of how Dalex makes its games, with captions and a transcript, and the
    articles as its Learn more section (D-33). A link to a game that is hidden in site.json becomes plain text, so a
    hidden game is never linked."""
    root = '../'
    shown = {g['slug'] for g in games}
    frag = (root_dir / 'content' / 'studio.html').read_text(encoding='utf-8')
    frag = re.sub(r'<a href="\.\./games/([a-z0-9-]+)/">(.*?)</a>',
                  lambda m: m.group(0) if m.group(1) in shown else m.group(2), frag)
    vtt = (root_dir / 'static' / (FILM + '.vtt')).read_text(encoding='utf-8')
    film = f'''<figure class="film">
  <video controls preload="none" playsinline width="1280" height="960" poster="{root}{FILM}-poster.jpg">
    <source src="{root}{FILM}.mp4" type="video/mp4">
    <track kind="captions" srclang="en" label="English" src="{root}{FILM}.vtt" default>
    <p>Your browser cannot play this film here. <a href="{root}{FILM}.mp4">Download it (MP4)</a>.</p>
  </video>
  <figcaption>How the studio works: a five-minute film recorded in the Dalex Studio. Captions are on; use the
  player&rsquo;s controls to turn them off. <a href="{root}{FILM}.mp4" download>Download the film (MP4)</a>.</figcaption>
</figure>'''
    if '<!-- learn more -->' not in frag:
        raise BuildError('content/studio.html has no <!-- learn more --> placeholder for the articles (D-33)')
    desk = ('<p class="actions"><a class="button primary" href="spec-desk/">Bring your idea to the spec desk</a></p>\n'
            if spec_desk_api(site) else '')
    body = (frag.replace('<!-- film -->', film).replace('<!-- transcript -->', transcript(vtt))
            .replace('<!-- learn more -->', desk + learn_more(arts)))
    return page(site, root=root, path='studio/', title='The Studio', body=body, current='studio',
                ld=ld_json(breadcrumbs(site, ('Studio', 'studio/'))),
                extra_head=articles_feed_link(site, root) if arts else '',
                description='A five-minute film of how Dalex Software makes its games: every role carried out by AI agents, '
                            'with people steering.')


ARTICLES = 'content/articles'   # articles.json (the metadata) and <slug>.html, one fragment per article (D-29, D-30)
WORDS_PER_MINUTE = 220
# The article fragment's whole vocabulary, shared with the INK & PAPER issue, which prints the same files as
# features (zx-media-kit build_issue.py keeps the same list): tag -> the attributes it may carry.
ARTICLE_TAGS = {'h2': {'id'}, 'h3': set(), 'p': set(), 'ul': set(), 'ol': {'class'}, 'li': set(), 'pre': set(),
                'code': set(), 'strong': set(), 'em': set(), 'span': set(), 'a': {'href'}, 'table': set(),
                'thead': set(), 'tbody': set(), 'tr': set(), 'th': {'scope'}, 'td': set(), 'aside': {'class'},
                'blockquote': {'class'}}
ARTICLE_CLASSES = {'ol': {'pipeline'}, 'aside': {'boxout'}, 'blockquote': {'pull'}}
ARTICLE_KEYS = ('slug', 'kicker', 'title', 'cover_title', 'tease', 'standfirst', 'byline', 'date', 'topics')


class _Vocabulary(HTMLParser):
    def __init__(self):
        super().__init__()
        self.bad = []

    def handle_starttag(self, tag, attrs):
        allowed = ARTICLE_TAGS.get(tag)
        if allowed is None:
            self.bad.append(f'<{tag}>')
            return
        for k, v in attrs:
            if k not in allowed or (k == 'class' and v not in ARTICLE_CLASSES.get(tag, ())):
                self.bad.append(f'<{tag} {k}="{v}">')


def check_fragment(name: str, frag: str):
    v = _Vocabulary()
    v.feed(frag)
    if v.bad:
        raise BuildError(f'{ARTICLES}/{name}: not in the article vocabulary: {", ".join(sorted(set(v.bad)))}')


def show_shown_games(frag: str, games) -> str:
    """Link only games that are shown: a link to a game hidden in site.json becomes plain text."""
    shown = {g['slug'] for g in games}
    return re.sub(r'<a href="\.\./\.\./games/([a-z0-9-]+)/">(.*?)</a>',
                  lambda m: m.group(0) if m.group(1) in shown else m.group(2), frag)


def load_articles(root_dir: Path):
    """The articles, newest first, each with its body and reading time. Refuses missing metadata or markup outside
    the shared vocabulary."""
    arts = json.loads((root_dir / ARTICLES / 'articles.json').read_text(encoding='utf-8'))
    seen = set()
    for a in arts:
        for k in ARTICLE_KEYS:
            if not a.get(k):
                raise BuildError(f'{ARTICLES}/articles.json: article {a.get("slug")!r} has no {k}')
        if a['slug'] in seen or not re.fullmatch(r'[a-z0-9-]+', a['slug']):
            raise BuildError(f'{ARTICLES}/articles.json: bad or duplicate slug {a["slug"]!r}')
        seen.add(a['slug'])
        date.fromisoformat(a['date'])
        a['body'] = (root_dir / ARTICLES / f'{a["slug"]}.html').read_text(encoding='utf-8')
        check_fragment(f'{a["slug"]}.html', a['body'])
        words = len(re.sub(r'<[^>]+>', ' ', a['standfirst'] + ' ' + a['body']).split())
        a['minutes'] = max(1, round(words / WORDS_PER_MINUTE))
    return sorted(arts, key=lambda a: (a['date'], a['slug']), reverse=True)


def article_meta(a) -> str:
    return (f'<p class="meta byline"><span>Words: {e(a["byline"])}</span>'
            f'<span><time datetime="{e(a["date"])}">{e(nice_date(a["date"]))}</time></span>'
            f'<span>{a["minutes"]} min read</span></p>')


def articles_feed_link(site, root):
    return (f'<link rel="alternate" type="application/atom+xml" title="{e(site["name"])} articles" '
            f'href="{root}studio/feed.xml">\n')


OOC = ('<p class="ooc"><strong>Out of character.</strong> Dalex Software, its staff and <em>INK &amp; PAPER</em> are '
       'fictional, and the rest of this site speaks as a 1987 studio. This feature is about the real tools and process '
       'behind the games.</p>')


def learn_more(arts):
    """The Studio page's Learn more section: the INK & PAPER features, out of character, on how the games and the
    studio are really made (D-29, D-30, D-33). There is no separate Articles section. Each shows its kicker, title and
    the magazine's tease, never the byline or standfirst: the Studio page names no real person (test_studio)."""
    if not arts:
        return ''
    items = '\n'.join(f'''  <li class="article-item">
    <p class="kicker">{e(a["kicker"])}</p>
    <h3><a href="{e(a["slug"])}/">{e(a["title"])}</a></h3>
    <p class="standfirst">{e(a["tease"])}.</p>
    <p class="meta"><span>{a["minutes"]} min read</span></p>
  </li>''' for a in arts)
    return f'''<section class="learn-more" aria-labelledby="learn-more">
<h2 id="learn-more">Learn more</h2>
<p>Features from <em>INK &amp; PAPER</em>, the Spectrum games monthly. The rest of this site stays in 1987; these step
out of character to show how the games are really made today, with AI agents, an assembler, emulators and a lot of
checks. <a href="feed.xml">Feed (Atom)</a>.</p>
<ul class="articles">
{items}
</ul>
</section>'''


def article_page(site, a, games):
    root = '../../'
    body = f'''<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Studio</a> <span aria-hidden="true">/</span> <span aria-current="page">{e(a["title"])}</span></nav>
<article class="feature">
<header class="feature-head">
  <p class="feature-mark" aria-hidden="true">INK<span>&amp;</span>PAPER</p>
  <p class="kicker">{e(a["kicker"])}</p>
  <h1>{e(a["title"])}</h1>
  <p class="standfirst">{e(a["standfirst"])}</p>
  {article_meta(a)}
  {OOC}
</header>
<div class="feature-body">
{show_shown_games(a["body"], games)}
</div>
</article>
<p class="actions"><a class="button" href="../">Back to the Studio</a></p>'''
    path = f'studio/{a["slug"]}/'
    art = {'@type': 'Article', 'headline': a['title'], 'description': a['standfirst'],
           'datePublished': a['date'], 'author': {'@type': 'Person', 'name': a['byline']},
           'publisher': publisher(site), 'mainEntityOfPage': site['base_url'] + path,
           'image': site['base_url'] + DEFAULT_IMAGE[0], 'inLanguage': 'en-GB'}
    return page(site, root=root, path=path, title=a['title'], body=body, current='studio', og_type='article',
                ld=ld_json(art, breadcrumbs(site, ('Studio', 'studio/'), (a['title'], path))),
                extra_head=articles_feed_link(site, root) + f'<meta property="article:published_time" content="{e(a["date"])}">\n',
                description=a['standfirst'])


def moved(site, *, root, path, to, title):
    """A stub at an old address (the Blog's, D-30, and the Articles section's, D-33) that sends the reader on."""
    url = site['base_url'] + to
    body = f'''<h1>{e(title)}</h1>
<p class="lede">This has moved to <a href="{root}{to}">{e(url)}</a>.</p>'''
    return page(site, root=root, path=to, title=title, body=body, current='studio',
                extra_head=f'<meta http-equiv="refresh" content="0; url={root}{to}">\n')


def articles_atom(site, arts):
    base = site['base_url']
    entries = ''.join(f'''  <entry>
    <title>{e(a["title"])}</title>
    <link href="{e(base)}studio/{e(a["slug"])}/"/>
    <id>{e(base)}articles/{e(a["slug"])}/</id>
    <updated>{e(a["date"])}T00:00:00Z</updated>
    <author><name>{e(a["byline"])}</name></author>
    <summary>{e(a["standfirst"])}</summary>
  </entry>
''' for a in arts)
    updated = arts[0]['date'] if arts else '1987-01-01'
    return f'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{e(site["name"])} articles</title>
  <link href="{e(base)}studio/"/>
  <link rel="self" href="{e(base)}studio/feed.xml"/>
  <id>{e(base)}articles/</id>
  <updated>{e(updated)}T00:00:00Z</updated>
{entries}</feed>
'''


def not_found(site):
    base = urlsplit(site['base_url']).path or '/'
    body = f'''<h1>R Tape loading error, 0:1</h1>
<p class="lede">That page isn&rsquo;t on this tape. Rewind and try again.</p>
<p class="actions"><a class="button primary" href="{e(base)}">Home</a> <a class="button" href="{e(base)}games/">All the games</a></p>'''
    return page(site, root=base, path='404.html', title='Page not found', body=body)


def sitemap(site, games, arts=(), episodes=()):
    urls = [('', None), ('games/', None), ('studio/', None), ('book/', None), ('about/', None)]
    urls += [('studio/spec-desk/', None)] if spec_desk_api(site) else []
    urls += [(f'studio/{a["slug"]}/', a['date']) for a in arts]
    urls += [('podcast/', None)] + [(f'podcast/{ep["slug"]}/', ep['date']) for ep in episodes]
    urls += [(f'games/{g["slug"]}/', (g.get('release') or {}).get('date')) for g in games]
    items = ''.join(f'  <url><loc>{e(site["base_url"] + u)}</loc>'
                    + (f'<lastmod>{e(d)}</lastmod>' if d else '') + '</url>\n' for u, d in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + items + '</urlset>\n')


def feed(site, games):
    dated = sorted(games, key=lambda g: ((g.get('release') or {}).get('date') or '', g['slug']), reverse=True)
    updated = next(((g.get('release') or {}).get('date') for g in dated if (g.get('release') or {}).get('date')),
                   '1987-01-01')
    entries = ''.join(f'''  <entry>
    <title>{e(g["title"])}</title>
    <link href="{e(site["base_url"])}games/{e(g["slug"])}/"/>
    <id>{e(site["base_url"])}games/{e(g["slug"])}/</id>
    <updated>{e((g.get("release") or {}).get("date") or updated)}T00:00:00Z</updated>
    <summary>{e(g.get("tagline", ""))}</summary>
  </entry>
''' for g in dated)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{e(site["name"])} releases</title>
  <link href="{e(site["base_url"])}"/>
  <link rel="self" href="{e(site["base_url"])}feed.xml"/>
  <id>{e(site["base_url"])}</id>
  <updated>{e(updated)}T00:00:00Z</updated>
  <author><name>{e(site["name"])}</name></author>
{entries}</feed>
'''


# ------------------------------------------------------------------ build

SPEC_DESK = 'content/spec-desk.html'


def spec_desk_api(site):
    """The spec desk service's address (site.json spec_desk_api, D-37): None while the desk is not open, else an https
    URL, or an http loopback one for a check on this machine."""
    api = site.get('spec_desk_api')
    if api is None:
        return None
    parts = urlsplit(str(api))
    if parts.scheme == 'https' and parts.hostname:
        return str(api).rstrip('/')
    if parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost'):
        return str(api).rstrip('/')
    raise BuildError('site.spec_desk_api must be null, an https URL, or http://127.0.0.1 for a local check')


def spec_desk(site, root_dir: Path):
    """The spec desk page (D-37): a conversation with Malcolm from the Studio's spec desk service. While
    spec_desk_api is null the page says the desk opens soon and loads no script."""
    root = '../../'
    api = spec_desk_api(site)
    frag = (root_dir / SPEC_DESK).read_text(encoding='utf-8')
    if '<!-- desk -->' not in frag:
        raise BuildError(f'{SPEC_DESK} has no <!-- desk --> placeholder')
    if api is None:
        desk = ('<div class="desk soon"><p class="desk-closed">The spec desk opens soon. Malcolm is clearing his desk '
                'for your ideas.</p><p>In the meantime, <a href="../../games/">play the games</a> or read '
                '<a href="../../book/">the Book</a>.</p></div>')
        scripts = ''
    else:
        desk = f'''<div id="spec-desk" class="desk" data-api="{e(api)}" data-people="{root}assets/people/" aria-busy="false">
  <noscript><p class="desk-closed">The spec desk needs JavaScript to talk to Malcolm.</p></noscript>
  <div id="desk-log" class="desk-log" aria-live="polite"></div>
  <p id="desk-status" class="desk-status small" role="status"></p>
  <p><button id="desk-start" class="button primary big" type="button" hidden>Sit down with Malcolm</button></p>
  <form id="desk-form" class="desk-form" hidden>
    <label for="desk-text">Your answer (by number, for example &ldquo;2 yes, 3 a hedgehog&rdquo;)</label>
    <textarea id="desk-text" rows="3" maxlength="600" autocomplete="off"></textarea>
    <p><button class="button primary" type="submit">Send</button></p>
  </form>
  <p id="desk-tools" class="actions" hidden><button id="desk-notes" class="button" type="button">Download your notes</button>
  <button id="desk-delete" class="button" type="button">Delete my brief</button></p>
</div>'''
        scripts = f'<script src="{root}assets/spec-desk.js" defer></script>\n'
    return page(site, root=root, path='studio/spec-desk/', title='The spec desk', body=frag.replace('<!-- desk -->', desk),
                current='studio', scripts=scripts,
                description='Bring your game idea to Malcolm at the Dalex spec desk and take home the first page of its '
                            'specification.')


def write(out: Path, rel: str, text: str):
    p = out / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8', newline='\n')


def build(root: Path = ROOT, config: Path = None, out: Path = None) -> Path:
    root = Path(root)
    config = Path(config or root / 'site.json')
    out = Path(out or root / '_site')
    site, games, featured = load(root, config)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(root / 'static', out)
    if (root / 'CNAME').is_file():
        shutil.copyfile(root / 'CNAME', out / 'CNAME')
    write(out, 'index.html', home(site, games, featured, podcast.load(root)[1]))
    write(out, 'games/index.html', games_index(site, games))
    for g in games:
        src = root / 'games' / g['slug']
        for f in sorted(src.rglob('*')):
            name = f.relative_to(src).as_posix()
            if f.is_file() and (GAME_FILES.match(name) or (name == DEMO_FILE and g['_demo'])):
                d = out / 'games' / g['slug'] / f.relative_to(src)
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, d)
        write(out, f'games/{g["slug"]}/index.html', game_page(site, g))
    write(out, 'about/index.html', about(site, root))
    arts = load_articles(root)
    write(out, 'studio/index.html', studio(site, root, games, arts))
    write(out, 'book/index.html', book(site, root, games))
    write(out, 'studio/spec-desk/index.html', spec_desk(site, root))
    # The articles are the Studio's Learn more (D-33): no Articles section; its old addresses and the Blog's send
    # readers on, and the feed is also left at its old address for anyone subscribed to it.
    write(out, 'studio/feed.xml', articles_atom(site, arts))
    write(out, 'articles/feed.xml', articles_atom(site, arts))
    write(out, 'articles/index.html', moved(site, root='../', path='articles/', to='studio/', title='The Studio'))
    write(out, 'blog/index.html', moved(site, root='../', path='blog/', to='studio/', title='The Studio'))
    for a in arts:
        write(out, f'studio/{a["slug"]}/index.html', article_page(site, a, games))
        write(out, f'articles/{a["slug"]}/index.html',
              moved(site, root='../../', path=f'articles/{a["slug"]}/', to=f'studio/{a["slug"]}/', title=a['title']))
        if a.get('moved_from_blog'):
            write(out, f'blog/{a["slug"]}/index.html',
                  moved(site, root='../../', path=f'blog/{a["slug"]}/', to=f'studio/{a["slug"]}/', title=a['title']))
    show, episodes = podcast.load(root)   # Dalex After Hours (D-31): only episodes marked visible
    if show:
        feed_link = (f'<link rel="alternate" type="application/rss+xml" title="{e(show["title"])}" '
                     'href="{root}podcast/feed.xml">\n')
        cover = (show['cover_small'], show['cover_alt'], 1400, 1400)
        write(out, 'podcast/index.html', page(site, root='../', path='podcast/', title=show['title'],
                                              body=podcast.index_body(show, episodes), current='podcast',
                                              extra_head=feed_link.replace('{root}', '../'), description=show['description'],
                                              image=cover, ld=ld_json(breadcrumbs(site, (show['title'], 'podcast/')))))
        for ep in episodes:
            body = podcast.episode_body(site, show, ep, podcast.transcript_html(ep['vtt']))
            write(out, f'podcast/{ep["slug"]}/index.html',
                  page(site, root='../../', path=f'podcast/{ep["slug"]}/', title=ep['title'], body=body,
                       current='podcast', extra_head=feed_link.replace('{root}', '../../'), description=ep['summary'],
                       image=cover, ld=ld_json(breadcrumbs(site, (show['title'], 'podcast/'),
                                                           (ep['title'], f'podcast/{ep["slug"]}/')))))
            write(out, f'podcast/{ep["slug"]}/transcript.vtt', ep['vtt'])
            write(out, f'podcast/{ep["slug"]}/chapters.json', podcast.chapters_json(ep))
        write(out, 'podcast/feed.xml', podcast.rss(site, show, episodes))
    write(out, '404.html', not_found(site))
    write(out, 'sitemap.xml', sitemap(site, games, arts, episodes))
    write(out, 'feed.xml', feed(site, games))
    write(out, 'robots.txt', f'User-agent: *\nAllow: /\n\nSitemap: {site["base_url"]}sitemap.xml\n')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--config', default=str(ROOT / 'site.json'))
    ap.add_argument('--out', default=str(ROOT / '_site'))
    a = ap.parse_args(argv)
    try:
        out = build(ROOT, Path(a.config), Path(a.out))
    except BuildError as err:
        print(f'build failed: {err}', file=sys.stderr)
        return 1
    n = sum(1 for _ in out.rglob('*') if _.is_file())
    print(f'built {out} ({n} files)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
