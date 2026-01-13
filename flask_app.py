"""
ALPHA DOLAR 2.0 - API Flask (CORRIGIDO - CORS + ROTAS)
Backend para Alpha Dolar 2.0
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sys
import os
import random
import time
from datetime import datetime

app = Flask(__name__)

# ✅ CORS CORRIGIDO
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Estado dos bots
bot_states = {
    'manual': {'running': False, 'stats': {}, 'start_time': None},
    'ia-simples': {'running': False, 'stats': {}, 'start_time': None},
    'ia-avancado': {'running': False, 'stats': {}, 'start_time': None},
    'ia': {'running': False, 'stats': {}, 'start_time': None}
}

@app.route('/api/bot/start', methods=['POST', 'OPTIONS'])
def start_bot():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    data = request.json
    bot_type = data.get('bot_type')
    config = data.get('config', {})

    if bot_type not in bot_states:
        return jsonify({'success': False, 'error': 'Bot não encontrado'}), 400

    if bot_states[bot_type]['running']:
        return jsonify({'success': False, 'error': 'Bot já está rodando'}), 400

    bot_states[bot_type]['running'] = True
    bot_states[bot_type]['start_time'] = time.time()
    bot_states[bot_type]['stats'] = {
        'balance': 10000.00,
        'saldo_liquido': 0.00,
        'win_rate': 0.0,
        'total_trades': 0,
        'wins': 0,
        'losses': 0,
        'trades': []
    }

    return jsonify({
        'success': True,
        'message': f'Bot {bot_type} iniciado!',
        'bot_type': bot_type,
        'mode': 'demo'
    })

@app.route('/api/bot/stop', methods=['POST', 'OPTIONS'])
def stop_bot():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    data = request.json
    bot_type = data.get('bot_type')

    if bot_type not in bot_states:
        return jsonify({'success': False, 'error': 'Bot não encontrado'}), 400

    stats = bot_states[bot_type].get('stats', {})
    bot_states[bot_type]['running'] = False

    return jsonify({
        'success': True,
        'message': f'Bot {bot_type} parado!',
        'stats': stats
    })

@app.route('/api/bot/stats/<bot_type>', methods=['GET', 'OPTIONS'])
def bot_stats(bot_type):
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    if bot_type not in bot_states:
        return jsonify({'success': False, 'error': 'Bot não encontrado'}), 404
    
    bot = bot_states[bot_type]
    
    if not bot['running']:
        return jsonify({
            'success': True,
            'bot_running': False,
            'stats': {
                'balance': 10000.00,
                'saldo_liquido': 0.00,
                'total_trades': 0
            }
        })
    
    stats = bot.get('stats', {})
    elapsed = time.time() - bot['start_time']
    
    if elapsed > 10 and stats['total_trades'] < 50:
        is_win = random.random() > 0.35
        profit = random.uniform(0.5, 2.0) if is_win else random.uniform(-0.35, -1.0)
        
        stats['total_trades'] += 1
        if is_win:
            stats['wins'] += 1
        else:
            stats['losses'] += 1
        
        stats['saldo_liquido'] += profit
        stats['balance'] = 10000 + stats['saldo_liquido']
        stats['win_rate'] = (stats['wins'] / stats['total_trades']) * 100
        
        bot['start_time'] = time.time()
    
    return jsonify({
        'success': True,
        'bot_running': True,
        'stats': stats
    })

@app.route('/api/balance', methods=['GET', 'OPTIONS'])
def get_balance():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    return jsonify({
        'success': True,
        'balance': 10000.00,
        'formatted': '$10,000.00'
    })

@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    return jsonify({
        'status': 'ok',
        'message': 'Alpha Dolar API Running on Render'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Alpha Dolar 2.0 API")
    print(f"🌐 Porta: {port}")
    app.run(debug=False, host='0.0.0.0', port=port)
