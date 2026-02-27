# VERSÃO CORRIGIDA 2026-02-27
"""
ALPHA DOLAR 2.0 - API PRODUCTION INTEGRADA
FIXES:
  ✅ Símbolo correto repassado ao BotConfig.DEFAULT_SYMBOL
  ✅ Token real repassado ao BotConfig.API_TOKEN
  ✅ Validação de saldo antes de iniciar
  ✅ Rota /api/bot/trades/<bot_type> adicionada (resolvia 404)
  ✅ Mapa de nomes de mercado para códigos Deriv
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import threading
import time
from datetime import datetime
import sys
import os

project_path = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.join(project_path, 'backend')
sys.path.insert(0, project_path)
sys.path.insert(0, backend_path)

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

# ==================== IMPORTAR BOTS ====================
import traceback as _tb
print(f"📁 project_path: {project_path}")
print(f"📁 backend_path: {backend_path}")

try:
    from backend.bot import AlphaDolar
    from backend.config import BotConfig
    from backend.strategies.alpha_bot_1 import AlphaBot1
    from backend.strategies.test_strategy import TestStrategy
    from backend.strategies.alpha_bot_balanced import AlphaBotBalanced
    BOTS_AVAILABLE = True
    print("✅ Bots Python carregados com sucesso!")
except ImportError as e:
    BOTS_AVAILABLE = False
    print(f"⚠️ Erro ao importar bots: {e}")
    _tb.print_exc()

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

# ==================== HELPER SALDO REAL ====================
def get_deriv_balance(token):
    try:
        import websocket, json
        result = {'balance': None, 'currency': None, 'done': False, 'error': None}

        def on_message(ws, message):
            data = json.loads(message)
            if data.get('msg_type') == 'authorize':
                if 'error' in data:
                    result['error'] = data['error']['message']
                    result['done'] = True
                    ws.close()
                else:
                    ws.send(json.dumps({"balance": 1, "subscribe": 0}))
            elif data.get('msg_type') == 'balance':
                if 'error' in data:
                    result['error'] = data['error']['message']
                else:
                    result['balance']  = data['balance']['balance']
                    result['currency'] = data['balance']['currency']
                result['done'] = True
                ws.close()

        def on_open(ws):  ws.send(json.dumps({"authorize": token}))
        def on_error(ws, error):
            result['error'] = str(error)
            result['done'] = True

        ws = websocket.WebSocketApp("wss://ws.binaryws.com/websockets/v3?app_id=1089",
            on_message=on_message, on_open=on_open, on_error=on_error)
        t = threading.Thread(target=ws.run_forever)
        t.daemon = True
        t.start()

        start = time.time()
        while not result['done'] and (time.time() - start) < 8:
            time.sleep(0.1)

        if result['error']:
            print(f"❌ Erro saldo Deriv: {result['error']}")
            return None, None
        return result['balance'], result['currency']
    except Exception as e:
        print(f"❌ Exceção saldo Deriv: {e}")
        return None, None

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

        # Validação saldo real
        if account_type == 'real' and token:
            balance, currency = get_deriv_balance(token)
            if balance is None:
                return jsonify({'success': False, 'error': 'Não foi possível verificar o saldo. Token inválido?', 'error_code': 'BALANCE_CHECK_FAILED'}), 400
            print(f"💰 Saldo real: {currency} {balance:.2f}")
            if stake_inicial > balance:
                return jsonify({'success': False, 'error': f'Quantia inicial (${stake_inicial:.2f}) maior que saldo (${balance:.2f}).', 'error_code': 'STAKE_EXCEEDS_BALANCE'}), 400
            if limite_perda > balance:
                return jsonify({'success': False, 'error': f'Limite de perda (${limite_perda:.2f}) maior que saldo (${balance:.2f}).', 'error_code': 'STOP_EXCEEDS_BALANCE'}), 400

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
                print(f"🔑 Token real: {token[:8]}...")
            else:
                print(f"🎮 Token demo padrão")

            print(f"📡 Subscrevendo: {BotConfig.DEFAULT_SYMBOL}")

            try:
                strategy = AlphaBotBalanced()
                print(f"✅ Estratégia: {strategy.name}")
            except Exception as e:
                return jsonify({'success': False, 'error': f'Erro estratégia: {str(e)}'}), 500

            try:
                bot = AlphaDolar(strategy=strategy, use_martingale=config.get('martingale', False))
                print(f"✅ Bot: {bot.bot_name}")
            except Exception as e:
                return jsonify({'success': False, 'error': f'Erro bot: {str(e)}'}), 500

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
                    self.stats = {'total_trades': 0, 'vitorias': 0, 'derrotas': 0, 'lucro_liquido': 0.0, 'saldo_atual': 10000.0, 'win_rate': 0.0}
                def run(self):
                    import random
                    while self.running:
                        time.sleep(5)
                        if random.random() < 0.3:
                            won = random.random() < 0.65
                            profit = stake_inicial * 0.95 if won else -stake_inicial
                            self.stats['total_trades'] += 1
                            if won: self.stats['vitorias'] += 1
                            else: self.stats['derrotas'] += 1
                            self.stats['lucro_liquido'] += profit
                            self.stats['saldo_atual'] += profit
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
            return jsonify({'success': True, 'message': f'Bot parado!', 'stats': stats})

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

    return jsonify({'success': True, 'bot_type': bot_type, 'running': state.get('running', False), 'stats': stats})

# ✅ ROTA QUE FALTAVA — resolvia 404 no frontend
@app.route('/api/bot/trades/<bot_type>')
def get_bot_trades(bot_type):
    if bot_type not in bots_state:
        return jsonify([])
    return jsonify(bots_state[bot_type].get('trades', []))

@app.route('/api/balance')
@app.route('/api/account/balance')
def get_balance():
    for bot_type, state in bots_state.items():
        bot = state.get('instance')
        if bot and BOTS_AVAILABLE and hasattr(bot, 'api'):
            try:
                b = bot.api.balance
                c = bot.api.currency
                return jsonify({'success': True, 'balance': b, 'currency': c, 'formatted': f"${b:,.2f}"})
            except: pass
    return jsonify({'success': True, 'balance': 9999.00, 'currency': 'USD', 'formatted': "$9,999.00"})

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
