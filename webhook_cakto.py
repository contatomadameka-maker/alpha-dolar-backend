"""
WEBHOOK CAKTO — Alpha Dolar Backend
=====================================
Adaptado para a estrutura REAL da tabela produtos_liberados:
  id, deriv_id, email, produto, tipo, comprado_em, ativo, data_expiracao, nome, origem

Como usar no alpha_bot_api_production.py:
  1. Coloque este arquivo na raiz do repositório backend
  2. Adicione no topo do alpha_bot_api_production.py:
       from webhook_cakto import register_cakto_webhook
  3. Após criar app e supabase, adicione:
       register_cakto_webhook(app, supabase)

Variáveis de ambiente no Render:
  CAKTO_SECRET       — token que você define e cadastra na Cakto
  TELEGRAM_TOKEN     — já existe
  TELEGRAM_CANAL_ID  — ex: -1003524534332
"""

import os
import hmac
import hashlib
import logging
import requests
from datetime import datetime, timedelta
from flask import request, jsonify

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MAPEAMENTO: nome do produto na Cakto → chave salva no Supabase
# Os valores devem bater EXATAMENTE com o que está na coluna "produto" da tabela
# (veja na imagem: alpha-bank, ia-avancado, alpha-shield, etc.)
# ---------------------------------------------------------------------------
PRODUTOS_MAP = {
    "Alpha Bank"       : "alpha-bank",
    "IA Avançado"      : "ia-avancado",
    "IA Avancado"      : "ia-avancado",
    "Alpha Pattern"    : "alpha-pattern",
    "Alpha Clock"      : "alpha-clock",
    "Alpha Copy"       : "alpha-copy",
    "Estratégias VIP"  : "estrategias-vip",
    "Estrategias VIP"  : "estrategias-vip",
    "Premium Elite"    : "premium-elite",
    "AI Signals"       : "ai-signals",
    "Alpha IA Pro"     : "ia-pro",
    "Alpha Shield"     : "alpha-shield",
    "Alpha IA Contextual": "ia-contextual",
    "Alpha Ia Contextual": "ia-contextual",
}

# Duração em dias por tipo de plano (None = sem expiração / vitalício)
DURACAO_PLANOS = {
    "mensal"     : 30,
    "trimestral" : 90,
    "semestral"  : 180,
    "anual"      : 365,
    "vitalicio"  : None,
    "unico"      : None,
    "lifetime"   : None,
}

EMOJI_PRODUTO = {
    "alpha-bank"     : "🏦",
    "ia-avancado"    : "🧠",
    "alpha-pattern"  : "🔮",
    "alpha-clock"    : "⏰",
    "alpha-copy"     : "📡",
    "estrategias-vip": "💎",
    "premium-elite"  : "⭐",
    "ai-signals"     : "📊",
    "ia-pro"         : "✨",
    "alpha-shield"   : "🛡️",
    "ia-contextual"  : "🧠",
}


def _notificar_telegram(email, nome, produto_raw, produto_chave, tipo_plano, valor, acao, data_expiracao):
    token = os.environ.get("TELEGRAM_TOKEN", "")
    canal = os.environ.get("TELEGRAM_CANAL_ID", "-1003524534332")
    if not token:
        return

    expiracao_str = data_expiracao.strftime("%d/%m/%Y") if data_expiracao else "Vitalício ♾️"
    emoji = EMOJI_PRODUTO.get(produto_chave, "🎉")

    msg = (
        f"{emoji} *Nova Venda — Alpha Dolar!*\n\n"
        f"👤 Cliente: `{nome or email}`\n"
        f"📧 Email: `{email}`\n"
        f"📦 Produto: *{produto_raw}*\n"
        f"🗓️ Plano: {tipo_plano.capitalize()}\n"
        f"💵 Valor: R$ {valor}\n"
        f"✅ Acesso: {acao.upper()}\n"
        f"📅 Expira: {expiracao_str}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": canal, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        logger.warning(f"Erro ao enviar Telegram: {e}")


def register_cakto_webhook(app, supabase_client):
    """Registra a rota /api/webhook/cakto no app Flask."""

    @app.route("/api/webhook/cakto", methods=["POST"])
    def webhook_cakto():

        # 1. VERIFICAR ASSINATURA
        secret = os.environ.get("CAKTO_SECRET", "")
        if secret:
            payload_bytes = request.get_data()
            assinatura_recebida = request.headers.get("X-Cakto-Signature", "")
            assinatura_esperada = hmac.new(
                secret.encode(), payload_bytes, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(assinatura_recebida, assinatura_esperada):
                logger.warning("[CAKTO] Assinatura inválida")
                return jsonify({"erro": "Assinatura inválida"}), 401

        # 2. PARSEAR PAYLOAD
        dados = request.get_json(silent=True)
        if not dados:
            return jsonify({"erro": "Payload inválido"}), 400
        logger.info(f"[CAKTO] Payload: {dados}")

        # 3. FILTRAR EVENTOS — só compras aprovadas
        evento = dados.get("event", dados.get("evento", "purchase.approved"))
        eventos_validos = {
            "purchase.approved", "purchase.completed", "order.paid",
            "subscription.activated", "sale.approved", "compra_aprovada",
        }
        if evento and evento not in eventos_validos:
            logger.info(f"[CAKTO] Evento ignorado: {evento}")
            return jsonify({"status": "ignorado", "evento": evento}), 200

        # 4. EXTRAIR CAMPOS
        cliente     = dados.get("customer", dados.get("cliente", {}))
        email       = (cliente.get("email") or dados.get("email") or dados.get("buyer_email", "")).strip().lower()
        nome        = (cliente.get("name") or cliente.get("nome") or dados.get("nome", "")).strip()
        produto_raw = (dados.get("product", {}).get("name") or dados.get("produto", {}).get("nome") or dados.get("product_name") or dados.get("nome_produto", "")).strip()
        _tipo_raw = (dados.get("plan", {}).get("type") or dados.get("plano", {}).get("tipo") or dados.get("recurrence") or dados.get("plan_type") or dados.get("subscription_type") or "unico").strip().lower()
        # Normalizar termos da Cakto para nosso padrão
        _tipo_map = {
            "monthly": "mensal", "month": "mensal", "mensal": "mensal",
            "quarterly": "trimestral", "trimestral": "trimestral",
            "semiannual": "semestral", "semestral": "semestral",
            "annual": "anual", "yearly": "anual", "anual": "anual",
            "once": "unico", "one_time": "unico", "unico": "unico",
            "lifetime": "vitalicio", "vitalicio": "vitalicio",
        }
        tipo_plano = _tipo_map.get(_tipo_raw, _tipo_raw)
        valor       = dados.get("amount") or dados.get("valor") or dados.get("price", 0)

        # 5. VALIDAR EMAIL E PRODUTO
        if not email:
            return jsonify({"erro": "Email não encontrado"}), 400

        produto_chave = PRODUTOS_MAP.get(produto_raw)
        if not produto_chave:
            for nome_cakto, chave in PRODUTOS_MAP.items():
                if nome_cakto.lower() in produto_raw.lower():
                    produto_chave = chave
                    break

        if not produto_chave:
            logger.error(f"[CAKTO] Produto não mapeado: '{produto_raw}'")
            return jsonify({"erro": f"Produto não reconhecido: {produto_raw}"}), 400

        # 6. CALCULAR EXPIRAÇÃO
        dias = DURACAO_PLANOS.get(tipo_plano, None)
        data_expiracao = datetime.utcnow() + timedelta(days=dias) if dias else None

        # 7. SALVAR NO SUPABASE
        try:
            existente = (
                supabase_client.table("produtos_liberados")
                .select("id")
                .eq("email", email)
                .eq("produto", produto_chave)
                .execute()
            )

            agora = datetime.utcnow().isoformat()

            if existente.data:
                # Renovar registro existente
                update_data = {
                    "ativo"       : True,
                    "tipo"        : tipo_plano,
                    "origem"      : "cakto",
                    "comprado_em" : agora,
                    "data_expiracao": data_expiracao.isoformat() if data_expiracao else None,
                }
                if nome:
                    update_data["nome"] = nome
                supabase_client.table("produtos_liberados").update(update_data).eq("id", existente.data[0]["id"]).execute()
                acao = "renovado"
            else:
                # Inserir novo
                insert_data = {
                    "email"       : email,
                    "produto"     : produto_chave,
                    "tipo"        : tipo_plano,
                    "ativo"       : True,
                    "origem"      : "cakto",
                    "comprado_em" : agora,
                    "deriv_id"    : None,
                    "data_expiracao": data_expiracao.isoformat() if data_expiracao else None,
                }
                if nome:
                    insert_data["nome"] = nome
                supabase_client.table("produtos_liberados").insert(insert_data).execute()
                acao = "liberado"

            logger.info(f"[CAKTO] '{produto_chave}' {acao} para {email}")

        except Exception as e:
            logger.error(f"[CAKTO] Erro Supabase: {e}")
            return jsonify({"erro": "Erro interno ao salvar acesso"}), 500

        # 8. TELEGRAM
        _notificar_telegram(email, nome, produto_raw, produto_chave, tipo_plano, valor, acao, data_expiracao)

        return jsonify({"status": "ok", "acao": acao, "produto": produto_chave, "email": email}), 200

    logger.info("[CAKTO] Rota /api/webhook/cakto registrada")