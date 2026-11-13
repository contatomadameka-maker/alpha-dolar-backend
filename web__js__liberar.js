/* Alpha Dolar — tudo liberado (sem cobranca, sem trial)
 * 1) consultas de produto no Supabase (produtos_ativos / produtos_liberados) respondem "liberado"
 * 2) ativarTrial / confirmarTrial seguem direto para a ferramenta; o modal de trial nao aparece
 * 3) botoes/links de compra (Cakto, /checkout) viram "Em breve"
 * Para voltar a cobrar no futuro: basta remover este arquivo das paginas.
 */
(function () {
  'use strict';
  if (/admin/i.test(location.pathname)) return; // LIBERAR-SEM-ADMIN

  // 1) consultas de acesso sempre liberadas
  var fetch0 = window.fetch;
  if (fetch0 && !fetch0.__liberar) {
    var f = function (u, o) {
      try {
        var s = typeof u === 'string' ? u : (u && u.url) || '';
        var met = (o && o.method) || (u && u.method) || 'GET';
        if (/\/rest\/v1\/produtos_(ativos|liberados)/.test(s) && /^get$/i.test(met)) {
          return Promise.resolve(new Response('[{"id":"liberado","ativo":true}]', { status: 200, headers: { 'Content-Type': 'application/json' } }));
        }
      } catch (e) {}
      return fetch0.apply(this, arguments);
    };
    f.__liberar = true;
    window.fetch = f;
  }

  // 2) trial desligado: executa o que viria depois da ativacao
  function seguir() {
    var cb = null;
    for (var i = 0; i < arguments.length; i++) if (typeof arguments[i] === 'function') { cb = arguments[i]; break; }
    try { if (cb) cb(); } catch (e) {}
    return Promise.resolve(true);
  }
  seguir.__liberar = true;
  function aplicar() {
    if (!window.ativarTrial || !window.ativarTrial.__liberar) window.ativarTrial = seguir;
    if (!window.confirmarTrial || !window.confirmarTrial.__liberar) window.confirmarTrial = seguir;
    window.verificarTrialDemo = function () { return Promise.resolve(); };
    var m = document.getElementById('modalTrial'); if (m) m.style.setProperty('display', 'none', 'important');
  }
  aplicar();
  document.addEventListener('DOMContentLoaded', aplicar);
  window.addEventListener('load', function () { aplicar(); setTimeout(aplicar, 1500); setTimeout(aplicar, 5000); });

  // 3) compras -> "Em breve"
  var COMPRA = /cakto\.com\.br|#em-breve|\/checkout(\?|$|\.html)|checkout\.html/i;
  var TXT = /^(\s*[\u{1F300}-\u{1FAFF}☀-➿✨🧠💎🛒💳🚀]*\s*)(comprar|adquirir|assinar|ativar trial|quero esse|quero o elite|comprar agora|adquirir agora)/iu;
  function emBreveTexto() { return (window.i18n && window.i18n.t) ? window.i18n.t('Em breve') : 'Em breve'; }
  function aviso() {
    var d = document.getElementById('lib-toast');
    if (!d) {
      d = document.createElement('div'); d.id = 'lib-toast';
      d.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:99999;background:#14161c;color:#e2e8f0;border:1px solid rgba(139,92,246,.45);border-radius:12px;padding:10px 16px;font:700 13px Inter,system-ui,sans-serif;box-shadow:0 10px 30px rgba(0,0,0,.45);transition:opacity .3s';
      document.body.appendChild(d);
    }
    d.textContent = emBreveTexto() + ' ✨'; d.style.opacity = '1';
    clearTimeout(d._t); d._t = setTimeout(function () { d.style.opacity = '0'; }, 2200);
  }
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href],button[onclick],[data-checkout]') : null;
    if (!a) return;
    var alvo = a.getAttribute('href') || a.getAttribute('onclick') || a.getAttribute('data-checkout') || '';
    if (COMPRA.test(alvo)) { e.preventDefault(); e.stopPropagation(); aviso(); }
  }, true);
  var open0 = window.open;
  window.open = function (u) {
    if (u && COMPRA.test(String(u))) { aviso(); return null; }
    return open0.apply(window, arguments);
  };
  function marcar() {
    var els = document.querySelectorAll('a[href],button[onclick]');
    for (var i = 0; i < els.length; i++) {
      var a = els[i], alvo = a.getAttribute('href') || a.getAttribute('onclick') || '';
      if (!COMPRA.test(alvo) || a.__emBreve) continue;
      a.__emBreve = true;
      a.style.opacity = '.75'; a.title = emBreveTexto();
      var mt = a.children.length === 0 ? a.textContent.match(TXT) : null;
      if (mt) a.textContent = (mt[1] || '') + emBreveTexto();
    }
  }
  document.addEventListener('DOMContentLoaded', marcar);
  window.addEventListener('load', function () { marcar(); setTimeout(marcar, 2000); });

  // traducao
  try {
    var d = window.i18n && window.i18n.dict;
    if (d) { if (d.en) d.en['Em breve'] = 'Coming soon'; if (d.es) d.es['Em breve'] = 'Próximamente'; }
  } catch (e) {}
})();
