/* ROTULO-ANALYTICS-V1 — troca o nome do botao "IA ALPHA" / "MODO IA ALPHA" por "ANALYTICS AO VIVO" em todos os robos,
   para o cliente entender que ali abre a tela de analise ao vivo. So muda o texto; o clique continua igual. */
(function () {
  if (window.__rotuloAnalytics) return; window.__rotuloAnalytics = true;
  var RX = /^[^A-Za-zÀ-ú]*(modo\s+)?ia\s+alpha[^A-Za-zÀ-ú]*$/i;
  function troca(root) {
    var L = (root || document).querySelectorAll('button, a, [role="button"]');
    for (var i = 0; i < L.length; i++) { var b = L[i]; if (b.__rotAn) continue; var t = String(b.textContent || '').replace(/\s+/g, ' ').trim();
      if (!t || t.length > 30 || !RX.test(t)) continue; b.__rotAn = true;
      var curto = b.id === 'ia2Lancar' || t.length <= 12;
      b.innerHTML = '<span aria-hidden="true">📊</span> ' + (curto ? 'ANALYTICS' : 'ANALYTICS AO VIVO');
      b.title = 'Abre a tela de análise ao vivo do robô'; b.setAttribute('aria-label', 'Analytics ao vivo'); }
  }
  function inicia() { troca(); new MutationObserver(function () { troca(); }).observe(document.body, { childList: true, subtree: true });
    var n = 0, t = setInterval(function () { troca(); if (++n > 30) clearInterval(t); }, 1000); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inicia); else inicia();
})();
