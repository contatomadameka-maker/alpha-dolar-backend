# VERSÃO CORRIGIDA 2026-02-27 v2
"""
ALPHA DOLAR 2.0 - API PRODUCTION INTEGRADA
FIXES:
  ✅ Símbolo convertido para código Deriv (resolve_symbol)
  ✅ Token real repassado ao BotConfig.API_TOKEN
  ✅ Validação de saldo REMOVIDA (Render free bloqueia WebSocket externo)
  ✅ Rota /api/bot/trades/<bot_type> adicionada
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import threading
import time
from datetime import datetime
import sys
import os
import traceback as _tb

project_path = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.join(project_path, 'backend')
sys.path.insert(0, project_path)
sys.path.insert(0, backend_path)

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

# ==================== IMPORTAR BOTS ====================
print(f"📁 project_path: {project_path}")
print(f"📁 backend_path: {backend_path}")
print(f"📁 sys.path: {sys.path[:3]}")

try:
    from backend.bot import AlphaDolar
    from backend.config import BotConfig
    from backend.strategies.alpha_bot_balanced import AlphaBotBalanced
    from backend.strategies.alpha_bot_1 import AlphaBot1
    from backend.strategies.alpha_bot_2 import AlphaBot2
    from backend.strategies.alpha_bot_3 import AlphaBot3
    from backend.strategies.alpha_mind import AlphaMind
    from backend.strategies.quantum_trader import QuantumTrader
    from backend.strategies.titan_core import TitanCore
    from backend.strategies.alpha_pulse import AlphaPulse
    from backend.strategies.alpha_smart import AlphaSmart
    from backend.strategies.alpha_analytics_sniper import AlphaAnalytics, AlphaSniper
    from backend.strategies.premium_strategies import MegaAlpha1, MegaAlpha2, MegaAlpha3, AlphaElite, AlphaNexus
    BOTS_AVAILABLE = True
    print("✅ Todas as 15 estratégias carregadas!")
except ImportError as e:
    BOTS_AVAILABLE = False
    print(f"⚠️ Erro ao importar bots: {e}")
    _tb.print_exc()

# Mapa de estratégias por ID
STRATEGY_MAP = {
    'alpha_bot_1':      lambda tm, rm: AlphaBot1(tm, rm),
    'alpha_bot_2':      lambda tm, rm: AlphaBot2(tm, rm),
    'alpha_bot_3':      lambda tm, rm: AlphaBot3(tm, rm),
    'alpha_bot_balanced': lambda tm, rm: AlphaBotBalanced(tm, rm),
    'alpha_mind':       lambda tm, rm: AlphaMind(tm, rm),
    'quantum_trader':   lambda tm, rm: QuantumTrader(tm, rm),
    'titan_core':       lambda tm, rm: TitanCore(tm, rm),
    'alpha_pulse':      lambda tm, rm: AlphaPulse(tm, rm),
    'alpha_smart':      lambda tm, rm: AlphaSmart(tm, rm),
    'alpha_analytics':  lambda tm, rm: AlphaAnalytics(tm, rm),
    'alpha_sniper':     lambda tm, rm: AlphaSniper(tm, rm),
    'mega_alpha_1':     lambda tm, rm: MegaAlpha1(tm, rm),
    'mega_alpha_2':     lambda tm, rm: MegaAlpha2(tm, rm),
    'mega_alpha_3':     lambda tm, rm: MegaAlpha3(tm, rm),
    'alpha_elite':      lambda tm, rm: AlphaElite(tm, rm),
    'alpha_nexus':      lambda tm, rm: AlphaNexus(tm, rm),
}

# ==================== MAPA DE SÍMBOLOS ====================
SYMBOL_MAP = {
    'Volatility 10 Index':       'R_10',
    'Volatility 25 Index':       'R_25',
    'Volatility 50 Index':       'R_50',
    'Volatility 75 Index':       'R_75',
    'Volatility 100 Index':      'R_100',
    'Volatility 10 (1s) Index':  '1HZ10V',
    'Volatility 25 (1s) Index':  '1HZ25V',
    'Volatility 50 (1s) Index':  '1HZ50V',
    'Volatility 75 (1s) Index':  '1HZ75V',
    'Volatility 100 (1s) Index': '1HZ100V',
    'Boom 1000 Index':           'BOOM1000',
    'Boom 500 Index':            'BOOM500',
    'Crash 1000 Index':          'CRASH1000',
    'Crash 500 Index':           'CRASH500',
    'Jump 10 Index':             'JD10',
    'Jump 25 Index':             'JD25',
    'Jump 50 Index':             'JD50',
    'Jump 75 Index':             'JD75',
    'Jump 100 Index':            'JD100',
    'R_10': 'R_10', 'R_25': 'R_25', 'R_50': 'R_50',
    'R_75': 'R_75', 'R_100': 'R_100',
    '1HZ10V': '1HZ10V', '1HZ25V': '1HZ25V', '1HZ50V': '1HZ50V',
    '1HZ75V': '1HZ75V', '1HZ100V': '1HZ100V',
}

def resolve_symbol(s):
    return SYMBOL_MAP.get(s, s or 'R_100')

# ==================== ESTADO GLOBAL ====================
bots_state = {
    'manual':      {'running': False, 'instance': None, 'thread': None, 'trades': []},
    'ia':          {'running': False, 'instance': None, 'thread': None, 'trades': []},
    'ia_simples':  {'running': False, 'instance': None, 'thread': None, 'trades': []},
    'ia_avancado': {'running': False, 'instance': None, 'thread': None, 'trades': []}
}

# ==================== ROTAS ESTÁTICAS ====================
@app.route('/')
def index():
    return send_from_directory('web', 'trading.html')

@app.route('/<path:path>')
def serve_static(path):
    try:
        return send_from_directory('web', path)
    except:
        return jsonify({'error': 'Not found'}), 404

# ==================== HEALTH ====================
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'message': 'Alpha Dolar API Running', 'bots_available': BOTS_AVAILABLE})

# ==================== START BOT ====================
@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400

        bot_type     = data.get('bot_type', 'manual')
        config       = data.get('config', {})
        account_type = data.get('account_type', 'demo')
        token        = data.get('token')

        # ✅ Resolve símbolo
        symbol = resolve_symbol(config.get('symbol', 'R_100'))

        stake_inicial = float(config.get('stake_inicial', 0.35))
        lucro_alvo    = float(config.get('lucro_alvo',    2.0))
        limite_perda  = float(config.get('limite_perda',  5.0))

        print(f"\n{'='*60}")
        print(f"📥 Iniciar bot: {bot_type} | conta: {account_type.upper()}")
        print(f"📊 Símbolo: {config.get('symbol')} → {symbol}")
        print(f"💰 stake={stake_inicial} target={lucro_alvo} stop={limite_perda}")
        print(f"🔑 Token: {'✅ SIM' if token else '❌ NÃO'}")
        print(f"{'='*60}\n")

        if bot_type not in bots_state:
            bots_state[bot_type] = {'running': False, 'instance': None, 'thread': None, 'trades': []}

        if bots_state[bot_type].get('running', False):
            return jsonify({'success': False, 'error': f'Bot {bot_type} já está rodando'}), 400

        # ==================== BOT REAL ====================
        if BOTS_AVAILABLE and bot_type in ['ia', 'ia_simples']:
            print("🤖 Iniciando BOT PYTHON REAL...")

            # ✅ Configura BotConfig
            BotConfig.DEFAULT_SYMBOL = symbol
            BotConfig.STAKE_INICIAL  = stake_inicial
            BotConfig.LUCRO_ALVO     = lucro_alvo
            BotConfig.LIMITE_PERDA   = limite_perda

            if account_type == 'real' and token:
                BotConfig.API_TOKEN = token
                print(f"🔑 Token real: {token[:10]}...")
            else:
                print(f"🎮 Token demo padrão")

            print(f"📡 Subscrevendo: {BotConfig.DEFAULT_SYMBOL}")

            # ✅ Parâmetros do frontend
            trading_mode   = config.get('trading_mode', 'faster')
            risk_mode      = config.get('risk_mode', 'conservative')
            strategy_id    = config.get('strategy', 'alpha_bot_1')
            stop_loss_type = config.get('stop_loss_type', 'value')
            max_losses     = int(config.get('max_losses', 5))
            print(f"⚡ Modo: {trading_mode} | Risco: {risk_mode} | Estratégia: {strategy_id} | StopLoss: {stop_loss_type}")

            # ✅ Aplica TODOS os valores do frontend no BotConfig ANTES de criar o bot
            BotConfig.STOP_LOSS_TYPE         = stop_loss_type
            BotConfig.MAX_CONSECUTIVE_LOSSES = max_losses
            BotConfig.STAKE_INICIAL          = float(config.get('stake', BotConfig.STAKE_INICIAL))
            BotConfig.LUCRO_ALVO             = float(config.get('target', BotConfig.LUCRO_ALVO))
            BotConfig.LIMITE_PERDA           = float(config.get('stop', BotConfig.LIMITE_PERDA))
            print(f"💰 stake={BotConfig.STAKE_INICIAL} target={BotConfig.LUCRO_ALVO} stop={BotConfig.LIMITE_PERDA}")

            try:
                factory  = STRATEGY_MAP.get(strategy_id, STRATEGY_MAP['alpha_bot_1'])
                strategy = factory(trading_mode, risk_mode)
                print(f"✅ Estratégia: {strategy.name} | Confiança: {strategy.min_confidence:.0%} | Martingale: {strategy.usar_martingale}")
            except Exception as e:
                return jsonify({'success': False, 'error': f'Erro estratégia: {str(e)}'}), 500

            try:
                bot = AlphaDolar(strategy=strategy, use_martingale=strategy.usar_martingale)
                print(f"✅ Bot: {bot.bot_name}")
            except Exception as e:
                return jsonify({'success': False, 'error': f'Erro bot: {str(e)}'}), 500

            # ✅ Callback para salvar cada trade na lista
            def on_trade_completed(direction, won, profit, stake, symbol_used, exit_tick=None):
                # Calcula win rate atualizado
                trades_ate_agora = bots_state[bot_type]['trades']
                total  = len(trades_ate_agora) + 1
                wins   = sum(1 for t in trades_ate_agora if t.get('result') == 'win') + (1 if won else 0)
                wr     = round((wins / total) * 100, 1) if total > 0 else 0

                # ✅ Próximo stake — usa martingale inteligente do bot
                step_atual = getattr(strategy, 'step_atual', 0)
                max_steps  = getattr(strategy, 'max_steps', 3)
                # Após registrar o resultado, calcula próximo stake
                perda_acum = getattr(bot, 'perda_acumulada', 0)
                if perda_acum > 0 and hasattr(bot, '_calcular_stake_recuperacao'):
                    next_stake = bot._calcular_stake_recuperacao()
                else:
                    next_stake = BotConfig.STAKE_INICIAL

                # Pega tique de saída do contrato se disponível
                exit_tick = None
                trades_list = bots_state[bot_type]['trades']

                trade = {
                    'id':           int(time.time() * 1000),
                    'direction':    direction,
                    'result':       'win' if won else 'loss',
                    'profit':       round(profit, 2),
                    'stake':        round(stake, 2),
                    'symbol':       symbol_used,
                    'timestamp':    datetime.now().strftime('%H:%M:%S'),
                    'next_stake':   round(next_stake, 2),
                    'step':         step_atual,
                    'max_steps':    max_steps,
                    'win_rate':     wr,
                    'total_trades': total,
                    'exit_tick':    str(exit_tick) if exit_tick else None
                }
                bots_state[bot_type]['trades'].append(trade)
                # Mantém só últimos 100 trades em memória
                if len(bots_state[bot_type]['trades']) > 100:
                    bots_state[bot_type]['trades'].pop(0)

            # Injeta callback no bot
            bot._on_trade_completed = on_trade_completed

            # Monkey-patch no on_contract_update para capturar resultado
            original_contract_update = bot.on_contract_update
            def patched_contract_update(contract_data):
                status = contract_data.get('status')
                if status in ['won', 'lost']:
                    profit     = float(contract_data.get('profit', 0))
                    won        = status == 'won'
                    direction  = contract_data.get('contract_type', 'CALL/PUT')
                    stake_used = getattr(bot, '_ultimo_stake_usado', BotConfig.STAKE_INICIAL)
                    exit_tick  = contract_data.get('exit_tick_value') or contract_data.get('exit_tick')
                    on_trade_completed(direction, won, profit, stake_used, BotConfig.DEFAULT_SYMBOL, exit_tick)

                    # ✅ Garante liberação AQUI — independente do bot.on_contract_update
                    bot.waiting_contract = False
                    bot.current_contract_id = None
                    bot._ultimo_trade_time = time.time()
                    print(f"[patched] ✅ waiting_contract liberado — status: {status}")

                original_contract_update(contract_data)
            bot.on_contract_update = patched_contract_update
            bot.api.set_contract_callback(patched_contract_update)

            def run_bot():
                try:
                    print(f"🚀 Thread bot [{account_type.upper()}] iniciada!")
                    bot.start()
                except Exception as e:
                    print(f"❌ Erro thread bot: {e}")
                    _tb.print_exc()
                    bots_state[bot_type]['running'] = False

            thread = threading.Thread(target=run_bot, daemon=True)
            thread.start()
            bots_state[bot_type] = {'running': True, 'instance': bot, 'thread': thread, 'trades': []}
            print(f"✅ Bot {bot_type} iniciado [{account_type.upper()}]!")

            return jsonify({
                'success': True,
                'message': f'Bot iniciado!',
                'bot_type': bot_type,
                'account_type': account_type,
                'symbol': symbol,
                'mode': f'REAL BOT - {account_type.upper()}'
            })

        # ==================== SIMULADO ====================
        else:
            print("⚠️ Modo simulado...")

            class SimulatedBot:
                def __init__(self):
                    self.running = True
                    self.stats = {
                        'total_trades': 0, 'vitorias': 0, 'derrotas': 0,
                        'lucro_liquido': 0.0, 'saldo_atual': 10000.0, 'win_rate': 0.0
                    }
                def run(self):
                    import random
                    while self.running:
                        time.sleep(5)
                        if random.random() < 0.3:
                            won = random.random() < 0.65
                            profit = stake_inicial * 0.95 if won else -stake_inicial
                            self.stats['total_trades'] += 1
                            if won: self.stats['vitorias'] += 1
                            else:   self.stats['derrotas'] += 1
                            self.stats['lucro_liquido'] += profit
                            self.stats['saldo_atual']   += profit
                            self.stats['win_rate'] = (self.stats['vitorias'] / self.stats['total_trades']) * 100
                            print(f"{'✅' if won else '❌'} Sim: ${profit:+.2f}")
                def stop(self): self.running = False

            bot = SimulatedBot()
            thread = threading.Thread(target=bot.run, daemon=True)
            thread.start()
            bots_state[bot_type] = {'running': True, 'instance': bot, 'thread': thread, 'trades': []}
            return jsonify({'success': True, 'message': 'Bot simulado iniciado', 'mode': 'SIMULATED'})

    except Exception as e:
        print(f"❌ ERRO start_bot: {e}")
        _tb.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== STOP BOT ====================
@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400

        bot_type = data.get('bot_type', 'ia')
        print(f"🛑 Parando: {bot_type}")

        if bot_type not in bots_state or not bots_state[bot_type].get('running', False):
            return jsonify({'success': False, 'error': f'Bot {bot_type} não está rodando'}), 400

        bot = bots_state[bot_type].get('instance')
        if bot:
            if hasattr(bot, 'stop'): bot.stop()
            elif hasattr(bot, 'running'): bot.running = False

            stats = {}
            if BOTS_AVAILABLE and hasattr(bot, 'stop_loss'):
                try: stats = bot.stop_loss.get_estatisticas()
                except: pass
            elif hasattr(bot, 'stats'):
                stats = bot.stats

            bots_state[bot_type]['running'] = False
            print(f"✅ Bot {bot_type} parado")
            return jsonify({'success': True, 'message': 'Bot parado!', 'stats': stats})

        return jsonify({'success': False, 'error': 'Instância não encontrada'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== STATS / BALANCE / TRADES ====================

@app.route('/api/bot/stats/<bot_type>')
def get_bot_stats(bot_type):
    if bot_type not in bots_state:
        return jsonify({'success': False, 'running': False, 'stats': {}})

    state = bots_state[bot_type]
    bot   = state.get('instance')
    stats = {}

    if bot:
        if BOTS_AVAILABLE and hasattr(bot, 'stop_loss'):
            try: stats = bot.stop_loss.get_estatisticas()
            except: pass
        elif hasattr(bot, 'stats'):
            stats = bot.stats
        if BOTS_AVAILABLE and hasattr(bot, 'api'):
            try:
                stats['balance']  = bot.api.balance
                stats['currency'] = bot.api.currency
            except: pass

    return jsonify({
        'success': True,
        'bot_type': bot_type,
        'running': state.get('running', False),
        'stats': stats,
        # campos diretos para compatibilidade com frontend antigo
        'bot_running':   state.get('running', False),
        'saldo_atual':   stats.get('balance', 0),
        'lucro_liquido': stats.get('saldo_liquido', 0),
        'total_trades':  stats.get('total_trades', 0),
        'win_rate':      stats.get('win_rate', 0),
        'vitorias':      stats.get('vitorias', 0),
        'derrotas':      stats.get('derrotas', 0),
    })

# ✅ ROTA QUE FALTAVA
@app.route('/api/bot/trades/<bot_type>')
def get_bot_trades(bot_type):
    if bot_type not in bots_state:
        return jsonify({'success': True, 'trades': []})
    trades = bots_state[bot_type].get('trades', [])
    return jsonify({'success': True, 'trades': trades, 'total': len(trades)})

@app.route('/api/balance')
@app.route('/api/account/balance')
def get_balance():
    for bot_type, state in bots_state.items():
        bot = state.get('instance')
        if bot and BOTS_AVAILABLE and hasattr(bot, 'api'):
            try:
                b = bot.api.balance
                c = bot.api.currency
                if b and b != 0:
                    return jsonify({'success': True, 'balance': b, 'currency': c, 'formatted': f"${b:,.2f}"})
            except: pass
    return jsonify({'success': True, 'balance': 0, 'currency': 'USD', 'formatted': "$0.00"})

@app.route('/api/emergency/reset', methods=['POST'])
def emergency_reset():
    global bots_state
    for state in bots_state.values():
        bot = state.get('instance')
        if bot and hasattr(bot, 'stop'):
            try: bot.stop()
            except: pass
    bots_state = {k: {'running': False, 'instance': None, 'thread': None, 'trades': []}
                  for k in ['manual', 'ia', 'ia_simples', 'ia_avancado']}
    return jsonify({'success': True, 'message': 'Estado resetado!'})

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 ALPHA DOLAR 2.0 - API PRODUCTION")
    print("✅ BOTS PYTHON REAIS!" if BOTS_AVAILABLE else "⚠️ MODO SIMULADO")
    print("="*70 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
