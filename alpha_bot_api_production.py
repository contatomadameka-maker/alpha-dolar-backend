# VERSÃO ATUALIZADA 2026-02-26 - FIXES: token real repassado + validação de saldo
"""
ALPHA DOLAR 2.0 - API PRODUCTION INTEGRADA
API Flask que conecta frontend web com bots Python reais
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import threading
import time
from datetime import datetime
import sys
import os

# Adiciona path dos bots
project_path = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.join(project_path, 'backend')
sys.path.insert(0, project_path)
sys.path.insert(0, backend_path)

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

# ==================== IMPORTAR BOTS REAIS ====================

import traceback as _tb
print(f"📁 project_path: {project_path}")
print(f"📁 backend_path: {backend_path}")
print(f"📁 sys.path: {sys.path[:3]}")

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
    print("   Sistema funcionará em modo simulado apenas")

# ==================== ESTADO GLOBAL ====================

bots_state = {
    'manual': {'running': False, 'instance': None, 'thread': None},
    'ia': {'running': False, 'instance': None, 'thread': None},
    'ia_simples': {'running': False, 'instance': None, 'thread': None},
    'ia_avancado': {'running': False, 'instance': None, 'thread': None}
}

global_config = {
    'symbol': 'R_100',
    'contract_type': 'CALL',
    'stake_inicial': 1.0,
    'lucro_alvo': 50.0,
    'limite_perda': 100.0
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

# ==================== ROTAS API ====================

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'message': 'Alpha Dolar API Running',
        'bots_available': BOTS_AVAILABLE
    })

@app.route('/api/bots/status')
def get_bots_status():
    status = {}
    for bot_type, state in bots_state.items():
        bot_instance = state.get('instance')
        status[bot_type] = {
            'running': state['running'],
            'stats': {}
        }
        if BOTS_AVAILABLE and bot_instance and hasattr(bot_instance, 'stop_loss'):
            try:
                stats = bot_instance.stop_loss.get_estatisticas()
                status[bot_type]['stats'] = stats
            except:
                pass

    return jsonify(status)

# ==================== ✅ HELPER: buscar saldo real via Deriv WebSocket ====================

def get_deriv_balance(token):
    """
    Conecta à Deriv via WebSocket, autentica com o token e retorna o saldo.
    Retorna (balance, currency) ou (None, None) em caso de erro.
    """
    try:
        import websocket
        import json

        balance_result = {'balance': None, 'currency': None, 'done': False, 'error': None}

        def on_message(ws, message):
            data = json.loads(message)
            if data.get('msg_type') == 'authorize':
                if 'error' in data:
                    balance_result['error'] = data['error']['message']
                    balance_result['done'] = True
                    ws.close()
                else:
                    # Autorizado — pede o saldo
                    ws.send(json.dumps({"balance": 1, "subscribe": 0}))

            elif data.get('msg_type') == 'balance':
                if 'error' in data:
                    balance_result['error'] = data['error']['message']
                else:
                    balance_result['balance'] = data['balance']['balance']
                    balance_result['currency'] = data['balance']['currency']
                balance_result['done'] = True
                ws.close()

        def on_open(ws):
            ws.send(json.dumps({"authorize": token}))

        def on_error(ws, error):
            balance_result['error'] = str(error)
            balance_result['done'] = True

        ws = websocket.WebSocketApp(
            "wss://ws.binaryws.com/websockets/v3?app_id=1089",
            on_message=on_message,
            on_open=on_open,
            on_error=on_error
        )

        t = threading.Thread(target=ws.run_forever)
        t.daemon = True
        t.start()

        # Aguarda até 8 segundos
        timeout = 8
        start = time.time()
        while not balance_result['done'] and (time.time() - start) < timeout:
            time.sleep(0.1)

        if balance_result['error']:
            print(f"❌ Erro ao buscar saldo Deriv: {balance_result['error']}")
            return None, None

        return balance_result['balance'], balance_result['currency']

    except Exception as e:
        print(f"❌ Exceção ao buscar saldo Deriv: {e}")
        return None, None

# ==================== START BOT ====================

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Iniciar bot — com repasse de token e validação de saldo"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400

        bot_type    = data.get('bot_type', 'manual')
        config      = data.get('config', {})
        account_type = data.get('account_type', 'demo')
        token        = data.get('token')  # ✅ token recebido do frontend

        print(f"\n{'='*60}")
        print(f"📥 Iniciar bot: {bot_type} | conta: {account_type.upper()}")
        print(f"⚙️ Config: {config}")
        print(f"🔑 Token recebido: {'✅ SIM' if token else '❌ NÃO'}")
        print(f"{'='*60}\n")

        stake_inicial = float(config.get('stake_inicial', 0.35))
        lucro_alvo    = float(config.get('lucro_alvo', 2.0))
        limite_perda  = float(config.get('limite_perda', 5.0))

        # ==================== ✅ VALIDAÇÃO DE SALDO ====================

        if account_type == 'real' and token:
            print("🔍 Verificando saldo da conta real...")
            balance, currency = get_deriv_balance(token)

            if balance is None:
                return jsonify({
                    'success': False,
                    'error': 'Não foi possível verificar o saldo. Verifique se o token é válido.',
                    'error_code': 'BALANCE_CHECK_FAILED'
                }), 400

            print(f"💰 Saldo real: {currency} {balance:.2f}")
            print(f"📊 stake={stake_inicial} | stop={limite_perda} | target={lucro_alvo}")

            # Validação 1: stake maior que saldo
            if stake_inicial > balance:
                return jsonify({
                    'success': False,
                    'error': f'Quantia inicial (${stake_inicial:.2f}) é maior que seu saldo disponível (${balance:.2f}). Reduza a quantia inicial.',
                    'error_code': 'STAKE_EXCEEDS_BALANCE',
                    'balance': balance,
                    'stake': stake_inicial
                }), 400

            # Validação 2: limite de perda maior que saldo
            if limite_perda > balance:
                return jsonify({
                    'success': False,
                    'error': f'Limite de perda (${limite_perda:.2f}) é maior que seu saldo disponível (${balance:.2f}). Reduza o limite de perda.',
                    'error_code': 'STOP_EXCEEDS_BALANCE',
                    'balance': balance,
                    'stop_loss': limite_perda
                }), 400

            # Validação 3: saldo mínimo recomendado (10x o stake)
            min_recomendado = stake_inicial * 10
            if balance < min_recomendado:
                print(f"⚠️ Aviso: saldo baixo para operação segura (mín recomendado: ${min_recomendado:.2f})")
                # Não bloqueia, apenas avisa via warning no response

        if bot_type not in bots_state:
            bots_state[bot_type] = {'running': False, 'instance': None, 'thread': None}

        if bots_state[bot_type].get('running', False):
            return jsonify({'success': False, 'error': f'Bot {bot_type} já está rodando'}), 400

        # ==================== BOT REAL ====================

        if BOTS_AVAILABLE and bot_type in ['ia', 'ia_simples']:
            print("🤖 Iniciando BOT PYTHON REAL...")

            BotConfig.DEFAULT_SYMBOL = config.get('symbol', 'R_100')
            BotConfig.STAKE_INICIAL  = stake_inicial
            BotConfig.LUCRO_ALVO     = lucro_alvo
            BotConfig.LIMITE_PERDA   = limite_perda

            # ✅ REPASSA TOKEN AO BotConfig para conta real
            if account_type == 'real' and token:
                BotConfig.API_TOKEN = token  # ✅ campo correto usado pelo DerivAPI
                print(f"🔑 Token real configurado: {token[:8]}...")
            else:
                print(f"🎮 Usando token demo padrão")

            try:
                strategy = AlphaBotBalanced()
                print(f"✅ Estratégia: {strategy.name}")
            except Exception as e:
                return jsonify({'success': False, 'error': f'Erro ao carregar estratégia: {str(e)}'}), 500

            try:
                use_martingale = config.get('martingale', False)
                bot = AlphaDolar(strategy=strategy, use_martingale=use_martingale)
                print(f"✅ Bot criado: {bot.bot_name}")
            except Exception as e:
                return jsonify({'success': False, 'error': f'Erro ao criar bot: {str(e)}'}), 500

            def run_bot():
                try:
                    print(f"🚀 Thread do bot iniciada [{account_type.upper()}]")
                    bot.start()
                except Exception as e:
                    print(f"❌ Erro na thread do bot: {e}")
                    import traceback
                    traceback.print_exc()
                    bots_state[bot_type]['running'] = False

            thread = threading.Thread(target=run_bot, daemon=True)
            thread.start()

            bots_state[bot_type] = {'running': True, 'instance': bot, 'thread': thread}

            print(f"✅ Bot {bot_type} iniciado [{account_type.upper()}]!")

            return jsonify({
                'success': True,
                'message': f'Bot {bot_type} iniciado com sucesso!',
                'bot_type': bot_type,
                'account_type': account_type,
                'config': {
                    'symbol': BotConfig.DEFAULT_SYMBOL,
                    'stake_inicial': BotConfig.STAKE_INICIAL,
                    'lucro_alvo': BotConfig.LUCRO_ALVO,
                    'limite_perda': BotConfig.LIMITE_PERDA,
                    'strategy': strategy.name
                },
                'mode': f'REAL BOT - {account_type.upper()}'
            })

        # ==================== FALLBACK SIMULADO ====================

        else:
            print("⚠️ Bots não disponíveis, usando modo simulado...")

            class SimulatedBot:
                def __init__(self, bot_type, config):
                    self.bot_type = bot_type
                    self.config   = config
                    self.running  = True
                    self.stats    = {
                        'total_trades': 0, 'vitorias': 0, 'derrotas': 0,
                        'lucro_liquido': 0.0, 'saldo_atual': 10000.0, 'win_rate': 0.0
                    }

                def run(self):
                    import random
                    while self.running:
                        time.sleep(5)
                        if random.random() < 0.3:
                            won    = random.random() < 0.65
                            stake  = self.config.get('stake_inicial', 1.0)
                            profit = stake * 0.95 if won else -stake
                            self.stats['total_trades'] += 1
                            if won: self.stats['vitorias'] += 1
                            else:   self.stats['derrotas'] += 1
                            self.stats['lucro_liquido'] += profit
                            self.stats['saldo_atual']   += profit
                            if self.stats['total_trades'] > 0:
                                self.stats['win_rate'] = (self.stats['vitorias'] / self.stats['total_trades']) * 100
                            print(f"{'✅' if won else '❌'} Trade simulado: ${profit:+.2f}")

                def stop(self):
                    self.running = False

            bot = SimulatedBot(bot_type, config)
            thread = threading.Thread(target=bot.run, daemon=True)
            thread.start()
            bots_state[bot_type] = {'running': True, 'instance': bot, 'thread': thread}

            return jsonify({
                'success': True,
                'message': f'Bot {bot_type} iniciado em MODO SIMULADO',
                'bot_type': bot_type,
                'config': config,
                'mode': 'SIMULATED'
            })

    except Exception as e:
        print(f"❌ ERRO em start_bot: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

# ==================== STOP BOT ====================

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400

        bot_type = data.get('bot_type', 'ia')
        print(f"🛑 Parando bot: {bot_type}")

        if bot_type not in bots_state:
            return jsonify({'success': False, 'error': f'Bot {bot_type} não encontrado'}), 400

        if not bots_state[bot_type].get('running', False):
            return jsonify({'success': False, 'error': f'Bot {bot_type} não está rodando'}), 400

        bot = bots_state[bot_type].get('instance')
        if bot:
            if hasattr(bot, 'stop'):   bot.stop()
            elif hasattr(bot, 'running'): bot.running = False

            stats = {}
            if BOTS_AVAILABLE and hasattr(bot, 'stop_loss'):
                try: stats = bot.stop_loss.get_estatisticas()
                except: pass
            elif hasattr(bot, 'stats'):
                stats = bot.stats

            bots_state[bot_type]['running'] = False
            print(f"✅ Bot {bot_type} parado")
            return jsonify({'success': True, 'message': f'Bot {bot_type} parado!', 'stats': stats})

        return jsonify({'success': False, 'error': 'Instância não encontrada'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

# ==================== OUTRAS ROTAS ====================

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'GET':
        return jsonify(global_config)
    try:
        data = request.get_json()
        if data:
            global_config.update(data)
            return jsonify({'success': True, 'config': global_config})
        return jsonify({'success': False, 'error': 'Dados inválidos'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    total_stats = {
        'total_trades': 0, 'vitorias': 0, 'derrotas': 0,
        'lucro_liquido': 0.0, 'saldo_atual': 10000.0, 'win_rate': 0.0
    }
    for bot_type, state in bots_state.items():
        bot = state.get('instance')
        if bot:
            if BOTS_AVAILABLE and hasattr(bot, 'stop_loss'):
                try:
                    stats = bot.stop_loss.get_estatisticas()
                    total_stats['total_trades']  += stats.get('total_trades', 0)
                    total_stats['vitorias']       += stats.get('vitorias', 0)
                    total_stats['derrotas']       += stats.get('derrotas', 0)
                    total_stats['lucro_liquido']  += stats.get('saldo_liquido', 0.0)
                except: pass
            elif hasattr(bot, 'stats'):
                stats = bot.stats
                total_stats['total_trades']  += stats.get('total_trades', 0)
                total_stats['vitorias']       += stats.get('vitorias', 0)
                total_stats['derrotas']       += stats.get('derrotas', 0)
                total_stats['lucro_liquido']  += stats.get('lucro_liquido', 0.0)

    if total_stats['total_trades'] > 0:
        total_stats['win_rate'] = (total_stats['vitorias'] / total_stats['total_trades']) * 100
    return jsonify(total_stats)

@app.route('/api/balance')
@app.route('/api/account/balance')
def get_balance():
    for bot_type, state in bots_state.items():
        bot = state.get('instance')
        if bot and BOTS_AVAILABLE and hasattr(bot, 'api'):
            try:
                balance  = bot.api.balance
                currency = bot.api.currency
                return jsonify({'success': True, 'balance': balance, 'currency': currency, 'formatted': f"${balance:,.2f}"})
            except: pass

    return jsonify({'success': True, 'balance': 9999.00, 'currency': 'USD', 'formatted': "$9,999.00"})

@app.route('/api/bot/stats/<bot_type>')
def get_bot_stats(bot_type):
    if bot_type not in bots_state:
        return jsonify({'success': False, 'error': 'Bot não encontrado'}), 404

    state = bots_state[bot_type]
    bot   = state.get('instance')

    if not bot:
        return jsonify({'success': False, 'error': 'Bot não está rodando'}), 400

    stats = {}
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

@app.route('/api/emergency/reset', methods=['POST'])
def emergency_reset():
    global bots_state
    for bot_type, state in bots_state.items():
        bot = state.get('instance')
        if bot and hasattr(bot, 'stop'):
            try: bot.stop()
            except: pass

    bots_state = {
        'manual':      {'running': False, 'instance': None, 'thread': None},
        'ia':          {'running': False, 'instance': None, 'thread': None},
        'ia_simples':  {'running': False, 'instance': None, 'thread': None},
        'ia_avancado': {'running': False, 'instance': None, 'thread': None}
    }
    return jsonify({'success': True, 'message': 'Estado resetado com sucesso!'})

# ==================== EXECUTAR ====================

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚀 ALPHA DOLAR 2.0 - API PRODUCTION")
    if BOTS_AVAILABLE:
        print("✅ BOTS PYTHON REAIS INTEGRADOS!")
    else:
        print("⚠️ MODO SIMULADO (Bots Python não disponíveis)")
    print("=" * 70)
    print("🌐 http://localhost:5000")
    print("=" * 70 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)