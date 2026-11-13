/* ROBOS-MENU-V1 — o botão "Robôs de IA" do menu abre a página /robos.html (cartões de todos os robôs) */
(function () {
  'use strict';
  if (window.__robosMenu) return; window.__robosMenu = 1;
  var EST = /\/robos(\.html)?$/.test(location.pathname);
  function alvo(t) { return t && t.closest && t.closest('.v3-grp[data-grp="ia"],[data-grp="ia"].v3-grp,.mf-grp[data-grp="ia"],[data-robos-menu]'); }
  document.addEventListener('click', function (e) {
    var b = alvo(e.target); if (!b) return;
    e.preventDefault(); e.stopPropagation(); if (e.stopImmediatePropagation) e.stopImmediatePropagation();
    if (!EST) location.href = '/robos.html';
  }, true);
  function marca() {
    document.querySelectorAll('.v3-grp[data-grp="ia"]').forEach(function (b) {
      b.setAttribute('aria-expanded', 'false'); b.title = 'Robôs de IA · ver todos';
      if (EST) b.classList.add('active');
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', marca); else marca();
  setTimeout(marca, 1500);
})();
