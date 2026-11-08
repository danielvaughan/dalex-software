#!/usr/bin/env python3
"""Copy visible podcast MP3s into the built site for browser-friendly audio/mpeg delivery.

The files live in this repository's podcast release, not in Git. The Pages
workflow uses its read-only GITHUB_TOKEN and the release-asset API: GitHub's
public release-download gateway can return 504. Each file must match the
recorded byte length before it becomes part of the deployed site.
"""
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import podcast  # noqa: E402

RELEASE = 'https://api.github.com/repos/danielvaughan/dalex-software/releases/tags/podcast'
HEADERS = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}


def release_assets(token: str, opener=urllib.request.urlopen) -> dict[str, dict]:
    """Name-to-metadata map for the podcast release, using the workflow's read-only token."""
    request = urllib.request.Request(RELEASE, headers={**HEADERS, 'Authorization': f'Bearer {token}'})
    with opener(request) as response:
        data = json.load(response)
    return {asset['name']: asset for asset in data['assets']}


def asset_open(url: str, token: str):
    request = urllib.request.Request(url, headers={
        'Accept': 'application/octet-stream',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    return urllib.request.urlopen(request, timeout=120)


def fetch(url: str, dest: Path, expected: int, opener=urllib.request.urlopen) -> None:
    """Download url to dest, refusing (and removing) a file whose length is not expected."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix('.part')
    try:
        with opener(url) as response, part.open('wb') as out:
            shutil.copyfileobj(response, out, 1 << 20)
        got = part.stat().st_size
        if got != expected:
            raise SystemExit(f'{url}: {got} bytes, expected {expected}')
        part.replace(dest)
    finally:
        part.unlink(missing_ok=True)


def main(site: Path) -> None:
    _, episodes = podcast.load(ROOT)
    token = os.environ.get('GITHUB_TOKEN')
    assets = release_assets(token) if token else {}
    for ep in episodes:
        name = f'{ep["slug"]}.mp3'
        expected = int(ep['audio_bytes'])
        dest = site / podcast.AUDIO / name
        if token:
            asset = assets.get(name)
            if not asset or int(asset['size']) != expected:
                raise SystemExit(f'{name}: missing release asset or recorded size mismatch')
            fetch(asset['url'], dest, expected, lambda url: asset_open(url, token))
        else:
            fetch(ep['audio_url'], dest, expected)
        print(f'{dest.relative_to(site)}  {expected} bytes')
    print(f'{len(episodes)} episode(s) copied into {site}')


if __name__ == '__main__':
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        raise SystemExit('usage: fetch_audio.py <built site directory>')
    main(Path(sys.argv[1]))
