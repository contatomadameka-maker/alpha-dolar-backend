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

def _headers():
    """Retorna headers atualizados com as variáveis de ambiente"""
    key = os.environ.get('SUPABASE_KEY', SUPABASE_KEY)
    return {
        'apikey': key,
        'Authorization': f'Bearer {key}',
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
        'bot_name': data.get('bot_name', ''),
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
        'Content-Type': 'application/json'
    }
    url = f"{SUPABASE_URL}/rest/v1/operacoes?order=criado_em.desc&limit=500"
    if bot_name:
        url += f"&bot_name=ilike.{bot_name}"
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
    payload = {'nome': data.get('nome'), 'dono': data.get('dono'), 'deriv_id': data.get('deriv_id'), 'status': data.get('status','ativo')}
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
    import requests as req, json
    headers = {**_headers(), 'Content-Type': 'application/json', 'Prefer': 'resolution=merge-duplicates'}
    payload = {
        'bot_type': bot_type,
        'estado': json.dumps(estado),
        'atualizado_em': 'now()'
    }
    r = req.post(f"{SUPABASE_URL}/rest/v1/bot_estado", json=payload, headers=headers)
    return r.status_code in [200, 201]

def recuperar_estado_bot(bot_type):
    """Recupera estado do bot do Supabase"""
    import requests as req, json
    r = req.get(f"{SUPABASE_URL}/rest/v1/bot_estado?bot_type=eq.{bot_type}&limit=1", headers=_headers())
    if r.status_code == 200 and r.json():
        try:
            return json.loads(r.json()[0]['estado'])
        except:
            return None
    return None

def limpar_estado_bot(bot_type):
    """Remove estado do bot (quando parado manualmente)"""
    import requests as req
    r = req.delete(f"{SUPABASE_URL}/rest/v1/bot_estado?bot_type=eq.{bot_type}", headers=_headers())
    return r.status_code in [200, 204]


# ==================== USUÁRIOS / PLANOS ====================

def verificar_usuario(deriv_id):
    """Verifica se usuário tem acesso ativo na plataforma"""
    import requests as req
    SUPABASE_URL_L = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY_L = os.environ.get('SUPABASE_KEY', '')
    headers = {'apikey': SUPABASE_KEY_L, 'Authorization': f'Bearer {SUPABASE_KEY_L}'}
    try:
        r = req.get(f"{SUPABASE_URL_L}/rest/v1/usuarios?deriv_id=eq.{deriv_id}&limit=1", headers=headers)
        if r.status_code == 200 and r.json():
            u = r.json()[0]
            return {
                'existe': True,
                'plano': u.get('plano', 'free'),
                'status': u.get('status', 'inativo'),
                'ativo': u.get('status') == 'ativo',
                'nome': u.get('nome', ''),
            }
    except: pass
    return {'existe': False, 'ativo': False, 'plano': 'free'}

def registrar_ou_atualizar_usuario(deriv_id, nome='', email=''):
    """Registra novo usuário ou atualiza último acesso"""
    import requests as req
    from datetime import datetime
    SUPABASE_URL_L = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY_L = os.environ.get('SUPABASE_KEY', '')
    headers = {
        'apikey': SUPABASE_KEY_L,
        'Authorization': f'Bearer {SUPABASE_KEY_L}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates,return=representation'
    }
    payload = {
        'deriv_id': deriv_id,
        'nome': nome,
        'email': email,
        'ultimo_acesso': datetime.utcnow().isoformat()
    }
    try:
        r = req.post(f"{SUPABASE_URL_L}/rest/v1/usuarios", json=payload, headers=headers)
        return r.status_code in [200, 201]
    except: return False

def listar_usuarios():
    """Lista todos os usuários para o admin"""
    import requests as req
    SUPABASE_URL_L = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY_L = os.environ.get('SUPABASE_KEY', '')
    headers = {'apikey': SUPABASE_KEY_L, 'Authorization': f'Bearer {SUPABASE_KEY_L}'}
    try:
        r = req.get(f"{SUPABASE_URL_L}/rest/v1/usuarios?order=ultimo_acesso.desc", headers=headers)
        if r.status_code == 200:
            return r.json()
    except: pass
    return []

def atualizar_plano_usuario(deriv_id, plano, status='ativo', dias=30):
    """Atualiza plano do usuário (chamado após pagamento)"""
    import requests as req
    from datetime import datetime, timedelta
    SUPABASE_URL_L = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY_L = os.environ.get('SUPABASE_KEY', '')
    headers = {
        'apikey': SUPABASE_KEY_L,
        'Authorization': f'Bearer {SUPABASE_KEY_L}',
        'Content-Type': 'application/json'
    }
    expiracao = (datetime.utcnow() + timedelta(days=dias)).isoformat()
    payload = {'plano': plano, 'status': status, 'data_expiracao': expiracao}
    try:
        r = req.patch(
            f"{SUPABASE_URL_L}/rest/v1/usuarios?deriv_id=eq.{deriv_id}",
            json=payload, headers=headers
        )
        return r.status_code in [200, 204]
    except: return False


# ─── SISTEMA DE INDICAÇÃO / REDE DE AFILIADOS (modelo A — cliente final) ─────
import random as _random
import string as _string

NIVEIS_PCT_REDE = [0.15, 0.08, 0.04, 0.02, 0.01]


def _gerar_ref_code():
    return ''.join(_random.choices(_string.ascii_lowercase + _string.digits, k=8))


def resolver_referral(deriv_id, bot_name, ref_code_recebido=None):
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
    if not markup_usd or markup_usd <= 0:
        return
    url = f"{SUPABASE_URL}/rest/v1/clientes"
    try:
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
