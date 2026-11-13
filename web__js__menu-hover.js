/* MENU-HOVER-V2 (no PC comeca sempre fechado; o ☰ nao fixa mais aberto) — no PC o menu lateral abre sozinho quando o mouse chega nele e fecha quando sai.
 * Abre por cima da tela (não empurra o painel nem o gráfico). Celular continua igual (toque no ☰).
 * Se o usuário fixou o menu aberto no ☰, fica como ele deixou. */
(function () {
  'use strict';
  if (window.__menuHover) return; window.__menuHover = true;
  var W = 210, ATRASO_ABRE = 90, ATRASO_FECHA = 320, PERTO = 10;
  var rail = null, aberto = false, tA = 0, tF = 0, w0 = 0;
  function pc() { try { return matchMedia('(hover: hover) and (pointer: fine)').matches && innerWidth > 900; } catch (e) { return innerWidth > 900; } }
  function fixado() { return false; }
  /* V2: no PC o menu comeca fechado, mesmo que antes tenha ficado salvo aberto */
  function recolheFixo() {
    if (!rail || !pc() || aberto) return;
    if (rail.classList.contains('expanded')) { rail.classList.remove('expanded'); var l = document.querySelector('.main-layout'); if (l) l.style.setProperty('--rail-w', '76px'); }
    try { localStorage.setItem('railExpanded', '0'); } catch (e) {}
  }
  function flyoutAberto() { var f = document.querySelector('.mfo.on'); return !!f; }
  var st = document.createElement('style');
  st.textContent = '.v3-rail.mh-over{z-index:9000!important;background:linear-gradient(180deg,#10121d,#0b0d16)!important;box-shadow:12px 0 40px rgba(0,0,0,.55),1px 0 0 rgba(139,92,246,.25);transition:width .16s ease,min-width .16s ease}' +
    '.v3-rail.mh-over .v3-rail-label,.v3-rail.mh-over .v3-badge,.v3-rail.mh-over .v3-grp-count,.v3-rail.mh-over .v3-grp-chev{animation:mhIn .18s ease-out}@keyframes mhIn{from{opacity:0}to{opacity:1}}';
  (document.head || document.documentElement).appendChild(st);
  function abre() {
    clearTimeout(tF); tF = 0;
    if (aberto || !rail || !pc() || fixado()) return;
    w0 = rail.getBoundingClientRect().width || 76;
    aberto = true;
    rail.classList.add('expanded', 'mh-over');
    var pos = getComputedStyle(rail).position, fix = pos === 'fixed';
    if (pos === 'static') rail.style.position = 'relative';
    rail.style.width = W + 'px'; rail.style.minWidth = W + 'px'; rail.style.maxWidth = W + 'px';
    if (!fix) rail.style.marginRight = (w0 - W) + 'px'; /* o espaço da coluna continua o mesmo: abre por cima */
  }
  function fecha() {
    if (!aberto || !rail) return;
    if (flyoutAberto()) return; /* com a lista de robôs aberta, o menu fica aberto */
    aberto = false;
    rail.classList.remove('expanded', 'mh-over');
    rail.style.width = rail.style.minWidth = rail.style.maxWidth = rail.style.marginRight = rail.style.position = '';
  }
  function pedeAbre() { clearTimeout(tF); tF = 0; if (aberto || tA) return; tA = setTimeout(function () { tA = 0; abre(); }, ATRASO_ABRE); }
  function pedeFecha() { clearTimeout(tA); tA = 0; if (!aberto) return; clearTimeout(tF); tF = setTimeout(function () { tF = 0; fecha(); }, ATRASO_FECHA); }
  function dentro(el) { return !!(el && el.closest && (el.closest('.v3-rail') || el.closest('.mfo'))); }
  function liga() {
    rail = document.querySelector('.v3-rail'); if (!rail) return;
    rail.addEventListener('mouseenter', pedeAbre);
    rail.addEventListener('mouseleave', function (e) { if (!dentro(e.relatedTarget)) pedeFecha(); });
    /* chegou perto da borda do menu: já abre */
    var raf = 0;
    document.addEventListener('mousemove', function (e) {
      if (raf) return; raf = requestAnimationFrame(function () {
        raf = 0; if (!pc() || !rail) return;
        var r = rail.getBoundingClientRect(), x = e.clientX, y = e.clientY, no = y >= r.top && y <= r.bottom;
        if (!aberto) { if (no && x <= r.right + PERTO && x >= r.left - 2) pedeAbre(); else if (tA) { clearTimeout(tA); tA = 0; } }
        else if (dentro(e.target)) { clearTimeout(tF); tF = 0; }
        else if (!tF) pedeFecha();
      });
    }, { passive: true });
    document.addEventListener('mouseleave', function () { pedeFecha(); });
    /* lista de robôs (flyout) fechou e o mouse está fora: recolhe */
    document.addEventListener('click', function () { setTimeout(function () { if (aberto && !flyoutAberto() && !rail.matches(':hover')) pedeFecha(); }, 120); }, true);
    /* V2: no PC o ☰ so abre/fecha por cima, nao deixa o menu preso aberto */
    document.addEventListener('click', function (e) {
      var t = e.target && e.target.closest && e.target.closest('.v3-rail-toggle');
      if (!t || !pc()) return;
      e.preventDefault(); e.stopPropagation(); if (e.stopImmediatePropagation) e.stopImmediatePropagation();
      if (aberto) { clearTimeout(tA); tA = 0; fecha(); } else abre();
    }, true);
    recolheFixo(); addEventListener('load', recolheFixo); setTimeout(recolheFixo, 800); setTimeout(recolheFixo, 2500);
    addEventListener('resize', function () { if (!pc()) { clearTimeout(tA); tA = 0; if (aberto) { aberto = false; rail.classList.remove('expanded', 'mh-over'); rail.style.width = rail.style.minWidth = rail.style.maxWidth = rail.style.marginRight = rail.style.position = ''; } } });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', liga); else liga();
})();
