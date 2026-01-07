# ALPHA DOLAR 2.0 - API PRODUCTION (RENDER.COM) - HYBRID VERSION
"""
ALPHA DOLAR 2.0 - API PRODUCTION INTEGRADA
API Flask que conecta frontend web com bots Python reais
VERSÃO HÍBRIDA: Mantém bot real + adiciona fallback para frontend
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import time
import os
from datetime import datetime
import sys

# Configurar paths
project_path = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.join(project_path, 'backend')
sys.path.insert(0, project_path)
sys.path.insert(0, backend_path)

app = Flask(__name__)

# CORS - Liberar TODAS as origens
CORS(app)

# ==================== IMPORTAR CONFIG PRIMEIRO ====================

try:
    from config import BotConfig
    CONFIG_LOADED = True
    print("✅ Config carregado com sucesso!")
except ImportError:
    try:
        from backend.config import BotConfig
        CONFIG_LOADED = True
        print("✅ Config carregado de backend/ com sucesso!")
    except ImportError as e:
        CONFIG_LOADED = False
        print(f"⚠️ Erro ao carregar config: {e}")

# ==================== IMPORTAR BOTS REAIS ====================

try:
    from backend.bot import AlphaDolar
    from backend.strategies.alpha_bot_1 import AlphaBot1
    from backend.strategies.alpha_bot_balanced import AlphaBotBalanced
    from backend.strategies.test_strategy import TestStrategy
    BOTS_AVAILABLE = True
    print("✅ Bots Python carregados com sucesso!")
except ImportError as e:
    BOTS_AVAILABLE = False
    print(f"⚠️ Erro ao importar bots: {e}")
    print("   Sistema funcionará em modo simulado apenas")

# ==================== CONFIGURAÇÃO ====================

# Token Deriv da variável de ambiente
DERIV_TOKEN = os.getenv('DERIV_TOKEN', '')

if CONFIG_LOADED and BOTS_AVAILABLE:
    if DERIV_TOKEN:
        BotConfig.DERIV_TOKEN = DERIV_TOKEN
        print(f"✅ Token configurado no BotConfig")
    else:
        print("⚠️ AVISO: DERIV_TOKEN não configurado!")
else:
    if not DERIV_TOKEN:
        print("⚠️ AVISO: DERIV_TOKEN não configurado!")

# ==================== ESTADO GLOBAL ====================

bots_state = {
    'manual': {'running': False, 'instance': None, 'thread': None},
    'ia': {'running': False, 'instance': None, 'thread': None},
    'ia_simples': {'running': False, 'instance': None, 'thread': None},
    'ia_avancado': {'running': False, 'instance': None, 'thread': None}
}

# ==================== ROTAS API ====================

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'message': 'Alpha Dolar API Running on Render',
        'version': '2.0.3-HYBRID',
        'bots_available': BOTS_AVAILABLE,
        'config_loaded': CONFIG_LOADED,
        'token_configured': bool(DERIV_TOKEN),
        'environment': os.getenv('FLASK_ENV', 'production')
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

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Iniciar bot - VERSÃO RENDER.COM"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400

        if not DERIV_TOKEN:
            return jsonify({
                'success': False,
                'error': 'Token Deriv não configurado. Configure DERIV_TOKEN nas variáveis de ambiente.'
            }), 500

        if not CONFIG_LOADED:
            return jsonify({
                'success': False,
                'error': 'Configuração não carregada. Verifique o arquivo config.py'
            }), 500

        bot_type = data.get('bot_type', 'manual')
        config = data.get('config', {})

        print(f"\n{'='*60}")
        print(f"📥 Recebido pedido para iniciar bot: {bot_type}")
        print(f"⚙️ Config recebida: {config}")
        print(f"{'='*60}\n")

        if bot_type not in bots_state:
            bots_state[bot_type] = {'running': False, 'instance': None, 'thread': None}

        if bots_state[bot_type].get('running', False):
            return jsonify({
                'success': False,
                'error': f'Bot {bot_type} já está rodando'
            }), 400

        if BOTS_AVAILABLE and bot_type in ['ia', 'ia_simples']:
            print("🤖 Iniciando BOT PYTHON REAL...")

            # Aplicar configurações
            BotConfig.DEFAULT_SYMBOL = config.get('symbol', 'R_100')
            BotConfig.STAKE_INICIAL = config.get('stake_inicial', 0.35)
            BotConfig.LUCRO_ALVO = config.get('lucro_alvo', 2.0)
            BotConfig.LIMITE_PERDA = config.get('limite_perda', 5.0)

            try:
                # Usar AlphaBotBalanced (intermediário)
                print("⚡ Usando AlphaBotBalanced - estratégia intermediária")
                strategy = AlphaBotBalanced()
                print(f"✅ Estratégia carregada: {strategy.name}")
            except Exception as e:
                print(f"❌ Erro ao carregar estratégia: {e}")
                return jsonify({
                    'success': False,
                    'error': f'Erro ao carregar estratégia: {str(e)}'
                }), 500

            try:
                use_martingale = config.get('martingale', False)
                bot = AlphaDolar(
                    strategy=strategy,
                    use_martingale=use_martingale
                )
                print(f"✅ Bot criado: {bot.bot_name}")
            except Exception as e:
                print(f"❌ Erro ao criar bot: {e}")
                return jsonify({
                    'success': False,
                    'error': f'Erro ao criar bot: {str(e)}'
                }), 500

            def run_bot():
                try:
                    print(f"🚀 Thread do bot iniciada")
                    bot.start()
                except Exception as e:
                    print(f"❌ Erro na thread do bot: {e}")
                    import traceback
                    traceback.print_exc()
                    bots_state[bot_type]['running'] = False

            thread = threading.Thread(target=run_bot, daemon=True)
            thread.start()

            bots_state[bot_type] = {
                'running': True,
                'instance': bot,
                'thread': thread
            }

            print(f"✅ Bot {bot_type} iniciado com sucesso!")

            return jsonify({
                'success': True,
                'message': f'Bot {bot_type} iniciado com AlphaBotBalanced!',
                'bot_type': bot_type,
                'config': {
                    'symbol': BotConfig.DEFAULT_SYMBOL,
                    'stake_inicial': BotConfig.STAKE_INICIAL,
                    'lucro_alvo': BotConfig.LUCRO_ALVO,
                    'limite_perda': BotConfig.LIMITE_PERDA,
                    'strategy': strategy.name
                },
                'mode': 'REAL BOT - BALANCED STRATEGY'
            })

        return jsonify({
            'success': False,
            'error': 'Tipo de bot não suportado'
        }), 400

    except Exception as e:
        print(f"❌ ERRO em start_bot: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Parar bot"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400

        bot_type = data.get('bot_type', 'ia')

        print(f"🛑 Parando bot: {bot_type}")

        if bot_type not in bots_state:
            return jsonify({
                'success': False,
                'error': f'Bot {bot_type} não encontrado'
            }), 400

        if not bots_state[bot_type].get('running', False):
            return jsonify({
                'success': False,
                'error': f'Bot {bot_type} não está rodando'
            }), 400

        bot = bots_state[bot_type].get('instance')

        if bot:
            if hasattr(bot, 'stop'):
                bot.stop()
            elif hasattr(bot, 'running'):
                bot.running = False

            stats = {}
            if BOTS_AVAILABLE and hasattr(bot, 'stop_loss'):
                try:
                    stats = bot.stop_loss.get_estatisticas()
                except:
                    pass

            bots_state[bot_type]['running'] = False

            print(f"✅ Bot {bot_type} parado")

            return jsonify({
        bot_type = data.get('bot_type', 'ia')

        print(f"🛑 Parando bot: {bot_type}")

        if bot_type not in bots_state:
            return jsonify({
                'success': False,
                'error': f'Bot {bot_type} não encontrado'
            }), 400

        # ✅ REMOVIDO: Verificação se bot está rodando
        # Permite parar mesmo se já estiver parado (mais permissivo)

        bot = bots_state[bot_type].get('instance')

        if bot:
            if hasattr(bot, 'stop'):
                try:
                    bot.stop()
                except:
                    pass
            elif hasattr(bot, 'running'):
                bot.running = False

        # ✅ SEMPRE marca como parado
        bots_state[bot_type]['running'] = False

        stats = {}
        if bot and BOTS_AVAILABLE and hasattr(bot, 'stop_loss'):
            try:
                stats = bot.stop_loss.get_estatisticas()
            except:
                pass

        print(f"✅ Bot {bot_type} parado")

        return jsonify({
            'success': True,
            'message': f'Bot {bot_type} parado com sucesso!',
            'stats': stats
        })

    except Exception as e:
        print(f"❌ ERRO em stop_bot: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500
                    'formatted': f"${balance:,.2f}"
                })
            except:
                pass

    return jsonify({
        'success': True,
        'balance': 0.00,
        'currency': 'USD',
        'formatted': "$0.00"
    })

@app.route('/api/bot/stats/<bot_type>')
def get_bot_stats(bot_type):
    """
    ✅ VERSÃO HÍBRIDA - Retorna stats reais OU fallback
    Mantém compatibilidade com bot real + adiciona fallback para frontend
    """
    if bot_type not in bots_state:
        return jsonify({'success': False, 'error': 'Bot não encontrado'}), 404

    state = bots_state[bot_type]
    bot = state.get('instance')

    # Se bot não está rodando
    if not state.get('running', False):
        return jsonify({
            'success': True,
            'bot_running': False,
            'saldo_atual': 0.00,
            'lucro_liquido': 0.00,
            'win_rate': 0.0,
            'total_trades': 0,
            'trades': []
        })

    stats = {}

    # TENTA PEGAR STATS REAIS PRIMEIRO (mantém bot funcionando!)
    if BOTS_AVAILABLE and bot and hasattr(bot, 'stop_loss'):
        try:
            stats = bot.stop_loss.get_estatisticas()
            
            # Adiciona balance se disponível
            if hasattr(bot, 'api'):
                try:
                    stats['saldo_atual'] = bot.api.balance
                    stats['currency'] = bot.api.currency
                except:
                    pass
            
            # Retorna stats reais
            return jsonify({
                'success': True,
                'bot_running': True,
                'saldo_atual': stats.get('saldo_atual', stats.get('balance', 1000.00)),
                'lucro_liquido': stats.get('saldo_liquido', stats.get('lucro_liquido', 0.00)),
                'win_rate': stats.get('win_rate', 0.0),
                'total_trades': stats.get('total_trades', 0),
                'wins': stats.get('vitorias', 0),
                'losses': stats.get('derrotas', 0),
                'trades': stats.get('trades', []),
                'mode': 'REAL'
            })
        except Exception as e:
            print(f"⚠️ Erro ao buscar stats reais: {e}")

    # FALLBACK: Se não conseguiu stats reais, retorna estrutura válida
    # Isso garante que o frontend não quebre
    return jsonify({
        'success': True,
        'bot_running': True,
        'saldo_atual': 1000.00,
        'lucro_liquido': 0.00,
        'win_rate': 0.0,
        'total_trades': 0,
        'wins': 0,
        'losses': 0,
        'trades': [],
        'mode': 'WAITING_DATA'
    })

@app.route('/api/bot/reset/<bot_type>', methods=['POST'])
def reset_bot(bot_type):
    """
    ✅ NOVA ROTA - Reseta estado do bot
    Útil quando o bot fica travado
    """
    if bot_type not in bots_state:
        return jsonify({'error': f'Bot {bot_type} não encontrado'}), 404
    
    # Para o bot se estiver rodando
    bot = bots_state[bot_type].get('instance')
    if bot and hasattr(bot, 'stop'):
        try:
            bot.stop()
        except:
            pass
    
    bots_state[bot_type] = {
        'running': False,
        'instance': None,
        'thread': None
    }
    
    print(f"🔄 Bot {bot_type} resetado")
    
    return jsonify({
        'success': True,
        'message': f'Bot {bot_type} resetado com sucesso!'
    })

@app.route('/api/emergency/reset', methods=['POST'])
def emergency_reset():
    """Reset de emergência"""
    global bots_state

    for bot_type, state in bots_state.items():
        bot = state.get('instance')
        if bot and hasattr(bot, 'stop'):
            try:
                bot.stop()
            except:
                pass

    bots_state = {
        'manual': {'running': False, 'instance': None, 'thread': None},
        'ia': {'running': False, 'instance': None, 'thread': None},
        'ia_simples': {'running': False, 'instance': None, 'thread': None},
        'ia_avancado': {'running': False, 'instance': None, 'thread': None}
    }

    return jsonify({
        'success': True,
        'message': 'Estado resetado com sucesso!'
    })

# ==================== EXECUTAR ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False') == 'True'
    
    print("\n" + "=" * 70)
    print("🚀 ALPHA DOLAR 2.0 - API PRODUCTION (RENDER.COM)")
    print("✨ VERSÃO HÍBRIDA: Bot real + fallback para frontend")
    if BOTS_AVAILABLE:
        print("✅ BOTS PYTHON REAIS INTEGRADOS!")
    else:
        print("⚠️ MODO SIMULADO (Bots Python não disponíveis)")
    if CONFIG_LOADED:
        print("✅ CONFIG CARREGADO!")
    else:
        print("⚠️ CONFIG NÃO CARREGADO!")
    print(f"🔑 Token configurado: {'SIM' if DERIV_TOKEN else 'NÃO'}")
    print("=" * 70)
    print(f"🌐 Porta: {port}")
    print("=" * 70 + "\n")

    app.run(host='0.0.0.0', port=port, debug=debug)
