# Decisions

Routine decisions made while building the site, so the owner can overrule any of them.

## D-01 Generator: Python standard library, no Jinja2 or PyYAML

`build.py` uses only the standard library (`json`, `html`, `shutil`). The pages are few and fixed,
so templates are Python functions with `html.escape`. CI needs no installs, and the owner's Mac and
Ubuntu machines build it with any Python 3.11+.

## D-02 Configuration is `site.json`, not YAML

The brief allowed YAML or JSON. JSON keeps the build and the toolkit's publisher on the standard
library and lets the publisher rewrite the file without losing anything. Fields per game: `slug`,
`visible`, `order`, `featured`, optional `blurb` and `price_label`.

## D-03 Hidden means not deployed

A game with `visible: false` gets no page, card, sitemap or feed entry, and none of its files are
copied to `_site/`. Its folder stays in `games/` so it can be shown again by flipping the flag.
`tests/test_site.py` checks this on the real games and on a fixture site.

## D-04 Relative links everywhere

Pages link relatively, so the same build works at `https://dalex-software.co.uk/` and under
`/dalex-software/` before DNS is set. Only canonical URLs, `sitemap.xml`, `feed.xml`,
`robots.txt` and `404.html` (which GitHub serves at any depth) use `site.base_url`.

## D-05 One JSSpeccy copy, loaded on Play

The vendored JSSpeccy 3.2 build (with its two documented patches, `PATCH.md`) is copied unchanged
from `danielvaughan.github.io/tiger-gorilla/jsspeccy/`, licence notice and source archive included,
and lives once at `/jsspeccy/`. The player script (`static/assets/player.js`, adapted from the old
pages' `player.js`) loads it only when Play is pressed, so nothing downloads or makes a sound until
then. The tape loads in 128K mode (48K for a 48K game) with JSSpeccy's tape traps.

## D-06 What each game page shows

- Tagline: the first sentence of the media kit's inlay blurb (`info.json`).
- Release date: the kit's `built_at` date (`kit.json`), shown plainly.
- Score: the kit's INK & PAPER Overall and category marks; the quote is the advert's first
  pull-quote (`quotes.json`), attributed to the reviewer whose opinion holds it; the verdict line
  is the review's own.
- Full review: the kit's `review.pdf` is published beside the page and linked, so the review counts
  as published.
- Screen shots: up to four from the kit's `shots/`, in the order the review captions them, reduced
  to the Spectrum's native 256×192 or 320×240 (with border) by nearest-neighbour and scaled back up
  in the browser with `image-rendering: pixelated`. Captions are the review's.
- Inlay, advert and poster: the kit's PNGs as JPEG at most 1600 px on the long side; the cover
  painting as JPEG at most 1200 px wide. Original PNGs were up to 4.5 MB each.
- Credits: publisher, the game specification version where there is a spec, the INK & PAPER
  reviewers, the game's own in-game credits page when it has one (`assets/text/credits.yaml`,
  which carries Wordris's required word-list credit), and any `game/licenses/` files.
- No gameplay video: the kits' MP4s are 4-18 MB each; the playable game is the better demo.

## D-07 Starting line-up and order

All six games are visible. Gold Master is featured (newest release, 29 October 2026) and first;
the rest follow newest first by kit date: Tiger Gorilla, Antigravity, Wordris, Mower Mayhem, WOLF.

## D-08 Mower Mayhem is published from its last kitted tape

Mower Mayhem is mid-way through M6.3: `build/mower-mayhem-m6.tap` and `verify/m6.json` are tape
`fa93c129`, but the newest media kit (M6, INK & PAPER 71%) was built for tape `fef4f005`. The
publisher refuses the plain run ("kit is stale against the release tape"). The site carries the
tape the kit describes, `media-kit/m6/mower-mayhem-m6-fef4f005.tap`, named explicitly with `--tap`;
the sha256 check still applies to it. Publish again when M6.3 has its own kit.

## D-09 In-world copy, honest footer

The About page is written in the studio's voice from the Dalex Studio vision and specification
(the fourteen named staff, Percy and Omnibot, and Brian of INK & PAPER across the courtyard). There
is no `GLOSSARY.md` in dalex-studio; the seven production stages come from the Gold Master
specification (Design, Assets, Build, Verify, Playtest, Sign-off, Release). The footer and About
page say plainly that Dalex Software and INK & PAPER are fictional and the games are real.

## D-10 Look

Black masthead with the house lockup (lockup A, stamped from the toolkit's
`house-style/logo/lockup-a-x8.png` at 1×, never recoloured) and the four-colour Spectrum stripe
as the accent, never as a wash. System fonts with a monospace face for headings; no web fonts. Dark
and light schemes follow the visitor's system setting. The INK & PAPER mark is a red stamp.

## D-11 Workflow

One workflow builds, tests and uploads on every push and pull request, and deploys from `main`
only, with the official `upload-pages-artifact` and `deploy-pages` actions pinned by commit SHA.
Top-level permissions are empty; the build job reads contents and the deploy job gets
`pages: write` and `id-token: write`. Checkout does not persist credentials.

## D-12 Deploy check, then the custom domain

The first deploy was checked at `https://danielvaughan.com/dalex-software/` (the account's Pages
host; `danielvaughan.github.io/dalex-software/` redirects there) before the custom domain was set:
the home page and every game page loaded, and headless Chromium pressed Play on each of the six
games and saw JSSpeccy load the tape to its title screen. Screenshots of that live site are in
[screenshots/](screenshots/). Then the Pages custom domain was set to `dalex-software.co.uk`, so
the old project address now redirects to the new domain, which serves nothing until the owner adds
the records in [DNS.md](DNS.md).

## D-13 Staff portraits on the About page

The owner asked for a picture of each person. They are the Dalex Studio's own cast pixels, so the site and the
Studio show the same people. `tools/portraits.py` renders each person's front-facing talking pose (the Studio's
tour frames), Percy sitting and Omnibot's close-up from the Studio's packed art and palette, keeping only the
figure's largest shape and cropping to it. The PNGs are committed under `static/assets/people/`, so the site build
stays standard-library only; rerun the tool with the Studio's Python when the cast art changes. Portraits are
shown at native scale on a shared floor line, so relative heights hold (Percy is small because he is a cat).

## D-15 Standing cast sprites on the About page

Supersedes D-13's portraits. The owner asked for new sprites of each character, all standing and at a consistent
size: the Studio's tour frames mixed seated, standing and close-up poses at different heights. Each person is now
a full-body, front-facing standing figure drawn for the site in the Studio's house style (VISION section 12, "One
cast, one hand"): Gemini image sheets on flat magenta, with the Studio's Neil and Colin strips as the style
reference and each person's Studio front frame as the identity reference. Five calls made the 14 people (Brian
included); Percy (sitting up) and Omnibot (full body) are cut from their existing Studio source sheets.
Prompts, raw sheets, identity strips, the manifest and provenance are in `assets/source/people/`.

`tools/people.py` rebuilds `static/assets/people/<id>.png` deterministically from those sources (Pillow and NumPy,
run with the Studio's interpreter; the site build stays standard-library only) and replaces `tools/portraits.py`.
Every PNG is one 96x192 canvas with the feet on the bottom row. People are scaled to a set height of 172 px give or
take 6% (Malcolm and Brian 182, Mo 162); Percy is 64 px and Omnibot 112 px, sized to sit well beside people rather
than at true scale. The page shows them at 2x with pixelated rendering, an integer scale that fits the narrowest
card (192 px of at least 222), every card's figure box the same height so the feet share one floor line. Brian stands beside his INK & PAPER paragraph rather than in the staff grid,
because he is not one of ours.
