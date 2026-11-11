// Home page: the music video plays on the page only when the visitor presses play (D-41). Until then the page loads
// nothing from YouTube; the poster is the site's own picture and the link opens YouTube without this script. The player
// comes from youtube-nocookie.com. Nothing is stored here: no cookies, no storage.
(function () {
  'use strict';
  Array.prototype.forEach.call(document.querySelectorAll('[data-youtube]'), function (box) {
    var id = box.getAttribute('data-youtube');
    var link = box.querySelector('a');
    if (!link || !/^[A-Za-z0-9_-]{11}$/.test(id)) return;
    link.addEventListener('click', function (ev) {
      ev.preventDefault();
      var frame = document.createElement('iframe');
      frame.src = 'https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&rel=0';
      frame.title = box.getAttribute('data-title') || 'Video';
      frame.width = '960';
      frame.height = '540';
      frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      frame.setAttribute('allowfullscreen', '');
      frame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
      box.replaceChild(frame, link);
      frame.focus();
    });
  });
}());
