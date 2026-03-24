from flask import Flask, send_from_directory, request, jsonify
import os, json, sqlite3 as _sq

def _get_adb():
    db = '/home/dirlei/alpha-dolar-2.0/analytics.db'
    conn = _sq.connect(db)
    conn.row_factory = _sq.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS quiz_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz TEXT, session_id TEXT, step INTEGER, answer TEXT,
        ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS quiz_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz TEXT, session_id TEXT UNIQUE, started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_step INTEGER DEFAULT 1, completed INTEGER DEFAULT 0, completed_at TIMESTAMP)''')
    conn.commit()
    return conn

app = Flask(__name__)

WEB_FOLDER  = os.environ.get('WEB_FOLDER', '/home/dirlei/alpha-dolar-2.0/web')
ROOT_FOLDER = os.environ.get('ROOT_FOLDER', '/home/dirlei/alpha-dolar-2.0')
IMG_FOLDER  = os.path.join(WEB_FOLDER, 'img')

@app.route('/')
def index():
    return send_from_directory(WEB_FOLDER, 'index.html')

@app.route('/admin')
def admin():
    return send_from_directory(WEB_FOLDER, 'admin.html')

@app.route('/login')
def login():
    return send_from_directory(WEB_FOLDER, 'login.html')

@app.route('/home')
def home():
    return send_from_directory(WEB_FOLDER, 'index.html')

@app.route('/dashboard')
def dashboard():
    return send_from_directory(WEB_FOLDER, 'dashboard-fixed.html')

@app.route('/videos')
def videos():
    if os.path.exists(os.path.join(WEB_FOLDER, 'videos.html')):
        return send_from_directory(WEB_FOLDER, 'videos.html')
    return send_from_directory(ROOT_FOLDER, 'vídeos.html')

@app.route('/landing')
def landing():
    return send_from_directory(WEB_FOLDER, 'landing.html')

@app.route('/parceiro')
def parceiro():
    return send_from_directory(WEB_FOLDER, 'parceiro.html')

@app.route('/trader')
def trader():
    return send_from_directory(WEB_FOLDER, 'trader-admin.html')

# ✅ ROTA PARA IMAGENS WIN/LOSS — usada pelo Telegram

@app.route('/guia-estrategias-vip')
def guia_estrategias_vip():
    return send_from_directory('web', 'guia-estrategias-vip.html')

@app.route('/guia-premium-elite')
def guia_premium_elite():
    return send_from_directory('web', 'guia-premium-elite.html')

@app.route('/quiz-parceiro')
def quiz_parceiro():
    return send_from_directory('web', 'quiz-parceiro.html')

@app.route('/quiz')
def quiz():
    return send_from_directory('web', 'quiz.html')

@app.route('/api/salvar-cliente', methods=['POST'])
def salvar_cliente():
    import sqlite3 as sq
    data = request.json or {}
    try:
        # Salva no SQLite local
        conn = sq.connect('/home/dirlei/alpha-dolar-2.0/alpha_dolar.db')
        conn.execute('''INSERT INTO clientes (deriv_id, nome, email, token_demo, token_real, account_type, ultimo_acesso, bot_name)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(deriv_id) DO UPDATE SET
                token_demo = excluded.token_demo,
                token_real = excluded.token_real,
                ultimo_acesso = CURRENT_TIMESTAMP,
                bot_name = excluded.bot_name
        ''', (
            data.get('deriv_id'), data.get('nome'), data.get('email'),
            data.get('token_demo'), data.get('token_real'),
            data.get('account_type', 'demo'), data.get('bot_name', 'default')
        ))
        conn.commit(); conn.close()
    except Exception as e:
        print('SQLite erro:', e)
    # Salva no Supabase também
    try:
        import urllib.request, json as _json
        SUPA_URL = 'https://urlthgicnomfbyklesou.supabase.co'
        SUPA_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVybHRoZ2ljbm9tZmJ5a2xlc291Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzA2NzIwNiwiZXhwIjoyMDg4NjQzMjA2fQ.ZcPJry5CAxteeM2x-vymjXTFQ3EWZast0SHw-YRh1vo'
        payload = _json.dumps({
            'deriv_id': data.get('deriv_id'),
            'nome': data.get('nome'),
            'email': data.get('email'),
            'token_demo': data.get('token_demo'),
            'token_real': data.get('token_real'),
            'account_type': data.get('account_type', 'demo'),
            'bot_name': data.get('bot_name', 'default')
        }).encode()
        req = urllib.request.Request(
            SUPA_URL + '/rest/v1/clientes',
            data=payload, method='POST'
        )
        req.add_header('Content-Type', 'application/json')
        req.add_header('apikey', SUPA_KEY)
        req.add_header('Authorization', 'Bearer ' + SUPA_KEY)
        req.add_header('Prefer', 'resolution=merge-duplicates')
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print('Supabase erro:', e)
    return jsonify({'ok': True})

@app.route('/api/operacoes', methods=['GET'])
def api_operacoes():
    import sqlite3 as sq
    bot_name = request.args.get('bot_name', '')
    deriv_id = request.args.get('deriv_id', '')
    limit    = int(request.args.get('limit', 100))
    try:
        conn = sq.connect('/home/dirlei/alpha-dolar-2.0/alpha_dolar.db')
        conn.row_factory = sq.Row
        if bot_name and deriv_id:
            rows = conn.execute('SELECT * FROM operacoes WHERE bot_name=? AND cliente_id=? ORDER BY criado_em DESC LIMIT ?', (bot_name, deriv_id, limit)).fetchall()
        elif bot_name:
            rows = conn.execute('SELECT * FROM operacoes WHERE bot_name=? ORDER BY criado_em DESC LIMIT ?', (bot_name, limit)).fetchall()
        elif deriv_id:
            rows = conn.execute('SELECT * FROM operacoes WHERE cliente_id=? ORDER BY criado_em DESC LIMIT ?', (deriv_id, limit)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM operacoes ORDER BY criado_em DESC LIMIT ?', (limit,)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/clientes', methods=['GET'])
def api_clientes():
    import sqlite3 as sq
    bot_name = request.args.get('bot_name', '')
    try:
        conn = sq.connect('/home/dirlei/alpha-dolar-2.0/alpha_dolar.db')
        conn.row_factory = sq.Row
        if bot_name:
            rows = conn.execute('SELECT * FROM clientes WHERE bot_name=? ORDER BY ultimo_acesso DESC', (bot_name,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM clientes ORDER BY ultimo_acesso DESC').fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/quiz/track', methods=['POST'])
def quiz_track():
    try:
        d = request.json or {}
        conn = _get_adb()
        step = int(d.get('step',1))
        completed = int(d.get('completed',0))
        conn.execute('''INSERT INTO quiz_sessions (quiz,session_id,last_step,completed,completed_at)
            VALUES (?,?,?,?,CASE WHEN ?=1 THEN CURRENT_TIMESTAMP ELSE NULL END)
            ON CONFLICT(session_id) DO UPDATE SET
            last_step=MAX(last_step,excluded.last_step),
            completed=MAX(completed,excluded.completed),
            completed_at=CASE WHEN excluded.completed=1 AND completed_at IS NULL THEN CURRENT_TIMESTAMP ELSE completed_at END
        ''', (d.get('quiz',''), d.get('session_id',''), step, completed, completed))
        conn.execute('INSERT INTO quiz_events (quiz,session_id,step,answer) VALUES (?,?,?,?)',
            (d.get('quiz',''), d.get('session_id',''), step, d.get('answer','')))
        conn.commit(); conn.close()
        return jsonify({'ok':True})
    except Exception as e:
        return jsonify({'ok':False,'erro':str(e)}), 200

@app.route('/api/quiz/stats', methods=['GET'])
def quiz_stats():
    if request.args.get('key') != 'alpha2026':
        return jsonify({'erro':'nao autorizado'}), 403
    try:
        conn = _get_adb()
        result = {}
        for q in ['quiz','quiz-parceiro']:
            total = conn.execute('SELECT COUNT(DISTINCT session_id) as n FROM quiz_sessions WHERE quiz=?',(q,)).fetchone()['n']
            completed = conn.execute('SELECT COUNT(*) as n FROM quiz_sessions WHERE quiz=? AND completed=1',(q,)).fetchone()['n']
            by_step = conn.execute('SELECT last_step,COUNT(*) as n FROM quiz_sessions WHERE quiz=? GROUP BY last_step ORDER BY last_step',(q,)).fetchall()
            result[q] = {
                'total': total, 'completed': completed,
                'conversion': round(completed/total*100,1) if total>0 else 0,
                'by_step': [{'step':r['last_step'],'count':r['n']} for r in by_step],
            }
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'erro':str(e)}), 500

@app.route('/checkout')
def checkout():
    return send_from_directory('web', 'checkout.html')

@app.route('/live')
def live():
    from flask import redirect, request, make_response
    # Se tem a chave — libera e redireciona para URL limpa
    if request.args.get('key') == 'alpha2026':
        resp = make_response(send_from_directory(WEB_FOLDER, 'live.html'))
        resp.set_cookie('live_access', 'alpha2026', max_age=86400, httponly=True)
        return resp
    # Se tem cookie valido — acesso liberado
    if request.cookies.get('live_access') == 'alpha2026':
        return send_from_directory(WEB_FOLDER, 'live.html')
    # Sem acesso — vai para login
    return redirect('/login')

@app.route('/img/<path:filename>')
def serve_img(filename):
    return send_from_directory(IMG_FOLDER, filename)

@app.route('/<path:path>')
def serve_file(path):
    if os.path.exists(os.path.join(WEB_FOLDER, path)):
        return send_from_directory(WEB_FOLDER, path)
    return send_from_directory(ROOT_FOLDER, path)

if __name__ == '__main__':
    app.run()
