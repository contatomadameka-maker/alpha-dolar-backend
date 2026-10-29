# -*- coding: utf-8 -*-
"""AGENTE-IA-V1 — Agente IA na sombra.

De hora em hora (vela de 1h fechada) o servidor faz sozinho a mesma "✨ Análise IA" que o usuário faz no gráfico:
  leitura SMC calculada por código (porta em Python do smc-motor.js) -> planos com entrada/stop/alvo -> a IA escolhe ou manda esperar.
Nada é comprado: o sinal entra em aia:sinais com origem='agente' e o conferidor do analise_ia (confere) marca alvo/stop nas velas da Deriv.
Só chama a IA quando o código achou plano (custo baixo: no máximo 1 chamada por mercado por hora).

  GET  /api/agente-ia/placar    -> placar só do agente (30 dias), por mercado, últimos sinais
  GET  /api/agente-ia/estado    -> última rodada (o que leu em cada mercado)
  POST /api/agente-ia/rodar     -> roda agora (X-Admin-Token = ADMIN_SENHA)
Variáveis: AGENTE_IA_LIGADO (1), AGENTE_IA_MERCADOS (lista separada por vírgula), AGENTE_IA_TF (3600).
"""
import os, time, math, threading
from nuvem_digitos import KV, Conexao

VERSAO = 'AGENTE-IA-V1.2'  # V1.2 ESPEROU-V1: planos recusados viram sombra ·  # V1.1: aparece no Escritorio como agente SOMBRA (placar com risco fixo de $10 por sinal)
MERCADOS = {'frxXAUUSD': ('Ouro', 2), 'frxXAGUSD': ('Prata', 3), 'frxEURUSD': ('EUR/USD', 5), 'frxGBPUSD': ('GBP/USD', 5),
            'frxUSDJPY': ('USD/JPY', 3), 'cryBTCUSD': ('Bitcoin', 2), 'cryETHUSD': ('Ethereum', 2)}
TFN = {60: 'M1', 300: 'M5', 900: 'M15', 1800: 'M30', 3600: 'H1', 14400: 'H4', 86400: 'D1'}


def log(*a):
    print('[AgenteIA]', *a, flush=True)


def htf_de(g):
    return 3600 if g <= 1800 else 14400 if g <= 3600 else 86400


# ═══════════════ motor SMC (mesma lógica do smc-motor.js) ═══════════════
def ema(a, n):
    k, o, e = 2.0 / (n + 1), [], a[0]
    for i, x in enumerate(a):
        e = x * k + e * (1 - k) if i else x
        o.append(e)
    return o


def atr(B, n):
    o, s = [], 0.0
    for i, b in enumerate(B):
        tr = max(b['h'] - b['l'], abs(b['h'] - B[i - 1]['c']), abs(b['l'] - B[i - 1]['c'])) if i else b['h'] - b['l']
        s = (s * i + tr) / (i + 1) if i < n else (s * (n - 1) + tr) / n
        o.append(s)
    return o


def rsi(c, n):
    o, g, l = [50.0], 0.0, 0.0
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        up, dn = max(d, 0), max(-d, 0)
        if i <= n:
            g += up / n
            l += dn / n
        else:
            g = (g * (n - 1) + up) / n
            l = (l * (n - 1) + dn) / n
        o.append(100.0 if l == 0 else 100 - 100 / (1 + g / l))
    return o


def sma(a, n):
    o = []
    for i in range(len(a)):
        w = a[max(0, i - n + 1):i + 1]
        o.append(sum(w) / len(w))
    return o


def stoch_rsi(c):
    r, st = rsi(c, 14), []
    for i in range(len(r)):
        w = r[max(0, i - 13):i + 1]
        mn, mx = min(w), max(w)
        st.append((r[i] - mn) / (mx - mn) * 100 if mx > mn else 50.0)
    k = sma(st, 3)
    return k, sma(k, 3)


def swings(B, L):
    H, Lo = [], []
    for i in range(L, len(B) - L):
        ih = il = True
        for j in range(i - L, i + L + 1):
            if j == i:
                continue
            if B[j]['h'] >= B[i]['h']:
                ih = False
            if B[j]['l'] <= B[i]['l']:
                il = False
        if ih:
            H.append({'i': i, 'p': B[i]['h']})
        if il:
            Lo.append({'i': i, 'p': B[i]['l']})
    return {'H': H, 'L': Lo}


def analisa(B, Bh=None):
    n = len(B)
    cl = [b['c'] for b in B]
    at = atr(B, 14)[n - 1]
    px = cl[n - 1]
    sw = swings(B, 3)
    ev, tend, lastH, lastL, hi, li = [], 0, None, None, 0, 0
    for i in range(n):
        while hi < len(sw['H']) and sw['H'][hi]['i'] + 3 <= i:
            lastH = sw['H'][hi]
            hi += 1
        while li < len(sw['L']) and sw['L'][li]['i'] + 3 <= i:
            lastL = sw['L'][li]
            li += 1
        if lastH and cl[i] > lastH['p'] and (not ev or ev[-1]['nivel'] != lastH['p']):
            ev.append({'i': i, 'dir': 1, 'nivel': lastH['p'], 'de': lastH['i'], 'tipo': 'CHoCH' if tend == -1 else 'BOS'})
            tend, lastH = 1, None
        elif lastL and cl[i] < lastL['p'] and (not ev or ev[-1]['nivel'] != lastL['p']):
            ev.append({'i': i, 'dir': -1, 'nivel': lastL['p'], 'de': lastL['i'], 'tipo': 'CHoCH' if tend == 1 else 'BOS'})
            tend, lastL = -1, None
    varr = []
    for a in range(max(0, n - 30), n):
        shs = [s for s in sw['H'] if a - 80 < s['i'] < a - 2]
        sls = [s for s in sw['L'] if a - 80 < s['i'] < a - 2]
        sh, sl = (shs[-1] if shs else None), (sls[-1] if sls else None)
        if sh and B[a]['h'] > sh['p'] and B[a]['c'] < sh['p']:
            varr.append({'i': a, 'dir': -1, 'nivel': sh['p'], 'nome': 'Varredura de topo'})
        if sl and B[a]['l'] < sl['p'] and B[a]['c'] > sl['p']:
            varr.append({'i': a, 'dir': 1, 'nivel': sl['p'], 'nome': 'Varredura de fundo'})
    varr = varr[-3:]
    obs = []
    for e in ev[-6:]:
        for j in range(e['i'] - 1, max(0, e['de'] - 4) - 1, -1):
            if (B[j]['c'] < B[j]['o']) if e['dir'] > 0 else (B[j]['c'] > B[j]['o']):
                ob = {'i': j, 'dir': e['dir'], 'lo': B[j]['l'], 'hi': B[j]['h'], 'ev': e['tipo'], 'vivo': True}
                for k in range(e['i'] + 1, n):
                    if (cl[k] < ob['lo']) if e['dir'] > 0 else (cl[k] > ob['hi']):
                        ob['vivo'] = False
                        break
                if ob['vivo']:
                    obs.append(ob)
                break
    fvg = []
    for f in range(max(2, n - 120), n):
        if B[f]['l'] > B[f - 2]['h'] and B[f]['l'] - B[f - 2]['h'] > at * 0.15:
            z = {'i': f - 1, 'dir': 1, 'lo': B[f - 2]['h'], 'hi': B[f]['l'], 'vivo': True}
            for q in range(f + 1, n):
                if B[q]['l'] <= z['lo']:
                    z['vivo'] = False
                    break
            if z['vivo']:
                fvg.append(z)
        if B[f]['h'] < B[f - 2]['l'] and B[f - 2]['l'] - B[f]['h'] > at * 0.15:
            w = {'i': f - 1, 'dir': -1, 'lo': B[f]['h'], 'hi': B[f - 2]['l'], 'vivo': True}
            for q in range(f + 1, n):
                if B[q]['h'] >= w['hi']:
                    w['vivo'] = False
                    break
            if w['vivo']:
                fvg.append(w)
    fvg = [z for z in fvg if z['dir'] > 0][-2:] + [z for z in fvg if z['dir'] < 0][-2:]
    liq = []

    def iguais(S, d, nome):
        x = len(S) - 1
        while x > 0 and x > len(S) - 12:
            y = x - 1
            while y >= 0 and y > x - 8:
                if abs(S[x]['p'] - S[y]['p']) < at * 0.2:
                    lv, tocado = (S[x]['p'] + S[y]['p']) / 2, False
                    for t in range(S[x]['i'] + 1, n):
                        if (B[t]['h'] > lv + at * 0.05) if d > 0 else (B[t]['l'] < lv - at * 0.05):
                            tocado = True
                            break
                    if not tocado:
                        liq.append({'i': S[y]['i'], 'i2': S[x]['i'], 'dir': d, 'p': lv, 'nome': nome})
                        return
                y -= 1
            x -= 1
    iguais(sw['H'], 1, 'Liquidez EQH')
    iguais(sw['L'], -1, 'Liquidez EQL')
    faixa = None
    if sw['H'] and sw['L']:
        uh, ul = sw['H'][-1], sw['L'][-1]
        top, bot = max(uh['p'], px), min(ul['p'], px)
        faixa = {'hi': top, 'lo': bot, 'eq': (top + bot) / 2, 'subindo': ul['i'] < uh['i']}
        faixa['ote'] = [top - 0.79 * (top - bot), top - 0.62 * (top - bot)] if faixa['subindo'] else [bot + 0.62 * (top - bot), bot + 0.79 * (top - bot)]
    pts = sorted([s['p'] for s in sw['H'] + sw['L']])
    sr, u = [], 0
    while u < len(pts):
        g, v = [pts[u]], u + 1
        while v < len(pts) and pts[v] - g[0] < at * 0.35:
            g.append(pts[v])
            v += 1
        if len(g) >= 3:
            sr.append({'p': sum(g) / len(g), 'toques': len(g)})
        u = v
    sr = sorted(sr, key=lambda s: abs(s['p'] - px))[:5]
    ses, dia = [], (B[-1]['t'] // 86400) * 86400
    for nome, h0, h1 in (('Sessão de Londres', 7, 16), ('Sessão de Nova York', 13, 21)):
        xs = [b for b in B if dia + h0 * 3600 <= b['t'] < dia + h1 * 3600]
        if len(xs) >= 2:
            ses.append({'nome': nome, 't0': xs[0]['t'], 't1': xs[-1]['t'], 'hi': max(b['h'] for b in xs), 'lo': min(b['l'] for b in xs)})
    htf, htf_txt = 0, 'sem dados'
    if Bh and len(Bh) > 60:
        ch = [b['c'] for b in Bh]
        e50, e200, k2 = ema(ch, 50), ema(ch, min(200, len(ch) - 1)), len(ch) - 1
        htf = 1 if ch[k2] > e50[k2] > e200[k2] else -1 if ch[k2] < e50[k2] < e200[k2] else 0
        htf_txt = 'alta (preço acima das médias 50 e 200)' if htf > 0 else 'baixa (preço abaixo das médias 50 e 200)' if htf < 0 else 'lateral (médias cruzadas)'
    k, d = stoch_rsi(cl)
    return {'n': n, 'px': px, 'atr': at, 'sw': sw, 'ev': ev, 'varr': varr, 'obs': obs, 'fvg': fvg, 'liq': liq, 'faixa': faixa, 'sr': sr,
            'ses': ses, 'htf': htf, 'htfTxt': htf_txt, 'stk': k, 'std': d, 'tend': tend}


def planos(R):
    px, at = R['px'], R['atr']

    def plano(d):
        zonas = [z for z in R['obs'] + R['fvg'] if z['dir'] == d and ((z['lo'] < px + at * 0.2) if d > 0 else (z['hi'] > px - at * 0.2))
                 and abs((z['hi'] if d > 0 else z['lo']) - px) < at * 6]
        if R['faixa']:
            eq = R['faixa']['eq']
            zonas = [z for z in zonas if ((z['lo'] <= eq + at * 0.3) if d > 0 else (z['hi'] >= eq - at * 0.3))]
        if not zonas:
            return None
        zonas.sort(key=lambda z: abs((z['hi'] if d > 0 else z['lo']) - px))
        z = zonas[0]
        dentro = z['lo'] <= px <= z['hi']
        ent = px if dentro else (z['hi'] if d > 0 else z['lo'])
        sl = z['lo'] - at * 0.3 if d > 0 else z['hi'] + at * 0.3
        for v in R['varr']:
            if v['dir'] == d and ((ent - at * 3 < v['nivel'] < ent) if d > 0 else (ent < v['nivel'] < ent + at * 3)):
                sl = min(sl, z['lo'] - at * 0.3) if d > 0 else max(sl, z['hi'] + at * 0.3)
        risco = abs(ent - sl)
        if risco < at * 0.2:
            risco = at * 0.2
            sl = ent - d * risco
        alvos = [l['p'] for l in R['liq'] if l['dir'] == d] + [s['p'] for s in (R['sw']['H'] if d > 0 else R['sw']['L'])[-8:]]
        alvos = sorted([p for p in alvos if ((p > ent + risco * 1.5) if d > 0 else (p < ent - risco * 1.5))], reverse=d < 0)
        tp = alvos[0] if alvos else ent + d * risco * 2
        rr = abs(tp - ent) / risco
        cap = False
        if rr > 4:
            tp, rr, cap = ent + d * risco * 3, 3, True
        if (px >= tp - risco * 0.5) if d > 0 else (px <= tp + risco * 0.5):
            return None
        por = ('order block (%s)' % z['ev'] if z.get('ev') else 'FVG') + (', preço dentro da zona' if dentro else ', esperar o preço voltar à zona') + \
              (', alvo na liquidez' if alvos and not cap else ', alvo pelo risco')
        return {'dir': d, 'ent': ent, 'sl': sl, 'tp': tp, 'rr': round(rr * 100) / 100.0, 'dentro': dentro, 'zona': z, 'por': por}
    return {'compra': plano(1), 'venda': plano(-1)}


def leitura(sym, g, B, R, P, hg, stk=10.0, mu=100.0):
    nome, d = MERCADOS.get(sym, (sym, 5))
    px = R['px']
    f = lambda v: ('%.' + str(d) + 'f') % v

    def z(L):
        return '; '.join(('OB ' + x['ev'] if x.get('ev') else 'FVG') + ' ' + f(x['lo']) + '-' + f(x['hi']) for x in L) or 'nenhuma'

    def pl(p):
        if not p:
            return None
        e = px if p['dentro'] else p['ent']
        return {'ent': f(p['ent']), 'sl': f(p['sl']), 'tp': f(p['tp']), 'rr': p['rr'], 'dentro': bool(p['dentro']),
                'sl_usd': '%.2f' % (stk * mu * abs(e - p['sl']) / e), 'tp_usd': '%.2f' % (stk * mu * abs(p['tp'] - e) / e), 'por': p['por']}
    zs = R['obs'] + R['fvg']
    return {'sym': sym, 'nome': nome, 'tf': TFN.get(g, str(g)), 'px': f(px), 'atr': f(R['atr']), 'htf_tf': TFN.get(hg, '-') if hg else '-', 'htf': R['htfTxt'],
            'estrutura': ', '.join(e['tipo'] + (' de alta' if e['dir'] > 0 else ' de baixa') + ' em ' + f(e['nivel']) for e in R['ev'][-3:]) or 'sem rompimentos',
            'varreduras': ', '.join(v['nome'] + ' em ' + f(v['nivel']) for v in R['varr']) or 'nenhuma',
            'demanda': z([x for x in zs if x['dir'] > 0]), 'oferta': z([x for x in zs if x['dir'] < 0]),
            'liquidez': ', '.join(l['nome'] + ' ' + f(l['p']) for l in R['liq']) or 'nenhuma',
            'pd': ('equilíbrio %s, preço em %s' % (f(R['faixa']['eq']), 'premium (caro)' if px > R['faixa']['eq'] else 'discount (barato)')) if R['faixa'] else 'sem faixa',
            'stoch': 'K %.0f D %.0f' % (R['stk'][-1], R['std'][-1]),
            'sessao': ', '.join(s['nome'] for s in R['ses']) or 'fora das sessões principais',
            'planos': {'compra': pl(P['compra']), 'venda': pl(P['venda'])}}


# ═══════════════ o agente ═══════════════
def register_agente_ia(app):
    from flask import request, jsonify
    kv = app.extensions.get('aia_kv') or KV()
    st = {'rodando': False}

    def mercados():
        L = [s.strip() for s in os.environ.get('AGENTE_IA_MERCADOS', '').split(',') if s.strip()]
        return L or list(MERCADOS)

    def conexao():
        tok = kv.get('mesa:tok') or ''
        conta = str((kv.jget('mesa:cfg') or {}).get('conta') or '')
        return Conexao(tok, conta) if tok and conta else None

    def velas(c, sym, g, n):
        q = {'ticks_history': sym, 'underlying_symbol': sym, 'end': 'latest', 'count': n, 'style': 'candles', 'granularity': g}
        r = c.req(q, 25)
        em = str((r.get('error') or {}).get('message', ''))
        if r.get('error') and ('underlying_symbol' in em or 'Properties not allowed' in em or 'validation' in em.lower()):
            q.pop('underlying_symbol', None)
            r = c.req(q, 25)
        if r.get('error'):
            raise RuntimeError(r['error'].get('message', 'erro nas velas'))
        return [{'t': int(x['epoch']), 'o': float(x['open']), 'h': float(x['high']), 'l': float(x['low']), 'c': float(x['close'])} for x in (r.get('candles') or [])]

    def aberto(sym):
        for s in (kv.jget('aia:sinais', []) or [])[:200]:
            if s.get('origem') == 'agente' and s.get('sym') == sym and s.get('st') in ('val', 'and'):
                return True
        return False

    def rodada(forcar=False):
        ia = app.extensions.get('aia_ia')
        if ia is None:
            return {'ok': False, 'erro': 'analise_ia sem aia_ia (instale o patch)'}
        g = int(os.environ.get('AGENTE_IA_TF', '3600'))
        hg = htf_de(g)
        c = conexao()
        if c is None:
            return {'ok': False, 'erro': 'sem conta da Mesa conectada (mesa:tok / mesa:cfg)'}
        res, agora = [], time.time()
        try:
            for sym in mercados():
                it = {'sym': sym, 't': int(agora)}
                try:
                    B = velas(c, sym, g, 301)
                    if len(B) < 120:
                        it['msg'] = 'poucas velas'
                        res.append(it)
                        continue
                    if agora - B[-1]['t'] > g * 3:
                        it['msg'] = 'mercado fechado'
                        res.append(it)
                        continue
                    B = B[:-1]                                   # só velas fechadas
                    try:
                        Bh = velas(c, sym, hg, 261)[:-1]
                    except Exception:
                        Bh = []
                    R = analisa(B, Bh)
                    P = planos(R)
                    it['planos'] = [k for k in ('compra', 'venda') if P[k]]
                    if not it['planos']:
                        it['msg'] = 'sem plano (código não achou zona com alvo)'
                        res.append(it)
                        continue
                    if aberto(sym) and not forcar:
                        it['msg'] = 'já tem sinal do agente em aberto'
                        res.append(it)
                        continue
                    L = leitura(sym, g, B, R, P, hg if len(Bh) > 60 else 0)
                    r, erro = ia(L)
                    if r is None:
                        it['msg'] = 'IA: ' + str(erro)
                        res.append(it)
                        continue
                    it.update({'escolha': r['escolha'], 'conf': r['confianca'], 'motivo': r['motivo'][:200]})
                    p = P.get(r['escolha']) if r['escolha'] in ('compra', 'venda') else None
                    S = kv.jget('aia:sinais', []) or []
                    S.insert(0, {'id': 'ag%d%s' % (int(time.time() * 1000), sym[-3:]), 't': int(time.time()), 'conta': 'IA', 'tipo': 'sombra', 'origem': 'agente',
                                 'sym': sym, 'tf': TFN.get(g, str(g)), 'g': g, 'escolha': r['escolha'], 'dir': p['dir'] if p else 0, 'conf': r['confianca'],
                                 'ent': p['ent'] if p else None, 'sl': p['sl'] if p else None, 'tp': p['tp'] if p else None, 'rr': p['rr'] if p else None,
                                 'px': R['px'], 'dentro': bool(p and p['dentro']), 'st': ('and' if p['dentro'] else 'val') if p else 'sem',
                                 'motivo': r['motivo'][:300]})
                    if not p:      # ESPEROU-V1: o plano que a IA recusou vira sombra (1 por mercado e lado em aberto)
                        for kk in ('compra', 'venda'):
                            q = P.get(kk)
                            if q and not any(x.get('origem') == 'agente-esperou' and x.get('sym') == sym and x.get('dir') == q['dir'] and x.get('st') in ('val', 'and') for x in S[:300]):
                                S.insert(0, {'id': 'ae%d%s%d' % (int(time.time() * 1000), sym[-3:], q['dir'] + 1), 't': int(time.time()), 'conta': 'IA', 'tipo': 'sombra', 'origem': 'agente-esperou',
                                             'sym': sym, 'tf': TFN.get(g, str(g)), 'g': g, 'escolha': kk, 'dir': q['dir'], 'conf': r['confianca'], 'ent': q['ent'], 'sl': q['sl'], 'tp': q['tp'],
                                             'rr': q['rr'], 'px': R['px'], 'dentro': bool(q['dentro']), 'st': 'and' if q['dentro'] else 'val'})
                    kv.jset('aia:sinais', S[:1500], ex=86400 * 60)
                except PermissionError:
                    it['msg'] = 'token da Mesa expirou: conecte de novo'
                    res.append(it)
                    break
                except Exception as e:
                    it['msg'] = 'erro: ' + str(e)[:80]
                res.append(it)
        finally:
            c.fecha()
        kv.jset('agia:ult', {'t': int(agora), 'tf': TFN.get(g), 'itens': res}, ex=86400 * 7)
        log('rodada', ', '.join('%s=%s' % (x['sym'], x.get('escolha') or x.get('msg', '')) for x in res))
        return {'ok': True, 'itens': res}

    def laco():
        time.sleep(90)
        while True:
            try:
                if os.environ.get('AGENTE_IA_LIGADO', '1') != '0':
                    g = int(os.environ.get('AGENTE_IA_TF', '3600'))
                    slot = int(time.time() // g)
                    # roda 1x por vela, 2 min depois dela fechar, em um processo só
                    if time.time() - slot * g >= 120 and kv.setnx('agia:slot:%d:%d' % (g, slot), '1', g * 2):
                        rodada()
            except Exception as e:
                log('laco', e)
            time.sleep(60)
    threading.Thread(target=laco, daemon=True).start()

    def adm():
        s = os.environ.get('ADMIN_SENHA', '')
        return bool(s) and request.headers.get('X-Admin-Token') == s

    @app.route('/api/agente-ia/rodar', methods=['POST'])
    def _agia_rodar():
        if not adm():
            return jsonify({'ok': False, 'erro': 'senha de admin'}), 403
        if st['rodando']:
            return jsonify({'ok': False, 'erro': 'já está rodando'})
        st['rodando'] = True
        try:
            return jsonify(rodada(forcar=request.args.get('forcar') == '1'))
        finally:
            st['rodando'] = False

    @app.route('/api/agente-ia/estado', methods=['GET'])
    def _agia_estado():
        return jsonify({'ok': True, 'versao': VERSAO, 'ligado': os.environ.get('AGENTE_IA_LIGADO', '1') != '0', 'mercados': mercados(),
                        'ult': kv.jget('agia:ult') or None, 'mesa_conectada': bool(kv.get('mesa:tok'))})

    @app.route('/api/agente-ia/placar', methods=['GET'])
    def _agia_placar():
        S = [s for s in (kv.jget('aia:sinais', []) or []) if s.get('origem') == 'agente' and time.time() - s.get('t', 0) < 30 * 86400]
        D = [s for s in S if s.get('dir')]
        alv = [s for s in D if s.get('st') == 'alv']
        stp = [s for s in D if s.get('st') == 'stp']
        n = len(alv) + len(stp)
        por = {}
        for s in alv + stp:
            m = por.setdefault(s['sym'], {'alvo': 0, 'stop': 0, 'r': 0.0})
            if s['st'] == 'alv':
                m['alvo'] += 1
                m['r'] = round(m['r'] + float(s.get('rr') or 0), 2)
            else:
                m['stop'] += 1
                m['r'] = round(m['r'] - 1, 2)
        rs = app.extensions.get('aia_resumo')
        E = [s for s in (kv.jget('aia:sinais', []) or []) if s.get('origem') == 'agente-esperou' and time.time() - s.get('t', 0) < 30 * 86400]
        return jsonify({'ok': True, 'versao': VERSAO, 'analises': len(S), 'esperou': len([s for s in S if not s.get('dir')]), 'resolvidos': n, 'planos_recusados': rs(E) if rs else None,
                        'alvo': len(alv), 'stop': len(stp), 'pc': round(len(alv) * 100.0 / n, 1) if n else None,
                        'saldo_r': round(sum(float(s.get('rr') or 0) for s in alv) - len(stp), 2),
                        'em_aberto': len([s for s in D if s.get('st') in ('val', 'and')]), 'invalidados': len([s for s in D if s.get('st') in ('inv', 'exp')]),
                        'por_mercado': por,
                        'ult': [{'t': s['t'], 'sym': s['sym'], 'tf': s.get('tf'), 'dir': s['dir'], 'ent': s.get('ent'), 'sl': s.get('sl'), 'tp': s.get('tp'),
                                 'rr': s.get('rr'), 'conf': s.get('conf'), 'st': s['st'], 'motivo': s.get('motivo')} for s in D[:20]]})

    RISCO = 10.0     # placar em $: cada sinal arrisca $10 no stop (alvo paga rr x $10)

    def agente_escritorio():
        S = [s for s in (kv.jget('aia:sinais', []) or []) if s.get('origem') == 'agente' and s.get('dir')]
        F = sorted([s for s in S if s.get('st') in ('alv', 'stp')], key=lambda x: x.get('fim') or x['t'])
        ult, eq, pico, dd, w, curva = [], 0.0, 0.0, 0.0, 0, [0]
        for s in F:
            pl = round(RISCO * float(s.get('rr') or 0), 2) if s['st'] == 'alv' else -RISCO
            eq += pl
            w += 1 if pl > 0 else 0
            pico = max(pico, eq)
            dd = max(dd, pico - eq)
            curva.append(round(eq, 2))
            nm = MERCADOS.get(s['sym'], (s['sym'], 5))[0]
            ult.append({'id': s.get('id'), 'ag': 'agente-ia', 'nome': 'Agente IA', 't0': s['t'], 't1': int(s.get('fim') or s['t']), 'lado': s['dir'], 'stk': RISCO,
                        'pl': pl, 'motivo': '%s %s · %s' % (nm, s.get('tf') or '', 'alvo' if s['st'] == 'alv' else 'stop'), 'sombra': 1})
        hoje = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 3 * 3600))
        U = kv.jget('agia:ult') or {}
        abertos = [s for s in S if s.get('st') in ('val', 'and')]
        txt = ' | '.join('%s: %s' % (MERCADOS.get(i['sym'], (i['sym'],))[0], i.get('escolha') or i.get('msg', '')) for i in (U.get('itens') or []))
        g = int(os.environ.get('AGENTE_IA_TF', '3600'))
        n = len(F)
        nivel = 'cedo' if n < 20 else ('forte' if eq > 0 and w * 1.0 / n >= 0.45 else 'ok' if eq > 0 else 'ruim')
        return {'id': 'agente-ia', 'nome': 'Agente IA', 'sym': 'cryBTCUSD', 'g': g, 'regra': 'ia', 'f': '', 'x': {}, 'stk': RISCO, 'mq': 100, 'an': [],
                'modo': 'sombra', 'ativo': os.environ.get('AGENTE_IA_LIGADO', '1') != '0', 'bt': {}, 'mercado': '7 mercados', 'tf': TFN.get(g, ''),
                'regra_n': 'SMC + IA (Claude escolhe)', 'saida': 'stop e alvo do plano, risco $10', 'analistas': [], 'etapa': 'sombra',
                'st': {'estado': 'analisando', 'ta': U.get('t'), 'prox': (int(time.time() // g) + 1) * g + 120,
                       'txt': ('Sinais em aberto: %d. ' % len(abertos) if abertos else '') + (txt or 'esperando a primeira rodada')},
                'placar': {'n': n, 'w': w, 'sum': round(eq, 2), 'dd': round(dd, 2), 'curva': curva[-200:], 'pf': None,
                           'hoje': round(sum(o['pl'] for o in ult if time.strftime('%Y-%m-%d', time.gmtime(o['t1'] - 3 * 3600)) == hoje), 2)},
                'ult': ult[-12:][::-1],
                'auditor': {'nivel': nivel, 'txt': ('Agente IA: analisa 7 mercados de hora em hora e só dá SINAL (não compra nem vai para a demo). '
                                                    'Placar conferido nas velas da Deriv, contando $10 de risco por sinal. ') +
                            ('Ainda cedo: %d sinal(is) resolvido(s), precisa de 20+ para julgar.' % n if n < 20 else '%d sinais, %d%% no alvo, saldo %+.2f.' % (n, round(w * 100.0 / n), eq))},
                'outro': {'n': 0, 'sum': 0}}

    def diretor_escritorio(d):
        """DIRETOR-ESC-V1: o chefe dos agentes aparece no Escritório, com as regras, as últimas decisões e a trava de lucro"""
        import json as _j
        A = [x for x in (d.get('agentes') or []) if x.get('id') not in ('agente-ia', 'diretor')]
        pr = d.get('prot') or {}
        L = []
        try:
            r = getattr(kv, '_r', None)
            L = [_j.loads(x) for x in r.lrange('mesa:log', 0, 299)] if r is not None else (d.get('log') or [])
        except Exception:
            L = d.get('log') or []
        dec = [x for x in L if isinstance(x, dict) and 'DIRETOR' in str(x.get('m', ''))][:6]
        som = len([x for x in A if x.get('modo') == 'sombra' and x.get('ativo') is not False])
        dem = len([x for x in A if x.get('modo') != 'sombra' and x.get('ativo') is not False])
        apo = len([x for x in A if x.get('ativo') is False])
        tv = (d.get('sombra') or {}).get('trava') or {}
        tvt = ('Trava de lucro: liga com lucro de %d%% da entrada e garante %d%% do maior lucro (%s na demo). ' % (round(float(pr.get('trava_ini', 0.3)) * 100), round(float(pr.get('trava_keep', 0.5)) * 100), 'fecha de verdade' if pr.get('trava_on', 1) else 'só medindo')) + \
              ('Na sombra, %d operações: sem trava %+.2f · com trava %+.2f (%d vezes ela teria fechado antes).' % (tv.get('n', 0), tv.get('sem', 0), tv.get('com', 0), tv.get('acionou', 0)) if tv.get('n') else 'Na sombra ainda não há operação medida com a trava.')
        txt = ('Regras: promove da sombra para a demo quem fizer %d+ operações com fator ≥ %.2f e lucro (até %d na demo); aposenta quem fizer %d+ operações com fator < %.2f. ' % (int(pr.get('prom_n', 20)), float(pr.get('prom_pf', 1.2)), int(pr.get('max_demo', 10)), int(pr.get('apos_n', 30)), float(pr.get('apos_pf', 0.85)))) + \
              ('Agora: %d na demo · %d na sombra · %d aposentados. ' % (dem, som, apo)) + \
              (('Últimas decisões: ' + ' | '.join(time.strftime('%d/%m %H:%M', time.gmtime(int(x.get('t', 0)) - 3 * 3600)) + ' ' + str(x.get('m', '')).replace('DIRETOR: ', '') for x in dec)) if dec else 'Ainda não precisou promover nem aposentar ninguém.')
        return {'id': 'diretor', 'nome': 'Diretor', 'sym': 'frxXAUUSD', 'g': 3600, 'regra': 'diretor', 'f': '', 'x': {}, 'stk': '—', 'mq': '—', 'an': [],
                'modo': 'demo', 'ativo': True, 'bt': {}, 'mercado': 'toda a mesa', 'tf': '', 'regra_n': 'promove e aposenta os agentes', 'saida': 'decide pelos números',
                'analistas': [], 'etapa': 'diretor', 'st': {'estado': 'analisando', 'txt': txt}, 'placar': {'n': 0, 'w': 0, 'sum': 0, 'dd': 0, 'curva': [0], 'pf': None, 'hoje': 0},
                'ult': [], 'auditor': {'nivel': 'ok', 'txt': tvt}, 'outro': {'n': 0, 'sum': 0}}

    orig = app.view_functions.get('_me')
    if orig is not None:
        def _me_com_agente(*a, **k):
            r = orig(*a, **k)
            try:
                d = r.get_json()
                if isinstance(d, dict) and os.environ.get('AGENTE_IA_ESCRITORIO', '1') != '0':
                    d.setdefault('agentes', []).append(agente_escritorio())
                    d['agentes'].append(diretor_escritorio(d))   # DIRETOR-ESC-V1
                    return jsonify(d)
            except Exception as e:
                log('escritorio', e)
            return r
        app.view_functions['_me'] = _me_com_agente

    log('%s registrado (%s)%s' % (VERSAO, ', '.join(mercados()), ' + Escritorio' if orig is not None else ''))
