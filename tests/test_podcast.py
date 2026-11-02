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
            'summary': 'A summary.', 'date': f'2026-12-0{number + 1}',
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

    def test_chapters_out_of_order_are_refused(self):
        path = self.root / podcast.CONTENT / 'episodes.json'
        eps = json.loads(path.read_text())
        eps[0]['chapters'] = [{'start': 60, 'title': 'Late'}, {'start': 0, 'title': 'Early'}]
        path.write_text(json.dumps(eps))
        with self.assertRaises(ValueError):
            podcast.load(self.root)

    def test_the_episode_page_says_the_voices_are_synthesised(self):
        show, eps = podcast.load(self.root)
        body = podcast.episode_body(show, eps[0], '<p>Transcript.</p>')
        self.assertIn('Synthesised voices', body)
        self.assertIn('<audio controls preload="none"', body)   # nothing autoplays sound


if __name__ == '__main__':
    unittest.main()
