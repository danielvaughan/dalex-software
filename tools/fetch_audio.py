#!/usr/bin/env python3
"""Copy each visible podcast episode's MP3 into the built site, so the site serves it as audio/mpeg (D-32).

The MP3s live as assets of this repository's `podcast` release, not in Git (D-31). GitHub's download host sends
every asset as application/octet-stream with `Content-Disposition: attachment`, which an iPhone refuses to play.
GitHub Pages sends a .mp3 as audio/mpeg with byte ranges, so the deploy fetches each episode the build published
(podcast.load: visible and its time come) into <site>/podcast/audio/<slug>.mp3, the address the pages and feed
give. It stops if a download's length is not the episode's `audio_bytes`. Standard library only; run after
build.py, in the deploy workflow:

    python3 tools/fetch_audio.py _site
"""
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import podcast  # noqa: E402


def fetch(url: str, dest: Path, expected: int, opener=urllib.request.urlopen) -> None:
    """Download url to dest, refusing (and removing) a file whose length is not `expected`."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix('.part')
    with opener(url) as response, part.open('wb') as out:
        shutil.copyfileobj(response, out, 1 << 20)
    got = part.stat().st_size
    if got != expected:
        part.unlink()
        raise SystemExit(f'{url}: {got} bytes, expected {expected}')
    part.replace(dest)


def main(site: Path) -> None:
    _, episodes = podcast.load(ROOT)
    for ep in episodes:
        dest = site / podcast.AUDIO / f'{ep["slug"]}.mp3'
        fetch(ep['audio_url'], dest, int(ep['audio_bytes']))
        print(f'{dest.relative_to(site)}  {ep["audio_bytes"]} bytes')
    print(f'{len(episodes)} episode(s) copied into {site}')


if __name__ == '__main__':
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        raise SystemExit('usage: fetch_audio.py <built site directory>')
    main(Path(sys.argv[1]))
