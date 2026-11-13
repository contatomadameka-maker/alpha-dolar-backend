/* ALPHA-TOUR-V2 — tour guiado no primeiro acesso ao painel de operação.
 * PC: igual a V1. Celular (<=768px): cards compactos perto do item, abre o menu ☰ e apresenta os itens.
 * Aparece uma vez por usuário (e-mail do login) neste navegador.
 * Para ver de novo: abra o painel com ?tour=1 no endereço ou rode AlphaTour.iniciar() no console.
 */
(function () {
  'use strict';
  if (window.AlphaTour) return;

  function ls(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
  function chave() { return 'alpha_tour_v1_' + ((ls('alpha_email') || 'anon').toLowerCase()); }
  function MOB() { return innerWidth <= 768; }

  /* ---------- achar os elementos da página ---------- */
  function visivel(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) return false;
    var cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none' && r.right > 0 && r.left < innerWidth;
  }
  function porTexto(rx, sel) {
    var L = document.querySelectorAll(sel || 'button,a,span,div'), melhor = null, area = Infinity;
    for (var i = 0; i < L.length; i++) {
      var el = L[i], t = (window.i18n && window.i18n.orig ? window.i18n.orig(el) : (el.textContent || '')).trim(); /* TOUR-I18N-V1 */
      if (t.length > 60 || !rx.test(t) || !visivel(el)) continue;
      var r = el.getBoundingClientRect(), a = r.width * r.height;
      if (a < area) { area = a; melhor = el; }
    }
    return melhor;
  }
  function q(sel) { var el = document.querySelector(sel); return visivel(el) ? el : null; }
  function painelIA() {
    var t = porTexto(/^Motor de negocia/i, 'div,span,small,p');
    if (!t) return null;
    var n = t, best = null;
    for (var i = 0; i < 12 && n && n !== document.body; i++, n = n.parentElement) {
      var r = n.getBoundingClientRect();
      if (r.height > 320 && r.width < innerWidth * 0.97) { best = n; break; }
    }
    if (!best && MOB()) return t; // no celular o painel ocupa a tela toda: destaca o título
    return best;
  }
  function contaDemoReal() {
    var d = porTexto(/^demo$/i, 'button,a,span'), r = porTexto(/^real$/i, 'button,a,span');
    if (!d || !r) return d || null;
    var n = d.parentElement;
    for (var i = 0; i < 4 && n; i++, n = n.parentElement) if (n.contains(r)) return n;
    return d;
  }
  var A = {
    videos: function () { return q('.v3-rail a[href*="videos"]'); },
    ia: function () { return q('.v3-rail [data-grp="ia"].v3-grp') || q('.v3-rail .v3-grp'); },
    grafico: function () { return q('.v3-rail a[href*="grafico"]'); },
    loja: function () { return q('.v3-rail a[href*="loja"]'); },
    vip: function () { return q('.v3-rail a[href*="sinais-vip"]') || A.ia(); },   /* TOUR-VIP-V1 */
    suporte: function () { return q('.v3-rail a[href*="wa.me"]'); }
  };

  /* ---------- passos do PC (iguais à V1) ---------- */
  var PASSOS_PC = [
    { ic: '👋', t: 'Seja bem-vindo à Alpha Dolar!', d: 'Em 1 minuto você conhece o painel. Pode pular quando quiser e ver de novo depois.', alvo: null },
    { ic: '🧭', t: 'Este é o menu principal', d: 'Todos os robôs e ferramentas ficam aqui. Passe o mouse ou toque nos ícones para abrir cada um.', alvo: function () { return q('.v3-rail'); } },
    { ic: '🎬', t: 'Assista aos vídeos primeiro', d: 'Antes de operar, veja os tutoriais: eles mostram como cada robô funciona e como usar o gerenciamento de risco.', alvo: A.videos },
    { ic: '🤖', t: 'Robôs de IA', d: 'Clique aqui para ver todos os robôs: IA Pro, Avançado, Contextual, Enxame, Dígitos, Touch e outros.', alvo: A.ia },
    { ic: '☁️', t: 'Robô Sinais VIP', d: 'Aqui fica o robô de sinais. Entre no grupo do robô de sinais: ligue uma vez e ele segue a sala de sinais na nuvem, com entrada em % da banca. Os mesmos sinais chegam no nosso canal do Telegram.', alvo: A.vip, link: 'https://t.me/+YHItYk9rqLAxZjRh', linkT: '📣 Entrar no canal de sinais do Telegram' },
    { ic: '📈', t: 'Gráfico ao vivo', d: 'Acompanhe o mercado em tempo real e opere manualmente pelo gráfico, com indicadores e sinais.', alvo: A.grafico },
    { ic: '⚙️', t: 'Painel do robô', d: 'Escolha o mercado, a estratégia, a entrada, a meta e o limite de perda. Depois é só clicar em Iniciar robô.', alvo: painelIA },
    { ic: '🎮', t: 'Comece pela conta Demo', d: 'Na Demo você opera com dinheiro virtual, sem risco, em todas as ferramentas. A conta Real é liberada com um plano.', alvo: contaDemoReal },
    { ic: '🛒', t: 'Loja e planos', d: 'Aqui você conhece os planos para liberar as ferramentas na conta real.', alvo: A.loja },
    { ic: '💬', t: 'Precisa de ajuda?', d: 'Nosso suporte atende pelo WhatsApp. É só clicar aqui.', alvo: A.suporte },
    { ic: '🚀', t: 'Tudo pronto!', d: 'Recomendamos assistir aos vídeos antes da primeira operação. Bons trades e lembre-se: sempre use limite de perda.', alvo: null, fim: true }
  ];

  /* ---------- passos do celular ---------- */
  var PASSOS_MOB = [
    { ic: '👋', t: 'Bem-vindo à Alpha Dolar!', d: 'Um tour rápido pelo painel. Pode pular quando quiser.', alvo: null },
    { ic: '☰', t: 'Aqui fica o menu', d: 'No celular o menu fica escondido. Toque neste botão no topo para abrir os robôs e as ferramentas.', alvo: function () { return q('#btnHome'); } },
    { ic: '🎬', t: 'Comece pelos vídeos', d: 'Abrimos o menu para você. Em Tutoriais estão os vídeos que mostram como cada robô funciona.', alvo: A.videos, menu: true },
    { ic: '🤖', t: 'Robôs de IA', d: 'Toque aqui para ver todos os robôs: IA Pro, Avançado, Contextual, Enxame, Dígitos, Touch e outros.', alvo: A.ia, menu: true },
    { ic: '☁️', t: 'Robô Sinais VIP', d: 'Toque aqui para entrar no grupo do robô de sinais: ele segue a sala de sinais na nuvem. Os sinais também chegam no nosso canal do Telegram.', alvo: A.vip, menu: true, link: 'https://t.me/+YHItYk9rqLAxZjRh', linkT: '📣 Entrar no canal de sinais do Telegram' },
    { ic: '📈', t: 'Gráfico ao vivo', d: 'Mercado em tempo real, com operação manual pelo gráfico.', alvo: A.grafico, menu: true },
    { ic: '🛒', t: 'Loja e planos', d: 'Os planos que liberam as ferramentas na conta real.', alvo: A.loja, menu: true },
    { ic: '💬', t: 'Precisa de ajuda?', d: 'Suporte pelo WhatsApp, direto por aqui.', alvo: A.suporte, menu: true },
    { ic: '⚙️', t: 'Painel do robô', d: 'De volta à tela principal: escolha mercado, estratégia, entrada, meta e limite de perda, e toque em Iniciar robô.', alvo: painelIA },
    { ic: '🎮', t: 'Comece pela Demo', d: 'Na Demo você opera com dinheiro virtual, sem risco. A conta Real é liberada com um plano.', alvo: contaDemoReal },
    { ic: '🚀', t: 'Tudo pronto!', d: 'Assista aos vídeos antes da primeira operação e sempre use limite de perda. Bons trades!', alvo: null, fim: true }
  ];
  function lista() { return MOB() ? PASSOS_MOB : PASSOS_PC; }

  /* ---------- menu do celular ---------- */
  function menuAberto() { return !!q('.v3-rail'); }
  function menu(quer) {
    try { if (quer !== menuAberto() && typeof window.toggleRail === 'function') window.toggleRail(); } catch (e) {}
  }

  /* ---------- visual ---------- */
  var CSS = '' +
    '#atour-ov{position:fixed;inset:0;z-index:2147483600;pointer-events:auto}' +
    '#atour-hole{position:fixed;border-radius:14px;box-shadow:0 0 0 9999px rgba(3,6,12,.78),0 0 0 2px rgba(245,197,66,.9),0 0 30px 6px rgba(245,197,66,.35);transition:all .35s cubic-bezier(.2,.8,.2,1);pointer-events:none}' +
    '#atour-hole.sem{box-shadow:0 0 0 9999px rgba(3,6,12,.82);width:0!important;height:0!important;left:50%!important;top:50%!important}' +
    '#atour-card{position:fixed;z-index:2147483601;width:360px;max-width:calc(100vw - 32px);background:linear-gradient(180deg,#121a26,#0b1118);border:1px solid rgba(245,197,66,.4);border-radius:18px;padding:20px 20px 16px;color:#e8edf5;font-family:Inter,system-ui,sans-serif;box-shadow:0 24px 70px rgba(0,0,0,.6);transition:top .35s,left .35s,opacity .2s;opacity:0}' +
    '#atour-card.on{opacity:1}' +
    '#atour-card .ic{width:52px;height:52px;border-radius:14px;display:grid;place-items:center;font-size:26px;background:radial-gradient(circle at 30% 30%,rgba(245,197,66,.35),rgba(34,211,165,.12));border:1px solid rgba(245,197,66,.35);margin-bottom:12px}' +
    '#atour-card h3{margin:0 0 6px;font:800 17px Inter,system-ui,sans-serif;color:#fff}' +
    '#atour-card p{margin:0;font-size:13.5px;line-height:1.55;color:#b8c4d0}' +
    '#atour-card .dots{display:flex;gap:5px;margin:16px 0 14px}' +
    '#atour-card .dots i{height:4px;flex:1;border-radius:4px;background:#243042;transition:background .2s}' +
    '#atour-card .dots i.on{background:linear-gradient(90deg,#f5c542,#22d3a5)}' +
    '#atour-card .bt{display:flex;gap:8px;align-items:center}' +
    '#atour-card button{border:0;border-radius:10px;padding:10px 14px;font:800 13px Inter,system-ui,sans-serif;cursor:pointer}' +
    '#atour-card .pular{background:transparent;color:#7d8899;padding-left:0;margin-right:auto}' +
    '#atour-card .volta{background:rgba(255,255,255,.05);color:#cbd5e1;border:1px solid #243042}' +
    '#atour-card .prox{background:linear-gradient(135deg,#f5c542,#d4a017);color:#111;min-width:110px}' +
    '#atour-card .vid{background:linear-gradient(135deg,#22d3a5,#14a37f);color:#06100c;flex:1}' +
    '#atour-card .cnt{font:700 11px "Space Mono",ui-monospace,monospace;color:#7d8899;letter-spacing:1px;position:absolute;top:20px;right:20px}' +
    '#atour-card .seta{position:absolute;width:14px;height:14px;background:#121a26;border-left:1px solid rgba(245,197,66,.4);border-top:1px solid rgba(245,197,66,.4);transform:rotate(45deg)}' +
    /* celular: card compacto, posicionado perto do item pelo JS */
    '#atour-card .tg{display:block;margin-top:12px;padding:10px 12px;border-radius:10px;text-align:center;font:800 13px Inter,system-ui,sans-serif;color:#fff;text-decoration:none;background:linear-gradient(135deg,#2aabee,#1c86c4);box-shadow:0 6px 18px rgba(42,171,238,.25)}' +
    '@media(max-width:768px){' +
      '#atour-card .tg{margin-top:9px;padding:8px 10px;font-size:12px;border-radius:9px}' +
      '#atour-card{left:12px!important;right:12px;width:auto;max-width:none;padding:13px 14px 11px;border-radius:14px}' +
      '#atour-card .top{display:flex;align-items:center;gap:10px;margin-bottom:6px;padding-right:34px}' +
      '#atour-card .ic{width:34px;height:34px;font-size:17px;border-radius:10px;margin:0;flex-shrink:0}' +
      '#atour-card h3{font-size:14.5px;margin:0}' +
      '#atour-card p{font-size:12.5px;line-height:1.45}' +
      '#atour-card .dots{margin:10px 0 9px;gap:4px}' +
      '#atour-card .dots i{height:3px}' +
      '#atour-card button{padding:8px 11px;font-size:12px;border-radius:9px}' +
      '#atour-card .prox{min-width:92px}' +
      '#atour-card .cnt{top:14px;right:14px;font-size:10px}' +
      '#atour-card .seta{width:12px;height:12px}' +
    '}';

  var st = { i: 0, ov: null, hole: null, card: null, ativo: false, tm: null };

  function montar() {
    if (!document.getElementById('atour-css')) { var s = document.createElement('style'); s.id = 'atour-css'; s.textContent = CSS; document.head.appendChild(s); }
    st.ov = document.createElement('div'); st.ov.id = 'atour-ov';
    st.hole = document.createElement('div'); st.hole.id = 'atour-hole';
    st.card = document.createElement('div'); st.card.id = 'atour-card'; st.card.setAttribute('role', 'dialog'); st.card.setAttribute('aria-modal', 'true');
    st.ov.appendChild(st.hole); document.body.appendChild(st.ov); document.body.appendChild(st.card);
    st.ov.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); });
    // o menu do celular fecha com toque fora dele: o toque no card nao pode chegar la
    st.card.addEventListener('click', function (e) { e.stopPropagation(); });
    document.addEventListener('keydown', tecla, true);
    window.addEventListener('resize', posicionar);
  }
  function tecla(e) {
    if (!st.ativo) return;
    if (e.key === 'Escape') { e.preventDefault(); fechar(); }
    else if (e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); ir(1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); ir(-1); }
  }
  function alvoDo(p) { try { return p.alvo ? p.alvo() : null; } catch (e) { return null; } }

  function render() {
    var p = lista()[st.i];
    clearTimeout(st.tm);
    if (MOB()) {
      var mudou = (p.menu === true) !== menuAberto();
      menu(p.menu === true);
      st.card.classList.remove('on');
      st.tm = setTimeout(desenhar, mudou ? 420 : 60);
    } else desenhar();
  }
  function desenhar() {
    if (!st.ativo) return;
    var P = lista(), p = P[st.i], n = P.length, el = alvoDo(p), mob = MOB();
    var desc = (!el && p.mob && innerWidth <= 900) ? p.mob : p.d;
    var dots = ''; for (var k = 0; k < n; k++) dots += '<i class="' + (k <= st.i ? 'on' : '') + '"></i>';
    var topo = mob
      ? '<div class="top"><div class="ic">' + p.ic + '</div><h3>' + p.t + '</h3></div>'
      : '<div class="ic">' + p.ic + '</div><h3>' + p.t + '</h3>';
    st.card.innerHTML = '<span class="seta"></span><span class="cnt">' + (st.i + 1) + '/' + n + '</span>' + topo + '<p>' + desc + '</p>' + (p.link ? '<a class="tg" href="' + p.link + '" target="_blank" rel="noopener">' + p.linkT + '</a>' : '') + '<div class="dots">' + dots + '</div>' +
      (p.fim
        ? '<div class="bt"><button type="button" class="volta" data-a="-1">Voltar</button><button type="button" class="vid" data-a="vid">▶ Ver os vídeos</button><button type="button" class="prox" data-a="fim">Começar</button></div>'
        : '<div class="bt"><button type="button" class="pular" data-a="pular">Pular tour</button>' + (st.i > 0 ? '<button type="button" class="volta" data-a="-1">Voltar</button>' : '') + '<button type="button" class="prox" data-a="1">' + (st.i === 0 ? 'Começar →' : 'Próximo →') + '</button></div>');
    st.card.querySelectorAll('button').forEach(function (b) {
      b.onclick = function () {
        var a = b.getAttribute('data-a');
        if (a === 'pular' || a === 'fim') fechar();
        else if (a === 'vid') { fechar(); location.href = '/videos.html'; }
        else ir(+a);
      };
    });
    st.alvo = el;
    if (el) { try { el.scrollIntoView({ block: mob ? 'center' : 'nearest', behavior: 'smooth' }); } catch (e) {} }
    setTimeout(function () { posicionar(); st.card && st.card.classList.add('on'); }, el ? 300 : 0);
    try { st.card.querySelector('.prox').focus({ preventScroll: true }); } catch (e) {}
  }
  function posicionar() {
    if (!st.ativo || !st.card) return;
    var el = st.alvo, h = st.hole, c = st.card, pad = MOB() ? 6 : 8;
    var seta = c.querySelector('.seta');
    if (!el || !visivel(el)) {
      h.className = 'sem';
      if (!MOB()) c.style.left = Math.max(16, (innerWidth - c.offsetWidth) / 2) + 'px';
      c.style.top = Math.max(16, (innerHeight - c.offsetHeight) / 2) + 'px';
      if (seta) seta.style.display = 'none';
      return;
    }
    var r = el.getBoundingClientRect();
    h.className = '';
    h.style.left = (r.left - pad) + 'px'; h.style.top = (r.top - pad) + 'px';
    h.style.width = (r.width + pad * 2) + 'px'; h.style.height = (r.height + pad * 2) + 'px';
    var cw = c.offsetWidth, ch = c.offsetHeight, x, y, lado;
    if (MOB()) {
      // celular: card logo abaixo do item (ou acima, se nao couber), nunca em cima dele
      var cx = c.getBoundingClientRect().left;
      var abaixo = r.bottom + pad + 14, acima = r.top - pad - 14 - ch;
      if (abaixo + ch <= innerHeight - 12) { y = abaixo; lado = 'baixo'; }
      else if (acima >= 12) { y = acima; lado = 'cima'; }
      else { y = Math.max(12, innerHeight - ch - 12); lado = null; }
      c.style.top = y + 'px';
      if (seta) {
        if (!lado) { seta.style.display = 'none'; return; }
        seta.style.display = '';
        seta.style.left = seta.style.top = seta.style.right = seta.style.bottom = '';
        seta.style.left = Math.max(14, Math.min(cw - 26, r.left + r.width / 2 - cx - 6)) + 'px';
        if (lado === 'baixo') { seta.style.top = '-7px'; seta.style.transform = 'rotate(45deg)'; }
        else { seta.style.bottom = '-7px'; seta.style.transform = 'rotate(225deg)'; }
      }
      return;
    }
    if (r.right + 20 + cw < innerWidth - 16) { lado = 'dir'; x = r.right + 20; y = r.top + r.height / 2 - ch / 2; }
    else if (r.left - 20 - cw > 16) { lado = 'esq'; x = r.left - 20 - cw; y = r.top + r.height / 2 - ch / 2; }
    else if (r.bottom + 20 + ch < innerHeight - 16) { lado = 'baixo'; x = r.left + r.width / 2 - cw / 2; y = r.bottom + 20; }
    else { lado = 'cima'; x = r.left + r.width / 2 - cw / 2; y = r.top - 20 - ch; }
    x = Math.max(16, Math.min(innerWidth - cw - 16, x)); y = Math.max(16, Math.min(innerHeight - ch - 16, y));
    c.style.left = x + 'px'; c.style.top = y + 'px';
    if (seta) {
      seta.style.display = '';
      seta.style.left = seta.style.top = seta.style.right = seta.style.bottom = '';
      if (lado === 'dir') { seta.style.left = '-8px'; seta.style.top = Math.max(18, Math.min(ch - 30, r.top + r.height / 2 - y - 7)) + 'px'; seta.style.transform = 'rotate(-45deg)'; }
      else if (lado === 'esq') { seta.style.right = '-8px'; seta.style.top = Math.max(18, Math.min(ch - 30, r.top + r.height / 2 - y - 7)) + 'px'; seta.style.transform = 'rotate(135deg)'; }
      else if (lado === 'baixo') { seta.style.top = '-8px'; seta.style.left = Math.max(18, Math.min(cw - 30, r.left + r.width / 2 - x - 7)) + 'px'; seta.style.transform = 'rotate(45deg)'; }
      else { seta.style.bottom = '-8px'; seta.style.left = Math.max(18, Math.min(cw - 30, r.left + r.width / 2 - x - 7)) + 'px'; seta.style.transform = 'rotate(225deg)'; }
    }
  }
  function ir(d) {
    var P = lista(), n = st.i + d;
    // PC: pula passos cujo elemento não existe nesta página. Celular: os itens do menu só aparecem depois de abri-lo, então não pula.
    if (!MOB()) while (n > 0 && n < P.length - 1 && P[n].alvo && !alvoDo(P[n])) n += d > 0 ? 1 : -1;
    if (n < 0) n = 0;
    if (n >= P.length) { fechar(); return; }
    st.i = n; render();
  }
  function fechar() {
    clearTimeout(st.tm);
    var estavaAtivo = st.ativo;
    st.ativo = false; ls(chave(), '1');
    if (st.ov) st.ov.remove(); if (st.card) st.card.remove();
    st.ov = st.card = st.hole = null;
    document.removeEventListener('keydown', tecla, true);
    window.removeEventListener('resize', posicionar);
    if (estavaAtivo && MOB()) menu(false);
  }
  function iniciar() {
    if (st.ativo) return;
    st.ativo = true; st.i = 0; montar(); render();
  }
  window.AlphaTour = { iniciar: iniciar, fechar: fechar, resetar: function () { try { localStorage.removeItem(chave()); } catch (e) {} } };

  function talvez() {
    var forcar = /[?&]tour=1\b/.test(location.search);
    if (!forcar && ls(chave())) return;
    if (document.getElementById('login-screen') && visivel(document.getElementById('login-screen'))) return;
    iniciar();
  }
  if (document.readyState === 'complete') setTimeout(talvez, 1800);
  else window.addEventListener('load', function () { setTimeout(talvez, 1800); });
})();
