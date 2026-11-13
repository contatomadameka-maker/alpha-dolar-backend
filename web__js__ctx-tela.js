/* CTX-TELA-V1 — IA Contextual: no PC ocupa a tela inteira (so CSS, nao mexe no motor). */
(function () {
  'use strict';
  if (window.__ctxTela) return; window.__ctxTela = true;
  var css = document.createElement('style');
  css.textContent =
    '@media (min-width:1151px){' +
      '#alphaCtxIaModal .c2{max-width:none!important;padding:18px 28px 28px!important}' +
      '#alphaCtxIaModal .c2-cols{grid-template-columns:minmax(330px,380px) minmax(0,1fr) minmax(300px,400px)!important;gap:18px!important}' +
      '#alphaCtxIaModal .ctx3d{height:clamp(370px,46vh,600px)!important}' +
    '}';
  document.head.appendChild(css);
})();
