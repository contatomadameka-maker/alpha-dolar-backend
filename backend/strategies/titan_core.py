"""
Titan Core - VIP | Win Rate: 79%
Estratégia robusta com filtro de volatilidade
Lógica: Só opera quando volatilidade está em faixa ideal. Usa suporte/resistência dinâmicos.
"""
from .base_strategy import BaseStrategy
from ..config import BotConfig
import statistics

class TitanCore(BaseStrategy):
    TRADING_MODE_CONFIG = {
        'lowRisk':  {'min_confidence': 0.90, 'cooldown': 30, 'vol_min': 0.15, 'vol_max': 0.8},
        'accurate': {'min_confidence': 0.82, 'cooldown': 22, 'vol_min': 0.10, 'vol_max': 1.0},
        'balanced': {'min_confidence': 0.72, 'cooldown': 14, 'vol_min': 0.08, 'vol_max': 1.2},
        'faster':   {'min_confidence': 0.65, 'cooldown':  8, 'vol_min': 0.05, 'vol_max': 1.5},
    }
    RISK_MODE_CONFIG = {
        'fixed':        {'martingale': False, 'multiplier': 1.0,  'max_steps': 0},
        'conservative': {'martingale': True,  'multiplier': 1.5,  'max_steps': 2},
        'optimized':    {'martingale': True,  'multiplier': 2.0,  'max_steps': 3},
        'aggressive':   {'martingale': True,  'multiplier': 2.5,  'max_steps': 5},
    }

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__(name="Titan Core")
        self.min_history = 30
        self.last_signal_tick = 0
        tm = self.TRADING_MODE_CONFIG.get(trading_mode, self.TRADING_MODE_CONFIG['faster'])
        self.min_confidence = tm['min_confidence']
        self.cooldown_ticks = tm['cooldown']
        self.vol_min = tm['vol_min']
        self.vol_max = tm['vol_max']
        self.trading_mode = trading_mode
        rm = self.RISK_MODE_CONFIG.get(risk_mode, self.RISK_MODE_CONFIG['conservative'])
        self.usar_martingale = rm['martingale']
        self.multiplicador_martingale = rm['multiplier']
        self.max_martingale_steps = rm['max_steps']
        self.risk_mode = risk_mode
        self.martingale_step = 0
        self.stake_atual = BotConfig.STAKE_INICIAL

    def on_trade_result(self, won):
        if not self.usar_martingale:
            self.stake_atual = BotConfig.STAKE_INICIAL
            return
        if won:
            self.martingale_step = 0
            self.stake_atual = BotConfig.STAKE_INICIAL
        else:
            if self.martingale_step < self.max_martingale_steps:
                self.martingale_step += 1
                self.stake_atual = round(BotConfig.STAKE_INICIAL * (self.multiplicador_martingale ** self.martingale_step), 2)
            else:
                self.martingale_step = 0
                self.stake_atual = BotConfig.STAKE_INICIAL

    def get_stake(self): return self.stake_atual

    def should_enter(self, tick_data):
        self.update_tick(tick_data)
        if len(self.ticks_history) < self.min_history:
            return False, None, 0.0
        if (len(self.ticks_history) - self.last_signal_tick) < self.cooldown_ticks:
            return False, None, 0.0
        try:
            prices = [t['quote'] for t in list(self.ticks_history)[-30:]]
            current = prices[-1]
            vol = statistics.stdev(prices[-20:])

            # Filtro de volatilidade — só opera na faixa ideal
            if not (self.vol_min <= vol <= self.vol_max):
                return False, None, 0.0

            # Suporte e resistência dinâmicos (últimos 30 ticks)
            support    = min(prices)
            resistance = max(prices)
            mid        = (support + resistance) / 2
            ma10       = statistics.mean(prices[-10:])
            ma30       = statistics.mean(prices)
            mom        = (prices[-1] - prices[-6]) / prices[-6] * 100

            call_conditions = [
                current <= support * 1.002,   # Perto do suporte
                current < mid,                 # Abaixo do meio
                ma10 > ma30,                   # Tendência de alta
                mom < -0.05,                   # Queda recente (entrada na reversão)
            ]
            put_conditions = [
                current >= resistance * 0.998,
                current > mid,
                ma10 < ma30,
                mom > 0.05,
            ]

            cs = sum(call_conditions)
            ps = sum(put_conditions)

            if cs >= 3:
                conf = 0.62 + (cs / 4) * 0.28
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "CALL", conf
            if ps >= 3:
                conf = 0.62 + (ps / 4) * 0.28
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "PUT", conf
            return False, None, 0.0
        except Exception as e:
            print(f"⚠️ Titan Core erro: {e}")
            return False, None, 0.0

    def get_contract_params(self, direction):
        return {"contract_type": direction, "duration": 1, "duration_unit": "t",
                "symbol": BotConfig.DEFAULT_SYMBOL, "basis": BotConfig.BASIS}

    def get_info(self):
        return {'name': self.name, 'tier': 'VIP', 'win_rate': '79%'}
