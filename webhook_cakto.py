"""
WEBHOOK CAKTO v2 (CAKTO-V2) — Alpha Dolar Backend
Formato real da Cakto: {"secret": "...", "event": "purchase_approved", "data": {customer, product, offer, amount, status, ...}}
Eventos: purchase_approved, subscription_renewed -> libera/renova
         refund, chargeback -> desliga o acesso
         subscription_canceled -> mantem ate vencer (so registra)
Todo aviso recebido fica salvo na tabela webhook_log (para conferir no admin).
Variaveis no Render:
  CAKTO_SECRET     — mesma chave secreta cadastrada no webhook da Cakto (opcional, recomendado)
  CAKTO_PRODUTOS   — opcional, JSON {"<id da oferta ou nome>": "plano-pro", ...} para casos especiais
  ADMIN_SENHA      — ja existe; protege GET /api/webhook/cakto/log
"""
import os
import json
import hmac
import hashlib
import logging
import requests
from datetime import datetime, timedelta
from flask import request, jsonify

logger = logging.getLogger(__name__)

# nomes antigos (ferramentas avulsas) -> chave em produtos_liberados
PRODUTOS_MAP = {
    "Alpha Bank": "alpha-bank",
    "IA Avançado": "ia-avancado", "IA Avancado": "ia-avancado",
    "Alpha Pattern": "alpha-pattern",
    "Alpha Clock": "alpha-clock",
    "Alpha Copy": "alpha-copy",
    "Estratégias VIP": "estrategias-vip", "Estrategias VIP": "estrategias-vip",
    "Premium Elite": "premium-elite",
    "AI Signals": "ai-signals",
    "Alpha IA Pro": "ia-pro",
    "Alpha Shield": "alpha-shield",
    "Alpha IA Contextual": "ia-contextual", "Alpha Ia Contextual": "ia-contextual",
}

EVENTOS_LIBERA = {"purchase_approved", "subscription_renewed", "purchase.approved", "purchase.completed",
                  "order.paid", "subscription.activated", "sale.approved", "compra_aprovada"}
EVENTOS_REMOVE = {"refund", "chargeback", "purchase.refunded", "purchase.chargeback"}

EMOJI = {"plano-sinais": "📊", "plano-pro": "✨", "plano-elite": "⭐", "premium-elite": "⭐", "ia-pro": "✨",
         "ia-avancado": "🧠", "ia-contextual": "🧠", "ai-signals": "📊", "estrategias-vip": "💎"}


def _sem_acento(s):
    t = (s or "").lower()
    for a, b in (("á", "a"), ("à", "a"), ("ã", "a"), ("â", "a"), ("é", "e"), ("ê", "e"), ("í", "i"), ("ó", "o"), ("õ", "o"), ("ô", "o"), ("ú", "u"), ("ç", "c")):
        t = t.replace(a, b)
    return t


def _produto_chave(produto_nome, oferta_nome, oferta_id):
    extra = {}
    try:
        extra = json.loads(os.environ.get("CAKTO_PRODUTOS", "") or "{}")
    except Exception:
        extra = {}
    for k in (str(oferta_id or ""), oferta_nome or "", produto_nome or ""):
        if k and k in extra:
            return extra[k]
    if produto_nome in PRODUTOS_MAP:
        return PRODUTOS_MAP[produto_nome]
    for nome, chave in PRODUTOS_MAP.items():
        if nome.lower() in (produto_nome or "").lower():
            return chave
    # planos novos: procura a palavra no nome do produto e da oferta
    tudo = " " + _sem_acento((produto_nome or "") + " " + (oferta_nome or "")) + " "
    for sep in "-_|/·.,()":
        tudo = tudo.replace(sep, " ")
    if " elite " in tudo:
        return "plano-elite"
    if " pro " in tudo:
        return "plano-pro"
    if " sinais " in tudo or " signals " in tudo:
        return "plano-sinais"
    return None


def _dias(produto_nome, oferta_nome, tipo_produto):
    t = _sem_acento((oferta_nome or "") + " " + (produto_nome or ""))
    if "vitalic" in t or "lifetime" in t or "vida toda" in t:
        return None
    if "anual" in t or "12 meses" in t:
        return 365
    if "semest" in t or "6 meses" in t:
        return 180
    if "trimest" in t or "3 meses" in t:
        return 90
    # mensal, assinatura ou nome sem prazo: 30 dias (o admin pode estender)
    return 30


def _telegram(email, nome, produto_raw, chave, plano_txt, valor, acao, exp):
    token = os.environ.get("TELEGRAM_TOKEN", "")
    canal = os.environ.get("TELEGRAM_CANAL_ID", "-1003524534332")
    if not token:
        return
    exp_txt = exp.strftime("%d/%m/%Y") if exp else "Vitalício ♾️"
    msg = (f"{EMOJI.get(chave, '🎉')} *Venda Alpha Dolar — {acao.upper()}*\n\n"
           f"👤 Cliente: `{nome or email}`\n📧 Email: `{email}`\n📦 Produto: *{produto_raw}*\n"
           f"🗓️ Oferta: {plano_txt}\n💵 Valor: R$ {valor}\n📅 Expira: {exp_txt}")
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": canal, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        logger.warning(f"[CAKTO] Telegram: {e}")


def _log(sb, evento, email, produto, chave, resultado, dados):
    try:
        limpo = dict(dados or {})
        limpo.pop("secret", None)
        sb.table("webhook_log").insert({"origem": "cakto", "evento": evento, "email": email, "produto": produto,
                                        "chave": chave, "resultado": resultado, "payload": limpo,
                                        "recebido_em": datetime.utcnow().isoformat()}).execute()
    except Exception as e:
        print(f"[CAKTO] webhook_log nao gravou ({e}) — rode o SQL da tabela webhook_log")


def register_cakto_webhook(app, supabase_client):
    """Registra /api/webhook/cakto (POST da Cakto) e /api/webhook/cakto/log (GET para o admin)."""

    @app.route("/api/webhook/cakto", methods=["POST"])
    def webhook_cakto():
        dados = request.get_json(silent=True) or {}
        if not dados:
            print("[CAKTO] aviso sem JSON")
            return jsonify({"erro": "Payload inválido"}), 400

        # 1. chave secreta: a Cakto manda no campo "secret" do corpo
        secret = os.environ.get("CAKTO_SECRET", "")
        if secret:
            ok = hmac.compare_digest(str(dados.get("secret", "")), secret)
            if not ok:
                assin = request.headers.get("X-Cakto-Signature", "")
                if assin:
                    esperado = hmac.new(secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
                    ok = hmac.compare_digest(assin, esperado)
            if not ok:
                print("[CAKTO] chave secreta diferente — confira CAKTO_SECRET no Render e na Cakto")
                _log(supabase_client, dados.get("event"), None, None, None, "recusado: chave secreta", dados)
                return jsonify({"erro": "Chave secreta inválida"}), 401

        # 2. campos (formato novo dentro de "data"; aceita o antigo tambem)
        evento = str(dados.get("event") or dados.get("evento") or "").strip()
        d = dados.get("data") if isinstance(dados.get("data"), dict) else dados
        cli = d.get("customer") or d.get("cliente") or {}
        prod = d.get("product") or d.get("produto") or {}
        ofe = d.get("offer") or d.get("oferta") or {}
        email = str(cli.get("email") or d.get("email") or d.get("buyer_email") or "").strip().lower()
        nome = str(cli.get("name") or cli.get("nome") or "").strip()
        produto_raw = str(prod.get("name") or prod.get("nome") or d.get("product_name") or "").strip()
        oferta_nome = str(ofe.get("name") or ofe.get("nome") or "").strip()
        oferta_id = ofe.get("id") or ""
        valor = d.get("amount") or d.get("baseAmount") or ofe.get("price") or 0
        print(f"[CAKTO] evento={evento} email={email} produto='{produto_raw}' oferta='{oferta_nome}' status={d.get('status')}")

        if evento not in EVENTOS_LIBERA and evento not in EVENTOS_REMOVE:
            _log(supabase_client, evento, email, produto_raw, None, "ignorado", dados)
            return jsonify({"status": "ignorado", "evento": evento}), 200
        if not email:
            _log(supabase_client, evento, None, produto_raw, None, "erro: sem email", dados)
            return jsonify({"erro": "Email não encontrado"}), 400

        chave = _produto_chave(produto_raw, oferta_nome, oferta_id)
        if not chave:
            print(f"[CAKTO] produto NAO mapeado: '{produto_raw}' / oferta '{oferta_nome}' ({oferta_id})")
            _log(supabase_client, evento, email, produto_raw, None, "pendente: produto nao mapeado", dados)
            return jsonify({"status": "pendente", "erro": f"Produto não reconhecido: {produto_raw}"}), 200

        tb = supabase_client.table("produtos_liberados")
        try:
            ex = tb.select("id,data_expiracao").eq("email", email).eq("produto", chave).execute().data or []
            agora = datetime.utcnow()

            # reembolso / chargeback: desliga
            if evento in EVENTOS_REMOVE:
                for r in ex:
                    tb.update({"ativo": False, "origem": "cakto-" + evento}).eq("id", r["id"]).execute()
                print(f"[CAKTO] acesso '{chave}' DESLIGADO para {email} ({evento})")
                _log(supabase_client, evento, email, produto_raw, chave, "desligado", dados)
                _telegram(email, nome, produto_raw, chave, oferta_nome or "-", valor, "desligado (" + evento + ")", None)
                return jsonify({"status": "ok", "acao": "desligado", "produto": chave}), 200

            dias = _dias(produto_raw, oferta_nome, prod.get("type"))
            exp = None
            if dias:
                base = agora
                if ex and ex[0].get("data_expiracao"):
                    try:
                        atual = datetime.fromisoformat(str(ex[0]["data_expiracao"]).replace("Z", "").split("+")[0])
                        if atual > agora:
                            base = atual  # renovacao soma em cima do que ainda falta
                    except Exception:
                        pass
                exp = base + timedelta(days=dias)
            tipo = "vitalicio" if dias is None else {30: "mensal", 90: "trimestral", 180: "semestral", 365: "anual"}.get(dias, "mensal")
            reg = {"ativo": True, "tipo": tipo, "origem": "cakto", "comprado_em": agora.isoformat(),
                   "data_expiracao": exp.isoformat() if exp else None}
            if nome:
                reg["nome"] = nome
            if ex:
                tb.update(reg).eq("id", ex[0]["id"]).execute()
                acao = "renovado"
            else:
                reg.update({"email": email, "produto": chave, "deriv_id": None})
                tb.insert(reg).execute()
                acao = "liberado"
            print(f"[CAKTO] '{chave}' {acao} para {email} ate {exp.date() if exp else 'vitalicio'}")
            _log(supabase_client, evento, email, produto_raw, chave, acao, dados)
        except Exception as e:
            print(f"[CAKTO] ERRO Supabase: {e}")
            _log(supabase_client, evento, email, produto_raw, chave, f"erro: {e}"[:300], dados)
            return jsonify({"erro": "Erro interno ao salvar acesso"}), 500

        _telegram(email, nome, produto_raw, chave, oferta_nome or tipo, valor, acao, exp)
        return jsonify({"status": "ok", "acao": acao, "produto": chave, "email": email}), 200

    @app.route("/api/webhook/cakto/log", methods=["GET"])
    def webhook_cakto_log():
        senha = os.environ.get("ADMIN_SENHA", "")
        if not senha or request.args.get("senha", "") != senha:
            return jsonify({"erro": "senha"}), 401
        try:
            r = supabase_client.table("webhook_log").select("*").order("recebido_em", desc=True).limit(50).execute()
            return jsonify({"ok": True, "avisos": r.data or []})
        except Exception as e:
            return jsonify({"ok": False, "erro": str(e)}), 500

    print("[CAKTO] Rotas /api/webhook/cakto (v2) e /api/webhook/cakto/log registradas")
