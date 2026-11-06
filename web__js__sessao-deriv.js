/* SESSAO-DERIV-V1: avisa quando o token da Deriv venceu e leva para o login */
(function () {
  if (window.__sessaoDerivV1) return; window.__sessaoDerivV1 = true;
  var CHAVES = ['deriv_accounts','deriv_conta_ativa','deriv_token_demo','deriv_token_real',
                'deriv_balance_demo','deriv_balance_real','deriv_bearer_token'];
  var adiadoAte = 0, aberto = false;

  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

  function entrarDeNovo() {
    try { CHAVES.forEach(function (k) { localStorage.removeItem(k); }); } catch (e) {}
    window.location.href = '/login?expirou=1';
  }

  function mostrar(origem) {
    if (aberto || Date.now() < adiadoAte) return;
    aberto = true;
    var fundo = document.createElement('div');
    fundo.id = 'sessaoDerivAviso';
    fundo.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:rgba(0,0,0,.72);' +
      'display:flex;align-items:center;justify-content:center;padding:16px;font-family:inherit';
    fundo.innerHTML =
      '<div style="max-width:380px;width:100%;background:#0d1117;border:1px solid #d4a017;border-radius:14px;' +
      'padding:22px 20px;color:#e6edf3;box-shadow:0 0 30px rgba(212,160,23,.25);text-align:center">' +
        '<div style="font-size:34px;line-height:1;margin-bottom:10px">🔑</div>' +
        '<div style="font-size:18px;font-weight:700;color:#f5c542;margin-bottom:8px">Sua sessão na Deriv expirou</div>' +
        '<div style="font-size:14px;line-height:1.5;color:#c9d1d9;margin-bottom:18px">' +
          'Por segurança, a Deriv encerra o acesso depois de um tempo. Entre de novo para continuar usando os robôs.' +
          (origem === 'robo' ? '' : '<br><span style="color:#8b949e;font-size:12.5px">Se um robô já estava ligado, ele continua operando — ao entrar de novo você volta a vê-lo.</span>') +
        '</div>' +
        '<button id="sdEntrar" style="width:100%;padding:12px;border:0;border-radius:10px;background:#f5c542;' +
          'color:#111;font-weight:700;font-size:15px;cursor:pointer;margin-bottom:8px">Entrar de novo</button>' +
        '<button id="sdDepois" style="width:100%;padding:10px;border:1px solid #30363d;border-radius:10px;' +
          'background:transparent;color:#8b949e;font-size:14px;cursor:pointer">Agora não</button>' +
      '</div>';
    document.body.appendChild(fundo);
    document.getElementById('sdEntrar').onclick = entrarDeNovo;
    document.getElementById('sdDepois').onclick = function () {
      adiadoAte = Date.now() + 10 * 60 * 1000; aberto = false; fundo.remove();
    };
  }

  // RETOMAR-V5: manda o token atual para os robos ligados no servidor
  function enviarToken(bearer) {
    try {
      var id = (typeof window.getDerivId === 'function') ? window.getDerivId() : null;
      if (!id || bearer.indexOf('ory_at_') !== 0) return;
      _f.call(window, 'https://alpha-dolar-backend.onrender.com/api/bot/token', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deriv_id: id, token: bearer })
      }).catch(function () {});
    } catch (e) {}
  }

  function checar() {
    var bearer = ls('deriv_bearer_token');
    if (!bearer || document.hidden) return;
    fetch('https://api.derivws.com/trading/v1/options/accounts', {
      headers: { 'Authorization': 'Bearer ' + bearer, 'Deriv-App-ID': '34lv1PuWzjElEuwWcDLyr' }
    }).then(function (r) { if (r.status === 401) mostrar('token'); else if (r.ok) enviarToken(bearer); }).catch(function () {});
  }

  // Servidor avisou que o robo parou por sessao expirada
  var _f = window.fetch;
  window.fetch = function (input) {
    var p = _f.apply(this, arguments);
    try {
      var u = typeof input === 'string' ? input : (input && input.url) || '';
      if (u.indexOf('/bot/stats/') >= 0) {
        p.then(function (r) {
          r.clone().json().then(function (d) {
            if (d && d.stop_reason === 'sessao_expirada') mostrar('robo');
          }).catch(function () {});
        }).catch(function () {});
      }
    } catch (e) {}
    return p;
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(checar, 1500); });
  else setTimeout(checar, 1500);
  setInterval(checar, 5 * 60 * 1000);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) checar(); });
})();
