"""AGENDA-AVISOS-V1 — painel 🔔 Avisos do admin + agenda pessoal no Alpha Avisos.
Guarda tudo no Redis (REDIS_URL, o mesmo do servidor): sobrevive aos deploys.
Rotas (cabecalho X-Admin-Token = ADMIN_SENHA):
  GET  /api/admin/avisos/status        status do robo, do vigia e historico dos envios
  POST /api/admin/avisos/teste         manda uma mensagem de teste
  POST /api/admin/avisos/resumo        manda o resumo do dia agora
  GET  /api/admin/agenda               lista os compromissos
  POST /api/admin/agenda               cria ou edita {id?, texto, hora 'HH:MM', data 'AAAA-MM-DD', repete nao|diario|semanal, dias [0-6 seg..dom], antes}
  POST /api/admin/agenda/<id>/feito    marca feito hoje (nao lembra mais hoje)
  DELETE /api/admin/agenda/<id>        apaga
Lembra 'antes' minutos antes e na hora; as 7h manda a lista do dia.
"""
import os
import json
import time
import uuid
import threading
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))
MANHA = int(os.environ.get('AGENDA_HORA_MANHA', '7'))
_K = 'alpha:agenda'
_MEM = {}
_ST = {'cache': None, 't': 0}
DIAS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']


def _r():
    try:
        from telegram_admin import _redis
        return _redis()
    except Exception:
        return None


def _todos():
    r = _r()
    if r is not None:
        try:
            return {k: json.loads(v) for k, v in (r.hgetall(_K) or {}).items()}
        except Exception as e:
            print('AGENDA: Redis leitura falhou', e, flush=True)
    return dict(_MEM)


def _salva(it):
    _MEM[it['id']] = it
    r = _r()
    if r is not None:
        try:
            r.hset(_K, it['id'], json.dumps(it, ensure_ascii=False))
        except Exception as e:
            print('AGENDA: Redis gravacao falhou', e, flush=True)


def _apaga(i):
    _MEM.pop(i, None)
    r = _r()
    if r is not None:
        try:
            r.hdel(_K, i)
        except Exception:
            pass


def _hoje():
    return datetime.now(BRT)


def _ocorre(it, d):
    if not it.get('ativo', True):
        return False
    rp = it.get('repete', 'nao')
    if rp == 'diario':
        return True
    if rp == 'semanal':
        return d.weekday() in [int(x) for x in (it.get('dias') or [])]
    return it.get('data') == d.strftime('%Y-%m-%d')


def _quando(it, d):
    h, m = [int(x) for x in str(it.get('hora', '00:00')).split(':')[:2]]
    return datetime(d.year, d.month, d.day, h, m, tzinfo=BRT)


def _desc(it):
    rp = it.get('repete', 'nao')
    if rp == 'diario':
        return 'todo dia'
    if rp == 'semanal':
        return ', '.join(DIAS[int(x)] for x in sorted(it.get('dias') or []))
    try:
        return datetime.strptime(it.get('data', ''), '%Y-%m-%d').strftime('%d/%m')
    except Exception:
        return it.get('data', '')


def _ciclo(avisar):
    ag = _hoje()
    hj = ag.strftime('%Y-%m-%d')
    itens = _todos()
    for it in itens.values():
        if not _ocorre(it, ag) or it.get('feito') == hj:
            continue
        q = _quando(it, ag)
        antes = int(it.get('antes') or 0)
        if antes > 0 and q - timedelta(minutes=antes) <= ag < q and it.get('ult_antes') != hj:
            it['ult_antes'] = hj
            _salva(it)
            avisar('⏰ Daqui a %d min (%s): %s' % (max(1, int((q - ag).total_seconds() // 60)), it['hora'], it['texto']))
        if q <= ag < q + timedelta(minutes=15) and it.get('ult_hora') != hj:
            it['ult_hora'] = hj
            _salva(it)
            avisar('🔔 Agora (%s): %s' % (it['hora'], it['texto']))
    # lista da manha
    if ag.hour == MANHA and ag.minute < 15:
        r = _r()
        marca = None
        try:
            marca = r.get(_K + ':manha') if r is not None else _ST.get('manha')
        except Exception:
            marca = _ST.get('manha')
        if marca != hj:
            hoje = sorted([it for it in itens.values() if _ocorre(it, ag)], key=lambda x: x.get('hora', ''))
            try:
                if r is not None:
                    r.set(_K + ':manha', hj, ex=86400)
            except Exception:
                pass
            _ST['manha'] = hj
            if hoje:
                avisar('📅 Bom dia! Hoje você tem:\n' + '\n'.join('• %s  %s' % (it['hora'], it['texto']) for it in hoje))
    # limpa compromissos unicos com mais de 7 dias
    limite = (ag - timedelta(days=7)).strftime('%Y-%m-%d')
    for it in list(itens.values()):
        if it.get('repete', 'nao') == 'nao' and it.get('data', '9999') < limite:
            _apaga(it['id'])


def register_agenda_admin(app):
    from flask import request, jsonify
    try:
        from telegram_admin import avisar, enviar_agora, historico, configurado
    except Exception as e:
        print('AGENDA: sem telegram_admin novo:', e, flush=True)
        return

    def ok_admin():
        s = os.environ.get('ADMIN_SENHA', '')
        return bool(s) and (request.headers.get('X-Admin-Token') or request.args.get('senha', '')) == s

    def negado():
        return jsonify({'ok': False, 'erro': 'nao autorizado'}), 401

    @app.route('/api/admin/avisos/status', methods=['GET'])
    def _av_status():
        if not ok_admin():
            return negado()
        tok, chat = configurado()
        log, fonte = historico(100)
        vg = {}
        try:
            import vigia_admin
            e = vigia_admin._ESTADO
            vg = {'site_ult': e.get('site_ult'), 'site_ok': e.get('site_ok'), 'site_info': e.get('site_info'), 'site_fora': e.get('site_fora'), 'robos_ult': e.get('robos_ult')}
        except Exception:
            pass
        try:
            import resumo_admin
            hora = resumo_admin.HORA
        except Exception:
            hora = None
        return jsonify({'ok': True, 'token': tok, 'chat': chat, 'vigia': vg, 'resumo_hora': hora, 'manha': MANHA, 'agora': int(time.time()),
                        'redis': _r() is not None, 'fonte_log': fonte, 'log': log})

    @app.route('/api/admin/avisos/teste', methods=['POST'])
    def _av_teste():
        if not ok_admin():
            return negado()
        ok, erro = enviar_agora('✅ Alpha Avisos ligado.\nTeste enviado pelo painel do admin.')
        return jsonify({'ok': ok, 'erro': erro})

    @app.route('/api/admin/avisos/resumo', methods=['POST'])
    def _av_resumo():
        if not ok_admin():
            return negado()
        try:
            import resumo_admin
            txt = resumo_admin.montar(app)
        except Exception as e:
            return jsonify({'ok': False, 'erro': 'resumo indisponivel: %s' % e})
        ok, erro = enviar_agora(txt)
        return jsonify({'ok': ok, 'erro': erro, 'texto': txt})

    @app.route('/api/admin/agenda', methods=['GET', 'POST'])
    def _ag_lista():
        if not ok_admin():
            return negado()
        if request.method == 'POST':
            d = request.get_json(silent=True) or {}
            texto = str(d.get('texto', '')).strip()[:200]
            hora = str(d.get('hora', '')).strip()[:5]
            rp = d.get('repete') if d.get('repete') in ('nao', 'diario', 'semanal') else 'nao'
            try:
                h, m = [int(x) for x in hora.split(':')]
                assert 0 <= h < 24 and 0 <= m < 60
                hora = '%02d:%02d' % (h, m)
            except Exception:
                return jsonify({'ok': False, 'erro': 'hora invalida (use HH:MM)'}), 400
            if not texto:
                return jsonify({'ok': False, 'erro': 'escreva o compromisso'}), 400
            dias = sorted({int(x) for x in (d.get('dias') or []) if str(x).isdigit() and 0 <= int(x) <= 6})
            data = str(d.get('data', '')).strip()[:10]
            if rp == 'nao':
                try:
                    datetime.strptime(data, '%Y-%m-%d')
                except Exception:
                    return jsonify({'ok': False, 'erro': 'escolha o dia'}), 400
            if rp == 'semanal' and not dias:
                return jsonify({'ok': False, 'erro': 'escolha os dias da semana'}), 400
            itens = _todos()
            it = itens.get(str(d.get('id') or '')) or {'id': uuid.uuid4().hex[:10], 'criado': int(time.time())}
            it.update({'texto': texto, 'hora': hora, 'repete': rp, 'dias': dias, 'data': data if rp == 'nao' else '',
                       'antes': max(0, min(1440, int(d.get('antes') or 0))), 'ativo': True})
            it.pop('ult_antes', None); it.pop('ult_hora', None)
            _salva(it)
            return jsonify({'ok': True, 'item': it})
        ag = _hoje()
        out = []
        for it in _todos().values():
            x = dict(it)
            x['quando'] = _desc(it)
            x['hoje'] = _ocorre(it, ag)
            out.append(x)
        out.sort(key=lambda x: (not x['hoje'], x.get('data') or '0', x.get('hora', '')))
        return jsonify({'ok': True, 'itens': out, 'redis': _r() is not None, 'hoje': ag.strftime('%Y-%m-%d')})

    @app.route('/api/admin/agenda/<i>/feito', methods=['POST'])
    def _ag_feito(i):
        if not ok_admin():
            return negado()
        it = _todos().get(i)
        if not it:
            return jsonify({'ok': False, 'erro': 'nao achei'}), 404
        it['feito'] = '' if it.get('feito') == _hoje().strftime('%Y-%m-%d') else _hoje().strftime('%Y-%m-%d')
        _salva(it)
        return jsonify({'ok': True, 'item': it})

    @app.route('/api/admin/agenda/<i>', methods=['DELETE'])
    def _ag_apaga(i):
        if not ok_admin():
            return negado()
        _apaga(i)
        return jsonify({'ok': True})

    def _loop():
        time.sleep(60)
        while True:
            try:
                _ciclo(avisar)
            except Exception as e:
                print('AGENDA erro:', e, flush=True)
            time.sleep(30)
    threading.Thread(target=_loop, daemon=True).start()
    print('AGENDA-AVISOS-V1 ativo: painel /api/admin/avisos/* e agenda (lista as %dh)' % MANHA, flush=True)
