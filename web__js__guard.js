/* Alpha Dolar - GUARD-V2: ferramentas so abrem com conexao Deriv valida (token OAuth ory_at_ + conta + dentro da validade) */
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

  /* limpa restos invalidos para o login nao achar que ja esta conectado */
  ['deriv_bearer_token', 'deriv_accounts', 'deriv_token_demo', 'deriv_token_real', 'deriv_token_em'].forEach(function (k) {
    try { localStorage.removeItem(k); } catch (e) {}
  });

  /* trava contra ida-e-volta infinita */
  var n = 0, agora = Date.now();
  try { var s = JSON.parse(sessionStorage.getItem('alpha_guard_n') || '{}'); n = (agora - (s.t || 0) < 30000) ? (s.n || 0) : 0; sessionStorage.setItem('alpha_guard_n', JSON.stringify({ n: n + 1, t: agora })); } catch (e) {}
  if (n >= 2) {
    document.addEventListener('DOMContentLoaded', function () {
      var d = document.createElement('div');
      d.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;background:rgba(3,6,10,.92);padding:16px';
      d.innerHTML = '<div style="max-width:380px;background:#0b1118;border:1px solid rgba(245,197,66,.45);border-radius:16px;padding:22px;color:#e6edf3;font:14px Inter,system-ui,sans-serif;text-align:center">' +
        '<div style="font-size:30px">🔌</div><div style="font-weight:800;font-size:17px;color:#f5c542;margin:6px 0 8px">Conecte sua conta Deriv</div>' +
        '<div style="color:#b8c4d0;line-height:1.5">Para usar os robôs é preciso entrar com a sua conta Deriv.</div>' +
        '<a href="/login?conectar=' + m + '" style="display:block;margin-top:16px;background:linear-gradient(135deg,#f5c542,#d4a017);color:#111;border-radius:10px;padding:12px;font-weight:800;text-decoration:none">Conectar Deriv</a></div>';
      document.body.appendChild(d);
    });
    return;
  }
  try { sessionStorage.setItem('alpha_voltar_para', location.pathname + location.search); sessionStorage.setItem('alpha_guard_motivo', m); } catch (e) {}
  document.documentElement.style.visibility = 'hidden';
  location.replace('/login?conectar=' + m);
})();
