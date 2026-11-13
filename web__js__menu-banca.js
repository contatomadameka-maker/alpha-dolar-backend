/* MENU-BANCA-V2 (+MENU-SINAIS-V1) — "Robôs de IA" organizado por banca (até $100 · $100–500 · $500+), cartões menores, 3 por linha.
 * Só reorganiza os mesmos botões do menu (mesmos links e cliques). Precisa do menu-flyout.js. */
(function () {
  'use strict';
  if (window.__menuBanca) return; window.__menuBanca = true;
  var F = [
    { k: 1, t: 'Até $100', c: '#4ade80', r: 'sugerido: a partir de $20', d: 'Entrada de $0,35 a $1, um robô por vez, recuperação curta.',
      n: ['ia pro', 'avançado', 'ia avançado', 'alpha dígitos', 'alpha digitos', 'alpha pulso', 'alpha prisma', 'alpha sniper', 'auto trading', 'ia simples'] },
    { k: 2, t: '$100 a $500', c: '#38bdf8', r: 'sugerido: a partir de $100', d: 'Vários robôs juntos ou recuperação mais longa.',
      n: ['alpha sinais', 'alpha touch', 'touch squad', 'alpha colhedor', 'esquadrão', 'alpha sentinelas', 'sentinelas', 'contextual', 'ia contextual'] },
    { k: 3, t: '$500 ou mais', c: '#fbbf24', r: 'sugerido: a partir de $500', d: 'Muitos robôs juntos, multiplicadores e mercados globais.',
      n: ['alpha enxame', 'alpha global', 'alpha regente', 'alpha perfil', 'sinais mt5', 'alpha sinais mt5'] },
    { k: 4, t: 'Ferramentas', c: '#a78bfa', r: 'só leitura', d: 'Para estudar antes de operar.', n: ['scanner alpha'] }
  ];
  var css = document.createElement('style');
  css.textContent = [
    '.mfo{width:440px}',
    '.mfo .v3-grp-body.mb-on{grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:6px!important}',
    '.mfo .mb-on .v3-rail-item{min-height:58px!important;padding:8px!important;gap:5px!important;border-radius:11px!important}',
    '.mfo .mb-on .v3-rail-ico{width:26px!important;height:26px!important;min-width:26px;border-radius:8px}',
    '.mfo .mb-on .v3-rail-ico .v3-svg{width:15px;height:15px}',
    '.mfo .mb-on .v3-rail-label{font-size:11.5px!important;line-height:1.2;text-shadow:none!important}',
    '.mfo .mb-on .v3-badge{top:6px!important;right:6px!important;font-size:8px!important;padding:1px 4px!important}',
    '.mb-h{grid-column:1/-1;display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin:10px 2px 0!important}',
    '.mb-h b{font-size:12.5px;color:#f1f5f9}.mb-h b i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}',
    '.mb-h small{font-size:10px;color:#8a8fb5}.mb-d{grid-column:1/-1;font-size:10.5px;color:#9da2c8;margin:0 2px 2px!important;line-height:1.4}',
    '.mb-tabs{grid-column:1/-1;display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin:0 0 2px!important}',
    '.mb-tabs span{grid-column:1/-1;font-size:10px;font-weight:800;letter-spacing:1.1px;color:#8a8fb5;text-transform:uppercase}',
    '.mb-tabs button{border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.03);color:#a3a8cf;border-radius:9px;padding:7px 2px;font:800 11px Inter,system-ui,sans-serif;cursor:pointer}',
    '.mb-tabs button.on{background:#6d5cff;border-color:#6d5cff;color:#fff}',
    '.mb-av{grid-column:1/-1;font-size:10px;line-height:1.45;color:#9da2c8;background:rgba(251,191,36,.06);border:1px solid rgba(251,191,36,.2);border-radius:9px;padding:7px 9px;margin-top:8px!important}',
    '.mb-ok{grid-column:1/-1;display:flex;gap:9px;align-items:flex-start;font-size:11.5px;line-height:1.45;color:#dcfce7;background:rgba(74,222,128,.10);border:1px solid rgba(74,222,128,.55);border-radius:11px;padding:9px 10px;margin:0 0 4px!important;animation:mbPulse 1.6s ease-in-out infinite}',
    '.mb-ok b{color:#4ade80;display:block;font-size:12px;margin-bottom:1px}.mb-ok i{font-style:normal;font-size:16px;line-height:1}',
    '@keyframes mbPulse{0%,100%{box-shadow:0 0 0 0 rgba(74,222,128,.0);border-color:rgba(74,222,128,.45)}50%{box-shadow:0 0 14px 2px rgba(74,222,128,.45);border-color:rgba(74,222,128,1)}}',
    '@media (prefers-reduced-motion:reduce){.mb-ok{animation:none}}',
    '@media (max-width:768px){.mfo{width:auto}}'
  ].join('');
  document.head.appendChild(css);
  function nome(it) { var l = it.querySelector('.v3-rail-label'); return l ? l.textContent.trim().toLowerCase() : ''; }
  function faixa(it) { var n = nome(it); for (var i = 0; i < F.length; i++) if (F[i].n.indexOf(n) >= 0) return F[i].k; return 2; }
  var filtro = (function () { try { return localStorage.getItem('alpha_menu_banca') || 'all'; } catch (e) { return 'all'; } })();
  function montar(body) {
    if (body.__mb) return; body.__mb = true; body.classList.add('mb-on');
    var itens = Array.prototype.slice.call(body.querySelectorAll(':scope > .v3-rail-item'));
    var ok = document.createElement('div'); ok.className = 'mb-ok';
    ok.innerHTML = '<i>✅</i><div><b>Todos os robôs funcionam com qualquer banca</b>Você pode testar qualquer um na demo e rodar com valores menores. As faixas abaixo são só uma sugestão de qual robô tende a render melhor com o valor que você tem.</div>';
    body.insertBefore(ok, body.firstChild);
    var tabs = document.createElement('div'); tabs.className = 'mb-tabs';
    tabs.innerHTML = '<span>Qual é a sua banca? (sugestão)</span><button data-f="all">Todas</button><button data-f="1">Até $100</button><button data-f="2">$100–500</button><button data-f="3">$500+</button>';
    body.insertBefore(tabs, ok.nextSibling);
    var secs = {};
    F.forEach(function (f) {
      var h = document.createElement('div'); h.className = 'mb-h'; h.dataset.k = f.k;
      h.innerHTML = '<b><i style="background:' + f.c + '"></i>' + f.t + '</b><small>' + f.r + '</small>';
      var d = document.createElement('div'); d.className = 'mb-d'; d.dataset.k = f.k; d.textContent = f.d;
      body.appendChild(h); body.appendChild(d); secs[f.k] = [h, d];
      itens.filter(function (it) { return faixa(it) === f.k; }).forEach(function (it) { it.dataset.mb = f.k; body.appendChild(it); });
    });
    var av = document.createElement('div'); av.className = 'mb-av';
    av.textContent = 'A faixa é só uma recomendação de risco (nenhum robô fica bloqueado) e não é promessa de ganho: considera a entrada mínima, quantos robôs operam juntos e quanto custa uma sequência de perdas. Teste na demo antes.';
    body.appendChild(av);
    function aplica() {
      tabs.querySelectorAll('button').forEach(function (b) { b.classList.toggle('on', b.dataset.f === filtro); });
      F.forEach(function (f) {
        var vis = filtro === 'all' || String(f.k) === filtro || f.k === 4;
        secs[f.k].forEach(function (e) { e.style.display = vis ? '' : 'none'; });
        body.querySelectorAll('[data-mb="' + f.k + '"]').forEach(function (it) { it.style.display = vis ? '' : 'none'; });
        var vazio = !body.querySelector('[data-mb="' + f.k + '"]'); if (vazio) secs[f.k].forEach(function (e) { e.style.display = 'none'; });
      });
    }
    tabs.addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; e.stopPropagation(); filtro = b.dataset.f; try { localStorage.setItem('alpha_menu_banca', filtro); } catch (x) {} aplica(); });
    aplica();
  }
  function tenta(n) {
    var body = document.querySelector('.mfo .v3-grp-body[data-grp="ia"]');
    if (body) return montar(body);
    if (n < 30) setTimeout(function () { tenta(n + 1); }, 300);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(function () { tenta(0); }, 50); }); else setTimeout(function () { tenta(0); }, 50);
})();
