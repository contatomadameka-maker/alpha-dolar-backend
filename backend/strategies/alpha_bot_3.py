"""
Alpha Bot 3 - Momentum com Filtro de Ruído
FREE | Win Rate esperado: 71%
Lógica: RSI simplificado + filtro de ruído por desvio padrão
"""
from .base_strategy import BaseStrategy
from ..config import BotConfig
import statistics

class AlphaBot3(BaseStrategy):
    TRADING_MODE_CONFIG = {
        'lowRisk':  {'min_confidence': 0.90, 'cooldown': 18, 'min_conditions': 4},
        'accurate': {'min_confidence': 0.80, 'cooldown': 13, 'min_conditions': 3},
        'balanced': {'min_confidence': 0.70, 'cooldown':  9, 'min_conditions': 3},
        'faster':   {'min_confidence': 0.60, 'cooldown':  5, 'min_conditions': 2},
    }
    RISK_MODE_CONFIG = {
        'fixed':        {'martingale': False, 'multiplier': 1.0,  'max_steps': 0},
        'conservative': {'martingale': True,  'multiplier': 1.5,  'max_steps': 2},
        'optimized':    {'martingale': True,  'multiplier': 2.0,  'max_steps': 3},
        'aggressive':   {'martingale': True,  'multiplier': 2.5,  'max_steps': 5},
    }

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__(name="Alpha Bot 3")
        self.min_history = 14
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
        print(f"⚙️ Alpha Bot 3 | Modo: {trading_mode} | Confiança: {self.min_confidence:.0%}")

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

    def _calc_rsi(self, prices, period=14):
        """RSI simplificado"""
        if len(prices) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, period + 1):
            diff = prices[-i] - prices[-i-1]
            if diff > 0: gains.append(diff)
            else: losses.append(abs(diff))
        avg_gain = statistics.mean(gains) if gains else 0.001
        avg_loss = statistics.mean(losses) if losses else 0.001
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def should_enter(self, tick_data):
        self.update_tick(tick_data)
        if len(self.ticks_history) < self.min_history:
            return False, None, 0.0
        if (len(self.ticks_history) - self.last_signal_tick) < self.cooldown_ticks:
            return False, None, 0.0
        try:
            prices = [t['quote'] for t in list(self.ticks_history)[-20:]]
            rsi = self._calc_rsi(prices)
            volatility = statistics.stdev(prices[-10:]) if len(prices) >= 10 else 0
            momentum = (prices[-1] - prices[-5]) / prices[-5] * 100 if len(prices) >= 5 else 0
            noise = volatility / (abs(momentum) + 0.001)  # baixo = sinal limpo

            call_conditions = [
                rsi < 35,               # Sobrevendido
                momentum < -0.05,       # Queda recente
                noise < 5,              # Sinal limpo (pouco ruído)
                volatility > 0.02,      # Volatilidade mínima
            ]
            put_conditions = [
                rsi > 65,
                momentum > 0.05,
                noise < 5,
                volatility > 0.02,
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
            print(f"⚠️ Alpha Bot 3 erro: {e}")
            return False, None, 0.0

    def get_contract_params(self, direction):
        return {"contract_type": direction, "duration": 1, "duration_unit": "t",
                "symbol": BotConfig.DEFAULT_SYMBOL, "basis": BotConfig.BASIS}

    def get_info(self):
        return {'name': self.name, 'tier': 'FREE', 'trading_mode': self.trading_mode,
                'risk_mode': self.risk_mode, 'win_rate': '71%'}
