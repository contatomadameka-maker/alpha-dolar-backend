import os
import requests

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}

def init_db():
    print("Supabase conectado!")

def salvar_cliente(data):
    deriv_id = data.get('deriv_id')
    url = f"{SUPABASE_URL}/rest/v1/clientes"
    payload = {
        'deriv_id': deriv_id,
        'nome': data.get('nome'),
        'email': data.get('email'),
        'token_demo': data.get('token_demo'),
        'token_real': data.get('token_real'),
        'account_type': data.get('account_type', 'demo'),
        'bot_name'     : data.get('bot_name', ''),
        'via_afiliado' : data.get('via_afiliado', False),
        'bot_afiliado' : data.get('bot_afiliado', ''),
    }
    # Tenta insert primeiro
    r = requests.post(url, json=payload, headers={**HEADERS, 'Prefer': 'return=representation'})
    if r.status_code in [200, 201]:
        return True
    # Se já existe, faz update
    r = requests.patch(f"{url}?deriv_id=eq.{deriv_id}", json=payload, headers=HEADERS)
    return r.status_code in [200, 204]

def listar_clientes():
    url = f"{SUPABASE_URL}/rest/v1/clientes?order=ultimo_acesso.desc"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return r.json()
    return []

def salvar_operacao(bot_name, cliente_id, direcao, ganhou, lucro, stake, markup_usd=0.0):
    import requests as req
    import os
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'bot_name': bot_name,
        'cliente_id': cliente_id,
        'tipo': direcao,
        'stake': float(stake),
        'resultado': 'win' if ganhou else 'loss',
        'lucro': float(lucro),
        'markup_usd': float(markup_usd)
    }
    try:
        req.post(f"{SUPABASE_URL}/rest/v1/operacoes", json=payload, headers=headers)
    except:
        pass

def listar_operacoes(bot_name=None):
    import requests as req
    import os
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'count=exact'
    }
    url = f"{SUPABASE_URL}/rest/v1/operacoes?order=criado_em.desc&limit=5000"
    if bot_name:
        url += f"&bot_name=eq.{bot_name}"
    try:
        r = req.get(url, headers=headers)
        if r.status_code == 200:
            return r.json()
    except: pass
    return []

def listar_bots():
    import requests as req, os
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
    headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    r = req.get(f"{SUPABASE_URL}/rest/v1/bots?order=criado_em.desc", headers=headers)
    return r.json() if r.status_code == 200 else []

def salvar_bot(data):
    import requests as req, os
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
    headers = {
        'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates,return=representation'
    }
    payload = {
        'nome'          : data.get('nome'),
        'dono'          : data.get('dono'),
        'deriv_id'      : data.get('deriv_id'),
        'status'        : data.get('status', 'ativo'),
        'afiliado_link' : data.get('afiliado_link', ''),
        'afiliado_token': data.get('afiliado_token', ''),
        'markup_pct'    : data.get('markup_pct', 2.0),
    }
    r = req.post(f"{SUPABASE_URL}/rest/v1/bots", json=payload, headers=headers)
    return r.status_code in [200, 201]

def atualizar_bot(nome, data):
    import requests as req, os
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
    headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json'}
    r = req.patch(f"{SUPABASE_URL}/rest/v1/bots?nome=eq.{nome}", json=data, headers=headers)
    return r.status_code in [200, 204]

def salvar_estado_bot(bot_type, estado):
    """Salva estado do bot no Supabase para auto-restart"""
    import requests as req, json, os
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '')
    headers = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'Prefer': 'resolution=merge-duplicates'}
    payload = {'bot_type': bot_type, 'estado': json.dumps(estado)}
    r = req.post(f"{url}/rest/v1/bot_estado", json=payload, headers=headers)
    return r.status_code in [200, 201]

def recuperar_estado_bot(bot_type):
    """Recupera estado do bot do Supabase"""
    import requests as req, json, os
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '')
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
    r = req.get(f"{url}/rest/v1/bot_estado?bot_type=eq.{bot_type}&limit=1", headers=headers)
    if r.status_code == 200 and r.json():
        try: return json.loads(r.json()[0]['estado'])
        except: return None
    return None

def limpar_estado_bot(bot_type):
    """Remove estado do bot (quando parado manualmente)"""
    import requests as req, os
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '')
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
    r = req.delete(f"{url}/rest/v1/bot_estado?bot_type=eq.{bot_type}", headers=headers)
    return r.status_code in [200, 204]


# ─── SISTEMA DE INDICAÇÃO / REDE DE AFILIADOS (modelo A — cliente final) ─────
# Não confundir com via_afiliado/bot_afiliado, que é o modelo B (parceiro de
# template pagando revenue share pra Alpha Dolar). Os dois nunca se misturam.

import random as _random
import string as _string

NIVEIS_PCT_REDE = [0.15, 0.08, 0.04, 0.02, 0.01]  # nivel 1 a 5


def _gerar_ref_code():
    return ''.join(_random.choices(_string.ascii_lowercase + _string.digits, k=8))


def resolver_referral(deriv_id, bot_name, ref_code_recebido=None):
    """
    Chamar em todo login/acesso, depois de salvar_cliente.
    Idempotente: só age na primeira vez que falta cada campo, nunca sobrescreve depois.
    """
    url = f"{SUPABASE_URL}/rest/v1/clientes"
    try:
        r = requests.get(
            f"{url}?deriv_id=eq.{deriv_id}&select=ref_code,ref_promoter_id,via_afiliado",
            headers=HEADERS
        )
        if r.status_code != 200 or not r.json():
            return
        cliente = r.json()[0]
        patch = {}

        if not cliente.get('ref_code'):
            patch['ref_code'] = _gerar_ref_code()

        # So vincula patrocinador se: ainda nao tem um E nao e cliente do modelo B
        if not cliente.get('ref_promoter_id') and ref_code_recebido and not cliente.get('via_afiliado'):
            pr = requests.get(
                f"{url}?ref_code=eq.{ref_code_recebido}&select=deriv_id,bot_name",
                headers=HEADERS
            )
            if pr.status_code == 200 and pr.json():
                promotor = pr.json()[0]
                if promotor.get('bot_name') == bot_name and promotor['deriv_id'] != deriv_id:
                    patch['ref_promoter_id'] = promotor['deriv_id']

        if patch:
            requests.patch(f"{url}?deriv_id=eq.{deriv_id}", json=patch, headers=HEADERS)
    except Exception as e:
        print(f"Erro em resolver_referral: {e}")


def distribuir_comissao(cliente_id, bot_name, markup_usd):
    """
    Chamar logo apos salvar_operacao, quando markup_usd > 0.
    Sobe a cadeia de patrocinadores gravando um lancamento por nivel.
    """
    if not markup_usd or markup_usd <= 0:
        return
    url = f"{SUPABASE_URL}/rest/v1/clientes"
    try:
        # Trava modelo B: cliente vindo de parceiro de template nao gera rede de indicacao
        r0 = requests.get(f"{url}?deriv_id=eq.{cliente_id}&select=via_afiliado", headers=HEADERS)
        if r0.status_code == 200 and r0.json() and r0.json()[0].get('via_afiliado'):
            return

        atual = cliente_id
        for nivel, pct in enumerate(NIVEIS_PCT_REDE, start=1):
            r = requests.get(f"{url}?deriv_id=eq.{atual}&select=ref_promoter_id", headers=HEADERS)
            if r.status_code != 200 or not r.json():
                break
            promotor = r.json()[0].get('ref_promoter_id')
            if not promotor:
                break
            valor = round(float(markup_usd) * pct, 4)
            requests.post(f"{SUPABASE_URL}/rest/v1/comissoes_rede", headers=HEADERS, json={
                'bot_name': bot_name,
                'beneficiario_id': promotor,
                'origem_cliente_id': cliente_id,
                'nivel': nivel,
                'markup_origem_usd': float(markup_usd),
                'percentual_aplicado': pct,
                'valor_usd': valor,
                'status': 'pendente',
            })
            atual = promotor
    except Exception as e:
        print(f"Erro em distribuir_comissao: {e}")


def resumo_rede(deriv_id, bot_name=None):
    """Soma as comissoes de rede de um beneficiario -- usado na tela Desempenho."""
    url = f"{SUPABASE_URL}/rest/v1/comissoes_rede"
    filtro = f"?beneficiario_id=eq.{deriv_id}"
    if bot_name:
        filtro += f"&bot_name=eq.{bot_name}"
    try:
        r = requests.get(f"{url}{filtro}&select=valor_usd,nivel,status,criado_em", headers=HEADERS)
        rows = r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"Erro em resumo_rede: {e}")
        rows = []

    total = round(sum(float(x.get('valor_usd', 0)) for x in rows), 4)
    pendente = round(sum(float(x.get('valor_usd', 0)) for x in rows if x.get('status') == 'pendente'), 4)
    disponivel = round(sum(float(x.get('valor_usd', 0)) for x in rows if x.get('status') == 'disponivel'), 4)

    # Rede ativa direta: quantos tem esse deriv_id como patrocinador
    url_c = f"{SUPABASE_URL}/rest/v1/clientes"
    try:
        rc = requests.get(f"{url_c}?ref_promoter_id=eq.{deriv_id}&select=deriv_id", headers=HEADERS)
        diretos = len(rc.json()) if rc.status_code == 200 else 0
    except Exception:
        diretos = 0

    return {
        'comissao_total': total,
        'comissao_pendente': pendente,
        'comissao_disponivel': disponivel,
        'total_lancamentos': len(rows),
        'parceiros_diretos': diretos,
    }


def arvore_rede(deriv_id, max_nivel=5):
    """Sobe a arvore de indicados, nivel por nivel -- usado na tela Rede."""
    url_c = f"{SUPABASE_URL}/rest/v1/clientes"
    url_com = f"{SUPABASE_URL}/rest/v1/comissoes_rede"
    resultado = []
    nivel_atual = [deriv_id]
    vistos = {deriv_id}

    for nivel in range(1, max_nivel + 1):
        if not nivel_atual:
            break
        ids_str = ','.join(f'"{i}"' for i in nivel_atual)
        try:
            r = requests.get(
                f"{url_c}?ref_promoter_id=in.({ids_str})&select=deriv_id,nome,ultimo_acesso,ref_promoter_id",
                headers=HEADERS
            )
            filhos = r.json() if r.status_code == 200 else []
        except Exception as e:
            print(f"Erro em arvore_rede (nivel {nivel}): {e}")
            filhos = []

        novos_ids = []
        for f in filhos:
            fid = f.get('deriv_id')
            if not fid or fid in vistos:
                continue
            vistos.add(fid)
            novos_ids.append(fid)

            comissao = 0.0
            comissao_hoje = 0.0
            try:
                from datetime import datetime, timezone
                hoje_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                rc = requests.get(
                    f"{url_com}?beneficiario_id=eq.{deriv_id}&origem_cliente_id=eq.{fid}&select=valor_usd,criado_em",
                    headers=HEADERS
                )
                if rc.status_code == 200:
                    itens = rc.json()
                    comissao = round(sum(float(v.get('valor_usd', 0)) for v in itens), 4)
                    comissao_hoje = round(sum(
                        float(v.get('valor_usd', 0)) for v in itens
                        if str(v.get('criado_em', '')).startswith(hoje_str)
                    ), 4)
            except Exception as e:
                print(f"Erro ao somar comissao de {fid}: {e}")

            resultado.append({
                'deriv_id': fid,
                'nome': f.get('nome') or '',
                'nivel': nivel,
                'comissao_gerada': comissao,
                'comissao_hoje': comissao_hoje,
                'ultimo_acesso': f.get('ultimo_acesso'),
                'promoter_id': f.get('ref_promoter_id'),
            })

        nivel_atual = novos_ids

    return resultado


def saldo_e_historico_saques(deriv_id, bot_name=None):
    """Usado na tela Saques: saldo disponivel + historico de solicitacoes."""
    url_com = f"{SUPABASE_URL}/rest/v1/comissoes_rede"
    filtro = f"?beneficiario_id=eq.{deriv_id}"
    if bot_name:
        filtro += f"&bot_name=eq.{bot_name}"
    try:
        r = requests.get(f"{url_com}{filtro}&select=valor_usd,status", headers=HEADERS)
        rows = r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"Erro em saldo_e_historico_saques (comissoes): {e}")
        rows = []

    total_gerado = round(sum(float(x.get('valor_usd', 0)) for x in rows), 4)

    url_saq = f"{SUPABASE_URL}/rest/v1/saques_rede"
    try:
        rs = requests.get(
            f"{url_saq}?beneficiario_id=eq.{deriv_id}&order=criado_em.desc&select=*",
            headers=HEADERS
        )
        historico = rs.json() if rs.status_code == 200 else []
    except Exception as e:
        print(f"Erro em saldo_e_historico_saques (saques): {e}")
        historico = []

    ja_sacado_ou_pedido = round(sum(
        float(h.get('valor_usd', 0)) for h in historico if h.get('status') in ('solicitado', 'pago')
    ), 4)

    saldo_disponivel = round(total_gerado - ja_sacado_ou_pedido, 4)

    return {
        'saldo_disponivel': max(saldo_disponivel, 0),
        'total_gerado': total_gerado,
        'total_sacado_ou_pendente': ja_sacado_ou_pedido,
        'historico': historico,
    }


def criar_solicitacao_saque(deriv_id, bot_name, valor_usd, metodo):
    """Cria um pedido de saque -- validacao de saldo fica a cargo de quem chama."""
    url = f"{SUPABASE_URL}/rest/v1/saques_rede"
    payload = {
        'bot_name': bot_name,
        'beneficiario_id': deriv_id,
        'valor_usd': float(valor_usd),
        'metodo': metodo,
        'status': 'solicitado',
    }
    try:
        r = requests.post(url, json=payload, headers={**HEADERS, 'Prefer': 'return=representation'})
        if r.status_code in (200, 201):
            return {'ok': True, 'saque': r.json()[0] if r.json() else None}
        return {'ok': False, 'erro': f'status {r.status_code}'}
    except Exception as e:
        return {'ok': False, 'erro': str(e)}


def ranking_rede(bot_name, limite=10):
    """Ranking geral (nao filtrado por indicacao pessoal) -- top ganhadores e top indicadores."""
    url_com = f"{SUPABASE_URL}/rest/v1/comissoes_rede"
    url_cli = f"{SUPABASE_URL}/rest/v1/clientes"

    try:
        r = requests.get(f"{url_com}?bot_name=eq.{bot_name}&select=beneficiario_id,valor_usd", headers=HEADERS)
        rows = r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"Erro em ranking_rede (comissoes): {e}")
        rows = []

    por_pessoa = {}
    for row in rows:
        bid = row.get('beneficiario_id')
        if not bid:
            continue
        por_pessoa[bid] = por_pessoa.get(bid, 0) + float(row.get('valor_usd', 0))

    top_ganhadores_ids = sorted(por_pessoa, key=por_pessoa.get, reverse=True)[:limite]

    try:
        rc = requests.get(f"{url_cli}?ref_promoter_id=not.is.null&bot_name=eq.{bot_name}&select=ref_promoter_id", headers=HEADERS)
        promotores = rc.json() if rc.status_code == 200 else []
    except Exception as e:
        print(f"Erro em ranking_rede (indicadores): {e}")
        promotores = []

    contagem = {}
    for p in promotores:
        pid = p.get('ref_promoter_id')
        if pid:
            contagem[pid] = contagem.get(pid, 0) + 1
    top_indicadores_ids = sorted(contagem, key=contagem.get, reverse=True)[:limite]

    ids_relevantes = list(set(top_ganhadores_ids) | set(top_indicadores_ids))
    nomes = {}
    if ids_relevantes:
        ids_str = ','.join(f'"{i}"' for i in ids_relevantes)
        try:
            rn = requests.get(f"{url_cli}?deriv_id=in.({ids_str})&select=deriv_id,nome", headers=HEADERS)
            for c in (rn.json() if rn.status_code == 200 else []):
                nomes[c['deriv_id']] = c.get('nome') or ''
        except Exception as e:
            print(f"Erro em ranking_rede (nomes): {e}")

    top_ganhadores = [
        {'deriv_id': i, 'nome': nomes.get(i, ''), 'valor': round(por_pessoa[i], 4)}
        for i in top_ganhadores_ids
    ]
    top_indicadores = [
        {'deriv_id': i, 'nome': nomes.get(i, ''), 'total_indicados': contagem[i]}
        for i in top_indicadores_ids
    ]

    return {'top_ganhadores': top_ganhadores, 'top_indicadores': top_indicadores}
