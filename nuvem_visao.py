# -*- coding: utf-8 -*-
"""NUVEM-VISAO-V1 — Alpha Visão: a IA lê o gráfico de velas de 1 minuto de vários mercados (Topo e Fundo, Médias Móveis 9/21,
Fibonacci, Tendência e RSI), mostra o voto de cada indicador, escolhe o mercado com mais confluência e entra em Sobe/Desce
de 5 ticks na hora. Gale automático (perdeu: analisa de novo e entra no gale), ciclos, teto da recuperação, meta e perda
máxima com teto real. Três jeitos de operar:
  - 'ia'     : um clique = um ciclo (análise → entrada → gales até ganhar ou acabar os gales) e para;
  - 'nuvem'  : fica operando sozinho no servidor até a meta ou a perda máxima (pode fechar a página);
  - 'manual' : a pessoa escolhe Compra/Venda e o mercado; uma entrada de 5 ticks.
A sessão (resultado, meta e perda máxima) continua entre os cliques até bater a meta/perda ou a pessoa zerar.

Rotas: POST /api/nuvem-visao/ligar|desligar|estado|zerar {token, conta[, cfg]} · GET /api/admin/nuvem-visao (X-Admin-Token)
"""
import os, json, time, math, uuid, threading, atexit, hashlib
from collections import deque
from datetime import datetime, timedelta, timezone

try:
    from nuvem_digitos import KV, Conexao, contas_do_token, log as _log
except Exception:   # pragma: no cover
    from backend.nuvem_digitos import KV, Conexao, contas_do_token, log as _log   # noqa

VERSAO = 'NUVEM-VISAO-V3.3'  # V3.3: 300 velas (5 h) + laboratório 12/24/48 h com a linha de 2h30 ·  # V3.2: mostra qual filtro segurou a entrada ·   # V3.1: gale imediato, tempo de análise, tendência longa, gatilho MM9, laboratório ·   # V3: indicadores alinhados (todos a favor da tendência, quase sem NEUTRO) + entrada só no tick a favor + placar novo
VERSAO_V27 = 'NUVEM-VISAO-V2.7'   # V2.7: a trava só arma quando o lucro cobre uma entrada (não para no negativo) e confere de novo antes de parar
VERSAO_V26 = 'NUVEM-VISAO-V2.6'   # V2.6: encerrar com o robô já parado não apaga o motivo (a trava não volta na sessão nova)
VERSAO_V25 = 'NUVEM-VISAO-V2.5'   # V2.5: lixeira do histórico
VERSAO_V24 = 'NUVEM-VISAO-V2.4'   # V2.4: quantidade de gale por ciclo escolhida pela pessoa + opção de trocar de mercado depois do LOSS
VERSAO_ANT = 'NUVEM-VISAO-V2.1'   # V2: quantidade de WIN no modo IA, HIT (entradas virtuais antes da real), análise completa em cada gale
MERC = ['R_10', 'R_25', 'R_50', 'R_75', 'R_100', '1HZ10V', '1HZ25V', '1HZ50V', '1HZ75V', '1HZ100V']
NOME = {'R_10': 'Vol 10', 'R_25': 'Vol 25', 'R_50': 'Vol 50', 'R_75': 'Vol 75', 'R_100': 'Vol 100', '1HZ10V': 'Vol 10 (1s)',
        '1HZ25V': 'Vol 25 (1s)', '1HZ50V': 'Vol 50 (1s)', '1HZ75V': 'Vol 75 (1s)', '1HZ100V': 'Vol 100 (1s)'}
PADRAO = ['1HZ25V', 'R_100', 'R_50', '1HZ75V', 'R_10', 'R_25']
WS_URLS = [u for u in [os.environ.get('SALA_WS_URL', '').strip(),
                       'wss://api.derivws.com/trading/v1/options/ws/public',
                       'wss://ws.derivws.com/websockets/v3?app_id=1089'] if u]
P = 'nuvem_vis:'
K_LISTA, K_LIDER, K_MOTOR = P + 'lista', P + 'lider', P + 'motor'
NV = 300                                   # velas de 1 minuto guardadas por mercado
VELAS = {s: deque(maxlen=NV) for s in MERC}   # [t, o, h, l, c]
TICKS = {s: deque(maxlen=60) for s in MERC}   # (epoch, preço)
LTK = {}
EST = {'pausa': False, 'ws': '', 'ticks': 0, 'hist': {}}
BRT = timezone(timedelta(hours=-3))
INDS = ['tf', 'mm', 'fb', 'td', 'rsi']
NIND = {'tf': 'Topo e Fundo', 'mm': 'Médias Móveis', 'fb': 'Fibonacci', 'td': 'Tendência', 'rsi': 'RSI'}
MODOS = {'conservador': 1, 'moderado': 2, 'agressivo': 4}
PAY0 = .80
T_ANALISE, T_ANALISE_GALE = 7.0, 6.0       # segundos de análise mostrados na tela antes de entrar


def log(*a):
    _log('[Visao]', *a)


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
        _ex(conta, tipo, cid, sym, stake, pl, 'visao', 'Alpha Visão', tp)
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


# ---------------- análise do gráfico (a mesma conta é desenhada na página) ----------------
def _mm(cs, n):
    out, s = [], 0.0
    for i, v in enumerate(cs):
        s += v[4]
        if i >= n:
            s -= cs[i - n][4]
        out.append(s / n if i >= n - 1 else None)
    return out


def analisa(cs):
    """NUVEM-VISAO-V3: os 5 indicadores leem a MESMA coisa (a favor da tendência), quase sem NEUTRO:
    Topo e Fundo = estrutura (topos e fundos subindo ou descendo) · Médias 9/21 · Fibonacci da última perna
    (a correção ainda respeita a perna?) · Tendência (inclinação de 30 velas) · RSI como força (acima/abaixo de 50,
    neutro só no exagero, acima de 80 ou abaixo de 20, para não comprar o topo nem vender o fundo)."""
    if len(cs) < 40:
        return None
    hi, lo, ih, il = -1e18, 1e18, 0, 0
    for i, v in enumerate(cs):
        if v[2] > hi:
            hi, ih = v[2], i
        if v[3] < lo:
            lo, il = v[3], i
    k = len(cs) - 1
    p = cs[k][4]
    m9, m21 = _mm(cs, 9), _mm(cs, 21)
    pos = (p - lo) / ((hi - lo) or 1e-9)
    n = 30
    xs = list(range(n))
    ys = [cs[k - n + 1 + i][4] for i in xs]
    mx, my = sum(xs) / float(n), sum(ys) / float(n)
    sl = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sum((x - mx) ** 2 for x in xs) or 1e-9)
    atr = sum(cs[k - j][2] - cs[k - j][3] for j in range(30)) / 30.0 or 1e-9
    g = q = 0.0
    for i in range(k - 13, k + 1):
        d = cs[i][4] - cs[i - 1][4]
        if d > 0:
            g += d
        else:
            q -= d
    rsi = 100.0 if q == 0 else 100 - 100 / (1 + g / q)
    cruz = None
    for j in range(k, max(21, k - 40), -1):
        if None not in (m9[j], m21[j], m9[j - 1], m21[j - 1]) and (m9[j] - m21[j]) * (m9[j - 1] - m21[j - 1]) < 0:
            cruz = j
            break
    tend = sl * 10 / atr
    # Topo e Fundo: estrutura das últimas 24 velas (2 blocos de 12): topo e fundo mais altos = alta, mais baixos = baixa
    a1, a2 = cs[k - 23:k - 11], cs[k - 11:k + 1]
    h1, h2 = max(v[2] for v in a1), max(v[2] for v in a2)
    l1, l2 = min(v[3] for v in a1), min(v[3] for v in a2)
    if h2 > h1 and l2 > l1:
        tf = 'u'
    elif h2 < h1 and l2 < l1:
        tf = 'd'
    else:   # estrutura misturada: vale o lado do extremo mais recente
        tf = 'u' if ih > il else 'd'
    # Fibonacci da última perna: perna de alta (fundo antes do topo) segue valendo enquanto o preço não perde 61,8% dela
    if il < ih:
        fb = 'u' if pos > .382 else 'd'
    else:
        fb = 'd' if pos < .618 else 'u'
    # Médias: preço e MM9 do mesmo lado da MM21; se misturado, vale a MM9 virando
    if m9[k] is not None and m21[k] is not None:
        if p > m9[k] > m21[k]:
            mm = 'u'
        elif p < m9[k] < m21[k]:
            mm = 'd'
        else:
            mm = 'u' if (m9[k] - (m9[k - 3] or m9[k])) > 0 else 'd'
    else:
        mm = 'n'
    td = 'u' if tend > .15 else 'd' if tend < -.15 else 'n'
    r_ = 'n' if rsi >= 80 or rsi <= 20 else ('u' if rsi > 50 else 'd')
    V = {'tf': tf, 'mm': mm, 'fb': fb, 'td': td, 'rsi': r_}
    u = sum(1 for x in V.values() if x == 'u')
    d = sum(1 for x in V.values() if x == 'd')
    dr = 'u' if u > d else 'd'
    mot = ('Preço abaixo da MM9' if p < (m9[k] or p) else 'Preço acima da MM9') + (' · baixa ▼' if dr == 'd' else ' · alta ▲')
    return {'V': V, 'u': u, 'd': d, 'dir': dr, 'n': max(u, d), 'conf': int(round(max(u, d) / 5.0 * 100)), 'forca': abs(tend),
            'rsi': round(rsi), 'pos': round(pos, 3), 'ti': cs[ih][0], 'tl': cs[il][0], 'hi': hi, 'lo': lo,
            'tc': cs[cruz][0] if cruz is not None else None, 'sl': sl, 'mot': mot, 'p': p}


def _incl(ys):
    n = len(ys)
    mx, my = (n - 1) / 2.0, sum(ys) / float(n)
    return sum((i - mx) * (y - my) for i, y in enumerate(ys)) / (sum((i - mx) ** 2 for i in range(n)) or 1e-9)


def filtros(cs, a, u):
    """NUVEM-VISAO-V3.1: filtros opcionais por cima da confluência.
    lg = tendência longa: a inclinação das últimas ~150 velas (2h30) precisa apontar para o mesmo lado da entrada.
    pb = gatilho na MM9: nas últimas 3 velas o preço voltou até a MM9 e agora está de novo do lado da entrada (fim da correção)."""
    if not a:
        return False
    k = len(cs) - 1
    if u.get('lg'):
        ys = [v[4] for v in cs[-150:]]
        if len(ys) < 60:
            return False
        if (_incl(ys) > 0) != (a['dir'] == 'u'):
            return False
    if u.get('pb'):
        m9 = _mm(cs, 9)
        p = cs[k][4]
        if m9[k] is None or k < 4:
            return False
        if a['dir'] == 'u':
            ok = p > m9[k] and any(m9[k - i] is not None and cs[k - i][3] <= m9[k - i] for i in range(1, 4))
        else:
            ok = p < m9[k] and any(m9[k - i] is not None and cs[k - i][2] >= m9[k - i] for i in range(1, 4))
        if not ok:
            return False
    return True


def porque(cs, a, u):
    """NUVEM-VISAO-V3.2: diz qual filtro segurou a entrada (vazio = liberado)"""
    if not a:
        return 'sem velas suficientes'
    k = len(cs) - 1
    lado = 'ALTA' if a['dir'] == 'u' else 'BAIXA'
    if u.get('lg'):
        ys = [v[4] for v in cs[-150:]]
        if len(ys) < 60:
            return 'juntando velas para a tendência longa'
        if (_incl(ys) > 0) != (a['dir'] == 'u'):
            return 'a tendência longa (2h30) está para %s' % ('ALTA' if a['dir'] == 'd' else 'BAIXA')
    if u.get('pb'):
        m9 = _mm(cs, 9)
        if m9[k] is None or k < 4:
            return 'juntando velas para a MM9'
        p = cs[k][4]
        if a['dir'] == 'u':
            ok = p > m9[k] and any(m9[k - i] is not None and cs[k - i][3] <= m9[k - i] for i in range(1, 4))
        else:
            ok = p < m9[k] and any(m9[k - i] is not None and cs[k - i][2] >= m9[k - i] for i in range(1, 4))
        if not ok:
            return 'falta o preço voltar na MM9 e retomar a %s' % lado
    return ''


def _mm9x(cs):
    """palpite do estilo da outra plataforma: o preço acabou de cruzar a MM9 (nas 2 últimas velas) e segue para esse lado"""
    k = len(cs) - 1
    m9 = _mm(cs, 9)
    if k < 12 or None in (m9[k], m9[k - 2]):
        return None
    p, p2 = cs[k][4], cs[k - 2][4]
    if p > m9[k] and p2 <= m9[k - 2]:
        return 'u'
    if p < m9[k] and p2 >= m9[k - 2]:
        return 'd'
    return None


def laboratorio(mk, horas, prog=None):
    """NUVEM-VISAO-LAB-V1: busca na Deriv as velas de 1 min e os ticks das últimas N horas de um mercado e confere,
    vela a vela, o que cada jeito de analisar teria feito com Sobe/Desce de 5 ticks (entrada = 1º tick depois da decisão,
    saída = 5 ticks depois, como a Deriv). Gale imediato = a próxima entrada no tick seguinte ao resultado, mesma direção."""
    import websocket
    import random as _rd
    ws, ult = None, ''
    for url in WS_URLS:
        try:
            ws = websocket.create_connection(url, timeout=20, origin='https://alphadolar.online', header=['User-Agent: Mozilla/5.0 (AlphaVisao lab)'])
            break
        except Exception as e:
            ult = str(e)[:80]
            ws = None
    if ws is None:
        raise RuntimeError('sem conexão com a Deriv (%s)' % ult)
    rid = [0]

    def req(o):
        for chave in ('ticks_history', 'underlying_symbol'):
            q = dict(o)
            if chave == 'underlying_symbol':
                q['underlying_symbol'] = o['ticks_history']
            rid[0] += 1
            q['req_id'] = rid[0]
            ws.send(json.dumps(q))
            fim = time.time() + 30
            while time.time() < fim:
                m = json.loads(ws.recv())
                if m.get('req_id') == rid[0]:
                    break
            else:
                raise RuntimeError('a Deriv não respondeu')
            if not m.get('error'):
                return m
        raise RuntimeError((m.get('error') or {}).get('message') or 'erro da Deriv')

    try:
        nv = int(horas * 60) + 310
        m = req({'ticks_history': mk, 'end': 'latest', 'count': min(5000, nv), 'style': 'candles', 'granularity': 60})
        cs = [[int(c['epoch']), float(c['open']), float(c['high']), float(c['low']), float(c['close'])] for c in (m.get('candles') or [])]
        if len(cs) < 350:
            raise RuntimeError('poucas velas (%d)' % len(cs))
        ini = cs[0][0] + 300 * 60
        TT, PP, end = [], [], 'latest'
        for volta in range(40):
            m = req({'ticks_history': mk, 'end': end, 'count': 5000, 'style': 'ticks'})
            h = m.get('history') or {}
            ts, ps = [int(x) for x in (h.get('times') or [])], [float(x) for x in (h.get('prices') or [])]
            if not ts:
                break
            TT, PP = ts + TT, ps + PP
            if prog:
                prog('baixando ticks: %d' % len(TT))
            if ts[0] <= ini:
                break
            end = ts[0] - 1
        # tira repetidos e garante a ordem
        vis, T2, P2 = set(), [], []
        for a_, b_ in zip(TT, PP):
            if a_ not in vis:
                vis.add(a_)
                T2.append(a_)
                P2.append(b_)
        TT, PP = T2, P2
    finally:
        try:
            ws.close()
        except Exception:
            pass
    import bisect
    VAR = [('v3', 'Visão atual (3 de 5) · 5 h de velas', {}), ('v150', 'Visão com 2h30 de velas (como era)', {}), ('v3c4', 'Visão 4 de 5', {'cmin': 4}), ('lg', 'Visão + tendência longa', {'lg': 1}),
           ('pb', 'Visão + gatilho MM9', {'pb': 1}), ('lgpb', 'Visão + tendência longa + MM9', {'lg': 1, 'pb': 1}),
           ('mm9x', 'Cruzamento da MM9 (palpite do estilo deles)', None), ('contra', 'Contrário da Visão (teste)', None), ('moeda', 'Cara ou coroa (comparação)', None)]
    R = {k: {'nome': nm, 'n': 0, 'w': 0, 'c1': [0, 0], 'c2': [0, 0], 'pl1': 0.0, 'pl2': 0.0} for k, nm, _ in VAR}
    rnd = _rd.Random(7)
    pay, M = PAY0, 2.2

    def res(j, lado):   # entrada no tick j+1, saída no tick j+6
        if j + 6 >= len(PP):
            return None
        e, s_ = PP[j + 1], PP[j + 6]
        return s_ > e if lado == 'u' else s_ < e

    ocupado = {k: 0 for k, _, _ in VAR}
    for k in range(300, len(cs)):
        tdec = cs[k][0] + 60   # vela k fechou
        if tdec < ini - 60:
            continue
        j0 = bisect.bisect_right(TT, tdec)
        if j0 + 20 >= len(TT):
            break
        janela = cs[max(0, k - 299):k + 1]
        a = analisa(janela)
        a150 = analisa(cs[max(0, k - 149):k + 1])
        for key, nm, opt in VAR:
            if tdec < ocupado[key]:
                continue
            if key == 'v150':
                if not a150 or a150['n'] < 3:
                    continue
                d = a150['dir']
            elif key in ('v3', 'v3c4', 'lg', 'pb', 'lgpb', 'contra'):
                u = opt or {}
                if not a or a['n'] < int(u.get('cmin') or 3) or not filtros(janela, a, u):
                    continue
                d = a['dir'] if key != 'contra' else ('d' if a['dir'] == 'u' else 'u')
            elif key == 'mm9x':
                d = _mm9x(janela)
                if not d:
                    continue
            else:
                d = 'u' if rnd.random() < .5 else 'd'
            # confirmação do tick (como a V3 ao vivo): os 3 últimos ticks andando para o lado, em até 15 s
            j = None
            for jj in range(j0, min(len(TT) - 7, j0 + 30)):
                if TT[jj] - tdec > 15:
                    break
                if jj >= 3 and ((PP[jj] - PP[jj - 3] > 0) if d == 'u' else (PP[jj] - PP[jj - 3] < 0)):
                    j = jj
                    break
            if j is None and key != 'moeda':
                continue
            j = j if j is not None else j0
            r1 = res(j, d)
            if r1 is None:
                continue
            Q = R[key]
            Q['n'] += 1
            Q['w'] += 1 if r1 else 0
            # ciclos com gale imediato (mesma direção, entrada no tick seguinte ao resultado)
            seq, jj = [r1], j
            for g in range(2):
                jj = jj + 6
                rr = res(jj, d)
                if rr is None:
                    break
                seq.append(rr)
            for G, ck, pk in ((1, 'c1', 'pl1'), (2, 'c2', 'pl2')):
                if len(seq) < G + 1:
                    continue
                perda, ganho = 0.0, None
                for g in range(G + 1):
                    st = 1.0 * M ** g
                    if seq[g]:
                        ganho = st * pay - perda
                        break
                    perda += st
                Q[ck][1] += 1
                if ganho is not None:
                    Q[ck][0] += 1
                    Q[pk] += ganho
                else:
                    Q[pk] -= perda
            ocupado[key] = TT[min(len(TT) - 1, j + 6)] + 1
    out = []
    for key, nm, _ in VAR:
        Q = R[key]
        out.append({'k': key, 'nome': nm, 'n': Q['n'], 'acerto': round(100.0 * Q['w'] / Q['n'], 1) if Q['n'] else None,
                    'c1': round(100.0 * Q['c1'][0] / Q['c1'][1], 1) if Q['c1'][1] else None, 'nc1': Q['c1'][1], 'pl1': r2(Q['pl1']),
                    'c2': round(100.0 * Q['c2'][0] / Q['c2'][1], 1) if Q['c2'][1] else None, 'nc2': Q['c2'][1], 'pl2': r2(Q['pl2'])})
    return {'mk': mk, 'horas': horas, 'de': ini, 'ate': TT[-1] if TT else 0, 'velas': len(cs), 'ticks': len(TT), 'var': out, 'pay': pay, 'M': M,
            'empate': round(100 / (1 + pay), 1)}


class NuvemVisao(object):
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

    def pedidos(self):
        """mercados que alguma página abriu no último minuto (para manter o gráfico vivo mesmo com o robô parado)"""
        d = self.kv.jget(P + 'pede', {}) or {}
        return [m for m, t in d.items() if m in MERC and time.time() - float(t) < 90]

    def pede(self, mk):
        if mk not in MERC:
            return
        d = self.kv.jget(P + 'pede', {}) or {}
        if time.time() - float(d.get(mk) or 0) > 20:
            d[mk] = int(time.time())
            self.kv.jset(P + 'pede', {m: t for m, t in d.items() if time.time() - float(t) < 120}, ex=300)

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

    # ---------------- preços: velas de 1 min + ticks ----------------
    def leitor(self):
        import websocket
        idx = 0
        while not EST['pausa']:
            if not self.lista() and not self.pedidos():
                time.sleep(4)
                continue
            url = WS_URLS[idx % len(WS_URLS)]
            ws = None
            try:
                ws = websocket.create_connection(url, timeout=15, origin='https://alphadolar.online', header=['User-Agent: Mozilla/5.0 (AlphaVisao nuvem)'])
                mapa, hist = {}, {}
                for i, s in enumerate(MERC):
                    mapa[i + 1] = s
                    ws.send(json.dumps({'ticks': s, 'subscribe': 1, 'req_id': i + 1}))
                    hist[100 + i] = s
                    ws.send(json.dumps({'ticks_history': s, 'end': 'latest', 'count': NV, 'style': 'candles', 'granularity': 60, 'req_id': 100 + i}))
                ws.settimeout(5)
                EST['con'], EST['vistos'], EST['ws'] = time.time(), set(), ''
                ult_ping, sem, ult_px = time.time(), time.time(), 0
                while not EST['pausa']:
                    if time.time() - ult_ping > 25:
                        ws.send('{"ping": 1}')
                        ult_ping = time.time()
                    if time.time() - sem > 45:
                        raise Exception('nenhum tick em 45 s')
                    if time.time() - ult_px > 1:
                        ult_px = time.time()
                        self.publica()
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        raise Exception('conexão fechada')
                    m = json.loads(raw)
                    rid = m.get('req_id')
                    if rid in hist:
                        s = hist[rid]
                        if m.get('error'):
                            if rid < 150:
                                ws.send(json.dumps({'ticks_history': s, 'underlying_symbol': s, 'end': 'latest', 'count': NV, 'style': 'candles', 'granularity': 60, 'req_id': rid + 50}))
                                hist[rid + 50] = s
                            continue
                        cs = m.get('candles') or []
                        V = VELAS[s]
                        novas = [[int(c['epoch']), float(c['open']), float(c['high']), float(c['low']), float(c['close'])] for c in cs]
                        if novas:
                            V.clear()
                            for c in novas:
                                V.append(c)
                            EST['hist'][s] = int(time.time())
                        continue
                    t = m.get('tick')
                    if not t or t.get('quote') is None:
                        continue
                    sym = t.get('symbol') or t.get('underlying_symbol') or mapa.get(rid)
                    if sym not in TICKS:
                        continue
                    sem = time.time()
                    ep, q = int(t.get('epoch') or time.time()), float(t['quote'])
                    T = TICKS[sym]
                    if T and T[-1][0] >= ep:
                        continue
                    T.append((ep, q))
                    V, m0 = VELAS[sym], ep // 60 * 60
                    if V and V[-1][0] == m0:
                        c = V[-1]
                        c[2], c[3], c[4] = max(c[2], q), min(c[3], q), q
                    elif not V or m0 > V[-1][0]:
                        V.append([m0, V[-1][4] if V else q, max(q, V[-1][4] if V else q), min(q, V[-1][4] if V else q), q])
                    EST['ticks'] += 1
                    LTK[sym] = time.time()
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

    def publica(self):
        """o líder guarda as velas e os últimos ticks dos mercados em uso (a página lê daqui, de qualquer processo)"""
        if not self.lider:
            return
        self.kv.set(K_MOTOR, str(int(time.time())), ex=60)
        uso = set(self.pedidos())
        for conta in self.lista():
            if self.ligado(conta):
                u = self.cfg(conta)
                for m in (u.get('mks') or []):
                    uso.add(m)
                if u.get('ab'):
                    uso.add(u['ab'].get('mk'))
        for m in uso:
            if m in VELAS and VELAS[m]:
                try:
                    self.kv.jset(P + 'cd:' + m, {'c': [[c[0], round(c[1], 5), round(c[2], 5), round(c[3], 5), round(c[4], 5)] for c in VELAS[m]],
                                                  't': [[e, round(q, 5)] for (e, q) in list(TICKS[m])[-40:]]}, ex=120)
                except Exception:
                    pass

    def vigia(self):
        while not EST['pausa'] and self.pid == os.getpid():
            try:
                if self.sou_lider():
                    for conta in self.lista():
                        t = self.trab.get(conta)
                        if (t is None or not t.is_alive()) and (self.ligado(conta) or self.cfg(conta).get('ab')):
                            t = threading.Thread(target=self.trabalha, args=(conta,), daemon=True)
                            self.trab[conta] = t
                            t.start()
            except Exception as e:
                log('vigia', e)
            time.sleep(1)

    # ---------------- o robô ----------------
    def para(self, conta, u, motivo):
        self.liga(conta, False)
        u['parado'], u['t_parou'], u['fase'] = motivo, int(time.time()), 'parado'
        u.pop('an_ate', None)
        u.pop('tk_ate', None)
        self.salva(conta, u)
        self.op_log(conta, {'t': int(time.time()), 'aviso': motivo})
        log('%s…%s parado: %s' % (conta[:3], conta[-3:], motivo))

    def trabalha(self, conta):
        c, hb, sb, tf, ta = None, 0, 0, 0, 0
        u = self.cfg(conta)
        while (self.ligado(conta) or (u or {}).get('ab')) and not EST['pausa'] and self.lider:   # encerrado com contrato aberto: termina de conferir
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
                elif not self.ligado(conta):
                    break
                elif u.get('vab'):
                    mudou = self.virtual(conta, u) or mudou
                elif time.time() - ta > 0.5:
                    ta = time.time()
                    mudou = self.passo(conta, c, u) or mudou
                    if not self.ligado(conta):
                        return
                if mudou or time.time() - tf > 2:
                    tf = time.time()
                    u['t_upd'] = int(time.time())
                    self.salva(conta, u)
                else:
                    time.sleep(0.1)
            except PermissionError:
                return self.para(conta, u, 'SUA SESSÃO NA DERIV EXPIROU: abra o Alpha Visão e entre de novo')
            except Exception as ex:
                log('trabalha', conta[-3:], ex)
                time.sleep(1.5)
        if u and not self.ligado(conta):
            if u.get('ciclo') and u['ciclo'].get('esp'):
                u['ciclo'] = None
            pm = self.kv.get(P + 'pmot:' + conta)
            if pm:
                u['parado'], u['t_parou'], u['fase'] = pm, int(time.time()), 'parado'
            self.salva(conta, u)

    def varre(self, u, so=None):
        sc, melhor, bloq = {}, None, {}
        for s in (so or u['mks']):
            a = analisa(list(VELAS.get(s) or []))
            if not a:
                sc[s] = [0, 0]
                continue
            sc[s] = [a['u'], a['d']]
            if a['n'] >= int(u.get('cmin') or 3) and (u.get('lg') or u.get('pb')):   # NUVEM-VISAO-V3.2: guarda o motivo do filtro
                pq = porque(list(VELAS.get(s) or []), a, u)
                if pq:
                    bloq[s] = '%s tem %d de 5 para %s, mas %s' % (NOME[s], a['n'], 'ALTA' if a['dir'] == 'u' else 'BAIXA', pq)
            if a['n'] >= int(u.get('cmin') or 3) and filtros(list(VELAS.get(s) or []), a, u) and (melhor is None or (a['n'], a['forca']) > (melhor[1]['n'], melhor[1]['forca'])):
                melhor = (s, a)
        u['scan'] = sc
        u['bloq'] = bloq
        return melhor

    def passo(self, conta, c, u):
        op = u.get('op') or 'ia'
        if op == 'manual':
            if not u.get('ciclo'):
                lado = 'CALL' if u.get('lado') == 'CALL' else 'PUT'
                u['ciclo'] = {'nivel': 0, 'perda': 0.0, 'base': self.base(u), 'mk': u['mmk'], 'lado': lado, 'cic': 1, 'V': {}}
                u['an'] = None
                self.compra(conta, c, u)
                return True
            return False
        if time.time() < float(u.get('prox') or 0):
            u['fase'] = 'pausa entre ciclos: volta a analisar em %d s' % max(1, int(float(u['prox']) - time.time()))
            self.varre(u)
            return True
        g = u.get('ciclo')
        # janela de análise que aparece na tela: depois dela, entra com a leitura mais nova
        if u.get('an_ate'):
            if time.time() < float(u['an_ate']):
                return False
            u.pop('an_ate', None)
            mk = (u.get('an') or {}).get('mk')
            a = analisa(list(VELAS.get(mk) or [])) if mk else None
            if not a or a['n'] < int(u.get('cmin') or 3) or not filtros(list(VELAS.get(mk) or []), a, u):
                u['fase'] = 'a confluência sumiu no último segundo: analisando de novo'
                u['an'] = None
                return True
            a['mk'] = mk
            a['t'] = int(time.time())
            u['an'] = a
            lado = 'CALL' if a['dir'] == 'u' else 'PUT'
            # NUVEM-VISAO-V3: entra só quando os últimos ticks andam para o lado da análise (até 15 s; senão analisa de novo)
            T3 = list(TICKS.get(mk) or [])
            nc = int(u.get('conf') or 0)   # NUVEM-VISAO-CONF-V1: N ticks seguidos do outro lado antes de entrar
            if len(T3) >= max(4, nc + 1):
                if nc > 0:
                    ok3 = all(((float(T3[-k][1]) < float(T3[-k - 1][1])) if a['dir'] == 'u' else (float(T3[-k][1]) > float(T3[-k - 1][1]))) for k in range(1, nc + 1))
                else:
                    mv = float(T3[-1][1]) - float(T3[-4][1])
                    ok3 = (mv > 0) if a['dir'] == 'u' else (mv < 0)
                if not ok3:
                    lim = float(u.get('tk_ate') or 0) or (time.time() + (45 if nc else 15))
                    u['tk_ate'] = lim
                    if time.time() < lim:
                        u['an_ate'] = time.time() + 1
                        u['fase'] = ('IA esperando %d tick(s) seguidos do outro lado para entrar %s em %s%s' % (nc, 'na ALTA' if a['dir'] == 'u' else 'na BAIXA', NOME[mk], (' · GALE %d' % g['nivel']) if g and g.get('nivel') else '')) if nc else ('IA esperando o tick confirmar %s em %s%s' % ('a ALTA' if a['dir'] == 'u' else 'a BAIXA', NOME[mk], (' · GALE %d' % g['nivel']) if g and g.get('nivel') else ''))
                        return True
                    u.pop('tk_ate', None)
                    u['an'] = None
                    u['fase'] = 'a confirmação dos ticks não veio a tempo: a IA analisa de novo'
                    return True
            u.pop('tk_ate', None)
            hit = int(u.get('hit') or 0)
            if not g and hit > 0 and int(u.get('hseq') or 0) < hit:   # HIT: entrada virtual (sem dinheiro) até vir a sequência escolhida
                T = list(TICKS.get(mk) or [])
                u['vab'] = {'mk': mk, 'lado': lado, 'e0': T[-1][0] if T else int(time.time()), 'p0': T[-1][1] if T else a['p'], 't': time.time()}
                u['fase'] = 'HIT · entrada VIRTUAL (sem dinheiro): %s %s · esperando %d %s seguido(s) · %d/%d' % (
                    'Compra' if lado == 'CALL' else 'Venda', NOME[mk], hit, 'WIN' if u.get('hitm') == 'win' else 'LOSS', int(u.get('hseq') or 0), hit)
                return True
            if g and g.get('esp'):
                g.update({'mk': mk, 'lado': lado, 'esp': False, 'V': a['V']})
            elif not g:
                u['ciclo'] = {'nivel': 0, 'perda': 0.0, 'base': self.base(u), 'mk': mk, 'lado': lado, 'cic': 1, 'V': a['V']}
                u['hseq'] = 0
            self.op_log(conta, {'t': int(time.time()), 'aviso': '👁 %s: %d de 5 indicadores para %s (%s)%s' % (
                NOME[mk], a['n'], 'ALTA' if a['dir'] == 'u' else 'BAIXA', a['mot'], (' · GALE %d' % u['ciclo']['nivel']) if u['ciclo']['nivel'] else '')})
            self.compra(conta, c, u)
            return True
        so = None
        if g and g.get('esp') and g.get('fora'):   # V2.4: troca de mercado depois do LOSS (se só sobrar ele, fica)
            so = [m for m in u['mks'] if m not in g['fora']] or [m for m in u['mks'] if m != g['fora'][-1]] or None
        melhor = self.varre(u, so)
        if not melhor:
            espera = int(time.time() - float(u.get('t_busca') or time.time()))
            u.setdefault('t_busca', time.time())
            top = max(u['scan'], key=lambda m: max(u['scan'][m])) if u.get('scan') else None
            bq = list((u.get('bloq') or {}).values())
            if bq:
                u['fase'] = 'IA esperando: ' + bq[0]
            else:
                u['fase'] = 'IA analisando %d mercados · nenhum com %d de 5 indicadores a favor agora%s' % (
                    len(u['mks']), int(u.get('cmin') or 3), (' · mais perto: %s %d/5' % (NOME[top], max(u['scan'][top]))) if top else '')
            u['an'] = None
            lim = 900 if (u.get('lg') or u.get('pb')) else 180   # NUVEM-VISAO-V3.2: com filtros a espera é maior
            if op == 'ia' and not g and espera > lim:
                self.para(conta, u, ('SEM ENTRADA em %d minutos: %s. Nada foi operado; os filtros (tendência longa / MM9) deixam a entrada rara.' % (lim // 60, bq[0])) if bq else
                          'SEM CONFLUÊNCIA: em %d minutos nenhum mercado teve %d de 5 indicadores a favor. Nada foi operado; tente de novo.' % (lim // 60, int(u.get('cmin') or 3)))
            return True
        u.pop('t_busca', None)
        mk, a = melhor
        a['mk'] = mk
        a['t'] = int(time.time())
        a['dur'] = float(u.get('tan') or 0) or (T_ANALISE_GALE if g else T_ANALISE)   # NUVEM-VISAO-V3.1: tempo de análise escolhido
        u['an'] = a
        u['an_ate'] = time.time() + a['dur']
        u['fase'] = 'IA analisando o gráfico de %s%s' % (NOME[mk], (' · GALE %d' % g['nivel']) if g and g.get('nivel') else '')
        return True

    def base(self, u):
        return r2(max(0.35, float(u['E'])))

    def stake(self, u):
        g = u['ciclo']
        if not g['nivel']:
            return g['base']
        if u.get('rec') == 'exata':
            a = float((u.get('pm') or {}).get(g['lado']) or PAY0)
            return max(0.35, ceil2((g['perda'] + g['base'] * a) / a))
        return max(0.35, r2(g['base'] * math.pow(float(u.get('M') or 2.2), g['nivel'])))

    def fim_ciclo(self, conta, u, txt, ganhou=False):
        """modo 'ia': 1 = um clique, um ciclo; N = continua até N ciclos ganhos; 0 = até a meta. A sessão continua."""
        op = u.get('op') or 'ia'
        if op == 'nuvem':
            return False
        if op == 'ia':
            q = int(u.get('qtd', 1) if u.get('qtd') is not None else 1)
            if ganhou:
                u['rw'] = int(u.get('rw') or 0) + 1
            if q == 0 or (q > 1 and int(u.get('rw') or 0) < q):
                pz = int(u.get('pia') if u.get('pia') is not None else 60)
                u['prox'] = time.time() + pz
                u['fase'] = '%s · %s · próxima análise em %d s' % (txt, ('WIN %d de %d' % (u['rw'], q)) if q else ('%d WIN até a meta' % int(u.get('rw') or 0)), pz)
                self.op_log(conta, {'t': int(time.time()), 'aviso': u['fase']})
                return False
            if q > 1:
                txt = 'CONCLUÍDO %d de %d WIN · %s' % (int(u.get('rw') or 0), q, txt)
        self.para(conta, u, txt)
        return True

    def virtual(self, conta, u):
        """HIT: confere a entrada virtual pelos ticks (5 ticks depois do tick de entrada), como a Deriv faria"""
        v = u['vab']
        T = [t for t in list(TICKS.get(v['mk']) or []) if t[0] > v['e0']]
        if len(T) < 6:
            if time.time() - float(v['t']) > 90:
                u.pop('vab', None)
                return True
            return False
        ent, sai = T[0][1], T[5][1]
        won = sai > ent if v['lado'] == 'CALL' else sai < ent
        quer = u.get('hitm') == 'win'
        hit = int(u.get('hit') or 0)
        u['hseq'] = int(u.get('hseq') or 0) + 1 if won == quer else 0
        u.pop('vab', None)
        self.op_log(conta, {'t': int(time.time()), 'virt': 1, 'mk': v['mk'], 'lado': v['lado'], 'res': 'w' if won else 'l', 'pe': ent,
                            'aviso': '👻 Virtual %s %s → %s · %s %d de %d' % ('Compra' if v['lado'] == 'CALL' else 'Venda', NOME[v['mk']], 'WIN' if won else 'LOSS',
                                                                         'WIN' if quer else 'LOSS', min(u['hseq'], hit), hit)})
        u['fase'] = ('HIT completo (%d %s): a próxima entrada é REAL' % (hit, 'WIN' if quer else 'LOSS')) if u['hseq'] >= hit else ('HIT %d/%d · analisando de novo' % (u['hseq'], hit))
        u['vres'] = {'res': 'w' if won else 'l', 't': int(time.time()), 'mk': v['mk']}
        return True

    def compra(self, conta, c, u):
        g, s = u['ciclo'], u.setdefault('sess', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'cw': 0, 'cl': 0})
        st = self.stake(u)
        L = float(u.get('L') or 0)
        if L > 0 and -s['pl'] + st > L + 1e-9:
            if g['nivel']:
                self.op_log(conta, {'t': int(time.time()), 'aviso': '🛡 O gale %d ($%.2f) passaria da perda máxima: assumiu −$%.2f e encerrou o ciclo.' % (g['nivel'], st, g['perda'])})
                s['cl'] += 1
                u['ciclo'], u['prox'] = None, time.time() + 15
                if -s['pl'] + g['base'] > L + 1e-9:
                    return self.para(conta, u, 'PERDA MÁXIMA: a próxima entrada passaria do limite de $%.2f · resultado %s$%.2f' % (L, '+' if s['pl'] >= 0 else '−', abs(s['pl'])))
                return self.fim_ciclo(conta, u, 'CICLO ENCERRADO: o gale passaria da perda máxima · resultado %s$%.2f' % ('+' if s['pl'] >= 0 else '−', abs(s['pl'])))
            return self.para(conta, u, 'PERDA MÁXIMA: a próxima entrada passaria do limite de $%.2f · resultado %s$%.2f' % (L, '+' if s['pl'] >= 0 else '−', abs(s['pl'])))
        tt, b0 = float(u.get('teto') or 0), float(u.get('banca0') or 0)
        if g['nivel'] and tt > 0 and b0 > 0 and g['perda'] + st > b0 * tt / 100.0 + 1e-9:
            self.op_log(conta, {'t': int(time.time()), 'aviso': '🛡 A recuperação passaria do teto de %d%% da banca ($%.2f): assumiu −$%.2f e voltou à entrada.' % (tt, b0 * tt / 100.0, g['perda'])})
            s['cl'] += 1
            u['ciclo'], u['prox'] = None, time.time() + 15
            return self.fim_ciclo(conta, u, 'CICLO ENCERRADO pelo teto da recuperação · resultado %s$%.2f' % ('+' if s['pl'] >= 0 else '−', abs(s['pl'])))
        if u.get('saldo') is not None and st > float(u['saldo']) + 1e-9:
            return self.para(conta, u, 'PARADO: saldo insuficiente para a entrada de $%.2f' % st)
        prm = {'contract_type': g['lado'], 'amount': st, 'basis': 'stake', 'currency': u.get('moeda') or 'USD', 'duration': 5, 'duration_unit': 't'}
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
            if u['erros'] >= 3 or 'balance' in msg.lower() or 'insufficient' in msg.lower() or (u.get('op') or 'ia') == 'manual':
                return self.para(conta, u, 'PARADO: a Deriv recusou (%s)' % msg[:90])
            u['ciclo'], u['prox'] = None, time.time() + 5
            return
        b = r.get('buy') or {}
        u['erros'] = 0
        try:
            p = float(b.get('payout')) / float(b.get('buy_price')) - 1
            if 0.3 < p < 1.2:
                u.setdefault('pm', {})[g['lado']] = p
        except Exception:
            pass
        T = TICKS.get(g['mk']) or []
        u['ab'] = {'cid': b.get('contract_id'), 'st': float(b.get('buy_price') or st), 'lado': g['lado'], 'mk': g['mk'], 't': time.time(),
                   'nivel': g['nivel'], 'p0': T[-1][1] if T else None, 'e0': T[-1][0] if T else None}
        u['fase'] = 'entrada confirmada · %s %s $%.2f · 5 ticks%s' % ('Compra' if g['lado'] == 'CALL' else 'Venda', NOME[g['mk']], u['ab']['st'], (' · GALE %d' % g['nivel']) if g['nivel'] else '')

    def confere(self, conta, c, u):
        ab = u['ab']
        if time.time() - float(ab['t']) < 4 or time.time() - float(ab.get('ult') or 0) < 0.8:
            return None
        ab['ult'] = time.time()
        try:
            q = c.req({'proposal_open_contract': 1, 'contract_id': ab['cid']}, 5).get('proposal_open_contract') or {}
        except PermissionError:
            raise
        except Exception:
            q = {}
        if q.get('entry_spot') is not None and ab.get('pe') is None:
            try:
                ab['pe'] = float(q['entry_spot'])
            except Exception:
                pass
        if not (q.get('is_sold') or q.get('status') in ('won', 'lost', 'sold')):
            if time.time() - float(ab['t']) > 120:
                u.pop('ab', None)
                u['ciclo'] = None
                self.op_log(conta, {'t': int(time.time()), 'aviso': 'a Deriv não confirmou o contrato %s: confira no histórico da Deriv' % ab['cid']})
                return 'parou' if self.fim_ciclo(conta, u, 'PARADO: a Deriv não confirmou um contrato (confira no histórico da Deriv)') else 'ok'
            return None
        u.pop('ab', None)
        if not self.kv.setnx(P + 'contou:%s' % ab['cid'], '1', 86400 * 3):
            return 'ok'
        pl = r2(float(q.get('profit') or 0))
        won = pl > 0
        s = u.setdefault('sess', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'cw': 0, 'cl': 0})
        g = u.get('ciclo') or {'nivel': 0, 'perda': 0.0, 'base': self.base(u), 'mk': ab['mk'], 'lado': ab['lado'], 'cic': 1}
        s['pl'], s['n'] = r2(s['pl'] + pl), s['n'] + 1
        self.dia(conta, pl)
        if g.get('V'):   # placar honesto: o indicador acertou se tinha votado no lado que de fato andou
            pc = self.kv.jget(P + 'plac3:' + conta, {}) or {}
            lado_ok = ('u' if ab['lado'] == 'CALL' else 'd') if won else ('d' if ab['lado'] == 'CALL' else 'u')
            for i, v in g['V'].items():
                if v in ('u', 'd'):
                    a = pc.setdefault(i, [0, 0])
                    a[1] += 1
                    a[0] += 1 if v == lado_ok else 0
            self.kv.jset(P + 'plac3:' + conta, pc, ex=86400 * 60)
        tipo = 'Compra' if ab['lado'] == 'CALL' else 'Venda'
        self.op_log(conta, {'t': int(time.time()), 'mk': ab['mk'], 'nome': NOME[ab['mk']], 'tipo': tipo, 'st': ab['st'], 'pl': pl, 'g': ab.get('nivel') or 0,
                            'cid': ab['cid'], 'pe': ab.get('pe'), 'px': q.get('exit_tick') or q.get('sell_spot'), 'op': u.get('op') or 'ia'})
        _extrato(conta, u.get('tipo'), ab['cid'], ab['mk'], ab['st'], pl, tipo + ' 5 ticks' + (' G%d' % ab['nivel'] if ab.get('nivel') else ''))
        W, L = float(u.get('W') or 0), float(u.get('L') or 0)
        sinal = '+' if s['pl'] >= 0 else '−'
        if L > 0 and -s['pl'] >= L - 1e-9:
            u['ciclo'] = None
            self.para(conta, u, 'PERDA MÁXIMA de $%.2f atingida · resultado −$%.2f' % (L, abs(s['pl'])))
            return 'parou'
        if won:
            s['w'] += 1
            s['cw'] += 1
            u['ciclo'], u['prox'] = None, time.time() + int(u.get('pausa') or 0)
            tv = int(u.get('trava') or 0)   # NUVEM-VISAO-V2.1: trava de lucro
            if tv and W > 0 and not u.get('travaOn') and s['pl'] >= max(W * tv / 100.0, self.base(u)) - 1e-9:   # V2.7
                u['travaOn'] = True
                self.op_log(conta, {'t': int(time.time()), 'aviso': '🔒 Trava de lucro ligada: passou de %d%% da meta (+$%.2f). Se vier um LOSS, o robô para e segura o lucro.' % (tv, s['pl'])})
            u['fase'] = 'WIN %s · %s +$%.2f' % (tipo, NOME[ab['mk']], pl)
            if W > 0 and s['pl'] >= W - 1e-9:
                self.para(conta, u, 'META BATIDA: +$%.2f em %d entradas' % (s['pl'], s['n']))
                return 'parou'
            if (u.get('op') or 'ia') == 'manual':
                self.para(conta, u, 'MANUAL · WIN +$%.2f · resultado da sessão %s$%.2f' % (pl, sinal, abs(s['pl'])))
                return 'parou'
            return 'parou' if self.fim_ciclo(conta, u, 'CICLO CONCLUÍDO · WIN +$%.2f%s · resultado da sessão %s$%.2f' % (pl, (' no gale %d' % ab['nivel']) if ab.get('nivel') else '', sinal, abs(s['pl'])), True) else 'ok'
        s['l'] += 1
        if u.get('travaOn') and r2(s['pl'] - pl) < max(W * int(u.get('trava') or 0) / 100.0, 0.01) - 1e-9:   # V2.7: trava velha (de outra sessão): desarma
            u['travaOn'] = False
        if u.get('travaOn'):
            u['ciclo'] = None
            self.para(conta, u, 'TRAVA DE LUCRO: perdeu depois de passar de %d%% da meta · resultado %s$%.2f' % (int(u.get('trava') or 0), sinal, abs(s['pl'])))
            return 'parou'
        if (u.get('op') or 'ia') == 'manual':
            u['ciclo'] = None
            self.para(conta, u, 'MANUAL · LOSS −$%.2f · resultado da sessão %s$%.2f' % (abs(pl), sinal, abs(s['pl'])))
            return 'parou'
        g['perda'] = r2(float(g['perda']) + ab['st'])
        T, C = int(u.get('G') or 0) + 1, max(1, int(u.get('C') or 1))
        g['nivel'] = int(g['nivel']) + 1
        g.setdefault('cic', 1)
        if u.get('troca') and ((g['nivel'] % T) or g['cic'] < C):   # V2.4: o mercado que perdeu fica de fora até o ciclo acabar
            fo = g.setdefault('fora', [])
            if ab['mk'] not in fo:
                fo.append(ab['mk'])
            if len([m for m in u['mks'] if m not in fo]):
                self.op_log(conta, {'t': int(time.time()), 'aviso': '🔀 Saiu de %s depois do LOSS: a IA analisa os outros mercados para o gale.' % NOME[ab['mk']]})
        if u.get('gim') and g['nivel'] % T:   # NUVEM-VISAO-V3.1: gale imediato, mesmo mercado e mesma direção (sem analisar de novo)
            g['esp'] = False
            u['ciclo'] = g
            self.op_log(conta, {'t': int(time.time()), 'aviso': '⚡ GALE %d imediato: %s %s de novo' % (g['nivel'], 'Compra' if g['lado'] == 'CALL' else 'Venda', NOME[g['mk']])})
            self.compra(conta, c, u)
            return 'parou' if not self.ligado(conta) else 'ok'
        if g['nivel'] % T:   # ainda tem gale neste ciclo: a IA analisa de novo e entra já
            g['esp'] = True
            u['ciclo'] = g
            u['fase'] = 'LOSS · a IA analisa de novo para o GALE %d' % g['nivel']
            return 'ok'
        if g['cic'] < C:     # perdeu o ciclo: a recuperação continua no próximo ciclo
            g.update({'cic': g['cic'] + 1, 'esp': True})
            u['ciclo'] = g
            u['fase'] = 'ciclo %d perdido (−$%.2f) · a recuperação continua no ciclo %d/%d' % (g['cic'] - 1, g['perda'], g['cic'], C)
            self.op_log(conta, {'t': int(time.time()), 'aviso': '🔁 Ciclo %d perdido (−$%.2f): a recuperação continua no ciclo %d de %d.' % (g['cic'] - 1, g['perda'], g['cic'], C)})
            return 'ok'
        s['cl'] += 1
        u['ciclo'], u['prox'] = None, time.time() + int(u.get('pausa') or 0)
        u['fase'] = 'LOSS: perdeu %s · −$%.2f' % (('os %d ciclos' % C) if C > 1 else ('o ciclo' if T > 1 else 'a entrada'), g['perda'])
        if u.get('cFim') == 'parar' and C > 1:
            self.para(conta, u, 'PAROU: perdeu os %d ciclos de gale, como você escolheu · resultado %s$%.2f' % (C, sinal, abs(s['pl'])))
            return 'parou'
        return 'parou' if self.fim_ciclo(conta, u, 'CICLO CONCLUÍDO · LOSS −$%.2f%s · resultado da sessão %s$%.2f' % (
            g['perda'], (' (perdeu os %d gales)' % (T - 1)) if T > 1 else '', sinal, abs(s['pl']))) else 'ok'


def register_nuvem_visao(app):
    from flask import request, jsonify
    nv = NuvemVisao()

    def solta():
        EST['pausa'] = True
        try:
            if nv.kv.get(K_LIDER) == nv.eu:
                nv.kv.set(K_LIDER, '', ex=1)
        except Exception:
            pass
    atexit.register(solta)

    @app.before_request
    def _nvi_garante():
        try:
            if nv.pid == os.getpid() or time.time() - getattr(nv, '_chk', 0) < 10:
                return
            nv._chk = time.time()
            if nv.lista() or nv.pedidos():
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

    def sessao_ativa(u0):
        """a sessão continua entre os cliques, até bater meta/perda, a pessoa zerar ou virar o dia"""
        if not u0 or not u0.get('sess'):
            return False
        if str(u0.get('parado') or '').startswith(('META BATIDA', 'PERDA MÁXIMA', 'PAROU', 'SUA SESSÃO', 'TRAVA DE LUCRO')):
            return False
        return datetime.fromtimestamp(float(u0.get('t_sess') or 0), BRT).date() == datetime.now(BRT).date()

    @app.route('/api/nuvem-visao/ligar', methods=['POST'])
    def _nvi_ligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta, cf = str(d['conta']), d.get('cfg') or {}
        u0 = nv.cfg(conta)
        if nv.ligado(conta) or u0.get('ab'):
            return jsonify({'ok': False, 'erro': 'o Alpha Visão já está operando nesta conta (espere terminar ou encerre)'}), 400
        if str(info.get('tipo')) == 'real':
            nvp = _nivel_plano(str(d.get('token') or ''))
            if nvp is None:
                return jsonify({'ok': False, 'erro': 'não consegui confirmar o seu plano agora; tente de novo em instantes'}), 503
            if nvp < 2:
                return jsonify({'ok': False, 'erro': 'Na conta real o Alpha Visão exige o plano Pro (ou superior). Na demo é liberado.'}), 403
        op = cf.get('op') if cf.get('op') in ('ia', 'nuvem', 'manual') else 'ia'
        mks = [m for m in (cf.get('mks') or PADRAO) if m in MERC][:10] or PADRAO
        continua = sessao_ativa(u0) and not cf.get('nova')
        saldo = float(info['saldo']) if info.get('saldo') is not None else None
        b0 = float(u0.get('banca0') or 0) if continua else (saldo or 0)
        pct = cf.get('un') == 'pct'
        if pct and not b0 > 0:
            return jsonify({'ok': False, 'erro': 'não consegui ler o saldo para calcular as porcentagens: use valores em US$'}), 400

        def val(k, d0, hi):
            v = num(cf.get(k), d0, 0, hi)
            return r2(b0 * v / 100.0) if pct else r2(v)
        E, W, L = max(0.35, val('E', 1, 5000 if not pct else 50)), val('W', 0, 1000000 if not pct else 500), val('L', 0, 1000000 if not pct else 100)
        if not L > 0:
            return jsonify({'ok': False, 'erro': 'coloque o stop loss (perda máxima) antes de operar'}), 400
        if L < E:
            return jsonify({'ok': False, 'erro': 'o stop loss precisa ser pelo menos o valor da entrada ($%.2f)' % E}), 400
        modo = cf.get('modo') if cf.get('modo') in MODOS else 'moderado'
        G = 0 if cf.get('unica') else MODOS[modo]
        if not cf.get('unica') and cf.get('G') is not None:   # V2.4: gales por ciclo escolhidos na configuração (0 a 6)
            G = int(num(cf.get('G'), G, 0, 6))
        u = {'conta': conta, 'tok': str(d['token']).strip(), 'tipo': info['tipo'], 'moeda': info['moeda'], 'parado': '', 't_lig': int(time.time()),
             'op': op, 'mks': mks, 'un': 'pct' if pct else 'usd', 'Ep': num(cf.get('E'), 1, 0, 5000), 'Wp': num(cf.get('W'), 0, 0, 1000000), 'Lp': num(cf.get('L'), 0, 0, 1000000),
             'E': E, 'W': W, 'L': L, 'modo': modo, 'unica': bool(cf.get('unica')), 'G': G, 'rec': 'exata' if cf.get('rec') == 'exata' else 'mult',
             'M': num(cf.get('M'), 2.2, 1.01, 10), 'C': int(num(cf.get('C'), 1, 1, 5)), 'cFim': 'parar' if cf.get('cFim') == 'parar' else 'reset',
             'troca': cf.get('troca') == 'troca', 'teto': int(num(cf.get('teto'), 0, 0, 90)), 'cmin': int(num(cf.get('cmin'), 3, 3, 5)), 'pausa': int(num(cf.get('pausa'), 0, 0, 600)),
             'pm': u0.get('pm') or {}, 'banca0': b0,
             'trava': int(num(cf.get('trava'), 0, 0, 90)), 'travaOn': bool(u0.get('travaOn')) if continua else False,
             'qtd': int(num(cf.get('qtd'), 1, 0, 50)), 'pia': int(num(cf.get('pia'), 60, 0, 900)), 'rw': 0,
             'conf': int(num(cf.get('conf'), 0, 0, 5)),   # NUVEM-VISAO-CONF-V1
             'gim': cf.get('gim') is True, 'tan': int(num(cf.get('tan'), 0, 0, 30)), 'lg': bool(cf.get('lg')), 'pb': bool(cf.get('pb')),   # NUVEM-VISAO-V3.1
             'hit': int(num(cf.get('hit'), 0, 0, 5)), 'hitm': 'win' if cf.get('hitm') == 'win' else 'loss', 'hseq': 0, 'vab': None,
             'sess': u0['sess'] if continua else {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'cw': 0, 'cl': 0},
             't_sess': u0.get('t_sess') if continua else int(time.time()),
             'ciclo': None, 'prox': 0, 'erros': 0, 'fase': 'IA analisando os mercados…', 'saldo': saldo, 'an': None}
        if op == 'ia' and u['qtd'] == 0 and not W > 0:
            return jsonify({'ok': False, 'erro': 'para operar "até a meta" coloque o stop win (meta) em Configurar'}), 400
        if op == 'manual':
            mm = cf.get('mk') if cf.get('mk') in MERC else mks[0]
            u.update({'mmk': mm, 'lado': 'CALL' if cf.get('lado') == 'CALL' else 'PUT', 'G': 0, 'fase': 'enviando a entrada manual'})
        if continua:
            Wr, Lr = W, L
            s = u['sess']
            if Wr > 0 and s['pl'] >= Wr - 1e-9:
                return jsonify({'ok': False, 'erro': 'a meta desta sessão já foi batida: toque em “Nova sessão” para começar outra'}), 400
            if Lr > 0 and -s['pl'] + E > Lr + 1e-9:
                return jsonify({'ok': False, 'erro': 'a próxima entrada passaria do stop loss desta sessão: toque em “Nova sessão” para começar outra'}), 400
        nv.salva(conta, u)
        nv.kv.set(P + 'pmot:' + conta, '', ex=60)
        nv.liga(conta, True)
        Ls = nv.lista()
        if conta not in Ls:
            Ls.append(conta)
            nv.kv.jset(K_LISTA, Ls)
        nv.garante()
        if op == 'nuvem':
            nv.op_log(conta, {'t': int(time.time()), 'aviso': '☁ NUVEM LIGADA na conta %s · entrada $%.2f · %s · meta %s · stop loss $%.2f' % (
                info['tipo'].upper(), E, ('entrada única' if not G else '%s até G%d ×%s' % (modo, G, str(u['M']).replace('.', ','))), ('$%.2f' % W) if W else 'sem', L)})
        return jsonify({'ok': True, 'cfg': publico(u)})

    @app.route('/api/nuvem-visao/lab', methods=['POST'])
    def _nvi_lab():   # NUVEM-VISAO-LAB-V1
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        mk = d.get('mk') if d.get('mk') in MERC else 'R_100'
        h = int(num(d.get('horas'), 12, 3, 48))
        ch = P + 'lab:%s:%d' % (mk, h)
        st = nv.kv.jget(ch) or {}
        if st.get('st') == 'pronto' and time.time() - float(st.get('t') or 0) < 1800 and not d.get('novo'):
            return jsonify({'ok': True, 'st': 'pronto', 'res': st.get('res'), 't': st.get('t')})
        if st.get('st') == 'erro' and time.time() - float(st.get('t') or 0) < 60 and not d.get('novo'):
            return jsonify({'ok': False, 'erro': 'o laboratório falhou: ' + str(st.get('msg') or '')})
        if st.get('st') == 'rodando' and time.time() - float(st.get('t') or 0) < 300:
            return jsonify({'ok': True, 'st': 'rodando', 'msg': st.get('msg') or 'começando'})

        def roda():
            def prog(m):
                nv.kv.jset(ch, {'st': 'rodando', 't': time.time(), 'msg': m}, ex=600)
            try:
                prog('baixando as velas')
                r = laboratorio(mk, h, prog)
                nv.kv.jset(ch, {'st': 'pronto', 't': time.time(), 'res': r}, ex=86400)
            except Exception as e:
                nv.kv.jset(ch, {'st': 'erro', 't': time.time(), 'msg': str(e)[:200]}, ex=600)
        nv.kv.jset(ch, {'st': 'rodando', 't': time.time(), 'msg': 'começando'}, ex=600)
        threading.Thread(target=roda, daemon=True).start()
        return jsonify({'ok': True, 'st': 'rodando', 'msg': 'começando'})

    @app.route('/api/nuvem-visao/desligar', methods=['POST'])
    def _nvi_desligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        if u and not nv.ligado(conta) and not u.get('ab') and u.get('parado'):   # V2.6: já estava parado (meta, perda, trava): não troca o motivo
            return jsonify({'ok': True, 'ja': True})
        mot = 'encerrado por você' + (' (o contrato aberto termina normalmente)' if u.get('ab') else '')
        nv.kv.set(P + 'pmot:' + conta, mot, ex=86400)
        nv.liga(conta, False)
        if u:
            u['parado'], u['t_parou'], u['fase'] = mot, int(time.time()), 'parado'
            u.pop('an_ate', None)
            nv.salva(conta, u)
        nv.op_log(conta, {'t': int(time.time()), 'aviso': 'ALPHA VISÃO encerrado por você'})
        return jsonify({'ok': True})

    @app.route('/api/nuvem-visao/zerar', methods=['POST'])
    def _nvi_zerar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        if d.get('hist'):   # V2.5: lixeira do histórico (não mexe no resultado da sessão)
            nv.kv.jset(P + 'ops:' + conta, [], ex=86400 * 30)
            return jsonify({'ok': True})
        if nv.ligado(conta):
            return jsonify({'ok': False, 'erro': 'encerre antes de zerar a sessão'}), 400
        u = nv.cfg(conta)
        if u:
            u['sess'] = {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'cw': 0, 'cl': 0}
            u['t_sess'], u['parado'], u['t_lig'] = int(time.time()), '', int(time.time())
            u['banca0'] = float(info['saldo']) if info.get('saldo') is not None else u.get('banca0')
            nv.salva(conta, u)
        return jsonify({'ok': True})

    @app.route('/api/nuvem-visao/estado', methods=['POST'])
    def _nvi_estado():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        if u:
            u['ligado'] = nv.ligado(conta)
        mk = d.get('mk') if d.get('mk') in MERC else None
        if u and u.get('ligado'):
            mk = ((u.get('ab') or {}).get('mk')) or ((u.get('an') or {}).get('mk')) or mk
        mk = mk or PADRAO[0]
        nv.pede(mk)
        try:
            if nv.pid != os.getpid():
                nv.garante()
        except Exception:
            pass
        mt = float(nv.kv.get(K_MOTOR) or 0)
        h = nv.kv.get(P + 'hb:' + conta)
        cd = nv.kv.jget(P + 'cd:' + mk, {}) or {}
        an_local = None
        if cd.get('c') and not (u and u.get('ligado')):
            try:
                an_local = analisa(cd['c'])
            except Exception:
                an_local = None
        return jsonify({'ok': True, 'versao': VERSAO, 'cfg': publico(u) if u else None, 'ops': (nv.kv.jget(P + 'ops:' + conta, []) or [])[:int(num(d.get('n'), 60, 1, 200))],
                        'dias': nv.dias(conta), 'mk': mk, 'cd': cd.get('c') or [], 'tk': cd.get('t') or [], 'an0': an_local,
                        'plac': nv.kv.jget(P + 'plac3:' + conta, {}) or {}, 'motor': time.time() - mt < 60,
                        'robo_idade': int(time.time() - float(h)) if h else None, 'saldo': info.get('saldo'), 'agora': time.time()})

    @app.route('/api/admin/nuvem-visao', methods=['GET'])
    def _nvi_admin():
        s = os.environ.get('ADMIN_SENHA', '')
        if not s or request.headers.get('X-Admin-Token') != s:
            return jsonify({'ok': False}), 403
        out = []
        for conta in nv.lista():
            u = nv.cfg(conta)
            out.append({'conta': conta[:3] + '…' + conta[-3:], 'tipo': u.get('tipo'), 'op': u.get('op'), 'ligado': nv.ligado(conta), 'parado': u.get('parado'), 'sess': u.get('sess'), 'fase': u.get('fase')})
        return jsonify({'ok': True, 'versao': VERSAO, 'lider': nv.lider, 'pid': nv.pid, 'ws': EST['ws'], 'ticks': EST['ticks'], 'hist': EST['hist'], 'pessoas': out})

    log('%s registrada' % VERSAO)
    return nv
