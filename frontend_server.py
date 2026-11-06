import requests
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


# ===== DOMINIO-DIRLEI-V1: dirleiluis.online mostra so as paginas de anuncio =====
from flask import request as _rq, redirect as _rd
_DL_HOSTS = ('dirleiluis.online', 'www.dirleiluis.online')
_DL_PAGINAS = ('/links', '/quiz', '/landing', '/seja-parceiro', '/parceiro', '/videos', '/ao-vivo', '/ao-vivo-b', '/ao-vivo-c', '/ao-vivo-d', '/ao-vivo-e', '/ao-vivo-f', '/ao-vivo-g', '/sala')
_DL_ARQUIVOS = ('.js', '.css', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.mp3', '.mp4', '.webm', '.json', '.txt', '.xml')
@app.before_request
def _dominio_dirlei():
    host = (_rq.host or '').split(':')[0].lower()
    if host not in _DL_HOSTS:
        return None
    p = _rq.path or '/'
    if p == '/':
        return _rd('/links', code=302)
    if p.startswith('/api/') or p.startswith('/static/') or p.lower().endswith(_DL_ARQUIVOS):
        return None
    if any(p == x or p.startswith(x) for x in _DL_PAGINAS):
        return None
    # qualquer outra pagina (login, painel, loja...) abre no alphadolar.online
    q = _rq.query_string.decode('utf-8', 'ignore')
    return _rd('https://alphadolar.online' + p + ('?' + q if q else ''), code=302)

WEB_FOLDER  = os.environ.get('WEB_FOLDER', '/home/dirlei/alpha-dolar-2.0/web')
ROOT_FOLDER = os.environ.get('ROOT_FOLDER', '/home/dirlei/alpha-dolar-2.0')
IMG_FOLDER  = os.path.join(WEB_FOLDER, 'img')

@app.route('/')
def index():
    return send_from_directory(WEB_FOLDER, 'index.html')

@app.route('/afiliados')
def pagina_afiliados():
    return send_from_directory(WEB_FOLDER, 'afiliados.html')

@app.route('/admin')
def admin():
    return send_from_directory(WEB_FOLDER, 'admin.html')

@app.route('/login')
def login():
    return send_from_directory(WEB_FOLDER, 'auth.html')

@app.route('/conectar-deriv')
def conectar_deriv():
    return send_from_directory(WEB_FOLDER, 'login.html')

@app.route('/home')
def home():
    return send_from_directory(WEB_FOLDER, 'index.html')

@app.route('/dashboard')
def dashboard():
    return send_from_directory(WEB_FOLDER, 'dashboard-fixed.html')

@app.route('/dashboard-v3')
def dashboard_v3():
    return send_from_directory(WEB_FOLDER, 'dashboard-v3.html')

@app.route('/dashboard.live')
def dashboard_live():
    return send_from_directory(WEB_FOLDER, 'live.html')

@app.route('/videos')
def videos():
    if os.path.exists(os.path.join(WEB_FOLDER, 'videos.html')):
        return send_from_directory(WEB_FOLDER, 'videos.html')
    return send_from_directory(ROOT_FOLDER, 'vídeos.html')

@app.route('/landing')
def landing():
    return send_from_directory(WEB_FOLDER, 'landing.html')

@app.route('/landing2')
def landing2():
    return send_from_directory(WEB_FOLDER, 'landing2.html')

@app.route('/links')
def links():
    return send_from_directory(WEB_FOLDER, 'links.html')

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

@app.route('/seja-parceiro')
def seja_parceiro():
    return send_from_directory('web', 'seja-parceiro.html')

@app.route('/quiz-parceiro')
def quiz_parceiro():
    return send_from_directory('web', 'quiz-parceiro.html')

@app.route('/ao-vivo-<v>')
def ao_vivo_var(v):  # TESTE-AB-AOVIVO-V1
    if v not in ('b', 'c', 'd', 'e', 'f', 'g'):
        return ('Pagina nao encontrada', 404)
    return send_from_directory('web', 'ao-vivo-%s.html' % v)

@app.route('/ao-vivo')
def ao_vivo():
    return send_from_directory('web', 'ao-vivo.html')

@app.route('/quiz')
def quiz():
    return send_from_directory('web', 'quiz.html')

@app.route('/api/oauth/ws-url', methods=['POST'])
def oauth_ws_url():
    try:
        import urllib.request as urlreq
        import json as _json
        data = request.json
        access_token = data.get('access_token', '')
        client_id = data.get('client_id', '')
        account_id = data.get('account_id', '')

        req = urlreq.Request(
            f'https://api.derivws.com/trading/v1/options/accounts/{account_id}/otp',
            method='POST',
            headers={
                'Authorization': 'Bearer ' + access_token,
                'Deriv-App-ID': client_id,
                'Content-Type': 'application/json'
            }
        )
        with urlreq.urlopen(req, timeout=10) as r:
            otp_data = _json.loads(r.read())

        return jsonify({'success': True, 'otp_data': otp_data})
    except Exception as e:
        body = b''
        if hasattr(e, 'read'):
            try: body = e.read()
            except: pass
        try: body = body.decode()
        except: body = str(body)
        return jsonify({'success': False, 'error': str(e), 'detail': body}), 500


@app.route('/api/pro/analisar', methods=['POST'])
def pro_analisar():
    data = request.json or {}
    digits = data.get('digits', [])
    ct = data.get('ct', 'DIGITEVEN')
    modo = data.get('modo', 'fixo')

    if len(digits) < 20:
        return jsonify({'score':0,'entrar':False,'desc':'Coletando...','barrier':None,'ct':ct})

    def analisar_tipo(ct, d):
        u20=d[-20:]; u10=d[-10:]; u30=d[-30:] if len(d)>=30 else d[:]
        pares=sum(1 for x in u20 if x%2==0); rp=pares/20
        media_u10=sum(u10)/10; last=d[-1]; last_par=last%2
        streak=1
        for i in range(len(d)-2, max(len(d)-9,-1), -1):
            if d[i]%2==last_par: streak+=1
            else: break
        score=0; barrier=None; desc=''
        if ct=='DIGITEVEN':
            s1=rp if rp>=0.60 else (rp*0.85 if rp>=0.55 else rp*0.5)
            s2=min(0.55+streak*0.05,0.80) if streak>=4 and last_par==1 else (0.58 if streak<=2 and last_par==0 else 0.45)
            s3=0.65 if rp>=0.55 else 0.40
            score=s1*0.45+s2*0.35+s3*0.20; desc=f'Par:{round(rp*100)}% Str:{streak}'
        elif ct=='DIGITODD':
            ri=1-rp
            s1=ri if ri>=0.60 else (ri*0.85 if ri>=0.55 else ri*0.5)
            s2=min(0.55+streak*0.05,0.80) if streak>=4 and last_par==0 else (0.58 if streak<=2 and last_par==1 else 0.45)
            s3=0.65 if ri>=0.55 else 0.40
            score=s1*0.45+s2*0.35+s3*0.20; desc=f'Impar:{round(ri*100)}% Str:{streak}'
        elif ct=='DIGITOVER':
            baixos=sum(1 for x in u10 if x<5)
            s1=0.75 if baixos>=7 else (0.65 if baixos>=6 else (0.55 if baixos>=5 else 0.30))
            seqB=0
            for i in range(len(d)-1, max(len(d)-6,-1), -1):
                if d[i]<5: seqB+=1
                else: break
            s2=0.70 if seqB>=3 else (0.60 if seqB>=2 else 0.40)
            s3=0.70 if media_u10<4 else (0.60 if media_u10<4.5 else 0.35)
            score=s1*0.40+s2*0.35+s3*0.25; desc=f'Baixos:{baixos}/10'
        elif ct=='DIGITUNDER':
            altos=sum(1 for x in u10 if x>=5)
            s1=0.75 if altos>=7 else (0.65 if altos>=6 else (0.55 if altos>=5 else 0.30))
            seqA=0
            for i in range(len(d)-1, max(len(d)-6,-1), -1):
                if d[i]>=5: seqA+=1
                else: break
            s2=0.70 if seqA>=3 else (0.60 if seqA>=2 else 0.40)
            s3=0.70 if media_u10>5.5 else (0.60 if media_u10>5 else 0.35)
            score=s1*0.40+s2*0.35+s3*0.25; desc=f'Altos:{altos}/10'
        elif ct=='DIGITMATCH':
            freq=[0]*10
            for x in u30: freq[x]+=1
            max_f=max(freq); dig_f=freq.index(max_f); pct=max_f/len(u30)
            s1=0.75 if pct>=0.20 else (0.65 if pct>=0.15 else (0.55 if pct>=0.12 else 0.35))
            recente=sum(1 for x in d[-5:] if x==dig_f)
            s2=0.70 if recente>=2 else (0.55 if recente>=1 else 0.35)
            b1=sum(1 for x in u10 if x==dig_f); b2=sum(1 for x in u20[:10] if x==dig_f)
            s3=0.70 if b1>=2 and b2>=2 else (0.55 if b1>=2 or b2>=2 else 0.35)
            score=s1*0.40+s2*0.35+s3*0.25; barrier=dig_f; desc=f'Digito:{dig_f} Freq:{round(pct*100)}%'
        elif ct=='DIGITDIFF':
            freq=[0]*10
            for x in u20: freq[x]+=1
            max_f=max(freq); entropia=max_f/20
            s1=0.75 if entropia<=0.15 else (0.65 if entropia<=0.20 else (0.55 if entropia<=0.25 else 0.35))
            last_dig=d[-1]; rep=sum(1 for x in d[-5:-1] if x==last_dig)
            s2=0.70 if rep==0 else (0.50 if rep==1 else 0.30)
            score=s1*0.45+s2*0.35+0.50*0.20; barrier=last_dig; desc=f'Entr:{round(entropia*100)}%'
        return {'score':round(score*100), 'barrier':barrier, 'desc':desc}

    if modo == 'auto':
        tipos=['DIGITEVEN','DIGITODD','DIGITOVER','DIGITUNDER','DIGITMATCH','DIGITDIFF']
        melhor={'score':0,'ct':'DIGITEVEN','barrier':None,'desc':''}
        todos={}
        for t in tipos:
            r=analisar_tipo(t,digits)
            todos[t]={'score':r['score'],'desc':r['desc']}
            if r['score']>melhor['score']:
                melhor={'score':r['score'],'ct':t,'barrier':r['barrier'],'desc':r['desc']}
        return jsonify({'score':melhor['score'],'entrar':melhor['score']>=45,'desc':'AUTO->'+melhor['ct']+' '+melhor['desc'],'barrier':melhor['barrier'],'ct':melhor['ct'],'todos':todos})
    else:
        r=analisar_tipo(ct,digits)
        return jsonify({'score':r['score'],'entrar':r['score']>=52,'desc':r['desc'],'barrier':r['barrier'],'ct':ct})

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
        SUPA_KEY = (__import__('os').environ.get('SUPABASE_KEY') or (open(__import__('os').path.expanduser('~/.alpha_supabase_key')).read().strip() if __import__('os').path.exists(__import__('os').path.expanduser('~/.alpha_supabase_key')) else ''))
        payload = _json.dumps({
            'deriv_id': data.get('deriv_id'),
            'nome': data.get('nome'),
            'email': data.get('email'),
            'token_demo': data.get('token_demo'),
            'token_real': data.get('token_real'),
            'account_type': data.get('account_type', 'demo'),
            'bot_name': data.get('bot_name', 'default')
        }).encode()
        from datetime import datetime as _dt, timezone, timedelta
        payload_dict = json.loads(payload.decode())
        _tz_br = timezone(timedelta(hours=-3))
        payload_dict['ultimo_acesso'] = _dt.now(_tz_br).isoformat()
        payload = json.dumps(payload_dict).encode()
        req = urllib.request.Request(
            SUPA_URL + '/rest/v1/clientes?on_conflict=deriv_id',
            data=payload, method='POST'
        )
        req.add_header('Content-Type', 'application/json')
        req.add_header('apikey', SUPA_KEY)
        req.add_header('Authorization', 'Bearer ' + SUPA_KEY)
        req.add_header('Prefer', 'resolution=merge-duplicates,return=minimal')
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
        for q in ['quiz','quiz-parceiro','ao-vivo','ao-vivo-b','ao-vivo-c','ao-vivo-d','ao-vivo-e','ao-vivo-f','ao-vivo-g','sala']:
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
    # LIVE-SEM-LOGIN-V1: sem key/cookie continua bloqueado, mas vai para a home (nao para o login)
    return redirect('/home')

@app.route('/img/<path:filename>')
def serve_img(filename):
    return send_from_directory(IMG_FOLDER, filename)



@app.route('/api/deriv/profile', methods=['GET'])
def deriv_profile():
    bearer = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not bearer:
        return jsonify({'error': 'No token'}), 401
    try:
        res = requests.get('https://api.derivws.com/trading/v1/options/accounts',
            headers={'Authorization': f'Bearer {bearer}', 'Deriv-App-ID': '34lv1PuWzjElEuwWcDLyr'})
        return jsonify(res.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/oauth/callback', methods=['POST'])
def oauth_callback():
    import traceback
    try:
        data = request.get_json()
        code = data.get('code')
        code_verifier = data.get('code_verifier')
        redirect_uri = data.get('redirect_uri', 'https://alphadolar.online/')
        APP_ID = '34lv1PuWzjElEuwWcDLyr'
        token_res = requests.post('https://auth.deriv.com/oauth2/token', data={
            'grant_type': 'authorization_code',
            'client_id': APP_ID,
            'code': code,
            'code_verifier': code_verifier,
            'redirect_uri': redirect_uri
        }, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        token_data = token_res.json()
        access_token = token_data.get('access_token')
        if not access_token:
            return jsonify({'error': token_data.get('error_description', 'Token error')}), 400
        return jsonify({'access_token': access_token, 'token_type': 'bearer'})
    except Exception as e:
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/ctx-ia', methods=['POST'])
def ctx_ia_proxy():
    try:
        import urllib.request as urlreq
        import json as _json
        payload = _json.dumps(request.get_json(silent=True) or {}).encode()
        req = urlreq.Request(
            'https://alpha-dolar-backend.onrender.com/api/ctx-ia',
            data=payload, method='POST'
        )
        req.add_header('Content-Type', 'application/json')
        with urlreq.urlopen(req, timeout=25) as r:
            data = _json.loads(r.read())
        return jsonify(data)
    except Exception as e:
        body = b''
        if hasattr(e, 'read'):
            try: body = e.read()
            except: pass
        try: body = body.decode()
        except: body = str(body)
        return jsonify({'erro': str(e) + (' | ' + body if body else '')}), 500

@app.route('/api/mult-ia', methods=['POST'])
def mult_ia_proxy():
    try:
        import urllib.request as urlreq
        import json as _json
        payload = _json.dumps(request.get_json(silent=True) or {}).encode()
        req = urlreq.Request(
            'https://alpha-dolar-backend.onrender.com/api/mult-ia',
            data=payload, method='POST'
        )
        req.add_header('Content-Type', 'application/json')
        with urlreq.urlopen(req, timeout=25) as r:
            data = _json.loads(r.read())
        return jsonify(data)
    except Exception as e:
        body = b''
        if hasattr(e, 'read'):
            try: body = e.read()
            except: pass
        try: body = body.decode()
        except: body = str(body)
        return jsonify({'erro': str(e) + (' | ' + body if body else '')}), 500



# PIXEL-ROTAS-V1 · PIXEL-ROTAS-V3 — pixel do Facebook por página (painel em /pixels.html)
# V2: vários pixels por página · V3: API de Conversões (token fica só aqui no servidor, nunca vai para a página)
def _px_dir():
    import os
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(d, exist_ok=True)
    return d

def _px_caminho():
    import os
    return os.path.join(_px_dir(), 'pixels.json')

def _px_jler(nome):
    import json, os
    try:
        with open(os.path.join(_px_dir(), nome), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _px_jgrava(nome, obj):
    import json, os
    p = os.path.join(_px_dir(), nome)
    with open(p + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(p + '.tmp', p)
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass

def _px_ler():
    return _px_jler('pixels.json')

_PX_ADM_OK = {}

def _px_chave_ok(k):
    # PX-ADMIN-V1: aceita a chave do painel OU a senha do admin (conferida no servidor do Render, guardada 15 min)
    import os, hmac, time, json, hashlib, urllib.request
    k = str(k or '')
    if not k:
        return False
    try:
        with open(os.path.expanduser('~/.alpha_pixel_key'), encoding='utf-8') as f:
            certa = f.read().strip()
        if certa and hmac.compare_digest(k, certa):
            return True
    except Exception:
        pass
    h = hashlib.sha256(k.encode()).hexdigest()
    if _PX_ADM_OK.get(h, 0) > time.time():
        return True
    try:
        rq = urllib.request.Request('https://alpha-dolar-backend.onrender.com/api/admin/login', data=json.dumps({'senha': k}).encode(),
                                    headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(rq, timeout=10) as r:
            ok = bool(json.loads(r.read().decode() or '{}').get('ok'))
    except Exception:
        ok = False
    if ok:
        _PX_ADM_OK[h] = time.time() + 900
    return ok

def _px_ids(pg):
    import re
    cfg = _px_ler()
    s = (cfg.get(pg) or cfg.get('padrao') or '')
    return [x for x in re.split(r'\D+', s) if len(x) >= 10][:5]

_PX_LOG = []

def _px_capi_envia(ids, ev, eid, url, ip, ua, fbp, fbc, dados):
    import json, time, urllib.request, urllib.parse
    tk = _px_jler('pixel_tokens.json')
    teste = (tk.get('_teste') or '').strip()
    ud = {'client_ip_address': ip, 'client_user_agent': ua}
    if fbp: ud['fbp'] = fbp
    if fbc: ud['fbc'] = fbc
    item = {'event_name': ev, 'event_time': int(time.time()), 'event_id': eid, 'action_source': 'website',
            'event_source_url': url, 'user_data': ud}
    if dados: item['custom_data'] = dados
    for pid in ids:
        token = (tk.get(pid) or '').strip()
        if not token:
            continue
        corpo = {'data': [item]}
        if teste: corpo['test_event_code'] = teste
        try:
            rq = urllib.request.Request('https://graph.facebook.com/v19.0/%s/events?access_token=%s' % (pid, urllib.parse.quote(token)),
                                        data=json.dumps(corpo).encode(), headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(rq, timeout=8) as r:
                res = 'OK %s' % r.status
        except Exception as e:
            msg = ''
            try:
                msg = json.loads(e.read().decode())['error']['message'][:140]
            except Exception:
                msg = str(e)[:140]
            res = 'ERRO ' + msg
        _PX_LOG.insert(0, {'h': time.strftime('%d/%m %H:%M:%S'), 'pixel': pid[-6:], 'ev': ev, 'res': res})
        del _PX_LOG[30:]

@app.route('/api/pixel', methods=['GET'])
def api_pixel_get():
    from flask import request, jsonify
    pg = (request.args.get('pg') or '').strip()
    ids = _px_ids(pg)
    tk = _px_jler('pixel_tokens.json')
    r = jsonify({'id': ','.join(ids), 'capi': any(tk.get(i) for i in ids)})
    r.headers['Cache-Control'] = 'no-store'
    return r

@app.route('/api/pixel/evento', methods=['POST'])
def api_pixel_evento():
    import re, threading
    from flask import request, jsonify
    d = request.get_json(silent=True, force=True) or {}
    ev = str(d.get('ev') or '')
    if ev not in ('PageView', 'Lead', 'InitiateCheckout', 'CompleteRegistration', 'ViewContent'):
        return jsonify({'ok': False}), 400
    pg = re.sub(r'[^a-z0-9-]', '', str(d.get('pg') or '').lower())[:40]
    ids = _px_ids(pg)
    if not ids:
        return jsonify({'ok': True, 'enviado': 0})
    eid = re.sub(r'[^A-Za-z0-9._-]', '', str(d.get('id') or ''))[:64]
    url = str(d.get('url') or '')[:500]
    ip = (request.headers.get('X-Real-IP') or (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip() or request.remote_addr or '')
    ua = (request.headers.get('User-Agent') or '')[:400]
    fbp = re.sub(r'[^A-Za-z0-9._-]', '', str(d.get('fbp') or ''))[:120]
    fbc = re.sub(r'[^A-Za-z0-9._-]', '', str(d.get('fbc') or ''))[:400]
    dados = d.get('dados') if isinstance(d.get('dados'), dict) else {}
    dados = {str(k)[:40]: str(v)[:120] for k, v in list(dados.items())[:6]}
    threading.Thread(target=_px_capi_envia, args=(ids, ev, eid, url, ip, ua, fbp, fbc, dados), daemon=True).start()
    return jsonify({'ok': True})

@app.route('/api/pixel/todos', methods=['POST'])
def api_pixel_todos():
    from flask import request, jsonify
    d = request.get_json(silent=True) or {}
    if not _px_chave_ok(d.get('chave')):
        return jsonify({'ok': False, 'erro': 'chave errada'}), 403
    tk = _px_jler('pixel_tokens.json')
    return jsonify({'ok': True, 'pixels': _px_ler(), 'tokens': {k: True for k, v in tk.items() if v and k != '_teste'},
                    'teste': tk.get('_teste') or '', 'log': _PX_LOG[:15]})

@app.route('/api/pixel/salvar', methods=['POST'])
def api_pixel_salvar():
    import re
    from flask import request, jsonify
    d = request.get_json(silent=True) or {}
    if not _px_chave_ok(d.get('chave')):
        return jsonify({'ok': False, 'erro': 'chave errada'}), 403
    novos = d.get('pixels') or {}
    limpo = {}
    for k, v in novos.items():
        k = re.sub(r'[^a-z0-9-]', '', str(k).lower())[:40]
        v = ','.join([x for x in re.split(r'\D+', str(v or '')) if len(x) >= 10][:5])
        if k and v:
            limpo[k] = v
    _px_jgrava('pixels.json', limpo)
    tk = _px_jler('pixel_tokens.json')
    for pid, tok in (d.get('tokens') or {}).items():
        pid = re.sub(r'\D', '', str(pid))[:20]
        tok = str(tok or '').strip()
        if not pid:
            continue
        if tok == '-':
            tk.pop(pid, None)
        elif tok:
            if not re.fullmatch(r'[A-Za-z0-9_-]{40,600}', tok):
                return jsonify({'ok': False, 'erro': 'token do pixel %s parece incompleto' % pid}), 400
            tk[pid] = tok
    if 'teste' in d:
        t = re.sub(r'[^A-Za-z0-9]', '', str(d.get('teste') or ''))[:20]
        if t:
            tk['_teste'] = t
        else:
            tk.pop('_teste', None)
    _px_jgrava('pixel_tokens.json', tk)
    return jsonify({'ok': True, 'pixels': limpo, 'tokens': {k: True for k, v in tk.items() if v and k != '_teste'}})



# VIDEO-ROTAS-V1 — páginas de vídeo para o funil (alphadolar.online/v/<nome>) com capa no WhatsApp e botão para a plataforma
def _vd_ler():
    # VIDEO-FIX-V1: arquivo proprio; o videos.json ja era usado pela pagina /videos
    d = _px_jler('funil_videos.json')
    return d if isinstance(d, dict) and isinstance(d.get('lista'), list) else {'lista': []}

def _vd_grava(d):
    _px_jgrava('funil_videos.json', d)

def _vd_yt(u):
    import re
    u = str(u or '').strip()
    for p in (r'youtu\.be/([A-Za-z0-9_-]{11})', r'[?&]v=([A-Za-z0-9_-]{11})', r'/shorts/([A-Za-z0-9_-]{11})', r'/embed/([A-Za-z0-9_-]{11})', r'/live/([A-Za-z0-9_-]{11})'):
        m = re.search(p, u)
        if m:
            return m.group(1)
    return u if re.fullmatch(r'[A-Za-z0-9_-]{11}', u) else ''

def _vd_slug(s):
    import re, unicodedata
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:40]

@app.route('/v/<nome>', methods=['GET'])
def video_pagina(nome):
    import os, html
    from flask import abort, Response
    d = _vd_ler()
    v = next((x for x in d['lista'] if x.get('slug') == nome), None)
    if not v:
        abort(404)
    v['views'] = int(v.get('views') or 0) + 1
    try:
        _vd_grava(d)
    except Exception:
        pass
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'v-tpl.html'), encoding='utf-8').read()
    e = lambda s: html.escape(str(s or ''), quote=True)
    capa = v.get('capa') or ('https://i.ytimg.com/vi/%s/hqdefault.jpg' % v['yt'])
    trocas = {'%%TITULO%%': e(v.get('titulo')), '%%TEXTO%%': e(v.get('texto')).replace('\n', '<br>'), '%%DESC%%': e((v.get('texto') or '')[:150]),
              '%%YT%%': e(v['yt']), '%%CAPA%%': e(capa), '%%BOTAO%%': e(v.get('botao') or 'Abrir a plataforma'),
              '%%CLIQUE%%': '/api/v/clique?s=' + e(v['slug']), '%%FORMATO%%': 'vert' if v.get('vertical') else 'hor',
              '%%URL%%': 'https://alphadolar.online/v/' + e(v['slug'])}
    for k, val in trocas.items():
        tpl = tpl.replace(k, val)
    r = Response(tpl, mimetype='text/html')
    r.headers['Cache-Control'] = 'no-store'
    return r

@app.route('/api/v/clique', methods=['GET'])
def video_clique():
    from flask import request, redirect
    d = _vd_ler()
    s = str(request.args.get('s') or '')
    v = next((x for x in d['lista'] if x.get('slug') == s), None)
    if not v:
        return redirect('https://alphadolar.online/login')
    v['cliques'] = int(v.get('cliques') or 0) + 1
    try:
        _vd_grava(d)
    except Exception:
        pass
    link = v.get('link') or 'https://alphadolar.online/login'
    return redirect(link if link.startswith('https://') else 'https://alphadolar.online/login')

@app.route('/api/videos/lista', methods=['POST'])
def videos_lista():
    from flask import request, jsonify
    if not _px_chave_ok((request.get_json(silent=True) or {}).get('chave')):
        return jsonify({'ok': False, 'erro': 'chave errada'}), 403
    return jsonify({'ok': True, 'lista': _vd_ler()['lista']})

@app.route('/api/videos/salvar', methods=['POST'])
def videos_salvar():
    import time, random, string
    from flask import request, jsonify
    b = request.get_json(silent=True) or {}
    if not _px_chave_ok(b.get('chave')):
        return jsonify({'ok': False, 'erro': 'chave errada'}), 403
    v = b.get('video') or {}
    yt = _vd_yt(v.get('youtube'))
    if not yt:
        return jsonify({'ok': False, 'erro': 'Não reconheci o link do YouTube.'}), 400
    titulo = str(v.get('titulo') or '').strip()[:120]
    if not titulo:
        return jsonify({'ok': False, 'erro': 'Coloque um título.'}), 400
    link = str(v.get('link') or '').strip()[:500] or 'https://alphadolar.online/login'
    if not link.startswith('https://'):
        return jsonify({'ok': False, 'erro': 'O link do botão precisa começar com https://'}), 400
    capa = str(v.get('capa') or '').strip()[:500]
    if capa and not capa.startswith('https://'):
        capa = ''
    d = _vd_ler()
    antigo = next((x for x in d['lista'] if x.get('slug') == v.get('slug')), None) if v.get('slug') else None
    if antigo:
        item = antigo
    else:
        base = _vd_slug(v.get('nome') or titulo) or 'video'
        slug = base
        while any(x.get('slug') == slug for x in d['lista']):
            slug = base + '-' + ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(3))
        item = {'slug': slug, 'criado': time.strftime('%d/%m/%Y'), 'views': 0, 'cliques': 0}
        d['lista'].insert(0, item)
    item.update({'yt': yt, 'titulo': titulo, 'texto': str(v.get('texto') or '').strip()[:600], 'botao': str(v.get('botao') or '').strip()[:40] or 'Abrir a plataforma',
                 'link': link, 'capa': capa, 'vertical': bool(v.get('vertical')) if 'vertical' in v else ('/shorts/' in str(v.get('youtube') or ''))})
    _vd_grava(d)
    return jsonify({'ok': True, 'video': item, 'lista': d['lista']})

@app.route('/api/videos/apagar', methods=['POST'])
def videos_apagar():
    from flask import request, jsonify
    b = request.get_json(silent=True) or {}
    if not _px_chave_ok(b.get('chave')):
        return jsonify({'ok': False, 'erro': 'chave errada'}), 403
    d = _vd_ler()
    d['lista'] = [x for x in d['lista'] if x.get('slug') != b.get('slug')]
    _vd_grava(d)
    return jsonify({'ok': True, 'lista': d['lista']})


@app.route('/<path:path>')
def serve_file(path):
    if os.path.exists(os.path.join(WEB_FOLDER, path)):
        return send_from_directory(WEB_FOLDER, path)
    return send_from_directory(ROOT_FOLDER, path)


# ═══ VIDEOS-V1: Alpha Academy — videos por tema (salvo em data/videos.json) ═══
import json as _vj, os as _vo, re as _vre, time as _vtime, threading as _vth, urllib.request as _vurl
from flask import request as _vreq, jsonify as _vjson

_VIDEOS_FILE = _vo.path.join(_vo.path.dirname(_vo.path.abspath(__file__)), 'data', 'videos.json')
_VIDEOS_ADMINS = {'DOT92009972', 'ROT92611002'}      # contas Deriv que podem editar os videos
_VIDEOS_LOCK = _vth.Lock()
_VIDEOS_CACHE_ADM = {}                               # token -> (eh_admin, expira)
_VIDEOS_PADRAO = {'temas': [
    {'id': 1, 'nome': 'Introdução', 'emo': '🚀'}, {'id': 2, 'nome': 'Depósito e Saque', 'emo': '💰'},
    {'id': 3, 'nome': 'Robôs e IA', 'emo': '🤖'}, {'id': 4, 'nome': 'Gestão de risco', 'emo': '🛡️'}], 'videos': []}

def _videos_ler():
    try:
        with open(_VIDEOS_FILE, encoding='utf-8') as f:
            return _vj.load(f)
    except Exception:
        return _VIDEOS_PADRAO

def _videos_eh_admin():
    sh = _vreq.headers.get('X-Admin-Senha', '').strip()
    if sh:
        try:
            import hashlib as _vh, hmac as _vhm
            alvo = open(_vo.path.join(_vo.path.dirname(_VIDEOS_FILE), 'videos_admin.txt')).read().strip()
            if _vhm.compare_digest(_vh.sha256(sh.encode()).hexdigest(), alvo):
                return True
        except Exception as e:
            print('VIDEOS: erro senha admin:', e)
    auth = _vreq.headers.get('Authorization', '')
    tk = auth[7:].strip() if auth.startswith('Bearer ') else ''
    if not tk or len(tk) > 4000:
        return False
    agora = _vtime.time()
    c = _VIDEOS_CACHE_ADM.get(tk)
    if c and c[1] > agora:
        return c[0]
    ok = False
    try:
        rq = _vurl.Request('https://api.derivws.com/trading/v1/options/accounts',
                           headers={'Authorization': 'Bearer ' + tk, 'Deriv-App-ID': '34lv1PuWzjElEuwWcDLyr'})
        with _vurl.urlopen(rq, timeout=10) as r:
            contas = _vj.loads(r.read().decode('utf-8')).get('data') or []
        ok = any(str(a.get('account_id', '')) in _VIDEOS_ADMINS for a in contas)
    except Exception as e:
        print('VIDEOS: falha ao validar admin:', e)
    _VIDEOS_CACHE_ADM[tk] = (ok, agora + 600)
    return ok

def _videos_limpar(d):
    if not isinstance(d, dict):
        raise ValueError('formato invalido')
    temas, videos = d.get('temas'), d.get('videos')
    if not isinstance(temas, list) or not isinstance(videos, list) or len(temas) > 100 or len(videos) > 2000:
        raise ValueError('listas invalidas')
    T, ids = [], set()
    for t in temas:
        tid = int(t.get('id'))
        T.append({'id': tid, 'nome': str(t.get('nome', ''))[:60].strip() or 'Tema', 'emo': str(t.get('emo', '🎓'))[:8]})
        ids.add(tid)
    V = []
    for v in videos:
        yt = str(v.get('yt', ''))
        if not _vre.fullmatch(r'[\w-]{11}', yt) or int(v.get('tema')) not in ids:
            continue
        V.append({'id': int(v.get('id')), 'tema': int(v.get('tema')), 'yt': yt,
                  'tit': str(v.get('tit', ''))[:120].strip() or 'Vídeo', 'desc': str(v.get('desc', ''))[:300].strip(),
                  'dest': bool(v.get('dest'))})
    return {'temas': T, 'videos': V}

@app.route('/api/videos', methods=['GET', 'POST'])
def alpha_videos_api():
    if _vreq.method == 'GET':
        r = _vjson(_videos_ler())
        r.headers['Cache-Control'] = 'no-store'
        return r
    if not _videos_eh_admin():
        return _vjson({'erro': 'sem permissao'}), 403
    try:
        dados = _videos_limpar(_vreq.get_json(force=True, silent=False))
    except Exception as e:
        return _vjson({'erro': 'dados invalidos: %s' % e}), 400
    with _VIDEOS_LOCK:
        _vo.makedirs(_vo.path.dirname(_VIDEOS_FILE), exist_ok=True)
        tmp = _VIDEOS_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            _vj.dump(dados, f, ensure_ascii=False, indent=1)
        _vo.replace(tmp, _VIDEOS_FILE)
    return _vjson({'ok': True, 'videos': len(dados['videos'])})

@app.route('/api/videos/admin', methods=['GET'])
def alpha_videos_admin():
    r = _vjson({'admin': _videos_eh_admin()})
    r.headers['Cache-Control'] = 'no-store'
    return r

if __name__ == '__main__':
    app.run()
