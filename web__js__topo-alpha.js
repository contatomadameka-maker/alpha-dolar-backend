/* TOPO-ALPHA-V4: Tour / Depositar / Sacar (topo no PC, menu lateral no celular), Alpha Projecao no menu, aviso de conexao Deriv vencendo */
(function () {
  var DERIV_CAIXA = 'https://home.deriv.com/dashboard/deposit';
  var DERIV_SAQUE = 'https://home.deriv.com/dashboard/withdraw';
  var VALIDADE_DIAS = 30, AVISAR_COM = 3;
  var SVG = {
    calc: '<rect width="16" height="20" x="4" y="2" rx="2"/><line x1="8" x2="16" y1="6" y2="6"/><line x1="16" x2="16" y1="14" y2="18"/><path d="M16 10h.01"/><path d="M12 10h.01"/><path d="M8 10h.01"/><path d="M12 14h.01"/><path d="M8 14h.01"/><path d="M12 18h.01"/><path d="M8 18h.01"/>',
    tour: '<circle cx="12" cy="12" r="10"/><path d="m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z"/>',
    dep: '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/>',
    saq: '<circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="m8 12 4 4 4-4"/>'
  };
  function svg(nome, ref) {
    var w = (ref && ref.getAttribute('width')) || '20', h = (ref && ref.getAttribute('height')) || '20';
    var cls = ref && ref.getAttribute('class') ? ' class="' + ref.getAttribute('class') + '"' : '';
    return '<svg' + cls + ' width="' + w + '" height="' + h + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + SVG[nome] + '</svg>';
  }
  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function abrirTour() { try { if (window.AlphaTour) { if (AlphaTour.resetar) AlphaTour.resetar(); AlphaTour.iniciar(); } } catch (e) {} }
  function css() {
    if (document.getElementById('topoAlphaCss')) return;
    var s = document.createElement('style'); s.id = 'topoAlphaCss';
    s.textContent =
      '.ta-btn{display:inline-flex;align-items:center;gap:6px;height:34px;padding:0 12px;border-radius:10px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.04);color:#e6edf3;font:700 12.5px Inter,system-ui,sans-serif;cursor:pointer;text-decoration:none;white-space:nowrap}' +
      '.ta-btn svg{width:16px;height:16px}.ta-btn:hover{border-color:rgba(245,197,66,.55);color:#f5c542}' +
      '.ta-dep{background:linear-gradient(135deg,#22c55e,#16a34a);border-color:transparent;color:#04130a}.ta-dep:hover{color:#04130a;filter:brightness(1.08)}' +
      '.ta-wrap{display:flex;align-items:center;gap:8px;margin-right:6px}' +
      '@media(min-width:769px){.ta-rail{display:none!important}}' +
      '@media(max-width:768px){.ta-wrap{display:none!important}}' +
      '#taAviso{position:fixed;left:0;right:0;top:0;z-index:2147482000;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;padding:9px 16px;background:linear-gradient(90deg,#f5c542,#e0a82e);color:#1a1205;font:600 13px Inter,system-ui,sans-serif;text-align:center;box-sizing:border-box}' +
      '#taAviso button{border:0;border-radius:9px;padding:7px 14px;font:800 12px Inter,system-ui,sans-serif;cursor:pointer}' +
      '#taAviso .ta-rc{background:#1a1205;color:#f5c542}#taAviso .ta-x{background:transparent;color:#1a1205;font-size:16px;padding:4px 8px}';
    document.head.appendChild(s);
  }
  function botoesTopo() {
    var alvo = document.querySelector('.topbar-right');
    if (!alvo || document.getElementById('taWrap')) return;
    var w = document.createElement('div'); w.className = 'ta-wrap'; w.id = 'taWrap';
    w.innerHTML =
      '<button type="button" class="ta-btn" id="taTour" title="Rever o tour da plataforma">' + svg('tour') + '<span>Tour</span></button>' +
      '<a class="ta-btn" href="' + DERIV_SAQUE + '" target="_blank" rel="noopener" title="Sacar pela Deriv">' + svg('saq') + '<span>Sacar</span></a>' +
      '<a class="ta-btn ta-dep" href="' + DERIV_CAIXA + '" target="_blank" rel="noopener" title="Depositar pela Deriv">' + svg('dep') + '<span>Depositar</span></a>';
    var notif = document.getElementById('notifWrap');
    if (notif && notif.parentNode === alvo) alvo.insertBefore(w, notif); else alvo.insertBefore(w, alvo.firstChild);
    document.getElementById('taTour').addEventListener('click', abrirTour);
  }
  /* item "Tutoriais" do menu lateral: modelo para os novos itens (mesmo visual) */
  function itemBase() {
    var cands = Array.prototype.slice.call(document.querySelectorAll('a,button'));
    return cands.find(function (e) { return /^\s*Tutoriais\s*$/i.test((window.i18n && window.i18n.orig ? window.i18n.orig(e) : (e.textContent || ''))) /* TOPO-I18N-V1 */ && e.closest('nav,aside,[class*="rail"],[class*="side"],[id*="rail"],[id*="side"]'); });
  }
  function clonar(base, rotulo, icone, extraCls) {
    var el = base.cloneNode(true);
    el.removeAttribute('id'); el.removeAttribute('onclick');
    el.querySelectorAll('[id]').forEach(function (x) { x.removeAttribute('id'); });
    el.classList.remove('active', 'ativo', 'on', 'selected');
    ['title', 'data-title', 'data-tooltip', 'aria-label', 'data-label'].forEach(function (a) { if (el.hasAttribute(a)) el.setAttribute(a, rotulo); });
    var s = el.querySelector('svg');
    if (s) { var t = document.createElement('span'); t.innerHTML = svg(icone, s); s.parentNode.replaceChild(t.firstChild, s); }
    var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), nd;
    while ((nd = walker.nextNode())) { var tt = window.i18n && window.i18n.t ? String(window.i18n.t('Tutoriais')).trim() : 'Tutoriais'; if (/Tutoriais/i.test(nd.nodeValue)) nd.nodeValue = nd.nodeValue.replace(/Tutoriais/i, rotulo); else if (tt && nd.nodeValue.indexOf(tt) >= 0) nd.nodeValue = nd.nodeValue.replace(tt, rotulo); }
    if (extraCls) el.classList.add(extraCls);
    return el;
  }
  function paraLink(el, url, novaAba) {
    if (el.tagName === 'A') { el.href = url; if (novaAba) { el.target = '_blank'; el.rel = 'noopener'; } else el.removeAttribute('target'); return el; }
    el.addEventListener('click', function (e) { e.preventDefault(); if (novaAba) window.open(url, '_blank', 'noopener'); else location.href = url; });
    return el;
  }
  function menu() {
    var base = itemBase(); if (!base) return;
    var ref = base;
    if (!document.querySelector('.ta-proj')) {
      var p = paraLink(clonar(base, 'Alpha Projeção', 'calc', 'ta-proj'), '/alpha-projecao.html', false);
      ref.parentNode.insertBefore(p, ref.nextSibling); ref = p;
    } else ref = document.querySelector('.ta-proj');
    if (document.querySelector('.ta-rail')) return;
    [['Tour', 'tour', null], ['Depositar', 'dep', DERIV_CAIXA], ['Sacar', 'saq', DERIV_SAQUE]].forEach(function (it) {
      var el = clonar(base, it[0], it[1], 'ta-rail');
      if (it[2]) paraLink(el, it[2], true);
      else el.addEventListener('click', function (e) { e.preventDefault(); abrirTour(); });
      if (el.tagName === 'A' && !it[2]) el.removeAttribute('href');
      ref.parentNode.insertBefore(el, ref.nextSibling); ref = el;
    });
  }
  function reconectar() {
    try { sessionStorage.setItem('alpha_voltar_para', location.pathname + location.search); } catch (e) {}
    if (window.AlphaSessaoDeriv && typeof AlphaSessaoDeriv.reconectar === 'function') return AlphaSessaoDeriv.reconectar();
    location.href = '/login?reconectar=1';
  }
  function encaixar(d) {
    var h = d.offsetHeight || 0, tb = document.querySelector('.topbar');
    if (tb) { var cs = getComputedStyle(tb); if (cs.position === 'fixed' || cs.position === 'sticky') tb.style.top = h + 'px'; }
    document.body.style.marginTop = h + 'px';
  }
  function soltar() { var tb = document.querySelector('.topbar'); if (tb) tb.style.top = ''; document.body.style.marginTop = ''; }
  function aviso() {
    if (!ls('deriv_bearer_token')) return;
    var em = parseInt(ls('deriv_token_em') || '0', 10); if (!em) return;
    var falta = Math.ceil((em + VALIDADE_DIAS * 864e5 - Date.now()) / 864e5);
    if (falta > AVISAR_COM || falta < 0) return;
    var hoje = new Date().toISOString().slice(0, 10);
    if (ls('ta_aviso_oculto') === hoje || document.getElementById('taAviso')) return;
    var d = document.createElement('div'); d.id = 'taAviso';
    d.innerHTML = '<span>' + (falta <= 0 ? 'Sua conexão com a Deriv vence hoje.' : 'Sua conexão com a Deriv vence em ' + falta + ' dia(s).') + ' Reconecte agora para não interromper os robôs.</span>' +
      '<button type="button" class="ta-rc">Reconectar</button><button type="button" class="ta-x" aria-label="Fechar">✕</button>';
    document.body.insertBefore(d, document.body.firstChild);
    encaixar(d); window.addEventListener('resize', function () { if (document.getElementById('taAviso')) encaixar(d); });
    d.querySelector('.ta-rc').onclick = reconectar;
    d.querySelector('.ta-x').onclick = function () { try { localStorage.setItem('ta_aviso_oculto', hoje); } catch (e) {} d.remove(); soltar(); };
  }
  function ini() { css(); botoesTopo(); menu(); aviso(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ini); else ini();
  window.AlphaTopo = { aviso: aviso };
})();
