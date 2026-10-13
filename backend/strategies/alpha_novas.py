"""
Estratégias novas Alpha Dolar (ALPHA-NOVAS-V1) — Rise/Fall (CALL/PUT), 1 tick
Cada uma tem um perfil diferente das existentes. Nenhuma garante acerto:
os índices sintéticos são aleatórios; o acerto real é medido no livro do Enxame.

  Alpha Elástico   — reversão: preço esticado 2 desvios da média de 20 ticks
  Alpha Rompimento — tendência: rompe a máxima/mínima de 30 ticks com volatilidade subindo
  Alpha Exaustão   — reversão confirmada: RSI 14 extremo e o último tick já virou
  Alpha Fluxo      — momento: 3 movimentos seguidos no mesmo lado, cada um maior
  Alpha Calmaria   — rompe o aperto: volatilidade bem abaixo do normal e um movimento forte
"""
from .base_strategy import BaseStrategy
from ..config import BotConfig
import statistics


class _AlphaNovaBase(BaseStrategy):
    TRADING_MODE_CONFIG = {
        'lowRisk':  {'min_confidence': 0.80, 'cooldown': 25},
        'accurate': {'min_confidence': 0.74, 'cooldown': 18},
        'balanced': {'min_confidence': 0.68, 'cooldown': 12},
        'faster':   {'min_confidence': 0.62, 'cooldown':  6},
    }
    RISK_MODE_CONFIG = {
        'fixed':        {'martingale': False, 'multiplier': 1.0,  'max_steps': 0},
        'conservative': {'martingale': True,  'multiplier': 1.5,  'max_steps': 2},
        'optimized':    {'martingale': True,  'multiplier': 2.0,  'max_steps': 3},
        'aggressive':   {'martingale': True,  'multiplier': 2.5,  'max_steps': 5},
    }
    MIN_HISTORY = 30
    DESCRICAO = ''
    PERFIL = ''

    def __init__(self, name, trading_mode='faster', risk_mode='conservative'):
        super().__init__(name=name)
        self.last_signal_tick = -10 ** 9
        tm = self.TRADING_MODE_CONFIG.get(trading_mode, self.TRADING_MODE_CONFIG['faster'])
        self.min_confidence = tm['min_confidence']
        self.cooldown_ticks = tm['cooldown']
        self.trading_mode = trading_mode
        if isinstance(risk_mode, dict):
            rm = dict(self.RISK_MODE_CONFIG.get(risk_mode.get('preset', 'conservative'), self.RISK_MODE_CONFIG['conservative']))
            if risk_mode.get('multiplicador') is not None:
                rm['multiplier'] = risk_mode['multiplicador']
        else:
            rm = self.RISK_MODE_CONFIG.get(risk_mode, self.RISK_MODE_CONFIG['conservative'])
        self.usar_martingale = rm['martingale']
        self.multiplicador_martingale = rm['multiplier']
        self.max_martingale_steps = rm['max_steps']
        self.risk_mode = risk_mode
        self.martingale_step = 0
        self.stake_atual = (self.config or BotConfig).STAKE_INICIAL
        self._n = 0  # ticks recebidos (o histórico tem teto de 100)

    # ---------- gestão (mesmo padrão das outras estratégias) ----------
    def on_trade_result(self, won):
        base = (self.config or BotConfig).STAKE_INICIAL
        if not self.usar_martingale or won:
            self.martingale_step = 0
            self.stake_atual = base
            return
        if self.martingale_step < self.max_martingale_steps:
            self.martingale_step += 1
            self.stake_atual = round(base * (self.multiplicador_martingale ** self.martingale_step), 2)
        else:
            self.martingale_step = 0
            self.stake_atual = base

    def get_stake(self):
        return self.stake_atual

    def get_contract_params(self, direction):
        cfg = self.config or BotConfig
        return {"contract_type": direction, "duration": 1, "duration_unit": "t",
                "symbol": cfg.DEFAULT_SYMBOL, "basis": cfg.BASIS}

    def get_info(self):
        return {'name': self.name, 'tier': 'VIP', 'perfil': self.PERFIL, 'descricao': self.DESCRICAO}

    # ---------- utilitários ----------
    def _precos(self, n):
        return [t['quote'] for t in list(self.ticks_history)[-n:]]

    @staticmethod
    def _passo_medio(p):
        if len(p) < 2:
            return 0.0
        return sum(abs(p[i] - p[i - 1]) for i in range(1, len(p))) / (len(p) - 1)

    def _emitir(self, direcao, conf):
        conf = max(0.0, min(0.95, conf))
        if conf < self.min_confidence:
            return False, None, 0.0
        self.last_signal_tick = self._n
        self.last_signal = direcao
        self.signal_count += 1
        return True, direcao, round(conf, 4)

    def should_enter(self, tick_data):
        self.update_tick(tick_data)
        self._n += 1
        if len(self.ticks_history) < self.MIN_HISTORY:
            return False, None, 0.0
        if self._n - self.last_signal_tick < self.cooldown_ticks:
            return False, None, 0.0
        try:
            return self._sinal()
        except Exception as e:
            print(f"⚠️ {self.name} erro: {e}")
            return False, None, 0.0

    def _sinal(self):
        return False, None, 0.0


class AlphaElastico(_AlphaNovaBase):
    MIN_HISTORY = 80
    PERFIL = 'reversão · entra pouco'
    DESCRICAO = 'Entra contra o preço quando ele estica 2 desvios da média de 20 ticks, só com a volatilidade normal.'

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__("Alpha Elástico", trading_mode, risk_mode)

    def _sinal(self):
        p80 = self._precos(80)
        p = p80[-20:]
        m = statistics.mean(p)
        sd = statistics.pstdev(p)
        if sd <= 0:
            return False, None, 0.0
        z = (p[-1] - m) / sd
        a20, a80 = self._passo_medio(p), self._passo_medio(p80)
        if a80 <= 0 or not (0.6 <= a20 / a80 <= 1.8):   # sem disparo nem mercado parado
            return False, None, 0.0
        virou = (p[-1] - p[-2]) * z < 0                   # último tick já voltou na direção da média
        conf = 0.64 + (abs(z) - 2.0) * 0.22 + (0.06 if virou else 0.0)
        if z <= -2.0:
            return self._emitir("CALL", conf)
        if z >= 2.0:
            return self._emitir("PUT", conf)
        return False, None, 0.0


class AlphaRompimento(_AlphaNovaBase):
    MIN_HISTORY = 41
    PERFIL = 'tendência · entradas raras'
    DESCRICAO = 'Entra a favor quando o preço rompe a máxima ou a mínima dos últimos 30 ticks e a volatilidade está subindo.'

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__("Alpha Rompimento", trading_mode, risk_mode)

    def _sinal(self):
        p = self._precos(41)
        cur, janela = p[-1], p[-31:-1]
        hi, lo = max(janela), min(janela)
        a_rec, a_ant = self._passo_medio(p[-11:]), self._passo_medio(p[:-10])
        if a_ant <= 0:
            return False, None, 0.0
        r = a_rec / a_ant
        if r < 1.2:
            return False, None, 0.0
        if cur > hi:
            conf = 0.62 + min(0.20, (cur - hi) / max(a_rec, 1e-12) * 0.10) + min(0.12, (r - 1.2) * 0.20)
            return self._emitir("CALL", conf)
        if cur < lo:
            conf = 0.62 + min(0.20, (lo - cur) / max(a_rec, 1e-12) * 0.10) + min(0.12, (r - 1.2) * 0.20)
            return self._emitir("PUT", conf)
        return False, None, 0.0


class AlphaExaustao(_AlphaNovaBase):
    MIN_HISTORY = 20
    PERFIL = 'reversão confirmada'
    DESCRICAO = 'RSI de 14 ticks abaixo de 20 ou acima de 80, e só entra depois que o último tick já virou de lado.'

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__("Alpha Exaustão", trading_mode, risk_mode)

    @staticmethod
    def _rsi(p):
        g = l = 0.0
        for i in range(1, len(p)):
            d = p[i] - p[i - 1]
            if d > 0: g += d
            else: l -= d
        if g + l == 0:
            return 50.0
        return 100.0 * g / (g + l)

    def _sinal(self):
        p = self._precos(17)
        rsi = self._rsi(p[:-1][-15:])   # RSI dos 14 movimentos antes do último tick
        ultimo = p[-1] - p[-2]
        if rsi <= 20 and ultimo > 0:
            return self._emitir("CALL", 0.62 + (20 - rsi) / 20 * 0.30)
        if rsi >= 80 and ultimo < 0:
            return self._emitir("PUT", 0.62 + (rsi - 80) / 20 * 0.30)
        return False, None, 0.0


class AlphaFluxo(_AlphaNovaBase):
    MIN_HISTORY = 21
    PERFIL = 'momento · entra bastante'
    DESCRICAO = 'Segue quando há 3 movimentos seguidos para o mesmo lado e cada um é maior que o anterior.'

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__("Alpha Fluxo", trading_mode, risk_mode)

    def _sinal(self):
        p = self._precos(21)
        d1, d2, d3 = p[-3] - p[-4], p[-2] - p[-3], p[-1] - p[-2]
        if not (d1 * d2 > 0 and d2 * d3 > 0):
            return False, None, 0.0
        if not (abs(d1) < abs(d2) < abs(d3)):
            return False, None, 0.0
        a20 = self._passo_medio(p)
        if a20 <= 0:
            return False, None, 0.0
        conf = 0.64 + min(0.26, (abs(d3) / a20 - 1.0) * 0.12)
        return self._emitir("CALL" if d3 > 0 else "PUT", conf)


class AlphaCalmaria(_AlphaNovaBase):
    MIN_HISTORY = 95
    PERFIL = 'paciente · entradas raras'
    DESCRICAO = 'Espera o mercado apertar (volatilidade bem abaixo do normal) e entra no lado do primeiro movimento forte que sai do aperto.'

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__("Alpha Calmaria", trading_mode, risk_mode)
        self._apertado = 0

    def _sinal(self):
        p = self._precos(95)
        a15, a90 = self._passo_medio(p[-16:-1]), self._passo_medio(p[:-1])
        if a90 <= 0 or a15 <= 0:
            return False, None, 0.0
        r = a15 / a90
        d = p[-1] - p[-2]
        if r < 0.7:
            self._apertado = 30          # aperto vale pelos próximos 30 ticks
        elif self._apertado:
            self._apertado -= 1
        if self._apertado and abs(d) > 2.0 * a15 and abs(d) > a90:
            self._apertado = 0
            conf = 0.62 + min(0.18, (abs(d) / a15 - 2.0) * 0.06) + min(0.12, max(0.0, 0.7 - r) * 0.4)
            return self._emitir("CALL" if d > 0 else "PUT", conf)
        return False, None, 0.0


ALPHA_NOVAS = {
    'alpha_elastico':   AlphaElastico,
    'alpha_rompimento': AlphaRompimento,
    'alpha_exaustao':   AlphaExaustao,
    'alpha_fluxo':      AlphaFluxo,
    'alpha_calmaria':   AlphaCalmaria,
}
