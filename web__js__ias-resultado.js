/* IAS-RESULTADO-V1 — IA Simples usa a mesma janela de Meta batida / Stop loss do IA Pro e do Avançado (AlphaResultado).
 * Não muda como o robô para: chama a janela antiga (que faz a limpeza da tela), esconde ela e mostra a nova.
 * Os números vêm da própria janela antiga (os mesmos que ela já mostrava); os dados do servidor são reserva.
 */
(function () {
  'use strict';
  if (window.__iasResultadoV1) return; window.__iasResultadoV1 = true;

  var inicio = null;
  setInterval(function () {
    var m = document.getElementById('botRunningModal');
    if (m && m.classList.contains('active') && !inicio) inicio = Date.now();
  }, 1000);

  function tipo(r) {
    r = String(r || '').toLowerCase();
    if (/take_profit|take|profit|meta|alvo/.test(r)) return 'win';
    if (/stop_loss|stop|loss/.test(r)) return 'stop';
    return null;
  }
  function num(v) { if (v == null) return null; var m = String(v).replace('−', '-').replace(',', '.').match(/-?\d+(\.\d+)?/); return m ? parseFloat(m[0]) : null; }
  function velha() { return document.getElementById('modalBotParado'); }
  function botaoVelho(rx) {
    var o = velha(); if (!o) return null;
    var L = o.querySelectorAll('button,a');
    for (var i = 0; i < L.length; i++) if (rx.test(L[i].textContent || '')) return L[i];
    return null;
  }
  function lerNumeros(stats) {
    var o = velha(), t = o ? (o.textContent || '').replace(/\s+/g, ' ') : '';
    var s = stats || {}; s = (s.stats && typeof s.stats === 'object') ? s.stats : s;
    var m;
    var valor = (m = t.match(/Resultado\s*([+\-−]?\s*\$?\s*-?[\d.,]+)/i)) ? num(m[1].replace(/\s/g, '')) : null;
    if (m && /^[\-−]/.test(m[1].trim()) && valor > 0) valor = -valor;
    if (valor == null) valor = num(s.lucro_liquido); if (valor == null) valor = num(s.saldo_liquido); if (valor == null) valor = num(s.profit) || 0;
    var ops = (m = t.match(/Total de trades\s*(\d+)/i)) ? +m[1] : (parseInt(s.total_trades || s.trades || 0, 10) || 0);
    var wr = (m = t.match(/Win Rate\s*([\d.,]+)\s*%/i)) ? num(m[1]) : num(s.win_rate);
    var wins = num(s.vitorias); if (wins == null) wins = num(s.wins);
    if (wins == null && wr != null && ops) wins = Math.round(wr / 100 * ops);
    return { valor: valor, ops: ops, wins: wins || 0 };
  }

  function card() { return document.querySelector('.ar-ov .ar-card'); }
  function limparNosso() {
    var c = card(); if (!c) return;
    var b2 = c.querySelector('.ar-ias2'); if (b2) b2.style.display = 'none';
    if (c.parentNode) c.parentNode.removeAttribute('data-ias');
  }
  function fecharVelha() { var f = botaoVelho(/fechar/i); try { if (f) f.click(); } catch (e) {} }
  function prepararCard(kind) {
    var c = card(); if (!c) return;
    var ov = c.parentNode; ov.setAttribute('data-ias', '1');
    var b = c.querySelector('.ar-b');
    if (b) b.textContent = kind === 'win' ? 'Fechar' : 'Entendi';
    if (!ov.__iasLigado) {
      ov.__iasLigado = true;
      ov.addEventListener('click', function (e) {
        if (ov.getAttribute('data-ias') !== '1') return;
        if (e.target === ov || (e.target.classList && e.target.classList.contains('ar-b'))) { fecharVelha(); limparNosso(); }
      });
    }
    var b2 = c.querySelector('.ar-ias2');
    if (!b2) {
      b2 = document.createElement('button'); b2.type = 'button'; b2.className = 'ar-ias2';
      b2.style.cssText = 'position:relative;width:100%;height:42px;margin-top:8px;border-radius:12px;background:transparent;border:1px solid rgba(255,255,255,.16);color:#cbd5e1;font:800 13px Inter,system-ui,sans-serif;cursor:pointer';
      b2.textContent = '↻ Continuar negociando';
      b2.addEventListener('click', function (e) {
        e.stopPropagation();
        ov.classList.remove('aberto'); limparNosso();
        var cont = botaoVelho(/continuar/i);
        if (cont) { try { cont.click(); } catch (er) {} }
      });
      c.appendChild(b2);
    }
    // só na meta: depois de um stop loss o certo é revisar a gestão, não religar com um toque
    b2.style.display = (kind === 'win' && botaoVelho(/continuar/i)) ? '' : 'none';
  }

  function embrulhar() {
    var orig = window.mostrarModalBotParado;
    if (typeof orig !== 'function' || orig.__ias) return;
    var w = function (reason, msg, stats) {
      var o = velha(); if (o) o.style.removeProperty('display');
      var r = orig.apply(this, arguments);
      try {
        var k = tipo(reason);
        if (!k || !window.AlphaResultado || typeof window.AlphaResultado.show !== 'function') return r;
        var n = lerNumeros(stats);
        var esconder = function () { var x = velha(); if (x) x.style.setProperty('display', 'none', 'important'); };
        esconder(); setTimeout(esconder, 60); setTimeout(esconder, 400);
        window.AlphaResultado.show({
          kind: k, bot: 'Alpha IA Simples', valor: n.valor, ops: n.ops, wins: n.wins, inicio: inicio,
          msg: k === 'win'
            ? 'O robô parou sozinho ao bater a sua meta. Bom momento para fazer uma pausa.'
            : 'O robô parou automaticamente no seu limite de perda para proteger o capital. Revise a gestão antes de voltar.'
        });
        prepararCard(k);
        inicio = null;
      } catch (e) { console.warn('[ias-resultado]', e); }
      return r;
    };
    w.__ias = true;
    window.mostrarModalBotParado = w;
  }
  embrulhar();
  setInterval(embrulhar, 1500); // se outro script redefinir a função depois, embrulha de novo
})();
