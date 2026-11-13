/* IA-AVANCADO-JANELAS-V2: o IA Avançado tem as próprias janelas de Mercado e de Limite de perda
   (não usa mais as do IA Simples, que ficavam presas no painel da esquerda, atrás da tela cheia).
   A escolha grava no mesmo lugar que o robô já lê: selectMarketGlobal() e os campos stopLossType/stopLossSequence. */
(function () {
  function $(i) { return document.getElementById(i); }
  var MERC = [
    ['R_10', 'Volatility 10 Index', 'Volatilidade constante de 10% com um tique a cada 2 segundos'],
    ['R_25', 'Volatility 25 Index', 'Volatilidade constante de 25% com um tique a cada 2 segundos'],
    ['R_50', 'Volatility 50 Index', 'Volatilidade constante de 50% com um tique a cada 2 segundos'],
    ['R_75', 'Volatility 75 Index', 'Volatilidade constante de 75% com um tique a cada 2 segundos'],
    ['R_100', 'Volatility 100 Index', 'Volatilidade constante de 100% com um tique a cada 2 segundos'],
    ['1HZ10V', 'Volatility 10 (1s) Index', 'Volatilidade constante de 10% com um tique a cada segundo'],
    ['1HZ25V', 'Volatility 25 (1s) Index', 'Volatilidade constante de 25% com um tique a cada segundo'],
    ['1HZ50V', 'Volatility 50 (1s) Index', 'Volatilidade constante de 50% com um tique a cada segundo'],
    ['1HZ75V', 'Volatility 75 (1s) Index', 'Volatilidade constante de 75% com um tique a cada segundo'],
    ['1HZ100V', 'Volatility 100 (1s) Index', 'Volatilidade constante de 100% com um tique a cada segundo']
  ];
  var st = document.createElement('style');
  st.textContent =
    '#a2Jan{position:fixed;inset:0;z-index:100005;background:rgba(3,4,10,.72);backdrop-filter:blur(3px);display:none;align-items:center;justify-content:center;padding:16px;box-sizing:border-box}' +
    '#a2Jan.on{display:flex}' +
    '#a2Jan .cx{width:min(460px,100%);max-height:86vh;overflow:auto;background:#0b0d16;border:1px solid rgba(139,92,246,.45);border-radius:16px;box-shadow:0 24px 70px rgba(0,0,0,.7);color:#e8ecf4;font-family:Inter,system-ui,sans-serif}' +
    '#a2Jan .hd{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid rgba(255,255,255,.07);position:sticky;top:0;background:#0b0d16}' +
    '#a2Jan .hd b{font-size:15px}#a2Jan .hd button{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.4);color:#f87171;border-radius:8px;width:32px;height:32px;cursor:pointer;font-size:16px}' +
    '#a2Jan .gr{padding:8px 16px 4px;font-size:10px;letter-spacing:1px;color:#7c86a2;font-weight:800;text-transform:uppercase}' +
    '#a2Jan .it{display:flex;flex-direction:column;gap:2px;width:calc(100% - 20px);margin:4px 10px;text-align:left;padding:10px 12px;border-radius:10px;border:1px solid transparent;background:rgba(255,255,255,.03);color:#e8ecf4;cursor:pointer;font:inherit}' +
    '#a2Jan .it:hover{border-color:rgba(139,92,246,.5)}#a2Jan .it.on{border-color:#8b5cf6;background:rgba(139,92,246,.14)}#a2Jan .it b{font-size:13.5px}#a2Jan .it small{font-size:11px;color:#8b93ad}' +
    '#a2Jan .bd{padding:14px 16px;display:flex;flex-direction:column;gap:10px;font-size:13px}#a2Jan .bd p{margin:0;color:#9aa3bd;line-height:1.5}' +
    '#a2Jan select,#a2Jan input{background:#14161f;border:1px solid #2a2f45;border-radius:10px;color:#e8ecf4;font:15px inherit;padding:10px 12px;width:100%;box-sizing:border-box}' +
    '#a2Jan label{font-size:11px;letter-spacing:.8px;color:#8b93ad;font-weight:800;text-transform:uppercase}' +
    '#a2Jan .ok{margin:6px 16px 16px;width:calc(100% - 32px);padding:12px;border:0;border-radius:10px;background:linear-gradient(135deg,#8b5cf6,#ec4899);color:#fff;font-weight:800;cursor:pointer;font-size:14px}' +
    '#advRegraModal.a2-keep{position:fixed!important;left:50%!important;top:50%!important;right:auto!important;transform:translate(-50%,-50%)!important;' +
    'width:min(480px,92vw)!important;z-index:100002!important;padding:16px!important;border-radius:14px!important;box-shadow:0 24px 70px rgba(0,0,0,.65)!important;' +
    'background:#0d1117!important;border:1px solid rgba(139,92,246,.45)!important}' +
    '#advRegraModal.a2-keep select,#advRegraModal.a2-keep input{min-height:40px;font-size:15px}';
  (document.head || document.documentElement).appendChild(st);

  function janela() {
    var j = $('a2Jan'); if (j) return j;
    j = document.createElement('div'); j.id = 'a2Jan';
    j.addEventListener('click', function (e) { if (e.target === j) fechar(); });
    document.body.appendChild(j); return j;
  }
  function fechar() { var j = $('a2Jan'); if (j) { j.classList.remove('on'); j.innerHTML = ''; } }
  function cab(t) { return '<div class="hd"><b>' + t + '</b><button type="button" data-x="1">✕</button></div>'; }

  function abrirMercado() {
    var j = janela(), atual = window.selectedMarketSymbol || window.selectedSymbol || 'R_100';
    var h = cab('Selecione o mercado') + '<div class="gr">Índices de volatilidade</div>';
    MERC.forEach(function (m, i) {
      if (i === 5) h += '<div class="gr">Índices (1s) — um tique por segundo</div>';
      h += '<button type="button" class="it' + (m[0] === atual ? ' on' : '') + '" data-m="' + i + '"><b>' + m[1] + '</b><small>' + m[2] + '</small></button>';
    });
    j.innerHTML = '<div class="cx">' + h + '</div>'; j.classList.add('on');
    j.querySelector('[data-x]').onclick = fechar;
    [].forEach.call(j.querySelectorAll('[data-m]'), function (b) {
      b.onclick = function () {
        var m = MERC[+b.dataset.m], obj = { symbol: m[0], id: m[0], name: m[1], description: m[2] };
        try { if (typeof window.selectMarketGlobal === 'function') window.selectMarketGlobal(obj); } catch (e) { console.warn('[IA Avançado] mercado', e); }
        window.selectedMarketSymbol = m[0]; window.selectedSymbol = m[0]; window.selectedMarketName = m[1];
        var a = $('advSelectedMarket'), ah = $('advMarketHint'); if (a) a.textContent = m[1]; if (ah) ah.textContent = m[2];
        fechar();
      };
    });
  }

  function abrirLimite() {
    var j = janela(), tipo = ($('stopLossType') || {}).value || window.selectedStopLossType || 'value', seq = ($('stopLossSequence') || {}).value || 3;
    j.innerHTML = '<div class="cx">' + cab('Opções de limite de perda') +
      '<div class="bd"><p>Escolha se o robô para pelo valor do limite, por um número de perdas seguidas, ou pelos dois.</p>' +
      '<label>Tipo de limite</label><select id="a2SlTipo"><option value="value">Usar valor do limite</option><option value="sequence">Usar perdas em sequência</option><option value="both">Usar os dois</option></select>' +
      '<div id="a2SlSeqG"><label>Perdas em sequência</label><input id="a2SlSeq" type="number" min="1" max="20" step="1"></div></div>' +
      '<button type="button" class="ok" id="a2SlOk">Salvar</button></div>';
    j.classList.add('on');
    var s = $('a2SlTipo'), n = $('a2SlSeq'), g = $('a2SlSeqG');
    s.value = tipo; n.value = seq;
    function mostra() { g.style.display = s.value === 'value' ? 'none' : 'block'; }
    s.onchange = mostra; mostra();
    j.querySelector('[data-x]').onclick = fechar;
    $('a2SlOk').onclick = function () {
      var v = s.value, q = Math.max(1, Math.min(20, parseInt(n.value, 10) || 3));
      var os = $('stopLossType'), on = $('stopLossSequence');
      if (on) { on.value = q; on.dispatchEvent(new Event('input', { bubbles: true })); on.dispatchEvent(new Event('change', { bubbles: true })); }
      if (os) { os.value = v; os.dispatchEvent(new Event('change', { bubbles: true })); }
      try { if (typeof window.applyStopLossType === 'function') window.applyStopLossType(v); } catch (e) {}
      window.selectedStopLossType = v; window.selectedMaxLosses = q;
      fechar();
    };
  }

  // clique no Mercado / na engrenagem do Limite dentro do IA Avançado: usa as janelas próprias
  window.addEventListener('click', function (e) {
    var t = e.target; if (!t || !t.closest) return;
    var m = t.closest('#advMarketSelect'), g = t.closest('[onclick*="openAdvStopLossModal"]');
    if (!m && !g) return;
    e.preventDefault(); e.stopImmediatePropagation();
    if (m) abrirMercado(); else abrirLimite();
  }, true);
  window.addEventListener('keydown', function (e) { if (e.key === 'Escape') fechar(); });
})();

/* ADV-FECHAR-V1: ao fechar o IA Avançado a tela ficava como camada invisível (z 99999) por cima de tudo
   e roubava os cliques (ex.: botão Iniciar do IA Pro). Ao fechar, ela é escondida de verdade; ao abrir, volta. */
(function () {
  var st = document.createElement('style');
  st.textContent = '#iaAvancadoModal.a2-fechado{display:none!important;pointer-events:none!important}';
  (document.head || document.documentElement).appendChild(st);
  function m() { return document.getElementById('iaAvancadoModal'); }
  function fechou() { var e = m(); if (e) e.classList.add('a2-fechado'); }
  function abriu() { var e = m(); if (e) e.classList.remove('a2-fechado'); }
  var feitos = {};
  function embrulhar() {
    Object.keys(window).forEach(function (k) {
      if (feitos[k] || !/^(abrir|fechar|open|close|mostrar|esconder)(Modal)?(Ia|IA)?Avan[cç]ado(Modal)?$/i.test(k)) return;
      var f = window[k]; if (typeof f !== 'function' || f.__a2f) return;
      var tipo = /^(fechar|close|esconder)/i.test(k) ? 'f' : 'a';
      if (!tipo) return;
      var w = function () {
        if (tipo === 'a') abriu();
        var r = f.apply(this, arguments);
        if (tipo === 'f') setTimeout(fechou, 0);
        return r;
      };
      w.__a2f = 1; window[k] = w; feitos[k] = tipo;
    });
  }
  var n = 0; (function tenta() { embrulhar(); if (++n < 40) setTimeout(tenta, 500); else console.log('[ADV-FECHAR-V1] funcoes:', JSON.stringify(feitos)); })();
})();

/* ADV-TEMPO-REAL-V1: o valor "Sessão" do topo vinha do servidor e demorava alguns segundos.
   Agora é a soma das operações da sessão nos registros (mesma conta da janela de resultado), na hora. */
(function () {
  function $(i) { return document.getElementById(i); }
  function num(t) { var m = String(t || '').replace(/[^\d.,\-]/g, '').replace(',', '.'); var v = parseFloat(m); return isFinite(v) ? v : null; }
  function soma() {
    var box = $('advMiniFeed'); if (!box || !box.children.length) return null;
    var L = Array.prototype.map.call(box.children, function (c) { return c.textContent || ''; });
    if (/iniciando/i.test(L[L.length - 1]) && !/iniciando/i.test(L[0])) L = L.slice().reverse();
    var tem = false, s = 0, n = 0;
    L.forEach(function (t) {
      if (/iniciando/i.test(t)) { tem = true; s = 0; n = 0; return; }
      var m = t.match(/([+\-−])\s*\$\s*([\d.,]+)/); if (!m) return;
      var v = parseFloat(m[2].replace(',', '.')); if (!isFinite(v)) return;
      s += m[1] === '+' ? v : -v; n++;
    });
    return tem && n ? Math.round(s * 100) / 100 : null;
  }
  var ult = null;
  setInterval(function () {
    var a = $('iaAvancadoModal'), e = $('advLucroEspelho');
    if (!a || !e || getComputedStyle(a).display === 'none') return;
    var v = soma(); if (v === null) return;
    var saldo = num(($('advSaldoEspelho') || {}).textContent), pct = saldo ? v / Math.max(1, saldo - v) * 100 : 0;
    var txt = (v >= 0 ? '$' : '$-') + Math.abs(v).toFixed(2) + ' (' + (pct >= 0 ? '' : '-') + Math.abs(pct).toFixed(2) + '%)';
    var atual = e.textContent || '';
    var novo = /\$/.test(atual) ? atual.replace(/\$\s*[+\-−]?\s*[\d.,]+(\s*\([^)]*\))?/, txt) : txt;
    if (novo !== atual) e.textContent = novo;
    if (ult !== (v >= 0)) { ult = v >= 0; e.style.color = v >= 0 ? '#4ade80' : '#f87171'; }
  }, 400);
})();
