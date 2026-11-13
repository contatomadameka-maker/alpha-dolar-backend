/* IA-PRO-TELA-V1 — IA Pro: no PC ocupa a tela inteira; no celular mantem a tela acesa enquanto o robo roda.
   Nao mexe no motor: so CSS e Wake Lock (pedido do navegador para nao apagar a tela). */
(function () {
  'use strict';
  if (window.__iaProTela) return; window.__iaProTela = true;
  var css = document.createElement('style');
  css.textContent =
    '@media (min-width:1101px){' +
      '#alphaIaProModal .p2{max-width:none!important;padding:18px 28px 28px!important}' +
      '#alphaIaProModal .p2-cols{grid-template-columns:minmax(320px,360px) minmax(0,1fr) minmax(300px,380px)!important;gap:18px!important}' +
      '#alphaIaProModal .pro3d{height:clamp(380px,46vh,560px)!important}' +
    '}' +
    '@media (min-width:1800px){#alphaIaProModal .p2-cols{grid-template-columns:400px minmax(0,1fr) 420px!important}}';
  document.head.appendChild(css);

  var cel = matchMedia('(max-width: 760px)').matches || /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent);
  if (!cel) return;
  var trava = null, avisou = false;
  function rodando() { var s = window._proState; return !!(s && s.running); }
  function pede() {
    if (trava || !rodando() || document.hidden || !('wakeLock' in navigator)) return;
    navigator.wakeLock.request('screen').then(function (t) { trava = t; t.addEventListener('release', function () { trava = null; }); }).catch(function () {});
  }
  function solta() { if (trava) { try { trava.release(); } catch (e) {} trava = null; } }
  setInterval(function () {
    if (rodando()) {
      pede();
      if (!avisou && typeof window.proAddFeed === 'function') { avisou = true; window.proAddFeed('📱 No celular, deixe esta tela aberta: se a tela apagar ou você trocar de app, o navegador pausa o robô.', '#f59e0b'); }
    } else { solta(); avisou = false; }
  }, 2000);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) pede(); });
})();
