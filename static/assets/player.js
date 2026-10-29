'use strict';
// Click-to-play JSSpeccy player for a game page. Nothing loads or makes a sound until Play is
// pressed. Reads the tape, machine and JSSpeccy path from #emulator's data attributes.
// Based on the danielvaughan.github.io /tiger-gorilla/ and /wolf/ player.
(function () {
  const host = document.getElementById('emulator');
  if (!host) return;
  const cover = document.getElementById('cover');
  const play = document.getElementById('play');
  const pause = document.getElementById('pause');
  const fullscreen = document.getElementById('fullscreen');
  const restart = document.getElementById('restart');
  const status = document.getElementById('status');
  const tape = host.dataset.tap;
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
    status.textContent = `Loading ${title}…`;
    try {
      releaseKeys();
      api?.exit();
      emulator = null;
      host.replaceChildren();
      await loadScript();
      const response = await fetch(tape);
      if (!response.ok) throw new Error('The game tape could not be loaded.');
      api = window.JSSpeccy(host, {machine: machine, zoom: 1, autoLoadTapes: true,
        autoStart: false, uiEnabled: false, sandbox: true});
      // The vendored JSSpeccy exposes its emulator; see jsspeccy/PATCH.md.
      emulator = window.__zxEmu;
      await Promise.race([
        new Promise(resolve => api.onReady(resolve)),
        new Promise((_, reject) => setTimeout(() => reject(new Error('The emulator took too long to start.')), 20000))
      ]);
      await emulator.openUrl(tape);
      emulator.setKeyboardEventRoot(host);
      cover.hidden = true;
      emulator.start();
      host.focus();
      pause.textContent = 'Pause';
      pause.disabled = fullscreen.disabled = restart.disabled = false;
      status.textContent = `${title} is running. Click the screen to give it the keyboard; the keys are listed under Controls.`;
      host.dataset.state = 'running';
    } catch (error) {
      api?.exit();
      api = emulator = null;
      cover.hidden = false;
      play.textContent = 'Try again';
      status.textContent = 'Unable to start the game. ' + error.message;
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
