# Dalex Software website

The official website of Dalex Software, a fictional 1987 Manchester software house, and its
ZX Spectrum games: <https://dalex-software.co.uk/>. Every game page plays a free demo in the browser
(JSSpeccy, click to play) or says "Demo coming soon", and shows the controls, screen shots and the
INK & PAPER scores and quote. Nothing is downloadable and no price is shown: the full tapes stay in the
games' private repositories, and prices are "to be confirmed" ([D-16 to D-19](docs/decisions.md)).

## Layout

| Path | Contents |
| --- | --- |
| `site.json` | site settings and the list of games: which are shown, in what order, which is featured |
| `games/<slug>/` | one folder per game, written by the toolkit's `zx-website` skill: `game.json`, `demo.bin` (the obfuscated demo tape, when there is a demo), cover, screen shots and any licences |
| `content/about.html` | the About page body |
| `static/` | CSS, the player script (which holds the demo key), the Dalex logo, favicons and the vendored JSSpeccy 3.2 (GPL-3.0, see `static/jsspeccy/README.md`) |
| `build.py` | the generator (Python 3 standard library only) that writes `_site/` |
| `tests/` | build checks run in CI before every deploy |
| `docs/` | [decisions](docs/decisions.md), [DNS records](docs/DNS.md) and screenshots |

## Show or hide a game

Edit `site.json`. Each game has an entry:

```json
{ "slug": "gold-master", "visible": true, "order": 1, "featured": true,
  "demo": { "milestone": 1, "sha256": "f63311ea…", "contains": "Level 1 of 4: …" } }
```

- `visible`: `false` hides the game everywhere. Its pages, sitemap and feed entries are not built and
  none of its files are deployed; its folder stays in `games/` so it can be shown again.
- `order`: position on the home page and games list (lowest first).
- `featured`: the game in the home page hero. At most one visible game may be featured; with none,
  the first visible game is used.
- `demo`: the demo tape the page plays (its milestone, sha256 and a line saying what it contains), or `null`
  for "Demo coming soon". The publisher writes it; the build checks `games/<slug>/demo.bin` decodes to that sha256.
  Change the demo by publishing again with `--demo` rather than editing the sha256 by hand. Editing only
  `contains` is fine.
- Optional `blurb` replaces the game's own blurb on the site. There is no price setting: no price is shown.

Commit and push to `main`; the workflow rebuilds and deploys the site.

## Publish or update a game

At the end of production, after the media kit passes, run the toolkit's `zx-website` skill from the
game's repository (`plugins/zx-media-kit/skills/zx-website/` in `spectrum-game-reference`):

```sh
python3 <zx-media-kit>/scripts/publish_site.py <game repo> [--site ../dalex-software] [--dry-run]
```

It refuses a kit that is stale against the release tape, picks the demo (`--demo <tape|milestone|none>`,
else `site.json`'s `demo`, else the game's gated first milestone), refuses the release tape as a demo,
writes `games/<slug>/` with the demo obfuscated as `demo.bin` and every price sentence cut, adds a new
game to `site.json` (shown, last in order) or keeps an existing entry's settings, runs the build and
tests, commits and pushes. Do not edit `games/<slug>/` by hand: the next publish replaces it.

## Build and test locally

```sh
python3 build.py
python3 -m unittest discover -s tests
python3 -m http.server -d _site 8000   # then open http://localhost:8000/
```

The player needs the site served over HTTP; opening the files directly cannot fetch the demo.

## Screenshots

[Home](docs/screenshots/home.jpg), [home on a phone](docs/screenshots/home-mobile.jpg), [a game page](docs/screenshots/game-gold-master.jpg) and the player running [Gold Master](docs/screenshots/play-gold-master.jpg) and [Wordris](docs/screenshots/play-wordris.jpg), captured from the first deploy. The demos at their title screens, captured after the switch to demos: [Gold Master](docs/screenshots/demo-gold-master.png), [Antigravity](docs/screenshots/demo-antigravity.png), [WOLF](docs/screenshots/demo-wolf.png) and [Wordris](docs/screenshots/demo-wordris.png), and a page with no demo yet, [Tiger Gorilla](docs/screenshots/no-demo-tiger-gorilla.png).

## Deploy

`.github/workflows/pages.yml` builds, tests and deploys `_site/` with the official GitHub Pages
actions on every push to `main`. The custom domain is `dalex-software.co.uk` (`CNAME`); the DNS
records the domain needs are in [docs/DNS.md](docs/DNS.md).
