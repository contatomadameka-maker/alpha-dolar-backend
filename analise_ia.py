# -*- coding: utf-8 -*-
"""ANALISE-IA-V1 — "✨ Análise IA" do Alpha Global.

O navegador faz a leitura técnica (SMC: estrutura, varredura, order block, FVG, liquidez, OTE, sessões, S/R, Stoch RSI)
e monta até 2 planos prontos (compra e venda) com entrada, stop e alvo calculados pelo código.
Este módulo só pede para a IA ESCOLHER entre os planos (ou mandar esperar) e EXPLICAR em português.
A IA nunca inventa preço: entrada/stop/alvo vêm do código.

  POST /api/analise-ia   {token, conta, leitura:{...}}  -> {ok, escolha, confianca, motivo, riscos, concordam, restam}
  GET  /api/analise-ia/placar                     -> acerto real dos sinais de todos (30 dias), conferido com as velas da Deriv
Limite: ANALISE_IA_LIMITE por conta por dia (padrão 10). Cada análise fica guardada (placar futuro).
"""
import os, re, json, time, hashlib, urllib.request
from datetime import datetime, timezone, timedelta

import threading
from nuvem_digitos import KV, contas_do_token, Conexao

TFS = {'M1': 60, 'M5': 300, 'M15': 900, 'M30': 1800, 'H1': 3600, 'H4': 14400, 'D1': 86400}
FIM = ('alv', 'stp', 'inv', 'exp')

VERSAO = 'ANALISE-IA-V2'  # V2: o servidor confere todos os sinais com as velas da Deriv e mostra o placar real (/api/analise-ia/placar)
BRT = timezone(timedelta(hours=-3))


def log(*a):
    print('[AnaliseIA]', *a, flush=True)


def limpa(v, n=80):
    return re.sub(r'[^\w\s.,:/%+\-()·=<>]', '', str(v if v is not None else ''))[:n]


def plano_txt(p):
    if not p:
        return 'nenhum'
    return 'entrada %s, stop %s, alvo %s, risco/retorno %s, perde $%s no stop, ganha $%s no alvo, motivo do codigo: %s' % (
        limpa(p.get('ent'), 14), limpa(p.get('sl'), 14), limpa(p.get('tp'), 14), limpa(p.get('rr'), 5),
        limpa(p.get('sl_usd'), 9), limpa(p.get('tp_usd'), 9), limpa(p.get('por'), 160))


def register_analise_ia(app):
    from flask import request, jsonify
    kv = KV()
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
        info = {'tipo': ac[0].get('account_type')}
        cache[h] = (time.time(), info)
        return info, None

    def ia(L):
        key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not key:
            return None, 'IA sem chave no servidor'
        pl = L.get('planos') or {}
        sistema = ('Voce e um analista de Smart Money Concepts revisando uma leitura tecnica JA CALCULADA por codigo, para um contrato Multiplicador da Deriv. '
                   'Voce NAO calcula precos: entrada, stop e alvo vem prontos nos planos. Sua tarefa: escolher "compra", "venda" ou "esperar" '
                   '(so pode escolher um plano que exista) e explicar. Seja conservador: estrutura contra o tempo maior, Stoch RSI extremo a favor da entrada, '
                   'risco/retorno abaixo de 1.5, preco longe da zona ou leitura confusa = esperar. Nunca prometa lucro nem fale em certeza. '
                   'Portugues do Brasil, frases curtas. Responda SO com JSON valido, sem markdown.')
        pedido = ('Mercado %s, tempo grafico %s, preco agora %s, ATR %s.\nTempo maior (%s): %s.\nEstrutura recente: %s.\nVarreduras: %s.\n'
                  'Zonas de demanda (abaixo): %s.\nZonas de oferta (acima): %s.\nLiquidez: %s.\nPremium/discount: %s.\nStoch RSI: %s.\nSessao: %s.\n'
                  'PLANO DE COMPRA: %s\nPLANO DE VENDA: %s\n\n'
                  'Formato: {"escolha":"compra|venda|esperar","confianca":0-100,"motivo":"2 a 3 frases","riscos":"1 frase","concordam":["ate 3 itens curtos"]}') % (
            limpa(L.get('nome'), 30), limpa(L.get('tf'), 5), limpa(L.get('px'), 14), limpa(L.get('atr'), 12), limpa(L.get('htf_tf'), 5), limpa(L.get('htf'), 80),
            limpa(L.get('estrutura'), 220), limpa(L.get('varreduras'), 160), limpa(L.get('demanda'), 220), limpa(L.get('oferta'), 220),
            limpa(L.get('liquidez'), 200), limpa(L.get('pd'), 120), limpa(L.get('stoch'), 60), limpa(L.get('sessao'), 80),
            plano_txt(pl.get('compra')), plano_txt(pl.get('venda')))
        body = json.dumps({'model': os.environ.get('ANALISE_IA_MODELO', 'claude-haiku-4-5-20251001'), 'max_tokens': 420, 'system': sistema,
                           'messages': [{'role': 'user', 'content': pedido}]}).encode()
        rq = urllib.request.Request('https://api.anthropic.com/v1/messages', data=body, method='POST',
                                    headers={'Content-Type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01'})
        try:
            with urllib.request.urlopen(rq, timeout=20) as r:
                resp = json.loads(r.read())
            txt = (resp.get('content') or [{}])[0].get('text', '')
            m = re.search(r'\{.*\}', txt, re.S)
            j = json.loads(m.group(0)) if m else {}
        except Exception as e:
            return None, 'IA não respondeu (%s)' % str(e)[:80]
        esc = str(j.get('escolha') or '').lower()
        if esc not in ('compra', 'venda', 'esperar') or (esc != 'esperar' and not pl.get(esc)):
            esc = 'esperar'
        try:
            cf = max(0, min(100, int(float(j.get('confianca') or 0))))
        except Exception:
            cf = 0
        conc = [limpa(x, 40) for x in (j.get('concordam') or []) if isinstance(x, str)][:3]
        return {'escolha': esc, 'confianca': cf, 'motivo': limpa(j.get('motivo'), 420), 'riscos': limpa(j.get('riscos'), 200), 'concordam': conc}, None

    @app.route('/api/analise-ia', methods=['POST'])
    def _aia():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta']).strip()
        dia = datetime.now(BRT).strftime('%Y-%m-%d')
        kq = 'aia:n:%s:%s' % (conta, dia)
        lim = int(os.environ.get('ANALISE_IA_LIMITE', '10'))
        try:
            n = int(kv.get(kq) or 0)
        except Exception:
            n = 0
        if n >= lim:
            return jsonify({'ok': False, 'erro': 'você usou as %d análises de hoje. Amanhã libera de novo.' % lim, 'restam': 0}), 200
        L = d.get('leitura') or {}
        r, erro = ia(L)
        if r is None:
            return jsonify({'ok': False, 'erro': erro, 'restam': lim - n}), 200
        kv.set(kq, str(n + 1), ex=86400 * 2)
        try:
            k = 'aia:sinais'
            S = kv.jget(k, []) or []
            p = (L.get('planos') or {}).get(r['escolha']) or {}
            def fl(v):
                try:
                    return float(v)
                except Exception:
                    return None
            ent, sl, tp, px = fl(p.get('ent')), fl(p.get('sl')), fl(p.get('tp')), fl(L.get('px'))
            ok = r['escolha'] in ('compra', 'venda') and None not in (ent, sl, tp)
            S.insert(0, {'id': '%d%04d' % (int(time.time() * 1000), n), 't': int(time.time()), 'conta': conta[-4:], 'tipo': info.get('tipo'), 'sym': limpa(L.get('sym'), 14),
                         'tf': limpa(L.get('tf'), 5), 'g': TFS.get(limpa(L.get('tf'), 5), 0), 'escolha': r['escolha'], 'dir': (1 if r['escolha'] == 'compra' else -1) if ok else 0,
                         'conf': r['confianca'], 'ent': ent, 'sl': sl, 'tp': tp, 'rr': fl(p.get('rr')), 'px': px, 'dentro': bool(p.get('dentro')),
                         'st': ('and' if p.get('dentro') else 'val') if ok else 'sem'})
            kv.jset(k, S[:500], ex=86400 * 60)
        except Exception:
            pass
        r.update({'ok': True, 'versao': VERSAO, 'restam': lim - n - 1})
        return jsonify(r)

    def conexao():
        tok = kv.get('mesa:tok') or ''
        c = kv.jget('mesa:cfg') or {}
        conta = str(c.get('conta') or '')
        if not tok or not conta:
            for ct in kv.jget('prot:lista', []) or []:
                u = kv.jget('prot:u:' + ct) or {}
                if u.get('tok') and u.get('ligado'):
                    tok, conta = u['tok'], ct
                    break
        return Conexao(tok, conta) if tok and conta else None

    def avanca(s, velas):
        for k in velas:
            if k['t'] + s['g'] <= s['t'] or s['st'] in FIM:
                continue
            d = s['dir']
            if s['st'] == 'val':
                if (k['h'] >= s['tp']) if d > 0 else (k['l'] <= s['tp']):
                    s['st'], s['fim'] = 'inv', k['t']
                    continue
                if (k['l'] <= s['sl']) if d > 0 else (k['h'] >= s['sl']):
                    s['st'], s['fim'] = 'inv', k['t']
                    continue
                if (k['l'] <= s['ent']) if d > 0 else (k['h'] >= s['ent']):
                    s['st'] = 'and'
            if s['st'] == 'and':
                bsl = (k['l'] <= s['sl']) if d > 0 else (k['h'] >= s['sl'])
                btp = (k['h'] >= s['tp']) if d > 0 else (k['l'] <= s['tp'])
                if bsl:                       # vela que toca os dois: conta como stop (o pior caso)
                    s['st'], s['fim'] = 'stp', k['t']
                elif btp:
                    s['st'], s['fim'] = 'alv', k['t']
        if s['st'] == 'val' and time.time() - s['t'] > s['g'] * 60:
            s['st'] = 'exp'

    def confere():
        if not kv.setnx('aia:res:lock', '1', 100):
            return
        S = kv.jget('aia:sinais', []) or []
        abertos = [s for s in S if s.get('dir') and s.get('g') and s.get('st') in ('val', 'and') and time.time() - s['t'] > s['g']]
        if not abertos:
            return
        c = conexao()
        if c is None:
            return
        try:
            grupos = {}
            for s in abertos:
                grupos.setdefault((s['sym'], s['g']), []).append(s)
            for (sym, g), L in grupos.items():
                t0 = min(s['t'] for s in L) - g
                r = c.req({'ticks_history': sym, 'underlying_symbol': sym, 'style': 'candles', 'granularity': g, 'start': int(t0), 'end': 'latest', 'count': 5000}, 20)
                if r.get('error') and 'underlying_symbol' in str(r['error']):
                    r = c.req({'ticks_history': sym, 'style': 'candles', 'granularity': g, 'start': int(t0), 'end': 'latest', 'count': 5000}, 20)
                velas = [{'t': int(q['epoch']), 'h': float(q['high']), 'l': float(q['low'])} for q in (r.get('candles') or [])]
                if velas:
                    for s in L:
                        avanca(s, velas[:-1])          # só velas fechadas
        except Exception as e:
            log('confere', e)
        finally:
            c.fecha()
        novo = {s['id']: s for s in abertos if s.get('id')}
        T = kv.jget('aia:sinais', []) or []              # relê (pode ter chegado sinal novo)
        for i, s in enumerate(T):
            if s.get('id') in novo:
                T[i] = novo[s['id']]
        kv.jset('aia:sinais', T[:500], ex=86400 * 60)

    def laco():
        while True:
            try:
                confere()
            except Exception as e:
                log('laco', e)
            time.sleep(120)
    threading.Thread(target=laco, daemon=True).start()
    app.extensions['aia_confere'] = confere
    app.extensions['aia_kv'] = kv

    @app.route('/api/analise-ia/placar', methods=['GET'])
    def _aia_placar():
        S = [s for s in (kv.jget('aia:sinais', []) or []) if s.get('dir') and time.time() - s.get('t', 0) < 30 * 86400]
        alv = [s for s in S if s.get('st') == 'alv']
        stp = [s for s in S if s.get('st') == 'stp']
        r_sum = round(sum(float(s.get('rr') or 0) for s in alv) - len(stp), 2)
        por = {}
        for s in alv + stp:
            m = por.setdefault(s['sym'], {'alvo': 0, 'stop': 0})
            m['alvo' if s['st'] == 'alv' else 'stop'] += 1
        n = len(alv) + len(stp)
        return jsonify({'ok': True, 'versao': VERSAO, 'resolvidos': n, 'alvo': len(alv), 'stop': len(stp), 'pc': round(len(alv) * 100.0 / n, 1) if n else None,
                        'saldo_r': r_sum, 'em_aberto': len([s for s in S if s.get('st') in ('val', 'and')]), 'invalidados': len([s for s in S if s.get('st') in ('inv', 'exp')]),
                        'por_mercado': por, 'ult': [{'t': s['t'], 'sym': s['sym'], 'tf': s.get('tf'), 'dir': s['dir'], 'rr': s.get('rr'), 'st': s['st']} for s in sorted(alv + stp, key=lambda x: x.get('fim') or x['t'], reverse=True)][:20]})

    log('%s registrada' % VERSAO)
