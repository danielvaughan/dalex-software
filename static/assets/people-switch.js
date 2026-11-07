// About page: switch every picture of the team between the pixel art and the 1987 photos (D-39).
// Pixel art is the default and the page works without this script. Nothing is stored: no cookies, no storage.
(function () {
  'use strict';
  var button = document.getElementById('people-switch');
  if (!button) return;
  var pictures = Array.prototype.slice.call(document.querySelectorAll('img[data-photo]'));
  var captions = Array.prototype.slice.call(document.querySelectorAll('[data-photo-caption]'));
  pictures.forEach(function (img) {
    img.setAttribute('data-pixel', img.getAttribute('src'));
    img.setAttribute('data-pixel-alt', img.getAttribute('alt'));
    if (img.hasAttribute('srcset')) img.setAttribute('data-pixel-srcset', img.getAttribute('srcset'));
  });
  captions.forEach(function (el) { el.setAttribute('data-pixel-caption', el.textContent); });

  function show(photos) {
    pictures.forEach(function (img) {
      var kind = photos ? 'photo' : 'pixel';
      img.setAttribute('src', img.getAttribute('data-' + kind));
      img.setAttribute('alt', img.getAttribute('data-' + kind + '-alt'));
      var srcset = img.getAttribute('data-' + kind + '-srcset');
      if (srcset) img.setAttribute('srcset', srcset); else img.removeAttribute('srcset');
    });
    captions.forEach(function (el) {
      el.textContent = el.getAttribute(photos ? 'data-photo-caption' : 'data-pixel-caption');
    });
    document.documentElement.classList.toggle('photos', photos);
    button.setAttribute('aria-pressed', photos ? 'true' : 'false');
    button.textContent = photos ? 'Show the pixel art' : 'Show the 1987 photos';
  }

  button.hidden = false;
  button.addEventListener('click', function () {
    show(button.getAttribute('aria-pressed') !== 'true');
  });
}());
