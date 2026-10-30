# -*- coding: utf-8 -*-
"""PENDENTES-NUVEM-V1 — "🎯 Usar como sinal" do Alpha Global: ordem pendente NA NUVEM.

A pessoa arma um sinal (entrada, stop e alvo em PREÇO). O servidor olha o preço a cada 2 s e, quando ele chega na entrada,
compra o Multiplicador com stop e alvo em dólar calculados no preço real daquele momento. Funciona com a página e o celular fechados.
Antes de entrar, o sinal é cancelado sozinho se o preço for ao stop ou ao alvo (plano perdido) ou se passar do prazo.

  POST /api/pendentes/criar     {token, conta, ordem:{sym, dir, ent, sl, tp, stk, mult, g, nome, aia}}
  POST /api/pendentes/cancelar  {token, conta, id}
  POST /api/pendentes/lista     {token, conta}
  GET  /api/pendentes/diag
"""
import os, time, socket, hashlib, threading, traceback

from nuvem_digitos import KV, Conexao, contas_do_token

VERSAO = 'PENDENTES-NUVEM-V1.1'  # V1.1 VETOS-V1: espera notícia forte passar e não dobra aposta no mesmo grupo
HOST = '%s:%d' % (socket.gethostname(), os.getpid())
K_LISTA = 'pend:lista'
PASSO = 2.0
MAX_ATIVAS = 5
FIM = ('fechada', 'invalida', 'expirou', 'cancelada', 'erro')


def log(*a):
    print('[Pendentes]', *a, flush=True)


def r2(v):
    return round(float(v) + 1e-9, 2)


def valores(o, px):
    """stop e alvo em dólar se entrar ao preço px"""
    ex = float(o['stk']) * float(o['mult'])
    return r2(ex * abs(px - o['sl']) / px), r2(ex * abs(o['tp'] - px) / px)


class Pendentes(object):
    def __init__(self):
        self.kv = KV()
        self.rodando = {}
        self.lk = threading.Lock()
        self.vig = False

    def lista(self):
        return self.kv.jget(K_LISTA, []) or []

    def cfg(self, conta):
        return self.kv.jget('pend:u:' + conta) or {}

    def salva(self, conta, u):
        self.kv.jset('pend:u:' + conta, u, ex=86400 * 30)
        L = self.lista()
        if conta not in L:
            L.append(conta)
            self.kv.jset(K_LISTA, L)

    def muda(self, conta, oid, **kw):
        """grava a mudança de uma ordem relendo o registro (a pessoa pode ter criado/cancelado outra no meio)"""
        u = self.cfg(conta)
        for o in u.get('ordens') or []:
            if o['id'] == oid:
                o.update(kw)
        self.salva(conta, u)
        return u

    def pega(self, conta):
        k = 'pend:dono:' + conta
        d = self.kv.get(k)
        if d == HOST:
            self.kv.set(k, HOST, ex=20)
            return True
        if d:
            return False
        return self.kv.setnx(k, HOST, 20)

    def precisa(self, u):
        return any(o.get('st') in ('obs', 'aberta') for o in u.get('ordens') or [])

    def vigia(self):
        while True:
            try:
                for conta in self.lista():
                    if not self.precisa(self.cfg(conta)):
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

    def preco(self, c, sym, symkey):
        q = {'ticks_history': sym, 'end': 'latest', 'count': 1, 'style': 'ticks'}
        q[symkey[0]] = sym
        r = c.req(q, 10)
        em = str((r.get('error') or {}).get('message', ''))
        if r.get('error') and ('symbol' in em.lower() or 'Properties not allowed' in em or 'validation' in em.lower()):
            q.pop(symkey[0], None)
            symkey[0] = 'symbol' if symkey[0] == 'underlying_symbol' else 'underlying_symbol'
            q[symkey[0]] = sym
            r = c.req(q, 10)
        if r.get('error'):
            raise RuntimeError(r['error'].get('message', 'sem preço'))
        P = (r.get('history') or {}).get('prices') or []
        return float(P[-1]) if P else None

    def veto(self, c, o):
        try:
            import vetos_global as V
        except Exception:
            return ''
        m = V.veto_noticia(o['sym'])
        if m:
            return m
        try:
            r = c.req({'portfolio': 1}, 10)
            ab = [(x.get('underlying_symbol') or x.get('underlying') or x.get('symbol'), V.lado_contrato(x.get('contract_type')))
                  for x in ((r.get('portfolio') or {}).get('contracts') or [])]
            return V.veto_corr(o['sym'], o['dir'], [x for x in ab if x[0] and x[1]])
        except Exception:
            return ''

    def compra(self, c, u, o, px, symkey):
        sl, tp = valores(o, px)
        if sl >= float(o['stk']) * 0.95:
            return None, 'o stop passaria do valor da entrada (stop out da Deriv): diminua o multiplicador'
        if sl < 0.1 or tp < 0.1:
            return None, 'stop ou alvo pequenos demais para a Deriv'
        p = {'contract_type': 'MULTUP' if o['dir'] > 0 else 'MULTDOWN', 'amount': r2(o['stk']), 'basis': 'stake', 'currency': u.get('moeda') or 'USD',
             'multiplier': int(o['mult']), 'limit_order': {'stop_loss': sl, 'take_profit': tp}}
        for _ in range(2):
            q = dict(p)
            q[symkey[0]] = o['sym']
            r = c.req({'buy': 1, 'price': r2(o['stk']), 'parameters': q}, 15)
            em = str((r.get('error') or {}).get('message', ''))
            if r.get('error') and ('symbol' in em.lower() or 'Properties not allowed' in em):
                symkey[0] = 'symbol' if symkey[0] == 'underlying_symbol' else 'underlying_symbol'
                continue
            break
        if r.get('error'):
            return None, em[:140] or 'compra recusada'
        b = r.get('buy') or {}
        return {'cid': str(b.get('contract_id') or ''), 'px_ent': px, 'sl_usd': sl, 'tp_usd': tp}, None

    def trabalha(self, conta):
        u = self.cfg(conta)
        c = Conexao(u.get('tok') or '', conta)
        symkey, erros, ult_poc = ['underlying_symbol'], 0, 0
        log('vigiando', conta[-4:])
        try:
            while True:
                u = self.cfg(conta)
                if not self.precisa(u) or not self.pega(conta):
                    break
                agora = time.time()
                try:
                    cache = {}
                    for o in [x for x in u.get('ordens') or [] if x.get('st') == 'obs']:
                        if agora > o.get('expira', 0):
                            self.muda(conta, o['id'], st='expirou', msg='passou do prazo sem o preço chegar na entrada', t_fim=int(agora))
                            continue
                        if o['sym'] not in cache:
                            cache[o['sym']] = self.preco(c, o['sym'], symkey)
                        px = cache[o['sym']]
                        if not px:
                            continue
                        d = o['dir']
                        if (px <= o['sl']) if d > 0 else (px >= o['sl']):
                            self.muda(conta, o['id'], st='invalida', msg='o preço foi ao stop antes da entrada', px=px, t_fim=int(agora))
                            continue
                        if (px >= o['tp']) if d > 0 else (px <= o['tp']):
                            self.muda(conta, o['id'], st='invalida', msg='o preço foi ao alvo sem passar pela entrada', px=px, t_fim=int(agora))
                            continue
                        chegou = (px <= o['ent']) if o['lado'] == 'cai' else (px >= o['ent'])
                        if not chegou:
                            if agora - o.get('t_px', 0) > 10:
                                self.muda(conta, o['id'], px=px, t_px=int(agora))
                            continue
                        vt = '' if o.get('sem_veto') else self.veto(c, o)   # VETOS-V1: notícia forte ou posição no mesmo grupo -> espera
                        if vt:
                            if agora - o.get('t_vt', 0) > 30:
                                self.muda(conta, o['id'], px=px, t_px=int(agora), t_vt=int(agora), msg='⏸ chegou na entrada, mas esperando: ' + vt)
                            continue
                        res, err = self.compra(c, u, o, px, symkey)
                        if err:
                            self.muda(conta, o['id'], st='erro', msg='Deriv recusou: ' + err, px=px, t_fim=int(agora))
                            log('recusou', conta[-4:], o['sym'], err)
                        else:
                            res.update({'st': 'aberta', 'msg': 'entrou a %s · stop −$%.2f · alvo +$%.2f' % (px, res['sl_usd'], res['tp_usd']), 't_ent': int(agora)})
                            self.muda(conta, o['id'], **res)
                            log('entrou', conta[-4:], o['sym'], px)
                    if agora - ult_poc > 10:
                        ult_poc = agora
                        for o in [x for x in u.get('ordens') or [] if x.get('st') == 'aberta' and x.get('cid')]:
                            if agora - o.get('t_ent', agora) > 86400 * 3:
                                self.muda(conta, o['id'], st='fechada', msg='aberta há mais de 3 dias: confira na Deriv')
                                continue
                            r = c.req({'proposal_open_contract': 1, 'contract_id': int(o['cid']) if o['cid'].isdigit() else o['cid']}, 10)
                            q = r.get('proposal_open_contract') or {}
                            if q and (q.get('is_sold') or q.get('status') in ('won', 'lost', 'sold')):
                                pl = r2(q.get('profit') or 0)
                                self.muda(conta, o['id'], st='fechada', pl=pl, msg=('✅ fechou no lucro ' if pl > 0 else '❌ fechou ') + ('+$%.2f' % pl if pl >= 0 else '−$%.2f' % abs(pl)), t_fim=int(agora))
                            elif q:
                                self.muda(conta, o['id'], pl=r2(q.get('profit') or 0))
                    erros = 0
                except PermissionError:
                    u = self.cfg(conta)
                    for o in u.get('ordens') or []:
                        if o.get('st') == 'obs':
                            o.update({'st': 'erro', 'msg': 'sua sessão na Deriv expirou: abra o Alpha Global e arme de novo'})
                    self.salva(conta, u)
                    break
                except Exception as e:
                    erros += 1
                    if erros in (5, 60):
                        log('instavel', conta[-4:], e)
                    time.sleep(min(10, erros))
                self.kv.set('pend:hb:' + conta, str(int(time.time())), ex=60)
                time.sleep(PASSO)
        except Exception as e:
            log('trabalha', conta[-4:], e, traceback.format_exc()[-400:])
        finally:
            c.fecha()
            with self.lk:
                self.rodando.pop(conta, None)
            if self.kv.get('pend:dono:' + conta) == HOST:
                self.kv.set('pend:dono:' + conta, '', ex=1)


def register_pendentes(app):
    from flask import request, jsonify
    pd = Pendentes()
    pd.garante_vigia()
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

    def fl(v):
        try:
            v = float(str(v).replace(',', '.'))
            return v if v == v and abs(v) != float('inf') else None
        except Exception:
            return None

    def publico(u):
        vivo = time.time() - float(pd.kv.get('pend:hb:' + str(u.get('_conta', ''))) or 0) < 30
        return [{k: o.get(k) for k in ('id', 'sym', 'nome', 'dir', 'ent', 'sl', 'tp', 'stk', 'mult', 'st', 'msg', 'px', 'pl', 'cid', 't', 'expira', 'sl_usd', 'tp_usd', 'g', 'lado')} for o in (u.get('ordens') or [])][:20], vivo

    def resposta(conta):
        u = pd.cfg(conta)
        u['_conta'] = conta
        L, vivo = publico(u)
        return {'ok': True, 'versao': VERSAO, 'ordens': L, 'vigiando': vivo}

    @app.route('/api/pendentes/criar', methods=['POST'])
    def _pn_criar():
        pd.garante_vigia()
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta']).strip()
        o = d.get('ordem') or {}
        sym = str(o.get('sym') or '')[:20]
        dr = 1 if fl(o.get('dir')) and fl(o.get('dir')) > 0 else -1
        ent, sl, tp, stk, mult, px = fl(o.get('ent')), fl(o.get('sl')), fl(o.get('tp')), fl(o.get('stk')), fl(o.get('mult')), fl(o.get('px'))
        if not sym or None in (ent, sl, tp, stk, mult) or min(ent, sl, tp) <= 0:
            return jsonify({'ok': False, 'erro': 'sinal incompleto'}), 400
        if not ((sl < ent < tp) if dr > 0 else (tp < ent < sl)):
            return jsonify({'ok': False, 'erro': 'stop e alvo do lado errado da entrada'}), 400
        if not (1 <= stk <= 5000) or not (1 <= mult <= 5000):
            return jsonify({'ok': False, 'erro': 'entrada ou multiplicador fora do limite'}), 400
        x = {'stk': stk, 'mult': mult, 'sl': sl, 'tp': tp}
        sl_usd, tp_usd = valores(x, ent)
        if sl_usd >= stk * 0.95:
            return jsonify({'ok': False, 'erro': 'com esse multiplicador o stop passaria do valor da entrada (stop out). Diminua o multiplicador ou aumente a entrada.'}), 400
        u = pd.cfg(conta)
        L = [q for q in (u.get('ordens') or []) if q.get('st') not in FIM or time.time() - q.get('t', 0) < 86400 * 3]
        if len([q for q in L if q.get('st') == 'obs']) >= MAX_ATIVAS:
            return jsonify({'ok': False, 'erro': 'você já tem %d sinais armados: cancele um antes' % MAX_ATIVAS}), 400
        g = int(fl(o.get('g')) or 3600)
        prazo = max(3600, min(86400 * 2, g * 60))
        ref = px if px else ent
        nova = {'id': '%d%03d' % (int(time.time() * 1000), len(L)), 't': int(time.time()), 'sym': sym, 'nome': str(o.get('nome') or sym)[:30], 'dir': dr,
                'ent': ent, 'sl': sl, 'tp': tp, 'stk': r2(stk), 'mult': int(mult), 'g': g, 'aia': str(o.get('aia') or '')[:30],
                'lado': 'cai' if ref >= ent else 'sobe', 'expira': int(time.time() + prazo), 'st': 'obs', 'px': px,
                'msg': 'observando: entra quando o preço chegar em %s' % ent, 'sl_usd': sl_usd, 'tp_usd': tp_usd}
        L.insert(0, nova)
        u.update({'tok': str(d['token']).strip(), 'tipo': info['tipo'], 'moeda': info['moeda'], 'ordens': L[:30]})
        pd.salva(conta, u)
        return jsonify(resposta(conta))

    @app.route('/api/pendentes/cancelar', methods=['POST'])
    def _pn_cancelar():
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta']).strip()
        u = pd.cfg(conta)
        for o in u.get('ordens') or []:
            if o['id'] == str(d.get('id')) and o.get('st') == 'obs':
                o.update({'st': 'cancelada', 'msg': 'cancelada por você', 't_fim': int(time.time())})
        pd.salva(conta, u)
        return jsonify(resposta(conta))

    @app.route('/api/pendentes/lista', methods=['POST'])
    def _pn_lista():
        pd.garante_vigia()
        d = request.get_json(silent=True) or {}
        info, err = dono(d)
        if err:
            return jsonify({'ok': False, 'erro': err}), 403
        conta = str(d['conta']).strip()
        u = pd.cfg(conta)
        if u and str(d.get('token') or '').strip() and u.get('tok') != str(d['token']).strip() and pd.precisa(u):
            u['tok'] = str(d['token']).strip()          # token novo do navegador: o servidor passa a usar
            pd.salva(conta, u)
        return jsonify(resposta(conta))

    @app.route('/api/pendentes/diag', methods=['GET'])
    def _pn_diag():
        L = pd.lista()
        return jsonify({'ok': True, 'versao': VERSAO, 'contas': len(L), 'com_ordens': len([c for c in L if pd.precisa(pd.cfg(c))])})

    log('%s registrada' % VERSAO)
    return pd
