// click the logo three times
(function () {
  var img = document.querySelector('.brand img'), clicks = 0, timer, gone = false;
  if (!img) return;
  img.addEventListener('click', function (e) {
    e.preventDefault();
    clicks++;
    clearTimeout(timer);
    timer = setTimeout(function () { clicks = 0; }, 1200);
    if (clicks < 3 || gone) return;
    gone = true;
    var r = img.getBoundingClientRect();
    // off it goes, up and to the right
    img.style.transition = 'transform .8s cubic-bezier(.5,-.4,.8,.6)';
    img.style.transform = 'translate(' + window.innerWidth + 'px,' + (-r.bottom - 60) + 'px) rotate(900deg)';
    setTimeout(function () {
      // something else comes back from the left
      img.style.transition = 'none';
      img.src = 'img/egg.png';
      img.style.transform = 'translateX(' + (-r.right - 80) + 'px) rotate(-540deg)';
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          img.style.transition = 'transform 1s cubic-bezier(.2,.9,.3,1.25)';
          img.style.transform = 'none';
        });
      });
    }, 1400);
  });
})();

// up up down down left right left right b a
(function () {
  var code = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
  var at = 0, typed = '';
  function banner(text, color, sub) {
    var d = document.createElement('div');
    d.style.cssText = 'position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;' +
      'background:linear-gradient(transparent 35%,rgba(0,0,0,.75) 45%,rgba(0,0,0,.75) 55%,transparent 65%);' +
      'pointer-events:none;opacity:0;transition:opacity 1.2s;z-index:99;font-family:Georgia,"Times New Roman",serif';
    d.innerHTML = '<div style="font-size:clamp(28px,6vw,64px);letter-spacing:.08em;color:' + color + ';text-shadow:0 0 18px ' +
      color + '88">' + text + '</div>' + (sub ? '<div style="color:#ddd;font-size:18px;margin-top:8px;font-style:italic">' +
      sub + '</div>' : '');
    document.body.appendChild(d);
    requestAnimationFrame(function () { d.style.opacity = 1; });
    setTimeout(function () { d.style.opacity = 0; }, 3200);
    setTimeout(function () { d.remove(); }, 4600);
  }
  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    at = (e.key === code[at]) ? at + 1 : (e.key === code[0] ? 1 : 0);
    if (at === code.length) {
      at = 0;
      banner('GREAT ENEMY FELLED', '#e8c872');
    }
    if (e.key.length === 1) {
      typed = (typed + e.key.toLowerCase()).slice(-6);
      if (typed === 'margit') banner('MARGIT, THE FELL OMEN', '#d6c79a', 'Put these foolish ambitions to rest!');
    }
  });
})();

// type chum
(function () {
  var typed = '';
  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.key.length !== 1) return;
    typed = (typed + e.key.toLowerCase()).slice(-4);
    if (typed !== 'chum') return;
    typed = '';
    var img = document.createElement('img');
    img.src = (location.pathname.indexOf('/') === 0 ? '/' : '') + 'img/chum.png';
    var y = 15 + Math.random() * 55;
    img.style.cssText = 'position:fixed;width:160px;height:160px;left:100vw;top:' + y + 'vh;z-index:99;' +
      'pointer-events:none;transition:left 9s linear,top 9s ease-in-out';
    document.body.appendChild(img);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        // he drifts, slowly, and not quite straight
        img.style.left = '-200px';
        img.style.top = (y + (Math.random() * 20 - 10)) + 'vh';
      });
    });
    setTimeout(function () { img.remove(); }, 9500);
  });
})();
