"""RESUMO-DIA-V1 — resumo do dia no Alpha Avisos, todo dia as 21h (horario de Brasilia).
Vendas (webhook_log da Cakto), operacoes de conta real (operacoes), markup oficial (MARKUP-AUTO) e custo da IA da Mesa.
Teste/envio manual: GET /api/admin/resumo-hoje?senha=ADMIN_SENHA
"""
import os
import json
import time
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))
HORA = int(os.environ.get('RESUMO_HORA', '21'))
_ENVIADO = {'dia': ''}


def _supa(caminho):
    url, key = os.environ.get('SUPABASE_URL', '').rstrip('/'), os.environ.get('SUPABASE_KEY', '')
    if not url or not key:
        return None
    req = urllib.request.Request(url + '/rest/v1/' + caminho, headers={'apikey': key, 'Authorization': 'Bearer ' + key})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode('utf-8') or '[]')
    except Exception as e:
        print('RESUMO-DIA: supabase falhou', caminho.split('?')[0], e, flush=True)
        return None


def _num(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def _rs(v):
    return ('R$ %.2f' % v).replace('.', ',')


def _us(v):
    return ('US$ %.2f' % v).replace('.', ',')


def montar(app, dia=None):
    agora = datetime.now(BRT)
    d = dia or agora.date()
    ini = datetime(d.year, d.month, d.day, tzinfo=BRT).astimezone(timezone.utc)
    fim = ini + timedelta(days=1)
    fi, ff = urllib.parse.quote(ini.strftime('%Y-%m-%dT%H:%M:%S')), urllib.parse.quote(fim.strftime('%Y-%m-%dT%H:%M:%S'))
    L = ['📊 RESUMO DO DIA · ' + d.strftime('%d/%m/%Y')]

    # vendas
    ws = _supa('webhook_log?select=resultado,produto,payload&origem=eq.cakto&recebido_em=gte.%s&recebido_em=lt.%s&limit=500' % (fi, ff))
    if ws is None:
        L.append('\n💰 Vendas: não consegui ler (tabela webhook_log)')
    else:
        ok = [w for w in ws if str(w.get('resultado')) in ('liberado', 'renovado')]
        tot = 0.0
        for w in ok:
            p = w.get('payload') or {}
            dd = p.get('data') if isinstance(p.get('data'), dict) else p
            tot += _num((dd or {}).get('amount') or (dd or {}).get('baseAmount') or 0)
        pend = [w for w in ws if str(w.get('resultado', '')).startswith(('pendente', 'erro', 'recusado'))]
        reemb = [w for w in ws if str(w.get('resultado')) == 'desligado']
        L.append('\n💰 Vendas: %d (%s)' % (len(ok), _rs(tot)) + (' · novas %d, renovações %d' % (sum(1 for w in ok if w.get('resultado') == 'liberado'), sum(1 for w in ok if w.get('resultado') == 'renovado')) if ok else ''))
        if pend:
            L.append('🟡 Pendentes/erro: %d — confira no admin (Vendas)' % len(pend))
        if reemb:
            L.append('↩️ Reembolsos/chargebacks: %d' % len(reemb))

    # operacoes
    real = _supa('operacoes?select=resultado,lucro,stake,ferramenta,deriv_id&conta=eq.real&criado_em=gte.%s&criado_em=lt.%s&limit=10000' % (fi, ff))
    demo = _supa('operacoes?select=deriv_id&conta=eq.demo&criado_em=gte.%s&criado_em=lt.%s&limit=10000' % (fi, ff))
    if real is None:
        L.append('\n📈 Operações: não consegui ler (tabela operacoes)')
    else:
        g = [o for o in real if o.get('resultado') in ('win', 'won')]
        p = [o for o in real if o.get('resultado') in ('loss', 'lost')]
        res = sum(abs(_num(o.get('lucro'))) for o in g) - sum(abs(_num(o.get('lucro'))) for o in p)
        vol = sum(_num(o.get('stake')) for o in real)
        cli = len({o.get('deriv_id') for o in real if o.get('deriv_id')})
        L.append('\n📈 Conta REAL: %d operações · %d clientes' % (len(real), cli))
        if real:
            L.append('   acerto %d%% · volume %s · resultado dos clientes %s%s' % (round(len(g) / max(1, len(g) + len(p)) * 100), _us(vol), '+' if res >= 0 else '−', _us(abs(res))))
            por = {}
            for o in real:
                por[o.get('ferramenta') or '?'] = por.get(o.get('ferramenta') or '?', 0) + 1
            top = sorted(por.items(), key=lambda x: -x[1])[:4]
            L.append('   mais usadas: ' + ', '.join('%s %d' % t for t in top))
        if demo is not None:
            L.append('🧪 Demo: %d operações · %d contas' % (len(demo), len({o.get('deriv_id') for o in demo if o.get('deriv_id')})))

    # markup e custo da IA (usa as rotas do proprio servidor)
    senha = os.environ.get('ADMIN_SENHA', '')
    try:
        with app.test_client() as c:
            mk = c.get('/api/admin/markup-auto?date_from=%s&date_to=%s' % (d.isoformat(), d.isoformat()), headers={'X-Admin-Token': senha}).get_json(silent=True) or {}
            mu = c.get('/api/admin/mesa-uso', headers={'X-Admin-Token': senha}).get_json(silent=True) or {}
        L.append('\n🏦 Markup Deriv: ' + (_us(_num(mk.get('markup'))) if mk.get('ok') else 'indisponível (' + str(mk.get('erro', ''))[:60] + ')'))
        hoje = [x for x in (mu.get('dias') or []) if x.get('dia') == datetime.now(timezone.utc).strftime('%Y-%m-%d')]
        if hoje:
            L.append('🪑 Mesa IA: %d chamadas · %s' % (hoje[0].get('chamadas', 0), _us(_num(hoje[0].get('custo_usd')))))
        else:
            L.append('🪑 Mesa IA: nenhuma chamada hoje')
    except Exception as e:
        L.append('\n🏦 Markup/IA: erro ao ler (' + str(e)[:60] + ')')
    return '\n'.join(L)


def register_resumo_admin(app):
    from flask import request, jsonify
    try:
        from telegram_admin import avisar, enviar_agora
    except Exception as e:
        print('RESUMO-DIA: sem telegram_admin:', e, flush=True)
        return

    @app.route('/api/admin/resumo-hoje', methods=['GET'])
    def _resumo_hoje():
        senha = os.environ.get('ADMIN_SENHA', '')
        dado = request.headers.get('X-Admin-Token') or request.args.get('senha', '')
        if not senha or dado != senha:
            return jsonify({'ok': False, 'erro': 'senha do admin errada'}), 403
        txt = montar(app)
        ok, erro = enviar_agora(txt)
        return jsonify({'ok': ok, 'erro': erro, 'texto': txt})

    def _loop():
        time.sleep(120)
        while True:
            try:
                ag = datetime.now(BRT)
                dia = ag.strftime('%Y-%m-%d')
                if ag.hour == HORA and ag.minute < 15 and _ENVIADO['dia'] != dia:
                    _ENVIADO['dia'] = dia
                    avisar(montar(app))
            except Exception as e:
                print('RESUMO-DIA erro:', e, flush=True)
            time.sleep(60)
    threading.Thread(target=_loop, daemon=True).start()
    print('RESUMO-DIA-V1 ativo: resumo as %dh (Brasilia) e /api/admin/resumo-hoje' % HORA, flush=True)
