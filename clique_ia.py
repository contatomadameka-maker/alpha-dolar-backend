# -*- coding: utf-8 -*-
"""CLIQUE-IA-V1 — IA de verdade (Claude) que revisa a sessão do Alpha Clique no modo automático.

As regras do navegador decidem cada entrada (rápido e sem custo). A IA é chamada no começo da sessão,
a cada ~10 operações e depois de perdas seguidas: escolhe o contrato dentro do que a pessoa liberou,
pode diminuir a entrada, pedir pausa ou encerrar, e explica o motivo em português.

POST /api/clique-ia  {familia, permitidos:[ids], candidatos:[{id,nome,chance,paga,saiu}], sessao:{...}, ultimos:[...]}
  -> {ok, escolha, acao, fator, motivo}
"""
import os, re, json, time, threading
import urllib.request
from datetime import datetime, timezone, timedelta

BRT = timezone(timedelta(hours=-3))


def register_clique_ia(app):
    from flask import request, jsonify
    trava = threading.Lock()
    uso = {'dia': '', 'n': 0, 'ip': {}}

    def s(v, n=40):
        return re.sub(r'[^\w\s.,;:!?/%+\-()·×]', '', str(v if v is not None else ''))[:n]

    def f(v, d=0.0):
        try:
            return float(v)
        except Exception:
            return d

    @app.route('/api/clique-ia', methods=['POST'])
    def _clique_ia():
        d = request.get_json(silent=True) or {}
        ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or '?').split(',')[0].strip()
        hoje = datetime.now(BRT).strftime('%Y-%m-%d')
        with trava:
            if uso['dia'] != hoje:
                uso.update({'dia': hoje, 'n': 0, 'ip': {}})
            if time.time() - uso['ip'].get(ip, 0) < 6:
                return jsonify({'ok': False, 'erro': 'aguarde alguns segundos'}), 200
            if uso['n'] >= int(os.environ.get('CLIQUE_IA_LIMITE_DIA', '3000')):
                return jsonify({'ok': False, 'erro': 'limite diario da IA atingido'}), 200
            uso['ip'][ip] = time.time()
            uso['n'] += 1
            if len(uso['ip']) > 20000:
                uso['ip'].clear()
        key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not key:
            return jsonify({'ok': False, 'erro': 'ANTHROPIC_API_KEY ausente'}), 200
        perm = [s(x, 10) for x in (d.get('permitidos') or []) if s(x, 10)][:8]
        if not perm:
            return jsonify({'ok': False, 'erro': 'sem contratos permitidos'}), 200
        cand = []
        for c in (d.get('candidatos') or [])[:8]:
            if not isinstance(c, dict) or s(c.get('id'), 10) not in perm:
                continue
            p, pm, saiu = f(c.get('chance'), .5), f(c.get('paga'), .8), f(c.get('saiu'), .5)
            cand.append('%s (%s): chance natural %.0f%%, paga %.1f%%, custo medio %.1f%% por operacao, saiu nos ultimos 30: %.0f%%' % (
                s(c.get('id'), 10), s(c.get('nome'), 14), p * 100, pm * 100, (p * pm - (1 - p)) * 100, saiu * 100))
        se = d.get('sessao') or {}
        ses = 'resultado %s em %s operacoes (%s vitorias, %s derrotas), perdas seguidas agora: %s, banca %s, entrada %s, gales %s, meta %s, stop %s, trava de lucro %s%%' % (
            s(se.get('pl'), 10), s(se.get('ops'), 5), s(se.get('w'), 5), s(se.get('l'), 5), s(se.get('seq'), 3), s(se.get('banca'), 12),
            s(se.get('entrada'), 8), s(se.get('gales'), 2), s(se.get('meta'), 8), s(se.get('stop'), 8), s(se.get('trava'), 3))
        ult = ' | '.join(s(x, 30) for x in (d.get('ultimos') or [])[:10]) or 'nenhuma'
        placar = s(d.get('placar'), 120)
        sistema = ('Voce e a IA de gestao do robo Alpha Clique (contratos de 1 a 5 ticks nos indices sinteticos da Deriv). '
                   'FATO OBRIGATORIO: os ticks sao aleatorios; nenhuma leitura de digitos preve o proximo resultado. Nunca prometa acerto nem lucro. '
                   'Seu trabalho e gestao: escolher, entre os contratos PERMITIDOS, o de menor custo medio (use os numeros dados), '
                   'proteger a banca (diminuir a entrada ou pausar depois de perdas seguidas, encerrar se o stop estiver perto) '
                   'e manter a disciplina (nao aumentar risco para recuperar). Portugues do Brasil, frase curta (ate 28 palavras). '
                   'Responda SO com JSON valido, sem markdown.')
        pedido = ('Contratos permitidos pela pessoa: %s\nCandidatos agora:\n%s\nSessao: %s\nUltimas operacoes (mais recente primeiro): %s\nPlacar leitura x sorteio: %s\n\n'
                  'Formato: {"escolha":"id permitido ou regras","acao":"continuar|reduzir|pausar|encerrar","fator":0.5 a 1.0,"motivo":"..."}') % (
            ', '.join(perm), '\n'.join(cand) or 'sem dados', ses, ult, placar or 'sem dados')
        body = json.dumps({'model': os.environ.get('CLIQUE_IA_MODELO', 'claude-haiku-4-5-20251001'), 'max_tokens': 220, 'system': sistema,
                           'messages': [{'role': 'user', 'content': pedido}]}).encode()
        rq = urllib.request.Request('https://api.anthropic.com/v1/messages', data=body, method='POST',
                                    headers={'Content-Type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01'})
        try:
            with urllib.request.urlopen(rq, timeout=15) as r:
                resp = json.loads(r.read())
            txt = (resp.get('content') or [{}])[0].get('text', '')
            m = re.search(r'\{.*\}', txt, re.S)
            o = json.loads(m.group(0)) if m else {}
        except Exception as e:
            return jsonify({'ok': False, 'erro': 'a IA nao respondeu (%s)' % str(e)[:60]}), 200
        esc = s(o.get('escolha'), 10)
        if esc not in perm:
            esc = 'regras'
        acao = o.get('acao') if o.get('acao') in ('continuar', 'reduzir', 'pausar', 'encerrar') else 'continuar'
        fator = min(1.0, max(0.5, f(o.get('fator'), 1.0)))
        if acao != 'reduzir':
            fator = 1.0
        return jsonify({'ok': True, 'escolha': esc, 'acao': acao, 'fator': round(fator, 2), 'motivo': s(o.get('motivo'), 220)})

    print('🟢 CLIQUE-IA-V1 ativa: /api/clique-ia', flush=True)
