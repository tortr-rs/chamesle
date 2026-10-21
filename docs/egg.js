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
