"""
Alpha Dolar — Controle de Acesso ao Canal de Sinais
Gerencia assinantes, verifica acesso e expulsa não autorizados
"""
import os
import requests
from datetime import datetime
import pytz

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1003524534332")
BR_TZ = pytz.timezone("America/Sao_Paulo")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def tg(endpoint, data=None, method="GET"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{endpoint}"
    try:
        if method == "POST":
            r = requests.post(url, json=data, timeout=10)
        else:
            r = requests.get(url, params=data, timeout=10)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def db_get(tabela, filtro=""):
    url = f"{SUPABASE_URL}/rest/v1/{tabela}{filtro}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    return r.json() if r.status_code == 200 else []

def db_post(tabela, data):
    url = f"{SUPABASE_URL}/rest/v1/{tabela}"
    r = requests.post(url, headers={**HEADERS, "Prefer": "return=representation"}, json=data, timeout=10)
    return r.json()

def db_patch(tabela, filtro, data):
    url = f"{SUPABASE_URL}/rest/v1/{tabela}{filtro}"
    r = requests.patch(url, headers={**HEADERS, "Prefer": "return=representation"}, json=data, timeout=10)
    return r.json()

# ─── FUNÇÕES PRINCIPAIS ───────────────────────────────────

def listar_assinantes():
    return db_get("assinantes_signals", "?order=created_at.desc")

def buscar_assinante(telegram_id):
    result = db_get("assinantes_signals", f"?telegram_id=eq.{telegram_id}")
    return result[0] if result else None

def adicionar_assinante(nome, email, telegram_id, telegram_username="", plano="signals", dias=30):
    from datetime import timedelta
    expiracao = datetime.now(BR_TZ) + timedelta(days=dias)
    data = {
        "nome": nome,
        "email": email,
        "telegram_id": telegram_id,
        "telegram_username": telegram_username,
        "plano": plano,
        "status": "ativo",
        "data_expiracao": expiracao.isoformat(),
        "liberado_por": "admin"
    }
    result = db_post("assinantes_signals", data)
    # Envia link de convite para o assinante
    if telegram_id:
        link = gerar_link_convite()
        if link:
            tg("sendMessage", {
                "chat_id": telegram_id,
                "text": f"✅ *Acesso liberado!*\n\nOlá {nome}! Seu acesso ao canal Alpha Signals foi ativado.\n\n🔗 Clique para entrar: {link}\n\n⚠️ Este link é exclusivo para você. Não compartilhe.",
                "parse_mode": "Markdown"
            }, "POST")
    return result

def revogar_assinante(telegram_id, motivo="manual"):
    # Atualiza status no banco
    db_patch("assinantes_signals", f"?telegram_id=eq.{telegram_id}", {"status": "inativo"})
    # Expulsa do canal
    result = tg("banChatMember", {
        "chat_id": CHANNEL_ID,
        "user_id": telegram_id
    }, "POST")
    # Desbanir logo depois (só expulsar, não banir permanente)
    if result.get("ok"):
        tg("unbanChatMember", {
            "chat_id": CHANNEL_ID,
            "user_id": telegram_id,
            "only_if_banned": True
        }, "POST")
        # Notifica o usuário
        tg("sendMessage", {
            "chat_id": telegram_id,
            "text": f"⚠️ Seu acesso ao canal Alpha Signals foi encerrado.\n\nMotivo: {motivo}\n\nPara renovar acesse: alphadolar.online",
            "parse_mode": "HTML"
        }, "POST")
    return result

def gerar_link_convite():
    result = tg("createChatInviteLink", {
        "chat_id": CHANNEL_ID,
        "member_limit": 1,
        "creates_join_request": False
    }, "POST")
    if result.get("ok"):
        return result["result"]["invite_link"]
    return None

def verificar_expiracao():
    """Verifica assinantes expirados e expulsa do canal"""
    agora = datetime.now(BR_TZ).isoformat()
    expirados = db_get("assinantes_signals", 
        f"?status=eq.ativo&data_expiracao=lt.{agora}")
    expulsos = []
    for a in expirados:
        if a.get("telegram_id"):
            revogar_assinante(a["telegram_id"], "Assinatura expirada")
            expulsos.append(a["nome"])
    return expulsos

def status_canal():
    """Retorna info do canal"""
    return tg("getChat", {"chat_id": CHANNEL_ID})

__all__ = [
    "listar_assinantes", "buscar_assinante", "adicionar_assinante",
    "revogar_assinante", "gerar_link_convite", "verificar_expiracao", "status_canal"
]
