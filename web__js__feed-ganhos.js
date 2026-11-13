/* Alpha Dolar — Feed de ganhos reais
 * - AlphaFeed.registrar({...}) envia um ganho real ao backend (usado pelos robôs do navegador)
 * - Mostra no canto da tela os últimos ganhos reais da plataforma (nome abreviado, selo DEMO/REAL)
 * Para só registrar, sem mostrar cartões: <script src="/js/feed-ganhos.js" data-toast="off"></script>
 */
(function () {
  'use strict';
  var BACKEND = 'https://alpha-dolar-backend.onrender.com';
  var me = document.currentScript;
  var TOAST = !(me && me.getAttribute('data-toast') === 'off');
  var SO_REAL = false; // mude para true para mostrar só ganhos de conta REAL

  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function nomeUsuario() {
    var keys = ['alpha_nome', 'alpha_perfil_nome', 'perfil_nome', 'deriv_fullname', 'user_name', 'nome'];
    for (var i = 0; i < keys.length; i++) { var v = ls(keys[i]); if (v && v.trim().length > 1) return v.trim(); }
    return '';
  }
  function contaAtiva() {
    var tipo = ls('deriv_conta_ativa') || 'demo';
    try {
      var arr = JSON.parse(ls('deriv_accounts') || '[]');
      var c = arr.find(function (a) { return tipo === 'real' ? !a.isDemo : a.isDemo; }) || arr[0];
      if (c) return { id: c.acct, tipo: c.isDemo ? 'demo' : 'real' };
    } catch (e) {}
    return { id: '', tipo: tipo };
  }

  // ─── registro (só ganhos) ───
  window.AlphaFeed = {
    registrar: function (o) {
      try {
        var lucro = parseFloat(o.lucro);
        if (!(lucro > 0) || !o.contract_id) return;
        var ca = contaAtiva();
        fetch(BACKEND + '/api/feed/ganho', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, keepalive: true,
          body: JSON.stringify({
            deriv_id: o.deriv_id || ca.id, conta: o.conta || ca.tipo, nome: o.nome || nomeUsuario(),
            bot: o.bot || '', mercado: o.mercado || '', lucro: lucro, stake: o.stake || 0, contract_id: String(o.contract_id)
          })
        }).catch(function () {});
      } catch (e) {}
    }
  };
  if (!TOAST) return;

  // ─── cartões ───
  var css = document.createElement('style');
  css.textContent =
    '#afeed{position:fixed;right:16px;top:calc(var(--tb-h, 70px) + 10px);z-index:9000;pointer-events:none;font-family:Inter,"Segoe UI",system-ui,sans-serif}' +
    '.afeed-card{pointer-events:auto;display:flex;align-items:center;gap:9px;width:240px;max-width:calc(100vw - 24px);box-sizing:border-box;padding:8px 26px 8px 10px;border-radius:12px;' +
    'background:rgba(20,22,28,.95);border:1px solid rgba(108,92,231,.3);box-shadow:0 8px 24px rgba(0,0,0,.4);' +
    '-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);transform:translateX(24px);opacity:0;transition:transform .35s cubic-bezier(.2,.9,.3,1.2),opacity .3s}' +
    '.afeed-card.in{transform:none;opacity:1}' +
    '.afeed-av{width:30px;height:30px;border-radius:9px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:12px;color:#fff;background:linear-gradient(135deg,#6366f1,#8b5cf6)}' +
    '.afeed-tx{flex:1;min-width:0;display:flex;flex-direction:column;gap:1px}' +
    '.afeed-top{display:flex;align-items:center;gap:5px;font-size:11.5px;font-weight:800;color:#e2e8f0;white-space:nowrap}' +
    '.afeed-top small{font-size:9.5px;font-weight:600;color:#64748b}' +
    '.afeed-val{font-family:"Space Mono",ui-monospace,monospace;font-size:13.5px;font-weight:700;color:#4ade80}' +
    '.afeed-sub{font-size:10px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.afeed-tag{font-size:8px;font-weight:900;letter-spacing:.4px;padding:1px 5px;border-radius:5px;margin-left:auto}' +
    '.afeed-tag.real{background:rgba(245,158,11,.15);color:#fbbf24;border:1px solid rgba(245,158,11,.4)}' +
    '.afeed-tag.demo{background:rgba(148,163,184,.12);color:#94a3b8;border:1px solid rgba(148,163,184,.3)}' +
    '.afeed-x{position:absolute;top:4px;right:6px;background:none;border:0;color:#475569;font-size:13px;cursor:pointer;line-height:1;padding:2px}' +
    '.afeed-lbl{display:none}' +
    '@media (max-width:600px){#afeed{right:10px;top:calc(var(--tb-h, 60px) + 8px)}.afeed-card{width:210px;padding:7px 24px 7px 8px}.afeed-av{width:26px;height:26px;font-size:11px}.afeed-val{font-size:12.5px}}';
  document.head.appendChild(css);

  var box, fila = [], vistos = {}, mostrando = false;
  try { if (sessionStorage.getItem('afeed_off') === '1') return; } catch (e) {}
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]; }); }
  function mercadoNome(s) {
    s = String(s || ''); var m;
    if ((m = s.match(/^R_(\d+)$/))) return 'Volatility ' + m[1];
    if ((m = s.match(/^1HZ(\d+)V$/))) return 'Volatility ' + m[1] + ' (1s)';
    if ((m = s.match(/^JD(\d+)$/))) return 'Jump ' + m[1];
    return s;
  }
  function tempo(iso) {
    var t = Date.parse(iso || ''); if (!t) return 'agora';
    var s = Math.max(0, (Date.now() - t) / 1000);
    if (s < 60) return 'agora'; if (s < 3600) return 'há ' + Math.floor(s / 60) + ' min';
    if (s < 86400) return 'há ' + Math.floor(s / 3600) + ' h'; return 'há ' + Math.floor(s / 86400) + ' d';
  }
  function mostrar() {
    if (mostrando || !fila.length) return;
    mostrando = true;
    var it = fila.shift();
    if (!box) { box = document.createElement('div'); box.id = 'afeed'; box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    var ini = (String(it.nome || 'T').replace(/[^A-Za-z\u00C0-\u00FA]/g, '')[0] || 'T').toUpperCase();
    var card = document.createElement('div');
    card.className = 'afeed-card'; card.style.position = 'relative';
    card.innerHTML =
      '<div class="afeed-av">' + esc(ini) + '</div>' +
      '<div class="afeed-tx">' +
        '<span class="afeed-lbl">Ganho recente</span>' +
        '<div class="afeed-top">' + esc(it.nome) + ' <small>' + esc(tempo(it.quando)) + '</small>' +
          '<span class="afeed-tag ' + (it.conta === 'real' ? 'real' : 'demo') + '">' + (it.conta === 'real' ? 'REAL' : 'DEMO') + '</span></div>' +
        '<span class="afeed-val">+$' + Number(it.lucro).toFixed(2) + '</span>' +
        '<span class="afeed-sub">' + esc([it.bot, mercadoNome(it.mercado)].filter(Boolean).join(' · ')) + '</span>' +
      '</div>' +
      '<button class="afeed-x" aria-label="Ocultar ganhos recentes">×</button>';
    card.querySelector('.afeed-x').onclick = function () { try { sessionStorage.setItem('afeed_off', '1'); } catch (e) {} box.remove(); fila = []; };
    box.innerHTML = ''; box.appendChild(card);
    requestAnimationFrame(function () { card.classList.add('in'); });
    setTimeout(function () { card.classList.remove('in'); setTimeout(function () { card.remove(); mostrando = false; setTimeout(mostrar, 6000); }, 400); }, 5500);
  }
  function buscar() {
    fetch(BACKEND + '/api/feed/ganhos?limit=30').then(function (r) { return r.json(); }).then(function (j) {
      var novos = (j.itens || []).filter(function (x) {
        var k = [x.nome, x.lucro, x.quando].join('|');
        if (vistos[k]) return false; vistos[k] = 1;
        return Date.now() - Date.parse(x.quando || 0) < 24 * 3600 * 1000;
      });
      novos.reverse();
      var reais = novos.filter(function (x) { return x.conta === 'real'; });
      var demos = novos.filter(function (x) { return x.conta !== 'real'; });
      if (SO_REAL) demos = [];
      fila = reais.concat(fila, demos).slice(0, 15);
      mostrar();
    }).catch(function () {});
  }
  setTimeout(buscar, 4000);
  setInterval(buscar, 45000);
})();
