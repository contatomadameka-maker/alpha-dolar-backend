# -*- coding: utf-8 -*-
"""SALA-DIGITOS-V1 - Sala de sinais Alpha Digitos (par/impar) no canal do Telegram.

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
WS_URL = os.environ.get('SALA_WS_URL', 'wss://ws.binaryws.com/websockets/v3?app_id=1089')

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
            return self._g() if self._g else None
        except Exception:
            return None

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


def enviar_canal(texto):
    """Envia no mesmo bot/canal do robo antigo. Devolve (ok, erro)."""
    try:
        import backend.telegram_signals as ts
        tok = getattr(ts, 'TELEGRAM_TOKEN', '') or os.environ.get('TELEGRAM_TOKEN', '')
        chat = getattr(ts, 'CHANNEL_ID', '')
    except Exception as e:
        return False, 'telegram_signals: %s' % e
    if not tok or not chat:
        return False, 'TELEGRAM_TOKEN ou CHANNEL_ID vazio no servidor'
    body = json.dumps({'chat_id': chat, 'text': texto, 'parse_mode': 'HTML',
                       'disable_web_page_preview': True}).encode('utf-8')
    req = urllib.request.Request('https://api.telegram.org/bot%s/sendMessage' % tok, data=body,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            j = json.loads(r.read().decode('utf-8'))
        return bool(j.get('ok')), (j.get('description') or '')
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode('utf-8')).get('description', str(e))
        except Exception:
            return False, str(e)
    except Exception as e:
        return False, str(e)


class Sala(object):
    def __init__(self, kv, enviar=enviar_canal, parar_antigo=None, fila_sincrona=False):
        self.kv = kv
        self._enviar = enviar
        self.parar_antigo = parar_antigo
        self.fila_sincrona = fila_sincrona   # testes: envia na hora
        self.id = uuid.uuid4().hex[:10]
        self.lock = threading.RLock()
        self.cfg = self._cfg_load()
        self.dig = {}
        self.st = {'fase': 'livre'}
        self.cool = 0
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
            self.kv.set('sala_dig:dia:' + self.dia, json.dumps(self.hoje), ex=86400 * 8)

    # ---------- envio em fila (nao trava a leitura de ticks) ----------
    def manda(self, texto):
        if self.fila_sincrona:
            self._manda_ja(texto)
            return
        self.fila.append(texto)
        if not self.fila_thread or not self.fila_thread.is_alive():
            self.fila_thread = threading.Thread(target=self._fila_loop, daemon=True)
            self.fila_thread.start()
        self.fila_ev.set()

    def _manda_ja(self, texto):
        ok, erro = self._enviar(texto)
        if ok:
            self.envio['ok'] += 1
            self.envio['ultimo'] = texto.split('\n')[0][:80]
        else:
            self.envio['falhas'] += 1
            self.envio['ultimo_erro'] = (erro or '')[:200]
            print('[SalaDigitos] Telegram recusou: %s' % erro)

    def _fila_loop(self):
        while True:
            self.fila_ev.wait(30)
            self.fila_ev.clear()
            while self.fila:
                self._manda_ja(self.fila.popleft())
                time.sleep(0.4)

    # ---------- textos ----------
    @staticmethod
    def _lado(l):
        return '🔵 PAR' if l == 'PAR' else '🟣 ÍMPAR'

    def _pct(self, h):
        t = h['win'] + h['loss']
        return round(h['win'] * 100.0 / t, 1) if t else 0.0

    def _placar_curto(self, h):
        return '✅ %d   ❌ %d   🎯 %s%%' % (h['win'], h['loss'], _num(self._pct(h)))

    def texto_parcial(self, ep=None):
        ep = ep or time.time()
        h = self._dia(ep)
        g = h['gale']
        dt = datetime.fromtimestamp(ep, BRT)
        return ('📊 <b>PARCIAL — ALPHA DÍGITOS</b>\n📅 %s • até %s\n\n'
                '✅ Win: <b>%d</b>\n❌ Loss: <b>%d</b>\n🎯 Assertividade: <b>%s%%</b>\n\n'
                '🥇 SG: %d\n1️⃣ G1: %d\n2️⃣ G2: %d\n3️⃣ G3: %d\n\n%s') % (
            dt.strftime('%d/%m'), dt.strftime('%H:%M'), h['win'], h['loss'], _num(self._pct(h)),
            g[0], g[1], g[2], g[3], RODAPE)

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
                    lado = 'PAR' if d % 2 == 1 else 'IMPAR'   # contra a sequencia
                    self.st = {'fase': 'atencao', 'sym': sym, 'lado': lado, 'seq': s, 'ini': ep,
                               'hist': list(q)[-s:]}
                    self.manda('⚠️ <b>ATENÇÃO — ALPHA DÍGITOS</b>\n\n📊 <b>%s</b>\n🎲 Par / Ímpar\n'
                               '🔎 Padrão em formação: %s\n\n⏳ Abra o mercado e aguarde a confirmação…'
                               % (NOMES[sym], ' '.join(str(x) for x in self.st['hist'])))
            elif f == 'atencao' and sym == st['sym']:
                seq_impar = st['lado'] == 'PAR'
                if (d % 2 == 1) == seq_impar:
                    st['seq'] += 1
                    st['hist'].append(d)
                    if st['seq'] >= c['confirma']:
                        st.update(fase='entrada', passo=0, quando=ep + c['espera'], res=[])
                        self.manda('✅ <b>ENTRADA CONFIRMADA</b>\n\n📊 <b>%s</b>\n🎯 Entrada: <b>%s</b>\n'
                                   '⏱ Duração: 1 tick\n🔁 Até %d gale%s (x%s)\n🕒 %s\n\n🌐 alphadolar.online'
                                   % (NOMES[sym], self._lado(st['lado']), c['gales'],
                                      '' if c['gales'] == 1 else 's', _num(c['mult']), _hora(ep)))
                else:
                    self._abortar(ep, 'O padrão se desfez antes da confirmação')
            elif f == 'entrada' and sym == st['sym'] and ep >= st['quando']:
                st['res'].append(d)
                ganhou = (d % 2 == 0) == (st['lado'] == 'PAR')
                if ganhou:
                    self._fim(ep, True)
                elif st['passo'] >= c['gales']:
                    self._fim(ep, False)
                else:
                    st['passo'] += 1
                    st['quando'] = ep + c['espera']
                    self.manda('🔁 <b>GALE %d</b> — %s • entrada x%s'
                               % (st['passo'], self._lado(st['lado']), _num(c['mult'] ** st['passo'])))

    def _abortar(self, ep, motivo):
        h = self._dia(ep)
        h['abort'] += 1
        self._salva_dia()
        sym = self.st.get('sym')
        self.manda('🚫 <b>ENTRADA ABORTADA</b>\n\n📊 %s\n%s. Aguarde o próximo sinal.'
                   % (NOMES.get(sym, sym or ''), motivo))
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
                               'passo': p, 'dig': st['res'], 'un': round(un, 3)})
        h['ciclos'] = h['ciclos'][:30]
        self._salva_dia()
        dig = ' '.join(str(x) for x in st['res'])
        if ganhou:
            self.manda('💰 <b>GAIN %s</b> ✅\n\n📊 %s • %s\n🎲 Dígitos: %s\n\n%s'
                       % ('SG' if p == 0 else 'G%d' % p, NOMES[st['sym']], self._lado(st['lado']), dig,
                          self._placar_curto(h)))
        else:
            self.manda('❌ <b>LOSS</b>\n\n📊 %s • %s\n🎲 Dígitos: %s\n\nFaz parte. Respeite seu stop e sua gestão.\n\n%s'
                       % (NOMES[st['sym']], self._lado(st['lado']), dig, self._placar_curto(h)))
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
                self.manda(self.texto_parcial(agora))
                self.ult_parcial, self.desde_parcial = agora, 0
            elif agora - self.ult_parcial >= self.cfg['parcial'] * 60:
                if self.desde_parcial > 0:
                    self.manda(self.texto_parcial(agora))
                self.ult_parcial, self.desde_parcial = agora, 0
            snap = {'fase': self.st.get('fase'), 'sym': self.st.get('sym'), 'lado': self.st.get('lado'),
                    'passo': self.st.get('passo', 0), 'seq': self.st.get('seq', 0),
                    'pausa_ate': int(self.cool), 'ws': self.ws, 'envio': self.envio, 'dono': self.id,
                    't': int(agora)}
        self.kv.set(K_SNAP, json.dumps(snap), ex=60)

    # ---------- leitura de ticks ----------
    def _ws_loop(self):
        try:
            import websocket
        except Exception as e:
            self.ws['erro'] = 'biblioteca websocket ausente: %s' % e
            return
        espera = 2
        while self.rodando:
            ws = None
            try:
                ws = websocket.create_connection(WS_URL, timeout=15)
                for s in SIMBOLOS:
                    ws.send(json.dumps({'ticks': s, 'subscribe': 1}))
                ws.settimeout(10)
                self.ws.update(conectado=True, erro='')
                espera, ult_ping = 2, time.time()
                while self.rodando:
                    if time.time() - ult_ping > 25:
                        ws.send('{"ping": 1}')
                        ult_ping = time.time()
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        raise Exception('conexão fechada pela Deriv')
                    m = json.loads(raw)
                    if m.get('error'):
                        self.ws['erro'] = (m['error'].get('message') or '')[:200]
                        continue
                    t = m.get('tick')
                    if not t or t.get('quote') is None:
                        continue
                    dec = int(t.get('pip_size') or 2)
                    d = int(('%.*f' % (dec, float(t['quote'])))[-1])
                    self.on_tick(t.get('symbol'), d, int(t.get('epoch') or time.time()))
                    self.ws['ultimo_tick'] = int(time.time())
                    self.ws['ticks'] += 1
            except Exception as e:
                self.ws.update(conectado=False, erro=str(e)[:200])
                print('[SalaDigitos] WS: %s' % e)
            finally:
                try:
                    if ws:
                        ws.close()
                except Exception:
                    pass
            self.ws['conectado'] = False
            if self.rodando:
                time.sleep(espera)
                espera = min(60, espera * 2)

    def supervisor(self):
        time.sleep(8)
        while True:
            try:
                on = self.kv.get(K_ON) == '1'
                if on and self.parar_antigo:
                    self.parar_antigo()
                dono = on and self.kv.trava(K_LOCK, self.id, 30)
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
                print('[SalaDigitos] supervisor: %s' % e)
            time.sleep(5)


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

    @app.route('/api/admin/sala-digitos/status', methods=['GET'])
    def _sd_status():
        if not ok_admin():
            return negado()
        raw = kv.get(K_SNAP)
        try:
            snap = json.loads(raw) if raw else None
        except Exception:
            snap = None
        return jsonify({'ok': True, 'ligado': kv.get(K_ON) == '1', 'cfg': sala._cfg_load(), 'hoje': _hoje(),
                        'snap': snap, 'nomes': NOMES, 'agora': int(time.time())})

    @app.route('/api/admin/sala-digitos/ligar', methods=['POST'])
    def _sd_ligar():
        if not ok_admin():
            return negado()
        ja = kv.get(K_ON) == '1'
        kv.set(K_ON, '1')
        if parar_antigo:
            parar_antigo()
        if not ja:
            threading.Thread(target=enviar_canal, daemon=True, args=(
                '🟢 <b>SALA ALPHA DÍGITOS ABERTA</b>\n\n🎲 Sinais de Par / Ímpar\n🔁 Até %d gales\n\n'
                'Fique atento ao ⚠️ ATENÇÃO e entre só no ✅ ENTRADA CONFIRMADA.\n\n%s'
                % (sala._cfg_load()['gales'], RODAPE),)).start()
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
        ok, erro = enviar_canal(sala.texto_parcial())
        return jsonify({'ok': ok, 'erro': erro})

    @app.route('/api/admin/sala-digitos/config', methods=['POST'])
    def _sd_config():
        if not ok_admin():
            return negado()
        c = valida_cfg(request.get_json(silent=True) or {}, sala._cfg_load())
        kv.set(K_CFG, json.dumps(c))
        return jsonify({'ok': True, 'cfg': c})

    threading.Thread(target=sala.supervisor, daemon=True).start()
    print('[SalaDigitos] SALA-DIGITOS-V1 registrada')
    return sala
