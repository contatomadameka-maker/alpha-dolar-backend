# -*- coding: utf-8 -*-
"""VETOS-V1 — analistas que só BLOQUEIAM (nunca abrem operação). Usados pela Mesa, pelas pendentes da nuvem e pela tela do Alpha Global.

1) Agente Notícias: sem entrada de 30 min antes até 30 min depois de notícia de ALTO impacto da moeda do mercado
   (calendário da Forex Factory, o mesmo da Mesa IA). Ouro, prata e cripto contam como USD. Sintéticos não têm notícia.
2) Agente Correlação: no máximo 1 posição por grupo na mesma direção de risco:
   cripto (BTC/ETH), metais (ouro/prata), dólar (EUR/USD comprado = dólar vendido; USD/JPY comprado = dólar comprado), iene.
O que foi barrado vira sombra na Mesa (marcado com o veto), para medir se barrar ajudou.

  GET /api/vetos/checar?sym=frxXAUUSD[&lado=1]   -> {veto, motivo, noticias:[próximas da moeda]}
  GET /api/vetos/estado                          -> próximas notícias fortes (24 h) + placar das entradas barradas na Mesa
"""
import os, json, time, threading, urllib.request
from datetime import datetime, timezone

VERSAO = 'VETOS-V1'
ANTES, DEPOIS = 30 * 60, 30 * 60
_CAL = {'t': 0, 'd': [], 'erro': ''}
_LK = threading.Lock()
PT = {'Non-Farm Employment Change': 'Payroll', 'CPI m/m': 'Inflação CPI', 'Core CPI m/m': 'Inflação CPI núcleo', 'CPI y/y': 'Inflação CPI anual',
      'Federal Funds Rate': 'Juros do Fed', 'FOMC Statement': 'Comunicado do Fed', 'FOMC Press Conference': 'Coletiva do Fed', 'Unemployment Rate': 'Desemprego',
      'Core PCE Price Index m/m': 'Inflação PCE', 'Advance GDP q/q': 'PIB', 'Retail Sales m/m': 'Vendas no varejo', 'ISM Manufacturing PMI': 'PMI industrial',
      'ISM Services PMI': 'PMI de serviços', 'Main Refinancing Rate': 'Juros do BCE', 'Official Bank Rate': 'Juros do BoE', 'BOJ Policy Rate': 'Juros do BoJ',
      'Unemployment Claims': 'Pedidos de seguro-desemprego', 'JOLTS Job Openings': 'Vagas JOLTS', 'PPI m/m': 'Inflação ao produtor'}


def log(*a):
    print('[Vetos]', *a, flush=True)


def _kv():
    try:
        from nuvem_digitos import KV
        return KV()
    except Exception:
        return None


_K = {'kv': None}


def calendario():
    """eventos de alto impacto desta semana, em UTC (cache 30 min; cópia no Redis para os outros processos)"""
    with _LK:
        if time.time() - _CAL['t'] < 1800 and _CAL['d']:
            return _CAL['d']
        if _K['kv'] is None:
            _K['kv'] = _kv()
        kv = _K['kv']
        try:
            c = kv.jget('vetos:cal') if kv is not None else None
            if c and time.time() - float(c.get('t', 0)) < 1800 and c.get('d'):
                _CAL.update({'t': float(c['t']), 'd': c['d'], 'erro': ''})
                return _CAL['d']
        except Exception:
            pass
        try:
            rq = urllib.request.Request('https://nfs.faireconomy.media/ff_calendar_thisweek.json', headers={'User-Agent': 'Mozilla/5.0 AlphaDolar'})
            with urllib.request.urlopen(rq, timeout=10) as r:
                bruto = json.loads(r.read().decode('utf-8'))
            ev = []
            for e in bruto:
                if str(e.get('impact', '')) != 'High':
                    continue
                try:
                    t = int(datetime.fromisoformat(str(e.get('date'))).astimezone(timezone.utc).timestamp())
                except Exception:
                    continue
                tit = str(e.get('title', ''))[:80]
                ev.append({'t': t, 'moeda': str(e.get('country', '')).upper()[:4], 'titulo': PT.get(tit, tit)})
            ev.sort(key=lambda x: x['t'])
            _CAL.update({'t': time.time(), 'd': ev, 'erro': ''})
            try:
                if kv is not None:
                    kv.jset('vetos:cal', {'t': time.time(), 'd': ev})
            except Exception:
                pass
        except Exception as e:
            _CAL['erro'] = str(e)[:120]
            _CAL['t'] = time.time() - 1500          # tenta de novo em 5 min
            log('calendario', e)
        return _CAL['d']


def moedas(sym):
    s = str(sym or '')
    if s.startswith(('R_', '1HZ', 'BOOM', 'CRASH', 'stp', 'JD', 'RDBEAR', 'RDBULL')):
        return []
    if s.startswith('cry') or s in ('frxXAUUSD', 'frxXAGUSD', 'frxXPTUSD', 'frxXPDUSD'):
        return ['USD']
    if s.startswith('frx') and len(s) >= 9:
        return [s[3:6], s[6:9]]
    if s.startswith('OTC_') or s.startswith('WLD'):
        return ['USD']
    return []


def veto_noticia(sym, agora=None):
    """'' se pode entrar; senão o motivo"""
    ms = moedas(sym)
    if not ms:
        return ''
    agora = agora or time.time()
    for e in calendario():
        if e['moeda'] in ms and e['t'] - ANTES <= agora <= e['t'] + DEPOIS:
            m = int(round((e['t'] - agora) / 60.0))
            quando = ('em %d min' % m) if m > 0 else ('há %d min' % -m if m < 0 else 'agora')
            return 'notícia forte %s (%s %s)' % (quando, e['titulo'], e['moeda'])
    return ''


def proximas(sym, horas=24, agora=None):
    ms = moedas(sym)
    agora = agora or time.time()
    return [e for e in calendario() if (not ms or e['moeda'] in ms) and agora - DEPOIS <= e['t'] <= agora + horas * 3600]


def grupo(sym, lado):
    """(grupo, direção do risco) — duas posições com o mesmo par são a mesma aposta"""
    s, lado = str(sym or ''), (1 if lado > 0 else -1)
    if s.startswith('cry'):
        return ('cripto', lado)
    if s in ('frxXAUUSD', 'frxXAGUSD', 'frxXPTUSD', 'frxXPDUSD'):
        return ('metais', lado)
    if s.startswith('frx') and len(s) >= 9:
        a, b = s[3:6], s[6:9]
        if b == 'USD':
            return ('dólar', -lado)
        if a == 'USD':
            return ('dólar', lado)
        if b == 'JPY':
            return ('iene', -lado)
    return None


NG = {'cripto': 'cripto (BTC/ETH)', 'metais': 'metais (ouro/prata)', 'dólar': 'dólar', 'iene': 'iene'}


def veto_corr(sym, lado, abertas):
    """abertas = [(sym, lado), ...] das posições de verdade já abertas"""
    g = grupo(sym, lado)
    if not g:
        return ''
    for s2, l2 in abertas or []:
        if grupo(s2, l2) == g:
            return 'já tem posição no mesmo grupo (%s %s, mesma direção): seria a mesma aposta dobrada' % (NG.get(g[0], g[0]), str(s2).replace('frx', '').replace('cry', ''))
    return ''


def lado_contrato(ct):
    ct = str(ct or '').upper()
    return 1 if ct in ('MULTUP', 'CALL', 'CALLE') else -1 if ct in ('MULTDOWN', 'PUT', 'PUTE') else 0


def register_vetos(app):
    from flask import request, jsonify

    @app.route('/api/vetos/checar', methods=['GET'])
    def _vt_checar():
        sym = str(request.args.get('sym') or '')[:20]
        m = veto_noticia(sym)
        return jsonify({'ok': True, 'versao': VERSAO, 'veto': bool(m), 'motivo': m,
                        'noticias': [{'t': e['t'], 'moeda': e['moeda'], 'titulo': e['titulo']} for e in proximas(sym, 12)][:6], 'erro': _CAL['erro']})

    @app.route('/api/vetos/estado', methods=['GET'])
    def _vt_estado():
        ops = []
        try:
            import mesa_agentes as M
            if _K.get('mkv') is None:
                _K['mkv'] = M.KV()
            ops = [o for o in _K['mkv'].lista(M.K_OPS, 3000) if o.get('veto')]
        except Exception as e:
            log('estado', e)
        por = {}
        for o in ops:
            k = 'notícia' if str(o['veto']).startswith('notícia') else 'correlação'
            d = por.setdefault(k, {'n': 0, 'pl': 0.0, 'ganhos': 0})
            d['n'] += 1
            d['pl'] = round(d['pl'] + float(o.get('pl') or 0), 2)
            d['ganhos'] += 1 if float(o.get('pl') or 0) > 0 else 0
        return jsonify({'ok': True, 'versao': VERSAO, 'noticias_24h': proximas('', 24), 'barradas': por,
                        'nota': 'barradas = o que teria acontecido nas entradas que os vetos bloquearam (pl negativo = o veto evitou perda)'})

    threading.Thread(target=calendario, daemon=True).start()
    log('%s registrado' % VERSAO)
