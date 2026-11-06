/* LOGIN-TELA-V1 (rev 3: no PC alarga o cartão e fica lado a lado; no celular empilha) — tela "Conectar conta Deriv" nova (estilo escolha: já tenho conta / ainda não tenho)
 * Não muda a lógica: move o botão original "ENTRAR COM DERIV" e o link "CRIAR CONTA NA DERIV" para o layout novo.
 * Não age quando a página está voltando da Deriv (?code=), para não esconder o "AUTENTICANDO...".
 * Para desfazer: tirar este arquivo da página.
 */
(function () {
  'use strict';
  if (window.__loginTela) return; window.__loginTela = true;
  var q = new URLSearchParams(location.search);
  if (q.has('code') || q.has('acct1')) return;

  function achar(re) { return Array.prototype.find.call(document.querySelectorAll('button,a'), function (x) { return re.test(x.textContent || ''); }) || null; }
  function montar() {
    var B = achar(/ENTRAR COM DERIV/i), L = achar(/CRIAR CONTA NA DERIV/i);
    if (!B) return false;
    /* o cartão = primeiro ancestral que também contém o link de criar conta e é largo */
    var card = B.parentNode;
    while (card && card !== document.body && !(L ? card.contains(L) : false) ) card = card.parentNode;
    if (!card || card === document.body) card = B.parentNode;
    while (card.parentNode && card.parentNode !== document.body && card.getBoundingClientRect().width < 320) card = card.parentNode;

    var css = document.createElement('style');
    css.textContent = [
      '.lt{font-family:Inter,system-ui,-apple-system,sans-serif;color:#e8e6f5;text-align:center;width:100%;max-width:100%;box-sizing:border-box;margin:0;padding:0;overflow-wrap:anywhere;align-self:stretch}','.lt *{box-sizing:border-box}',
      '.lt-top{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:18px}',
      '.lt-logo{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;font:900 22px Inter,sans-serif;color:#fff;background:linear-gradient(135deg,#6d4dff,#9b7bff);box-shadow:0 0 24px rgba(124,92,255,.45)}',
      '.lt-top b{font-size:17px;letter-spacing:.5px}',
      '.lt h1{font-size:clamp(20px,3.4vw,27px);line-height:1.2;margin:0 0 10px;font-weight:800;text-wrap:balance}',
      '.lt-sub{font-size:14px;line-height:1.6;color:#a7a3c2;max-width:520px;margin:0 auto}',
      '.lt-flow{display:flex;align-items:center;justify-content:center;gap:10px;margin:22px 0}',
      '.lt-flow i{font-style:normal;flex:0 0 auto;width:50px;height:50px;border-radius:50%;display:grid;place-items:center;font-size:22px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.12)}',
      '.lt-flow i.d{background:#e2524f;border-color:#e2524f;color:#fff;font:900 20px Inter,sans-serif}',
      '.lt-flow i.a{background:linear-gradient(135deg,#6d4dff,#9b7bff);border:0;color:#fff;font:900 20px Inter,sans-serif}',
      '.lt-flow s{text-decoration:none;flex:0 1 46px;border-top:2px dashed rgba(167,163,194,.35)}',
      '.lt-opts{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;text-align:left;width:100%}',
      '.lt-op{border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:18px;background:rgba(255,255,255,.025);display:flex;flex-direction:column;gap:8px;min-width:0}',
      '.lt-op.pri{border-color:rgba(124,92,255,.55);background:rgba(124,92,255,.07)}',
      '.lt-op .ic{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;font-size:17px;background:rgba(124,92,255,.25)}',
      '.lt-op h3{margin:4px 0 0;font-size:16px;font-weight:800}',
      '.lt-op p{margin:0;font-size:13px;line-height:1.55;color:#a7a3c2;flex:1}',
      '.lt-op .lt-slot>*{width:100%!important;margin:6px 0 0!important;box-sizing:border-box}',
      '.lt-op .lt-slot>button,.lt-op .lt-slot>a{font-size:13px!important;letter-spacing:1.5px!important;padding:15px 12px!important;min-height:0!important;height:auto!important;justify-content:center}',
      '.lt-op .lt-slot>div{display:none!important}',
      '.lt-passos{margin:18px 0 0;text-align:left;border:1px solid rgba(251,191,36,.25);background:rgba(251,191,36,.05);border-radius:14px;padding:14px 16px}',
      '.lt-passos b.t{display:block;font-size:12px;letter-spacing:1.2px;text-transform:uppercase;color:#fbbf24;margin-bottom:8px}',
      '.lt-passos ol{margin:0;padding-left:20px;font-size:13px;line-height:1.7;color:#cfcbe4}',
      '.lt-passos em{font-style:normal;color:#fde68a;font-weight:700}',
      '.lt-chips{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin:16px 0 0}',
      '.lt-chips span{font-size:11.5px;color:#a7a3c2;border:1px solid rgba(255,255,255,.1);border-radius:999px;padding:5px 10px}',
      '.lt-pe{font-size:11.5px;line-height:1.55;color:#77738f;margin:16px auto 0;max-width:560px}'
    ].join('\n');
    document.head.appendChild(css);

    var box = document.createElement('div'); box.className = 'lt';
    box.innerHTML =
      '<div class="lt-top"><div class="lt-logo">$</div><b>Alpha Dolar</b></div>' +
      '<h1>Sua conta de operação fica na Deriv</h1>' +
      '<div class="lt-sub">A Deriv é a corretora: é lá que fica o seu dinheiro e onde as operações acontecem. Você só autoriza o Alpha Dolar a operar na sua conta — a sua senha nunca passa por aqui.</div>' +
      '<div class="lt-flow"><i>👤</i><s></s><i class="a">$</i><s></s><i class="d">d</i></div>' +
      '<div class="lt-opts">' +
        '<div class="lt-op pri"><div class="ic">🔑</div><h3>Já tenho conta na Deriv</h3><p>A Deriv abre em outra aba. Entre com seu e-mail e senha e autorize — você volta sozinho para cá.</p><div class="lt-slot" id="ltA"></div></div>' +
        '<div class="lt-op"><div class="ic">➕</div><h3>Ainda não tenho conta</h3><p>Crie grátis no site da Deriv (já vem com conta demo para treinar). Depois volte aqui e toque em <b>Entrar com Deriv</b>.</p><div class="lt-slot" id="ltB"></div></div>' +
      '</div>' +
      '<div class="lt-passos"><b class="t">Se a Deriv não voltar para cá</b><ol>' +
        '<li>Às vezes, depois do login, a Deriv fica no painel dela em vez de voltar.</li>' +
        '<li><em>Volte para esta aba</em> (ou feche a aba da Deriv): o Alpha Dolar conclui sozinho, sem pedir a senha de novo.</li>' +
        '<li>No celular, use o <em>Chrome ou Safari</em> — não o app da Deriv nem o navegador do Instagram/WhatsApp.</li>' +
      '</ol></div>' +
      '<div class="lt-chips"><span>🔒 Login oficial da Deriv</span><span>🧪 Comece na conta demo</span><span>🏦 Depósito e saque só na Deriv</span></div>' +
      '<div class="lt-pe">Operar envolve risco: os resultados passados não garantem os próximos. Negocie apenas com o que você pode perder. O Alpha Dolar não guarda o seu dinheiro.</div>';

    /* esconde o conteúdo antigo do cartão (sem apagar) e põe o novo */
    Array.prototype.forEach.call(card.children, function (k) { k.setAttribute('data-lt-old', '1'); k.style.display = 'none'; });
    card.appendChild(box);
    document.getElementById('ltA').appendChild(B);
    if (L) { document.getElementById('ltB').appendChild(L); L.setAttribute('target', '_blank'); }
    else document.getElementById('ltB').innerHTML = '<a href="https://t.deriv.link?t=2QKC88VGYBTZ" target="_blank" rel="noopener" style="display:block;text-align:center;padding:14px;border-radius:14px;border:1px solid rgba(255,255,255,.2);color:#e8e6f5;text-decoration:none;font-weight:800">Criar conta na Deriv</a>';
    [B, L].forEach(function (x) { if (x && x.getAttribute('data-lt-old')) { x.removeAttribute('data-lt-old'); x.style.display = ''; } });
    /* PC: alarga o cartão original (e os contêineres estreitos em volta) para os 2 cartões ficarem lado a lado */
    var largos = [];
    function alarga() {
      var pc = innerWidth >= 900;
      if (!largos.length) for (var el = card; el && el !== document.body; el = el.parentNode) {
        var w = el.getBoundingClientRect().width; if (w > 250 && w < 860) largos.push([el, el.style.width, el.style.maxWidth]);
      }
      largos.forEach(function (x, i) {
        var fora = i === largos.length - 1; /* só o mais de fora ganha 880px; os de dentro ocupam 100% dele */
        if (pc) { x[0].style.maxWidth = fora ? '880px' : 'none'; x[0].style.width = fora ? 'min(880px, calc(100vw - 48px))' : '100%'; x[0].style.boxSizing = 'border-box'; }
        else { x[0].style.width = x[1]; x[0].style.maxWidth = x[2]; }
      });
    }
    alarga(); var rt; addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(alarga, 150); });
    return true;
  }
  function ir() { if (!montar()) setTimeout(ir, 300); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ir); else ir();
})();
