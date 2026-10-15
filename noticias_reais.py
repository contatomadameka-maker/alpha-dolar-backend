"""NOTICIAS-REAIS-V1 — Analista de Noticias: resultado real das noticias de alto impacto (Apify, ForexFactory com 'actual').
Env: APIFY_TOKEN (obrigatorio), NOTICIAS_MAX_RUNS_DIA (padrao 40), NOTICIAS_TELEGRAM (1 = avisa no Alpha Avisos).
So consulta a Apify logo depois de uma noticia de alto impacto sair (3 tentativas por horario) -> custo baixo.
Rotas: GET /api/mesa-noticias-real (publica: eventos ja divulgados nas ultimas 12h)
       GET /api/admin/noticias-teste?senha=ADMIN_SENHA (roda uma consulta agora e diz quantas noticias vieram)
"""
import os
import json
import time
import threading
import urllib.request
from datetime import datetime, timezone

ACTOR = os.environ.get('NOTICIAS_ACTOR', 'xtracto~forexfactory-calendar')
_REAL = {}
_ST = {'dia': '', 'runs': 0, 'erro': '', 'ult': 0, 'tent': {}, 'avisados': set()}


def _token():
    return os.environ.get('APIFY_TOKEN', '').strip()


def _consulta(dia):
    tk = _token()
    if not tk:
        raise RuntimeError('falta APIFY_TOKEN no Render')
    hoje = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if _ST['dia'] != hoje:
        _ST.update({'dia': hoje, 'runs': 0})
    if _ST['runs'] >= int(os.environ.get('NOTICIAS_MAX_RUNS_DIA', '40')):
        raise RuntimeError('limite de consultas do dia atingido')
    _ST['runs'] += 1
    corpo = json.dumps({'dateRange': 'day', 'day': dia, 'minImpact': 'high', 'upcomingOnly': False, 'maxItems': 60}).encode()
    url = 'https://api.apify.com/v2/acts/%s/run-sync-get-dataset-items?timeout=150' % ACTOR
    rq = urllib.request.Request(url, data=corpo, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tk}, method='POST')
    with urllib.request.urlopen(rq, timeout=170) as r:
        itens = json.loads(r.read().decode('utf-8') or '[]')
    _ST['ult'] = time.time()
    n = 0
    for it in itens if isinstance(itens, list) else []:
        try:
            t = int(it.get('dateline') or 0)
            if not t:
                t = int(datetime.fromisoformat(str(it.get('datetimeISO')).replace('Z', '+00:00')).timestamp())
            ev = {'id': str(it.get('id') or '%s|%s' % (it.get('currency'), t)), 't': t, 'moeda': str(it.get('currency', ''))[:4],
                  'titulo': str(it.get('title', ''))[:80], 'impacto': str(it.get('impact', '')),
                  'atual': it.get('actual'), 'previsao': str(it.get('forecast') or ''), 'anterior': str(it.get('previous') or ''),
                  'bw': int(it.get('actualBetterWorse') or 0)}
            _REAL[ev['id']] = ev
            if ev['atual'] not in (None, ''):
                n += 1
        except Exception:
            continue
    corte = time.time() - 2 * 86400
    for k in [k for k, v in _REAL.items() if v['t'] < corte]:
        _REAL.pop(k, None)
    _ST['erro'] = ''
    return n, len(itens) if isinstance(itens, list) else 0


def _texto(ev):
    efeito = {1: 'mais forte para o ' + ev['moeda'], -1: 'mais fraco para o ' + ev['moeda']}.get(ev['bw'], 'em linha com o esperado')
    return '📰 Saiu %s · %s: %s (previsto %s, anterior %s) → %s' % (
        datetime.fromtimestamp(ev['t'], timezone.utc).strftime('%H:%M UTC'), ev['moeda'] + ' ' + ev['titulo'],
        ev['atual'], ev['previsao'] or '—', ev['anterior'] or '—', efeito)


def _ciclo(app):
    agora = time.time()
    try:  # agenda das noticias (Forex Factory, sem o resultado) - a rota ja existente guarda em cache 30 min
        with app.test_client() as c:
            prog = (c.get('/api/mesa-noticias').get_json(silent=True) or {}).get('eventos') or []
    except Exception:
        prog = []
    pend = []
    for e in prog:
        if e.get('impacto') != 'alto':
            continue
        if not (agora - 40 * 60 <= e['t'] <= agora - 90):
            continue
        ja = any(abs(v['t'] - e['t']) < 120 and v['moeda'] == e.get('moeda') and v['atual'] not in (None, '') for v in _REAL.values())
        if ja:
            continue
        k = '%s|%s' % (e['t'], e.get('moeda'))
        tn = _ST['tent'].get(k, [0, 0])
        if tn[0] >= 3 or agora - tn[1] < 240:
            continue
        pend.append((k, e))
    if pend:
        for k, e in pend:
            tn = _ST['tent'].get(k, [0, 0])
            _ST['tent'][k] = [tn[0] + 1, agora]
        try:
            _consulta(datetime.fromtimestamp(pend[0][1]['t'], timezone.utc).strftime('%Y-%m-%d'))
        except Exception as ex:
            _ST['erro'] = str(ex)[:200]
            print('NOTICIAS-REAIS: consulta falhou:', ex, flush=True)
    if os.environ.get('NOTICIAS_TELEGRAM', '1') == '1':
        try:
            from telegram_admin import avisar
            for v in sorted(_REAL.values(), key=lambda x: x['t']):
                if v['atual'] in (None, '') or v['id'] in _ST['avisados'] or agora - v['t'] > 3 * 3600:
                    continue
                _ST['avisados'].add(v['id'])
                avisar(_texto(v))
        except Exception:
            pass


def register_noticias_reais(app):
    from flask import request, jsonify

    @app.route('/api/mesa-noticias-real', methods=['GET'])
    def _noticias_real():
        ag = time.time()
        ev = [v for v in _REAL.values() if v['atual'] not in (None, '') and ag - 12 * 3600 <= v['t'] <= ag + 60]
        return jsonify({'ok': bool(_token()), 'eventos': sorted(ev, key=lambda x: x['t']), 'erro': _ST['erro'] if _token() else 'falta APIFY_TOKEN',
                        'consultas_hoje': _ST['runs'], 'fonte': 'ForexFactory (resultado real) via Apify'})

    @app.route('/api/admin/noticias-teste', methods=['GET'])
    def _noticias_teste():
        s = os.environ.get('ADMIN_SENHA', '')
        if not s or (request.headers.get('X-Admin-Token') or request.args.get('senha', '')) != s:
            return jsonify({'ok': False, 'erro': 'senha do admin errada'}), 403
        dia = request.args.get('dia') or datetime.now(timezone.utc).strftime('%Y-%m-%d')
        try:
            n, tot = _consulta(dia)
        except Exception as ex:
            return jsonify({'ok': False, 'erro': str(ex)[:300]})
        ex = [v for v in _REAL.values() if datetime.fromtimestamp(v['t'], timezone.utc).strftime('%Y-%m-%d') == dia]
        return jsonify({'ok': True, 'dia': dia, 'noticias_alto_impacto': tot, 'ja_com_resultado': n, 'consultas_hoje': _ST['runs'],
                        'exemplos': [_texto(v) for v in sorted(ex, key=lambda x: x['t']) if v['atual'] not in (None, '')][:6]})

    def _loop():
        time.sleep(100)
        while True:
            try:
                _ciclo(app)
            except Exception as e:
                print('NOTICIAS-REAIS erro:', e, flush=True)
            time.sleep(60)
    threading.Thread(target=_loop, daemon=True).start()
    print('NOTICIAS-REAIS-V1 ativo (token=%s): /api/mesa-noticias-real' % bool(_token()), flush=True)
