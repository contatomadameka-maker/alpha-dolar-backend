/* Alpha Dolar - GUARD-V3 (GUARD-V2 + resgate: login da Deriv bom mas sem contas guardadas → busca as contas de novo em vez de expulsar)
   ferramentas so abrem com conexao Deriv valida (token OAuth ory_at_ + conta + dentro da validade) */
(function () {
  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function motivo() {
    var t = ls('deriv_bearer_token') || '';
    if (!t) return 'sem_deriv';
    if (!/^ory_at_/.test(t)) return 'token_antigo';
    var em = parseInt(ls('deriv_token_em') || '0', 10);
    if (em && Date.now() - em > 30 * 864e5) return 'expirado';
    try {
      var a = JSON.parse(ls('deriv_accounts') || '[]');
      if (!Array.isArray(a) || !a.some(function (x) { return x && x.acct; })) return 'sem_conta';
    } catch (e) { return 'sem_conta'; }
    return null;
  }
  var m = motivo();
  if (!m) { try { sessionStorage.removeItem('alpha_guard_n'); } catch (e) {} return; }

  function expulsa() {
    /* limpa restos invalidos para o login nao achar que ja esta conectado */
    ['deriv_bearer_token', 'deriv_accounts', 'deriv_token_demo', 'deriv_token_real', 'deriv_token_em'].forEach(function (k) {
      try { localStorage.removeItem(k); } catch (e) {}
    });
    /* trava contra ida-e-volta infinita */
    var n = 0, agora = Date.now();
    try { var s = JSON.parse(sessionStorage.getItem('alpha_guard_n') || '{}'); n = (agora - (s.t || 0) < 30000) ? (s.n || 0) : 0; sessionStorage.setItem('alpha_guard_n', JSON.stringify({ n: n + 1, t: agora })); } catch (e) {}
    if (n >= 2) {
      document.documentElement.style.visibility = '';
      var mostra = function () {
        var d = document.createElement('div');
        d.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;background:rgba(3,6,10,.92);padding:16px';
        d.innerHTML = '<div style="max-width:380px;background:#0b1118;border:1px solid rgba(245,197,66,.45);border-radius:16px;padding:22px;color:#e6edf3;font:14px Inter,system-ui,sans-serif;text-align:center">' +
          '<div style="font-size:30px">🔌</div><div style="font-weight:800;font-size:17px;color:#f5c542;margin:6px 0 8px">Conecte sua conta Deriv</div>' +
          '<div style="color:#b8c4d0;line-height:1.5">Para usar os robôs é preciso entrar com a sua conta Deriv.</div>' +
          '<a href="/conectar-deriv" style="display:block;margin-top:16px;background:linear-gradient(135deg,#f5c542,#d4a017);color:#111;border-radius:10px;padding:12px;font-weight:800;text-decoration:none">Conectar Deriv</a>' +
          '<a href="https://wa.me/5547992206579?text=' + encodeURIComponent('Olá! Não estou conseguindo conectar com a Deriv na Alpha Dolar (motivo: ' + m + ').') + '" target="_blank" style="display:block;margin-top:8px;background:#25d366;color:#05230f;border-radius:10px;padding:11px;font-weight:800;text-decoration:none">💬 Falar com o suporte</a></div>';
        document.body.appendChild(d);
      };
      if (document.body) mostra(); else document.addEventListener('DOMContentLoaded', mostra);
      return;
    }
    try { sessionStorage.setItem('alpha_voltar_para', location.pathname + location.search); sessionStorage.setItem('alpha_guard_motivo', m); } catch (e) {}
    document.documentElement.style.visibility = 'hidden';
    location.replace('/login?conectar=' + m);
  }
  if (m !== 'sem_conta') return expulsa();

  /* GUARD-V3: tem login da Deriv válido mas as contas não foram guardadas (a Deriv falhou na hora do login) → busca de novo */
  var tok = ls('deriv_bearer_token');
  document.documentElement.style.visibility = 'hidden';
  var caixa = null;
  function tela(html) {
    var pinta = function () {
      document.documentElement.style.visibility = '';
      if (!caixa) {
        caixa = document.createElement('div');
        caixa.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;background:#05070d;padding:16px;font:14px Inter,system-ui,sans-serif;color:#e6edf3';
        document.body.appendChild(caixa);
      }
      caixa.innerHTML = '<div style="max-width:390px;width:100%;background:#0b1118;border:1px solid rgba(245,197,66,.45);border-radius:16px;padding:22px;text-align:center">' + html + '</div>';
    };
    if (document.body) pinta(); else document.addEventListener('DOMContentLoaded', pinta);
  }
  var espera = setTimeout(function () { tela('<div style="font-size:30px">🔄</div><div style="font-weight:800;font-size:16px;color:#f5c542;margin:6px 0">Conferindo sua conta Deriv…</div><div style="color:#b8c4d0;line-height:1.5">A Deriv está demorando para responder. Aguarde alguns segundos.</div>'); }, 1500);
  var D = [0, 1500, 3000, 5000, 8000], st = null;
  (function tenta(i) {
    setTimeout(function () {
      fetch('https://api.derivws.com/trading/v1/options/accounts', { headers: { Authorization: 'Bearer ' + tok, 'Deriv-App-ID': '34lv1PuWzjElEuwWcDLyr' } })
        .then(function (r) {
          st = r.status;
          if (r.status === 401 || r.status === 403) { clearTimeout(espera); return expulsa(); }
          if (!r.ok) throw new Error('Deriv ' + r.status);
          return r.json().then(function (j) {
            var L = ((j || {}).data || []).map(function (a) { return { acct: a.account_id, token: tok, cur: a.currency || 'USD', isDemo: String(a.account_type) === 'demo', balance: parseFloat(a.balance || 0), name: '', email: '' }; });
            if (!L.length) throw new Error('sem contas');
            localStorage.setItem('deriv_accounts', JSON.stringify(L));
            if (!ls('deriv_token_em')) localStorage.setItem('deriv_token_em', String(Date.now()));
            var at = ls('deriv_conta_ativa');
            if (!L.some(function (a) { return a.isDemo === (at === 'demo'); }) || (at !== 'demo' && at !== 'real')) localStorage.setItem('deriv_conta_ativa', L.some(function (a) { return a.isDemo; }) ? 'demo' : 'real');
            clearTimeout(espera);
            location.reload();   /* recarrega com as contas no lugar, para a página iniciar normal */
          });
        })
        .catch(function () {
          if (i + 1 < D.length) return tenta(i + 1);
          clearTimeout(espera);
          tela('<div style="font-size:30px">🛠️</div><div style="font-weight:800;font-size:17px;color:#f5c542;margin:6px 0 8px">A Deriv está instável agora</div>' +
            '<div style="color:#b8c4d0;line-height:1.5">O seu login está certo, mas a Deriv não respondeu' + (st ? ' (erro ' + st + ')' : '') + '. Não é problema da sua conta: costuma voltar em poucos minutos.</div>' +
            '<button type="button" onclick="location.reload()" style="width:100%;margin-top:16px;border:0;border-radius:10px;padding:12px;font-weight:800;background:linear-gradient(135deg,#f5c542,#d4a017);color:#111;cursor:pointer">🔄 Tentar de novo</button>' +
            '<a href="https://wa.me/5547992206579?text=' + encodeURIComponent('Olá! A Alpha Dolar diz que a Deriv está instável (erro ' + (st || 'sem resposta') + ') e não consigo entrar.') + '" target="_blank" style="display:block;margin-top:8px;background:#25d366;color:#05230f;border-radius:10px;padding:11px;font-weight:800;text-decoration:none">💬 Falar com o suporte</a>' +
            '<a href="/conectar-deriv" onclick="try{localStorage.removeItem(\'deriv_bearer_token\');localStorage.removeItem(\'deriv_accounts\')}catch(e){}" style="display:block;margin-top:10px;color:#94a3b8;font-size:12.5px">Entrar de novo com a Deriv</a>');
        });
    }, D[i]);
  })(0);
})();
