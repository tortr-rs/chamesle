(function () {
  var main = document.querySelector('main');
  var link = document.getElementById('edit-link');
  if (!main || !link) return;

  var key = 'edit:' + location.pathname;
  var editing = false;
  var bar = null;

  function stored() {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function store(html) {
    try { localStorage.setItem(key, html); } catch (e) {}
  }
  function forget() {
    try { localStorage.removeItem(key); } catch (e) {}
  }

  var original = main.innerHTML;
  var saved = stored();
  if (saved) main.innerHTML = saved;

  function button(label, fn) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.onclick = fn;
    return b;
  }

  function download() {
    var doc = '<!doctype html>\n' + document.documentElement.outerHTML;
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([doc], { type: 'text/html' }));
    a.download = location.pathname.split('/').pop() || 'index.html';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function stop() {
    editing = false;
    main.removeAttribute('contenteditable');
    main.classList.remove('editing');
    store(main.innerHTML);
    if (bar) { bar.remove(); bar = null; }
    link.textContent = 'Edit text';
  }

  function start() {
    editing = true;
    main.setAttribute('contenteditable', 'true');
    main.classList.add('editing');
    bar = document.createElement('div');
    bar.id = 'editbar';
    bar.appendChild(document.createTextNode('Editing this page. Changes stay in your browser. '));
    bar.appendChild(button('Done', stop));
    bar.appendChild(button('Download page', function () { stop(); download(); }));
    bar.appendChild(button('Undo all', function () {
      forget();
      main.innerHTML = original;
      stop();
      forget();
    }));
    document.body.insertBefore(bar, document.body.firstChild);
    link.textContent = 'Stop editing';
    main.focus();
  }

  link.onclick = function (e) {
    e.preventDefault();
    if (editing) stop(); else start();
  };
})();
