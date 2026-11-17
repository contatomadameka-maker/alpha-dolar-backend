# -*- coding: utf-8 -*-
"""NUVEM-DOUBLE-V1 — o automático do Alpha Double rodando NO SERVIDOR (funciona com o celular fechado).

Mesma regra do robô do navegador (bot-double.html V1.6):
- I.A Alpha (lado que saiu em 13+ das últimas 20) OU as estratégias da pessoa (sequência gatilho de até 8 PAR/ÍMPAR -> lado).
- Depois de cada resultado espera o "tempo de análise" e então o padrão; entra no tick em que o padrão completa.
- Gale: exato (recupera + 1 entrada com o pagamento real) ou multiplicador; tentativas por ciclo x ciclos;
  TODO gale espera o padrão da mesma estratégia de novo, contando só os ticks depois da perda (ciclo novo: + pausa).
- Stop win / stop loss em US$ (o navegador já converte % em US$ ao ligar); stop loss é teto real; teto de $10.000 da Deriv.
- Contrato DIGITEVEN / DIGITODD de 1 tick, na conta da pessoa (OTP), um de cada vez.
- Tudo no Redis; só um servidor (o líder) compra; os trabalhadores sobem no processo que atende o site (gunicorn preload).

Rotas (a pessoa prova que é dona da conta mandando o token da Deriv do próprio navegador):
  POST /api/nuvem-double/ligar     {token, conta, cfg}
  POST /api/nuvem-double/desligar  {token, conta}
  POST /api/nuvem-double/estado    {token, conta}
  GET  /api/admin/nuvem-double     (X-Admin-Token)
"""
import os, json, time, math, uuid, threading, atexit, hashlib
from collections import deque

try:
    from nuvem_digitos import KV, Conexao, contas_do_token, digito_saida, log as _log
except Exception:   # pragma: no cover
    from backend.nuvem_digitos import KV, Conexao, contas_do_token, digito_saida, log as _log   # noqa

VERSAO = 'NUVEM-DOUBLE-V1'
MERC = ['R_10', 'R_25', 'R_50', 'R_75', 'R_100', '1HZ10V', '1HZ25V', '1HZ50V', '1HZ75V', '1HZ100V']
WS_URLS = [u for u in [os.environ.get('SALA_WS_URL', '').strip(),
                       'wss://api.derivws.com/trading/v1/options/ws/public',
                       'wss://ws.derivws.com/websockets/v3?app_id=1089'] if u]
P = 'nuvem_dbl:'
K_LISTA, K_LIDER, K_MOTOR = P + 'lista', P + 'lider', P + 'motor'
TICKS = {s: deque(maxlen=400) for s in MERC}   # (epoch, dígito)
EST = {'pausa': False, 'ws': '', 'ticks': 0}


def log(*a):
    try:
        _log('[NuvemDouble]', *a)
    except Exception:
        print('[NuvemDouble]', *a)


def r2(v):
    return round(float(v) + 1e-9, 2)


def ceil2(v):
    return math.ceil(float(v) * 100 - 1e-6) / 100.0


def par(d):
    return 'par' if int(d) % 2 == 0 else 'impar'


# ---------- regras (iguais às do navegador) ----------
def digs(sym, ep=0):
    return [d for (e, d) in list(TICKS.get(sym) or []) if e > ep]


def casa_fim(h, seq):
    for k in range(min(len(seq), len(h)), 0, -1):
        if all(par(h[len(h) - k + j]) == seq[j] for j in range(k)):
            return k
    return 0


def prog(est, sym, ep=0):
    """-> (k, n, lado, ok)"""
    if est.get('id') == 'alpha':
        u = digs(sym)[-20:]
        if len(u) < 20:
            return 0, 13, None, False
        p = sum(1 for d in u if d % 2 == 0)
        m, lado = (p, 'par') if p >= 20 - p else (20 - p, 'impar')
        ok = m >= 13 and (not ep or len(digs(sym, ep)) >= 3)
        return m, 13, lado, ok
    seq = est.get('seq') or []
    k = casa_fim(digs(sym, ep), seq)
    return k, len(seq), est.get('em'), bool(seq) and k >= len(seq)


def nome_est(e):
    if e.get('id') == 'alpha':
        return 'I.A Alpha'
    return e.get('nome') or (''.join('P' if x == 'par' else 'I' for x in e.get('seq') or []) + ' → ' + ('PAR' if e.get('em') == 'par' else 'ÍMPAR'))


def ativas(u):
    if u.get('ia'):
        return [{'id': 'alpha'}]
    return [e for e in (u.get('ests') or []) if e.get('seq')]


class NuvemDouble(object):
    def __init__(self):
        self.kv = KV()
        self.eu = '%d-%s' % (os.getpid(), uuid.uuid4().hex[:6])
        self.pid = None
        self.lider = False
        self.trab = {}
        self.locks = {}
        self.lock = threading.Lock()

    def garante(self):
        """sobe as threads no processo que atende (no gunicorn com preload o import roda no processo mestre)"""
        if self.pid == os.getpid():
            return
        with self.lock:
            if self.pid == os.getpid():
                return
            self.pid = os.getpid()
            self.eu = '%d-%s' % (os.getpid(), uuid.uuid4().hex[:6])
            self.trab = {}
            threading.Thread(target=self.leitor, daemon=True).start()
            threading.Thread(target=self.vigia, daemon=True).start()
            log('threads no processo', self.pid)

    # ---------- estado ----------
    def trava(self, conta):
        with self.lock:
            return self.locks.setdefault(conta, threading.RLock())

    def cfg(self, conta):
        return self.kv.jget(P + 'u:' + conta) or {}

    def salva(self, conta, u):
        self.kv.jset(P + 'u:' + conta, {k: v for k, v in u.items() if k != 'ligado'})

    def ligado(self, conta):
        return self.kv.get(P + 'on:' + conta) == '1'

    def liga(self, conta, on):
        self.kv.set(P + 'on:' + conta, '1' if on else '0')

    def lista(self):
        return self.kv.jget(K_LISTA, []) or []

    def op_log(self, conta, reg):
        k = P + 'ops:' + conta
        L = self.kv.jget(k, []) or []
        L.insert(0, reg)
        self.kv.jset(k, L[:200], ex=86400 * 30)

    def para(self, conta, motivo):
        self.liga(conta, False)
        with self.trava(conta):
            u = self.cfg(conta)
            if u:
                u['parado'] = motivo
                u['t_parou'] = int(time.time())
                u['fase'] = 'parado'
                self.salva(conta, u)
        self.op_log(conta, {'t': int(time.time()), 'aviso': motivo})
        log('%s…%s parado: %s' % (conta[:3], conta[-3:], motivo))

    def sou_lider(self):
        v = self.kv.get(K_LIDER)
        if v == self.eu:
            self.kv.set(K_LIDER, self.eu, ex=20)
            self.lider = True
        elif v in (None, ''):
            self.lider = self.kv.setnx(K_LIDER, self.eu, 20)
        else:
            self.lider = False
        return self.lider

    # ---------- ticks (endpoint público, 10 mercados) ----------
    def leitor(self):
        import websocket
        idx = 0
        while not EST['pausa']:
            if not self.lista():
                time.sleep(5)
                continue
            url = WS_URLS[idx % len(WS_URLS)]
            ws = None
            try:
                ws = websocket.create_connection(url, timeout=15, origin='https://alphadolar.online', header=['User-Agent: Mozilla/5.0 (AlphaDouble nuvem)'])
                mapa = {}
                for i, s in enumerate(MERC):
                    mapa[i + 1] = s
                    ws.send(json.dumps({'ticks': s, 'subscribe': 1, 'req_id': i + 1}))
                ws.settimeout(10)
                EST['ws'] = ''
                ult_ping, sem = time.time(), time.time()
                while not EST['pausa']:
                    if time.time() - ult_ping > 25:
                        ws.send('{"ping": 1}')
                        ult_ping = time.time()
                    if time.time() - sem > 45:
                        raise Exception('nenhum tick em 45 s')
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        raise Exception('conexão fechada')
                    m = json.loads(raw)
                    t = m.get('tick')
                    if not t or t.get('quote') is None:
                        continue
                    sym = t.get('symbol') or t.get('underlying_symbol') or mapa.get(m.get('req_id'))
                    if sym not in TICKS:
                        continue
                    sem = time.time()
                    dec = int(t.get('pip_size') or 2)
                    d = int(('%.*f' % (dec, float(t['quote'])))[-1])
                    TICKS[sym].append((int(t.get('epoch') or time.time()), d))
                    EST['ticks'] += 1
                    if EST['ticks'] % 50 == 0:
                        self.kv.set(K_MOTOR, str(int(time.time())), ex=60)
            except Exception as e:
                EST['ws'] = ('%s -> %s' % (url.split('/')[2], e))[:200]
                idx += 1
                time.sleep(3)
            finally:
                try:
                    if ws:
                        ws.close()
                except Exception:
                    pass

    def vigia(self):
        while not EST['pausa'] and self.pid == os.getpid():
            try:
                if self.sou_lider():
                    for conta in self.lista():
                        t = self.trab.get(conta)
                        if self.ligado(conta) and (t is None or not t.is_alive()):
                            t = threading.Thread(target=self.trabalha, args=(conta,), daemon=True)
                            self.trab[conta] = t
                            t.start()
            except Exception as e:
                log('vigia', e)
            time.sleep(4)

    # ---------- um trabalhador por conta ----------
    def trabalha(self, conta):
        c, ult_ep = None, 0
        while self.ligado(conta) and not EST['pausa'] and self.lider:
            try:
                u = self.cfg(conta)
                if not u:
                    return
                if c is None or c.tok != u.get('tok'):
                    c = Conexao(u.get('tok', ''), conta)
                if u.get('aberto'):                       # contrato que ficou aberto (deploy/queda): confere antes de seguir
                    self.confere(conta, c, u['aberto'])
                    continue
                sym = u.get('sym') or 'R_100'
                T = TICKS.get(sym)
                if not T or T[-1][0] <= ult_ep:
                    time.sleep(0.05)
                    if c and time.time() - c.ult > 20:
                        try:
                            c.req({'ping': 1}, 8)
                        except PermissionError:
                            raise
                        except Exception:
                            pass
                    continue
                ult_ep = T[-1][0]
                self.decide(conta, c, u, sym)
            except PermissionError:
                self.para(conta, 'SUA SESSÃO NA DERIV EXPIROU: abra o Alpha Double e ligue a nuvem de novo')
                return
            except Exception as ex:
                log('trabalha', conta[-3:], ex)
                time.sleep(1.5)

    def decide(self, conta, c, u, sym):
        g = u.get('ciclo')
        agora = time.time()
        if g and g.get('nivel', 0) > 0:
            if g.get('esp') and float(g.get('pausa', 0)) > agora:
                self.fase(conta, u, 'pausa entre ciclos: falta %d s' % math.ceil(float(g['pausa']) - agora))
                return
            es = ativas(u)
            pri = [e for e in es if (e.get('id') or nome_est(e)) == g.get('est')] or es
            for e in pri:
                k, n, lado, ok = prog(e, sym, int(g.get('ep') or 0))
                if ok and lado == g.get('lado'):
                    g['esp'] = False
                    return self.compra(conta, c, u, sym, g['lado'], nome_est(e), e.get('id') or nome_est(e))
            self.fase(conta, u, 'gale %d em %s: esperando o padrão de novo' % (g['nivel'], 'PAR' if g.get('lado') == 'par' else 'ÍMPAR'))
            return
        if agora < float(u.get('prox', 0)):
            self.fase(conta, u, 'analisando as rodadas')
            return
        for e in ativas(u):
            k, n, lado, ok = prog(e, sym, 0)
            if ok and lado:
                return self.compra(conta, c, u, sym, lado, nome_est(e), e.get('id') or nome_est(e))
        self.fase(conta, u, 'esperando o padrão')

    def fase(self, conta, u, txt):
        if u.get('fase') != txt:
            with self.trava(conta):
                v = self.cfg(conta)
                if v:
                    v['fase'] = txt
                    self.salva(conta, v)
            u['fase'] = txt

    def stake(self, u, lado):
        g, b = u.get('ciclo'), float(u.get('E', 1))
        if not g or not g.get('nivel'):
            return r2(max(0.35, b))
        if u.get('M') == 'x':
            pm = float((u.get('pm') or {}).get(lado) or 0.82)
            return max(0.35, ceil2((float(g['perda']) + float(g['base']) * pm) / pm))
        return r2(max(0.35, float(g['ult']) * float(u.get('M') or 2.2)))

    def compra(self, conta, c, u, sym, lado, nome, est_id):
        s = u.setdefault('sessao', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0})
        st = self.stake(u, lado)
        pm = float((u.get('pm') or {}).get(lado) or 0.82)
        L = float(u.get('L') or 0)
        if st * (1 + pm) > 9990:
            return self.para(conta, 'PARADO: a entrada de $%.2f passa do pagamento máximo da Deriv ($10.000)' % st)
        if L > 0 and -s['pl'] + st > L + 1e-9:
            return self.para(conta, 'STOP: a próxima entrada ($%.2f) passaria do seu stop loss ($%.2f) · resultado %s$%.2f' % (st, L, '+' if s['pl'] >= 0 else '−', abs(s['pl'])))
        prm = {'contract_type': 'DIGITEVEN' if lado == 'par' else 'DIGITODD', 'amount': st, 'basis': 'stake',
               'currency': u.get('moeda') or 'USD', 'duration': 1, 'duration_unit': 't'}
        prm[c.symkey] = sym
        r = c.req({'buy': 1, 'price': st, 'parameters': prm}, 10)
        msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error') and ('symbol' in msg.lower() or 'Properties not allowed' in msg or 'validation' in msg.lower()):
            prm.pop(c.symkey, None)
            c.symkey = 'symbol' if c.symkey == 'underlying_symbol' else 'underlying_symbol'
            prm[c.symkey] = sym
            r = c.req({'buy': 1, 'price': st, 'parameters': prm}, 10)
            msg = ((r.get('error') or {}).get('message') or '')
        if r.get('error'):
            u['erros'] = int(u.get('erros', 0)) + 1
            with self.trava(conta):
                v = self.cfg(conta)
                v['erros'] = u['erros']
                self.salva(conta, v)
            self.op_log(conta, {'t': int(time.time()), 'aviso': 'Deriv recusou a entrada: ' + msg[:120]})
            if u['erros'] >= 3 or 'balance' in msg.lower() or 'insufficient' in msg.lower():
                self.para(conta, 'PARADO: a Deriv recusou (%s)' % msg[:90])
            time.sleep(1)
            return
        b = r.get('buy') or {}
        try:
            p = float(b.get('payout')) / float(b.get('buy_price')) - 1
            if 0.3 < p < 1.2:
                u.setdefault('pm', {})[lado] = p
        except Exception:
            pass
        ab = {'cid': b.get('contract_id'), 'st': float(b.get('buy_price') or st), 'lado': lado, 'sym': sym, 'nome': nome, 'est': est_id, 't': int(time.time())}
        with self.trava(conta):
            v = self.cfg(conta)
            v['erros'] = 0
            v['pm'] = u.get('pm') or v.get('pm')
            v['aberto'] = ab
            v['fase'] = 'operação em andamento · %s $%.2f' % ('PAR' if lado == 'par' else 'ÍMPAR', ab['st'])
            if not v.get('ciclo'):
                v['ciclo'] = {'nivel': 0, 'perda': 0.0, 'base': r2(max(0.35, float(v.get('E', 1)))), 'ult': 0.0, 'lado': lado, 'est': est_id, 'esp': False, 'pausa': 0, 'ep': 0}
            self.salva(conta, v)
        self.confere(conta, c, ab)

    def confere(self, conta, c, ab):
        cid = ab.get('cid')
        q, fim = None, time.time() + 90
        time.sleep(1.0)
        while time.time() < fim:
            try:
                rr = c.req({'proposal_open_contract': 1, 'contract_id': cid}, 8)
            except PermissionError:
                raise
            except Exception:
                time.sleep(1)
                continue
            q = rr.get('proposal_open_contract') or {}
            if q.get('is_sold') or q.get('status') in ('won', 'lost', 'sold'):
                break
            q = None
            time.sleep(0.4)
        with self.trava(conta):
            u = self.cfg(conta)
            u.pop('aberto', None)
            if q is None:
                self.salva(conta, u)
                self.op_log(conta, {'t': int(time.time()), 'aviso': 'a Deriv não confirmou o contrato %s em 90 s: confira no histórico da Deriv' % cid})
                self.liga(conta, False)
                u['parado'] = 'PARADO: a Deriv não confirmou um contrato (confira no histórico da Deriv)'
                self.salva(conta, u)
                return
            if not self.kv.setnx(P + 'contou:%s' % cid, '1', 86400 * 3):
                self.salva(conta, u)
                return
            pl = r2(float(q.get('profit') or 0))
            ganhou = pl > 0
            sym = ab.get('sym')
            saiu = digito_saida(q, sym)
            s = u.setdefault('sessao', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0})
            s['n'] += 1
            s['pl'] = r2(s['pl'] + pl)
            g = u.get('ciclo') or {'nivel': 0, 'perda': 0.0, 'base': r2(max(0.35, float(u.get('E', 1)))), 'ult': 0.0, 'lado': ab['lado'], 'est': ab.get('est')}
            T, C = int(u.get('T', 1)), int(u.get('C', 1))
            tot = T * C - 1
            para_cic = False
            if ganhou:
                s['w'] += 1
                tx = 'Gale %d recuperou' % g['nivel'] if g.get('nivel') else 'Vitória'
                u['ciclo'] = None
            elif g.get('nivel', 0) < tot:
                s['l'] += 1
                nv = g['nivel']
                g['nivel'] = nv + 1
                g['perda'] = r2(float(g['perda']) + ab['st'])
                g['ult'] = ab['st']
                g['lado'] = ab['lado']
                g['est'] = ab.get('est')
                g['esp'] = C > 1 and g['nivel'] % T == 0
                pz = int(u.get('P', 0)) if g['esp'] else 0
                g['pausa'] = time.time() + pz
                ult = TICKS.get(sym)
                g['ep'] = (ult[-1][0] if ult else int(time.time())) + pz
                tx = ('Perdeu o gale %d' % nv if nv else 'Perdeu') + (' · ciclo %d perdido, o gale continua no ciclo %d/%d' % (g['nivel'] // T, g['nivel'] // T + 1, C) if g['esp'] else '')
                u['ciclo'] = g
            else:
                s['l'] += 1
                tx = 'Perdeu os %d ciclos' % C if C > 1 else ('Ciclo perdido (todos os gales)' if tot > 0 else 'Perdeu')
                para_cic = tot > 0 and u.get('F') == 'parar'
                u['ciclo'] = None
            u['prox'] = time.time() + float(u.get('A', 5))
            u['fase'] = ('ganhou' if ganhou else 'perdeu') + ' · saiu %s' % ('?' if saiu is None else saiu)
            self.salva(conta, u)
        self.op_log(conta, {'t': int(time.time()), 'sym': sym, 'lado': ab['lado'], 'saiu': saiu, 'stake': ab['st'], 'pl': pl, 'tx': tx, 'nome': ab.get('nome'), 'cid': cid})
        W, L = float(u.get('W') or 0), float(u.get('L') or 0)
        if W > 0 and s['pl'] >= W - 1e-9 and not u.get('ciclo'):
            return self.para(conta, 'META BATIDA: +$%.2f em %d entradas' % (s['pl'], s['n']))
        if L > 0 and -s['pl'] >= L - 1e-9:
            return self.para(conta, 'STOP LOSS de $%.2f atingido · resultado −$%.2f' % (L, abs(s['pl'])))
        if para_cic:
            return self.para(conta, 'PAROU: perdeu %s, como você escolheu · resultado %s$%.2f' % ('os %d ciclos de gale' % C if C > 1 else 'todos os %d gales' % tot, '+' if s['pl'] >= 0 else '−', abs(s['pl'])))


def register_nuvem_double(app):
    from flask import request, jsonify
    nv = NuvemDouble()

    def solta():
        EST['pausa'] = True
        try:
            if nv.kv.get(K_LIDER) == nv.eu:
                nv.kv.set(K_LIDER, '', ex=1)
        except Exception:
            pass
    atexit.register(solta)

    @app.before_request
    def _ndb_garante():
        # barato: só confere o Redis a cada 10 s por processo
        try:
            if nv.pid == os.getpid() or time.time() - getattr(nv, '_chk', 0) < 10:
                return
            nv._chk = time.time()
            if nv.lista():
                nv.garante()
        except Exception:
            pass

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
        info = {'tipo': ac[0].get('account_type'), 'moeda': ac[0].get('currency') or 'USD', 'saldo': ac[0].get('balance')}
        cache[h] = (time.time(), info)
        if len(cache) > 5000:
            cache.clear()
        return info, None

    def num(v, d, lo, hi):
        try:
            return max(lo, min(hi, float(str(v).replace(',', '.'))))
        except Exception:
            return d

    def publico(u):
        return {k: v for k, v in u.items() if k != 'tok'}

    def limpa_ests(L):
        out = []
        for e in (L or [])[:12]:
            seq = [('par' if x == 'par' else 'impar') for x in (e.get('seq') or [])][:8]
            if not seq:
                continue
            out.append({'id': str(e.get('id') or '')[:20], 'nome': str(e.get('nome') or '').replace('<', '').replace('>', '')[:30], 'seq': seq, 'em': 'par' if e.get('em') == 'par' else 'impar'})
        return out

    @app.route('/api/nuvem-double/ligar', methods=['POST'])
    def _ndb_ligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta, cf = str(d['conta']), d.get('cfg') or {}
        u = nv.cfg(conta)
        if nv.ligado(conta) or u.get('aberto'):
            return jsonify({'ok': False, 'erro': 'a nuvem já está ligada nesta conta (desligue antes)'}), 400
        ests = limpa_ests(cf.get('ests'))
        ia = bool(cf.get('ia'))
        if not ia and not ests:
            return jsonify({'ok': False, 'erro': 'ligue a I.A Alpha ou pelo menos uma estratégia'}), 400
        M = cf.get('M') if cf.get('M') in ('x', '2', '2.2', '2.5') else 'x'
        u = {'conta': conta, 'tok': str(d['token']).strip(), 'tipo': info['tipo'], 'moeda': info['moeda'], 'parado': '', 't_lig': int(time.time()),
             'sym': cf.get('sym') if cf.get('sym') in MERC else 'R_100', 'ia': ia, 'ests': ests,
             'E': num(cf.get('E'), 1, 0.35, 5000), 'W': num(cf.get('W'), 0, 0, 1000000), 'L': num(cf.get('L'), 0, 0, 1000000),
             'M': M, 'T': int(num(cf.get('T'), 1, 1, 13)), 'C': int(num(cf.get('C'), 1, 1, 10)), 'P': int(num(cf.get('P'), 0, 0, 600)),
             'F': 'parar' if cf.get('F') == 'parar' else 'reset', 'A': num(cf.get('A'), 5, 0, 30),
             'pm': u.get('pm') or {}, 'erros': 0, 'prox': time.time() + num(cf.get('A'), 5, 0, 30), 'ciclo': None, 'fase': 'ligando',
             'sessao': {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'ini': int(time.time())}}
        nv.salva(conta, u)
        nv.liga(conta, True)
        L = nv.lista()
        if conta not in L:
            L.append(conta)
            nv.kv.jset(K_LISTA, L)
        nv.garante()
        nv.op_log(conta, {'t': int(time.time()), 'aviso': 'NUVEM LIGADA na conta %s · %s · %s · entrada $%.2f · stop win %s · stop loss %s' % (
            info['tipo'].upper(), u['sym'], 'I.A Alpha' if ia else '%d estratégia(s)' % len(ests), u['E'],
            ('$%.2f' % u['W']) if u['W'] else 'sem', ('$%.2f' % u['L']) if u['L'] else 'sem')})
        return jsonify({'ok': True, 'cfg': publico(u)})

    @app.route('/api/nuvem-double/desligar', methods=['POST'])
    def _ndb_desligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        nv.para(conta, 'desligado por você' + (' (o contrato aberto termina normalmente)' if u.get('aberto') else ''))
        return jsonify({'ok': True})

    @app.route('/api/nuvem-double/estado', methods=['POST'])
    def _ndb_estado():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        if u:
            u['ligado'] = nv.ligado(conta)
        mt = float(nv.kv.get(K_MOTOR) or 0)
        return jsonify({'ok': True, 'versao': VERSAO, 'cfg': publico(u) if u else None, 'ops': (nv.kv.jget(P + 'ops:' + conta, []) or [])[:40],
                        'motor': time.time() - mt < 60, 'saldo': info.get('saldo')})

    @app.route('/api/admin/nuvem-double', methods=['GET'])
    def _ndb_admin():
        s = os.environ.get('ADMIN_SENHA', '')
        if not s or request.headers.get('X-Admin-Token') != s:
            return jsonify({'ok': False}), 403
        out = []
        for conta in nv.lista():
            u = nv.cfg(conta)
            out.append({'conta': conta[:3] + '…' + conta[-3:], 'tipo': u.get('tipo'), 'ligado': nv.ligado(conta), 'parado': u.get('parado'), 'fase': u.get('fase'),
                        'sessao': u.get('sessao'), 'sym': u.get('sym')})
        return jsonify({'ok': True, 'versao': VERSAO, 'lider': nv.lider, 'pid': nv.pid, 'ws': EST['ws'], 'ticks': EST['ticks'], 'pessoas': out})

    log('%s registrada' % VERSAO)
    return nv
