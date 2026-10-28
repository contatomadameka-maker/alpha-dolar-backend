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
import os, io, json, time, math, gzip, uuid, lzma, struct, zipfile, threading, traceback
import urllib.request, urllib.error
from datetime import datetime, timezone

VERSAO = 'MESA-AGENTES-V2'  # V2: stop do dia (mesa e agente) + aposentadoria automática + etapas
API = 'https://api.derivws.com/trading/v1/options'
APP_ID = os.environ.get('DERIV_OAUTH_APP_ID', '34lv1PuWzjElEuwWcDLyr')
HOLD = {3600: 72, 900: 288, 300: 864}
NOME = {'cryBTCUSD': 'Bitcoin', 'cryETHUSD': 'Ethereum', 'frxXAUUSD': 'Ouro', 'frxXAGUSD': 'Prata', 'frxEURUSD': 'EUR/USD',
        'frxGBPUSD': 'GBP/USD', 'frxUSDJPY': 'USD/JPY', 'frxAUDUSD': 'AUD/USD', 'frxUSDCAD': 'USD/CAD', 'frxUSDCHF': 'USD/CHF',
        'frxEURJPY': 'EUR/JPY', 'frxGBPJPY': 'GBP/JPY', 'frxEURGBP': 'EUR/GBP', 'frxAUDJPY': 'AUD/JPY'}
REGRA_N = {'smc': 'SMC (reteste do order block)', 'tend': 'Tendência EMA 20/50', 'rsi': 'Reversão do RSI', 'romp': 'Rompimento do dia anterior'}
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
    S = {'atr': atr_s(B, 14), 'smc': [0] * n, 'tend': [0] * n, 'rsi': [0] * n, 'romp': [0] * n,
         'slL': [0.0] * n, 'slS': [0.0] * n, 'ses': [0] * n, 'e20': e20, 'e50': e50, 'rs': rs}
    A = smc_analisa(B)
    S['smc'], S['slL'], S['slS'], S['tr'], S['obs'] = A['sig'], A['slL'], A['slS'], A['tr'], A['obs']
    dia = ''
    dH = dL = pH = pL = 0.0
    fezU = fezD = ''
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
        else:
            dH, dL = max(dH, B[i]['h']), min(dL, B[i]['l'])
        if pH and B[i]['c'] > pH and fezU != d:
            S['romp'][i] = 1
            fezU = d
        elif pL and B[i]['c'] < pL and fezD != d:
            S['romp'][i] = -1
            fezD = d
    S['pH'], S['pL'] = pH, pL
    return S


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


def _baixa(url, to=25):
    rq = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(rq, timeout=to) as r:
        return r.read()


def _hl_path(sym, g):
    return os.path.join(HL_DIR, '%s_%d.json' % (sym, g))


def _duka_mes(ins, y, m):
    """velas de 1 h de um mês inteiro (arquivo BID_candles_hour_1.bi5; o mês da URL começa em 00)."""
    url = 'https://datafeed.dukascopy.com/datafeed/%s/%04d/%02d/BID_candles_hour_1.bi5' % (ins, y, m - 1)
    try:
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
    linhas = []
    for i, (y, m) in enumerate(meses):
        for tent in range(3):
            try:
                linhas += _duka_mes(ins, y, m)
                break
            except Exception as e:
                if tent == 2:
                    log('Dukascopy %s %d-%02d falhou: %s' % (ins, y, m, e))
                time.sleep(1.5)
        prog(i + 1, len(meses), 'Dukascopy %s %d/%02d' % (ins, y, m))
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
        def prog(a, b, msg):
            st['pct'] = int(a * 100 / max(1, b))
            st['msg'] = msg
            if HL_KV is not None and a % 5 == 0:
                HL_KV.set('mesa:hl:%s' % sym, json.dumps(st), ex=900)
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
            HL_KV.delete('mesa:hl:%s' % sym)
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
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 5 * 86400:
        return {'status': 'pronto', 'arquivo': p}
    key = (sym, g)
    if HL_KV is not None:
        st = HL_KV.jget('mesa:hl:%s' % sym)
        if st and st.get('status') in ('baixando', 'erro') and not (key in HL_JOBS and HL_JOBS[key].get('status') == 'baixando'):
            return st
        if not HL_KV.trava('mesa:hlt:%s' % sym, HL_DONO, 900):
            return {'status': 'baixando', 'pct': 0, 'msg': 'outro servidor está baixando'}
    with HL_LOCK:
        st = HL_JOBS.get(key)
        if not st or st.get('status') in ('erro', 'pronto'):
            if st and st.get('status') == 'erro' and time.time() - st.get('t', 0) < 120:
                return dict(st)
            st = HL_JOBS[key] = {'status': 'baixando', 'pct': 0, 'msg': 'começando', 't': time.time()}
            threading.Thread(target=_hl_job, args=(sym, g), daemon=True).start()
    return dict(st)


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
PROT_PADRAO = {'stop_dia': 400.0, 'stop_ag_dia': 160.0, 'apos_n': 30, 'apos_pf': 0.85}
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
        raise ValueError('agente precisa de sym, g (3600/900/300) e regra (smc/tend/rsi/romp)')
    x = {k: float(v) for k, v in (a.get('x') or {}).items() if k in ('es', 'r', 'a1', 'a2', 'sl', 'tp') and v not in (None, '')}
    if not (x.get('es') or x.get('a1') or (x.get('sl') and x.get('tp'))):
        raise ValueError('saída inválida')
    aid = str(a.get('id') or '%s-%s-%s%s' % (sym[-6:].lower(), regra, TF_N[g], '-s' if a.get('f') else ''))[:40]
    return {'id': aid, 'nome': str(a.get('nome') or ('Agente ' + NOME.get(sym, sym)))[:40], 'sym': sym, 'g': g, 'regra': regra,
            'f': 's' if a.get('f') else '', 'x': x, 'stk': max(1.0, min(2000.0, float(a.get('stk') or 80))), 'mq': int(a.get('mq') or 100),
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

    def prot(self):
        p = dict(PROT_PADRAO)
        p.update({k: v for k, v in (self.cfg().get('prot') or {}).items() if k in PROT_PADRAO})
        return p

    def hoje(self, aid=None, ops=None):
        """resultado de hoje (Brasília): fechadas + o que está aberto agora"""
        d = dia_brt(time.time())
        ops = ops if ops is not None else self.kv.lista(K_OPS, 3000)
        v = sum(o['pl'] for o in ops if dia_brt(o.get('t1') or 0) == d and (aid is None or o.get('ag') == aid))
        for a in self.cfg().get('agentes') or []:
            if aid is None or a['id'] == aid:
                po = (self.st.get(a['id']) or {}).get('pos') or {}
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
            B = self.d.velas(a['sym'], g, 1000)
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
        S = sinais(B)
        i = len(B) - 1
        lado = S[a['regra']][i]
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
        if lado:
            pr = self.prot()
            ops = self.kv.lista(K_OPS, 3000)
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

    def leitura(self, a, S, B, i, lado):
        r, px = a['regra'], B[i]['c']
        if r == 'rsi':
            t = 'RSI %.1f · compra quando cruza abaixo de 25, vende quando cruza acima de 75' % S['rs'][i]
        elif r == 'tend':
            up = S['e20'][i] > S['e50'][i]
            t = 'EMA 20 %s da EMA 50 · espera o preço recuar até a EMA 20 (%.5g) e voltar' % ('acima' if up else 'abaixo', S['e20'][i])
        elif r == 'smc':
            t = 'estrutura %s · %d order block(s) vivo(s) · espera o reteste a favor' % ({1: 'de alta', -1: 'de baixa'}.get(S['tr'], 'indefinida'), S['obs'])
        else:
            t = 'máxima de ontem %.5g · mínima de ontem %.5g · preço %.5g' % (S['pH'], S['pL'], px)
        if lado:
            t = ('SINAL DE COMPRA · ' if lado > 0 else 'SINAL DE VENDA · ') + t
        return t

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
        s.pop('pos', None)
        s['estado'] = 'analisando'
        s['ultop'] = op
        self.nota('%s fechou %s em %s: %s%.2f (%s)' % (a['nome'], 'compra' if p['lado'] > 0 else 'venda', NOME.get(a['sym'], a['sym']), '+' if pl >= 0 else '−', abs(pl), mot))
        # MESA-AGENTES-V2: aposentadoria automática
        try:
            pr = self.prot()
            L = [o for o in self.kv.lista(K_OPS, 5000) if o.get('ag') == a['id']]
            if pr['apos_n'] and len(L) >= int(pr['apos_n']) and fator(L) < float(pr['apos_pf']):
                c = self.cfg()
                for x in c.get('agentes') or []:
                    if x['id'] == a['id']:
                        x['ativo'] = False
                        x['aposentado'] = {'t': int(time.time()), 'n': len(L), 'pf': round(fator(L), 2), 'sum': round(sum(o['pl'] for o in L), 2)}
                self.salva(c)
                s['estado'] = 'aposentado'
                s['txt'] = 'Aposentado: %d operações reais com fator %.2f (abaixo de %.2f). Fica no descanso; o admin pode religar.' % (len(L), fator(L), pr['apos_pf'])
                self.nota('%s APOSENTADO: %d operações, fator %.2f, %s%.2f' % (a['nome'], len(L), fator(L), '+' if sum(o['pl'] for o in L) >= 0 else '−', abs(sum(o['pl'] for o in L))))
        except Exception as e:
            log('aposentadoria:', e)

    # ---------- para o Escritório ----------
    def estado(self):
        c = self.cfg()
        ops = self.kv.lista(K_OPS, 5000)
        hb = float(self.kv.get('mesa:hb') or 0)
        ags = []
        tot = {'n': 0, 'w': 0, 'sum': 0.0}
        for a in c.get('agentes') or []:
            s = self.st.get(a['id']) if self.lider else None
            if s is None:
                s = self.kv.jget('mesa:st:' + a['id']) or {}
            L = [o for o in ops if o.get('ag') == a['id']]
            L.reverse()
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
            etapa = 'aposentado' if not a.get('ativo') else ('em teste' if len(L) < int(pr['apos_n']) else 'aprovado' if fator(L) >= 1.1 else 'em observação')
            tot['n'] += len(L)
            tot['w'] += w
            tot['sum'] += eq
            x = dict(a)
            x.update({'mercado': NOME.get(a['sym'], a['sym']), 'tf': TF_N.get(a['g'], ''), 'regra_n': REGRA_N.get(a['regra'], a['regra']),
                      'saida': saida_nome(a['x']), 'st': {k: v for k, v in s.items() if k != 'ultop'}, 'placar': pl,
                      'ult': [o for o in L[-12:]][::-1], 'etapa': etapa})
            ags.append(x)
        tot['sum'] = round(tot['sum'], 2)
        conta = c.get('conta') or ''
        return {'versao': VERSAO, 'ligada': bool(c.get('ligada')), 'conectada': bool(self.kv.get(K_TOK)), 'conta': (conta[:3] + '…' + conta[-3:]) if conta else '',
                'vivo': time.time() - hb < 90, 'hb': int(hb), 'erro': self.erro, 'agentes': ags, 'total': tot, 'agora': int(time.time()),
                'ops': ops[:40], 'log': self.kv.lista(K_LOG, 30), 'redis': self.kv.redis, 'prot': self.prot(), 'hoje': self.hoje(None, ops)}


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
        if not velho and len(L) >= 16:
            return jsonify({'ok': False, 'erro': 'a mesa já tem 16 agentes; remova um antes'}), 400
        c['agentes'] = [x for x in L if x['id'] != a['id']] + [a]
        mesa.salva(c)
        mesa.nota('agente %s %s' % (a['nome'], 'atualizado' if velho else 'entrou na mesa'))
        return jsonify({'ok': True, 'agente': a})

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
