/* ROBO-EXTRA-V1 (v10: data-conf-dif = robô com modo Differs além do normal (Mapa de Dígitos: Difere rápido) · v9: confirmação própria do Differs (descansar N / logo depois que sair) e do Accumulator (N ticks no corredor) — data-conf-tipo · v7: okSym/ticks para robôs sem lista de ticks (IA Contextual), Rise/Fall Equal, barra volta para perto da entrada se a tela for remontada · v5: "Lado do robô" opcional nos robôs que trocam de lado sozinhos — data-lados · v4: a confirmação só conta resultados que saíram DEPOIS do último contrato fechado · v3: barra compacta + janela de ajustes; data-conf-alem) — 3 recursos iguais em todos os robôs:
   1) Entrada em % da banca (a entrada sobe quando a banca sobe e desce quando cai; fixa durante a recuperação)
   2) Confirmar antes de entrar: espera N resultados seguidos do OUTRO lado do contrato (Par espera ímpares, Over 4 espera 0 a 4, Sobe espera quedas…)
   3) Trava de lucro 30/40/60% da meta (só nos robôs que ainda não têm trava própria)
   O motor de cada robô chama:
     __extra.base(stakeDoCampo, seq)              -> entrada da vez (seq = nível de recuperação; 0 = ciclo novo)
     __extra.ok(ganha, digitos, precos, rf)       -> pode entrar agora? ganha = function(dígito) -> true se esse dígito ganha; rf = 'RISE'/'FALL' para Sobe/Desce
     __extra.okCt(contrato, barreira, digitos, precos)  -> o mesmo, a partir do tipo de contrato da Deriv (DIGITEVEN, DIGITOVER…)
     __extra.res(ganhou, valor, lucroSessao, meta) -> depois de cada resultado; devolve [tipo, título, texto] quando a trava encerra a sessão
   Nada disso muda a chance de cada entrada: muda o tamanho da entrada, o momento de entrar e quando parar. */
(function () {
  'use strict';
  if (window.__extra) return;
  var me = document.currentScript, PG = (me && me.getAttribute('data-pg')) || location.pathname.replace(/^\/|\.html$/g, '') || 'robo';
  var TEM_TRAVA = !!(me && me.getAttribute('data-trava-propria'));
  var TIPO = (me && me.getAttribute('data-conf-tipo')) || '';   /* v9: 'dif' (Differs) ou 'accu' (Accumulator): confirmação própria */
  var DIF2 = !!(me && me.getAttribute('data-conf-dif'));   /* v10: além da confirmação normal, tem um modo Differs */
  var SEM_CONF = !TIPO && !!(me && me.getAttribute('data-sem-conf'));   /* esquadrões: sem confirmação */
  var SEL = (me && me.getAttribute('data-stake')) || '#iStake';
  var APOS = me && me.getAttribute('data-apos');   /* bloco depois do qual a barra entra (opcional) */
  var ALEM = !!(me && me.getAttribute('data-conf-alem'));
  var LADOS = ((me && me.getAttribute('data-lados')) || '').split(',').filter(Boolean);   /* v5: lados que o robô aceita fixar (EVEN,ODD,OVER,UNDER,RISE,FALL) */
  var NOMES = { EVEN: 'Par', ODD: 'Ímpar', OVER: '5 a 9 (Acima de 4)', UNDER: '0 a 4 (Abaixo de 5)', RISE: 'Sobe', FALL: 'Desce' };   /* robôs de padrão ("depois do dígito X"): conta os resultados ANTES do dígito do padrão */
  var K = 'extra_' + PG;
  function lsG(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsS(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function f$(v) { return '$' + (+v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  var C = { pct: 0, max: 0, conf: 0, trava: 0, lado: '', dif: 0, acc: 0 };
  try { var g = JSON.parse(lsG(K) || '{}'); ['pct', 'max', 'conf', 'trava', 'dif', 'acc'].forEach(function (k) { if (g[k] != null) C[k] = +g[k] || 0; }); if (typeof g.lado === 'string') C.lado = g.lado; } catch (e) {}
  var PL = { com: [0, 0], sem: [0, 0] };
  try { var h = JSON.parse(lsG(K + '_pl') || 'null'); if (h && h.com && h.sem) PL = h; } catch (e) {}
  function salva() { lsS(K, JSON.stringify(C)); lsS(K + '_pl', JSON.stringify(PL)); }
  var B = { saldo: null, cache: null, armada: false, sessPl: null, esp: null, espT: 0 };

  /* saldo: lido das mensagens de saldo que o próprio robô recebe da Deriv */
  (function () {
    var vis = new WeakSet(), o = WebSocket.prototype.send;
    WebSocket.prototype.send = function () {
      if (!vis.has(this) && this.addEventListener) { vis.add(this); this.addEventListener('message', function (ev) { try { var m = JSON.parse(ev.data); vigia(m); var v = (m.balance && m.balance.balance) != null ? m.balance.balance : (m.authorize && m.authorize.balance); if (v != null && isFinite(+v)) B.saldo = +v; } catch (e) {} }); }
      return o.apply(this, arguments);
    };
  })();
  /* v4: guarda os ticks de cada mercado (hora + dígito + preço) e a hora de saída do último contrato fechado */
  var TK = {}, SAIDA = null;
  function vigia(m) {
    if (m.msg_type === 'tick' && m.tick) {
      var t = m.tick, s = t.symbol || t.underlying_symbol, q = +t.quote; if (!s || !isFinite(q)) return;
      var a = TK[s] || (TK[s] = { ep: [], dg: [], px: [], n: 0 }), pip = typeof t.pip_size === 'number' ? t.pip_size : null;
      a.n++; a.ep.push(+t.epoch || Math.floor(Date.now() / 1000)); a.px.push(q); a.dg.push(pip != null ? Math.round(q * Math.pow(10, pip)) % 10 : null);
      if (a.ep.length > 60) { a.ep.shift(); a.px.shift(); a.dg.shift(); }
    }
    var p = m.proposal_open_contract;
    if (p && (p.is_sold || p.status === 'won' || p.status === 'lost')) {
      var ep = +p.exit_tick_time || +p.sell_spot_time || +p.sell_time || Math.floor(Date.now() / 1000);
      if (!SAIDA || ep >= SAIDA.ep) SAIDA = { ep: ep, s: p.underlying || p.underlying_symbol || null };
    }
  }
  function iguais(a, b, n) { if (!a || !b || a.length < n || b.length < n) return false; for (var i = 1; i <= n; i++) if (a[a.length - i] !== b[b.length - i]) return false; return true; }
  /* quantos ticks desse mercado saíram depois do último contrato fechado (Infinity = não sei / não limita) */
  function novos(dg, px) {
    if (!SAIDA) return Infinity;
    var s = null;
    for (var k in TK) { if ((px && px.length && iguais(TK[k].px, px, 3)) || (dg && dg.length && TK[k].dg[TK[k].dg.length - 1] != null && iguais(TK[k].dg, dg, 6))) { s = k; break; } }
    if (!s) s = SAIDA.s; var a = s && TK[s]; if (!a || !a.ep.length) return Infinity;
    var n = 0; for (var i = a.ep.length - 1; i >= 0 && a.ep[i] > SAIDA.ep; i--) n++;
    return n;
  }
  function confAtivo() { return TIPO === 'dif' ? !!C.dif : TIPO === 'accu' ? !!C.acc : !!C.conf; }
  function txConf() { return TIPO === 'dif' ? (C.dif < 0 ? 'logo depois que sair' : C.dif ? 'descansar ' + C.dif : 'na hora') : TIPO === 'accu' ? (C.acc ? C.acc + ' no corredor' : 'na hora') : (C.conf ? C.conf + ' do outro lado' : 'na hora'); }
  function banca() { if (B.saldo != null) return B.saldo; try { var s = window.__alphaBot && __alphaBot.saldo && __alphaBot.saldo(); if (isFinite(+s) && +s > 0) return +s; } catch (e) {} return null; }
  function entradaPct() { var b = banca(); if (!(b > 0)) return null; var x = Math.floor(b * C.pct) / 100; if (C.max > 0) x = Math.min(x, C.max); return Math.max(0.35, Math.round(x * 100) / 100); }

  function contraDe(ct, bar) {
    ct = String(ct || '').toUpperCase().replace('DIGIT', ''); var b = parseInt(bar, 10);
    if (ct === 'EVEN') return function (d) { return d % 2 === 0; };
    if (ct === 'ODD') return function (d) { return d % 2 === 1; };
    if (ct === 'OVER') { if (!isFinite(b)) b = 4; return function (d) { return d > b; }; }
    if (ct === 'UNDER') { if (!isFinite(b)) b = 5; return function (d) { return d < b; }; }
    return null;
  }
  function seguidosDig(ganha, dg) { var n = 0; for (var i = (dg || []).length - 1; i >= 0 && !ganha(dg[i]); i--) n++; return n; }
  function seguidosPx(rf, px) { var n = 0; px = px || []; for (var i = px.length - 1; i > 0; i--) { var d = px[i] - px[i - 1]; if (d === 0) break; if ((rf === 'RISE' && d < 0) || (rf === 'FALL' && d > 0)) n++; else break; } return n; }

  window.__extra = {
    base: function (b, seq) {
      if (!C.pct) { B.cache = null; return b; }
      if (seq && B.cache != null) return B.cache;
      var x = entradaPct(); if (x == null) return b;
      B.cache = x; pinta(); return x;
    },
    ok: function (ganha, dg, px, rf) {
      if (SEM_CONF || !C.conf) return true;
      var lim = novos(dg, px);   /* v4: o resultado do contrato que acabou de fechar não conta como confirmação */
      if (ALEM) { dg = (dg || []).slice(0, -1); px = (px || []).slice(0, -1); lim = lim - 1; }
      var k = rf ? seguidosPx(rf, px) : (ganha ? seguidosDig(ganha, dg) : C.conf);
      if (k > lim) k = Math.max(0, lim);
      if (k >= C.conf) { B.esp = null; B.okT = Date.now(); pintaSt(); return true; }
      B.esp = { k: k, txt: rf ? (rf === 'RISE' ? 'quedas' : 'altas') : (function () { var o = []; for (var d = 0; d < 10; d++) if (!ganha(d)) o.push(d); return o.length === 5 && o[0] === 1 && o[4] === 9 ? 'ímpares' : o.length === 5 && o[0] === 0 && o[4] === 8 ? 'pares' : o.length ? 'de ' + o[0] + ' a ' + o[o.length - 1] : ''; })() };
      B.espT = Date.now(); pintaSt(); return false;
    },
    okCt: function (ct, bar, dg, px) {
      var s = String(ct || '').toUpperCase().replace(/^(CALL|PUT)E$/, '$1');   /* v7: Rise/Fall Equal */
      if (s === 'CALL' || s === 'RISE') return this.ok(null, dg, px, 'RISE');
      if (s === 'PUT' || s === 'FALL') return this.ok(null, dg, px, 'FALL');
      var gh = contraDe(ct, bar); return gh ? this.ok(gh, dg, px) : true;
    },
    res: function (won, v, pl, meta) {
      try { var a = confAtivo() ? PL.com : PL.sem; a[1]++; if (won) a[0]++; salva(); } catch (e) {}
      if (Math.abs(pl - v) < 1e-6) B.armada = false;   /* primeiro resultado da sessão */
      pinta();
      if (TEM_TRAVA || !C.trava || !(meta > 0)) return null;
      if (B.armada && !won) { B.armada = false; return ['win', 'Trava de lucro', 'Passou de ' + C.trava + '% da meta e veio uma perda: a sessão parou com ' + f$(pl) + '.']; }
      if (!B.armada && pl >= meta * C.trava / 100 - 1e-9 && pl < meta - 1e-9) { B.armada = true; pinta(); }
      return null;
    },
    /* v9 Differs: n > 0 = o dígito proibido precisa ficar n ticks seguidos sem sair; -1 = entra no tick logo depois que ele sair (só conta tick novo, depois do último contrato) */
    okDif: function (dig, dg) {
      if ((TIPO !== 'dif' && !DIF2) || !C.dif) return true;
      dg = dg || []; var lim = novos(dg, null), d = +dig;
      if (C.dif < 0) { var ok = dg.length && dg[dg.length - 1] === d && lim >= 1; if (ok) { B.esp = null; B.okT = Date.now(); } else { B.esp = { msg: '🔎 Esperando sair o ' + d + ' para entrar no tick seguinte' }; B.espT = Date.now(); } pintaSt(); return !!ok; }
      var k = 0; for (var i = dg.length - 1; i >= 0 && dg[i] !== d; i--) k++; if (k > lim) k = lim;
      if (k >= C.dif) { B.esp = null; B.okT = Date.now(); pintaSt(); return true; }
      B.esp = { msg: '🔎 Esperando o ' + d + ' descansar: ' + k + '/' + C.dif + ' ticks sem sair' }; B.espT = Date.now(); pintaSt(); return false;
    },
    /* v9 Accumulator: os últimos N movimentos ficaram dentro do corredor (|Δ preço| < distância da parede) */
    okAccu: function (px, dist) {
      if (TIPO !== 'accu' || !C.acc || !(dist > 0)) return true;
      px = px || []; var lim = novos(null, px), k = 0;
      for (var i = px.length - 1; i > 0 && Math.abs(px[i] - px[i - 1]) < dist; i--) k++; if (k > lim) k = lim;
      if (k >= C.acc) { B.esp = null; B.okT = Date.now(); pintaSt(); return true; }
      B.esp = { msg: '🔎 Esperando ' + C.acc + ' ticks seguidos dentro do corredor (' + k + '/' + C.acc + ')' }; B.espT = Date.now(); pintaSt(); return false;
    },
    okSym: function (ct, bar, sym) { var a = TK[sym]; if (!a || !a.px.length) return !C.conf || SEM_CONF; return this.okCt(ct, bar, a.dg, a.px); },   /* v7: usa os ticks que o próprio módulo guardou */
    ticks: function (sym) { return TK[sym] ? TK[sym].n : 0; },
    lado: function () { return LADOS.indexOf(C.lado) >= 0 ? C.lado : null; },   /* v5: null = o robô decide pela leitura dele (como sempre) */
    zera: function () { B.armada = false; B.sessPl = null; B.cache = null; B.esp = null; pinta(); },
    cfg: C
  };

  /* ---------- barra compacta + janela de ajustes ---------- */
  function css() {
    var s = document.createElement('style');
    s.textContent =
      '#rxBar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;width:100%;flex-basis:100%;grid-column:1/-1;box-sizing:border-box;margin:0 0 10px;font-family:Inter,system-ui,sans-serif}' +
      '#rxOpen{display:inline-flex;align-items:center;gap:7px;flex-wrap:wrap;max-width:100%;border:1px solid rgba(94,234,212,.35);background:rgba(94,234,212,.07);color:#cbd5e1;border-radius:999px;padding:6px 12px;font:600 12px Inter,system-ui,sans-serif;cursor:pointer;text-align:left;line-height:1.3}' +
      '#rxOpen:hover{background:rgba(94,234,212,.14);border-color:#5eead4}#rxOpen b{color:#fff;font-weight:800}#rxOpen i{font-style:normal;color:#5eead4;font-weight:800}#rxOpen .sep{color:#475569}' +
      '#rxSt{font:700 11.5px Inter,system-ui,sans-serif;color:#fde68a;min-width:0}#rxSt.ok{color:#5eead4}#rxSt:empty{display:none}' +
      '#rxOv{position:fixed;inset:0;z-index:2147483000;background:rgba(2,4,10,.72);display:flex;align-items:center;justify-content:center;padding:16px;box-sizing:border-box}#rxOv[hidden]{display:none!important}' +
      '#rxBox{width:100%;max-width:440px;max-height:calc(100vh - 32px);overflow:auto;box-sizing:border-box;padding:16px 16px 14px;border:1px solid rgba(94,234,212,.3);border-radius:16px;background:#0b0f1a;box-shadow:0 20px 60px rgba(0,0,0,.6);font-family:Inter,system-ui,sans-serif;color:#cbd5e1;text-align:left}' +
      '#rxBox .hd{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}#rxBox .hd b{font:800 14px Inter,system-ui,sans-serif;color:#fff;letter-spacing:.02em}' +
      '#rxBox .x{border:0;background:rgba(248,113,113,.15);color:#fca5a5;width:30px;height:30px;border-radius:9px;font:800 15px Inter,system-ui,sans-serif;cursor:pointer;flex:0 0 auto}' +
      '#rxBox .pl{font:800 10.5px Inter,system-ui,sans-serif;letter-spacing:.12em;color:#a5aec6;text-transform:uppercase;margin:14px 0 7px}#rxBox .hd+.pl{margin-top:4px}' +
      '#rxBox .ch{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}#rxBox .ch button{border:1px solid rgba(148,163,184,.25);background:#060912;color:#cbd5e1;border-radius:10px;padding:9px 4px;font:800 12px Inter,system-ui,sans-serif;cursor:pointer;white-space:nowrap}' +
      '#rxBox .ch.c4{grid-template-columns:repeat(4,1fr)}#rxBox .ch.c2{grid-template-columns:repeat(2,1fr)}#rxBox .ch button.on{background:rgba(94,234,212,.16);border-color:#5eead4;color:#fff}' +
      '#rxBox label.mx{display:flex!important;flex-direction:row!important;align-items:center!important;justify-content:flex-start!important;gap:8px;margin:8px 0 0;letter-spacing:0!important;text-transform:none!important;width:auto!important;font:600 12px Inter,system-ui,sans-serif!important;color:#a5aec6!important}' +
      '#rxBox .mx input{width:90px;padding:7px 9px;border-radius:9px;border:1px solid rgba(148,163,184,.3);background:#06070d;color:#fff;font:700 13px ui-monospace,monospace}' +
      '#rxBox .tx{margin-top:7px;font:500 11.5px/1.45 Inter,system-ui,sans-serif;color:#94a3b8}#rxBox .tx b{color:#e2e8f0}' +
      '#rxBox .pc{margin-top:14px;padding:9px 10px;border-radius:10px;background:rgba(94,234,212,.06);font:600 11.5px/1.4 Inter,system-ui,sans-serif;color:#5eead4}' +
      '#rxBox .ok2{margin-top:14px;width:100%;border:0;border-radius:11px;padding:11px;background:#5eead4;color:#04201b;font:800 13px Inter,system-ui,sans-serif;cursor:pointer}' +
      '@media (max-width:640px){#rxOv{align-items:flex-end;padding:0}#rxBox{max-width:none;border-radius:18px 18px 0 0;max-height:88vh;padding-bottom:calc(14px + env(safe-area-inset-bottom,0px))}#rxOpen{font-size:11.5px;padding:7px 12px;width:100%;border-radius:12px}#rxOpen i{margin-left:auto}}';
    document.head.appendChild(s);
  }
  function chips(id, lista, val, cl) { return '<div class="ch ' + (cl || '') + '" id="' + id + '">' + lista.map(function (x) { return '<button type="button" data-v="' + x[0] + '"' + (+x[0] === val ? ' class="on"' : '') + '>' + x[1] + '</button>'; }).join('') + '</div>'; }
  /* onde a barra entra: antes da linha de campos que tem a entrada (ou depois de data-apos) */
  function lugar(inp) {
    if (APOS && inp.closest(APOS)) return [inp.closest(APOS), 'depois'];
    var e = inp, A = null;
    for (var n = 0; n < 8 && e.parentElement && e.parentElement !== document.body; n++) { e = e.parentElement; if (e.querySelectorAll('input,select').length >= 3) { A = e; break; } }
    if (!A) return [inp.parentElement, 'depois'];
    /* linha de campos (curta, lado a lado): a barra vai em cima dela, ocupando a largura toda */
    var cs = getComputedStyle(A);
    if (A.children.length >= 3 && /flex|grid/.test(cs.display) && A.getBoundingClientRect().height < 340) return [A, /grid/.test(cs.display) || cs.flexWrap === 'wrap' ? 'dentro' : 'antes'];
    /* coluna de campos: a barra vai logo depois do campo da entrada */
    var c = inp; while (c.parentElement !== A) c = c.parentElement;
    return [c, 'depois'];
  }
  function monta() {
    if (document.getElementById('rxBar')) return true;
    var inp = document.querySelector(SEL); if (!inp) return false;
    var bar = document.createElement('div'); bar.id = 'rxBar';
    bar.innerHTML = '<button type="button" id="rxOpen" title="Valor da entrada, confirmação e trava"></button><span id="rxSt"></span>';
    var L = lugar(inp);
    if (L[1] === 'dentro') L[0].insertBefore(bar, L[0].firstChild); else if (L[1] === 'antes') L[0].parentNode.insertBefore(bar, L[0]); else L[0].parentNode.insertBefore(bar, L[0].nextSibling);
    var ov = document.createElement('div'); ov.id = 'rxOv'; ov.hidden = true;
    ov.innerHTML = '<div id="rxBox" role="dialog" aria-label="Ajustes da entrada"><div class="hd"><b>⚙ Ajustes da entrada</b><button type="button" class="x" id="rxX" aria-label="Fechar">✕</button></div>' +
      '<div class="pl">Valor da entrada</div>' + chips('rxPct', [[0, '💲 Fixo'], [0.5, '0,5%'], [1, '1%'], [2, '2%'], [3, '3%'], [5, '5%']], C.pct) +
      '<label class="mx" id="rxMaxL">Entrada máxima $ <input id="rxMax" inputmode="decimal" placeholder="sem teto"></label><div class="tx" id="rxPctTx"></div>' +
      (TIPO === 'dif' ? '<div class="pl">Confirmar antes de entrar</div>' + chips('rxDif', [[0, 'Na hora'], [5, 'Descansar 5'], [10, 'Descansar 10'], [15, 'Descansar 15'], [-1, 'Logo depois que sair']], C.dif, 'c2') +
        '<div class="tx"><b>Descansar N</b>: só entra depois que o dígito proibido ficar N ticks seguidos sem sair. <b>Logo depois que sair</b>: espera o dígito proibido aparecer e entra no tick seguinte. Vale também para a recuperação (conta só os ticks depois da perda).</div><div class="st" id="rxSt"></div>' : '') +
      (TIPO === 'accu' ? '<div class="pl">Confirmar antes de entrar</div>' + chips('rxAcc', [[0, 'Na hora'], [2, '2 no corredor'], [3, '3 no corredor'], [5, '5 no corredor']], C.acc, 'c2') +
        '<div class="tx">Só entra depois que os últimos N ticks seguidos teriam ficado <b>dentro do corredor</b> (a distância da parede que a Deriv informa). Depois de tocar a parede, espera ticks novos de novo.</div><div class="st" id="rxSt"></div>' : '') +
      (DIF2 ? '<div class="pl">No modo Differs (Difere rápido)</div>' + chips('rxDif', [[0, 'Na hora'], [5, 'Descansar 5'], [10, 'Descansar 10'], [15, 'Descansar 15'], [-1, 'Logo depois que sair']], C.dif, 'c2') +
        '<div class="tx">No Differs não existe "outro lado". <b>Descansar N</b>: só entra depois que o dígito proibido ficar N ticks seguidos sem sair. <b>Logo depois que sair</b>: espera o proibido aparecer e entra no tick seguinte. A confirmação de baixo vale para o Manual e o Automático.</div>' : '') +
      (SEM_CONF || TIPO ? '' : '<div class="pl">Confirmar antes de entrar</div>' + chips('rxConf', [[0, 'Na hora'], [1, '1 do outro lado'], [2, '2 seguidos'], [3, '3 seguidos']], C.conf, 'c2') +
        '<div class="tx">Só entra depois de sair essa quantidade seguida do <b>outro lado</b> (Par espera ímpares, Over 4 espera 0 a 4, Sobe espera quedas). ' +
        (ALEM ? 'Aqui o sinal já vem "depois do dígito X": o robô confere os resultados <b>antes</b> desse dígito, e se não bater ele <b>pula o sinal</b>.' : 'Vale também para a recuperação.') + '</div>' +
        (LADOS.length ? '<div class="pl">Lado do robô</div><div class="ch c2" id="rxLado">' + [['', 'Pela leitura (como sempre)']].concat(LADOS.map(function (x) { return [x, NOMES[x] || x]; })).map(function (x) { return '<button type="button" data-l="' + x[0] + '">' + x[1] + '</button>'; }).join('') + '</div><div class="tx" id="rxLadoTx"></div>' : '')) +
      (TEM_TRAVA ? '' : '<div class="pl">Trava de lucro</div>' + chips('rxTr', [[0, 'Desligada'], [30, '30%'], [40, '40%'], [60, '60%']], C.trava, 'c4') + '<div class="tx">Quando o lucro passar dessa parte da meta, a próxima perda encerra a sessão para guardar o lucro.</div>') +
      '<div class="pc" id="rxPl"></div><button type="button" class="ok2" id="rxOk">Pronto</button></div>';
    document.body.appendChild(ov);
    function abre(v) { ov.hidden = !v; if (v) pinta(); }
    document.getElementById('rxOpen').onclick = function () { abre(true); };
    document.getElementById('rxX').onclick = document.getElementById('rxOk').onclick = function () { abre(false); };
    ov.addEventListener('click', function (e) { if (e.target === ov) abre(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !ov.hidden) abre(false); });
    function liga(id, k) { ov.querySelectorAll('#' + id + ' button').forEach(function (b) { b.onclick = function () { C[k] = +b.dataset.v; if (k === 'pct') B.cache = null; if (k === 'conf' || k === 'dif' || k === 'acc') { B.esp = null; B.okT = 0; } salva(); pinta(); }; }); }
    ov.querySelectorAll('#rxLado button').forEach(function (b) { b.onclick = function () { C.lado = b.dataset.l; B.esp = null; salva(); pinta(); }; });
    liga('rxPct', 'pct'); if (!SEM_CONF && !TIPO) liga('rxConf', 'conf'); if (TIPO === 'dif' || DIF2) liga('rxDif', 'dif'); if (TIPO === 'accu') liga('rxAcc', 'acc'); if (!TEM_TRAVA) liga('rxTr', 'trava');
    var mx = document.getElementById('rxMax'); mx.value = C.max ? String(C.max).replace('.', ',') : '';
    mx.oninput = function () { var v = parseFloat(String(mx.value).replace(',', '.')); C.max = isFinite(v) && v > 0 ? v : 0; salva(); pinta(); };
    return true;
  }
  function pintaSt() {
    var e = document.getElementById('rxSt'); if (!e) return;
    var t = '', ok = false;
    if ((TIPO || DIF2) && B.esp && B.esp.msg && Date.now() - B.espT < 4000) t = B.esp.msg;
    else if (TIPO && confAtivo() && B.okT && Date.now() - B.okT < 6000) { t = '✅ Confirmação batida (' + txConf() + ')'; ok = true; }
    else if (!SEM_CONF && !TIPO && C.conf && B.esp && Date.now() - B.espT < 4000) t = '🔎 Esperando ' + C.conf + ' ' + B.esp.txt + ' seguidos (' + Math.min(B.esp.k, C.conf) + '/' + C.conf + ')';
    else if (!SEM_CONF && !TIPO && C.conf && B.okT && Date.now() - B.okT < 6000) { t = '✅ Confirmação batida (' + C.conf + ' do outro lado)'; ok = true; }
    else if (B.armada) t = '🔒 Trava armada';
    e.textContent = t; e.className = ok ? 'ok' : '';
  }
  function p(a) { return a[1] ? Math.round(a[0] / a[1] * 100) + '% em ' + a[1] : 'sem entradas'; }
  function pinta() {
    var bt = document.getElementById('rxOpen'); if (!bt) return;
    var x = C.pct ? entradaPct() : null, sep = '<span class="sep">·</span>';
    bt.innerHTML = '⚙ <span>Entrada <b>' + (C.pct ? String(C.pct).replace('.', ',') + '%' + (x != null ? ' (' + f$(B.cache != null ? B.cache : x) + ')' : '') : 'fixa') + '</b></span>' +
      (SEM_CONF ? '' : sep + '<span>Confirmar <b>' + txConf() + '</b></span>') +
      (DIF2 ? sep + '<span>Differs <b>' + (C.dif < 0 ? 'logo depois que sair' : C.dif ? 'descansar ' + C.dif : 'na hora') + '</b></span>' : '') +
      (LADOS.indexOf(C.lado) >= 0 ? sep + '<span>Lado <b>' + (NOMES[C.lado] || C.lado) + '</b></span>' : '') +
      (TEM_TRAVA ? '' : sep + '<span>Trava <b>' + (C.trava ? C.trava + '%' : 'off') + '</b></span>') + sep + '<i>ajustar</i>';
    var inp = document.querySelector(SEL);
    if (inp) { inp.readOnly = !!C.pct; inp.style.opacity = C.pct ? '.7' : ''; inp.title = C.pct ? 'A entrada está em % da banca (⚙ Ajustes da entrada)' : ''; }
    var d = document.getElementById('rxBox');
    if (d) {
      [['rxPct', 'pct'], ['rxConf', 'conf'], ['rxTr', 'trava'], ['rxDif', 'dif'], ['rxAcc', 'acc']].forEach(function (y) { d.querySelectorAll('#' + y[0] + ' button').forEach(function (b) { b.classList.toggle('on', +b.dataset.v === C[y[1]]); }); });
      d.querySelectorAll('#rxLado button').forEach(function (b) { b.classList.toggle('on', b.dataset.l === (LADOS.indexOf(C.lado) >= 0 ? C.lado : '')); });
      var lt = document.getElementById('rxLadoTx');
      if (lt) lt.innerHTML = LADOS.indexOf(C.lado) >= 0 ? 'O robô só entra em <b>' + NOMES[C.lado] + '</b>' + (C.conf ? ', depois de sair ' + C.conf + ' seguido' + (C.conf > 1 ? 's' : '') + ' do outro lado' : ' (escolha também quantos esperar do outro lado)') + '. A leitura e o contrato lá embaixo ficam de lado enquanto isso estiver ligado.' : 'O robô escolhe o lado pela leitura dele, como sempre.' + (C.conf ? ' Como a leitura troca de lado a cada tick, a confirmação pode demorar: para ela funcionar melhor, escolha um lado fixo.' : '');
      document.getElementById('rxMaxL').style.display = C.pct ? '' : 'none';
      document.getElementById('rxPctTx').innerHTML = !C.pct ? 'Entrada fixa: usa o valor do campo de entrada.' : x == null ? 'Esperando o saldo da conta…' : 'Entrada agora: <b>' + f$(B.cache != null ? B.cache : x) + '</b> (' + String(C.pct).replace('.', ',') + '% de ' + f$(banca()) + (C.max ? ', teto ' + f$(C.max) : '') + '). Sobe quando a banca sobe, desce quando cai; fica igual durante a recuperação. Meta e limite de perda continuam em dólar.';
      document.getElementById('rxPl').textContent = SEM_CONF ? (B.armada ? '🔒 Trava armada' : 'A % vale a partir da próxima entrada nova.') : 'Seu acerto neste robô · com confirmação: ' + p(PL.com) + ' · na hora: ' + p(PL.sem) + '. Só vale comparar depois de algumas centenas de entradas.' + (B.armada ? ' · 🔒 trava armada' : '');
    }
    pintaSt();
  }
  function recoloca() {   /* v7: se a tela do robô foi remontada e a barra ficou escondida, põe de novo perto do campo de entrada */
    var bar = document.getElementById('rxBar'), inp = document.querySelector(SEL); if (!bar || !inp) return;
    if (bar.offsetParent !== null || inp.offsetParent === null) return;
    var L = lugar(inp); if (L[1] === 'dentro') L[0].insertBefore(bar, L[0].firstChild); else if (L[1] === 'antes') L[0].parentNode.insertBefore(bar, L[0]); else L[0].parentNode.insertBefore(bar, L[0].nextSibling);
  }
  function inicia() { css(); var n = 0; (function t() { if (monta()) { pinta(); setInterval(function () { recoloca(); pinta(); }, 3000); setInterval(pintaSt, 1000); setTimeout(recoloca, 1500); } else if (n++ < 40) setTimeout(t, 500); })(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inicia); else inicia();
})();
