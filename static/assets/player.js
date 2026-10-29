'use strict';
// Click-to-play JSSpeccy player for a game page's free demo. Nothing loads or makes a sound until
// Play is pressed. Reads the demo file, machine and JSSpeccy path from #emulator's data attributes.
// Based on the danielvaughan.github.io /tiger-gorilla/ and /wolf/ player.
//
// The demo is served obfuscated, never as a plain tape (site decisions D-16, D-18): demo.bin is
// 'DLXDEMO1' followed by the tape XORed with an xorshift32 keystream seeded by FNV-1a of DEMO_KEY.
// It is decoded here, in memory, just before JSSpeccy gets it. build.py and the toolkit's zx-website
// skill read DEMO_KEY from this line, so change it only by republishing every game.
const DEMO_KEY = '1ca6784172cdb4d187628239b5db4e8f'; // gitleaks:allow (public by design, D-18)
(function () {
  const host = document.getElementById('emulator');
  if (!host) return;
  const cover = document.getElementById('cover');
  const play = document.getElementById('play');
  const pause = document.getElementById('pause');
  const fullscreen = document.getElementById('fullscreen');
  const restart = document.getElementById('restart');
  const status = document.getElementById('status');
  const demo = host.dataset.demo;
  const machine = Number(host.dataset.machine) || 128;
  const title = host.dataset.title || 'the game';
  let api = null;
  let emulator = null;
  let loading = false;
  let scriptPromise = null;
  const held = new Map();

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

  function releaseKeys() {
    for (const event of held.values()) emulator?.keyboardHandler.keyupHandler(event);
    held.clear();
  }

  function pauseGame() {
    if (!emulator?.isRunning) return;
    releaseKeys();
    emulator.pause();
    pause.textContent = 'Resume';
    status.textContent = 'Paused. Press Resume to carry on.';
  }

  async function loadGame() {
    if (loading) return;
    loading = true;
    play.disabled = true;
    pause.disabled = fullscreen.disabled = restart.disabled = true;
    status.textContent = `Loading the ${title} demo…`;
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
      cover.hidden = true;
      emulator.start();
      host.focus();
      pause.textContent = 'Pause';
      pause.disabled = fullscreen.disabled = restart.disabled = false;
      status.textContent = `The ${title} demo is running. Click the screen to give it the keyboard; the keys are listed under Controls.`;
      host.dataset.state = 'running';
    } catch (error) {
      api?.exit();
      api = emulator = null;
      cover.hidden = false;
      play.textContent = 'Try again';
      status.textContent = 'Unable to start the demo. ' + error.message;
      host.dataset.state = 'error';
    } finally {
      loading = false;
      play.disabled = false;
    }
  }

  play.addEventListener('click', loadGame);
  restart.addEventListener('click', loadGame);
  pause.addEventListener('click', () => {
    if (!emulator) return;
    if (emulator.isRunning) pauseGame();
    else {
      emulator.start();
      pause.textContent = 'Pause';
      status.textContent = 'Playing. Click the screen to give it the keyboard.';
      host.focus();
    }
  });
  fullscreen.addEventListener('click', () => { api?.toggleFullscreen(); host.focus(); });
  host.addEventListener('pointerdown', () => host.focus());
  host.addEventListener('keydown', event => { if (!event.repeat) held.set(event.code, event); });
  host.addEventListener('keyup', event => held.delete(event.code));
  host.addEventListener('blur', releaseKeys);
  window.addEventListener('blur', pauseGame);
  document.addEventListener('visibilitychange', () => { if (document.hidden) pauseGame(); });
})();
