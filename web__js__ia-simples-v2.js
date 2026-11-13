/* Alpha Dolar — IA Simples v2 (estilo DC)
 * 1) Mercado / Estrategia / Modo / Risco / Limite abrem DENTRO do painel da IA (nao por cima do grafico)
 * 2) Robo rodando: fica dentro do painel, configuracoes recolhiveis e lista das operacoes embaixo
 * Para desfazer: basta remover este arquivo da pagina.
 */
(function () {
  'use strict';
  var PICKERS = ['marketModal', 'strategyModal', 'tradingModeModal', 'riskModal', 'stopLossModal'];
  var RUN = 'botRunningModal';
  var APP_ID = '34lv1PuWzjElEuwWcDLyr';
  var API = 'https://api.derivws.com/trading/v1/options';
  var $ = function (id) { return document.getElementById(id); };
  function T(s) { return window.i18n && window.i18n.t ? window.i18n.t(s) : s; }
  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]; }); }
  function imp(el, p, v) { el.style.setProperty(p, v, 'important'); }

  (function () {
    var d = window.i18n && window.i18n.dict; if (!d) return;
    var add = { 'Configurações': ['Settings', 'Configuración'], 'Ganhos/Perdas': ['Wins/Losses', 'Ganancias/Pérdidas'],
      'Todos': ['All', 'Todos'], 'Ganhos': ['Wins', 'Ganancias'], 'Perdas': ['Losses', 'Pérdidas'], 'Ganho': ['Win', 'Ganancia'],
      'Perda': ['Loss', 'Pérdida'], 'Em andamento': ['In progress', 'En curso'], 'Entrada': ['Stake', 'Entrada'],
      'As operações desta sessão aparecem aqui.': ['Trades from this session appear here.', 'Las operaciones de esta sesión aparecen aquí.'] };
    Object.keys(add).forEach(function (k) { if (d.en && !d.en[k]) d.en[k] = add[k][0]; if (d.es && !d.es[k]) d.es[k] = add[k][1]; });
  })();

  // ─── estilo ───
  var css = document.createElement('style');
  css.textContent =
    '.ias-ov{background:transparent!important;backdrop-filter:none!important;-webkit-backdrop-filter:none!important}' +
    '.ias-box{background:#15171d!important;border:1px solid #262a33!important;border-radius:16px!important;box-shadow:0 18px 50px rgba(0,0,0,.55)!important;overflow:hidden auto!important;animation:iasIn .16s ease-out}' +
    '@keyframes iasIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}' +
    '.ias-box .modal-header{padding:14px 16px!important;background:#15171d!important;border-bottom:1px solid #22252d!important}' +
    '.ias-box .modal-header h3{font-size:15px!important;margin:0!important}' +
    '.ias-box .modal-header button{width:30px!important;height:30px!important;min-width:30px!important;padding:0!important}' +
    '.ias-box>:not(.modal-header){zoom:.8}' +
    '.ias-box::-webkit-scrollbar,.ias-rbox::-webkit-scrollbar{width:6px}.ias-box::-webkit-scrollbar-thumb,.ias-rbox::-webkit-scrollbar-thumb{background:#3b82f6;border-radius:6px}' +
    '.ias-rbox>:not(.ias-ops):not(.ias-cfg-btn):not(#stopBotBtn){zoom:.8}' +
    '.ias-rbox #stopBotBtn{padding:12px!important;min-height:0!important;height:auto!important;font-size:15px!important;border-radius:12px!important}' +
    '.ias-run{pointer-events:none!important}' +
    '.ias-run>*{pointer-events:auto}' +
    '.ias-rbox{background:#15171d!important;border:1px solid #262a33!important;border-radius:16px!important;box-shadow:0 18px 50px rgba(0,0,0,.5)!important;overflow:hidden auto!important;display:flex!important;flex-direction:column!important;gap:10px!important;padding:16px!important;box-sizing:border-box!important}' +
    '.ias-rbox #stopBotBtn{position:sticky!important;bottom:0!important;margin-top:auto!important;z-index:2;flex-shrink:0}' +
    '.ias-cfg-btn{display:flex;align-items:center;gap:10px;width:100%;background:transparent;border:0;border-top:1px solid #262a33;border-bottom:1px solid #262a33;color:#e2e8f0;font:700 13px Inter,system-ui,sans-serif;padding:10px 2px;cursor:pointer;flex-shrink:0}' +
    '.ias-cfg-btn .ic{width:26px;height:26px;border-radius:50%;border:1.5px solid #60a5fa;display:grid;place-items:center;color:#60a5fa;font-size:14px}' +
    '.ias-cfg-btn .ch{margin-left:auto;transition:transform .2s;color:#94a3b8}' +
    '.ias-cfg-btn.on{border-color:#60a5fa}.ias-cfg-btn.on .ch{transform:rotate(180deg)}' +
    '.ias-rbox .bot-config-display.ias-fechado{display:none!important}' +
    '.ias-ops{display:flex;flex-direction:column;gap:8px;font-family:Inter,system-ui,sans-serif;flex-shrink:0}' +
    '.ias-ops-top{display:flex;align-items:center;justify-content:flex-end;gap:8px;font-size:12.5px;color:#94a3b8}' +
    '.ias-ops-top b.w{color:#4ade80}.ias-ops-top b.l{color:#f87171}' +
    '.ias-fil{margin-left:6px;border:1px solid #2c313b;background:transparent;color:#e2e8f0;border-radius:999px;padding:6px 14px;font:800 11.5px Inter,system-ui,sans-serif;letter-spacing:.4px;cursor:pointer}' +
    '.ias-op{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;align-items:center;gap:12px;background:#0d0f14;border:1px solid #1f232b;border-radius:12px;padding:10px 12px}' +
    '.ias-op small{display:block;font-size:10.5px;color:#64748b;font-weight:600}' +
    '.ias-op b{font:700 13px "Space Mono",ui-monospace,monospace;color:#e2e8f0;font-variant-numeric:tabular-nums;white-space:nowrap}' +
    '.ias-op .t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:Inter,system-ui,sans-serif}' +
    '.ias-op .r{text-align:right}.ias-op .r b.w{color:#4ade80}.ias-op .r b.l{color:#f87171}.ias-op .r b.a{color:#fbbf24}' +
    '.ias-op.a{border-color:rgba(251,191,36,.35)}' +
    '.ias-vazio{text-align:center;color:#64748b;font-size:12.5px;padding:18px 8px;border:1px dashed #262a33;border-radius:12px}';
  document.head.appendChild(css);

  // ─── posicao: em cima do painel da IA ───
  function painel() {
    var p = document.querySelector('aside.left-panel');
    if (!p) return null;
    var r = p.getBoundingClientRect();
    if (r.width < 200 || r.height < 200) return null;
    return r;
  }
  function visivel(el) {
    if (!el) return false;
    var cs = getComputedStyle(el);
    return cs.display !== 'none' && cs.visibility !== 'hidden' && el.getClientRects().length > 0;
  }
  function limpaOv(ov, run) {
    ['background', 'backdrop-filter', '-webkit-backdrop-filter', 'transform', 'filter', 'perspective', 'contain', 'zoom'].forEach(function (p) {
      imp(ov, p, p === 'background' ? 'transparent' : p === 'zoom' ? '1' : 'none');
    });
    if (run) imp(ov, 'pointer-events', 'none');
  }
  var ancora = null;   // campo do painel que foi clicado por ultimo
  document.addEventListener('click', function (e) {
    var p = e.target && e.target.closest && e.target.closest('aside.left-panel');
    if (!p) return;
    var f = e.target.closest('.form-group, .input-group, [onclick], button') || e.target;
    ancora = f.getBoundingClientRect().top;
  }, true);
  function corrigir(box, left, top) {
    var a = box.getBoundingClientRect();
    if (Math.abs(a.left - left) > 1) imp(box, 'left', (parseFloat(box.style.left) + left - a.left) + 'px');
    if (Math.abs(a.top - top) > 1) imp(box, 'top', (parseFloat(box.style.top) + top - a.top) + 'px');
  }
  function encaixar(box, r, altura) {
    var top = Math.max(r.top, 8) + 8;
    var bot = Math.min(r.bottom, innerHeight - 8) - 8;
    var left = Math.max(r.left, 0) + 8;
    var w = Math.min(r.width, innerWidth) - 16;
    imp(box, 'position', 'fixed'); imp(box, 'left', left + 'px'); imp(box, 'top', top + 'px');
    imp(box, 'right', 'auto'); imp(box, 'bottom', 'auto'); imp(box, 'transform', 'none'); imp(box, 'margin', '0');
    imp(box, 'box-sizing', 'border-box'); imp(box, 'zoom', '1');
    imp(box, 'width', w + 'px'); imp(box, 'max-width', w + 'px'); imp(box, 'min-width', '0');
    if (altura) {
      imp(box, 'max-height', Math.max(240, bot - top) + 'px'); imp(box, 'height', Math.max(240, bot - top) + 'px');
    } else {   // lista: tamanho de dropdown, com rolagem, aberta perto do campo clicado
      var maxH = Math.min(520, bot - top);
      imp(box, 'height', 'auto'); imp(box, 'max-height', maxH + 'px');
      var h = Math.min(box.getBoundingClientRect().height || maxH, maxH);
      var t = top;   // sempre no topo do painel, como no DC
      top = Math.max(top, t); imp(box, 'top', top + 'px');
    }
    corrigir(box, left, top);
  }
  function arrumarPicker(ov) {
    var box = ov.querySelector('.modal-container'); var r = painel();
    if (!box || !r) return;
    ov.classList.add('ias-ov'); limpaOv(ov, false); box.classList.add('ias-box');
    encaixar(box, r, false);
    if (!ov.__ias) {
      ov.__ias = true;
      ov.addEventListener('mousedown', function (e) {       // clicar fora fecha
        if (e.target !== ov) return;
        var x = ov.querySelector('.modal-header button, .modal-close, [onclick*="close"], [onclick*="fechar"]');
        if (x) x.click(); else ov.style.display = 'none';
      });
    }
  }
  function arrumarRun(ov) {
    var box = ov.querySelector('.modal-container-bot-running'); var r = painel();
    if (!box || !r) return;
    ov.classList.add('ias-ov', 'ias-run'); limpaOv(ov, true); box.classList.add('ias-rbox');
    encaixar(box, r, true);
    montarRun(box);
  }
  function tudo() {
    PICKERS.forEach(function (id) { var ov = $(id); if (visivel(ov)) arrumarPicker(ov); });
    var run = $(RUN);
    if (visivel(run)) { arrumarRun(run); iniciarOps(); } else pararOps();
  }
  var fila = 0;
  function agendar() { if (fila) return; fila = requestAnimationFrame(function () { fila = 0; tudo(); }); }
  function observar() {
    PICKERS.concat([RUN]).forEach(function (id) {
      var el = $(id); if (!el || el.__iasObs) return; el.__iasObs = true;
      new MutationObserver(agendar).observe(el, { attributes: true, attributeFilter: ['style', 'class'] });
    });
  }
  addEventListener('resize', agendar); addEventListener('scroll', agendar, true);
  document.addEventListener('DOMContentLoaded', function () { observar(); agendar(); });
  addEventListener('load', function () { observar(); agendar(); setTimeout(observar, 2000); });
  setInterval(function () { observar(); tudo(); }, 1500);

  // ─── robo rodando: configuracoes recolhiveis + lista de operacoes ───
  var ops = null;
  function montarRun(box) {
    var cfg = box.querySelector('.bot-config-display');
    if (cfg && !cfg.__ias) {
      cfg.__ias = true;
      var b = document.createElement('button'); b.type = 'button'; b.className = 'ias-cfg-btn';
      b.innerHTML = '<span class="ic">⚙</span><span>' + esc(T('Configurações')) + '</span><span class="ch">▾</span>';
      cfg.parentNode.insertBefore(b, cfg);
      var aberto = ls('ias_cfg') === '1';
      var aplica = function () { cfg.classList.toggle('ias-fechado', !aberto); b.classList.toggle('on', aberto); };
      aplica();
      b.onclick = function () { aberto = !aberto; lsSet('ias_cfg', aberto ? '1' : '0'); aplica(); };
    }
    if (!box.querySelector('.ias-ops')) {
      ops = document.createElement('div'); ops.className = 'ias-ops';
      ops.innerHTML = '<div class="ias-ops-top"><span>' + esc(T('Ganhos/Perdas')) + '</span><b class="w" data-w>0</b><b class="l" data-l>0</b>' +
        '<button type="button" class="ias-fil" data-fil>☰ ' + esc(T('Todos')) + '</button></div><div data-lista></div>';
      var stop = $('stopBotBtn');
      if (stop && stop.parentNode === box) box.insertBefore(ops, stop); else box.appendChild(ops);
      ops.querySelector('[data-fil]').onclick = function () {
        O.filtro = O.filtro === 'todos' ? 'ganhos' : O.filtro === 'ganhos' ? 'perdas' : 'todos';
        this.textContent = '☰ ' + T(O.filtro === 'todos' ? 'Todos' : O.filtro === 'ganhos' ? 'Ganhos' : 'Perdas');
        desenhar();
      };
      desenhar();
    }
  }

  // ─── dados da Deriv (so enquanto o robo roda) ───
  var O = { ws: null, pend: {}, id: 1, conta: null, desde: 0, fechadas: [], abertas: {}, filtro: 'todos', timer: null, ativo: false, fechaT: null, conectando: null };
  window.__iasOps = O; window.__iasTipo = function (c) { return tipo(c); };  // IA Alpha lê as operações da IA Simples daqui
  function contaAtiva() { try { var p = sessionStorage.getItem('ias_conta'); if (p && O.ativo) return p; } catch (e) {} return ls('deriv_conta_ativa') === 'real' ? 'real' : 'demo'; } /* IAS-FIX-V1 */
  function send(o) {
    return new Promise(function (res, rej) {
      if (!O.ws || O.ws.readyState !== 1) return rej(new Error('sem conexao'));
      var id = O.id++; o.req_id = id;
      var t = setTimeout(function () { delete O.pend[id]; rej(new Error('timeout')); }, 15000);
      O.pend[id] = function (m) { clearTimeout(t); res(m); };
      O.ws.send(JSON.stringify(o));
    });
  }
  function conectar() {
    if (O.conectando) return O.conectando;
    O.conectando = (async function () {
      var tk = ls('deriv_bearer_token'); if (!tk) throw new Error('sem token');
      var H = { Authorization: 'Bearer ' + tk, 'Deriv-App-ID': APP_ID };
      var contas = ((await (await fetch(API + '/accounts', { headers: H })).json()).data) || [];
      O.conta = contaAtiva();
      var acct = contas.find(function (a) { return a.account_type === O.conta; });
      if (!acct) throw new Error('sem conta');
      var url = (((await (await fetch(API + '/accounts/' + encodeURIComponent(acct.account_id) + '/otp', { method: 'POST', headers: H })).json()).data) || {}).url;
      if (!url) throw new Error('sem otp');
      await new Promise(function (res, rej) {
        var ws = new WebSocket(url); O.ws = ws;
        ws.onopen = function () { res(); try { ws.send(JSON.stringify({ proposal_open_contract: 1, subscribe: 1 })); } catch (e) {} };
        ws.onerror = function () { rej(new Error('ws')); };
        ws.onclose = function () { if (O.ws === ws) { O.ws = null; O.pend = {}; } };
        ws.onmessage = function (ev) {
          var m; try { m = JSON.parse(ev.data); } catch (e) { return; }
          if (m.req_id && O.pend[m.req_id] && m.msg_type !== 'proposal_open_contract') { var cb = O.pend[m.req_id]; delete O.pend[m.req_id]; cb(m); }
          if (m.msg_type === 'proposal_open_contract' && m.proposal_open_contract) aoVivo(m.proposal_open_contract);
        };
      });
    })();
    return O.conectando.finally(function () { O.conectando = null; });
  }
  function aoVivo(c) {
    if (!c.contract_id || (c.purchase_time && c.purchase_time < O.desde)) return;
    if (c.is_sold || c.status === 'won' || c.status === 'lost' || c.status === 'sold') {
      delete O.abertas[c.contract_id]; setTimeout(buscar, 1200);
    } else O.abertas[c.contract_id] = c;
    desenhar();
  }
  async function buscar() {
    if (!O.ativo) return;
    try {
      if (!O.ws || O.ws.readyState !== 1 || O.conta !== contaAtiva()) { if (O.ws) try { O.ws.close(); } catch (e) {} O.ws = null; await conectar(); }
      var r = await send({ profit_table: 1, description: 1, sort: 'DESC', limit: 50, date_from: O.desde });
      O.fechadas = (r.profit_table && r.profit_table.transactions) || [];
      O.fechadas.forEach(function (t) { delete O.abertas[t.contract_id]; });
      desenhar();
    } catch (e) {}
  }
  function iniciarOps() {
    clearTimeout(O.fechaT); O.fechaT = null;
    if (O.ativo) return;
    O.ativo = true;
    var s = 0; try { s = Number(sessionStorage.getItem('ias_desde')) || 0; } catch (e) {}
    if (!s || Date.now() / 1000 - s > 12 * 3600) { s = Math.floor(Date.now() / 1000) - 5; try { sessionStorage.setItem('ias_desde', s); } catch (e) {} }
    O.desde = s; O.fechadas = []; O.abertas = {};
    buscar(); O.timer = setInterval(buscar, 5000);
  }
  function pararOps() {
    if (!O.ativo) return;
    O.ativo = false; clearInterval(O.timer); O.timer = null;
    try { sessionStorage.removeItem('ias_desde'); } catch (e) {}
    O.fechaT = setTimeout(function () { if (!O.ativo && O.ws) { try { O.ws.close(); } catch (e) {} O.ws = null; } }, 30000);
  }

  // ─── desenho da lista ───
  function hora(ep) {
    var d = new Date(Number(ep) * 1000); if (isNaN(d)) return '—';
    var p = function (n) { return String(n).padStart(2, '0'); };
    return { d: p(d.getDate()) + '/' + p(d.getMonth() + 1), h: p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()) };
  }
  function tipo(c) {
    var t = c.contract_type || String(c.shortcode || '').split('_')[0];
    var m = { CALL: 'Rise ▲', PUT: 'Fall ▼', CALLE: 'Rise ▲', PUTE: 'Fall ▼', DIGITEVEN: 'Par', DIGITODD: 'Ímpar', DIGITOVER: 'Over', DIGITUNDER: 'Under', DIGITMATCH: 'Match', DIGITDIFF: 'Differs' };
    return m[t] || t || '—';
  }
  function linha(c, aberta) {
    var hr = hora(c.purchase_time), stake = Number(c.buy_price) || 0;
    var lucro = aberta ? Number(c.profit) || 0 : (Number(c.sell_price) || 0) - stake;
    var cls = aberta ? 'a' : lucro > 0 ? 'w' : 'l';
    var rot = aberta ? T('Em andamento') : lucro > 0 ? T('Ganho') : T('Perda');
    return '<div class="ias-op' + (aberta ? ' a' : '') + '">' +
      '<div><small>' + hr.d + '</small><b>' + hr.h + '</b></div>' +
      '<div class="t"><small>' + esc(tipo(c)) + '</small><b class="t">' + esc(T('Entrada')) + ' $' + stake.toFixed(2) + '</b></div>' +
      '<div></div>' +
      '<div class="r"><b class="' + cls + '">' + (lucro > 0 ? '+' : lucro < 0 ? '−' : '') + '$' + Math.abs(lucro).toFixed(2) + '</b><small>' + esc(rot) + '</small></div></div>';
  }
  var dT = 0;
  function desenhar() {
    if (!ops) return;
    clearTimeout(dT);
    dT = setTimeout(function () {
      var w = 0, l = 0;
      O.fechadas.forEach(function (t) { if ((Number(t.sell_price) || 0) - (Number(t.buy_price) || 0) > 0) w++; else l++; });
      ops.querySelector('[data-w]').textContent = w; ops.querySelector('[data-l]').textContent = l;
      var html = '';
      if (O.filtro === 'todos') Object.keys(O.abertas).forEach(function (id) { html += linha(O.abertas[id], true); });
      O.fechadas.forEach(function (t) {
        var g = (Number(t.sell_price) || 0) - (Number(t.buy_price) || 0) > 0;
        if (O.filtro === 'todos' || (O.filtro === 'ganhos') === g) html += linha(t, false);
      });
      ops.querySelector('[data-lista]').innerHTML = html || '<div class="ias-vazio">' + esc(T('As operações desta sessão aparecem aqui.')) + '</div>';
      ops.querySelector('[data-lista]').style.cssText = 'display:flex;flex-direction:column;gap:8px';
    }, 60);
  }
})();

/* ─── GERENCIAMENTO DE RISCO v6 (tela nova + Raio-X) ───
 * - "Gerenciamento de risco" abre uma tela propria em cima do painel da IA (cartoes, Raio-X em barras, acelerador, Salvar)
 * - Salvar chama o selectRiskMode original: o robo recebe o modo exatamente como antes
 * - Conta igual a do robo: aposta = (perda acumulada + entrada x acelerador) / (lucro do payout x 0.98)
 * - Tentativas por modo = presets do backend (fixed 0, conservative 2, optimized 3, aggressive 5)
 */
(function () {
  'use strict';
  var PAYOUT = 0.79, ACERTO = 0.5;
  var SVG = {
    fixed: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/></svg>',
    conservative: '<svg viewBox="0 0 24 24" fill="#fff"><path d="M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5l-8-3z"/></svg>',
    optimized: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round"><path d="M4 19V11M10 19V7M16 19v-5M22 19V4"/></svg>',
    aggressive: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/></svg>'
  };
  var MODOS = [
    { id: 'fixed', nome: 'Quantia fixa', nivel: 'Sem recuperação', cor: '#818cf8', grad: 'linear-gradient(135deg,#6366f1,#818cf8)', passos: 0, rec: 10, risco: 1, desc: 'Toda operação usa a mesma entrada. Uma perda custa só a entrada.' },
    { id: 'conservative', nome: 'Conservador', nivel: 'Baixo risco', cor: '#4ade80', grad: 'linear-gradient(135deg,#16a34a,#4ade80)', passos: 2, rec: 50, risco: 2, desc: 'Até 2 recuperações curtas. Se não recuperar, aceita a perda e recomeça.' },
    { id: 'optimized', nome: 'Otimizado', nivel: 'Médio risco', cor: '#fbbf24', grad: 'linear-gradient(135deg,#f59e0b,#fbbf24)', passos: 3, rec: 100, risco: 3, desc: 'Até 3 recuperações. Mais chance de sair no positivo, mais saldo em jogo.' },
    { id: 'aggressive', nome: 'Agressivo', nivel: 'Alto risco', cor: '#f87171', grad: 'linear-gradient(135deg,#dc2626,#f87171)', passos: 5, rec: 200, risco: 4, desc: 'Até 5 recuperações. As entradas sobem rápido e comprometem mais do saldo.' }
  ];
  function T(s) { return window.i18n && window.i18n.t ? window.i18n.t(s) : s; }
  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]; }); }
  function num(s) { var m = String(s || '').replace(/[^\d.,-]/g, '').replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.'); var n = parseFloat(m); return isNaN(n) ? 0 : n; }
  function m$(n) { return '$' + n.toFixed(2); }
  function modoPor(id) { for (var i = 0; i < MODOS.length; i++) if (MODOS[i].id === id) return MODOS[i]; return MODOS[1]; }

  (function () {
    var d = window.i18n && window.i18n.dict; if (!d) return;
    var add = {
      'Gerenciamento de risco': ['Risk management', 'Gestión de riesgo'], 'Como cada modo funciona': ['How each mode works', 'Cómo funciona cada modo'],
      'Quantia fixa': ['Fixed amount', 'Monto fijo'], 'Conservador': ['Conservative', 'Conservador'], 'Otimizado': ['Optimized', 'Optimizado'], 'Agressivo': ['Aggressive', 'Agresivo'],
      'Sem recuperação': ['No recovery', 'Sin recuperación'], 'Baixo risco': ['Low risk', 'Riesgo bajo'], 'Médio risco': ['Medium risk', 'Riesgo medio'], 'Alto risco': ['High risk', 'Riesgo alto'],
      'Toda operação usa a mesma entrada. Uma perda custa só a entrada.': ['Every trade uses the same stake. A loss costs only the stake.', 'Toda operación usa la misma entrada. Una pérdida cuesta solo la entrada.'],
      'Até 2 recuperações curtas. Se não recuperar, aceita a perda e recomeça.': ['Up to 2 short recoveries. If it does not recover, it accepts the loss and restarts.', 'Hasta 2 recuperaciones cortas. Si no recupera, acepta la pérdida y reinicia.'],
      'Até 3 recuperações. Mais chance de sair no positivo, mais saldo em jogo.': ['Up to 3 recoveries. More chance to end positive, more balance at stake.', 'Hasta 3 recuperaciones. Más chance de terminar en positivo, más saldo en juego.'],
      'Até 5 recuperações. As entradas sobem rápido e comprometem mais do saldo.': ['Up to 5 recoveries. Stakes rise fast and commit more of the balance.', 'Hasta 5 recuperaciones. Las entradas suben rápido y comprometen más del saldo.'],
      'Raio-X do risco': ['Risk X-ray', 'Rayos X del riesgo'], 'pode investir em': ['may invest across', 'puede invertir en'], 'entradas': ['stakes', 'entradas'], 'do saldo': ['of balance', 'del saldo'],
      'entrada': ['stake', 'entrada'], 'rec': ['rec', 'rec'], 'por operação perdida · sem aumento de entrada': ['per lost trade · stake never increases', 'por operación perdida · sin aumento de entrada'],
      'Perder as': ['Losing all', 'Perder las'], 'entradas seguidas acontece, em média,': ['stakes in a row happens, on average,', 'entradas seguidas ocurre, en promedio,'],
      '1 vez a cada': ['once every', '1 vez cada'], 'operações': ['trades', 'operaciones'],
      'Se perder todas, o robô aceita a perda e volta para a entrada inicial.': ['If all are lost, the bot accepts the loss and goes back to the initial stake.', 'Si pierde todas, el robot acepta la pérdida y vuelve a la entrada inicial.'],
      'Passa do seu limite de perda — o robô para antes do fim da sequência.': ['Exceeds your loss limit — the bot stops before the end of the sequence.', 'Supera tu límite de pérdida — el robot se detiene antes del final de la secuencia.'],
      'Acelerador de lucro': ['Profit accelerator', 'Acelerador de ganancia'], 'por recuperação': ['per recovery', 'por recuperación'],
      'Quanto a mais cada recuperação tenta ganhar. Recomendado: 1.00x': ['How much extra each recovery tries to win. Recommended: 1.00x', 'Cuánto más intenta ganar cada recuperación. Recomendado: 1.00x'],
      'Conta com pagamento de ~79% e acerto de ~50% dos índices sintéticos. Não é garantia de resultado.': ['Estimate with ~79% payout and ~50% win rate on synthetic indices. Not a guarantee of results.', 'Cálculo con pago de ~79% y acierto de ~50% en índices sintéticos. No es garantía de resultado.'],
      'Salvar': ['Save', 'Guardar'], 'Investe até': ['Invests up to', 'Invierte hasta'], 'em': ['in', 'en'], 'Entrada fixa de': ['Fixed stake of', 'Entrada fija de'],
      'Valor recomendado: no mínimo': ['Recommended amount: at least', 'Monto recomendado: mínimo']
    };
    Object.keys(add).forEach(function (k) { if (d.en && !d.en[k]) d.en[k] = add[k][0]; if (d.es && !d.es[k]) d.es[k] = add[k][1]; });
  })();

  // envia o acelerador junto com o start da IA Simples (o robo ja aceita "multiplicador")
  function acel() { var v = parseFloat(ls('ias_acel')); return v >= 1 && v <= 3 ? v : 1; }
  (function () {
    var f0 = window.fetch; if (!f0 || f0.__acel) return;
    var f = function (u, o) {
      try {
        var s = typeof u === 'string' ? u : (u && u.url) || '';
        if (/\/bot\/start/.test(s) && o && typeof o.body === 'string') {
          var b = JSON.parse(o.body), a = acel();
          if ((b.bot_type || 'ia') === 'ia' && a > 1 && b.origem !== 'ia_avancado' && !(b.config && b.config.origem === 'ia_avancado')) {
            b.multiplicador = a; if (b.config && typeof b.config === 'object') b.config.multiplicador = a;
            o = Object.assign({}, o, { body: JSON.stringify(b) });
          }
        }
      } catch (e) {}
      return f0.call(this, u, o);
    };
    f.__acel = true; window.fetch = f;
  })();

  var css = document.createElement('style');
  css.textContent =
    '.rg-ov{position:fixed;inset:0;z-index:99990;background:transparent;display:none}' +
    '.rg-scr{position:fixed;z-index:99991;display:none;flex-direction:column;background:#0f1116;border:1px solid #23262e;border-radius:18px;box-shadow:0 18px 60px rgba(0,0,0,.6);overflow:hidden;font-family:Inter,system-ui,sans-serif;color:#e2e8f0;animation:rgIn .16s ease-out}' +
    '@keyframes rgIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}' +
    '.rg-scr button{font-family:inherit}' +
    '.rg-sh{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid #23262e;flex-shrink:0}' +
    '.rg-sh h2{margin:0;font-size:16px;font-weight:900}' +
    '.rg-x{width:30px;height:30px;border-radius:10px;border:1px solid rgba(248,113,113,.4);background:rgba(248,113,113,.08);color:#f87171;font-size:15px;cursor:pointer}' +
    '.rg-sb{padding:12px 14px;overflow:auto;display:flex;flex-direction:column;gap:11px;flex:1}' +
    '.rg-sb::-webkit-scrollbar{width:6px}.rg-sb::-webkit-scrollbar-thumb{background:#3b82f6;border-radius:6px}' +
    '.rg-how{border:1px solid #23262e;border-radius:12px;background:#0d0f14}' +
    '.rg-how>button{width:100%;display:flex;justify-content:space-between;align-items:center;background:transparent;border:0;color:#e2e8f0;font-weight:700;font-size:12.5px;padding:10px 12px;cursor:pointer}' +
    '.rg-how ul{display:none;margin:0;padding:0 12px 11px;list-style:none;flex-direction:column;gap:7px}.rg-how.on ul{display:flex}' +
    '.rg-how li{font-size:11.5px;color:#94a3b8;display:flex;gap:8px;line-height:1.45}.rg-how li b{color:#e2e8f0}.rg-how li i{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:5px}' +
    '.rg-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}' +
    '.rg-mode{position:relative;background:#0d0f14;border:1.5px solid #23262e;border-radius:15px;padding:12px 8px 10px;display:flex;flex-direction:column;align-items:center;gap:5px;cursor:pointer;text-align:center;transition:border-color .15s,transform .15s}' +
    '.rg-mode:hover{transform:translateY(-1px)}.rg-mode b{font-size:13px}.rg-mode>span{font-size:10.5px;font-weight:700}' +
    '.rg-ck{position:absolute;top:7px;right:7px;width:19px;height:19px;border-radius:50%;background:#4ade80;color:#052e16;font-size:11px;font-weight:900;display:none;place-items:center}.rg-mode.sel .rg-ck{display:grid}' +
    '.rg-ico{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;flex-shrink:0}.rg-ico svg{width:22px;height:22px}' +
    '.rg-meter{display:flex;gap:3px;margin-top:1px}.rg-meter i{width:13px;height:5px;border-radius:3px;background:#262a33}' +
    '.rg-box{background:#0d0f14;border:1px solid #23262e;border-radius:14px}' +
    '.rg-rx{padding:12px 13px}.rg-rxh{font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:#64748b}' +
    '.rg-big{font:700 27px "Space Mono",ui-monospace,monospace;color:#4ade80;margin:6px 0 2px;font-variant-numeric:tabular-nums;line-height:1.1}' +
    '.rg-sub{font-size:11.5px;color:#94a3b8}.rg-sub b{color:#4ade80}' +
    '.rg-bars{display:flex;align-items:flex-end;gap:5px;height:88px;margin:16px 0 4px;padding-bottom:17px}' +
    '.rg-bar{flex:1;border-radius:7px 7px 3px 3px;background:linear-gradient(180deg,rgba(139,92,246,.9),rgba(99,102,241,.45));position:relative;min-height:6px;transition:height .35s}' +
    '.rg-bar.last{background:linear-gradient(180deg,rgba(74,222,128,.95),rgba(74,222,128,.4))}' +
    '.rg-bar em{position:absolute;bottom:-16px;left:50%;transform:translateX(-50%);font:700 9px "Space Mono",ui-monospace,monospace;color:#94a3b8;font-style:normal;white-space:nowrap}' +
    '.rg-bar u{position:absolute;top:-14px;left:50%;transform:translateX(-50%);font-size:8.5px;font-weight:700;color:#64748b;text-decoration:none;white-space:nowrap}' +
    '.rg-odds{display:flex;gap:9px;align-items:flex-start;background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.22);border-radius:10px;padding:8px 10px;font-size:11.5px;margin-top:9px;line-height:1.4}' +
    '.rg-odds b{color:#fbbf24;font-family:"Space Mono",ui-monospace,monospace}' +
    '.rg-dots{display:flex;gap:3px;flex-wrap:wrap;margin-top:5px}.rg-dots i{width:6px;height:6px;border-radius:2px;background:#262a33}.rg-dots i.hit{background:#fbbf24}' +
    '.rg-reset{font-size:11px;color:#94a3b8;margin-top:8px}' +
    '.rg-warn{background:rgba(248,113,113,.08);border:1px solid rgba(248,113,113,.3);border-radius:10px;padding:7px 10px;font-size:11.5px;color:#fca5a5;margin-top:8px}' +
    '.rg-acel{padding:12px 13px;display:flex;flex-direction:column;gap:8px}' +
    '.rg-acel .t{display:flex;justify-content:space-between;align-items:center;gap:8px}.rg-acel .t b{font-size:13px}' +
    '.rg-pill{font-size:10.5px;font-weight:800;background:#1e2230;border-radius:999px;padding:4px 9px;color:#60a5fa;white-space:nowrap}' +
    '.rg-acel small{font-size:11px;color:#64748b}' +
    '.rg-stp{display:grid;grid-template-columns:42px 1fr 42px;gap:8px}.rg-stp button{height:40px;border-radius:11px;border:1px solid #2c313b;background:#1a1d24;color:#e2e8f0;font-size:19px;cursor:pointer}' +
    '.rg-stp div{height:40px;border-radius:11px;border:1px solid #2c313b;display:grid;place-items:center;font:700 15px "Space Mono",ui-monospace,monospace;color:#60a5fa}' +
    '.rg-note{font-size:10px;color:#64748b;text-align:center}' +
    '.rg-sf{padding:11px 14px 14px;border-top:1px solid #23262e;flex-shrink:0}' +
    '.rg-save{width:100%;background:linear-gradient(135deg,#6366f1,#8b5cf6);border:0;border-radius:13px;color:#fff;font-weight:800;font-size:14.5px;padding:13px;cursor:pointer}' +
    /* cartao do painel */
    '.rg-pc{margin-top:8px;background:#0d0f14;border:1px solid #1f232b;border-radius:14px;overflow:hidden;font-family:Inter,system-ui,sans-serif}' +
    '.rg-pch{display:flex;align-items:center;gap:10px;width:100%;background:transparent;border:0;color:#e2e8f0;padding:10px 13px;cursor:pointer;text-align:left;font-family:inherit}' +
    '.rg-pch .ic{width:24px;height:24px;border-radius:7px;display:grid;place-items:center;background:rgba(96,165,250,.14);color:#60a5fa;font-size:12px;flex-shrink:0}' +
    '.rg-pch .tx{display:flex;flex-direction:column;gap:1px;min-width:0}.rg-pch small{font-size:9.5px;font-weight:800;letter-spacing:.7px;text-transform:uppercase;color:#64748b}' +
    '.rg-pch span.r{font-size:12px;color:#cbd5e1}.rg-pch span.r b{color:#4ade80;font-family:"Space Mono",ui-monospace,monospace}' +
    '.rg-pch .ch{margin-left:auto;color:#94a3b8;transition:transform .2s}.rg-pc.on .rg-pch .ch{transform:rotate(180deg)}' +
    '.rg-pc .rg-rxh{display:none}.rg-pc .rg-rx{display:none;border-top:1px solid #1f232b}.rg-pc.on .rg-rx{display:block}';
  document.head.appendChild(css);

  // ─── dados do painel ───
  function raiz() { return document.getElementById('iaSimpleMode'); }
  function atual() { var m = String(window.selectedRiskMode || ''); return modoPor(m).id === m ? m : 'conservative'; }
  function entradas() {
    var r = raiz(), ins = r ? r.querySelectorAll('.value-inputs-grid input') : [];
    return { stake: ins[0] ? num(ins[0].value) : 0, limite: ins[2] ? num(ins[2].value) : 0 };
  }
  function saldo() {
    var ids = ['topBalance', 'balanceValue', 'accountBalance', 'saldoTopo'];
    for (var i = 0; i < ids.length; i++) { var e = document.getElementById(ids[i]); if (e && num(e.textContent) > 0) return num(e.textContent); }
    return 0;
  }
  function seq(m, s0, a) {
    var r = PAYOUT * 0.98, perda = 0, out = [];
    for (var i = 0; i <= m.passos; i++) {
      var s = i === 0 ? s0 : Math.max(s0, (perda + s0 * a) / r);
      s = Math.round(s * 100) / 100; out.push(s); perda += s;
    }
    return out;
  }
  function cada(k) { var q = 1 - ACERTO, qk = Math.pow(q, k); return Math.round((1 - qk) / ((1 - q) * qk)); }
  function soma(a) { return a.reduce(function (x, y) { return x + y; }, 0); }
  function resumo(m, a) {
    var e = entradas(), s0 = e.stake || 0.35, sq = seq(m, s0, a), t = soma(sq), sd = saldo();
    if (!m.passos) return T('Entrada fixa de') + ' <b>' + m$(s0) + '</b>';
    return T('Investe até') + ' <b>' + m$(t) + '</b> ' + T('em') + ' ' + sq.length + ' ' + T('entradas') + (sd ? ' · ' + (t / sd * 100).toFixed(2) + '% ' + T('do saldo') : '');
  }
  function rxHTML(m, a) {
    var e = entradas(), s0 = e.stake || 0.35, sd = saldo(), sq = seq(m, s0, a), t = soma(sq), mx = Math.max.apply(null, sq);
    if (!m.passos) return '<div class="rg-rx"><div class="rg-rxh">◎ ' + T('Raio-X do risco') + '</div><div class="rg-big">' + m$(s0) + '</div><div class="rg-sub">' + T('por operação perdida · sem aumento de entrada') + '</div></div>';
    var bars = sq.map(function (v, i) {
      return '<div class="rg-bar' + (i === sq.length - 1 ? ' last' : '') + '" style="height:' + Math.max(8, v / mx * 100) + '%"><u>' + (i ? i + 'ª ' + T('rec') : T('entrada')) + '</u><em>' + m$(v) + '</em></div>';
    }).join('');
    var n = cada(sq.length), k = Math.min(n, 60), dots = '';
    for (var i = 0; i < k; i++) dots += '<i' + (i === k - 1 ? ' class="hit"' : '') + '></i>';
    return '<div class="rg-rx"><div class="rg-rxh">◎ ' + T('Raio-X do risco') + '</div><div class="rg-big">' + m$(t) + '</div>' +
      '<div class="rg-sub">' + T('pode investir em') + ' ' + sq.length + ' ' + T('entradas') + (sd ? ' · <b>' + (t / sd * 100).toFixed(2) + '% ' + T('do saldo') + '</b>' : '') + '</div>' +
      '<div class="rg-bars">' + bars + '</div>' +
      '<div class="rg-odds">⚠<div>' + T('Perder as') + ' ' + sq.length + ' ' + T('entradas seguidas acontece, em média,') + ' <b>' + T('1 vez a cada') + ' ~' + n + '</b> ' + T('operações') + (n <= 60 ? '<div class="rg-dots">' + dots + '</div>' : '') + '</div></div>' +
      (e.limite > 0 && t > e.limite ? '<div class="rg-warn">' + T('Passa do seu limite de perda — o robô para antes do fim da sequência.') + '</div>' : '') +
      '<div class="rg-reset">↩ ' + T('Se perder todas, o robô aceita a perda e volta para a entrada inicial.') + '</div></div>';
  }

  // ─── cartao no painel (embaixo do botao de risco) ───
  var pc = null, pcChave = '';
  function aplicarIcone() {
    var m = modoPor(atual()), ic = document.querySelector('#riskButton .risk-icon');
    if (ic) { ic.style.background = m.grad; ic.innerHTML = SVG[m.id]; var s = ic.querySelector('svg'); if (s) { s.style.width = '24px'; s.style.height = '24px'; } }
  }
  function painelCard() {
    var btn = document.getElementById('riskButton'); if (!btn) return;
    var velho = btn.parentNode.querySelector('.rx'); if (velho) velho.remove();   // Raio-X da versao anterior
    if (!pc || !document.body.contains(pc)) {
      pc = document.createElement('div'); pc.className = 'rg-pc' + (ls('rg_pc') === '1' ? ' on' : '');
      pc.innerHTML = '<button type="button" class="rg-pch"><span class="ic">◎</span><span class="tx"><small></small><span class="r"></span></span><span class="ch">▾</span></button><div data-rx></div>';
      btn.parentNode.insertBefore(pc, btn.nextSibling);
      pc.querySelector('.rg-pch').onclick = function () { pc.classList.toggle('on'); lsSet('rg_pc', pc.classList.contains('on') ? '1' : '0'); };
      pcChave = '';
    }
    var m = modoPor(atual()), a = acel(), e = entradas();
    var chave = [m.id, a, e.stake, e.limite, saldo(), window.i18n && window.i18n.current].join('|');
    if (chave === pcChave) return; pcChave = chave;
    pc.querySelector('small').textContent = T('Raio-X do risco');
    pc.querySelector('.r').innerHTML = resumo(m, a);
    pc.querySelector('[data-rx]').innerHTML = rxHTML(m, a);
    aplicarIcone();
  }

  // ─── tela nova ───
  var ov = null, scr = null, sel = null, acelTmp = 1;
  function montarTela() {
    if (scr) return;
    ov = document.createElement('div'); ov.className = 'rg-ov';
    scr = document.createElement('div'); scr.className = 'rg-scr';
    document.body.appendChild(ov); document.body.appendChild(scr);
    ov.addEventListener('mousedown', fechar);
  }
  function posicionar() {
    if (!scr || scr.style.display !== 'flex') return;
    var p = document.querySelector('aside.left-panel'), r = p ? p.getBoundingClientRect() : null;
    if (!r || r.width < 200) {
      var w = Math.min(400, innerWidth - 24);
      scr.style.left = ((innerWidth - w) / 2) + 'px'; scr.style.top = '12px'; scr.style.width = w + 'px'; scr.style.height = (innerHeight - 24) + 'px'; return;
    }
    var top = Math.max(r.top, 8) + 8, bot = Math.min(r.bottom, innerHeight - 8) - 8;
    scr.style.left = (Math.max(r.left, 0) + 8) + 'px'; scr.style.top = top + 'px';
    scr.style.width = (Math.min(r.width, innerWidth) - 16) + 'px'; scr.style.height = Math.max(420, bot - top) + 'px';
  }
  function meter(n, c) { var h = '<div class="rg-meter">'; for (var i = 0; i < 4; i++) h += '<i' + (i < n ? ' style="background:' + c + '"' : '') + '></i>'; return h + '</div>'; }
  function desenharTela() {
    var m = modoPor(sel), aberto = scr.querySelector('.rg-how.on') ? ' on' : '';
    var sbTop = scr.querySelector('.rg-sb') ? scr.querySelector('.rg-sb').scrollTop : 0;
    scr.innerHTML =
      '<div class="rg-sh"><h2>' + T('Gerenciamento de risco') + '</h2><button type="button" class="rg-x" data-f>✕</button></div>' +
      '<div class="rg-sb">' +
      '<div class="rg-how' + aberto + '"><button type="button" data-how>' + T('Como cada modo funciona') + ' <span>▾</span></button><ul>' +
      MODOS.map(function (x) { return '<li><i style="background:' + x.cor + '"></i><div><b>' + esc(T(x.nome)) + '</b> — ' + esc(T(x.desc)) + '</div></li>'; }).join('') + '</ul></div>' +
      '<div class="rg-grid">' + MODOS.map(function (x) {
        var on = x.id === sel;
        return '<div class="rg-mode' + (on ? ' sel' : '') + '" data-m="' + x.id + '" style="' + (on ? 'border-color:' + x.cor : '') + '"><span class="rg-ck">✓</span>' +
          '<div class="rg-ico" style="background:' + x.grad + '">' + SVG[x.id] + '</div><b>' + esc(T(x.nome)) + '</b><span style="color:' + x.cor + '">● ' + esc(T(x.nivel)) + '</span>' + meter(x.risco, x.cor) + '</div>';
      }).join('') + '</div>' +
      '<div class="rg-box">' + rxHTML(m, acelTmp) + '</div>' +
      (m.passos ? '<div class="rg-box rg-acel"><div class="t"><b>' + T('Acelerador de lucro') + '</b><span class="rg-pill">' + acelTmp.toFixed(2) + 'x ' + T('por recuperação') + '</span></div>' +
        '<small>' + T('Quanto a mais cada recuperação tenta ganhar. Recomendado: 1.00x') + '</small>' +
        '<div class="rg-stp"><button type="button" data-a="-">−</button><div>' + acelTmp.toFixed(2) + 'x</div><button type="button" data-a="+">+</button></div></div>' : '') +
      '<div class="rg-note">' + T('Conta com pagamento de ~79% e acerto de ~50% dos índices sintéticos. Não é garantia de resultado.') + '</div>' +
      '</div><div class="rg-sf"><button type="button" class="rg-save" data-s>' + T('Salvar') + '</button></div>';
    scr.querySelector('.rg-sb').scrollTop = sbTop;
    scr.querySelector('[data-f]').onclick = fechar;
    scr.querySelector('[data-how]').onclick = function () { this.parentNode.classList.toggle('on'); };
    Array.prototype.forEach.call(scr.querySelectorAll('[data-m]'), function (el) { el.onclick = function () { sel = el.getAttribute('data-m'); desenharTela(); }; });
    Array.prototype.forEach.call(scr.querySelectorAll('[data-a]'), function (b) {
      b.onclick = function () { acelTmp = Math.min(3, Math.max(1, Math.round((acelTmp + (b.getAttribute('data-a') === '+' ? 0.25 : -0.25)) * 100) / 100)); desenharTela(); };
    });
    scr.querySelector('[data-s]').onclick = salvar;
  }
  function abrir() {
    montarTela(); sel = atual(); acelTmp = acel();
    try { var old = document.getElementById('riskModal'); if (old) old.classList.remove('active'); } catch (e) {}
    ov.style.display = 'block'; scr.style.display = 'flex';
    desenharTela(); posicionar();
  }
  function fechar() { if (scr) scr.style.display = 'none'; if (ov) ov.style.display = 'none'; }
  var selectOriginal = null;
  function salvar() {
    var m = modoPor(sel);
    lsSet('ias_acel', String(acelTmp));
    var fn = selectOriginal || window.selectRiskMode;
    try {
      if (typeof fn === 'function') fn({ id: m.id, name: T(m.nome), level: T(m.nivel), description: T('Valor recomendado: no mínimo') + ' $' + m.rec, color: m.cor });
      else window.selectedRiskMode = m.id;
    } catch (e) { window.selectedRiskMode = m.id; }
    fechar(); pcChave = ''; painelCard();
  }
  function ligar() {
    if (typeof window.selectRiskMode === 'function' && !window.selectRiskMode.__rg) selectOriginal = window.selectRiskMode;
    if (!window.openRiskModal || !window.openRiskModal.__rg) { var f = function () { abrir(); }; f.__rg = true; window.openRiskModal = f; }
  }
  ligar();
  document.addEventListener('DOMContentLoaded', function () { ligar(); painelCard(); });
  addEventListener('load', function () { ligar(); painelCard(); setTimeout(function () { ligar(); painelCard(); }, 2000); });
  addEventListener('resize', posicionar); addEventListener('scroll', posicionar, true);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') fechar(); });
  document.addEventListener('input', function (ev) { if (ev.target && ev.target.closest && ev.target.closest('#iaSimpleMode')) painelCard(); }, true);
  addEventListener('alpha:idioma', function () { pcChave = ''; painelCard(); if (scr && scr.style.display === 'flex') desenharTela(); });
  setInterval(function () { ligar(); painelCard(); posicionar(); }, 1500);
})();

/* ─── CAMPOS COMPACTOS (v7): Quantia inicial | Lucro alvo | Limite de perda lado a lado, estilo DC ─── */
(function () {
  'use strict';
  var css = document.createElement('style');
  css.textContent =
    '#iaSimpleMode .value-inputs-grid{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:8px!important;align-items:start!important}' +
    '#iaSimpleMode .value-inputs-grid>*{min-width:0!important;width:auto!important;margin:0!important;grid-column:auto!important}' +
    '#iaSimpleMode .value-inputs-grid label{display:flex!important;align-items:center!important;justify-content:space-between!important;gap:4px!important;min-height:22px!important;margin:0 0 6px!important;font-size:12px!important;font-weight:700!important;letter-spacing:0!important;text-transform:none!important;color:#e2e8f0!important;white-space:nowrap!important;overflow:hidden!important}' +
    '#iaSimpleMode .value-inputs-grid label button,#iaSimpleMode .value-inputs-grid [onclick*="topLoss"],#iaSimpleMode .value-inputs-grid .fa-cog,#iaSimpleMode .value-inputs-grid svg{flex-shrink:0}' +
    '#iaSimpleMode .value-inputs-grid>* :has(>input){display:flex!important;align-items:center!important;gap:6px!important;height:42px!important;min-height:0!important;padding:0 12px!important;border-radius:999px!important;background:#0b0d12!important;border:1px solid #2a2e37!important;box-sizing:border-box!important;width:100%!important;min-width:0!important}' +
    '#iaSimpleMode .value-inputs-grid>* :has(>input):focus-within{border-color:#6366f1!important;box-shadow:0 0 0 3px rgba(99,102,241,.18)!important}' +
    '#iaSimpleMode .value-inputs-grid>*>input{height:42px!important;padding:0 14px!important;border-radius:999px!important;background:#0b0d12!important;border:1px solid #2a2e37!important;box-sizing:border-box!important;width:100%!important;min-width:0!important;color:#fff!important;font:600 16px Inter,system-ui,sans-serif!important}' +
    '#iaSimpleMode .value-inputs-grid>* :has(>input) input{flex:1 1 auto!important;width:100%!important;min-width:0!important;height:auto!important;padding:0!important;margin:0!important;border:0!important;outline:0!important;background:transparent!important;box-shadow:none!important;color:#fff!important;font:600 16px Inter,system-ui,sans-serif!important}' +
    '#iaSimpleMode .value-inputs-grid>* :has(>input)>span,#iaSimpleMode .value-inputs-grid>* :has(>input)>i{flex-shrink:0!important;color:#94a3b8!important;font-size:14px!important;font-weight:700!important;margin:0!important;position:static!important}' +
    '#iaSimpleMode .value-inputs-grid small,#iaSimpleMode .value-inputs-grid .input-hint,#iaSimpleMode .value-inputs-grid .ias-pct{display:block!important;margin:5px 0 0 4px!important;font-size:10.5px!important;color:#60a5fa!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}' +
    '@media (max-width:380px){#iaSimpleMode .value-inputs-grid{gap:6px!important}#iaSimpleMode .value-inputs-grid>* :has(>input){padding:0 9px!important}#iaSimpleMode .value-inputs-grid label{font-size:11px!important}}';
  document.head.appendChild(css);

  // "% do saldo" certo (usa o saldo mostrado no topo)
  function num(s) { var m = String(s || '').replace(/[^\d.,-]/g, '').replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.'); var n = parseFloat(m); return isNaN(n) ? 0 : n; }
  function saldo() {
    var ids = ['topBalance', 'balanceValue', 'accountBalance', 'saldoTopo'];
    for (var i = 0; i < ids.length; i++) { var e = document.getElementById(ids[i]); if (e && num(e.textContent) > 0) return num(e.textContent); }
    return 0;
  }
  function T(s) { return window.i18n && window.i18n.t ? window.i18n.t(s) : s; }
  function corrigir() {
    var r = document.getElementById('iaSimpleMode'), sd = saldo(); if (!r || !sd) return;
    Array.prototype.forEach.call(r.querySelectorAll('.value-inputs-grid > *'), function (g) {
      var inp = g.querySelector('input'); if (!inp) return;
      var v = num(inp.value), p = v / sd * 100, txt = (p > 0 && p < 0.01 ? '<0.01' : p < 1 ? p.toFixed(2) : p.toFixed(1)) + '% ' + T('do saldo');
      var el = null;
      Array.prototype.forEach.call(g.querySelectorAll('*'), function (x) { if (!el && x.children.length === 0 && /%/.test(x.textContent) && x !== inp) el = x; });
      if (el && el.textContent !== txt) el.textContent = txt;
    });
  }
  document.addEventListener('input', function (e) { if (e.target && e.target.closest && e.target.closest('#iaSimpleMode')) setTimeout(corrigir, 30); }, true);
  addEventListener('load', function () { setTimeout(corrigir, 500); });
  setInterval(corrigir, 1500);
})();
