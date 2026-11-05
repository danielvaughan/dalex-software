/* The spec desk (D-37): a conversation with Malcolm, from the Dalex Studio's spec desk service.
   Vanilla JavaScript, no third-party code, no cookies or storage: the session id lives in this page only. */
(function () {
  'use strict';
  var desk = document.getElementById('spec-desk');
  if (!desk || !window.fetch) return;
  var api = desk.getAttribute('data-api').replace(/\/$/, '');
  var people = desk.getAttribute('data-people');
  var NAMES = { malcolm: 'Malcolm Winstanley', colin: 'Colin Ollerenshaw', mo: 'Mo Greenhalgh' };
  var ROLES = { malcolm: 'Commissioning editor', colin: 'Game designer', mo: 'Producer' };
  var log = document.getElementById('desk-log');
  var form = document.getElementById('desk-form');
  var box = document.getElementById('desk-text');
  var status = document.getElementById('desk-status');
  var start = document.getElementById('desk-start');
  var tools = document.getElementById('desk-tools');
  var sid = null, title = 'my-game', busy = false;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function call(method, path, body, timeout) {
    var ctl = window.AbortController ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, timeout || 120000) : null;
    var opts = { method: method, headers: {}, signal: ctl ? ctl.signal : undefined, credentials: 'omit', cache: 'no-store' };
    if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    return fetch(api + path, opts).then(function (r) {
      if (timer) clearTimeout(timer);
      return r;
    }, function (err) { if (timer) clearTimeout(timer); throw err; });
  }

  function setBusy(on, words) {
    busy = on;
    desk.setAttribute('aria-busy', on ? 'true' : 'false');
    status.textContent = words || '';
    Array.prototype.forEach.call(desk.querySelectorAll('button, textarea'), function (b) {
      if (b.id !== 'desk-start') b.disabled = on || !sid;
    });
  }

  function closed(words) {
    desk.className = 'desk closed';
    desk.innerHTML = '';
    var p = el('p', 'desk-closed', words || 'The spec desk is closed for now. Malcolm will be back soon.');
    var q = el('p');
    q.innerHTML = 'In the meantime, <a href="../../games/">play the games</a> or read <a href="../../book/">the Book</a>.';
    desk.appendChild(p);
    desk.appendChild(q);
  }

  function said(who, lines) {
    var art = el('article', 'turn turn-' + (who === 'visitor' ? 'visitor' : 'desk'));
    if (who === 'visitor') {
      art.appendChild(el('p', 'turn-who', 'You'));
    } else {
      var head = el('header', 'turn-head');
      var img = el('img');
      img.src = people + who + '.png';
      img.alt = 'Portrait of ' + (NAMES[who] || who);
      img.width = 64; img.height = 64;
      head.appendChild(img);
      var name = el('p', 'turn-who');
      name.appendChild(el('strong', null, NAMES[who] || who));
      name.appendChild(document.createTextNode(' ' + (ROLES[who] || '')));
      head.appendChild(name);
      art.appendChild(head);
    }
    lines.forEach(function (line) { art.appendChild(el('p', null, line)); });
    return art;
  }

  function show(reply) {
    var art = said(reply.speaker, reply.lines || []);
    if (reply.questions && reply.questions.length) {
      var ol = el('ol', 'questions');
      reply.questions.forEach(function (q) {
        var li = el('li');
        li.value = q.n;
        li.appendChild(el('p', 'q', q.question));
        var rec = el('p', 'rec');
        rec.appendChild(el('span', 'rec-label', q.own ? 'For example: ' : 'Malcolm suggests: '));
        rec.appendChild(document.createTextNode(q.recommendation));
        li.appendChild(rec);
        if (!q.own) {
          var b = el('button', 'button', 'Accept');
          b.type = 'button';
          b.setAttribute('aria-label', 'Accept the suggestion for question ' + q.n);
          b.addEventListener('click', function () { send({ answers: (function (o) { o[q.n] = 'yes'; return o; })({}) }, 'Question ' + q.n + ': accepted'); });
          li.appendChild(b);
        } else {
          li.appendChild(el('p', 'small', 'This one needs your own words: type it below, starting with ' + q.n + '.'));
        }
        ol.appendChild(li);
      });
      art.appendChild(ol);
    }
    if (reply.done) {
      var next = el('p', 'next');
      next.innerHTML = 'That is the brief for now. Download your notes, then read <a href="../../book/">the Book</a> to see how a brief becomes a Spectrum game.';
      art.appendChild(next);
    }
    log.appendChild(art);
    var h = art.querySelector('.turn-who');
    if (h) { h.tabIndex = -1; h.focus({ preventScroll: false }); }
  }

  function send(message, echo) {
    if (busy || !sid) return;
    log.appendChild(said('visitor', [echo]));
    setBusy(true, 'Malcolm is thinking…');
    call('POST', '/v1/sessions/' + sid + '/messages', message).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, status: r.status, d: d }; });
    }).then(function (x) {
      setBusy(false);
      if (x.status === 404) { closed('Your session has ended. Reload the page to start a new brief.'); return; }
      if (!x.ok) { status.textContent = (x.d && x.d.line) || 'Something went wrong. Please try again.'; return; }
      show(x.d.reply);
      box.focus();
    }).catch(function () { setBusy(false); status.textContent = 'The desk did not answer. Please try again in a moment.'; });
  }

  function begin() {
    start.disabled = true;
    setBusy(true, 'Malcolm is coming to the desk…');
    call('POST', '/v1/sessions').then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, d: d }; });
    }).then(function (x) {
      if (!x.ok) { setBusy(false); closed((x.d && x.d.line) || undefined); return; }
      sid = x.d.id;
      start.hidden = true;
      form.hidden = false;
      tools.hidden = false;
      setBusy(false);
      show(x.d.reply);
    }).catch(function () { closed(); });
  }

  function download() {
    if (!sid) return;
    call('GET', '/v1/sessions/' + sid + '/notes.md').then(function (r) {
      if (!r.ok) throw new Error('notes');
      return r.text();
    }).then(function (text) {
      var m = /^# (.+?): spec notes/m.exec(text);
      if (m) title = m[1].toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'my-game';
      var url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }));
      var a = el('a');
      a.href = url; a.download = title + '-spec-notes.md';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      status.textContent = 'Your notes are downloaded as ' + a.download + '.';
    }).catch(function () { status.textContent = 'The notes could not be downloaded. Please try again.'; });
  }

  function forget() {
    if (!sid) return;
    call('DELETE', '/v1/sessions/' + sid).then(function () {
      sid = null;
      closed('Your brief is deleted. Reload the page to start a new one.');
    }).catch(function () { status.textContent = 'The brief could not be deleted just now. Please try again.'; });
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var text = box.value.trim();
    if (!text) return;
    box.value = '';
    send({ text: text }, text);
  });
  box.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); form.requestSubmit ? form.requestSubmit() : form.submit(); }
  });
  document.getElementById('desk-notes').addEventListener('click', download);
  document.getElementById('desk-delete').addEventListener('click', forget);
  start.addEventListener('click', begin);

  status.textContent = 'Checking the desk is open…';
  call('GET', '/v1/health', undefined, 5000).then(function (r) {
    if (!r.ok) throw new Error('health');
    return r.json();
  }).then(function (h) {
    if (!h.ok) throw new Error('health');
    desk.className = 'desk open';
    start.hidden = false;
    status.textContent = '';
  }).catch(function () { closed(); });
})();
