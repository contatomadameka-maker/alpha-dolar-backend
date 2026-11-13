/* IAS-HUD-V1 — IA Simples: painel do robo rodando com identidade nossa.
   Anel da sessao (verde = caminho ate a meta, vermelho = quanto do limite de perda ja foi usado), lucro no centro,
   pulso de radar enquanto espera sinal, contador de ganhos/perdas e as ultimas operacoes em pontos.
   So le o que o modal ja mostra; nao mexe no robo. */
(function () {
  if (window.__iasHud) return; window.__iasHud = true;
  function $(i) { return document.getElementById(i); }
  function num(t) { var m = String(t || '').replace(/,/g, '').match(/-?\$?\s*-?\d+(\.\d+)?/); if (!m) return NaN; return parseFloat(m[0].replace(/[$\s]/g, '')); }
  function txt(id) { var e = $(id); return e ? String(e.textContent || '').trim() : ''; }
  var R = 74, C = 2 * Math.PI * R, ult = null, hist = [], ultW = -1, ultL = -1;
  function estilo() {
    var s = document.createElement('style');
    s.textContent = '#iasHud{position:relative;display:flex;flex-direction:column;align-items:center;gap:10px;padding:14px 10px 6px;margin:0 0 6px}' +
      '#iasHud .rg{position:relative;width:190px;height:190px}#iasHud svg{width:100%;height:100%;overflow:visible}' +
      '#iasHud .bg{fill:none;stroke:rgba(108,92,231,.14);stroke-width:12}#iasHud .gn{fill:none;stroke:#4ADE80;stroke-width:12;stroke-linecap:round;transition:stroke-dashoffset .8s ease;filter:drop-shadow(0 0 8px rgba(74,222,128,.55))}' +
      '#iasHud .rd{fill:none;stroke:#FB7185;stroke-width:5;stroke-linecap:round;transition:stroke-dashoffset .8s ease;opacity:.9}' +
      '#iasHud .sw{transform-origin:95px 95px;animation:iasGira 2.6s linear infinite}#iasHud.op .sw{animation-duration:.9s}#iasHud.parado .sw{display:none}' +
      '@keyframes iasGira{to{transform:rotate(360deg)}}' +
      '#iasHud .ct{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;pointer-events:none}' +
      '#iasHud .ct small{font-size:10px;letter-spacing:.18em;color:#8B90B8}#iasHud .ct b{font:800 30px "Space Mono",ui-monospace,monospace;line-height:1.1;color:#E8ECF4}#iasHud .ct b.pos{color:#4ADE80;text-shadow:0 0 16px rgba(74,222,128,.45)}#iasHud .ct b.neg{color:#FB7185}' +
      '#iasHud .ct em{font-style:normal;font-size:12px;color:#A9AED0;margin-top:2px}#iasHud .ct i{font-style:normal;font-size:11px;color:#6C7196;margin-top:6px}' +
      '#iasHud .fl{position:absolute;inset:-6px;border-radius:50%;pointer-events:none;opacity:0}#iasHud .fl.w{animation:iasFl .9s ease-out;box-shadow:0 0 0 2px rgba(74,222,128,.8),0 0 40px rgba(74,222,128,.6)}#iasHud .fl.l{animation:iasFl .9s ease-out;box-shadow:0 0 0 2px rgba(251,113,133,.8),0 0 40px rgba(251,113,133,.5)}' +
      '@keyframes iasFl{0%{opacity:1;transform:scale(.92)}100%{opacity:0;transform:scale(1.12)}}' +
      '#iasHud .st{display:flex;align-items:center;gap:8px;font-size:13px;color:#C9CCEA;min-height:20px;text-align:center}#iasHud .st i{width:8px;height:8px;border-radius:50%;background:#6C5CE7;box-shadow:0 0 10px #6C5CE7;animation:iasPi 1.2s ease-in-out infinite;flex:none}' +
      '#iasHud.op .st i{background:#FBBF24;box-shadow:0 0 10px #FBBF24}@keyframes iasPi{50%{opacity:.25}}' +
      '#iasHud .kp{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;width:100%}#iasHud .kp div{padding:7px 6px;border-radius:10px;background:rgba(255,255,255,.03);border:1px solid rgba(108,92,231,.18);text-align:center}' +
      '#iasHud .kp small{display:block;font-size:9.5px;letter-spacing:.12em;color:#8B90B8}#iasHud .kp b{font:700 14px "Space Mono",ui-monospace,monospace;color:#E8ECF4}' +
      '#iasHud .dt{display:flex;gap:4px;justify-content:center;flex-wrap:wrap;min-height:10px}#iasHud .dt span{width:10px;height:10px;border-radius:3px;background:#262A40}#iasHud .dt span.w{background:#4ADE80}#iasHud .dt span.l{background:#FB7185}' +
      '#botRunningModal .ias-rola{overflow-y:auto;overscroll-behavior:contain;padding-right:4px;-webkit-mask-image:linear-gradient(180deg,#000 calc(100% - 28px),transparent);mask-image:linear-gradient(180deg,#000 calc(100% - 28px),transparent)}' +
      '#botRunningModal .ias-rola::-webkit-scrollbar{width:6px}#botRunningModal .ias-rola::-webkit-scrollbar-thumb{background:rgba(108,92,231,.45);border-radius:6px}#botRunningModal .ias-rola::-webkit-scrollbar-track{background:transparent}#botRunningModal .ias-rola{scrollbar-width:thin;scrollbar-color:rgba(108,92,231,.45) transparent}' +
      '@media (max-width:768px){html.ias-mob,html.ias-mob body{overflow:hidden!important;overscroll-behavior:none}' + /* IAS-HUD-V3: celular, so o painel na tela */
      'html.ias-mob #botRunningModal{position:fixed!important;inset:0!important;z-index:2000!important;background:rgba(5,6,12,.97)!important;display:block!important;overflow:hidden!important}' +
      'html.ias-mob #botRunningModal .modal-container-bot-running{position:fixed!important;left:8px!important;right:8px!important;top:calc(8px + env(safe-area-inset-top,0px))!important;bottom:calc(86px + env(safe-area-inset-bottom,0px))!important;width:auto!important;height:auto!important;max-height:none!important;min-height:0!important;margin:0!important;transform:none!important;overflow-y:auto!important;overflow-x:hidden!important;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;padding-bottom:18px!important}}' +
      '#botRunningModal.ias-hud .bot-running-header,#botRunningModal.ias-hud #botStatusMessage{display:none!important}';
    document.head.appendChild(s);
  }
  function monta() {
    var box = document.querySelector('#botRunningModal .modal-container-bot-running'); if (!box) return;
    if ($('iasHud')) return;
    var h = document.createElement('div'); h.id = 'iasHud';
    h.innerHTML = '<div class="rg"><svg viewBox="0 0 190 190" aria-hidden="true">' +
      '<defs><linearGradient id="iasSw" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#6C5CE7" stop-opacity="0"/><stop offset="1" stop-color="#6C5CE7" stop-opacity=".55"/></linearGradient></defs>' +
      '<circle class="bg" cx="95" cy="95" r="' + R + '"/>' +
      '<g class="sw"><path d="M95 95 L95 9 A86 86 0 0 1 169.5 52 Z" fill="url(#iasSw)" opacity=".35"/></g>' +
      '<circle class="gn" id="iasG" cx="95" cy="95" r="' + R + '" stroke-dasharray="' + C.toFixed(1) + '" stroke-dashoffset="' + C.toFixed(1) + '" transform="rotate(-90 95 95)"/>' +
      '<circle class="rd" id="iasRd" cx="95" cy="95" r="' + (R - 13) + '" stroke-dasharray="' + (2 * Math.PI * (R - 13)).toFixed(1) + '" stroke-dashoffset="' + (2 * Math.PI * (R - 13)).toFixed(1) + '" transform="rotate(-90 95 95)"/>' +
      '</svg><div class="ct"><small>SESSÃO</small><b id="iasV">$0.00</b><em id="iasP">0% da meta</em><i id="iasS">saldo —</i></div><div class="fl" id="iasFl"></div></div>' +
      '<div class="st"><i></i><span id="iasT">Iniciando…</span></div>' +
      '<div class="kp"><div><small>GANHOS</small><b id="iasW" style="color:#4ADE80">0</b></div><div><small>PERDAS</small><b id="iasL" style="color:#FB7185">0</b></div><div><small>LIMITE USADO</small><b id="iasU">0%</b></div></div>' +
      '<div class="dt" id="iasDt" aria-label="Últimas operações"></div>';
    box.insertBefore(h, box.firstChild);
    $('botRunningModal').classList.add('ias-hud');
  }
  function celular(ov) { var vis = ov.classList.contains('active') || getComputedStyle(ov).display !== 'none', on = innerWidth <= 768 && vis; document.documentElement.classList.toggle('ias-mob', on); }
  document.addEventListener('click', function (e) { var b = e.target.closest && e.target.closest('#botRunningModal .ias-cfg-btn'); if (!b || innerWidth > 768) return;
    setTimeout(function () { var box = document.querySelector('#botRunningModal .modal-container-bot-running'); if (!box || !b.classList.contains('on')) return; var y = b.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop - 8; try { box.scrollTo({ top: y, behavior: 'smooth' }); } catch (x) { box.scrollTop = y; } }, 80); }, true);
  function pinta() {
    var ov = $('botRunningModal'); if (!ov) return; celular(ov);
    if (!$('iasHud')) monta(); if (!$('iasHud')) return;
    var pl = num(txt('botRunningProfit')), meta = Math.abs(num(txt('botDisplayTarget'))), stop = Math.abs(num(txt('botDisplayStop')));
    if (!isFinite(pl)) pl = 0;
    var v = $('iasV'); v.textContent = (pl < 0 ? '−$' : '$') + Math.abs(pl).toFixed(2); v.className = pl > 0 ? 'pos' : pl < 0 ? 'neg' : '';
    var pm = meta > 0 ? Math.max(0, Math.min(1, pl / meta)) : 0, pu = stop > 0 ? Math.max(0, Math.min(1, -pl / stop)) : 0;
    $('iasG').style.strokeDashoffset = (C * (1 - pm)).toFixed(1);
    var c2 = 2 * Math.PI * (R - 13); $('iasRd').style.strokeDashoffset = (c2 * (1 - pu)).toFixed(1);
    $('iasP').textContent = meta > 0 ? Math.round(pm * 100) + '% da meta de $' + meta.toFixed(2) : 'sem meta';
    $('iasU').textContent = Math.round(pu * 100) + '%'; $('iasU').style.color = pu >= .7 ? '#FB7185' : pu >= .4 ? '#FBBF24' : '#E8ECF4';
    var sd = txt('botRunningSaldo'); $('iasS').textContent = sd && sd !== '$—' ? 'saldo ' + sd : 'saldo —';
    var st = txt('botStatusText') || txt('dcBarLabel'); var cr = txt('dcCronometro'); $('iasT').textContent = (st || 'Aguardando sinal…').replace(/\s+/g, ' ') + (cr && st.indexOf(cr) < 0 ? ' · ' + cr : '');
    var hud = $('iasHud'), em = /andamento|comprad|aberta|operando|executando/i.test(st + ' ' + ((document.querySelector('.ias-ops [data-lista]') || {}).textContent || ''));
    hud.classList.toggle('op', em); hud.classList.toggle('parado', !ov.classList.contains('active') && getComputedStyle(ov).display === 'none');
    var w = parseInt(((document.querySelector('.ias-ops [data-w]') || {}).textContent) || '', 10), l = parseInt(((document.querySelector('.ias-ops [data-l]') || {}).textContent) || '', 10);
    if (isFinite(w)) $('iasW').textContent = w; if (isFinite(l)) $('iasL').textContent = l;
    if (isFinite(w) && isFinite(l)) {
      if (ultW >= 0 && (w > ultW || l > ultL)) { for (var a = ultW; a < w; a++) hist.push('w'); for (var b = ultL; b < l; b++) hist.push('l'); hist = hist.slice(-20); flash(w > ultW ? 'w' : 'l'); }
      else if (ultW < 0 && (w || l)) { var lin = document.querySelectorAll('.ias-ops [data-lista] > *'); hist = []; Array.prototype.slice.call(lin, 0, 20).reverse().forEach(function (e) { var t = e.textContent || ''; if (/\+\$|ganho|won/i.test(t)) hist.push('w'); else if (/−\$|-\$|perda|lost/i.test(t)) hist.push('l'); }); }
      ultW = w; ultL = l; }
    else if (ult != null && pl !== ult) { hist.push(pl > ult ? 'w' : 'l'); hist = hist.slice(-20); flash(pl > ult ? 'w' : 'l'); }
    ult = pl;
    lista();
    $('iasDt').innerHTML = hist.map(function (k) { return '<span class="' + k + '"></span>'; }).join('');
  }
  function lista() { /* IAS-HUD-V2: a lista de operacoes rola por dentro e termina antes do botao Parar */
    var Ls = document.querySelector('#botRunningModal .ias-ops [data-lista]'), st = $('stopBotBtn'); if (!Ls || !st) return;
    Ls.classList.add('ias-rola'); var box = document.querySelector('#botRunningModal .modal-container-bot-running'), pos = getComputedStyle(st).position, mx = 320;
    if ((pos === 'fixed' || pos === 'sticky') && box && box.clientHeight > 0) { var sobra = box.scrollHeight - box.clientHeight, ra = Ls.getBoundingClientRect(), rb = st.getBoundingClientRect(), fim = ra.bottom + box.scrollTop - sobra, over = fim - (rb.top - 12);
      mx = Math.round(Ls.clientHeight - sobra - Math.max(0, over)); }
    mx = Math.max(150, Math.min(520, mx)); if (Ls.__mx !== mx) { Ls.__mx = mx; Ls.style.maxHeight = mx + 'px'; }
  }
  function flash(k) { var f = $('iasFl'); if (!f) return; f.className = 'fl'; void f.offsetWidth; f.className = 'fl ' + k; }
  function inicia() { estilo(); monta(); setInterval(pinta, 700); pinta(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inicia); else inicia();
})();
