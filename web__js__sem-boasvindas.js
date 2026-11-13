/* SEM-BOASVINDAS-V3: esconde o popup de boas-vindas ("Antes de operar / conheça a plataforma").
   V3: também em outros idiomas (a tradução troca o texto antes daqui, então procura o texto traduzido também) */
(function () {
  var RX = /conhe(ç|c|&ccedil;)a a plataforma|BEM-VINDO AO ALPHA|Fechar e operar agora|Guia Visual de D[ií]gitos/i;
  var RX2 = null, RX2lang = '';
  function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function rxIdioma() {
    try {
      var i = window.i18n, l = i && (i.getLang ? i.getLang() : i.current);
      if (!i || !i.dict || !l || l === 'pt') return null;
      if (RX2lang === l) return RX2;
      var v = [];
      [i.dict[l] || {}, i.dict.en || {}].forEach(function (d) { for (var k in d) if (RX.test(k) && d[k] && String(d[k]).length > 6) v.push(esc(String(d[k]).trim())); });
      RX2lang = l; RX2 = v.length ? new RegExp(v.join('|'), 'i') : null;
      return RX2;
    } catch (e) { return null; }
  }
  function esconder(el) {
    var n = el, ov = null, top = null;
    while (n && n !== document.body && n !== document.documentElement) {
      var cs = getComputedStyle(n);
      if (cs.position === 'fixed' || cs.position === 'absolute' && (n.offsetWidth >= innerWidth * .9)) ov = n;
      if (/modal|overlay|popup|boas|welcome|onboard|tutorial|intro/i.test((n.id || '') + ' ' + (typeof n.className === 'string' ? n.className : ''))) top = top || n;
      n = n.parentElement;
    }
    var alvo = ov || top; if (!alvo || alvo.getAttribute('data-sbv') === '1') return;
    if (alvo.id === 'atour-ov' || alvo.closest && alvo.closest('#atour-ov')) return;   // nunca esconde o tour
    alvo.setAttribute('data-sbv', '1'); alvo.style.setProperty('display', 'none', 'important'); alvo.style.setProperty('visibility', 'hidden', 'important');
    document.body.style.overflow = ''; document.documentElement.style.overflow = ''; document.body.classList.remove('modal-open');
  }
  function sweep() {
    if (!document.body) return;
    var R2 = rxIdioma();
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, { acceptNode: function (t) { var v = t.nodeValue || ''; return (RX.test(v) || (R2 && R2.test(v))) ? 1 : 3; } }), t, L = [];
    while ((t = w.nextNode())) L.push(t.parentElement);
    L.forEach(esconder);
  }
  var tm = null;
  function agenda() { if (tm) return; tm = setTimeout(function () { tm = null; sweep(); }, 80); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sweep); else sweep();
  window.addEventListener('load', sweep);
  window.addEventListener('alpha:idioma', function () { RX2lang = ''; sweep(); });
  try { new MutationObserver(agenda).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class'] }); } catch (e) {}
})();
