/* LOGIN-VOLTA-V3 (V2 + não confia em aba.closed: a Deriv usa COOP e a aba parece fechada na hora) — login da Deriv em outra aba + conclusão automática
 * A Deriv às vezes larga a pessoa no painel dela (home.deriv.com/dashboard/home) depois do login,
 * sem voltar para o site (acontece também na DC Bots). Mas, depois disso, a pessoa JÁ está logada
 * na Deriv: um novo pedido de login volta na hora, sem senha. Então:
 * - "Entrar com Deriv" abre a Deriv em OUTRA aba; esta aba fica esperando.
 * - Deu certo na outra aba → o token aparece aqui também e esta aba segue para o painel.
 * - Ficou presa → quando a pessoa fecha a aba da Deriv ou volta para cá, esta aba refaz o pedido
 *   sozinha e conclui (sem afiliado na nova tentativa).
 * - Celular/navegador que bloqueia a aba nova → mesma aba; ao voltar ao site, conclui sozinho.
 * - www.alphadolar.online → alphadolar.online.
 */
(function () {
  'use strict';
  if (window.__loginVolta) return; window.__loginVolta = true;
  var K = 'alpha_oauth_pendente', JANELA = 20 * 60 * 1000, MAX = 2;
  function lsG() { try { return JSON.parse(localStorage.getItem(K) || 'null'); } catch (e) { return null; } }
  function lsS(v) { try { if (v) localStorage.setItem(K, JSON.stringify(v)); else localStorage.removeItem(K); } catch (e) {} }
  function temToken() { try { return /^ory_at_/.test(localStorage.getItem('deriv_bearer_token') || ''); } catch (e) { return false; } }
  function painel() { try { return window.__destino ? window.__destino('/dashboard') : '/dashboard'; } catch (e) { return '/dashboard'; } }
  var q = new URLSearchParams(location.search);

  if (/^www\./i.test(location.hostname) && /alphadolar\.online$/i.test(location.hostname)) {
    location.replace(location.protocol + '//' + location.hostname.replace(/^www\./i, '') + location.pathname + location.search + location.hash);
    return;
  }
  /* aba que voltou da Deriv com o code: deixa o login.html concluir; se foi aberta por nós, fecha e avisa a aba de origem */
  if (q.has('code') || q.has('acct1')) {
    lsS(null);
    var n0 = 0, t0 = setInterval(function () {
      if (++n0 > 120) return clearInterval(t0);
      if (!temToken()) return;
      clearInterval(t0);
      try { if (window.opener && !window.opener.closed && window.opener.location.host === location.host) { window.opener.focus(); setTimeout(function () { window.close(); }, 1500); } } catch (e) {}
    }, 500);
    return;
  }

  var aba = null, vigia = null, ov = null, tmr = null, semAfiliado = false, orig = window.getOAuthURL;
  function urlNova() {
    if (typeof orig !== 'function') return Promise.reject(new Error('sem getOAuthURL'));
    return Promise.resolve(orig()).then(function (u) {
      if (semAfiliado) u = String(u).replace(/([?&])t=[^&]*&?/, '$1').replace(/[?&]$/, '');
      return u;
    });
  }
  function marca() { var p = lsG(); var n = p && Date.now() - p.t < JANELA ? (p.n || 0) + 1 : 1; lsS({ t: Date.now(), n: n }); return n; }
  function fechar() { if (ov) ov.remove(); ov = null; clearInterval(tmr); }
  function caixa(ic, tit, txt, bt1, bt2) {
    fechar();
    ov = document.createElement('div');
    ov.style.cssText = 'position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(3,4,10,.84);font-family:Inter,system-ui,sans-serif';
    ov.innerHTML = '<div style="max-width:390px;width:100%;background:#0d0f1a;border:1px solid rgba(139,92,246,.4);border-radius:18px;padding:22px;text-align:center;color:#e2e8f0">' +
      '<div style="font-size:34px">' + ic + '</div><div style="font-size:17px;font-weight:800;margin:6px 0">' + tit + '</div>' +
      '<div style="font-size:13px;color:#94a3b8;line-height:1.55">' + txt + '</div>' +
      (bt1 ? '<button type="button" id="lvGo" style="width:100%;margin-top:16px;border:0;border-radius:12px;padding:13px;font:800 14px Inter,system-ui,sans-serif;color:#fff;background:linear-gradient(135deg,#7c3aed,#6366f1);cursor:pointer">' + bt1 + '</button>' : '') +
      (bt2 ? '<button type="button" id="lvNo" style="width:100%;margin-top:8px;border:1px solid #2a2d45;border-radius:12px;padding:10px;font:700 12.5px Inter,system-ui,sans-serif;color:#94a3b8;background:transparent;cursor:pointer">' + bt2 + '</button>' : '') + '</div>';
    document.body.appendChild(ov);
    var no = document.getElementById('lvNo'); if (no) no.onclick = function () { lsS(null); pararVigia(); fechar(); };
    return document.getElementById('lvGo');
  }
  function pararVigia() { clearInterval(vigia); vigia = null; }
  function irPainel() { pararVigia(); lsS(null); caixa('✅', 'Conta Deriv conectada', 'Abrindo a plataforma…'); setTimeout(function () { location.href = painel(); }, 600); }

  /* conclui nesta mesma aba (a Deriv já tem a sessão → volta direto) */
  function concluirAqui() {
    pararVigia(); semAfiliado = true;
    var n = marca();
    caixa('🔑', 'Concluindo o login…', 'Você já entrou na Deriv. Buscando a confirmação — não precisa digitar a senha de novo.');
    urlNova().then(function (u) { setTimeout(function () { location.href = u; }, 400); }).catch(function () { fechar(); });
    return n;
  }
  function esperar() {
    var go = caixa('🪟', 'Entre na aba da Deriv', 'Abrimos a Deriv em outra aba. Entre com seu e-mail e senha lá.<br><br>Se depois de entrar a Deriv ficar no painel dela, <b>é só voltar para esta aba</b> (ou fechar a da Deriv) — a gente conclui sozinho.',
      'Já entrei na Deriv · concluir', 'Cancelar');
    if (go) go.onclick = concluirAqui;
  }
  function vigiar() {
    pararVigia();
    vigia = setInterval(function () {
      if (temToken()) return irPainel();
    }, 800);
  }
  function entrar(ev) {
    if (ev) { ev.preventDefault(); ev.stopPropagation(); if (ev.stopImmediatePropagation) ev.stopImmediatePropagation(); }
    if (typeof orig !== 'function') return;
    marca();
    var w = null;
    try { w = window.open('about:blank', '_blank'); } catch (e) { w = null; }
    urlNova().then(function (u) {
      if (w && !w.closed) {
        try { w.location.href = u; aba = w; esperar(); vigiar(); return; } catch (e) {}
      }
      location.href = u; /* aba nova bloqueada: segue na mesma aba */
    });
  }

  function botao() { return Array.prototype.find.call(document.querySelectorAll('button,a'), function (x) { return /ENTRAR COM DERIV/i.test(x.textContent || ''); }) || null; }
  function preparar() {
    var b = botao(); if (!b || b.__lv) return; b.__lv = 1;
    if (typeof orig === 'function') document.addEventListener('click', function (e) { if (b.contains(e.target)) entrar(e); }, true);
    var dica = document.createElement('div');
    dica.style.cssText = 'font-size:11.5px;line-height:1.5;color:#94a3b8;margin:8px 2px 0;text-align:center';
    dica.innerHTML = 'A Deriv abre em outra aba. Se depois de entrar ela ficar no painel dela, é só fechar aquela aba e voltar aqui.';
    b.parentNode.insertBefore(dica, b.nextSibling);
  }

  /* voltou ao site sem concluir (aba única ou recarregou) */
  function checar() {
    if (temToken()) { var p0 = lsG(); if (p0) irPainel(); return; }
    if (ov || vigia) return;
    var p = lsG(); if (!p || Date.now() - p.t > JANELA) { if (p) lsS(null); return; }
    if ((p.n || 1) > MAX) {
      var go = caixa('⚠️', 'A Deriv não devolveu você para cá', 'Tente assim: abra pelo <b>navegador</b> (Chrome ou Safari) — não pelo app da Deriv nem pelo navegador do Instagram/WhatsApp — e entre com <b>e-mail e senha</b>. Se continuar, chame o suporte.', 'Tentar de novo', 'Cancelar');
      if (go) go.onclick = function () { lsS({ t: Date.now(), n: 0 }); concluirAqui(); };
      return;
    }
    var go2 = caixa('🔑', 'Falta só concluir o login', 'Você já entrou na sua conta Deriv. Vamos buscar a confirmação automaticamente — não precisa digitar a senha de novo.', 'Concluindo em 3s…', 'Cancelar');
    var s = 3; tmr = setInterval(function () { s--; if (s <= 0) { clearInterval(tmr); concluirAqui(); } else if (go2) go2.textContent = 'Concluindo em ' + s + 's…'; }, 1000);
    if (go2) go2.onclick = concluirAqui;
  }
  window.addEventListener('storage', function (e) { if (e.key === 'deriv_bearer_token' && temToken() && (vigia || lsG())) irPainel(); });
  function iniciar() { preparar(); setTimeout(checar, 400); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar); else iniciar();
  window.addEventListener('pageshow', function (e) { if (e.persisted) setTimeout(checar, 300); });
  var escondidaEm = 0, tmr2 = null;
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState !== 'visible') { escondidaEm = Date.now(); return; }
    if (vigia) {
      /* voltou para esta aba depois de um tempo na Deriv: se não chegou o token, ficou presa lá → conclui (com 3s para cancelar) */
      if (temToken()) return irPainel();
      if (escondidaEm && Date.now() - escondidaEm > 8000 && !tmr2) {
        var go3 = caixa('🔑', 'Ficou no painel da Deriv?', 'Se você já entrou na Deriv, a gente conclui o login por aqui — não precisa digitar a senha de novo.', 'Concluindo em 3s…', 'Ainda não entrei');
        var s3 = 3; tmr2 = setInterval(function () { s3--; if (s3 <= 0) { clearInterval(tmr2); tmr2 = null; concluirAqui(); } else if (go3) go3.textContent = 'Concluindo em ' + s3 + 's…'; }, 1000);
        if (go3) go3.onclick = function () { clearInterval(tmr2); tmr2 = null; concluirAqui(); };
        var no3 = document.getElementById('lvNo'); if (no3) no3.onclick = function () { clearInterval(tmr2); tmr2 = null; esperar(); };
      }
      return;
    }
    setTimeout(checar, 300);
  });
})();
