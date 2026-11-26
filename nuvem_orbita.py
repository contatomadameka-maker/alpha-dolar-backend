# -*- coding: utf-8 -*-
"""NUVEM-ORBITA-V1 — Alpha Órbita: um agente no servidor que varre vários mercados de Volatility atrás de um sinal raro
(preço esticado da média + RSI no extremo + o último tick já virando) e entra em Sobe/Desce de 1 minuto CONTRA a esticada.
Uma operação por vez. Gale multiplicado (×M) ou exato, até G gales por ciclo, entrando logo depois da perda no mesmo mercado.
Ciclos: perdeu o ciclo, o gale NÃO zera; espera um sinal novo em OUTRO mercado e continua a recuperação (até C ciclos).
Teto da recuperação em % da banca (a perda do ciclo + a próxima entrada nunca passa dele).
Meta de lucro e perda máxima com teto real (nenhuma entrada passa do limite). Funciona com o celular fechado.

Rotas: POST /api/nuvem-orbita/ligar|desligar|estado {token, conta[, cfg]} · GET /api/admin/nuvem-orbita (X-Admin-Token)
"""
import os, json, time, math, uuid, threading, atexit, hashlib
from collections import deque
from datetime import datetime, timedelta, timezone

try:
    from nuvem_digitos import KV, Conexao, contas_do_token, log as _log
except Exception:   # pragma: no cover
    from backend.nuvem_digitos import KV, Conexao, contas_do_token, log as _log   # noqa

VERSAO = 'NUVEM-ORBITA-V1.1'  # V1.1 NUVEM-ORBITA-GALE-NOVA-V1: opção de gale com nova análise + placar imediato x nova análise
MERC = ['R_10', 'R_25', 'R_50', 'R_75', 'R_100', '1HZ10V', '1HZ25V', '1HZ50V', '1HZ75V', '1HZ100V']
NOME = {'R_10': 'Vol 10', 'R_25': 'Vol 25', 'R_50': 'Vol 50', 'R_75': 'Vol 75', 'R_100': 'Vol 100', '1HZ10V': 'Vol 10 (1s)',
        '1HZ25V': 'Vol 25 (1s)', '1HZ50V': 'Vol 50 (1s)', '1HZ75V': 'Vol 75 (1s)', '1HZ100V': 'Vol 100 (1s)'}
PADRAO = ['R_10', 'R_25', 'R_50', 'R_75', 'R_100', '1HZ25V']
WS_URLS = [u for u in [os.environ.get('SALA_WS_URL', '').strip(),
                       'wss://api.derivws.com/trading/v1/options/ws/public',
                       'wss://ws.derivws.com/websockets/v3?app_id=1089'] if u]
P = 'nuvem_orb:'
K_LISTA, K_LIDER, K_MOTOR = P + 'lista', P + 'lider', P + 'motor'
TICKS = {s: deque(maxlen=240) for s in MERC}   # (epoch, preço)
LTK = {}
EST = {'pausa': False, 'ws': '', 'ticks': 0}
BRT = timezone(timedelta(hours=-3))
# sensibilidade: desvio da média de 20 ticks (σ), RSI de 14 ticks (extremo) e pausa depois de um ciclo
SENS = {'preciso': (2.4, 85, 120), 'equilibrado': (2.1, 80, 60), 'rapido': (1.8, 75, 30)}
JAN, RSI_N = 20, 14
PAY0 = .80


def log(*a):
    _log('[Orbita]', *a)


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
        _ex(conta, tipo, cid, sym, stake, pl, 'orbita', 'Alpha Órbita', tp)
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


def leitura(sym, z_min, rsi_ext):
    """força do sinal (0–100) e o lado (CALL/PUT) quando o preço esticou da média, o RSI está no extremo e o último tick virou"""
    L = [q for (e, q) in list(TICKS.get(sym) or [])]
    if len(L) < max(JAN, RSI_N) + 2:
        return 0, None, 'juntando ticks'
    J = L[-JAN:]
    m = sum(J) / float(JAN)
    dp = math.sqrt(sum((x - m) ** 2 for x in J) / float(JAN)) or 1e-9
    z = (L[-1] - m) / dp
    g = p = 0.0
    for i in range(len(L) - RSI_N, len(L)):
        d = L[i] - L[i - 1]
        if d > 0:
            g += d
        else:
            p -= d
    rsi = 100.0 if p == 0 else 100 - 100 / (1 + g / p)
    lo = 100 - rsi_ext
    fz = min(1.0, abs(z) / z_min)
    fr = min(1.0, max(0.0, (rsi - 50) / (rsi_ext - 50))) if z > 0 else min(1.0, max(0.0, (50 - rsi) / (50 - lo)))
    forca = int(round(100 * (0.55 * fz + 0.45 * fr)))
    virou_baixo, virou_cima = L[-1] < L[-2], L[-1] > L[-2]
    tx = 'z %+.1fσ · RSI %d' % (z, round(rsi))
    if z >= z_min and rsi >= rsi_ext and virou_baixo:
        return max(forca, 95), 'PUT', 'esticou %.1fσ para cima · RSI %d · virou' % (z, round(rsi))
    if z <= -z_min and rsi <= lo and virou_cima:
        return max(forca, 95), 'CALL', 'esticou %.1fσ para baixo · RSI %d · virou' % (-z, round(rsi))
    return min(forca, 94), None, tx


class NuvemOrbita(object):
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

    def dias(self, conta):
        out, hoje = [], datetime.now(BRT).date()
        for i in range(6, -1, -1):
            d = hoje - timedelta(days=i)
            try:
                v = float(self.kv.get(P + 'dia:' + conta + ':' + d.strftime('%Y-%m-%d')) or 0)
            except Exception:
                v = 0.0
            out.append([d.strftime('%d/%m'), r2(v)])
        return out

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
                ws = websocket.create_connection(url, timeout=15, origin='https://alphadolar.online', header=['User-Agent: Mozilla/5.0 (AlphaOrbita nuvem)'])
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
                    T.append((ep, float(t['quote'])))
                    EST['ticks'] += 1
                    LTK[sym] = time.time()
                    EST.setdefault('vistos', set()).add(sym)
                    if EST['ticks'] % 50 == 0:
                        self.kv.set(K_MOTOR, str(int(time.time())), ex=60)
                        try:
                            self.kv.jset(P + 'px', {s: [round(q, 4) for (e, q) in list(TICKS[s])[-40:]] for s in MERC}, ex=120)
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
                        if (self.ligado(conta) or self.cfg(conta).get('ab')) and (t is None or not t.is_alive()):   # NUVEM-ORBITA-AB-V1: termina o contrato aberto mesmo depois de encerrar
                            t = threading.Thread(target=self.trabalha, args=(conta,), daemon=True)
                            self.trab[conta] = t
                            t.start()
            except Exception as e:
                log('vigia', e)
            time.sleep(4)

    # ---------- o agente ----------
    def para(self, conta, u, motivo):
        self.liga(conta, False)
        u['parado'], u['t_parou'], u['fase'] = motivo, int(time.time()), 'parado'
        self.salva(conta, u)
        self.op_log(conta, {'t': int(time.time()), 'aviso': motivo})
        log('%s…%s parado: %s' % (conta[:3], conta[-3:], motivo))

    def trabalha(self, conta):
        c, hb, sb, ult, tf = None, 0, 0, 0, 0
        u = self.cfg(conta)
        while (self.ligado(conta) or u.get('ab')) and not EST['pausa'] and self.lider:
            try:
                if not u:
                    return
                if c is None or c.tok != u.get('tok'):
                    c = Conexao(u.get('tok', ''), conta)
                mudou = False
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
                elif self.ligado(conta):
                    t = max([TICKS[s][-1][0] for s in u['mks'] if TICKS.get(s)] or [0])
                    if t > ult:
                        ult = t
                        mudou = self.procura(conta, c, u) or mudou
                if mudou or time.time() - tf > 3:
                    tf = time.time()
                    u['t_upd'] = int(time.time())
                    self.salva(conta, u)
                else:
                    time.sleep(0.1)
                if not self.ligado(conta) and not u.get('ab'):
                    break
            except PermissionError:
                return self.para(conta, u, 'SUA SESSÃO NA DERIV EXPIROU: abra o Alpha Órbita e ligue de novo')
            except Exception as ex:
                log('trabalha', conta[-3:], ex)
                time.sleep(1.5)
        if u and not self.ligado(conta):
            pm = self.kv.get(P + 'pmot:' + conta)
            if pm:
                u['parado'], u['t_parou'], u['fase'] = pm, int(time.time()), 'parado'
            self.salva(conta, u)

    def procura(self, conta, c, u):
        zmin, rext, pausa = SENS.get(u.get('sens')) or SENS['equilibrado']
        fz, melhor = {}, None
        for s in u['mks']:
            f, lado, tx = leitura(s, zmin, rext)
            fz[s] = f
            if lado and (melhor is None or f > melhor[0]):
                melhor = (f, s, lado, tx)
        u['forca'] = fz
        vb = u.get('vab')   # NUVEM-ORBITA-HIT-V1: entrada virtual (sem dinheiro) de 1 minuto
        if vb:
            T = TICKS.get(vb['mk'])
            falta = int(float(vb['t']) + 60 - time.time())
            if falta > 0 or not T:
                u['alvo'] = None
                u['fase'] = 'HIT · entrada VIRTUAL (sem dinheiro): %s %s · resultado em %d s · %d/%d' % ('Aumento' if vb['lado'] == 'CALL' else 'Queda', NOME[vb['mk']], max(0, falta), int(u.get('hseq') or 0), int(u.get('hit') or 0))
                return True
            px = float(T[-1][1])
            ganhou = px > float(vb['p0']) if vb['lado'] == 'CALL' else px < float(vb['p0'])
            quer = u.get('hitm') == 'win'
            u['hseq'] = (int(u.get('hseq') or 0) + 1) if ganhou == quer else 0
            u['vab'] = None
            hit = int(u.get('hit') or 0)
            self.op_log(conta, {'t': int(time.time()), 'aviso': '👻 HIT virtual em %s: %s · %d/%d %s seguido(s)%s' % (NOME[vb['mk']], 'WIN' if ganhou else 'LOSS', u['hseq'], hit, 'WIN' if quer else 'LOSS', ' → a próxima entrada é REAL' if u['hseq'] >= hit else '')})
            return True
        ec = u.get('espc')   # NUVEM-ORBITA-CONF-V1: espera N ticks seguidos do outro lado antes de entrar
        if ec:
            nc = int(u.get('conf') or 0)
            for (e, p) in list(TICKS.get(ec['mk']) or []):
                if e > ec['ue']:
                    contra = float(p) < ec['up'] if ec['lado'] == 'CALL' else float(p) > ec['up']
                    ec['n'] = ec['n'] + 1 if contra else 0
                    ec['ue'], ec['up'] = e, float(p)
            if ec['n'] >= nc:
                u['espc'] = None
                self.op_log(conta, {'t': int(time.time()), 'aviso': '✔ %s: vieram %d tick(s) seguidos do outro lado → entra' % (NOME[ec['mk']], nc)})
                return self.entra_novo(conta, c, u, ec['mk'], ec['lado'], ec['tx'])
            if time.time() - float(ec['t']) > 45:
                u['espc'] = None
                self.op_log(conta, {'t': int(time.time()), 'aviso': '⏱ %s: em 45 s não vieram %d tick(s) seguidos do outro lado · sinal descartado' % (NOME[ec['mk']], nc)})
                return True
            u['alvo'] = None
            u['fase'] = 'sinal em %s → %s · esperando %d tick(s) seguidos do outro lado: %d/%d' % (NOME[ec['mk']], 'Aumento' if ec['lado'] == 'CALL' else 'Queda', nc, ec['n'], nc)
            return True
        if time.time() < float(u.get('prox') or 0):
            u['fase'] = 'pausa depois do ciclo: volta a varrer em %d s' % max(1, int(float(u['prox']) - time.time()))
            return True
        gn = u.get('ciclo')
        if gn and gn.get('espg'):   # NUVEM-ORBITA-GALE-NOVA-V1
            if not melhor:
                top = max(fz, key=fz.get) if fz else None
                u['alvo'] = None
                u['fase'] = 'gale %d ($%.2f a recuperar): esperando nova análise · %d s' % (gn['nivel'], gn['perda'], int(time.time() - float(gn.get('tg') or time.time()))) + (' · mais perto: %s %d%%' % (NOME[top], fz[top]) if top else '')
                return True
            f, s, lado, tx = melhor
            gn.update({'mk': s, 'lado': lado, 'espg': False})
            u['alvo'], u['sinal'] = s, '%s %s' % (NOME[s], tx)
            self.op_log(conta, {'t': int(time.time()), 'aviso': '🛰 Gale %d com nova análise: sinal em %s (%s) → %s' % (gn['nivel'], NOME[s], tx, 'Aumento' if lado == 'CALL' else 'Queda')})
            self.compra(conta, c, u)
            return True
        if not melhor:
            top = max(fz, key=fz.get) if fz else None
            u['fase'] = 'varrendo %d mercados · aguardando sinal' % len(u['mks']) + (' · mais perto: %s %d%%' % (NOME[top], fz[top]) if top else '')
            u['alvo'] = None
            return True
        g0 = u.get('ciclo')
        if g0 and g0.get('esp'):   # ciclo novo da recuperação: outro mercado, se houver sinal nele
            cand = None
            for m in u['mks']:
                if m == g0.get('ex'):
                    continue
                f2, l2, t2 = leitura(m, zmin, rext)
                if l2 and (cand is None or f2 > cand[0]):
                    cand = (f2, m, l2, t2)
            if not cand:
                u['fase'] = 'ciclo %d de %d da recuperação ($%.2f): esperando sinal em outro mercado (fora %s)' % (g0['cic'], int(u.get('C') or 1), g0['perda'], NOME.get(g0.get('ex'), '?'))
                return True
            f, s, lado, tx = cand
            g0.update({'mk': s, 'lado': lado, 'esp': False})
            u['alvo'], u['sinal'] = s, '%s %s' % (NOME[s], tx)
            self.op_log(conta, {'t': int(time.time()), 'aviso': '🛰 Ciclo %d: sinal em %s (%s) → %s · continua a recuperação de $%.2f' % (g0['cic'], NOME[s], tx, 'Aumento' if lado == 'CALL' else 'Queda', g0['perda'])})
            self.compra(conta, c, u)
            return True
        f, s, lado, tx = melhor
        nc = int(u.get('conf') or 0)
        if nc > 0:   # NUVEM-ORBITA-CONF-V1
            T = TICKS.get(s)
            if T:
                u['espc'] = {'mk': s, 'lado': lado, 'tx': tx, 't': time.time(), 'ue': T[-1][0], 'up': float(T[-1][1]), 'n': 0}
                u['alvo'] = None
                self.op_log(conta, {'t': int(time.time()), 'aviso': '🛰 Sinal em %s (%s) → %s · esperando %d tick(s) seguidos do outro lado' % (NOME[s], tx, 'Aumento' if lado == 'CALL' else 'Queda', nc)})
            return True
        return self.entra_novo(conta, c, u, s, lado, tx)

    def entra_novo(self, conta, c, u, s, lado, tx):
        hit = int(u.get('hit') or 0)
        if hit > 0 and int(u.get('hseq') or 0) < hit:   # NUVEM-ORBITA-HIT-V1: antes de cada ciclo novo, espera N resultados virtuais
            T = TICKS.get(s)
            if T:
                u['vab'] = {'mk': s, 'lado': lado, 'p0': float(T[-1][1]), 't': time.time()}
                u['alvo'] = None
                self.op_log(conta, {'t': int(time.time()), 'aviso': '👻 HIT: sinal em %s (%s) → %s VIRTUAL, sem dinheiro · esperando %d %s seguido(s)' % (NOME[s], tx, 'Aumento' if lado == 'CALL' else 'Queda', hit, 'WIN' if u.get('hitm') == 'win' else 'LOSS')})
            return True
        u['hseq'] = 0
        u['alvo'] = s
        u['sinal'] = '%s %s' % (NOME[s], tx)
        self.op_log(conta, {'t': int(time.time()), 'aviso': '🛰 Sinal em %s: %s → %s' % (NOME[s], tx, 'Aumento' if lado == 'CALL' else 'Queda')})
        u['ciclo'] = {'nivel': 0, 'perda': 0.0, 'base': self.base(u), 'mk': s, 'lado': lado, 'cic': 1, 'esp': False}
        self.compra(conta, c, u)
        return True

    def gcmp(self, conta, u, rec, pl):   # NUVEM-ORBITA-GALE-NOVA-V1: placar dos gales (imediato x nova análise)
        try:
            k = P + 'gcmp:' + conta
            d = self.kv.jget(k, {}) or {}
            m = d.setdefault('nova' if u.get('gan') == 'nova' else 'imediato', {'rec': 0, 'perd': 0, 'pl': 0.0})
            m['rec' if rec else 'perd'] += 1
            m['pl'] = r2(float(m['pl']) + pl)
            self.kv.jset(k, d, ex=86400 * 90)
        except Exception:
            pass

    def base(self, u):
        return r2(max(0.35, float(u['E'])))

    def stake(self, u):
        g = u['ciclo']
        if not g['nivel']:
            return g['base']
        if u.get('modo') == 'exata':
            a = float((u.get('pm') or {}).get(g['lado']) or PAY0)
            return max(0.35, ceil2((g['perda'] + g['base'] * a) / a))
        return max(0.35, r2(g['base'] * math.pow(float(u.get('M') or 2.3), g['nivel'])))

    def compra(self, conta, c, u):
        g, s = u['ciclo'], u.setdefault('sess', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'cw': 0, 'cl': 0})
        st = self.stake(u)
        L = float(u.get('L') or 0)
        if L > 0 and -s['pl'] + st > L + 1e-9:
            if g['nivel']:
                self.op_log(conta, {'t': int(time.time()), 'aviso': '🛡 O gale %d ($%.2f) passaria da perda máxima: assumiu −$%.2f e encerrou o ciclo.' % (g['nivel'], st, g['perda'])})
                s['cl'] += 1
                u['ciclo'], u['prox'] = None, time.time() + 30
                if L > 0 and -s['pl'] + g['base'] > L + 1e-9:
                    return self.para(conta, u, 'PERDA MÁXIMA: a próxima entrada passaria do limite de $%.2f · resultado %s$%.2f' % (L, '+' if s['pl'] >= 0 else '−', abs(s['pl'])))
                return
            return self.para(conta, u, 'PERDA MÁXIMA: a próxima entrada passaria do limite de $%.2f · resultado %s$%.2f' % (L, '+' if s['pl'] >= 0 else '−', abs(s['pl'])))
        tt, b0 = float(u.get('teto') or 0), float(u.get('banca0') or 0)
        if g['nivel'] and tt > 0 and b0 > 0 and g['perda'] + st > b0 * tt / 100.0 + 1e-9:
            self.op_log(conta, {'t': int(time.time()), 'aviso': '🛡 A recuperação passaria do teto de %d%% da banca ($%.2f): assumiu −$%.2f e voltou à entrada.' % (tt, b0 * tt / 100.0, g['perda'])})
            s['cl'] += 1
            u['ciclo'], u['prox'] = None, time.time() + 30
            return
        if u.get('saldo') is not None and st > float(u['saldo']) + 1e-9:
            return self.para(conta, u, 'PARADO: saldo insuficiente para a entrada de $%.2f' % st)
        prm = {'contract_type': g['lado'], 'amount': st, 'basis': 'stake', 'currency': u.get('moeda') or 'USD', 'duration': 1, 'duration_unit': 'm'}
        prm[c.symkey] = g['mk']
        r = c.req({'buy': 1, 'price': st, 'parameters': prm}, 10)
        msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error') and ('symbol' in msg.lower() or 'Properties not allowed' in msg or 'validation' in msg.lower()):
            prm.pop(c.symkey, None)
            c.symkey = 'symbol' if c.symkey == 'underlying_symbol' else 'underlying_symbol'
            prm[c.symkey] = g['mk']
            r = c.req({'buy': 1, 'price': st, 'parameters': prm}, 10)
            msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error'):
            u['erros'] = int(u.get('erros') or 0) + 1
            self.op_log(conta, {'t': int(time.time()), 'aviso': 'A Deriv recusou a entrada: ' + msg[:120]})
            if u['erros'] >= 3 or 'balance' in msg.lower() or 'insufficient' in msg.lower():
                return self.para(conta, u, 'PARADO: a Deriv recusou (%s)' % msg[:90])
            u['ciclo'], u['prox'] = None, time.time() + 10
            return
        b = r.get('buy') or {}
        u['erros'] = 0
        try:
            p = float(b.get('payout')) / float(b.get('buy_price')) - 1
            if 0.3 < p < 1.2:
                u.setdefault('pm', {})[g['lado']] = p
        except Exception:
            pass
        u['ab'] = {'cid': b.get('contract_id'), 'st': float(b.get('buy_price') or st), 'lado': g['lado'], 'mk': g['mk'], 't': time.time(), 'nivel': g['nivel']}
        u['fase'] = 'operação em andamento · %s %s $%.2f%s' % ('Aumento' if g['lado'] == 'CALL' else 'Queda', NOME[g['mk']], u['ab']['st'], (' · GALE %d' % g['nivel']) if g['nivel'] else '')

    def confere(self, conta, c, u):
        ab = u['ab']
        if time.time() - float(ab['t']) < 61 or time.time() - float(ab.get('ult') or 0) < 1.5:
            return None
        ab['ult'] = time.time()
        try:
            q = c.req({'proposal_open_contract': 1, 'contract_id': ab['cid']}, 5).get('proposal_open_contract') or {}
        except PermissionError:
            raise
        except Exception:
            q = {}
        if not (q.get('is_sold') or q.get('status') in ('won', 'lost', 'sold')):
            if time.time() - float(ab['t']) > 240:
                u.pop('ab', None)
                u['ciclo'] = None
                self.op_log(conta, {'t': int(time.time()), 'aviso': 'a Deriv não confirmou o contrato %s: confira no histórico da Deriv' % ab['cid']})
                return 'ok'
            return None
        u.pop('ab', None)
        if not self.kv.setnx(P + 'contou:%s' % ab['cid'], '1', 86400 * 3):
            return 'ok'
        pl = r2(float(q.get('profit') or 0))
        won = pl > 0
        s, g = u.setdefault('sess', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'cw': 0, 'cl': 0}), u.get('ciclo') or {'nivel': 0, 'perda': 0.0, 'base': self.base(u), 'mk': ab['mk'], 'lado': ab['lado']}
        s['pl'], s['n'] = r2(s['pl'] + pl), s['n'] + 1
        self.dia(conta, pl)
        tipo = 'Aumento' if ab['lado'] == 'CALL' else 'Queda'
        self.op_log(conta, {'t': int(time.time()), 'mk': ab['mk'], 'nome': NOME[ab['mk']], 'tipo': tipo, 'st': ab['st'], 'pl': pl, 'g': ab.get('nivel') or 0, 'cid': ab['cid']})
        _extrato(conta, u.get('tipo'), ab['cid'], ab['mk'], ab['st'], pl, tipo + (' G%d' % ab['nivel'] if ab.get('nivel') else ''))
        _, _, pausa = SENS.get(u.get('sens')) or SENS['equilibrado']
        W, L = float(u.get('W') or 0), float(u.get('L') or 0)
        if won and int(g.get('nivel') or 0) > 0:
            self.gcmp(conta, u, True, pl - float(g.get('perda') or 0))
        if won:
            s['w'] += 1
            s['cw'] += 1
            u['ciclo'], u['prox'] = None, time.time() + pausa
            u['fase'] = 'WIN %s · %s +$%.2f' % (tipo, NOME[ab['mk']], pl)
            tv = int(u.get('trava') or 0)   # NUVEM-ORBITA-TRAVA-V1: arma quando passa da % da meta e o lucro cobre uma entrada
            if tv and W > 0 and not u.get('travaOn') and s['pl'] >= max(W * tv / 100.0, self.base(u)) - 1e-9:
                u['travaOn'] = True
                self.op_log(conta, {'t': int(time.time()), 'aviso': '🔒 Trava de lucro ligada: passou de %d%% da meta (+$%.2f). Se vier um LOSS, o robô para e segura o lucro.' % (tv, s['pl'])})
        else:
            s['l'] += 1
            if u.get('travaOn'):   # NUVEM-ORBITA-TRAVA-V1
                u['ciclo'] = None
                self.para(conta, u, 'TRAVA DE LUCRO: perdeu depois de passar de %d%% da meta · resultado %s$%.2f' % (int(u.get('trava') or 0), '+' if s['pl'] >= 0 else '−', abs(s['pl'])))
                return 'parou'
            g['perda'] = r2(float(g['perda']) + ab['st'])
            T, C = int(u.get('G') or 0) + 1, max(1, int(u.get('C') or 1))
            g['nivel'] = int(g['nivel']) + 1
            g.setdefault('cic', 1)
            if g['nivel'] % T and u.get('gan') == 'nova':   # NUVEM-ORBITA-GALE-NOVA-V1: espera o radar confirmar um sinal de novo
                g.update({'espg': True, 'tg': time.time()})
                u['ciclo'] = g
                u['fase'] = 'gale %d ($%.2f a recuperar): esperando nova análise do radar' % (g['nivel'], g['perda'])
                self.op_log(conta, {'t': int(time.time()), 'aviso': '🔎 LOSS em %s: o gale %d espera o radar achar um sinal de novo (nova análise)' % (NOME[ab['mk']], g['nivel'])})
            elif g['nivel'] % T:   # ainda tem gale neste ciclo: entra já, no mesmo mercado
                if u.get('inv', True):
                    g['lado'] = 'PUT' if g['lado'] == 'CALL' else 'CALL'
                u['ciclo'] = g
                if not (L > 0 and -s['pl'] >= L - 1e-9):
                    self.compra(conta, c, u)
                    return 'parou' if not self.ligado(conta) else 'ok'
            elif g['cic'] < C:   # perdeu o ciclo: o gale continua no próximo ciclo, com sinal novo em outro mercado
                g.update({'cic': g['cic'] + 1, 'esp': True, 'ex': ab['mk']})
                u['ciclo'], u['prox'] = g, time.time() + int(u.get('cP') or 0)
                u['fase'] = 'ciclo %d perdido (−$%.2f) · o gale continua no ciclo %d/%d em outro mercado' % (g['cic'] - 1, g['perda'], g['cic'], C)
                self.op_log(conta, {'t': int(time.time()), 'aviso': '🔁 Ciclo %d perdido em %s (−$%.2f): a recuperação continua no ciclo %d de %d, com sinal novo em outro mercado.' % (g['cic'] - 1, NOME[ab['mk']], g['perda'], g['cic'], C)})
            else:
                s['cl'] += 1
                if int(g.get('nivel') or 0) > 1 or T > 1:
                    self.gcmp(conta, u, False, -float(g.get('perda') or 0))
                u['ciclo'], u['prox'] = None, time.time() + pausa
                u['fase'] = 'LOSS: perdeu %s · −$%.2f' % (('os %d ciclos' % C) if C > 1 else 'o ciclo', g['perda'])
                if u.get('cFim') == 'parar' and C > 1:
                    self.para(conta, u, 'PAROU: perdeu os %d ciclos de gale, como você escolheu · resultado %s$%.2f' % (C, '+' if s['pl'] >= 0 else '−', abs(s['pl'])))
                    return 'parou'
        if W > 0 and s['pl'] >= W - 1e-9 and not u.get('ciclo'):
            self.para(conta, u, 'META BATIDA: +$%.2f em %d entradas' % (s['pl'], s['n']))
            return 'parou'
        if L > 0 and -s['pl'] >= L - 1e-9:
            self.para(conta, u, 'PERDA MÁXIMA de $%.2f atingida · resultado −$%.2f' % (L, abs(s['pl'])))
            return 'parou'
        return 'ok'


def register_nuvem_orbita(app):
    from flask import request, jsonify
    nv = NuvemOrbita()

    def solta():
        EST['pausa'] = True
        try:
            if nv.kv.get(K_LIDER) == nv.eu:
                nv.kv.set(K_LIDER, '', ex=1)
        except Exception:
            pass
    atexit.register(solta)

    @app.before_request
    def _nor_garante():
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

    @app.route('/api/nuvem-orbita/ligar', methods=['POST'])
    def _nor_ligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta, cf = str(d['conta']), d.get('cfg') or {}
        u0 = nv.cfg(conta); ab0 = u0.get('ab')   # NUVEM-ORBITA-AB-V1
        if ab0 and not nv.ligado(conta) and time.time() - float(ab0.get('t') or 0) > 300:
            u0.pop('ab', None)
            u0['ciclo'] = None
            nv.salva(conta, u0)
            nv.op_log(conta, {'t': int(time.time()), 'aviso': 'o contrato %s ficou sem resultado depois de encerrar: confira no histórico da Deriv' % ab0.get('cid')})
            ab0 = None
        if nv.ligado(conta):
            return jsonify({'ok': False, 'erro': 'o Órbita já está ligado nesta conta (encerre antes)'}), 400
        if ab0:
            return jsonify({'ok': False, 'erro': 'o Órbita está terminando o último contrato (%s). Espere cerca de 1 minuto e ligue de novo.' % NOME.get(ab0.get('mk'), '')}), 400
        if str(info.get('tipo')) == 'real':
            nvp = _nivel_plano(str(d.get('token') or ''))
            if nvp is None:
                return jsonify({'ok': False, 'erro': 'não consegui confirmar o seu plano agora; tente de novo em instantes'}), 503
            if nvp < 2:
                return jsonify({'ok': False, 'erro': 'Na conta real o Alpha Órbita exige o plano Pro (ou superior). Na demo é liberado.'}), 403
        mks = [m for m in (cf.get('mks') or PADRAO) if m in MERC][:10] or PADRAO
        E = num(cf.get('E'), 1, 0.35, 5000)
        L = num(cf.get('L'), 0, 0, 1000000)
        if not L > 0:
            return jsonify({'ok': False, 'erro': 'coloque a perda máxima antes de ligar'}), 400
        if L < E:
            return jsonify({'ok': False, 'erro': 'a perda máxima precisa ser pelo menos o valor da entrada'}), 400
        u = {'conf': int(num(cf.get('conf'), 0, 0, 5)), 'espc': None,   # NUVEM-ORBITA-CONF-V1
             'gan': 'nova' if cf.get('gan') == 'nova' else 'imediato',   # NUVEM-ORBITA-GALE-NOVA-V1
             'hit': int(num(cf.get('hit'), 0, 0, 5)), 'hitm': 'win' if cf.get('hitm') == 'win' else 'loss', 'hseq': 0, 'vab': None,   # NUVEM-ORBITA-HIT-V1
             'trava': int(num(cf.get('trava'), 0, 0, 90)), 'travaOn': False,   # NUVEM-ORBITA-TRAVA-V1: trava de lucro (% da meta)
             'conta': conta, 'tok': str(d['token']).strip(), 'tipo': info['tipo'], 'moeda': info['moeda'], 'parado': '', 't_lig': int(time.time()),
             'mks': mks, 'E': E, 'W': num(cf.get('W'), 0, 0, 1000000), 'L': L, 'modo': 'exata' if cf.get('modo') == 'exata' else 'mult',
             'M': num(cf.get('M'), 2.3, 1.2, 5), 'G': int(num(cf.get('G'), 2, 0, 5)), 'inv': cf.get('inv') is not False,
             'sens': cf.get('sens') if cf.get('sens') in SENS else 'equilibrado', 'pm': nv.cfg(conta).get('pm') or {},
             'C': int(num(cf.get('C'), 1, 1, 10)), 'cP': int(num(cf.get('cP'), 0, 0, 900)), 'cFim': 'parar' if cf.get('cFim') == 'parar' else 'reset',
             'teto': int(num(cf.get('teto'), 0, 0, 90)), 'banca0': float(info['saldo']) if info.get('saldo') is not None else 0,
             'sess': {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'cw': 0, 'cl': 0}, 'ciclo': None, 'prox': 0, 'erros': 0, 'fase': 'ligando',
             'saldo': float(info['saldo']) if info.get('saldo') is not None else None}
        nv.salva(conta, u)
        nv.kv.set(P + 'pmot:' + conta, '', ex=60)
        nv.liga(conta, True)
        Ls = nv.lista()
        if conta not in Ls:
            Ls.append(conta)
            nv.kv.jset(K_LISTA, Ls)
        nv.garante()
        nv.op_log(conta, {'t': int(time.time()), 'aviso': 'ÓRBITA LIGADO na conta %s · %s · entrada $%.2f · %s até %d gale(s) · meta %s · perda máxima $%.2f' % (
            info['tipo'].upper(), ', '.join(NOME[m] for m in mks), E, ('exato' if u['modo'] == 'exata' else '×%.1f' % u['M']), u['G'],
            ('$%.2f' % u['W']) if u['W'] else 'sem', L)})
        return jsonify({'ok': True, 'cfg': publico(u)})

    @app.route('/api/nuvem-orbita/desligar', methods=['POST'])
    def _nor_desligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        mot = 'encerrado por você' + (' (o contrato aberto termina normalmente)' if u.get('ab') else '')
        nv.kv.set(P + 'pmot:' + conta, mot, ex=86400)
        nv.liga(conta, False)
        if u:
            u['parado'], u['t_parou'], u['fase'] = mot, int(time.time()), 'parado'
            nv.salva(conta, u)
        nv.op_log(conta, {'t': int(time.time()), 'aviso': 'ÓRBITA ENCERRADO por você'})
        return jsonify({'ok': True})

    @app.route('/api/nuvem-orbita/limpar', methods=['POST'])
    def _nor_limpar():   # NUVEM-ORBITA-LIMPAR-V1: lixeira das últimas ações e dos últimos 7 dias
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta, o = str(d['conta']), d.get('o')
        if o == 'ops':
            nv.kv.jset(P + 'ops:' + conta, [], ex=86400 * 30)
        elif o == 'dias':
            hoje = datetime.now(BRT).date()
            for i in range(10):
                nv.kv.set(P + 'dia:' + conta + ':' + (hoje - timedelta(days=i)).strftime('%Y-%m-%d'), '0', ex=86400 * 10)
        else:
            return jsonify({'ok': False, 'erro': 'opção inválida'}), 400
        return jsonify({'ok': True})

    @app.route('/api/nuvem-orbita/estado', methods=['POST'])
    def _nor_estado():
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
                        'dias': nv.dias(conta), 'px': nv.kv.jget(P + 'px', {}) or {}, 'motor': time.time() - mt < 60,
                        'robo_idade': int(time.time() - float(h)) if h else None, 'saldo': info.get('saldo'),
                        'gcmp': nv.kv.jget(P + 'gcmp:' + conta, {}) or {}})

    @app.route('/api/admin/nuvem-orbita', methods=['GET'])
    def _nor_admin():
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
