// Home page: previous and next buttons for the games carousel (D-42). The carousel is a plain list that scrolls
// sideways and works without this script; the buttons stay hidden until it runs. It never moves by itself and stores
// nothing: no cookies, no storage.
(function () {
  'use strict';
  Array.prototype.forEach.call(document.querySelectorAll('.reel-buttons'), function (box) {
    var buttons = box.querySelectorAll('button[data-reel]');
    var reel = document.getElementById(buttons[0] && buttons[0].getAttribute('aria-controls'));
    if (!reel) return;
    var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    function update() {
      var max = reel.scrollWidth - reel.clientWidth;
      buttons[0].disabled = reel.scrollLeft <= 1;
      buttons[1].disabled = reel.scrollLeft >= max - 1;
      box.hidden = max <= 1;   // everything fits: no buttons needed
    }
    Array.prototype.forEach.call(buttons, function (b) {
      b.addEventListener('click', function () {
        var step = Number(b.getAttribute('data-reel')) * reel.clientWidth * 0.85;
        reel.scrollBy({ left: step, behavior: still ? 'auto' : 'smooth' });
      });
    });
    reel.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
  });
}());
