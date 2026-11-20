# -*- coding: utf-8 -*-
"""NUVEM-AUTO-V1 — os robôs de DÍGITOS da Alpha Automação rodando NO SERVIDOR (funciona com o celular fechado).

Mesmas regras do motor da página (bot-automacao.html + AUTO-EXTRA-V1 + AUTO-V3):
- Sinal: domínio nos últimos 30 dígitos (Par/Ímpar ou 0–4/5–9) acima do mínimo do perfil; "segue" entra no lado que domina,
  "contra" no outro. "Acima de 3" (dig_o3) entra sempre em DIGITOVER 3 (só o Confirmar filtra).
- Confirmar antes de entrar (N seguidos do outro lado, só ticks depois do último contrato da vaga).
- Entrada fixa ou % da banca (com teto), recuperação exata com o pagamento real, ciclos de gale (pausa e espera o sinal de
  novo; perdeu todos: volta à entrada ou para a vaga), pausa depois da perda, meta e stop por vaga, rodadas, trava de lucro,
  limite global da conta e "uma operação por vez".
Contratos de 1 tick. Os robôs Rise/Fall continuam no servidor deles (auto-N), como sempre.

Rotas: POST /api/nuvem-auto/ligar|desligar|estado|vaga {token, conta[, cfg | i, acao]} · GET /api/admin/nuvem-auto (X-Admin-Token)
"""
import os, json, time, math, uuid, threading, atexit, hashlib
from collections import deque

try:
    from nuvem_digitos import KV, Conexao, contas_do_token, digito_saida, log as _log
except Exception:   # pragma: no cover
    from backend.nuvem_digitos import KV, Conexao, contas_do_token, digito_saida, log as _log   # noqa

VERSAO = 'NUVEM-AUTO-V1'
MERC = ['R_10', 'R_25', 'R_50', 'R_75', 'R_100', '1HZ10V', '1HZ25V', '1HZ50V', '1HZ75V', '1HZ100V',
        'JD10', 'JD25', 'JD50', 'JD75', 'JD100', 'RDBULL', 'RDBEAR', 'stpRNG', 'stpRNG2', 'stpRNG3', 'stpRNG4', 'stpRNG5']
SO_DEMO = ('stpRNG',)
WS_URLS = [u for u in [os.environ.get('SALA_WS_URL', '').strip(),
                       'wss://api.derivws.com/trading/v1/options/ws/public',
                       'wss://ws.derivws.com/websockets/v3?app_id=1089'] if u]
P = 'nuvem_aut:'
K_LISTA, K_LIDER, K_MOTOR = P + 'lista', P + 'lider', P + 'motor'
TICKS = {s: deque(maxlen=120) for s in MERC}   # (epoch, dígito)
LTK = {}
EST = {'pausa': False, 'ws': '', 'ticks': 0}
JAN = 30
PERF = {'preciso': (20, 0), 'equilibrado': (18, 2), 'rapido': (17, 4)}
CT = {'EVEN': ('DIGITEVEN', None, 'Par'), 'ODD': ('DIGITODD', None, 'Ímpar'), 'OVER': ('DIGITOVER', '4', 'Acima de 4'),
      'UNDER': ('DIGITUNDER', '5', 'Abaixo de 5'), 'OVER3': ('DIGITOVER', '3', 'Acima de 3')}
PAY0 = {'EVEN': .95, 'ODD': .95, 'OVER': .95, 'UNDER': .95, 'OVER3': .557}
OUTRO = {'EVEN': lambda d: d % 2 == 1, 'ODD': lambda d: d % 2 == 0, 'OVER': lambda d: d <= 4, 'UNDER': lambda d: d >= 5, 'OVER3': lambda d: d <= 3}
NOME_OUTRO = {'EVEN': 'ímpares', 'ODD': 'pares', 'OVER': 'de 0 a 4', 'UNDER': 'de 5 a 9', 'OVER3': 'de 0 a 3'}
VAGAS_PLANO = {0: 1, 1: 2, 2: 5, 3: 15}   # conta real: Free 1 · Sinais 2 · Pro 5 · Elite 15


def log(*a):
    _log('[Auto]', *a)


def r2(v):
    return round(float(v) + 1e-9, 2)


def ceil2(v):
    return math.ceil(float(v) * 100 - 1e-6) / 100.0


def _extrato(conta, tipo, cid, sym, stake, pl, tp):
    try:
        from nuvem_clique import _extrato as _ex
    except Exception:
        try:
            from backend.nuvem_clique import _extrato as _ex   # noqa
        except Exception:
            return
    try:
        _ex(conta, tipo, cid, sym, stake, pl, 'automacao', 'Alpha Automação', tp)
    except Exception as e:
        log('extrato', str(e)[:120])


def _nivel_plano(tok):
    try:
        from nuvem_digitos import _nivel_plano as f
    except Exception:
        try:
            from backend.nuvem_digitos import _nivel_plano as f   # noqa
        except Exception:
            return None
    return f(tok)


def sinal(v, sym):
    """lado da entrada agora (ou None) e o texto do que está esperando"""
    L = list(TICKS.get(sym) or [])
    if v['cat'] == 'o3':
        return 'OVER3', ''
    if len(L) < JAN:
        return None, 'juntando ticks (%d/%d)' % (len(L), JAN)
    ds = [d for (e, d) in L[-JAN:]]
    s = sum(1 for d in ds if (d % 2 == 0 if v['cat'] == 'pi' else d >= 5))
    m = max(s, JAN - s)
    if m < v['n']:
        return None, 'esperando o sinal (%d de %d, precisa %d)' % (m, JAN, v['n'])
    c = 2 * s >= JAN
    l = c if v['mo'] == 'segue' else not c
    if v['cat'] == 'pi':
        return ('EVEN' if l else 'ODD'), ''
    return ('OVER' if l else 'UNDER'), ''


def confirma(v, sym, lado):
    n = int(v.get('xc') or 0)
    if not n:
        return True, ''
    ep0 = int(v.get('cfN') or 0)
    k = 0
    for (e, d) in reversed(list(TICKS.get(sym) or [])):
        if e <= ep0 or not OUTRO[lado](d):
            break
        k += 1
    if k >= n:
        return True, ''
    return False, '🔎 Confirmando: esperando %d %s seguidos (%d/%d)' % (n, NOME_OUTRO[lado], k, n)


class NuvemAuto(object):
    def __init__(self):
        self.kv = KV()
        self.eu = '%d-%s' % (os.getpid(), uuid.uuid4().hex[:6])
        self.pid = None
        self.lider = False
        self.trab = {}
        self.lock = threading.Lock()

    def garante(self):
        if self.pid == os.getpid():
            return
        with self.lock:
            if self.pid == os.getpid():
                return
            self.pid = os.getpid()
            self.eu = '%d-%s' % (os.getpid(), uuid.uuid4().hex[:6])
            self.trab = {}
            threading.Thread(target=self.leitor, daemon=True).start()
            threading.Thread(target=self.vigia, daemon=True).start()
            log('threads no processo', self.pid)

    # ---------- armazenamento ----------
    def cfg(self, conta):
        return self.kv.jget(P + 'u:' + conta) or {}

    def salva(self, conta, u):
        self.kv.jset(P + 'u:' + conta, {k: v for k, v in u.items() if k != 'ligado'}, ex=86400 * 30)

    def ligado(self, conta):
        return self.kv.get(P + 'on:' + conta) == '1'

    def liga(self, conta, on):
        self.kv.set(P + 'on:' + conta, '1' if on else '0')

    def lista(self):
        return self.kv.jget(K_LISTA, []) or []

    def op_log(self, conta, reg):
        k = P + 'ops:' + conta
        L = self.kv.jget(k, []) or []
        L.insert(0, reg)
        self.kv.jset(k, L[:200], ex=86400 * 30)

    def cmds(self, conta):
        k = P + 'cmd:' + conta
        L = self.kv.jget(k, []) or []
        if L:
            self.kv.jset(k, [], ex=3600)
        return L

    def sou_lider(self):
        v = self.kv.get(K_LIDER)
        if v == self.eu:
            self.kv.set(K_LIDER, self.eu, ex=20)
            self.lider = True
        elif v in (None, ''):
            self.lider = self.kv.setnx(K_LIDER, self.eu, 20)
        else:
            self.lider = False
        return self.lider

    # ---------- ticks públicos ----------
    def leitor(self):
        import websocket
        idx = 0
        while not EST['pausa']:
            if not self.lista():
                time.sleep(5)
                continue
            url = WS_URLS[idx % len(WS_URLS)]
            ws = None
            try:
                ws = websocket.create_connection(url, timeout=15, origin='https://alphadolar.online', header=['User-Agent: Mozilla/5.0 (AlphaAuto nuvem)'])
                mapa = {}
                for i, s in enumerate(MERC):
                    mapa[i + 1] = s
                    ws.send(json.dumps({'ticks': s, 'subscribe': 1, 'req_id': i + 1}))
                ws.settimeout(10)
                EST['con'] = time.time()
                EST['vistos'] = set()
                EST['ws'] = ''
                ult_ping, sem = time.time(), time.time()
                while not EST['pausa']:
                    if time.time() - ult_ping > 25:
                        ws.send('{"ping": 1}')
                        ult_ping = time.time()
                    vel = [x for x in EST.get('vistos', ()) if time.time() - LTK.get(x, 0) > 25]
                    if vel and time.time() - EST.get('con', 0) > 40:
                        raise Exception('sem preço de %s há 25 s' % ','.join(vel))
                    if time.time() - sem > 45:
                        raise Exception('nenhum tick em 45 s')
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        raise Exception('conexão fechada')
                    m = json.loads(raw)
                    t = m.get('tick')
                    if not t or t.get('quote') is None:
                        continue
                    sym = t.get('symbol') or t.get('underlying_symbol') or mapa.get(m.get('req_id'))
                    if sym not in TICKS:
                        continue
                    sem = time.time()
                    q = float(t['quote'])
                    dec = int(t.get('pip_size') or 2)
                    d = int(('%.*f' % (dec, q))[-1])
                    ep = int(t.get('epoch') or time.time())
                    T = TICKS[sym]
                    if T and T[-1][0] >= ep:
                        continue
                    T.append((ep, d))
                    EST['ticks'] += 1
                    LTK[sym] = time.time()
                    EST.setdefault('vistos', set()).add(sym)
                    if EST['ticks'] % 50 == 0:
                        self.kv.set(K_MOTOR, str(int(time.time())), ex=60)
            except Exception as e:
                EST['ws'] = ('%s -> %s' % (url.split('/')[2], e))[:200]
                idx += 1
                time.sleep(3)
            finally:
                try:
                    if ws:
                        ws.close()
                except Exception:
                    pass

    def vigia(self):
        while not EST['pausa'] and self.pid == os.getpid():
            try:
                if self.sou_lider():
                    for conta in self.lista():
                        t = self.trab.get(conta)
                        if self.ligado(conta) and (t is None or not t.is_alive()):
                            t = threading.Thread(target=self.trabalha, args=(conta,), daemon=True)
                            self.trab[conta] = t
                            t.start()
            except Exception as e:
                log('vigia', e)
            time.sleep(4)

    # ---------- contas da vaga ----------
    @staticmethod
    def ge(v):
        return r2(float(v.get('plS') or 0) - float(v.get('b0') or 0))

    @staticmethod
    def sessao(u):
        return r2(sum(float(v.get('plS') or 0) for v in u['vagas']))

    @staticmethod
    def aberto_total(u):
        return sum(float((v.get('ab') or {}).get('st') or 0) for v in u['vagas'])

    def cabe(self, u, v, x):
        return -self.ge(v) + x <= float(v['sp']) + 1e-9 and -self.sessao(u) + self.aberto_total(u) + x <= float(u['lim']) + 1e-9

    def base(self, u, v):
        if not float(v.get('xp') or 0) > 0:
            return r2(max(0.35, float(v['st'])))
        bal = u.get('saldo')
        if bal is None:
            return r2(max(0.35, float(v.get('pb') or v['st'])))
        if not v.get('perdaSeq') or v.get('pb') is None:
            x = math.floor(float(bal) * float(v['xp'])) / 100.0
            if float(v.get('xm') or 0) > 0:
                x = min(x, float(v['xm']))
            v['pb'] = r2(max(0.35, x))
        return float(v['pb'])

    def stake(self, u, v, lado, b):
        te, C = int(v.get('te') or 0), max(1, int(v.get('gc') or 1))
        T = te + 1
        if not float(v.get('perdaSeq') or 0) or not te:
            return b
        if int(v.get('passo') or 0) > T * C - 1:
            v['passo'], v['perdaSeq'] = 0, 0.0
            return b
        a = float((u.get('pm') or {}).get(lado) or PAY0[lado])
        return max(b, ceil2((float(v['perdaSeq']) + b * a) / a))

    def fim_vaga(self, conta, u, v, estado, msg):
        v['s'], v['msg'] = estado, msg
        self.op_log(conta, {'t': int(time.time()), 'aviso': '%s %s · %s: %s' % ('🎯' if estado == 'met' else '🛡' if estado == 'stp' else '■', v['nome'], v['mk'], msg), 'vaga': v['i']})

    def para(self, conta, motivo):
        self.liga(conta, False)
        u = self.cfg(conta)
        if u:
            u['parado'] = motivo
            u['t_parou'] = int(time.time())
            for v in u.get('vagas') or []:
                if v.get('s') == 'run':
                    v['s'] = 'off'
            self.salva(conta, u)
        self.op_log(conta, {'t': int(time.time()), 'aviso': motivo})
        log('%s…%s parado: %s' % (conta[:3], conta[-3:], motivo))

    # ---------- o robô de cada conta ----------
    def trabalha(self, conta):
        c, visto, hb, sb = None, {}, 0, 0
        u = self.cfg(conta)
        while self.ligado(conta) and not EST['pausa'] and self.lider:
            try:
                if not u or not u.get('vagas'):
                    return
                if c is None or c.tok != u.get('tok'):
                    c = Conexao(u.get('tok', ''), conta)
                mudou = False
                for cm in self.cmds(conta):
                    for v in u['vagas']:
                        if v['i'] == cm.get('i'):
                            if cm.get('acao') == 'parar' and v.get('s') in ('run', 'met'):
                                v['s'], v['msg'] = 'off', 'Parado por você' + (' (o contrato aberto termina normalmente)' if v.get('ab') else '')
                                mudou = True
                            elif cm.get('acao') == 'ligar' and v.get('s') != 'run':
                                v['s'], v['msg'], v['b0'], v['arm'], v['cicN'], v['rest'] = 'run', '', v.get('plS', 0), False, 1, 0
                                v['cfN'] = (TICKS.get(v['mk']) or [(0, 0)])[-1][0]
                                mudou = True
                if time.time() - hb > 5:
                    hb = time.time()
                    self.kv.set(P + 'hb:' + conta, str(int(hb)), ex=600)
                if time.time() - sb > 30:
                    sb = time.time()
                    try:
                        r = c.req({'balance': 1}, 6)
                        if (r.get('balance') or {}).get('balance') is not None:
                            u['saldo'] = float(r['balance']['balance'])
                            mudou = True
                    except PermissionError:
                        raise
                    except Exception:
                        pass
                agora = time.time()
                for v in u['vagas']:
                    if v.get('ab'):
                        mudou = self.confere(conta, c, u, v) or mudou
                for v in u['vagas']:
                    if v.get('s') == 'met' and v.get('rest') and agora >= float(v['rest']):
                        v['cicN'] = int(v.get('cicN') or 1) + 1
                        v.update({'s': 'run', 'b0': v.get('plS', 0), 'arm': False, 'rest': 0,
                                  'msg': 'Rodada %d de %d começou.' % (v['cicN'], int(v.get('cic') or 1))})
                        mudou = True
                if not any(v.get('s') == 'run' or v.get('ab') or (v.get('s') == 'met' and v.get('rest')) for v in u['vagas']):
                    self.salva(conta, u)
                    return self.para(conta, 'TODOS OS ROBÔS PARARAM: ' + ' · '.join('%s %s' % (v['nome'], v.get('msg') or v.get('s')) for v in u['vagas'])[:300])
                for v in u['vagas']:
                    if v.get('s') != 'run' or v.get('ab'):
                        continue
                    T = TICKS.get(v['mk'])
                    if not T or T[-1][0] <= visto.get(v['i'], 0):
                        continue
                    visto[v['i']] = T[-1][0]
                    mudou = self.decide(conta, c, u, v) or mudou
                if mudou:
                    u['t_upd'] = int(time.time())
                    self.salva(conta, u)
                else:
                    time.sleep(0.05)
                if not self.ligado(conta):
                    break
            except PermissionError:
                self.salva(conta, u)
                self.para(conta, 'SUA SESSÃO NA DERIV EXPIROU: abra a Alpha Automação e ligue a nuvem de novo')
                return
            except Exception as ex:
                log('trabalha', conta[-3:], ex)
                time.sleep(1.5)
        if u:
            pm = self.kv.get(P + 'pmot:' + conta)   # desligado pela rota: guarda o estado com o motivo
            if pm and not self.ligado(conta):
                u['parado'], u['t_parou'] = pm, int(time.time())
            if not self.ligado(conta):
                for v in u.get('vagas') or []:
                    if v.get('s') in ('run', 'met'):
                        v['s'] = 'off'
            self.salva(conta, u)

    def decide(self, conta, c, u, v):
        agora = time.time()
        if agora < float(v.get('prox') or 0):
            return False
        if u.get('um') and any(o.get('ab') for o in u['vagas'] if o is not v):
            if v.get('msg') != '☝ esperando a outra vaga terminar (uma por vez)':
                v['msg'] = '☝ esperando a outra vaga terminar (uma por vez)'
                return True
            return False
        lado, tx = sinal(v, v['mk'])
        if not lado:
            if v.get('msg') != tx:
                v['msg'] = tx
                return True
            return False
        ok, tx = confirma(v, v['mk'], lado)
        if not ok:
            if v.get('msg') != tx:
                v['msg'] = tx
                return True
            return False
        b = self.base(u, v)
        st = self.stake(u, v, lado, b)
        if not self.cabe(u, v, st):
            if not float(v.get('perdaSeq') or 0) or not self.cabe(u, v, b):
                glob = -self.sessao(u) + self.aberto_total(u) + b > float(u['lim']) + 1e-9
                self.fim_vaga(conta, u, v, 'stp', 'Parou antes de passar do limite global.' if glob else 'Parou antes de passar do stop deste robô.')
                return True
            self.op_log(conta, {'t': int(time.time()), 'aviso': '🛡 %s: a recuperação passaria do stop. Assumiu −$%.2f e voltou à entrada.' % (v['nome'], float(v['perdaSeq'])), 'vaga': v['i']})
            v['perdaSeq'], v['passo'], st = 0.0, 0, b
        if u.get('saldo') is not None and st > float(u['saldo']) + 1e-9:
            self.fim_vaga(conta, u, v, 'stp', 'Saldo insuficiente para a próxima entrada.')
            return True
        ct, bar, nome = CT[lado]
        prm = {'contract_type': ct, 'amount': st, 'basis': 'stake', 'currency': u.get('moeda') or 'USD', 'duration': 1, 'duration_unit': 't'}
        if bar is not None:
            prm['barrier'] = bar
        prm[c.symkey] = v['mk']
        r = c.req({'buy': 1, 'price': st, 'parameters': prm}, 10)
        msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error') and ('symbol' in msg.lower() or 'Properties not allowed' in msg or 'validation' in msg.lower()):
            prm.pop(c.symkey, None)
            c.symkey = 'symbol' if c.symkey == 'underlying_symbol' else 'underlying_symbol'
            prm[c.symkey] = v['mk']
            r = c.req({'buy': 1, 'price': st, 'parameters': prm}, 10)
            msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error'):
            v['err'] = int(v.get('err') or 0) + 1
            if 'rate' in msg.lower() or 'too many' in msg.lower():
                v['prox'], v['msg'] = time.time() + 30, 'A Deriv pediu uma pausa. Volta em 30 s.'
            else:
                v['prox'], v['msg'] = time.time() + 4, 'Não entrou: ' + msg[:120]
            if v['err'] >= 5 or 'balance' in msg.lower() or 'insufficient' in msg.lower():
                self.fim_vaga(conta, u, v, 'stp', 'A Deriv recusou: ' + msg[:100])
            return True
        bb = r.get('buy') or {}
        try:
            p = float(bb.get('payout')) / float(bb.get('buy_price')) - 1
            if 0.2 < p < 1.2:
                u.setdefault('pm', {})[lado] = p
        except Exception:
            pass
        if bb.get('balance_after') is not None:
            try:
                u['saldo'] = float(bb['balance_after'])
            except Exception:
                pass
        T = TICKS.get(v['mk'])
        v['err'] = 0
        v['ab'] = {'cid': bb.get('contract_id'), 'st': float(bb.get('buy_price') or st), 'lado': lado, 't': time.time(), 'ep': T[-1][0] if T else 0}
        v['msg'] = 'operação em andamento · %s $%.2f' % (nome, v['ab']['st'])
        return True

    def confere(self, conta, c, u, v):
        ab = v['ab']
        if time.time() - float(ab.get('t') or 0) < 1.2 or time.time() - float(ab.get('ult') or 0) < 0.8:
            return False
        ab['ult'] = time.time()
        q = None
        try:
            rr = c.req({'proposal_open_contract': 1, 'contract_id': ab['cid']}, 5)
            q = rr.get('proposal_open_contract') or {}
            if not (q.get('is_sold') or q.get('status') in ('won', 'lost', 'sold')):
                q = None
        except PermissionError:
            raise
        except Exception:
            q = None
        if q is None:
            if time.time() - float(ab.get('t') or 0) > 90:
                v.pop('ab', None)
                v['msg'] = 'A Deriv não confirmou o contrato %s em 90 s: confira no histórico da Deriv.' % ab['cid']
                self.op_log(conta, {'t': int(time.time()), 'aviso': '%s: %s' % (v['nome'], v['msg']), 'vaga': v['i']})
                return True
            return False
        v.pop('ab', None)
        if not self.kv.setnx(P + 'contou:%s' % ab['cid'], '1', 86400 * 3):
            return True
        pl = r2(float(q.get('profit') or 0))
        won = pl > 0
        lado = ab['lado']
        dg = digito_saida(q, v['mk'])
        v['plS'] = r2(float(v.get('plS') or 0) + pl)
        v['o'] = int(v.get('o') or 0) + 1
        s = u.setdefault('sess', {'n': 0, 'w': 0, 'l': 0})
        s['n'] += 1
        if won:
            v['w'] = int(v.get('w') or 0) + 1
            s['w'] += 1
            v['perdaSeq'], v['passo'] = 0.0, 0
        else:
            s['l'] += 1
            v['perdaSeq'] = r2(float(v.get('perdaSeq') or 0) + ab['st'])
            v['passo'] = int(v.get('passo') or 0) + 1
        T = TICKS.get(v['mk'])
        v['cfN'] = T[-1][0] if T else int(time.time())   # a confirmação conta só ticks depois deste contrato
        v['prox'] = time.time() + 3
        v['msg'] = ''
        tx = 'WIN' if won else 'LOSS'
        if not won and int(v.get('pz') or 0) > 0:
            v['prox'] = time.time() + int(v['pz'])
            v['msg'] = 'Pausa de %d s depois da perda.' % int(v['pz'])
        te, C = int(v.get('te') or 0), max(1, int(v.get('gc') or 1))
        Tn = te + 1
        if not won and te and C >= 2:
            if v['passo'] > Tn * C - 1:
                m = 'Perdeu os %d ciclos de gale (−$%.2f).' % (C, float(v['perdaSeq']))
                if v.get('gcFim') == 'parar':
                    v['perdaSeq'], v['passo'] = 0.0, 0
                    self.fim_vaga(conta, u, v, 'stp', m + ' Parou, como você escolheu.')
                else:
                    v['msg'] = m + ' Assumiu a perda e voltou à entrada.'
                tx += ' · ' + m
            elif v['passo'] % Tn == 0:
                pz = max(0, int(v.get('gcP') or 0))
                v['prox'] = max(float(v['prox']), time.time() + pz)
                v['msg'] = '🔁 Ciclo %d de %d perdido · %sdepois espera o sinal de novo e continua a recuperação ($%.2f).' % (v['passo'] // Tn, C, ('pausa de %d s, ' % pz) if pz else '', float(v['perdaSeq']))
                tx += ' · ciclo %d de %d perdido' % (v['passo'] // Tn, C)
        self.op_log(conta, {'t': int(time.time()), 'vaga': v['i'], 'nome': v['nome'], 'mk': v['mk'], 'lado': CT[lado][2], 'saiu': dg,
                            'st': ab['st'], 'pl': pl, 'cid': ab['cid'], 'tx': tx})
        _extrato(conta, u.get('tipo'), ab['cid'], v['mk'], ab['st'], pl, CT[lado][2])
        if v.get('s') != 'run':
            return True
        g = self.ge(v)
        tv, me = int(v.get('xt') or 0), float(v.get('me') or 0)
        if tv and me > 0:
            if v.get('arm') and not won:
                v['arm'] = False
                self.fim_vaga(conta, u, v, 'stp', 'Trava de lucro: passou de %d%% da meta e veio uma perda. Parou com %s$%.2f.' % (tv, '+' if g >= 0 else '−', abs(g)))
            elif not v.get('arm') and me * tv / 100.0 - 1e-9 <= g < me - 1e-9:
                v['arm'] = True
        if v.get('s') == 'run':
            if me > 0 and g >= me - 1e-9:
                n, cN = int(v.get('cic') or 1), int(v.get('cicN') or 1)
                if n > cN:
                    pz = max(1, int(v.get('cicPz') or 3))
                    v['rest'] = time.time() + 60 * pz
                    self.fim_vaga(conta, u, v, 'met', 'Meta batida: +$%.2f nesta rodada. Próxima rodada (%d de %d) em %d min.' % (g, cN + 1, n, pz))
                else:
                    self.fim_vaga(conta, u, v, 'met', 'Meta batida: +$%.2f nesta rodada.' % g)
            elif -g >= float(v['sp']) - 1e-9:
                self.fim_vaga(conta, u, v, 'stp', 'Stop deste robô atingido.')
        if -self.sessao(u) >= float(u['lim']) - 1e-9:
            for o in u['vagas']:
                if o.get('s') == 'run':
                    o['s'], o['msg'] = 'stp', 'Limite global atingido.'
            self.op_log(conta, {'t': int(time.time()), 'aviso': '🛡 LIMITE GLOBAL de $%.2f atingido · resultado −$%.2f' % (float(u['lim']), abs(self.sessao(u)))})
        return True


def register_nuvem_auto(app):
    from flask import request, jsonify
    nv = NuvemAuto()

    def solta():
        EST['pausa'] = True
        try:
            if nv.kv.get(K_LIDER) == nv.eu:
                nv.kv.set(K_LIDER, '', ex=1)
        except Exception:
            pass
    atexit.register(solta)

    @app.before_request
    def _nau_garante():
        try:
            if nv.pid == os.getpid() or time.time() - getattr(nv, '_chk', 0) < 10:
                return
            nv._chk = time.time()
            if nv.lista():
                nv.garante()
        except Exception:
            pass

    cache = {}

    def dono(d):
        tok, conta = str(d.get('token') or '').strip(), str(d.get('conta') or '').strip()
        if not tok or not conta:
            return None, 'faltou token ou conta'
        h = hashlib.sha256((tok + '|' + conta).encode()).hexdigest()
        cc = cache.get(h)
        if cc and time.time() - cc[0] < 600:
            return cc[1], None
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
        if len(cache) > 5000:
            cache.clear()
        return info, None

    def num(v, d, lo, hi):
        try:
            return max(lo, min(hi, float(str(v).replace(',', '.'))))
        except Exception:
            return d

    def publico(u):
        return {k: v for k, v in u.items() if k != 'tok'}

    def limpa_vaga(x, i, real):
        cat = x.get('cat') if x.get('cat') in ('pi', 'ou', 'o3') else None
        mk = str(x.get('mk') or '')
        if not cat or mk not in MERC:
            return None, 'vaga %d: robô ou mercado inválido' % (i + 1)
        if real and mk.startswith(SO_DEMO):
            return None, 'vaga %d: %s só funciona na conta demo' % (i + 1, mk)
        pf = PERF.get(x.get('perf'))
        if x.get('perf') == 'custom' and num(x.get('nmin'), 0, 0, 30) > 0:
            pf = (int(num(x.get('nmin'), 18, 15, 30)), int(num(x.get('tent'), 0, 0, 12)))
        pf = pf or PERF['equilibrado']
        return {'i': int(num(x.get('i'), i, 0, 30)), 'rb': str(x.get('rb') or '')[:30], 'nome': str(x.get('nome') or 'Robô')[:40], 'cat': cat,
                'mo': 'contra' if x.get('mo') == 'contra' else 'segue', 'mk': mk, 'n': pf[0], 'te': pf[1],
                'st': num(x.get('st'), 0.35, 0.35, 5000), 'xp': num(x.get('xp'), 0, 0, 100), 'xm': num(x.get('xm'), 0, 0, 100000),
                'me': num(x.get('me'), 3, 0.01, 1000000), 'sp': num(x.get('sp'), 5, 0.35, 1000000), 'pz': int(num(x.get('pz'), 0, 0, 3600)),
                'xc': int(num(x.get('xc'), 0, 0, 5)), 'xt': int(num(x.get('xt'), 0, 0, 95)),
                'gc': int(num(x.get('gc'), 1, 1, 10)), 'gcP': int(num(x.get('gcP'), 60, 0, 3600)), 'gcFim': 'parar' if x.get('gcFim') == 'parar' else 'reset',
                'cic': int(num(x.get('cic'), 1, 1, 50)), 'cicPz': int(num(x.get('cicPz'), 3, 1, 240)), 'cicN': 1,
                's': 'run', 'plS': 0.0, 'b0': 0.0, 'o': 0, 'w': 0, 'perdaSeq': 0.0, 'passo': 0, 'prox': 0, 'cfN': 0, 'arm': False, 'msg': 'ligando'}, None

    @app.route('/api/nuvem-auto/ligar', methods=['POST'])
    def _nau_ligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta, cf = str(d['conta']), d.get('cfg') or {}
        if nv.ligado(conta) or any(v.get('ab') for v in (nv.cfg(conta).get('vagas') or [])):
            return jsonify({'ok': False, 'erro': 'a nuvem já está ligada nesta conta (desligue antes)'}), 400
        real = str(info.get('tipo')) == 'real'
        vs, vistos = [], set()
        for i, x in enumerate((cf.get('vagas') or [])[:15]):
            v, e = limpa_vaga(x or {}, i, real)
            if e:
                return jsonify({'ok': False, 'erro': e}), 400
            if v['mk'] in vistos:
                return jsonify({'ok': False, 'erro': 'dois robôs no mesmo mercado (%s)' % v['mk']}), 400
            vistos.add(v['mk'])
            vs.append(v)
        if not vs:
            return jsonify({'ok': False, 'erro': 'nenhum robô de dígitos configurado'}), 400
        if real:
            nvp = _nivel_plano(str(d.get('token') or ''))
            if nvp is None:
                return jsonify({'ok': False, 'erro': 'não consegui confirmar o seu plano agora; tente de novo em instantes'}), 503
            mx = VAGAS_PLANO.get(nvp, 15 if nvp > 3 else 1)
            if len(vs) > mx:
                return jsonify({'ok': False, 'erro': 'Na conta real o seu plano libera %d robô(s) ao mesmo tempo (você mandou %d).' % (mx, len(vs))}), 403
        lim = num(cf.get('lim'), 10, 0.35, 10000000)
        u = {'conta': conta, 'tok': str(d['token']).strip(), 'tipo': info['tipo'], 'moeda': info['moeda'], 'parado': '', 't_lig': int(time.time()),
             'lim': lim, 'um': bool(cf.get('um')), 'vagas': vs, 'pm': {}, 'sess': {'n': 0, 'w': 0, 'l': 0},
             'saldo': float(info['saldo']) if info.get('saldo') is not None else None}
        for v in vs:
            T = TICKS.get(v['mk'])
            v['cfN'] = T[-1][0] if T else int(time.time())
        nv.salva(conta, u)
        nv.kv.jset(P + 'cmd:' + conta, [], ex=3600)
        nv.kv.set(P + 'pmot:' + conta, '', ex=60)
        nv.liga(conta, True)
        L = nv.lista()
        if conta not in L:
            L.append(conta)
            nv.kv.jset(K_LISTA, L)
        nv.garante()
        nv.op_log(conta, {'t': int(time.time()), 'aviso': 'NUVEM LIGADA na conta %s · %d robô(s): %s · limite global $%.2f%s' % (
            info['tipo'].upper(), len(vs), ', '.join('%s em %s' % (v['nome'], v['mk']) for v in vs)[:250], lim, ' · uma por vez' if u['um'] else '')})
        return jsonify({'ok': True, 'cfg': publico(u)})

    @app.route('/api/nuvem-auto/desligar', methods=['POST'])
    def _nau_desligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        ab = any(v.get('ab') for v in (u.get('vagas') or []))
        mot = 'desligado por você' + (' (o contrato aberto termina normalmente)' if ab else '')
        nv.kv.set(P + 'pmot:' + conta, mot, ex=86400)
        nv.liga(conta, False)
        if u:
            u['parado'] = mot
            u['t_parou'] = int(time.time())
            for v in u.get('vagas') or []:
                if v.get('s') in ('run', 'met'):
                    v['s'] = 'off'
            nv.salva(conta, u)
        nv.op_log(conta, {'t': int(time.time()), 'aviso': 'NUVEM DESLIGADA por você'})
        return jsonify({'ok': True})

    @app.route('/api/nuvem-auto/vaga', methods=['POST'])
    def _nau_vaga():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        if not nv.ligado(conta):
            return jsonify({'ok': False, 'erro': 'a nuvem não está ligada'}), 400
        k = P + 'cmd:' + conta
        L = nv.kv.jget(k, []) or []
        L.append({'i': int(num(d.get('i'), -1, -1, 30)), 'acao': 'ligar' if d.get('acao') == 'ligar' else 'parar'})
        nv.kv.jset(k, L[-30:], ex=3600)
        return jsonify({'ok': True})

    @app.route('/api/nuvem-auto/estado', methods=['POST'])
    def _nau_estado():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        if u:
            u['ligado'] = nv.ligado(conta)
        mt = float(nv.kv.get(K_MOTOR) or 0)
        h = nv.kv.get(P + 'hb:' + conta)
        n = int(num(d.get('n'), 60, 1, 200))
        return jsonify({'ok': True, 'versao': VERSAO, 'cfg': publico(u) if u else None, 'ops': (nv.kv.jget(P + 'ops:' + conta, []) or [])[:n],
                        'motor': time.time() - mt < 60, 'robo_idade': int(time.time() - float(h)) if h else None, 'saldo': info.get('saldo')})

    @app.route('/api/admin/nuvem-auto', methods=['GET'])
    def _nau_admin():
        s = os.environ.get('ADMIN_SENHA', '')
        if not s or request.headers.get('X-Admin-Token') != s:
            return jsonify({'ok': False}), 403
        out = []
        for conta in nv.lista():
            u = nv.cfg(conta)
            out.append({'conta': conta[:3] + '…' + conta[-3:], 'tipo': u.get('tipo'), 'ligado': nv.ligado(conta), 'parado': u.get('parado'),
                        'vagas': [{'nome': v.get('nome'), 'mk': v.get('mk'), 's': v.get('s'), 'pl': v.get('plS')} for v in u.get('vagas') or []]})
        return jsonify({'ok': True, 'versao': VERSAO, 'lider': nv.lider, 'pid': nv.pid, 'ws': EST['ws'], 'ticks': EST['ticks'], 'pessoas': out})

    log('%s registrada' % VERSAO)
    return nv
