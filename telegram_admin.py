"""TELEGRAM-ADMIN-V1 + AVISOS-LOG-V1 — avisos pessoais do Dirlei no Telegram (robo separado do robo de sinais dos clientes).
Variaveis no Render: TELEGRAM_ADMIN_TOKEN (token do BotFather) e TELEGRAM_ADMIN_CHAT (id do chat).
Sem as duas, nada e enviado e nada quebra.
Uso no resto do servidor: from telegram_admin import avisar; avisar('texto', chave='venda', intervalo=60)
"""
import os
import time
import threading
import urllib.parse
import urllib.request

_ULTIMO = {}
_TRAVA = threading.Lock()
# AVISOS-LOG-V1: historico dos envios (memoria + Redis, para o painel do admin)
import json as _json
from collections import deque as _deque
_LOG = _deque(maxlen=200)
_RKEY = 'alpha:avisos_log'
_REDIS = {'c': None, 't': 0}


def _redis():
    if _REDIS['c'] is not None or time.time() - _REDIS['t'] < 60:
        return _REDIS['c']
    _REDIS['t'] = time.time()
    try:
        import redis
        url = os.environ.get('REDIS_URL', '')
        if url:
            _REDIS['c'] = redis.from_url(url, decode_responses=True, socket_timeout=3)
    except Exception as e:
        print('AVISOS-LOG: sem Redis', e)
    return _REDIS['c']


def _tipo(texto):
    t = str(texto)
    if 'EXEMPLO' in t or t.startswith('✅ Alpha Avisos'):
        return 'teste'
    if t.startswith(('💰', '🔁', '🟡', '↩️', '🔴 VENDA', '⚠️ Cakto')):
        return 'venda'
    if 'SITE' in t[:20] or t.startswith('✅ Site'):
        return 'site'
    if t.startswith('⚠️ ROBÔ'):
        return 'robo'
    if t.startswith('📊'):
        return 'resumo'
    if t.startswith(('📅', '⏰', '🔔')):
        return 'agenda'
    return 'aviso'


def _registra(texto, ok, erro):
    item = {'t': int(time.time()), 'tipo': _tipo(texto), 'texto': str(texto)[:600], 'ok': bool(ok), 'erro': str(erro or '')[:200]}
    _LOG.appendleft(item)
    try:
        r = _redis()
        if r is not None:
            r.lpush(_RKEY, _json.dumps(item, ensure_ascii=False))
            r.ltrim(_RKEY, 0, 299)
    except Exception as e:
        print('AVISOS-LOG: nao gravou no Redis', e)


def historico(n=80):
    try:
        r = _redis()
        if r is not None:
            return [_json.loads(x) for x in r.lrange(_RKEY, 0, n - 1)], 'redis'
    except Exception:
        pass
    return list(_LOG)[:n], 'memoria'


def configurado():
    tok, chat = _cfg()
    return bool(tok), bool(chat)


def _cfg():
    return os.environ.get('TELEGRAM_ADMIN_TOKEN', '').strip(), os.environ.get('TELEGRAM_ADMIN_CHAT', '').strip()


def enviar_agora(texto):
    """Envia e espera a resposta. Devolve (ok, erro)."""
    tok, chat = _cfg()
    if not tok or not chat:
        return False, 'faltou TELEGRAM_ADMIN_TOKEN ou TELEGRAM_ADMIN_CHAT no Render'
    try:
        dados = urllib.parse.urlencode({'chat_id': chat, 'text': str(texto)[:4000], 'disable_web_page_preview': 'true'}).encode()
        req = urllib.request.Request('https://api.telegram.org/bot%s/sendMessage' % tok, data=dados)
        urllib.request.urlopen(req, timeout=12).read()
        _registra(texto, True, '')
        return True, ''
    except Exception as e:
        msg = str(e)
        if tok in msg:
            msg = msg.replace(tok, '***')
        _registra(texto, False, msg)
        return False, msg[:200]


def avisar(texto, chave=None, intervalo=0):
    """Envia em segundo plano (nao atrasa o servidor). Com chave+intervalo, nao repete o mesmo aviso antes do intervalo (segundos)."""
    tok, chat = _cfg()
    if not tok or not chat:
        return False
    if chave and intervalo:
        agora = time.time()
        with _TRAVA:
            if agora - _ULTIMO.get(chave, 0) < intervalo:
                return False
            _ULTIMO[chave] = agora

    def _vai():
        ok, erro = enviar_agora(texto)
        if not ok:
            print('TELEGRAM-ADMIN: nao enviou:', erro)
    threading.Thread(target=_vai, daemon=True).start()
    return True


def register_telegram_admin(app):
    from flask import request, jsonify

    @app.route('/api/admin/telegram-teste', methods=['GET'])
    def _tg_admin_teste():
        senha = os.environ.get('ADMIN_SENHA', '')
        dado = request.headers.get('X-Admin-Token') or request.args.get('senha', '')
        if not senha or dado != senha:
            return jsonify({'ok': False, 'erro': 'senha do admin errada'}), 403
        tok, chat = _cfg()
        if request.args.get('exemplo') == 'venda':
            ok, erro = enviar_agora('💰 VENDA APROVADA (EXEMPLO, não é venda real)\n👤 Cliente Teste\n📧 cliente@exemplo.com\n📦 Alpha Dolar Plano Pro · Mensal\n💵 R$ 97,00\n✅ plano-pro liberado até 14/11/2026')
        else:
            ok, erro = enviar_agora('✅ Alpha Avisos ligado.\nDaqui pra frente os avisos do sistema chegam aqui.')
        return jsonify({'ok': ok, 'erro': erro, 'tem_token': bool(tok), 'tem_chat': bool(chat)})

    app.config['ALPHA_AVISAR'] = avisar
    print('TELEGRAM-ADMIN: registrado (token=%s, chat=%s)' % (bool(_cfg()[0]), bool(_cfg()[1])))
