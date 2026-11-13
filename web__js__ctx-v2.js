/* Alpha Dolar — IA CONTEXTUAL v2 (layout novo, igual à amostra aprovada)
 * Monta a tela nova e MOVE os campos originais (pelos ids/classes) para dentro dela.
 * Os dados do raciocínio vêm do que o próprio robô já calcula: a resposta da IA (/api/ctx-ia),
 * os indicadores que ele envia para ela, #ctxStatusText, #ctxQuoteText e _ctxRankingData.
 * Fundo próprio: "Sinapse". Para desfazer: remover este arquivo da página.
 */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  function num(s) { var m = String(s == null ? '' : s).replace(/[$\s]/g, '').replace('−', '-').replace(',', '.').match(/-?\d+(\.\d+)?/); return m ? parseFloat(m[0]) : null; }
  function el(t, c, h) { var e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; }
  function st() { return window._ctxState || {}; }
  function nomeMerc(v) { var s = $('ctxMercado'); if (s) for (var i = 0; i < s.options.length; i++) if (s.options[i].value === v) return s.options[i].text; return v || ''; }

  /* ─────────── escuta a IA: o que o robô manda (indicadores) e o que ela responde ─────────── */
  var IA = { porMerc: {}, ultimo: null };
  (function () {
    var f0 = window.fetch; if (!f0 || f0.__c2) return;
    var f = function (u, o) {
      var url = String(u && u.url || u || ''), corpo = null;
      if (url.indexOf('/api/ctx-ia') >= 0 && o && typeof o.body === 'string') { try { corpo = JSON.parse(o.body); } catch (e) {} }
      var p = f0.apply(this, arguments);
      if (corpo) p.then(function (r) {
        r.clone().json().then(function (j) {
          var res = j && j.resultado; if (!res) return;
          var reg = { mercado: corpo.mercado, ind: corpo, res: res, t: Date.now() };
          IA.porMerc[corpo.mercado] = reg; IA.ultimo = reg;
        }).catch(function () {});
      }).catch(function () {});
      return p;
    };
    f.__c2 = true; window.fetch = f;
  })();

  /* ───────────────────────── estilo ───────────────────────── */
  var css = el('style');
  css.textContent = [
    '#alphaCtxIaModal.c2-on{background:#05060a!important;overflow:auto!important;isolation:isolate}',
    '#alphaCtxIaModal.c2-on>*:not(.c2):not(.c2-bg):not(.c2-keep){display:none!important}',
    '#alphaCtxIaModal>.c2-keep{z-index:100!important}',
    '.c2-bg{position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none}',
    '.c2{position:relative;z-index:1;width:100%;max-width:1400px;margin:0 auto;padding:18px 20px 28px;color:#e8ecf4;font-family:Inter,system-ui,sans-serif;box-sizing:border-box;text-align:left;flex:1 1 auto;align-self:stretch}',
    '.c2 *,.c2 *::before,.c2 *::after{box-sizing:border-box}',
    '.c2-hd{display:flex;align-items:center;gap:14px;margin-bottom:14px;flex-wrap:wrap}',
    '.c2-ic{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;font-size:23px;border:1px solid rgba(236,72,153,.4);background:rgba(236,72,153,.1);box-shadow:0 0 26px rgba(236,72,153,.22)}',
    '.c2-hd h1{margin:0;font-size:22px;font-weight:900;display:flex;align-items:center;gap:10px;color:#fff}',
    '.c2-hd h1 span{font-size:10px;letter-spacing:1.5px;padding:4px 9px;border-radius:999px;background:linear-gradient(135deg,#ec4899,#8b5cf6);color:#fff}',
    '.c2-hd p{margin:3px 0 0;color:#8b93a7;font-size:12.5px}.c2-sp{flex:1}',
    '.c2-acc{display:flex;gap:8px;align-items:center;flex-wrap:wrap}',
    '.c2 #ctxSaldoDemo,.c2 #ctxSaldoReal{all:unset;cursor:pointer;display:flex!important;flex-direction:column;align-items:flex-start;border:1px solid #2a2d45!important;border-radius:14px!important;padding:6px 14px!important;background:rgba(0,0,0,.35)!important;min-width:0!important;box-shadow:none!important}',
    '.c2 #ctxSaldoDemo>div:first-child,.c2 #ctxSaldoReal>div:first-child{font:800 9px Inter,system-ui,sans-serif!important;letter-spacing:1px;color:#8b93a7!important}',
    '.c2 #ctxSaldoDemoVal,.c2 #ctxSaldoRealVal{font:700 14px "Space Mono",ui-monospace,monospace!important;color:#fff!important}',
    '.c2 #ctxSaldoDemo.c2-sel,.c2 #ctxSaldoReal.c2-sel{border-color:#8b5cf6!important;background:rgba(139,92,246,.2)!important;box-shadow:0 0 16px rgba(139,92,246,.3)!important}',
    '.c2-motor{margin-top:6px!important}',
    '.c2-pill{border:1px solid #2a2d45;border-radius:999px;padding:7px 14px;font:700 13px "Space Mono",ui-monospace,monospace;background:rgba(0,0,0,.35)}',
    '.c2 .c2-alpha{all:unset;cursor:pointer;border:1px solid rgba(139,92,246,.45)!important;border-radius:999px!important;padding:7px 12px!important;font:800 11.5px Inter,system-ui,sans-serif!important;color:#e9d5ff!important;background:rgba(139,92,246,.14)!important;white-space:nowrap}',
    '.c2-x{all:unset;cursor:pointer;width:36px;height:36px;border-radius:12px;display:grid;place-items:center;font-size:16px;font-weight:900;color:#fca5a5;border:1px solid rgba(248,113,113,.45);background:rgba(248,113,113,.1)}',
    '.c2-cols{display:grid;grid-template-columns:330px minmax(0,1fr) 300px;gap:14px;align-items:start}',
    '.c2-mid{display:flex;flex-direction:column;gap:14px;min-width:0}',
    '.c2-pn{background:rgba(12,12,22,.72);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid rgba(139,92,246,.26);border-radius:20px;padding:16px;min-width:0}',
    '.c2-lb{font-size:10px;font-weight:800;letter-spacing:1px;color:#7c84a0;text-transform:uppercase;margin:0 0 6px}',
    '.c2-ttl{font-size:11px;font-weight:900;letter-spacing:1.4px;color:#9aa3c0;text-transform:uppercase;display:flex;align-items:center;gap:8px;margin-bottom:12px}',
    '.c2-ttl i{width:7px;height:7px;border-radius:50%;background:#4ade80;box-shadow:0 0 8px #4ade80;animation:c2pl 1.6s infinite}@keyframes c2pl{50%{opacity:.3}}',
    '.c2-ttl.parado i{background:#64748b;box-shadow:none;animation:none}.c2-ttl em{font-style:normal;font-weight:700;letter-spacing:0;text-transform:none;color:#6f7790;margin-left:auto}',
    '.c2-g2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}.c2-g3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:12px}.c2-g2>div,.c2-g3>div{min-width:0}',
    '.c2 .c2-in{width:100%!important;height:40px!important;border-radius:11px!important;border:1px solid #262a40!important;background:rgba(0,0,0,.4)!important;color:#fff!important;font:700 14px Inter,system-ui,sans-serif!important;padding:0 10px!important;outline:0!important;margin:0!important;box-shadow:none!important;min-width:0!important;display:block!important}',
    '.c2 select.c2-in option{background:#0d0f1a;color:#fff}.c2 .c2-in:focus{border-color:#8b5cf6!important}',
    '.c2-chips{display:flex;gap:6px;margin-bottom:12px}',
    '.c2 .c2-chips>.ctx-mult-btn{all:unset;cursor:pointer;flex:1;text-align:center;border:1px solid #262a40!important;border-radius:10px!important;padding:8px 0!important;font:700 12px Inter,system-ui,sans-serif!important;color:#aab!important;background:transparent!important}',
    '.c2 .c2-chips>.ctx-mult-btn.active{border-color:#8b5cf6!important;background:rgba(139,92,246,.16)!important;color:#fff!important}',
    '.c2-modes{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:12px}',
    '.c2 .c2-modes>.ctx-mode-card{all:unset;cursor:pointer;border:1px solid #262a40!important;border-radius:11px!important;padding:8px 10px!important;background:transparent!important;display:block}',
    '.c2 .c2-modes>.ctx-mode-card.active{border-color:#8b5cf6!important;background:rgba(139,92,246,.16)!important}',
    '.c2 .ctx-mode-title{font:800 12.5px Inter,system-ui,sans-serif!important;color:#fff!important;margin:0!important}.c2 .ctx-mode-desc{font:600 10.5px Inter,system-ui,sans-serif!important;color:#8b93a7!important;margin:2px 0 0!important}',
    '.c2-conf{border:1px solid #262a40;border-radius:12px;padding:10px 12px;margin-bottom:12px;background:rgba(0,0,0,.25)}',
    '.c2-conf .h{display:flex;justify-content:space-between;font-size:12px;color:#aab3c9}.c2 #ctxConfLabel{color:#a78bfa!important;font:700 13px "Space Mono",ui-monospace,monospace!important}',
    '.c2 #ctxConfianca{width:100%!important;accent-color:#8b5cf6;margin:8px 0 2px!important}.c2 #ctxConfHint{font-size:10.5px!important;color:#6f7790!important}',
    '.c2-voz{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;font-size:12px;color:#aab3c9}',
    '.c2 #ctxStartBtn{width:100%!important;border:0!important;border-radius:14px!important;padding:14px!important;font:900 15px Inter,system-ui,sans-serif!important;color:#fff!important;background:linear-gradient(135deg,#ec4899,#7c3aed)!important;box-shadow:0 10px 30px rgba(236,72,153,.28)!important;cursor:pointer;margin:0!important}',
    '.c2 #ctxStartBtn.c2-run{background:linear-gradient(135deg,#dc2626,#f97316)!important;box-shadow:0 10px 30px rgba(239,68,68,.3)!important}',
    /* raciocínio */
    '.c2-think{border-color:rgba(236,72,153,.35);box-shadow:0 0 40px rgba(139,92,246,.12);transition:box-shadow .4s}.c2-think.novo{box-shadow:0 0 50px rgba(236,72,153,.32)}',
    '.c2-tb{display:flex;gap:20px;align-items:center}.c2-ring{position:relative;width:140px;height:140px;flex-shrink:0}.c2-ring svg{width:100%;height:100%}',
    '.c2-ring .c{position:absolute;inset:0;display:grid;place-content:center;text-align:center}.c2-ring .c b{font:900 34px Inter,system-ui,sans-serif}.c2-ring .c small{font-size:9.5px;font-weight:800;letter-spacing:1px;color:#9aa3c0}',
    '.c2-tx{flex:1;min-width:0}.c2-bdg{display:inline-block;font-size:10px;font-weight:900;letter-spacing:1px;padding:4px 9px;border-radius:999px;margin-bottom:6px}',
    '.c2-tx h3{margin:0 0 6px;font:900 22px Inter,system-ui,sans-serif}.c2-tx p{margin:0;font-size:14px;line-height:1.55;color:#dbe2f0;min-height:44px}',
    '.c2-dec{position:relative;height:8px;border-radius:5px;background:linear-gradient(90deg,#3b1d2a,#2a2f45 50%,#1b3a2a);margin:16px 0 18px}',
    '.c2-dec i{position:absolute;top:-4px;width:16px;height:16px;border-radius:50%;margin-left:-8px;transition:left .6s}.c2-dec u{position:absolute;top:-6px;bottom:-6px;width:2px;background:#fff;opacity:.6}',
    '.c2-dec span{position:absolute;right:0;top:12px;font-size:10px;color:#8b93a7}',
    '.c2-motor{font-size:11px;color:#8b93a7;margin-top:-6px}.c2 #ctxEngineText{display:inline!important;font-size:11px!important;color:#c4b5fd!important;background:none!important;border:0!important;padding:0!important}',
    '.c2-inds{display:grid;grid-template-columns:1fr 1fr;gap:8px}.c2-ind{background:rgba(0,0,0,.3);border:1px solid #23263a;border-radius:12px;padding:10px 12px}',
    '.c2-ind span{display:block;font-size:10px;font-weight:800;letter-spacing:.8px;color:#7c84a0;text-transform:uppercase}.c2-ind b{display:block;font-size:14px;margin:3px 0 8px}',
    '.c2-ind p{position:relative;margin:0;height:6px;border-radius:4px;background:linear-gradient(90deg,rgba(248,113,113,.35),rgba(251,191,36,.25),rgba(74,222,128,.35))}.c2-ind p i{position:absolute;top:-3px;width:12px;height:12px;border-radius:50%;margin-left:-6px;transition:left .6s}',
    '.c2-rk{display:grid;grid-template-columns:26px minmax(0,1fr) 110px 30px 16px;gap:10px;align-items:center;padding:7px 8px;border-radius:10px;font-size:13px}',
    '.c2-rk.at{background:rgba(139,92,246,.12);border:1px solid rgba(139,92,246,.35)}.c2-rk em{font-style:normal;color:#a78bfa;font-weight:900}',
    '.c2-rk small{font-size:9.5px;font-weight:800;color:#a78bfa;letter-spacing:.5px;text-transform:uppercase;margin-left:4px}',
    '.c2-rk p{margin:0;height:6px;border-radius:4px;background:#141726;overflow:hidden}.c2-rk p i{display:block;height:100%;background:linear-gradient(90deg,#ec4899,#8b5cf6);transition:width .6s}.c2-rk b{font:700 12px "Space Mono",ui-monospace,monospace}',
    '.c2-sw{margin-top:8px;font-size:12px;padding:9px 12px;border-radius:10px;border:1px solid rgba(99,102,241,.4);background:rgba(99,102,241,.1);color:#c7d2fe}.c2-sw.off{border-color:#23263a;background:transparent;color:#6f7790}',
    '.c2-vazio{color:#6f7790;font-size:12px;padding:14px 4px}',
    '.c2-kpi{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}.c2-kpi div{background:rgba(0,0,0,.35);border:1px solid #23263a;border-radius:12px;padding:9px 10px}',
    '.c2-kpi span{display:block;font-size:9.5px;font-weight:800;letter-spacing:.6px;color:#7c84a0;text-transform:uppercase}.c2-kpi b{display:block;font:700 17px "Space Mono",ui-monospace,monospace;margin-top:2px}',
    '.c2-spark{width:100%;height:70px;display:block}.c2-tl{display:flex;gap:4px;flex-wrap:wrap;min-height:12px}.c2-tl i{width:12px;height:12px;border-radius:4px}',
    '.c2 #ctxFeedBox{max-height:330px!important;overflow:auto!important;background:transparent!important;border:0!important;padding:0!important;margin:0!important;height:auto!important}',
    '.c2 #ctxFeedBox .ctx-feed-line{border-radius:8px;background:rgba(0,0,0,.25)!important;margin-bottom:5px!important;padding:6px 8px!important;border:0!important;font-size:12px}',
    '.c2 #ctxTradesList{max-height:200px;overflow:auto}',
    '.c2-lim{all:unset;cursor:pointer;font:800 10px Inter,system-ui,sans-serif;color:#a78bfa;border:1px solid rgba(139,92,246,.4);border-radius:8px;padding:3px 8px;margin-left:auto}',
    '@media (max-width:1150px){.c2-cols{grid-template-columns:1fr}.c2-inds{grid-template-columns:1fr}}',
    '@media (max-width:760px){.c2{padding:12px 12px 24px}.c2-tb{flex-direction:column;text-align:center}.c2-hd{position:relative}.c2-hd>div:nth-child(2){padding-right:46px}.c2-acc{width:100%}.c2-x{position:absolute;top:5px;right:0}.c2-hd h1{font-size:18px}.c2-hd p{display:none}}'
  ].join('\n');
  document.head.appendChild(css);

  /* ─────────── fundo "Sinapse": ondas cerebrais com pulsos de luz ─────────── */
  function iniciarFundo(cv, aberto) {
    var x = cv.getContext('2d'), W = 0, H = 0, t = 0, pulsos = [], nos = [];
    var ONDAS = [{ c: '236,72,153', a: .09, f: 1.6, v: .55, y: .3 }, { c: '139,92,246', a: .07, f: 2.3, v: -.4, y: .45 }, { c: '34,211,238', a: .05, f: 3.1, v: .7, y: .6 }, { c: '168,85,247', a: .08, f: 1.2, v: -.3, y: .75 }];
    function Y(o, px) { return H * o.y + Math.sin(px / W * Math.PI * 2 * o.f + t * o.v) * H * o.a + Math.sin(px / W * 17 + t * 2.2) * H * .008; }
    (function q() {
      requestAnimationFrame(q);
      if (document.hidden || !aberto()) return;
      var d = Math.min(devicePixelRatio || 1, 2), w = cv.clientWidth, h = cv.clientHeight; if (!w || !h) return;
      if (w !== W || h !== H) { W = w; H = h; cv.width = W * d; cv.height = H * d; nos = []; for (var i = 0; i < 26; i++) nos.push({ x: Math.random() * W, y: Math.random() * H, f: Math.random() * 6 }); }
      x.setTransform(d, 0, 0, d, 0, 0); x.clearRect(0, 0, W, H); t += .016;
      var g = x.createRadialGradient(W * .5, H * .35, 0, W * .5, H * .35, W * .6); g.addColorStop(0, 'rgba(236,72,153,.10)'); g.addColorStop(.5, 'rgba(139,92,246,.06)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, 0, W, H);
      nos.forEach(function (n) { var b = .15 + .25 * (.5 + .5 * Math.sin(t * 1.5 + n.f)); x.fillStyle = 'rgba(244,114,182,' + b + ')'; x.beginPath(); x.arc(n.x, n.y, 1.6, 0, 7); x.fill(); });
      ONDAS.forEach(function (o, k) {
        x.lineWidth = 1.4; x.strokeStyle = 'rgba(' + o.c + ',.22)'; x.beginPath();
        for (var px = 0; px <= W; px += 6) { var py = Y(o, px); px ? x.lineTo(px, py) : x.moveTo(px, py); } x.stroke();
        if (Math.random() < .025) pulsos.push({ o: k, p: 0, v: 2 + Math.random() * 2.5 });
      });
      pulsos.forEach(function (p) {
        p.p += p.v; var o = ONDAS[p.o];
        for (var i = 0; i < 14; i++) { var px = p.p - i * 7; if (px < 0 || px > W) continue; var a = (1 - i / 14) * .9;
          x.fillStyle = 'rgba(' + o.c + ',' + a + ')'; x.beginPath(); x.arc(px, Y(o, px), i ? 1.8 : 3.2, 0, 7); x.fill(); }
        if (p.p > 0 && p.p < W) { x.shadowColor = 'rgb(' + o.c + ')'; x.shadowBlur = 16; x.fillStyle = '#fff'; x.beginPath(); x.arc(p.p, Y(o, p.p), 1.6, 0, 7); x.fill(); x.shadowBlur = 0; }
      });
      pulsos = pulsos.filter(function (p) { return p.p < W + 120; });
      var v = x.createRadialGradient(W / 2, H / 2, Math.min(W, H) * .25, W / 2, H / 2, Math.max(W, H) * .75); v.addColorStop(0, 'rgba(5,6,10,0)'); v.addColorStop(1, 'rgba(5,6,10,.72)'); x.fillStyle = v; x.fillRect(0, 0, W, H);
    })();
  }

  /* ─────────────────── montagem ─────────────────── */
  var R = {}, montado = false;
  function aberto() { var m = $('alphaCtxIaModal'); if (!m) return false; var s = getComputedStyle(m); return s.display !== 'none' && s.visibility !== 'hidden'; }
  function mover(e, d, c) { if (!e) return null; if (c) e.classList.add(c); d.appendChild(e); return e; }
  function campo(rot, e, wrap) { var d = el('div'); d.appendChild(el('div', 'c2-lb', rot)); if (e) { e.classList.add('c2-in'); d.appendChild(e); } wrap.appendChild(d); return d; }

  function montar() {
    var modal = $('alphaCtxIaModal'), lay = modal && modal.querySelector('.ctx-layout');
    if (!modal || !lay || !$('ctxStartBtn') || !$('ctxMercado')) return false;
    Array.prototype.slice.call(modal.querySelectorAll('*')).forEach(function (e) {
      var p = e.style.position; if (!p) { try { p = getComputedStyle(e).position; } catch (z) {} }
      if (p === 'fixed') { modal.appendChild(e); e.classList.add('c2-keep'); }
    });
    var bg = el('canvas', 'c2-bg'); modal.insertBefore(bg, modal.firstChild); iniciarFundo(bg, aberto);
    var raiz = el('div', 'c2');

    /* cabeçalho */
    var hd = el('div', 'c2-hd', '<div class="c2-ic">🧠</div><div><h1>Alpha IA Contextual <span>IA REAL</span></h1><p>A IA lê o gráfico, explica o raciocínio e escolhe o melhor mercado</p></div><div class="c2-sp"></div>');
    var acc = el('div', 'c2-acc'); mover($('ctxSaldoDemo'), acc); mover($('ctxSaldoReal'), acc);
    R.ses = el('div', 'c2-pill', 'Sessão +$0.00'); acc.appendChild(R.ses);
    var ab = modal.querySelector('[onclick*="abrirModalIaAlpha"]'); if (ab) { ab.classList.add('c2-alpha'); ab.textContent = '✨ Modo IA Alpha'; acc.appendChild(ab); }
    var x = el('button', 'c2-x', '✕'); x.type = 'button'; x.onclick = function () { if (typeof window.fecharCtxIa === 'function') window.fecharCtxIa(); }; acc.appendChild(x);
    hd.appendChild(acc); raiz.appendChild(hd);

    var grid = el('div', 'c2-cols'); raiz.appendChild(grid);

    /* ── esquerda: configuração (campos originais) ── */
    var pe = el('div', 'c2-pn'); grid.appendChild(pe);
    var g1 = el('div', 'c2-g2'); campo('Mercado', $('ctxMercado'), g1); campo('Contrato', $('ctxTipo'), g1); pe.appendChild(g1);
    var g2 = el('div', 'c2-g3'); campo('Entrada', $('ctxStake'), g2); campo('Lucro alvo', $('ctxLucroAlvo'), g2); campo('Stop', $('ctxStopLoss'), g2); pe.appendChild(g2);
    var g3 = el('div', 'c2-g2'); campo('Duração', $('ctxDuracao'), g3); pe.appendChild(g3);
    var mb = modal.querySelectorAll('.ctx-mult-btn');
    if (mb.length) { pe.appendChild(el('div', 'c2-lb', 'Multiplicador após perda')); var ch = el('div', 'c2-chips'); Array.prototype.forEach.call(mb, function (b) { ch.appendChild(b); }); pe.appendChild(ch); }
    var md = modal.querySelectorAll('.ctx-mode-card');
    if (md.length) { pe.appendChild(el('div', 'c2-lb', 'Modo de operação')); var mo = el('div', 'c2-modes'); Array.prototype.forEach.call(md, function (b) { mo.appendChild(b); }); pe.appendChild(mo); }
    var cf = $('ctxConfianca');
    if (cf) {
      var cb = el('div', 'c2-conf'), h = el('div', 'h'); h.appendChild(el('span', null, 'Confiança mínima da IA')); mover($('ctxConfLabel'), h);
      cb.appendChild(h); cb.appendChild(cf); mover($('ctxConfHint'), cb); pe.appendChild(cb);
    }
    var vt = $('ctxVozToggle');
    if (vt) { var vz = el('div', 'c2-voz', '<span>🔊 Voz da IA narrando as decisões</span>'); vz.appendChild(vt); pe.appendChild(vz); }
    pe.appendChild($('ctxStartBtn'));

    /* ── centro: raciocínio, o que a IA vê, ranking ── */
    var mid = el('div', 'c2-mid'); grid.appendChild(mid);
    R.think = el('div', 'c2-pn c2-think');
    R.ttl = el('div', 'c2-ttl', '<i></i><span>Raciocínio da IA</span><em></em>'); R.think.appendChild(R.ttl);
    R.think.appendChild(el('div', 'c2-tb', '<div class="c2-ring"></div><div class="c2-tx"><span class="c2-bdg"></span><h3></h3><p></p><div class="c2-dec"><i></i><u></u><span></span></div></div>'));
    var en = $('ctxEngineText'); if (en) { var mt = el('div', 'c2-motor', ''); mt.appendChild(en); R.think.appendChild(mt); }
    mid.appendChild(R.think);
    var pi = el('div', 'c2-pn'); pi.appendChild(el('div', 'c2-ttl', '📐 O que a IA está vendo')); R.inds = el('div', 'c2-inds'); pi.appendChild(R.inds); mid.appendChild(pi);
    var pr = el('div', 'c2-pn'); pr.appendChild(el('div', 'c2-ttl', '🏆 Ranking de mercados<em>a IA troca quando outro mercado fica 15+ pontos melhor</em>')); R.rank = el('div'); pr.appendChild(R.rank); mid.appendChild(pr);

    /* ── direita: sessão + registros ── */
    var pd = el('div', 'c2-pn'); grid.appendChild(pd);
    pd.appendChild(el('div', 'c2-ttl', '📊 Sessão'));
    R.kpi = el('div', 'c2-kpi', '<div><span>Lucro</span><b data-k="l">+$0.00</b></div><div><span>Acerto</span><b data-k="w">—</b></div><div><span>Operações</span><b data-k="n">0</b></div><div><span>Score médio</span><b data-k="s">—</b></div>');
    pd.appendChild(R.kpi);
    R.spark = el('canvas', 'c2-spark'); pd.appendChild(R.spark);
    var l1 = el('div', 'c2-lb', 'Linha do tempo'); l1.style.marginTop = '10px'; pd.appendChild(l1);
    R.tl = el('div', 'c2-tl'); pd.appendChild(R.tl);
    var rh = el('div', 'c2-lb', 'Registros'); rh.style.cssText = 'margin-top:12px;display:flex;align-items:center';
    var lim = el('button', 'c2-lim', 'Limpar'); lim.type = 'button'; lim.onclick = function () { if (typeof window.ctxLimparFeed === 'function') window.ctxLimparFeed(); }; rh.appendChild(lim);
    pd.appendChild(rh); mover($('ctxFeedBox'), pd);
    var tr = $('ctxTradesList'); if (tr) { pd.appendChild(el('div', 'c2-lb', 'Últimos trades')).style.marginTop = '12px'; pd.appendChild(tr); }

    modal.appendChild(raiz); modal.classList.add('c2-on');
    montado = true; return true;
  }

  /* ─────────────────── raciocínio ─────────────────── */
  function arc(p, c) { var r = 58, C = 2 * Math.PI * r; return '<svg viewBox="0 0 140 140"><circle cx="70" cy="70" r="' + r + '" fill="none" stroke="#1c2033" stroke-width="11"/><circle cx="70" cy="70" r="' + r + '" fill="none" stroke="' + c + '" stroke-width="11" stroke-linecap="round" stroke-dasharray="' + (C * Math.max(0, Math.min(1, p))) + ' ' + C + '" transform="rotate(-90 70 70)" style="filter:drop-shadow(0 0 8px ' + c + ');transition:stroke-dasharray .6s"/></svg>'; }
  var ultTexto = '', digit = null;
  function escrever(p, t) { clearInterval(digit); var i = 0; p.textContent = ''; digit = setInterval(function () { p.textContent = t.slice(0, i += 2); if (i >= t.length) clearInterval(digit); }, 16); }
  function lerStatus() {
    var spans = ($('ctxStatusText') || document.createElement('div')).querySelectorAll('span');
    var dirTxt = spans[0] ? spans[0].textContent : '', sc = spans[1] ? num(spans[1].textContent) : null, resumo = spans[2] ? spans[2].textContent : '';
    var dir = /UP|▲|ALTA|RISE/i.test(dirTxt) ? 'UP' : /DOWN|▼|BAIXA|FALL/i.test(dirTxt) ? 'DOWN' : null;
    var u = IA.porMerc[($('ctxMercado') || {}).value] || null;
    if (u && u.res) { if (typeof u.res.score === 'number') sc = u.res.score; if (u.res.direcao) dir = /UP/i.test(u.res.direcao) ? 'UP' : /DOWN/i.test(u.res.direcao) ? 'DOWN' : dir; resumo = u.res.resumo || resumo; }
    var quote = (($('ctxQuoteText') || {}).textContent || '').trim();
    return { dir: dir, sc: sc, resumo: quote && !/assim que o rob/i.test(quote) ? quote : resumo };
  }
  function desenharRaciocinio() {
    var s = st(), r = lerStatus(), lim = num(($('ctxConfLabel') || {}).textContent) || 65, rod = !!s.running;
    var merc = ($('ctxMercado') || {}).value;
    R.ttl.classList.toggle('parado', !rod);
    R.ttl.querySelector('span').textContent = 'Raciocínio da IA · ' + nomeMerc(merc);
    var u = IA.porMerc[merc]; R.ttl.querySelector('em').textContent = u ? new Date(u.t).toTimeString().slice(0, 8) : (rod ? 'analisando…' : '');
    var tem = r.sc !== null && r.dir;
    var c = !tem ? '#94a3b8' : r.sc < lim ? '#fbbf24' : r.dir === 'UP' ? '#4ade80' : '#f87171';
    var bd = !rod ? ['⏸ PARADO', '#94a3b8'] : !tem ? ['⏳ ANALISANDO', '#94a3b8'] : r.sc >= lim ? ['🚀 ENTRADA LIBERADA', c] : ['⏳ ABAIXO DO MÍNIMO', '#fbbf24'];
    var box = R.think;
    box.querySelector('.c2-ring').innerHTML = arc((r.sc || 0) / 100, c) + '<div class="c"><b style="color:' + c + '">' + (r.sc === null ? '—' : Math.round(r.sc)) + '</b><small>CONFIANÇA</small></div>';
    var b = box.querySelector('.c2-bdg'); b.textContent = bd[0]; b.style.cssText = 'background:' + bd[1] + '22;color:' + bd[1];
    var h3 = box.querySelector('h3'); h3.textContent = !tem ? (rod ? 'Lendo o mercado…' : 'Inicie o robô para ver a análise') : r.dir === 'UP' ? '▲ RISE (alta)' : '▼ FALL (queda)'; h3.style.color = tem ? (r.dir === 'UP' ? '#4ade80' : '#f87171') : '#e2e8f0';
    var txt = r.resumo || (rod ? 'A IA está juntando as últimas velas para analisar.' : 'Assim que o robô iniciar, o raciocínio da IA aparece aqui em tempo real.');
    if (txt !== ultTexto) { ultTexto = txt; escrever(box.querySelector('p'), txt); box.classList.add('novo'); setTimeout(function () { box.classList.remove('novo'); }, 900); }
    var dec = box.querySelector('.c2-dec'); dec.querySelector('i').style.cssText = 'left:' + Math.max(0, Math.min(100, r.sc || 0)) + '%;background:' + c + ';box-shadow:0 0 10px ' + c;
    var eng = $('ctxEngineText');
    if (eng) { var w = document.createTreeWalker(eng, NodeFilter.SHOW_TEXT), nd; while ((nd = w.nextNode())) { var t0 = nd.nodeValue, t1 = t0.replace(/\b(1HZ\d+V|R_\d+|BOOM\d+N?|CRASH\d+N?|stpRNG\w*)\b/g, function (c) { return nomeMerc(c); }); if (t1 !== t0) nd.nodeValue = t1; } }
    dec.querySelector('u').style.left = lim + '%'; dec.querySelector('span').textContent = 'mínimo ' + lim;
  }

  /* ─────────────────── o que a IA está vendo ─────────────────── */
  function lado(v) {
    if (v == null) return 0; if (typeof v === 'number') return v > 0 ? 1 : v < 0 ? -1 : 0;
    var s = String(v).toLowerCase(); return /up|alta|bull|subi|cima|compra|\+/.test(s) ? 1 : /down|baixa|bear|caind|queda|baixo|venda|-/.test(s) ? -1 : 0;
  }
  function velas(l3) {
    var a = Array.isArray(l3) ? l3 : typeof l3 === 'string' ? l3.split(/[\s,;|]+/).filter(Boolean) : [];
    if (a.length === 1 && typeof a[0] === 'string' && a[0].length > 1) a = a[0].split('');
    var up = 0, n = 0;
    a.forEach(function (v) { var k = typeof v === 'object' && v ? (v.c > v.o ? 1 : v.c < v.o ? -1 : 0) : lado(v) || (/^[gv]/i.test(String(v)) ? 1 : /^[rp]/i.test(String(v)) ? -1 : 0); if (k) { n++; if (k > 0) up++; } });
    return { up: up, n: n };
  }
  function desenharIndicadores() {
    var u = IA.porMerc[($('ctxMercado') || {}).value] || IA.ultimo;
    if (!u) { R.inds.innerHTML = '<div class="c2-vazio" style="grid-column:1/-1">Os indicadores aparecem na primeira análise da IA.</div>'; return; }
    var I = u.ind, rsi = num(I.rsi), bb = num(I.bb_pct); if (bb !== null && bb > 1.5) bb = bb / 100;
    var et = lado(I.ema_trend), vl = velas(I.last3);
    var lst = [
      ['RSI 14', rsi === null ? '—' : Math.round(rsi) + ' · ' + (rsi > 70 ? 'esticado para cima' : rsi < 30 ? 'esticado para baixo' : rsi > 55 ? 'força compradora' : rsi < 45 ? 'força vendedora' : 'neutro'), rsi === null ? .5 : rsi / 100],
      ['Médias 9/21', et > 0 ? 'subindo' : et < 0 ? 'caindo' : 'sem direção', et > 0 ? .82 : et < 0 ? .18 : .5],
      ['Bollinger', bb === null ? '—' : bb > .85 ? 'perto do topo' : bb < .15 ? 'perto do fundo' : 'meio da banda', bb === null ? .5 : Math.max(0, Math.min(1, bb))],
      ['Últimas velas', vl.n ? (vl.up > vl.n / 2 ? vl.up + ' de ' + vl.n + ' em alta' : vl.up < vl.n / 2 ? (vl.n - vl.up) + ' de ' + vl.n + ' em queda' : 'alternando') : '—', vl.n ? vl.up / vl.n : .5]];
    R.inds.innerHTML = lst.map(function (x) { var p = x[2], cl = p > .6 ? '#4ade80' : p < .4 ? '#f87171' : '#fbbf24'; return '<div class="c2-ind"><span>' + x[0] + '</span><b>' + x[1] + '</b><p><i style="left:' + p * 100 + '%;background:' + cl + ';box-shadow:0 0 8px ' + cl + '"></i></p></div>'; }).join('');
  }

  /* ─────────────────── ranking ─────────────────── */
  /* TROCA-V1: ranking com hora de cada análise + troca automática de mercado */
  var INCOMP = {}, rdRef = null, rdT = 0, ultTroca = 0, ultScan = 0;
  function durAtual() { return (($('ctxDuracao') || {}).value || '') + '|' + (($('ctxTipo') || {}).value || ''); }
  function incompat(m) { return !!INCOMP[m + '|' + durAtual()]; }
  window._c2MarcarIncompat = function (m) {
    if (!m) return; INCOMP[m + '|' + durAtual()] = true;
    try { if (typeof window.ctxAddFeed === 'function') window.ctxAddFeed('⛔ ' + nomeMerc(m) + ' não aceita esta duração/contrato — vou procurar outro mercado.', '#f59e0b'); } catch (e) {}
    ultTroca = 0; setTimeout(trocar, 300);
  };
  function montarLista() {
    var rd = window._ctxRankingData, lista = [];
    if (rd !== rdRef) { rdRef = rd; rdT = Date.now(); }
    if (rd && rd.length) lista = rd.map(function (r) { return { m: r.mercado, s: r.score, d: r.direcao, t: rdT }; });
    Object.keys(IA.porMerc).forEach(function (k) {
      var r = IA.porMerc[k]; if (!r.res || typeof r.res.score !== 'number') return;
      var j = lista.find(function (x) { return x.m === k; });
      if (!j) lista.push({ m: k, s: r.res.score, d: r.res.direcao, t: r.t }); else if (r.t > j.t) { j.s = r.res.score; j.d = r.res.direcao; j.t = r.t; }
    });
    return lista.filter(function (x) { return typeof x.s === 'number' && Date.now() - x.t < 10 * 60000; }).sort(function (a, b) { return b.s - a.s; });
  }
  function avaliar(lista) {
    var atual = ($('ctxMercado') || {}).value;
    var ok = lista.filter(function (x) { return !incompat(x.m); }), ref = lista.find(function (x) { return x.m === atual; });
    var refS = incompat(atual) ? -999 : ref && Date.now() - ref.t < 6 * 60000 ? ref.s : null, top = ok[0];
    var troca = top && top.m !== atual && Date.now() - top.t < 6 * 60000 && (refS === null ? top.s >= 60 : top.s >= refS + 15);
    return { atual: atual, ref: ref, refS: refS, top: top, troca: troca };
  }
  function trocar() {
    var s = st(); if (!s.running || s.waiting) return;
    var sel = $('ctxMercado'); if (!sel) return;
    var A = avaliar(montarLista());
    if (A.troca && Date.now() - ultTroca > 60000) {
      ultTroca = Date.now();
      sel.value = A.top.m; try { sel.dispatchEvent(new Event('change', { bubbles: true })); } catch (e) {}
      try { if (typeof window.chartConnect === 'function') window.chartConnect(A.top.m); } catch (e) {}
      try { if (typeof window.ctxAddFeed === 'function') window.ctxAddFeed('🔀 Trocando para ' + nomeMerc(A.top.m) + ' — score ' + Math.round(A.top.s) + '% (era ' + (A.refS === null || A.refS < 0 ? 'sem boa leitura' : Math.round(A.refS) + '%') + ' em ' + nomeMerc(A.atual) + ')', '#6366f1'); } catch (e) {}
    }
    // varredura periódica: mantém o ranking atualizado mesmo quando o mercado atual está operando
    if (!s._scanning && typeof window.ctxScanMercados === 'function' && Date.now() - ultScan > 5 * 60000) {
      ultScan = Date.now(); try { window.ctxScanMercados(); } catch (e) {}
    }
  }
  var estavaRod = false;
  setInterval(function () { var r = !!st().running; if (r && !estavaRod) { ultScan = Date.now() - 5 * 60000 + 20000; ultTroca = 0; } estavaRod = r; try { if (r) trocar(); } catch (e) {} }, 2000);

  function desenharRanking() {
    var lista = montarLista(), A = avaliar(lista), atual = A.atual;
    if (!lista.length) { R.rank.innerHTML = '<div class="c2-vazio">A IA analisa todos os mercados logo depois de iniciar e a cada 5 minutos — o ranking aparece aqui.</div>'; return; }
    var mostra = lista.slice(0, 8); if (A.ref && mostra.indexOf(A.ref) < 0) mostra.push(A.ref);
    R.rank.innerHTML = mostra.map(function (x) { var i = lista.indexOf(x), at = x.m === atual, up = /UP/i.test(x.d || ''), bad = incompat(x.m);
      return '<div class="c2-rk' + (at ? ' at' : '') + '"' + (bad ? ' style="opacity:.45"' : '') + '><em>' + (i + 1) + 'º</em><span>' + nomeMerc(x.m) + (at ? ' <small>atual</small>' : '') + (bad ? ' <small style="color:#f87171">não aceita esta duração</small>' : '') + '</span><p><i style="width:' + Math.max(0, Math.min(100, x.s)) + '%"></i></p><b>' + Math.round(x.s) + '</b><strong style="color:' + (up ? '#4ade80' : '#f87171') + '">' + (x.d ? (up ? '▲' : '▼') : '') + '</strong></div>'; }).join('');
    var msg = A.troca ? '<div class="c2-sw">🔀 Trocando para <b>' + nomeMerc(A.top.m) + '</b> — ' + Math.round(A.top.s) + '% contra ' + (A.refS === null || A.refS < 0 ? 'nenhuma boa leitura' : Math.round(A.refS) + '%') + ' no atual</div>'
      : '<div class="c2-sw off">Mantendo ' + nomeMerc(atual) + (A.refS !== null && A.refS >= 0 ? ' (' + Math.round(A.refS) + '%)' : '') + ' — nenhum mercado está 15 pontos melhor.</div>';
    R.rank.insertAdjacentHTML('beforeend', msg);
  }

  /* ─────────────────── sessão ─────────────────── */
  var hist = [0], ultN = -1;
  function desenharSessao() {
    var s = st(), lucro = (+s.lucro || 0) - (+s.perda || 0), n = +s.trades || 0, w = +s.wins || 0;
    if (n < ultN) hist = [0]; if (n !== ultN && n > 0) hist.push(lucro); ultN = n;
    var k = function (q) { return R.kpi.querySelector('[data-k="' + q + '"]'); };
    var txt = (lucro < 0 ? '−$' : '+$') + Math.abs(lucro).toFixed(2), cor = lucro > 0 ? '#4ade80' : lucro < 0 ? '#f87171' : '#e2e8f0';
    k('l').textContent = txt; k('l').style.color = cor; k('w').textContent = n ? Math.round(w / n * 100) + '%' : '—'; k('n').textContent = n;
    k('s').textContent = n && s.scoreTotal ? Math.round(s.scoreTotal / n) : '—';
    R.ses.textContent = 'Sessão ' + txt; R.ses.style.color = cor;
    var hs = (s.historico || []).slice(-40); R.tl.innerHTML = hs.map(function (h) { var ok = /WIN/i.test(h.resultado || h.dir || ''); return '<i style="background:' + (ok ? '#4ade80' : '#f87171') + '"></i>'; }).join('');
    var cv = R.spark, d = Math.min(devicePixelRatio || 1, 2), W = cv.clientWidth, H = cv.clientHeight; if (!W) return;
    cv.width = W * d; cv.height = H * d; var x = cv.getContext('2d'); x.scale(d, d);
    var mn = Math.min.apply(0, hist.concat(0)), mx = Math.max.apply(0, hist.concat(.01)), Y = function (v) { return H - 6 - (v - mn) / (mx - mn || 1) * (H - 12); };
    x.strokeStyle = 'rgba(255,255,255,.15)'; x.setLineDash([3, 3]); x.beginPath(); x.moveTo(0, Y(0)); x.lineTo(W, Y(0)); x.stroke(); x.setLineDash([]);
    x.strokeStyle = lucro >= 0 ? '#4ade80' : '#f87171'; x.lineWidth = 2; x.beginPath(); hist.forEach(function (v, i) { var X = i / Math.max(1, hist.length - 1) * W; i ? x.lineTo(X, Y(v)) : x.moveTo(X, Y(v)); }); x.stroke();
    var b = $('ctxStartBtn'); if (b) b.classList.toggle('c2-run', !!s.running);
    var conta = s.conta === 'real' ? 'real' : 'demo';
    if ($('ctxSaldoDemo')) $('ctxSaldoDemo').classList.toggle('c2-sel', conta === 'demo'); if ($('ctxSaldoReal')) $('ctxSaldoReal').classList.toggle('c2-sel', conta === 'real');
  }

  function tick() {
    try {
      if (!montado && !montar()) return;
      if (!aberto()) return;
      desenharRaciocinio(); desenharIndicadores(); desenharRanking(); desenharSessao();
    } catch (e) { console.warn('[ctx-v2]', e); }
  }
  setInterval(tick, 800);
  if (document.readyState !== 'loading') tick(); else document.addEventListener('DOMContentLoaded', tick);
})();
