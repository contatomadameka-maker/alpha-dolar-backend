# -*- coding: utf-8 -*-
"""PROTECAO-LUCRO-V1 — protege o lucro das posições de Multiplicador (Alpha Global) NO SERVIDOR, com a página fechada.

Regras (em dólar de lucro da posição; 0 = desligada):
  zera_em        — ZERAR RISCO: quando o lucro chega a X, a posição não pode mais fechar no prejuízo (piso = $0).
  trava_em/guarda — TRAVAR LUCRO: quando o lucro chega a X, garante pelo menos Y (ex.: chegou a +20, garante +15).
  movel          — STOP MÓVEL: o piso acompanha o maior lucro a X dólares de distância.
Quando o lucro cai até o piso, o servidor vende a posição (sell). A Deriv não deixa o stop dela guardar lucro,
por isso quem fecha é o servidor. Num salto de preço a venda pode sair um pouco abaixo do piso.

Rotas (a pessoa prova que é dona da conta mandando o token da Deriv do próprio navegador):
  POST /api/protecao/ligar     {token, conta, regras:{zera_em, trava_em, guarda, movel}}
  POST /api/protecao/desligar  {token, conta}
  POST /api/protecao/estado    {token, conta}
  GET  /api/protecao/diag
"""
import os, json, time, socket, hashlib, threading, traceback
from datetime import datetime, timezone, timedelta

from nuvem_digitos import KV, Conexao, contas_do_token

VERSAO = 'PROTECAO-LUCRO-V1'
BRT = timezone(timedelta(hours=-3))
HOST = '%s:%d' % (socket.gethostname(), os.getpid())
K_LISTA = 'prot:lista'
PASSO = 1.0          # segundos entre conferências
PORTF = 4.0          # segundos entre buscas de posições novas
NOMES = {'frxXAUUSD': 'Ouro', 'frxXAGUSD': 'Prata', 'frxEURUSD': 'EUR/USD', 'frxGBPUSD': 'GBP/USD', 'frxUSDJPY': 'USD/JPY', 'cryBTCUSD': 'Bitcoin', 'cryETHUSD': 'Ethereum'}


def nm(s):
    return NOMES.get(s, s or 'posição')


def log(*a):
    print('[Protecao]', *a, flush=True)


def r2(v):
    return round(float(v) + 1e-9, 2)


def piso_de(rg, mx):
    """o piso (lucro mínimo garantido) para o maior lucro já visto"""
    p = None
    z = float(rg.get('zera_em') or 0)
    if z > 0 and mx >= z:
        p = 0.0
    t, g = float(rg.get('trava_em') or 0), float(rg.get('guarda') or 0)
    if t > 0 and mx >= t:
        p = g if p is None else max(p, g)
    m = float(rg.get('movel') or 0)
    if m > 0 and mx >= m:            # o móvel só começa quando já está a X de lucro (aí nunca fecha no negativo)
        v = mx - m
        p = v if p is None else max(p, v)
    return None if p is None else r2(p)


class Protecao(object):
    def __init__(self):
        self.kv = KV()
        self.rodando = {}
        self.lk = threading.Lock()
        self.vig = False

    # ---------- armazenamento ----------
    def lista(self):
        return self.kv.jget(K_LISTA, []) or []

    def cfg(self, conta):
        return self.kv.jget('prot:u:' + conta) or {}

    def salva(self, conta, u):
        self.kv.jset('prot:u:' + conta, u)
        L = self.lista()
        if conta not in L:
            L.append(conta)
            self.kv.jset(K_LISTA, L)

    def ev(self, conta, txt, pl=None):
        k = 'prot:log:' + conta
        L = self.kv.jget(k, []) or []
        L.insert(0, {'t': int(time.time()), 'm': txt, 'pl': pl})
        self.kv.jset(k, L[:60], ex=86400 * 14)

    def mesa_cids(self, conta):
        """posições abertas pelos agentes da Mesa nessa conta não são mexidas"""
        out = set()
        try:
            c = self.kv.jget('mesa:cfg') or {}
            if str(c.get('conta') or '') != conta:
                return out
            for a in c.get('agentes') or []:
                s = self.kv.jget('mesa:st:' + str(a.get('id'))) or {}
                p = s.get('pos') or {}
                if p.get('cid'):
                    out.add(str(p['cid']))
        except Exception:
            pass
        return out

    # ---------- dono da conta (um servidor só vigia cada conta) ----------
    def pega(self, conta):
        k = 'prot:dono:' + conta
        d = self.kv.get(k)
        if d == HOST:
            self.kv.set(k, HOST, ex=20)
            return True
        if d:
            return False
        return self.kv.setnx(k, HOST, 20)

    def vigia(self):
        while True:
            try:
                for conta in self.lista():
                    u = self.cfg(conta)
                    if not u.get('ligado'):
                        continue
                    with self.lk:
                        vivo = conta in self.rodando and self.rodando[conta].is_alive()
                    if not vivo and self.pega(conta):
                        th = threading.Thread(target=self.trabalha, args=(conta,), daemon=True)
                        with self.lk:
                            self.rodando[conta] = th
                        th.start()
            except Exception as e:
                log('vigia', e)
            time.sleep(3)

    def garante_vigia(self):
        if not self.vig:
            self.vig = True
            threading.Thread(target=self.vigia, daemon=True).start()

    # ---------- o trabalho de cada conta ----------
    def trabalha(self, conta):
        u = self.cfg(conta)
        c = Conexao(u.get('tok') or '', conta)
        pos, ult_pf, erros = {}, 0, 0
        log('vigiando', conta[-4:])
        try:
            while True:
                u = self.cfg(conta)
                if not u.get('ligado') or not self.pega(conta):
                    break
                rg = u.get('regras') or {}
                agora = time.time()
                try:
                    if agora - ult_pf > PORTF:
                        ult_pf = agora
                        r = c.req({'portfolio': 1}, 12)
                        fora = self.mesa_cids(conta)
                        vistos = set()
                        for q in (r.get('portfolio') or {}).get('contracts') or []:
                            ct = str(q.get('contract_type') or '')
                            cid = str(q.get('contract_id') or '')
                            if not ct.startswith('MULT') or not cid or cid in fora:
                                continue
                            vistos.add(cid)
                            if cid not in pos:
                                pos[cid] = {'cid': cid, 'sym': q.get('underlying_symbol') or q.get('symbol') or q.get('underlying') or '',
                                            'tipo': ct, 'stake': q.get('buy_price'), 't': int(agora), 'mx': None, 'piso': None, 'pl': None}
                        for cid in list(pos):
                            if cid not in vistos and agora - pos[cid]['t'] > 30:
                                pos.pop(cid, None)          # fechou por outro motivo (alvo, stop, na mão)
                    for cid, p in list(pos.items()):
                        r = c.req({'proposal_open_contract': 1, 'contract_id': int(cid) if cid.isdigit() else cid}, 10)
                        q = r.get('proposal_open_contract') or {}
                        if r.get('error') or not q:
                            continue
                        if q.get('is_sold') or q.get('status') in ('won', 'lost', 'sold'):
                            pos.pop(cid, None)
                            continue
                        pl = r2(q.get('profit') or 0)
                        p['pl'] = pl
                        p['sym'] = p['sym'] or q.get('underlying_symbol') or q.get('underlying') or ''
                        p['mx'] = pl if p['mx'] is None else max(p['mx'], pl)
                        novo = piso_de(rg, p['mx'])
                        if novo is not None and (p['piso'] is None or novo > p['piso']):
                            if p['piso'] is None or novo - p['piso'] >= 0.5:
                                self.ev(conta, '%s: piso subiu para %s (maior lucro %s)' % (nm(p['sym']), fm(novo), fm(p['mx'])))
                            p['piso'] = novo
                        if p['piso'] is not None and pl <= p['piso']:
                            rs = c.req({'sell': int(cid) if cid.isdigit() else cid, 'price': 0}, 15)
                            if rs.get('error'):
                                msg = (rs['error'] or {}).get('message', '')
                                self.ev(conta, 'Não consegui fechar %s: %s' % (nm(p['sym']), msg[:90]))
                            else:
                                vend = r2((rs.get('sell') or {}).get('sold_for') or 0) - r2(p.get('stake') or 0)
                                self.ev(conta, '🛡 Fechei %s protegendo o lucro: %s (maior lucro %s, piso %s)' % (nm(p['sym']), fm(vend), fm(p['mx']), fm(p['piso'])), vend)
                                pos.pop(cid, None)
                    erros = 0
                except PermissionError:
                    u = self.cfg(conta)
                    u['ligado'] = False
                    u['parado'] = 'sua sessão na Deriv expirou: abra o Alpha Global e ligue de novo'
                    self.salva(conta, u)
                    self.ev(conta, 'Proteção desligada: a sessão da Deriv expirou.')
                    break
                except Exception as e:
                    erros += 1
                    if erros in (3, 30):
                        self.ev(conta, 'Conexão com a Deriv instável (%s). Continuo tentando.' % str(e)[:60])
                    time.sleep(min(10, erros))
                self.kv.jset('prot:c:' + conta, {'t': int(time.time()), 'host': HOST, 'pos': list(pos.values())}, ex=120)
                time.sleep(PASSO)
        except Exception as e:
            log('trabalha', conta[-4:], e, traceback.format_exc()[-400:])
        finally:
            c.fecha()
            with self.lk:
                self.rodando.pop(conta, None)
            if self.kv.get('prot:dono:' + conta) == HOST:
                self.kv.set('prot:dono:' + conta, '', ex=1)


def fm(v):
    v = float(v or 0)
    return ('+$' if v >= 0 else '−$') + '%.2f' % abs(v)


def register_protecao(app):
    from flask import request, jsonify
    pr = Protecao()
    pr.garante_vigia()
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
        info = {'tipo': ac[0].get('account_type'), 'moeda': ac[0].get('currency') or 'USD'}
        cache[h] = (time.time(), info)
        return info, None

    def num(v, lo=0, hi=100000):
        try:
            return max(lo, min(hi, float(str(v).replace(',', '.'))))
        except Exception:
            return 0.0

    def regras(d):
        rg = d.get('regras') or {}
        o = {'zera_em': num(rg.get('zera_em')), 'trava_em': num(rg.get('trava_em')), 'guarda': num(rg.get('guarda')), 'movel': num(rg.get('movel'))}
        if o['trava_em'] and o['guarda'] >= o['trava_em']:
            o['guarda'] = r2(o['trava_em'] * 0.75)
        return o

    def estado(conta):
        u = pr.cfg(conta)
        s = pr.kv.jget('prot:c:' + conta) or {}
        vivo = bool(s) and time.time() - float(s.get('t') or 0) < 15
        return {'ok': True, 'versao': VERSAO, 'ligado': bool(u.get('ligado')), 'parado': u.get('parado') or '', 'tipo': u.get('tipo'),
                'regras': u.get('regras') or {}, 'vivo': vivo, 'pos': (s.get('pos') or []) if vivo else [], 'log': (pr.kv.jget('prot:log:' + conta, []) or [])[:25]}

    @app.route('/api/protecao/ligar', methods=['POST'])
    def _pt_ligar():
        pr.garante_vigia()
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        rg = regras(d)
        if not (rg['zera_em'] or rg['trava_em'] or rg['movel']):
            return jsonify({'ok': False, 'erro': 'escolha pelo menos uma proteção'}), 400
        conta = str(d['conta']).strip()
        u = pr.cfg(conta)
        u.update({'tok': str(d['token']).strip(), 'tipo': info['tipo'], 'regras': rg, 'ligado': True, 'parado': '', 't_lig': int(time.time())})
        pr.salva(conta, u)
        pr.ev(conta, 'Proteção ligada na conta %s.' % (info['tipo'] or '').upper())
        return jsonify(estado(conta))

    @app.route('/api/protecao/desligar', methods=['POST'])
    def _pt_desligar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta']).strip()
        u = pr.cfg(conta)
        u['ligado'] = False
        u['parado'] = 'desligada por você'
        pr.salva(conta, u)
        pr.ev(conta, 'Proteção desligada por você.')
        return jsonify(estado(conta))

    @app.route('/api/protecao/estado', methods=['POST'])
    def _pt_estado():
        pr.garante_vigia()
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        return jsonify(estado(str(d['conta']).strip()))

    @app.route('/api/protecao/diag', methods=['GET'])
    def _pt_diag():
        L = pr.lista()
        return jsonify({'ok': True, 'versao': VERSAO, 'pid': os.getpid(), 'contas': len(L),
                        'ligadas': len([c for c in L if pr.cfg(c).get('ligado')]),
                        'vigiadas': len([c for c in L if (pr.kv.jget('prot:c:' + c) or {}).get('t', 0) > time.time() - 15])})

    log('%s registrada' % VERSAO)
    return pr
