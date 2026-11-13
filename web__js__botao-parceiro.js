/* BOTAO-PARCEIRO-V1: botao "Seja parceiro" no topo do painel, leva ao quiz de parceiro */
(function () {
  'use strict';
  if (window.__btParceiro) return; window.__btParceiro = 1;
  var LINK = 'https://www.dirleiluis.online/quiz-parceiro';
  var css = document.createElement('style');
  css.textContent = '.bt-parc{display:inline-flex;align-items:center;gap:7px;height:38px;padding:0 15px;margin-right:8px;border-radius:10px;border:1px solid rgba(96,165,250,.7);'
    + 'background:linear-gradient(135deg,#2563eb,#3b82f6);color:#fff!important;font:700 13.5px Inter,system-ui,sans-serif;text-decoration:none!important;white-space:nowrap;'
    + 'box-shadow:0 0 0 0 rgba(59,130,246,.55);animation:btParc 2.2s ease-in-out infinite;flex:none}'
    + '.bt-parc:hover{filter:brightness(1.1)}'
    + '@keyframes btParc{0%,100%{box-shadow:0 0 0 0 rgba(59,130,246,.55);background:linear-gradient(135deg,#2563eb,#3b82f6)}50%{box-shadow:0 0 18px 4px rgba(96,165,250,.45);background:linear-gradient(135deg,#3b82f6,#60a5fa)}}'
    + '@media (max-width:760px){.bt-parc .bp-t{display:none}.bt-parc{padding:0 11px;height:34px}}'
    + '@media (prefers-reduced-motion:reduce){.bt-parc{animation:none}}';
  document.head.appendChild(css);
  function cria() {
    var a = document.createElement('a');
    a.className = 'bt-parc'; a.href = LINK; a.target = '_blank'; a.rel = 'noopener';
    a.title = 'Tenha a sua própria plataforma de robôs';
    a.innerHTML = '<span>🤝</span><span class="bp-t">Seja parceiro</span>';
    a.addEventListener('click', function () { try { fetch('/api/quiz/track', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ quiz: 'quiz-parceiro', session_id: 'painel_' + Date.now(), step: 0, answer: 'botao_painel', completed: 0 }) }).catch(function () {}); } catch (e) {} });
    return a;
  }
  function alvo() {
    var els = document.querySelectorAll('header button, header a, .topbar button, .topbar a, .v3-topbar button, .v3-topbar a, button, a');
    var achou = null;
    for (var i = 0; i < els.length && !achou; i++) { var t = (els[i].textContent || '').trim(); if (/^(🧭\s*)?(Tour|Tour guiado)$/i.test(t) || els[i].id === 'tourBtn') achou = els[i]; }
    if (!achou) for (var j = 0; j < els.length && !achou; j++) { var u = (els[j].textContent || '').trim(); if (/^Sacar$/i.test(u)) achou = els[j]; }
    if (!achou) return null;
    var r = achou.getBoundingClientRect(); return r.top < 140 ? achou : null;
  }
  var n = 0;
  (function tenta() {
    if (document.querySelector('.bt-parc')) return;
    var t = alvo();
    if (t && t.parentNode) { t.parentNode.insertBefore(cria(), t); return; }
    if (++n < 30) return setTimeout(tenta, 400);
    var a = cria(); a.style.cssText = 'position:fixed;right:16px;bottom:18px;z-index:9998'; document.body.appendChild(a);
  })();
})();
