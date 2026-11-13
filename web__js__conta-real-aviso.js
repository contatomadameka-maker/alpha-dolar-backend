/* CONTA-REAL-AVISO-V1 \u2014 pergunta antes de trocar para a conta REAL em qualquer robo.
   Funciona sozinho: vigia o toque em qualquer botao escrito "Real" / "REAL" / "Conta real",
   mostra o aviso e so deixa o botao agir se a pessoa confirmar. */
(function () {
  if (window.__contaRealAviso) return; window.__contaRealAviso = 1;
  var ATIVO = /(^|\s)(on|active|ativo|ativa|sel|selected|atual|is-active)(\s|$)/i;
  var liberado = null, ultimoOk = 0;

  function ehBotaoReal(el) {
    var b = el && el.closest && el.closest('button,[role="button"],a,[onclick]');
    if (!b || b.disabled) return null;
    if (b.hasAttribute('data-sem-aviso-real')) return null;
    var t = (b.textContent || '').replace(/\s+/g, ' ').trim().toUpperCase();
    if (t !== 'REAL' && t !== 'CONTA REAL') return null;
    // filtros de historico (Demo/Real da lista de operacoes) nao trocam a conta
    if (b.hasAttribute('data-v') || /^op|hist|filt/i.test(b.id || '') || b.closest('[id*="hist" i],[id*="Hist"],[id*="filt" i],.ops,.hist')) return null;
    if (ATIVO.test(b.className || '') || b.getAttribute('aria-pressed') === 'true') return null; // ja esta na real
    return b;
  }

  function css() {
    if (document.getElementById('cra-css')) return;
    var s = document.createElement('style'); s.id = 'cra-css';
    s.textContent =
      '#cra{position:fixed;inset:0;z-index:2147483600;display:flex;align-items:center;justify-content:center;padding:16px;' +
      'background:rgba(2,4,8,.62);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px)}' +
      '#cra .cx{width:100%;max-width:420px;background:#121009;border:1px solid rgba(212,175,55,.55);border-radius:20px;' +
      'padding:26px 22px 22px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.6),0 0 30px rgba(212,175,55,.12);' +
      'font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}' +
      '#cra h3{margin:0 0 10px;font-size:22px;font-weight:800;color:#f5c96a}' +
      '#cra p{margin:0 0 20px;font-size:15px;line-height:1.45;color:#e8e4d8}' +
      '#cra .bt{display:flex;gap:12px}' +
      '#cra button{flex:1;padding:13px 10px;border-radius:12px;font:inherit;font-size:16px;font-weight:800;cursor:pointer}' +
      '#cra .no{background:transparent;color:#e8e4d8;border:1px solid rgba(232,228,216,.22)}' +
      '#cra .ok{background:linear-gradient(135deg,#f6d27a,#d6a03c);color:#1a1205;border:0}';
    document.head.appendChild(s);
  }

  function pergunta(sim) {
    css();
    var v = document.getElementById('cra'); if (v) v.remove();
    var d = document.createElement('div'); d.id = 'cra'; d.setAttribute('role', 'dialog'); d.setAttribute('aria-modal', 'true');
    d.innerHTML = '<div class="cx"><h3>Trocar para a conta real?</h3><p>As opera\u00e7\u00f5es passar\u00e3o a usar dinheiro real.</p>' +
      '<div class="bt"><button type="button" class="no">Cancelar</button><button type="button" class="ok">Confirmar</button></div></div>';
    function fecha() { d.remove(); document.removeEventListener('keydown', esc, true); }
    function esc(e) { if (e.key === 'Escape') fecha(); }
    d.querySelector('.no').onclick = fecha;
    d.addEventListener('click', function (e) { if (e.target === d) fecha(); });
    d.querySelector('.ok').onclick = function () { fecha(); sim(); };
    document.addEventListener('keydown', esc, true);
    document.body.appendChild(d);
    setTimeout(function () { try { d.querySelector('.ok').focus(); } catch (e) {} }, 30);
  }

  document.addEventListener('click', function (e) {
    var b = ehBotaoReal(e.target);
    if (!b) return;
    if (liberado === b) { liberado = null; return; }      // ja confirmado: deixa o botao agir
    e.preventDefault(); e.stopPropagation(); if (e.stopImmediatePropagation) e.stopImmediatePropagation();
    pergunta(function () { liberado = b; ultimoOk = Date.now(); b.click(); });
  }, true);

  // paginas antigas que ainda perguntam com a caixinha do navegador: nao pergunta duas vezes
  var conf0 = window.confirm;
  window.confirm = function (m) {
    if (Date.now() - ultimoOk < 4000 && /conta real/i.test(String(m || '')) && /trocar/i.test(String(m || ''))) return true;
    return conf0.apply(window, arguments);
  };
})();
