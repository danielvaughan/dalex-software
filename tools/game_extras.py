#!/usr/bin/env python3
"""Write each game's generated extras (D-47, proposed, dev preview): its milestone timeline and its genre.

For every game in site.json, reads the game's own repository at the commit its page was published from
(`games/<slug>/game.json` `source.commit`), in a local clone beside this checkout (`../zx-<slug>`, or --repos):

- the milestones, from the `## M<n>: <title>` headings of `game/milestones.md`, up to the release milestone;
- each milestone's date, the day its tape was finished: when its media kit was made (`kit.json` `built_at`, else
  the commit that added its review), else, for a milestone that was never boxed, its last gate
  (`game/milestones/m<n>.md`, `## Gate <date>`);
- one screen shot per milestone, the first one its INK & PAPER review captions (`review.json`), with that caption,
  copied only when it is a native Spectrum frame (256x192, or 320x240 with the border), is not the same picture or
  caption as an earlier milestone's, and its caption carries no price or finding number;
- the genre, from the `Genre` line of the game's specification, when it has one.

Writes `content/extras/<slug>/milestones.json` and `content/extras/<slug>/m<n>.png`; the hand-curated
`content/extras/<slug>/extras.json` is never touched. Nothing is written to the game repositories, and GitHub is not
needed: the games keep their milestones in the repository (their GitHub milestone lists are empty).
In production this belongs in the toolkit's zx-website skill, beside the rest of `games/<slug>/`.

Run: python3 tools/game_extras.py [--repos ..] [--slug wolf]
"""
import argparse, json, re, struct, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build import PRICE_RE  # noqa: E402

HEADING = re.compile(r'^## M(\d+)\s*[:\-]\s*(.+?)\s*$', re.M)
TRAILING_NOTE = re.compile(r'\s*\([^()]*\)\s*$')          # "(owner, 2026-10-19)", "(issue #8)", "(final)"
GENRE = re.compile(r'^\s*-\s*\*\*Genre[^*]*:\*\*\s*(.+)$', re.M)
NATIVE = {(256, 192), (320, 240)}
GATE = re.compile(r'^## Gate (\d{4}-\d{2}-\d{2})', re.M)
FINDING_ID = re.compile(r'^[A-Z]{1,3}-\d+:')


def git(repo: Path, *args, binary=False):
    r = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if r.returncode:
        return None
    return r.stdout if binary else r.stdout.decode('utf-8')


def show(repo, commit, path, binary=False):
    return git(repo, 'show', f'{commit}:{path}', binary=binary)


def png_size(data: bytes):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', data[16:24])


def clean_title(t: str) -> str:
    while TRAILING_NOTE.search(t):
        t = TRAILING_NOTE.sub('', t)
    return t.strip(' .')


def genre_of(repo, commit, slug):
    spec = show(repo, commit, f'specs/{slug}-spec.md')
    m = GENRE.search(spec or '')
    if not m:
        return None
    g = re.split(r'\.\s|\.$', m.group(1).strip())[0].split(',')[0].strip()
    g = re.sub(r'[*_]', '', g)
    return {'text': g[:1].upper() + g[1:], 'source': f'specs/{slug}-spec.md'}


def extras_for(repo: Path, game: dict, out: Path) -> dict:
    src = game['source']
    commit = src['commit']
    release = (game.get('release') or {}).get('milestone')
    plan = show(repo, commit, 'game/milestones.md')
    if plan is None:
        raise SystemExit(f'{game["slug"]}: game/milestones.md not found at {commit[:8]} in {repo}')
    kit_root = str(Path(src.get('kit') or 'game/media-kit/m1').parent)
    items, seen = [], set()
    for m in HEADING.finditer(plan):
        n, title = int(m.group(1)), clean_title(m.group(2))
        if release and n > release:
            continue
        item = {'milestone': n, 'title': title, 'date': None, 'shot': None}
        kit = f'{kit_root}/m{n}'
        built = json.loads(show(repo, commit, f'{kit}/kit.json') or '{}').get('built_at')
        added = (git(repo, 'log', '--diff-filter=A', '--format=%cs', commit, '--', f'{kit}/review.json') or '').split()
        gates = GATE.findall(show(repo, commit, f'game/milestones/m{n}.md') or '')
        if built:
            item['date'] = datetime.fromisoformat(built).date().isoformat()
        elif added:
            item['date'] = added[-1]
        elif gates:
            item['date'] = gates[-1]
        review = json.loads(show(repo, commit, f'{kit}/review.json') or '{}')
        for cap in review.get('captions') or []:
            data = show(repo, commit, f'{kit}/shots/{cap.get("screenshot")}.png', binary=True)
            text = (cap.get('text') or '').strip()
            if (not data or not text or PRICE_RE.search(text) or FINDING_ID.match(text)
                    or png_size(data) not in NATIVE or data in seen or text in seen):
                continue
            seen.update((data, text))
            name = f'm{n}.png'
            (out / name).write_bytes(data)
            w, h = png_size(data)
            item['shot'] = {'src': name, 'size': [w, h], 'caption': text}
            break
        items.append(item)
    return {'schema': 'dalex-site-extras/1', 'slug': game['slug'],
            'source': {'repo': src['repo'], 'commit': commit, 'plan': 'game/milestones.md',
                       'kits': kit_root},
            'genre': genre_of(repo, commit, game['slug']),
            'milestones': items}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--repos', default=str(ROOT.parent), help='folder holding the zx-<slug> clones')
    ap.add_argument('--slug', action='append', help='only these games')
    a = ap.parse_args(argv)
    cfg = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
    for entry in cfg['games']:
        slug = entry['slug']
        if a.slug and slug not in a.slug:
            continue
        game = json.loads((ROOT / 'games' / slug / 'game.json').read_text(encoding='utf-8'))
        repo = Path(a.repos) / Path(game['source']['repo']).name
        if git(repo, 'cat-file', '-e', game['source']['commit'] + '^{commit}') is None:
            print(f'{slug}: skipped, commit {game["source"]["commit"][:8]} is not in {repo}', file=sys.stderr)
            continue
        out = ROOT / 'content' / 'extras' / slug
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob('m*.png'):
            old.unlink()
        data = extras_for(repo, game, out)
        (out / 'milestones.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        shots = sum(1 for x in data['milestones'] if x['shot'])
        print(f'{slug}: {len(data["milestones"])} milestones, {shots} with a screen shot')
    return 0


if __name__ == '__main__':
    sys.exit(main())
