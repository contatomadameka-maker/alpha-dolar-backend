/* Alpha Dolar — correções do motor do IA Pro
 * 1) _alphaDs(tick): texto da cotação com as casas decimais REAIS do mercado,
 *    para o último dígito sair certo (antes toFixed(5) fazia todo dígito virar 0).
 * 2) proEscolherMercado: o Auto de mercado passa a usar a conexão nova da Deriv (OTP),
 *    analisa os 10 índices de volatilidade de uma vez com os últimos 60 ticks de cada um.
 */
(function () {
  'use strict';
  var APP_ID = '34lv1PuWzjElEuwWcDLyr', API = 'https://api.derivws.com/trading/v1/options';
  var PIP_FIXO = { R_10: 3, R_25: 3, R_50: 4, R_75: 4, R_100: 2, '1HZ10V': 2, '1HZ25V': 2, '1HZ50V': 2, '1HZ75V': 2, '1HZ100V': 2 };
  var PIP = window._alphaPip = window._alphaPip || {};

  function casas(q) { var t = String(q), i = t.indexOf('.'); return i < 0 ? 0 : t.length - i - 1; }
  function pipDe(sym, quote, pip) {
    if (pip != null && !isNaN(+pip)) return +pip;                 // a Deriv informou: usa
    var k = sym || '_', p = PIP[k] || (PIP[k] = { max: 0, n: 0 });
    p.max = Math.max(p.max, casas(quote)); p.n++;
    if (p.n >= 5 || PIP_FIXO[k] == null) return p.max;             // aprende com as cotações
    return Math.max(p.max, PIP_FIXO[k]);                           // primeiros ticks: tabela
  }
  window._alphaDs = function (tick) {
    var t = tick || {}, sym = t.symbol || t.underlying_symbol || '', q = parseFloat(t.quote);
    return q.toFixed(pipDe(sym, t.quote, t.pip_size)).replace('.', '');
  };
  window._alphaDigito = function (quote, sym, pip) {
    var t = (+quote).toFixed(pipDe(sym, quote, pip)); return +t.charAt(t.length - 1);
  };

  /* ── escolha automática de mercado pela conexão nova ── */
  var MERCADOS = [
    ['R_10', 'Volatility 10'], ['R_25', 'Volatility 25'], ['R_50', 'Volatility 50'], ['R_75', 'Volatility 75'], ['R_100', 'Volatility 100'],
    ['1HZ10V', 'Volatility 10 (1s)'], ['1HZ25V', 'Volatility 25 (1s)'], ['1HZ50V', 'Volatility 50 (1s)'], ['1HZ75V', 'Volatility 75 (1s)'], ['1HZ100V', 'Volatility 100 (1s)']
  ];
  function feed(m, c) { try { if (typeof window.proAddFeed === 'function') window.proAddFeed(m, c); } catch (e) {} }
  async function abrirWs() {
    var tk = localStorage.getItem('deriv_bearer_token'); if (!tk) throw new Error('sem login');
    var H = { Authorization: 'Bearer ' + tk, 'Deriv-App-ID': APP_ID };
    var r = await fetch(API + '/accounts', { headers: H }); if (!r.ok) throw new Error('contas ' + r.status);
    var contas = (await r.json()).data || [];
    var tipo = (window._proState && window._proState.contaTipo) || localStorage.getItem('deriv_conta_ativa') || 'demo';
    tipo = /real/i.test(tipo) ? 'real' : 'demo';
    var acct = contas.find(function (a) { return a.account_type === tipo; }) || contas[0]; if (!acct) throw new Error('sem conta');
    var o = await fetch(API + '/accounts/' + encodeURIComponent(acct.account_id) + '/otp', { method: 'POST', headers: H });
    var url = ((await o.json()).data || {}).url; if (!url) throw new Error('sem otp');
    return await new Promise(function (res, rej) {
      var ws = new WebSocket(url), t = setTimeout(function () { rej(new Error('timeout')); try { ws.close(); } catch (e) {} }, 8000);
      ws.onopen = function () { clearTimeout(t); res(ws); }; ws.onerror = function () { clearTimeout(t); rej(new Error('ws')); };
    });
  }
  function pedir(ws, obj) {
    return new Promise(function (res) {
      var id = Math.floor(Math.random() * 1e9), t = setTimeout(function () { ws.removeEventListener('message', f); res(null); }, 8000);
      function f(ev) { var m; try { m = JSON.parse(ev.data); } catch (e) { return; } if (m.req_id === id) { clearTimeout(t); ws.removeEventListener('message', f); res(m); } }
      ws.addEventListener('message', f); obj.req_id = id; ws.send(JSON.stringify(obj));
    });
  }
  function scoreDe(digits) {
    var tipos = ['DIGITEVEN', 'DIGITODD', 'DIGITOVER', 'DIGITUNDER'], melhor = 0, tipoMelhor = '';
    tipos.forEach(function (t) {
      var sc = 0;
      try { sc = +(window.proAnalisarTipo(t, digits) || {}).score || 0; } catch (e) {}
      if (sc > 0 && sc <= 1) sc = sc * 100;
      if (sc > melhor) { melhor = sc; tipoMelhor = t; }
    });
    return { score: Math.round(melhor), tipo: tipoMelhor };
  }
  var original = window.proEscolherMercado;
  window.proEscolherMercado = async function () {
    var sel = document.getElementById('proSymbol'), atual = sel ? sel.value : 'R_100', ws = null;
    feed('🔍 AUTO: analisando os 10 mercados de volatilidade...', '#a855f7');
    try {
      ws = await abrirWs();
      var res = [];
      for (var i = 0; i < MERCADOS.length; i++) {
        var m = MERCADOS[i], r = await pedir(ws, { ticks_history: m[0], end: 'latest', count: 60, style: 'ticks' });
        var pr = r && r.history && r.history.prices; if (!pr || pr.length < 20) continue;
        var digits = pr.map(function (p) { return window._alphaDigito(p, m[0], r.pip_size); });
        var sc = scoreDe(digits);
        res.push({ sym: m[0], label: m[1], score: sc.score, tipo: sc.tipo });
      }
      if (!res.length) throw new Error('nenhum mercado respondeu');
      res.sort(function (a, b) { return b.score - a.score; });
      feed('📊 ' + res.slice(0, 3).map(function (x) { return x.label + ' ' + x.score + '%'; }).join(' · '), '#64748b');
      var melhor = res[0];
      if (sel) {
        var tem = Array.prototype.some.call(sel.options, function (o) { return o.value === melhor.sym; });
        if (!tem) { var alt = res.find(function (x) { return Array.prototype.some.call(sel.options, function (o) { return o.value === x.sym; }); }); if (alt) melhor = alt; }
        sel.value = melhor.sym; sel.dispatchEvent(new Event('change', { bubbles: true }));
      }
      feed('✅ Melhor mercado: ' + melhor.label + ' (score ' + melhor.score + '%)', '#22c55e');
      try { if (typeof window.proFalar === 'function') window.proFalar('Mercado escolhido: ' + melhor.label); } catch (e) {}
      return melhor.sym;
    } catch (e) {
      feed('⚠️ AUTO: não consegui analisar os mercados (' + (e && e.message || e) + '). Mantendo ' + atual + '.', '#f59e0b');
      return atual;
    } finally { try { if (ws) ws.close(); } catch (e) {} }
  };
  window.proEscolherMercado.__original = original;
})();
