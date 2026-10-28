# -*- coding: utf-8 -*-
"""NUVEM-DIGITOS-V1 — o robô Alpha Dígitos seguindo a Sala de Sinais NO SERVIDOR (funciona com o celular fechado).

Como funciona:
- A Sala de Sinais (sala_digitos.py) já lê os ticks no servidor. Este módulo "escuta" o motor da sala:
  quando a sala está em ENTRADA e falta 1 tick para o resultado (o mesmo momento em que o robô do navegador compra),
  compra o contrato de 1 tick (DIGITEVEN / DIGITODD) na conta de cada pessoa ligada na nuvem.
- O gale segue a sala (o mesmo tick decide), até o número de gales que a pessoa escolheu.
- Entrada, modo do gale (recuperação exata ou fator), limite de perda e meta são os da pessoa (vêm da tela do robô).
- Limite de perda é teto real: se a próxima entrada passaria do limite, não entra e desliga.
- Tudo fica no Redis (sobrevive ao deploy); contratos abertos no deploy são conferidos pelo servidor novo.

Rotas (a pessoa prova que é dona da conta mandando o token da Deriv do próprio navegador):
  POST /api/nuvem-digitos/ligar     {token, conta, cfg:{base, modo, fator, gales, sl, tp}}
  POST /api/nuvem-digitos/desligar  {token, conta}
  POST /api/nuvem-digitos/estado    {token, conta}
  GET  /api/admin/nuvem-digitos     (X-Admin-Token)
"""
import os, json, time, math, queue, hashlib, threading, atexit, traceback
import urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

VERSAO = 'NUVEM-DIGITOS-V1.2'  # V1.2: estado traz a situação da sala (ligada/viva) · V1.1  # V1.1: sinal do motor marcado no próprio tick (gunicorn preload) + cada contrato conta 1 vez só
API = 'https://api.derivws.com/trading/v1/options'
APP_ID = os.environ.get('DERIV_OAUTH_APP_ID', '34lv1PuWzjElEuwWcDLyr')
BRT = timezone(timedelta(hours=-3))
K_LISTA, K_MOTOR = 'nuvem_dig:lista', 'nuvem_dig:motor'
PARA = {'pausa': False}
CONFERE_ESPERA = 2      # segundos antes de perguntar à Deriv o resultado do contrato


def log(*a):
    print('[NuvemDig]', *a, flush=True)


def ceil2(v):
    return math.ceil(v * 100 - 1e-6) / 100


def r2(v):
    return round(float(v) + 1e-9, 2)


def stake_gale(modo, base, fator, nivel, perda, pm):
    """mesma conta do robô do navegador (bot-digitos.html stakeGale)"""
    if nivel <= 0:
        return r2(base)
    if modo == 'rec':
        return max(0.35, ceil2((perda + base * pm) / pm))
    return r2(base * math.pow(max(1.0, fator), nivel))


class KV(object):
    def __init__(self):
        self._m, self._r = {}, None
        url = os.environ.get('REDIS_URL', '').strip()
        if url:
            try:
                import redis as _redis
                self._r = _redis.from_url(url, decode_responses=True, socket_timeout=4)
                self._r.ping()
            except Exception as e:
                log('Redis indisponivel:', e)
                self._r = None

    def get(self, k):
        if self._r is not None:
            try:
                return self._r.get(k)
            except Exception:
                pass
        return self._m.get(k)

    def set(self, k, v, ex=None):
        self._m[k] = v
        if self._r is not None:
            try:
                self._r.set(k, v, ex=ex) if ex else self._r.set(k, v)
            except Exception:
                pass

    def setnx(self, k, v, ex):
        if self._r is not None:
            try:
                return bool(self._r.set(k, v, nx=True, ex=ex))
            except Exception:
                pass
        if k in self._m:
            return False
        self._m[k] = v
        return True

    def jget(self, k, d=None):
        try:
            v = self.get(k)
            return json.loads(v) if v else d
        except Exception:
            return d

    def jset(self, k, v, ex=None):
        self.set(k, json.dumps(v, ensure_ascii=False), ex)


def contas_do_token(tok):
    rq = urllib.request.Request(API + '/accounts', headers={'Authorization': 'Bearer ' + tok, 'Deriv-App-ID': APP_ID, 'User-Agent': 'AlphaDolar-Nuvem'})
    try:
        with urllib.request.urlopen(rq, timeout=12) as r:
            return json.loads(r.read().decode() or '{}').get('data') or []
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PermissionError('TOKEN')
        raise


class Conexao(object):
    """WebSocket com OTP da conta (demo ou real), sempre aberto para comprar rápido"""

    def __init__(self, tok, conta):
        self.tok, self.conta, self.ws, self.n, self.ult, self.symkey = tok, conta, None, 1, 0, 'underlying_symbol'

    def abre(self):
        import websocket
        self.fecha()
        rq = urllib.request.Request(API + '/accounts/%s/otp' % self.conta, data=b'', method='POST',
                                    headers={'Authorization': 'Bearer ' + self.tok, 'Deriv-App-ID': APP_ID, 'User-Agent': 'AlphaDolar-Nuvem'})
        try:
            with urllib.request.urlopen(rq, timeout=12) as r:
                url = (json.loads(r.read().decode() or '{}').get('data') or {}).get('url')
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise PermissionError('TOKEN')
            raise
        if not url:
            raise RuntimeError('OTP sem url')
        self.ws = websocket.create_connection(url, timeout=15)
        self.ult = time.time()

    def fecha(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        self.ws = None

    def req(self, obj, to=10):
        for tent in range(2):
            try:
                if self.ws is None:
                    self.abre()
                rid = self.n
                self.n += 1
                o = dict(obj)
                o['req_id'] = rid
                self.ws.settimeout(to)
                self.ws.send(json.dumps(o))
                fim = time.time() + to
                while time.time() < fim:
                    m = json.loads(self.ws.recv())
                    if m.get('req_id') == rid:
                        self.ult = time.time()
                        return m
                raise RuntimeError('tempo esgotado')
            except PermissionError:
                raise
            except Exception:
                self.fecha()
                if tent:
                    raise
        raise RuntimeError('sem resposta')


class Pessoa(object):
    """uma conta ligada na nuvem: fila de compras + conferência dos contratos"""

    def __init__(self, nv, conta):
        self.nv, self.conta, self.q = nv, conta, queue.Queue()
        self.c = None
        self.vivo = True
        self.th = threading.Thread(target=self.laco, daemon=True)
        self.th.start()

    def cfg(self):
        return self.nv.cfg(self.conta)

    def salva(self, u):
        self.nv.salva(self.conta, u)

    def para(self, u, motivo):
        self.nv.para(self.conta, motivo)

    def laco(self):
        while self.vivo:
            try:
                job = self.q.get(timeout=0.5)
            except queue.Empty:
                job = None
            try:
                u = self.cfg()
                if not u:
                    continue
                u['ligado'] = self.nv.ligado(self.conta)
                if self.c is None or self.c.tok != u.get('tok'):
                    if self.c:
                        self.c.fecha()
                    self.c = Conexao(u.get('tok', ''), self.conta)
                if job:
                    self.compra(u, job)
                else:
                    self.confere(u)
                    if u.get('ligado') and time.time() - self.c.ult > 20:
                        self.c.req({'ping': 1}, 8)
            except PermissionError:
                if self.nv.ligado(self.conta):
                    self.nv.para(self.conta, 'SUA SESSÃO NA DERIV EXPIROU: abra o Alpha Dígitos e ligue a nuvem de novo')
            except Exception as e:
                log('pessoa', self.conta[-3:], e)
                time.sleep(1)

    def compra(self, u, job):
        if not self.nv.ligado(self.conta) or PARA['pausa']:
            return
        if time.time() - job['t'] > (0.8 if str(job['sym']).startswith('1HZ') else 1.6):
            self.nv.op_log(self.conta, {'t': int(time.time()), 'aviso': 'entrada %s perdida: o servidor atrasou' % ('SG' if not job['g'] else 'G%d' % job['g'])})
            return
        par = {'contract_type': 'DIGITEVEN' if job['lado'] == 'PAR' else 'DIGITODD', 'amount': job['stake'], 'basis': 'stake',
               'currency': u.get('moeda') or 'USD', 'duration': 1, 'duration_unit': 't'}
        par[self.c.symkey] = job['sym']
        r = self.c.req({'buy': 1, 'price': job['stake'], 'parameters': par}, 8)
        msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error') and ('symbol' in msg.lower() or 'Properties not allowed' in msg):
            par.pop(self.c.symkey, None)
            self.c.symkey = 'symbol' if self.c.symkey == 'underlying_symbol' else 'underlying_symbol'
            par[self.c.symkey] = job['sym']
            r = self.c.req({'buy': 1, 'price': job['stake'], 'parameters': par}, 8)
        if r.get('error'):
            self.nv.op_log(self.conta, {'t': int(time.time()), 'aviso': 'Deriv recusou a entrada: ' + msg[:120]})
            with self.nv.trava(self.conta):
                u = self.cfg()
                u['erros'] = u.get('erros', 0) + 1
                self.salva(u)
            if u['erros'] >= 3:
                self.nv.para(self.conta, 'PARADO APÓS 3 ERROS SEGUIDOS NA DERIV (%s)' % msg[:80])
            return
        b = r.get('buy') or {}
        with self.nv.trava(self.conta):
            u = self.cfg()
            u['erros'] = 0
            try:
                pm = float(b.get('payout')) / float(b.get('buy_price')) - 1
                if 0.5 < pm < 1.2:
                    u['pm'] = pm
            except Exception:
                pass
            u.setdefault('abertos', []).append({'cid': b.get('contract_id'), 'stake': job['stake'], 'g': job['g'], 'k': job['k'], 'sym': job['sym'],
                                                'lado': job['lado'], 't': int(time.time())})
            self.salva(u)

    def confere(self, u):
        ab = u.get('abertos') or []
        if not ab:
            return
        fechados = []
        for p in list(ab):
            if time.time() - p['t'] < CONFERE_ESPERA:
                continue
            r = self.c.req({'proposal_open_contract': 1, 'contract_id': p['cid']}, 8)
            q = r.get('proposal_open_contract') or {}
            if r.get('error'):
                if time.time() - p['t'] > 600:
                    fechados.append((p, None, None))
                continue
            if q.get('is_sold') or q.get('status') in ('won', 'lost', 'sold'):
                fechados.append((p, r2(float(q.get('profit') or 0)), str(q.get('exit_tick_display_value') or q.get('exit_tick') or '')[-1:] or None))
        if not fechados:
            return
        with self.nv.trava(self.conta):
            u2 = self.cfg()
            ids = {f[0]['cid'] for f in fechados}
            u2['abertos'] = [p for p in (u2.get('abertos') or []) if p['cid'] not in ids]
            s = u2.setdefault('sessao', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0})
            for p, pl, dg in fechados:
                if pl is None or not self.nv.kv.setnx('nuvem_dig:contou:%s' % p['cid'], '1', 86400 * 3):
                    continue
                s['pl'] = r2(s['pl'] + pl)
                s['n'] += 1
                s['w' if pl > 0 else 'l'] += 1
                self.nv.op_log(self.conta, {'t': int(time.time()), 'sym': p['sym'], 'lado': p['lado'], 'g': p['g'], 'stake': p['stake'], 'pl': pl, 'dig': dg})
            self.salva(u2)
        if self.nv.ligado(self.conta) and u2.get('tp') and s.get('pl', 0) >= u2['tp'] and not u2['abertos']:
            self.nv.para(self.conta, 'META ATINGIDA (+$%.2f)' % s['pl'])


class Nuvem(object):
    def __init__(self):
        self.kv = KV()
        self.pessoas = {}
        self.ult_sinal = None
        self.ult_tick = 0
        self.lock = threading.Lock()
        self.locks = {}
        threading.Thread(target=self.vigia, daemon=True).start()

    def lista(self):
        return self.kv.jget(K_LISTA, []) or []

    def trava(self, conta):
        with self.lock:
            return self.locks.setdefault(conta, threading.RLock())

    def cfg(self, conta):
        return self.kv.jget('nuvem_dig:u:' + conta) or {}

    def salva(self, conta, u):
        u = {k: v for k, v in u.items() if k != 'ligado'}
        self.kv.jset('nuvem_dig:u:' + conta, u)

    def ligado(self, conta):
        return self.kv.get('nuvem_dig:on:' + conta) == '1'

    def liga(self, conta, on):
        self.kv.set('nuvem_dig:on:' + conta, '1' if on else '0')

    def para(self, conta, motivo):
        self.liga(conta, False)
        with self.trava(conta):
            u = self.cfg(conta)
            u['parado'] = motivo
            u['t_parou'] = int(time.time())
            self.salva(conta, u)
        self.op_log(conta, {'t': int(time.time()), 'aviso': motivo})
        log('%s…%s parado: %s' % (conta[:3], conta[-3:], motivo))

    def op_log(self, conta, reg):
        k = 'nuvem_dig:ops:' + conta
        L = self.kv.jget(k, []) or []
        L.insert(0, reg)
        self.kv.jset(k, L[:300], ex=86400 * 30)

    def vigia(self):
        """só no servidor que recebe os ticks da sala: mantém um trabalhador por conta ligada"""
        while True:
            try:
                if time.time() - self.ult_tick < 30:
                    self.kv.set(K_MOTOR, str(int(time.time())), ex=60)
                    for conta in self.lista():
                        u = self.cfg(conta)
                        if (self.ligado(conta) or u.get('abertos')) and conta not in self.pessoas:
                            self.pessoas[conta] = Pessoa(self, conta)
            except Exception as e:
                log('vigia', e)
            time.sleep(5)

    # chamado depois de cada tick que a sala processou
    def no_tick(self, sala, sym, ep):
        agora = time.time()
        if agora - self.ult_tick > 5:
            self.kv.set(K_MOTOR, str(int(agora)), ex=60)   # V1.1: marca daqui (a thread vigia pode estar em outro processo)
        self.ult_tick = agora
        st = sala.st
        if st.get('fase') != 'entrada' or st.get('falta') != 1 or st.get('sym') != sym:
            return
        chave = (st.get('k'), st.get('passo', 0))
        if chave == self.ult_sinal:
            return
        self.ult_sinal = chave
        g, lado, k = int(st.get('passo', 0)), st.get('lado'), st.get('k')
        for conta in self.lista():
            try:
                self.entra(conta, sym, lado, g, k)
            except Exception as e:
                log('entra', conta[-3:], e)

    def entra(self, conta, sym, lado, g, k):
        if not self.ligado(conta):
            return
        with self.trava(conta):
            self._entra(conta, sym, lado, g, k)

    def _entra(self, conta, sym, lado, g, k):
        u = self.cfg(conta)
        ciclo = u.get('ciclo') or {}
        if g == 0:
            ciclo = {'k': k, 'perda': 0.0, 'g': 0}
        elif ciclo.get('k') != k or ciclo.get('g') != g - 1:
            return                         # ligou no meio do ciclo: não entra direto num gale
        if g > int(u.get('gales', 3)):
            return
        perda = r2(float(ciclo.get('perda', 0)) + float(ciclo.get('ult', 0))) if g > 0 else 0.0
        stake = stake_gale(u.get('modo', 'rec'), float(u.get('base', 0.35)), float(u.get('fator', 2.1)), g, perda, float(u.get('pm', 0.95)))
        s = u.get('sessao') or {'pl': 0.0}
        aberto = sum(float(p['stake']) for p in (u.get('abertos') or []))
        P = float(s.get('pl', 0)) - aberto
        sl, tp = float(u.get('sl') or 0), float(u.get('tp') or 0)
        if tp > 0 and P >= tp:
            self.para(conta, 'META ATINGIDA (+$%.2f)' % P)
            return
        if sl > 0 and (-P + stake) > sl + 1e-9:
            self.para(conta, 'PARADO: a próxima entrada ($%.2f) passaria do seu limite de perda ($%.2f)' % (stake, sl))
            return
        ciclo.update({'k': k, 'g': g, 'ult': stake, 'perda': perda})
        u['ciclo'] = ciclo
        self.salva(conta, u)
        p = self.pessoas.get(conta)
        if p is None:
            p = self.pessoas[conta] = Pessoa(self, conta)
        p.q.put({'sym': sym, 'lado': lado, 'g': g, 'k': k, 'stake': stake, 't': time.time()})


def register_nuvem_digitos(app):
    from flask import request, jsonify
    nv = Nuvem()
    try:
        import sala_digitos as _sd
        orig = _sd.Sala.on_tick
        if not getattr(orig, '_nuvem', False):
            def on_tick(self, sym, d, ep, _o=orig):
                r = _o(self, sym, d, ep)
                try:
                    nv.no_tick(self, sym, ep)
                except Exception as e:
                    log('no_tick', e)
                return r
            on_tick._nuvem = True
            _sd.Sala.on_tick = on_tick
            log('%s ligada no motor da Sala de Sinais' % VERSAO)
    except Exception as e:
        log('NAO achei a Sala de Sinais:', e)

    atexit.register(lambda: PARA.update(pausa=True))
    cache = {}

    def dono(d):
        tok, conta = str(d.get('token') or '').strip(), str(d.get('conta') or '').strip()
        if not tok or not conta:
            return None, 'faltou token ou conta'
        h = hashlib.sha256((tok + '|' + conta).encode()).hexdigest()
        c = cache.get(h)
        if c and time.time() - c[0] < 600:
            return c[1], None
        try:
            ac = [a for a in contas_do_token(tok) if str(a.get('account_id')) == conta]
        except PermissionError:
            return None, 'sua sessão na Deriv expirou: entre de novo'
        except Exception as e:
            return None, 'Deriv não respondeu (%s)' % str(e)[:60]
        if not ac:
            return None, 'essa conta não é deste login'
        info = {'tipo': ac[0].get('account_type'), 'moeda': ac[0].get('currency') or 'USD', 'saldo': ac[0].get('balance')}
        cache[h] = (time.time(), info)
        return info, None

    def num(v, d, lo, hi):
        try:
            v = float(str(v).replace(',', '.'))
            return max(lo, min(hi, v))
        except Exception:
            return d

    def publico(u):
        return {k: v for k, v in u.items() if k not in ('tok',)}

    @app.route('/api/nuvem-digitos/ligar', methods=['POST'])
    def _nd_ligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        cf = d.get('cfg') or {}
        u = nv.cfg(conta)
        if u.get('abertos'):
            return jsonify({'ok': False, 'erro': 'ainda tem contrato aberto; espere alguns segundos'}), 400
        u.update({'conta': conta, 'tok': str(d['token']).strip(), 'tipo': info['tipo'], 'moeda': info['moeda'], 'parado': '',
                  't_lig': int(time.time()), 'base': num(cf.get('base'), 0.35, 0.35, 500), 'modo': 'fator' if cf.get('modo') == 'fator' else 'rec',
                  'fator': num(cf.get('fator'), 2.1, 1.0, 5.0), 'gales': int(num(cf.get('gales'), 3, 0, 3)), 'sl': num(cf.get('sl'), 15, 0, 100000),
                  'tp': num(cf.get('tp'), 5, 0, 100000), 'sessao': {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'ini': int(time.time())}, 'ciclo': {}, 'erros': 0,
                  'abertos': [], 'pm': u.get('pm', 0.95)})
        nv.salva(conta, u)
        nv.liga(conta, True)
        L = nv.lista()
        if conta not in L:
            L.append(conta)
            nv.kv.jset(K_LISTA, L)
        nv.op_log(conta, {'t': int(time.time()), 'aviso': 'NUVEM LIGADA na conta %s · entrada $%.2f · %d gale(s) · limite $%.2f · meta $%.2f' % (
            info['tipo'].upper(), u['base'], u['gales'], u['sl'], u['tp'])})
        return jsonify({'ok': True, 'cfg': publico(u)})

    @app.route('/api/nuvem-digitos/desligar', methods=['POST'])
    def _nd_desligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        nv.para(conta, 'desligado por você')
        return jsonify({'ok': True})

    @app.route('/api/nuvem-digitos/estado', methods=['POST'])
    def _nd_estado():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        if u:
            u['ligado'] = nv.ligado(conta)
        motor = float(nv.kv.get(K_MOTOR) or 0)
        on = nv.kv.get('sala_dig:on')
        try:
            vivo = time.time() - float((json.loads(nv.kv.get('sala_dig:live') or '{}') or {}).get('tp') or 0) < 20
        except Exception:
            vivo = False
        sala = {'ligada': (on == '1') if on is not None else None, 'vivo': vivo or time.time() - motor < 60}
        return jsonify({'ok': True, 'versao': VERSAO, 'sala': sala, 'cfg': publico(u) if u else None, 'ops': (nv.kv.jget('nuvem_dig:ops:' + conta, []) or [])[:40],
                        'motor': time.time() - motor < 60, 'saldo': info.get('saldo')})

    @app.route('/api/admin/nuvem-digitos', methods=['GET'])
    def _nd_admin():
        s = os.environ.get('ADMIN_SENHA', '')
        if not s or request.headers.get('X-Admin-Token') != s:
            return jsonify({'ok': False}), 403
        out = []
        for conta in nv.lista():
            u = nv.cfg(conta)
            out.append({'conta': conta[:3] + '…' + conta[-3:], 'tipo': u.get('tipo'), 'ligado': nv.ligado(conta), 'parado': u.get('parado'),
                        'sessao': u.get('sessao'), 'base': u.get('base'), 'gales': u.get('gales')})
        return jsonify({'ok': True, 'motor': time.time() - float(nv.kv.get(K_MOTOR) or 0) < 60, 'pessoas': out})

    log('%s registrada' % VERSAO)
    return nv
