# -*- coding: utf-8 -*-
"""MESA-AGENTES-V1 — Mesa de agentes do Alpha Global + histórico longo para a Fábrica.

1) Histórico longo (para a Fábrica testar ANOS, não só o ~1 ano que a Deriv guarda):
   - Bitcoin / Ethereum: Binance (velas de 1 h desde 2018)
   - Ouro, Prata e forex: Dukascopy (velas de 1 h desde 2018)
   GET /api/hist/longo?sym=frxXAUUSD&g=3600   -> {status: pronto|baixando|erro|sem_fonte, c: [[t,o,h,l,c],...]}
   GET /api/hist/teste                          -> confere se o servidor alcança a Binance e a Dukascopy

2) Mesa de agentes: cada agente é uma regra da Fábrica (mercado + tempo gráfico + regra + saída).
   Um laço no servidor analisa cada vela fechada, abre o multiplicador SOZINHO na conta DEMO,
   acompanha até fechar (alvo, stop ou tempo máximo) e grava cada resultado, ganho ou perda.
   Só aceita conta DEMO. As contas são as mesmas da Fábrica/Laboratório (mesmo código das regras).
   GET  /api/mesa/estado                       (público: o Escritório mostra)
   POST /api/mesa/conectar   {token, conta}    (X-Admin-Token = ADMIN_SENHA)
   POST /api/mesa/ligar      {ligada: true/false}
   POST /api/mesa/agente     {agente: {...}}   (cria ou atualiza)
   POST /api/mesa/agente/remover {id}
   POST /api/mesa/zerar      {id}              (apaga o placar de um agente)
"""
import os, io, json, time, math, gzip, uuid, lzma, base64, struct, zipfile, threading, traceback
import urllib.request, urllib.error
from datetime import datetime, timezone

VERSAO = 'MESA-AGENTES-V4.5'  # V4.5 CONSENSO-V1: regra 'cons' (4 tempos gráficos) ·  # V4.4 VETOS-V1: Agente Notícias + Agente Correlação ·  # V4.3 MESA-TRAVA-V1: trava de lucro na demo e medição com/sem trava na sombra ·  # V4.2: rota /api/hist/subir (histórico baixado no computador do admin) · V4.1 V4.1: download da Dukascopy guarda mês a mês e repete os recusados · V4 V4: 4 regras novas, agentes SOMBRA (virtuais), diretor (promove/aposenta) e auditor
# V3  # V3: analistas (filtros da Fábrica V5) + cópia do placar no Supabase (tabela mesa_ops)
# V2  # V2: stop do dia (mesa e agente) + aposentadoria automática + etapas
API = 'https://api.derivws.com/trading/v1/options'
APP_ID = os.environ.get('DERIV_OAUTH_APP_ID', '34lv1PuWzjElEuwWcDLyr')
HOLD = {3600: 72, 900: 288, 300: 864}
NOME = {'cryBTCUSD': 'Bitcoin', 'cryETHUSD': 'Ethereum', 'frxXAUUSD': 'Ouro', 'frxXAGUSD': 'Prata', 'frxEURUSD': 'EUR/USD',
        'frxGBPUSD': 'GBP/USD', 'frxUSDJPY': 'USD/JPY', 'frxAUDUSD': 'AUD/USD', 'frxUSDCAD': 'USD/CAD', 'frxUSDCHF': 'USD/CHF',
        'frxEURJPY': 'EUR/JPY', 'frxGBPJPY': 'GBP/JPY', 'frxEURGBP': 'EUR/GBP', 'frxAUDJPY': 'AUD/JPY'}
REGRA_N = {'cons': 'Consenso 4 tempos (5m/15m/1h/4h) + repique na EMA 9',   # CONSENSO-V1
           'smc': 'SMC (reteste do order block)', 'tend': 'Tendência EMA 20/50', 'rsi': 'Reversão do RSI', 'romp': 'Rompimento do dia anterior',
           'lon': 'Rompimento da faixa da Ásia (abertura de Londres)', 'ny': 'Rompimento da 1ª hora de Nova York',
           'don': 'Rompimento Donchian 55 velas', 'bb': 'Volta para dentro da Bollinger 20/2'}
TF_N = {3600: '1h', 900: '15m', 300: '5m'}


def log(*a):
    print('[Mesa]', *a, flush=True)


# ════════════════════════ armazenamento (Redis, ou memória) ════════════════════════
class KV(object):
    def __init__(self):
        self._m = {}
        self._l = {}
        self._r = None
        url = os.environ.get('REDIS_URL', '').strip()
        if url:
            try:
                import redis as _redis
                self._r = _redis.from_url(url, decode_responses=True, socket_timeout=4)
                self._r.ping()
            except Exception as e:
                log('Redis indisponivel, usando memoria:', e)
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

    def delete(self, k):
        self._m.pop(k, None)
        if self._r is not None:
            try:
                self._r.delete(k)
            except Exception:
                pass

    def jget(self, k, d=None):
        try:
            v = self.get(k)
            return json.loads(v) if v else d
        except Exception:
            return d

    def jset(self, k, v):
        self.set(k, json.dumps(v, ensure_ascii=False))

    def push(self, k, v, cap=20000):
        s = json.dumps(v, ensure_ascii=False)
        self._l.setdefault(k, []).insert(0, s)
        del self._l[k][cap:]
        if self._r is not None:
            try:
                self._r.lpush(k, s)
                self._r.ltrim(k, 0, cap - 1)
            except Exception:
                pass

    def lista(self, k, n=20000):
        if self._r is not None:
            try:
                return [json.loads(x) for x in self._r.lrange(k, 0, n - 1)]
            except Exception:
                pass
        return [json.loads(x) for x in self._l.get(k, [])[:n]]

    def trava(self, k, dono, ex):
        if self._r is None:
            cur = self._m.get(k)
            if cur in (None, dono):
                self._m[k] = dono
                return True
            return False
        try:
            if self._r.set(k, dono, nx=True, ex=ex):
                return True
            if self._r.get(k) == dono:
                self._r.expire(k, ex)
                return True
        except Exception:
            return True
        return False

    @property
    def redis(self):
        return self._r is not None


# ════════════════════════ indicadores e regras (cópia fiel da Fábrica / global-smc.js) ════════════════════════
def ema(a, n):
    k = 2.0 / (n + 1)
    e = a[0] if a else 0
    o = []
    for v in a:
        e = v * k + e * (1 - k)
        o.append(e)
    return o


def atr_s(C, n):
    o = [0.0] * len(C)
    a = 0.0
    for i in range(1, len(C)):
        t = max(C[i]['h'] - C[i]['l'], abs(C[i]['h'] - C[i - 1]['c']), abs(C[i]['l'] - C[i - 1]['c']))
        a = (a * (i - 1) + t) / i if i <= n else (a * (n - 1) + t) / n
        o[i] = a
    return o


def supertrend(C, at, k=3.0):
    """CONSENSO-V1: SuperTrend clássico (ATR 10, multiplicador 3). Devolve (linha, True se em alta) da última vela."""
    up_band = dn_band = None
    alta = True
    linha = 0.0
    for j in range(len(C)):
        if not at[j]:
            continue
        m = (C[j]['h'] + C[j]['l']) / 2.0
        bu, bd = m + k * at[j], m - k * at[j]
        if up_band is None:
            up_band, dn_band = bu, bd
        else:
            up_band = bu if (bu < up_band or C[j - 1]['c'] > up_band) else up_band
            dn_band = bd if (bd > dn_band or C[j - 1]['c'] < dn_band) else dn_band
        if alta and C[j]['c'] < dn_band:
            alta = False
        elif (not alta) and C[j]['c'] > up_band:
            alta = True
        linha = dn_band if alta else up_band
    return linha, alta


def rsi_s(c, n):
    o = [50.0] * len(c)
    g = l = 0.0
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        up = d if d > 0 else 0.0
        dn = -d if d < 0 else 0.0
        if i <= n:
            g += up / n
            l += dn / n
        else:
            g = (g * (n - 1) + up) / n
            l = (l * (n - 1) + dn) / n
        if i >= n:
            o[i] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    return o


SMC_K = 3


def _abriu(C, i):
    o = C[i].get('o')
    if o is not None and math.isfinite(o):
        return o
    return C[i - 1]['c'] if i else C[i]['c']


def smc_analisa(C):
    """global-smc.js analisa(C, porBarra=true). Devolve sig/slL/slS por vela + tendência e order blocks vivos."""
    n = len(C)
    K = SMC_K
    SH, SL, obs, fvg = [], [], [], []
    tr = 0
    lastSH = lastSL = None
    sig_a = [0] * n
    slL = [0.0] * n
    slS = [0.0] * n
    at = 0.0
    for i in range(n):
        if i >= 1:
            t1 = max(C[i]['h'] - C[i]['l'], abs(C[i]['h'] - C[i - 1]['c']), abs(C[i]['l'] - C[i - 1]['c']))
            at = (at * (i - 1) + t1) / i if i <= 14 else (at * 13 + t1) / 14
        j = i - K
        if j >= K:
            isH = isL = True
            for q in range(j - K, j + K + 1):
                if q == j:
                    continue
                if C[q]['h'] >= C[j]['h']:
                    isH = False
                if C[q]['l'] <= C[j]['l']:
                    isL = False
            if isH:
                lastSH = {'i': j, 'p': C[j]['h'], 'br': False}
                SH.append(lastSH)
            if isL:
                lastSL = {'i': j, 'p': C[j]['l'], 'br': False}
                SL.append(lastSL)
        b = C[i]
        if lastSH and not lastSH['br'] and b['c'] > lastSH['p']:
            lastSH['br'] = True
            tr = 1
            for u in range(i - 1, max(0, i - 25) - 1, -1):
                if C[u]['c'] < _abriu(C, u):
                    obs.append({'d': 1, 'h': C[u]['h'], 'l': C[u]['l'], 'i0': u, 'i': i, 'viva': True, 'tocou': False})
                    break
        if lastSL and not lastSL['br'] and b['c'] < lastSL['p']:
            lastSL['br'] = True
            tr = -1
            for w in range(i - 1, max(0, i - 25) - 1, -1):
                if C[w]['c'] > _abriu(C, w):
                    obs.append({'d': -1, 'h': C[w]['h'], 'l': C[w]['l'], 'i0': w, 'i': i, 'viva': True, 'tocou': False})
                    break
        if i >= 2:
            if C[i]['l'] > C[i - 2]['h']:
                fvg.append({'d': 1, 'h': C[i]['l'], 'l': C[i - 2]['h'], 'i0': i - 1, 'aberto': True})
            elif C[i]['h'] < C[i - 2]['l']:
                fvg.append({'d': -1, 'h': C[i - 2]['l'], 'l': C[i]['h'], 'i0': i - 1, 'aberto': True})
        sig = 0
        o = len(obs) - 1
        while o >= 0 and o >= len(obs) - 8:
            z = obs[o]
            o -= 1
            if not z['viva'] or z['i'] >= i:
                continue
            if z['d'] > 0:
                if b['c'] < z['l']:
                    z['viva'] = False
                    continue
                if not z['tocou'] and b['l'] <= z['h']:
                    z['tocou'] = True
                    if tr == 1 and b['c'] > z['l']:
                        sig = 1
            else:
                if b['c'] > z['h']:
                    z['viva'] = False
                    continue
                if not z['tocou'] and b['h'] >= z['l']:
                    z['tocou'] = True
                    if tr == -1 and b['c'] < z['h']:
                        sig = -1
        f = len(fvg) - 1
        while f >= 0 and f >= len(fvg) - 12:
            g = fvg[f]
            f -= 1
            if not g['aberto'] or g['i0'] >= i - 1:
                continue
            if (b['l'] <= g['l']) if g['d'] > 0 else (b['h'] >= g['h']):
                g['aberto'] = False
        sig_a[i] = sig
        sl = ss = 0.0
        a = len(SL) - 1
        while a >= 0 and a >= len(SL) - 6:
            if SL[a]['p'] < b['c'] - 0.3 * at:
                sl = SL[a]['p'] - 0.2 * at
                break
            a -= 1
        c = len(SH) - 1
        while c >= 0 and c >= len(SH) - 6:
            if SH[c]['p'] > b['c'] + 0.3 * at:
                ss = SH[c]['p'] + 0.2 * at
                break
            c -= 1
        slL[i] = sl if (sl > 0 and sl < b['c']) else 0.0
        slS[i] = ss if ss > b['c'] else 0.0
    vivas = len([z for z in obs[-8:] if z['viva']])
    return {'sig': sig_a, 'slL': slL, 'slS': slS, 'tr': tr, 'obs': vivas}


def sinais(B):
    """global-fabrica.js sinais(B)."""
    n = len(B)
    cl = [c['c'] for c in B]
    e20, e50, rs = ema(cl, 20), ema(cl, 50), rsi_s(cl, 14)
    S = {'atr': atr_s(B, 14), 'smc': [0] * n, 'tend': [0] * n, 'rsi': [0] * n, 'romp': [0] * n, 'lon': [0] * n, 'ny': [0] * n, 'don': [0] * n, 'bb': [0] * n,
         'slL': [0.0] * n, 'slS': [0.0] * n, 'ses': [0] * n, 'e20': e20, 'e50': e50, 'rs': rs}
    A = smc_analisa(B)
    S['smc'], S['slL'], S['slS'], S['tr'], S['obs'] = A['sig'], A['slL'], A['slS'], A['tr'], A['obs']
    dia = ''
    dH = dL = pH = pL = 0.0
    fezU = fezD = ''
    aH = aL = nH = nL = None
    fLU = fLD = fNU = fND = ''
    bbU = [0.0] * n
    bbL = [0.0] * n
    for i in range(n):
        if i >= 19:
            sm = 0.0
            for k in range(i - 19, i + 1):
                sm += cl[k]
            m = sm / 20
            v = 0.0
            for k in range(i - 19, i + 1):
                v += (cl[k] - m) * (cl[k] - m)
            sd = math.sqrt(v / 20)
            bbU[i], bbL[i] = m + 2 * sd, m - 2 * sd
    for i in range(1, n):
        h = datetime.fromtimestamp(B[i]['t'], tz=timezone.utc)
        d = h.strftime('%Y-%m-%d')
        hr = h.hour
        S['ses'][i] = 1 if 7 <= hr < 17 else 0
        if i > 60:
            if e20[i] > e50[i] and B[i]['l'] <= e20[i] and B[i]['c'] > e20[i] and B[i - 1]['c'] > e20[i - 1]:
                S['tend'][i] = 1
            elif e20[i] < e50[i] and B[i]['h'] >= e20[i] and B[i]['c'] < e20[i] and B[i - 1]['c'] < e20[i - 1]:
                S['tend'][i] = -1
            if rs[i] < 25 and rs[i - 1] >= 25:
                S['rsi'][i] = 1
            elif rs[i] > 75 and rs[i - 1] <= 75:
                S['rsi'][i] = -1
        if d != dia:
            if dia:
                pH, pL = dH, dL
            dia = d
            dH, dL = B[i]['h'], B[i]['l']
            aH = aL = nH = nL = None
        else:
            dH, dL = max(dH, B[i]['h']), min(dL, B[i]['l'])
        c = B[i]['c']
        if hr < 7:
            aH = B[i]['h'] if aH is None else max(aH, B[i]['h'])
            aL = B[i]['l'] if aL is None else min(aL, B[i]['l'])
        elif hr < 11 and aH is not None:
            if c > aH and fLU != d:
                S['lon'][i] = 1
                fLU = d
            elif c < aL and fLD != d:
                S['lon'][i] = -1
                fLD = d
        if hr == 13:
            nH = B[i]['h'] if nH is None else max(nH, B[i]['h'])
            nL = B[i]['l'] if nL is None else min(nL, B[i]['l'])
        elif 14 <= hr < 18 and nH is not None:
            if c > nH and fNU != d:
                S['ny'][i] = 1
                fNU = d
            elif c < nL and fND != d:
                S['ny'][i] = -1
                fND = d
        if i >= 56:
            mx = max(B[k]['h'] for k in range(i - 55, i))
            mx1 = max(B[k]['h'] for k in range(i - 56, i - 1))
            mn = min(B[k]['l'] for k in range(i - 55, i))
            mn1 = min(B[k]['l'] for k in range(i - 56, i - 1))
            if c > mx and B[i - 1]['c'] <= mx1:
                S['don'][i] = 1
            elif c < mn and B[i - 1]['c'] >= mn1:
                S['don'][i] = -1
            S['dmx'], S['dmn'] = mx, mn
        if i >= 20:
            if cl[i - 1] < bbL[i - 1] and c > bbL[i]:
                S['bb'][i] = 1
            elif cl[i - 1] > bbU[i - 1] and c < bbU[i]:
                S['bb'][i] = -1
        if pH and B[i]['c'] > pH and fezU != d:
            S['romp'][i] = 1
            fezU = d
        elif pL and B[i]['c'] < pL and fezD != d:
            S['romp'][i] = -1
            fezD = d
    S['pH'], S['pL'] = pH, pL
    S['aH'], S['aL'], S['nH'], S['nL'], S['bbU'], S['bbL'] = aH, aL, nH, nL, bbU, bbL
    return S


AN_N = {'tf': 'tendência maior a favor (EMA 200)', 'vA': 'volatilidade alta', 'vB': 'volatilidade baixa', 'mom': 'momento a favor (24 velas)', 'dia': 'sem segunda e sexta'}


def analistas(B):
    """global-fabrica.js V5 analistas(B)"""
    n = len(B)
    cl = [c['c'] for c in B]
    e200 = ema(cl, 200)
    at = atr_s(B, 14)
    r = [at[i] / cl[i] if cl[i] > 0 else 0 for i in range(n)]
    pct = [0.0] * n
    wd = [0] * n
    for i in range(n):
        a = max(0, i - 499)
        ri = r[i]
        pct[i] = sum(1 for j in range(a, i + 1) if r[j] <= ri) / (i - a + 1)
        wd[i] = (datetime.fromtimestamp(B[i]['t'], tz=timezone.utc).weekday() + 1) % 7   # 0 = domingo, como getUTCDay
    return {'e200': e200, 'pct': pct, 'wd': wd, 'cl': cl}


def passa(A, k, i, lado):
    if k == 'tf':
        return A['cl'][i] > A['e200'][i] if lado > 0 else A['cl'][i] < A['e200'][i]
    if k == 'vA':
        return A['pct'][i] >= 0.5
    if k == 'vB':
        return A['pct'][i] < 0.5
    if k == 'mom':
        return i >= 24 and lado * (A['cl'][i] - A['cl'][i - 24]) > 0
    if k == 'dia':
        return A['wd'][i] not in (1, 5)
    return True


def niveis(x, K, stk, comm, ent, atr, slPx):
    """global-fabrica.js niveis(): stop/alvo em $ com a comissão."""
    cap = (stk - 2 * comm) / K
    if x.get('es'):
        if not (slPx and slPx > 0):
            return None
        slD = abs(ent - slPx) / ent
        if not (slD > 0) or slD > cap:
            return None
        tpD = slD * float(x.get('r') or 1.5)
    elif x.get('a1'):
        if not (atr and atr > 0):
            return None
        slD = min(float(x['a1']) * atr / ent, cap)
        tpD = float(x['a2']) * atr / ent
    else:
        slD = min((float(x['sl']) - comm) / K, cap)
        tpD = (float(x['tp']) + comm) / K
    sl_ = slD * K + comm
    tp_ = tpD * K - comm
    if not (sl_ >= 1) or not (tp_ >= 1):
        return None
    return {'slD': slD, 'tpD': tpD, 'sl': math.floor(sl_ * 100) / 100, 'tp': round(tp_ * 100) / 100}


def _n(v):
    return ('%g' % float(v)).replace('.', ',')


def saida_nome(x):
    if x.get('es'):
        return 'stop estrutural · alvo %s× o risco' % _n(x.get('r') or 1.5)
    if x.get('a1'):
        return 'stop %s×ATR · alvo %s×ATR' % (_n(x['a1']), _n(x['a2']))
    return 'stop $%s · alvo $%s' % (_n(x.get('sl')), _n(x.get('tp')))


# ════════════════════════ histórico longo (Binance / Dukascopy) ════════════════════════
HL_DIR = os.environ.get('MESA_HIST_DIR', '/tmp/mesa_hist')
HL_INI = int(datetime(2018, 1, 1, tzinfo=timezone.utc).timestamp())
BINA = {'cryBTCUSD': 'BTCUSDT', 'cryETHUSD': 'ETHUSDT', 'cryLTCUSD': 'LTCUSDT', 'cryXRPUSD': 'XRPUSDT', 'cryBNBUSD': 'BNBUSDT'}
DUKA = {'frxXAUUSD': 'XAUUSD', 'frxXAGUSD': 'XAGUSD', 'frxEURUSD': 'EURUSD', 'frxGBPUSD': 'GBPUSD', 'frxUSDJPY': 'USDJPY',
        'frxAUDUSD': 'AUDUSD', 'frxUSDCAD': 'USDCAD', 'frxUSDCHF': 'USDCHF', 'frxEURJPY': 'EURJPY', 'frxGBPJPY': 'GBPJPY',
        'frxEURGBP': 'EURGBP', 'frxAUDJPY': 'AUDJPY', 'frxNZDUSD': 'NZDUSD'}
FAIXA = {'XAUUSD': (200, 20000), 'XAGUSD': (2, 500), 'USDJPY': (40, 400), 'EURJPY': (40, 400), 'GBPJPY': (40, 500), 'AUDJPY': (20, 300)}
HL_JOBS = {}
HL_LOCK = threading.Lock()
HL_KV = None          # o KV da mesa (Redis): o download de cada mercado roda em 1 processo só
HL_GZ = {}            # (sym, g) -> (mtime, bytes gzip) para não reler o arquivo a cada pedido
HL_DONO = uuid.uuid4().hex[:10]
UA = {'User-Agent': 'Mozilla/5.0 (AlphaDolar Fabrica)'}


HL_SEM = threading.BoundedSemaphore(1)   # V3.2: no máximo 2 downloads ao mesmo tempo (a Dukascopy devolve 503 se pedir muito)
HL_FILA = threading.Lock()                # V3.2: um mercado da Dukascopy por vez


def _baixa(url, to=20):
    rq = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(rq, timeout=to) as r:
        return r.read()


def _hl_path(sym, g):
    return os.path.join(HL_DIR, '%s_%d.json' % (sym, g))


def _duka_mes(ins, y, m):
    """velas de 1 h de um mês inteiro (arquivo BID_candles_hour_1.bi5; o mês da URL começa em 00)."""
    url = 'https://datafeed.dukascopy.com/datafeed/%s/%04d/%02d/BID_candles_hour_1.bi5' % (ins, y, m - 1)
    try:
        with HL_SEM:
            raw = _baixa(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise
    if not raw:
        return []
    try:
        dat = lzma.decompress(raw, format=lzma.FORMAT_ALONE)
    except Exception:
        dat = lzma.decompress(raw)
    ini = int(datetime(y, m, 1, tzinfo=timezone.utc).timestamp())
    out = []
    for k in range(0, len(dat) - 23, 24):
        t, o, c, a, b, v = struct.unpack('>IIIIIf', dat[k:k + 24])
        if v <= 0:
            continue
        out.append([ini + t, o, max(o, c, a, b), min(o, c, a, b), c])
    return out


def _duka_escala(ins, linhas):
    if not linhas:
        return 1.0
    med = sorted(x[4] for x in linhas)[len(linhas) // 2]
    lo, hi = FAIXA.get(ins, (0.3, 5))
    for f in (1e5, 1e3, 1e2, 1e4, 1e6, 10.0, 1.0):
        if lo <= med / f <= hi:
            return f
    return 1e5


def _duka(sym, prog):
    ins = DUKA[sym]
    agora = datetime.now(timezone.utc)
    meses = []
    y, m = 2018, 1
    while (y, m) <= (agora.year, agora.month):
        meses.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    # MESA-AGENTES-V4.1: cada mês baixado fica guardado no Redis (um erro não joga fora horas de download),
    # "connection reset" espera como 503, e os meses recusados são tentados de novo no fim (3 voltas).
    atual = (agora.year, agora.month)

    def ck(ym):
        return 'mesa:dkm:%s:%04d-%02d' % (ins, ym[0], ym[1])

    def do_cache(ym):
        if HL_KV is None or ym == atual:
            return None
        try:
            b = HL_KV.get(ck(ym))
            return json.loads(gzip.decompress(base64.b64decode(b)).decode()) if b else None
        except Exception:
            return None

    def guarda(ym, L):
        if HL_KV is None or ym == atual:
            return
        try:
            HL_KV.set(ck(ym), base64.b64encode(gzip.compress(json.dumps(L, separators=(',', ':')).encode(), 6)).decode(), ex=60 * 86400)
        except Exception as e:
            log('cache do mes %s: %s' % (ck(ym), e))

    def espera(seg, feito, msg):
        for _ in range(max(1, int(math.ceil(seg / 20.0)))):
            prog(feito, len(meses), msg)          # mantém a trava e mostra que está vivo
            time.sleep(min(20, seg))

    def um(ym, feito, tentativas):
        L = do_cache(ym)
        if L is not None:
            return L, True
        y, m = ym
        for tent in range(tentativas):
            try:
                L = _duka_mes(ins, y, m)
                guarda(ym, L)
                time.sleep(1.0)
                return L, True
            except Exception as e:
                es = str(e)
                lento = any(x in es for x in ('503', '429', '104', 'reset', 'timed out', 'timeout', 'Temporary', 'EOF'))
                if tent < tentativas - 1:
                    espera(60 * (tent + 1) if lento else 3 * (tent + 1), feito, 'Dukascopy %s · %d-%02d recusado, esperando para tentar de novo' % (ins, y, m))
                else:
                    log('Dukascopy %s %d-%02d falhou: %s' % (ins, y, m, e))
        return [], False

    por_mes, falta = {}, []
    prog(0, len(meses), 'na fila (um mercado por vez)')
    with HL_FILA:
        for i, ym in enumerate(meses):
            L, ok = um(ym, i, 4)
            if ok:
                por_mes[ym] = L
            else:
                falta.append(ym)
            prog(i + 1, len(meses), 'Dukascopy %s' % ins + (' · %d mês(es) para repetir no fim' % len(falta) if falta else ''))
        for volta in range(3):
            if not falta:
                break
            espera(180, len(meses), 'Dukascopy %s · repetindo %d mês(es) recusado(s) (volta %d de 3)' % (ins, len(falta), volta + 1))
            ainda = []
            for ym in falta:
                L, ok = um(ym, len(meses), 3)
                if ok:
                    por_mes[ym] = L
                else:
                    ainda.append(ym)
            falta = ainda
    if falta:
        nomes = ['%d-%02d' % ym for ym in falta]
        prog(None, None, None, erro='faltaram %s' % ', '.join(nomes[:4]))
        # nunca guarda histórico com buraco (os meses que deram certo ficam no Redis para a próxima vez)
        raise RuntimeError('a Dukascopy recusou %d mês(es) (%s). Os outros ficaram guardados; peça de novo que ele baixa só o que falta.' % (len(falta), ', '.join(nomes[:4])))
    linhas = []
    for ym in meses:
        linhas += por_mes.get(ym, [])
    f = _duka_escala(ins, linhas)
    return [[r[0], r[1] / f, r[2] / f, r[3] / f, r[4] / f] for r in linhas], 'Dukascopy'


def _bina_t(v):
    t = int(float(v))
    while t > 1e11:
        t //= 1000
    return t


def _bina_api(par, prog):
    out, ini, fim = [], HL_INI * 1000, int(time.time() * 1000)
    tot = max(1, (fim - ini) // (3600000 * 1000) + 1)
    k = 0
    while ini < fim and k < 200:
        k += 1
        j = json.loads(_baixa('https://data-api.binance.vision/api/v3/klines?symbol=%s&interval=1h&startTime=%d&limit=1000' % (par, ini)).decode())
        if not j:
            break
        for r in j:
            out.append([_bina_t(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])])
        ini = int(j[-1][0]) + 3600000
        prog(k, tot, 'Binance %s' % par)
        if len(j) < 1000:
            break
    return out


def _bina_zip(par, prog):
    agora = datetime.now(timezone.utc)
    meses, y, m = [], 2018, 1
    while (y, m) < (agora.year, agora.month):
        meses.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    out = []

    def csv(raw):
        z = zipfile.ZipFile(io.BytesIO(raw))
        for nm in z.namelist():
            for ln in z.read(nm).decode().splitlines():
                p = ln.split(',')
                if len(p) >= 5 and p[0][:1].isdigit():
                    out.append([_bina_t(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4])])
    for i, (y, m) in enumerate(meses):
        try:
            csv(_baixa('https://data.binance.vision/data/spot/monthly/klines/%s/1h/%s-1h-%04d-%02d.zip' % (par, par, y, m)))
        except Exception as e:
            log('Binance zip %s %d-%02d: %s' % (par, y, m, e))
        prog(i + 1, len(meses) + 1, 'Binance %s %d/%02d' % (par, y, m))
    for d in range(1, agora.day):
        try:
            csv(_baixa('https://data.binance.vision/data/spot/daily/klines/%s/1h/%s-1h-%04d-%02d-%02d.zip' % (par, par, agora.year, agora.month, d)))
        except Exception:
            pass
    return out


def _bina(sym, prog):
    par = BINA[sym]
    try:
        L = _bina_api(par, prog)
        if len(L) > 5000:
            return L, 'Binance'
    except Exception as e:
        log('Binance API %s: %s (vou pelos arquivos mensais)' % (par, e))
    return _bina_zip(par, prog), 'Binance (arquivos)'


def _hl_job(sym, g):
    key = (sym, g)
    st = HL_JOBS[key]
    try:
        def prog(a, b, msg, erro=None):
            if erro:
                st['falhas'] = st.get('falhas', 0) + 1
                st['ult_erro'] = erro
            else:
                st['pct'] = int(a * 100 / max(1, b))
                st['msg'] = msg
            st['hb'] = time.time()
            if HL_KV is not None:
                HL_KV.set('mesa:hl:%s' % sym, json.dumps(st), ex=900)
                HL_KV.trava('mesa:hlt:%s' % sym, HL_DONO, 120)
        if sym in BINA:
            L, fonte = _bina(sym, prog)
        else:
            L, fonte = _duka(sym, prog)
        vis, lim = {}, []
        for r in L:
            if r[0] >= HL_INI and r[0] not in vis and r[4] > 0:
                vis[r[0]] = 1
                lim.append([r[0]] + [float('%.6g' % v) for v in r[1:]])
        lim.sort(key=lambda r: r[0])
        if len(lim) < 1000:
            raise RuntimeError('a fonte %s entregou só %d velas' % (fonte, len(lim)))
        os.makedirs(HL_DIR, exist_ok=True)
        tmp = _hl_path(sym, g) + '.tmp'
        with open(tmp, 'w') as f:
            json.dump({'sym': sym, 'g': g, 'fonte': fonte, 'n': len(lim), 'de': lim[0][0], 'ate': lim[-1][0], 'em': time.time(), 'c': lim}, f, separators=(',', ':'))
        os.replace(tmp, _hl_path(sym, g))
        st.update({'status': 'pronto', 'pct': 100, 'msg': '%s: %d velas' % (fonte, len(lim))})
        if HL_KV is not None:
            with open(_hl_path(sym, g), 'rb') as f:
                HL_KV.set('mesa:hlgz2:%s' % sym, base64.b64encode(gzip.compress(f.read(), 6)).decode(), ex=30 * 86400)
            HL_KV.delete('mesa:hl:%s' % sym)
            HL_KV.delete('mesa:hlt:%s' % sym)
            if sym in DUKA:   # V4.1: com o histórico inteiro guardado, os pedaços mês a mês não precisam mais ocupar o Redis
                y, m = 2018, 1
                while (y, m) <= (datetime.now(timezone.utc).year, datetime.now(timezone.utc).month):
                    HL_KV.delete('mesa:dkm:%s:%04d-%02d' % (DUKA[sym], y, m))
                    m += 1
                    if m > 12:
                        y, m = y + 1, 1
        log('historico longo %s pronto: %s %d velas desde %s' % (sym, fonte, len(lim), datetime.fromtimestamp(lim[0][0], tz=timezone.utc).date()))
    except Exception as e:
        st.update({'status': 'erro', 'erro': str(e)[:300], 't': time.time()})
        if HL_KV is not None:
            HL_KV.set('mesa:hl:%s' % sym, json.dumps(st), ex=120)
        log('historico longo %s falhou: %s' % (sym, e))


def hist_longo(sym, g):
    if g != 3600:
        return {'status': 'sem_fonte', 'erro': 'histórico longo só em velas de 1 hora'}
    if sym not in BINA and sym not in DUKA:
        return {'status': 'sem_fonte', 'erro': 'sem fonte externa para ' + sym}
    p = _hl_path(sym, g)
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 30 * 86400:
        return {'status': 'pronto', 'arquivo': p}
    key = (sym, g)
    # MESA-AGENTES-V3: o resultado fica também no Redis (todos os servidores enxergam e sobrevive ao deploy)
    if HL_KV is not None:
        b = HL_KV.get('mesa:hlgz2:%s' % sym)
        if b:
            try:
                os.makedirs(HL_DIR, exist_ok=True)
                with open(p + '.tmp', 'wb') as f:
                    f.write(gzip.decompress(base64.b64decode(b)))
                os.replace(p + '.tmp', p)
                return {'status': 'pronto', 'arquivo': p}
            except Exception as e:
                log('copia do Redis falhou:', e)
    with HL_LOCK:
        st = HL_JOBS.get(key)
        if st and st.get('status') == 'baixando':
            return dict(st)
        if HL_KV is not None:
            rs = HL_KV.jget('mesa:hl:%s' % sym)
            if rs and rs.get('status') == 'baixando' and time.time() - float(rs.get('hb') or rs.get('t') or 0) < 90:
                return rs
            if rs and rs.get('status') == 'erro' and time.time() - float(rs.get('t') or 0) < 120:
                return rs
            if not HL_KV.trava('mesa:hlt:%s' % sym, HL_DONO, 120):
                return rs or {'status': 'baixando', 'pct': 0, 'msg': 'outro servidor está baixando'}
        elif st and st.get('status') == 'erro' and time.time() - st.get('t', 0) < 120:
            return dict(st)
        st = HL_JOBS[key] = {'status': 'baixando', 'pct': 0, 'msg': 'começando', 't': time.time(), 'hb': time.time(), 'host': HOST}
        threading.Thread(target=_hl_job, args=(sym, g), daemon=True).start()
    return dict(st)


HOST = '%s:%d' % (__import__('socket').gethostname(), os.getpid())


def hist_status():
    out = {'servidor': HOST}
    for sym in ['cryBTCUSD', 'cryETHUSD', 'frxXAUUSD', 'frxXAGUSD', 'frxEURUSD', 'frxGBPUSD', 'frxUSDJPY']:
        rs = HL_KV.jget('mesa:hl:%s' % sym) if HL_KV is not None else None
        out[sym] = {'arquivo_aqui': os.path.exists(_hl_path(sym, 3600)), 'copia_redis': bool(HL_KV is not None and HL_KV.get('mesa:hlgz2:%s' % sym)),
                    'download': {k: v for k, v in (rs or {}).items() if k in ('status', 'pct', 'msg', 'falhas', 'ult_erro', 'host', 'erro')} or None}
    return out


def hist_teste():
    out = {}
    try:
        L = _duka_mes('XAUUSD', 2020, 3)
        out['dukascopy'] = {'ok': len(L) > 100, 'velas_marco_2020': len(L), 'exemplo': L[:1], 'escala': _duka_escala('XAUUSD', L)}
    except Exception as e:
        out['dukascopy'] = {'ok': False, 'erro': str(e)[:200]}
    try:
        j = json.loads(_baixa('https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1514764800000&limit=3').decode())
        out['binance_api'] = {'ok': len(j) == 3, 'exemplo': j[:1]}
    except Exception as e:
        out['binance_api'] = {'ok': False, 'erro': str(e)[:200]}
    try:
        raw = _baixa('https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2018-01.zip')
        out['binance_arquivos'] = {'ok': len(raw) > 1000, 'bytes': len(raw)}
    except Exception as e:
        out['binance_arquivos'] = {'ok': False, 'erro': str(e)[:200]}
    return out


# ════════════════════════ Deriv (REST + WebSocket com OTP) ════════════════════════
class DerivErro(Exception):
    pass


class Deriv(object):
    def __init__(self, tok, conta):
        self.tok, self.conta = tok, conta
        self.ws = None
        self.n = 1
        self.symkey = 'underlying_symbol'
        self.ult = 0

    def _rest(self, path, method='GET'):
        rq = urllib.request.Request(API + path, method=method, data=b'' if method == 'POST' else None,
                                    headers={'Authorization': 'Bearer ' + self.tok, 'Deriv-App-ID': APP_ID, 'User-Agent': 'AlphaDolar-Mesa'})
        try:
            with urllib.request.urlopen(rq, timeout=15) as r:
                return json.loads(r.read().decode() or '{}')
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise DerivErro('TOKEN')
            raise DerivErro('HTTP %d' % e.code)

    def contas(self):
        return self._rest('/accounts').get('data') or []

    def conecta(self):
        import websocket
        self.fecha()
        ac = [a for a in self.contas() if str(a.get('account_id')) == str(self.conta)]
        if not ac:
            raise DerivErro('conta %s não encontrada neste token' % self.conta)
        if str(ac[0].get('account_type')) != 'demo':
            raise DerivErro('a Mesa só opera em conta DEMO')
        url = (self._rest('/accounts/%s/otp' % self.conta, 'POST').get('data') or {}).get('url')
        if not url:
            raise DerivErro('OTP sem url')
        self.ws = websocket.create_connection(url, timeout=20)
        self.ult = time.time()

    def fecha(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        self.ws = None

    def req(self, obj, to=20):
        for tent in range(2):
            try:
                if self.ws is None:
                    self.conecta()
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
                raise DerivErro('tempo esgotado')
            except DerivErro as e:
                if str(e) == 'TOKEN' or 'DEMO' in str(e) or tent:
                    raise
                self.fecha()
            except Exception as e:
                self.fecha()
                if tent:
                    raise DerivErro(str(e)[:200])
        raise DerivErro('sem resposta')

    def req_sym(self, obj, sym, to=20):
        o = dict(obj)
        o[self.symkey] = sym
        r = self.req(o, to)
        msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error') and ('symbol' in msg.lower() or 'Properties not allowed' in msg or 'validation' in msg.lower()):
            self.symkey = 'symbol' if self.symkey == 'underlying_symbol' else 'underlying_symbol'
            o = dict(obj)
            o[self.symkey] = sym
            r = self.req(o, to)
        return r

    def velas(self, sym, g, n=1000):
        q = {'ticks_history': sym, 'underlying_symbol': sym, 'end': 'latest', 'count': n, 'style': 'candles', 'granularity': g}
        r = self.req(q, 30)
        em = str((r.get('error') or {}).get('message', ''))
        if r.get('error') and ('underlying_symbol' in em or 'Properties not allowed' in em or 'validation' in em.lower()):
            q.pop('underlying_symbol', None)
            r = self.req(q, 30)
        if r.get('error'):
            raise DerivErro(r['error'].get('message', 'erro nas velas'))
        return [{'t': int(c['epoch']), 'o': float(c['open']), 'h': float(c['high']), 'l': float(c['low']), 'c': float(c['close'])} for c in (r.get('candles') or [])]


# ════════════════════════ cópia do placar no Supabase (tabela mesa_ops) ════════════════════════
def _supa(path, method='GET', body=None, extra=None):
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_KEY', '')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL/SUPABASE_KEY não definidas')
    h = {'apikey': key, 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    if extra:
        h.update(extra)
    rq = urllib.request.Request(url + '/rest/v1/' + path, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    with urllib.request.urlopen(rq, timeout=15) as r:
        t = r.read().decode()
        return json.loads(t) if t else None


# ════════════════════════ a mesa ════════════════════════
PADRAO = [
    {'id': 'btc-smc-1h', 'nome': 'Agente Satoshi', 'sym': 'cryBTCUSD', 'g': 3600, 'regra': 'smc', 'f': '', 'x': {'es': 1, 'r': 1.5}},
    {'id': 'ouro-rsi-5m', 'nome': 'Agente Midas', 'sym': 'frxXAUUSD', 'g': 300, 'regra': 'rsi', 'f': '', 'x': {'sl': 40, 'tp': 40}},
    {'id': 'prata-rsi-15m', 'nome': 'Agente Argento', 'sym': 'frxXAGUSD', 'g': 900, 'regra': 'rsi', 'f': '', 'x': {'sl': 40, 'tp': 40}},
    {'id': 'prata-smc-1h', 'nome': 'Agente Prisma', 'sym': 'frxXAGUSD', 'g': 3600, 'regra': 'smc', 'f': 's', 'x': {'sl': 40, 'tp': 80}},
    {'id': 'jpy-romp-1h', 'nome': 'Agente Samurai', 'sym': 'frxUSDJPY', 'g': 3600, 'regra': 'romp', 'f': '', 'x': {'es': 1, 'r': 1.5}},
    {'id': 'eur-rsi-15m', 'nome': 'Agente Euro', 'sym': 'frxEURUSD', 'g': 900, 'regra': 'rsi', 'f': '', 'x': {'a1': 1.5, 'a2': 3}},
]
K_CFG, K_TOK, K_OPS, K_LOCK, K_LOG = 'mesa:cfg', 'mesa:tok', 'mesa:ops', 'mesa:lock', 'mesa:log'
# MESA-AGENTES-V2: proteções. stop_dia = perda máxima da mesa no dia (Brasília); stop_ag_dia = por agente;
# apos_n / apos_pf = com apos_n+ operações reais e fator de lucro abaixo de apos_pf o agente se aposenta sozinho.
PROT_PADRAO = {'stop_dia': 400.0, 'stop_ag_dia': 160.0, 'apos_n': 30, 'apos_pf': 0.85,
               'veto_noticia': 1.0, 'veto_corr': 1.0,   # VETOS-V1: 1 = ligado, 0 = desligado
               # MESA-AGENTES-V4 diretor: sombra com prom_n+ ops e fator >= prom_pf vira DEMO (até max_demo agentes na demo)
               'prom_n': 20, 'prom_pf': 1.2, 'max_demo': 10,
               # MESA-TRAVA-V1: trava de lucro. Quando o lucro chega a trava_ini x entrada, garante trava_keep do maior lucro.
               # trava_on=1 fecha de verdade as posições da DEMO; na SOMBRA só mede (plt = como teria sido com a trava).
               'trava_on': 1.0, 'trava_ini': 0.30, 'trava_keep': 0.50}


def auditor(L, bt):
    """parecer do auditor sobre as operações reais (L) comparadas com o teste da Fábrica (bt)"""
    n = len(L)
    if n < 10:
        return {'nivel': 'cedo', 'txt': '%d operação(ões): cedo para qualquer conclusão (o auditor começa a julgar com 10 e decide com 30).' % n}
    pl = [o['pl'] for o in L]
    md = sum(pl) / n
    sd = math.sqrt(sum((x - md) ** 2 for x in pl) / (n - 1)) if n > 1 else 0
    tt = md / (sd / math.sqrt(n)) if sd > 0 else 0
    sorte = 0.5 * math.erfc(tt / math.sqrt(2)) * 100      # chance de um resultado assim (ou melhor) sem vantagem nenhuma
    pf = fator(L)
    bpf = float((bt or {}).get('pf') or 0) or None
    t = '%d ops · fator %.2f · média %+.2f por operação · chance de ser sorte %.0f%%' % (n, pf, md, sorte)
    if bpf:
        t += ' · no teste o fator era %.2f' % bpf
    if pf < 0.9 and n >= 20:
        return {'nivel': 'ruim', 'txt': t + '. Não está repetindo o teste.', 'sorte': round(sorte, 1)}
    if pf >= 1.2 and sorte <= 10 and n >= 30:
        return {'nivel': 'forte', 'txt': t + '. Resultado consistente: candidato a entrada maior.', 'sorte': round(sorte, 1)}
    if bpf and pf < bpf - 0.4:
        return {'nivel': 'atencao', 'txt': t + '. Bem abaixo do teste: observar.', 'sorte': round(sorte, 1)}
    return {'nivel': 'ok', 'txt': t + '.', 'sorte': round(sorte, 1)}
BRT = timezone(__import__('datetime').timedelta(hours=-3))


def dia_brt(t):
    return datetime.fromtimestamp(t, tz=BRT).strftime('%Y-%m-%d')


def fator(L):
    g = sum(o['pl'] for o in L if o['pl'] > 0)
    p = -sum(o['pl'] for o in L if o['pl'] <= 0)
    return g / p if p > 0 else (99.0 if g > 0 else 0.0)


def _limpa_ag(a, velho=None):
    a = dict(velho or {}, **(a or {}))
    sym = str(a.get('sym') or '')
    g = int(a.get('g') or 3600)
    regra = str(a.get('regra') or '')
    if not sym or g not in HOLD or regra not in REGRA_N:
        raise ValueError('agente precisa de sym, g (3600/900/300) e regra (%s)' % '/'.join(REGRA_N))
    x = {k: float(v) for k, v in (a.get('x') or {}).items() if k in ('es', 'r', 'a1', 'a2', 'sl', 'tp') and v not in (None, '')}
    if not (x.get('es') or x.get('a1') or (x.get('sl') and x.get('tp'))):
        raise ValueError('saída inválida')
    aid = str(a.get('id') or '%s-%s-%s%s' % (sym[-6:].lower(), regra, TF_N[g], '-s' if a.get('f') else ''))[:40]
    return {'id': aid, 'nome': str(a.get('nome') or ('Agente ' + NOME.get(sym, sym)))[:40], 'sym': sym, 'g': g, 'regra': regra,
            'f': 's' if a.get('f') else '', 'x': x, 'stk': max(1.0, min(2000.0, float(a.get('stk') or 80))), 'mq': int(a.get('mq') or 100),
            'an': [k for k in (a.get('an') or []) if k in AN_N][:3], 'modo': 'sombra' if a.get('modo') == 'sombra' else 'demo',
            'ativo': a.get('ativo', True) is not False, 'bt': a.get('bt') if isinstance(a.get('bt'), dict) else {}, 'criado': a.get('criado') or time.time()}


class Mesa(object):
    def __init__(self):
        self.kv = KV()
        self.dono = uuid.uuid4().hex[:10]
        self.d = None
        self.st = {}          # estado por agente (em memória, espelhado no Redis)
        self.erro = ''
        self.hb = 0
        self.lider = False
        self.cache_cm = {}    # (sym, stk, mq) -> (mult, comm, t)
        self.ult_ping = 0
        self.supa = 'ainda não usado'
        self.cache_v = {}     # (sym, g, barra) -> velas (vários agentes no mesmo mercado e tempo baixam 1 vez)
        self.ult_rel = ''
        threading.Thread(target=self.restaura, daemon=True).start()
        cfg = self.kv.jget(K_CFG)
        if not cfg:
            cfg = {'ligada': False, 'conta': '', 'agentes': [_limpa_ag(a) for a in PADRAO]}
            self.kv.jset(K_CFG, cfg)

    # ---------- config ----------
    def cfg(self):
        return self.kv.jget(K_CFG) or {'ligada': False, 'conta': '', 'agentes': []}

    def salva(self, c):
        self.kv.jset(K_CFG, c)

    def nota(self, txt):
        linha = {'t': int(time.time()), 'm': str(txt)[:300]}
        self.kv.push(K_LOG, linha, cap=300)
        log(txt)

    def st_ag(self, aid):
        s = self.st.get(aid)
        if s is None:
            s = self.kv.jget('mesa:st:' + aid) or {}
            self.st[aid] = s
        return s

    def grava_st(self, aid):
        self.kv.jset('mesa:st:' + aid, self.st.get(aid) or {})

    def copia(self, op):
        def _vai():
            try:
                _supa('mesa_ops?on_conflict=id', 'POST', {'id': op['id'], 'ag': op['ag'], 't1': op['t1'], 'reg': op},
                      {'Prefer': 'resolution=merge-duplicates,return=minimal'})
                self.supa = 'ok'
            except Exception as e:
                self.supa = 'falhou: %s' % str(e)[:120]
                log('Supabase mesa_ops:', e)
        threading.Thread(target=_vai, daemon=True).start()

    def restaura(self):
        """se o Redis perdeu o placar (reinício), traz de volta do Supabase"""
        try:
            time.sleep(5)
            if self.kv.lista(K_OPS, 1):
                return
            if not self.kv.trava('mesa:restaura', self.dono, 300):
                return
            L, ini = [], 0
            while ini < 50000:
                lote = _supa('mesa_ops?select=reg&order=t1.asc&offset=%d&limit=1000' % ini) or []
                L += [x.get('reg') for x in lote if x.get('reg')]
                if len(lote) < 1000:
                    break
                ini += 1000
            for op in L:
                self.kv.push(K_OPS, op)
            self.supa = 'ok (restaurou %d operações)' % len(L)
            if L:
                log('placar restaurado do Supabase: %d operações' % len(L))
        except Exception as e:
            self.supa = 'falhou: %s' % str(e)[:120]

    def prot(self):
        p = dict(PROT_PADRAO)
        p.update({k: v for k, v in (self.cfg().get('prot') or {}).items() if k in PROT_PADRAO})
        return p

    def hoje(self, aid=None, ops=None):
        """resultado de hoje (Brasília): fechadas + o que está aberto agora"""
        d = dia_brt(time.time())
        ops = ops if ops is not None else self.kv.lista(K_OPS, 3000)
        v = sum(o['pl'] for o in ops if not o.get('sombra') and dia_brt(o.get('t1') or 0) == d and (aid is None or o.get('ag') == aid))
        for a in self.cfg().get('agentes') or []:
            if aid is None or a['id'] == aid:
                po = (self.st.get(a['id']) or {}).get('pos') or {}
                if not po.get('sombra'):
                    v += min(0.0, float(po.get('pl') or 0))
        return round(v, 2)

    # ---------- laço ----------
    def supervisor(self):
        time.sleep(20)
        while True:
            try:
                self.passo()
            except Exception as e:
                self.erro = str(e)[:300]
                log('erro no passo:', e)
                traceback.print_exc()
                time.sleep(10)
            time.sleep(8)

    def passo(self):
        c = self.cfg()
        tok = self.kv.get(K_TOK) or ''
        self.auto_ping()
        if not c.get('ligada') or not tok or not c.get('conta'):
            self.lider = False
            if self.d:
                self.d.fecha()
                self.d = None
            return
        if not self.kv.trava(K_LOCK, self.dono, 120):
            self.lider = False
            return
        if not self.lider:
            self.st = {}          # acabou de virar o servidor da mesa: relê o estado do Redis
        self.lider = True
        self.hb = time.time()
        self.kv.set('mesa:hb', str(int(self.hb)), ex=120)
        if self.d is None or self.d.tok != tok or self.d.conta != c['conta']:
            if self.d:
                self.d.fecha()
            self.d = Deriv(tok, c['conta'])
        try:
            self.acompanha(c)
            for a in c.get('agentes') or []:
                if a.get('ativo'):
                    if not self.kv.trava(K_LOCK, self.dono, 120):
                        self.lider = False
                        return
                    self.analisa(a)
            if time.time() - self.d.ult > 25:
                self.d.req({'ping': 1}, 10)
            self.relatorio()
            self.erro = ''
        except DerivErro as e:
            if str(e) == 'TOKEN':
                self.erro = 'O token da demo expirou. Abra o Escritório e toque em "Conectar minha demo" de novo.'
                c['ligada'] = False
                self.salva(c)
                self.nota('Mesa desligada: token da Deriv expirou')
            else:
                self.erro = str(e)[:200]
            self.d.fecha()

    def auto_ping(self):
        """o Render gratuito dorme sem visitas; enquanto a mesa estiver ligada, o servidor se visita a cada 9 min"""
        if time.time() - self.ult_ping < 540:
            return
        self.ult_ping = time.time()
        base = os.environ.get('RENDER_EXTERNAL_URL', '').rstrip('/')
        if base and (self.cfg().get('ligada')):
            try:
                _baixa(base + '/api/health', 15)
            except Exception:
                pass

    # ---------- uma vela fechada -> analisa e, se tiver sinal, entra ----------
    def analisa(self, a):
        g, aid = a['g'], a['id']
        s = self.st_ag(aid)
        agora = time.time()
        barra = int(agora // g) - 1           # a vela que acabou de fechar
        if s.get('barra') == barra or agora - (barra + 1) * g < 4:
            return
        try:
            kc = (a['sym'], g, barra)
            B = self.cache_v.get(kc)
            if B is None:
                B = self.d.velas(a['sym'], g, 1000)
                if len(self.cache_v) > 120:
                    self.cache_v = {}
                self.cache_v[kc] = B
            B = list(B)
        except DerivErro as e:
            s.update({'estado': 'erro', 'txt': 'Deriv recusou as velas: %s' % e, 'barra': barra, 'ta': int(agora)})
            self.grava_st(aid)
            return
        B = [b for b in B if b['t'] <= barra * g]
        s['barra'] = barra
        s['ta'] = int(agora)
        s['prox'] = (barra + 2) * g + 4
        if len(B) < 120:
            s.update({'estado': 'erro', 'txt': 'a Deriv entregou só %d velas' % len(B)})
            self.grava_st(aid)
            return
        if B[-1]['t'] < barra * g - 2 * g:
            s.update({'estado': 'fechado', 'txt': 'Mercado fechado agora (última vela %s UTC). Volta a analisar quando abrir.' % datetime.fromtimestamp(B[-1]['t'], tz=timezone.utc).strftime('%d/%m %H:%M')})
            self.grava_st(aid)
            return
        fechou_agora = False
        if s.get('pos') and s['pos'].get('sombra'):
            fechou_agora = self.anda_sombra(a, s, B) == B[-1]['t']
        ks = (a['sym'], g, barra, 'S')
        S = self.cache_v.get(ks)
        if S is None or len(S['ses']) != len(B):
            S = sinais(B)          # todos os agentes do mesmo mercado e tempo usam o mesmo cálculo
            self.cache_v[ks] = S
        i = len(B) - 1
        lado = S[a['regra']][i] if a['regra'] in S else 0
        if a['regra'] == 'cons':   # CONSENSO-V1
            lado = self.consenso(a, B, S, i)
        px = B[i]['c']
        s['px'] = px
        s['txt'] = self.leitura(a, S, B, i, lado)
        if s.get('pos'):
            s['estado'] = 'posicionado'
            self.grava_st(aid)
            return
        s['estado'] = 'analisando'
        if lado and a.get('f') == 's' and not S['ses'][i]:
            s['txt'] += ' · sinal fora do horário 07–17h UTC, não entra'
            lado = 0
        if lado and a.get('an'):
            A = analistas(B)
            j = len(B) - 1
            contra = [AN_N[k] for k in a['an'] if not passa(A, k, j, lado)]
            if contra:
                s['txt'] += ' · analista discordou (%s), não entra' % ', '.join(contra)
                lado = 0
            else:
                s['txt'] += ' · analistas de acordo: ' + ', '.join(AN_N[k] for k in a['an'])
        if lado and a.get('modo') == 'sombra' and fechou_agora:
            lado = 0          # igual à Fábrica: não entra na mesma vela em que saiu
        if lado:   # VETOS-V1: Agente Notícias e Agente Correlação (só bloqueiam; o barrado vira sombra marcada, para medir)
            vt = self.vetos(a, lado)
            if vt:
                if a.get('modo') != 'sombra':
                    s['txt'] += ' · 🚫 vetado: %s (vai para a sombra para medir)' % vt
                    self.nota('%s: 🚫 VETADO (%s) · a entrada vai para a sombra' % (a['nome'], vt))
                else:
                    s['txt'] += ' · 🚫 seria vetado: %s' % vt
                if not fechou_agora:
                    self.entra_sombra(a, s, lado, B[i], S['atr'][i], S['slL'][i] if lado > 0 else S['slS'][i])
                    if s.get('pos') and s['pos'].get('sombra'):
                        s['pos']['veto'] = vt
                        if a.get('modo') != 'sombra':
                            s['pos']['vet'] = 1
                lado = 0
        if lado and a.get('modo') == 'sombra':
            self.entra_sombra(a, s, lado, B[i], S['atr'][i], S['slL'][i] if lado > 0 else S['slS'][i])
            lado = 0
        if lado:
            pr = self.prot()
            ops = [o for o in self.kv.lista(K_OPS, 3000) if not o.get('sombra')]
            hm_, ha_ = self.hoje(None, ops), self.hoje(aid, ops)
            if pr['stop_dia'] and hm_ <= -pr['stop_dia']:
                s['txt'] += ' · STOP DO DIA DA MESA (%.2f): não entra até amanhã' % hm_
                lado = 0
            elif pr['stop_ag_dia'] and ha_ <= -pr['stop_ag_dia']:
                s['txt'] += ' · stop do dia deste agente (%.2f): descansa até amanhã' % ha_
                lado = 0
        if lado:
            self.entra(a, s, lado, px, S['atr'][i], S['slL'][i] if lado > 0 else S['slS'][i])
        self.grava_st(aid)

    def vetos(self, a, lado):
        """VETOS-V1: '' = pode entrar; senão o motivo"""
        try:
            import vetos_global as V
        except Exception:
            return ''
        pr = self.prot()
        if float(pr.get('veto_noticia', 1)) > 0:
            m = V.veto_noticia(a['sym'])
            if m:
                return m
        if float(pr.get('veto_corr', 1)) > 0 and a.get('modo') != 'sombra':
            ab = []
            for b in self.cfg().get('agentes') or []:
                if b.get('id') == a.get('id'):
                    continue
                p = (self.st_ag(b['id']) or {}).get('pos') or {}
                if p and not p.get('sombra'):
                    ab.append((b.get('sym'), p.get('lado') or 0))
            m = V.veto_corr(a['sym'], lado, ab)
            if m:
                return m
        return ''

    def consenso(self, a, B, S, i):
        """CONSENSO-V1 — o sinal da IA embaixo do gráfico do Alpha Global, reconstruído no servidor:
        em cada tempo gráfico (5m, 15m, 1h, 4h) a direção é de alta se o preço está acima do SuperTrend (10, 3) e a EMA 9 acima da EMA 21
        (baixa ao contrário). Entra quando os 4 concordam, o RSI 14 não está esgotado (entre 25 e 75) e a vela do tempo do agente
        fez um repique até a EMA 9 e fechou de volta a favor. Stop e alvo vêm da saída do agente (estrutural)."""
        if not hasattr(self, 'cons_txt'):
            self.cons_txt = {}
        dirs, nomes = [], {300: '5m', 900: '15m', 3600: '1h', 14400: '4h'}
        agora = time.time()
        for tf in (300, 900, 3600, 14400):
            try:
                if tf == a['g']:
                    C = B
                else:
                    kc = (a['sym'], tf, int(agora // tf))
                    C = self.cache_v.get(kc)
                    if C is None:
                        C = [c for c in self.d.velas(a['sym'], tf, 300) if c['t'] + tf <= agora + 2]
                        self.cache_v[kc] = C
                if len(C) < 60:
                    dirs.append(0)
                    continue
                cl = [c['c'] for c in C]
                e9, e21, at = ema(cl, 9), ema(cl, 21), atr_s(C, 10)
                st, up = supertrend(C, at)
                d = 1 if (up and e9[-1] > e21[-1]) else -1 if ((not up) and e9[-1] < e21[-1]) else 0
                dirs.append(d)
            except Exception:
                dirs.append(0)
        rs = rsi_s([c['c'] for c in B], 14)[i]
        e9b = ema([c['c'] for c in B], 9)[i]
        b = B[i]
        txt = ' '.join('%s%s' % (nomes[tf], {1: '▲', -1: '▼', 0: '–'}[d]) for tf, d in zip((300, 900, 3600, 14400), dirs))
        lado = 0
        if all(d == 1 for d in dirs):
            lado = 1 if (25 < rs < 75 and b['l'] <= e9b and b['c'] > e9b and b['c'] > b['o']) else 0
            txt = 'ALTA nos 4 tempos (%s) · RSI %.0f · espera repique até a EMA 9 (%.5g) e fechar de volta' % (txt, rs, e9b)
        elif all(d == -1 for d in dirs):
            lado = -1 if (25 < rs < 75 and b['h'] >= e9b and b['c'] < e9b and b['c'] < b['o']) else 0
            txt = 'BAIXA nos 4 tempos (%s) · RSI %.0f · espera repique até a EMA 9 (%.5g) e fechar de volta' % (txt, rs, e9b)
        else:
            txt = 'sem consenso (%s) · só entra quando os 4 tempos concordam' % txt
        if lado:   # stop estrutural: se o SMC não achou topo/fundo, usa a máxima/mínima das últimas 12 velas + margem
            atv = S['atr'][i] or 0
            if lado < 0 and not S['slS'][i]:
                S['slS'][i] = max(c['h'] for c in B[max(0, i - 11):i + 1]) + 0.2 * atv
            if lado > 0 and not S['slL'][i]:
                S['slL'][i] = min(c['l'] for c in B[max(0, i - 11):i + 1]) - 0.2 * atv
        self.cons_txt[a['id']] = txt
        return lado

    def leitura(self, a, S, B, i, lado):
        r, px = a['regra'], B[i]['c']
        if r == 'rsi':
            t = 'RSI %.1f · compra quando cruza abaixo de 25, vende quando cruza acima de 75' % S['rs'][i]
        elif r == 'tend':
            up = S['e20'][i] > S['e50'][i]
            t = 'EMA 20 %s da EMA 50 · espera o preço recuar até a EMA 20 (%.5g) e voltar' % ('acima' if up else 'abaixo', S['e20'][i])
        elif r == 'smc':
            t = 'estrutura %s · %d order block(s) vivo(s) · espera o reteste a favor' % ({1: 'de alta', -1: 'de baixa'}.get(S['tr'], 'indefinida'), S['obs'])
        elif r == 'lon':
            t = ('faixa da Ásia hoje %.5g a %.5g · entra se fechar fora entre 07h e 11h UTC' % (S['aH'], S['aL'])) if S.get('aH') is not None else 'esperando a faixa da Ásia (00h–07h UTC) de hoje'
        elif r == 'ny':
            t = ('1ª hora de Nova York %.5g a %.5g · entra se fechar fora entre 14h e 18h UTC' % (S['nH'], S['nL'])) if S.get('nH') is not None else 'esperando a 1ª hora de Nova York (13h UTC) de hoje'
        elif r == 'don':
            t = 'canal de 55 velas %.5g a %.5g · entra quando fechar fora · preço %.5g' % (S.get('dmx', 0), S.get('dmn', 0), px)
        elif r == 'bb':
            t = 'Bollinger %.5g a %.5g · entra quando o preço sai e volta para dentro · preço %.5g' % (S['bbU'][i], S['bbL'][i], px)
        elif r == 'cons':
            t = getattr(self, 'cons_txt', {}).get(a['id'], 'lendo os 4 tempos gráficos')
        else:
            t = 'máxima de ontem %.5g · mínima de ontem %.5g · preço %.5g' % (S['pH'], S['pL'], px)
        if lado:
            t = ('SINAL DE COMPRA · ' if lado > 0 else 'SINAL DE VENDA · ') + t
        return t

    # ---------- agentes SOMBRA: entram no papel com o preço real da Deriv (sem ordem), mesma conta da Fábrica ----------
    def entra_sombra(self, a, s, lado, b, atr, slpx):
        try:
            mult, comm = self.mult_comm(a)
        except DerivErro as e:
            s['txt'] += ' · sem proposta da Deriv (%s)' % e
            return
        K = a['stk'] * mult
        nv = niveis(a['x'], K, a['stk'], comm, b['c'], atr, slpx)
        if not nv:
            s['txt'] += ' · stop/alvo não cabem nesta entrada, pulou'
            return
        s['pos'] = {'sombra': 1, 'cid': None, 'lado': lado, 'ent': b['c'], 'bi': b['t'], 't': int(time.time()), 'stk': a['stk'], 'mult': mult, 'comm': comm,
                    'K': K, 'slD': nv['slD'], 'tpD': nv['tpD'], 'sl': nv['sl'], 'tp': nv['tp'], 'velas': 0, 'venc': int(time.time()) + HOLD[a['g']] * a['g'], 'pl': 0.0}
        s['estado'] = 'posicionado'
        self.nota('%s (sombra) entrou %s em %s · stop $%.2f · alvo $%.2f' % (a['nome'], 'COMPRA' if lado > 0 else 'VENDA', NOME.get(a['sym'], a['sym']), nv['sl'], nv['tp']))

    def anda_sombra(self, a, s, B):
        p = s['pos']
        ent, lado, hold = p['ent'], p['lado'], HOLD[a['g']]
        novas = [b for b in B if b['t'] > p['bi'] and b['t'] > p.get('vista', 0)]
        for b in novas:
            p['vista'] = b['t']
            p['velas'] = p.get('velas', 0) + 1
            adv = (ent - b['l']) / ent if lado > 0 else (b['h'] - ent) / ent
            fav = (b['h'] - ent) / ent if lado > 0 else (ent - b['l']) / ent
            pl, mot = None, ''
            pr0 = getattr(self, '_prot_cache', None) or self.prot()
            mx0 = float(p.get('mx') or 0)
            if p.get('plt') is None and mx0 >= float(pr0['trava_ini']) * float(p['stk']) and p['K'] * (-adv) - p['comm'] <= float(pr0['trava_keep']) * mx0:
                p['plt'] = round(float(pr0['trava_keep']) * mx0, 2)   # MESA-TRAVA-V1: aqui a trava teria fechado
            p['mx'] = max(mx0, p['K'] * fav - p['comm'])
            if adv >= p['slD']:
                pl, mot = -p['sl'], 'stop'
            elif fav >= p['tpD']:
                pl, mot = p['tp'], 'alvo'
            elif p['velas'] >= hold:
                pl, mot = p['K'] * lado * (b['c'] / ent - 1) - p['comm'], 'tempo'
            if pl is not None:
                op = {'id': 'S%s-%d' % (a['id'], p['bi']), 'ag': a['id'], 'nome': a['nome'], 'sym': a['sym'], 'g': a['g'], 'regra': a['regra'], 'lado': lado,
                      'stk': p['stk'], 'mult': p['mult'], 'ent': ent, 'sai': b['c'], 't0': p['t'], 't1': int(b['t'] + a['g']), 'pl': round(pl, 2), 'motivo': mot, 'sombra': 1,
                      'mx': round(float(p.get('mx') or 0), 2), 'plt': p['plt'] if p.get('plt') is not None else round(pl, 2), 'veto': p.get('veto') or '', 'vet': p.get('vet') or 0}
                self.kv.push(K_OPS, op)
                self.copia(op)
                s.pop('pos', None)
                s['estado'] = 'analisando'
                self.nota('%s (sombra) fechou %s em %s: %s%.2f (%s)' % (a['nome'], 'compra' if lado > 0 else 'venda', NOME.get(a['sym'], a['sym']), '+' if pl >= 0 else '−', abs(pl), mot))
                if not p.get('vet'):
                    self.diretor(a)
                return b['t']
        p['pl'] = round(p['K'] * lado * (B[-1]['c'] / ent - 1) - p['comm'], 2)

    # ---------- DIRETOR: promove sombra boa para a demo, aposenta quem não repete o teste ----------
    def diretor(self, a):
        try:
            pr = self.prot()
            c = self.cfg()
            x = [y for y in c.get('agentes') or [] if y['id'] == a['id']]
            if not x:
                return
            x = x[0]
            todas = self.kv.lista(K_OPS, 8000)
            Ls = [o for o in todas if o.get('ag') == a['id'] and o.get('sombra')]
            Ld = [o for o in todas if o.get('ag') == a['id'] and not o.get('sombra')]
            ndemo = len([y for y in c['agentes'] if y.get('ativo') and y.get('modo', 'demo') == 'demo'])
            if x.get('modo') == 'sombra':
                if len(Ls) >= int(pr['prom_n']) and fator(Ls) >= float(pr['prom_pf']) and sum(o['pl'] for o in Ls) > 0:
                    if ndemo < int(pr['max_demo']):
                        x['modo'] = 'demo'
                        x['promovido'] = {'t': int(time.time()), 'n': len(Ls), 'pf': round(fator(Ls), 2)}
                        self.salva(c)
                        self.nota('DIRETOR: %s PROMOVIDO para a demo (%d operações na sombra, fator %.2f)' % (x['nome'], len(Ls), fator(Ls)))
                    return
                if len(Ls) >= int(pr['apos_n']) and fator(Ls) < float(pr['apos_pf']):
                    x['ativo'] = False
                    x['aposentado'] = {'t': int(time.time()), 'n': len(Ls), 'pf': round(fator(Ls), 2), 'sum': round(sum(o['pl'] for o in Ls), 2), 'sombra': 1}
                    self.salva(c)
                    self.nota('DIRETOR: %s aposentado na sombra (%d operações, fator %.2f)' % (x['nome'], len(Ls), fator(Ls)))
            else:
                if pr['apos_n'] and len(Ld) >= int(pr['apos_n']) and fator(Ld) < float(pr['apos_pf']):
                    x['ativo'] = False
                    x['aposentado'] = {'t': int(time.time()), 'n': len(Ld), 'pf': round(fator(Ld), 2), 'sum': round(sum(o['pl'] for o in Ld), 2)}
                    self.salva(c)
                    s = self.st_ag(a['id'])
                    s['estado'] = 'aposentado'
                    s['txt'] = 'Aposentado pelo diretor: %d operações reais com fator %.2f (abaixo de %.2f).' % (len(Ld), fator(Ld), pr['apos_pf'])
                    self.grava_st(a['id'])
                    self.nota('DIRETOR: %s APOSENTADO: %d operações, fator %.2f, %s%.2f' % (x['nome'], len(Ld), fator(Ld), '+' if sum(o['pl'] for o in Ld) >= 0 else '−', abs(sum(o['pl'] for o in Ld))))
        except Exception as e:
            log('diretor:', e)

    def relatorio(self):
        """AUDITOR: relatório do dia às 21h de Brasília, no feed"""
        agora = datetime.now(BRT)
        chave = agora.strftime('%Y-%m-%d')
        if agora.hour < 21 or self.ult_rel == chave or self.kv.get('mesa:rel') == chave:
            return
        self.ult_rel = chave
        self.kv.set('mesa:rel', chave, ex=2 * 86400)
        ops = [o for o in self.kv.lista(K_OPS, 3000) if dia_brt(o.get('t1') or 0) == chave]
        d = [o for o in ops if not o.get('sombra')]
        sb = [o for o in ops if o.get('sombra')]
        self.nota('AUDITOR · relatório de hoje: demo %d operações %+.2f (acerto %s) · sombra %d operações %+.2f' % (
            len(d), sum(o['pl'] for o in d), ('%d%%' % round(100 * len([o for o in d if o['pl'] > 0]) / len(d))) if d else '—', len(sb), sum(o['pl'] for o in sb)))

    def mult_comm(self, a):
        k = (a['sym'], a['stk'], a['mq'])
        v = self.cache_cm.get(k)
        if v and time.time() - v[2] < 6 * 3600:
            return v[0], v[1]
        mult = a['mq']
        try:
            r = self.d.req({'contracts_for': a['sym']}, 15)
            mults = sorted({int(m) for x in ((r.get('contracts_for') or {}).get('available') or []) if str(x.get('contract_type', '')).startswith('MULT') for m in (x.get('multiplier_range') or [])})
            if mults:
                mult = min(mults, key=lambda m: abs(m - a['mq']))
        except Exception:
            pass
        comm = 0.0
        r = self.d.req_sym({'proposal': 1, 'contract_type': 'MULTUP', 'amount': a['stk'], 'basis': 'stake', 'currency': 'USD', 'multiplier': mult}, a['sym'], 15)
        if r.get('proposal'):
            comm = float(r['proposal'].get('commission') or 0)
        elif r.get('error'):
            raise DerivErro(r['error'].get('message', 'proposta recusada'))
        self.cache_cm[k] = (mult, comm, time.time())
        return mult, comm

    def entra(self, a, s, lado, px, atr, slpx):
        try:
            mult, comm = self.mult_comm(a)
        except DerivErro as e:
            s['txt'] += ' · não deu para entrar: %s' % e
            self.nota('%s: sem proposta (%s)' % (a['nome'], e))
            return
        K = a['stk'] * mult
        nv = niveis(a['x'], K, a['stk'], comm, px, atr, slpx)
        if not nv:
            s['txt'] += ' · stop/alvo não cabem nesta entrada, pulou'
            return
        par = {'contract_type': 'MULTUP' if lado > 0 else 'MULTDOWN', 'amount': round(a['stk'], 2), 'basis': 'stake', 'currency': 'USD',
               'multiplier': mult, 'limit_order': {'stop_loss': nv['sl'], 'take_profit': nv['tp']}}
        par[self.d.symkey] = a['sym']
        r = self.d.req({'buy': 1, 'price': round(a['stk'], 2), 'parameters': par}, 20)
        msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error') and ('symbol' in msg.lower() or 'Properties not allowed' in msg):
            par.pop(self.d.symkey, None)
            self.d.symkey = 'symbol' if self.d.symkey == 'underlying_symbol' else 'underlying_symbol'
            par[self.d.symkey] = a['sym']
            r = self.d.req({'buy': 1, 'price': round(a['stk'], 2), 'parameters': par}, 20)
        if r.get('error'):
            s['txt'] += ' · Deriv recusou: %s' % r['error'].get('message', '')
            self.nota('%s: compra recusada (%s)' % (a['nome'], r['error'].get('message', '')))
            return
        b = r.get('buy') or {}
        s['pos'] = {'cid': b.get('contract_id'), 'lado': lado, 'ent': px, 't': int(time.time()), 'stk': a['stk'], 'mult': mult, 'comm': comm,
                    'sl': nv['sl'], 'tp': nv['tp'], 'venc': int(time.time()) + HOLD[a['g']] * a['g'], 'pl': 0.0}
        s['estado'] = 'posicionado'
        self.nota('%s abriu %s em %s · entrada $%.2f x%d · stop $%.2f · alvo $%.2f' % (a['nome'], 'COMPRA' if lado > 0 else 'VENDA', NOME.get(a['sym'], a['sym']), a['stk'], mult, nv['sl'], nv['tp']))

    # ---------- acompanha as posições abertas ----------
    def acompanha(self, c):
        agora = time.time()
        for a in c.get('agentes') or []:
            s = self.st_ag(a['id'])
            p = s.get('pos')
            if not p or not p.get('cid'):
                continue
            if agora - p.get('chk', 0) < 20:
                continue
            p['chk'] = agora
            r = self.d.req({'proposal_open_contract': 1, 'contract_id': p['cid']}, 20)
            q = r.get('proposal_open_contract') or {}
            if r.get('error'):
                p['err'] = r['error'].get('message', '')
                continue
            p['pl'] = float(q.get('profit') or 0)
            p['mx'] = max(float(p.get('mx') or 0), p['pl'])   # MESA-TRAVA-V1
            pr = self.prot()
            if pr.get('trava_on') and not (q.get('is_sold') or q.get('status') in ('won', 'lost', 'sold')) and p['mx'] >= float(pr['trava_ini']) * float(p['stk']) \
                    and p['pl'] <= float(pr['trava_keep']) * p['mx'] and not p.get('motivo'):
                rs = self.d.req({'sell': p['cid'], 'price': 0}, 20)
                if not rs.get('error'):
                    p['motivo'] = 'trava'
                    p['chk'] = 0
                    self.nota('%s: TRAVA DE LUCRO fechou (maior lucro +%.2f, piso +%.2f)' % (a['nome'], p['mx'], float(pr['trava_keep']) * p['mx']))
            if q.get('current_spot'):
                s['px'] = float(q['current_spot'])
            if q.get('is_sold') or q.get('status') in ('won', 'lost', 'sold'):
                self.fecha_op(a, s, p, q)
            elif agora >= p.get('venc', 1e18):
                rs = self.d.req({'sell': p['cid'], 'price': 0}, 20)
                if rs.get('error'):
                    p['err'] = 'não vendeu no tempo máximo: ' + rs['error'].get('message', '')
                else:
                    p['motivo'] = 'tempo'
                    p['chk'] = 0
            self.grava_st(a['id'])

    def fecha_op(self, a, s, p, q):
        pl = round(float(q.get('profit') or 0), 2)
        mot = p.get('motivo') or ''
        if not mot:
            sl, tp = float(p.get('sl') or 0), float(p.get('tp') or 0)
            mot = 'alvo' if (tp and pl >= tp - 0.6) else 'stop' if (sl and pl <= -sl + 0.6) else 'fechou'
        op = {'id': str(p['cid']), 'ag': a['id'], 'nome': a['nome'], 'sym': a['sym'], 'g': a['g'], 'regra': a['regra'], 'lado': p['lado'],
              'stk': p['stk'], 'mult': p['mult'], 'ent': p['ent'], 'sai': float(q.get('exit_tick') or q.get('current_spot') or 0),
              't0': p['t'], 't1': int(q.get('sell_time') or time.time()), 'pl': pl, 'motivo': mot}
        self.kv.push(K_OPS, op)
        self.copia(op)
        s.pop('pos', None)
        s['estado'] = 'analisando'
        s['ultop'] = op
        self.nota('%s fechou %s em %s: %s%.2f (%s)' % (a['nome'], 'compra' if p['lado'] > 0 else 'venda', NOME.get(a['sym'], a['sym']), '+' if pl >= 0 else '−', abs(pl), mot))
        self.diretor(a)   # MESA-AGENTES-V4: aposentadoria pelo diretor

    # ---------- para o Escritório ----------
    def estado(self):
        c = self.cfg()
        ops = self.kv.lista(K_OPS, 5000)
        hb = float(self.kv.get('mesa:hb') or 0)
        ags = []
        tot = {'n': 0, 'w': 0, 'sum': 0.0}
        tsb = {'n': 0, 'sum': 0.0}
        for a in c.get('agentes') or []:
            s = self.st.get(a['id']) if self.lider else None
            if s is None:
                s = self.kv.jget('mesa:st:' + a['id']) or {}
            LS = [o for o in ops if o.get('ag') == a['id'] and o.get('sombra')]
            LS.reverse()
            L = [o for o in ops if o.get('ag') == a['id'] and not o.get('sombra')]
            L.reverse()
            if a.get('modo') == 'sombra':
                L, LS = LS, L          # na sombra o placar principal é o virtual
            eq = pico = dd = 0.0
            w = 0
            curva = [0]
            for o in L:
                eq += o['pl']
                w += 1 if o['pl'] > 0 else 0
                pico = max(pico, eq)
                dd = max(dd, pico - eq)
                curva.append(round(eq, 2))
            pl = {'n': len(L), 'w': w, 'sum': round(eq, 2), 'dd': round(dd, 2), 'curva': curva[-200:], 'pf': round(fator(L), 2) if L else None,
                  'hoje': round(sum(o['pl'] for o in L if dia_brt(o.get('t1') or 0) == dia_brt(time.time())), 2)}
            pr = self.prot()
            etapa = 'aposentado' if not a.get('ativo') else 'sombra' if a.get('modo') == 'sombra' else ('em teste' if len(L) < int(pr['apos_n']) else 'aprovado' if fator(L) >= 1.1 else 'em observação')
            if a.get('modo') != 'sombra':
                tot['n'] += len(L)
                tot['w'] += w
                tot['sum'] += eq
            else:
                tsb['n'] += len(L)
                tsb['sum'] += eq
            x = dict(a)
            x.update({'mercado': NOME.get(a['sym'], a['sym']), 'tf': TF_N.get(a['g'], ''), 'regra_n': REGRA_N.get(a['regra'], a['regra']),
                      'saida': saida_nome(a['x']), 'analistas': [AN_N[k] for k in (a.get('an') or []) if k in AN_N], 'st': {k: v for k, v in s.items() if k != 'ultop'}, 'placar': pl,
                      'ult': [o for o in L[-12:]][::-1], 'etapa': etapa, 'auditor': auditor(L, a.get('bt')),
                      'outro': {'n': len(LS), 'sum': round(sum(o['pl'] for o in LS), 2)}})
            ags.append(x)
        tot['sum'] = round(tot['sum'], 2)
        tsb['sum'] = round(tsb['sum'], 2)
        try:   # MESA-TRAVA-V1: sombra com e sem a trava
            idsb = {x['id'] for x in (c.get('agentes') or []) if x.get('modo') == 'sombra'}
            LT = [o for o in ops if o.get('sombra') and o.get('ag') in idsb and o.get('plt') is not None]
            tsb['trava'] = {'n': len(LT), 'sem': round(sum(float(o['pl']) for o in LT), 2), 'com': round(sum(float(o['plt']) for o in LT), 2),
                            'acionou': len([o for o in LT if abs(float(o['plt']) - float(o['pl'])) > 0.005]), 'regra': {k: self.prot()[k] for k in ('trava_on', 'trava_ini', 'trava_keep')}}
        except Exception:
            pass
        try:   # MESA-MOVIMENTOS-V1: agentes parecidos entrando juntos contam 1 movimento (mesmo mercado, mesmo lado, mesma meia hora)
            idsb = {x['id'] for x in (c.get('agentes') or []) if x.get('modo') == 'sombra'}
            grp = {}
            for o in ops:
                if o.get('sombra') and o.get('ag') in idsb:
                    grp.setdefault((o.get('sym'), o.get('lado'), int((o.get('t0') or 0) // 1800)), []).append(float(o.get('pl') or 0))
            tsb['mov'] = len(grp)
            tsb['sum_mov'] = round(sum(sum(v) / len(v) for v in grp.values()), 2)
        except Exception:
            pass
        ops = [o for o in ops if not o.get('sombra')]
        conta = c.get('conta') or ''
        return {'versao': VERSAO, 'ligada': bool(c.get('ligada')), 'conectada': bool(self.kv.get(K_TOK)), 'conta': (conta[:3] + '…' + conta[-3:]) if conta else '',
                'vivo': time.time() - hb < 90, 'hb': int(hb), 'erro': self.erro, 'agentes': ags, 'total': tot, 'agora': int(time.time()),
                'ops': ops[:40], 'log': self.kv.lista(K_LOG, 30), 'redis': self.kv.redis, 'prot': self.prot(), 'hoje': self.hoje(None, ops), 'supabase': self.supa, 'sombra': tsb}


def register_mesa(app):
    from flask import request, jsonify, Response
    global HL_KV
    mesa = Mesa()
    HL_KV = mesa.kv

    def ok_admin():
        s = os.environ.get('ADMIN_SENHA', '')
        return bool(s) and (request.headers.get('X-Admin-Token') == s)

    def negado():
        return jsonify({'ok': False, 'erro': 'senha de admin incorreta'}), 403

    @app.route('/api/hist/longo', methods=['GET'])
    def _hl():
        sym = request.args.get('sym', '')
        g = int(request.args.get('g', 3600) or 3600)
        d = hist_longo(sym, g)
        if d.get('status') != 'pronto':
            return jsonify(d)
        p = d['arquivo']
        mt = os.path.getmtime(p)
        c = HL_GZ.get((sym, g))
        if not c or c[0] != mt:
            with open(p) as f:
                j = json.load(f)
            j['status'] = 'pronto'
            c = HL_GZ[(sym, g)] = (mt, gzip.compress(json.dumps(j, separators=(',', ':')).encode(), 6))
        if 'gzip' in (request.headers.get('Accept-Encoding') or ''):
            return Response(c[1], mimetype='application/json', headers={'Content-Encoding': 'gzip', 'Cache-Control': 'public, max-age=3600'})
        return Response(gzip.decompress(c[1]), mimetype='application/json')

    # MESA-AGENTES-V4.2: histórico longo baixado no computador do admin e enviado pronto (a Dukascopy bloqueia o servidor)
    @app.route('/api/hist/subir', methods=['POST'])
    def _hl_subir():
        if not ok_admin():
            return negado()
        sym = request.args.get('sym', '')
        if sym not in DUKA and sym not in BINA:
            return jsonify({'ok': False, 'erro': 'mercado desconhecido'}), 400
        try:
            j = json.loads(gzip.decompress(request.get_data()).decode())
            c = j.get('c') or []
            ini = int(datetime(2010, 1, 1, tzinfo=timezone.utc).timestamp())
            vis, lim = set(), []
            for r in c:
                t, o, h, l, cl = int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])
                if t < ini or t in vis or not (cl > 0 and h >= max(o, cl) * 0.999 and l <= min(o, cl) * 1.001):
                    continue
                vis.add(t)
                lim.append([t, float('%.6g' % o), float('%.6g' % h), float('%.6g' % l), float('%.6g' % cl)])
            lim.sort(key=lambda r: r[0])
        except Exception as e:
            return jsonify({'ok': False, 'erro': 'arquivo inválido: %s' % str(e)[:120]}), 400
        if len(lim) < 5000:
            return jsonify({'ok': False, 'erro': 'poucas velas (%d)' % len(lim)}), 400
        ins = DUKA.get(sym)
        lo, hi = FAIXA.get(ins, (0.3, 5)) if ins else (0, 1e9)
        med = sorted(r[4] for r in lim)[len(lim) // 2]
        if not (lo <= med <= hi):
            return jsonify({'ok': False, 'erro': 'preço fora da faixa esperada (mediana %s)' % med}), 400
        fonte = str(j.get('fonte') or 'Dukascopy (enviado pelo admin)')[:60]
        os.makedirs(HL_DIR, exist_ok=True)
        p = _hl_path(sym, 3600)
        with open(p + '.tmp', 'w') as f:
            json.dump({'sym': sym, 'g': 3600, 'fonte': fonte, 'n': len(lim), 'de': lim[0][0], 'ate': lim[-1][0], 'em': time.time(), 'c': lim}, f, separators=(',', ':'))
        os.replace(p + '.tmp', p)
        if HL_KV is not None:
            with open(p, 'rb') as f:
                HL_KV.set('mesa:hlgz2:%s' % sym, base64.b64encode(gzip.compress(f.read(), 6)).decode(), ex=60 * 86400)
            HL_KV.delete('mesa:hl:%s' % sym)
            HL_KV.delete('mesa:hlt:%s' % sym)
        HL_JOBS.pop((sym, 3600), None)
        log('historico longo %s recebido do admin: %d velas desde %s' % (sym, len(lim), datetime.fromtimestamp(lim[0][0], tz=timezone.utc).date()))
        return jsonify({'ok': True, 'sym': sym, 'n': len(lim), 'de': lim[0][0], 'ate': lim[-1][0]})

    @app.route('/api/hist/status', methods=['GET'])
    def _hls():
        return jsonify(hist_status())

    @app.route('/api/hist/teste', methods=['GET'])
    def _hlt():
        return jsonify(hist_teste())

    @app.route('/api/mesa/estado', methods=['GET'])
    def _me():
        return jsonify(mesa.estado())

    @app.route('/api/mesa/conectar', methods=['POST'])
    def _mc():
        if not ok_admin():
            return negado()
        d = request.get_json(silent=True) or {}
        tok, conta = str(d.get('token') or '').strip(), str(d.get('conta') or '').strip()
        if not tok or not conta:
            return jsonify({'ok': False, 'erro': 'faltou token ou conta'}), 400
        try:
            ac = [x for x in Deriv(tok, conta).contas() if str(x.get('account_id')) == conta]
        except DerivErro as e:
            return jsonify({'ok': False, 'erro': 'a Deriv recusou o token (%s)' % e}), 401
        if not ac:
            return jsonify({'ok': False, 'erro': 'essa conta não pertence a esse token'}), 403
        if str(ac[0].get('account_type')) != 'demo':
            return jsonify({'ok': False, 'erro': 'a Mesa só aceita conta DEMO'}), 403
        mesa.kv.set(K_TOK, tok)
        c = mesa.cfg()
        c['conta'] = conta
        mesa.salva(c)
        mesa.nota('demo conectada (%s…%s)' % (conta[:3], conta[-3:]))
        return jsonify({'ok': True, 'saldo': ac[0].get('balance')})

    @app.route('/api/mesa/ligar', methods=['POST'])
    def _ml():
        if not ok_admin():
            return negado()
        d = request.get_json(silent=True) or {}
        c = mesa.cfg()
        c['ligada'] = bool(d.get('ligada'))
        if c['ligada'] and not (mesa.kv.get(K_TOK) and c.get('conta')):
            return jsonify({'ok': False, 'erro': 'conecte a demo primeiro'}), 400
        mesa.salva(c)
        mesa.nota('Mesa %s' % ('LIGADA' if c['ligada'] else 'desligada (posições abertas continuam com stop e alvo na Deriv)'))
        return jsonify({'ok': True, 'ligada': c['ligada']})

    @app.route('/api/mesa/agente', methods=['POST'])
    def _ma():
        if not ok_admin():
            return negado()
        d = (request.get_json(silent=True) or {}).get('agente') or {}
        c = mesa.cfg()
        L = c.get('agentes') or []
        velho = [x for x in L if x['id'] == d.get('id')]
        try:
            a = _limpa_ag(d, velho[0] if velho else None)
        except Exception as e:
            return jsonify({'ok': False, 'erro': str(e)}), 400
        if not velho and len(L) >= 48:
            return jsonify({'ok': False, 'erro': 'a mesa já tem 48 agentes; remova um antes'}), 400
        c['agentes'] = [x for x in L if x['id'] != a['id']] + [a]
        mesa.salva(c)
        mesa.nota('agente %s %s' % (a['nome'], 'atualizado' if velho else 'entrou na mesa'))
        return jsonify({'ok': True, 'agente': a})

    @app.route('/api/mesa/candidatos', methods=['POST'])
    def _mcand():
        """MESA-AGENTES-V4: várias regras da Fábrica de uma vez, como SOMBRA (o diretor promove as boas)"""
        if not ok_admin():
            return negado()
        lista = (request.get_json(silent=True) or {}).get('lista') or []
        c = mesa.cfg()
        L = c.get('agentes') or []
        ids = {x['id'] for x in L}
        novos, erros = 0, []
        for d in lista[:40]:
            if len(L) >= 50:   # CONSENSO-V1: cabe 50
                erros.append('mesa cheia (50 agentes)')
                break
            try:
                d = dict(d, modo='sombra')
                a = _limpa_ag(d)
                if a['id'] in ids:
                    continue
                L.append(a)
                ids.add(a['id'])
                novos += 1
            except Exception as e:
                erros.append(str(e)[:80])
        c['agentes'] = L
        mesa.salva(c)
        mesa.nota('%d candidato(s) entraram como SOMBRA (o diretor promove para a demo quem fizer %d+ operações com fator >= %.2f)' % (novos, mesa.prot()['prom_n'], mesa.prot()['prom_pf']))
        return jsonify({'ok': True, 'novos': novos, 'erros': erros[:5]})

    @app.route('/api/mesa/agente/remover', methods=['POST'])
    def _mr():
        if not ok_admin():
            return negado()
        aid = str((request.get_json(silent=True) or {}).get('id') or '')
        c = mesa.cfg()
        if mesa.st_ag(aid).get('pos'):
            return jsonify({'ok': False, 'erro': 'esse agente está com posição aberta; espere fechar'}), 400
        c['agentes'] = [x for x in c.get('agentes') or [] if x['id'] != aid]
        mesa.salva(c)
        mesa.nota('agente %s saiu da mesa' % aid)
        return jsonify({'ok': True})

    @app.route('/api/mesa/zerar', methods=['POST'])
    def _mz():
        if not ok_admin():
            return negado()
        aid = str((request.get_json(silent=True) or {}).get('id') or '')
        ops = [o for o in mesa.kv.lista(K_OPS, 20000) if o.get('ag') != aid]
        mesa.kv.delete(K_OPS)
        mesa.kv._l.pop(K_OPS, None)
        for o in reversed(ops):
            mesa.kv.push(K_OPS, o)
        mesa.nota('placar do agente %s zerado' % aid)
        return jsonify({'ok': True})

    @app.route('/api/mesa/protecao', methods=['POST'])
    def _mp():
        if not ok_admin():
            return negado()
        d = request.get_json(silent=True) or {}
        c = mesa.cfg()
        p = mesa.prot()
        try:
            for k in PROT_PADRAO:
                if d.get(k) not in (None, ''):
                    p[k] = max(0.0, float(str(d[k]).replace(',', '.')))
            p['apos_n'] = int(p['apos_n'])
        except Exception:
            return jsonify({'ok': False, 'erro': 'valores inválidos'}), 400
        c['prot'] = p
        mesa.salva(c)
        mesa.nota('proteções: stop do dia da mesa $%.0f · por agente $%.0f · aposenta com %d ops e fator < %.2f' % (p['stop_dia'], p['stop_ag_dia'], p['apos_n'], p['apos_pf']))
        return jsonify({'ok': True, 'prot': p})

    threading.Thread(target=mesa.supervisor, daemon=True).start()
    log('%s registrada (Redis: %s)' % (VERSAO, 'sim' if mesa.kv.redis else 'NAO - sem REDIS_URL o placar some a cada deploy'))
    return mesa
