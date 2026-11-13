/* SIGA-REDES-V1 + PARCEIRO-BORDA-V1: botao "Siga a gente" na barra de cima com Instagram, YouTube, TikTok e Kwai */
(function () {
  if (window.__sigaRedes) return; window.__sigaRedes = 1;
  var REDES = [
    { id: 'instagram', n: 'Instagram', d: 'Conteúdo diário', u: 'https://www.instagram.com/dirlleiluis', c: 'linear-gradient(45deg,#feda75,#fa7e1e 25%,#d62976 55%,#962fbf 80%,#4f5bd5)',
      s: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4.2"/><circle cx="17.3" cy="6.7" r="1.1" fill="#fff" stroke="none"/></svg>' },
    { id: 'youtube', n: 'YouTube', d: 'Tutoriais e lives', u: 'https://youtube.com/@dirleiluis', c: '#ff0033',
      s: '<svg viewBox="0 0 24 24" width="22" height="22"><rect x="2" y="5" width="20" height="14" rx="4" fill="#fff"/><path d="M10 9l5.2 3L10 15z" fill="#ff0033"/></svg>' },
    { id: 'tiktok', n: 'TikTok', d: 'Vídeos curtos', u: 'https://www.tiktok.com/@dirlleiluis', c: '#000',
      s: '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M14.5 3h3c.2 1.9 1.6 3.4 3.5 3.6v3a7 7 0 0 1-3.5-1.1v6.3A5.9 5.9 0 1 1 11.6 9v3.1a2.9 2.9 0 1 0 2.9 2.8z" fill="#25f4ee" transform="translate(-.6 -.4)"/><path d="M14.5 3h3c.2 1.9 1.6 3.4 3.5 3.6v3a7 7 0 0 1-3.5-1.1v6.3A5.9 5.9 0 1 1 11.6 9v3.1a2.9 2.9 0 1 0 2.9 2.8z" fill="#fe2c55" transform="translate(.6 .4)"/><path d="M14.5 3h3c.2 1.9 1.6 3.4 3.5 3.6v3a7 7 0 0 1-3.5-1.1v6.3A5.9 5.9 0 1 1 11.6 9v3.1a2.9 2.9 0 1 0 2.9 2.8z" fill="#fff"/></svg>' },
    { id: 'kwai', n: 'Kwai', d: 'Vídeos e dicas', u: 'https://kwai-video.com/u/@dirleiluissest/VnKCHACx', c: 'linear-gradient(135deg,#ff7a00,#ff4d00)',
      s: '<svg viewBox="0 0 24 24" width="22" height="22"><rect x="3" y="7" width="12" height="10" rx="3" fill="#fff"/><path d="M15.5 10.5l5-3v9l-5-3z" fill="#fff"/><circle cx="7.5" cy="10.5" r="1.4" fill="#ff5a00"/></svg>' }
  ];
  var CSS = '' +
    '#sigaBtn{position:relative;display:inline-flex;align-items:center;gap:8px;height:var(--sg-h,44px);padding:0 16px;margin:0 6px;border-radius:12px;border:0;cursor:pointer;color:#fff;font:800 14px Inter,system-ui,sans-serif;white-space:nowrap;' +
      'background:linear-gradient(#141a26,#141a26) padding-box,linear-gradient(45deg,#feda75,#fa7e1e,#d62976,#962fbf,#4f5bd5) border-box;border:2px solid transparent;animation:sgPulse 2.2s ease-in-out infinite;flex-shrink:0}' +
    '#sigaBtn:hover{filter:brightness(1.15)}' +
    '#sigaBtn .ig{width:22px;height:22px;border-radius:7px;display:grid;place-items:center;background:linear-gradient(45deg,#feda75,#fa7e1e 25%,#d62976 55%,#962fbf 80%,#4f5bd5)}' +
    '#sigaBtn .ig svg{width:15px;height:15px}' +
    '#sigaBtn .pt{position:absolute;top:-4px;right:-4px;width:11px;height:11px;border-radius:50%;background:#ff2d55;box-shadow:0 0 0 2px #0b1118;animation:sgPisca 1s steps(2) infinite}' +
    '#sigaBtn.visto .pt{display:none}' +
    '@keyframes sgPulse{0%,100%{box-shadow:0 0 0 0 rgba(214,41,118,.0),0 0 10px rgba(214,41,118,.35)}50%{box-shadow:0 0 0 4px rgba(214,41,118,.18),0 0 22px rgba(250,126,30,.55)}}' +
    '@keyframes sgPisca{50%{opacity:.25}}' +
    '#sigaBtn.solto{position:fixed;right:12px;z-index:9990;height:40px;width:40px;padding:0;justify-content:center;border-radius:50%;margin:0}' +
    '#sigaBtn.solto .tx{display:none}' +
    '#sigaMenu{position:fixed;z-index:2147483000;width:280px;max-width:calc(100vw - 24px);background:#0f1520;border:1px solid #263247;border-radius:16px;padding:8px;box-shadow:0 20px 60px rgba(0,0,0,.6);font-family:Inter,system-ui,sans-serif;display:none}' +
    '#sigaMenu.on{display:block;animation:sgIn .18s ease-out}' +
    '@keyframes sgIn{from{opacity:0;transform:translateY(-6px)}}' +
    '#sigaMenu .tt{font:800 11px Inter,system-ui,sans-serif;letter-spacing:1.4px;color:#8a96a8;padding:8px 10px 6px;text-transform:uppercase}' +
    '#sigaMenu a{display:flex;align-items:center;gap:12px;padding:10px;border-radius:12px;color:#e8edf5;text-decoration:none}' +
    '#sigaMenu a:hover{background:#1a2332}' +
    '#sigaMenu .ic{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;flex-shrink:0}' +
    '#sigaMenu b{display:block;font-size:14px}#sigaMenu small{display:block;color:#8a96a8;font-size:12px;margin-top:1px}' +
    '#sigaMenu .vai{margin-left:auto;color:#5d6b80;font-size:16px}' +
    '.sg-parc{background:linear-gradient(#141a26,#141a26) padding-box,linear-gradient(45deg,#93c5fd,#3b82f6,#22d3ee,#3b82f6) border-box!important;border:2px solid transparent!important;color:#fff!important;animation:sgAzul 2.2s ease-in-out infinite!important;text-shadow:none!important}' +
    '.sg-parc::before,.sg-parc::after{display:none!important}' +
    '.sg-parc:hover{filter:brightness(1.15)}' +
    '@keyframes sgAzul{0%,100%{box-shadow:0 0 10px rgba(59,130,246,.35)}50%{box-shadow:0 0 0 4px rgba(59,130,246,.16),0 0 22px rgba(34,211,238,.55)}}' +
    '@media(max-width:900px){#sigaBtn:not(.solto){padding:0;width:var(--sg-h,40px);justify-content:center}#sigaBtn:not(.solto) .tx{display:none}}';
  function lsG(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsS(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function vis(e) { if (!e) return false; var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.top < 160 && getComputedStyle(e).visibility !== 'hidden'; }
  function acha(lista) {
    var nomes = lista || ['Sacar', 'Tour', 'Depositar'], L = document.querySelectorAll('button,a');
    for (var k = 0; k < nomes.length; k++)
      for (var i = 0; i < L.length; i++) {
        var e = L[i]; if (e.id === 'sigaBtn' || e.closest('#sigaMenu')) continue;
        var t = (window.i18n && window.i18n.orig ? window.i18n.orig(e) : e.textContent || '').replace(/[^A-Za-zÀ-ÿ ]/g, ' ').replace(/\s+/g, ' ').trim();
        if (t === nomes[k] && vis(e)) return e;
      }
    return null;
  }
  var btn, menu;
  function montar() {
    if (document.getElementById('sigaBtn')) return;
    var s = document.createElement('style'); s.id = 'siga-css'; s.textContent = CSS; document.head.appendChild(s);
    btn = document.createElement('button'); btn.type = 'button'; btn.id = 'sigaBtn'; btn.setAttribute('aria-label', 'Siga a gente nas redes');
    btn.innerHTML = '<span class="ig">' + REDES[0].s + '</span><span class="tx">Siga a gente</span><span class="pt"></span>';
    if (lsG('siga_visto')) btn.classList.add('visto');
    menu = document.createElement('div'); menu.id = 'sigaMenu'; menu.setAttribute('role', 'menu');
    menu.innerHTML = '<div class="tt">Siga a gente nas redes</div>' + REDES.map(function (r) {
      return '<a href="' + r.u + '" target="_blank" rel="noopener" data-r="' + r.id + '"><span class="ic" style="background:' + r.c + '">' + r.s + '</span><span><b>' + r.n + '</b><small>' + r.d + '</small></span><span class="vai">↗</span></a>';
    }).join('');
    document.body.appendChild(menu);
    btn.addEventListener('click', function (e) { e.stopPropagation(); menu.classList.contains('on') ? fecha() : abre(); });
    menu.addEventListener('click', function (e) {
      var a = e.target.closest('a'); if (!a) return;
      try { window.fbq && window.fbq('trackCustom', 'SigaRedes', { rede: a.getAttribute('data-r') }); } catch (x) {}
      fecha();
    });
    document.addEventListener('click', function (e) { if (menu.classList.contains('on') && !menu.contains(e.target)) fecha(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') fecha(); });
    window.addEventListener('resize', function () { lugar(); if (menu.classList.contains('on')) posMenu(); });
    lugar();
    var n = 0, t = setInterval(function () { lugar(); if (++n > 20) clearInterval(t); }, 500);   // a barra de cima monta depois
  }
  function lugar() {
    var pc = acha(['Seja parceiro']); if (pc) pc.classList.add('sg-parc');   /* PARCEIRO-BORDA-V1 */
    var ref = acha();
    if (ref) {
      if (btn.nextSibling !== ref || btn.parentNode !== ref.parentNode) ref.parentNode.insertBefore(btn, ref);
      btn.classList.remove('solto'); btn.style.top = '';
      var h = ref.getBoundingClientRect().height; if (h > 24) btn.style.setProperty('--sg-h', Math.round(h) + 'px');
    } else {
      if (btn.parentNode !== document.body) document.body.appendChild(btn);
      btn.classList.add('solto');
      var tb = document.querySelector('.v3-topbar,.topbar,header'); var b = tb ? tb.getBoundingClientRect().bottom : 60;
      btn.style.top = Math.max(8, Math.min(140, b + 8)) + 'px';
    }
  }
  function posMenu() {
    var r = btn.getBoundingClientRect(), w = menu.offsetWidth || 280;
    menu.style.top = Math.round(r.bottom + 8) + 'px';
    menu.style.left = Math.round(Math.max(12, Math.min(innerWidth - w - 12, r.left + r.width / 2 - w / 2))) + 'px';
  }
  function abre() { menu.classList.add('on'); posMenu(); btn.classList.add('visto'); lsS('siga_visto', '1'); }
  function fecha() { menu.classList.remove('on'); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', montar); else montar();
})();
