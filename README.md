# Dalex Software website

The official website of Dalex Software, a fictional 1987 Manchester software house, and its
ZX Spectrum games: <https://dalex-software.co.uk/>. Every game page plays the tape in the browser
(JSSpeccy, click to play), shows the controls, screen shots, the INK & PAPER review, the cassette
inlay, advert and poster, and offers the tape for download with its SHA-256.

## Layout

| Path | Contents |
| --- | --- |
| `site.json` | site settings and the list of games: which are shown, in what order, which is featured |
| `games/<slug>/` | one folder per game, written by the toolkit's `zx-website` skill: `game.json`, the tape, cover, screen shots, inlay, advert, poster, review PDF and any licences |
| `content/about.html` | the About page body |
| `static/` | CSS, the player script, the Dalex logo, favicons and the vendored JSSpeccy 3.2 (GPL-3.0, see `static/jsspeccy/README.md`) |
| `build.py` | the generator (Python 3 standard library only) that writes `_site/` |
| `tests/` | build checks run in CI before every deploy |
| `docs/` | [decisions](docs/decisions.md), [DNS records](docs/DNS.md) and screenshots |

## Show or hide a game

Edit `site.json`. Each game has an entry:

```json
{ "slug": "gold-master", "visible": true, "order": 1, "featured": true }
```

- `visible`: `false` hides the game everywhere. Its pages, sitemap and feed entries are not built and
  none of its files are deployed; its folder stays in `games/` so it can be shown again.
- `order`: position on the home page and games list (lowest first).
- `featured`: the game in the home page hero. At most one visible game may be featured; with none,
  the first visible game is used.
- Optional `blurb` and `price_label` replace the game's own blurb and price on the site.

Commit and push to `main`; the workflow rebuilds and deploys the site.

## Publish or update a game

At the end of production, after the media kit passes, run the toolkit's `zx-website` skill from the
game's repository (`plugins/zx-media-kit/skills/zx-website/` in `spectrum-game-reference`):

```sh
python3 <zx-media-kit>/scripts/publish_site.py <game repo> [--site ../dalex-software] [--dry-run]
```

It refuses a kit that is stale against the release tape, writes `games/<slug>/`, adds a new game to
`site.json` (shown, last in order) or keeps an existing entry's settings, runs the build and tests,
commits and pushes. Do not edit `games/<slug>/` by hand: the next publish replaces it.

## Build and test locally

```sh
python3 build.py
python3 -m unittest discover -s tests
python3 -m http.server -d _site 8000   # then open http://localhost:8000/
```

The player needs the site served over HTTP; opening the files directly cannot fetch the tape.

## Screenshots

[Home](docs/screenshots/home.jpg), [home on a phone](docs/screenshots/home-mobile.jpg), [a game page](docs/screenshots/game-gold-master.jpg) and the player running [Gold Master](docs/screenshots/play-gold-master.jpg) and [Wordris](docs/screenshots/play-wordris.jpg), captured from the first deploy.

## Deploy

`.github/workflows/pages.yml` builds, tests and deploys `_site/` with the official GitHub Pages
actions on every push to `main`. The custom domain is `dalex-software.co.uk` (`CNAME`); the DNS
records the domain needs are in [docs/DNS.md](docs/DNS.md).
