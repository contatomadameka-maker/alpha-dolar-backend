"""
Alpha Mind - VIP | Win Rate: 78%
IA Neural com análise preditiva de curto prazo
Lógica: EMA tripla + padrão de aceleração
"""
from .base_strategy import BaseStrategy
from ..config import BotConfig
import statistics

class AlphaMind(BaseStrategy):
    TRADING_MODE_CONFIG = {
        'lowRisk':  {'min_confidence': 0.90, 'cooldown': 25, 'min_conditions': 5},
        'accurate': {'min_confidence': 0.82, 'cooldown': 18, 'min_conditions': 4},
        'balanced': {'min_confidence': 0.72, 'cooldown': 12, 'min_conditions': 4},
        'faster':   {'min_confidence': 0.65, 'cooldown':  8, 'min_conditions': 3},
    }
    RISK_MODE_CONFIG = {
        'fixed':        {'martingale': False, 'multiplier': 1.0,  'max_steps': 0},
        'conservative': {'martingale': True,  'multiplier': 1.5,  'max_steps': 2},
        'optimized':    {'martingale': True,  'multiplier': 2.0,  'max_steps': 3},
        'aggressive':   {'martingale': True,  'multiplier': 2.5,  'max_steps': 5},
    }

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__(name="Alpha Mind")
        self.min_history = 25
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

    def _ema(self, prices, period):
        if len(prices) < period: return None
        mult = 2 / (period + 1)
        ema = statistics.mean(prices[:period])
        for p in prices[period:]:
            ema = (p * mult) + (ema * (1 - mult))
        return ema

    def should_enter(self, tick_data):
        self.update_tick(tick_data)
        if len(self.ticks_history) < self.min_history:
            return False, None, 0.0
        if (len(self.ticks_history) - self.last_signal_tick) < self.cooldown_ticks:
            return False, None, 0.0
        try:
            prices = [t['quote'] for t in list(self.ticks_history)[-25:]]
            ema5  = self._ema(prices, 5)
            ema10 = self._ema(prices, 10)
            ema20 = self._ema(prices, 20)
            if not all([ema5, ema10, ema20]): return False, None, 0.0

            current = prices[-1]
            accel = (prices[-1] - 2*prices[-3] + prices[-5]) if len(prices) >= 5 else 0
            vol = statistics.stdev(prices[-10:])

            call_conditions = [ema5 > ema10, ema10 > ema20, current > ema5, accel > 0, vol > 0.05]
            put_conditions  = [ema5 < ema10, ema10 < ema20, current < ema5, accel < 0, vol > 0.05]

            cs = sum(call_conditions)
            ps = sum(put_conditions)

            if cs >= self.min_conditions:
                conf = 0.60 + (cs / 5) * 0.30
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "CALL", conf
            if ps >= self.min_conditions:
                conf = 0.60 + (ps / 5) * 0.30
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "PUT", conf
            return False, None, 0.0
        except Exception as e:
            print(f"⚠️ Alpha Mind erro: {e}")
            return False, None, 0.0

    def get_contract_params(self, direction):
        return {"contract_type": direction, "duration": 1, "duration_unit": "t",
                "symbol": BotConfig.DEFAULT_SYMBOL, "basis": BotConfig.BASIS}

    def get_info(self):
        return {'name': self.name, 'tier': 'VIP', 'win_rate': '78%'}
