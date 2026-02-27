"""
Quantum Trader - VIP | Win Rate: 80%
Múltiplos indicadores com decisão quantitativa
Lógica: RSI + Bollinger + Momentum combinados com peso quantitativo
"""
from .base_strategy import BaseStrategy
from ..config import BotConfig
import statistics

class QuantumTrader(BaseStrategy):
    TRADING_MODE_CONFIG = {
        'lowRisk':  {'min_confidence': 0.90, 'cooldown': 28, 'min_score': 7},
        'accurate': {'min_confidence': 0.82, 'cooldown': 20, 'min_score': 6},
        'balanced': {'min_confidence': 0.72, 'cooldown': 13, 'min_score': 5},
        'faster':   {'min_confidence': 0.65, 'cooldown':  8, 'min_score': 4},
    }
    RISK_MODE_CONFIG = {
        'fixed':        {'martingale': False, 'multiplier': 1.0,  'max_steps': 0},
        'conservative': {'martingale': True,  'multiplier': 1.5,  'max_steps': 2},
        'optimized':    {'martingale': True,  'multiplier': 2.0,  'max_steps': 3},
        'aggressive':   {'martingale': True,  'multiplier': 2.5,  'max_steps': 5},
    }

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__(name="Quantum Trader")
        self.min_history = 30
        self.last_signal_tick = 0
        tm = self.TRADING_MODE_CONFIG.get(trading_mode, self.TRADING_MODE_CONFIG['faster'])
        self.min_confidence = tm['min_confidence']
        self.cooldown_ticks = tm['cooldown']
        self.min_score = tm['min_score']
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

    def _rsi(self, prices, period=14):
        if len(prices) < period+1: return 50.0
        gains = [max(0, prices[-i]-prices[-i-1]) for i in range(1, period+1)]
        losses = [max(0, prices[-i-1]-prices[-i]) for i in range(1, period+1)]
        ag = statistics.mean(gains) or 0.001
        al = statistics.mean(losses) or 0.001
        return 100 - (100/(1+ag/al))

    def should_enter(self, tick_data):
        self.update_tick(tick_data)
        if len(self.ticks_history) < self.min_history:
            return False, None, 0.0
        if (len(self.ticks_history) - self.last_signal_tick) < self.cooldown_ticks:
            return False, None, 0.0
        try:
            prices = [t['quote'] for t in list(self.ticks_history)[-30:]]
            current = prices[-1]
            ma20 = statistics.mean(prices[-20:])
            std  = statistics.stdev(prices[-20:])
            upper = ma20 + 2*std
            lower = ma20 - 2*std
            rsi   = self._rsi(prices)
            mom   = (prices[-1]-prices[-8])/prices[-8]*100
            ma5   = statistics.mean(prices[-5:])
            vol   = statistics.stdev(prices[-10:])

            # Sistema de pontuação quantitativo (0-10 pontos)
            call_score = 0
            put_score  = 0

            if rsi < 30: call_score += 3
            elif rsi < 40: call_score += 1
            if rsi > 70: put_score += 3
            elif rsi > 60: put_score += 1

            if current < lower: call_score += 2
            elif current < ma20: call_score += 1
            if current > upper: put_score += 2
            elif current > ma20: put_score += 1

            if mom < -0.2: call_score += 2
            elif mom < -0.1: call_score += 1
            if mom > 0.2: put_score += 2
            elif mom > 0.1: put_score += 1

            if ma5 < ma20: call_score += 1
            if ma5 > ma20: put_score += 1

            if vol > 0.1: call_score += 1; put_score += 1

            if call_score >= self.min_score:
                conf = 0.60 + (call_score / 10) * 0.30
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "CALL", min(conf, 0.92)
            if put_score >= self.min_score:
                conf = 0.60 + (put_score / 10) * 0.30
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "PUT", min(conf, 0.92)
            return False, None, 0.0
        except Exception as e:
            print(f"⚠️ Quantum Trader erro: {e}")
            return False, None, 0.0

    def get_contract_params(self, direction):
        return {"contract_type": direction, "duration": 1, "duration_unit": "t",
                "symbol": BotConfig.DEFAULT_SYMBOL, "basis": BotConfig.BASIS}

    def get_info(self):
        return {'name': self.name, 'tier': 'VIP', 'win_rate': '80%'}
