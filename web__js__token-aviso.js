/* TOKEN-AVISO-V1: avisa ANTES do acesso da Deriv vencer (30 dias) e manda o token novo aos robos do servidor.
   Data do login: deriv_token_em (login.html) ou, se faltar, o dia em que este token foi visto pela 1a vez. */
(function () {
  if (window.__tokenAvisoV1) return; window.__tokenAvisoV1 = true;
  if (/\/login/.test(location.pathname)) return;
  var DIA = 864e5, AVISA = 25, VALE = 30, BK = 'https://alpha-dolar-backend.onrender.com';
  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function grava(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function hash(s) { var h = 5381; for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return String(h >>> 0); }
  function contas() { try { var L = JSON.parse(ls('deriv_accounts') || '[]'); return (Array.isArray(L) ? L : []).map(function (a) { return a && (a.acct || a.loginid || a.account_id); }).filter(Boolean); } catch (e) { return []; } }
  function enviar(tk) { /* robos ligados no servidor passam a usar o token novo (RETOMAR-V5) */
    contas().forEach(function (id) { try { fetch(BK + '/api/bot/token', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ deriv_id: id, token: tk }) }).catch(function () {}); } catch (e) {} }); }
  function desde() {
    var tk = ls('deriv_bearer_token'); if (!tk) return null;
    var h = hash(tk), v = null, em = +ls('deriv_token_em') || 0; try { v = JSON.parse(ls('deriv_token_visto') || 'null'); } catch (e) {}
    if (!v || v.h !== h) { var novo = !!v; var usaEm = !!em && (!novo || em > v.t) && em <= Date.now(); v = { h: h, t: usaEm ? em : Date.now(), aprox: !usaEm }; grava('deriv_token_visto', JSON.stringify(v)); if (novo && tk.indexOf('ory_at_') === 0) enviar(tk); }
    else if (em > v.t) { v.t = em; v.aprox = false; grava('deriv_token_visto', JSON.stringify(v)); }
    return v;
  }
  function renovar() {
    ['deriv_accounts', 'deriv_conta_ativa', 'deriv_token_demo', 'deriv_token_real', 'deriv_balance_demo', 'deriv_balance_real', 'deriv_bearer_token'].forEach(function (k) { try { localStorage.removeItem(k); } catch (e) {} });
    location.href = '/login?expirou=1';
  }
  function faixa() {
    var v = desde(); if (!v || document.getElementById('tkAviso')) return;
    var dias = Math.floor((Date.now() - v.t) / DIA); if (dias < AVISA) return;
    if (Date.now() < (+ls('deriv_token_adiado') || 0)) return;
    var resta = VALE - dias, txt = resta > 0 ? 'Sua conexão com a Deriv vence em <b>' + resta + (resta > 1 ? ' dias' : ' dia') + '</b>' : 'Sua conexão com a Deriv já tem <b>' + dias + ' dias</b> e pode ser encerrada a qualquer momento';
    var d = document.createElement('div'); d.id = 'tkAviso';
    d.style.cssText = 'position:fixed;left:50%;bottom:calc(14px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);z-index:2147483000;width:min(620px,calc(100% - 24px));box-sizing:border-box;' +
      'display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;padding:10px 12px;border-radius:12px;background:#0d1117;border:1px solid #d4a017;box-shadow:0 6px 24px rgba(0,0,0,.5);color:#e6edf3;font:13px/1.45 system-ui,sans-serif';
    d.innerHTML = '<span style="font-size:20px">🔑</span><span style="flex:1;min-width:200px">' + txt + (v.aprox ? ' <small style="color:#8b949e">(data aproximada)</small>' : '') + '. Entre de novo para nenhum robô parar no meio — leva 10 segundos.</span>' +
      '<button id="tkRen" type="button" style="padding:8px 14px;border:0;border-radius:9px;background:#f5c542;color:#111;font-weight:700;cursor:pointer">Renovar agora</button>' +
      '<button id="tkDep" type="button" style="padding:8px 12px;border:1px solid #30363d;border-radius:9px;background:transparent;color:#8b949e;cursor:pointer">Lembrar amanhã</button>';
    document.body.appendChild(d);
    document.getElementById('tkRen').onclick = renovar;
    document.getElementById('tkDep').onclick = function () { grava('deriv_token_adiado', String(Date.now() + 20 * 3600e3)); d.remove(); };
  }
  function inicia() { setTimeout(faixa, 2500); setInterval(faixa, 30 * 60000); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inicia); else inicia();
})();
