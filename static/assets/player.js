'use strict';
// Click-to-play JSSpeccy player for a game page's free demo. Nothing loads or makes a sound until
// Play is pressed. Reads the demo file, machine and JSSpeccy path from #emulator's data attributes.
// Based on the danielvaughan.github.io /tiger-gorilla/ and /wolf/ player.
//
// The demo is served obfuscated, never as a plain tape (site decisions D-16, D-18): demo.bin is
// 'DLXDEMO1' followed by the tape XORed with an xorshift32 keystream seeded by FNV-1a of DEMO_KEY.
// It is decoded here, in memory, just before JSSpeccy gets it. build.py and the toolkit's zx-website
// skill read DEMO_KEY from this line, so change it only by republishing every game.
//
// Keys (D-21): while the game is loading or running and the screen has focus, every key except Tab,
// Escape, the function keys and Cmd/Meta shortcuts is kept from the page (preventDefault in the capture
// phase), so Space, the arrows, Page Up/Down, Home/End and Backspace never scroll or navigate. Tab and
// Escape are stopped before JSSpeccy sees them (it would preventDefault them too): Tab moves focus out
// of the game and Escape releases it. Paused, or with focus elsewhere, the page keys work as usual.
//
// Touch (D-22): #pad holds on-screen buttons whose data-keys name Spectrum keys from the game's own
// controls list; a press is keydown, a release, cancel or lost capture is keyup, held with pointer capture.
const DEMO_KEY = '1ca6784172cdb4d187628239b5db4e8f'; // gitleaks:allow (public by design, D-18)
(function () {
  const host = document.getElementById('emulator');
  if (!host) return;
  const stage = document.getElementById('stage') || host.parentElement;
  const screen = host.closest('.screen') || host;
  const cover = document.getElementById('cover');
  const play = document.getElementById('play');
  const pause = document.getElementById('pause');
  const fullscreen = document.getElementById('fullscreen');
  const restart = document.getElementById('restart');
  const status = document.getElementById('status');
  const pad = document.getElementById('pad');
  const padToggle = document.getElementById('pad-toggle');
  const demo = host.dataset.demo;
  const machine = Number(host.dataset.machine) || 128;
  const title = host.dataset.title || 'the game';
  const LEAVE = 'Press Tab to leave the game, or Escape to release the keyboard.';
  let api = null;
  let emulator = null;
  let loading = false;
  let scriptPromise = null;
  const held = new Map();        // physical keys held down: code -> event
  const touchHeld = new Map();   // on-screen keys held down: Spectrum key name -> press count

  // ------------------------------------------------------------------ state
  function setState(s) { host.dataset.state = s; }
  function running() { return !!emulator?.isRunning; }
  function hasFocus() { return host.contains(document.activeElement); }
  function say(text) { status.textContent = text; }

  function loadScript() {
    if (window.JSSpeccy) return Promise.resolve();
    if (!scriptPromise) {
      scriptPromise = new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = host.dataset.jsspeccy;
        s.onload = resolve;
        s.onerror = () => reject(new Error('The emulator could not be loaded.'));
        document.head.appendChild(s);
      });
    }
    return scriptPromise;
  }

  function decodeDemo(buffer) {
    const magic = 'DLXDEMO1';
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < magic.length; i++) {
      if (bytes[i] !== magic.charCodeAt(i)) throw new Error('The demo file is damaged.');
    }
    let h = 0x811c9dc5;
    for (let i = 0; i < DEMO_KEY.length; i++) h = Math.imul(h ^ DEMO_KEY.charCodeAt(i), 0x01000193) >>> 0;
    let s = h || 1;
    const out = new Uint8Array(bytes.length - magic.length);
    for (let i = 0; i < out.length; i++) {
      s = (s ^ (s << 13)) >>> 0;
      s = (s ^ (s >>> 17)) >>> 0;
      s = (s ^ (s << 5)) >>> 0;
      out[i] = bytes[i + magic.length] ^ (s >>> 24);
    }
    // A tape starts with a 19-byte header block (length 0x0013); anything else is a bad decode.
    if (out[0] !== 0x13 || out[1] !== 0x00) throw new Error('The demo file could not be read.');
    return out.buffer;
  }

  // ------------------------------------------------------------------ Spectrum keys from the pad
  // JSSpeccy's standard keyboard map reads keyCode: letters and digits are their ASCII codes.
  const KEYCODE = {SPACE: 32, ENTER: 13};
  function keyCode(name) {
    if (KEYCODE[name]) return KEYCODE[name];
    return /^[A-Z0-9]$/.test(name) ? name.charCodeAt(0) : 0;
  }
  function sendKey(name, down) {
    const code = keyCode(name);
    if (!code || !emulator) return;
    // Called directly, as the harness does (PATCH.md), so it works whether or not the listeners are bound.
    const ev = {keyCode: code, key: '', code: '', metaKey: false, repeat: false, preventDefault() {}};
    if (down) emulator.keyboardHandler.keydownHandler(ev);
    else emulator.keyboardHandler.keyupHandler(ev);
  }
  function touchDown(name) {
    const n = touchHeld.get(name) || 0;
    touchHeld.set(name, n + 1);
    if (!n) sendKey(name, true);
  }
  function touchUp(name) {
    const n = touchHeld.get(name) || 0;
    if (n <= 1) { touchHeld.delete(name); if (n) sendKey(name, false); }
    else touchHeld.set(name, n - 1);
  }

  function releaseKeys() {
    for (const event of held.values()) emulator?.keyboardHandler.keyupHandler(event);
    held.clear();
    for (const name of touchHeld.keys()) sendKey(name, false);
    touchHeld.clear();
    pad?.querySelectorAll('.held').forEach(b => b.classList.remove('held'));
  }

  // ------------------------------------------------------------------ play, pause, resume
  function focusGame() {
    host.focus({preventScroll: true});
  }

  function showScreen() {
    // The whole screen (and the pad with it, when that fits) in view.
    const r = stage.getBoundingClientRect();
    const target = r.height <= window.innerHeight ? stage : screen;
    target.scrollIntoView({block: target === stage ? 'center' : 'start', behavior: 'instant'});
  }

  function pauseGame(why) {
    if (!running()) return;
    releaseKeys();
    emulator.pause();
    setState('paused');
    pause.textContent = 'Resume';
    say(why || 'Paused. Press Resume, or click the screen and press a key, to carry on.');
  }

  function resumeGame() {
    if (!emulator || running()) return;
    emulator.start();
    setState('running');
    pause.textContent = 'Pause';
    focusGame();
    say(`Playing. ${LEAVE}`);
  }

  async function loadGame() {
    if (loading) return;
    loading = true;
    // Focus the screen first, so the keyboard is the game's from the moment Play is pressed (the Play
    // button is about to be disabled, which would drop focus to the page and let Space scroll it).
    showScreen();
    focusGame();
    setState('loading');
    play.disabled = true;
    pause.disabled = fullscreen.disabled = restart.disabled = true;
    say(`Loading the ${title} demo…`);
    try {
      releaseKeys();
      api?.exit();
      emulator = null;
      host.replaceChildren();
      await loadScript();
      const response = await fetch(demo);
      if (!response.ok) throw new Error('The demo could not be loaded.');
      const tape = decodeDemo(await response.arrayBuffer());
      api = window.JSSpeccy(host, {machine: machine, zoom: 1, autoLoadTapes: true,
        autoStart: false, uiEnabled: false, sandbox: true});
      // The vendored JSSpeccy exposes its emulator; see jsspeccy/PATCH.md.
      emulator = window.__zxEmu;
      await Promise.race([
        new Promise(resolve => api.onReady(resolve)),
        new Promise((_, reject) => setTimeout(() => reject(new Error('The emulator took too long to start.')), 20000))
      ]);
      // JSSpeccy picks its loader by file name; the decoded tape never touches a URL.
      await emulator.getFileOpener('demo.tap')(tape);
      emulator.setKeyboardEventRoot(host);
      // JSSpeccy makes its own box a second tab stop; one stop (the screen) is enough, and Tab must leave.
      for (const el of host.querySelectorAll('[tabindex]')) el.tabIndex = -1;
      cover.hidden = true;
      emulator.start();
      setState('running');
      focusGame();
      showScreen();
      pause.textContent = 'Pause';
      pause.disabled = fullscreen.disabled = restart.disabled = false;
      say(`The ${title} demo is running; the keys are listed under Controls. ${LEAVE}`);
    } catch (error) {
      api?.exit();
      api = emulator = null;
      cover.hidden = false;
      play.textContent = 'Try again';
      say('Unable to start the demo. ' + error.message);
      setState('error');
    } finally {
      loading = false;
      play.disabled = false;
    }
  }

  // ------------------------------------------------------------------ the keyboard
  function passThrough(event) {
    // Keys the page always keeps: leaving the game, function keys and system shortcuts.
    return event.key === 'Tab' || event.key === 'Escape' || /^F\d{1,2}$/.test(event.key) || event.metaKey;
  }

  function onKey(event) {
    if (!hasFocus()) return;
    const active = loading || running();
    if (event.key === 'Tab' || event.key === 'Escape') {
      event.stopPropagation();            // JSSpeccy would preventDefault them and trap the keyboard
      if (event.type === 'keydown' && event.key === 'Escape') {
        releaseKeys();
        host.blur();
      }
      return;
    }
    if (!active) {
      // Paused with focus on the screen: a game key carries on playing (and does not scroll the page).
      if (event.type === 'keydown' && emulator && host.dataset.state === 'paused' && !passThrough(event)
          && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        resumeGame();
      }
      return;
    }
    if (passThrough(event)) return;
    event.preventDefault();               // Space, arrows, PageUp/Down, Home/End, Backspace, letters...
    if (event.type === 'keydown' && !event.repeat) held.set(event.code, event);
    if (event.type === 'keyup') held.delete(event.code);
  }

  for (const type of ['keydown', 'keyup', 'keypress']) host.addEventListener(type, onKey, true);

  host.addEventListener('focusin', () => {
    if (running()) say(`Playing. ${LEAVE}`);
  });
  host.addEventListener('focusout', event => {
    if (host.contains(event.relatedTarget)) return;
    releaseKeys();
    if (running()) say('The keyboard is back with the page. Click the screen, or Tab back to it, to play.');
  });

  play.addEventListener('click', loadGame);
  restart.addEventListener('click', loadGame);
  pause.addEventListener('click', () => {
    if (!emulator) return;
    if (running()) pauseGame();
    else resumeGame();
  });
  fullscreen.addEventListener('click', () => {
    // The wrapper holds the screen and the touch pad, so the pad comes too.
    if (document.fullscreenElement) document.exitFullscreen?.();
    else (stage.requestFullscreen || stage.webkitRequestFullscreen)?.call(stage)?.catch?.(() => {});
    focusGame();
  });
  document.addEventListener('fullscreenchange', () => {
    fullscreen.textContent = document.fullscreenElement ? 'Exit full screen' : 'Full screen';
    if (emulator) focusGame();
  });
  host.addEventListener('pointerdown', () => {
    if (host.dataset.state === 'paused') resumeGame();
    focusGame();
  });
  window.addEventListener('blur', () => pauseGame('Paused while the window was in the background. Press Resume, or click the screen, to carry on.'));
  document.addEventListener('visibilitychange', () => { if (document.hidden) pauseGame(); });

  // ------------------------------------------------------------------ the touch pad
  if (!pad) return;
  let padForced = null;            // true/false once the visitor uses the toggle; null = automatic

  function showPad(on) {
    pad.hidden = !on;
    stage.classList.toggle('with-pad', on);
    if (padToggle) {
      padToggle.setAttribute('aria-pressed', String(on));
      padToggle.textContent = on ? 'Hide touch controls' : 'Show touch controls';
    }
  }
  const coarse = window.matchMedia?.('(pointer: coarse)');
  showPad(!!coarse?.matches);
  window.addEventListener('touchstart', () => { if (padForced === null && pad.hidden) showPad(true); },
    {passive: true, capture: true});
  window.addEventListener('keydown', event => {
    // A physical keyboard is in use: the pad gets out of the way (unless the visitor asked for it).
    if (padForced === null && !pad.hidden && event.isTrusted && !pad.contains(event.target)
        && !passThrough(event)) showPad(false);
  }, true);
  padToggle?.addEventListener('click', () => {
    padForced = pad.hidden;
    showPad(padForced);
  });

  const buzz = () => { try { navigator.vibrate?.(8); } catch (e) { /* not supported */ } };
  const keysOf = el => (el.dataset.keys || '').split(' ').filter(Boolean);

  // Action buttons: each holds its key(s) while pressed; several fingers can hold several buttons.
  for (const btn of pad.querySelectorAll('.pad-btn')) {
    btn.addEventListener('pointerdown', event => {
      event.preventDefault();
      if (!emulator) return;
      if (host.dataset.state === 'paused') resumeGame();
      btn.setPointerCapture?.(event.pointerId);
      if (btn.classList.contains('held')) return;
      btn.classList.add('held');
      keysOf(btn).forEach(touchDown);
      buzz();
    });
    const up = () => {
      if (!btn.classList.contains('held')) return;
      btn.classList.remove('held');
      keysOf(btn).forEach(touchUp);
    };
    for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) btn.addEventListener(type, up);
    // A keyboard or switch user activating the button with Enter/Space: a short tap of the key.
    btn.addEventListener('click', event => {
      if (event.detail !== 0 || !emulator) return;
      keysOf(btn).forEach(touchDown);
      setTimeout(() => keysOf(btn).forEach(touchUp), 150);
    });
  }

  // The direction pad: one finger on it picks a direction (or a diagonal, as two keys, where the game
  // drives diagonally) from where it is, and follows the finger as it slides.
  const dpad = pad.querySelector('.dpad');
  if (dpad) {
    const dirs = {};
    for (const b of dpad.querySelectorAll('[data-dir]')) dirs[b.dataset.dir] = b;
    const eight = dpad.dataset.diagonals === 'true';
    let pointer = null;
    let current = [];
    const pick = event => {
      const r = dpad.getBoundingClientRect();
      const dx = event.clientX - (r.left + r.width / 2);
      const dy = event.clientY - (r.top + r.height / 2);
      if (Math.hypot(dx, dy) < r.width * 0.12) return [];
      const a = Math.atan2(dy, dx) * 180 / Math.PI;           // 0 right, 90 down
      const near = (target, span) => Math.abs(((a - target + 540) % 360) - 180) <= span;
      const out = [];
      if (eight) {
        if (near(0, 67.5)) out.push('right');
        if (near(180, 67.5)) out.push('left');
        if (near(90, 67.5)) out.push('down');
        if (near(-90, 67.5)) out.push('up');
      } else {
        out.push(near(0, 45) ? 'right' : near(180, 45) ? 'left' : near(90, 45) ? 'down' : 'up');
      }
      return out.filter(d => dirs[d]);
    };
    const set = next => {
      for (const d of current) if (!next.includes(d)) { dirs[d].classList.remove('held'); keysOf(dirs[d]).forEach(touchUp); }
      for (const d of next) if (!current.includes(d)) { dirs[d].classList.add('held'); keysOf(dirs[d]).forEach(touchDown); buzz(); }
      current = next;
    };
    dpad.addEventListener('pointerdown', event => {
      event.preventDefault();
      if (!emulator || pointer !== null) return;
      if (host.dataset.state === 'paused') resumeGame();
      pointer = event.pointerId;
      dpad.setPointerCapture?.(event.pointerId);
      set(pick(event));
    });
    dpad.addEventListener('pointermove', event => { if (event.pointerId === pointer) set(pick(event)); });
    const end = event => { if (event.pointerId === pointer) { pointer = null; set([]); } };
    for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) dpad.addEventListener(type, end);
    for (const b of Object.values(dirs)) {
      b.addEventListener('click', event => {
        if (event.detail !== 0 || !emulator) return;
        keysOf(b).forEach(touchDown);
        setTimeout(() => keysOf(b).forEach(touchUp), 150);
      });
    }
  }
  // No long-press menu, text selection or double-tap zoom on the pad.
  pad.addEventListener('contextmenu', event => event.preventDefault());
  pad.addEventListener('touchstart', event => event.preventDefault(), {passive: false});
  pad.addEventListener('mousedown', event => event.preventDefault());   // keep the keyboard on the screen
})();
