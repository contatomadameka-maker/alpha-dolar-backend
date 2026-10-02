"""PLANO-API-V1: qual plano o cliente tem + trava de conta real no /api/bot/start."""
import os, time
from datetime import datetime, timezone
import requests
from flask import request, jsonify

NIVEL = {'free': 0, 'sinais': 1, 'pro': 2, 'elite': 3}
NOME_NIVEL = {v: k for k, v in NIVEL.items()}
# produto (coluna "produto" de produtos_liberados) -> plano inteiro
PLANO_DO_PRODUTO = {'plano-sinais': 'sinais', 'plano-pro': 'pro', 'plano-elite': 'elite', 'premium-elite': 'elite'}
# produtos antigos vendidos avulsos -> ferramentas que eles liberam
FERRAMENTAS_DO_PRODUTO = {
    'ia-pro': ['ia-pro'], 'alpha-ia-pro': ['ia-pro'], 'ia-avancado': ['ia-avancado'], 'ia-contextual': ['ia-contextual'],
    'ai-signals': ['sinais'], 'estrategias-vip': ['estrategias-vip', 'estrategias-premium'],
}
# nivel minimo de cada ferramenta na CONTA REAL (na demo tudo e livre)
NIVEL_FERRAMENTA = {
    'ia-simples': 0, 'grafico': 0, 'manual': 0,
    'sinais': 1, 'auto-trading': 1, 'digitos': 1,
    'ia-pro': 2, 'ia-avancado': 2, 'ia-contextual': 3, 'touch': 2, 'global': 3, 'estrategias-premium': 2,
    'enxame': 3, 'esquadrao': 3, 'regente': 3, 'perfil': 3, 'estrategias-vip': 3,
}
PREMIUM = ('mega_alpha_1', 'mega_alpha_2', 'mega_alpha_3', 'alpha_elite', 'alpha_nexus')
_CACHE = {}


def _expirado(exp, agora):
    if not exp:
        return False
    try:
        dt = datetime.fromisoformat(str(exp).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt < agora
    except Exception:
        return False


def _eh_real(d):
    """O pedido de /api/bot/start e para conta real?"""
    for k in ('account_type', 'conta', 'tipo_conta', 'modo_conta', 'account'):
        if str(d.get(k, '')).strip().lower() == 'real':
            return True
    if d.get('is_demo') is False or d.get('demo') is False or d.get('is_virtual') in (0, False):
        return True
    did = str(d.get('deriv_id', '')).strip().upper()
    return did.startswith(('ROT', 'CR', 'MF', 'MLT', 'MX'))


def _ferramenta_do_start(d):
    bt = str(d.get('bot_type', '')).lower()
    tudo = ' '.join(str(v).lower() for v in d.values() if isinstance(v, (str, int, float)))
    if bt.startswith('enxame'):
        return 'enxame'
    if bt.startswith('unidade'):
        return 'esquadrao'
    if 'avancado' in tudo:
        return 'ia-avancado'
    if any(p in tudo for p in PREMIUM):
        return 'estrategias-premium'
    return 'ia-simples'


def register_plano_api(app, supabase_client=None):
    URL = os.environ.get('SUPABASE_URL', 'https://urlthgicnomfbyklesou.supabase.co').rstrip('/')
    APP_ID = os.environ.get('DERIV_APP_ID', '34lv1PuWzjElEuwWcDLyr')

    def _key():
        k = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or ''
        if not k:
            try:
                k = open(os.path.expanduser('~/.alpha_supabase_key')).read().strip()
            except Exception:
                k = getattr(supabase_client, 'supabase_key', '') or ''
        return k

    def _sb(path):
        k = _key()
        r = requests.get(URL + '/rest/v1/' + path, headers={'apikey': k, 'Authorization': 'Bearer ' + k}, timeout=15)
        if not r.ok:
            print('[PLANO] supabase', r.status_code, r.text[:200])
            raise RuntimeError('supabase %s' % r.status_code)
        return r.json()

    def _contas_do_token(tk):
        """Confere na Deriv quais contas pertencem a este login (nao da para inventar um deriv_id)."""
        if not tk:
            return []
        if tk in _CACHE and time.time() - _CACHE[tk][0] < 600:
            return _CACHE[tk][1]
        try:
            r = requests.get('https://api.derivws.com/trading/v1/options/accounts',
                             headers={'Authorization': 'Bearer ' + tk, 'Deriv-App-ID': APP_ID}, timeout=12)
            ids = [a.get('account_id') for a in (r.json().get('data') or []) if a.get('account_id')] if r.ok else []
        except Exception:
            ids = []
        if ids:
            _CACHE[tk] = (time.time(), ids)
        return ids

    def _liberados():
        return [x.strip().lower() for x in os.environ.get('ALPHA_LIBERADOS', '').split(',') if x.strip()]

    def plano_por_ids(ids, email_informado=''):
        ids = [i for i in ids if i]
        lib = _liberados()
        emails_ligados = set()
        if ids:
            for c in _sb('clientes?select=email&deriv_id=in.(' + ','.join(ids) + ')'):
                if c.get('email'):
                    emails_ligados.add(c['email'].strip().lower())
        if any(i.lower() in lib for i in ids) or any(e in lib for e in emails_ligados):
            return {'plano': 'elite', 'nivel': 3, 'ferramentas': [], 'produtos': [], 'motivo': 'liberado'}
        emails = set(emails_ligados)
        if email_informado:
            emails.add(email_informado)
        filtro = []
        if ids:
            filtro.append('deriv_id.in.(' + ','.join(ids) + ')')
        if emails:
            filtro.append('email.in.(' + ','.join('"' + e.replace('"', '') + '"' for e in emails) + ')')
        if not filtro:
            return {'plano': 'free', 'nivel': 0, 'ferramentas': [], 'produtos': []}
        rows = _sb('produtos_liberados?select=produto,ativo,data_expiracao&or=(' + ','.join(filtro) + ')')
        agora = datetime.now(timezone.utc)
        nivel, ferr, prods = 0, set(), []
        for r in rows if isinstance(rows, list) else []:
            if r.get('ativo') is False or _expirado(r.get('data_expiracao'), agora):
                continue
            p = str(r.get('produto', '')).strip().lower()
            prods.append(p)
            if p in PLANO_DO_PRODUTO:
                nivel = max(nivel, NIVEL[PLANO_DO_PRODUTO[p]])
            ferr.update(FERRAMENTAS_DO_PRODUTO.get(p, []))
        return {'plano': NOME_NIVEL[nivel], 'nivel': nivel, 'ferramentas': sorted(ferr), 'produtos': prods}

    def pode(info, ferramenta):
        return info['nivel'] >= NIVEL_FERRAMENTA.get(ferramenta, 0) or ferramenta in info['ferramentas']

    _TOQUE = {}
    def _tocar(ids):  # ULTIMO-ACESSO-V1: atualiza clientes.ultimo_acesso (no maximo 1x a cada 10 min)
        k = ','.join(sorted(ids))
        if time.time() - _TOQUE.get(k, 0) < 600: return
        _TOQUE[k] = time.time()
        try:
            kk = _key()
            requests.patch(URL + '/rest/v1/clientes?deriv_id=in.(' + ','.join(ids) + ')',
                           headers={'apikey': kk, 'Authorization': 'Bearer ' + kk, 'Content-Type': 'application/json', 'Prefer': 'return=minimal'},
                           json={'ultimo_acesso': datetime.now(timezone.utc).isoformat()}, timeout=8)
        except Exception as e:
            print('[PLANO] ultimo_acesso falhou:', e)

    @app.route('/api/plano', methods=['POST'])
    def plano_do_cliente():
        d = request.get_json(silent=True) or {}
        ids = _contas_do_token(str(d.get('token', '')).strip())
        if not ids:
            return jsonify({'ok': True, 'plano': 'free', 'nivel': 0, 'ferramentas': [], 'contas': [], 'motivo': 'login nao confirmado'})
        _tocar(ids)
        try:
            info = plano_por_ids(ids, str(d.get('email', '')).strip().lower())
        except Exception as e:
            return jsonify({'ok': False, 'erro': str(e)}), 503
        info.update({'ok': True, 'contas': ids, 'niveis': NIVEL_FERRAMENTA})
        return jsonify(info)

    # ===== OPS-API-V1: grava as operacoes de todas as ferramentas (navegador) na tabela operacoes =====
    _BOTS = {'t': 0, 'pct': {}}
    def _markup_pct(bot_name):
        if time.time() - _BOTS['t'] > 600:
            try:
                _BOTS['pct'] = {b.get('nome'): float(b.get('markup_pct') or 0) for b in _sb('bots?select=nome,markup_pct')}
                _BOTS['t'] = time.time()
            except Exception:
                pass
        return _BOTS['pct'].get(bot_name, 0.0)

    _CLI = {}
    def _cliente_de(ids):
        k = ','.join(sorted(ids))
        if k in _CLI and time.time() - _CLI[k][0] < 600:
            return _CLI[k][1]
        row = {}
        try:
            rows = _sb('clientes?select=id,bot_name,deriv_id&deriv_id=in.(' + ','.join(ids) + ')&limit=1')
            row = rows[0] if rows else {}
        except Exception:
            pass
        _CLI[k] = (time.time(), row)
        return row

    @app.route('/api/ops/registrar', methods=['POST'])
    def ops_registrar():
        d = request.get_json(silent=True) or {}
        ids = _contas_do_token(str(d.get('token', '')).strip())
        if not ids:
            return jsonify({'ok': False, 'erro': 'login nao confirmado'}), 401
        cli = _cliente_de(ids)
        bot = cli.get('bot_name') or 'sem bot'
        pct = _markup_pct(bot)
        linhas = []
        for o in (d.get('ops') or [])[:50]:
            try:
                acc = str(o.get('deriv_id') or '')
                if acc and acc not in ids:
                    continue  # so aceita contas do proprio login
                conta = 'real' if str(o.get('conta')) == 'real' else 'demo'
                stake = round(float(o.get('stake') or 0), 2)
                lucro = round(float(o.get('lucro') or 0), 2)
                linhas.append({
                    'contract_id': str(o.get('contract_id')), 'deriv_id': acc or None, 'cliente_id': cli.get('id'),
                    'bot_name': bot, 'ferramenta': str(o.get('ferramenta') or '')[:40], 'conta': conta,
                    'stake': stake, 'lucro': lucro, 'resultado': 'won' if lucro > 0 else 'lost',
                    'symbol': str(o.get('symbol') or '')[:30], 'tipo': str(o.get('tipo') or '')[:30],
                    'markup_usd': round(stake * pct / 100, 4) if conta == 'real' else 0,
                })
            except Exception:
                continue
        if not linhas:
            return jsonify({'ok': True, 'gravadas': 0})
        k = _key()
        r = requests.post(URL + '/rest/v1/operacoes?on_conflict=contract_id', json=linhas, timeout=15,
                          headers={'apikey': k, 'Authorization': 'Bearer ' + k, 'Content-Type': 'application/json',
                                   'Prefer': 'resolution=ignore-duplicates,return=minimal'})
        if not r.ok:
            print('[OPS] supabase', r.status_code, r.text[:300])
            return jsonify({'ok': False, 'erro': 'supabase %s' % r.status_code}), 502
        return jsonify({'ok': True, 'gravadas': len(linhas)})

    @app.before_request
    def _trava_conta_real():
        if request.method != 'POST' or request.path.rstrip('/') != '/api/bot/start':
            return None
        d = request.get_json(silent=True) or {}
        print('[PLANO] bot/start campos:', sorted(d.keys()), 'bot_type=', d.get('bot_type'),
              'deriv_id=', d.get('deriv_id'), 'account_type=', d.get('account_type'))
        if not _eh_real(d):
            return None
        ferramenta = _ferramenta_do_start(d)
        try:
            info = plano_por_ids([str(d.get('deriv_id', '')).strip()])
        except Exception:
            return jsonify({'success': False, 'error': 'Nao consegui confirmar seu plano agora. Tente de novo em instantes.'}), 503
        if pode(info, ferramenta):
            return None
        precisa = NOME_NIVEL[NIVEL_FERRAMENTA.get(ferramenta, 0)]
        print('[PLANO] BLOQUEADO conta real', d.get('deriv_id'), ferramenta, 'plano', info['plano'])
        return jsonify({'success': False, 'plano_necessario': precisa, 'ferramenta': ferramenta,
                        'error': 'Conta real exige o plano %s. Na conta demo continua liberado.' % precisa.capitalize()}), 403
