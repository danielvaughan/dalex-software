# Decisions

Routine decisions made while building the site, so the owner can overrule any of them.

## D-01 Generator: Python standard library, no Jinja2 or PyYAML

`build.py` uses only the standard library (`json`, `html`, `shutil`). The pages are few and fixed,
so templates are Python functions with `html.escape`. CI needs no installs, and the owner's Mac and
Ubuntu machines build it with any Python 3.11+.

## D-02 Configuration is `site.json`, not YAML

The brief allowed YAML or JSON. JSON keeps the build and the toolkit's publisher on the standard
library and lets the publisher rewrite the file without losing anything. Fields per game: `slug`,
`visible`, `order`, `featured`, optional `blurb` and `price_label`. (D-16 and D-19: `price_label` is gone and
each game has a `demo` record.)

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

Superseded in part by D-16 to D-19: no tape, price, review PDF, inlay, advert or poster is shown, and the quote and
verdict skip price sentences.

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

## D-14 The Studio film

The owner asked for a five-minute documentary of how the studio works, naming no customers, for this site
(dalex-studio#104). It is published on its own page, `studio/`, linked from the home page, the About page and the
main navigation. The film, its poster and its WebVTT captions are made by the Studio
(`record_studio_tour.py --tour documentary`, then `check_documentary.py`) and committed under `static/media/`, which
`build.py` already copies, so the site stays standard-library only and nothing is hosted by a third party. The page
uses `<video controls preload="none">` with the poster and a default English captions track, never autoplays, and
prints the captions as a transcript for anyone who would rather read. The MP4 is H.264/AAC with `+faststart` and is
re-made, not edited here, whenever the Studio changes. The Studio checked it before publication: public fixture data
only on screen (a frame every 2 s inspected), every line confirmed by Whisper, and a deny-list over the script,
captions and sidecar. `tests/test_studio.py` repeats the deploy and deny-list checks on every build.

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

## D-16 Free demo in the browser, no downloads (owner, 2026-10-29)

The owner decided that visitors play a free demo of each game in the browser and that nothing is offered for
download. Every game page loses its tape download, size and SHA-256 line; the games list loses "Download the tape";
the home page intro and the About page no longer promise downloadable tapes. The full release tapes are no longer
in this repository's tree (removed by an ordinary commit) and are never deployed; they stay only in each game's
private repository. Old commits still contain them: rewriting history is out of scope and was raised with the
owner separately.

A paid route for the full tapes (a merchant-of-record store) was considered and is **deferred by the owner**:
there is no buy button, store link or shop wording on the site. Where a price used to appear the site says "Price
to be confirmed" (D-19).

Each `site.json` game entry records its demo: `"demo": {"milestone", "sha256", "contains"}`, or `null` for no demo.
`build.py` refuses a build where `site.json` and the published `game.json` disagree on the demo's sha256, or where
`demo.bin` does not decode to it. A game with a demo shows "Play the demo", a line saying what the demo contains,
and a note that the demo is an earlier milestone build. A game without one shows its cover with "Demo coming soon"
and no play button and loads no player script. The build copies only the cover, screen shots, licences and
`demo.bin` from a game folder, whatever else is there.

## D-17 Which tape is each game's demo

The demo is the earliest milestone tape that a milestone gate passed and that plays a sensible slice, never the
release tape. Each was checked against its gate: the gate's recorded sha256 equals the tape in the game
repository's `game/build/`. Gold Master's M1 is the model.

| Game | Demo | sha256 | Contains | Why |
| --- | --- | --- | --- | --- |
| Gold Master | `gold-master-m1.tap` (M1) | `f63311eaed9b03a6d40de63d82d42e708a8f55150181cbd0ed787e37636c48b6` | Level 1 of 4: the Production room, from the Design Doc to the Gold Master | M1 is "Production only: level 1 from title to shipped"; gate passed with issues, 2026-10-29 |
| Antigravity | `antigravity-m2.tap` (M2) | `cb2aaaaa78302e2c25ebc2b2267617bc1f051e67f0629ff3ee469d1675f95d83` | Sectors 1 to 3 of 10 | M1 (`ba0a928f…`, one sector, gate passed) would be the earliest, but its title screen prints its text scrambled (the game's own M1 verify screenshot shows the same), so the first thing a visitor saw would be a fault. M2, "Moving threats and mission", has a clean title and three of the release's ten sectors; gate passed, 2026-10-21 |
| WOLF | `wolf-m1.tap` (M1) | `f977ca08f76be13316a95f97976805e78999d7c523b93b665697c89045b74073` | January's session with Stevo | M1 is the session-1 vertical slice. Its first gate failed; a docs-only re-run under the game's ruling D-135 passed it with issues, so it qualifies, but the owner may prefer M2 |
| Wordris | `wordris-m1.tap` (M1) | `b2152833b7ff0c8c6f15cdfcefcbb72caab3a3fbba5c404a18addc9706b14ec7` | The core game from an early build | M1 is "the whole core loop": the earliest gated tape, but close to the full game (M2 and M3 added the pause and high-score sessions, the title pages and polish). Set `demo: null` if that gives away too much |
| Tiger Gorilla | none | | | Only M4, the release milestone, has a gate; M1 to M3 were built and verified but never gated |
| Mower Mayhem | none | | | M1 and M2 were playtested but never gated; the earliest gate is M4, already the complete game, and M5 (the earliest gated tape still in `build/`) is complete too |

The `zx-website` skill's default picks each game's gated M1 (D-20); Antigravity's M2 was chosen with `--demo 2` after the headless check showed M1's title.

## D-18 The demo is served obfuscated

A plain `.tap` is never served. `games/<slug>/demo.bin` is the 8-byte header `DLXDEMO1` followed by the demo tape
XORed with a keystream: xorshift32 (shifts 13, 17, 5) seeded with the 32-bit FNV-1a hash of `DEMO_KEY`, one key byte
(the top byte of the state) per tape byte. `DEMO_KEY` lives once, in `static/assets/player.js`; `build.py`, the
tests and the toolkit's `zx-website` skill read it from there. `player.js` fetches `demo.bin` only when Play is
pressed, decodes it in memory, checks it starts like a tape (a 19-byte header block), and hands the bytes to
JSSpeccy with `getFileOpener('demo.tap')`, so the decoded tape never has a URL. This is a cheap deterrent against
casual copying, not protection: anyone who reads `player.js` can decode it. Changing the key means republishing
every game.

## D-19 No prices anywhere (owner, 2026-10-29)

The owner: "The games should also not have prices anywhere at this point; it should be 'to be confirmed' or
similar, on reviews etc."

- Cards, the home page hero, the games list and game pages show "Price to be confirmed" where a price was.
  `game.json` no longer has a `price`, and `site.json`'s `price_label` override is withdrawn.
- Quotes skip any pull-quote that states or discusses a price and take the next one from the kit's
  `quotes.json`, verbatim from the same review: Gold Master "Lovely value at £2.99" became "Worth a go" (Kev
  Mallin); Wordris "this is a cracking cheapie" became "Clever, tidy and a touch unkind" (Mandy Pike).
- Review text: sentences that state or discuss a price are cut whole, as an editorial cut; the reviewers' words
  are never rewritten. Each of these verdicts is one sentence, so it is cut and only the score, the category bars
  and the quote remain: Antigravity ("a budget flier"), Mower Mayhem ("a fine figure for the price"), Wordris
  ("worth £1.99 of anyone's pocket money"). "Budget", "cheapie" and "value" talk count as discussing a price.
- Review PDFs: every one prints a price (the PRICE box, and some the text), so none is linked or deployed.
- The inlay (price on the back flap), advert (price strip) and poster (the poster shows "£2.99") are dropped, not
  cropped: a crop that leaves no price would be the cover painting, which the page already shows. The "In the
  shops" section is gone.
- `build.py` refuses a game whose shown text states a price, and the tests check every built text file for a
  currency amount (£, $, €, pence, quid, pounds, 99p, 3/6d) and that no tape, PDF or kit art is deployed.

## D-20 The publisher publishes demos only

The toolkit's `zx-website` skill (`publish_site.py`, zx-media-kit 0.15.1) writes only `demo.bin`, never a tape,
review PDF, inlay, advert or poster, and applies D-19's rules. Its demo comes from `--demo` (a tape, a milestone or
`none`), else this site's `site.json` record, else the earliest gated tape when that is the game's first
milestone (a later milestone is often the complete game, so it needs an explicit `--demo`). It refuses a demo that
has no passing gate, and refuses the release tape unless `--allow-full-demo` is given. All six games were
republished with it on 2026-10-29.

## D-21 The game keeps the keyboard while it has focus (owner, 2026-10-29)

The owner: "when i press space the browser scrolls." JSSpeccy's own handler already calls `preventDefault` while
it is bound, but it is bound only while the emulator runs, and only on the emulator box. A key reached the page
in three cases. While the demo loaded, the Play button was disabled, so focus fell to the page. While paused,
including the automatic pause when the window loses focus, JSSpeccy unbinds. And after a click elsewhere, focus
was no longer in the game. JSSpeccy also blocked Tab, so a keyboard user could not leave the game.

`player.js` now:

- **Play** scrolls the screen (and the touch pad when it fits) into view and focuses it *before* loading, so
  the keyboard is the game's from the first press.
- **While the game is loading or running and has focus**, a capture-phase listener on the emulator box
  `preventDefault`s every key on keydown, keyup and keypress (letters, digits, Space, Enter, the arrows,
  Shift and Ctrl as Caps and Symbol Shift, Page Up/Down, Home/End, Backspace). It leaves alone Tab, Escape,
  F1 to F12 and Cmd/Meta shortcuts.
- **Tab and Escape** are stopped before JSSpeccy sees them. Tab moves focus out of the game, and Escape
  releases it. The screen is one tab stop: JSSpeccy's inner box is taken out of the tab order.
- **Paused, or with focus elsewhere**, page keys work as usual. One exception: if the screen itself still has
  focus while paused, a game key resumes play instead of scrolling the page.
- **Focus and status**: a focus ring on the screen (`.screen:focus-within`); the status line says "Press Tab to
  leave the game, or Escape to release the keyboard" and says when the keyboard is back with the page.
- **Full screen** now enlarges the wrapper (`#stage`) holding the screen and the touch pad, not JSSpeccy's
  canvas box, and the same key rules apply there.

`tests/test_site.py` (`Player`) checks this statically. The playtest in
[playtest-2026-10-29.md](playtest-2026-10-29.md) checks it in Chromium.

## D-22 Touch controls (owner, 2026-10-29)

The owner: "the website should also have touch controls for the games so they can be played on a mobile
without a keyboard."

- **Where the layouts live**: each game's on-screen pad is a `touch` block in its `site.json` entry:
  `{"dpad": {direction: key}, "diagonals": bool, "buttons": [{"keys", "label"}]}`. It is not in `game.json`,
  which the publisher writes and replaces on every publish.
- **No invented controls**: `build.py` refuses a layout that uses a key the game's own controls list (on its page)
  does not name (`control_keys`). Tiger Gorilla's title menu keys, for example, are not on its page, so they are
  not on its pad.
- **The pad**: a direction pad, 8-way where the game moves diagonally with two keys (Mower Mayhem, Antigravity's
  thrusters), and action buttons. The first button (SPACE in every game) is the large start/fire button.
  - Every button is a real `<button>` with an `aria-label` naming its key and job, and shows a pictogram or a
    short word plus the key. Targets are at least 52 px.
  - A press is a JSSpeccy keydown and a release, cancel or lost pointer capture is a keyup. Pointer capture means
    a finger that slides off still releases, and several fingers hold several buttons (a direction and fire
    together).
  - Keyboard or switch activation of a button taps its key. Light haptics (`navigator.vibrate`) are used where
    supported.
  - The pad has `touch-action: none`, no text selection and no long-press menu, so it never scrolls or zooms the
    page.
- **When it shows**: automatically on a coarse pointer or at the first touch, and hidden again when a physical
  keyboard is used. "Show touch controls" in the toolbar turns it on or off for anyone. With no touch layout,
  the page says the demo needs a keyboard.
- **Landscape and full screen**: on a phone held sideways, and in full screen in landscape, the direction pad
  sits left of the screen and the buttons right. Full screen takes the wrapper, so the pad comes with it.

## D-23 Single-level demos; Tiger Gorilla and Mower Mayhem demos (owner, 2026-10-29)

The owner asked first for Tiger Gorilla and Mower Mayhem demos ("There should also be tiger gorilla and mower
mayhem demos"), then decided: "all games on the website should be single level demos." This overrides D-17's
rule that a demo is a gated milestone tape.

- **Each game's demo will be a demo build**: the release source built with the game's demo flag, stopping after
  level 1 with an end-of-demo card, as `game/build/<slug>-demo.tap` in the game's repository. Those builds are
  being made in the game repositories.
- **Publishing**: the toolkit's `zx-website` skill (zx-media-kit 0.16.0) takes that tape by default, ahead of
  `site.json` and the milestone tapes. It needs no gate, refuses the release tape, and records the sha256 and
  `source_tape`. The page note says "Level 1 demo" (with the level's name when the build gives one) and "The demo
  is the first level of the game" in place of the "earlier milestone build" line.
- **Until those tapes arrive**: the current four demos stay as they are, and Tiger Gorilla and Mower Mayhem still
  say "Demo coming soon". A skipped site test (`test_every_demo_is_a_single_level_demo_build`) is enabled once
  every game has published its demo build.
- **Milestone tapes looked at first** (superseded, for the record): Tiger Gorilla M1
  (`c50b0ed4…`, "vertical slice": zone 1 level 1) and M2 (`52fc73cf…`, "zone 1 complete") and Mower Mayhem M1
  (`2eda6d06…`, "vertical slice, Lawn 1 complete").
  - Each has a verify PASS on its current tape and an agent playtest with no open severity-1 finding, but no
    milestone gate.
  - Tiger Gorilla M2 loaded, started and played for a minute in headless JSSpeccy.
  - Mower Mayhem M1 steers like a tank (O/P turn, Q/A speed), not with the direct drive its page's controls
    describe.

  None was published.
