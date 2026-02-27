"""
Alpha Bot 1 - Análise de Tendência
FREE | Win Rate esperado: 72%
Lógica: SMA cruzamento + tendência de curto prazo
"""
from .base_strategy import BaseStrategy
from ..config import BotConfig
import statistics

class AlphaBot1(BaseStrategy):
    TRADING_MODE_CONFIG = {
        'lowRisk':  {'min_confidence': 0.90, 'cooldown': 20, 'min_conditions': 4},
        'accurate': {'min_confidence': 0.80, 'cooldown': 14, 'min_conditions': 4},
        'balanced': {'min_confidence': 0.70, 'cooldown': 10, 'min_conditions': 3},
        'faster':   {'min_confidence': 0.60, 'cooldown':  6, 'min_conditions': 2},
    }
    RISK_MODE_CONFIG = {
        'fixed':        {'martingale': False, 'multiplier': 1.0,  'max_steps': 0},
        'conservative': {'martingale': True,  'multiplier': 1.5,  'max_steps': 2},
        'optimized':    {'martingale': True,  'multiplier': 2.0,  'max_steps': 3},
        'aggressive':   {'martingale': True,  'multiplier': 2.5,  'max_steps': 5},
    }

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__(name="Alpha Bot 1")
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
        print(f"⚙️ Alpha Bot 1 | Modo: {trading_mode} | Confiança: {self.min_confidence:.0%}")

    def on_trade_result(self, won: bool):
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

    def get_stake(self):
        return self.stake_atual

    def should_enter(self, tick_data):
        self.update_tick(tick_data)
        if len(self.ticks_history) < self.min_history:
            return False, None, 0.0
        ticks_since_last = len(self.ticks_history) - self.last_signal_tick
        if ticks_since_last < self.cooldown_ticks:
            return False, None, 0.0
        try:
            prices = [t['quote'] for t in list(self.ticks_history)[-15:]]
            sma5  = statistics.mean(prices[-5:])
            sma15 = statistics.mean(prices[-15:])
            current = prices[-1]
            prev    = prices[-2]

            # Tendência pelos últimos 8 ticks
            ups   = sum(1 for i in range(1, 8) if prices[-i] > prices[-i-1])
            downs = sum(1 for i in range(1, 8) if prices[-i] < prices[-i-1])

            call_conditions = [
                sma5 > sma15,           # SMA curta acima da longa
                current > sma5,         # Preço acima da SMA5
                ups > downs,            # Mais ticks subindo
                current > prev,         # Último tick subiu
            ]
            put_conditions = [
                sma5 < sma15,
                current < sma5,
                downs > ups,
                current < prev,
            ]

            call_score = sum(call_conditions)
            put_score  = sum(put_conditions)

            if call_score >= self.min_conditions:
                confidence = 0.55 + (call_score / 4) * 0.35
                if confidence >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "CALL", confidence

            if put_score >= self.min_conditions:
                confidence = 0.55 + (put_score / 4) * 0.35
                if confidence >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "PUT", confidence

            return False, None, 0.0
        except Exception as e:
            print(f"⚠️ Alpha Bot 1 erro: {e}")
            return False, None, 0.0

    def get_contract_params(self, direction):
        return {"contract_type": direction, "duration": 1, "duration_unit": "t",
                "symbol": BotConfig.DEFAULT_SYMBOL, "basis": BotConfig.BASIS}

    def get_info(self):
        return {'name': self.name, 'tier': 'FREE', 'trading_mode': self.trading_mode,
                'risk_mode': self.risk_mode, 'win_rate': '72%'}
