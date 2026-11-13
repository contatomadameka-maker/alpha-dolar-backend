/* DERIV-COMPAT-V1 — adapta os robôs do navegador à API nova da Deriv, sem mexer no código deles:
   1) acompanhamento do contrato com contract_id numérico (a API nova recusa texto);
   2) se a compra pelo número da proposta voltar "Unknown contract proposal", recompra na hora pelos dados da proposta.
   Não altera nenhuma outra mensagem. Páginas com tsq-ritmo.js (Touch) ou motor próprio (Sniper) não precisam dele. */
(function () {
  'use strict';
  if (window.__derivCompat || window.__tsqRitmo || !window.WebSocket) return; window.__derivCompat = true;
  var WS = window.WebSocket, envia = WS.prototype.send, props = {};
  WS.prototype.send = function (data) {
    if (this.__dc && typeof data === 'string' && data.indexOf('"proposal_open_contract"') >= 0 && data.indexOf('"contract_id":"') >= 0) {
      try { var o = JSON.parse(data); if (typeof o.contract_id === 'string' && /^\d+$/.test(o.contract_id)) { o.contract_id = Number(o.contract_id); data = JSON.stringify(o); } } catch (e) {}
    }
    return envia.call(this, data);
  };
  function filtro(ev) {
    var d = ev.data; if (typeof d !== 'string' || (d.indexOf('"proposal"') < 0 && d.indexOf('"buy"') < 0)) return;
    var m; try { m = JSON.parse(d); } catch (e) { return; }
    if (m.msg_type === 'proposal' && m.proposal && m.proposal.id && m.echo_req) {
      var q = {}; for (var k in m.echo_req) if (!/^(proposal|req_id|subscribe|passthrough)$/.test(k)) q[k] = m.echo_req[k];
      props[m.proposal.id] = q; var ks = Object.keys(props); if (ks.length > 300) ks.slice(0, 100).forEach(function (z) { delete props[z]; });
      return;
    }
    if (m.msg_type === 'buy' && m.error && /InvalidContractProposal|Unknown contract proposal/i.test((m.error.code || '') + ' ' + (m.error.message || '')) && m.echo_req && !m.echo_req.parameters) {
      var p = props[m.echo_req.buy];
      if (p && this.readyState === 1) {
        ev.stopImmediatePropagation();
        var nb = { buy: 1, price: m.echo_req.price, parameters: p }; if (m.echo_req.req_id != null) nb.req_id = m.echo_req.req_id; if (m.echo_req.passthrough) nb.passthrough = m.echo_req.passthrough;
        try { console.info('[Deriv] compra pela proposta recusada; recomprando pelos dados da proposta'); } catch (e) {}
        envia.call(this, JSON.stringify(nb));
      }
    }
  }
  function Novo(url, prot) {
    var ws = prot !== undefined ? new WS(url, prot) : new WS(url);
    if (/deriv/i.test(String(url))) { ws.__dc = true; ws.addEventListener('message', filtro); }
    return ws;
  }
  Novo.prototype = WS.prototype;
  ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'].forEach(function (k) { try { Object.defineProperty(Novo, k, { value: WS[k] }); } catch (e) {} });
  window.WebSocket = Novo;
})();
