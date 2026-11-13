/* PADRAO-ENTRADA-V1 — valor inicial seguro em todos os robôs: entrada $0,35 (mínimo da Deriv) e limite de perda $10.
 * Roda UMA vez por robô em cada navegador (na primeira visita depois da atualização).
 * Depois disso vale o que a pessoa escolher: ela muda o valor e a página guarda como sempre guardou. */
(function () {
  'use strict';
  var me = document.currentScript, pg = me && me.getAttribute('data-pg');
  if (!pg) return;
  var E = 0.35, L = 10;
  function units() { var b = document.querySelector('#mUn button.on'); var n = b ? parseInt(b.getAttribute('data-v'), 10) : 6; return n > 0 ? n : 6; }
  var MAPA = {
    'dashboard': [['#initialStake', E], ['#stopLoss', L], ['#manualStake', E], ['#advStake', E], ['#advStop', L], ['#proStake', E], ['#proStop', L], ['#ctxStake', E], ['#ctxStopLoss', L]],
    'bot-colhedor': [['#iStake', E], ['#iStop', L]],
    'bot-ia-avancado': [['#iStake', E], ['#iStop', L]],
    'bot-perfil': [['#iStake', E], ['#iStop', L]],
    'bot-prisma': [['#iStake', E], ['#iStop', L]],
    'bot-pulso': [['#iStake', E], ['#iStop', L]],
    'bot-regente': [['#iStake', E], ['#iStop', L]],
    'bot-sniper': [['#iStake', E], ['#iStop', L]],
    'bot-touch-squad': [['#iStake', E], ['#iStop', L]],
    'bot-sentinelas': [['#iSt', E], ['#iLim', L]],
    'bot-digitos': [['#stake', E], ['#mStake', E], ['#sl', L]],
    'bot-sinais': [['#stake', E], ['#sl', L]],
    'bot-touch': [['#stake', E], ['#sl', L]],
    'grafico': [['#stake', E], ['#sl', L]],
    'bot-global': [['#stopD', L]],
    'auto-trading': [['#stAuto', E], ['#limitePerdaSessao', L], ['#limitePerdaAuto', L], ['#limitePerdaAutoMult', L]],
    'enxame': [['#iCap', function () { return Math.round(E * units() * 100) / 100; }], ['#iStopOp', L]],
    'esquadrao': [['input[id^="stake-unidade"]', E, true], ['#ecLim', L]]
  };
  var lista = MAPA[pg]; if (!lista) return;
  var K = 'alpha_padrao_v1:' + pg;
  function lg(k) { try { return localStorage.getItem(k); } catch (e) { return '1'; } }
  function ls(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  if (lg(K)) return;
  function poe(el, v) {
    var txt = v.toFixed(2);
    if (el.type === 'number') txt = String(Math.round(v * 100) / 100);
    if (el.value === txt) return;
    el.value = txt;
    try { el.dispatchEvent(new Event('input', { bubbles: true })); } catch (e) {}
    try { el.dispatchEvent(new Event('change', { bubbles: true })); } catch (e) {}
  }
  function tenta(n) {
    var falta = false;
    lista.forEach(function (it) {
      if (it.feito) return;
      var els = it[2] ? document.querySelectorAll(it[0]) : [document.querySelector(it[0])];
      els = Array.prototype.filter.call(els, Boolean);
      if (!els.length) { falta = true; return; }
      var v = typeof it[1] === 'function' ? it[1]() : it[1];
      els.forEach(function (el) { poe(el, v); });
      it.feito = true;
    });
    if (falta && n < 24) return setTimeout(function () { tenta(n + 1); }, 500);
    ls(K, String(Date.now()));
  }
  function ini() { setTimeout(function () { tenta(0); }, 700); }
  if (document.readyState === 'complete') ini(); else addEventListener('load', ini);
})();
