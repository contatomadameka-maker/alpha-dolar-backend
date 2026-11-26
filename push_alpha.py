# -*- coding: utf-8 -*-
"""PUSH-ALPHA-V1 — notificações no celular/PC (Web Push), mesmo com o site fechado.

- Chaves VAPID: do ambiente (VAPID_PRIVATE_PEM) ou geradas UMA vez e guardadas no Redis (push:vapid).
- Inscrições no Redis (hash push:subs): {sub, contas, top, lang, t}. As contas vêm do token da Deriv
  (a pessoa prova que é dona; ninguém recebe o resultado de outra conta).
- Avisos:
    sala      -> Sinais VIP: ATENÇÃO / ENTRADA CONFIRMADA / abortada   (todo mundo que marcou)
    sala_res  -> Sinais VIP: WIN / LOSS do sinal
    fim       -> robô na nuvem parou (meta, stop, sessão expirou, Deriv recusou)   (só o dono da conta)
    res       -> cada operação de um robô na nuvem (lista de robôs que a pessoa marcou)
- Os ganchos embrulham para() e op_log() dos motores nuvem_*.py e post()/edita() da Sala,
  sem mexer neles. Se algo falhar aqui, o robô continua normal.

Rotas:
  GET  /api/push/chave
  POST /api/push/inscrever  {sub, token?, top, lang}
  POST /api/push/sair       {endpoint}
  POST /api/push/testar     {endpoint}
  GET  /api/admin/push      (X-Admin-Token)
"""
import os, re, sys, json, time, base64, hashlib, threading, queue

VERSAO = 'PUSH-ALPHA-V1.3'  # V1.3: aviso da operação mostra o valor da entrada e o gale ·  # V1.2: placar da sessão atualizado (lê a sessão viva do robô) ·  # V1.1: registro dos últimos avisos por aparelho, teste com atraso (app fechado), diagnóstico no Testar
K_SUBS, K_VAPID = 'push:subs', 'push:vapid'
CONTATO = os.environ.get('VAPID_SUB', 'mailto:suporte@alphadolar.online')
# módulo, classe, id, nome, página
ROBOS = [
    ('nuvem_double', 'NuvemDouble', 'double', 'Alpha Double', '/bot-double.html'),
    ('nuvem_clique', 'NuvemClique', 'clique', 'Alpha Clique', '/alpha-clique.html'),
    ('nuvem_clique2', 'NuvemClique2', 'clique2', 'Alpha Clique 2.0', '/bot-clique2.html'),
    ('nuvem_orbita', 'NuvemOrbita', 'orbita', 'Alpha Órbita', '/bot-orbita.html'),
    ('nuvem_visao', 'NuvemVisao', 'visao', 'Alpha Visão', '/bot-visao.html'),
    ('nuvem_pulso', 'NuvemPulso', 'pulso', 'Alpha Pulso', '/bot-pulso.html'),
    ('nuvem_auto', 'NuvemAuto', 'auto', 'Alpha Automação', '/bot-automacao.html'),
    ('nuvem_digitos', 'Nuvem', 'digitos', 'Alpha Sinais VIP (robô)', '/bot-sinais-vip.html'),
]
SALA_URL = '/bot-sinais-vip.html'
EST = {'env': 0, 'ok': 0, 'erro': 0, 'apagadas': 0, 'ult_erro': '', 'ganchos': []}


def log(*a):
    try:
        print('[Push]', *a, flush=True)
    except Exception:
        pass


# ---------------- armazenamento ----------------
class _Mem(object):
    def __init__(self):
        self.h, self.s = {}, {}

    def hset(self, k, f, v):
        self.h.setdefault(k, {})[f] = v

    def hdel(self, k, f):
        self.h.get(k, {}).pop(f, None)

    def hgetall(self, k):
        return dict(self.h.get(k, {}))

    def hget(self, k, f):
        return self.h.get(k, {}).get(f)

    def hlen(self, k):
        return len(self.h.get(k, {}))

    def get(self, k):
        return self.s.get(k)

    def set(self, k, v, nx=False, ex=None):
        if nx and k in self.s:
            return False
        self.s[k] = v
        return True


_DB = {'r': None, 't': 0}


def db():
    if _DB['r'] is not None:
        return _DB['r']
    url = os.environ.get('REDIS_URL', '').strip()
    if url and time.time() - _DB['t'] > 30:
        _DB['t'] = time.time()
        try:
            import redis as _redis
            r = _redis.from_url(url, decode_responses=True, socket_timeout=4)
            r.ping()
            _DB['r'] = r
            return r
        except Exception as e:
            log('Redis indisponivel:', e)
    if not hasattr(db, 'mem'):
        db.mem = _Mem()
    return db.mem


# ---------------- chaves VAPID ----------------
_V = {}


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def vapid():
    if _V.get('v'):
        return _V['v'], _V['pub']
    from py_vapid import Vapid
    from cryptography.hazmat.primitives import serialization
    pem = os.environ.get('VAPID_PRIVATE_PEM', '').replace('\\n', '\n').strip()
    r = db()
    if not pem:
        pem = r.get(K_VAPID)
        if not pem:
            v = Vapid()
            v.generate_keys()
            novo = v.private_pem().decode()
            r.set(K_VAPID, novo, nx=True)
            pem = r.get(K_VAPID) or novo
    v = Vapid.from_pem(pem.encode())
    pub = _b64(v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    _V.update(v=v, pub=pub)
    return v, pub


# ---------------- inscrições ----------------
def sid(endpoint):
    return hashlib.sha1(str(endpoint).encode()).hexdigest()[:20]


_C = {'t': 0, 'L': []}


def todas(fresco=False):
    if not fresco and time.time() - _C['t'] < 20:
        return _C['L']
    L = []
    try:
        for k, v in (db().hgetall(K_SUBS) or {}).items():
            try:
                d = json.loads(v)
                d['_id'] = k
                L.append(d)
            except Exception:
                pass
    except Exception as e:
        log('ler inscricoes:', e)
        return _C['L']
    _C.update(t=time.time(), L=L)
    return L


def apaga(i):
    try:
        db().hdel(K_SUBS, i)
        EST['apagadas'] += 1
        _C['t'] = 0
    except Exception:
        pass


# ---------------- envio ----------------
_Q = queue.Queue(maxsize=5000)
_W = {'pid': None}


def _garante_worker():
    if _W['pid'] == os.getpid():
        return
    _W['pid'] = os.getpid()
    threading.Thread(target=_loop, name='push-alpha', daemon=True).start()


def _ult(d, payload, st):   # V1.1: últimos 8 avisos de cada aparelho (para o diagnóstico do Testar)
    try:
        i = d.get('_id') or sid(d['sub'].get('endpoint'))
        r = db()
        L = json.loads(r.hget('push:ult', i) or '[]') if hasattr(r, 'hget') else []
        L.insert(0, {'t': int(time.time()), 'tit': str(payload.get('t') or '')[:60], 'st': st})
        r.hset('push:ult', i, json.dumps(L[:8], ensure_ascii=False))
    except Exception:
        pass


def _manda(d, payload, ttl, urg):
    st, err = _manda0(d, payload, ttl, urg)
    _ult(d, payload, st)
    return st, err


def _manda0(d, payload, ttl, urg):
    from pywebpush import webpush, WebPushException
    v, _ = vapid()
    try:
        webpush(subscription_info=d['sub'], data=json.dumps(payload, ensure_ascii=False), vapid_private_key=v,
                vapid_claims={'sub': CONTATO}, ttl=ttl, headers={'Urgency': urg}, timeout=10)
        EST['ok'] += 1
        return 201, ''
    except WebPushException as e:
        st = getattr(getattr(e, 'response', None), 'status_code', 0) or 0
        if st in (404, 410):
            apaga(d.get('_id') or sid(d['sub'].get('endpoint')))
        EST['erro'] += 1
        EST['ult_erro'] = ('%s %s' % (st, str(e)))[:200]
        return st or 500, str(e)[:200]
    except Exception as e:
        EST['erro'] += 1
        EST['ult_erro'] = str(e)[:200]
        return 500, str(e)[:200]


def _loop():
    while True:
        try:
            alvos, payload, ttl, urg = _Q.get()
            for d in alvos:
                p = payload
                if d.get('lang') == 'es' and payload.get('es'):
                    p = dict(payload, **payload['es'])
                p = {k: v for k, v in p.items() if k != 'es'}
                _manda(d, p, ttl, urg)
        except Exception as e:
            log('loop:', e)
            time.sleep(1)


def _limpa(txt, n=240):
    t = re.sub(r'<[^>]+>', '', str(txt or ''))
    t = t.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n', t).strip()
    return t[:n]


def _uma_vez(chave, seg=90):
    """o mesmo aviso não sai 2x (vários processos / reenvio)"""
    try:
        return bool(db().set('push:dd:' + hashlib.sha1(chave.encode()).hexdigest()[:24], '1', nx=True, ex=seg))
    except Exception:
        return True


def enfileira(alvos, titulo, corpo, url='/', tag='alpha', ttl=300, urg='normal', es=None):
    if not alvos:
        return 0
    _garante_worker()
    p = {'t': _limpa(titulo, 90), 'b': _limpa(corpo), 'u': url, 'tag': tag, 'ts': int(time.time() * 1000)}
    if es:
        p['es'] = {'t': _limpa(es[0], 90), 'b': _limpa(es[1])}
    try:
        _Q.put_nowait((list(alvos), p, ttl, urg))
        EST['env'] += len(alvos)
    except queue.Full:
        log('fila cheia')
    return len(alvos)


def avisar_conta(conta, tipo, rid, titulo, corpo, url, tag, chave=None, seg=90):
    """tipo: 'fim' (parou) ou 'res' (cada operação) · só para quem é dono da conta"""
    conta = str(conta or '')
    if not conta:
        return 0
    alvos = []
    for d in todas():
        if conta not in (d.get('contas') or []):
            continue
        top = d.get('top') or {}
        if tipo == 'fim' and top.get('fim', True):
            alvos.append(d)
        elif tipo == 'res' and rid in (top.get('res') or []):
            alvos.append(d)
    if not alvos or (chave and not _uma_vez(chave, seg)):   # ninguém inscrito: nem toca no Redis
        return 0
    return enfileira(alvos, titulo, corpo, url, tag, ttl=3600 if tipo == 'fim' else 120, urg='high')


def avisar_sala(tipo, titulo, corpo, tag, chave=None):
    alvos = [d for d in todas() if (d.get('top') or {}).get(tipo)]
    if not alvos or (chave and not _uma_vez(chave)):
        return 0
    es = None
    try:
        from sala_digitos import _es
        es = (_es(titulo), _es(corpo))
    except Exception:
        pass
    return enfileira(alvos, titulo, corpo, SALA_URL, tag, ttl=60 if tipo == 'sala' else 600, urg='high', es=es)


# ---------------- ganchos nos robôs ----------------
def _f2(v):
    try:
        v = float(v)
        return ('+' if v >= 0 else '−') + '$%.2f' % abs(v)
    except Exception:
        return ''


def _gancho_robo(cls, rid, nome, url):
    if getattr(cls, '_push_ok', False):
        return False
    para0, log0 = cls.para, cls.op_log

    def para(self, *a, **k):
        r = para0(self, *a, **k)
        try:
            conta, motivo = a[0], (k.get('motivo') or a[-1])
            m = str(motivo)
            if 'META' in m.upper() or m.startswith('🎯'):
                tit = '🎯 %s · meta batida' % nome
            elif 'MANUAL' in m.upper():
                tit = '📊 %s · resultado' % nome
            else:
                tit = '⛔ %s parou' % nome
            avisar_conta(conta, 'fim', rid, tit, m, url, 'fim-%s' % rid, chave='fim|%s|%s|%s' % (rid, conta, m))
        except Exception as e:
            log('gancho para %s:' % rid, e)
        return r

    def op_log(self, conta, reg, *a, **k):
        r = log0(self, conta, reg, *a, **k)
        try:
            if isinstance(reg, dict) and reg.get('pl') is not None and not reg.get('virt') and not reg.get('aviso'):
                pl = float(reg['pl'])
                ok = pl > 0
                gl = reg.get('g') if reg.get('g') is not None else reg.get('nivel')
                try:
                    gl = int(gl or 0)
                except Exception:
                    gl = 0
                stk = reg.get('stake') if reg.get('stake') is not None else reg.get('st')
                lado = reg.get('tipo') or reg.get('nome') or reg.get('lado') or reg.get('c')
                if rid == 'digitos' and reg.get('lado'):
                    lado = 'PAR' if str(reg['lado']).lower() == 'par' else 'ÍMPAR'
                oque = ' · '.join(str(x) for x in [lado, reg.get('sym') or reg.get('mk'), ('G%d' % gl) if gl else None,
                                                    ('entrada $%.2f' % float(stk)) if stk is not None else None] if x)   # V1.3: valor da entrada e o gale
                tot = ''
                try:
                    # V1.2: o robô guarda a sessão na memória e só grava no Redis depois -> lê a sessão viva de quem chamou
                    s, fl = None, sys._getframe(1).f_locals
                    for k in ('s', 'sess'):
                        if isinstance(fl.get(k), dict) and fl[k].get('pl') is not None:
                            s = fl[k]; break
                    if s is None and isinstance(fl.get('u'), dict):
                        s = fl['u'].get('sess') or fl['u'].get('sessao')
                    if not (isinstance(s, dict) and s.get('pl') is not None):
                        u = self.cfg(conta) if hasattr(self, 'cfg') else None
                        s = (u or {}).get('sess') or (u or {}).get('sessao') or (u or {}).get('s') or {}
                    if isinstance(s, dict) and s.get('pl') is not None:
                        tot = '\nSessão: %s' % _f2(s['pl'])
                        if s.get('w') is not None and s.get('l') is not None:
                            tot += ' · %dW %dL' % (int(s['w']), int(s['l']))
                except Exception:
                    pass
                tit = ('✅ WIN %s' if ok else '❌ LOSS %s') % _f2(pl)
                chave = 'res|%s|%s|%s|%s' % (rid, conta, reg.get('cid') or reg.get('t'), pl)
                avisar_conta(conta, 'res', rid, tit + ' · ' + nome, (oque + tot).strip(), url, 'res-%s' % rid, chave=chave, seg=300)
        except Exception as e:
            log('gancho op_log %s:' % rid, e)
        return r

    cls.para, cls.op_log, cls._push_ok = para, op_log, True
    return True


def _gancho_sala(cls):
    if getattr(cls, '_push_ok', False):
        return False
    post0, edita0 = cls.post, cls.edita

    def _parte(texto):
        t = _limpa(texto, 600)
        L = [x for x in t.split('\n') if x.strip()]
        return (L[0] if L else 'Sinais VIP'), '\n'.join(L[1:4])

    def post(self, chave, texto, img=None, *a, **k):
        r = post0(self, chave, texto, img, *a, **k)
        try:
            if img in ('atencao', 'confirmada'):
                tit, corpo = _parte(texto)
                avisar_sala('sala', tit, corpo, 'sala', chave='sala|%s|%s' % (chave, img))
        except Exception as e:
            log('gancho sala post:', e)
        return r

    def edita(self, chave, texto, img=None, *a, **k):
        r = edita0(self, chave, texto, img, *a, **k)
        try:
            if img in ('gain', 'loss', 'abortada'):
                tit, corpo = _parte(texto)
                avisar_sala('sala' if img == 'abortada' else 'sala_res', tit, corpo, 'sala', chave='salar|%s|%s' % (chave, img))
        except Exception as e:
            log('gancho sala edita:', e)
        return r

    cls.post, cls.edita, cls._push_ok = post, edita, True
    return True


def instala_ganchos():
    feitos = []
    for (mod, cn, rid, nome, url) in ROBOS:
        for mn in (mod, 'backend.' + mod):
            m = sys.modules.get(mn)
            cls = getattr(m, cn, None) if m else None
            if cls is not None and hasattr(cls, 'para') and hasattr(cls, 'op_log'):
                if _gancho_robo(cls, rid, nome, url):
                    feitos.append(rid)
    for mn in ('sala_digitos', 'backend.sala_digitos'):
        m = sys.modules.get(mn)
        cls = getattr(m, 'Sala', None) if m else None
        if cls is not None and _gancho_sala(cls):
            feitos.append('sala')
    EST['ganchos'] = sorted(set(EST['ganchos'] + feitos))
    log('ganchos:', ', '.join(EST['ganchos']) or 'nenhum')
    return feitos


# ---------------- rotas ----------------
def register_push(app):
    from flask import request, jsonify

    @app.route('/api/push/chave', methods=['GET'])
    def _push_chave():
        try:
            _, pub = vapid()
            return jsonify({'ok': True, 'chave': pub, 'versao': VERSAO,
                            'robos': [{'id': r[2], 'nome': r[3]} for r in ROBOS]})
        except Exception as e:
            return jsonify({'ok': False, 'erro': 'push indisponível: %s' % str(e)[:120]}), 503

    @app.route('/api/push/inscrever', methods=['POST'])
    def _push_inscrever():
        d = request.get_json(silent=True) or {}
        sub = d.get('sub') or {}
        ep = str(sub.get('endpoint') or '')
        keys = sub.get('keys') or {}
        if not ep.startswith('https://') or not keys.get('p256dh') or not keys.get('auth') or len(ep) > 1000:
            return jsonify({'ok': False, 'erro': 'inscrição inválida'}), 400
        t = d.get('top') or {}
        ids = set(r[2] for r in ROBOS)
        top = {'sala': bool(t.get('sala')), 'sala_res': bool(t.get('sala_res')), 'fim': bool(t.get('fim', True)),
               'res': [x for x in (t.get('res') or []) if x in ids][:20]}
        contas = []
        tok = str(d.get('token') or '').strip()
        if tok:
            try:
                from nuvem_digitos import contas_do_token
            except Exception:
                from backend.nuvem_digitos import contas_do_token   # noqa
            try:
                contas = [str(a.get('account_id')) for a in contas_do_token(tok) if a.get('account_id')]
            except PermissionError:
                return jsonify({'ok': False, 'erro': 'sua sessão na Deriv expirou: entre de novo'}), 401
            except Exception as e:
                return jsonify({'ok': False, 'erro': 'Deriv não respondeu (%s)' % str(e)[:60]}), 502
        i = sid(ep)
        reg = {'sub': {'endpoint': ep, 'keys': {'p256dh': str(keys['p256dh']), 'auth': str(keys['auth'])}},
               'contas': contas[:20], 'top': top, 'lang': 'es' if str(d.get('lang') or '').startswith('es') else 'pt',
               't': int(time.time()), 'ua': str(request.headers.get('User-Agent', ''))[:120]}
        db().hset(K_SUBS, i, json.dumps(reg, ensure_ascii=False))
        _C['t'] = 0
        return jsonify({'ok': True, 'id': i, 'contas': len(contas), 'top': top})

    @app.route('/api/push/sair', methods=['POST'])
    def _push_sair():
        d = request.get_json(silent=True) or {}
        apaga(sid(d.get('endpoint') or ''))
        return jsonify({'ok': True})

    @app.route('/api/push/testar', methods=['POST'])
    def _push_testar():
        d = request.get_json(silent=True) or {}
        i = sid(d.get('endpoint') or '')
        raw = db().hgetall(K_SUBS).get(i)
        if not raw:
            return jsonify({'ok': False, 'erro': 'este aparelho não está inscrito'}), 404
        s = json.loads(raw)
        s['_id'] = i
        es = s.get('lang') == 'es'
        try:
            atraso = max(0, min(60, int(d.get('atraso') or 0)))
        except Exception:
            atraso = 0
        p = {'t': '🔔 Alpha Dolar', 'b': ('¡Listo! Los avisos llegan a este dispositivo.' if es else
                                          'Pronto! Os avisos chegam neste aparelho.'), 'u': '/', 'tag': 'teste', 'ts': int(time.time() * 1000)}
        try:
            ult = json.loads(db().hget('push:ult', i) or '[]')
        except Exception:
            ult = []
        diag = {'contas': len(s.get('contas') or []), 'top': s.get('top'), 'ganchos': EST['ganchos'], 'ult': ult[:6], 'versao': VERSAO}
        if atraso:
            threading.Timer(atraso, lambda: _manda(s, dict(p, ts=int(time.time() * 1000)), 300, 'high')).start()
            return jsonify({'ok': True, 'status': 0, 'atraso': atraso, 'diag': diag})
        st, err = _manda(s, p, 120, 'high')
        return jsonify({'ok': st in (200, 201), 'status': st, 'erro': err, 'diag': diag})

    @app.route('/api/admin/push', methods=['GET'])
    def _push_admin():
        s = os.environ.get('ADMIN_SENHA', '')
        if not s or request.headers.get('X-Admin-Token') != s:
            return jsonify({'ok': False}), 403
        L = todas(True)
        c = {'total': len(L), 'com_conta': 0, 'sala': 0, 'sala_res': 0, 'fim': 0, 'res': {}}
        for d in L:
            t = d.get('top') or {}
            c['com_conta'] += 1 if d.get('contas') else 0
            for k in ('sala', 'sala_res', 'fim'):
                c[k] += 1 if t.get(k) else 0
            for r in t.get('res') or []:
                c['res'][r] = c['res'].get(r, 0) + 1
        return jsonify({'ok': True, 'versao': VERSAO, 'inscritos': c, 'envio': EST})

    instala_ganchos()
