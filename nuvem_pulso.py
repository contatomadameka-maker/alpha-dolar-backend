# -*- coding: utf-8 -*-
"""NUVEM-PULSO-V1 — o Alpha Pulso rodando NO SERVIDOR (funciona com o celular fechado).

Mesmas regras da página (bot-pulso.html):
- Contrato Par/Ímpar, Acima 4/Abaixo 5, Sobe/Desce ou Misto (1 tick); leitura Segue / Inverte / Maioria dos 10 / Alterna; lado fixo do Ajustes.
- Intervalo entre ciclos; Confirmar antes de entrar (N do outro lado, só depois do último contrato).
- Gestão Fixa / Recuperar 1 vez / Recuperação livre / Martingale (× até N gales) com CICLOS DE GALE (1–10, pausa, resetar/parar);
  ciclo novo espera no mínimo 2 do outro lado.
- Meta, limite de perda (nunca passa), número de ciclos, tempo de sessão, pausa de 60 s depois de N perdas, proteção de lucro (60% da meta).
Rotas: POST /api/nuvem-pulso/ligar|desligar|estado {token, conta[, cfg]} · GET /api/admin/nuvem-pulso (X-Admin-Token)
"""
import os, json, time, math, uuid, random, threading, atexit, hashlib
from collections import deque

try:
    from nuvem_digitos import KV, Conexao, contas_do_token, digito_saida, log as _log
except Exception:   # pragma: no cover
    from backend.nuvem_digitos import KV, Conexao, contas_do_token, digito_saida, log as _log   # noqa

VERSAO = 'NUVEM-PULSO-V1.1'
MERC = ['R_10', 'R_25', 'R_50', 'R_75', 'R_100', '1HZ10V', '1HZ25V', '1HZ50V', '1HZ75V', '1HZ100V']
WS_URLS = [u for u in [os.environ.get('SALA_WS_URL', '').strip(),
                       'wss://api.derivws.com/trading/v1/options/ws/public',
                       'wss://ws.derivws.com/websockets/v3?app_id=1089'] if u]
P = 'nuvem_pls:'
K_LISTA, K_LIDER, K_MOTOR = P + 'lista', P + 'lider', P + 'motor'
TICKS = {s: deque(maxlen=200) for s in MERC}   # (epoch, dígito, subiu 0/1/None)
ULTQ = {}
EST = {'pausa': False, 'ws': '', 'ticks': 0}
LADOS = {'EVEN': ('DIGITEVEN', None, 'PAR'), 'ODD': ('DIGITODD', None, 'ÍMPAR'), 'OVER': ('DIGITOVER', '4', 'ACIMA DE 4'),
         'UNDER': ('DIGITUNDER', '5', 'ABAIXO DE 5'), 'RISE': ('CALL', None, 'SOBE'), 'FALL': ('PUT', None, 'DESCE')}
OPP = {'EVEN': 'ODD', 'ODD': 'EVEN', 'OVER': 'UNDER', 'UNDER': 'OVER', 'RISE': 'FALL', 'FALL': 'RISE'}
FAMS = ['pi', 'ou', 'rf']


def log(*a):
    try:
        _log('[NuvemPulso]', *a)
    except Exception:
        print('[NuvemPulso]', *a)


def r2(v):
    return round(float(v) + 1e-9, 2)


def ceil2(v):
    return math.ceil(float(v) * 100 - 1e-6) / 100.0


def ganha_lado(l, d, up):
    """o resultado (dígito / subiu) faria esse lado ganhar?"""
    if l == 'EVEN':
        return d % 2 == 0
    if l == 'ODD':
        return d % 2 == 1
    if l == 'OVER':
        return d > 4
    if l == 'UNDER':
        return d < 5
    if l == 'RISE':
        return up == 1
    if l == 'FALL':
        return up == 0
    return False


def fam_de(l):
    return 'pi' if l in ('EVEN', 'ODD') else 'ou' if l in ('OVER', 'UNDER') else 'rf'


def leitura(u, sym):
    """o lado da vez, igual à página (Segue / Inverte / Maioria dos 10 / Alterna) — ou o lado fixo do usuário"""
    if u.get('lado') in LADOS:
        return u['lado']
    L = list(TICKS.get(sym) or [])
    if len(L) < 2:
        return None
    fam = u.get('ct') or 'pi'
    if fam == 'mix':
        fam = FAMS[int(u.get('mixI', 0)) % 3]
    e, d, up = L[-1]
    if fam == 'pi':
        t = 'EVEN' if d % 2 == 0 else 'ODD'
    elif fam == 'ou':
        t = 'OVER' if d > 4 else 'UNDER'
    else:
        if up is None:
            return None
        t = 'RISE' if up == 1 else 'FALL'
    le = u.get('le') or 'segue'
    if le == 'segue':
        return t
    if le == 'inverte':
        return OPP[t]
    if le == 'alterna':
        ult = u.get('ult')
        return OPP[ult] if ult and fam_de(ult) == fam else t
    base = 'EVEN' if fam == 'pi' else 'OVER' if fam == 'ou' else 'RISE'
    o = r = 0
    for (e2, d2, up2) in L[-10:]:
        if fam == 'rf' and up2 is None:
            continue
        if ganha_lado(base, d2, up2):
            o += 1
        else:
            r += 1
    if o == r:
        return t
    return base if o > r else OPP[base]


def seguidos_contra(l, sym, ep=0):
    """quantos resultados seguidos que fariam o lado l PERDER (só os depois de ep) — o Confirmar antes de entrar"""
    n = 0
    for (e, d, up) in reversed(list(TICKS.get(sym) or [])):
        if ep and e <= ep:
            break
        if l in ('RISE', 'FALL') and up is None:
            break
        if not ganha_lado(l, d, up):
            n += 1
        else:
            break
    return n


# ═══ EXTRATO-NUVEM-V1: cada contrato da nuvem entra na tabela operacoes (Extrato e "Ao vivo" do admin) ═══
def _extrato(conta, tipo, cid, sym, stake, pl, ferr, nome_feed, tp):
    def vai():
        try:
            from nuvem_digitos import _nop_cliente, _nop_pct, _nop_supa
        except Exception:
            from backend.nuvem_digitos import _nop_cliente, _nop_pct, _nop_supa   # noqa
        for i in range(3):
            try:
                cli = _nop_cliente(conta)
                bot = cli.get('bot_name') or 'sem bot'
                real = str(tipo) == 'real'
                st, lu = r2(float(stake or 0)), r2(float(pl or 0))
                L = {'contract_id': str(cid), 'deriv_id': conta, 'cliente_id': cli.get('id'), 'bot_name': bot, 'ferramenta': ferr,
                     'conta': 'real' if real else 'demo', 'stake': st, 'lucro': lu, 'resultado': 'won' if lu > 0 else 'lost',
                     'symbol': str(sym or '')[:30], 'tipo': str(tp or '')[:30],
                     'markup_usd': round(st * _nop_pct(bot) / 100, 4) if real else 0}
                _nop_supa('operacoes?on_conflict=contract_id', 'POST', [L], {'Prefer': 'resolution=ignore-duplicates,return=minimal'})
                if real and lu > 0:
                    try:
                        import sys as _sys
                        for mn in ('alpha_bot_api_production', '__main__'):
                            fr = getattr(_sys.modules.get(mn), '_feed_registrar', None)
                            if fr:
                                fr(conta, '', nome_feed, L['symbol'], lu, st, 'real', L['contract_id'])
                                break
                    except Exception as e:
                        log('extrato feed', str(e)[:100])
                return
            except Exception as e:
                log('extrato grava', str(e)[:150])
                time.sleep(3 + i * 5)
    if cid:
        threading.Thread(target=vai, daemon=True).start()

class NuvemPulso(object):
    def __init__(self):
        self.kv = KV()
        self.eu = '%d-%s' % (os.getpid(), uuid.uuid4().hex[:6])
        self.pid = None
        self.lider = False
        self.trab = {}
        self.locks = {}
        self.lock = threading.Lock()

    def garante(self):
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
                ws = websocket.create_connection(url, timeout=15, origin='https://alphadolar.online', header=['User-Agent: Mozilla/5.0 (AlphaPulso nuvem)'])
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
                    q = float(t['quote'])
                    dec = int(t.get('pip_size') or 2)
                    d = int(('%.*f' % (dec, q))[-1])
                    up = None if sym not in ULTQ else (1 if q > ULTQ[sym] else 0)
                    ULTQ[sym] = q
                    TICKS[sym].append((int(t.get('epoch') or time.time()), d, up))
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

    def fase(self, conta, u, txt):
        if u.get('fase') != txt:
            with self.trava(conta):
                v = self.cfg(conta)
                if v:
                    v['fase'] = txt
                    self.salva(conta, v)
            u['fase'] = txt

    def trabalha(self, conta):
        c, ult_ep = None, 0
        while self.ligado(conta) and not EST['pausa'] and self.lider:
            try:
                u = self.cfg(conta)
                if not u:
                    return
                if c is None or c.tok != u.get('tok'):
                    c = Conexao(u.get('tok', ''), conta)
                if u.get('aberto'):
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
                self.para(conta, 'SUA SESSÃO NA DERIV EXPIROU: abra o Alpha Pulso e ligue a nuvem de novo')
                return
            except Exception as ex:
                log('trabalha', conta[-3:], ex)
                time.sleep(1.5)

    # ---------- gestão (igual à página) ----------
    def nome_g(self, u, gs):   # V1.1: com ciclos, o nível vira "gale k do ciclo c" (antes aparecia "gale 4" no ciclo 2)
        T, C = int(u.get('gal', 3)) + 1, int(u.get('cic', 1))
        if C > 1:
            c, k = gs // T + 1, gs % T
            return ('entrada do ciclo %d' % c) if k == 0 else ('gale %d do ciclo %d' % (k, c))
        return 'gale %d' % gs

    def tot(self, u):
        C, gal = int(u.get('cic', 1)), int(u.get('gal', 3))
        return (gal + 1) * C - 1 if C > 1 else gal

    def base(self, u):
        return r2(max(0.35, float(u.get('E', 1))))

    def stake(self, u, lado):
        s = u['sessao']
        e = self.base(u)
        ger = u.get('ger')
        if ger == 'mult':
            gs = int(s.get('gs', 0))
            return r2(e * math.pow(float(u.get('mul', 2.3)), gs)) if 0 < gs <= self.tot(u) else e
        if ger in ('rec1', 'livre') and float(s.get('rec', 0)) > 0:
            k = float((u.get('pm') or {}).get(LADOS[lado][0]) or 0.85)
            return r2(max(e, (float(s['rec']) + e * k) / k))
        return e

    def decide(self, conta, c, u, sym):
        s = u['sessao']
        agora = time.time()
        if agora - float(s.get('ini', agora)) > 60 * float(u.get('maxT', 20)):
            return self.para(conta, 'TEMPO DE SESSÃO: rodou os %d minutos combinados · resultado %s' % (int(u.get('maxT', 20)), sinal(s['pl'])))
        if agora < float(u.get('pausa_ate', 0)):
            return self.fase(conta, u, '%s: falta %d s' % (u.get('pausa_txt') or 'pausa de segurança', math.ceil(float(u['pausa_ate']) - agora)))
        if agora < float(u.get('prox', 0)):
            return self.fase(conta, u, 'próximo ciclo em %d s' % math.ceil(float(u['prox']) - agora))
        lado = leitura(u, sym)
        if not lado:
            return
        conf = int(u.get('conf', 0))
        if s.get('cic_novo'):   # ciclo de gale novo: lê o mercado de novo (no mínimo 2 ticks depois da perda) antes de entrar
            ep = int(u.get('saida_ep') or 0)
            novos = sum(1 for x in list(TICKS.get(sym) or []) if x[0] > ep)
            if novos < 2:
                return self.fase(conta, u, 'ciclo novo: lendo o mercado de novo (%d/2)' % novos)
        if conf:
            k = seguidos_contra(lado, sym, int(u.get('saida_ep') or 0))
            if k < conf:
                return self.fase(conta, u, 'confirmando %s: esperando %d do outro lado (%d/%d)' % (LADOS[lado][2], conf, min(k, conf), conf))
        return self.compra(conta, c, u, sym, lado)

    def compra(self, conta, c, u, sym, lado):
        s = u['sessao']
        st = self.stake(u, lado)
        stop = float(u.get('stop') or 0)
        if max(0.0, -s['pl']) + st > stop + 1e-9:
            if s.get('rec') or s.get('gs'):
                s['rec'] = 0
                s['gs'] = 0
                st = self.base(u)
                self.op_log(conta, {'t': int(time.time()), 'aviso': 'A próxima recuperação passaria do limite de perda: voltou para a entrada inicial.'})
            if max(0.0, -s['pl']) + st > stop + 1e-9:
                return self.para(conta, 'LIMITE DE PERDA PROTEGIDO: a próxima entrada ($%.2f) passaria do limite de $%.2f · resultado %s' % (st, stop, sinal(s['pl'])))
        ct, bar, nome = LADOS[lado]
        prm = {'contract_type': ct, 'amount': st, 'basis': 'stake', 'currency': u.get('moeda') or 'USD', 'duration': 1, 'duration_unit': 't'}
        if bar is not None:
            prm['barrier'] = bar
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
            u['prox'] = time.time() + 3
            with self.trava(conta):
                v = self.cfg(conta)
                v['erros'], v['prox'] = u['erros'], u['prox']
                self.salva(conta, v)
            self.op_log(conta, {'t': int(time.time()), 'aviso': 'Deriv recusou a entrada (%s): %s' % (nome, msg[:120])})
            if u['erros'] >= 5 or 'balance' in msg.lower() or 'insufficient' in msg.lower():
                self.para(conta, 'PARADO: a Deriv recusou (%s)' % msg[:90])
            return
        b = r.get('buy') or {}
        try:
            p = float(b.get('payout')) / float(b.get('buy_price')) - 1
            if 0.05 < p < 1.5:
                u.setdefault('pm', {})[ct] = p
        except Exception:
            pass
        ab = {'cid': b.get('contract_id'), 'st': float(b.get('buy_price') or st), 'lado': lado, 'sym': sym, 't': int(time.time()), 'n': int(s.get('c', 0)) + 1}
        with self.trava(conta):
            v = self.cfg(conta)
            v['erros'] = 0
            v['pm'] = u.get('pm') or v.get('pm')
            v['aberto'] = ab
            v['ult'] = lado
            if (v.get('ct') or 'pi') == 'mix':
                v['mixI'] = int(v.get('mixI', 0)) + 1
            v.setdefault('sessao', {})['cic_novo'] = False
            v['fase'] = 'ciclo %d · %s · $%.2f' % (ab['n'], nome, ab['st'])
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
        parar = None
        with self.trava(conta):
            u = self.cfg(conta)
            u.pop('aberto', None)
            if q is None:
                self.liga(conta, False)
                u['parado'] = 'PARADO: a Deriv não confirmou um contrato (confira no histórico da Deriv)'
                self.salva(conta, u)
                self.op_log(conta, {'t': int(time.time()), 'aviso': 'a Deriv não confirmou o contrato %s em 90 s: confira no histórico da Deriv' % cid})
                return
            if not self.kv.setnx(P + 'contou:%s' % cid, '1', 86400 * 3):
                self.salva(conta, u)
                return
            pl = r2(float(q.get('profit') or 0))
            t = pl > 0
            sym, lado = ab['sym'], ab['lado']
            dg = digito_saida(q, sym) if lado not in ('RISE', 'FALL') else None
            try:
                u['saida_ep'] = int(q.get('exit_tick_time') or q.get('sell_spot_time') or time.time())
            except Exception:
                u['saida_ep'] = int(time.time())
            s = u['sessao']
            s['pl'] = r2(s['pl'] + pl)
            s['c'] = int(s.get('c', 0)) + 1
            ger = u.get('ger')
            tx = 'GANHO' if t else 'PERDA'
            if t:
                s['w'] = int(s.get('w', 0)) + 1
                if s.get('gs'):
                    tx = '%s recuperou' % self.nome_g(u, int(s['gs']))
                s['seqL'] = 0
                s['rec'] = 0
                s['gs'] = 0
                s['cic_novo'] = False
            else:
                s['seqL'] = int(s.get('seqL', 0)) + 1
                if ger == 'livre':
                    s['rec'] = r2(float(s.get('rec', 0)) + abs(pl))
                else:
                    s['rec'] = 0 if s.get('rec') else abs(pl)
                if ger == 'mult':
                    C, T, tt = int(u.get('cic', 1)), int(u.get('gal', 3)) + 1, self.tot(u)
                    if int(s.get('gs', 0)) + 1 > tt:
                        s['gs'] = 0
                        tx = 'PERDEU OS %d CICLOS DE GALE' % C if C > 1 else 'PERDEU TODOS OS %d GALES' % int(u.get('gal', 3))
                        if u.get('cicFim') == 'parar':
                            parar = tx.capitalize() + ': o robô parou, como você escolheu'
                    else:
                        s['gs'] = int(s.get('gs', 0)) + 1
                        if s['gs']:
                            tx = 'PERDEU · %s vem aí' % self.nome_g(u, int(s['gs']))
                        if C > 1 and s['gs'] % T == 0:
                            pz = int(u.get('cicP', 0))
                            if pz:
                                u['pausa_ate'] = time.time() + pz
                                u['pausa_txt'] = 'pausa entre ciclos'
                            s['cic_novo'] = True
                            tx = 'CICLO %d PERDIDO · o ciclo %d/%d começa depois de ler o mercado de novo' % (s['gs'] // T, s['gs'] // T + 1, C)
            u['prox'] = time.time() + float(u.get('ri', 5))
            s['pico'] = max(float(s.get('pico', 0)), s['pl'])
            meta, stop = float(u.get('meta') or 0), float(u.get('stop') or 0)
            if not parar:
                if s['pl'] < meta - 1e-9 and u.get('trail') and not t and s['pico'] >= .6 * meta - 1e-9:
                    parar = 'LUCRO PROTEGIDO: já tinha passado de 60%% da meta (%s) e veio uma perda' % sinal(s['pico'])
                elif s['pl'] >= meta - 1e-9:
                    parar = 'META BATIDA: %s em %d ciclos' % (sinal(s['pl']), s['c'])
                elif -s['pl'] >= stop - 1e-9:
                    parar = 'LIMITE DE PERDA de $%.2f atingido' % stop
                elif s['c'] >= int(u.get('maxC', 60)):
                    parar = 'OPERAÇÕES DA SESSÃO COMPLETAS: %d de %d (Máx. ciclos)' % (s['c'], int(u.get('maxC', 60)))
            ps = int(u.get('ps', 3))
            if not parar and ps > 0 and s['seqL'] >= ps:
                u['pausa_ate'] = time.time() + 60
                u['pausa_txt'] = 'pausa de segurança (%d perdas seguidas)' % ps
                s['seqL'] = 0
                if ger not in ('livre', 'mult'):
                    s['rec'] = 0
                self.op_log(conta, {'t': int(time.time()), 'aviso': '%d perdas seguidas: pausa de segurança de 60 s' % ps})
            u['fase'] = ('ganho' if t else 'perda') + ' · ciclo %d · %s' % (s['c'], sinal(pl))
            self.salva(conta, u)
        self.op_log(conta, {'t': int(time.time()), 'n': s['c'], 'sym': sym, 'lado': lado, 'tipo': LADOS[lado][2], 'saiu': dg, 'stake': ab['st'], 'pl': pl, 'tx': tx, 'cid': cid})
        _extrato(conta, u.get('tipo'), cid, sym, ab['st'], pl, 'pulso', 'Alpha Pulso', LADOS[lado][2])
        if parar:
            self.para(conta, parar + ' · resultado ' + sinal(s['pl']))


def sinal(v):
    v = float(v or 0)
    return ('+' if v >= 0 else '−') + '$%.2f' % abs(v)


def register_nuvem_pulso(app):
    from flask import request, jsonify
    nv = NuvemPulso()

    def solta():
        EST['pausa'] = True
        try:
            if nv.kv.get(K_LIDER) == nv.eu:
                nv.kv.set(K_LIDER, '', ex=1)
        except Exception:
            pass
    atexit.register(solta)

    @app.before_request
    def _npl_garante():
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

    @app.route('/api/nuvem-pulso/ligar', methods=['POST'])
    def _npl_ligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta, cf = str(d['conta']), d.get('cfg') or {}
        u = nv.cfg(conta)
        if nv.ligado(conta) or u.get('aberto'):
            return jsonify({'ok': False, 'erro': 'a nuvem já está ligada nesta conta (desligue antes)'}), 400
        lados_ok = list(LADOS.keys())
        u = {'conta': conta, 'tok': str(d['token']).strip(), 'tipo': info['tipo'], 'moeda': info['moeda'], 'parado': '', 't_lig': int(time.time()),
             'sym': cf.get('sym') if cf.get('sym') in MERC else 'R_100', 'ct': cf.get('ct') if cf.get('ct') in ('pi', 'ou', 'rf', 'mix') else 'pi',
             'le': cf.get('le') if cf.get('le') in ('segue', 'inverte', 'maioria', 'alterna') else 'segue', 'ri': num(cf.get('ri'), 5, 1, 120),
             'E': num(cf.get('E'), 1, 0.35, 5000), 'meta': num(cf.get('meta'), 5, 0.01, 1000000), 'stop': num(cf.get('stop'), 10, 0.35, 1000000),
             'ger': cf.get('ger') if cf.get('ger') in ('fixa', 'rec1', 'livre', 'mult') else 'fixa', 'mul': num(cf.get('mul'), 2.3, 1.5, 3.5),
             'gal': int(num(cf.get('gal'), 3, 1, 8)), 'cic': int(num(cf.get('cic'), 1, 1, 10)), 'cicP': int(num(cf.get('cicP'), 0, 0, 600)),
             'cicFim': 'parar' if cf.get('cicFim') == 'parar' else 'reset', 'ps': int(num(cf.get('ps'), 3, 0, 10)),
             'maxC': int(num(cf.get('maxC'), 60, 1, 5000)), 'maxT': int(num(cf.get('maxT'), 20, 1, 1440)), 'trail': 1 if cf.get('trail') else 0,
             'conf': int(num(cf.get('conf'), 0, 0, 5)), 'lado': cf.get('lado') if cf.get('lado') in lados_ok else '',
             'pm': u.get('pm') or {}, 'erros': 0, 'prox': 0, 'mixI': 0, 'ult': None, 'saida_ep': 0, 'pausa_ate': 0, 'fase': 'ligando',
             'sessao': {'pl': 0.0, 'c': 0, 'w': 0, 'seqL': 0, 'rec': 0, 'gs': 0, 'pico': 0.0, 'cic_novo': False, 'ini': int(time.time())}}
        if u['E'] > u['stop']:
            return jsonify({'ok': False, 'erro': 'a entrada é maior que o limite de perda'}), 400
        nv.salva(conta, u)
        nv.liga(conta, True)
        L = nv.lista()
        if conta not in L:
            L.append(conta)
            nv.kv.jset(K_LISTA, L)
        nv.garante()
        nv.op_log(conta, {'t': int(time.time()), 'aviso': 'NUVEM LIGADA na conta %s · %s · entrada $%.2f · %s · meta $%.2f · limite $%.2f' % (
            info['tipo'].upper(), u['sym'], u['E'], {'fixa': 'fixa', 'rec1': 'recuperar 1 vez', 'livre': 'recuperação livre', 'mult': 'martingale ×%.2f até %d gales%s' % (u['mul'], u['gal'], (' × %d ciclos' % u['cic']) if u['cic'] > 1 else '')}[u['ger']], u['meta'], u['stop'])})
        return jsonify({'ok': True, 'cfg': publico(u)})

    @app.route('/api/nuvem-pulso/desligar', methods=['POST'])
    def _npl_desligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        nv.para(conta, 'desligado por você' + (' (o contrato aberto termina normalmente)' if u.get('aberto') else ''))
        return jsonify({'ok': True})

    @app.route('/api/nuvem-pulso/estado', methods=['POST'])
    def _npl_estado():
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

    @app.route('/api/admin/nuvem-pulso', methods=['GET'])
    def _npl_admin():
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
