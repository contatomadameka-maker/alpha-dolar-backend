/* IAS-FIX-V1 — IA Simples (robô do servidor)
 * 1) Conta fixa da sessão: ao ligar, guarda a conta (deriv_id) nesta aba. Enquanto o robô roda, a página conversa
 *    sempre com essa conta, mesmo que outra aba/robô troque a conta ativa (era isso que fazia o Parar mandar o
 *    pedido para a conta errada e o robô continuar ligado no servidor).
 * 2) Botão Parar confiável: manda a parada para a conta da sessão, com tempo limite e
 *    3 tentativas, confere no servidor se parou de verdade e só então fecha a tela. Não trava mais com o servidor lento.
 * 3) Lista de operações só com as do IA Simples: antes mostrava tudo da conta (outros robôs, outra conta). */
(function () {
  'use strict';
  if (window.__iasFix) return; window.__iasFix = true;
  var API = 'https://alpha-dolar-backend.onrender.com/api';
  var of = window.fetch.bind(window), origDid = window.getDerivId;
  function ss(k, v) { try { if (v === undefined) return sessionStorage.getItem(k); if (v === null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, v); } catch (e) {} return null; }
  function contas() { try { return JSON.parse(localStorage.getItem('deriv_accounts') || '[]'); } catch (e) { return []; } }
  function idDe(c) { return c && (c.acct || c.loginid || c.deriv_id); }
  function contaDe(id) { var c = contas().filter(function (x) { return idDe(x) === id; })[0]; return c ? (c.isDemo ? 'demo' : 'real') : null; }
  function didAtivo() { try { return origDid ? origDid() : 'anonymous'; } catch (e) { return 'anonymous'; } }
  function fixar(id) { ss('ias_did', id); var c = contaDe(id); if (c) ss('ias_conta', c); ss('ias_did_t', String(Date.now())); }
  function soltar() { ss('ias_did', null); ss('ias_conta', null); ss('ias_did_t', null); }
  /* enquanto o robo da sessao roda, a pagina usa a conta em que ele foi ligado */
  window.getDerivId = function () { return ss('ias_did') || didAtivo(); };
  var parando = false, passe = false;

  window.fetch = function (u, o) {
    var url = String((u && u.url) || u || ''), p = of(u, o);
    try {
      if (/\/bot\/start$/.test(url) && o && o.body) {
        var b = JSON.parse(o.body);
        if ((b.bot_type || 'ia') === 'ia' && b.deriv_id) p.then(function (r) { if (r.ok) fixar(b.deriv_id); }).catch(function () {});
      }
      if (/\/bot\/stats\/ia\?/.test(url) && ss('ias_did')) {
        p.then(function (r) { return r.clone().json(); }).then(function (d) {
          var t = +ss('ias_did_t') || 0;
          if (d && d.running === false && d.stop_reason && !parando && Date.now() - t > 20000) soltar();
        }).catch(function () {});
      }
    } catch (e) {}
    return p;
  };

  /* ---------- parar de verdade ---------- */
  function espera(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function comTempo(url, op, ms) {
    var c = window.AbortController ? new AbortController() : null, t = setTimeout(function () { if (c) c.abort(); }, ms);
    if (c) { op = op || {}; op.signal = c.signal; }
    return of(url, op).then(function (r) { clearTimeout(t); return r.json().catch(function () { return {}; }).then(function (d) { return { st: r.status, d: d }; }); }, function (e) { clearTimeout(t); throw e; });
  }
  function postStop(id) {
    return comTempo(API + '/bot/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_type: 'ia', deriv_id: id }) }, 9000)
      .then(function (x) { return x; }, function () { return null; });
  }
  function rodando(id) {
    return comTempo(API + '/bot/stats/ia?deriv_id=' + encodeURIComponent(id), null, 8000)
      .then(function (x) { return !!(x.d && x.d.running); }, function () { return null; });
  }
  async function pararServidor(info) {
    var ids = [ss('ias_did') || didAtivo()]; /* so a conta da sessao: nao derruba um IA Simples ligado em outra aba/conta */
    for (var tent = 1; tent <= 3; tent++) {
      info('Parando o robô… (' + tent + '/3)');
      for (var i = 0; i < ids.length; i++) await postStop(ids[i]);
      await espera(1500);
      var vivos = 0, semResp = 0;
      for (i = 0; i < ids.length; i++) { var r = await rodando(ids[i]); if (r === true) vivos++; if (r === null) semResp++; }
      if (!vivos && !semResp) return true;
    }
    /* ainda rodando: normalmente esta terminando o contrato aberto (dura poucos segundos) */
    var fim = Date.now() + 45000;
    while (Date.now() < fim) {
      info('Terminando a operação aberta…');
      await espera(3000);
      var v2 = 0, s2 = 0;
      for (i = 0; i < ids.length; i++) { var r2 = await rodando(ids[i]); if (r2 === true) { v2++; await postStop(ids[i]); } if (r2 === null) s2++; }
      if (!v2 && !s2) return true;
    }
    return false;
  }
  var PLAY = '<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M8 5v14l11-7z"/></svg><span>Iniciar Robô</span>';
  document.addEventListener('click', function (e) {
    if (passe) return;
    var b = e.target && e.target.closest && e.target.closest('#stopBotBtn, #startButton'); if (!b) return;
    if (b.id === 'startButton' && !/parar/i.test(b.textContent || '')) return;
    if (window._iaAdv && window._iaAdv.running) return; /* IA Avançado tem parada propria */
    e.preventDefault(); e.stopPropagation(); if (e.stopImmediatePropagation) e.stopImmediatePropagation();
    if (parando) return; parando = true;
    var sb = document.getElementById('stopBotBtn'), h0 = sb ? sb.innerHTML : '';
    function info(t) { if (sb) { sb.disabled = true; sb.innerHTML = '<span>⏳ ' + t + '</span>'; } }
    pararServidor(info).then(function (ok) {
      if (sb) { sb.disabled = false; sb.innerHTML = h0; }
      if (!ok) {
        parando = false;
        if (sb) { sb.innerHTML = '<span>⚠️ Servidor não confirmou · toque de novo</span>'; setTimeout(function () { sb.innerHTML = h0; }, 6000); }
        return;
      }
      soltar();
      passe = true; try { b.click(); } catch (x) {} passe = false; /* deixa a tela fazer o fechamento normal (resumo da sessao) */
      setTimeout(function () {
        var m = document.getElementById('botRunningModal');
        if (m && m.classList.contains('active')) { m.classList.remove('active'); var s = document.getElementById('startButton'); if (s) s.innerHTML = PLAY; }
        parando = false;
      }, 600);
    });
  }, true);

  /* ---------- lista de operacoes: so as do IA Simples ---------- */
  var RF = { CALL: 1, PUT: 1, CALLE: 1, PUTE: 1 }, BT = [];
  function parse(c) {
    var t = c.contract_type, s = c.underlying || c.underlying_symbol, m = String(c.shortcode || '').match(/^([A-Z]+)_((?:R_\d+)|(?:1HZ\d+V)|(?:[A-Za-z0-9]+))_/);
    if (m) { t = t || m[1]; s = s || m[2]; } return { t: t || '', s: s || '' };
  }
  function simbolos() { var o = {}; o[window.selectedMarketSymbol || 'R_100'] = 1; BT.forEach(function (x) { if (x && x.symbol) o[x.symbol] = 1; }); return o; }
  function filtrarFechadas(arr) {
    if (!Array.isArray(arr)) return arr;
    var sy = simbolos(), pool = BT.map(function (x) { return { s: x.symbol, st: +x.stake, u: false }; });
    return arr.filter(function (c) {
      var p = parse(c); if (!sy[p.s]) return false;
      var st = +c.buy_price, k = null;
      for (var i = 0; i < pool.length; i++) if (!pool[i].u && pool[i].s === p.s && Math.abs(pool[i].st - st) <= 0.011) { k = pool[i]; break; }
      if (k) { k.u = true; return true; }
      return !pool.length && !!RF[p.t];
    });
  }
  function abertaOk(c) { var p = parse(c); return !!simbolos()[p.s] && !!RF[p.t]; }
  function ligarFiltro() {
    var O = window.__iasOps; if (!O || O.__filtro) return !!O; O.__filtro = true;
    var f = filtrarFechadas(O.fechadas || []);
    Object.defineProperty(O, 'fechadas', { configurable: true, enumerable: true, get: function () { return f; }, set: function (v) { f = filtrarFechadas(v); } });
    function px(base) { return new Proxy(base || {}, { set: function (t, k, v) { if (v && typeof v === 'object' && v.contract_id && !abertaOk(v)) return true; t[k] = v; return true; } }); }
    var a = px(O.abertas); Object.defineProperty(O, 'abertas', { configurable: true, enumerable: true, get: function () { return a; }, set: function (v) { a = px(v); } });
    return true;
  }
  (function tenta(n) { if (!ligarFiltro() && n < 40) setTimeout(function () { tenta(n + 1); }, 250); })(0);
  setInterval(function () {
    var O = window.__iasOps; if (!O || !O.ativo) return;
    comTempo(API + '/bot/trades/ia?deriv_id=' + encodeURIComponent(window.getDerivId()), null, 8000).then(function (x) {
      if (x.d && Array.isArray(x.d.trades)) BT = x.d.trades;
    }, function () {});
  }, 5000);
})();
