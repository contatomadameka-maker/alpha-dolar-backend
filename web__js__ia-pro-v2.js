/* Alpha Dolar — IA PRO v2 (layout novo, igual à amostra aprovada)
 * Monta a tela nova (cabeçalho + 3 colunas) e MOVE os campos originais para dentro dela,
 * pelos ids. Os campos continuam sendo os mesmos elementos, com os mesmos cliques,
 * então a lógica do robô não muda. Nada do original é apagado, só escondido.
 * Para desfazer: remover este arquivo da página.
 */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var LIMIAR = { baixo_risco: 70, preciso: 60, balanceado: 52, veloz: 45 };
  var NOME_TIPO = { DIGITEVEN: 'PAR', DIGITODD: 'ÍMPAR', DIGITOVER: 'OVER', DIGITUNDER: 'UNDER', DIGITMATCH: 'MATCH', DIGITDIFF: 'DIFF', CALL: 'RISE', PUT: 'FALL' };
  function st() { try { return window._proState || null; } catch (e) { return null; } }
  function num(s) { var m = String(s == null ? '' : s).replace(',', '.').match(/-?\d+(\.\d+)?/); return m ? parseFloat(m[0]) : null; }
  function m$(n) { return (n < 0 ? '−$' : '+$') + Math.abs(n).toFixed(2); }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  /* ───────────────────────── estilo ───────────────────────── */
  var css = document.createElement('style');
  css.textContent = [
    '#alphaIaProModal.p2-on{background:#05060a!important;overflow:auto!important;isolation:isolate}',
    '#alphaIaProModal.p2-on>*:not(.p2):not(.p2-bg):not(.p2-keep){display:none!important}',
    '#alphaIaProModal>.p2-keep{z-index:100!important}',
    '.p2-bg{position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none}',
    '.p2{position:relative;z-index:1;max-width:1400px;margin:0 auto;padding:18px 20px 28px;color:#e8ecf4;font-family:Inter,system-ui,sans-serif;box-sizing:border-box;text-align:left}',
    '.p2 *,.p2 *::before,.p2 *::after{box-sizing:border-box}',
    /* cabecalho */
    '.p2-hd{display:flex;align-items:center;gap:14px;margin-bottom:14px;flex-wrap:wrap}',
    '.p2-ic{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;font-size:23px;border:1px solid rgba(139,92,246,.4);background:rgba(139,92,246,.12);box-shadow:0 0 26px rgba(139,92,246,.25)}',
    '.p2-hd h1{margin:0;font-size:22px;font-weight:900;display:flex;align-items:center;gap:10px;color:#fff}',
    '.p2-hd h1 span{font-size:10px;letter-spacing:1.5px;padding:4px 9px;border-radius:999px;background:linear-gradient(135deg,#a855f7,#ec4899);color:#fff}',
    '.p2-hd p{margin:3px 0 0;color:#8b93a7;font-size:12.5px}.p2-sp{flex:1}',
    '.p2-acc{display:flex;gap:8px;align-items:center;flex-wrap:wrap}',
    '.p2-tg{display:flex;background:rgba(0,0,0,.35);border:1px solid #262a40;border-radius:999px;padding:3px;gap:2px}',
    '.p2-tg>*{all:unset;cursor:pointer;padding:6px 16px!important;border-radius:999px!important;font:800 12px Inter,system-ui,sans-serif!important;color:#8b93a7!important;background:transparent!important;border:0!important;box-shadow:none!important;width:auto!important;margin:0!important}',
    '.p2-tg>*.on{background:#7c5cff!important;color:#fff!important}',
    '.p2-pill,.p2-pill *{font:700 13px "Space Mono",ui-monospace,monospace!important;color:#fff!important;background:none!important;border:0!important;padding:0!important;margin:0!important;box-shadow:none!important}',
    '.p2 .p2-pill{border:1px solid #2a2d45!important;border-radius:999px!important;padding:7px 14px!important;background:rgba(0,0,0,.35)!important;display:flex!important;align-items:center;gap:6px;min-height:0!important;width:auto!important;height:auto!important}',
    '.p2-pill small{font:700 10px Inter,system-ui,sans-serif!important;color:#8b93a7!important;letter-spacing:.5px}',
    '.p2 .p2-alpha{all:unset;cursor:pointer;border:1px solid rgba(139,92,246,.45)!important;border-radius:999px!important;padding:7px 12px!important;font:800 11.5px Inter,system-ui,sans-serif!important;color:#e9d5ff!important;background:rgba(139,92,246,.14)!important;white-space:nowrap;width:auto!important;margin:0!important;box-shadow:none!important}',
    '.p2-x{all:unset;cursor:pointer;width:36px;height:36px;border-radius:12px;display:grid;place-items:center;font-size:16px;font-weight:900;color:#fca5a5;border:1px solid rgba(248,113,113,.45);background:rgba(248,113,113,.1)}',
    /* colunas */
    '.p2-cols{display:grid;grid-template-columns:340px minmax(0,1fr) 300px;gap:14px;align-items:start}',
    '.p2-pn{background:rgba(12,12,22,.7);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid rgba(139,92,246,.26);border-radius:20px;padding:16px;min-width:0}',
    '.p2-lb{font-size:10px;font-weight:800;letter-spacing:1px;color:#7c84a0;text-transform:uppercase;margin:0 0 6px}',
    '.p2-ttl{font-size:11px;font-weight:900;letter-spacing:1.4px;color:#9aa3c0;text-transform:uppercase;display:flex;align-items:center;gap:8px;margin-bottom:12px}',
    '.p2-ttl i{width:7px;height:7px;border-radius:50%;background:#4ade80;box-shadow:0 0 8px #4ade80;animation:p2pl 1.6s infinite}@keyframes p2pl{50%{opacity:.3}}',
    '.p2-g2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}.p2-g3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:12px}',
    '.p2-g2>div,.p2-g3>div{min-width:0}',
    '.p2 .p2-in{width:100%!important;height:40px!important;border-radius:11px!important;border:1px solid #262a40!important;background:rgba(0,0,0,.4)!important;color:#fff!important;font:700 14px Inter,system-ui,sans-serif!important;padding:0 10px!important;outline:0!important;margin:0!important;box-shadow:none!important;min-width:0!important;display:block!important}',
    '.p2 select.p2-in option{background:#0d0f1a;color:#fff}',
    '.p2 .p2-in:focus{border-color:#8b5cf6!important}',
    '.p2-chips{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap}',
    '.p2 .p2-chips>*{all:unset;cursor:pointer;flex:1 1 0;min-width:52px;text-align:center;border:1px solid #262a40!important;border-radius:10px!important;padding:8px 4px!important;font:700 12px Inter,system-ui,sans-serif!important;color:#aab!important;background:transparent!important;box-shadow:none!important;margin:0!important;white-space:nowrap;width:auto!important;height:auto!important;box-sizing:border-box}',
    '.p2 .p2-chips>*.on{border-color:#8b5cf6!important;background:rgba(139,92,246,.16)!important;color:#fff!important}',
    '.p2 .p2-chips.p2-neg>*{flex:1 1 40%}',
    '.p2 .p2-chips>input.p2-multin{flex:0 0 62px;min-width:0;cursor:text;border-style:dashed!important;font-family:"Space Mono",ui-monospace,monospace!important;color:#fff!important}',
    '.p2 .p2-chips>input[type=hidden]{display:none!important}',
    '.p2-dim{opacity:.45;pointer-events:none}',
    '.p2-auto-note{font-size:10.5px;color:#a78bfa;margin:-6px 0 10px}',
    /* perda na sequencia (#proStopBar) */
    '.p2 #proStopBar{border:1px solid rgba(251,191,36,.3)!important;background:rgba(251,191,36,.07)!important;border-radius:12px!important;padding:10px 12px!important;font-size:12px!important;color:#fde68a!important;line-height:1.45;margin:0 0 12px!important;display:block!important;width:auto!important;box-shadow:none!important}',
    /* opcoes avancadas */
    '.p2-adv{border:1px solid #23263a;border-radius:14px;background:rgba(0,0,0,.22);margin-bottom:12px}',
    '.p2-adv-h{all:unset;cursor:pointer;display:flex;align-items:center;gap:8px;width:100%;box-sizing:border-box;padding:11px 12px;font:800 11px Inter,system-ui,sans-serif;letter-spacing:1px;color:#9aa3c0;text-transform:uppercase}',
    '.p2-adv-h em{font-style:normal;margin-left:auto;transition:transform .2s}.p2-adv.aberto .p2-adv-h em{transform:rotate(180deg)}',
    '.p2-adv-h b{font:700 10px Inter,system-ui,sans-serif;letter-spacing:0;color:#a78bfa;text-transform:none}',
    '.p2-adv-c{display:none;padding:0 12px 12px;font-size:12.5px}.p2-adv.aberto .p2-adv-c{display:block}',
    '.p2-adv-c>*{margin-top:0!important;margin-bottom:10px!important}.p2-adv-c>*:last-child{margin-bottom:0!important}',
    '.p2-adv-c input:not([type=checkbox]):not([type=radio]),.p2-adv-c select{background:rgba(0,0,0,.4)!important;border:1px solid #262a40!important;color:#fff!important;border-radius:9px!important}',
    /* botao iniciar */
    '.p2 #proStartBtn{width:100%!important;border:0!important;border-radius:14px!important;padding:14px!important;font:900 15px Inter,system-ui,sans-serif!important;color:#fff!important;background:linear-gradient(135deg,#7c3aed,#22c55e)!important;box-shadow:0 10px 30px rgba(124,92,255,.3)!important;cursor:pointer;margin:0!important;height:auto!important;display:block!important}',
    '.p2 #proStartBtn.p2-run{background:linear-gradient(135deg,#dc2626,#f97316)!important;box-shadow:0 10px 30px rgba(239,68,68,.3)!important}',
    /* centro */
    '.p2-lead{display:flex;align-items:center;gap:18px;border-radius:18px;padding:16px;margin-bottom:12px;border:1px solid rgba(148,163,184,.22);background:rgba(0,0,0,.25);transition:border-color .4s,background .4s}',
    '.p2-lead.on{background:linear-gradient(135deg,rgba(74,222,128,.1),rgba(34,211,238,.05));border-color:rgba(74,222,128,.35)}',
    '.p2-ring{position:relative;width:150px;height:150px;flex-shrink:0}.p2-ring svg{width:100%;height:100%;transform:rotate(-90deg)}',
    '.p2-ring .c{position:absolute;inset:0;display:grid;place-items:center;text-align:center}.p2-ring .c b{font:900 34px Inter,system-ui,sans-serif;display:block}.p2-ring .c small{font-size:10px;font-weight:800;letter-spacing:1px;color:#9aa3c0}',
    '.p2-lead h3{margin:0 0 4px;font:900 22px Inter,system-ui,sans-serif}.p2-lead p{margin:0;color:#aab3c9;font-size:13px;line-height:1.5}',
    '.p2-bd{display:inline-block;margin-bottom:8px;font-size:10px;font-weight:900;letter-spacing:1px;padding:4px 9px;border-radius:999px}',
    '.p2-digs{display:flex;gap:4px;margin:6px 0 12px}.p2-digs b{flex:1;text-align:center;border-radius:8px;padding:6px 0;font:700 13px "Space Mono",ui-monospace,monospace;background:rgba(0,0,0,.35);border:1px solid #23263a}',
    '.p2-digs b.p{color:#22d3ee}.p2-digs b.i{color:#f472b6}.p2-digs b.n{border-color:#fff;box-shadow:0 0 12px rgba(255,255,255,.3)}',
    '.p2-duel{background:rgba(0,0,0,.3);border:1px solid #23263a;border-radius:14px;padding:11px 13px;margin-bottom:8px;transition:border-color .3s}',
    '.p2-duel.top{border-color:rgba(74,222,128,.45);box-shadow:0 0 22px rgba(74,222,128,.12)}',
    '.p2-duel .h{display:flex;justify-content:space-between;font-size:12px;font-weight:900;letter-spacing:.8px;margin-bottom:7px}.p2-duel .h span{color:#6f7790;font-weight:700;letter-spacing:0}',
    '.p2-bar{position:relative;height:14px;border-radius:8px;background:#141726;overflow:hidden;display:flex}.p2-bar i{display:block;height:100%;transition:width .6s}',
    '.p2-bar u{position:absolute;left:50%;top:-2px;bottom:-2px;width:2px;background:rgba(255,255,255,.35)}',
    '.p2-duel .f{display:flex;justify-content:space-between;font:700 11px "Space Mono",ui-monospace,monospace;margin-top:5px;color:#9aa3c0}',
    '.p2-note{font-size:10.5px;color:#6f7790;line-height:1.45;margin-top:8px}',
    '.p2-motor{font-size:11px;color:#8b93a7;margin:-4px 0 10px}.p2 .p2-motor #proMlFase{display:inline!important;color:#c4b5fd!important;font-size:11px!important;background:none!important;border:0!important;padding:0!important;margin:0!important}',
    /* direita */
    '.p2-kpi{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}.p2-kpi div{background:rgba(0,0,0,.35);border:1px solid #23263a;border-radius:12px;padding:9px 10px}',
    '.p2-kpi span{display:block;font-size:9.5px;font-weight:800;letter-spacing:.6px;color:#7c84a0;text-transform:uppercase}.p2-kpi b{display:block;font:700 17px "Space Mono",ui-monospace,monospace;margin-top:2px}',
    '.p2-spark{width:100%;height:70px;display:block}',
    '.p2-tl{display:flex;gap:4px;flex-wrap:wrap;min-height:12px}.p2-tl i{width:12px;height:12px;border-radius:4px}',
    '.p2 #proFeed>div{padding:5px 8px!important;margin-bottom:4px;border-radius:8px;background:rgba(0,0,0,.25);border-bottom:0!important;font:12px "Space Mono",ui-monospace,monospace;line-height:1.4;word-break:break-word}',
    '.p2 #proFeed{max-height:340px!important;min-height:120px!important;overflow:auto!important;background:transparent!important;border:0!important;padding:0!important;margin:0!important;font-size:12px!important;height:auto!important;flex:none!important}',
    '.p2 .p2-amp{all:unset;cursor:pointer;font:800 10px Inter,system-ui,sans-serif!important;letter-spacing:.5px;color:#a78bfa!important;border:1px solid rgba(139,92,246,.4)!important;border-radius:8px!important;padding:4px 8px!important;background:transparent!important;width:auto!important;margin:0 0 0 auto!important;text-transform:none}',
    '@media (max-width:1100px){.p2-cols{grid-template-columns:320px minmax(0,1fr)}.p2-dir{grid-column:1/-1}}',
    '.p2-adv-c button{background:rgba(139,92,246,.12);border:1px solid rgba(139,92,246,.35);color:#e9d5ff;border-radius:9px;padding:6px 10px;font:700 12px Inter,system-ui,sans-serif;cursor:pointer}',
    '.p2-adv-c label{color:#9aa3c0;font-size:11px}',
    '@media (max-width:760px){.p2-hd{position:relative}.p2-hd>div:nth-child(2){padding-right:46px}.p2-acc{width:100%}.p2-x{position:absolute;top:5px;right:0}.p2{padding:12px 12px 24px}.p2-cols{grid-template-columns:1fr}.p2-lead{flex-direction:column;text-align:center}.p2-ring{width:130px;height:130px}.p2-hd h1{font-size:18px}.p2-hd p{display:none}}'
  ].join('\n');
  document.head.appendChild(css);

  /* ─────────────────── montagem da tela nova ─────────────────── */
  var montado = false, R = {};

  function soltarFlutuantes(raiz, destino) { // modais internos (ex.: regra de dígitos) não podem ficar dentro de algo escondido
    Array.prototype.slice.call(raiz.querySelectorAll('*')).forEach(function (e) {
      var p = e.style.position; if (!p) { try { p = getComputedStyle(e).position; } catch (x) {} }
      if (p === 'fixed') { destino.appendChild(e); e.classList.add('p2-keep'); }
    });
  }
  function interativo(b) { return b && b.nodeType === 1 && (b.matches('input,select,button,textarea,label,[onclick]') || b.querySelector('input,select,button,textarea,[onclick]')); }
  function mover(e, dest, cls) { if (!e) return null; if (cls) e.classList.add(cls); dest.appendChild(e); return e; }
  function campo(rot, e, wrap) { var d = el('div'); d.appendChild(el('div', 'p2-lb', rot)); if (e) { e.classList.add('p2-in'); d.appendChild(e); } wrap.appendChild(d); return d; }

  function montar() {
    var modal = $('alphaIaProModal'), cols = $('proTwoCols'), left = $('proColLeft');
    if (!modal || !cols || !left || !$('proStartBtn') || !$('proFeed')) return false;

    var bg = el('canvas', 'p2-bg'); modal.insertBefore(bg, modal.firstChild); iniciarFundo(bg);
    var raiz = el('div', 'p2');
    soltarFlutuantes(cols, modal);

    /* cabeçalho: título + Demo/Real + saldo + Modo IA Alpha + fechar */
    var hd = el('div', 'p2-hd',
      '<div class="p2-ic">✨</div><div><h1>Alpha IA Pro <span>PREMIUM</span></h1><p>3 modelos combinados · Voz IA · Score máximo</p></div><div class="p2-sp"></div>');
    var acc = el('div', 'p2-acc'), tg = el('div', 'p2-tg');
    mover($('proBtnDemo'), tg); mover($('proBtnReal'), tg); if (tg.children.length) acc.appendChild(tg);
    mover($('proSaldoBox'), acc, 'p2-pill');
    var alphaBtn = modal.querySelector('[onclick*="abrirModalIaAlpha"]');
    if (alphaBtn) { alphaBtn.classList.add('p2-alpha'); alphaBtn.textContent = '✨ Modo IA Alpha'; acc.appendChild(alphaBtn); }
    var x = el('button', 'p2-x', '✕'); x.type = 'button'; x.title = 'Fechar';
    x.onclick = function () { if (typeof window.fecharAlphaIaPro === 'function') window.fecharAlphaIaPro(); };
    acc.appendChild(x); hd.appendChild(acc); raiz.appendChild(hd);

    var grid = el('div', 'p2-cols'); raiz.appendChild(grid);

    /* ── coluna esquerda: configuração ── */
    var pe = el('div', 'p2-pn'); grid.appendChild(pe);
    var mf = $('proModoFixo'), ma = $('proModoAuto');
    if (mf || ma) { pe.appendChild(el('div', 'p2-lb', 'Tipo de contrato')); var cm = el('div', 'p2-chips p2-modo'); mover(mf, cm); mover(ma, cm); pe.appendChild(cm); R.modo = cm; }
    var g2 = el('div', 'p2-g2'); R.ct = campo('Contrato', $('proContractType'), g2); campo('Mercado', $('proSymbol'), g2); pe.appendChild(g2);
    R.autoNote = el('div', 'p2-auto-note', '🔄 No modo Auto o robô escolhe o contrato com maior score.'); R.autoNote.style.display = 'none'; pe.appendChild(R.autoNote);
    var g3 = el('div', 'p2-g3'); campo('Entrada', $('proStake'), g3); campo('Lucro alvo', $('proTarget'), g3); campo('Stop loss', $('proStop'), g3); pe.appendChild(g3);

    var mb = modal.querySelectorAll('.pro-mult-btn'), mi = $('proMultiplier');
    if (mb.length || mi) {
      pe.appendChild(el('div', 'p2-lb', 'Multiplicador'));
      var cmu = el('div', 'p2-chips p2-mult'); Array.prototype.slice.call(mb).forEach(function (b) { cmu.appendChild(b); });
      if (mi) { if (mi.tagName === 'INPUT' && mi.type !== 'hidden') { mi.classList.add('p2-multin'); mi.title = 'Multiplicador personalizado'; } cmu.appendChild(mi); }
      pe.appendChild(cmu); R.mult = cmu;
    }
    var nb = modal.querySelectorAll('.pro-modoneg-btn');
    if (nb.length) {
      pe.appendChild(el('div', 'p2-lb', 'Modo de negociação'));
      var cn = el('div', 'p2-chips p2-neg'); Array.prototype.slice.call(nb).forEach(function (b) { cn.appendChild(b); });
      pe.appendChild(cn); R.neg = cn;
    }

    /* opções avançadas: o que sobrou na coluna esquerda (perdas virtuais, frequência, voz, regras…) */
    var adv = el('div', 'p2-adv' + (lsGet('p2_adv') === '1' ? ' aberto' : ''));
    var ah = el('button', 'p2-adv-h', '⚙ Opções avançadas <b></b><em>▾</em>'); ah.type = 'button';
    ah.onclick = function () { adv.classList.toggle('aberto'); lsSet('p2_adv', adv.classList.contains('aberto') ? '1' : '0'); };
    var ac = el('div', 'p2-adv-c'); adv.appendChild(ah); adv.appendChild(ac); R.advResumo = ah.querySelector('b');

    var start = $('proStartBtn'), stopBar = $('proStopBar'), feed = $('proFeed');
    Array.prototype.slice.call(left.children).forEach(function (b) { if (!b.contains(start) && interativo(b)) ac.appendChild(b); });
    // se o botão Iniciar estiver dentro de um bloco com outros controles (ex.: Voz), traz esses controles também
    var sb = start; while (sb.parentNode && sb.parentNode !== left) sb = sb.parentNode;
    if (sb !== start && sb.parentNode === left) Array.prototype.slice.call(sb.querySelectorAll('input,select,[onclick]')).forEach(function (c) {
      if (!sb.contains(c) || c === start || start.contains(c) || c.contains(start)) return;
      var blk = c; while (blk.parentNode !== sb && !blk.parentNode.contains(start)) blk = blk.parentNode;
      if (!blk.contains(start)) ac.appendChild(blk);
    });
    // controles desconhecidos que sobrarem nas outras colunas também vão para as opções (nada some)
    [$('proColCenter'), $('proColRight')].forEach(function (col) {
      if (!col) return;
      Array.prototype.slice.call(col.children).forEach(function (b) {
        if ((stopBar && b.contains(stopBar)) || b.id === 'proAutoPainel' || b.contains(feed) || ($('proScore') && b.contains($('proScore')))) return;
        if (b.querySelector('[onclick*="proAbrirFeedCompleto"]') || b.matches('[onclick*="proAbrirFeedCompleto"]')) return;
        if (interativo(b)) ac.appendChild(b);
      });
    });
    if (ac.children.length) pe.appendChild(adv);
    if (stopBar) pe.appendChild(stopBar);
    pe.appendChild(start);

    /* ── centro: análise ── */
    var pc = el('div', 'p2-pn'); grid.appendChild(pc);
    R.ttl = el('div', 'p2-ttl', '<i></i><span>Análise em tempo real</span>'); pc.appendChild(R.ttl);
    var ml = $('proMlFase'); if (ml) { var mo = el('div', 'p2-motor', 'Motor: '); mo.appendChild(ml); pc.appendChild(mo); }
    R.lead = el('div', 'p2-lead'); pc.appendChild(R.lead);
    pc.appendChild(el('div', 'p2-lb', 'Últimos dígitos'));
    R.digs = el('div', 'p2-digs'); pc.appendChild(R.digs);
    R.duels = el('div'); pc.appendChild(R.duels);
    pc.appendChild(el('div', 'p2-note', 'O score é o do motor do robô. As barras mostram a distribuição dos últimos 20 dígitos. Força do sinal não é chance de acerto: nos índices sintéticos cada dígito é sorteado de forma independente.'));

    /* ── direita: sessão + registros ── */
    var pd = el('div', 'p2-pn p2-dir'); grid.appendChild(pd);
    pd.appendChild(el('div', 'p2-ttl', '📊 Sessão'));
    R.kpi = el('div', 'p2-kpi', '<div><span>Lucro</span><b data-k="l">+$0.00</b></div><div><span>Acerto</span><b data-k="w">—</b></div><div><span>Operações</span><b data-k="n">0</b></div><div><span>Maior seq.</span><b data-k="s">0</b></div>');
    pd.appendChild(R.kpi);
    R.spark = el('canvas', 'p2-spark'); pd.appendChild(R.spark);
    var ltl = el('div', 'p2-lb', 'Linha do tempo'); ltl.style.marginTop = '10px'; pd.appendChild(ltl);
    R.tl = el('div', 'p2-tl'); pd.appendChild(R.tl);
    var rh = el('div', 'p2-ttl', '<span>Registros</span>'); rh.style.margin = '14px 0 8px';
    var amp = modal.querySelector('[onclick*="proAbrirFeedCompleto"]'); if (amp) { amp.classList.add('p2-amp'); amp.textContent = '⤢ Ampliar'; rh.appendChild(amp); }
    pd.appendChild(rh); R.feedSlot = el('div', 'p2-feedslot'); pd.appendChild(R.feedSlot); R.feedSlot.appendChild(feed);
    // o "Ampliar" original devolve os registros para a coluna antiga (escondida): devolve para a tela nova
    var fecharOrig = window.proFecharFeedCompleto;
    window.proFecharFeedCompleto = function () { try { if (typeof fecharOrig === 'function') fecharOrig.apply(this, arguments); } catch (e) {} devolverFeed(true); };

    modal.appendChild(raiz);
    modal.classList.add('p2-on');

    // clique nos chips marca na hora (o estado real é conferido no laço)
    [R.modo, R.mult, R.neg, tg].forEach(function (g) {
      if (!g) return;
      g.addEventListener('click', function (ev) {
        var b = ev.target; while (b && b.parentNode !== g) b = b.parentNode; if (!b || b.tagName === 'INPUT') return;
        Array.prototype.forEach.call(g.children, function (c) { c.classList.toggle('on', c === b); }); g._manual = b; g._manualEm = Date.now();
      }, true);
    });
    R.tg = tg;
    montado = true;
    return true;
  }

  /* ─────────────────── estado dos chips ─────────────────── */
  function argDe(b) { var o = b.getAttribute('onclick') || ''; var m = o.match(/\(\s*['"]?([^'",)]*)/); return m ? m[1] : ''; }
  function marcar(g, fn) {
    if (!g) return;
    if (g._manual && Date.now() - g._manualEm < 1500) return;
    var achou = null; Array.prototype.forEach.call(g.children, function (c) { if (!achou && c.tagName !== 'INPUT' && fn(c)) achou = c; });
    if (!achou) achou = g._manual || null;
    Array.prototype.forEach.call(g.children, function (c) { c.classList.toggle('on', c === achou); });
  }
  function atualizarChips() {
    var s = st() || {};
    var modo = String(window._proModo || '').toLowerCase(), auto = modo.indexOf('auto') >= 0;
    marcar(R.modo, function (c) { return modo ? (c.id === 'proModoAuto') === auto : false; });
    if (R.ct) R.ct.classList.toggle('p2-dim', auto);
    if (R.autoNote) R.autoNote.style.display = auto ? 'block' : 'none';
    var mi = $('proMultiplier'), mv = num(mi && mi.value); if (mv === null) mv = num(s.mult);
    marcar(R.mult, function (c) { var v = num(argDe(c)); if (v === null) v = num(c.textContent); return mv !== null && v !== null && Math.abs(v - mv) < 0.001; });
    var neg = String(window._proModoNeg || '');
    marcar(R.neg, function (c) { return !!neg && (argDe(c) === neg || c.getAttribute('data-modo') === neg); });
    var conta = ''; try { conta = String(s.contaTipo || s.conta || s.accountType || window._proConta || lsGet('deriv_conta_ativa') || ''); } catch (e) {}
    conta = conta.toLowerCase();
    var demo = /demo|dot|vrt/.test(conta), real = !demo && /real|rot|cr\d/.test(conta);
    marcar(R.tg, function (c) { return (demo && c.id === 'proBtnDemo') || (real && c.id === 'proBtnReal'); });
    var sb = $('proStartBtn'); if (sb) sb.classList.toggle('p2-run', !!s.running);
    if (R.advResumo) {
      var on = [];
      if (window._proFreqAtivo) on.push('frequência');
      if (window._proRegras && window._proRegras.length) on.push(window._proRegras.length + ' regra' + (window._proRegras.length > 1 ? 's' : ''));
      R.advResumo.textContent = on.length ? '· ' + on.join(', ') : '';
    }
  }

  /* ─────────────────── centro: sinal líder ─────────────────── */
  function arc(p, c) { var r = 64, C = 2 * Math.PI * r; return '<svg viewBox="0 0 150 150"><circle cx="75" cy="75" r="' + r + '" fill="none" stroke="#1c2033" stroke-width="12"/><circle cx="75" cy="75" r="' + r + '" fill="none" stroke="' + c + '" stroke-width="12" stroke-linecap="round" stroke-dasharray="' + (C * Math.max(0, Math.min(1, p))) + ' ' + C + '" style="filter:drop-shadow(0 0 8px ' + c + ');transition:stroke-dasharray .6s"/></svg>'; }
  function desenharCentro() {
    var s = st() || {};
    var sym = $('proSymbol'), nomeMerc = sym && sym.options && sym.selectedIndex >= 0 ? sym.options[sym.selectedIndex].text : '';
    R.ttl.querySelector('span').textContent = 'Análise em tempo real' + (nomeMerc ? ' · ' + nomeMerc : '');
    var dig = (s.digits || []).map(Number).filter(function (v) { return !isNaN(v); });
    var score = num(($('proScore') || {}).textContent), tipoRaw = String((($('proTipo') || {}).textContent) || '').trim();
    if (!tipoRaw || tipoRaw === '—' || tipoRaw === '-') { var ctp = $('proContractType'); tipoRaw = ctp ? ctp.value : ''; }
    var tipo = NOME_TIPO[tipoRaw] || tipoRaw || '—', lim = LIMIAR[window._proModoNeg] || 52, rodando = !!s.running;
    var ok = score !== null && score >= lim, perto = score !== null && score >= lim - 8;
    var cor = !rodando || score === null ? '#94a3b8' : ok ? '#4ade80' : perto ? '#fbbf24' : '#94a3b8';
    var nivel = !rodando ? ['AGUARDANDO INÍCIO', '#94a3b8'] : ok ? ['SINAL FORTE', '#4ade80'] : perto ? ['SINAL MODERADO', '#fbbf24'] : ['SINAL FRACO', '#94a3b8'];
    var modoTxt = String(window._proModoNeg || 'balanceado').replace('_', ' ');
    var txt = !rodando ? 'Configure à esquerda e clique em <b>Iniciar</b> para o robô começar a analisar.'
      : ok ? 'O robô vai entrar em <b>' + tipo + '</b> no próximo tick.<br>Modo ' + modoTxt + ' entra a partir de score ' + lim + '.'
      : 'Sinal abaixo do mínimo — o robô espera um padrão mais claro.<br>Modo ' + modoTxt + ' entra a partir de score ' + lim + '.';
    R.lead.className = 'p2-lead' + (ok && rodando ? ' on' : '');
    R.lead.innerHTML = '<div class="p2-ring">' + arc((score || 0) / 100, cor) + '<div class="c"><div><b style="color:' + cor + '">' + (score === null ? '—' : Math.round(score)) + '</b><small>SCORE</small></div></div></div>' +
      '<div><span class="p2-bd" style="background:' + nivel[1] + '22;color:' + nivel[1] + '">' + (ok && rodando ? '👑 ' : '') + nivel[0] + '</span><h3 style="color:' + (ok && rodando ? '#4ade80' : '#e2e8f0') + '">' + tipo + '</h3><p>' + txt + '</p></div>';
    if (!dig.length) { R.digs.innerHTML = '<b style="flex:1;color:#6f7790;font-weight:600">aguardando ticks…</b>'; R.duels.innerHTML = ''; return; }
    R.digs.innerHTML = dig.slice(-12).map(function (v, i, a) { return '<b class="' + (v % 2 ? 'i' : 'p') + (i === a.length - 1 ? ' n' : '') + '">' + v + '</b>'; }).join('');
    var d = dig.slice(-20), n = d.length, ev = d.filter(function (v) { return v % 2 === 0; }).length / n, ov = d.filter(function (v) { return v > 4; }).length / n, last = d[n - 1], mt = d.filter(function (v) { return v === last; }).length / n;
    var S = [{ a: 'PAR', b: 'ÍMPAR', pa: ev, ca: '#22d3ee', cb: '#f472b6', base: .5 }, { a: 'OVER 4', b: 'UNDER 5', pa: ov, ca: '#a78bfa', cb: '#fbbf24', base: .5 }, { a: 'MATCH ' + last, b: 'DIFF ' + last, pa: mt, ca: '#4ade80', cb: '#94a3b8', base: .1 }];
    S.forEach(function (q) { q.f = Math.min(1, Math.abs(q.pa - q.base) / (q.base === .5 ? .5 : .9)); });
    var top = S.slice().sort(function (a, b) { return b.f - a.f; })[0];
    R.duels.innerHTML = S.map(function (q) { var pa = Math.round(q.pa * 100); return '<div class="p2-duel' + (q === top ? ' top' : '') + '"><div class="h"><b style="color:' + q.ca + '">' + q.a + '</b><span>força ' + Math.round(50 + q.f * 50) + '</span><b style="color:' + q.cb + '">' + q.b + '</b></div><div class="p2-bar"><i style="width:' + pa + '%;background:linear-gradient(90deg,' + q.ca + '55,' + q.ca + ')"></i><i style="width:' + (100 - pa) + '%;background:linear-gradient(90deg,' + q.cb + ',' + q.cb + '55)"></i>' + (q.base === .5 ? '<u></u>' : '') + '</div><div class="f"><span>' + pa + '%</span><span>' + (100 - pa) + '%</span></div></div>'; }).join('');
  }

  /* ─────────────────── direita: sessão ─────────────────── */
  var hist = [0], tl = [], ult = { w: 0, l: 0, lucro: 0 }, seq = 0, maior = 0;
  function desenharSessao() {
    var s = st(); if (!s) return;
    var w = +s.wins || 0, l = +s.losses || 0, lucro = (+s.lucro || 0) - (+s.perda || 0); // o robô guarda ganhos e perdas separados; a meta usa o líquido
    if (w + l < ult.w + ult.l) { hist = [0]; tl = []; seq = 0; maior = 0; }
    for (var i = 0; i < w - ult.w; i++) { tl.push(1); seq = seq > 0 ? seq + 1 : 1; maior = Math.max(maior, Math.abs(seq)); }
    for (var j = 0; j < l - ult.l; j++) { tl.push(0); seq = seq < 0 ? seq - 1 : -1; maior = Math.max(maior, Math.abs(seq)); }
    if (tl.length > 40) tl = tl.slice(-40);
    if (lucro !== ult.lucro) hist.push(lucro); if (hist.length > 150) hist = hist.slice(-150);
    ult = { w: w, l: l, lucro: lucro };
    var n = w + l, k = function (q) { return R.kpi.querySelector('[data-k="' + q + '"]'); };
    k('l').textContent = m$(lucro); k('l').style.color = lucro >= 0 ? '#4ade80' : '#f87171';
    k('w').textContent = n ? Math.round(w / n * 100) + '%' : '—'; k('n').textContent = n; k('s').textContent = maior;
    R.tl.innerHTML = tl.map(function (v) { return '<i style="background:' + (v ? '#4ade80' : '#f87171') + '"></i>'; }).join('');
    var cv = R.spark, d = Math.min(window.devicePixelRatio || 1, 2), W = cv.clientWidth, H = cv.clientHeight; if (!W) return;
    cv.width = W * d; cv.height = H * d; var x = cv.getContext('2d'); x.scale(d, d);
    var mn = Math.min.apply(0, hist.concat(0)), mx = Math.max.apply(0, hist.concat(.01)), Y = function (v) { return H - 6 - (v - mn) / (mx - mn || 1) * (H - 12); };
    x.strokeStyle = 'rgba(255,255,255,.15)'; x.setLineDash([3, 3]); x.beginPath(); x.moveTo(0, Y(0)); x.lineTo(W, Y(0)); x.stroke(); x.setLineDash([]);
    x.strokeStyle = lucro >= 0 ? '#4ade80' : '#f87171'; x.lineWidth = 2; x.beginPath();
    hist.forEach(function (v, i) { var X = i / Math.max(1, hist.length - 1) * W; i ? x.lineTo(X, Y(v)) : x.moveTo(X, Y(v)); }); x.stroke();
  }

  /* ─────────────────── fundo radar ─────────────────── */
  function iniciarFundo(cv) {
    var x = cv.getContext('2d'), pts = [], t = 0;
    for (var i = 0; i < 40; i++) pts.push({ a: Math.random() * 6.28, r: .15 + Math.random() * .8, v: 0 });
    (function q() {
      requestAnimationFrame(q);
      if (!document.body.classList.contains('ia-pro-open') || document.hidden) return;
      var d = Math.min(window.devicePixelRatio || 1, 2), W = cv.clientWidth, H = cv.clientHeight; if (!W || !H) return;
      if (cv.width !== Math.round(W * d) || cv.height !== Math.round(H * d)) { cv.width = W * d; cv.height = H * d; }
      x.setTransform(d, 0, 0, d, 0, 0); x.clearRect(0, 0, W, H); t += .016;
      var cx = W / 2, cy = H / 2, Rr = Math.max(W, H) * .6, ang = t * .6;
      var g = x.createRadialGradient(cx, cy, 0, cx, cy, Rr); g.addColorStop(0, 'rgba(34,211,238,.08)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, 0, W, H);
      x.lineWidth = 1; x.strokeStyle = 'rgba(34,211,238,.07)'; for (var k = 1; k <= 6; k++) { x.beginPath(); x.arc(cx, cy, Rr * k / 6, 0, 7); x.stroke(); }
      x.beginPath(); x.moveTo(cx - Rr, cy); x.lineTo(cx + Rr, cy); x.moveTo(cx, cy - Rr); x.lineTo(cx, cy + Rr); x.stroke();
      if (x.createConicGradient) { var cg = x.createConicGradient(ang - .6, cx, cy); cg.addColorStop(0, 'rgba(34,211,238,0)'); cg.addColorStop(.09, 'rgba(34,211,238,.16)'); cg.addColorStop(.1, 'rgba(34,211,238,0)'); x.fillStyle = cg; x.fillRect(0, 0, W, H); }
      pts.forEach(function (p) { var dif = ((ang - p.a) % 6.283 + 6.283) % 6.283; if (dif < .08) p.v = 1; p.v *= .985;
        if (p.v > .02) { x.fillStyle = 'rgba(74,222,128,' + p.v + ')'; x.beginPath(); x.arc(cx + Math.cos(p.a) * p.r * Rr, cy + Math.sin(p.a) * p.r * Rr, 2.2, 0, 7); x.fill(); } });
      var v = x.createRadialGradient(W / 2, H / 2, Math.min(W, H) * .25, W / 2, H / 2, Math.max(W, H) * .75); v.addColorStop(0, 'rgba(5,6,10,0)'); v.addColorStop(1, 'rgba(5,6,10,.72)'); x.fillStyle = v; x.fillRect(0, 0, W, H);
    })();
  }

  /* ─────────────────── laço ─────────────────── */
  function devolverFeed(forcar) {
    var f = $('proFeed'), m = $('proFeedFullModal'); if (!f || !R.feedSlot || R.feedSlot.contains(f)) return;
    var ampliado = m && getComputedStyle(m).display !== 'none' && m.contains(f);
    if (ampliado && !forcar) return;
    R.feedSlot.appendChild(f); f.style.minHeight = ''; f.style.maxHeight = ''; f.scrollTop = f.scrollHeight;
  }
  function tick() {
    try {
      if (!montado && !montar()) return;
      if (!document.body.classList.contains('ia-pro-open')) return;
      devolverFeed(false); atualizarChips(); desenharCentro(); desenharSessao();
    } catch (e) { console.warn('[ia-pro-v2]', e); }
  }
  setInterval(tick, 700);
  if (document.readyState !== 'loading') tick(); else document.addEventListener('DOMContentLoaded', tick);
})();
