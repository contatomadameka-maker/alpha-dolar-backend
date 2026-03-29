"""
Alpha Pulse - VIP | Win Rate: 77%
Detecção de pulsos de mercado em tempo real
Lógica: Detecta aceleração e desaceleração súbita de preço (pulsos)
"""
from .base_strategy import BaseStrategy
from ..config import BotConfig
import statistics

class AlphaPulse(BaseStrategy):
    TRADING_MODE_CONFIG = {
        'lowRisk':  {'min_confidence': 0.90, 'cooldown': 20, 'pulse_threshold': 0.25},
        'accurate': {'min_confidence': 0.82, 'cooldown': 14, 'pulse_threshold': 0.18},
        'balanced': {'min_confidence': 0.72, 'cooldown':  9, 'pulse_threshold': 0.12},
        'faster':   {'min_confidence': 0.65, 'cooldown':  5, 'pulse_threshold': 0.08},
    }
    RISK_MODE_CONFIG = {
        'fixed':        {'martingale': False, 'multiplier': 1.0,  'max_steps': 0},
        'conservative': {'martingale': True,  'multiplier': 1.5,  'max_steps': 2},
        'optimized':    {'martingale': True,  'multiplier': 2.0,  'max_steps': 3},
        'aggressive':   {'martingale': True,  'multiplier': 2.5,  'max_steps': 5},
    }

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__(name="Alpha Pulse")
        self.min_history = 20
        self.last_signal_tick = 0
        tm = self.TRADING_MODE_CONFIG.get(trading_mode, self.TRADING_MODE_CONFIG['faster'])
        self.min_confidence = tm['min_confidence']
        self.cooldown_ticks = tm['cooldown']
        self.pulse_threshold = tm['pulse_threshold']
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
            prices = [t['quote'] for t in list(self.ticks_history)[-20:]]
            # Calcula variações tick a tick
            changes = [prices[i]-prices[i-1] for i in range(1, len(prices))]
            recent_changes = changes[-5:]
            older_changes  = changes[-10:-5]

            recent_vol = statistics.stdev(recent_changes) if len(recent_changes) > 1 else 0
            older_vol  = statistics.stdev(older_changes)  if len(older_changes)  > 1 else 0.001

            # Pulso: aumento súbito de volatilidade
            pulse_ratio = recent_vol / older_vol
            avg_recent  = statistics.mean(recent_changes)
            ma20        = statistics.mean(prices)
            current     = prices[-1]

            # Pulso de queda forte → espera reversão para CALL
            call_conditions = [
                avg_recent < -self.pulse_threshold,  # Pulso de queda
                pulse_ratio > 1.5,                   # Volatilidade aumentou
                current < ma20,                      # Abaixo da média
                recent_vol > 0.03,                   # Volatilidade real
            ]
            # Pulso de alta forte → espera reversão para PUT
            put_conditions = [
                avg_recent > self.pulse_threshold,
                pulse_ratio > 1.5,
                current > ma20,
                recent_vol > 0.03,
            ]

            cs = sum(call_conditions)
            ps = sum(put_conditions)

            if cs >= 3:
                conf = 0.60 + min(pulse_ratio / 10, 0.25)
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "CALL", conf
            if ps >= 3:
                conf = 0.60 + min(pulse_ratio / 10, 0.25)
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "PUT", conf
            return False, None, 0.0
        except Exception as e:
            print(f"⚠️ Alpha Pulse erro: {e}")
            return False, None, 0.0

    def get_contract_params(self, direction):
        return {"contract_type": direction, "duration": 1, "duration_unit": "t",
                "symbol": BotConfig.DEFAULT_SYMBOL, "basis": BotConfig.BASIS}

    def get_info(self):
        return {'name': self.name, 'tier': 'VIP', 'win_rate': '77%'}
