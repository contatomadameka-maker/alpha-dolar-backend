/* PLANO-JS-V5 — Alpha Dolar: conta DEMO livre em tudo; conta REAL exige plano.
 * Carregar como PRIMEIRO script do <head>. Bloqueia:
 *  - ordens "buy" enviadas por WebSocket numa conta real (IA Pro, Digitos, Global, Touch, Manual...)
 *  - /api/bot/start de conta real (IA Simples premium, Avancado, Enxame, Esquadrao)
 */
(function () {
  'use strict';
  if (window.AlphaPlano) return;

  var BACK = 'https://alpha-dolar-backend.onrender.com';
  var NIVEL = { free: 0, sinais: 1, pro: 2, elite: 3 };
  var NOME = ['Free', 'Alpha Sinais', 'Alpha Pro', 'Alpha Elite'];
  var SLUG = ['free', 'sinais', 'pro', 'elite'];
  var NIV_F = {
    'ia-simples': 0, 'grafico': 0, 'manual': 0,
    'sinais': 1, 'auto-trading': 1, 'digitos': 1,
    'ia-pro': 2, 'prisma': 2, 'pulso': 2, 'espectro': 2, 'sinais-vip': 1, 'diferente': 2, 'mapa-digitos': 2, 'ia-avancado': 2, 'colhedor': 2, 'sniper': 2, 'ia-contextual': 3, 'touch': 2, 'mt5': 3, 'sentinelas': 3, 'touch-squad': 3, 'global': 3, 'estrategias-premium': 2,
    'automacao': 0, 'enxame': 3, 'esquadrao': 3, 'regente': 3, 'perfil': 3, 'estrategias-vip': 3
  };
  if (!NIV_F.hasOwnProperty('touch-squad')) NIV_F['touch-squad'] = 3;  // TRAVA-TOUCH-SQUAD-V1: Touch Squad = Alpha Elite
  var NOME_F = { 'touch-squad': 'Touch Squad',
    'ia-simples': 'IA Simples', 'grafico': 'Gráfico', 'manual': 'Operação manual', 'sinais': 'Alpha Sinais',
    'auto-trading': 'Auto Trading', 'digitos': 'Alpha Dígitos', 'ia-pro': 'IA Pro', 'prisma': 'Alpha Prisma', 'pulso': 'Alpha Pulso', 'espectro': 'Alpha Espectro', 'sinais-vip': 'Alpha Sinais VIP', 'diferente': 'Alpha Diferente', 'mapa-digitos': 'Alpha Mapa de Dígitos', 'ia-avancado': 'IA Avançado', 'colhedor': 'Alpha Colhedor', 'sniper': 'Alpha Sniper',
    'ia-contextual': 'IA Contextual', 'touch': 'Alpha Touch', 'mt5': 'Alpha Sinais MT5', 'sentinelas': 'Alpha Sentinelas', 'touch-squad': 'Touch Squad', 'global': 'Alpha Global',
    'estrategias-premium': 'Estratégias Premium', 'automacao': 'Alpha Automação', 'enxame': 'Enxame', 'esquadrao': 'Esquadrão',
    'regente': 'Regente', 'perfil': 'Perfil Alpha', 'estrategias-vip': 'Estratégias VIP'
  };
  var PREMIUM = /mega_alpha_[123]|alpha_elite|alpha_nexus/i;
  var CK = 'alpha_plano_v1';

  function ls(k) { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } }
  function ehDemoId(id) { return /^(DOT|VRT|VRW)/i.test(String(id || '')); }
  function ehRealId(id) { return /^(ROT|CR|MF|MLT|MX)/i.test(String(id || '')); }

  /* ---------- plano do cliente ---------- */
  var st = { info: null, carregando: null, erro: null };
  function tokenAtual() { return ls('deriv_bearer_token'); }
  function lerCache() {
    try {
      var c = JSON.parse(sessionStorage.getItem(CK) || 'null');
      if (c && c.tk === tokenAtual().slice(-16) && Date.now() - c.t < 5 * 60 * 1000) return c.d;
    } catch (e) {}
    return null;
  }
  function carregar(forcar) {
    if (!forcar) { var c = lerCache(); if (c) { st.info = c; return Promise.resolve(c); } }
    if (st.carregando) return st.carregando;
    var f = window.__plano_fetch0 || window.fetch;
    st.carregando = f(BACK + '/api/plano', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: tokenAtual(), email: ls('alpha_email') })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.ok) throw new Error((d && d.erro) || 'falha');
      st.info = d; st.erro = null;
      try { sessionStorage.setItem(CK, JSON.stringify({ t: Date.now(), tk: tokenAtual().slice(-16), d: d })); } catch (e) {}
      return d;
    }).catch(function (e) { st.erro = e; throw e; })
      .finally(function () { st.carregando = null; });
    return st.carregando;
  }
  function pode(ferr) {
    var i = st.info; if (!i) return null; // ainda nao sei
    var n = NIV_F.hasOwnProperty(ferr) ? NIV_F[ferr] : 2; if (!NIV_F.hasOwnProperty(ferr)) { try { console.warn('[plano] ferramenta sem nivel cadastrado, exigindo plano na conta real:', ferr); } catch (e) {} }  // TRAVA-TOUCH-SQUAD-V1: desconhecida = bloqueada na real
    return i.nivel >= n || (i.ferramentas || []).indexOf(ferr) >= 0;
  }

  /* ---------- qual ferramenta esta operando ---------- */
  function visivel(id) {
    var el = document.getElementById(id); if (!el) return false;
    try { var cs = getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden' && el.getClientRects().length > 0; } catch (e) { return false; }
  }
  function ferramentaDaPagina() {
    var p = location.pathname.toLowerCase();
    if (/bot-automacao/.test(p)) return 'automacao';  // AUTOMACAO-PLANO-V1
    if (/bot-ia-pro/.test(p)) return 'ia-pro';
    if (/bot-ia-avancado/.test(p)) return 'ia-avancado';
    if (/bot-regente/.test(p)) return 'regente';
    if (/bot-perfil/.test(p)) return 'perfil';
    if (/bot-touch-squad/.test(p)) return 'touch-squad';
    if (/bot-touch/.test(p)) return 'touch';
    if (/bot-sniper/.test(p)) return 'sniper';
    if (/bot-sinais-mt5/.test(p)) return 'mt5';
    if (/bot-sentinelas/.test(p)) return 'sentinelas';
    if (/bot-sinais-vip/.test(p)) return 'sinais-vip';
    if (/bot-mapa-digitos/.test(p)) return 'mapa-digitos';
    if (/bot-diferente/.test(p)) return 'diferente';
    if (/bot-espectro/.test(p)) return 'espectro';
    if (/bot-pulso/.test(p)) return 'pulso';
    if (/bot-prisma/.test(p)) return 'prisma';
    if (/bot-colhedor/.test(p)) return 'colhedor';
    if (/bot-digitos/.test(p)) return 'digitos';
    if (/bot-global/.test(p)) return 'global';
    if (/bot-sinais|ai-signals|sinais/.test(p)) return 'sinais';
    if (/auto-?trading/.test(p)) return 'auto-trading';
    if (/grafico/.test(p)) return (window.__alphaBot && window.__alphaBot.st && (window.__alphaBot.st() || {}).run) ? 'auto-trading' : 'grafico';
    if (/enxame/.test(p)) return 'enxame';
    if (/esquadr/.test(p)) return 'esquadrao';
    if (/regente/.test(p)) return 'regente';
    if (/perfil/.test(p)) return 'perfil';
    if (visivel('alphaCtxIaModal')) return 'ia-contextual';
    if (visivel('iaAvancadoModal')) return 'ia-avancado';
    if (visivel('alphaIaProModal')) return 'ia-pro';
    return 'manual';
  }
  function ferramentaDoStart(b) {
    var bt = String(b.bot_type || '').toLowerCase(), tudo = '';
    try { tudo = JSON.stringify(b).toLowerCase(); } catch (e) {}
    if (/^enxame/.test(bt)) return 'enxame';
    if (/^unidade/.test(bt)) return 'esquadrao';
    if (/avancado/.test(tudo)) return 'ia-avancado';
    if (PREMIUM.test(tudo)) return 'estrategias-premium';
    var pg = ferramentaDaPagina();
    return pg === 'manual' ? 'ia-simples' : pg;
  }

  /* ---------- aviso ---------- */
  function aviso(ferr, carregando) {
    try { console.warn('[plano] aviso de conta real:', ferr, '| motivo:', window.__planoMotivo || '?', '| conexao:', window.__planoUrl || '?', '| conta escolhida:', localStorage.getItem('deriv_conta_ativa')); } catch (e) {}  // PLANO-AVISO-V1
    var precisa = NIV_F[ferr] || 0;
    var id = 'alpha-plano-aviso', d = document.getElementById(id);
    if (d && d.getAttribute('data-f') === ferr + (carregando ? ':c' : '')) return; // ja esta aberto
    if (d) d.remove();
    d = document.createElement('div'); d.id = id; d.setAttribute('data-f', ferr + (carregando ? ':c' : ''));
    d.style.cssText = 'position:fixed;inset:0;z-index:2147483646;display:flex;align-items:center;justify-content:center;background:rgba(3,6,10,.72);backdrop-filter:blur(4px);padding:16px;font-family:Inter,system-ui,sans-serif';
    var titulo = carregando ? 'Verificando seu plano…' : 'Conta real bloqueada';
    var texto = carregando
      ? 'Ainda estou confirmando o seu plano no servidor. Aguarde alguns segundos e tente de novo. Na conta demo tudo continua liberado.'
      : 'A ferramenta <b>' + (NOME_F[ferr] || ferr) + '</b> na <b>conta real</b> faz parte do plano <b style="color:#f5c542">' + NOME[precisa] + '</b>. Na conta demo ela continua 100% liberada.';
    d.innerHTML = '<div style="max-width:380px;width:100%;background:#0b1118;border:1px solid rgba(245,197,66,.45);border-radius:16px;padding:22px;color:#e6edf3;box-shadow:0 20px 60px rgba(0,0,0,.6);text-align:center">' +
      '<div style="font-size:30px">' + (carregando ? '⏳' : '🔒') + '</div>' +
      '<div style="font:800 17px Inter,system-ui,sans-serif;margin:6px 0 8px;color:#f5c542">' + titulo + '</div>' +
      '<div style="font-size:13.5px;line-height:1.5;color:#b8c4d0">' + texto + '</div>' +
      '<div style="display:flex;gap:8px;margin-top:16px;flex-wrap:wrap">' +
      (carregando ? '' : '<a href="/loja.html?plano=' + SLUG[precisa] + '&ferramenta=' + encodeURIComponent(ferr) + '" style="flex:1;min-width:140px;background:linear-gradient(135deg,#f5c542,#d4a017);color:#111;font:800 14px Inter,system-ui,sans-serif;border-radius:10px;padding:12px;text-decoration:none">Ver planos</a>') +
      '<button type="button" data-x style="flex:1;min-width:140px;background:transparent;color:#9fb0c0;border:1px solid #2a3542;border-radius:10px;padding:12px;font:700 14px Inter,system-ui,sans-serif;cursor:pointer">' + (carregando ? 'Ok' : 'Continuar na demo') + '</button>' +
      '</div></div>';
    d.addEventListener('click', function (e) {
      if (e.target === d || e.target.hasAttribute('data-x')) {
        d.remove();
        if (!carregando && e.target.hasAttribute('data-x')) irParaDemo();
      }
    });
    (document.body || document.documentElement).appendChild(d);
  }

  /* "Continuar na demo": clica no botao Demo da propria pagina */
  function irParaDemo() {
    try { sessionStorage.setItem('plano_aviso_demo', '1'); localStorage.setItem('deriv_conta_ativa', 'demo'); } catch (e) {}  // PLANO-AVISO-V1
    /* DEMO-MODAL-V1: usa o botao Demo da ferramenta aberta (IA Pro, Avancado, Contextual) antes do topo */
    try {
      var rx = /conta\(\s*['"]demo['"]/i;
      var acha = function (raiz) {
        var els = (raiz || document).querySelectorAll('[onclick]');
        for (var i = 0; i < els.length; i++) {
          var oc = els[i].getAttribute('onclick') || '';
          if (rx.test(oc) && els[i].getClientRects().length) return els[i];
        }
        return null;
      };
      var mods = ['alphaIaProModal', 'iaAvancadoModal', 'alphaCtxIaModal'];
      for (var k = 0; k < mods.length; k++) {
        if (visivel(mods[k])) { var b = acha(document.getElementById(mods[k])); if (b) { b.click(); return; } }
      }
      var g = acha(document); if (g) { g.click(); return; }
    } catch (e) {}
    try {
      var bs = document.querySelectorAll('button, [role="button"], a');
      for (var i = 0; i < bs.length; i++) {
        var b = bs[i], tx = (b.textContent || '').trim();
        if (/^demo$/i.test(tx) && b.getClientRects().length && !b.disabled) { b.click(); return; }
      }
    } catch (e) {}
  }
  /* ao conectar numa conta real sem plano, avisa na hora (antes de qualquer entrada) */
  function avisarConta() {
    try { if ((localStorage.getItem('deriv_conta_ativa') || 'demo') !== 'real') { console.info('[plano] conexao real ignorada: voce esta na demo'); return; } if (sessionStorage.getItem('plano_aviso_demo') === '1') return; } catch (e) {}  // PLANO-AVISO-V1
    window.__planoMotivo = 'conexao com conta real';
    var f = ferramentaDaPagina();
    carregar(false).then(function () { if (pode(f) === false) aviso(f, false); }).catch(function () {});
  }

  /* decide: true = deixa passar */
  function liberar(ferr) {
    var p = pode(ferr);
    if (p === true) return true;
    if (p === null) { carregar(false).catch(function () {}); aviso(ferr, true); return false; }
    aviso(ferr, false); return false;
  }

  /* ---------- quais sockets sao de conta real ---------- */
  var URL_REAL = {}, URL_DEMO = {}, URL_ACC = {};
  function marcarOtp(url, resp) {
    var m = /\/accounts\/([^/?#]+)\/otp/i.exec(url); if (!m) return;
    var id = decodeURIComponent(m[1]);
    resp.clone().json().then(function (j) {
      var u = j && j.data && j.data.url; if (!u) return;
      var base = String(u).split('?')[0]; URL_ACC[String(u)] = id;
      if (ehDemoId(id) || /\/ws\/demo/i.test(base)) URL_DEMO[base] = 1; else { URL_REAL[base] = 1; avisarConta(); }
    }).catch(function () {});
  }
  function socketReal(ws) {
    if (ws.__alphaReal === true) return true;
    if (ws.__alphaReal === false) return false;
    var base = String(ws.url || '').split('?')[0];
    if (URL_REAL[base]) return true;
    if (URL_DEMO[base]) return false;
    if (/\/ws\/real/i.test(base)) return true;
    /* REAL-OTP-V1: conexao OTP da API nova que nao e demo conta como real (na duvida, bloqueia) */
    if (/derivws\.com\/trading\//i.test(base) && !/\/ws\/demo/i.test(base)) return true;
    return false;
  }

  /* ---------- fetch: OTP + /api/bot/start ---------- */
  var fetch0 = window.fetch;
  window.__plano_fetch0 = fetch0;
  function contaDoCorpo(b) {
    var k, v;
    for (k in { account_type: 1, conta: 1, tipo_conta: 1, modo_conta: 1, account: 1 }) {
      v = String(b[k] || '').toLowerCase(); if (v === 'real') return true; if (v === 'demo') return false;
    }
    if (b.is_demo === false || b.demo === false || b.is_virtual === 0 || b.is_virtual === false) return true;
    if (ehRealId(b.deriv_id)) return true;
    try {
      var accs = JSON.parse(ls('deriv_accounts') || '[]');
      for (var i = 0; i < accs.length; i++) {
        var a = accs[i];
        if ((b.deriv_id && a.acct === b.deriv_id) || (b.token && a.token && a.token === b.token)) return a.isDemo === false;
      }
    } catch (e) {}
    return false;
  }
  window.fetch = function (u, o) {
    var url = typeof u === 'string' ? u : (u && u.url) || '';
    try {
      if (/\/api\/bot\/start/.test(url) && o && typeof o.body === 'string') {
        var b = JSON.parse(o.body);
        if (contaDoCorpo(b)) {
          var ferr = ferramentaDoStart(b);
          if (!liberar(ferr)) {
            var msg = 'Conta real exige o plano ' + NOME[NIV_F[ferr] || 0] + '. Na conta demo continua liberado.';
            return Promise.resolve(new Response(JSON.stringify({ success: false, error: msg, plano_necessario: SLUG[NIV_F[ferr] || 0] }), { status: 403, headers: { 'Content-Type': 'application/json' } }));
          }
        }
      }
    } catch (e) {}
    var p = fetch0.apply(this, arguments);
    if (/\/accounts\/[^/]+\/otp/i.test(url)) p.then(function (r) { marcarOtp(url, r); }).catch(function () {});
    return p;
  };

  /* ---------- WebSocket: bloqueia "buy" em conta real ---------- */
  var WSP = window.WebSocket && window.WebSocket.prototype;
  if (WSP && !WSP.send.__plano) {
    var send0 = WSP.send;
    var novo = function (data) {
      var ws = this, obj = null;
      if (!ws.__alphaOps) { ws.__alphaOps = true; try { ws.addEventListener('message', function (ev) { try { opsMsg(ws, JSON.parse(ev.data)); } catch (e) {} }); } catch (e) {} }
      if (typeof data === 'string' && data.charAt(0) === '{') { try { obj = JSON.parse(data); } catch (e) {} }
      if (obj) {
        if (obj.authorize && !ws.__alphaAuthOuvindo) {
          ws.__alphaAuthOuvindo = true;
          ws.addEventListener('message', function (ev) {
            try { var m = JSON.parse(ev.data); if (m.msg_type === 'authorize' && m.authorize) ws.__alphaReal = !m.authorize.is_virtual; } catch (e) {}
          });
        }
        if ((obj.buy || obj.buy_contract_for_multiple_accounts) && socketReal(ws)) {
          window.__planoMotivo = 'ordem de compra enviada numa conexao REAL'; window.__planoUrl = String(ws.url || '').split('?')[0];  // PLANO-AVISO-V1
          var ferr = ferramentaDaPagina();
          if (!liberar(ferr)) {
            var resp = { echo_req: obj, msg_type: 'buy', error: { code: 'PlanoNecessario', message: 'Conta real exige o plano ' + NOME[NIV_F[ferr] || 0] + '. Na demo continua liberado.' } };
            if (obj.req_id != null) resp.req_id = obj.req_id;
            setTimeout(function () { try { ws.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(resp) })); } catch (e) {} }, 0);
            return;
          }
        }
      }
      return send0.apply(ws, arguments);
    };
    novo.__plano = true;
    WSP.send = novo;
  }

  /* ---------- confirm() bonito (troca de conta e outras confirmacoes) ---------- */
  var ult = null, conf0 = window.confirm;
  document.addEventListener('click', function (e) { ult = { el: e.target, t: Date.now(), tipo: 'click' }; }, true);
  document.addEventListener('change', function (e) { ult = { el: e.target, t: Date.now(), tipo: 'change' }; }, true);
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function modalConfirmar(msg, ok) {
    var old = document.getElementById('alpha-confirmar'); if (old) old.remove();
    var real = /conta\s*real|dinheiro real/i.test(msg);
    var d = document.createElement('div'); d.id = 'alpha-confirmar';
    d.style.cssText = 'position:fixed;inset:0;z-index:2147483645;display:flex;align-items:center;justify-content:center;background:rgba(3,6,10,.72);backdrop-filter:blur(4px);padding:16px;font-family:Inter,system-ui,sans-serif';
    var cor = real ? '#f5c542' : '#22d3a5';
    d.innerHTML = '<div role="dialog" aria-modal="true" style="max-width:380px;width:100%;background:#0b1118;border:1px solid ' + (real ? 'rgba(245,197,66,.45)' : 'rgba(34,211,165,.4)') + ';border-radius:16px;padding:22px;color:#e6edf3;box-shadow:0 20px 60px rgba(0,0,0,.6);text-align:center">' +
      '<div style="font-size:30px">' + (real ? '💰' : '❔') + '</div>' +
      '<div style="font:800 17px Inter,system-ui,sans-serif;margin:6px 0 8px;color:' + cor + '">' + (real ? 'Usar a conta real?' : 'Confirmar') + '</div>' +
      '<div style="font-size:13.5px;line-height:1.5;color:#b8c4d0">' + esc(msg).replace(/\n/g, '<br>') + '</div>' +
      '<div style="display:flex;gap:8px;margin-top:16px;flex-wrap:wrap">' +
      '<button type="button" data-n style="flex:1;min-width:130px;background:transparent;color:#9fb0c0;border:1px solid #2a3542;border-radius:10px;padding:12px;font:700 14px Inter,system-ui,sans-serif;cursor:pointer">Cancelar</button>' +
      '<button type="button" data-s style="flex:1;min-width:130px;background:' + (real ? 'linear-gradient(135deg,#f5c542,#d4a017)' : 'linear-gradient(135deg,#22d3a5,#14a37f)') + ';color:#111;border:0;border-radius:10px;padding:12px;font:800 14px Inter,system-ui,sans-serif;cursor:pointer">' + (real ? 'Sim, usar a real' : 'Confirmar') + '</button>' +
      '</div></div>';
    function fechar() { d.remove(); document.removeEventListener('keydown', tecla, true); }
    function tecla(e) { if (e.key === 'Escape') { e.preventDefault(); fechar(); } else if (e.key === 'Enter') { e.preventDefault(); fechar(); ok(); } }
    d.addEventListener('click', function (e) {
      if (e.target === d || e.target.hasAttribute('data-n')) fechar();
      else if (e.target.hasAttribute('data-s')) { fechar(); ok(); }
    });
    document.addEventListener('keydown', tecla, true);
    (document.body || document.documentElement).appendChild(d);
    try { d.querySelector('[data-s]').focus(); } catch (e) {}
  }
  window.confirm = function (msg) {
    if (window.__alphaConfirmSim) { window.__alphaConfirmSim = false; return true; }
    var u = ult;
    // so troca quando veio de um clique/troca do usuario agora (para poder repetir a acao depois do "sim")
    if (!u || Date.now() - u.t > 1500 || !document.body || !document.contains(u.el)) return conf0.call(window, msg);
    ult = null;
    modalConfirmar(String(msg == null ? '' : msg), function () {
      window.__alphaConfirmSim = true;
      try { /* CONFIRM-ICONE-V1: clique em icone (svg) repete no botao de verdade */
        if (u.tipo === 'change') u.el.dispatchEvent(new Event('change', { bubbles: true }));
        else {
          var alvo = (u.el.closest && u.el.closest('button,a,[onclick],[role=button],input,label,summary')) || u.el;
          if (typeof alvo.click === 'function') alvo.click();
          else alvo.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
        }
      }
      catch (e) {}
      setTimeout(function () { window.__alphaConfirmSim = false; }, 0);
    });
    return false;
  };

  /* ---------- OPS-JS-V1: registra cada operacao fechada (para o extrato do admin) ---------- */
  var OPS_BUY = {}, OPS_FEITO = {}, FILA = [], tEnvio = null;
  function opsMsg(ws, m) {
    if (!m || !m.msg_type) return;
    if (m.msg_type === 'authorize' && m.authorize) ws.__alphaAcc = m.authorize.loginid;
    if (m.msg_type === 'balance' && m.balance && m.balance.loginid) { /* REAL-OTP-V1 */
      if (!ws.__alphaAcc) ws.__alphaAcc = m.balance.loginid;
      if (ws.__alphaReal == null) { ws.__alphaReal = ehRealId(m.balance.loginid); if (ws.__alphaReal) { try { avisarConta(); } catch (e) {} } }
    }
    if (m.msg_type === 'buy' && m.buy && m.buy.contract_id) {
      OPS_BUY[m.buy.contract_id] = { f: ferramentaDaPagina(), conta: socketReal(ws) ? 'real' : 'demo', acc: ws.__alphaAcc || URL_ACC[String(ws.url)] || '', stake: +m.buy.buy_price || 0 };
    }
    if (m.msg_type === 'proposal_open_contract' && m.proposal_open_contract) {
      var c = m.proposal_open_contract, id = c.contract_id, b = OPS_BUY[id];
      if (!b || OPS_FEITO[id]) return;
      if (!(c.is_sold || c.status === 'won' || c.status === 'lost')) return;
      OPS_FEITO[id] = 1; delete OPS_BUY[id];
      FILA.push({ contract_id: String(id), ferramenta: b.f, conta: b.conta, deriv_id: b.acc, stake: +c.buy_price || b.stake, lucro: +c.profit || 0, symbol: c.underlying || c.underlying_symbol || '', tipo: c.contract_type || '' });
      agendarEnvio();
    }
  }
  function agendarEnvio(ms) { if (!tEnvio) tEnvio = setTimeout(enviarOps, ms || 4000); }
  function enviarOps() {
    tEnvio = null; var tk = tokenAtual(); if (!FILA.length || !tk) return;
    var lote = FILA.splice(0, 50);
    try {
      fetch0(BACK + '/api/ops/registrar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: tk, ops: lote }), keepalive: true })
        .then(function (r) { if (r.status >= 500) throw new Error('srv'); })
        .catch(function () { FILA = lote.concat(FILA).slice(0, 500); agendarEnvio(20000); });
    } catch (e) {}
    if (FILA.length) agendarEnvio();
  }
  window.addEventListener('pagehide', enviarOps);

  window.AlphaPlano = {
    carregar: carregar, pode: pode, exigir: liberar, info: function () { return st.info; },
    ferramenta: ferramentaDaPagina, niveis: NIV_F,
    limpar: function () { try { sessionStorage.removeItem(CK); } catch (e) {} st.info = null; return carregar(true); }
  };
  if (tokenAtual()) carregar(false).catch(function () {});
})();

/* DIAG-PLANO-V1 — painel de diagnostico da trava (so aparece abrindo a pagina com ?diagplano=1) */
(function () {
  try { if (/[?&]diagplano=1/.test(location.search)) sessionStorage.setItem('diagplano', '1'); if (/[?&]diagplano=0/.test(location.search)) sessionStorage.removeItem('diagplano'); if (sessionStorage.getItem('diagplano') !== '1') return; } catch (e) { return; }
  var L = [], P = null;
  function add(t) { L.unshift(new Date().toTimeString().slice(0, 8) + ' ' + t); L = L.slice(0, 14); draw(); }
  var WSP = WebSocket.prototype, s1 = WSP.send;
  WSP.send = function (d) {
    try { var o = typeof d === 'string' && d.charAt(0) === '{' ? JSON.parse(d) : null; if (o && (o.buy || o.proposal)) { var u = String(this.url || '').split('?')[0].replace(/^wss:\/\/[^/]+/, ''); add((o.buy ? 'COMPRA' : 'proposta') + ' via ' + u); if (o.buy && !this.__dg) { this.__dg = 1; this.addEventListener('message', function (ev) { try { var m = JSON.parse(ev.data); if (m.msg_type === 'buy') add(m.error ? 'BLOQUEADA/ERRO: ' + (m.error.code || '') + ' ' + (m.error.message || '') : 'COMPRA ACEITA #' + (m.buy && m.buy.contract_id)); } catch (e) {} }); } } } catch (e) {}
    return s1.apply(this, arguments);
  };
  function draw() {
    var b = document.getElementById('diagplano'); if (!b) { if (!document.body) return; b = document.createElement('div'); b.id = 'diagplano'; b.style.cssText = 'position:fixed;left:6px;right:6px;top:6px;z-index:2147483647;background:rgba(0,0,0,.92);color:#0f0;font:11px/1.35 monospace;padding:8px;border:1px solid #0f0;border-radius:8px;max-height:46vh;overflow:auto;white-space:pre-wrap;pointer-events:auto'; document.body.appendChild(b); b.onclick = function () { b.style.maxHeight = b.style.maxHeight === '18px' ? '46vh' : '18px'; }; }
    var sc = Array.prototype.map.call(document.scripts, function (s) { return s.src; }).filter(function (s) { return /plano/.test(s); }).map(function (s) { return s.replace(/^.*\/js\//, ''); });
    var ac = ''; try { ac = JSON.parse(localStorage.getItem('deriv_accounts') || '[]').map(function (a) { return a.acct + (a.isDemo ? '(demo)' : '(real)'); }).join(' '); } catch (e) {}
    b.textContent = 'DIAG PLANO (toque para recolher · ?diagplano=0 desliga)\npagina: ' + location.pathname + '\nscript: ' + sc.join(',') + '\ntrava ws: ' + !!(WSP.send && (WSP.send.__plano || s1.__plano)) + '\nconta escolhida: ' + localStorage.getItem('deriv_conta_ativa') + '\ncontas: ' + ac + '\nemail: ' + (localStorage.getItem('alpha_email') || '(vazio)') + '\nplano servidor: ' + (P ? JSON.stringify(P) : 'consultando...') + '\n--- compras ---\n' + L.join('\n');
  }
  function plano() { var f = window.__plano_fetch0 || window.fetch; f('https://alpha-dolar-backend.onrender.com/api/plano', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: localStorage.getItem('deriv_bearer_token'), email: localStorage.getItem('alpha_email') }) }).then(function (r) { return r.json(); }).then(function (d) { P = { ok: d.ok, nivel: d.nivel, plano: d.plano, ferramentas: d.ferramentas }; draw(); }).catch(function (e) { P = { erro: String(e) }; draw(); }); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { draw(); plano(); }); else { draw(); plano(); }
  setInterval(draw, 2000);
})();
