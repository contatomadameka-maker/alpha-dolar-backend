/* SUPORTE-ALPHA-V1.3 (teste de conexão com a Deriv + telas de login) | SUPORTE-ALPHA-V1.2 (entre o Manual e o idioma no computador) | SUPORTE-ALPHA-V1.1 | SUPORTE-ALPHA-V1: assistente flutuante de suporte (abre o WhatsApp com a dúvida já escrita) */
(function () {
  'use strict';
  if (window.__suporteAlpha) return; window.__suporteAlpha = 1;
  var WA = '5547992206579';
  function lsG(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsS(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function link(sel, fb) { var a = document.querySelector(sel); return (a && a.getAttribute('href')) || fb; }
  function conta() { var real = document.body.innerText.indexOf('Conta Real') >= 0 && document.body.innerText.indexOf('Conta Demo') < 0; return real ? 'real' : 'demo'; }
  var LOGIN = /^\/(conectar-deriv|login|auth)/i.test(location.pathname);
  var black = Date.now() < new Date(2026, 11, 1).getTime();
  var OP = [
    { k: 'conexao', ic: '🔌', t: 'Não estou conseguindo conexão com a Deriv', r: null, m: '' },
    { k: 'comecar', ic: '🚀', t: 'Como começar', r: 'É simples: <b>1)</b> conecte a sua conta Deriv, <b>2)</b> comece pela conta <b>DEMO</b> (dinheiro virtual), <b>3)</b> escolha um robô no menu <b>Robôs de IA</b>, defina a entrada, a meta e o limite de perda e ligue. Os tutoriais mostram passo a passo.', bt: [['📚 Ver tutoriais', link('a[href*="tutoria"]', '/tutoriais')]], m: 'Olá! Estou no painel da Alpha Dolar e quero ajuda para começar.' },
    { k: 'robo', ic: '🤖', t: 'Qual robô usar com a minha banca', r: 'No menu <b>Robôs de IA</b> tem as abas <b>Até $100</b>, <b>$100 a $500</b> e <b>$500+</b>: cada uma mostra os robôs indicados para aquele tamanho de banca. Para começar, use entrada de no máximo 1% da banca e teste na demo.', bt: [], m: 'Olá! Estou no painel da Alpha Dolar e quero saber qual robô usar com a minha banca. Minha banca é de: ' },
    { k: 'dinheiro', ic: '💰', t: 'Depositar ou sacar', r: 'Use os botões <b>Depositar</b> e <b>Sacar</b> no topo do painel. O dinheiro fica na sua conta da Deriv: nós não recebemos nem guardamos o seu saldo.', bt: [], m: 'Olá! Estou no painel da Alpha Dolar e tenho uma dúvida sobre depósito ou saque.' },
    { k: 'real', ic: '🔓', t: 'Conta real e planos', r: (black ? '🖤 <b>Até 30/11 todos os robôs estão liberados na conta real, de graça.</b> ' : '') + 'Na conta demo tudo é liberado para testar. Para a conta real, cada robô pede um plano (Sinais, Pro ou Elite).', bt: [['🛒 Ver planos', '/loja.html']], m: 'Olá! Estou no painel da Alpha Dolar e quero saber sobre a conta real e os planos.' },
    { k: 'outra', ic: '💬', t: 'Outra dúvida', r: null, m: '' }
  ];
  var css = '#supB{position:fixed;right:28px;bottom:calc(74px + env(safe-area-inset-bottom,0px));z-index:9980;width:62px;height:62px;border-radius:50%;border:0;cursor:pointer;background:radial-gradient(circle at 35% 30%,#7dd3fc,#4f8cff 55%,#6d28d9);box-shadow:0 12px 30px rgba(79,140,255,.45),0 0 0 6px rgba(79,140,255,.14);display:grid;place-items:center;animation:supF 3.2s ease-in-out infinite}' +
    '@keyframes supF{50%{transform:translateY(-6px)}}#supB svg{width:38px;height:38px}#supB i{position:absolute;top:2px;right:2px;width:14px;height:14px;border-radius:50%;background:#34d399;border:2px solid #0b1220}' +
    '#supN{position:fixed;right:102px;bottom:calc(90px + env(safe-area-inset-bottom,0px));z-index:9980;background:#fff;color:#0b1220;font:700 13.5px Inter,system-ui,sans-serif;padding:9px 13px;border-radius:14px 14px 4px 14px;box-shadow:0 10px 30px rgba(0,0,0,.35);cursor:pointer;display:none;max-width:200px}#supN.on{display:block;animation:supA .35s ease}' +
    '@keyframes supA{from{opacity:0;transform:translateY(8px)}}' +
    '#supP{position:fixed;right:28px;bottom:calc(148px + env(safe-area-inset-bottom,0px));z-index:9981;width:min(360px,calc(100vw - 28px));max-height:min(70vh,560px);overflow:auto;background:#0b1220;border:1px solid #22324d;border-radius:20px;box-shadow:0 24px 70px rgba(0,0,0,.6);color:#e2e8f0;font:14px/1.45 Inter,system-ui,sans-serif;display:none}#supP.on{display:block;animation:supA .25s ease}' +
    '#supP .hd{display:flex;align-items:center;gap:11px;padding:14px 16px;background:linear-gradient(135deg,rgba(79,140,255,.22),rgba(109,40,217,.18));border-bottom:1px solid #1d2b44}#supP .hd b{display:block;font-size:15px}#supP .hd small{color:#94a3b8;font-size:12px}#supP .hd .av{width:40px;height:40px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#7dd3fc,#4f8cff 55%,#6d28d9);display:grid;place-items:center;flex:none}#supP .hd .av svg{width:26px;height:26px}' +
    '#supP .x{margin-left:auto;background:none;border:0;color:#94a3b8;font-size:20px;cursor:pointer}' +
    '#supP .bd{padding:14px 16px;display:grid;gap:9px}#supP .ms{background:#14213a;border-radius:4px 14px 14px 14px;padding:10px 12px;font-size:13.5px}' +
    '#supP .op{display:flex;align-items:center;gap:10px;width:100%;text-align:left;border:1px solid #22324d;background:#0f192c;color:#e2e8f0;border-radius:12px;padding:11px 12px;font:600 13.5px Inter,sans-serif;cursor:pointer}#supP .op:hover{border-color:#4f8cff}#supP .op span{font-size:18px}' +
    '#supP .ac{display:flex;gap:8px;flex-wrap:wrap}#supP .wa,#supP .lk,#supP .vt{border:0;border-radius:11px;padding:11px 14px;font:800 13.5px Inter,sans-serif;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:7px}#supP .wa{background:#25d366;color:#05230f}#supP .lk{background:#1d2b44;color:#e2e8f0}#supP .vt{background:none;color:#94a3b8;padding:6px 0;font-weight:700}' +
    '#supP textarea{width:100%;min-height:80px;background:#060b16;border:1px solid #23324a;border-radius:10px;color:#fff;padding:10px;font:14px Inter,sans-serif;resize:vertical;box-sizing:border-box}' +
    '#supP .rd{font-size:11.5px;color:#64748b;text-align:center;padding:0 16px 12px}' +
    '@media (max-width:760px){#supB{width:54px;height:54px;right:12px;bottom:calc(84px + env(safe-area-inset-bottom,0px))}#supB svg{width:32px;height:32px}#supN{right:74px;bottom:calc(96px + env(safe-area-inset-bottom,0px))}#supP{right:12px;bottom:calc(148px + env(safe-area-inset-bottom,0px))}}';
  var BOT = '<svg viewBox="0 0 48 48" fill="none"><rect x="9" y="14" width="30" height="24" rx="9" fill="#e0f2fe"/><rect x="13" y="19" width="22" height="12" rx="6" fill="#0b1220"/><circle cx="19" cy="25" r="2.6" fill="#38e1d0"><animate attributeName="r" values="2.6;2.6;.4;2.6" dur="4s" repeatCount="indefinite"/></circle><circle cx="29" cy="25" r="2.6" fill="#38e1d0"><animate attributeName="r" values="2.6;2.6;.4;2.6" dur="4s" repeatCount="indefinite"/></circle><path d="M24 9v5" stroke="#e0f2fe" stroke-width="2.5" stroke-linecap="round"/><circle cx="24" cy="8" r="2.6" fill="#f2c14e"/><rect x="5" y="22" width="4" height="9" rx="2" fill="#bae6fd"/><rect x="39" y="22" width="4" height="9" rx="2" fill="#bae6fd"/></svg>';
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function abreWa(txt) {
    var t = txt + '\n\n(Conta: ' + conta() + ' · página: ' + (LOGIN ? 'login' : location.pathname) + ')';
    try { if (window.fbq) fbq('track', 'Contact', { content_name: 'suporte-painel' }); } catch (e) {}
    window.open('https://wa.me/' + WA + '?text=' + encodeURIComponent(t), '_blank');
  }
  function inicio() {
    $b().innerHTML = '<div class="ms">Oi! 👋 Eu sou o assistente da Alpha. Qual é a sua dúvida?</div>' + OP.map(function (o, i) { return '<button type="button" class="op" data-i="' + i + '"><span>' + o.ic + '</span>' + esc(o.t) + '</button>'; }).join('');
    $b().querySelectorAll('.op').forEach(function (b) { b.onclick = function () { resp(OP[+b.dataset.i]); }; });
  }
  function carregaCx() {
    return new Promise(function (ok) {
      if (window.AlphaConexao) return ok(window.AlphaConexao);
      var sc = document.createElement('script'); sc.src = '/js/conexao-deriv.js?v=1';
      sc.onload = function () { ok(window.AlphaConexao || null); }; sc.onerror = function () { ok(null); }; document.head.appendChild(sc);
    });
  }
  function conexao(o) {
    var eu = '<div class="ms" style="background:#1d2b44;border-radius:14px 4px 14px 14px;justify-self:end">' + o.ic + ' ' + esc(o.t) + '</div>';
    $b().innerHTML = eu + '<div class="ms">🔎 Testando a sua conexão com a Deriv… (pode levar até 30 s se a Deriv estiver lenta)</div>';
    carregaCx().then(function (CX) {
      if (!CX) { $b().innerHTML = eu + '<div class="ms">Não consegui fazer o teste agora. Fale com o suporte:</div><div class="ac"><button type="button" class="wa" id="supW">💬 Falar no WhatsApp</button></div>'; document.getElementById('supW').onclick = function () { abreWa('Olá! Não estou conseguindo conectar com a Deriv na Alpha Dolar.'); }; return; }
      return CX.diag().then(function (d) {
        var h = eu, bt = '';
        if (d.app) h += '<div class="ms">⚠️ Você abriu pelo navegador do <b>' + esc(d.app) + '</b>. Ele costuma bloquear o login da Deriv. Toque nos <b>3 pontinhos</b> e escolha <b>Abrir no Chrome</b> (ou Safari).</div>';
        if (d.k === 'ok') { h += '<div class="ms">✅ <b>A sua conexão com a Deriv está funcionando.</b>' + (d.consertou ? ' Encontrei o problema: as suas contas não tinham sido guardadas no login. <b>Já guardei de novo.</b>' : '') + '</div>'; bt = '<a class="lk" href="/dashboard">▶ Abrir o painel</a>'; }
        else if (d.k === 'deriv') { h += '<div class="ms">🛠️ <b>A Deriv está fora do ar ou instável agora</b>' + (d.status ? ' (erro ' + d.status + ')' : '') + '. Não é problema da sua conta nem do seu celular. Costuma voltar em poucos minutos: espere 2 minutos e toque em <b>Testar de novo</b>.</div>'; bt = '<button type="button" class="lk" id="supR">🔄 Testar de novo</button>'; }
        else if (d.k === 'rede') { h += '<div class="ms">📡 <b>Não consegui falar com a Deriv daqui.</b> Tente: desligar VPN ou bloqueador de anúncios, trocar Wi-Fi por dados móveis (ou o contrário) e abrir no Chrome/Safari.</div>'; bt = '<button type="button" class="lk" id="supR">🔄 Testar de novo</button>'; }
        else { h += '<div class="ms">🔑 <b>' + (d.k === 'semlogin' ? 'Falta entrar com a sua conta Deriv.' : esc(d.res)) + '</b> Vou limpar o login antigo deste navegador e abrir a Deriv de novo. Entre com o <b>e-mail e a senha da Deriv</b>.</div>'; bt = '<button type="button" class="lk" id="supL">🔑 Limpar e entrar de novo</button>'; }
        h += '<div class="ac">' + bt + '<button type="button" class="wa" id="supW">💬 Mandar o teste no WhatsApp</button></div><button type="button" class="vt" id="supV">← voltar às perguntas</button>';
        $b().innerHTML = h;
        var R = document.getElementById('supR'); if (R) R.onclick = function () { conexao(o); };
        var Lg = document.getElementById('supL'); if (Lg) Lg.onclick = function () { CX.limpar(); location.href = '/conectar-deriv'; };
        document.getElementById('supV').onclick = inicio;
        document.getElementById('supW').onclick = function () { abreWa('Olá! Não estou conseguindo conectar com a Deriv na Alpha Dolar.\n\n' + d.txt); };
      });
    }).catch(function () {});
  }
  function resp(o) {
    if (o.k === 'conexao') return conexao(o);
    var h = '<div class="ms" style="background:#1d2b44;border-radius:14px 4px 14px 14px;justify-self:end">' + o.ic + ' ' + esc(o.t) + '</div>';
    if (o.r) {
      h += '<div class="ms">' + o.r + '</div><div class="ac">' + (o.bt || []).map(function (x) { return '<a class="lk" href="' + esc(x[1]) + '">' + esc(x[0]) + '</a>'; }).join('') + '<button type="button" class="wa" id="supW">💬 Falar no WhatsApp</button></div>';
    } else {
      h += '<div class="ms">Escreva a sua dúvida que eu já mando para o suporte no WhatsApp:</div><textarea id="supT" placeholder="Ex.: liguei o robô e ele não entra em nenhuma operação"></textarea><div class="ac"><button type="button" class="wa" id="supW">💬 Enviar no WhatsApp</button></div>';
    }
    h += '<button type="button" class="vt" id="supV">← voltar às perguntas</button>';
    $b().innerHTML = h;
    document.getElementById('supV').onclick = inicio;
    document.getElementById('supW').onclick = function () { var ta = document.getElementById('supT'); var m = ta ? 'Olá! Estou no painel da Alpha Dolar e tenho uma dúvida: ' + (ta.value.trim() || '(escreva aqui)') : o.m; abreWa(m); };
  }
  function $b() { return document.querySelector('#supP .bd'); }
  function monta() {
    var s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
    var b = document.createElement('button'); b.type = 'button'; b.id = 'supB'; b.title = 'Suporte'; b.setAttribute('aria-label', 'Suporte'); b.innerHTML = BOT + '<i></i>'; document.body.appendChild(b);
    var n = document.createElement('div'); n.id = 'supN'; n.textContent = LOGIN ? 'Não consegue conectar? 👋' : 'Precisa de ajuda? 👋'; document.body.appendChild(n);
    var p = document.createElement('div'); p.id = 'supP';
    p.innerHTML = '<div class="hd"><div class="av">' + BOT + '</div><div><b>Suporte Alpha</b><small>● online · resposta pelo WhatsApp</small></div><button type="button" class="x" aria-label="Fechar">×</button></div><div class="bd"></div><div class="rd">Atendimento humano pelo WhatsApp (47) 99220-6579</div>';
    document.body.appendChild(p);
    function abre(on) { p.classList.toggle('on', on); n.classList.remove('on'); if (on) inicio(); }
    b.onclick = function () { abre(!p.classList.contains('on')); };
    n.onclick = function () { abre(true); };
    p.querySelector('.x').onclick = function () { abre(false); };
    var hoje = new Date().toISOString().slice(0, 10);
    if (LOGIN) setTimeout(function () { if (!p.classList.contains('on')) { n.classList.add('on'); setTimeout(function () { n.classList.remove('on'); }, 9000); } }, 8000);
    else if (lsG('sup_aviso') !== hoje) setTimeout(function () { if (!p.classList.contains('on')) { n.classList.add('on'); lsS('sup_aviso', hoje); setTimeout(function () { n.classList.remove('on'); }, 9000); } }, 20000);
  }
  if (document.body) monta(); else document.addEventListener('DOMContentLoaded', monta);
})();
