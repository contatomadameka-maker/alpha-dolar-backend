/* IA-AVANCADO-IR-V1: o IA Avançado agora é uma página própria (/bot-ia-avancado.html).
   Qualquer forma de abrir a tela antiga dentro do painel leva para a página nova. */
(function () {
  var URL_NOVA = '/bot-ia-avancado.html', indo = false;
  function ir() { if (indo) return; indo = true; location.href = URL_NOVA; }
  function embrulhar() {
    Object.keys(window).forEach(function (k) {
      if (!/^(abrir|open|mostrar)(Modal)?(Ia|IA)?Avan[cç]ado(Modal)?$/i.test(k)) return;
      var f = window[k]; if (typeof f !== 'function' || f.__ir) return;
      var w = function () { ir(); }; w.__ir = 1; window[k] = w;
    });
  }
  var n = 0; (function tenta() { embrulhar(); if (++n < 40) setTimeout(tenta, 500); })();
  setInterval(function () {
    var m = document.getElementById('iaAvancadoModal'); if (!m) return;
    var s = getComputedStyle(m);
    if (s.display !== 'none' && s.visibility !== 'hidden' && m.getClientRects().length) { m.style.setProperty('display', 'none', 'important'); ir(); }
  }, 300);
})();
