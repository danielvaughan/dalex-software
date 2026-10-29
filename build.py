#!/usr/bin/env python3
"""Build the Dalex Software website into _site/ (Python 3 standard library only).

    python3 build.py [--config site.json] [--out _site]

Reads site.json (which games exist and which are shown), games/<slug>/game.json (written by the
toolkit's zx-website skill), content/about.html, static/ (with the studio film in static/media/) and
content/studio.html. Only games with "visible": true are
built into any page, the sitemap or the feed, and only their files are copied to the output, so a
hidden game is not deployed at all. The output is deterministic: the same inputs give the same bytes.

Only the free demo is played and nothing is downloadable (D-16): a game's demo is games/<slug>/demo.bin,
the demo tape obfuscated with DEMO_KEY from static/assets/player.js (D-18), decoded in the browser and
checked here against the sha256 recorded in site.json and game.json. No tape, review PDF or price-bearing
kit image (inlay, advert, poster) is copied, and no page may show a price (D-19).
"""
import argparse, hashlib, html, json, re, shutil, sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

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


def page(site, *, root, path, title, body, description='', current='', extra_head='', scripts=''):
    """A whole HTML page. root is the relative prefix back to the site root ('' / '../' / ...);
    path is this page's path below the site root, for the canonical URL."""
    full_title = f'{title} · {site["name"]}' if title != site['name'] else title
    nav = [('', 'Home', 'home'), ('games/', 'Games', 'games'), ('studio/', 'The Studio', 'studio'), ('about/', 'About', 'about')]
    links = ''.join(
        f'<li><a href="{root}{href}"{CURRENT if key == current else ""}>{label}</a></li>'
        for href, label, key in nav)
    return f'''<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(description or site.get('description', ''))}">
<meta name="color-scheme" content="dark light">
<link rel="canonical" href="{e(site['base_url'] + path)}">
<link rel="icon" href="{root}favicon.ico" sizes="any">
<link rel="icon" href="{root}favicon.png" type="image/png">
<link rel="alternate" type="application/atom+xml" title="{e(site['name'])} releases" href="{root}feed.xml">
<link rel="stylesheet" href="{root}assets/site.css">
{extra_head}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="masthead">
  <div class="wrap masthead-in">
    <a class="brand" href="{root or './'}"><img src="{root}assets/dalex-lockup.png" width="160" height="64" alt="Dalex Software"></a>
    <nav aria-label="Main"><ul>{links}</ul></nav>
  </div>
  <div class="rainbow" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
</header>
<main id="main" class="wrap">
{body}
</main>
<footer class="foot">
  <div class="wrap">
    <p><img src="{root}assets/dalex-mark.png" width="48" height="16" alt=""> <strong>{e(site['name'])}</strong>. {e(site.get('footer', ''))}</p>
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

def home(site, games, featured):
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
    cards = '\n'.join(card(x, root) for x in games)
    body = f'''<h1 class="sr-only">{e(site["name"])}: games for the ZX Spectrum</h1>
<p class="intro">{e(site.get("intro", ""))}</p>
{hero}
<section aria-labelledby="all-games">
  <h2 id="all-games">The games</h2>
  <ul class="grid">{cards}</ul>
</section>
<section class="studio-link" aria-labelledby="studio-film">
  <h2 id="studio-film">How the studio works</h2>
  <p>Take the five-minute tour of the studio where these games are made, from the first idea to the magazine review.
  <a href="studio/">Watch the film</a>.</p>
</section>'''
    return page(site, root=root, path='', title=site['name'], body=body, current='home')


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
    return page(site, root=root, path='games/', title='Games', body=body, current='games',
                description='All Dalex Software games for the ZX Spectrum.')


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
        player = f'''<section id="play-now" class="player" aria-labelledby="play-h">
  <h2 id="play-h" class="sr-only">Play the {e(game["title"])} demo</h2>
  <div class="screen">
    <div id="emulator" tabindex="0" role="application" aria-label="The {e(game["title"])} demo running on an emulated ZX Spectrum. Click here, then use the keys listed under Controls."
      data-demo="{DEMO_FILE}" data-machine="{machine_n}" data-title="{e(game["title"])}" data-jsspeccy="{root}jsspeccy/jsspeccy.js"></div>
    <div id="cover" class="cover"{cover_style}>
      <div class="cover-in">
        <p>{e(game.get("tagline", ""))}</p>
        <button id="play" type="button" class="button primary big">&#9654; Play the demo</button>
        <p class="small">Free. Loads the demo in a {machine_n}K Spectrum, with sound. You will need a keyboard.</p>
      </div>
    </div>
  </div>
  <div class="toolbar">
    <button id="pause" type="button" class="button" disabled>Pause</button>
    <button id="fullscreen" type="button" class="button" disabled>Full screen</button>
    <button id="restart" type="button" class="button" disabled>Restart</button>
  </div>
  {contains}
  <p class="small">The demo is an earlier milestone build of the game, so it may differ from the finished tape.</p>
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
    <p>{'Until then, the free demo above plays in your browser.' if demo else 'A free demo to play in your browser is coming soon.'}</p>
  </section>
  <section class="panel" aria-labelledby="credits-h">
    <h2 id="credits-h">Credits</h2>
    <dl class="credits">{credits}</dl>
    {igc_html}
    {lic_html}
  </section>
</div>'''
    return page(site, root=root, path=f'games/{game["slug"]}/', title=game['title'], body=body,
                current='games', description=f'{game["title"]} for the {game["machine"]}: '
                + (game.get('tagline') or ''),
                scripts=scripts)


def about(site, root_dir: Path):
    frag = (root_dir / 'content' / 'about.html').read_text(encoding='utf-8')
    return page(site, root='../', path='about/', title='About Dalex Software', body=frag, current='about',
                description='Dalex Software, a small Spectrum games house in a Manchester mill, and the people who make its games.')


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


def studio(site, root_dir: Path, games):
    """The Studio: the documentary film of how Dalex makes its games, with captions and a transcript. A link to a
    game that is hidden in site.json becomes plain text, so a hidden game is never linked."""
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
    body = frag.replace('<!-- film -->', film).replace('<!-- transcript -->', transcript(vtt))
    return page(site, root=root, path='studio/', title='The Studio', body=body, current='studio',
                description='A five-minute film of how Dalex Software makes its games: every role carried out by AI agents, '
                            'with people steering.')


def not_found(site):
    base = urlsplit(site['base_url']).path or '/'
    body = f'''<h1>R Tape loading error, 0:1</h1>
<p class="lede">That page isn&rsquo;t on this tape. Rewind and try again.</p>
<p class="actions"><a class="button primary" href="{e(base)}">Home</a> <a class="button" href="{e(base)}games/">All the games</a></p>'''
    return page(site, root=base, path='404.html', title='Page not found', body=body)


def sitemap(site, games):
    urls = [('', None), ('games/', None), ('studio/', None), ('about/', None)]
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
    write(out, 'index.html', home(site, games, featured))
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
    write(out, 'studio/index.html', studio(site, root, games))
    write(out, '404.html', not_found(site))
    write(out, 'sitemap.xml', sitemap(site, games))
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
