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
