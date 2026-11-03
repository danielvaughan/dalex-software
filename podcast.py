"""Dalex After Hours, the podcast from the book Machine Code Mayhem: its pages and its RSS feed (standard library only).

Reads content/podcast/show.json (the show), content/podcast/episodes.json (the episodes) and, for each episode,
its show notes content/podcast/<slug>.html and transcript content/podcast/<slug>.vtt. Only
episodes with "visible": true whose date and time have come are built anywhere, so an episode the author has not yet listened to never reaches
the site, the feed or the sitemap (the book's ADR-0025: nothing is published until the author has heard it).

The feed is RSS 2.0 with Apple's iTunes tags and the Podcast Index namespace (podcast:transcript for the WebVTT
transcript, podcast:chapters for JSON chapters). The audio is not in this repository: each episode's MP3 is a
GitHub release asset, named by its full URL and byte length. Every page and the feed say plainly that the people
are fictional and the voices synthesised. The output is deterministic: no timestamps beyond the episodes' own dates.
"""
import html
import json
import re
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path

CONTENT = 'content/podcast'
HONESTY = 'fictional'          # the show's description must say the people are fictional ...
SYNTHESISED = 'synthesised'    # ... and the voices synthesised
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
EPISODE_KEYS = ('number', 'slug', 'title', 'guest', 'summary', 'date', 'audio_url', 'audio_bytes', 'seconds',
                'chapters', 'visible')
ITUNES = 'http://www.itunes.com/dtds/podcast-1.0.dtd'
PODCAST = 'https://podcastindex.org/namespace/1.0'


def e(s) -> str:
    return html.escape(str(s), quote=True)


def load(root: Path):
    """(show, visible episodes newest first), or (None, []) when the site has no podcast yet."""
    folder = root / CONTENT
    if not (folder / 'show.json').exists():
        return None, []
    show = json.loads((folder / 'show.json').read_text(encoding='utf-8'))
    for word in (HONESTY, SYNTHESISED):
        if word not in show['description']:
            raise ValueError(f'the show description must say the cast are {HONESTY} and the voices {SYNTHESISED}')
    episodes = json.loads((folder / 'episodes.json').read_text(encoding='utf-8'))
    seen = set()
    for ep in episodes:
        missing = [k for k in EPISODE_KEYS if k not in ep]
        if missing:
            raise ValueError(f'episode {ep.get("slug")} lacks {missing}')
        if not SLUG.match(ep['slug']) or ep['slug'] in seen:
            raise ValueError(f'bad or repeated slug: {ep["slug"]}')
        seen.add(ep['slug'])
        date.fromisoformat(ep['date'])
        if not ep['audio_url'].startswith('https://'):
            raise ValueError(f'{ep["slug"]}: audio must be served over https')
        starts = [c['start'] for c in ep['chapters']]
        if starts != sorted(starts) or (starts and starts[0] != 0):
            raise ValueError(f'{ep["slug"]}: chapters must start at 0 and run in order')
    now = datetime.now(timezone.utc)   # an episode goes out at its own date and time, not before (D-31)
    shown = [ep for ep in episodes if ep['visible'] is True and released(ep) <= now]
    for ep in shown:
        ep['notes'] = (folder / f'{ep["slug"]}.html').read_text(encoding='utf-8')
        ep['vtt'] = (folder / f'{ep["slug"]}.vtt').read_text(encoding='utf-8')
    return show, sorted(shown, key=lambda ep: (ep['date'], ep['number']), reverse=True)


def released(ep) -> datetime:
    """When an episode goes out: its date at its time (HH:MM UTC), 19:00 UTC when no time is given."""
    d = date.fromisoformat(ep['date'])
    hour, minute = (int(x) for x in (ep.get('time') or '19:00').split(':'))
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone.utc)


def clock(seconds: int) -> str:
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def rfc2822(iso: str, number: int = 0, at: str = '') -> str:
    """The publication time (`time`, HH:MM UTC, written when the episode is published; 19:00 when absent), a second
    later per episode number, so episodes published together keep their order and none is dated in the future."""
    d = date.fromisoformat(iso)
    hour, minute = (int(x) for x in (at or '19:00').split(':'))
    return format_datetime(datetime(d.year, d.month, d.day, hour, minute, number % 60, tzinfo=timezone.utc))


def transcript_html(vtt: str) -> str:
    """The WebVTT transcript as paragraphs, one per turn, the speaker in bold."""
    out, at = [], ''
    for line in vtt.splitlines():
        if '-->' in line:
            at = clock(int(float(line.split('-->')[0].strip().split(':')[-1]) + 60 * int(line.split(':')[-2])
                           + 3600 * int(line.split(':')[0])))
            continue
        voice = re.match(r'<v ([^>]+)>(.*)', line)
        if voice:
            out.append(f'<p><span class="small">{e(at)}</span> <strong>{e(voice.group(1))}</strong> {e(voice.group(2))}</p>')
    return '\n'.join(out) + '\n'


def chapters_json(ep) -> str:
    """Podcast Index JSON chapters (served as application/json+chapters)."""
    return json.dumps({'version': '1.2.0', 'chapters': [{'startTime': c['start'], 'title': c['title']}
                                                        for c in ep['chapters']]}, indent=2) + '\n'


def rss(site, show, episodes) -> str:
    base = site['base_url']
    home = f'{base}podcast/'
    items = ''.join(f'''    <item>
      <title>{e(ep["title"])}</title>
      <link>{e(home)}{e(ep["slug"])}/</link>
      <guid isPermaLink="false">dalex-after-hours-{e(ep["slug"])}</guid>
      <pubDate>{rfc2822(ep["date"], int(ep["number"]), ep.get("time", ""))}</pubDate>
      <description>{e(ep["summary"])}</description>
      <enclosure url="{e(ep["audio_url"])}" length="{int(ep["audio_bytes"])}" type="audio/mpeg"/>
      <itunes:episode>{int(ep["number"])}</itunes:episode>
      <itunes:episodeType>{"trailer" if ep["number"] == 0 else "full"}</itunes:episodeType>
      <itunes:duration>{int(ep["seconds"])}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
      <itunes:image href="{e(base)}{e(show["cover"])}"/>
      <podcast:transcript url="{e(home)}{e(ep["slug"])}/transcript.vtt" type="text/vtt" language="en-GB"/>
      <podcast:chapters url="{e(home)}{e(ep["slug"])}/chapters.json" type="application/json+chapters"/>
    </item>
''' for ep in episodes)
    latest = rfc2822(episodes[0]['date'], int(episodes[0]['number']), episodes[0].get('time', '')) if episodes else rfc2822('1987-01-01')
    return f'''<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:itunes="{ITUNES}" xmlns:podcast="{PODCAST}" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{e(show["title"])}</title>
    <link>{e(home)}</link>
    <atom:link href="{e(home)}feed.xml" rel="self" type="application/rss+xml"/>
    <language>en-gb</language>
    <copyright>{e(show["copyright"])}</copyright>
    <description>{e(show["description"])}</description>
    <lastBuildDate>{latest}</lastBuildDate>
    <image><url>{e(base)}{e(show["cover"])}</url><title>{e(show["title"])}</title><link>{e(home)}</link></image>
    <itunes:image href="{e(base)}{e(show["cover"])}"/>
    <itunes:author>{e(show["author"])}</itunes:author>
    <itunes:category text="{e(show["category"])}"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <podcast:locked>no</podcast:locked>
{items}  </channel>
</rss>
'''


def index_body(show, episodes) -> str:
    rows = ''.join(f'''<li class="episode-row">
  <a href="{e(ep["slug"])}/"><strong>{e(ep["number"])}. {e(ep["title"])}</strong></a>
  <span class="small">with {e(ep["guest"])} · {e(clock(ep["seconds"]))}</span>
  <p>{e(ep["summary"])}</p>
</li>
''' for ep in episodes)
    listing = f'<ol class="episodes" reversed>\n{rows}</ol>' if episodes else '<p>The first episode is on its way.</p>'
    return f'''<h1>{e(show["title"])}</h1>
<img class="podcast-cover" src="../{e(show["cover_small"])}" width="350" height="350" alt="{e(show["cover_alt"])}">
<p>{e(show["description"])}</p>
{listing}
<p class="small"><a href="feed.xml">Podcast feed (RSS)</a>: paste it into any podcast app.</p>
'''


def episode_body(show, ep, transcript_html: str) -> str:
    """The episode page: a player, then show notes in a fixed shape (the notes fragment carries In this episode,
    the topic sections, Summary, Resources and Related episodes), the chapters and the transcript."""
    chapters = ''.join(f'<li><span class="small">{e(clock(c["start"]))}</span> {e(c["title"])}</li>\n'
                       for c in ep['chapters'])
    return f'''<p class="small"><a href="../">{e(show["title"])}</a> · episode {e(ep["number"])}</p>
<h1>{e(ep["title"])}</h1>
<p>With {e(ep["guest"])}. {e(clock(ep["seconds"]))}.</p>
<audio controls preload="none" src="{e(ep["audio_url"])}"></audio>
<p class="small">Synthesised voices; the people are fictional and the facts about the games are real.</p>
{ep["notes"]}
<h2>Chapters</h2>
<ol class="chapters">
{chapters}</ol>
<details><summary>Transcript</summary>
{transcript_html}
</details>
'''
