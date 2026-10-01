"""
JOB DIÁRIO — Desativa assinaturas expiradas
Rodar no PythonAnywhere Scheduled Tasks: todo dia às 03:00
Comando: python3 /home/dirlei/repo_backend/job_expiracao.py
"""

import requests
from datetime import datetime, timezone

SUPABASE_URL = 'https://urlthgicnomfbyklesou.supabase.co'
SUPABASE_KEY = (__import__('os').environ.get('SUPABASE_KEY') or (open(__import__('os').path.expanduser('~/.alpha_supabase_key')).read().strip() if __import__('os').path.exists(__import__('os').path.expanduser('~/.alpha_supabase_key')) else ''))

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}

def desativar_expirados():
    agora = datetime.now(timezone.utc).isoformat()

    # Busca registros ativos com data_expiracao no passado
    url = (
        f"{SUPABASE_URL}/rest/v1/produtos_liberados"
        f"?ativo=eq.true&data_expiracao=lt.{agora}&data_expiracao=not.is.null"
    )
    r = requests.get(url, headers=HEADERS, timeout=10)
    expirados = r.json() if r.status_code == 200 else []

    if not expirados:
        print(f"[{agora}] Nenhuma assinatura expirada.")
        return

    # Desativa cada um
    for item in expirados:
        patch_url = f"{SUPABASE_URL}/rest/v1/produtos_liberados?id=eq.{item['id']}"
        requests.patch(patch_url, headers=HEADERS, json={"ativo": False}, timeout=10)
        print(f"❌ Desativado: {item['email']} — {item['produto']} (expirou em {item['data_expiracao']})")

    print(f"✅ Total desativados: {len(expirados)}")

if __name__ == '__main__':
    desativar_expirados()
