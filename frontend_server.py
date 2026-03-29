from flask import Flask, send_from_directory
import os

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

@app.route('/live')
def live():
    return send_from_directory(WEB_FOLDER, 'live.html')

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
