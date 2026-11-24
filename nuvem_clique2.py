# -*- coding: utf-8 -*-
"""NUVEM-CLIQUE2-V1 — Alpha Clique 2.0 no servidor (modo AUTO, "Uma por vez"), funciona com a página fechada e
aparece igual no PC e no celular.

O mesmo motor da página:
- análise: os últimos 30 dígitos de cada um dos 10 mercados; 10 contratos de dígito (Over 1–4, Under 5–8, Par, Ímpar);
  nota = (frequência − chance) + sequência contra (até 3) · 0,02; uma jogada por mercado; entra na melhor.
- contrato de 1 tick, % = chance real do contrato.
- HIT: espera N LOSS virtuais seguidos (dígitos do outro lado) antes de entrar; no gale também, se escolhido.
- gale: Desligado / Na mesma / Nova análise (outro mercado, chance parecida); método Tradicional (recuperação exata)
  ou Perdas consecutivas (fator fixo; perder tudo para a sessão).
- ciclos: perdeu o ciclo → pausa → HIT de novo (mínimo 2) → a recuperação continua; se perder tudo: resetar ou parar.
- meta, stop loss estrito (nenhuma entrada passa dele), trava de lucro.

Rotas: POST /api/nuvem-clique2/ligar|desligar|estado {token, conta[, cfg]} · GET /api/admin/nuvem-clique2 (X-Admin-Token)
"""
import os, json, time, math, uuid, random, threading, atexit, hashlib
from collections import deque
from datetime import datetime, timedelta, timezone

try:
    from nuvem_digitos import KV, Conexao, contas_do_token, log as _log
except Exception:   # pragma: no cover
    from backend.nuvem_digitos import KV, Conexao, contas_do_token, log as _log   # noqa

VERSAO = 'NUVEM-CLIQUE2-V1.1'  # V1.1: zerar a sessão ·
MERC = ['R_10', 'R_25', 'R_50', 'R_75', 'R_100', '1HZ10V', '1HZ25V', '1HZ50V', '1HZ75V', '1HZ100V']
NOME = {'R_10': 'Vol 10', 'R_25': 'Vol 25', 'R_50': 'Vol 50', 'R_75': 'Vol 75', 'R_100': 'Vol 100', '1HZ10V': 'Vol 10 (1s)',
        '1HZ25V': 'Vol 25 (1s)', '1HZ50V': 'Vol 50 (1s)', '1HZ75V': 'Vol 75 (1s)', '1HZ100V': 'Vol 100 (1s)'}
WS_URLS = [u for u in [os.environ.get('SALA_WS_URL', '').strip(),
                       'wss://api.derivws.com/trading/v1/options/ws/public',
                       'wss://ws.derivws.com/websockets/v3?app_id=1089'] if u]
P = 'nuvem_cl2:'
K_LISTA, K_LIDER, K_MOTOR = P + 'lista', P + 'lider', P + 'motor'
TICKS = {s: deque(maxlen=200) for s in MERC}   # (epoch, dígito)
LTK = {}
EST = {'pausa': False, 'ws': '', 'ticks': 0}
BRT = timezone(timedelta(hours=-3))
# contratos: nome, tipo, barreira, chance
CT = [('OVER %d' % b, 'DIGITOVER', b, (9 - b) / 10.0) for b in (1, 2, 3, 4)] + \
     [('UNDER %d' % b, 'DIGITUNDER', b, b / 10.0) for b in (5, 6, 7, 8)] + \
     [('PAR', 'DIGITEVEN', None, .5), ('ÍMPAR', 'DIGITODD', None, .5)]


def log(*a):
    _log('[Clique2]', *a)


def r2(v):
    return round(float(v) + 1e-9, 2)


def ceil2(v):
    return math.ceil(float(v) * 100 - 1e-6) / 100.0


def ok(ct, bar, d):
    if ct == 'DIGITOVER':
        return d > bar
    if ct == 'DIGITUNDER':
        return d < bar
    if ct == 'DIGITEVEN':
        return d % 2 == 0
    return d % 2 == 1


def f2(v):
    return ('−' if v < 0 else '+') + '$%.2f' % abs(v)


def _extrato(conta, tipo, cid, sym, stake, pl, tp):
    try:
        from nuvem_clique import _extrato as _ex
    except Exception:
        try:
            from backend.nuvem_clique import _extrato as _ex   # noqa
        except Exception:
            return
    try:
        _ex(conta, tipo, cid, sym, stake, pl, 'clique2', 'Alpha Clique 2.0', tp)
    except Exception as e:
        log('extrato', str(e)[:120])


def analisa():
    L = []
    for s in MERC:
        d = [x[1] for x in list(TICKS[s])[-30:]]
        if len(d) < 20:
            continue
        for (n, ct, bar, p) in CT:
            f = sum(1 for x in d if ok(ct, bar, x)) / float(len(d))
            sq = 0
            for x in reversed(d):
                if ok(ct, bar, x):
                    break
                sq += 1
            L.append({'mk': s, 'm': NOME[s], 'c': n, 'ct': ct, 'bar': bar, 'p': p, 'f': round(f, 3), 'sc': (f - p) + min(sq, 3) * .02 + random.random() * .01})
    L.sort(key=lambda x: -x['sc'])
    out, vis = [], set()
    for x in L:
        if x['mk'] in vis:
            continue
        vis.add(x['mk'])
        out.append(x)
        if len(out) >= 8:
            break
    return out


class NuvemClique2(object):
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

    def dia(self, conta, pl):
        k = P + 'dia:' + conta + ':' + datetime.now(BRT).strftime('%Y-%m-%d')
        try:
            v = float(self.kv.get(k) or 0)
        except Exception:
            v = 0.0
        self.kv.set(k, str(r2(v + pl)), ex=86400 * 10)

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
                ws = websocket.create_connection(url, timeout=15, origin='https://alphadolar.online', header=['User-Agent: Mozilla/5.0 (AlphaClique2 nuvem)'])
                mapa = {}
                for i, s in enumerate(MERC):
                    mapa[i + 1] = s
                    ws.send(json.dumps({'ticks': s, 'subscribe': 1, 'req_id': i + 1}))
                ws.settimeout(10)
                EST['con'], EST['vistos'], EST['ws'] = time.time(), set(), ''
                ult_ping, sem = time.time(), time.time()
                while not EST['pausa']:
                    if time.time() - ult_ping > 25:
                        ws.send('{"ping": 1}')
                        ult_ping = time.time()
                    vel = [x for x in EST.get('vistos', ()) if time.time() - LTK.get(x, 0) > 20]
                    if vel and time.time() - EST.get('con', 0) > 30:
                        raise Exception('sem preço de %s há 20 s' % ','.join(vel))
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
                    ep, T = int(t.get('epoch') or time.time()), TICKS[sym]
                    if T and T[-1][0] >= ep:
                        continue
                    dec = int(t.get('pip_size') or 2)
                    T.append((ep, int(('%.*f' % (dec, float(t['quote'])))[-1])))
                    EST['ticks'] += 1
                    LTK[sym] = time.time()
                    EST.setdefault('vistos', set()).add(sym)
                    if EST['ticks'] % 50 == 0:
                        self.kv.set(K_MOTOR, str(int(time.time())), ex=60)
                        try:
                            self.kv.jset(P + 'dg', {s: [x[1] for x in list(TICKS[s])[-30:]] for s in MERC}, ex=120)
                        except Exception:
                            pass
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

    # ---------- o robô ----------
    def para(self, conta, u, motivo):
        self.liga(conta, False)
        u['parado'], u['t_parou'], u['fase'], u['esp'] = motivo, int(time.time()), 'parado', None
        self.salva(conta, u)
        self.op_log(conta, {'t': int(time.time()), 'aviso': motivo})
        log('%s…%s parado: %s' % (conta[:3], conta[-3:], motivo))

    def trabalha(self, conta):
        c, hb, sb, tf = None, 0, 0, 0
        u = self.cfg(conta)
        while self.ligado(conta) and not EST['pausa'] and self.lider:
            try:
                if not u:
                    return
                if c is None or c.tok != u.get('tok'):
                    c = Conexao(u.get('tok', ''), conta)
                mudou = False
                if self.kv.get(P + 'zerar:' + conta) == '1':   # NUVEM-CLIQUE2-ZERAR-V1: a pessoa zerou a sessão com o robô ligado
                    self.kv.set(P + 'zerar:' + conta, '0', ex=60)
                    u['sess'], u['travaOn'], mudou = {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0}, False, True
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
                if u.get('ab'):
                    fim = self.confere(conta, c, u)
                    if fim:
                        mudou = True
                        if fim == 'parou':
                            return
                else:
                    mudou = self.passo(conta, c, u) or mudou
                if mudou or time.time() - tf > 3:
                    tf = time.time()
                    u['t_upd'] = int(time.time())
                    self.salva(conta, u)
                else:
                    time.sleep(0.15)
                if not self.ligado(conta):
                    break
            except PermissionError:
                return self.para(conta, u, 'SUA SESSÃO NA DERIV EXPIROU: abra o Alpha Clique 2.0 e ligue o AUTO de novo')
            except Exception as ex:
                log('trabalha', conta[-3:], ex)
                time.sleep(1.5)
        if u and not self.ligado(conta):
            pm = self.kv.get(P + 'pmot:' + conta)
            if pm:
                u['parado'], u['t_parou'], u['fase'] = pm, int(time.time()), 'parado'
            u['esp'] = None
            self.salva(conta, u)

    def gef(self, u):
        return 0 if u.get('gm') == 'off' else int(u.get('G') or 0)

    def stake(self, u, j):
        g, E = u['G_'], float(u['E'])
        if not g['passo']:
            return r2(max(0.35, E))
        if u.get('met') == 'seq' and float(u.get('f') or 0) > 0:
            return max(0.35, r2(E * math.pow(float(u['f']), g['passo'])))
        r = float((u.get('pm') or {}).get(j['c']) or (.95 / j['p'] - 1))
        return max(0.35, ceil2((g['perda'] + E * r) / r))

    def zera(self, u):
        u['G_'] = {'nivel': 0, 'perda': 0.0, 'passo': 0, 'ciclo': 1, 'novo': False, 'ex': None, 'p0': .5}

    def passo(self, conta, c, u):
        """sem contrato aberto: pausa entre ciclos → análise → HIT → compra"""
        g = u.setdefault('G_', None) or self.zera(u) or u['G_']
        agora = time.time()
        if agora < float(u.get('prox') or 0):
            f = int(float(u['prox']) - agora) + 1
            u['fase'] = ('⏸ CICLO %d/%d em %d s · depois espera o HIT · recupera $%.2f' % (g['ciclo'], int(u.get('C') or 1), f, g['perda'])) if g['passo'] else 'próxima análise em %d s' % f
            return True
        e = u.get('esp')
        if e:   # esperando o HIT na jogada escolhida
            T = [x for x in list(TICKS[e['mk']]) if x[0] > e['ep']]
            if not T:
                return False
            for (ep, d) in T:
                e['ep'] = ep
                w = ok(e['ct'], e['bar'], d)
                e['n'] = 0 if w else e['n'] + 1
                e['v'] = (e.get('v') or [])[-7:] + [[d, 1 if w else 0]]
            u['fase'] = '👻 HIT %d/%d em %s · %s' % (e['n'], e['k'], e['c'], NOME[e['mk']])
            if e['n'] >= e['k']:
                j = e['j']
                u['esp'] = None
                self.op_log(conta, {'t': int(time.time()), 'aviso': '✔ HIT completo: %d LOSS virtual(is) seguido(s) em %s · %s → entrando' % (e['k'], j['c'], j['m'])})
                return self.compra(conta, c, u, j) or True
            if not g['passo'] and time.time() - e['t0'] > 90:   # entrada normal: 90 s sem HIT → analisa de novo
                u['esp'] = None
                u['fase'] = 'o HIT não veio em 90 s · nova análise'
            return True
        # análise (pede 2 s de "analisando" para todos verem a troca)
        if not u.get('an_t'):
            u['an_t'] = agora + 2.0
            u['fase'] = '🧠 analisando os 10 mercados…'
            return True
        if agora < u['an_t']:
            return False
        u['an_t'] = 0
        J = analisa()
        if len(J) < 3:
            u['fase'] = 'juntando os dígitos dos mercados…'
            u['prox'] = agora + 3
            return True
        j = J[0]
        if g['passo'] and u.get('gm') == 'nova':
            cand = [x for x in J if x['mk'] != g.get('ex')] or J
            cand.sort(key=lambda x: (abs(x['p'] - g['p0']), -x['sc']))
            j = cand[0]
        elif g['passo'] and u.get('ult'):
            j = u['ult']   # gale "Na mesma": a mesma jogada
        u['J'] = [{k: x[k] for k in ('mk', 'm', 'c', 'p', 'f')} for x in J]
        u['alvo'] = {k: j[k] for k in ('mk', 'm', 'c', 'ct', 'bar', 'p', 'f')}
        k = int(u.get('k') or 0)
        if g.get('novo'):
            k = max(k, 2)
            g['novo'] = False
        if k > 0 and (not g['nivel'] or u.get('kg', True)):
            T = TICKS[j['mk']]
            u['esp'] = {'mk': j['mk'], 'c': j['c'], 'ct': j['ct'], 'bar': j['bar'], 'k': k, 'n': 0, 'v': [], 'ep': T[-1][0] if T else 0, 't0': agora, 'j': u['alvo']}
            u['fase'] = '👻 HIT 0/%d em %s · %s' % (k, j['c'], j['m'])
            return True
        return self.compra(conta, c, u, u['alvo']) or True

    def compra(self, conta, c, u, j):
        g, s = u['G_'], u.setdefault('sess', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0})
        st = self.stake(u, j)
        L = float(u.get('L') or 0)
        if L > 0 and -s['pl'] + st > L + 1e-9:
            return self.para(conta, u, '⛔ a entrada de $%.2f passaria do stop loss de $%.2f (faltam $%.2f) · resultado %s' % (st, L, max(0, L + s['pl']), f2(s['pl'])))
        if u.get('saldo') is not None and st > float(u['saldo']) + 1e-9:
            return self.para(conta, u, 'PARADO: saldo insuficiente para a entrada de $%.2f' % st)
        prm = {'contract_type': j['ct'], 'amount': st, 'basis': 'stake', 'currency': u.get('moeda') or 'USD', 'duration': 1, 'duration_unit': 't'}
        if j.get('bar') is not None:
            prm['barrier'] = str(j['bar'])
        prm[c.symkey] = j['mk']
        r = c.req({'buy': 1, 'price': st, 'parameters': prm}, 10)
        msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error') and ('symbol' in msg.lower() or 'Properties not allowed' in msg or 'validation' in msg.lower()):
            prm.pop(c.symkey, None)
            c.symkey = 'symbol' if c.symkey == 'underlying_symbol' else 'underlying_symbol'
            prm[c.symkey] = j['mk']
            r = c.req({'buy': 1, 'price': st, 'parameters': prm}, 10)
            msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error'):
            u['erros'] = int(u.get('erros') or 0) + 1
            self.op_log(conta, {'t': int(time.time()), 'aviso': 'A Deriv recusou a entrada: ' + msg[:120]})
            if u['erros'] >= 3 or 'balance' in msg.lower() or 'insufficient' in msg.lower():
                return self.para(conta, u, 'PARADO: a Deriv recusou (%s)' % msg[:90])
            u['prox'] = time.time() + 5
            return
        b = r.get('buy') or {}
        u['erros'] = 0
        try:
            p = float(b.get('payout')) / float(b.get('buy_price')) - 1
            if 0.03 < p < 3:
                u.setdefault('pm', {})[j['c']] = p
        except Exception:
            pass
        u['ult'] = j
        u['ab'] = {'cid': b.get('contract_id'), 'st': float(b.get('buy_price') or st), 'j': j, 't': time.time(), 'nivel': g['nivel'], 'ciclo': g['ciclo'], 'passo': g['passo']}
        u['fase'] = '🎰 entrou: %s · %s $%.2f%s' % (j['c'], j['m'], u['ab']['st'], (' · CICLO %d' % g['ciclo'] if int(u.get('C') or 1) > 1 and g['passo'] else '') + (' · GALE %d' % g['nivel'] if g['nivel'] else ''))

    def confere(self, conta, c, u):
        ab = u['ab']
        if time.time() - float(ab['t']) < 1.8 or time.time() - float(ab.get('ult') or 0) < 0.8:
            return None
        ab['ult'] = time.time()
        try:
            q = c.req({'proposal_open_contract': 1, 'contract_id': ab['cid']}, 5).get('proposal_open_contract') or {}
        except PermissionError:
            raise
        except Exception:
            q = {}
        if not (q.get('is_sold') or q.get('status') in ('won', 'lost', 'sold')):
            if time.time() - float(ab['t']) > 120:
                u.pop('ab', None)
                self.zera(u)
                self.op_log(conta, {'t': int(time.time()), 'aviso': 'a Deriv não confirmou o contrato %s: confira no histórico da Deriv' % ab['cid']})
                return 'ok'
            return None
        u.pop('ab', None)
        if not self.kv.setnx(P + 'contou:%s' % ab['cid'], '1', 86400 * 3):
            return 'ok'
        pl = r2(float(q.get('profit') or 0))
        won, j = pl > 0, ab['j']
        s, g = u.setdefault('sess', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0}), u['G_']
        s['pl'], s['n'] = r2(s['pl'] + pl), s['n'] + 1
        if won:
            s['w'] += 1
        else:
            s['l'] += 1
        self.dia(conta, pl)
        dg = None
        try:
            dg = int(str(q.get('exit_tick_display_value') or q.get('exit_tick') or '')[-1])
        except Exception:
            pass
        C = max(1, int(u.get('C') or 1))
        self.op_log(conta, {'t': int(time.time()), 'mk': j['mk'], 'nome': j['m'], 'c': j['c'], 'tipo': j['c'], 'st': ab['st'], 'pl': pl, 'g': ab.get('nivel') or 0,
                            'cic': ab.get('ciclo') if C > 1 and ab.get('passo') else 0, 'd': dg, 'cid': ab['cid']})
        _extrato(conta, u.get('tipo'), ab['cid'], j['mk'], ab['st'], pl, j['c'] + (' G%d' % ab['nivel'] if ab.get('nivel') else ''))
        W, L, tv, E = float(u.get('W') or 0), float(u.get('L') or 0), int(u.get('tv') or 0), float(u['E'])
        if tv and W > 0 and not u.get('travaOn') and s['pl'] >= max(W * tv / 100.0, E):
            u['travaOn'] = True
            self.op_log(conta, {'t': int(time.time()), 'aviso': '🔒 Trava de lucro armada: o próximo LOSS encerra a sessão.'})
        if W > 0 and s['pl'] >= W - 1e-9:
            self.para(conta, u, '🎯 META ATINGIDA: %s em %d entradas' % (f2(s['pl']), s['n']))
            return 'parou'
        if L > 0 and -s['pl'] >= L - 1e-9:
            self.para(conta, u, '⛔ STOP LOSS: %s' % f2(s['pl']))
            return 'parou'
        if not won and u.get('travaOn'):
            self.para(conta, u, '🔒 TRAVA DE LUCRO: o LOSS depois da trava encerrou com %s' % f2(s['pl']))
            return 'parou'
        if won:
            if g['passo']:
                self.op_log(conta, {'t': int(time.time()), 'aviso': '✅ WIN %s%s: recuperou e ficou %s na sequência' % (('no CICLO %d · ' % g['ciclo']) if C > 1 and g['ciclo'] > 1 else '', ('GALE %d' % g['nivel']) if g['nivel'] else 'entrada', f2(pl - g['perda']))})
            self.zera(u)
            u['prox'], u['fase'] = time.time() + 1.5, 'WIN %s · %s %s' % (j['c'], j['m'], f2(pl))
            return 'ok'
        g['passo'] += 1
        g['perda'] = r2(g['perda'] + ab['st'])
        g['ex'] = j['mk']
        if g['passo'] == 1:
            g['p0'] = j['p']
        if g['nivel'] < self.gef(u):
            g['nivel'] += 1
            u['fase'] = 'LOSS %s → %sGALE %d %s' % (f2(pl), ('CICLO %d · ' % g['ciclo']) if C > 1 else '', g['nivel'], 'com nova análise em outro mercado' if u.get('gm') == 'nova' else 'na mesma jogada')
            u['prox'] = time.time() + 0.8
            return 'ok'
        if g['ciclo'] < C:
            g['ciclo'] += 1
            g['nivel'], g['novo'] = 0, True
            u['prox'] = time.time() + int(u.get('Cp') or 0)
            self.op_log(conta, {'t': int(time.time()), 'aviso': '🔁 Perdeu o ciclo %d (−$%.2f): CICLO %d/%d depois da pausa e do HIT · a recuperação continua' % (g['ciclo'] - 1, g['perda'], g['ciclo'], C)})
            return 'ok'
        passo = g['passo']
        self.zera(u)
        if u.get('met') == 'seq':
            self.para(conta, u, '⛔ PERDAS CONSECUTIVAS: perdeu %d entrada(s) seguidas%s · %s' % (passo, (' (%d ciclos)' % C) if C > 1 else '', f2(s['pl'])))
            return 'parou'
        if u.get('Cf') == 'parar':
            self.para(conta, u, '⛔ PERDEU TUDO: %d entrada(s) seguidas%s · sessão parada (%s)' % (passo, (' nos %d ciclos' % C) if C > 1 else '', f2(s['pl'])))
            return 'parou'
        u['prox'], u['fase'] = time.time() + 1.5, 'LOSS · perdeu a sequência (%d entradas) · resetou' % passo
        return 'ok'


def register_nuvem_clique2(app):
    from flask import request, jsonify
    nv = NuvemClique2()

    def solta():
        EST['pausa'] = True
        try:
            if nv.kv.get(K_LIDER) == nv.eu:
                nv.kv.set(K_LIDER, '', ex=1)
        except Exception:
            pass
    atexit.register(solta)

    @app.before_request
    def _ncl2_garante():
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
        return {k: v for k, v in u.items() if k not in ('tok', 'pm')}

    @app.route('/api/nuvem-clique2/ligar', methods=['POST'])
    def _ncl2_ligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta, cf = str(d['conta']), d.get('cfg') or {}
        if nv.ligado(conta) or nv.cfg(conta).get('ab'):
            return jsonify({'ok': False, 'erro': 'o AUTO já está ligado na nuvem nesta conta'}), 400
        E = num(cf.get('E'), .35, 0.35, 5000)
        W, L = num(cf.get('W'), 0, 0, 1000000), num(cf.get('L'), 0, 0, 1000000)
        if not (W > 0 and L > 0):
            return jsonify({'ok': False, 'erro': 'coloque meta e stop loss antes de ligar o automático'}), 400
        if L < E:
            return jsonify({'ok': False, 'erro': 'o stop loss precisa ser pelo menos o valor da entrada'}), 400
        u = {'conta': conta, 'tok': str(d['token']).strip(), 'tipo': info['tipo'], 'moeda': info['moeda'], 'parado': '', 't_lig': int(time.time()),
             'E': E, 'W': W, 'L': L, 'tv': int(num(cf.get('tv'), 0, 0, 90)), 'k': int(num(cf.get('k'), 0, 0, 6)), 'kg': cf.get('kg') is not False,
             'G': int(num(cf.get('G'), 2, 0, 4)), 'gm': cf.get('gm') if cf.get('gm') in ('off', 'mesmo', 'nova') else 'nova',
             'met': 'seq' if cf.get('met') == 'seq' else 'trad', 'f': num(cf.get('f'), 0, 0, 5),
             'C': int(num(cf.get('C'), 1, 1, 10)), 'Cp': int(num(cf.get('Cp'), 0, 0, 900)), 'Cf': 'parar' if cf.get('Cf') == 'parar' else 'reset',
             'pm': nv.cfg(conta).get('pm') or {}, 'sess': {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0}, 'travaOn': False, 'prox': 0, 'erros': 0,
             'esp': None, 'an_t': 0, 'fase': 'ligando', 'saldo': float(info['saldo']) if info.get('saldo') is not None else None}
        nv.zera(u)
        nv.salva(conta, u)
        nv.kv.set(P + 'pmot:' + conta, '', ex=60)
        nv.liga(conta, True)
        Ls = nv.lista()
        if conta not in Ls:
            Ls.append(conta)
            nv.kv.jset(K_LISTA, Ls)
        nv.garante()
        nv.op_log(conta, {'t': int(time.time()), 'aviso': '🤖 AUTO LIGADO NA NUVEM · conta %s · entrada $%.2f · %s · meta $%.2f · stop $%.2f' % (
            info['tipo'].upper(), E, ('sem gale' if u['gm'] == 'off' or not u['G'] else '%d gale(s)%s' % (u['G'], (' · %d ciclos' % u['C']) if u['C'] > 1 else '')), W, L)})
        return jsonify({'ok': True, 'cfg': publico(u)})

    @app.route('/api/nuvem-clique2/desligar', methods=['POST'])
    def _ncl2_desligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        mot = 'AUTO desligado por você' + (' (a entrada aberta termina normalmente)' if u.get('ab') else '')
        nv.kv.set(P + 'pmot:' + conta, mot, ex=86400)
        nv.liga(conta, False)
        if u:
            u['parado'], u['t_parou'], u['fase'], u['esp'] = mot, int(time.time()), 'parado', None
            nv.salva(conta, u)
        nv.op_log(conta, {'t': int(time.time()), 'aviso': mot})
        return jsonify({'ok': True})

    @app.route('/api/nuvem-clique2/zerar', methods=['POST'])
    def _ncl2_zerar():   # NUVEM-CLIQUE2-ZERAR-V1
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        if u.get('ab') or (u.get('G_') or {}).get('passo'):
            return jsonify({'ok': False, 'erro': 'espere a entrada ou a recuperação (gale/ciclo) em andamento terminar para zerar'}), 400
        nv.kv.jset(P + 'ops:' + conta, [], ex=86400 * 30)
        if nv.ligado(conta):
            nv.kv.set(P + 'zerar:' + conta, '1', ex=60)
        elif u:
            u['sess'], u['travaOn'] = {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0}, False
            nv.salva(conta, u)
        nv.op_log(conta, {'t': int(time.time()), 'aviso': '🗑 Sessão zerada por você' + (' (o AUTO continua ligado: meta e stop contam a partir de agora)' if nv.ligado(conta) else '')})
        return jsonify({'ok': True})

    @app.route('/api/nuvem-clique2/estado', methods=['POST'])
    def _ncl2_estado():
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
        return jsonify({'ok': True, 'versao': VERSAO, 'cfg': publico(u) if u else None, 'ops': (nv.kv.jget(P + 'ops:' + conta, []) or [])[:int(num(d.get('n'), 60, 1, 200))],
                        'motor': time.time() - mt < 60, 'robo_idade': int(time.time() - float(h)) if h else None, 'saldo': info.get('saldo')})

    @app.route('/api/admin/nuvem-clique2', methods=['GET'])
    def _ncl2_admin():
        s = os.environ.get('ADMIN_SENHA', '')
        if not s or request.headers.get('X-Admin-Token') != s:
            return jsonify({'ok': False}), 403
        out = []
        for conta in nv.lista():
            u = nv.cfg(conta)
            out.append({'conta': conta[:3] + '…' + conta[-3:], 'tipo': u.get('tipo'), 'ligado': nv.ligado(conta), 'parado': u.get('parado'), 'sess': u.get('sess'), 'fase': u.get('fase')})
        return jsonify({'ok': True, 'versao': VERSAO, 'lider': nv.lider, 'pid': nv.pid, 'ws': EST['ws'], 'ticks': EST['ticks'], 'pessoas': out})

    log('%s registrada' % VERSAO)
    return nv
