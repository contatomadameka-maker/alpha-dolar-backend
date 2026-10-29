# -*- coding: utf-8 -*-
"""TRAVA-DIAG-V1 — descobre o que prende o servidor.

Marca a hora de cada pedido que entra. Um vigia, a cada 10 s, vê os pedidos ainda abertos:
se algum passa de 40 s, ou se 10 ou mais estão abertos ao mesmo tempo, grava no log do Render
a pilha de TODAS as threads (no máximo 1 vez a cada 5 min), com o caminho de cada pedido preso.
Também guarda o último relatório no Redis (trava:ult) e mostra em GET /api/diag/trava (X-Admin-Token).
"""
import os, sys, time, threading, traceback

VERSAO = 'TRAVA-DIAG-V1'


def register_trava_diag(app):
    from flask import request, jsonify
    abertos = {}          # thread id -> (inicio, metodo caminho)
    st = {'ult': 0, 'rel': None}
    try:
        from nuvem_digitos import KV
        kv = KV()
    except Exception:
        kv = None

    @app.before_request
    def _td_ini():
        abertos[threading.get_ident()] = (time.time(), '%s %s' % (request.method, request.path))

    @app.teardown_request
    def _td_fim(exc=None):
        abertos.pop(threading.get_ident(), None)

    def relatorio(motivo):
        agora = time.time()
        frames = sys._current_frames()
        nomes = {t.ident: t.name for t in threading.enumerate()}
        L = ['[TravaDiag] ===== %s · %d pedidos abertos =====' % (motivo, len(abertos))]
        for tid, (t0, rota) in sorted(abertos.items(), key=lambda x: x[1][0]):
            L.append('[TravaDiag] PEDIDO %.0fs %s (thread %s)' % (agora - t0, rota, tid))
        for tid, fr in frames.items():
            pilha = ''.join(traceback.format_stack(fr)[-6:])
            rota = abertos.get(tid)
            L.append('[TravaDiag] --- thread %s %s%s\n%s' % (tid, nomes.get(tid, '?'), (' · ' + rota[1]) if rota else '', pilha))
        txt = '\n'.join(L)
        print(txt, flush=True)
        st['rel'] = {'t': int(agora), 'motivo': motivo, 'texto': txt[-20000:]}
        if kv is not None:
            try:
                kv.jset('trava:ult', st['rel'], ex=86400 * 3)
            except Exception:
                pass

    def vigia():
        while True:
            time.sleep(10)
            try:
                agora = time.time()
                velhos = [v for v in list(abertos.values()) if agora - v[0] > 40]
                if (velhos or len(abertos) >= 10) and agora - st['ult'] > 300:
                    st['ult'] = agora
                    relatorio('%d pedido(s) há mais de 40 s' % len(velhos) if velhos else 'muitos pedidos abertos ao mesmo tempo')
            except Exception as e:
                print('[TravaDiag] vigia', e, flush=True)
    threading.Thread(target=vigia, daemon=True, name='trava-diag').start()

    @app.route('/api/diag/trava', methods=['GET'])
    def _td_ver():
        s = os.environ.get('ADMIN_SENHA', '')
        if not s or request.headers.get('X-Admin-Token') != s:
            return jsonify({'ok': False, 'erro': 'senha de admin'}), 403
        rel = st['rel'] or (kv.jget('trava:ult') if kv is not None else None)
        agora = time.time()
        return jsonify({'ok': True, 'versao': VERSAO, 'pid': os.getpid(), 'abertos': [{'s': round(agora - t0), 'rota': r} for t0, r in abertos.values()], 'ultimo': rel})

    print('[TravaDiag] %s registrado (processo %s)' % (VERSAO, os.getpid()), flush=True)
