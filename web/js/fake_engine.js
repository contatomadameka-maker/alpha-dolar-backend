/**
 * ALPHA DOLAR — FakeEngine
 * Motor de simulação para /live
 */
(function() {
'use strict';

const CFG = {
  saldo_inicial:   10000,
  velocidade:      1,
  win_rate_alvo:   0.72,
  max_loss_streak: 7,
  max_win_streak:  7,
  tick_interval:   800,
  trade_duration:  3000,
  mercados: ['Volatility 10 Index','Volatility 25 Index','Volatility 50 Index','Volatility 75 Index','Volatility 100 Index']
};

const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('saldo'))      CFG.saldo_inicial = parseFloat(urlParams.get('saldo'));
if (urlParams.get('velocidade')) CFG.velocidade    = parseFloat(urlParams.get('velocidade'));

const STATE = {
  running:false, saldo:CFG.saldo_inicial, saldo_inicial:CFG.saldo_inicial,
  total_trades:0, vitorias:0, derrotas:0, lucro_liquido:0,
  win_streak:0, loss_streak:0, stake_atual:0.35, stake_base:0.35,
  trades:[], forcando_win:false, timer_id:null, tick_id:null, preco_atual:1234.56
};

function injetarLoginFake() {
  if (!localStorage.getItem('deriv_accounts')) {
    localStorage.setItem('deriv_accounts', JSON.stringify([{
      token:'FAKE_TOKEN_'+Date.now(), acct:'VRTC000001',
      loginid:'VRTC000001', isDemo:true, currency:'USD', balance:CFG.saldo_inicial
    }]));
    localStorage.setItem('deriv_conta_ativa','demo');
    localStorage.setItem('deriv_balance_demo', CFG.saldo_inicial.toString());
  }
}

function decidirResultado(stake) {
  const lucro_sessao = STATE.saldo - STATE.saldo_inicial;
  if (lucro_sessao < -(STATE.saldo_inicial * 0.05)) STATE.forcando_win = true;
  if (STATE.forcando_win) { STATE.forcando_win = false; return 'WIN'; }
  if (STATE.loss_streak >= CFG.max_loss_streak) return 'WIN';
  if (STATE.win_streak  >= CFG.max_win_streak)  return 'LOSS';
  const wins_necessarios = Math.round(STATE.total_trades * CFG.win_rate_alvo);
  if (STATE.vitorias < wins_necessarios) return 'WIN';
  return Math.random() < CFG.win_rate_alvo ? 'WIN' : 'LOSS';
}

function calcularLucro(resultado, stake) {
  return resultado === 'WIN'
    ? parseFloat((stake * 0.87).toFixed(2))
    : parseFloat((-stake).toFixed(2));
}

function gerarTrade() {
  if (!STATE.running) return;
  const stake     = STATE.stake_atual;
  const resultado = decidirResultado(stake);
  const lucro     = calcularLucro(resultado, stake);
  const mercado   = window.selectedMarketName || CFG.mercados[Math.floor(Math.random()*CFG.mercados.length)];
  const tipo      = Math.random() > 0.5 ? 'CALL' : 'PUT';

  STATE.total_trades++;
  STATE.saldo        = parseFloat((STATE.saldo + lucro).toFixed(2));
  STATE.lucro_liquido= parseFloat((STATE.lucro_liquido + lucro).toFixed(2));

  if (resultado === 'WIN') {
    STATE.vitorias++; STATE.win_streak++; STATE.loss_streak = 0;
    STATE.stake_atual = STATE.stake_base;
  } else {
    STATE.derrotas++; STATE.loss_streak++; STATE.win_streak = 0;
    STATE.stake_atual = parseFloat((STATE.stake_atual * 2.2).toFixed(2));
    if (STATE.stake_atual > STATE.stake_base * 128) STATE.stake_atual = STATE.stake_base;
  }

  const trade = {
    id:STATE.total_trades, trade_id:STATE.total_trades, tipo, mercado,
    valor:stake, duracao:'1 tick', resultado, lucro,
    proximoStake:STATE.stake_atual, step:STATE.loss_streak, timestamp:new Date().toISOString()
  };
  STATE.trades.unshift(trade);
  if (STATE.trades.length > 100) STATE.trades.pop();
  if (typeof window.registrarTrade === 'function') window.registrarTrade(trade);
  atualizarSaldoUI();
  const intervalo = (CFG.trade_duration + Math.random()*2000) / CFG.velocidade;
  STATE.timer_id = setTimeout(gerarTrade, intervalo);
}

function atualizarSaldoUI() {
  const saldoStr = '$' + STATE.saldo.toFixed(2) + ' USD';
  ['balanceDisplay','saldoAtual','balance-value','demo-balance','proSaldoBox'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = saldoStr;
  });
  document.querySelectorAll('[data-balance],.balance-amount,.saldo-valor').forEach(el => {
    el.textContent = saldoStr;
  });
  localStorage.setItem('deriv_balance_demo', STATE.saldo.toString());
}

function iniciarTicks() {
  STATE.tick_id = setInterval(() => {
    STATE.preco_atual = parseFloat((STATE.preco_atual + (Math.random()-0.5)*0.5).toFixed(4));
    window.dispatchEvent(new CustomEvent('fakeTick',{detail:{
      symbol: window.selectedMarketSymbol||'R_100',
      quote: STATE.preco_atual,
      epoch: Math.floor(Date.now()/1000)
    }}));
  }, CFG.tick_interval / CFG.velocidade);
}

const _fetchOrig = window.fetch;
window.fetch = async function(url, options) {
  const u = typeof url === 'string' ? url : url.toString();
  if (u.includes('alpha-dolar-backend') || u.includes('/api/bot')) {
    if (u.includes('/bot/start')) {
      const body = options && options.body ? JSON.parse(options.body) : {};
      STATE.stake_base = body.config && body.config.stake_inicial ? body.config.stake_inicial : 0.35;
      STATE.stake_atual = STATE.stake_base;
      STATE.running = true;
      iniciarTicks();
      setTimeout(gerarTrade, 1500 / CFG.velocidade);
      return fakeResponse({success:true, bot_type: body.bot_type||'ia', strategy:'alpha_bot_1'});
    }
    if (u.includes('/bot/stop')) {
      STATE.running = false;
      clearTimeout(STATE.timer_id);
      clearInterval(STATE.tick_id);
      return fakeResponse({success:true, stats:getStats()});
    }
    if (u.includes('/bot/stats'))   return fakeResponse({...getStats(), success:true});
    if (u.includes('/bot/trades'))  return fakeResponse({success:true, trades:STATE.trades});
    if (u.includes('/bots/status')) return fakeResponse({ia:{running:STATE.running},ia_simples:{running:false},ia_avancado:{running:false},manual:{running:false}});
    if (u.includes('/health'))      return fakeResponse({status:'ok'});
    return fakeResponse({success:true});
  }
  return _fetchOrig.apply(this, arguments);
};

const _WSorig = window.WebSocket;
window.WebSocket = function(url) {
  if (url && url.includes('derivws.com')) return criarFakeWS(url);
  return new _WSorig(url);
};
window.WebSocket.CONNECTING=0; window.WebSocket.OPEN=1;
window.WebSocket.CLOSING=2;    window.WebSocket.CLOSED=3;

function criarFakeWS(url) {
  const ws = {
    url, readyState:1,
    onopen:null, onmessage:null, onerror:null, onclose:null,
    send(data) { try { setTimeout(()=>this._handle(JSON.parse(data)),50); } catch(e){} },
    close() { this.readyState=3; if(this.onclose) this.onclose({code:1000}); },
    _respond(data) { if(this.onmessage && this.readyState===1) this.onmessage({data:JSON.stringify(data)}); },
    _respondBalance() {
      this._respond({msg_type:'balance',balance:{balance:STATE.saldo,currency:'USD',loginid:'VRTC000001'}});
    },
    _startTicks(symbol) {
      const self=this;
      setInterval(()=>{
        if(self.readyState!==1) return;
        STATE.preco_atual=parseFloat((STATE.preco_atual+(Math.random()-0.5)*0.3).toFixed(4));
        self._respond({msg_type:'tick',tick:{symbol,quote:STATE.preco_atual,epoch:Math.floor(Date.now()/1000)}});
      }, CFG.tick_interval/CFG.velocidade);
    },
    _handle(msg) {
      if (msg.authorize) {
        this._respond({msg_type:'authorize',authorize:{loginid:'VRTC000001',balance:STATE.saldo,currency:'USD',fullname:'Alpha Trader'}});
      } else if (msg.balance) {
        this._respondBalance();
        setInterval(()=>{ if(this.readyState===1) this._respondBalance(); }, 3000/CFG.velocidade);
      } else if (msg.ticks) {
        this._startTicks(msg.ticks);
      } else if (msg.buy) {
        const cid='FAKE-'+Date.now(), stake=parseFloat(msg.price||0.35);
        this._respond({msg_type:'buy',buy:{contract_id:cid,payout:parseFloat((stake*1.87).toFixed(2)),buy_price:stake,transaction_id:Date.now()}});
        setTimeout(()=>{
          const res=decidirResultado(stake), luc=calcularLucro(res,stake);
          this._respond({msg_type:'proposal_open_contract',proposal_open_contract:{
            contract_id:cid, status:res==='WIN'?'won':'lost',
            profit:luc, sell_price:res==='WIN'?stake+luc:0,
            buy_price:stake, is_sold:1, is_expired:1, current_spot:STATE.preco_atual
          }});
        }, CFG.trade_duration/CFG.velocidade);
      } else if (msg.proposal) {
        const stake=parseFloat(msg.amount||0.35);
        this._respond({msg_type:'proposal',proposal:{id:'PROP-'+Date.now(),ask_price:stake,payout:parseFloat((stake*1.87).toFixed(2)),spot:STATE.preco_atual,spot_time:Math.floor(Date.now()/1000)}});
      }
    }
  };
  setTimeout(()=>{ ws.readyState=1; if(ws.onopen) ws.onopen({type:'open'}); }, 100);
  return ws;
}

function fakeResponse(data, status=200) {
  return Promise.resolve(new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}}));
}

function getStats() {
  const wr = STATE.total_trades > 0 ? parseFloat(((STATE.vitorias/STATE.total_trades)*100).toFixed(1)) : 0;
  return {running:STATE.running, total_trades:STATE.total_trades, vitorias:STATE.vitorias,
    derrotas:STATE.derrotas, lucro_liquido:STATE.lucro_liquido, win_rate:wr,
    saldo_atual:STATE.saldo, balance:STATE.saldo, status_texto:STATE.running?'Operando...':'Bot parado'};
}

function injetarBadge() {
  const b=document.createElement('div');
  b.innerHTML='&#9679; LIVE';
  b.style.cssText='position:fixed;bottom:12px;right:12px;background:rgba(0,200,80,0.12);color:#00c850;border:1px solid rgba(0,200,80,0.25);border-radius:6px;padding:4px 10px;font-size:11px;font-family:monospace;z-index:99999;letter-spacing:1px;pointer-events:none;';
  document.body.appendChild(b);
}

function injetarControles() {
  const p=document.createElement('div');
  p.style.cssText='position:fixed;bottom:44px;right:12px;background:rgba(19,21,26,0.95);border:1px solid #2a2d35;border-radius:8px;padding:8px 10px;z-index:99999;';
  p.innerHTML='<div style="font-size:10px;color:#888;margin-bottom:4px;letter-spacing:1px;">VELOCIDADE</div><div style="display:flex;gap:4px;"><button id="spd-1" style="padding:3px 8px;font-size:11px;background:#007bff;border:1px solid #2a2d35;color:#fff;border-radius:4px;cursor:pointer;">1x</button><button id="spd-2" style="padding:3px 8px;font-size:11px;background:#1e2128;border:1px solid #2a2d35;color:#ccc;border-radius:4px;cursor:pointer;">2x</button><button id="spd-3" style="padding:3px 8px;font-size:11px;background:#1e2128;border:1px solid #2a2d35;color:#ccc;border-radius:4px;cursor:pointer;">3x</button></div>';
  document.body.appendChild(p);
  [1,2,3].forEach(n => {
    document.getElementById('spd-'+n).onclick = () => window.FakeEngine.setVelocidade(n);
  });
}

window.FakeEngine = {
  getStats, getState:()=>STATE,
  setVelocidade(v) {
    CFG.velocidade=v;
    [1,2,3].forEach(n=>{
      const btn=document.getElementById('spd-'+n);
      if(btn) btn.style.background = n===v?'#007bff':'#1e2128';
    });
  },
  setSaldo(v) { STATE.saldo=v; STATE.saldo_inicial=v; atualizarSaldoUI(); }
};

function init() {
  injetarLoginFake();
  injetarBadge();
  injetarControles();
  console.log('%c[FakeEngine] Alpha Dolar Live Engine v1.0', 'color:#00c850;font-weight:bold');
}

if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
else init();

})();
