/* IDIOMAS-MOBILE-V1 — no celular, os idiomas do menu (que só tinham PT/EN/ES) viram um botão "🌐 Idioma"
   que abre um painel ao lado com os 11 idiomas. No computador nada muda. */
(function () {
  'use strict';
  if (window.__idiomasMob) return; window.__idiomasMob = true;
  var MAX = 768;
  var L = [['pt', '🇧🇷', 'Português'], ['en', '🇺🇸', 'English'], ['es', '🇪🇸', 'Español'], ['vi', '🇻🇳', 'Tiếng Việt'],
    ['fr', '🇫🇷', 'Français'], ['de', '🇩🇪', 'Deutsch'], ['it', '🇮🇹', 'Italiano'], ['id', '🇮🇩', 'Bahasa Indonesia'],
    ['hi', '🇮🇳', 'हिन्दी'], ['th', '🇹🇭', 'ไทย'], ['ar', '🌍', 'العربية']];
  var TIT = { pt: 'Idioma', en: 'Language', es: 'Idioma', vi: 'Ngôn ngữ', fr: 'Langue', de: 'Sprache', it: 'Lingua', id: 'Bahasa', hi: 'भाषा', th: 'ภาษา', ar: 'اللغة' };
  var RXT = /^\s*(🇧🇷|🇺🇸|🇬🇧|🇪🇸)?\s*(portugu[eê]s|english|ingl[eê]s|espa[nñ]ol|espanhol|pt|en|es|pt-br)\s*$/i;
  function atual() { var i = window.i18n; var l = i && (i.getLang ? i.getLang() : i.current); if (!l) { try { l = localStorage.getItem('alpha_lang'); } catch (e) {} } return (l || 'pt').slice(0, 2); }
  function mob() { return innerWidth <= MAX; }

  var css = document.createElement('style');
  css.textContent =
    '.idm-bt{display:none;align-items:center;gap:10px;width:calc(100% - 16px);margin:8px;padding:11px 12px;border-radius:12px;border:1px solid rgba(139,92,246,.35);background:linear-gradient(160deg,rgba(139,92,246,.14),rgba(255,255,255,.02));color:#fff;font:800 14px Inter,system-ui,sans-serif;cursor:pointer;text-align:left;box-sizing:border-box}' +
    '.idm-bt i{font-style:normal;font-size:18px}.idm-bt span{flex:1}.idm-bt small{font-size:11px;font-weight:800;color:#c4b5fd}' +
    '@media (max-width:' + MAX + 'px){.idm-bt{display:flex}.idm-esc{display:none!important}}' +
    '.idm-bg{position:fixed;inset:0;z-index:2147483000;background:rgba(2,3,10,.55);display:none}.idm-bg.on{display:block}' +
    '.idm{position:fixed;top:0;bottom:0;left:0;z-index:2147483001;width:min(320px,86vw);display:flex;flex-direction:column;background:linear-gradient(180deg,#141726,#0d0f1a);border-right:1px solid rgba(139,92,246,.35);box-shadow:20px 0 60px rgba(0,0,0,.6);transform:translateX(-105%);transition:transform .2s ease-out;font-family:Inter,system-ui,sans-serif;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}' +
    '.idm.on{transform:none}' +
    '.idm-h{display:flex;align-items:center;gap:10px;padding:16px 16px 12px;border-bottom:1px solid rgba(255,255,255,.06)}' +
    '.idm-h b{font-size:16px;font-weight:800;color:#f1f5f9}.idm-h button{margin-left:auto;width:34px;height:34px;border-radius:10px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);color:#cbd5e1;font-size:18px;cursor:pointer}' +
    '.idm-l{overflow:auto;padding:12px;display:grid;gap:8px}' +
    '.idm-l button{display:flex;align-items:center;gap:12px;padding:13px 14px;border-radius:13px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);color:#fff;font:700 15px Inter,system-ui,sans-serif;cursor:pointer;text-align:left}' +
    '.idm-l button i{font-style:normal;font-size:20px}.idm-l button span{flex:1}' +
    '.idm-l button.on{border-color:rgba(245,197,66,.7);background:rgba(245,197,66,.1);color:#f5c542}.idm-l button.on::after{content:"✓";font-weight:900}';
  document.head.appendChild(css);

  var bg, pn;
  function painel() {
    if (pn) return;
    bg = document.createElement('div'); bg.className = 'idm-bg'; bg.setAttribute('data-no-i18n', '1');
    pn = document.createElement('div'); pn.className = 'idm'; pn.setAttribute('data-no-i18n', '1'); pn.setAttribute('dir', 'ltr');
    pn.innerHTML = '<div class="idm-h"><b>🌐 <span class="idm-tt"></span></b><button type="button" aria-label="Fechar">✕</button></div><div class="idm-l">' +
      L.map(function (x) { return '<button type="button" data-l="' + x[0] + '"><i>' + x[1] + '</i><span>' + x[2] + '</span></button>'; }).join('') + '</div>';
    document.body.appendChild(bg); document.body.appendChild(pn);
    bg.onclick = fechar; pn.querySelector('.idm-h button').onclick = fechar;
    pn.querySelectorAll('[data-l]').forEach(function (b) { b.onclick = function () { trocar(b.dataset.l); fechar(); }; });
  }
  function abrir(e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    painel(); var l = atual();
    pn.querySelector('.idm-tt').textContent = TIT[l] || 'Idioma';
    pn.querySelectorAll('[data-l]').forEach(function (b) { b.classList.toggle('on', b.dataset.l === l); });
    bg.classList.add('on'); requestAnimationFrame(function () { pn.classList.add('on'); });
  }
  function fechar() { if (!pn) return; pn.classList.remove('on'); bg.classList.remove('on'); }
  function trocar(l) {
    try { if (typeof window.trocarIdioma === 'function') window.trocarIdioma(l); } catch (e) {}
    try { if (window.i18n && (window.i18n.getLang ? window.i18n.getLang() : '') !== l) window.i18n.apply(l); } catch (e) {}
    try { localStorage.setItem('alpha_lang', l); } catch (e) {}
    rotulo();
  }

  /* acha os itens de idioma que ja existem no menu (PT/EN/ES) */
  function ehIdioma(el) {
    var oc = el.getAttribute('onclick') || '', d = el.getAttribute('data-lang') || el.getAttribute('data-idioma') || '';
    if (/trocarIdioma|setLang|changeLang|mudarIdioma/i.test(oc) || /^(pt|en|es)/i.test(d)) return true;
    var t = (window.i18n && window.i18n.orig ? window.i18n.orig(el) : el.textContent) || '';
    return t.length < 30 && RXT.test(t.replace(/\s+/g, ' '));
  }
  function grupos() {
    var itens = Array.prototype.filter.call(document.querySelectorAll('a,button,li,[onclick],[data-lang],[data-idioma]'), function (el) {
      return !el.closest('.idm, .idm-bt, #atour-ov') && ehIdioma(el);
    });
    var gs = [];
    itens.forEach(function (el) {
      var p = el.parentElement;
      for (var i = 0; i < 4 && p && p !== document.body; i++, p = p.parentElement) {
        var n = itens.filter(function (x) { return p.contains(x); }).length;
        if (n >= 2) { if (gs.indexOf(p) < 0 && !gs.some(function (g) { return g.contains(p); })) gs.push(p); return; }
      }
    });
    return gs.filter(function (g) { return !gs.some(function (o) { return o !== g && o.contains(g); }); });
  }
  var bt = null;
  function rotulo() { if (!bt) return; var l = atual(), x = L.filter(function (y) { return y[0] === l; })[0] || L[0]; bt.innerHTML = '<i>🌐</i><span>' + (TIT[l] || 'Idioma') + '</span><small>' + x[1] + ' ' + l.toUpperCase() + ' ›</small>'; }
  function montar() {
    if (bt && bt.isConnected) return true;
    var gs = grupos(), ancora = null;
    // prefere o grupo de idiomas que fica dentro do menu do celular
    gs.forEach(function (g) { if (!ancora && g.closest('.v3-rail, nav, aside, [class*="menu"], [class*="rail"], [class*="side"], [id*="menu"], [id*="rail"]')) ancora = g; });
    if (!ancora && gs.length) ancora = gs[0];
    bt = document.createElement('button'); bt.type = 'button'; bt.className = 'idm-bt'; bt.setAttribute('data-no-i18n', '1');
    bt.onclick = abrir;
    if (ancora) {
      gs.forEach(function (g) { if (g.closest('.v3-rail, nav, aside, [class*="menu"], [class*="rail"], [class*="side"], [id*="menu"], [id*="rail"]') || g === ancora) g.classList.add('idm-esc'); });
      ancora.parentNode.insertBefore(bt, ancora);
    } else {
      var rail = document.querySelector('.v3-rail'); if (!rail) { bt = null; return false; }
      rail.appendChild(bt);
    }
    rotulo(); return true;
  }
  function init() { var n = 0; (function vai() { if (!montar() && ++n < 20) setTimeout(vai, 500); })(); }
  addEventListener('alpha:idioma', rotulo);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  window.AlphaIdiomas = { abrir: abrir, trocar: trocar };
})();
