// Screen shots open full size in a lightbox (D-47, dev preview). Without script each picture is a plain link to
// the full-size image. With it, a link opens a dialog: "Image 2 of 6", the caption, Previous and Next buttons,
// the arrow keys to move, Esc or Close to leave, and focus goes back to the picture you opened. Stores nothing.
(function () {
  'use strict';
  var links = Array.prototype.slice.call(document.querySelectorAll('a.zoom[data-gallery]'));
  if (!links.length || typeof HTMLDialogElement !== 'function') return;

  var dlg = document.createElement('dialog');
  dlg.className = 'lightbox';
  dlg.setAttribute('aria-labelledby', 'lightbox-count');
  dlg.innerHTML =
    '<div class="lightbox-in">' +
    '<p id="lightbox-count" class="kicker" aria-live="polite"></p>' +
    '<figure><img class="px" alt=""><figcaption></figcaption></figure>' +
    '<div class="toolbar">' +
    '<button type="button" class="button" data-go="-1">&larr; Previous</button>' +
    '<button type="button" class="button" data-go="1">Next &rarr;</button>' +
    '<button type="button" class="button" data-close>Close</button>' +
    '</div></div>';
  document.body.appendChild(dlg);
  var img = dlg.querySelector('img'), cap = dlg.querySelector('figcaption'), count = dlg.querySelector('#lightbox-count');
  var group = [], at = 0, opener = null;

  function show(i) {
    at = (i + group.length) % group.length;
    var a = group[at], thumb = a.querySelector('img'), fig = a.closest('figure');
    var text = fig && fig.querySelector('figcaption') ? fig.querySelector('figcaption').textContent : '';
    img.src = a.getAttribute('href');
    img.alt = thumb ? thumb.alt : '';
    if (thumb) { img.width = Number(thumb.getAttribute('width')); img.height = Number(thumb.getAttribute('height')); }
    cap.textContent = text;
    cap.hidden = !text;
    count.textContent = 'Image ' + (at + 1) + ' of ' + group.length;
    var single = group.length < 2;
    dlg.querySelectorAll('[data-go]').forEach(function (b) { b.hidden = single; });
  }

  links.forEach(function (a) {
    a.addEventListener('click', function (ev) {
      if (ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
      ev.preventDefault();
      var name = a.getAttribute('data-gallery');
      group = links.filter(function (x) { return x.getAttribute('data-gallery') === name; });
      opener = a;
      show(group.indexOf(a));
      dlg.showModal();
      dlg.querySelector('[data-close]').focus();
    });
  });

  dlg.addEventListener('click', function (ev) {
    var t = ev.target;
    if (t === dlg) { dlg.close(); return; }                     // a click on the backdrop
    if (t.closest('[data-close]')) { dlg.close(); return; }
    var go = t.closest('[data-go]');
    if (go) show(at + Number(go.getAttribute('data-go')));
  });
  dlg.addEventListener('keydown', function (ev) {
    if (ev.key === 'ArrowRight') { ev.preventDefault(); show(at + 1); }
    else if (ev.key === 'ArrowLeft') { ev.preventDefault(); show(at - 1); }
  });
  dlg.addEventListener('close', function () {                  // Esc closes the dialog by itself
    img.removeAttribute('src');
    if (opener) opener.focus();
  });
})();
