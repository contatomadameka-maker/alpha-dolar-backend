/* Alpha Dolar — IA CONTEXTUAL: conexão própria com a Deriv (OTP)
 * Antes: comprava pela conexão do Modo Manual (window.manualWs) e o ranking usava o endereço antigo
 * da Deriv (ws.derivws.com/websockets/v3), que não aceita mais o app. Resultado: "WebSocket não conectado!"
 * e ranking vazio.
 * Agora: uma conexão só do Contextual, na conta escolhida (demo/real), que compra, acompanha o contrato
 * até o fim e entrega o resultado para a lógica original (window._ctxOnContract(status, lucro)).
 * Para desfazer: remover este arquivo da página.
 */
(function () {
  'use strict';
  var APP_ID = '34lv1PuWzjElEuwWcDLyr', API = 'https://api.derivws.com/trading/v1/options';
  function feed(m, c) { try { if (typeof window.ctxAddFeed === 'function') window.ctxAddFeed(m, c); } catch (e) {} }
  function st() { return window._ctxState || {}; }

  /* ─────────── conexão própria ─────────── */
  var C = { ws: null, conta: null, abrindo: null, id: 1, pend: {}, subs: {}, ping: null };
  function tipoConta() { var c = st().conta || window.currentAccountType || localStorage.getItem('deriv_conta_ativa') || 'demo'; return /real/i.test(c) ? 'real' : 'demo'; }
  async function abrir() {
    var conta = tipoConta();
    if (C.ws && C.ws.readyState === 1 && C.conta === conta) return C.ws;
    if (C.abrindo && C.conta === conta) return C.abrindo;
    if (C.ws) { try { C.ws.close(); } catch (e) {} C.ws = null; }
    C.conta = conta;
    C.abrindo = (async function () {
      var tk = localStorage.getItem('deriv_bearer_token'); if (!tk) throw new Error('sem login na Deriv');
      var H = { Authorization: 'Bearer ' + tk, 'Deriv-App-ID': APP_ID };
      var r = await fetch(API + '/accounts', { headers: H }); if (!r.ok) throw new Error('contas HTTP ' + r.status);
      var contas = (await r.json()).data || [];
      var acct = contas.find(function (a) { return a.account_type === conta; });
      if (!acct) throw new Error('nenhuma conta ' + conta + ' no seu login');
      var o = await fetch(API + '/accounts/' + encodeURIComponent(acct.account_id) + '/otp', { method: 'POST', headers: H });
      var url = ((await o.json()).data || {}).url; if (!url) throw new Error('a Deriv não liberou a conexão (OTP)');
      var ws = await new Promise(function (res, rej) {
        var w = new WebSocket(url), t = setTimeout(function () { rej(new Error('tempo esgotado ao conectar')); try { w.close(); } catch (e) {} }, 10000);
        w.onopen = function () { clearTimeout(t); res(w); };
        w.onerror = function () { clearTimeout(t); rej(new Error('erro de conexão')); };
      });
      ws.onmessage = function (ev) {
        var m; try { m = JSON.parse(ev.data); } catch (e) { return; }
        if (m.msg_type === 'proposal_open_contract' && m.proposal_open_contract) {
          var poc = m.proposal_open_contract, h = C.subs[String(poc.contract_id)];
          if (m.req_id && C.pend[m.req_id]) { var e1 = C.pend[m.req_id]; delete C.pend[m.req_id]; e1(m); }
          if (h) h(poc);
          return;
        }
        if (m.req_id && C.pend[m.req_id]) { var cb = C.pend[m.req_id]; delete C.pend[m.req_id]; cb(m); }
      };
      ws.onclose = function () { if (C.ws === ws) C.ws = null; };
      clearInterval(C.ping); C.ping = setInterval(function () { if (C.ws && C.ws.readyState === 1) try { C.ws.send('{"ping":1}'); } catch (e) {} }, 25000);
      C.ws = ws; acctId = acct.account_id;
      return ws;
    })();
    try { return await C.abrindo; } finally { C.abrindo = null; }
  }
  var acctId = null;
  function pedir(obj, ms) {
    return new Promise(function (res, rej) {
      if (!C.ws || C.ws.readyState !== 1) return rej(new Error('sem conexão'));
      var id = C.id++; obj.req_id = id;
      var t = setTimeout(function () { delete C.pend[id]; rej(new Error('tempo esgotado')); }, ms || 15000);
      C.pend[id] = function (m) { clearTimeout(t); res(m); };
      C.ws.send(JSON.stringify(obj));
    });
  }

  /* ─────────── velas para o ranking de mercados ─────────── */
  window.ctxFetchMarketCandles = async function (symbol) {
    await abrir();
    var base = { ticks_history: symbol, count: 60, end: 'latest', style: 'candles', granularity: 60 };
    var r = await pedir(Object.assign({ underlying_symbol: symbol }, base), 10000);
    if (r.error) r = await pedir(Object.assign({}, base), 10000);
    if (r.error) throw new Error(r.error.message || 'erro');
    return (r.candles || []).map(function (c) { return { o: parseFloat(c.open), c: parseFloat(c.close) }; });
  };

  /* ─────────── compra + acompanhamento do contrato ─────────── */
  var chave = 'underlying_symbol';
  window.ctxExecutarTrade = async function (r) {
    var s = st();
    if (s.waiting || !s.running) return;
    s.waiting = true;
    var mercado = (document.getElementById('ctxMercado') || {}).value || '1HZ100V';
    var tipo = (document.getElementById('ctxTipo') || {}).value || 'CALL/PUT';
    var duracao = parseInt((document.getElementById('ctxDuracao') || {}).value || 1, 10) || 1;
    var par = tipo.split('/'), ct = r.direcao === 'UP' ? par[0] : par[1];
    var stake = +(+s.stakeAtual).toFixed(2);
    try { await abrir(); }
    catch (e) { feed('❌ Sem conexão com a Deriv: ' + e.message, '#ef4444'); s.waiting = false; return; }
    if (!s.running) { s.waiting = false; return; }

    feed('🚀 Entrada ' + r.direcao + ' · $' + stake.toFixed(2) + ' · Score ' + r.score + '%', r.direcao === 'UP' ? '#22c55e' : '#ef4444');
    function params(k) { var p = { amount: stake, basis: 'stake', contract_type: ct, currency: 'USD', duration: duracao, duration_unit: 't' }; p[k] = mercado; return p; }
    var b;
    try {
      b = await pedir({ buy: 1, price: stake, parameters: params(chave) }, 15000);
      if (b.error && /parameter|validation|symbol/i.test(b.error.message || '')) { chave = chave === 'underlying_symbol' ? 'symbol' : 'underlying_symbol'; b = await pedir({ buy: 1, price: stake, parameters: params(chave) }, 15000); }
      if (b.error) throw new Error(b.error.message || 'erro');
    } catch (e) { feed('🔴 Ordem recusada: ' + e.message, '#ef4444'); s.waiting = false; if (/not offered|duration|dura[cç][aã]o|not available|indispon/i.test(e.message || '') && typeof window._c2MarcarIncompat === 'function') window._c2MarcarIncompat(mercado); return; }

    var cid = String(b.buy.contract_id), feito = false;
    window._ctxUltimoContractId = cid;
    function fim(status, lucro) {
      if (feito) return; feito = true; delete C.subs[cid];
      try { window._ctxOnContract(status, lucro); } catch (e) { console.warn('[ctx-fix]', e); }
    }
    C.subs[cid] = function (poc) {
      var acabou = poc.is_sold || poc.status === 'won' || poc.status === 'lost';
      if (!acabou) return;
      var p = parseFloat(poc.profit); if (!isFinite(p)) p = poc.status === 'won' ? (parseFloat(poc.payout) - stake) : -stake;
      fim(poc.status || (p > 0 ? 'won' : 'lost'), p);
    };
    try { await pedir({ proposal_open_contract: 1, contract_id: +cid, subscribe: 1 }, 15000).catch(function () {}); } catch (e) {}
    setTimeout(function () { if (!feito && st().waiting) feed('⏳ Contrato #' + cid + ' ainda não fechou após 30s — aguardando o resultado real...', '#f59e0b'); }, 30000);
    // rede de segurança: pergunta o resultado direto se a atualização não chegar
    setTimeout(async function () {
      if (feito) return;
      try { var m = await pedir({ proposal_open_contract: 1, contract_id: +cid }, 15000); if (m.proposal_open_contract) C.subs[cid] && C.subs[cid](m.proposal_open_contract); } catch (e) {}
      if (!feito) { feito = true; delete C.subs[cid]; s.waiting = false; feed('⚠ Não recebi o resultado do contrato #' + cid + ' em 3 min — confira na Deriv. Robô liberado.', '#f59e0b'); }
    }, 180000);
  };

  /* fecha a conexão quando o robô parar (abre de novo sozinha no próximo início) */
  var estava = false;
  setInterval(function () {
    var r = !!st().running;
    if (estava && !r) setTimeout(function () { if (!st().running && C.ws && !Object.keys(C.subs).length) { try { C.ws.close(); } catch (e) {} C.ws = null; } }, 5000);
    if (!estava && r) abrir().catch(function (e) { feed('⚠ Conexão própria do Contextual: ' + e.message, '#f59e0b'); });
    estava = r;
  }, 1000);
})();
