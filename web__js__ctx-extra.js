/* CTX-EXTRA-V1 — Alpha IA Contextual: % da banca + Confirmar antes de entrar + Trava de lucro (usa o robo-extra.js).
   A IA continua decidindo a direção; a confirmação só escolhe o momento: depois que a IA manda entrar em ▲ UP,
   espera N quedas seguidas (▼ DOWN espera N altas) e só então compra. Se não vier em ~40 ticks, descarta o sinal.
   Para desfazer: remover este arquivo da página. */
(function () {
  'use strict';
  if (window.__ctxExtra) return; window.__ctxExtra = true;
  var LIM = 40;
  function X() { return window.__extra; }
  function S() { return window._ctxState || {}; }
  function v(id, d) { var e = document.getElementById(id); return e && e.value ? e.value : d; }
  function feed(m, c) { try { window.ctxAddFeed(m, c); } catch (e) {} }
  function embrulhaCompra() {
    var ox = window.ctxExecutarTrade; if (typeof ox !== 'function' || ox.__cx) return;
    var nx = function (r) {
      var s = S(), x = X(); if (!x || !r) return ox.apply(this, arguments);
      if (s.waiting || !s.running) return;
      if (x.cfg.pct && Math.abs((+s.stakeAtual || 0) - (+s.stake || 0)) < 0.005) { var b = x.base(+v('ctxStake', '0.35') || 0.35, 0); s.stake = s.stakeAtual = b; }   /* % da banca no começo de cada ciclo */
      var mercado = v('ctxMercado', '1HZ100V'), par = v('ctxTipo', 'CALL/PUT').split('/'), ct = r.direcao === 'UP' ? par[0] : par[1], self = this;
      if (!x.cfg.conf || x.okSym(ct, null, mercado)) return ox.call(self, r);
      s.waiting = true; var t0 = Date.now(), n0 = x.ticks(mercado);
      feed('🔎 IA decidiu ' + (r.direcao === 'UP' ? '▲ UP' : '▼ DOWN') + ' · confirmando: esperando ' + x.cfg.conf + ' ' + (r.direcao === 'UP' ? 'tick(s) de queda' : 'tick(s) de alta') + ' seguido(s) antes de entrar', '#94a3b8');
      (function espera() {
        var s2 = S();
        if (!s2.running) { s2.waiting = false; return; }
        if (x.okSym(ct, null, mercado)) { s2.waiting = false; feed('✅ Confirmado: entrando ' + r.direcao, '#5eead4'); return ox.call(self, r); }
        if (x.ticks(mercado) - n0 > LIM || Date.now() - t0 > 60000) { s2.waiting = false; feed('⏭ A confirmação não veio a tempo: sinal descartado, a IA analisa de novo', '#f59e0b'); return; }
        setTimeout(espera, 250);
      })();
    };
    nx.__cx = true; window.ctxExecutarTrade = nx;
  }
  function embrulhaResultado() {
    var oc = window._ctxOnContract; if (typeof oc !== 'function' || oc.__cx) return;
    var nc = function (status, profit) {
      var s = S(), n0 = +s.trades || 0, r = oc.apply(this, arguments), x = X();
      try {
        if (x && s.running && (+s.trades || 0) > n0) {
          var p = +profit || 0, pl = (+s.lucro || 0) - (+s.perda || 0), cx = x.res(p > 0, p, pl, +s.lucroAlvo || 0);
          if (cx) { feed('🔒 ' + cx[2], '#fde68a'); try { window.ctxFalar('Trava de lucro acionada. Lucro guardado.'); } catch (e) {} if (typeof window.ctxParar === 'function') window.ctxParar('trava'); }
        }
      } catch (e) {}
      return r;
    };
    nc.__cx = true; window._ctxOnContract = nc;
  }
  /* o ctx-fix.js troca essas funções quando carrega: confere sempre e embrulha a versão atual */
  setInterval(function () { embrulhaCompra(); embrulhaResultado(); }, 1000);
  embrulhaCompra(); embrulhaResultado();
})();
