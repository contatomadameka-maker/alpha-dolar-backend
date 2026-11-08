# -*- coding: utf-8 -*-
"""PLANILHA-ALPHA-V1 — planilha de resultados de cada pessoa (todos os robôs), guardada no Redis.

A pessoa prova que é dona pelo token da Deriv do próprio navegador. A chave é o menor id de conta do login
(o mesmo "pessoa" que a Sala de Sinais usa), então o celular e o computador veem a mesma planilha.

Rotas (POST, corpo JSON com "token"):
  /api/planilha/estado   -> {ok, cfg, itens}
  /api/planilha/add      {item}   -> registra um resultado / saque / depósito
  /api/planilha/del      {id}
  /api/planilha/cfg      {cfg}    -> banca inicial (demo/real), meta do mês, cotação manual
"""
import os, json, time, hashlib, uuid, threading
from datetime import datetime, timezone, timedelta

BRT = timezone(timedelta(hours=-3))
MAX_ITENS = 6000


def register_planilha(app):
    from flask import request, jsonify
    try:
        from nuvem_digitos import KV, contas_do_token
    except Exception:
        from backend.nuvem_digitos import KV, contas_do_token   # noqa
    kv = KV()
    cache = {}
    trava = threading.Lock()

    def pessoa(d):
        tok = str(d.get('token') or '').strip()
        if not tok:
            return None, 'entre com a sua conta Deriv'
        h = hashlib.sha256(tok.encode()).hexdigest()
        c = cache.get(h)
        if c and time.time() - c[0] < 900:
            return c[1], None
        try:
            ids = sorted(str(a.get('account_id')) for a in contas_do_token(tok) if a.get('account_id'))
        except PermissionError:
            return None, 'sua sessão na Deriv expirou: entre de novo'
        except Exception as e:
            if c:
                return c[1], None
            return None, 'a Deriv não respondeu agora (%s)' % str(e)[:60]
        if not ids:
            return None, 'nenhuma conta neste login'
        cache[h] = (time.time(), ids[0])
        if len(cache) > 5000:
            cache.clear()
        return ids[0], None

    def le(p):
        return kv.jget('planilha:itens:' + p, []) or [], kv.jget('planilha:cfg:' + p, {}) or {}

    def num(v, d=0.0):
        try:
            return float(str(v).replace(',', '.'))
        except Exception:
            return d

    def limpo(it):
        k = it.get('k') if it.get('k') in ('res', 'saque', 'dep') else 'res'
        v = round(num(it.get('v')), 2)
        if k in ('saque', 'dep'):
            v = abs(v)
        dia = str(it.get('d') or '')[:10]
        try:
            datetime.strptime(dia, '%Y-%m-%d')
        except Exception:
            dia = datetime.now(BRT).strftime('%Y-%m-%d')
        out = {'id': str(it.get('id') or uuid.uuid4().hex[:12])[:40], 'd': dia, 'v': v, 'k': k,
               'r': str(it.get('r') or ('Manual' if k == 'res' else ''))[:40], 'c': 'demo' if it.get('c') == 'demo' else 'real',
               'n': str(it.get('n') or '')[:140], 'a': bool(it.get('a')), 't': int(time.time())}
        for x in ('ops', 'w', 'l'):
            if it.get(x) is not None:
                out[x] = int(num(it.get(x)))
        if it.get('sid'):
            out['sid'] = str(it['sid'])[:60]
        return out

    @app.route('/api/planilha/estado', methods=['POST'])
    def _pl_estado():
        d = request.get_json(silent=True) or {}
        p, err = pessoa(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        itens, cfg = le(p)
        return jsonify({'ok': True, 'cfg': cfg, 'itens': itens})

    @app.route('/api/planilha/add', methods=['POST'])
    def _pl_add():
        d = request.get_json(silent=True) or {}
        p, err = pessoa(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        it = limpo(d.get('item') or {})
        with trava:
            itens, _ = le(p)
            if it.get('sid') and any(x.get('sid') == it['sid'] for x in itens):
                return jsonify({'ok': True, 'repetido': True, 'itens': itens})
            itens.append(it)
            itens = itens[-MAX_ITENS:]
            kv.jset('planilha:itens:' + p, itens)
        return jsonify({'ok': True, 'item': it, 'itens': itens})

    @app.route('/api/planilha/del', methods=['POST'])
    def _pl_del():
        d = request.get_json(silent=True) or {}
        p, err = pessoa(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        with trava:
            itens, _ = le(p)
            itens = [x for x in itens if x.get('id') != str(d.get('id'))]
            kv.jset('planilha:itens:' + p, itens)
        return jsonify({'ok': True, 'itens': itens})

    @app.route('/api/planilha/cfg', methods=['POST'])
    def _pl_cfg():
        d = request.get_json(silent=True) or {}
        p, err = pessoa(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        c = d.get('cfg') or {}
        with trava:
            _, cfg = le(p)
            for k in ('banca_real', 'banca_demo', 'meta_real', 'meta_demo', 'cot'):
                if k in c:
                    cfg[k] = max(0.0, round(num(c[k]), 4))
            kv.jset('planilha:cfg:' + p, cfg)
        return jsonify({'ok': True, 'cfg': cfg})

    @app.route('/api/planilha/zerar', methods=['POST'])
    def _pl_zerar():
        d = request.get_json(silent=True) or {}
        p, err = pessoa(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        c = 'demo' if d.get('c') == 'demo' else 'real'
        with trava:
            itens, _ = le(p)
            kv.jset('planilha:apagados:' + p, [x for x in itens if x.get('c') == c][-MAX_ITENS:], 86400 * 30)   # guarda 30 dias por segurança
            itens = [x for x in itens if x.get('c') != c]
            kv.jset('planilha:itens:' + p, itens)
        return jsonify({'ok': True, 'itens': itens})

    print('🟢 PLANILHA-ALPHA-V1 ativa: /api/planilha/*', flush=True)
