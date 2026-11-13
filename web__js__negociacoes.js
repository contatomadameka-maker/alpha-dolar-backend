/* Alpha Dolar — aba NEGOCIACOES (Carteira + Historico)
 * Busca direto da Deriv todas as operacoes da conta ativa, de qualquer robo ou ferramenta.
 * - Carteira: posicoes abertas com lucro ao vivo (e botao de fechar quando a Deriv permite)
 * - Historico: operacoes fechadas com filtro de periodo, resumo e "carregar mais"
 */
(function () {
  'use strict';
  var APP_ID = '34lv1PuWzjElEuwWcDLyr';
  var API = 'https://api.derivws.com/trading/v1/options';
  var $ = function (id) { return document.getElementById(id); };
  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]; }); }
  function money(n) { n = Number(n) || 0; return (n < 0 ? '−$' : '$') + Math.abs(n).toFixed(2); }
  function sinal(n) { n = Number(n) || 0; return (n > 0 ? '+' : n < 0 ? '−' : '') + '$' + Math.abs(n).toFixed(2); }
  function T(s) { return window.i18n && window.i18n.t ? window.i18n.t(s) : s; }

  // textos novos no dicionario de traducao
  (function () {
    var d = window.i18n && window.i18n.dict; if (!d) return;
    var add = {
      'Hoje': ['Today', 'Hoy'], '7 dias': ['7 days', '7 días'], '30 dias': ['30 days', '30 días'], 'Tudo': ['All', 'Todo'],
      'Operações': ['Trades', 'Operaciones'], 'Vitórias': ['Wins', 'Victorias'], 'Derrotas': ['Losses', 'Derrotas'],
      'Resultado': ['Result', 'Resultado'], 'Carregar mais': ['Load more', 'Cargar más'], 'Atualizar': ['Refresh', 'Actualizar'],
      'Carregando operações…': ['Loading trades…', 'Cargando operaciones…'], 'Nenhuma operação neste período': ['No trades in this period', 'No hay operaciones en este período'],
      'Nenhuma posição aberta': ['No open positions', 'Ninguna posición abierta'], 'Fechar agora': ['Close now', 'Cerrar ahora'],
      'Fechar esta posição agora pelo valor atual?': ['Close this position now at the current value?', '¿Cerrar esta posición ahora al valor actual?'],
      'Ganhou': ['Won', 'Ganó'], 'Perdeu': ['Lost', 'Perdió'], 'Empate': ['Tie', 'Empate'], 'Entrada': ['Stake', 'Entrada'],
      'Lucro atual': ['Current P/L', 'Resultado actual'], 'Aberta há': ['Open for', 'Abierta hace'], 'Vence em': ['Expires in', 'Vence en'],
      'Sem conexão com a Deriv. Tentando de novo…': ['No connection to Deriv. Retrying…', 'Sin conexión con Deriv. Reintentando…'],
      'Faça login para ver suas operações.': ['Log in to see your trades.', 'Inicia sesión para ver tus operaciones.'],
      'Todas as operações da sua conta, de qualquer robô ou ferramenta.': ['All trades on your account, from any bot or tool.', 'Todas las operaciones de tu cuenta, de cualquier robot o herramienta.']
    };
    Object.keys(add).forEach(function (k) {
      if (d.en && !d.en[k]) d.en[k] = add[k][0];
      if (d.es && !d.es[k]) d.es[k] = add[k][1];
    });
  })();

  // ─── nomes amigaveis ───
  function mercado(s) {
    s = String(s || ''); var m;
    if ((m = s.match(/^R_(\d+)$/))) return 'Volatility ' + m[1];
    if ((m = s.match(/^1HZ(\d+)V$/))) return 'Volatility ' + m[1] + ' (1s)';
    if ((m = s.match(/^JD(\d+)$/))) return 'Jump ' + m[1];
    if ((m = s.match(/^BOOM(\d+)/))) return 'Boom ' + m[1];
    if ((m = s.match(/^CRASH(\d+)/))) return 'Crash ' + m[1];
    if ((m = s.match(/^frx([A-Z]{3})([A-Z]{3})$/))) return m[1] + '/' + m[2];
    if ((m = s.match(/^cry([A-Z]{3})([A-Z]{3})$/))) return m[1] + '/' + m[2];
    return s || '—';
  }
  function simbolo(c) {
    if (c.underlying_symbol) return c.underlying_symbol;
    if (c.underlying) return c.underlying;
    if (c.symbol) return c.symbol;
    var p = String(c.shortcode || '').split('_');     // ex: CALL_R_100_1.95_...  /  MULTUP_1HZ10V_10.00_...
    if (p.length > 2) return /^\d/.test(p[2]) ? p[1] : p[1] + '_' + p[2];
    return '';
  }
  function tipo(c) {
    var t = String(c.contract_type || ''), bar = '';
    var p = String(c.shortcode || '').split('_');
    if (/^DIGIT(OVER|UNDER|MATCH|DIFF)/.test(t)) bar = ' ' + (p[p.length - 1] || '');
    var map = { CALL: 'Rise ▲', PUT: 'Fall ▼', CALLE: 'Rise= ▲', PUTE: 'Fall= ▼', DIGITEVEN: 'Par', DIGITODD: 'Ímpar', DIGITOVER: 'Over', DIGITUNDER: 'Under',
      DIGITMATCH: 'Match', DIGITDIFF: 'Differs', MULTUP: 'Multiplier ▲', MULTDOWN: 'Multiplier ▼', ONETOUCH: 'Touch', NOTOUCH: 'No Touch',
      ACCU: 'Accumulator', TICKHIGH: 'High Tick', TICKLOW: 'Low Tick', RUNHIGH: 'Only Ups', RUNLOW: 'Only Downs' };
    var nome = map[t] || t;
    if (/^MULT/.test(t) && c.multiplier) nome += ' x' + c.multiplier;
    return nome + (bar && /^\d$/.test(bar.trim()) ? bar : '');
  }
  function hora(ep, comData) {
    var d = new Date(Number(ep) * 1000); if (!ep || isNaN(d)) return '—';
    var h = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0') + ':' + String(d.getSeconds()).padStart(2, '0');
    if (!comData) return h;
    return String(d.getDate()).padStart(2, '0') + '/' + String(d.getMonth() + 1).padStart(2, '0') + ' ' + h;
  }
  function duracao(s) { s = Math.max(0, Math.round(s)); if (s < 60) return s + 's'; if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's'; return Math.floor(s / 3600) + 'h ' + Math.floor(s % 3600 / 60) + 'm'; }

  // ─── estilo ───
  var css = document.createElement('style');
  css.textContent =
    '.ng-box{display:flex;flex-direction:column;gap:10px;padding:12px 14px;font-family:Inter,"Segoe UI",system-ui,sans-serif}' +
    '.ng-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}' +
    '.ng-chip{border:1px solid #23262e;background:#0a0d12;color:#94a3b8;font:700 12px Inter,system-ui,sans-serif;padding:6px 12px;border-radius:9px;cursor:pointer}' +
    '.ng-chip.on{background:rgba(139,92,246,.16);color:#c4b5fd;border-color:rgba(139,92,246,.45)}' +
    '.ng-chip:hover{color:#fff}' +
    '.ng-sp{margin-left:auto}' +
    '.ng-note{font-size:11.5px;color:#64748b}' +
    '.ng-sum{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}' +
    '.ng-sum div{background:#0a0d12;border:1px solid #1e2128;border-radius:12px;padding:10px 12px;display:flex;flex-direction:column;gap:3px}' +
    '.ng-sum span{font-size:10px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:#64748b}' +
    '.ng-sum b{font:700 16px "Space Mono",ui-monospace,monospace;color:#e2e8f0;font-variant-numeric:tabular-nums}' +
    '.ng-wrap{overflow-x:auto;border:1px solid #1e2128;border-radius:12px}' +
    '.ng-t{width:100%;border-collapse:collapse;font-size:12.5px;min-width:620px}' +
    '.ng-t th{text-align:left;font-size:10px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:#64748b;padding:9px 12px;border-bottom:1px solid #1e2128;background:#0e1117;position:sticky;top:0}' +
    '.ng-t td{padding:9px 12px;border-bottom:1px solid rgba(255,255,255,.04);color:#cbd5e1;white-space:nowrap}' +
    '.ng-t td.n{font-family:"Space Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}' +
    '.ng-t tr:hover td{background:rgba(255,255,255,.02)}' +
    '.ng-w{color:#4ade80 !important}.ng-l{color:#f87171 !important}' +
    '.ng-pill{font-size:10px;font-weight:900;padding:2px 8px;border-radius:6px}' +
    '.ng-pill.w{background:rgba(34,197,94,.14);color:#4ade80}.ng-pill.l{background:rgba(239,68,68,.14);color:#f87171}.ng-pill.e{background:rgba(148,163,184,.14);color:#94a3b8}' +
    '.ng-more{align-self:center}' +
    '.ng-empty{text-align:center;color:#64748b;padding:36px 12px;font-size:13px}' +
    '.ng-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}' +
    '.ng-card{background:#0a0d12;border:1px solid #1e2128;border-radius:14px;padding:12px 14px;display:flex;flex-direction:column;gap:6px}' +
    '.ng-card h4{margin:0;font-size:13px;font-weight:800;color:#e2e8f0;display:flex;justify-content:space-between;gap:8px}' +
    '.ng-card h4 small{font-weight:600;color:#64748b}' +
    '.ng-row{display:flex;justify-content:space-between;font-size:12px;color:#94a3b8}' +
    '.ng-row b{font:700 12.5px "Space Mono",ui-monospace,monospace;color:#e2e8f0}' +
    '.ng-big{font:700 20px "Space Mono",ui-monospace,monospace}' +
    '.ng-sell{margin-top:4px;border:0;border-radius:10px;padding:8px;font:800 12px Inter,system-ui,sans-serif;color:#fff;background:linear-gradient(135deg,#dc2626,#ef4444);cursor:pointer}' +
    '.ng-sell:disabled{opacity:.5;cursor:not-allowed}' +
    '@media (max-width:600px){.ng-sum{grid-template-columns:repeat(2,minmax(0,1fr))}.ng-box{padding:10px}}';
  document.head.appendChild(css);

  // ─── conexao Deriv (propria, so enquanto a aba estiver aberta) ───
  var S = { ws: null, ok: false, conta: null, acct: null, reqId: 1, pend: {}, abertos: {}, hist: [], periodo: 'hoje', offset: 0, fim: false, carregando: false, ultimaCarga: 0 };
  setInterval(function () { if (S.ws && S.ws.readyState === 1) { try { S.ws.send('{"ping":1}'); } catch (e) {} } }, 25000);
  function contaAtiva() { return ls('deriv_conta_ativa') === 'real' ? 'real' : 'demo'; }
  function send(o, to) {
    return new Promise(function (res, rej) {
      if (!S.ws || S.ws.readyState !== 1) return rej(new Error('sem conexao'));
      var id = S.reqId++; o.req_id = id;
      var t = setTimeout(function () { delete S.pend[id]; rej(new Error('tempo esgotado')); }, to || 15000);
      S.pend[id] = function (m) { clearTimeout(t); res(m); };
      S.ws.send(JSON.stringify(o));
    });
  }
  function conectar() {
    if (S.conectando) return S.conectando;
    S.conectando = (async function () {
      var tk = ls('deriv_bearer_token');
      if (!tk) { mostrarAviso(T('Faça login para ver suas operações.')); throw new Error('sem token'); }
      var H = { Authorization: 'Bearer ' + tk, 'Deriv-App-ID': APP_ID };
      var r = await fetch(API + '/accounts', { headers: H });
      if (!r.ok) throw new Error('contas HTTP ' + r.status);
      var contas = (await r.json()).data || [];
      S.conta = contaAtiva();
      S.acct = contas.find(function (a) { return a.account_type === S.conta; }) || null;
      if (!S.acct) throw new Error('sem conta ' + S.conta);
      var o = await fetch(API + '/accounts/' + encodeURIComponent(S.acct.account_id) + '/otp', { method: 'POST', headers: H });
      if (!o.ok) throw new Error('OTP HTTP ' + o.status);
      var url = ((await o.json()).data || {}).url;
      if (!url) throw new Error('OTP sem url');
      await new Promise(function (res, rej) {
        var ws = new WebSocket(url); S.ws = ws;
        ws.onopen = function () { S.ok = true; res(); };
        ws.onerror = function () { rej(new Error('erro ws')); };
        ws.onclose = function () { if (S.ws === ws) { S.ok = false; S.ws = null; S.pend = {}; } };
        ws.onmessage = function (ev) {
          var m; try { m = JSON.parse(ev.data); } catch (e) { return; }
          if (m.req_id && S.pend[m.req_id] && !(m.msg_type === 'proposal_open_contract' && m.subscription)) { var cb = S.pend[m.req_id]; delete S.pend[m.req_id]; cb(m); }
          if (m.msg_type === 'proposal_open_contract' && m.proposal_open_contract) aoVivo(m.proposal_open_contract);
        };
      });
    })();
    return S.conectando.finally(function () { S.conectando = null; });
  }
  async function pronto() {
    if (S.ws && S.ws.readyState === 1 && S.conta === contaAtiva()) return;
    if (S.ws) { try { S.ws.close(); } catch (e) {} S.ws = null; }
    S.abertos = {}; S.hist = []; S.offset = 0; S.fim = false;
    await conectar();
    try { S.ws.send(JSON.stringify({ proposal_open_contract: 1, subscribe: 1 })); } catch (e) {}   // todas as posicoes abertas ao vivo
  }

  // ─── CARTEIRA ───
  var carteira = null;
  function montarCarteira() {
    var box = $('neg-carteira'); if (!box || carteira) return;
    Array.prototype.forEach.call(box.children, function (c) { c.style.display = 'none'; });
    carteira = document.createElement('div'); carteira.className = 'ng-box';
    carteira.innerHTML = '<div class="ng-top"><span class="ng-note">' + esc(T('Todas as operações da sua conta, de qualquer robô ou ferramenta.')) + '</span>' +
      '<button class="ng-chip ng-sp" type="button" data-ng="refresh-c">↻ ' + esc(T('Atualizar')) + '</button></div><div class="ng-cards" id="ngCards"></div>';
    box.appendChild(carteira);
    carteira.querySelector('[data-ng="refresh-c"]').onclick = function () { carregarCarteira(); };
  }
  async function carregarCarteira() {
    montarCarteira();
    try {
      await pronto();
      var r = await send({ portfolio: 1 });
      if (r.error) throw new Error(r.error.message);
      var vivos = {};
      (r.portfolio.contracts || []).forEach(function (c) {
        var id = String(c.contract_id); vivos[id] = 1;
        S.abertos[id] = Object.assign({ contract_id: c.contract_id, contract_type: c.contract_type, buy_price: c.buy_price, purchase_time: c.purchase_time,
          date_expiry: c.expiry_time, underlying: simbolo(c), shortcode: c.shortcode }, S.abertos[id] || {});
      });
      Object.keys(S.abertos).forEach(function (id) { if (!vivos[id] && !S.abertos[id].__vivo) delete S.abertos[id]; });
      desenharCarteira();
    } catch (e) { mostrarAviso(T('Sem conexão com a Deriv. Tentando de novo…')); }
  }
  function aoVivo(p) {
    var id = String(p.contract_id); if (!id) return;
    if (p.is_sold || p.status === 'won' || p.status === 'lost' || p.status === 'sold') {
      if (S.abertos[id]) { delete S.abertos[id]; desenharCarteira(); setTimeout(function () { recarregarHistorico(); }, 1500); }
      return;
    }
    S.abertos[id] = Object.assign(S.abertos[id] || {}, p, { __vivo: true, underlying: simbolo(p) || (S.abertos[id] || {}).underlying });
    desenharCarteira();
  }
  var desenhoT = null;
  function desenharCarteira() {
    if (desenhoT) return;
    desenhoT = setTimeout(function () {
      desenhoT = null;
      var el = $('ngCards'); if (!el) return;
      var ids = Object.keys(S.abertos);
      if (!ids.length) { el.innerHTML = '<div class="ng-empty" style="grid-column:1/-1"><div style="font-size:34px;opacity:.3">📂</div>' + esc(T('Nenhuma posição aberta')) + '</div>'; return; }
      var agora = Date.now() / 1000;
      el.innerHTML = ids.map(function (id) {
        var c = S.abertos[id], lucro = Number(c.profit), temLucro = isFinite(lucro);
        var venc = c.date_expiry && !/^MULT|^ACCU/.test(c.contract_type) ? '<div class="ng-row">' + esc(T('Vence em')) + ' <b>' + duracao(c.date_expiry - agora) + '</b></div>' : '';
        var vender = c.is_valid_to_sell ? '<button class="ng-sell" type="button" data-sell="' + esc(id) + '">' + esc(T('Fechar agora')) + (c.bid_price ? ' · ' + money(c.bid_price) : '') + '</button>' : '';
        return '<div class="ng-card"><h4>' + esc(tipo(c)) + ' <small>' + esc(mercado(c.underlying)) + '</small></h4>' +
          '<div class="ng-big ' + (temLucro ? (lucro >= 0 ? 'ng-w' : 'ng-l') : '') + '">' + (temLucro ? sinal(lucro) : '—') + '</div>' +
          '<div class="ng-row">' + esc(T('Entrada')) + ' <b>' + money(c.buy_price) + '</b></div>' +
          '<div class="ng-row">' + esc(T('Aberta há')) + ' <b>' + duracao(agora - (c.purchase_time || c.date_start || agora)) + '</b></div>' + venc +
          '<div class="ng-row">#' + esc(id) + ' <b>' + hora(c.purchase_time || c.date_start) + '</b></div>' + vender + '</div>';
      }).join('');
      Array.prototype.forEach.call(el.querySelectorAll('[data-sell]'), function (b) {
        b.onclick = async function () {
          if (!confirm(T('Fechar esta posição agora pelo valor atual?'))) return;
          b.disabled = true;
          try { var r = await send({ sell: Number(b.getAttribute('data-sell')), price: 0 }); if (r.error) { alert(r.error.message); b.disabled = false; } }
          catch (e) { b.disabled = false; }
        };
      });
    }, 150);
  }

  // ─── HISTORICO ───
  var hbox = null;
  function montarHistorico() {
    var box = $('neg-historico'); if (!box || hbox) return;
    Array.prototype.forEach.call(box.children, function (c) { c.style.display = 'none'; });
    hbox = document.createElement('div'); hbox.className = 'ng-box';
    hbox.innerHTML =
      '<div class="ng-top">' +
        ['hoje|Hoje', '7|7 dias', '30|30 dias', 'tudo|Tudo'].map(function (x) { var p = x.split('|'); return '<button class="ng-chip' + (p[0] === S.periodo ? ' on' : '') + '" type="button" data-per="' + p[0] + '">' + esc(T(p[1])) + '</button>'; }).join('') +
        '<button class="ng-chip ng-sp" type="button" data-ng="refresh-h">↻ ' + esc(T('Atualizar')) + '</button>' +
      '</div>' +
      '<div class="ng-sum"><div><span>' + esc(T('Operações')) + '</span><b id="ngQ">—</b></div><div><span>' + esc(T('Vitórias')) + '</span><b id="ngW">—</b></div>' +
        '<div><span>' + esc(T('Derrotas')) + '</span><b id="ngL">—</b></div><div><span>' + esc(T('Resultado')) + '</span><b id="ngP">—</b></div></div>' +
      '<div class="ng-wrap"><table class="ng-t"><thead><tr><th>' + esc(T('Hora')) + '</th><th>' + esc(T('Tipo')) + '</th><th>' + esc(T('Mercado')) + '</th><th>' + esc(T('Entrada')) + '</th><th>' + esc(T('Resultado')) + '</th><th>' + esc(T('Lucro')) + '</th><th>#</th></tr></thead><tbody id="ngBody"></tbody></table></div>' +
      '<button class="ng-chip ng-more" type="button" id="ngMore" hidden>' + esc(T('Carregar mais')) + '</button>';
    box.appendChild(hbox);
    Array.prototype.forEach.call(hbox.querySelectorAll('[data-per]'), function (b) {
      b.onclick = function () {
        S.periodo = b.getAttribute('data-per');
        Array.prototype.forEach.call(hbox.querySelectorAll('[data-per]'), function (x) { x.classList.toggle('on', x === b); });
        recarregarHistorico();
      };
    });
    hbox.querySelector('[data-ng="refresh-h"]').onclick = function () { recarregarHistorico(); };
    $('ngMore').onclick = function () { carregarHistorico(false); };
  }
  function desde() {
    var d = new Date();
    if (S.periodo === 'hoje') { d.setHours(0, 0, 0, 0); return Math.floor(d / 1000); }
    if (S.periodo === '7') return Math.floor(Date.now() / 1000) - 7 * 86400;
    if (S.periodo === '30') return Math.floor(Date.now() / 1000) - 30 * 86400;
    return 0;
  }
  function recarregarHistorico() { S.hist = []; S.offset = 0; S.fim = false; carregarHistorico(true); }
  async function carregarHistorico(limpar) {
    montarHistorico();
    if (S.carregando) return; S.carregando = true;
    var body = $('ngBody');
    if (limpar && body) body.innerHTML = '<tr><td colspan="7" class="ng-empty">' + esc(T('Carregando operações…')) + '</td></tr>';
    try {
      await pronto();
      var req = { profit_table: 1, description: 1, sort: 'DESC', limit: 100, offset: S.offset };
      var dt = desde(); if (dt) req.date_from = dt;
      var r = await send(req, 20000);
      if (r.error) throw new Error(r.error.message);
      var tx = (r.profit_table && r.profit_table.transactions) || [];
      S.hist = S.hist.concat(tx); S.offset += tx.length; S.fim = tx.length < 100;
      desenharHistorico();
    } catch (e) {
      if (body) body.innerHTML = '<tr><td colspan="7" class="ng-empty">' + esc(T('Sem conexão com a Deriv. Tentando de novo…')) + '</td></tr>';
      setTimeout(function () { if (visivel()) recarregarHistorico(); }, 5000);
    } finally { S.carregando = false; S.ultimaCarga = Date.now(); }
  }
  function desenharHistorico() {
    var body = $('ngBody'); if (!body) return;
    var w = 0, l = 0, tot = 0;
    if (!S.hist.length) body.innerHTML = '<tr><td colspan="7" class="ng-empty">' + esc(T('Nenhuma operação neste período')) + '</td></tr>';
    else body.innerHTML = S.hist.map(function (t) {
      var p = (Number(t.sell_price) || 0) - (Number(t.buy_price) || 0);
      p = Math.round(p * 100) / 100; tot += p;
      var res = p > 0 ? 'w' : p < 0 ? 'l' : 'e'; if (p > 0) w++; else if (p < 0) l++;
      var nome = res === 'w' ? 'Ganhou' : res === 'l' ? 'Perdeu' : 'Empate';
      return '<tr title="' + esc(t.longcode || '') + '"><td class="n">' + hora(t.sell_time || t.purchase_time, true) + '</td><td>' + esc(tipo(t)) + '</td><td>' + esc(mercado(simbolo(t))) + '</td>' +
        '<td class="n">' + money(t.buy_price) + '</td><td><span class="ng-pill ' + res + '">' + esc(T(nome)) + '</span></td>' +
        '<td class="n ' + (p > 0 ? 'ng-w' : p < 0 ? 'ng-l' : '') + '">' + sinal(p) + '</td><td class="n" style="color:#475569">' + esc(t.contract_id) + '</td></tr>';
    }).join('');
    var q = S.hist.length;
    $('ngQ').textContent = q + (S.fim ? '' : '+');
    $('ngW').textContent = w + (q ? ' (' + Math.round(w / q * 100) + '%)' : '');
    $('ngL').textContent = l;
    var P = $('ngP'); P.textContent = sinal(tot); P.className = tot > 0 ? 'ng-w' : tot < 0 ? 'ng-l' : '';
    $('ngMore').hidden = S.fim;
  }

  function mostrarAviso(msg) {
    var el = $('ngCards'); if (el) el.innerHTML = '<div class="ng-empty" style="grid-column:1/-1">' + esc(msg) + '</div>';
    var b = $('ngBody'); if (b) b.innerHTML = '<tr><td colspan="7" class="ng-empty">' + esc(msg) + '</td></tr>';
  }

  // ─── liga quando a aba NEGOCIACOES esta aberta ───
  function visivel() { var t = $('tab-negociacoes'); return !!(t && t.offsetParent !== null && t.getClientRects().length); }
  var estavaVisivel = false, contaVista = contaAtiva(), ultimaCarteira = 0;
  setInterval(function () {
    var v = visivel();
    if (contaAtiva() !== contaVista) { contaVista = contaAtiva(); if (v) { carregarCarteira(); recarregarHistorico(); } else { S.hist = []; } }
    if (v && !estavaVisivel) { carregarCarteira(); ultimaCarteira = Date.now(); if (!S.hist.length || Date.now() - S.ultimaCarga > 30000) recarregarHistorico(); }
    if (v && Date.now() - ultimaCarteira > 15000) { carregarCarteira(); ultimaCarteira = Date.now(); }
    if (v && Object.keys(S.abertos).length) desenharCarteira();      // atualiza os contadores de tempo
    estavaVisivel = v;
  }, 1000);
})();
