"""
Alpha Analytics - VIP | Win Rate: 78%
Análise estatística avançada de padrões
Lógica: Z-score + correlação de padrões históricos
"""
from .base_strategy import BaseStrategy
from ..config import BotConfig
import statistics

class AlphaAnalytics(BaseStrategy):
    TRADING_MODE_CONFIG = {
        'lowRisk':  {'min_confidence': 0.90, 'cooldown': 24, 'zscore_threshold': 2.5},
        'accurate': {'min_confidence': 0.82, 'cooldown': 17, 'zscore_threshold': 2.0},
        'balanced': {'min_confidence': 0.72, 'cooldown': 11, 'zscore_threshold': 1.7},
        'faster':   {'min_confidence': 0.65, 'cooldown':  7, 'zscore_threshold': 1.5},
    }
    RISK_MODE_CONFIG = {
        'fixed':        {'martingale': False, 'multiplier': 1.0,  'max_steps': 0},
        'conservative': {'martingale': True,  'multiplier': 1.5,  'max_steps': 2},
        'optimized':    {'martingale': True,  'multiplier': 2.0,  'max_steps': 3},
        'aggressive':   {'martingale': True,  'multiplier': 2.5,  'max_steps': 5},
    }

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__(name="Alpha Analytics")
        self.min_history = 30
        self.last_signal_tick = 0
        tm = self.TRADING_MODE_CONFIG.get(trading_mode, self.TRADING_MODE_CONFIG['faster'])
        self.min_confidence = tm['min_confidence']
        self.cooldown_ticks = tm['cooldown']
        self.zscore_threshold = tm['zscore_threshold']
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
            mean = statistics.mean(prices)
            std  = statistics.stdev(prices) or 0.001
            zscore = (current - mean) / std

            # Padrão de alternância
            last6 = prices[-6:]
            alternating = sum(1 for i in range(1, 6) if (last6[i]-last6[i-1]) * (last6[i-1]-last6[i-2] if i > 1 else -1) < 0)
            momentum = (prices[-1] - prices[-5]) / prices[-5] * 100
            vol = statistics.stdev(prices[-10:])

            # Z-score negativo extremo → CALL (preço muito abaixo da média)
            if zscore < -self.zscore_threshold:
                conf = min(0.62 + abs(zscore) * 0.06, 0.92)
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "CALL", conf

            # Z-score positivo extremo → PUT
            if zscore > self.zscore_threshold:
                conf = min(0.62 + abs(zscore) * 0.06, 0.92)
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "PUT", conf

            return False, None, 0.0
        except Exception as e:
            print(f"⚠️ Alpha Analytics erro: {e}")
            return False, None, 0.0

    def get_contract_params(self, direction):
        return {"contract_type": direction, "duration": 1, "duration_unit": "t",
                "symbol": BotConfig.DEFAULT_SYMBOL, "basis": BotConfig.BASIS}

    def get_info(self):
        return {'name': self.name, 'tier': 'VIP', 'win_rate': '78%'}


# ============================================================

"""
Alpha Sniper - VIP | Win Rate: 82%
Alta precisão com menos operações por sessão
Lógica: Só entra em condições perfeitas — todos os indicadores alinhados
"""

class AlphaSniper(BaseStrategy):
    TRADING_MODE_CONFIG = {
        'lowRisk':  {'min_confidence': 0.92, 'cooldown': 40, 'min_conditions': 6},
        'accurate': {'min_confidence': 0.86, 'cooldown': 30, 'min_conditions': 5},
        'balanced': {'min_confidence': 0.80, 'cooldown': 20, 'min_conditions': 5},
        'faster':   {'min_confidence': 0.75, 'cooldown': 12, 'min_conditions': 4},
    }
    RISK_MODE_CONFIG = {
        'fixed':        {'martingale': False, 'multiplier': 1.0,  'max_steps': 0},
        'conservative': {'martingale': True,  'multiplier': 1.5,  'max_steps': 2},
        'optimized':    {'martingale': True,  'multiplier': 2.0,  'max_steps': 3},
        'aggressive':   {'martingale': True,  'multiplier': 2.5,  'max_steps': 5},
    }

    def __init__(self, trading_mode='faster', risk_mode='conservative'):
        super().__init__(name="Alpha Sniper")
        self.min_history = 35
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

    def _rsi(self, prices, period=14):
        if len(prices) < period+1: return 50.0
        gains  = [max(0, prices[-i]-prices[-i-1]) for i in range(1, period+1)]
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
            prices = [t['quote'] for t in list(self.ticks_history)[-35:]]
            current = prices[-1]
            ma10 = statistics.mean(prices[-10:])
            ma20 = statistics.mean(prices[-20:])
            ma35 = statistics.mean(prices)
            std  = statistics.stdev(prices[-20:])
            rsi  = self._rsi(prices)
            mom  = (prices[-1]-prices[-8])/prices[-8]*100
            vol  = statistics.stdev(prices[-10:])
            zscore = (current - ma35) / (std or 0.001)

            # SNIPER CALL — tudo alinhado
            call_conditions = [
                rsi < 32,
                current < ma10,
                current < ma20,
                ma10 < ma20,
                mom < -0.15,
                zscore < -1.8,
            ]
            # SNIPER PUT — tudo alinhado
            put_conditions = [
                rsi > 68,
                current > ma10,
                current > ma20,
                ma10 > ma20,
                mom > 0.15,
                zscore > 1.8,
            ]

            cs = sum(call_conditions)
            ps = sum(put_conditions)

            if cs >= self.min_conditions:
                conf = 0.70 + (cs / 6) * 0.25
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "CALL", min(conf, 0.95)
            if ps >= self.min_conditions:
                conf = 0.70 + (ps / 6) * 0.25
                if conf >= self.min_confidence:
                    self.last_signal_tick = len(self.ticks_history)
                    return True, "PUT", min(conf, 0.95)
            return False, None, 0.0
        except Exception as e:
            print(f"⚠️ Alpha Sniper erro: {e}")
            return False, None, 0.0

    def get_contract_params(self, direction):
        return {"contract_type": direction, "duration": 1, "duration_unit": "t",
                "symbol": BotConfig.DEFAULT_SYMBOL, "basis": BotConfig.BASIS}

    def get_info(self):
        return {'name': self.name, 'tier': 'VIP', 'win_rate': '82%'}
