"""Dalex After Hours (the book's ADR-0025): the feed and pages are well formed, honest, and hide unheard episodes.

Run: python3 -m unittest discover -s tests
"""
import json, shutil, sys, tempfile, unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import podcast  # noqa: E402

ITUNES = '{http://www.itunes.com/dtds/podcast-1.0.dtd}'
PC = '{https://podcastindex.org/namespace/1.0}'
SITE = {'base_url': 'https://dalex-software.co.uk/'}


def episode(number, slug, visible):
    return {'number': number, 'slug': slug, 'title': f'Episode {number}', 'guest': 'Gareth Cadwaladr',
            'summary': 'A summary.', 'date': f'2026-09-0{number + 1}',
            'audio_url': f'https://github.com/danielvaughan/dalex-software/releases/download/podcast/{slug}.mp3',
            'audio_bytes': 10_000_000, 'seconds': 1080,
            'chapters': [{'start': 0, 'title': 'Welcome'}, {'start': 60, 'title': 'The desk'}], 'visible': visible}


class Podcast(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='dalex-podcast-'))
        folder = self.root / podcast.CONTENT
        folder.mkdir(parents=True)
        shutil.copy(ROOT / podcast.CONTENT / 'show.json', folder / 'show.json')
        eps = [episode(0, 'pilot', True), episode(1, 'mo', False)]
        (folder / 'episodes.json').write_text(json.dumps(eps))
        for ep in eps:
            (folder / f'{ep["slug"]}.html').write_text('<h2>In this episode</h2>\n<p>Notes.</p>\n')
            (folder / f'{ep["slug"]}.vtt').write_text('WEBVTT\n')

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_the_real_show_loads_and_is_honest(self):
        show, _ = podcast.load(ROOT)
        self.assertIn('fictional', show['description'])
        self.assertIn('synthesised', show['description'])

    def test_a_show_that_hides_the_truth_is_refused(self):
        path = self.root / podcast.CONTENT / 'show.json'
        show = json.loads(path.read_text())
        show['description'] = 'A podcast.'
        path.write_text(json.dumps(show))
        with self.assertRaises(ValueError):
            podcast.load(self.root)

    def test_hidden_episodes_are_left_out(self):
        show, eps = podcast.load(self.root)
        self.assertEqual([ep['slug'] for ep in eps], ['pilot'])
        feed = podcast.rss(SITE, show, eps)
        self.assertNotIn('/mo', feed)
        self.assertNotIn('Episode 1', podcast.index_body(show, eps))

    def test_the_feed_has_what_podcast_apps_need(self):
        show, eps = podcast.load(self.root)
        channel = ET.fromstring(podcast.rss(SITE, show, eps)).find('channel')
        for tag in ('title', 'link', 'description', 'language', ITUNES + 'image', ITUNES + 'author',
                    ITUNES + 'category', ITUNES + 'explicit'):
            self.assertIsNotNone(channel.find(tag), tag)
        item = channel.find('item')
        enclosure = item.find('enclosure')
        self.assertEqual((enclosure.get('type'), enclosure.get('length')), ('audio/mpeg', '10000000'))
        self.assertTrue(enclosure.get('url').startswith('https://'))
        self.assertEqual(item.find('guid').text, 'dalex-after-hours-pilot')
        self.assertEqual(item.find(PC + 'chapters').get('type'), 'application/json+chapters')
        self.assertEqual(item.find(PC + 'transcript').get('type'), 'text/vtt')
        self.assertEqual(item.find(ITUNES + 'episodeType').text, 'trailer')

    def test_chapters_and_determinism(self):
        show, eps = podcast.load(self.root)
        data = json.loads(podcast.chapters_json(eps[0]))
        self.assertEqual([c['startTime'] for c in data['chapters']], [0, 60])
        self.assertEqual(podcast.rss(SITE, show, eps), podcast.rss(SITE, *podcast.load(self.root)[0:1], eps))

    def test_an_episode_waits_for_its_own_day(self):
        """D-31: each episode goes out on its 1987 recording day; one dated ahead is not built yet."""
        path = self.root / podcast.CONTENT / 'episodes.json'
        eps = json.loads(path.read_text())
        eps[1]['visible'] = True
        eps[1]['date'] = '2999-01-01'
        path.write_text(json.dumps(eps))
        self.assertEqual([ep['slug'] for ep in podcast.load(self.root)[1]], ['pilot'])

    def test_chapters_out_of_order_are_refused(self):
        path = self.root / podcast.CONTENT / 'episodes.json'
        eps = json.loads(path.read_text())
        eps[0]['chapters'] = [{'start': 60, 'title': 'Late'}, {'start': 0, 'title': 'Early'}]
        path.write_text(json.dumps(eps))
        with self.assertRaises(ValueError):
            podcast.load(self.root)

    def test_the_episode_page_says_the_voices_are_synthesised(self):
        show, eps = podcast.load(self.root)
        body = podcast.episode_body(SITE, show, eps[0], '<p>Transcript.</p>')
        self.assertIn('Synthesised voices', body)
        self.assertIn('<audio controls preload="none"', body)   # nothing autoplays sound

    def test_the_player_and_feed_use_the_sites_own_copy(self):
        """D-32: an iPhone will not play GitHub's octet-stream download, so both point at the site's audio/mpeg copy."""
        show, eps = podcast.load(self.root)
        own = f'https://dalex-software.co.uk/podcast/audio/{eps[0]["slug"]}.mp3'
        self.assertIn(f'src="{own}"', podcast.episode_body(SITE, show, eps[0], ''))
        feed = podcast.rss(SITE, show, eps)
        self.assertIn(f'url="{own}"', feed)
        self.assertNotIn('releases/download', feed)

    def test_fetch_audio_refuses_a_short_download(self):
        import io, contextlib
        sys.path.insert(0, str(ROOT / 'tools'))
        import fetch_audio
        dest = self.root / 'site' / podcast.AUDIO / 'x.mp3'
        opener = lambda url: contextlib.closing(io.BytesIO(b'ID3' + bytes(7)))
        fetch_audio.fetch('https://example.invalid/x.mp3', dest, 10, opener)
        self.assertEqual(dest.stat().st_size, 10)
        with self.assertRaises(SystemExit):
            fetch_audio.fetch('https://example.invalid/x.mp3', dest.with_name('y.mp3'), 11, opener)
        self.assertFalse(dest.with_name('y.mp3').exists() or dest.with_name('y.part').exists())

    def test_a_transcript_line_is_timed_by_its_start(self):
        vtt = 'WEBVTT\n\n00:00:57.200 --> 00:01:02.000\n<v Bev>Across the minute.\n'
        self.assertIn('>0:57<', podcast.transcript_html(vtt))   # not 1:57, the end's minute with the start's seconds


if __name__ == '__main__':
    unittest.main()
