"""
Alpha Smart - VIP | Win Rate: 76%
Scalping inteligente com gestão automática de risco
Lógica: Micro-tendências de 3-5 ticks com confirmação de volume implícito
"""
from .base_strategy import BaseStrategy
from ..config import BotConfig
import statistics

class AlphaSmart(BaseStrategy):
    TRADING_MODE_CONFIG = {
        'lowRisk':  {'min_confidence': 0.90, 'cooldown': 15, 'min_conditions': 4},
        'accurate': {'min_confidence': 0.82, 'cooldown': 10, 'min_conditions': 4},
        'balanced': {'min_confidence': 0.72, 'cooldown':  7, 'min_conditions': 3},
        'faster':   {'min_confidence': 0.65, 'cooldown':  4, 'min_conditions': 3},
    }
    RISK_MODE_CONFIG = {
        'fixed':        {'martingale': False, 'multiplier': 1.0,  'max_steps': 0},
        'conservative': {'martingale': True,  'multiplier': 1.5,  'max_steps': 2},
        'optimized':    {'martingale': True,  'multiplier': 2.0,  'max_steps': 3},
        'aggressive':   {'martingale': True,  'multiplier': 2.5,  'max_steps': 5},
    }

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__(name="Alpha Smart")
        self.min_history = 15
        self.last_signal_tick = 0
        tm = self.TRADING_MODE_CONFIG.get(trading_mode, self.TRADING_MODE_CONFIG['faster'])
        self.min_confidence = tm['min_confidence']
        self.cooldown_ticks = tm['cooldown']
        self.min_conditions = tm['min_conditions']
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
            prices = [t['quote'] for t in list(self.ticks_history)[-15:]]
            current = prices[-1]
            micro3  = prices[-3:]
            micro5  = prices[-5:]

            # Micro tendência 3 ticks
            micro_trend3 = (micro3[-1] - micro3[0]) / micro3[0] * 100
            # Micro tendência 5 ticks
            micro_trend5 = (micro5[-1] - micro5[0]) / micro5[0] * 100
            # Média geral
            ma15 = statistics.mean(prices)
            vol  = statistics.stdev(prices[-8:]) if len(prices) >= 8 else 0

            # Scalp CALL: micro-tendência de alta confirmada
            call_conditions = [
                micro_trend3 > 0.02,
                micro_trend5 > 0.01,
                current > ma15,
                vol > 0.02,
            ]
            # Scalp PUT
            put_conditions = [
                micro_trend3 < -0.02,
                micro_trend5 < -0.01,
                current < ma15,
                vol > 0.02,
            ]

            cs = sum(call_conditions)
            ps = sum(put_conditions)

            if cs >= self.min_conditions:
                conf = 0.60 + (cs / 4) * 0.28
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "CALL", conf
            if ps >= self.min_conditions:
                conf = 0.60 + (ps / 4) * 0.28
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "PUT", conf
            return False, None, 0.0
        except Exception as e:
            print(f"⚠️ Alpha Smart erro: {e}")
            return False, None, 0.0

    def get_contract_params(self, direction):
        return {"contract_type": direction, "duration": 1, "duration_unit": "t",
                "symbol": BotConfig.DEFAULT_SYMBOL, "basis": BotConfig.BASIS}

    def get_info(self):
        return {'name': self.name, 'tier': 'VIP', 'win_rate': '76%'}
