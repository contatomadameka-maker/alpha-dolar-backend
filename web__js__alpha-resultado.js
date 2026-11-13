/* Alpha Dolar — janela de META BATIDA / STOP LOSS (IA Pro e IA Avançado)
 * Mesmo visual do Alpha Sinais. Não muda como o robô para: só embrulha proParar e iaAdvParar
 * para mostrar o resultado, e esconde janelas antigas de meta/stop que aparecerem junto.
 * Para desfazer: remover este arquivo da página.
 */
(function () {
  'use strict';
  if (window.AlphaResultado) return;
  var $ = function (id) { return document.getElementById(id); };
  function num(s) { var m = String(s == null ? '' : s).replace(/[$\s]/g, '').replace('−', '-').replace(',', '.').match(/-?\d+(\.\d+)?/); return m ? parseFloat(m[0]) : null; }
  function dinheiro(v) { return (v > 0 ? '+' : v < 0 ? '−' : '') + '$' + Math.abs(v).toFixed(2); }
  function duracao(ms) { var s = Math.max(0, Math.round(ms / 1000)); return s >= 3600 ? Math.floor(s / 3600) + 'h' + String(Math.floor(s % 3600 / 60)).padStart(2, '0') : Math.floor(s / 60) + 'm' + String(s % 60).padStart(2, '0') + 's'; }

  var css = document.createElement('style');
  css.textContent = [
    '.ar-ov{position:fixed;inset:0;z-index:2147483000;display:none;align-items:center;justify-content:center;padding:16px;background:rgba(3,5,12,.74);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);font-family:Inter,system-ui,sans-serif}',
    '.ar-ov.aberto{display:flex;animation:arFade .25s ease}@keyframes arFade{from{opacity:0}}@keyframes arPop{from{transform:scale(.9);opacity:0}}',
    '.ar-card{position:relative;overflow:hidden;width:100%;max-width:390px;border-radius:22px;padding:28px 24px 22px;text-align:center;animation:arPop .3s cubic-bezier(.2,.9,.3,1.2);box-sizing:border-box}',
    '.ar-card *{box-sizing:border-box}',
    '.ar-glow{position:absolute;top:-90px;left:50%;width:280px;height:280px;transform:translateX(-50%);pointer-events:none}',
    '.ar-ic{position:relative;width:74px;height:74px;margin:0 auto 14px;border-radius:50%;display:flex;align-items:center;justify-content:center}',
    '.ar-t{position:relative;font-size:23px;font-weight:900;color:#fff;letter-spacing:-.3px}',
    '.ar-s{position:relative;font-size:12px;font-weight:700;margin-top:4px}',
    '.ar-vb{position:relative;margin:16px 0 12px;padding:14px;border-radius:14px;background:rgba(0,0,0,.32);border:1px solid rgba(255,255,255,.08)}',
    '.ar-vl{font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#94a3b8}',
    '.ar-v{font-family:"Space Mono",ui-monospace,monospace;font-size:34px;font-weight:700;margin-top:4px}',
    '.ar-st{position:relative;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:12px}',
    '.ar-st div{padding:8px 4px;border-radius:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);display:flex;flex-direction:column;gap:2px}',
    '.ar-st b{font-family:"Space Mono",ui-monospace,monospace;font-size:15px;color:#fff}.ar-st span{font-size:10px;color:#94a3b8;font-weight:600}',
    '.ar-m{position:relative;font-size:12.5px;line-height:1.5;color:#cbd5e1;margin-bottom:16px}',
    '.ar-b{position:relative;width:100%;height:48px;border-radius:12px;border:none;font:900 14px Inter,system-ui,sans-serif;letter-spacing:.5px;color:#fff;cursor:pointer}',
    '.ar-card.stop{background:linear-gradient(165deg,#2a0f14 0%,#0b0709 100%);border:1px solid rgba(239,68,68,.45);box-shadow:0 0 60px rgba(239,68,68,.22)}',
    '.ar-card.stop .ar-glow{background:radial-gradient(circle,rgba(239,68,68,.35),transparent 70%)}',
    '.ar-card.stop .ar-ic{background:rgba(239,68,68,.14);border:1px solid rgba(239,68,68,.5);color:#f87171}',
    '.ar-card.stop .ar-s{color:#fca5a5}.ar-card.stop .ar-v{color:#f87171}',
    '.ar-card.stop .ar-b{background:linear-gradient(135deg,#dc2626,#ef4444);box-shadow:0 8px 22px rgba(239,68,68,.3)}',
    '.ar-card.win{background:linear-gradient(165deg,#0c2a1a 0%,#060c09 100%);border:1px solid rgba(34,197,94,.55);box-shadow:0 0 60px rgba(34,197,94,.25)}',
    '.ar-card.win .ar-glow{background:radial-gradient(circle,rgba(34,197,94,.4),transparent 70%)}',
    '.ar-card.win .ar-ic{background:rgba(34,197,94,.14);border:1px solid rgba(34,197,94,.55);color:#4ade80}',
    '.ar-card.win .ar-s{color:#86efac}.ar-card.win .ar-v{color:#4ade80}',
    '.ar-card.win .ar-b{background:linear-gradient(135deg,#16a34a,#22c55e);box-shadow:0 8px 22px rgba(34,197,94,.3)}'
  ].join('\n');
  document.head.appendChild(css);

  var ICON_WIN = '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/></svg>';
  var ICON_STOP = '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v6c0 4.5-3.4 8.2-8 9-4.6-.8-8-4.5-8-9V6zM12 8v5M12 16h.01"/></svg>';

  var ov = null;
  function montar() {
    if (ov) return ov;
    ov = document.createElement('div'); ov.className = 'ar-ov'; ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-modal', 'true');
    ov.innerHTML = '<div class="ar-card win"><div class="ar-glow"></div><div class="ar-ic"></div><div class="ar-t"></div><div class="ar-s"></div>' +
      '<div class="ar-vb"><div class="ar-vl"></div><div class="ar-v"></div></div>' +
      '<div class="ar-st"><div><b data-r="ops">0</b><span>operações</span></div><div><b data-r="wr">—</b><span>acerto</span></div><div><b data-r="dur">—</b><span>duração</span></div></div>' +
      '<div class="ar-m"></div><button class="ar-b" type="button">Continuar</button></div>';
    document.body.appendChild(ov);
    ov.addEventListener('click', function (e) { if (e.target === ov || e.target.classList.contains('ar-b')) ov.classList.remove('aberto'); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') ov.classList.remove('aberto'); });
    return ov;
  }

  /* janelas antigas de meta/stop que abrirem junto são escondidas (só as que aparecerem nos 3s seguintes) */
  function visiveisFixos() {
    return Array.prototype.slice.call(document.querySelectorAll('body *')).filter(function (e) {
      if (e === ov || (ov && ov.contains(e))) return false;
      var s = getComputedStyle(e); if (s.position !== 'fixed' || s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false;
      var r = e.getBoundingClientRect(); return r.width > 180 && r.height > 120;
    });
  }
  function abafar(antes) {
    var TXT = /meta (batida|atingida)|lucro alvo|take profit|stop loss|limite de perda|sess[aã]o encerrada|resultado da sess/i;
    [150, 600, 1500, 3000].forEach(function (ms) {
      setTimeout(function () {
        visiveisFixos().forEach(function (e) {
          if (antes.indexOf(e) >= 0) return;
          if (e.id === 'alphaIaProModal' || e.id === 'iaAvancadoModal' || e.closest('#alphaIaProModal .p2,#iaAvancadoModal .a2')) return;
          if (!TXT.test(e.textContent || '')) return;
          e.setAttribute('data-ar-escondido', '1'); e.style.setProperty('display', 'none', 'important');
        });
      }, ms);
    });
  }

  var TEXTOS = {
    win: { t: 'Meta batida!', s: 'Lucro alvo atingido', vl: 'Lucro da sessão', m: 'O robô parou sozinho para garantir o seu lucro. Bom momento para fazer uma pausa.', b: 'Continuar' },
    stop: { t: 'Stop loss atingido', s: 'Limite de perda', vl: 'Resultado da sessão', m: 'O robô parou automaticamente para proteger o seu capital. Revise a gestão antes de voltar.', b: 'Entendi' }
  };
  function show(o) {
    var el = montar(), T = TEXTOS[o.kind] || TEXTOS.win, c = el.firstChild;
    c.className = 'ar-card ' + (o.kind === 'stop' ? 'stop' : 'win');
    c.querySelector('.ar-ic').innerHTML = o.kind === 'stop' ? ICON_STOP : ICON_WIN;
    c.querySelector('.ar-t').textContent = o.titulo || T.t;
    c.querySelector('.ar-s').textContent = (o.bot ? o.bot + ' · ' : '') + (o.sub || T.s);
    c.querySelector('.ar-vl').textContent = T.vl;
    var ve = c.querySelector('.ar-v'); ve.textContent = dinheiro(+o.valor || 0); ve.style.color = (+o.valor || 0) > 0 ? '#4ade80' : (+o.valor || 0) < 0 ? '#f87171' : '#e2e8f0';
    c.querySelector('[data-r="ops"]').textContent = o.ops || 0;
    c.querySelector('[data-r="wr"]').textContent = o.ops ? Math.round((o.wins || 0) / o.ops * 100) + '%' : '—';
    c.querySelector('[data-r="dur"]').textContent = o.inicio ? duracao(Date.now() - o.inicio) : '—';
    c.querySelector('.ar-m').textContent = o.msg || T.m;
    c.querySelector('.ar-b').textContent = T.b;
    el.classList.add('aberto'); ultimoShow = Date.now();
  }
  window.AlphaResultado = { show: show };

  /* ── marca a hora de início de cada robô ── */
  var inicio = { pro: 0, adv: 0 }, estava = { pro: false, adv: false };
  setInterval(function () {
    var p = !!(window._proState && window._proState.running), a = !!(window._iaAdv && window._iaAdv.running);
    if (p && !estava.pro) inicio.pro = Date.now(); if (a && !estava.adv) inicio.adv = Date.now();
    if (estava.pro && !p) vigiarJanelaVelha('pro'); if (estava.adv && !a) vigiarJanelaVelha('adv');
    estava.pro = p; estava.adv = a;
  }, 500);

  /* plano B: se o robô parou por outro caminho e abriu a janela antiga, troca pela nova */
  var ultimoShow = 0;
  function vigiarJanelaVelha(bot) {
    var TXT_WIN = /meta (batida|atingida)|lucro alvo|take profit/i, TXT_STOP = /stop loss|limite de perda/i;
    [300, 1000, 2500, 5000].forEach(function (ms) {
      setTimeout(function () {
        if (Date.now() - ultimoShow < 6000) return;
        visiveisFixos().forEach(function (e) {
          if (Date.now() - ultimoShow < 6000) return;
          if (e.id === 'alphaIaProModal' || e.id === 'iaAvancadoModal' || e.querySelector('#alphaIaProModal,#iaAvancadoModal')) return;
          var t = e.textContent || '', k = TXT_WIN.test(t) ? 'win' : TXT_STOP.test(t) ? 'stop' : null; if (!k || t.length > 1500) return;
          e.setAttribute('data-ar-escondido', '1'); e.style.setProperty('display', 'none', 'important');
          if (bot === 'pro') { var s = window._proState || {}; show({ kind: k, bot: 'Alpha IA Pro', valor: (+s.lucro || 0) - (+s.perda || 0), ops: (+s.wins || 0) + (+s.losses || 0), wins: +s.wins || 0, inicio: inicio.pro }); }
          else { var tr = tradesAdv(), v = num((($('advLucroEspelho') || {}).textContent || '').replace(/\(.*$/, '')); show({ kind: k, bot: 'IA Avançado', valor: v === null ? (tr.soma || 0) : v, ops: tr.n, wins: tr.w, inicio: inicio.adv }); }
        });
      }, ms);
    });
  }

  /* ── IA Pro ── */
  function tipoDe(motivo) {
    var m = String(motivo || '').toLowerCase();
    if (/manual|usu[aá]rio|user|parad[oa] pelo/.test(m)) return null;
    if (/take|profit|lucro|meta|alvo|target|win/.test(m)) return 'win';
    if (/stop|loss|perda|limite/.test(m)) return 'stop';
    return null;
  }
  function embrulhar(nome, fn) {
    var n = 0, iv = setInterval(function () {
      var f = window[nome]; if (++n > 120) clearInterval(iv);
      if (typeof f !== 'function' || f.__ar) return; clearInterval(iv);
      var w = function () { var antes = visiveisFixos(), r = f.apply(this, arguments); try { fn(arguments[0], antes); } catch (e) { console.warn('[alpha-resultado]', e); } return r; };
      w.__ar = true; window[nome] = w;
    }, 500);
  }
  embrulhar('proParar', function (motivo, antes) {
    var k = tipoDe(motivo); if (!k) return;
    var s = window._proState || {}, ops = (+s.wins || 0) + (+s.losses || 0);
    show({ kind: k, bot: 'Alpha IA Pro', valor: (+s.lucro || 0) - (+s.perda || 0), ops: ops, wins: +s.wins || 0, inicio: inicio.pro });
    abafar(antes);
  });

  /* ── IA Avançado ── */
  function tradesAdv() {
    var h = (window._iaAdv && window._iaAdv.historico) || [], n = 0, w = 0, soma = 0, temValor = false;
    if (h.length && typeof h[0] === 'object') h.forEach(function (t) {
      var p = t.profit != null ? +t.profit : t.lucro != null ? +t.lucro : null;
      var ok = t.win === true || t.won === true || /won|win|ganh/i.test(String(t.result || t.status || t.resultado || '')) || (p !== null && p > 0);
      var ruim = t.win === false || /lost|loss|perd/i.test(String(t.result || t.status || t.resultado || '')) || (p !== null && p < 0);
      if (ok || ruim) { n++; if (ok) w++; } if (p !== null) { soma += p; temValor = true; }
    });
    if (!n) { var f = $('advMiniFeed'); if (f) Array.prototype.forEach.call(f.children, function (c) { var t = c.textContent || ''; if (/✅|WIN|GANHOU/i.test(t)) { n++; w++; } else if (/❌|LOSS|PERDEU/i.test(t)) n++; }); }
    return { n: n, w: w, soma: temValor ? soma : null };
  }
  embrulhar('iaAdvParar', function (motivo, antes) {
    var k = tipoDe(motivo); if (!k) return;
    // o servidor para o robô antes da tela receber a última operação: espera ela entrar na conta
    var ini = inicio.adv;
    setTimeout(function () {
      /* ADV-STOP-V1 */ var t = tradesAdv(), f = feedSessaoAdv(), lt = (($('advLucroEspelho') || {}).textContent || '').replace(/\(.*$/, ''), v = null;
      if (f && f.n) { v = f.soma; t = { n: f.n, w: f.w }; }
      if (v === null && t.soma != null) v = t.soma;
      if (v === null) v = num(lt);
      if (v === null) v = 0;
      show({ kind: k, bot: 'IA Avançado', valor: v, ops: t.n, wins: t.w, inicio: ini });
      if (k === 'stop') setTimeout(function () { motivoAdv(v, f); }, 30);
      abafar(antes);
    }, 3000);
  });

  /* ADV-STOP-V1: soma das operações da sessão atual, lida dos registros (depois do último "Iniciando") */
  function feedSessaoAdv() {
    var box = $('advMiniFeed'); if (!box || !box.children.length) return null;
    var L = Array.prototype.map.call(box.children, function (c) { return c.textContent || ''; });
    var primeiro = /iniciando/i.test(L[L.length - 1]) && !/iniciando/i.test(L[0]);   // lista com o mais novo em cima
    if (primeiro) L = L.slice().reverse();
    var n = 0, w = 0, soma = 0, seq = 0;
    L.forEach(function (t) {
      if (/iniciando/i.test(t)) { n = 0; w = 0; soma = 0; seq = 0; return; }
      var m = t.match(/([+\-−])\s*\$\s*([\d.,]+)/); if (!m) return;
      var val = parseFloat(m[2].replace(',', '.')); if (!isFinite(val)) return;
      if (m[1] === '+') { n++; w++; soma += val; seq = 0; } else { n++; soma -= val; seq++; }
    });
    return { n: n, w: w, soma: Math.round(soma * 100) / 100, seq: seq };
  }
  function motivoAdv(v, f) {
    var lim = parseFloat(String((($('advStop') || {}).value) || '0').replace(',', '.')) || 0;
    var tipo = String(window.selectedStopLossType || 'value'), maxl = parseInt(window.selectedMaxLosses, 10) || 0;
    var titulo = null, sub = null, msg = null;
    if ((tipo === 'sequence' || tipo === 'both') && f && maxl && f.seq >= maxl) {
      titulo = 'Parou por ' + f.seq + ' perdas seguidas'; sub = 'IA Avançado · Limite de perdas em sequência';
      msg = 'Você escolheu parar depois de ' + maxl + ' perdas seguidas. O resultado acima é o total da sessão.';
    } else if (lim && v > -lim + 0.01) {
      titulo = 'Proteção do limite'; sub = 'IA Avançado · Limite de perda $' + lim.toFixed(2);
      msg = 'A próxima entrada de recuperação passaria do seu limite de perda, então o robô parou antes. O resultado acima é o total da sessão.';
    }
    if (!titulo) return;
    var achou = 0;
    Array.prototype.forEach.call(document.querySelectorAll('body *'), function (e) {
      if (achou > 2 || e.children.length) return;
      var t = (e.textContent || '').trim();
      if (t === 'Stop loss atingido') { e.textContent = titulo; achou++; }
      else if (/^IA Avançado\s*·\s*Limite de perda$/.test(t)) { e.textContent = sub; achou++; }
      else if (/^O robô parou automaticamente para proteger o seu capital/.test(t)) { e.textContent = msg; achou++; }
    });
  }
})();
