# -*- coding: utf-8 -*-
"""DOUBLE-LIVE-V1 — Live do Alpha Double: o operador opera no Manual e quem está na sala copia no mesmo instante.

O servidor só repassa: guarda a última entrada do operador e a lista das últimas 30. Cada pessoa compra na própria
conta Deriv, com o próprio valor, gale e stop (a compra é feita pelo navegador dela). A trava de saldo ($10) fica no robô.

Senha do operador: variável de ambiente DOUBLE_LIVE_SENHA (se não existir, usa ADMIN_SENHA).

POST /api/double-live/login     {senha}                 -> {ok}
POST /api/double-live/abrir     {senha, nome, mk}       -> {ok}
POST /api/double-live/fechar    {senha}                 -> {ok}
POST /api/double-live/entrada   {senha, lado, mk, st}   -> {ok, seq}
POST /api/double-live/resultado {senha, ok, d}          -> {ok}
GET  /api/double-live/agora?v=<id>&s=1                  -> {ok, on, nome, mk, n, ult, hist, agora}
"""
import os, json, time, threading, re

VERSAO = 'DOUBLE-LIVE-V1'
K = 'double_live:estado'


def register_double_live(app):
    from flask import request, jsonify
    try:
        from nuvem_digitos import KV
    except Exception:
        from backend.nuvem_digitos import KV   # noqa
    kv = KV()
    trava = threading.Lock()
    mem = {'vis': {}, 'tent': {}}

    def senha_ok(s):
        cert = os.environ.get('DOUBLE_LIVE_SENHA') or os.environ.get('ADMIN_SENHA') or ''
        return bool(cert) and str(s or '') == cert

    def estado():
        e = kv.jget(K, None)
        return e if isinstance(e, dict) else {'on': False, 'nome': '', 'mk': 'R_100', 'seq': 0, 'ult': None, 'hist': []}

    def grava(e):
        kv.set(K, json.dumps(e), ex=86400)

    def ms():
        return int(time.time() * 1000)

    def ip():
        return (request.headers.get('X-Forwarded-For') or request.remote_addr or '?').split(',')[0].strip()

    def corpo():
        d = request.get_json(silent=True) or {}
        # trava simples contra chute de senha: 8 erros por IP a cada 10 min
        t = mem['tent'].get(ip(), [0, 0])
        if time.time() - t[1] > 600:
            t = [0, time.time()]
        if t[0] >= 8:
            return d, 'muitas tentativas: espere 10 minutos'
        if not senha_ok(d.get('senha')):
            mem['tent'][ip()] = [t[0] + 1, t[1]]
            return d, 'senha de operador errada'
        return d, None

    def vistos():
        agora = time.time()
        r = getattr(kv, '_r', None)
        if r is not None:
            try:
                r.zremrangebyscore('double_live:vis', 0, agora - 25)
                return int(r.zcard('double_live:vis'))
            except Exception:
                pass
        for k in [k for k, v in mem['vis'].items() if agora - v > 25]:
            mem['vis'].pop(k, None)
        return len(mem['vis'])

    def marca(vid):
        vid = re.sub(r'[^a-z0-9]', '', str(vid or ''))[:16]
        if not vid:
            return
        r = getattr(kv, '_r', None)
        if r is not None:
            try:
                r.zadd('double_live:vis', {vid: time.time()})
                return
            except Exception:
                pass
        mem['vis'][vid] = time.time()
        if len(mem['vis']) > 20000:
            mem['vis'].clear()

    @app.route('/api/double-live/login', methods=['POST'])
    def _dl_login():
        d, erro = corpo()
        return jsonify({'ok': not erro, 'erro': erro})

    @app.route('/api/double-live/abrir', methods=['POST'])
    def _dl_abrir():
        d, erro = corpo()
        if erro:
            return jsonify({'ok': False, 'erro': erro})
        with trava:
            e = estado()
            e.update({'on': True, 'nome': re.sub(r'[<>"&]', '', str(d.get('nome') or 'Operador'))[:24], 'mk': re.sub(r'[^A-Z0-9_]', '', str(d.get('mk') or 'R_100'))[:10] or 'R_100', 't0': ms()})
            grava(e)
        return jsonify({'ok': True})

    @app.route('/api/double-live/fechar', methods=['POST'])
    def _dl_fechar():
        d, erro = corpo()
        if erro:
            return jsonify({'ok': False, 'erro': erro})
        with trava:
            e = estado()
            e['on'] = False
            grava(e)
        return jsonify({'ok': True})

    @app.route('/api/double-live/entrada', methods=['POST'])
    def _dl_entrada():
        d, erro = corpo()
        if erro:
            return jsonify({'ok': False, 'erro': erro})
        lado = 'par' if d.get('lado') == 'par' else 'impar'
        mk = re.sub(r'[^A-Z0-9_]', '', str(d.get('mk') or 'R_100'))[:10] or 'R_100'
        with trava:
            e = estado()
            if not e.get('on'):
                return jsonify({'ok': False, 'erro': 'abra a live primeiro'})
            e['seq'] = int(e.get('seq') or 0) + 1
            u = {'seq': e['seq'], 'lado': lado, 'mk': mk, 't': ms(), 'ok': None, 'd': None}
            e['ult'] = u
            e['mk'] = mk
            e['hist'] = ([u] + list(e.get('hist') or []))[:30]
            grava(e)
        return jsonify({'ok': True, 'seq': u['seq']})

    @app.route('/api/double-live/resultado', methods=['POST'])
    def _dl_res():
        d, erro = corpo()
        if erro:
            return jsonify({'ok': False, 'erro': erro})
        with trava:
            e = estado()
            h = list(e.get('hist') or [])
            if h:
                h[0]['ok'] = bool(d.get('ok'))
                try:
                    h[0]['d'] = int(d.get('d')) % 10
                except Exception:
                    h[0]['d'] = None
                e['hist'] = h
                if e.get('ult') and e['ult'].get('seq') == h[0].get('seq'):
                    e['ult'] = dict(h[0])
                grava(e)
        return jsonify({'ok': True})

    @app.route('/api/double-live/agora', methods=['GET'])
    def _dl_agora():
        marca(request.args.get('v'))
        e = estado()
        out = {'ok': True, 'versao': VERSAO, 'on': bool(e.get('on')), 'nome': e.get('nome') or '', 'mk': e.get('mk') or 'R_100',
               'n': vistos(), 'ult': e.get('ult'), 'agora': ms()}
        if request.args.get('s'):
            out['hist'] = (e.get('hist') or [])[:15]
        return jsonify(out)
