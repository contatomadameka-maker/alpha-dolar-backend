/* IA2-FULL-V1: no grafico embutido, avisa a pagina de fora quando a IA ALPHA abre/fecha (para ela ir para tela cheia) */
(function () {
  try {
    if (!/[?&]embed=1/.test(location.search) || window.parent === window) return;
    var ult = null;
    setInterval(function () {
      var p = document.getElementById('ia2'), on = !!(p && p.classList.contains('on'));
      if (on !== ult) { ult = on; window.parent.postMessage({ type: 'alpha-ia2', open: on }, location.origin); }
    }, 250);
  } catch (e) {}
})();
/* Alpha Dolar — IA ALPHA v2 (tela nova, 3 visuais para o usuário escolher)
 * Abre por cima da tela antiga do IA Alpha (que continua existindo, escondida).
 * Lê as operações direto do robô que abriu o IA Alpha (IA Pro, IA Avançado ou IA Contextual),
 * inclusive as que já aconteceram antes de abrir. O botão PARAR usa o botão do próprio robô.
 * Para desfazer: remover este arquivo da página.
 */
(function () {
  'use strict';
  if (window.__ia2) return; window.__ia2 = true;
  var $ = function (id) { return document.getElementById(id); };
  function num(s) { var m = String(s == null ? '' : s).replace(/[$\s]/g, '').replace('−', '-').replace(',', '.').match(/-?\d+(\.\d+)?/); return m ? parseFloat(m[0]) : null; }
  function m$(v) { return (v < 0 ? '−$' : '+$') + Math.abs(v).toFixed(2); }
  function vis(el) { if (!el) return false; var s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' && el.getClientRects().length > 0; }
  function ls(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }

  var T = { nucleo: ['#8b5cf6', 'rgba(139,92,246,.45)', 'rgba(139,92,246,.25)'], esfera: ['#22d3ee', 'rgba(34,211,238,.45)', 'rgba(34,211,238,.22)'], reator: ['#ec4899', 'rgba(236,72,153,.45)', 'rgba(236,72,153,.22)'] };
  var OPT = T[ls('ia_alpha_visual')] ? ls('ia_alpha_visual') : 'nucleo', score = 0, aberto = false, ORIG = 'avancado';

  /* ───────────────────────── estilo ───────────────────────── */
  var css = document.createElement('style');
  css.textContent = [
    '#iaAlphaModal.ia2-esc{visibility:hidden!important;pointer-events:none!important}',
    '#ia2Lancar{position:fixed;left:18px;bottom:18px;z-index:2147481000;border:1px solid rgba(139,92,246,.6);border-radius:999px;padding:11px 18px;font:900 12.5px Inter,system-ui,sans-serif;letter-spacing:1.5px;color:#fff;background:linear-gradient(135deg,#7c3aed,#ec4899);box-shadow:0 10px 30px rgba(139,92,246,.45),0 0 0 0 rgba(236,72,153,.5);cursor:pointer;display:flex;align-items:center;gap:8px;animation:ia2lp 2.4s infinite}',
    '#ia2Lancar:hover{transform:translateY(-2px)}@keyframes ia2lp{70%{box-shadow:0 10px 30px rgba(139,92,246,.45),0 0 0 14px rgba(236,72,153,0)}}',
    '@media (max-width:760px){#ia2Lancar{left:12px;bottom:12px;padding:10px 14px;font-size:11.5px}}',
    '#ia2{position:fixed;inset:0;z-index:2147482000;background:#04050a;color:#e8ecf4;font-family:Inter,system-ui,sans-serif;overflow-y:auto;overflow-x:hidden;display:none;--a:#8b5cf6;--ab:rgba(139,92,246,.45);--ag:rgba(139,92,246,.25)}',
    '#ia2 canvas{background:transparent!important;border:0!important;box-shadow:none!important;border-radius:0!important}',
    '#ia2.on{display:block}#ia2 *,#ia2 *::before,#ia2 *::after{box-sizing:border-box}',
    '#ia2Bg{position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none}',
    '#ia2 .ia2-app{position:relative;z-index:1;max-width:1180px;margin:0 auto;padding:16px 18px 30px;display:flex;flex-direction:column;align-items:center}',
    '#ia2 .ia2-top{width:100%;display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap}',
    '#ia2 .ia2-brand{display:flex;align-items:center;gap:12px}#ia2 .ia2-brand svg{width:42px;height:42px;color:var(--a)}',
    '#ia2 .ia2-brand h1{margin:0;font:900 24px Orbitron,Inter,system-ui,sans-serif;letter-spacing:4px;color:#fff}#ia2 .ia2-brand h1 b{color:var(--a);text-shadow:0 0 18px var(--a)}',
    '#ia2 .ia2-brand small{display:block;font:700 10px Inter,system-ui,sans-serif;letter-spacing:1.5px;color:#8b93a7;margin-top:2px}',
    '#ia2 .ia2-sp{flex:1}',
    '#ia2 .ia2-pill{display:flex;align-items:center;gap:8px;border:1px solid rgba(255,255,255,.12);border-radius:999px;padding:7px 14px;font:800 11px Inter,system-ui,sans-serif;letter-spacing:1.5px;background:rgba(0,0,0,.45)}',
    '#ia2 .ia2-pill i{width:8px;height:8px;border-radius:50%;background:#64748b}#ia2 .ia2-pill.on i{background:#4ade80;box-shadow:0 0 10px #4ade80;animation:ia2pl 1.4s infinite}@keyframes ia2pl{50%{opacity:.35}}',
    '#ia2 .ia2-conta{border-radius:999px;padding:7px 12px;font:900 11px Inter,system-ui,sans-serif;letter-spacing:1px;background:var(--a);color:#fff}#ia2 .ia2-conta.real{background:#f59e0b;color:#1a1204}',
    '#ia2 .ia2-ib{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;border:1px solid rgba(255,255,255,.14);background:rgba(0,0,0,.45);cursor:pointer;color:#cbd5e1;font-size:15px;padding:0}',
    '#ia2 .ia2-ib.x{color:#fca5a5;border-color:rgba(248,113,113,.4)}#ia2 .ia2-ib.off{opacity:.45}',
    '#ia2 .ia2-tema{position:relative}#ia2 .ia2-menu{position:absolute;right:0;top:46px;z-index:5;width:230px;border-radius:14px;padding:6px;background:rgba(10,10,22,.96);border:1px solid rgba(255,255,255,.12);box-shadow:0 20px 40px rgba(0,0,0,.5);display:none}',
    '#ia2 .ia2-tema.aberto .ia2-menu{display:block}#ia2 .ia2-menu div{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:10px;cursor:pointer;font-size:13px;font-weight:700}',
    '#ia2 .ia2-menu div:hover{background:rgba(255,255,255,.06)}#ia2 .ia2-menu div.on{background:rgba(255,255,255,.1)}#ia2 .ia2-menu i{width:14px;height:14px;border-radius:50%;flex-shrink:0}#ia2 .ia2-menu small{display:block;font-weight:500;color:#8b93a7;font-size:11px}',
    '#ia2 .ia2-hud{width:min(760px,100%);border-radius:22px;padding:18px 22px;background:linear-gradient(180deg,rgba(14,12,30,.86),rgba(8,8,18,.78));border:1px solid var(--ab);box-shadow:0 0 50px var(--ag),inset 0 1px 0 rgba(255,255,255,.06);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}',
    '#ia2 .ia2-hr{display:flex;justify-content:space-between;align-items:flex-end;gap:16px}#ia2 .ia2-hr span{font-size:12px;color:#94a3b8;font-weight:700}#ia2 .ia2-hr b{display:block;font:700 30px "Space Mono",ui-monospace,monospace;margin-top:2px}#ia2 .ia2-hr .r{text-align:right}',
    '#ia2 .ia2-bolas{display:flex;gap:4px;margin-top:6px;min-height:9px}#ia2 .ia2-bolas i{width:9px;height:9px;border-radius:50%}',
    '#ia2 .ia2-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:16px 0 8px}#ia2 .ia2-steps i{height:7px;border-radius:5px;background:rgba(255,255,255,.08);position:relative;overflow:hidden}',
    '#ia2 .ia2-steps i.ok{background:var(--a);box-shadow:0 0 12px var(--a)}#ia2 .ia2-steps i.run::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent,var(--a),transparent);animation:ia2sw 1s linear infinite}@keyframes ia2sw{from{transform:translateX(-100%)}to{transform:translateX(100%)}}',
    '#ia2 .ia2-steps.win i{background:#4ade80;box-shadow:0 0 12px #4ade80}#ia2 .ia2-steps.loss i{background:#f87171;box-shadow:0 0 12px #f87171}',
    '#ia2 .ia2-stxt{text-align:center;font-size:14px;font-weight:700;color:#e2e8f0;min-height:20px}#ia2 .ia2-stxt small{display:block;font-weight:500;color:#8b93a7;font-size:11.5px;margin-top:2px}',
    '#ia2 .ia2-btns{display:flex;gap:10px;justify-content:center;margin-top:12px;flex-wrap:wrap}',
    '#ia2 .ia2-b{border:0;border-radius:12px;padding:11px 20px;font:900 13px Inter,system-ui,sans-serif;letter-spacing:1px;cursor:pointer;display:flex;align-items:center;gap:8px}',
    '#ia2 .ia2-b.ia2-stop{background:linear-gradient(135deg,#dc2626,#f97316);color:#fff;box-shadow:0 8px 24px rgba(239,68,68,.3)}#ia2 .ia2-b.ia2-go{background:linear-gradient(135deg,var(--a),#6366f1);color:#fff}',
    '#ia2 .ia2-b.ia2-ghost{background:rgba(255,255,255,.06);color:#e2e8f0;border:1px solid rgba(255,255,255,.14)}',
    '#ia2 .ia2-spin{width:14px;height:14px;border-radius:50%;border:2px solid rgba(255,255,255,.35);border-top-color:#fff;animation:ia2rt .8s linear infinite}@keyframes ia2rt{to{transform:rotate(360deg)}}',
    '#ia2 .ia2-stage{position:relative;width:min(520px,92vw);aspect-ratio:1;margin:-8px 0 -26px;pointer-events:none}#ia2 .ia2-stage canvas{width:100%;height:100%;display:block}',
    '#ia2 .ia2-cfg{width:min(760px,100%);display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:12px}#ia2 .ia2-cfg div{border-radius:12px;padding:8px 10px;background:rgba(0,0,0,.55);border:1px solid rgba(255,255,255,.08)}',
    '#ia2 .ia2-cfg span{display:block;font-size:9.5px;font-weight:800;letter-spacing:1px;color:#7c84a0;text-transform:uppercase}#ia2 .ia2-cfg b{font:700 14px "Space Mono",ui-monospace,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}',
    '#ia2 .ia2-lst{width:min(980px,100%)}#ia2 .ia2-lh{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:8px;flex-wrap:wrap}',
    '#ia2 .ia2-cnt{display:flex;gap:10px;align-items:center;border-radius:12px;padding:9px 14px;background:rgba(0,0,0,.6);border:1px solid rgba(255,255,255,.08);font-size:13px;font-weight:700;flex-wrap:wrap}#ia2 .ia2-cnt .w{color:#4ade80}#ia2 .ia2-cnt .l{color:#f87171}',
    '#ia2 .ia2-flt{display:flex;border-radius:12px;padding:3px;background:rgba(0,0,0,.6);border:1px solid rgba(255,255,255,.08)}#ia2 .ia2-flt b{padding:7px 12px;border-radius:9px;font-size:11.5px;color:#94a3b8;cursor:pointer}#ia2 .ia2-flt b.on{background:rgba(255,255,255,.1);color:#fff}',
    '#ia2 .ia2-tr{display:grid;grid-template-columns:90px 1.2fr 1fr .8fr .8fr;gap:12px;align-items:center;border-radius:14px;padding:11px 16px;margin-bottom:7px;background:rgba(10,10,22,.82);border:1px solid rgba(255,255,255,.07)}',
    '#ia2 .ia2-tr.novo{animation:ia2in .5s ease}@keyframes ia2in{from{opacity:0;transform:translateY(-8px)}}',
    '#ia2 .ia2-tr small{display:block;font-size:10.5px;color:#7c84a0}#ia2 .ia2-tr b{font-size:13.5px}#ia2 .ia2-tr .w{color:#4ade80}#ia2 .ia2-tr .l{color:#f87171}',
    '#ia2 .ia2-tr.win{border-left:3px solid #4ade80}#ia2 .ia2-tr.loss{border-left:3px solid #f87171}',
    '#ia2 .ia2-vazio{text-align:center;color:#6f7790;font-size:13px;padding:22px;border-radius:14px;background:rgba(10,10,22,.7);border:1px dashed rgba(255,255,255,.1)}',
    '@media (max-width:760px){#ia2 .ia2-app{padding:12px 12px 26px}#ia2 .ia2-top .ia2-sp{flex-basis:100%;height:0}#ia2 .ia2-brand h1{font-size:19px}#ia2 .ia2-pill{padding:6px 10px;font-size:10px}#ia2 .ia2-ib{width:34px;height:34px}',
    '#ia2 .ia2-hud{background:rgba(8,8,18,.95);padding:16px}#ia2 .ia2-hr{flex-wrap:wrap}#ia2 .ia2-hr .r{text-align:left}#ia2 .ia2-hr b{font-size:22px}#ia2 .ia2-cfg{grid-template-columns:repeat(3,1fr)}#ia2 .ia2-tr{grid-template-columns:1fr 1fr;row-gap:6px}}'
  ].join('\n');
  document.head.appendChild(css);

  /* ───────────────────────── tela ───────────────────────── */
  var R = {};
  function montar() {
    var d = document.createElement('div'); d.id = 'ia2';
    d.innerHTML = '<canvas id="ia2Bg"></canvas><div class="ia2-app">' +
      '<div class="ia2-top"><div class="ia2-brand"><svg viewBox="0 0 48 48" fill="none" stroke="currentColor"><circle cx="24" cy="24" r="20" stroke-width="1.5" opacity=".5"/><path d="M24 6v8M24 34v8M6 24h8M34 24h8" stroke-width="2"/><circle cx="24" cy="24" r="7" stroke-width="2.5"/><circle cx="24" cy="24" r="2.5" fill="currentColor"/></svg><div><h1>IA <b>ALPHA</b></h1><small data-r="bot">IA AVANÇADO</small></div></div>' +
      '<div class="ia2-sp"></div><div class="ia2-pill" data-r="pill"><i></i><span>MOTOR PARADO</span></div><div class="ia2-conta" data-r="conta">DEMO</div>' +
      '<button class="ia2-ib" data-r="som" style="display:none" title="Som de vitória">🔊</button>' +
      '<div class="ia2-tema"><button class="ia2-ib" data-r="tm" title="Escolher visual">🎨</button><div class="ia2-menu">' +
      '<div data-o="nucleo"><i style="background:#8b5cf6"></i><span>Núcleo Quântico<small>cristal 3D roxo</small></span></div>' +
      '<div data-o="esfera"><i style="background:#22d3ee"></i><span>Esfera de Dígitos<small>globo de números ciano</small></span></div>' +
      '<div data-o="reator"><i style="background:#ec4899"></i><span>Reator Alpha<small>anéis de energia rosa</small></span></div></div></div>' +
      '<button class="ia2-ib" data-r="cfgb" title="Voltar às configurações do robô">⚙</button><button class="ia2-ib x" data-r="x" title="Fechar">✕</button></div>' +
      '<div class="ia2-hud"><div class="ia2-hr"><div><span>Lucro da sessão</span><b data-r="lucro">+$0.00</b><div class="ia2-bolas" data-r="bolas"></div></div><div class="r"><span data-r="sl">Saldo</span><b data-r="saldo">—</b></div></div>' +
      '<div class="ia2-steps" data-r="steps"><i></i><i></i><i></i><i></i></div><div class="ia2-stxt" data-r="stxt"></div>' +
      '<div class="ia2-btns"><button class="ia2-b ia2-stop" data-r="stop"><span class="ia2-spin"></span>PARAR IA</button><button class="ia2-b ia2-ghost" data-r="voltar">⚙ AJUSTAR</button></div></div>' +
      '<div class="ia2-stage"><canvas id="ia2Core"></canvas></div>' +
      '<div class="ia2-cfg"><div><span>Mercado</span><b data-r="cm">—</b></div><div><span>Contrato</span><b data-r="cc">—</b></div><div><span>Entrada</span><b data-r="ce">—</b></div><div><span>Meta</span><b data-r="ct">—</b></div><div><span>Stop</span><b data-r="cs">—</b></div></div>' +
      '<div class="ia2-lst"><div class="ia2-lh"><div class="ia2-cnt">Ganhos/Perdas <span class="w" data-r="nw">0</span><span class="l" data-r="nl">0</span><span style="color:#8b93a7;font-weight:600">· acerto <b data-r="wr">—</b></span></div>' +
      '<div class="ia2-flt" data-r="flt"><b data-f="todos" class="on">TODOS</b><b data-f="ganhos">GANHOS</b><b data-f="perdas">PERDAS</b></div></div><div data-r="trs"></div></div></div>';
    document.body.appendChild(d); R.root = d;
    d.querySelectorAll('[data-r]').forEach(function (e) { R[e.getAttribute('data-r')] = e; });
    R.tm.onclick = function (ev) { ev.stopPropagation(); R.tm.parentNode.classList.toggle('aberto'); };
    d.addEventListener('click', function () { R.tm.parentNode.classList.remove('aberto'); });
    d.querySelectorAll('.ia2-menu div[data-o]').forEach(function (b) { b.onclick = function () { OPT = b.getAttribute('data-o'); ls('ia_alpha_visual', OPT); tema(); }; });
    R.flt.querySelectorAll('b').forEach(function (b) { b.onclick = function () { filtro = b.getAttribute('data-f'); R.flt.querySelectorAll('b').forEach(function (x) { x.classList.toggle('on', x === b); }); ultHash = ''; atualizar(); }; });
    R.x.onclick = fechar; R.cfgb.onclick = fechar; R.voltar.onclick = fechar;
    R.som.onclick = function () { somOn = !somOn; ls('ia_alpha_som', somOn ? '1' : '0'); R.som.classList.toggle('off', !somOn); R.som.textContent = somOn ? '🔊' : '🔇'; };
    R.som.classList.toggle('off', !somOn); R.som.textContent = somOn ? '🔊' : '🔇';
    R.stop.onclick = function () { var b = fonte().btn(); if (b) b.click(); else fechar(); };
    tema(); desenho();
  }
  function tema() {
    var t = T[OPT]; if (!R.root) return;
    R.root.style.setProperty('--a', t[0]); R.root.style.setProperty('--ab', t[1]); R.root.style.setProperty('--ag', t[2]);
    R.root.querySelectorAll('.ia2-menu div[data-o]').forEach(function (x) { x.classList.toggle('on', x.getAttribute('data-o') === OPT); });
  }

  /* ─────────── som de vitória ─────────── */
  var somOn = ls('ia_alpha_som') !== '0', audio = null;
  function tocar() { if (!somOn) return; try { if (!audio) { audio = new Audio('/sounds/cash-register.mp3'); audio.volume = .8; } audio.currentTime = 0; audio.play().catch(function () {}); } catch (e) {} }

  /* ─────────── de onde vêm os dados (robô que abriu o IA Alpha) ─────────── */
  function texto(id) { return (($(id) || {}).textContent || '').trim(); }
  function valor(id) { return (($(id) || {}).value || ''); }
  function optTxt(id) { var s = $(id); if (s && s.options && s.selectedIndex >= 0) return s.options[s.selectedIndex].text; return texto(id); }
  function linhasFeed(id) { var f = $(id); return f ? Array.prototype.map.call(f.children, function (c) { return (c.textContent || '').replace(/\s+/g, ' ').trim(); }) : []; }
  var FONTES = {
    pro: {
      nome: 'IA PRO',
      st: function () { var s = window._proState || {}; return { run: !!s.running, esp: !!s.waiting, lucro: (+s.lucro || 0) - (+s.perda || 0), stake: +s.stakeAtual || +s.stake || 0, mult: +s.mult || 0, score: num(texto('proScore')), tipo: texto('proTipo') || valor('proContractType') }; },
      saldo: function () { return texto('proSaldoBox'); },
      conta: function () { return /real/i.test((window._proState || {}).contaTipo || ls('deriv_conta_ativa') || '') ? 'real' : 'demo'; },
      cfg: function () { return { m: optTxt('proSymbol'), c: valor('proContractType').replace('DIGIT', '') || '—', t: valor('proTarget'), s: valor('proStop') }; },
      btn: function () { return $('proStartBtn'); },
      trades: function () { // linhas do feed: "📤 Entrada: DIGITEVEN | $0.35" e depois "✅ WIN +$0.33" / "❌ LOSS -$0.35"
        var out = [], ent = null;
        linhasFeed('proFeed').forEach(function (l) {
          var h = (l.match(/\[(\d\d:\d\d:\d\d)\]/) || [])[1] || '';
          if (/Entrada:/i.test(l)) { ent = { tipo: ((l.match(/Entrada:\s*([A-Z]+)/i) || [])[1] || '').replace('DIGIT', ''), stake: num((l.split('|')[1]) || '') }; return; }
          var w = /✅|\bWIN\b/i.test(l), lo = /❌|\bLOSS\b/i.test(l); if ((!w && !lo) || /virtual/i.test(l)) return;
          var v = num((l.match(/[+\-−]\s*\$\s*[\d.,]+/) || [])[0]); if (v === null) return;
          out.push({ h: h, win: w, v: w ? Math.abs(v) : -Math.abs(v), tipo: ent ? ent.tipo : '', stake: ent ? ent.stake : null, merc: optTxt('proSymbol') }); ent = null;
        });
        return out;
      }
    },
    avancado: {
      nome: 'IA AVANÇADO',
      st: function () { var s = window._iaAdv || {}; var lt = texto('advLucroEspelho').replace(/\(.*$/, ''); return { run: !!s.running, esp: !!s.tradeEmAndamento, lucro: num(lt) || 0, stake: +s.stakeAtual || 0, mult: +s.mult || 0, score: null, tipo: (valor('advContractType') || s.contractType || '').replace('DIGIT', '') }; },
      saldo: function () { return texto('advSaldoEspelho').replace(/^saldo:\s*/i, ''); },
      conta: function () { return /real/i.test(ls('deriv_conta_ativa') || '') ? 'real' : 'demo'; },
      cfg: function () { return { m: texto('advSelectedMarket') || '—', c: (valor('advContractType') || '').replace('DIGIT', '') || '—', t: valor('advTarget'), s: valor('advStop') }; },
      btn: function () { return $('advStartBtn'); },
      trades: function () { // "[09:06:09] ✅ +$0.28 CALL"
        var out = [];
        linhasFeed('advMiniFeed').forEach(function (l) {
          var w = /✅/.test(l), lo = /❌/.test(l); if (!w && !lo) return;
          var v = num((l.match(/[+\-−]\s*\$\s*[\d.,]+/) || [])[0]); if (v === null) return;
          out.push({ h: (l.match(/(\d\d:\d\d:\d\d)/) || [])[1] || '', win: w, v: w ? Math.abs(v) : -Math.abs(v), tipo: ((l.match(/\b(CALL|PUT|RISE|FALL|DIGIT\w+|EVEN|ODD|OVER|UNDER|MATCH|DIFF)\b/i) || [])[1] || '').replace(/^CALL$/i, 'RISE').replace(/^PUT$/i, 'FALL').replace('DIGIT', ''), stake: null, merc: texto('advSelectedMarket') });
        });
        return out.reverse(); // o mini-feed já vem do mais novo para o mais velho
      }
    },
    ctx: {
      nome: 'IA CONTEXTUAL',
      st: function () { var s = window._ctxState || {}; var sp = ($('ctxStatusText') || document.createElement('i')).querySelectorAll('span'); return { run: !!s.running, esp: !!s.waiting, lucro: (+s.lucro || 0) - (+s.perda || 0), stake: +s.stakeAtual || 0, mult: +s.mult || 0, score: sp[1] ? num(sp[1].textContent) : null, tipo: valor('ctxTipo').replace('CALL/PUT', 'Rise/Fall') }; },
      saldo: function () { var s = window._ctxState || {}; return texto(s.conta === 'real' ? 'ctxSaldoRealVal' : 'ctxSaldoDemoVal'); },
      conta: function () { return (window._ctxState || {}).conta === 'real' ? 'real' : 'demo'; },
      cfg: function () { return { m: optTxt('ctxMercado'), c: optTxt('ctxTipo'), t: valor('ctxLucroAlvo'), s: valor('ctxStopLoss') }; },
      btn: function () { return $('ctxStartBtn'); },
      trades: function () {
        var s = window._ctxState || {};
        return (s.historico || []).map(function (h) { var w = /WIN/i.test(h.resultado || h.dir || ''); return { h: h.hora || '', win: w, v: w ? Math.abs(+h.profit || 0) : -Math.abs(+h.profit || 0), tipo: '', stake: null, merc: optTxt('ctxMercado'), score: h.score }; });
      }
    }
  };
  /* robôs de página própria (Touch, Sinais, Gráfico...) se registram em window.__alphaBot */
  FONTES.pagina = {
    get nome() { return (window.__alphaBot && window.__alphaBot.nome) || 'ALPHA'; },
    st: function () { return window.__alphaBot.st(); }, saldo: function () { return window.__alphaBot.saldo(); },
    conta: function () { return window.__alphaBot.conta(); }, cfg: function () { return window.__alphaBot.cfg(); },
    btn: function () { return window.__alphaBot.btn(); }, trades: function () { return window.__alphaBot.trades(); }
  };
  /* Alpha Esquadrão: lido direto da página (4 unidades) */
  function esqRodando(n) { var b = $('btnToggle-unidade-' + n); return !!b && /parar/i.test(b.textContent || ''); }
  FONTES.esquadrao = {
    nome: 'ALPHA ESQUADRÃO',
    st: function () { var l = 0, run = false, stk = 0; for (var n = 1; n <= 4; n++) { l += num(texto('lucro-unidade-' + n)) || 0; if (esqRodando(n)) { run = true; stk += num(texto('runningStake-unidade-' + n)) || 0; } } return { run: run, esp: (num(texto('statExposto')) || 0) > 0, lucro: l, stake: stk, mult: 0, score: null, tipo: 'Multi' }; },
    saldo: function () { return texto('saldoValor'); },
    conta: function () { var r = $('btnReal'); return r && /e2-sel|active|on\b/.test(r.className) ? 'real' : (/real/i.test(ls('deriv_conta_ativa') || '') ? 'real' : 'demo'); },
    cfg: function () { var a = 0; for (var n = 1; n <= 4; n++) if (esqRodando(n)) a++; return { m: a + ' unidade(s)', c: 'Esquadrão', t: '', s: '' }; },
    btn: function () { return { click: function () { var algum = false; for (var n = 1; n <= 4; n++) if (esqRodando(n)) { algum = true; $('btnToggle-unidade-' + n).click(); } if (!algum) { var i = 0; for (var k = 1; k <= 4; k++) (function (k) { setTimeout(function () { if (!esqRodando(k)) $('btnToggle-unidade-' + k).click(); }, 900 * i++); })(k); } } }; },
    trades: function () {
      var out = []; linhasFeed('logMovimentacao').forEach(function (l) {
        var v = num((l.match(/[+\-−]\s*\$\s*[\d.,]+/) || [])[0]); if (v === null || v === 0) return;
        var w = /✅|ganh|win/i.test(l) || (!/❌|perd|loss/i.test(l) && /\+\s*\$/.test(l));
        out.push({ h: (l.match(/(\d\d:\d\d(:\d\d)?)/) || [])[1] || '', win: w, v: w ? Math.abs(v) : -Math.abs(v), tipo: ((l.match(/unidade[\s-]*\d/i) || [])[0] || '').replace(/unidade[\s-]*/i, 'U'), stake: null, merc: ((l.match(/Volatility[^·|]*|Boom \d+|Crash \d+|Step Index/i) || [])[0] || '').trim() });
      });
      return out.reverse();
    }
  };
  /* IA Simples: operações vêm da lista que a tela da IA Simples já busca na Deriv (profit_table) */
  function iasMerc(t) { return ((String(t.longcode || '').match(/(Volatility \d+ \(1s\) Index|Volatility \d+ Index|Boom \d+ Index|Crash \d+ Index|Step Index|Jump \d+ Index)/i) || [])[1] || t.underlying || t.display_name || ''); }
  FONTES.simples = {
    nome: 'IA SIMPLES',
    st: function () { var O = window.__iasOps || { fechadas: [], abertas: {} }, l = 0; O.fechadas.forEach(function (t) { l += (+t.sell_price || 0) - (+t.buy_price || 0); });
      return { run: vis($('botRunningModal')), esp: Object.keys(O.abertas || {}).length > 0, lucro: Math.round(l * 100) / 100, stake: num(texto('iaAlphaStake')) || 0, mult: 0, score: num(texto('iaAlphaScore')), tipo: texto('iaAlphaTipo') }; },
    saldo: function () { return texto('iaAlphaSaldo'); },
    conta: function () { return /real/i.test(ls('deriv_conta_ativa') || '') ? 'real' : 'demo'; },
    cfg: function () { var O = window.__iasOps || { fechadas: [] }; return { m: O.fechadas[0] ? iasMerc(O.fechadas[0]) : '—', c: texto('iaAlphaTipo') || '—', t: '', s: '' }; },
    btn: function () { return vis($('botRunningModal')) ? $('stopBotBtn') : null; },
    trades: function () {
      var O = window.__iasOps || { fechadas: [] };
      return O.fechadas.slice().reverse().map(function (t) {
        var v = Math.round(((+t.sell_price || 0) - (+t.buy_price || 0)) * 100) / 100, d = new Date((+t.purchase_time || 0) * 1000);
        return { h: isNaN(d) ? '' : d.toTimeString().slice(0, 8), win: v > 0, v: v, tipo: typeof window.__iasTipo === 'function' ? window.__iasTipo(t) : '', stake: +t.buy_price || null, merc: iasMerc(t) };
      });
    }
  };
  /* Enxame: lido da página (resultado total, log ao vivo, Parar Tudo) */
  function linhasDom(id) { var f = $(id); return f ? Array.prototype.map.call(f.children, function (c) { return { t: (c.textContent || '').replace(/\s+/g, ' ').trim(), c: String(c.className || '') + ' ' + String((c.firstElementChild || {}).className || '') }; }) : []; }
  FONTES.enxame = {
    nome: 'ALPHA ENXAME',
    st: function () { return { run: vis($('telaRodando')), esp: false, lucro: num(texto('statResultadoTotal')) || 0, stake: 0, mult: 0, score: null, tipo: 'Enxame' }; },
    saldo: function () { return texto('statSaldoConta') || texto('saldoEnxameConfig'); },
    conta: function () { var r = $('btnEnxameReal'); return r && /ativ|active|\bon\b|sel/.test(r.className) ? 'real' : (/real/i.test(ls('deriv_conta_ativa') || '') ? 'real' : 'demo'); },
    cfg: function () { return { m: (texto('statAtivas') || '—') + ' unid.', c: 'Enxame', t: valor('inputMetaLucro'), s: valor('inputLimitePerda') }; },
    btn: function () {
      if (!vis($('telaRodando'))) return null;
      return { click: function () { var b = $('btnPararTudo'); if (b) b.click(); setTimeout(function () { var ok = document.querySelector('#confirmarPararOverlay .aviso-btn'); if (ok) ok.click(); }, 150); } };
    },
    trades: function () {
      var out = [];
      linhasDom('feedLista').forEach(function (r) {
        var l = r.t; if (/aguardando/i.test(l)) return;
        var v = num((l.match(/[+\-−]\s*\$\s*[\d.,]+/) || [])[0]); if (v === null) return;
        var w = /won|win|vit|ganh/i.test(r.c) || /✅|🏆|vit[oó]ria/i.test(l) || (!/lost|loss|derr|perd/i.test(r.c + l) && /\+\s*\$/.test(l));
        out.push({ h: (l.match(/(\d\d:\d\d(:\d\d)?)/) || [])[1] || '', win: w, v: w ? Math.abs(v) : -Math.abs(v), tipo: ((l.match(/unidade\s*\d+|U\d+/i) || [])[0] || '').replace(/unidade\s*/i, 'U'), stake: null, merc: ((l.match(/Volatility[^·|]*?(Index|\))|Boom \d+|Crash \d+|Step Index|\b(R_\d+|1HZ\d+V)\b/i) || [])[0] || '').trim() });
      });
      return out.reverse();
    }
  };
  function fonte() { return FONTES[ORIG] || FONTES.avancado; }
  function descobrirOrigem(arg) {
    if (arg === 'pro') return 'pro';
    if (vis($('alphaCtxIaModal'))) return 'ctx';
    if (vis($('alphaIaProModal'))) return 'pro';
    if (vis($('iaAvancadoModal'))) return 'avancado';
    if (vis($('botRunningModal')) && window.__iasOps) return 'simples';
    if (window.__alphaBot) return 'pagina';
    if ($('card-unidade-1') && $('logMovimentacao')) return 'esquadrao';
    if ($('feedLista') && $('btnPararTudo') && $('telaRodando')) return 'enxame';
    if (window._ctxState && window._ctxState.running) return 'ctx';
    if (window._proState && window._proState.running) return 'pro';
    if (window._iaAdv && window._iaAdv.running) return 'avancado';
    return null;
  }

  /* ─────────── abrir / fechar ─────────── */
  function abrir(arg) {
    var o = descobrirOrigem(arg); if (!o) return false; ORIG = o;
    if (!R.root) montar();
    R.bot.textContent = fonte().nome;
    R.root.classList.add('on'); aberto = true;
    var m = $('iaAlphaModal'); if (m) m.classList.add('ia2-esc');
    document.documentElement.style.overflow = 'hidden';
    ultN = -1; ultHash = ''; atualizar();
  }
  function fechar() {
    aberto = false; if (R.root) R.root.classList.remove('on');
    document.documentElement.style.overflow = '';
    var m = $('iaAlphaModal'); if (m) m.classList.remove('ia2-esc');
    try { if (typeof window.fecharModalIaAlpha === 'function') window.fecharModalIaAlpha(); } catch (e) {}
  }
  (function () {
    var n = 0, iv = setInterval(function () {
      var f = window.abrirModalIaAlpha; if (++n > 120) clearInterval(iv);
      if (typeof f !== 'function' || f.__ia2) return; clearInterval(iv);
      var w = function (o) { var origemTela = descobrirOrigem(o); var r = f.apply(this, arguments); abrir(o === 'pro' ? 'pro' : origemTela); return r; };
      w.__ia2 = true; window.abrirModalIaAlpha = w;
    }, 500);
    // se o modal antigo abrir por outro caminho, abre a tela nova também
    setInterval(function () { var m = $('iaAlphaModal'); if (m && m.classList.contains('show') && !aberto && !m.__ia2nao) { if (abrir(window._iaAlphaOrigem) === false) m.__ia2nao = true; } if (m && !m.classList.contains('show')) m.__ia2nao = false; }, 400);
    // páginas sem o IA Alpha antigo (Touch, Sinais, Gráfico, Esquadrão...): cria a função e um botão flutuante
    setTimeout(function () {
      if ($('iaAlphaModal')) return;
      if (typeof window.abrirModalIaAlpha !== 'function') window.abrirModalIaAlpha = function (o) { abrir(o); };
      if (!descobrirOrigem()) { var tent = 0, iv2 = setInterval(function () { if (++tent > 20) clearInterval(iv2); if (descobrirOrigem() && !$('ia2Lancar')) { clearInterval(iv2); criar(); } }, 1000); return; }
      criar(); }, 1500);
    function criar() {
      if (!document.querySelector('link[href*="Orbitron"]')) { var lk = document.createElement('link'); lk.rel = 'stylesheet'; lk.href = 'https://fonts.googleapis.com/css2?family=Orbitron:wght@800;900&display=swap'; document.head.appendChild(lk); }
      var bt = document.createElement('button'); bt.id = 'ia2Lancar'; bt.type = 'button'; bt.innerHTML = '<span>✨</span> IA ALPHA';
      bt.onclick = function () { abrir(); }; document.body.appendChild(bt);
    }
  })();

  /* ─────────── atualização ─────────── */
  var filtro = 'todos', ultN = -1, ultHash = '', resAte = 0, resWin = false, ultLista = [];
  function atualizar() {
    if (!aberto) return;
    var F = fonte(), s = F.st(), lista = F.trades(), n = lista.length, w = lista.filter(function (t) { return t.win; }).length;
    // lucro: o do robô; se ele não tiver, soma das operações
    var lucro = s.lucro || lista.reduce(function (a, t) { return a + t.v; }, 0);
    R.lucro.textContent = m$(lucro); R.lucro.style.color = lucro > 0 ? '#4ade80' : lucro < 0 ? '#f87171' : '#e2e8f0';
    R.bolas.innerHTML = lista.slice(-12).map(function (t) { return '<i style="background:' + (t.win ? '#4ade80' : '#f87171') + '"></i>'; }).join('');
    var conta = F.conta(); R.sl.textContent = conta === 'real' ? 'Saldo real' : 'Saldo demo'; R.conta.textContent = conta === 'real' ? 'REAL' : 'DEMO'; R.conta.classList.toggle('real', conta === 'real');
    var sd = F.saldo(); R.saldo.textContent = sd ? (/\$/.test(sd) ? sd : '$' + sd) : (texto('iaAlphaSaldo') || '—');
    R.pill.classList.toggle('on', s.run); R.pill.querySelector('span').textContent = s.run ? 'MOTOR ATIVO' : 'MOTOR PARADO';
    R.stop.innerHTML = s.run ? '<span class="ia2-spin"></span>PARAR IA' : '▶ INICIAR IA'; R.stop.className = 'ia2-b ' + (s.run ? 'ia2-stop' : 'ia2-go');
    var c = F.cfg(); R.cm.textContent = (c.m || '—').replace(' Index', ''); R.cc.textContent = c.c || s.tipo || '—'; R.ce.textContent = s.stake ? '$' + s.stake.toFixed(2) : '—';
    R.ct.textContent = c.t ? '$' + (+String(c.t).replace(',', '.')).toFixed(2) : '—'; R.cs.textContent = c.s ? '$' + (+String(c.s).replace(',', '.')).toFixed(2) : '—';
    R.nw.textContent = w; R.nl.textContent = n - w; R.wr.textContent = n ? Math.round(w / n * 100) + '%' : '—';
    if (s.score !== null && s.score !== undefined && !isNaN(s.score)) score = Math.round(s.score);
    // operação nova: flash, etapa "Resultado" e som
    if (ultN >= 0 && n > ultN) { var u = lista[n - 1]; resAte = Date.now() + 3000; resWin = u.win; flash = 1; /* SOM-UNICO-V1: o proprio robo ja toca o som do ganho */ }
    ultN = n;
    // etapas
    var st = R.steps, its = st.children, ag = Date.now();
    st.className = 'ia2-steps';
    if (ag < resAte) { st.classList.add(resWin ? 'win' : 'loss'); var u2 = lista[n - 1]; R.stxt.innerHTML = (resWin ? '✅ Ganhou ' : '❌ Perdeu ') + m$(u2 ? u2.v : 0) + '<small>próxima entrada ' + (s.stake ? '$' + s.stake.toFixed(2) : '—') + '</small>'; for (var i = 0; i < 4; i++) its[i].className = ''; }
    else {
      var e = !s.run ? -1 : s.esp ? 2 : (s.score !== null && s.score !== undefined && !isNaN(s.score) && s.score >= 60 ? 1 : 0);
      for (var k = 0; k < 4; k++) its[k].className = e < 0 ? '' : k < e ? 'ok' : k === e ? 'run' : '';
      R.stxt.innerHTML = e < 0 ? 'Robô parado<small>clique em Iniciar IA ou ajuste as configurações</small>' : e === 2 ? 'Contrato comprado<small>aguardando o resultado</small>' : e === 1 ? 'Sinal confirmado<small>confiança ' + Math.round(s.score) + '%</small>' : 'Analisando mercado<small>lendo os últimos ticks</small>';
    }
    // lista (só redesenha quando muda)
    var hash = filtro + '|' + n + '|' + (n ? lista[n - 1].h + lista[n - 1].v : '');
    if (hash !== ultHash) {
      var novo = ultHash && ultHash.split('|')[1] !== String(n); ultHash = hash;
      var v = lista.slice().reverse().filter(function (t) { return filtro === 'todos' || (filtro === 'ganhos' ? t.win : !t.win); }).slice(0, 80);
      var hoje = new Date().toLocaleDateString('pt-BR').slice(0, 5), ct = conta === 'real' ? 'Real' : 'Demo';
      R.trs.innerHTML = v.length ? v.map(function (t, i) {
        return '<div class="ia2-tr ' + (t.win ? 'win' : 'loss') + (novo && i === 0 ? ' novo' : '') + '"><div><small>' + hoje + '</small><b>' + (t.h || '—') + '</b></div>' +
          '<div><small>Mercado</small><b>' + (t.merc || '—').replace(' Index', '') + '</b></div>' +
          '<div><small>' + ct + (t.stake ? ' · entrada $' + (+t.stake).toFixed(2) : '') + '</small><b class="' + (t.win ? 'w' : 'l') + '">' + (t.win ? 'Ganho ' : 'Perda ') + m$(t.v) + '</b></div>' +
          '<div><small>Tipo</small><b>' + (t.tipo ? (/[▲▼]/.test(t.tipo) ? '' : /RISE|CALL/i.test(t.tipo) ? '▲ ' : /FALL|PUT/i.test(t.tipo) ? '▼ ' : '') + t.tipo : '—') + '</b></div>' +
          '<div><small>' + (t.score ? 'Confiança' : 'Resultado') + '</small><b>' + (t.score ? Math.round(t.score) + '%' : (t.win ? 'WIN' : 'LOSS')) + '</b></div></div>';
      }).join('') : '<div class="ia2-vazio">' + (filtro === 'todos' ? 'Nenhuma operação ainda nesta sessão — elas aparecem aqui assim que o robô operar.' : 'Nenhuma operação neste filtro.') + '</div>';
    }
  }
  setInterval(function () { try { atualizar(); } catch (e) { console.warn('[ia-alpha-v2]', e); } }, 700);
  setInterval(function () { if (aberto) { dig = Math.floor(Math.random() * 10); var ds = (window._proState && window._proState.digits) || []; if (ORIG === 'pro' && ds.length) dig = +ds[ds.length - 1] || 0; flash = Math.max(flash, .3); } }, 1000);

  /* ─────────── desenho (fundo de circuito + os 3 visuais) ─────────── */
  var flash = 0, dig = 7;
  function desenho() {
    var D=Math.min(devicePixelRatio||1,2),t=0;
    function rgb(h,a){var n=parseInt(h.slice(1),16);return 'rgba('+(n>>16)+','+(n>>8&255)+','+(n&255)+','+a+')'}
    /* fundo: placa de circuito com pulsos */
    var bg=document.getElementById('ia2Bg'),bx=bg.getContext('2d'),W,H,TR=[];
    function fitBg(){W=innerWidth;H=innerHeight;bg.width=W*D;bg.height=H*D;bx.setTransform(D,0,0,D,0,0);TR=[];var cx=W/2,cy=H*.48;
     for(var i=0;i<70;i++){var a=Math.random()*6.283,r=120+Math.random()*90,x=cx+Math.cos(a)*r,y=cy+Math.sin(a)*r,p=[[x,y]],dir=Math.abs(Math.cos(a))>Math.abs(Math.sin(a))?0:1;
      for(var k=0;k<4;k++){var L=60+Math.random()*180;if(dir==0)x+=Math.sign(Math.cos(a))*L;else y+=Math.sign(Math.sin(a))*L;p.push([x,y]);dir=1-dir}TR.push({p:p,o:Math.random()*10,v:.5+Math.random()})}}
    function drawBg(c){bx.clearRect(0,0,W,H);var g=bx.createRadialGradient(W/2,H*.48,0,W/2,H*.48,Math.max(W,H)*.6);g.addColorStop(0,rgb(c,.16));g.addColorStop(1,'rgba(0,0,0,0)');bx.fillStyle=g;bx.fillRect(0,0,W,H);
     bx.strokeStyle='rgba(255,255,255,.025)';bx.lineWidth=1;for(var x=0;x<W;x+=40){bx.beginPath();bx.moveTo(x,0);bx.lineTo(x,H);bx.stroke()}for(var y=0;y<H;y+=40){bx.beginPath();bx.moveTo(0,y);bx.lineTo(W,y);bx.stroke()}
     TR.forEach(function(r){bx.strokeStyle=rgb(c,.16+flash*.25);bx.lineWidth=1.4;bx.beginPath();r.p.forEach(function(q,i){i?bx.lineTo(q[0],q[1]):bx.moveTo(q[0],q[1])});bx.stroke();
      var e=r.p[r.p.length-1];bx.fillStyle=rgb(c,.5);bx.beginPath();bx.arc(e[0],e[1],2.5,0,7);bx.fill();
      var tot=0,seg=[];for(var i=1;i<r.p.length;i++){var l=Math.hypot(r.p[i][0]-r.p[i-1][0],r.p[i][1]-r.p[i-1][1]);seg.push(l);tot+=l}
      var d=((t*60*r.v+r.o*80)%(tot+200));if(d<tot){for(var i=0;i<seg.length;i++){if(d<=seg[i]){var f=d/seg[i],px=r.p[i][0]+(r.p[i+1][0]-r.p[i][0])*f,py=r.p[i][1]+(r.p[i+1][1]-r.p[i][1])*f;bx.fillStyle='#fff';bx.shadowColor=c;bx.shadowBlur=14;bx.beginPath();bx.arc(px,py,2.2,0,7);bx.fill();bx.shadowBlur=0;break}d-=seg[i]}}});
     var v=bx.createRadialGradient(W/2,H/2,Math.min(W,H)*.3,W/2,H/2,Math.max(W,H)*.75);v.addColorStop(0,'rgba(4,5,10,0)');v.addColorStop(1,'rgba(4,5,10,.85)');bx.fillStyle=v;bx.fillRect(0,0,W,H)}
    /* centro */
    var cv=document.getElementById('ia2Core'),x=cv.getContext('2d'),S;
    function fit(){S=cv.clientWidth;cv.width=S*D;cv.height=S*D;x.setTransform(D,0,0,D,0,0)}
    var ph=(1+Math.sqrt(5))/2,V=[[-1,ph,0],[1,ph,0],[-1,-ph,0],[1,-ph,0],[0,-1,ph],[0,1,ph],[0,-1,-ph],[0,1,-ph],[ph,0,-1],[ph,0,1],[-ph,0,-1],[-ph,0,1]],E=[];
    for(var i=0;i<12;i++)for(var j=i+1;j<12;j++){var d=Math.hypot(V[i][0]-V[j][0],V[i][1]-V[j][1],V[i][2]-V[j][2]);if(d<2.1)E.push([i,j])}
    var lit=V.map(function(){return 0});
    var SP=[];for(var i=0;i<260;i++){var y=1-i/259*2,r=Math.sqrt(1-y*y),a=i*2.39996;SP.push({x:Math.cos(a)*r,y:y,z:Math.sin(a)*r,d:Math.floor(Math.random()*10)})}
    var RING=[[.92,48,.25],[.76,36,-.4],[.6,24,.7],[.44,12,-1.1]],RL=RING.map(function(r){return new Array(r[1]).fill(0)});
    function rot(p,ay,ax){var c=Math.cos(ay),s=Math.sin(ay),X=p[0]*c-p[2]*s,Z=p[0]*s+p[2]*c,c2=Math.cos(ax),s2=Math.sin(ax),Y=p[1]*c2-Z*s2;Z=p[1]*s2+Z*c2;return[X,Y,Z]}
    function nucleo(c){var R=S*.26,cx=S/2,cy=S/2,ay=t*.5,ax=.35+Math.sin(t*.3)*.2;
     for(var k=0;k<3;k++){x.strokeStyle=rgb(c,.12+k*.06);x.lineWidth=1;x.setLineDash(k==1?[4,8]:[]);x.beginPath();x.arc(cx,cy,R*(1.45+k*.18),t*(k%2?-.3:.2),t*(k%2?-.3:.2)+5.5);x.stroke()}x.setLineDash([]);
     var P=V.map(function(v){var q=rot(v,ay,ax),f=1/(1+q[2]*.12);return[cx+q[0]*R*.55*f,cy+q[1]*R*.55*f,q[2]]});
     E.forEach(function(e){var a=P[e[0]],b=P[e[1]],z=(a[2]+b[2])/2,al=.25+(z+1.7)/3.4*.5,l=Math.max(lit[e[0]],lit[e[1]]);x.strokeStyle=l>.1?'rgba(255,255,255,'+(al+l*.4)+')':rgb(c,al);x.lineWidth=1.2+l*2;x.beginPath();x.moveTo(a[0],a[1]);x.lineTo(b[0],b[1]);x.stroke()});
     P.forEach(function(p,i){lit[i]*=.95;var r2=3+lit[i]*6;x.fillStyle=lit[i]>.1?'#fff':rgb(c,.9);x.shadowColor=c;x.shadowBlur=10+lit[i]*25;x.beginPath();x.arc(p[0],p[1],r2,0,7);x.fill();x.shadowBlur=0});
     if(Math.random()<.06)lit[Math.floor(Math.random()*12)]=1;
     var g=x.createRadialGradient(cx,cy,0,cx,cy,R*.5);g.addColorStop(0,rgb(c,.55+flash*.4));g.addColorStop(1,'rgba(0,0,0,0)');x.fillStyle=g;x.beginPath();x.arc(cx,cy,R*.5,0,7);x.fill();
     for(var k=0;k<24;k++){var a=k/24*6.283+t*.15,on=(Math.floor(t*6)+k)%8<2;x.strokeStyle=on?rgb(c,.9):rgb(c,.15);x.lineWidth=3;x.beginPath();x.arc(cx,cy,R*1.25,a,a+.17);x.stroke()}}
    function esfera(c){var R=S*.33,cx=S/2,cy=S/2,ay=t*.35,ax=.25;
     x.strokeStyle=rgb(c,.18);x.lineWidth=1;x.beginPath();x.ellipse(cx,cy,R*1.12,R*.3,0,0,7);x.stroke();x.beginPath();x.ellipse(cx,cy,R*1.12,R*.3,0,Math.sin(t)*0,7);x.stroke();
     var P=SP.map(function(p){var q=rot([p.x,p.y,p.z],ay,ax);return{x:cx+q[0]*R,y:cy+q[1]*R,z:q[2],d:p.d}}).sort(function(a,b){return a.z-b.z});
     x.textAlign='center';x.textBaseline='middle';
     P.forEach(function(p){var al=.15+(p.z+1)/2*.6,on=p.d===dig,sz=9+(p.z+1)*4;x.font='700 '+sz+'px Space Mono,monospace';if(on){x.fillStyle='rgba(255,255,255,'+(.5+flash*.5)+')';x.shadowColor=c;x.shadowBlur=14}else{x.fillStyle=rgb(c,al*.8);x.shadowBlur=0}x.fillText(p.d,p.x,p.y)});x.shadowBlur=0;
     x.font='900 '+S*.16+'px Orbitron,Inter,sans-serif';x.fillStyle='#fff';x.shadowColor=c;x.shadowBlur=30;x.fillText(dig,cx,cy+4);x.shadowBlur=0;
     x.font='800 11px Inter,sans-serif';x.fillStyle=rgb(c,.9);x.fillText('ÚLTIMO DÍGITO',cx,cy+S*.11)}
    function reator(c){var cx=S/2,cy=S/2,R=S*.46;
     RING.forEach(function(r,k){var n=r[1],a0=t*r[2],w=6.283/n;for(var i=0;i<n;i++){RL[k][i]*=.93;var a=a0+i*w,on=RL[k][i];x.strokeStyle=on>.08?'rgba(255,255,255,'+(.3+on*.7)+')':rgb(c,.18+.1*(k%2));x.lineWidth=k==0?5:k==3?10:7;if(on>.08){x.shadowColor=c;x.shadowBlur=18*on}x.beginPath();x.arc(cx,cy,R*r[0],a+w*.12,a+w*.88);x.stroke();x.shadowBlur=0}
      var idx=Math.floor((t*(3+k*2))%n);RL[k][idx]=1});
     for(var i=0;i<6;i++){var a=i/6*6.283+t*.2;x.strokeStyle=rgb(c,.25);x.lineWidth=1;x.beginPath();x.moveTo(cx+Math.cos(a)*R*.2,cy+Math.sin(a)*R*.2);x.lineTo(cx+Math.cos(a)*R*.95,cy+Math.sin(a)*R*.95);x.stroke()}
     x.beginPath();for(var i=0;i<6;i++){var a=i/6*6.283+Math.PI/6;x.lineTo(cx+Math.cos(a)*R*.3,cy+Math.sin(a)*R*.3)}x.closePath();var g=x.createRadialGradient(cx,cy,0,cx,cy,R*.3);g.addColorStop(0,rgb(c,.5+flash*.4));g.addColorStop(1,'rgba(10,8,20,.9)');x.fillStyle=g;x.fill();x.strokeStyle=c;x.lineWidth=2;x.shadowColor=c;x.shadowBlur=20;x.stroke();x.shadowBlur=0;
     x.textAlign='center';x.textBaseline='middle';x.font='900 '+S*.085+'px Orbitron,Inter,sans-serif';x.fillStyle='#fff';x.fillText(score?score+'%':'IA',cx,cy-4);x.font='800 10px Inter,sans-serif';x.fillStyle=rgb(c,.95);x.fillText(score?'CONFIANÇA':'ALPHA',cx,cy+S*.05)}
    function frame() {
      requestAnimationFrame(frame);
      if (!aberto || document.hidden) return;
      if (S !== cv.clientWidth) fit();
      t += .016; flash *= .94; var c = T[OPT][0]; drawBg(c); x.clearRect(0, 0, S, S);
      if (OPT === 'nucleo') nucleo(c); else if (OPT === 'esfera') esfera(c); else reator(c);
    }
    fitBg(); fit(); addEventListener('resize', function () { fitBg(); fit(); }); frame();
  }
})();
