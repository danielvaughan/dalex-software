# Dalex Software website: project instructions

This repository is the public website for Dalex Software and its ZX Spectrum games,
deployed to <https://dalex-software.co.uk/> by GitHub Pages. Read [README.md](README.md) first.

## Rules

- **Game content is generated.** `games/<slug>/` is written by the `zx-website` skill in the
  toolkit (`spectrum-game-reference`, plugin `zx-media-kit`). Fix content in the game's own
  repository or media kit and publish again; never hand-edit a game folder.
- **Demos only, no prices.** The site plays each game's obfuscated demo (`demo.bin`) and offers nothing
  for download; full tapes never enter this repository, and no price appears anywhere ("Price to be
  confirmed"). See decisions D-16 to D-20; the tests check it.
- **Visibility lives in `site.json`.** Hidden games must never reach `_site/`; the tests check it.
- **Standard library only.** `build.py` and the tests use Python 3 and nothing else, so CI needs no
  installs. Keep the build deterministic (no timestamps, sorted output).
- **Relative links.** Pages link relatively so the site works at `/` and under a project path; only
  canonical URLs, the sitemap, the feed, robots.txt and `404.html` use `site.base_url`.
- **In-world and honest.** The site speaks as the 1987 studio. Scores and quotes come only from
  the INK & PAPER review in each game's media kit; never invent features, scores or quotes.
- **Accessible and private.** Keyboard-usable, alt text on every image, good contrast in both
  colour schemes, nothing autoplays sound, no analytics, cookies or third-party fonts.
- **JSSpeccy is GPL-3.0.** Keep `static/jsspeccy/COPYING`, its README, `PATCH.md` and the source
  archive with the vendored build, and keep the footer credit.

## Checks and commits

```sh
python3 build.py && python3 -m unittest discover -s tests
```

Run `pre-commit install` once; commits must pass Gitleaks, Markdownlint, zizmor and actionlint.
Pin every GitHub Action to a commit SHA with its version in a comment, and keep workflow
permissions minimal. Record routine decisions in [docs/decisions.md](docs/decisions.md).
