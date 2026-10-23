# -*- coding: utf-8 -*-
"""SALA-DIGITOS-V4.1 (ponte do Telegram sem conexao pendurada; rotas do site sem rede) / V4 (robo segue o sinal do servidor; Telegram obrigatorio) / V3.5 (1 processo so, log das respostas) / V3.4 (ticks no formato do schema novo) / V3.3 (varios enderecos de ticks) / V3.2 (assume trava abandonada) / V3.1 (diagnostico + supervisor que se religa) / V3 (1 postagem por sinal, editada no resultado; banner + botao) - Sala de sinais Alpha Digitos (par/impar) no canal do Telegram.

Usa o MESMO bot e o MESMO canal do robo de sinais antigo
(backend.telegram_signals: TELEGRAM_TOKEN / CHANNEL_ID). Nada novo no Render.
Quando a sala esta ligada, o loop antigo (robo_sinais) e desligado para nao misturar.

Ciclo: ATENCAO -> ENTRADA CONFIRMADA -> GAIN (SG/G1/G2/G3) | LOSS | ABORTADA
Parcial automatica (padrao: a cada 60 min) e sob demanda pelo admin.

Rotas (cabecalho X-Admin-Token = ADMIN_SENHA):
  GET  /api/admin/sala-digitos/status
  POST /api/admin/sala-digitos/ligar
  POST /api/admin/sala-digitos/desligar
  POST /api/admin/sala-digitos/parcial
  POST /api/admin/sala-digitos/config   {mercados, atencao, confirma, gales, mult, payout, espera, intervalo, parcial}
"""
import os
import json
import time
import uuid
import threading
import urllib.request
import urllib.error
from collections import deque
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))
# SALA-DIGITOS-V3.3: tenta varios enderecos publicos de ticks (o binaryws respondia 520)
WS_URLS = [u for u in [os.environ.get('SALA_WS_URL', '').strip(),
                       'wss://api.derivws.com/trading/v1/options/ws/public',
                       'wss://ws.derivws.com/websockets/v3?app_id=1089',
                       'wss://ws.binaryws.com/websockets/v3?app_id=1089'] if u]
WS_URL = WS_URLS[0]
# SALA-DIGITOS-V2: cada sinal sai como foto + texto + botao para o robo
LINK_ROBO = os.environ.get('SALA_LINK', 'https://alphadolar.online/bot-digitos.html')
IMG_BASE = os.environ.get('SALA_IMG_BASE', 'https://alphadolar.online/img/sala/')
IMG_VER = '3'
ESTRATEGIA = 'ALPHA VIRADA'
BOTAO = {'inline_keyboard': [[{'text': '🎲 Abrir Alpha Dígitos', 'url': LINK_ROBO}]]}
_FILE_IDS = {}

NOMES = {
    'R_10': 'Volatility 10 Index', 'R_25': 'Volatility 25 Index', 'R_50': 'Volatility 50 Index',
    'R_75': 'Volatility 75 Index', 'R_100': 'Volatility 100 Index',
    '1HZ10V': 'Volatility 10 (1s) Index', '1HZ25V': 'Volatility 25 (1s) Index',
    '1HZ50V': 'Volatility 50 (1s) Index', '1HZ75V': 'Volatility 75 (1s) Index',
    '1HZ100V': 'Volatility 100 (1s) Index',
}
SIMBOLOS = list(NOMES.keys())

CFG_PADRAO = {
    'mercados': ['R_10', 'R_25', 'R_50', 'R_75', 'R_100'],
    'atencao': 3,      # sequencia de mesma paridade que dispara o ATENCAO
    'confirma': 4,     # sequencia que confirma a entrada (aposta na paridade contraria)
    'gales': 3,        # 0 a 3
    'mult': 2.5,       # multiplicador do gale
    'payout': 0.95,    # lucro por unidade no par/impar (so para o saldo em unidades do admin)
    'espera': 4,       # segundos entre a confirmacao/gale e o tick que vale
    'intervalo': 5,    # minutos de pausa depois de um GAIN/LOSS
    'parcial': 60,     # minutos entre parciais automaticas
}
LIMITES = {'atencao': (2, 8), 'confirma': (3, 10), 'gales': (0, 3), 'espera': (1, 30),
           'intervalo': (0, 120), 'parcial': (15, 480)}

K_ON, K_CFG, K_LOCK, K_SNAP, K_CMD = 'sala_dig:on', 'sala_dig:cfg', 'sala_dig:lock', 'sala_dig:snap', 'sala_dig:cmd'
K_LIVE, K_TGATIVO = 'sala_dig:live', 'sala_dig:tgativo'   # SALA-DIGITOS-V4.3: estado ao vivo compartilhado entre servidores
RODAPE = '<i>Análise estatística — não é garantia de resultado.</i>\n🌐 alphadolar.online'


def _hora(ep):
    return datetime.fromtimestamp(ep, BRT).strftime('%H:%M:%S')


def _num(x):
    s = ('%.2f' % x).rstrip('0').rstrip('.')
    return s.replace('.', ',')


def valida_cfg(d, base):
    c = dict(base)
    d = d or {}
    if isinstance(d.get('mercados'), list):
        m = [s for s in d['mercados'] if s in NOMES]
        if m:
            c['mercados'] = m
    for k, (lo, hi) in LIMITES.items():
        if k in d:
            try:
                c[k] = max(lo, min(hi, int(float(d[k]))))
            except (TypeError, ValueError):
                pass
    for k, lo, hi in (('mult', 1.0, 5.0), ('payout', 0.5, 1.0)):
        if k in d:
            try:
                c[k] = round(max(lo, min(hi, float(str(d[k]).replace(',', '.')))), 3)
            except (TypeError, ValueError):
                pass
    if c['confirma'] <= c['atencao']:
        c['confirma'] = c['atencao'] + 1
    return c


class KV(object):
    """Redis quando existir; senao memoria (um processo so)."""

    def __init__(self, get_redis=None):
        self._g = get_redis
        self._m = {}

    def _r(self):
        try:
            r = self._g() if self._g else None
        except Exception:
            r = None
        if r is not None:
            return r
        # SALA-DIGITOS-V3.1: o app principal nao tem redis_client global; usa o REDIS_URL direto (como o resto do backend)
        if not hasattr(self, '_proprio'):
            self._proprio = None
            url = os.environ.get('REDIS_URL', '').strip()
            if url:
                try:
                    import redis as _redis
                    self._proprio = _redis.from_url(url, decode_responses=True, socket_timeout=3)
                except Exception as e:
                    print('[SalaDigitos] Redis indisponivel: %s' % e)
        return self._proprio

    @staticmethod
    def _s(v):
        return v.decode() if isinstance(v, bytes) else v

    def get(self, k):
        r = self._r()
        if r is not None:
            try:
                return self._s(r.get(k))
            except Exception:
                pass
        return self._m.get(k)

    def set(self, k, v, ex=None):
        self._m[k] = v
        r = self._r()
        if r is not None:
            try:
                if ex:
                    r.set(k, v, ex=ex)
                else:
                    r.set(k, v)
            except Exception:
                pass

    def delete(self, k):
        self._m.pop(k, None)
        r = self._r()
        if r is not None:
            try:
                r.delete(k)
            except Exception:
                pass

    def trava(self, k, dono, ex):
        """True se este processo e (ou passou a ser) o dono da trava."""
        r = self._r()
        if r is None:
            cur = self._m.get(k)
            if cur in (None, dono):
                self._m[k] = dono
                return True
            return False
        try:
            if r.set(k, dono, nx=True, ex=ex):
                return True
            if self._s(r.get(k)) == dono:
                r.expire(k, ex)
                return True
            return False
        except Exception:
            return True


def _cred():
    try:
        import backend.telegram_signals as ts
        tok = getattr(ts, 'TELEGRAM_TOKEN', '') or os.environ.get('TELEGRAM_TOKEN', '')
        chat = getattr(ts, 'CHANNEL_ID', '')
    except Exception as e:
        return '', '', 'telegram_signals: %s' % e
    if not tok or not chat:
        return '', '', 'TELEGRAM_TOKEN ou CHANNEL_ID vazio no servidor'
    return tok, chat, ''


def _tg_raw(metodo, dados, timeout=15):
    """Chamada crua ao Telegram (sem chat_id automatico). Devolve (ok, erro, json)."""
    tok, _chat, erro = _cred()
    if erro:
        return False, erro, {}
    body = json.dumps(dados).encode('utf-8')
    req = urllib.request.Request('https://api.telegram.org/bot%s/%s' % (tok, metodo), data=body,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode('utf-8'))
        return bool(j.get('ok')), (j.get('description') or ''), j
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode('utf-8')).get('description', str(e)), {}
        except Exception:
            return False, str(e), {}
    except Exception as e:
        return False, str(e), {}


def _tg_http(metodo, dados):
    """Chamada ao Telegram no canal do robo antigo (poe o chat_id do canal)."""
    _tok, chat, erro = _cred()
    if erro:
        return False, erro, {}
    dados = dict(dados)
    dados['chat_id'] = chat
    return _tg_raw(metodo, dados)


# ---------- SALA-DIGITOS-V4: liberar o "Seguir a Sala" so para quem esta no canal ----------
CANAL_LINK = os.environ.get('SALA_CANAL_LINK', 'https://t.me/+YHItYk9rqLAxZjRh')
_BOT = {}


def bot_usuario():
    if not _BOT.get('u'):
        ok, _e, j = _tg_raw('getMe', {}, timeout=10)
        if ok:
            _BOT['u'] = (j.get('result') or {}).get('username') or ''
    return _BOT.get('u') or ''


class Ponte(object):
    """Liga a pessoa do site ao Telegram dela: /start <codigo> no bot -> confere se e membro do canal."""

    def __init__(self, kv):
        self.kv = kv
        self.id = uuid.uuid4().hex[:10]
        self.pid = None
        self.th = None
        self.ativo_ate = 0          # SALA-DIGITOS-V4.1: so le o bot quando alguem pediu link (15 min)
        self.pend = set()           # pessoas para conferir no canal (em segundo plano)
        self.cache = {}             # pessoa -> (conectado, membro, quando)
        self.info = {'ativo': False, 'erro': '', 'ligados': 0, 'volta': 0}

    def garante(self):
        if self.th is not None and self.th.is_alive() and self.pid == os.getpid():
            return
        self.pid = os.getpid()
        self.id = uuid.uuid4().hex[:10]
        self.th = threading.Thread(target=self.loop, daemon=True)
        self.th.start()

    def _confere(self, pessoa):
        """Rede: so roda na thread da ponte, nunca dentro de um pedido do site."""
        uid = self.kv.get('sala_dig:tguser:' + pessoa)
        if not uid:
            self.cache[pessoa] = (False, False, time.time())
            return False, False
        ok, _e, j = _tg_http('getChatMember', {'user_id': int(uid)})
        if not ok:
            ant = self.cache.get(pessoa)
            return (True, ant[1]) if ant else (True, False)
        r = j.get('result') or {}
        st = r.get('status') or ''
        mem = st in ('creator', 'administrator', 'member') or (st == 'restricted' and bool(r.get('is_member')))
        self.cache[pessoa] = (True, bool(mem), time.time())
        return True, bool(mem)

    def membro(self, pessoa, forca=False):
        """Resposta imediata (memoria). Se estiver velho ou pedirem, agenda conferencia em segundo plano."""
        ant = self.cache.get(pessoa)
        if ant is None:
            uid = self.kv.get('sala_dig:tguser:' + pessoa)
            ant = (bool(uid), False, 0)
            self.cache[pessoa] = ant
        idade = time.time() - ant[2]
        if ant[0] and ((forca and idade > 6) or idade > (600 if ant[1] else 15)):
            self.pend.add(pessoa)
        return ant[0], ant[1]

    def _responde(self, uid, texto):
        _tg_raw('sendMessage', {'chat_id': uid, 'text': texto, 'parse_mode': 'HTML', 'disable_web_page_preview': True,
                                'reply_markup': {'inline_keyboard': [[{'text': '📣 Entrar no canal da Sala', 'url': CANAL_LINK}],
                                                                     [{'text': '🎲 Voltar ao Alpha Dígitos', 'url': LINK_ROBO}]]}},
                timeout=10)

    def _trata(self, u):
        m = u.get('message') or {}
        txt = (m.get('text') or '').strip()
        uid = (m.get('from') or {}).get('id')
        if not uid or not txt.startswith('/start'):
            return
        partes = txt.split()
        cod = partes[1] if len(partes) > 1 else ''
        pessoa = self.kv.get('sala_dig:tgcod:' + cod) if cod else None
        if not pessoa:
            self._responde(uid, '👋 Olá! Para liberar o <b>Seguir a Sala</b> no Alpha Dígitos, toque em '
                                '<b>Conectar meu Telegram</b> dentro do robô.')
            return
        self.kv.delete('sala_dig:tgcod:' + cod)
        self.kv.set('sala_dig:tguser:' + pessoa, str(uid))
        self.info['ligados'] += 1
        _lig, mem = self._confere(pessoa)
        if mem:
            self._responde(uid, '✅ <b>Telegram conectado!</b>\n\nVocê já está no canal da Sala. Volte ao Alpha Dígitos e toque em '
                                '<b>Seguir a Sala de Sinais</b>.')
        else:
            self._responde(uid, '✅ <b>Telegram conectado!</b>\n\nFalta só um passo: entre no canal da Sala de Sinais no botão abaixo. '
                                'Depois volte ao Alpha Dígitos e toque em <b>Seguir a Sala de Sinais</b>.')

    def loop(self):
        meu = self.id
        while meu == self.id:
            try:
                self.info['volta'] = int(time.time())
                if not _BOT.get('u'):
                    bot_usuario()
                for p in list(self.pend)[:5]:          # conferencias pedidas pelo site
                    self.pend.discard(p)
                    self._confere(p)
                try:
                    self.ativo_ate = max(self.ativo_ate, float(self.kv.get(K_TGATIVO) or 0))   # V4.3
                except Exception:
                    pass
                if time.time() > self.ativo_ate:       # ninguem pediu link: nao le o bot
                    self.info['ativo'] = False
                    time.sleep(3)
                    continue
                self.info['ativo'] = True
                off = int(self.kv.get('sala_dig:tgoff') or 0)
                ok, erro, j = _tg_raw('getUpdates', {'offset': off, 'timeout': 0, 'allowed_updates': ['message']}, timeout=10)
                if not ok:
                    self.info['erro'] = erro[:200]
                    print('[SalaDigitos] ponte Telegram: %s' % erro)
                    time.sleep(30 if 'onflict' in erro else 6)
                    continue
                self.info['erro'] = ''
                for u in j.get('result') or []:
                    off = max(off, int(u.get('update_id', 0)) + 1)
                    try:
                        self._trata(u)
                    except Exception as e:
                        print('[SalaDigitos] ponte /start: %s' % e)
                self.kv.set('sala_dig:tgoff', str(off))
                time.sleep(3)
            except Exception as e:
                self.info['erro'] = str(e)[:200]
                time.sleep(6)


def _foto(img):
    return _FILE_IDS.get(img) or (IMG_BASE + img + '.jpg?v=' + IMG_VER)


def _guarda_foto(img, j):
    try:
        _FILE_IDS[img] = j['result']['photo'][-1]['file_id']
    except Exception:
        pass


def postar(tg, texto, img=None, botao=True):
    """Posta (foto+legenda, ou so texto se a foto falhar). Devolve (ok, erro, message_id, tipo)."""
    extra = {'reply_markup': BOTAO} if botao else {}
    erro_foto = ''
    if img:
        d = {'photo': _foto(img), 'caption': texto[:1024], 'parse_mode': 'HTML'}
        d.update(extra)
        ok, erro, j = tg('sendPhoto', d)
        if ok:
            _guarda_foto(img, j)
            return True, '', (j.get('result') or {}).get('message_id'), 'foto'
        _FILE_IDS.pop(img, None)
        erro_foto = 'foto %s: %s' % (img, erro)
        print('[SalaDigitos] foto falhou, mandando so texto: %s' % erro)
    d = {'text': texto, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    d.update(extra)
    ok, erro, j = tg('sendMessage', d)
    return ok, (erro or erro_foto), (j.get('result') or {}).get('message_id'), 'texto'


def enviar_canal(texto, img=None, botao=True):
    ok, erro, _mid, _t = postar(_tg_http, texto, img, botao)
    return ok, erro


def _par(d):
    return 'PAR' if d % 2 == 0 else 'IMPAR'


def _lado_txt(l):
    return 'PAR' if l == 'PAR' else 'ÍMPAR'


def _tick_s(sym):
    return 1 if str(sym).startswith('1HZ') else 2


class Sala(object):
    """SALA-DIGITOS-V3: 1 postagem por sinal (ATENCAO -> apaga; CONFIRMADA -> editada no GAIN/LOSS)."""

    def __init__(self, kv, tg=_tg_http, parar_antigo=None, fila_sincrona=False):
        self.kv = kv
        self.tg = tg
        self.parar_antigo = parar_antigo
        self.fila_sincrona = fila_sincrona   # testes: envia na hora
        self.id = uuid.uuid4().hex[:10]
        self.lock = threading.RLock()
        self.cfg = self._cfg_load()
        self.dig = {}
        self.st = {'fase': 'livre'}
        self.cool = 0
        self.ciclo = 0
        self.msgs = {}
        self.dia = None
        self.hoje = None
        self.desde_parcial = 0
        self.ult_parcial = time.time()
        self.rodando = False
        self.ws_thread = None
        self.ws = {'conectado': False, 'ultimo_tick': 0, 'erro': '', 'ticks': 0}
        self.envio = {'ok': 0, 'falhas': 0, 'ultimo_erro': '', 'ultimo': ''}
        self.fila = deque()
        self.fila_ev = threading.Event()
        self.fila_thread = None
        self.sup_thread = None
        self.diag = {'pid': os.getpid(), 'sup_inicio': 0, 'sup_volta': 0, 'voltas': 0, 'sup_erro': '', 'dono': False}

    # ---------- config / dia ----------
    def _cfg_load(self):
        raw = self.kv.get(K_CFG)
        try:
            return valida_cfg(json.loads(raw) if raw else {}, CFG_PADRAO)
        except Exception:
            return dict(CFG_PADRAO)

    def _dia(self, ep):
        d = datetime.fromtimestamp(ep, BRT).strftime('%Y-%m-%d')
        if d != self.dia:
            self.dia = d
            raw = self.kv.get('sala_dig:dia:' + d)
            try:
                self.hoje = json.loads(raw) if raw else None
            except Exception:
                self.hoje = None
            if not self.hoje:
                self.hoje = {'win': 0, 'loss': 0, 'abort': 0, 'gale': [0, 0, 0, 0], 'un': 0.0, 'ciclos': []}
            self.desde_parcial = 0
        return self.hoje

    def _salva_dia(self):
        if self.dia and self.hoje is not None:
            self.kv.set('sala_dig:dia:' + self.dia, json.dumps(self.hoje), ex=86400 * 31)   # SALA-HIST-V2: detalhe 31 dias
            h = self.hoje
            self.kv.set('sala_dig:res:' + self.dia, json.dumps({'win': h['win'], 'loss': h['loss'], 'abort': h['abort'],
                                                                 'gale': h['gale'], 'un': h['un']}))   # resumo do dia: sem prazo

    # ---------- fila de envio (nao trava a leitura de ticks) ----------
    def _fila(self, item):
        if self.fila_sincrona:
            self._exec(item)
            return
        self.fila.append(item)
        if not self.fila_thread or not self.fila_thread.is_alive():
            self.fila_thread = threading.Thread(target=self._fila_loop, daemon=True)
            self.fila_thread.start()
        self.fila_ev.set()

    def post(self, chave, texto, img=None, botao=True):
        self._fila({'op': 'post', 'k': chave, 't': texto, 'img': img, 'b': botao})

    def edita(self, chave, texto, img=None, botao=True):
        self._fila({'op': 'edit', 'k': chave, 't': texto, 'img': img, 'b': botao})

    def apaga(self, chave):
        self._fila({'op': 'del', 'k': chave})

    def manda(self, texto, img=None, botao=True):   # postagem avulsa (parcial, abertura)
        self.post(None, texto, img, botao)

    def _conta(self, ok, erro, texto=''):
        if ok:
            self.envio['ok'] += 1
            self.envio['ultimo'] = (texto or '').split('\n')[0][:80]
        else:
            self.envio['falhas'] += 1
            self.envio['ultimo_erro'] = (erro or '')[:200]
            print('[SalaDigitos] Telegram recusou: %s' % erro)

    def _exec(self, it):
        op, k = it['op'], it.get('k')
        try:
            if op == 'post' or (op == 'edit' and k not in self.msgs):
                ok, erro, mid, tipo = postar(self.tg, it['t'], it['img'], it['b'])
                self._conta(ok, erro, it['t'])
                if ok and k and mid:
                    self.msgs[k] = (mid, tipo)
                    if len(self.msgs) > 40:
                        for velho in list(self.msgs)[:-40]:
                            self.msgs.pop(velho, None)
                return
            if op == 'del':
                m = self.msgs.pop(k, None)
                if m:
                    self.tg('deleteMessage', {'message_id': m[0]})
                return
            mid, tipo = self.msgs[k]
            extra = {'reply_markup': BOTAO} if it['b'] else {}
            if tipo == 'foto':
                ok, erro = False, ''
                if it['img']:
                    d = {'message_id': mid, 'media': {'type': 'photo', 'media': _foto(it['img']),
                                                      'caption': it['t'][:1024], 'parse_mode': 'HTML'}}
                    d.update(extra)
                    ok, erro, j = self.tg('editMessageMedia', d)
                    if ok:
                        _guarda_foto(it['img'], j)
                if not ok:
                    d = {'message_id': mid, 'caption': it['t'][:1024], 'parse_mode': 'HTML'}
                    d.update(extra)
                    ok, erro, j = self.tg('editMessageCaption', d)
            else:
                d = {'message_id': mid, 'text': it['t'], 'parse_mode': 'HTML', 'disable_web_page_preview': True}
                d.update(extra)
                ok, erro, j = self.tg('editMessageText', d)
            if not ok and 'not modified' in (erro or ''):
                ok = True
            self._conta(ok, erro, it['t'])
        except Exception as e:
            self._conta(False, 'erro interno: %s' % e)

    def _fila_loop(self):
        while True:
            self.fila_ev.wait(30)
            self.fila_ev.clear()
            while self.fila:
                self._exec(self.fila.popleft())
                time.sleep(0.35)

    # ---------- textos ----------
    def _pct(self, h):
        t = h['win'] + h['loss']
        return round(h['win'] * 100.0 / t, 1) if t else 0.0

    def texto_parcial(self, ep=None):
        ep = ep or time.time()
        h = self._dia(ep)
        g = h['gale']
        dt = datetime.fromtimestamp(ep, BRT)
        return ('📊 <b>PARCIAL ALPHA DÍGITOS</b>\n📅 %s · %s\n━━━━━━━━━━━━━━\n'
                '✅ Win: <b>%d</b>    ❌ Loss: <b>%d</b>\n🎯 Assertividade: <b>%s%%</b>\n'
                '🥇 Wins por gale: SG: %d · G1: %d · G2: %d · G3: %d\n━━━━━━━━━━━━━━\n%s') % (
            dt.strftime('%d/%m/%Y'), dt.strftime('%H:%M'), h['win'], h['loss'], _num(self._pct(h)),
            g[0], g[1], g[2], g[3], RODAPE)

    def _cab(self, st):
        c = self.cfg
        return ('📊 Mercado: <b>%s</b>\n🧠 Estratégia: %s\n🧩 Padrão: %s +%d = %s ATÉ %d GALE\n🎯 Sinal: <b>%s</b>'
                % (NOMES[st['sym']], ESTRATEGIA, ' · '.join(st['pad']), st['n'], _lado_txt(st['lado']).upper(),
                   c['gales'], _lado_txt(st['lado'])))

    def _txt_confirmada(self, st, indo=None):
        c = self.cfg
        t = ('🎯 <b>ENTRADA CONFIRMADA</b> 🎯\n\n%s\n⏱ Entrar: depois de <b>%d tick%s</b> · contrato de 1 tick\n'
             '🔁 Até %d gale (x%s)\n⏰ %s') % (self._cab(st), st['n'], '' if st['n'] == 1 else 's', c['gales'],
                                              _num(c['mult']), _hora(st['t_conf']))
        if st['linhas']:
            t += '\n\n' + '\n'.join(st['linhas'])
        if indo:
            t += '\n➡️ Faça o <b>G%d</b> agora (x%s)' % (indo, _num(c['mult'] ** indo))
        return t

    # ---------- motor ----------
    @staticmethod
    def _seq(q):
        if not q:
            return 0
        p, n = q[-1] % 2, 0
        for d in reversed(q):
            if d % 2 != p:
                break
            n += 1
        return n

    def _n(self, sym):
        return max(1, int(round(self.cfg['espera'] / float(_tick_s(sym)))))

    def on_tick(self, sym, d, ep):
        with self.lock:
            q = self.dig.setdefault(sym, deque(maxlen=30))
            q.append(d)
            c, st = self.cfg, self.st
            f = st['fase']
            if f != 'livre' and ep - st.get('ini', ep) > 240:
                self._abortar(ep, 'O mercado parou de mandar ticks')
                return
            if f == 'livre':
                if ep < self.cool or sym not in c['mercados']:
                    return
                s = self._seq(q)
                if s == c['atencao']:
                    self.ciclo += 1
                    lado = 'PAR' if d % 2 == 1 else 'IMPAR'   # contra a sequencia
                    self.st = {'fase': 'atencao', 'sym': sym, 'lado': lado, 'seq': s, 'ini': ep,
                               'k': 'c%d' % self.ciclo, 'linhas': []}
                    pad = ['P' if x % 2 == 0 else 'I' for x in list(q)[-s:]]
                    self.post(self.st['k'] + 'a',
                              '⚠️ <b>ATENÇÃO</b> ⚠️\n\n📊 Mercado: <b>%s</b>\n🧠 Estratégia: %s\n'
                              '🧩 Padrão em formação: %s\n\n⏳ Abra o Alpha Dígitos neste mercado e aguarde a confirmação.'
                              % (NOMES[sym], ESTRATEGIA, ' · '.join(pad)), 'atencao')
            elif f == 'atencao' and sym == st['sym']:
                seq_impar = st['lado'] == 'PAR'
                if (d % 2 == 1) == seq_impar:
                    st['seq'] += 1
                    if st['seq'] >= c['confirma']:
                        st.update(fase='entrada', passo=0, n=self._n(sym), falta=self._n(sym), t_conf=ep, res=[],
                                  pad=['P' if x % 2 == 0 else 'I' for x in list(q)[-6:]])
                        self.apaga(st['k'] + 'a')
                        self.post(st['k'], self._txt_confirmada(st), 'confirmada')
                else:
                    self._abortar(ep, 'O padrão se desfez antes da confirmação')
            elif f == 'entrada' and sym == st['sym']:
                st['falta'] -= 1
                if st['falta'] > 0:
                    return
                st['res'].append(d)
                st.setdefault('passos', []).append({'g': st['passo'], 'ep': int(ep), 'd': d})   # SALA-COMPARA-V1
                rot = 'SG' if st['passo'] == 0 else 'G%d' % st['passo']
                ganhou = _par(d) == st['lado']
                st['linhas'].append('%s: %s → %d %s' % (rot, _lado_txt(_par(d)), d, '✅' if ganhou else '❌'))
                if ganhou:
                    self._fim(ep, True)
                elif st['passo'] >= c['gales']:
                    self._fim(ep, False)
                else:
                    st['passo'] += 1
                    st['falta'] = st['n']
                    self.edita(st['k'], self._txt_confirmada(st, indo=st['passo']), None)

    def _abortar(self, ep, motivo):
        h = self._dia(ep)
        h['abort'] += 1
        self._salva_dia()
        st = self.st
        sym = st.get('sym')
        k = st.get('k')
        txt = ('🚫 <b>ENTRADA ABORTADA</b> 🚫\n\n📊 Mercado: %s\n%s. Aguarde o próximo sinal.'
               % (NOMES.get(sym, sym or ''), motivo))
        if st.get('fase') == 'entrada' and k:
            self.edita(k, txt, 'abortada')
        elif k:
            self.apaga(k + 'a')   # padrao desfeito: some do canal (fica so a contagem no admin)
        self.st = {'fase': 'livre'}
        self.cool = ep + min(60, self.cfg['intervalo'] * 60)

    def _fim(self, ep, ganhou):
        c, st = self.cfg, self.st
        h = self._dia(ep)
        p = st['passo']
        stakes = [c['mult'] ** i for i in range(p + 1)]
        if ganhou:
            un = stakes[-1] * c['payout'] - sum(stakes[:-1])
            h['win'] += 1
            h['gale'][p] += 1
        else:
            un = -sum(stakes)
            h['loss'] += 1
        h['un'] = round(h['un'] + un, 4)
        h['ciclos'].insert(0, {'t': int(ep), 'sym': st['sym'], 'lado': st['lado'], 'res': 'win' if ganhou else 'loss',
                               'passo': p, 'dig': st['res'], 'un': round(un, 3),
                               'k': st.get('k'), 'conf': int(st.get('t_conf') or 0), 'passos': st.get('passos', [])})
        h['ciclos'] = h['ciclos'][:1000]  # SALA-HIST-V1
        self._salva_dia()
        d = st['res'][-1]
        corpo = '%s\n🎲 Resultado: %s · dígito %d\n%s\n⏰ %s' % (
            self._cab(st), _lado_txt(_par(d)), d, '\n'.join(st['linhas']), _hora(ep))
        if ganhou:
            tit = '✅ <b>WIN DE PRIMEIRA (SG)</b> ✅' if p == 0 else '✅ <b>WIN NO %dº GALE (G%d)</b> ✅' % (p, p)
            self.edita(st['k'], tit + '\n\n' + corpo, 'gain')
        else:
            self.edita(st['k'], '❌ <b>LOSS</b> ❌\n\n' + corpo + '\n\nFaz parte. Respeite seu stop e sua gestão.', 'loss')
        self.desde_parcial += 1
        self.st = {'fase': 'livre'}
        self.cool = ep + c['intervalo'] * 60

    # ---------- tarefas periodicas (so no dono) ----------
    def tarefas(self, agora=None):
        agora = agora or time.time()
        with self.lock:
            novo = self._cfg_load()
            if novo != self.cfg:
                self.cfg = novo
            cmd = self.kv.get(K_CMD)
            if cmd == 'parcial':
                self.kv.delete(K_CMD)
                self.manda(self.texto_parcial(agora), None, True)
                self.ult_parcial, self.desde_parcial = agora, 0
            elif agora - self.ult_parcial >= self.cfg['parcial'] * 60:
                if self.desde_parcial > 0:
                    self.manda(self.texto_parcial(agora), None, True)
                self.ult_parcial, self.desde_parcial = agora, 0
        self.kv.set(K_SNAP, json.dumps(self.snap(agora)), ex=60)

    def snap(self, agora=None):
        return {'fase': self.st.get('fase'), 'sym': self.st.get('sym'), 'lado': self.st.get('lado'),
                'passo': self.st.get('passo', 0), 'seq': self.st.get('seq', 0),
                'pausa_ate': int(self.cool), 'ws': dict(self.ws), 'envio': dict(self.envio), 'dono': self.id,
                't': int(agora or time.time())}

    # ---------- leitura de ticks ----------
    def _ws_loop(self):
        try:
            import websocket
        except Exception as e:
            self.ws['erro'] = 'biblioteca websocket ausente: %s' % e
            return
        espera, idx = 2, 0
        while self.rodando:
            ws = None
            url = WS_URLS[idx % len(WS_URLS)]
            novo = 'api.derivws.com' in url
            mapa = {}
            try:
                ws = websocket.create_connection(url, timeout=15, origin='https://alphadolar.online',
                                                 header=['User-Agent: Mozilla/5.0 (AlphaDigitos sala)'])
                vistos = 0
                for i, s in enumerate([x for x in SIMBOLOS if x in self.cfg['mercados']] or SIMBOLOS[:5]):
                    mapa[i + 1] = s
                    # SALA-DIGITOS-V3.4: o endpoint publico novo aceita so {ticks, subscribe, req_id} (schema da Deriv)
                    ws.send(json.dumps({'ticks': s, 'subscribe': 1, 'req_id': i + 1}))
                ws.settimeout(10)
                self.ws.update(conectado=True, erro='', url=url)
                sem_tick = time.time()
                espera, ult_ping = 2, time.time()
                while self.rodando:
                    if time.time() - ult_ping > 25:
                        ws.send('{"ping": 1}')
                        ult_ping = time.time()
                    if time.time() - sem_tick > 45:
                        raise Exception('conectou mas nenhum tick chegou em 45 s')
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        raise Exception('conexão fechada pela Deriv')
                    if vistos < 4:   # SALA-DIGITOS-V3.5: mostra no log as 1as respostas da Deriv
                        vistos += 1
                        print('[SalaDigitos] resposta %d de %s: %s' % (vistos, url.split('/')[2], str(raw)[:300]))
                    m = json.loads(raw)
                    if m.get('error'):
                        self.ws['erro'] = ('%s (%s)' % (m['error'].get('message') or '', mapa.get(m.get('req_id'), '?')))[:200]
                        continue
                    t = m.get('tick')
                    if not t or t.get('quote') is None:
                        continue
                    sym = t.get('symbol') or t.get('underlying_symbol') or mapa.get(m.get('req_id'))
                    if sym not in NOMES:
                        continue
                    sem_tick = time.time()
                    dec = int(t.get('pip_size') or 2)
                    d = int(('%.*f' % (dec, float(t['quote'])))[-1])
                    self.on_tick(sym, d, int(t.get('epoch') or time.time()))
                    self.ws['ultimo_tick'] = int(time.time())
                    self.ws['ticks'] += 1
            except Exception as e:
                self.ws.update(conectado=False, erro=('%s -> %s' % (url.split('/')[2], e))[:200])
                print('[SalaDigitos] WS %s: %s' % (url, e))
                idx += 1   # proxima tentativa usa o proximo endereco
            finally:
                try:
                    if ws:
                        ws.close()
                except Exception:
                    pass
            self.ws['conectado'] = False
            if self.rodando:
                time.sleep(espera)
                espera = min(30, espera * 2) if idx % len(WS_URLS) == 0 else 2

    def supervisor(self, atraso=8):
        self.diag['sup_inicio'] = int(time.time())
        time.sleep(atraso)
        while True:
            self.diag['sup_volta'] = int(time.time())
            self.diag['voltas'] += 1
            try:
                on = self.kv.get(K_ON) == '1'
                self.diag['ligada'] = on
                if on and self.parar_antigo:
                    self.parar_antigo()
                dono = on and self.kv.trava(K_LOCK, self.id, 30)
                if on and not dono:
                    # SALA-DIGITOS-V3.2: dono da trava sem sinal de vida (snapshot velho ou de outro dono) -> assume
                    atual = self.kv.get(K_LOCK)
                    try:
                        sn = json.loads(self.kv.get(K_SNAP) or 'null') or {}
                    except Exception:
                        sn = {}
                    vivo = sn.get('dono') == atual and time.time() - (sn.get('t') or 0) < 20
                    self.diag['lock_dono'] = atual
                    self.diag['lock_vivo'] = bool(vivo)
                    if not vivo:
                        self.diag['espera_lock'] = self.diag.get('espera_lock', 0) + 1
                        if self.diag['espera_lock'] >= 4:   # ~20 s sem sinal de vida do outro dono
                            self.kv.set(K_LOCK, self.id, ex=30)
                            dono = True
                            self.diag['assumiu'] = int(time.time())
                            print('[SalaDigitos] trava de %s sem sinal de vida; assumindo (%s)' % (atual, self.id))
                    else:
                        self.diag['espera_lock'] = 0
                else:
                    self.diag['espera_lock'] = 0
                self.diag['dono'] = bool(dono)
                if dono and not self.rodando:
                    self.rodando = True
                    self.cfg = self._cfg_load()
                    self.ult_parcial, self.desde_parcial = time.time(), 0
                    if not self.ws_thread or not self.ws_thread.is_alive():
                        self.ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
                        self.ws_thread.start()
                    print('[SalaDigitos] rodando (processo %s)' % self.id)
                elif not dono and self.rodando:
                    self.rodando = False
                    with self.lock:
                        self.st = {'fase': 'livre'}
                    if self.kv.get(K_LOCK) == self.id:
                        self.kv.delete(K_LOCK)
                    print('[SalaDigitos] parada (processo %s)' % self.id)
                if self.rodando:
                    self.tarefas()
            except Exception as e:
                import traceback
                self.diag['sup_erro'] = ('%s: %s' % (type(e).__name__, e))[:300]
                print('[SalaDigitos] supervisor: %s' % traceback.format_exc())
            time.sleep(5)

    def garante_supervisor(self, atraso=0):
        """Religa o supervisor se a thread morreu ou nunca rodou neste processo."""
        vivo = self.sup_thread is not None and self.sup_thread.is_alive() and self.diag.get('pid') == os.getpid()
        if not vivo:
            if self.diag['pid'] != os.getpid():
                self.id = uuid.uuid4().hex[:10]   # processo novo = dono novo
                self.rodando = False
            self.diag['pid'] = os.getpid()
            self.sup_thread = threading.Thread(target=self.supervisor, args=(atraso,), daemon=True)
            self.sup_thread.start()
            print('[SalaDigitos] supervisor (re)iniciado no processo %s' % os.getpid())
            if not getattr(self, 'ao_vivo_th', None) or not self.ao_vivo_th.is_alive() or getattr(self, 'ao_vivo_pid', None) != os.getpid():
                self.ao_vivo_pid = os.getpid()
                self.ao_vivo_th = threading.Thread(target=self._ao_vivo_loop, daemon=True)
                self.ao_vivo_th.start()
            return True
        return False

    # ---------- SALA-DIGITOS-V4.3: varios servidores (Render pago mantem 2 no ar) ----------
    def estado_vivo(self):
        st = self.st
        return {'fase': st.get('fase'), 'sym': st.get('sym'), 'lado': st.get('lado'), 'passo': st.get('passo', 0),
                'k': st.get('k'), 'pausa_ate': int(self.cool), 'dono': self.id, 'tp': time.time()}

    def _ao_vivo_loop(self):
        """Dono: publica o estado no Redis (0,5 s). Os outros: copiam o estado do dono para a memoria (1 s)."""
        self.remoto, ult, ult_pub = None, None, 0
        while True:
            try:
                if self.rodando:
                    ev = self.estado_vivo()
                    chave = json.dumps({k: ev[k] for k in ('fase', 'sym', 'lado', 'passo', 'k', 'pausa_ate')})
                    if chave != ult or time.time() - ult_pub > 3:
                        self.kv.set(K_LIVE, json.dumps(ev), ex=15)
                        ult, ult_pub = chave, time.time()
                    time.sleep(0.5)
                else:
                    raw = self.kv.get(K_LIVE)
                    try:
                        r = json.loads(raw) if raw else None
                    except Exception:
                        r = None
                    self.remoto = r if (r and time.time() - (r.get('tp') or 0) < 10) else None
                    time.sleep(1)
            except Exception as e:
                self.diag['vivo_erro'] = str(e)[:150]
                time.sleep(2)


def register_sala_digitos(app, get_redis=None, parar_antigo=None):
    from flask import request, jsonify
    kv = KV(get_redis)
    sala = Sala(kv, parar_antigo=parar_antigo)

    def ok_admin():
        s = os.environ.get('ADMIN_SENHA', '')
        return bool(s) and (request.headers.get('X-Admin-Token') or request.args.get('senha', '')) == s

    def negado():
        return jsonify({'ok': False, 'erro': 'sem acesso'}), 401

    def _hoje():
        d = datetime.now(BRT).strftime('%Y-%m-%d')
        raw = kv.get('sala_dig:dia:' + d)
        try:
            h = json.loads(raw) if raw else None
        except Exception:
            h = None
        h = h or {'win': 0, 'loss': 0, 'abort': 0, 'gale': [0, 0, 0, 0], 'un': 0.0, 'ciclos': []}
        t = h['win'] + h['loss']
        h['pct'] = round(h['win'] * 100.0 / t, 1) if t else 0.0
        return h

    def _resumo_dia(d):
        try:
            r = json.loads(kv.get('sala_dig:res:' + d) or 'null')
        except Exception:
            r = None
        if not r:
            try:
                h = json.loads(kv.get('sala_dig:dia:' + d) or 'null')
            except Exception:
                h = None
            if h:
                r = {'win': h.get('win', 0), 'loss': h.get('loss', 0), 'abort': h.get('abort', 0),
                     'gale': h.get('gale', [0, 0, 0, 0]), 'un': h.get('un', 0.0)}
        if r:
            t = r['win'] + r['loss']
            r['pct'] = round(r['win'] * 100.0 / t, 1) if t else 0.0
            r['dia'] = d
        return r

    @app.route('/api/admin/sala-digitos/historico', methods=['GET'])
    def _sd_historico():
        # SALA-HIST-V2: ?dia=AAAA-MM-DD (sinais de um dia) ou ?dias=N (resumo de N dias, ate 365)
        if not ok_admin():
            return negado()
        import re as _re2
        dia = (request.args.get('dia') or '').strip()
        if dia:
            if not _re2.match(r'^\d{4}-\d{2}-\d{2}$', dia):
                return jsonify({'ok': False, 'erro': 'data invalida'}), 400
            try:
                h = json.loads(kv.get('sala_dig:dia:' + dia) or 'null')
            except Exception:
                h = None
            h = h or {'win': 0, 'loss': 0, 'abort': 0, 'gale': [0, 0, 0, 0], 'un': 0.0, 'ciclos': []}
            t = h['win'] + h['loss']
            h['pct'] = round(h['win'] * 100.0 / t, 1) if t else 0.0
            return jsonify({'ok': True, 'dia': dia, 'hoje': h})
        try:
            n = max(1, min(365, int(request.args.get('dias', 7))))
        except Exception:
            n = 7
        hoje = datetime.now(BRT).date()
        dias, tot = [], {'win': 0, 'loss': 0, 'abort': 0, 'gale': [0, 0, 0, 0], 'un': 0.0}
        for i in range(n):
            r = _resumo_dia((hoje - timedelta(days=i)).strftime('%Y-%m-%d'))
            if not r:
                continue
            dias.append(r)
            for k in ('win', 'loss', 'abort'):
                tot[k] += r.get(k, 0)
            tot['gale'] = [a + b for a, b in zip(tot['gale'], (r.get('gale') or [0, 0, 0, 0]) + [0] * 4)]
            tot['un'] = round(tot['un'] + float(r.get('un') or 0), 4)
        t = tot['win'] + tot['loss']
        tot['pct'] = round(tot['win'] * 100.0 / t, 1) if t else 0.0
        tot['dias_com_sinal'] = len(tot) and len(dias)
        return jsonify({'ok': True, 'dias': dias, 'total': tot, 'n': n})

    @app.route('/api/admin/sala-digitos/status', methods=['GET'])
    def _sd_status():
        if not ok_admin():
            return negado()
        raw = kv.get(K_SNAP)
        try:
            snap = json.loads(raw) if raw else None
        except Exception:
            snap = None
        religou = sala.garante_supervisor()
        if not snap and sala.rodando:
            snap = sala.snap()
        r = kv._r()
        if r is None:
            modo = 'memoria (sem Redis)'
        else:
            try:
                r.ping()
                modo = 'redis ok'
            except Exception as e:
                modo = 'redis com erro: %s' % str(e)[:80]
        agora = int(time.time())
        diag = dict(sala.diag, rodando=sala.rodando, religou=religou, kv=modo, pid_agora=os.getpid(),
                    sup_vivo=bool(sala.sup_thread and sala.sup_thread.is_alive()),
                    ws_vivo=bool(sala.ws_thread and sala.ws_thread.is_alive()),
                    seg_desde_volta=(agora - sala.diag['sup_volta']) if sala.diag['sup_volta'] else None,
                    ws=dict(sala.ws), envio=dict(sala.envio), fila=len(sala.fila), fase=sala.st.get('fase'),
                    ponte=dict(getattr(sala, 'ponte', None).info) if getattr(sala, 'ponte', None) else None,
                    servidor=os.environ.get('RENDER_INSTANCE_ID') or __import__('socket').gethostname(), motor_outro=bool(getattr(sala, 'remoto', None)))
        return jsonify({'ok': True, 'ligado': kv.get(K_ON) == '1', 'cfg': sala._cfg_load(), 'hoje': _hoje(),
                        'snap': snap, 'diag': diag, 'nomes': NOMES, 'agora': agora})

    @app.route('/api/admin/sala-digitos/ligar', methods=['POST'])
    def _sd_ligar():
        if not ok_admin():
            return negado()
        ja = kv.get(K_ON) == '1'
        kv.set(K_ON, '1')
        sala.garante_supervisor(atraso=1)
        if parar_antigo:
            parar_antigo()
        if not ja:
            threading.Thread(target=enviar_canal, daemon=True, args=(
                '🟢 <b>SALA ALPHA DÍGITOS ABERTA</b>\n\n🎲 Sinais de Par / Ímpar\n🔁 Até %d gales\n\n'
                'Fique atento ao ⚠️ ATENÇÃO e entre só no ✅ ENTRADA CONFIRMADA.\n\n%s'
                % (sala._cfg_load()['gales'], RODAPE), 'aberta', True)).start()
        return jsonify({'ok': True, 'ligado': True})

    @app.route('/api/admin/sala-digitos/desligar', methods=['POST'])
    def _sd_desligar():
        if not ok_admin():
            return negado()
        kv.set(K_ON, '0')
        return jsonify({'ok': True, 'ligado': False})

    @app.route('/api/admin/sala-digitos/parcial', methods=['POST'])
    def _sd_parcial():
        if not ok_admin():
            return negado()
        if kv.get(K_ON) == '1':
            kv.set(K_CMD, 'parcial', ex=120)
            return jsonify({'ok': True, 'msg': 'parcial na fila (sai em até 5 s)'})
        ok, erro = enviar_canal(sala.texto_parcial(), None, True)
        return jsonify({'ok': ok, 'erro': erro})

    @app.route('/api/admin/sala-digitos/config', methods=['POST'])
    def _sd_config():
        if not ok_admin():
            return negado()
        c = valida_cfg(request.get_json(silent=True) or {}, sala._cfg_load())
        kv.set(K_CFG, json.dumps(c))
        return jsonify({'ok': True, 'cfg': c})

    # SALA-DIGITOS-V3.5: o motor so liga dentro do processo que atende o site (o gunicorn carrega o app
    # no processo mestre e depois copia; antes a sala rodava 2x, uma em cada processo)
    ponte = Ponte(kv)
    sala.ponte = ponte

    @app.before_request
    def _sd_garante():
        if sala.diag.get('pid') != os.getpid() or sala.sup_thread is None:
            sala.garante_supervisor(atraso=3)
        ponte.garante()

    import re as _re

    def _pessoa(v):
        v = (v or '').strip()
        return v if _re.match(r'^[A-Za-z0-9_-]{3,40}$', v) else ''

    @app.route('/api/sala-digitos/agora', methods=['GET'])
    def _sd_agora():
        # SALA-DIGITOS-V4: estado ao vivo da sala para o robo do Alpha Digitos seguir o mesmo sinal
        # V4.3: so memoria (nunca Redis no pedido); se o motor roda em OUTRO servidor, usa a copia do estado dele
        rem = getattr(sala, 'remoto', None)
        if sala.rodando:
            d, rodando, onde = sala.estado_vivo(), True, 'local'
        elif rem:
            d, rodando, onde = dict(rem), True, 'outro servidor'
        else:
            d, rodando, onde = sala.estado_vivo(), False, '-'
        d.pop('dono', None)
        d.update(ok=True, ligada=bool(sala.diag.get('ligada')), rodando=rodando, motor=onde, t=time.time(), mercados=list(sala.cfg.get('mercados') or []))
        return jsonify(d)

    # ---------- SALA-COMPARA-V1: entradas do robo (Alpha Digitos) x ticks da sala ----------
    def _num_ok(v, tipo=float, padrao=0):
        try:
            return tipo(v)
        except Exception:
            return padrao

    @app.route('/api/sala-digitos/robo', methods=['POST'])
    def _sd_robo():
        j = request.get_json(silent=True) or {}
        p = _pessoa(j.get('pessoa'))
        sym = str(j.get('sym') or '')
        if not p or sym not in NOMES:
            return jsonify({'ok': False, 'erro': 'dados invalidos'}), 400
        reg = {'pessoa': p, 'sym': sym, 'lado': 'PAR' if j.get('lado') in ('p', 'PAR') else 'IMPAR',
               'g': _num_ok(j.get('g'), int), 'stake': round(_num_ok(j.get('stake')), 2), 'won': bool(j.get('won')),
               'profit': round(_num_ok(j.get('profit')), 2), 'exit_ep': _num_ok(j.get('exit_ep'), int),
               'exit_d': j.get('exit_d') if isinstance(j.get('exit_d'), int) else None,
               'local_ep': _num_ok(j.get('local_ep'), int), 'local_d': j.get('local_d') if isinstance(j.get('local_d'), int) else None,
               'buy_ep': _num_ok(j.get('buy_ep'), int), 'conta': 'real' if j.get('real') else 'demo', 't': int(time.time())}
        dia = datetime.now(BRT).strftime('%Y-%m-%d')
        try:
            lst = json.loads(kv.get('sala_dig:robo:' + dia) or '[]')
        except Exception:
            lst = []
        lst.insert(0, reg)
        kv.set('sala_dig:robo:' + dia, json.dumps(lst[:800]), ex=86400 * 31)
        return jsonify({'ok': True})

    @app.route('/api/admin/sala-digitos/comparar', methods=['GET'])
    def _sd_comparar():
        if not ok_admin():
            return negado()
        import re as _re3
        dia = (request.args.get('dia') or datetime.now(BRT).strftime('%Y-%m-%d')).strip()
        if not _re3.match(r'^\d{4}-\d{2}-\d{2}$', dia):
            return jsonify({'ok': False, 'erro': 'data invalida'}), 400
        try:
            robo = json.loads(kv.get('sala_dig:robo:' + dia) or '[]')
        except Exception:
            robo = []
        try:
            ciclos = (json.loads(kv.get('sala_dig:dia:' + dia) or 'null') or {}).get('ciclos') or []
        except Exception:
            ciclos = []
        passos = []
        for cy in ciclos:
            for ps in cy.get('passos') or []:
                passos.append({'sym': cy.get('sym'), 'lado': cy.get('lado'), 'g': ps.get('g'), 'ep': ps.get('ep'), 'd': ps.get('d'),
                               'conf': cy.get('conf'), 'res': cy.get('res'), 'passo_final': cy.get('passo')})
        out, certos, comparaveis = [], 0, 0
        for r in robo:
            ep = r.get('exit_ep') or r.get('local_ep') or 0
            tk = 1 if str(r['sym']).startswith('1HZ') else 2
            mesmo = [s for s in passos if s['sym'] == r['sym'] and s['ep'] == ep]
            perto = sorted([s for s in passos if s['sym'] == r['sym'] and s['g'] == r['g'] and abs((s['ep'] or 0) - ep) <= 60],
                           key=lambda s: abs(s['ep'] - ep))
            sala = mesmo[0] if mesmo else (perto[0] if perto else None)
            if sala is None:
                veredito, dif = 'sem_sinal', None
            else:
                dif = int(round((ep - sala['ep']) / float(tk)))
                veredito = 'certo' if dif == 0 else ('atrasado' if dif > 0 else 'adiantado')
                comparaveis += 1
                certos += 1 if dif == 0 else 0
            out.append(dict(r, sala=sala, veredito=veredito, dif_ticks=dif))
        return jsonify({'ok': True, 'dia': dia, 'itens': out, 'certos': certos, 'comparaveis': comparaveis,
                        'total': len(out), 'lucro': round(sum(x.get('profit') or 0 for x in robo), 2)})

    @app.route('/api/sala-digitos/tg/codigo', methods=['POST'])
    def _sd_tg_codigo():
        p = _pessoa((request.get_json(silent=True) or {}).get('pessoa'))
        if not p:
            return jsonify({'ok': False, 'erro': 'conta invalida'}), 400
        ponte.ativo_ate = time.time() + 900      # V4.1: liga a leitura do bot por 15 min
        kv.set(K_TGATIVO, str(int(ponte.ativo_ate)), ex=900)   # V4.3: vale para o servidor que le o bot
        bu = _BOT.get('u')
        if not bu:
            return jsonify({'ok': False, 'erro': 'preparando o bot, tente de novo em alguns segundos'}), 503
        cod = uuid.uuid4().hex[:12]
        kv.set('sala_dig:tgcod:' + cod, p, ex=900)
        return jsonify({'ok': True, 'link': 'https://t.me/%s?start=%s' % (bu, cod), 'canal': CANAL_LINK})

    @app.route('/api/sala-digitos/tg/status', methods=['GET'])
    def _sd_tg_status():
        p = _pessoa(request.args.get('pessoa'))
        if not p:
            return jsonify({'ok': False, 'erro': 'conta invalida'}), 400
        forca = request.args.get('forca') == '1' and kv.get('sala_dig:tgf:' + p) != '1'
        if forca:
            kv.set('sala_dig:tgf:' + p, '1', ex=8)
        lig, mem = ponte.membro(p, forca=forca)
        return jsonify({'ok': True, 'conectado': lig, 'membro': mem, 'canal': CANAL_LINK})
    print('[SalaDigitos] SALA-DIGITOS-V4.4 registrada (processo %s)' % os.getpid())
    return sala
