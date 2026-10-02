"""ADMIN-API-V1: o admin.html fala com o Supabase por aqui. A chave fica so no servidor."""
import os, hmac, time
import requests
from flask import request, jsonify

def register_admin_api(app):
    URL = os.environ.get('SUPABASE_URL', 'https://urlthgicnomfbyklesou.supabase.co').rstrip('/')

    def _senha_ok(t):
        s = os.environ.get('ADMIN_SENHA', '')
        return bool(s) and bool(t) and hmac.compare_digest(s.encode(), str(t).encode())

    @app.route('/api/admin/login', methods=['POST'])
    def admin_login():
        t = (request.get_json(silent=True) or {}).get('senha', '')
        if _senha_ok(t):
            return jsonify({'ok': True})
        time.sleep(1.5)
        return jsonify({'ok': False, 'erro': 'senha incorreta' if os.environ.get('ADMIN_SENHA') else 'ADMIN_SENHA nao definida no Render'}), 401

    @app.route('/api/admin/supa', methods=['POST'])
    def admin_supa():
        _tk = request.headers.get('X-Admin-Token', '') or (request.get_json(silent=True) or {}).get('token', '')  # ADMIN-API-V2
        if not _senha_ok(_tk):
            time.sleep(1)
            return jsonify({'erro': 'nao autorizado'}), 401
        d = request.get_json(silent=True) or {}
        path = str(d.get('path', ''))
        method = str(d.get('method') or 'GET').upper()
        if not path.startswith('/rest/v1/') or '..' in path or method not in ('GET', 'POST', 'PATCH', 'DELETE'):
            return jsonify({'erro': 'pedido invalido'}), 400
        key = os.environ.get('SUPABASE_KEY', '')
        if not key:
            return jsonify({'erro': 'SUPABASE_KEY nao definida no Render'}), 500
        h = {'apikey': key, 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
        if d.get('prefer'):
            h['Prefer'] = str(d['prefer'])
        r = requests.request(method, URL + path, headers=h, data=d.get('body'), timeout=20)
        return (r.content, r.status_code, {'Content-Type': r.headers.get('Content-Type', 'application/json')})
