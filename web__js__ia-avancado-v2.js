/* Alpha Dolar — IA AVANÇADO v2 (layout novo, igual à amostra aprovada)
 * Monta a tela nova e MOVE os campos originais (pelos ids) para dentro dela.
 * Os campos são os mesmos elementos, com os mesmos cliques: a lógica do robô não muda.
 * Dígitos: lidos das mensagens de tick que a própria página já recebe (não abre conexão nova).
 * Para desfazer: remover este arquivo da página.
 */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  function num(s) { var m = String(s == null ? '' : s).replace(',', '.').match(/-?\d+(\.\d+)?/); return m ? parseFloat(m[0]) : null; }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function S() { try { return window._iaAdv || {}; } catch (e) { return {}; } }
  var JANELA = 50;

  /* ─────────── dígitos: escuta os ticks que já chegam nos WebSockets da página ─────────── */
  var BUF = {}, DEC = {}, ultimoSym = null; // BUF guarda as cotações; o dígito é calculado na leitura
  function casas(q) { var t = String(q), i = t.indexOf('.'); return i < 0 ? 0 : t.length - i - 1; }
  function guardar(sym, q, pip) {
    if (!sym || q == null || isNaN(+q)) return; q = +q;
    DEC[sym] = Math.max(DEC[sym] || 0, pip != null ? +pip : 0, casas(q));
    var b = BUF[sym] || (BUF[sym] = []); b.push(q); if (b.length > 200) b.splice(0, b.length - 200); ultimoSym = sym;
  }
  function digitoDe(q, pip) { var t = pip != null ? (+q).toFixed(pip) : String(q); return +t.charAt(t.length - 1); }
  function ouvir(ev) {
    var d; if (typeof ev.data !== 'string' || (ev.data.indexOf('tick') < 0 && ev.data.indexOf('history') < 0)) return;
    try { d = JSON.parse(ev.data); } catch (e) { return; }
    if (d.tick && d.tick.quote != null) guardar(d.tick.symbol || d.tick.underlying_symbol, d.tick.quote, d.tick.pip_size);
    else if (d.history && d.history.prices && d.echo_req) {
      var sym = d.echo_req.ticks_history || d.echo_req.underlying_symbol, pr = d.history.prices;
      if (sym && pr.length > 5) { var b = BUF[sym] || []; BUF[sym] = []; pr.slice(-200).forEach(function (p) { guardar(sym, p, d.pip_size); }); b.forEach(function (p) { guardar(sym, p); }); }
    }
  }
  (function () { // escuta pelo protótipo: pega também as conexões criadas por outros scripts (ex.: interceptor OTP)
    var WS = window.WebSocket; if (!WS || WS.prototype.__a2) return;
    var P = WS.prototype, add = EventTarget.prototype.addEventListener, dsc = Object.getOwnPropertyDescriptor(P, 'onmessage');
    function ligar(ws) { if (!ws.__a2on) { ws.__a2on = 1; add.call(ws, 'message', ouvir); } }
    if (dsc && dsc.set) Object.defineProperty(P, 'onmessage', { configurable: true, enumerable: true, get: function () { return dsc.get.call(this); }, set: function (fn) { ligar(this); dsc.set.call(this, fn); } });
    P.addEventListener = function (t, fn, o) { if (t === 'message') ligar(this); return add.call(this, t, fn, o); };
    P.__a2 = true;
  })();
  (function () { // plano B: embrulha a função de dígito do próprio robô
    var n = 0, iv = setInterval(function () {
      var f = window.iaAdvOnDigit; if (++n > 60) clearInterval(iv);
      if (typeof f !== 'function' || f.__a2) return; clearInterval(iv);
      var w = function (a) {
        try { var d = null;
          if (typeof a === 'number' && a >= 0 && a <= 9 && a === Math.floor(a)) d = a;
          else if (typeof a === 'string' && /^\d$/.test(a)) d = +a;
          else if (a && typeof a === 'object') { if (a.digit != null) d = +a.digit; else if (a.quote != null) d = digitoDe(a.quote, a.pip_size); else if (a.tick && a.tick.quote != null) d = digitoDe(a.tick.quote, a.tick.pip_size); }
          if (d !== null && !isNaN(d)) { var b = BUF._adv || (BUF._adv = []); b.push(d); if (b.length > 200) b.shift(); }
        } catch (e) {}
        return f.apply(this, arguments);
      };
      w.__a2 = true; window.iaAdvOnDigit = w;
    }, 500);
  })();
  function simboloAtual() {
    var s = S(); if (s.symbol) return s.symbol; if (s.mercado) return s.mercado;
    var nome = (($('advSelectedMarket') || {}).textContent || '').trim(), n = (nome.match(/\d+/) || [])[0];
    if (!n) return null; return /1s/i.test(nome) ? '1HZ' + n + 'V' : 'R_' + n;
  }
  function digitos() {
    var sym = simboloAtual(), b = null;
    if (sym && BUF[sym] && BUF[sym].length) b = BUF[sym].map(function (q) { return digitoDe(q, DEC[sym]); });
    else if (BUF._adv && BUF._adv.length) b = BUF._adv;
    if (!b) { var h = S().historico; if (h && h.length && h.every(function (x) { return typeof x === 'number' && x >= 0 && x <= 9; })) b = h; }
    return (b || []).slice(-JANELA);
  }

  /* ─────────── conexão própria (só se a página não entregar ticks em 6s) ─────────── */
  var APP_ID = '34lv1PuWzjElEuwWcDLyr', API = 'https://api.derivws.com/trading/v1/options';
  var own = { ws: null, sym: null, tent: 0, espera: 0, conectando: false };
  async function conectarProprio() {
    if (own.conectando || (own.ws && own.ws.readyState <= 1)) return;
    var tk = lsGet('deriv_bearer_token'); if (!tk) return;
    own.conectando = true; own.tent++;
    try {
      var H = { Authorization: 'Bearer ' + tk, 'Deriv-App-ID': APP_ID };
      var r = await fetch(API + '/accounts', { headers: H }); if (!r.ok) throw 0;
      var contas = (await r.json()).data || [], tipo = /real|rot/i.test(lsGet('deriv_conta_ativa') || '') ? 'real' : 'demo';
      var acct = contas.find(function (a) { return a.account_type === tipo; }) || contas[0]; if (!acct) throw 0;
      var o = await fetch(API + '/accounts/' + encodeURIComponent(acct.account_id) + '/otp', { method: 'POST', headers: H });
      var url = ((await o.json()).data || {}).url; if (!url) throw 0;
      var ws = new WebSocket(url); own.ws = ws; own.sym = null;
      ws.addEventListener('message', ouvir);
      ws.onopen = function () { assinar(); };
      ws.onclose = function () { if (own.ws === ws) own.ws = null; };
      setInterval(function () { if (ws.readyState === 1) try { ws.send('{"ping":1}'); } catch (e) {} }, 25000);
    } catch (e) {} finally { own.conectando = false; }
  }
  function assinar() {
    var sym = simboloAtual(), ws = own.ws; if (!ws || ws.readyState !== 1 || !sym || sym === own.sym) return;
    try {
      if (own.sym) ws.send(JSON.stringify({ forget_all: 'ticks' }));
      ws.send(JSON.stringify({ ticks_history: sym, end: 'latest', count: 100, style: 'ticks' }));
      ws.send(JSON.stringify({ ticks: sym, subscribe: 1 }));
      own.sym = sym;
    } catch (e) {}
  }
  function vigiarTicks() { // chamado a cada 700ms com a tela aberta
    var sym = simboloAtual(), tem = sym && BUF[sym] && BUF[sym].length;
    if (own.ws) { assinar(); return; }
    if (tem) { own.espera = 0; return; }
    own.espera += 0.7; if (own.espera > 6 && own.tent < 5) { own.espera = -20; conectarProprio(); }
  }

  /* ORIGEM-V1: o servidor usa o mesmo nome ('ia') para IA Simples e IA Avançado.
     Marca o início vindo daqui para o servidor não aplicar as regras próprias da IA Simples. */
  (function () {
    var n = 0, iv = setInterval(function () {
      var f = window.iaAdvIniciar; if (++n > 120) clearInterval(iv);
      if (typeof f !== 'function' || f.__orig) return; clearInterval(iv);
      var w = function () { window.__advIniciando = Date.now(); return f.apply(this, arguments); };
      w.__orig = true; window.iaAdvIniciar = w;
    }, 500);
    var f0 = window.fetch; if (!f0 || f0.__origAdv) return;
    var ff = function (u, o) {
      try {
        var url = typeof u === 'string' ? u : (u && u.url) || '';
        if (/\/bot\/start/.test(url) && o && typeof o.body === 'string' && window.__advIniciando && Date.now() - window.__advIniciando < 20000) {
          var b = JSON.parse(o.body);
          if ((b.bot_type || 'ia') === 'ia') { b.origem = 'ia_avancado'; if (b.config && typeof b.config === 'object') b.config.origem = 'ia_avancado'; o = Object.assign({}, o, { body: JSON.stringify(b) }); }
        }
      } catch (e) {}
      return f0.call(this, u, o);
    };
    ff.__origAdv = true; window.fetch = ff;
  })();

  /* ───────────────────────── estilo ───────────────────────── */
  var css = document.createElement('style');
  css.textContent = [
    '#iaAvancadoModal.a2-on{background:#05060a!important;overflow:auto!important;isolation:isolate}',
    '#iaAvancadoModal.a2-on>*:not(.a2):not(.a2-bg):not(.a2-keep){display:none!important}',
    '#iaAvancadoModal>.a2-keep{z-index:100!important}',
    '.a2-bg{position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none}',
    '.a2{position:relative;z-index:1;width:100%;max-width:1400px;margin:0 auto;padding:18px 20px 28px;color:#e8ecf4;font-family:Inter,system-ui,sans-serif;box-sizing:border-box;text-align:left;flex:1 1 auto;align-self:stretch}',
    '.a2 *,.a2 *::before,.a2 *::after{box-sizing:border-box}',
    '.a2-hd{display:flex;align-items:center;gap:14px;margin-bottom:14px;flex-wrap:wrap}',
    '.a2-ic{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;font-size:23px;border:1px solid rgba(139,92,246,.4);background:rgba(139,92,246,.12);box-shadow:0 0 26px rgba(139,92,246,.25)}',
    '.a2-hd h1{margin:0;font-size:22px;font-weight:900;display:flex;align-items:center;gap:10px;color:#fff}',
    '.a2-hd h1 span{font-size:10px;letter-spacing:1.5px;padding:4px 9px;border-radius:999px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff}',
    '.a2-hd p{margin:3px 0 0;color:#8b93a7;font-size:12.5px}.a2-sp{flex:1}',
    '.a2-acc{display:flex;gap:8px;align-items:center;flex-wrap:wrap}',
    '.a2-tg{display:flex;background:rgba(0,0,0,.35);border:1px solid #262a40;border-radius:999px;padding:3px;gap:2px}',
    '.a2 .a2-tg>*{all:unset;cursor:pointer;padding:6px 16px!important;border-radius:999px!important;font:800 12px Inter,system-ui,sans-serif!important;color:#8b93a7!important;background:transparent!important;border:0!important;box-shadow:none!important;width:auto!important;margin:0!important}',
    '.a2 .a2-tg>*.on{background:#7c5cff!important;color:#fff!important}',
    '.a2 .a2-pill{border:1px solid #2a2d45!important;border-radius:999px!important;padding:7px 14px!important;background:rgba(0,0,0,.35)!important;display:flex!important;align-items:center;gap:6px;margin:0!important;width:auto!important;height:auto!important;box-shadow:none!important}',
    '.a2 .a2-pill,.a2 .a2-pill *{font:700 13px "Space Mono",ui-monospace,monospace!important;color:#fff;background:none;border:0;padding:0;margin:0}',
    '.a2 .a2-alpha{all:unset;cursor:pointer;border:1px solid rgba(139,92,246,.45)!important;border-radius:999px!important;padding:7px 12px!important;font:800 11.5px Inter,system-ui,sans-serif!important;color:#e9d5ff!important;background:rgba(139,92,246,.14)!important;white-space:nowrap;width:auto!important;margin:0!important;box-shadow:none!important}',
    '.a2-x{all:unset;cursor:pointer;width:36px;height:36px;border-radius:12px;display:grid;place-items:center;font-size:16px;font-weight:900;color:#fca5a5;border:1px solid rgba(248,113,113,.45);background:rgba(248,113,113,.1)}',
    '.a2-cols{display:grid;grid-template-columns:380px minmax(0,1fr);gap:14px;align-items:start}',
    '.a2-pn{background:rgba(12,12,22,.7);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid rgba(139,92,246,.26);border-radius:20px;padding:16px;min-width:0}',
    '.a2-lb{font-size:10px;font-weight:800;letter-spacing:1px;color:#7c84a0;text-transform:uppercase;margin:0 0 6px;display:flex;align-items:center;gap:6px}',
    '.a2-ttl{font-size:11px;font-weight:900;letter-spacing:1.4px;color:#9aa3c0;text-transform:uppercase;display:flex;align-items:center;gap:8px;margin-bottom:12px}',
    '.a2-ttl i{width:7px;height:7px;border-radius:50%;background:#4ade80;box-shadow:0 0 8px #4ade80;animation:a2pl 1.6s infinite}@keyframes a2pl{50%{opacity:.3}}',
    '.a2-ttl.parado i{background:#64748b;box-shadow:none;animation:none}',
    '.a2-g2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}.a2-g3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:12px}',
    '.a2-g2>div,.a2-g3>div{min-width:0}',
    '.a2 .a2-in{width:100%!important;height:40px!important;border-radius:11px!important;border:1px solid #262a40!important;background:rgba(0,0,0,.4)!important;color:#fff!important;font:700 14px Inter,system-ui,sans-serif!important;padding:0 10px!important;outline:0!important;margin:0!important;box-shadow:none!important;min-width:0!important;display:flex!important;align-items:center;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}',
    '.a2 div.a2-in{cursor:pointer}.a2 div.a2-in *{font:inherit!important;color:inherit!important;background:none!important;border:0!important;padding:0!important;margin:0!important;overflow:hidden;text-overflow:ellipsis}',
    '.a2 select.a2-in option{background:#0d0f1a;color:#fff}.a2 .a2-in:focus{border-color:#8b5cf6!important}',
    '.a2 .a2-hint{font-size:10px!important;color:#6f7790!important;margin:4px 0 0!important;padding:0!important;background:none!important;border:0!important;line-height:1.3}',
    '.a2 .a2-chips{display:flex!important;gap:6px;margin:-4px 0 12px!important;flex-wrap:wrap;padding:0!important;background:none!important;border:0!important}',
    '.a2 .a2-chips>*{all:unset;cursor:pointer;flex:1 1 0;min-width:44px;text-align:center;border:1px solid #262a40!important;border-radius:10px!important;padding:7px 4px!important;font:700 12px Inter,system-ui,sans-serif!important;color:#aab!important;background:transparent!important;box-shadow:none!important;margin:0!important;white-space:nowrap}',
    '.a2 .a2-chips>*.on{border-color:#8b5cf6!important;background:rgba(139,92,246,.16)!important;color:#fff!important}',
    '.a2 .a2-cfg{all:unset;cursor:pointer;font-size:11px!important;line-height:1;padding:2px 6px!important;border-radius:6px!important;border:1px solid #33384f!important;color:#c4b5fd!important;background:transparent!important;margin:0 0 0 auto!important;width:auto!important;height:auto!important}',
    '.a2-vv{border:1px solid #262a40;border-radius:14px;background:rgba(0,0,0,.3);margin-bottom:12px}',
    '.a2-vv-h{all:unset;cursor:pointer;display:flex;align-items:center;gap:8px;width:100%;box-sizing:border-box;padding:11px 13px;font:800 12.5px Inter,system-ui,sans-serif;color:#e8ecf4}',
    '.a2-vv-h em{font-style:normal;margin-left:auto;color:#8b93a7;transition:transform .2s}.a2-vv.aberto .a2-vv-h em{transform:rotate(180deg)}',
    '.a2-vv-h b{font:700 11px Inter,system-ui,sans-serif;color:#a78bfa}',
    '.a2-vv-c{display:none;padding:0 13px 12px;font-size:12.5px}.a2-vv.aberto .a2-vv-c{display:block}',
    '.a2-vv-c>*{margin-top:0!important;margin-bottom:10px!important}.a2-vv-c>*:last-child{margin-bottom:0!important}',
    '.a2-vv-c input:not([type=checkbox]):not([type=radio]),.a2-vv-c select{background:rgba(0,0,0,.4)!important;border:1px solid #262a40!important;color:#fff!important;border-radius:9px!important;min-height:34px}',
    '.a2-vv-c button{background:rgba(139,92,246,.12);border:1px solid rgba(139,92,246,.35);color:#e9d5ff;border-radius:9px;padding:6px 10px;font:700 12px Inter,system-ui,sans-serif;cursor:pointer}',
    '.a2-vv-c label{color:#9aa3c0;font-size:11px}',
    '.a2-stp{display:grid;grid-template-columns:36px 1fr 36px;gap:6px}',
    '.a2 .a2-stp>*{all:unset;display:grid!important;place-items:center;height:38px!important;border-radius:11px!important;border:1px solid #262a40!important;background:rgba(0,0,0,.35)!important;font:800 15px "Space Mono",ui-monospace,monospace!important;color:#fff!important;cursor:pointer;margin:0!important;padding:0!important;width:auto!important}',
    '.a2 .a2-stp>span{cursor:default}',
    '.a2-info{display:flex;gap:10px;flex-wrap:wrap;font-size:10.5px;color:#6f7790;margin:0 0 12px}.a2-info b{color:#c4b5fd}',
    '.a2-risk{border-radius:14px;padding:12px;border:1px solid rgba(248,113,113,.35);background:rgba(248,113,113,.07);margin-bottom:12px}',
    '.a2-risk .seq{display:flex;gap:5px;flex-wrap:wrap;margin:8px 0;align-items:center;color:#6f7790}',
    '.a2-risk .seq span{font:700 11px "Space Mono",ui-monospace,monospace;padding:3px 8px;border-radius:999px;border:1px solid #3a2a35;color:#e8ecf4}.a2-risk .seq span.on{background:#f87171;color:#1a0505;border-color:#f87171}',
    '.a2 #advStartBtn{width:100%!important;border:0!important;border-radius:14px!important;padding:14px!important;font:900 15px Inter,system-ui,sans-serif!important;color:#fff!important;background:linear-gradient(135deg,#6366f1,#22c55e)!important;box-shadow:0 10px 30px rgba(99,102,241,.3)!important;cursor:pointer;margin:0!important;height:auto!important;display:flex!important;align-items:center;justify-content:center;gap:8px}',
    '.a2 #advStartBtn.a2-run{background:linear-gradient(135deg,#dc2626,#f97316)!important;box-shadow:0 10px 30px rgba(239,68,68,.3)!important}',
    '.a2 #advStartBtn *{color:#fff!important;font:inherit!important}',
    '.a2-main{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:14px}.a2-main>div{min-width:0}',
    '.a2-wheel{position:relative;aspect-ratio:1;max-width:440px;margin:0 auto;width:100%}.a2-wheel svg{width:100%;height:100%;overflow:visible}',
    '.a2-hist{display:flex;align-items:flex-end;gap:6px;height:130px;padding-top:14px}.a2-hist div{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;height:100%;justify-content:flex-end}',
    '.a2-hist i{width:100%;border-radius:6px 6px 3px 3px;transition:height .5s,background .5s}.a2-hist b{font:700 12px "Space Mono",ui-monospace,monospace;color:#9aa3c0}.a2-hist small{font:700 9.5px "Space Mono",ui-monospace,monospace;color:#6f7790}',
    '.a2-kpi{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:14px}.a2-kpi div{background:rgba(0,0,0,.35);border:1px solid #23263a;border-radius:12px;padding:9px 10px;min-width:0}',
    '.a2-kpi span{display:block;font-size:9.5px;font-weight:800;letter-spacing:.6px;color:#7c84a0;text-transform:uppercase}.a2-kpi b{display:block;font:700 16px "Space Mono",ui-monospace,monospace;margin-top:2px;white-space:nowrap}',
    '.a2-tl{display:flex;gap:4px;flex-wrap:wrap;min-height:12px}.a2-tl i{width:12px;height:12px;border-radius:4px}',
    '.a2 #advMiniFeed{max-height:190px!important;overflow:auto!important;background:transparent!important;border:0!important;padding:0!important;margin:0!important;font-size:12px!important;height:auto!important;display:block!important}',
    '.a2-vazio{color:#6f7790;font-size:12px;padding:30px 10px;text-align:center}',
    '.a2-note{font-size:10.5px;color:#6f7790;line-height:1.45;margin-top:10px}',
    '@media (max-width:1150px){.a2-main{grid-template-columns:1fr}}',
    '@media (max-width:860px){.a2{padding:12px 12px 24px}.a2-cols{grid-template-columns:1fr}.a2-hd{position:relative}.a2-hd>div:nth-child(2){padding-right:46px}.a2-acc{width:100%}.a2-x{position:absolute;top:5px;right:0}.a2-hd h1{font-size:18px}.a2-hd p{display:none}.a2-kpi{grid-template-columns:1fr 1fr}}'
  ].join('\n');
  document.head.appendChild(css);

  /* ─────────────────── montagem ─────────────────── */
  var montado = false, R = {};
  function interativo(b) { return b && b.nodeType === 1 && (b.matches('input,select,button,textarea,[onclick]') || b.querySelector('input,select,button,textarea,[onclick]')); }
  function mover(e, dest, cls) { if (!e) return null; if (cls) String(cls).split(' ').forEach(function (c) { e.classList.add(c); }); dest.appendChild(e); return e; }
  function campo(rot, e, wrap, hint) { var d = el('div'); var l = el('div', 'a2-lb', rot); d.appendChild(l); if (e) { e.classList.add('a2-in'); d.appendChild(e); } if (hint) { hint.classList.add('a2-hint'); d.appendChild(hint); } wrap.appendChild(d); return d; }
  function secao(titulo, chave) {
    var box = el('div', 'a2-vv' + (lsGet('a2_' + chave) === '1' ? ' aberto' : ''));
    var h = el('button', 'a2-vv-h', titulo + ' <b></b><em>▾</em>'); h.type = 'button';
    h.onclick = function () { box.classList.toggle('aberto'); lsSet('a2_' + chave, box.classList.contains('aberto') ? '1' : '0'); };
    var c = el('div', 'a2-vv-c'); box.appendChild(h); box.appendChild(c); box._c = c; box._b = h.querySelector('b'); return box;
  }

  function montar() {
    var modal = $('iaAvancadoModal'), cols = $('advTwoCols');
    if (!modal || !cols || !$('advStartBtn') || !$('advStake')) return false;

    // janelas internas (regra de dígitos) ficam fora de qualquer área escondida
    var rm = $('advRegraModal'); if (rm) { modal.appendChild(rm); rm.classList.add('a2-keep'); }
    Array.prototype.slice.call(cols.querySelectorAll('*')).forEach(function (e) {
      var p = e.style.position; if (!p) { try { p = getComputedStyle(e).position; } catch (x) {} }
      if (p === 'fixed') { modal.appendChild(e); e.classList.add('a2-keep'); }
    });

    var bg = el('canvas', 'a2-bg'); modal.insertBefore(bg, modal.firstChild); iniciarFundo(bg, modal);
    var raiz = el('div', 'a2');

    /* cabeçalho */
    var hd = el('div', 'a2-hd', '<div class="a2-ic">🧬</div><div><h1>IA Avançado <span>AVANÇADO</span></h1><p>Perdas virtuais · Multiplicador adaptativo · Frequência de dígitos</p></div><div class="a2-sp"></div>');
    var acc = el('div', 'a2-acc'), tg = el('div', 'a2-tg');
    mover($('advDemoBtn'), tg); mover($('advRealBtn'), tg); if (tg.children.length) acc.appendChild(tg); R.tg = tg;
    var se = $('advSaldoEspelho'), le = $('advLucroEspelho');
    if (se) { var p1 = el('div', 'a2-pill'); p1.appendChild(se); acc.appendChild(p1); }
    if (le) { var p2 = el('div', 'a2-pill'); p2.appendChild(le); acc.appendChild(p2); R.lucroPill = le; }
    var alphaBtn = modal.querySelector('[onclick*="abrirModalIaAlpha"]');
    if (alphaBtn) { alphaBtn.classList.add('a2-alpha'); alphaBtn.textContent = '✨ Modo IA Alpha'; acc.appendChild(alphaBtn); }
    var x = el('button', 'a2-x', '✕'); x.type = 'button'; x.title = 'Fechar';
    x.onclick = function () { if (typeof window.fecharIaAvancado === 'function') window.fecharIaAvancado(); };
    acc.appendChild(x); hd.appendChild(acc); raiz.appendChild(hd);

    var grid = el('div', 'a2-cols'); raiz.appendChild(grid);

    /* ── esquerda: configuração ── */
    var pe = el('div', 'a2-pn'); grid.appendChild(pe);
    R.ttlMotor = el('div', 'a2-ttl', '<i></i><span>Motor IA ativo</span>'); pe.appendChild(R.ttlMotor);
    var g2 = el('div', 'a2-g2');
    campo('Mercado', $('advMarketSelect'), g2, $('advMarketHint')); campo('Negociação', $('advContractType'), g2); pe.appendChild(g2);
    var g3a = el('div', 'a2-g3');
    campo('Duração', $('advDuration'), g3a); campo('Unidade', $('advDurationUnit'), g3a); campo('Multiplic.', $('advMultiplier'), g3a); pe.appendChild(g3a);
    var mc = $('advMultChips'); if (mc) { mc.classList.add('a2-chips'); pe.appendChild(mc); R.mult = mc; }
    var g3b = el('div', 'a2-g3');
    campo('Entrada', $('advStake'), g3b, $('advStakeHint')); campo('Lucro alvo', $('advTarget'), g3b, $('advTargetHint'));
    var cStop = campo('Limite', $('advStop'), g3b, $('advStopHint'));
    var cfg = modal.querySelector('[onclick*="openAdvStopLossModal"]');
    if (cfg) { cfg.classList.add('a2-cfg'); cfg.textContent = '⚙'; cfg.title = 'Opções de limite de perda'; cStop.firstChild.appendChild(cfg); }
    pe.appendChild(g3b);

    /* perdas virtuais */
    var vv = secao('👻 Perdas virtuais', 'virt'); R.vv = vv;
    var vg = el('div', 'a2-g2'); vg.style.margin = '0 0 10px';
    var q = el('div'); q.appendChild(el('div', 'a2-lb', 'Quantas'));
    var stp = el('div', 'a2-stp');
    var menos = modal.querySelector('[onclick*="iaAdvStep(\'perdas\',-1)"],[onclick*="iaAdvStep(\'perdas\', -1)"]'), mais = modal.querySelector('[onclick*="iaAdvStep(\'perdas\',+1)"],[onclick*="iaAdvStep(\'perdas\', +1)"],[onclick*="iaAdvStep(\'perdas\',1)"]');
    mover(menos, stp); mover($('advPerdasVirt'), stp); mover(mais, stp); q.appendChild(stp); vg.appendChild(q);
    campo('Negociar', $('advNegVirt'), vg); vv._c.appendChild(vg);
    var vg2 = el('div', 'a2-g2'); vg2.style.margin = '0'; campo('Iniciar com virtuais', $('advIniciarVirt'), vg2); vv._c.appendChild(vg2);
    pe.appendChild(vv);

    /* frequência de dígitos */
    var fq = secao('📊 Frequência de dígitos', 'freq'); R.fq = fq;
    [$('advFreqBtn'), $('advFreqConfig'), $('advRegrasContainer')].forEach(function (e) { if (e) fq._c.appendChild(e); });
    var addR = modal.querySelector('[onclick*="advAddRegra"]'); if (addR && !fq._c.contains(addR)) { addR.textContent = '+ Nova regra'; fq._c.appendChild(addR); }

    /* resto da coluna antiga (pontos virtuais, etc.) — nada some */
    var velha = cols.querySelector('.adv-panel') || $('iaAdvancedMode') || cols.firstElementChild;
    var start = $('advStartBtn');
    if (velha) Array.prototype.slice.call(velha.children).forEach(function (b) {
      if (b.contains(start) || b.querySelector('#iaInfoJanela')) return;
      if (interativo(b)) fq._c.appendChild(b);
    });
    pe.appendChild(fq);

    /* info (janela / virtuais / mult) */
    var inf = el('div', 'a2-info');
    [['iaInfoJanela', 'Janela'], ['iaInfoVirtuais', 'Virtuais'], ['iaInfoMult', 'Mult.']].forEach(function (p) { var e = $(p[0]); if (e) { var s = el('span', null, p[1] + ': '); s.appendChild(e); inf.appendChild(s); } });
    if (inf.children.length) pe.appendChild(inf);

    R.risk = el('div', 'a2-risk'); pe.appendChild(R.risk);
    pe.appendChild(start);

    /* ── direita: mapa + frequência + sessão ── */
    var pd = el('div', 'a2-pn'); grid.appendChild(pd);
    var mn = el('div', 'a2-main'); pd.appendChild(mn);
    var ca = el('div'); R.ttlMapa = el('div', 'a2-ttl', '<i></i><span>Mapa de calor · últimos ' + JANELA + ' ticks</span>'); ca.appendChild(R.ttlMapa);
    var wh = el('div', 'a2-wheel'); wh.innerHTML = '<svg viewBox="-160 -160 320 320"></svg>'; R.svg = wh.firstChild; ca.appendChild(wh); mn.appendChild(ca);
    var cb = el('div');
    cb.appendChild(el('div', 'a2-ttl', '📊 Frequência dos dígitos'));
    R.hist = el('div', 'a2-hist'); cb.appendChild(R.hist);
    R.kpi = el('div', 'a2-kpi', '<div><span>Operações</span><b data-k="n">0</b></div><div><span>Acerto</span><b data-k="w">—</b></div><div><span>Virtuais</span><b data-k="v">0/0</b></div><div><span>Próxima</span><b data-k="p">$0.00</b></div>');
    cb.appendChild(R.kpi);
    var l1 = el('div', 'a2-lb', 'Linha do tempo'); l1.style.marginTop = '12px'; cb.appendChild(l1);
    R.tl = el('div', 'a2-tl'); cb.appendChild(R.tl);
    var l2 = el('div', 'a2-lb', 'Registros'); l2.style.marginTop = '12px'; cb.appendChild(l2);
    var feed = $('advMiniFeed'); if (feed) cb.appendChild(feed);
    cb.appendChild(el('div', 'a2-note', 'O mapa mostra quantas vezes cada dígito saiu nos últimos ' + JANELA + ' ticks. Nos índices sintéticos cada dígito é sorteado de forma independente — o desequilíbrio é contexto, não garantia do próximo.'));
    mn.appendChild(cb);

    modal.appendChild(raiz);
    modal.classList.add('a2-on');

    [R.mult, tg].forEach(function (g) {
      if (!g) return;
      g.addEventListener('click', function (ev) {
        var b = ev.target; while (b && b.parentNode !== g) b = b.parentNode; if (!b) return;
        Array.prototype.forEach.call(g.children, function (c) { c.classList.toggle('on', c === b); }); g._manual = b; g._manualEm = Date.now();
      }, true);
    });
    montado = true;
    return true;
  }

  /* ─────────────────── estado ─────────────────── */
  function marcar(g, fn) {
    if (!g || (g._manual && Date.now() - g._manualEm < 1500)) return;
    var achou = null; Array.prototype.forEach.call(g.children, function (c) { if (!achou && fn(c)) achou = c; });
    if (!achou) achou = g._manual || null;
    Array.prototype.forEach.call(g.children, function (c) { c.classList.toggle('on', c === achou); });
  }
  function aberto() { var m = $('iaAvancadoModal'); if (!m) return false; var s = getComputedStyle(m); return s.display !== 'none' && s.visibility !== 'hidden'; }

  var trades = { n: 0, w: 0, tl: [] };
  function lerTrades() {
    var h = S().historico, n = 0, w = 0, tl = [];
    if (h && h.length && typeof h[0] === 'object') {
      h.forEach(function (t) {
        var p = t.profit != null ? +t.profit : t.lucro != null ? +t.lucro : null;
        var ok = t.win === true || t.won === true || /won|win|ganh/i.test(String(t.result || t.status || t.resultado || '')) || (p !== null && p > 0);
        var ruim = t.win === false || /lost|loss|perd/i.test(String(t.result || t.status || t.resultado || '')) || (p !== null && p < 0);
        if (ok || ruim) { n++; if (ok) w++; tl.push(ok ? 1 : 0); }
      });
    }
    if (!n) { // plano B: contar o mini-feed
      var f = $('advMiniFeed');
      if (f) Array.prototype.forEach.call(f.children, function (c) { var t = c.textContent || ''; var ok = /✅|WIN|GANHOU|\+\s*\$/i.test(t), ruim = /❌|LOSS|PERDEU|[−-]\s*\$/i.test(t); if (ok || ruim) { n++; if (ok) w++; tl.unshift(ok ? 1 : 0); } });
    }
    trades = { n: n, w: w, tl: tl.slice(-36) };
  }

  function atualizar() {
    var s = S(), rodando = !!s.running;
    var mv = num(($('advMultiplier') || {}).value); if (mv === null) mv = num(s.mult);
    marcar(R.mult, function (c) { var v = num(c.textContent); return mv !== null && v !== null && Math.abs(v - mv) < 0.001; });
    var conta = String(lsGet('deriv_conta_ativa') || '').toLowerCase();
    try { if (window.currentAccountType) conta = String(window.currentAccountType).toLowerCase(); } catch (e) {}
    var demo = /demo|dot|vrt/.test(conta), real = !demo && /real|rot|cr\d/.test(conta);
    marcar(R.tg, function (c) { return (demo && c.id === 'advDemoBtn') || (real && c.id === 'advRealBtn'); });
    var sb = $('advStartBtn'); if (sb) sb.classList.toggle('a2-run', rodando);
    R.ttlMotor.classList.toggle('parado', !rodando); R.ttlMotor.querySelector('span').textContent = rodando ? 'Motor IA ativo' : 'Motor IA pronto';
    var lt = (R.lucroPill && R.lucroPill.textContent) || '', lv = num(lt.replace(/\(.*$/, '').replace(/[$\s]/g, '').replace('−', '-'));
    if (R.lucroPill) R.lucroPill.style.color = lv === null || lv === 0 ? '#fff' : lv > 0 ? '#4ade80' : '#f87171';

    var perdas = +s.perdas || num(($('advPerdasVirt') || {}).textContent) || 0, vc = +s.virtContador || 0;
    R.vv._b.textContent = '· ' + perdas + ' antes de entrar';
    R.fq._b.textContent = window._advFreqAtivo ? '· ligada' + (window._advRegras && window._advRegras.length ? ' · ' + window._advRegras.length + ' regra(s)' : '') : '· desligada';

    lerTrades();
    var k = function (q) { return R.kpi.querySelector('[data-k="' + q + '"]'); };
    k('n').textContent = trades.n; k('w').textContent = trades.n ? Math.round(trades.w / trades.n * 100) + '%' : '—';
    k('v').textContent = vc + '/' + perdas; k('p').textContent = '$' + (+s.stakeAtual || num(($('advStake') || {}).value) || 0).toFixed(2);
    R.tl.innerHTML = trades.tl.map(function (v) { return '<i style="background:' + (v ? '#4ade80' : '#f87171') + '"></i>'; }).join('');

    desenharRisco(s);
  }

  function desenharRisco(s) {
    var base = num(($('advStake') || {}).value) || +s.stakeBase || 0.35 /* ADV-SEQ-V1 */, mult = num(($('advMultiplier') || {}).value) || +s.mult || 2, passo = +s.stepMart || 0;
    var lim = num(($('advStop') || {}).value) || 0, a = [], v = base, tot = 0, cabe = 0, soma = 0;
    for (var i = 0; i < 6; i++) { a.push(v); tot += v; v = +(v * mult).toFixed(2); }
    v = base; while (soma + v <= lim && cabe < 30) { soma += v; cabe++; v = v * mult; }
    R.risk.innerHTML = '<b style="font-size:12.5px">⚠ Sequência de recuperação (' + String(mult).replace('.', ',') + '×)</b>' +
      '<div class="seq">' + a.map(function (x, i) { return '<span class="' + (i < passo ? 'on' : '') + '">$' + x.toFixed(2) + '</span>'; }).join('→') + '</div>' +
      '<div style="font-size:11.5px;color:#fecaca">Perder 6 seguidas custa <b>−$' + tot.toFixed(2) + '</b>.' + (lim ? ' Com o limite em $' + lim.toFixed(2) + ' a sequência pode chegar a ' + cabe + ' entrada' + (cabe === 1 ? '' : 's') + ' (≈ −$' + soma.toFixed(2) + ').' : '') + '</div>';
  }

  /* ─────────────────── mapa de calor + histograma ─────────────────── */
  var ang = 0;
  function cor(f) { var t = Math.max(0, Math.min(1, (f - .05) / .1)); return 'rgb(' + Math.round(99 + t * 145) + ',' + Math.round(102 + t * 12) + ',' + Math.round(241 - t * 59) + ')'; }
  function rgba(c, a) { return c.replace('rgb(', 'rgba(').replace(')', ',' + a + ')'); }
  function lado() {
    var ct = String((($('advContractType') || {}).value) || S().contractType || 'DIGITEVEN').toUpperCase();
    return ct;
  }
  function desenharMapa() {
    var D = digitos(), n = D.length;
    if (!n) {
      R.svg.innerHTML = '<circle r="150" fill="none" stroke="rgba(139,92,246,.35)" stroke-width="2"/>' + [0,1,2,3,4,5,6,7,8,9].map(function (k) { var a = k / 10 * Math.PI * 2 - Math.PI / 2; return '<circle cx="' + Math.cos(a) * 120 + '" cy="' + Math.sin(a) * 120 + '" r="18" fill="rgba(99,102,241,.12)" stroke="rgba(99,102,241,.4)"/><text x="' + Math.cos(a) * 120 + '" y="' + (Math.sin(a) * 120 + 6) + '" text-anchor="middle" font-family="Space Mono,monospace" font-weight="700" font-size="17" fill="#9aa3c0">' + k + '</text>'; }).join('') +
        '<text y="4" text-anchor="middle" font-family="Inter,sans-serif" font-weight="800" font-size="12" fill="#9aa3c0">aguardando ticks…</text>';
      R.hist.innerHTML = '<div class="a2-vazio" style="flex:1;align-self:center">Os dígitos aparecem assim que os ticks do mercado chegarem.</div>';
      return;
    }
    var c = [0,0,0,0,0,0,0,0,0,0]; D.forEach(function (d) { c[d]++; }); var last = D[n - 1], s = '';
    s += '<circle r="150" fill="none" stroke="rgba(139,92,246,.35)" stroke-width="2"/><circle r="112" fill="none" stroke="rgba(139,92,246,.12)" stroke-dasharray="3 6"/>';
    for (var k = 0; k < 10; k++) {
      var a = k / 10 * Math.PI * 2 - Math.PI / 2, x = Math.cos(a) * 112, y = Math.sin(a) * 112, f = c[k] / n, r = 14 + f * 100, col = cor(f), on = k === last;
      s += '<circle cx="' + x + '" cy="' + y + '" r="' + Math.min(r, 32) + '" fill="' + col + '" fill-opacity="' + (on ? .95 : .28) + '" stroke="' + col + '" stroke-width="' + (on ? 3 : 1.5) + '" style="filter:drop-shadow(0 0 ' + (on ? 18 : 6) + 'px ' + col + ')"/><text x="' + x + '" y="' + (y + 6) + '" text-anchor="middle" font-family="Space Mono,monospace" font-weight="700" font-size="18" fill="#fff">' + k + '</text>';
    }
    var alvo = last / 10 * 360, dif = ((alvo - ang) % 360 + 540) % 360 - 180; ang += dif * .35;
    var ct = lado(), ev = D.filter(function (d) { return d % 2 === 0; }).length / n, ov = D.filter(function (d) { return d > 4; }).length / n;
    var pct, rot;
    if (ct === 'DIGITODD') { pct = 1 - ev; rot = 'ÍMPAR'; } else if (ct === 'DIGITOVER') { pct = ov; rot = 'OVER'; } else if (ct === 'DIGITUNDER') { pct = 1 - ov; rot = 'UNDER'; }
    else if (ct === 'DIGITMATCH' || ct === 'DIGITDIFF') { pct = c[last] / n; rot = ct === 'DIGITMATCH' ? 'MATCH ' + last : 'DIFF ' + last; if (ct === 'DIGITDIFF') pct = 1 - pct; }
    else { pct = ev; rot = 'PAR'; }
    s += '<g transform="rotate(' + ang + ')"><line x1="0" y1="0" x2="0" y2="-92" stroke="#fbbf24" stroke-width="3" stroke-linecap="round" style="filter:drop-shadow(0 0 6px #fbbf24)"/><circle r="8" fill="#fbbf24"/></g>';
    s += '<circle r="52" fill="rgba(10,10,20,.88)" stroke="rgba(139,92,246,.5)"/><text y="6" text-anchor="middle" font-family="Inter,sans-serif" font-weight="900" font-size="28" fill="#fff">' + Math.round(pct * 100) + '%</text><text y="26" text-anchor="middle" font-family="Inter,sans-serif" font-weight="800" font-size="9" letter-spacing="1.5" fill="#9aa3c0">' + rot + ' · ' + n + ' TICKS</text>';
    R.svg.innerHTML = s;
    var mx = Math.max.apply(0, c) || 1;
    R.hist.innerHTML = c.map(function (v, k) { var f = v / n, cl = cor(f); return '<div><small>' + Math.round(f * 100) + '%</small><i style="height:' + Math.max(6, v / mx * 100) + '%;background:linear-gradient(180deg,' + cl + ',' + rgba(cl, .35) + ')' + (k === last ? ';box-shadow:0 0 14px ' + cl : '') + '"></i><b style="' + (k === last ? 'color:#fff' : '') + '">' + k + '</b></div>'; }).join('');
  }

  /* ─────────────────── fundo "rede" ─────────────────── */
  function iniciarFundo(cv, modal) {
    var x = cv.getContext('2d'), P = [], W = 0, H = 0;
    (function q() {
      requestAnimationFrame(q);
      if (document.hidden || !aberto()) return;
      var d = Math.min(window.devicePixelRatio || 1, 2), w = cv.clientWidth, h = cv.clientHeight; if (!w || !h) return;
      if (w !== W || h !== H) { W = w; H = h; cv.width = W * d; cv.height = H * d; P = []; var n = Math.round(Math.min(90, W * H / 22000)); for (var i = 0; i < n; i++) P.push({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * .35, vy: (Math.random() - .5) * .35 }); }
      x.setTransform(d, 0, 0, d, 0, 0); x.clearRect(0, 0, W, H);
      var g = x.createRadialGradient(W * .25, H * .25, 0, W * .25, H * .25, W * .6); g.addColorStop(0, 'rgba(124,92,255,.14)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, 0, W, H);
      P.forEach(function (a) { a.x += a.vx; a.y += a.vy; if (a.x < 0 || a.x > W) a.vx *= -1; if (a.y < 0 || a.y > H) a.vy *= -1; });
      for (var i = 0; i < P.length; i++) for (var j = i + 1; j < P.length; j++) { var dd = Math.hypot(P[i].x - P[j].x, P[i].y - P[j].y); if (dd < 130) { x.strokeStyle = (i % 3 ? 'rgba(139,92,246,' : 'rgba(34,211,238,') + ((1 - dd / 130) * .3) + ')'; x.lineWidth = 1; x.beginPath(); x.moveTo(P[i].x, P[i].y); x.lineTo(P[j].x, P[j].y); x.stroke(); } }
      P.forEach(function (a, i) { x.fillStyle = i % 4 ? 'rgba(139,92,246,.8)' : 'rgba(34,211,238,.9)'; x.beginPath(); x.arc(a.x, a.y, i % 4 ? 1.6 : 2.4, 0, 7); x.fill(); });
      var v = x.createRadialGradient(W / 2, H / 2, Math.min(W, H) * .25, W / 2, H / 2, Math.max(W, H) * .75); v.addColorStop(0, 'rgba(5,6,10,0)'); v.addColorStop(1, 'rgba(5,6,10,.72)'); x.fillStyle = v; x.fillRect(0, 0, W, H);
    })();
  }

  /* ─────────────────── laço ─────────────────── */
  function tick() {
    try {
      if (!montado && !montar()) return;
      if (!aberto()) return;
      atualizar(); vigiarTicks();
    } catch (e) { console.warn('[ia-avancado-v2]', e); }
  }
  setInterval(tick, 700);
  setInterval(function () { try { if (montado && aberto()) desenharMapa(); } catch (e) { console.warn('[ia-avancado-v2]', e); } }, 250);
  if (document.readyState !== 'loading') tick(); else document.addEventListener('DOMContentLoaded', tick);
})();
