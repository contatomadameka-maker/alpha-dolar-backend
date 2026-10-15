"""TELEGRAM-ADMIN-V1 — avisos pessoais do Dirlei no Telegram (robo separado do robo de sinais dos clientes).
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
        return True, ''
    except Exception as e:
        msg = str(e)
        if tok in msg:
            msg = msg.replace(tok, '***')
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
        ok, erro = enviar_agora('✅ Alpha Avisos ligado.\nDaqui pra frente os avisos do sistema chegam aqui.')
        return jsonify({'ok': ok, 'erro': erro, 'tem_token': bool(tok), 'tem_chat': bool(chat)})

    app.config['ALPHA_AVISAR'] = avisar
    print('TELEGRAM-ADMIN: registrado (token=%s, chat=%s)' % (bool(_cfg()[0]), bool(_cfg()[1])))
