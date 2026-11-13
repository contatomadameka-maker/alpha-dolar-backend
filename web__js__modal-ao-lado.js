/* MODAL-AO-LADO-V1 — a janela do robô rodando (IA Simples) abre ao lado do menu lateral, sem cobrir o menu (só no computador) */
(function () {
  'use strict';
  if (window.__modalAoLado) return; window.__modalAoLado = true;
  function menu() {
    var a = document.getElementById('railIdiomaSub'), e = a;
    while (e && e !== document.body) {
      var r = e.getBoundingClientRect();
      if (r.left <= 6 && r.width > 40 && r.width < 420 && r.height > innerHeight * 0.5) return e;
      e = e.parentElement;
    }
    return null;
  }
  function visivel(el) { if (!el) return false; var s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' && el.getBoundingClientRect().width > 0; }
  function ajusta() {
    var m = document.getElementById('botRunningModal'); if (!m) return;
    var box = m.firstElementChild; if (!box) return;
    if (innerWidth < 900 || !visivel(m)) { if (box.style.translate) box.style.translate = ''; return; }
    var rl = menu(), dir = rl && visivel(rl) ? rl.getBoundingClientRect().right : 0;
    box.style.translate = '';
    var dx = dir ? Math.max(0, dir + 12 - box.getBoundingClientRect().left) : 0;
    if (dx) box.style.translate = dx + 'px 0';
    m.style.pointerEvents = 'none'; box.style.pointerEvents = 'auto';   /* o menu por trás continua clicável */
  }
  setInterval(ajusta, 400); addEventListener('resize', ajusta);
})();
