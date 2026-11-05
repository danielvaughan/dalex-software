// The spec desk page in a real browser (D-37, SD-W2, SD-W3, SD-W5). Run by hand; CI keeps to the standard-library
// tests. Needs Node with the playwright package and its Chromium, a local build pointed at a loopback desk, and the
// Studio's spec desk service started without the model:
//
//   (dalex-studio) .venv/bin/python devtools/dalex/spec_desk_service.py --no-model --port 18791 \
//                  --origin http://127.0.0.1:8000 --root /tmp/desk-check
//   (here)         python3 build.py --config <site.json with "spec_desk_api": "http://127.0.0.1:18791"> --out /tmp/desk-site
//                  python3 -m http.server 8000 --bind 127.0.0.1 --directory /tmp/desk-site
//                  node tools/spec_desk_check.mjs http://127.0.0.1:8000/studio/spec-desk/ OUT_DIR [--closed]
//
// With --closed (the service stopped) it checks the page shows the closed state within 5 s. Otherwise it plays a brief
// from the first round to the downloaded notes, by keyboard only, at desktop and phone widths, and fails on any
// console error, sideways scroll, missing portrait alt text or questions outside a list. Screenshots go to OUT_DIR.
import { chromium } from 'playwright';
import { mkdirSync, readFileSync } from 'node:fs';

const [url, out = '.', flag] = process.argv.slice(2);
if (!url) { console.error('usage: node tools/spec_desk_check.mjs PAGE_URL [OUT_DIR] [--closed]'); process.exit(2); }
mkdirSync(out, { recursive: true });
const fail = (msg) => { console.error('FAIL ' + msg); process.exitCode = 1; };

async function run(width, height, label) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width, height }, acceptDownloads: true });
  const page = await context.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(url);

  if (flag === '--closed') {
    const t0 = Date.now();
    await page.waitForSelector('.desk.closed', { timeout: 6000 }).catch(() => fail(`${label}: no closed state`));
    const took = Date.now() - t0;
    if (took > 5500) fail(`${label}: closed state took ${took} ms`);
    await page.screenshot({ path: `${out}/closed-${label}.png`, fullPage: true });
    console.log(`${label}: closed state shown in ${took} ms`);
    await browser.close();
    return;
  }

  await page.waitForSelector('#desk-start:not([hidden])', { timeout: 6000 });
  // Keyboard only: Tab to the start button and press Enter.
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press('Tab');
    if (await page.evaluate(() => document.activeElement && document.activeElement.id === 'desk-start')) break;
  }
  if (!(await page.evaluate(() => document.activeElement.id === 'desk-start'))) fail(`${label}: start button not reachable by Tab`);
  await page.keyboard.press('Enter');
  await page.waitForSelector('.turn-desk ol.questions li', { timeout: 30000 });
  const portrait = await page.$eval('.turn-desk .turn-head img', (img) => img.alt);
  if (!/^Portrait of Malcolm Winstanley$/.test(portrait)) fail(`${label}: portrait alt is ${JSON.stringify(portrait)}`);
  const who = await page.$eval('.turn-desk .turn-who strong', (n) => n.textContent);
  if (who !== 'Malcolm Winstanley') fail(`${label}: speaker is ${who}`);

  // Round 1 needs the visitor's own words: type them into the box and press Enter.
  await page.focus('#desk-text');
  await page.keyboard.type('1 You are a lighthouse keeper keeping the lamp lit through a stormy night.');
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => document.querySelectorAll('.turn-desk').length >= 2, null, { timeout: 30000 });
  // Accept the first suggestion with the keyboard: Tab to its Accept button.
  await page.focus('#desk-text');
  for (let i = 0; i < 80; i++) {
    await page.keyboard.press('Shift+Tab');
    const label2 = await page.evaluate(() => document.activeElement.getAttribute('aria-label') || '');
    if (label2.startsWith('Accept the suggestion')) break;
  }
  const chosen = await page.evaluate(() => document.activeElement.getAttribute('aria-label') || '');
  if (!chosen.startsWith('Accept the suggestion')) fail(`${label}: no Accept button reachable by keyboard`);
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => document.querySelectorAll('.turn-desk').length >= 3, null, { timeout: 30000 });
  await page.screenshot({ path: `${out}/conversation-${label}.png`, fullPage: true });

  const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  if (wide) fail(`${label}: the page scrolls sideways`);

  // Download the notes by keyboard.
  await page.focus('#desk-notes');
  const [download] = await Promise.all([page.waitForEvent('download', { timeout: 15000 }), page.keyboard.press('Enter')]);
  const path = `${out}/notes-${label}.md`;
  await download.saveAs(path);
  const notes = readFileSync(path, 'utf8');
  if (!notes.includes('| D-01 |') || !notes.includes('lighthouse')) fail(`${label}: notes lack D-01`);
  if (!/-spec-notes\.md$/.test(download.suggestedFilename())) fail(`${label}: notes named ${download.suggestedFilename()}`);

  // Delete the brief.
  await page.focus('#desk-delete');
  await page.keyboard.press('Enter');
  await page.waitForSelector('.desk.closed', { timeout: 10000 });
  const cookies = await context.cookies();
  if (cookies.length) fail(`${label}: cookies set: ${cookies.map((c) => c.name)}`);
  const stored = await page.evaluate(() => localStorage.length + sessionStorage.length);
  if (stored) fail(`${label}: browser storage used`);
  if (errors.length) fail(`${label}: console errors: ${errors.join(' | ')}`);
  console.log(`${label}: ${process.exitCode ? 'problems above' : 'ok'} (notes ${notes.length} bytes, ${download.suggestedFilename()})`);
  await browser.close();
}

await run(1280, 900, 'desktop');
await run(390, 844, 'phone');
