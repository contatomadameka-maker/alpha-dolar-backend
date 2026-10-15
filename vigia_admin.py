"""VIGIA-ADMIN-V1 — avisos do Alpha Avisos sobre a saude do sistema.
1) Site (PythonAnywhere): o Render confere https://alphadolar.online a cada 5 min. 2 falhas seguidas -> avisa; quando volta -> avisa.
   (Se o proprio Render cair, quem avisa e o e-mail do UptimeRobot.)
2) Robo travado (robos do servidor):
   - esperando o resultado de um contrato ha mais de 6 min (qualquer conta);
   - conta REAL ligada sem operar ha mais de 40 min.
   Junta tudo numa mensagem so e repete no maximo a cada 2 h por robo.
"""
import os
import time
import threading
import urllib.request

SITE = os.environ.get('VIGIA_SITE_URL', 'https://alphadolar.online/')
_ESTADO = {'site_falhas': 0, 'site_fora': False, 'espera': {}, 'avisado': {}}


def _demo(did):
    return str(did).upper().startswith(('DOT', 'VRTC', 'VRW'))


def _site_ok():
    try:
        req = urllib.request.Request(SITE, headers={'User-Agent': 'AlphaVigia/1.0'})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status < 500, 'HTTP %s' % r.status
    except urllib.error.HTTPError as e:
        return e.code < 500, 'HTTP %s' % e.code
    except Exception as e:
        return False, str(e)[:120]


def _checa_site(avisar):
    ok, info = _site_ok()
    if ok:
        if _ESTADO['site_fora']:
            avisar('✅ Site voltou: alphadolar.online está no ar de novo.')
        _ESTADO['site_falhas'] = 0
        _ESTADO['site_fora'] = False
        return
    _ESTADO['site_falhas'] += 1
    if _ESTADO['site_falhas'] >= 2 and not _ESTADO['site_fora']:
        _ESTADO['site_fora'] = True
        avisar('🔴 SITE FORA DO AR\nalphadolar.online não responde há ~10 min (' + info + ').\n👉 Veja o PythonAnywhere: Web → Reload, e o log de erros.')


def _checa_robos(avisar, registro):
    agora = time.time()
    linhas = []
    try:
        itens = list((registro() or {}).items())
    except Exception:
        itens = []
    vivos = set()
    for chave, val in itens:
        try:
            bot = val[0] if isinstance(val, (tuple, list)) else val
            if not getattr(bot, 'is_running', False):
                continue
            vivos.add(chave)
            did, bt = chave
            conta = 'demo' if _demo(did) else 'REAL'
            if getattr(bot, 'waiting_contract', False):
                desde = _ESTADO['espera'].setdefault(chave, agora)
                if agora - desde > 6 * 60:
                    linhas.append((chave, '⏳ %s · %s (%s): esperando resultado de contrato há %d min' % (bt, did, conta, (agora - desde) // 60)))
            else:
                _ESTADO['espera'].pop(chave, None)
                if conta == 'REAL':
                    ult = max(float(getattr(bot, '_ultimo_trade_time', 0) or 0), float(getattr(bot, '_rt_inicio', 0) or 0))
                    if ult and agora - ult > 40 * 60:
                        linhas.append((chave, '💤 %s · %s (REAL): ligado sem operar há %d min' % (bt, did, (agora - ult) // 60)))
        except Exception:
            continue
    for k in list(_ESTADO['espera']):
        if k not in vivos:
            _ESTADO['espera'].pop(k, None)
    novas = [t for k, t in linhas if agora - _ESTADO['avisado'].get(k, 0) > 2 * 3600]
    if novas:
        for k, t in linhas:
            if t in novas:
                _ESTADO['avisado'][k] = agora
        avisar('⚠️ ROBÔ TRAVADO?\n' + '\n'.join(novas[:12]) + ('\n… e mais %d' % (len(novas) - 12) if len(novas) > 12 else '') +
               '\n👉 Confira no admin (Ao vivo). Se precisar, pare e ligue de novo.')


def iniciar_vigia(registro):
    try:
        from telegram_admin import avisar
    except Exception as e:
        print('VIGIA-ADMIN: sem telegram_admin:', e, flush=True)
        return

    def _loop():
        time.sleep(90)  # deixa o servidor terminar de subir
        n = 0
        while True:
            try:
                _checa_robos(avisar, registro)
                if n % 5 == 0:
                    _checa_site(avisar)
            except Exception as e:
                print('VIGIA-ADMIN erro:', e, flush=True)
            n += 1
            time.sleep(60)
    threading.Thread(target=_loop, daemon=True).start()
    print('VIGIA-ADMIN-V1 ativo: site a cada 5 min, robos a cada 1 min', flush=True)
