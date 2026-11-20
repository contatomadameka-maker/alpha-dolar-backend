# -*- coding: utf-8 -*-
"""NUVEM-CLIQUE-V1 — o AUTOMÁTICO do Alpha Clique rodando NO SERVIDOR (funciona com o celular fechado).

Mesmas regras do automático da página (alpha-clique.html, CLIQUE-V1.6.3 + ciclos V1.4), sem a revisão da IA:
- Família (geral / 0–4×5–9 / Par×Ímpar / Sobe×Desce): escolhe o par que paga mais e o lado pela leitura dos últimos 30 ticks
  (seguir o lado que mais saiu ou contrariar).
- Confirmar antes de entrar: N resultados seguidos do OUTRO lado do cartão (no gale, só os que saíram depois da perda).
- Gale exato (recupera + 1 entrada com o pagamento real), gales 0–12, ciclos 1–10 com pausa; ciclo novo espera no mínimo 2.
- Stop win / stop loss em US$ (a página converte % em US$ ao ligar), stop loss teto real, trava de lucro, pausa depois de N perdas.
Contratos: Par/Ímpar, Over 4/Under 5 (1 tick) e Sobe/Desce (5 ticks).

Rotas: POST /api/nuvem-clique/ligar|desligar|estado {token, conta[, cfg]} · GET /api/admin/nuvem-clique (X-Admin-Token)
"""
import os, json, time, math, uuid, random, threading, atexit, hashlib
from collections import deque

try:
    from nuvem_digitos import KV, Conexao, contas_do_token, digito_saida, log as _log
except Exception:   # pragma: no cover
    from backend.nuvem_digitos import KV, Conexao, contas_do_token, digito_saida, log as _log   # noqa

VERSAO = 'NUVEM-CLIQUE-V1.3'   # V1.3: a confirmacao so conta ticks NOVOS (depois de ligar e depois de cada operacao) · V1.2   # V1.2: reconecta se um mercado parar de mandar preço; batimento do robô; estado mostra a idade do último tick
MERC = ['R_10', 'R_25', 'R_50', 'R_75', 'R_100', '1HZ10V', '1HZ25V', '1HZ50V', '1HZ75V', '1HZ100V']
WS_URLS = [u for u in [os.environ.get('SALA_WS_URL', '').strip(),
                       'wss://api.derivws.com/trading/v1/options/ws/public',
                       'wss://ws.derivws.com/websockets/v3?app_id=1089'] if u]
P = 'nuvem_clq:'
K_LISTA, K_LIDER, K_MOTOR = P + 'lista', P + 'lider', P + 'motor'
TICKS = {s: deque(maxlen=200) for s in MERC}   # (epoch, dígito, subiu 0/1/None)
ULTQ = {}
QT = {s: deque(maxlen=60) for s in MERC}   # CLIQUE-HIT-V1: preço de cada tick (para simular Sobe/Desce no virtual)
EST = {'pausa': False, 'ws': '', 'ticks': 0}
LTK = {}   # NUVEM-CLIQUE-V1.2: hora (relógio do servidor) do último tick de cada mercado
# cartões: contrato, barreira, duração, pagamento inicial, predicado de "ganha", nome
CART = {'par': ('DIGITEVEN', None, 1, .818, 'Par'), 'impar': ('DIGITODD', None, 1, .818, 'Ímpar'),
        'over': ('DIGITOVER', '4', 1, .80, 'Over 4'), 'under': ('DIGITUNDER', '5', 1, .80, 'Under 5'),
        'sobe': ('CALL', None, 5, .79, 'Sobe'), 'desce': ('PUT', None, 5, .79, 'Desce')}
OPOSTO = {'par': 'impar', 'impar': 'par', 'over': 'under', 'under': 'over', 'sobe': 'desce', 'desce': 'sobe'}
FAM = {'geral': ['par', 'impar', 'over', 'under', 'sobe', 'desce'], 'ou': ['over', 'under'], 'pi': ['par', 'impar'], 'sd': ['sobe', 'desce']}


def log(*a):
    try:
        _log('[NuvemClique]', *a)
    except Exception:
        print('[NuvemClique]', *a)


def r2(v):
    return round(float(v) + 1e-9, 2)


def ceil2(v):
    return math.ceil(float(v) * 100 - 1e-6) / 100.0


def ganha(card, d, up):
    """o resultado (dígito / subiu) faria o cartão ganhar?"""
    if card == 'par':
        return d % 2 == 0
    if card == 'impar':
        return d % 2 == 1
    if card == 'over':
        return d > 4
    if card == 'under':
        return d < 5
    if card == 'sobe':
        return up == 1
    if card == 'desce':
        return up == 0
    return False


def saiu(card, sym, n=30):
    """fração dos últimos n ticks em que o cartão teria ganhado (a leitura da página)"""
    L = list(TICKS.get(sym) or [])[-n:]
    if card in ('sobe', 'desce'):
        L = [x for x in L if x[2] is not None]
    if not L:
        return .5
    return sum(1 for (e, d, up) in L if ganha(card, d, up)) / float(len(L))


def seguidos_outro(card, sym, ep=0):
    """quantos resultados seguidos do OUTRO lado do cartão (só os depois de ep)"""
    n = 0
    for (e, d, up) in reversed(list(TICKS.get(sym) or [])):
        if ep and e <= ep:
            break
        if card in ('sobe', 'desce') and up is None:
            break
        if ganha(OPOSTO[card], d, up):
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

class NuvemClique(object):
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
                ws = websocket.create_connection(url, timeout=15, origin='https://alphadolar.online', header=['User-Agent: Mozilla/5.0 (AlphaClique nuvem)'])
                mapa = {}
                for i, s in enumerate(MERC):
                    mapa[i + 1] = s
                    ws.send(json.dumps({'ticks': s, 'subscribe': 1, 'req_id': i + 1}))
                ws.settimeout(10)
                EST['con'] = time.time()
                EST['vistos'] = set()
                EST['ws'] = ''
                ult_ping, sem = time.time(), time.time()
                while not EST['pausa']:
                    if time.time() - ult_ping > 25:
                        ws.send('{"ping": 1}')
                        ult_ping = time.time()
                    _vel = [x for x in EST.get('vistos', ()) if time.time() - LTK.get(x, 0) > 20]
                    if _vel and time.time() - EST.get('con', 0) > 30:   # V1.2: um mercado parou sozinho (ex.: R_100) -> reconecta
                        raise Exception('sem preço de %s há 20 s' % ','.join(_vel))
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
                    QT[sym].append((int(t.get('epoch') or time.time()), q))   # CLIQUE-HIT-V1
                    EST['ticks'] += 1
                    LTK[sym] = time.time()
                    EST.setdefault('vistos', set()).add(sym)
                    if time.time() - EST.get('tkw', 0) > 4:
                        EST['tkw'] = time.time()
                        try:
                            self.kv.set(P + 'tk:' + self.eu, json.dumps(LTK), ex=60)
                        except Exception:
                            pass
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

    # CLIQUE-HIT-V1: modo virtual. Simula a estrategia (confirmacao + entrada + os gales de 1 ciclo) sem comprar; quando der
    # LOSS completo (o "hit") HIT vezes seguidas, a proxima entrada vai de verdade. Terminou o ciclo real, volta ao virtual.
    def vsave(self, conta, u, **kw):
        with self.trava(conta):
            v = self.cfg(conta)
            if v:
                v.update(kw)
                self.salva(conta, v)
        u.update(kw)

    def vres(self, vab, sym):
        card, ep = vab['card'], int(vab.get('ep') or 0)
        if CART[card][2] == 1:
            L = [x for x in list(TICKS.get(sym) or []) if x[0] > ep]
            if not L:
                return None
            return ganha(card, L[0][1], None), str(L[0][1])
        Q = [x for x in list(QT.get(sym) or []) if x[0] > ep]
        n = CART[card][2]
        if len(Q) < n + 1:
            return None
        a, b = Q[0][1], Q[n][1]
        return ((b > a) if card == 'sobe' else (b < a)), ('subiu' if b > a else 'desceu' if b < a else 'empatou')

    def sombra(self, conta, u, sym):
        need = int(u.get('HIT') or 0)
        sb = dict(u.get('sb') or {'v': True, 'k': 0})
        if not need or not sb.get('v', True):
            return False
        T = int(u.get('gales', 0)) + 1
        tq = TICKS.get(sym)
        ult = int(tq[-1][0]) if tq else int(time.time())
        hits = ('wins ' if u.get('HITm') == 'win' else 'hits ') + '%d/%d' % (int(sb.get('k') or 0), need)
        vab, vc = u.get('vab'), u.get('vc')
        if vab:
            r = self.vres(vab, sym)
            if r is None:
                if time.time() - float(vab.get('t') or 0) > 60:
                    self.vsave(conta, u, vab=None)
                self.fase(conta, u, '👻 virtual · %s · esperando o resultado · %s' % (CART[vab['card']][4], hits))
                return True
            won, saiu_tx = r
            niv = int(vab.get('niv') or 0)
            if u.get('HITm') == 'win':   # CLIQUE-HIT-V2: conta WIN seguidos (sem gale no virtual)
                vc = None
                if won:
                    sb['k'] = int(sb.get('k') or 0) + 1
                    tx = 'WIN %d de %d' % (sb['k'], need)
                    if sb['k'] >= need:
                        sb = {'v': False, 'k': 0}
                        tx += ' · a próxima entrada vai na conta de verdade'
                else:
                    sb['k'] = 0
                    tx = 'LOSS · zera a contagem de wins'
            elif won:
                sb['k'] = 0
                vc = None
                tx = 'WIN' + (' no gale %d' % niv if niv else '') + ' · zera a contagem de hits'
            elif niv < T - 1:
                vc = {'nivel': niv + 1, 'card': vab['card'], 'ep': ult}
                tx = 'LOSS · vai para o gale %d (virtual)' % (niv + 1)
            else:
                sb['k'] = int(sb.get('k') or 0) + 1
                vc = None
                tx = 'HIT %d de %d (perdeu a entrada e os gales)' % (sb['k'], need)
                if sb['k'] >= need:
                    sb = {'v': False, 'k': 0}
                    tx += ' · a próxima entrada vai na conta de verdade'
            self.op_log(conta, {'t': int(time.time()), 'aviso': '👻 Virtual · %s · saiu %s · %s' % (CART[vab['card']][4], saiu_tx, tx)})
            self.vsave(conta, u, sb=sb, vab=None, vc=vc, alvo=None, ep0=ult, prox=time.time() + 0.9)
            if not sb.get('v', True):
                self.fase(conta, u, '🎯 hit confirmado no virtual: esperando o padrão para entrar de verdade')
                return False
            return True
        hits = ('wins ' if u.get('HITm') == 'win' else 'hits ') + '%d/%d' % (int(sb.get('k') or 0), need)
        conf = int(u.get('conf', 0))
        if vc:
            card = vc['card']
            k = seguidos_outro(card, sym, int(vc.get('ep') or 0))
            if conf and k < conf:
                self.fase(conta, u, '👻 virtual · gale %d em %s: esperando %d do outro lado (%d/%d) · %s' % (vc['nivel'], CART[card][4], conf, min(k, conf), conf, hits))
                return True
            self.vsave(conta, u, vab={'card': card, 'ep': ult, 'niv': vc['nivel'], 't': time.time()})
            self.fase(conta, u, '👻 virtual · gale %d em %s · %s' % (vc['nivel'], CART[card][4], hits))
            return True
        if time.time() < float(u.get('prox', 0)):
            return True
        card = u.get('alvo')
        if not card:
            card = self.escolhe(u, sym)
            self.vsave(conta, u, alvo=card)
        k = seguidos_outro(card, sym, int(u.get('ep0') or 0))
        if conf and k < conf:
            self.fase(conta, u, '👻 virtual · analisando %s: esperando %d do outro lado (%d/%d) · %s' % (CART[card][4], conf, min(k, conf), conf, hits))
            return True
        self.vsave(conta, u, vab={'card': card, 'ep': ult, 'niv': 0, 't': time.time()})
        self.fase(conta, u, '👻 virtual · entrou em %s · %s' % (CART[card][4], hits))
        return True

    def fase(self, conta, u, txt):
        if int(u.get('HIT') or 0) and not (u.get('sb') or {}).get('v', True) and not str(txt).startswith(('👻', '🎯')):   # CLIQUE-HIT-V1
            txt = txt + ' · 🎯 vale de verdade (hit confirmado)'
        if u.get('fase') != txt:
            with self.trava(conta):
                v = self.cfg(conta)
                if v:
                    v['fase'] = txt
                    self.salva(conta, v)
            u['fase'] = txt

    def trabalha(self, conta):
        c, ult_ep, hb = None, 0, 0
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
                if time.time() - hb > 5:   # V1.2: batimento do robô desta conta
                    hb = time.time()
                    self.kv.set(P + 'hb:' + conta, str(int(hb)), ex=600)
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
                self.para(conta, 'SUA SESSÃO NA DERIV EXPIROU: abra o Alpha Clique e ligue a nuvem de novo')
                return
            except Exception as ex:
                log('trabalha', conta[-3:], ex)
                time.sleep(1.5)

    def escolhe(self, u, sym):
        fam = FAM.get(u.get('fam')) or FAM['geral']
        pm = u.get('pm') or {}
        pares = []
        for a in fam:
            r = a if a < OPOSTO[a] else OPOSTO[a]
            if r not in pares and OPOSTO[a] in fam:
                pares.append(r)
        if not pares:
            return fam[0]
        melhor, nota = None, -1e9
        for a in pares:
            # V1.1 SEGUIR-O-MAIS-FORTE: a dupla que está mais desequilibrada nos últimos 30 ticks (a % mais longe de 50%); o pagamento só desempata
            n = 100 * abs(saiu(a, sym) - .5) + (min(float(pm.get(a) or CART[a][3]), float(pm.get(OPOSTO[a]) or CART[OPOSTO[a]][3])) - 1) / 100.0
            if n > nota:
                nota, melhor = n, a
        r, s = melhor, OPOSTO[melhor]
        cr, cs = saiu(r, sym), saiu(s, sym)
        seguir = u.get('lei') != 'contrariar'
        if cr == cs:
            return random.choice([r, s])
        return r if (cr > cs) == seguir else s

    def decide(self, conta, c, u, sym):
        if self.sombra(conta, u, sym):   # CLIQUE-HIT-V1
            return
        g, agora = u.get('ciclo'), time.time()
        conf = int(u.get('conf', 0))
        if g and g.get('nivel', 0) > 0:
            card = g['card']
            if g.get('esp') and float(g.get('pausa', 0)) > agora:
                return self.fase(conta, u, 'pausa entre ciclos: falta %d s' % math.ceil(float(g['pausa']) - agora))
            need = max(conf, 2) if g.get('esp') else conf
            k = seguidos_outro(card, sym, int(g.get('ep') or 0))
            if need and k < need:
                return self.fase(conta, u, 'gale %d em %s: esperando %d do outro lado (%d/%d)' % (g['nivel'], CART[card][4], need, min(k, need), need))
            g['esp'] = False
            return self.compra(conta, c, u, sym, card)
        if agora < float(u.get('pausa_ate', 0)):
            return self.fase(conta, u, 'pausa depois das perdas: falta %d s' % math.ceil(float(u['pausa_ate']) - agora))
        if agora < float(u.get('prox', 0)):
            return
        card = u.get('alvo')
        if not card:
            card = self.escolhe(u, sym)
            u['alvo'] = card
            with self.trava(conta):
                v = self.cfg(conta)
                v['alvo'] = card
                self.salva(conta, v)
        k = seguidos_outro(card, sym, int(u.get('ep0') or 0))   # V1.3: so ticks depois de ligar / da ultima operacao
        if conf and k < conf:
            return self.fase(conta, u, 'analisando %s: esperando %d do outro lado (%d/%d)' % (CART[card][4], conf, min(k, conf), conf))
        return self.compra(conta, c, u, sym, card)

    def stake(self, u, card):
        g, b = u.get('ciclo'), float(u.get('E', 1))
        if not g or not g.get('nivel'):
            return r2(max(0.35, b))
        pm = float((u.get('pm') or {}).get(card) or CART[card][3])
        return max(0.35, ceil2((float(g['perda']) + float(g['base']) * pm) / pm))

    def compra(self, conta, c, u, sym, card):
        s = u.setdefault('sessao', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'seq': 0})
        st = self.stake(u, card)
        pm = float((u.get('pm') or {}).get(card) or CART[card][3])
        L = float(u.get('L') or 0)
        if st * (1 + pm) > 9990:
            return self.para(conta, 'PARADO: a entrada de $%.2f passa do pagamento máximo da Deriv ($10.000)' % st)
        if L > 0 and -s['pl'] + st > L + 1e-9:
            return self.para(conta, 'STOP: a próxima entrada ($%.2f) passaria do seu stop loss ($%.2f) · resultado %s$%.2f' % (st, L, '+' if s['pl'] >= 0 else '−', abs(s['pl'])))
        ct, bar, dur, _, nome = CART[card]
        prm = {'contract_type': ct, 'amount': st, 'basis': 'stake', 'currency': u.get('moeda') or 'USD', 'duration': dur, 'duration_unit': 't'}
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
                u.setdefault('pm', {})[card] = p
        except Exception:
            pass
        ab = {'cid': b.get('contract_id'), 'st': float(b.get('buy_price') or st), 'card': card, 'sym': sym, 't': int(time.time())}
        with self.trava(conta):
            v = self.cfg(conta)
            v['erros'] = 0
            v['pm'] = u.get('pm') or v.get('pm')
            v['aberto'] = ab
            v['fase'] = 'operação em andamento · %s $%.2f' % (nome, ab['st'])
            if not v.get('ciclo'):
                v['ciclo'] = {'nivel': 0, 'perda': 0.0, 'base': r2(max(0.35, float(v.get('E', 1)))), 'card': card, 'esp': False, 'pausa': 0, 'ep': 0}
            self.salva(conta, v)
        self.confere(conta, c, ab)

    def confere(self, conta, c, ab):
        cid = ab.get('cid')
        dur = CART[ab['card']][2]
        q, fim = None, time.time() + 90
        time.sleep(1.0 if dur == 1 else 4.0)
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
                self.liga(conta, False)
                u['parado'] = 'PARADO: a Deriv não confirmou um contrato (confira no histórico da Deriv)'
                self.salva(conta, u)
                self.op_log(conta, {'t': int(time.time()), 'aviso': 'a Deriv não confirmou o contrato %s em 90 s: confira no histórico da Deriv' % cid})
                return
            if not self.kv.setnx(P + 'contou:%s' % cid, '1', 86400 * 3):
                self.salva(conta, u)
                return
            pl = r2(float(q.get('profit') or 0))
            ganhou = pl > 0
            sym, card = ab['sym'], ab['card']
            dg = digito_saida(q, sym) if CART[card][2] == 1 else None
            s = u.setdefault('sessao', {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'seq': 0})
            s['n'] += 1
            s['pl'] = r2(s['pl'] + pl)
            g = u.get('ciclo') or {'nivel': 0, 'perda': 0.0, 'base': r2(max(0.35, float(u.get('E', 1)))), 'card': card}
            gales, C = int(u.get('gales', 0)), int(u.get('cic', 1))
            T = gales + 1
            tot = T * C - 1 if C > 1 else gales
            para_cic, trava_ok = False, bool(u.get('travaOn'))
            if ganhou:
                s['w'] += 1
                s['seq'] = 0
                tx = 'Gale %d recuperou' % g['nivel'] if g.get('nivel') else 'Vitória'
                u['ciclo'] = None
                u['alvo'] = None
            elif g.get('nivel', 0) < tot and not trava_ok:
                s['l'] += 1
                s['seq'] = int(s.get('seq', 0)) + 1
                nv = g['nivel']
                g['nivel'] = nv + 1
                g['perda'] = r2(float(g['perda']) + ab['st'])
                g['card'] = card
                g['esp'] = C > 1 and g['nivel'] % T == 0
                pz = int(u.get('cicP', 0)) if g['esp'] else 0
                g['pausa'] = time.time() + pz
                ult = TICKS.get(sym)
                g['ep'] = (ult[-1][0] if ult else int(time.time())) + pz
                tx = ('Perdeu o gale %d' % nv if nv else 'Perdeu') + (' · ciclo %d perdido, o gale continua no ciclo %d/%d' % (g['nivel'] // T, g['nivel'] // T + 1, C) if g['esp'] else '')
                u['ciclo'] = g
            else:
                s['l'] += 1
                s['seq'] = int(s.get('seq', 0)) + 1
                tx = 'Perdeu a trava de lucro' if trava_ok else ('Perdeu os %d ciclos de gale' % C if C > 1 else ('Ciclo perdido (todos os gales)' if gales else 'Perdeu'))
                para_cic = tot > 0 and u.get('cicFim') == 'parar'
                u['ciclo'] = None
                u['alvo'] = None
            W, L = float(u.get('W') or 0), float(u.get('L') or 0)
            tv = int(u.get('trava', 0))
            if tv and W > 0 and not u.get('travaOn') and s['pl'] >= W * tv / 100.0 - 1e-9:
                u['travaOn'] = True
            pz_n = int(u.get('pausaN', 0))
            if not u.get('ciclo') and pz_n and s['seq'] >= pz_n:
                u['pausa_ate'] = time.time() + 60
                s['seq'] = 0
            u['prox'] = time.time() + (0.9 if u.get('ciclo') else 2.2)
            _tq = TICKS.get(sym)
            u['ep0'] = int(_tq[-1][0]) if _tq else int(time.time())   # V1.3: a proxima confirmacao comeca do zero
            u['fase'] = ('ganhou' if ganhou else 'perdeu') + ' · %s' % CART[card][4]
            if int(u.get('HIT') or 0) and not u.get('ciclo'):   # CLIQUE-HIT-V1: terminou o ciclo real, volta ao virtual
                u['sb'], u['vab'], u['vc'] = {'v': True, 'k': 0}, None, None
                u['fase'] += ' · volta para o virtual'
            self.salva(conta, u)
        self.op_log(conta, {'t': int(time.time()), 'sym': sym, 'card': card, 'nome': CART[card][4], 'saiu': dg, 'stake': ab['st'], 'pl': pl, 'tx': tx, 'cid': cid})
        _extrato(conta, u.get('tipo'), cid, sym, ab['st'], pl, 'clique', 'Alpha Clique', CART[card][4])   # EXTRATO-NUVEM-V1
        if W > 0 and s['pl'] >= W - 1e-9 and not u.get('ciclo'):
            return self.para(conta, 'META BATIDA: +$%.2f em %d entradas' % (s['pl'], s['n']))
        if L > 0 and -s['pl'] >= L - 1e-9:
            return self.para(conta, 'STOP LOSS de $%.2f atingido · resultado −$%.2f' % (L, abs(s['pl'])))
        if trava_ok and not ganhou:
            return self.para(conta, 'TRAVA DE LUCRO: perdeu depois de passar de %d%% da meta · resultado %s$%.2f' % (tv, '+' if s['pl'] >= 0 else '−', abs(s['pl'])))
        if para_cic:
            return self.para(conta, 'PAROU: perdeu %s, como você escolheu · resultado %s$%.2f' % ('os %d ciclos de gale' % C if C > 1 else 'todos os %d gales' % gales, '+' if s['pl'] >= 0 else '−', abs(s['pl'])))


def register_nuvem_clique(app):
    from flask import request, jsonify
    nv = NuvemClique()

    def solta():
        EST['pausa'] = True
        try:
            if nv.kv.get(K_LIDER) == nv.eu:
                nv.kv.set(K_LIDER, '', ex=1)
        except Exception:
            pass
    atexit.register(solta)

    @app.before_request
    def _ncq_garante():
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

    @app.route('/api/nuvem-clique/ligar', methods=['POST'])
    def _ncq_ligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta, cf = str(d['conta']), d.get('cfg') or {}
        u = nv.cfg(conta)
        if nv.ligado(conta) or u.get('aberto'):
            return jsonify({'ok': False, 'erro': 'a nuvem já está ligada nesta conta (desligue antes)'}), 400
        u = {'conta': conta, 'tok': str(d['token']).strip(), 'tipo': info['tipo'], 'moeda': info['moeda'], 'parado': '', 't_lig': int(time.time()),
             'sym': cf.get('sym') if cf.get('sym') in MERC else 'R_100', 'fam': cf.get('fam') if cf.get('fam') in FAM else 'geral',
             'lei': 'contrariar' if cf.get('lei') == 'contrariar' else 'seguir',
             'E': num(cf.get('E'), 1, 0.35, 5000), 'W': num(cf.get('W'), 0, 0, 1000000), 'L': num(cf.get('L'), 0, 0, 1000000),
             'gales': int(num(cf.get('gales'), 2, 0, 12)), 'cic': int(num(cf.get('cic'), 1, 1, 10)), 'cicP': int(num(cf.get('cicP'), 0, 0, 600)),
             'cicFim': 'parar' if cf.get('cicFim') == 'parar' else 'reset', 'conf': int(num(cf.get('conf'), 0, 0, 6)),
             'HIT': int(num(cf.get('HIT'), 0, 0, 10)), 'HITm': 'win' if cf.get('HITm') == 'win' else 'loss', 'sb': {'v': True, 'k': 0}, 'vab': None, 'vc': None, 'trava': int(num(cf.get('trava'), 0, 0, 90)), 'pausaN': int(num(cf.get('pausaN'), 3, 0, 5)),
             'pm': u.get('pm') or {}, 'erros': 0, 'prox': 0, 'ciclo': None, 'alvo': None, 'travaOn': False, 'fase': 'ligando',
             'sessao': {'pl': 0.0, 'n': 0, 'w': 0, 'l': 0, 'seq': 0, 'ini': int(time.time())}, 'ep0': int(time.time())}
        nv.salva(conta, u)
        nv.liga(conta, True)
        L = nv.lista()
        if conta not in L:
            L.append(conta)
            nv.kv.jset(K_LISTA, L)
        nv.garante()
        nv.op_log(conta, {'t': int(time.time()), 'aviso': 'NUVEM LIGADA na conta %s · %s · família %s · entrada $%.2f · %d gale(s)%s · stop win %s · stop loss %s' % (
            info['tipo'].upper(), u['sym'], u['fam'], u['E'], u['gales'], (' × %d ciclos' % u['cic']) if u['cic'] > 1 else '',
            ('$%.2f' % u['W']) if u['W'] else 'sem', ('$%.2f' % u['L']) if u['L'] else 'sem')})
        return jsonify({'ok': True, 'cfg': publico(u)})

    @app.route('/api/nuvem-clique/desligar', methods=['POST'])
    def _ncq_desligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        nv.para(conta, 'desligado por você' + (' (o contrato aberto termina normalmente)' if u.get('aberto') else ''))
        return jsonify({'ok': True})

    @app.route('/api/nuvem-clique/estado', methods=['POST'])
    def _ncq_estado():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta'])
        u = nv.cfg(conta)
        if u:
            u['ligado'] = nv.ligado(conta)
        mt = float(nv.kv.get(K_MOTOR) or 0)
        _ti, _hb = None, None
        try:   # V1.2: idade do último preço do mercado desta conta no robô líder + batimento
            _ld = nv.kv.get(K_LIDER) or ''
            _tk = nv.kv.jget(P + 'tk:' + _ld, {}) if _ld else {}
            if u and _tk.get(u.get('sym') or 'R_100'):
                _ti = int(time.time() - float(_tk[u.get('sym') or 'R_100']))
            _h = nv.kv.get(P + 'hb:' + conta)
            _hb = int(time.time() - float(_h)) if _h else None
        except Exception:
            pass
        return jsonify({'ok': True, 'versao': VERSAO, 'cfg': publico(u) if u else None, 'ops': (nv.kv.jget(P + 'ops:' + conta, []) or [])[:40],
                        'motor': (time.time() - mt < 60) if _ti is None else _ti < 25, 'tick_idade': _ti, 'robo_idade': _hb, 'saldo': info.get('saldo')})

    @app.route('/api/admin/nuvem-clique', methods=['GET'])
    def _ncq_admin():
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
