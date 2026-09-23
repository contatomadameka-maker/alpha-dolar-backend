"""Alpha Bot 1 - Estratégia Rise/Fall
Alpha Dolar 2.0"""
from .base_strategy import BaseStrategy
try:
    from ..config import BotConfig
except ImportError:
    from config import BotConfig

class AlphaBot1(BaseStrategy):
    """
    Estratégia Alpha Bot 1 - Rise/Fall Simples
    Lógica:
    - Analisa tendência dos últimos N ticks
    - Entra em CALL se tendência de alta
    - Entra em PUT se tendência de baixa
    - Usa confirmação de padrão consecutivo
    """
    def __init__(self, trading_mode=None, risk_mode=None, lookback_period=None, min_consecutive=None, confidence_threshold=None):
        super().__init__(name="Alpha Bot 1")

        # Perfis por modo de negociacao (nomes reais enviados pelo frontend)
        perfis = {
            'fast':       {'lookback_period': 3, 'min_consecutive': 1, 'confidence_threshold': 0.30},
            'faster':     {'lookback_period': 3, 'min_consecutive': 1, 'confidence_threshold': 0.30},
            'balanced':   {'lookback_period': 4, 'min_consecutive': 2, 'confidence_threshold': 0.45},
            'precise':    {'lookback_period': 5, 'min_consecutive': 2, 'confidence_threshold': 0.60},
            'slow':       {'lookback_period': 6, 'min_consecutive': 3, 'confidence_threshold': 0.70},
        }
        perfil = perfis.get(trading_mode, perfis['balanced'])

        self.lookback_period      = lookback_period if lookback_period is not None else perfil['lookback_period']
        self.min_consecutive      = min_consecutive if min_consecutive is not None else perfil['min_consecutive']
        self.confidence_threshold = confidence_threshold if confidence_threshold is not None else perfil['confidence_threshold']
        print(f"⚙️ Modo: {trading_mode or 'balanced'} | lookback={self.lookback_period} min_consec={self.min_consecutive} conf_min={self.confidence_threshold}")

        # ── Sistema de Martingale ──
        rm = risk_mode or {}
        if isinstance(rm, str):
            rm = {}
        self.usar_martingale          = rm.get('martingale', True)
        self.multiplicador_martingale = rm.get('multiplicador', 2.2)
        self.max_martingale_steps     = rm.get('max_steps', 3)
        self.martingale_step          = 0
        self.stake_atual              = (self.config or BotConfig).STAKE_INICIAL

        # Objeto martingale compatível com o backend
        self.martingale = self

        print(f"🤖 Alpha Bot 1 | Martingale: {self.usar_martingale} | Mult: {self.multiplicador_martingale}x | Máx: {self.max_martingale_steps}")

    def get_info(self):
        """Compatível com bot.martingale.get_info()"""
        return {
            'step_atual':  self.martingale_step,
            'max_steps':   self.max_martingale_steps,
            'stake_atual': self.stake_atual,
            'ativo':       self.usar_martingale,
        }

    def atualizar_apos_trade(self, ganhou, lucro=0):
        """Atualiza o step do martingale após cada trade"""
        if not self.usar_martingale:
            return
        if ganhou:
            self.martingale_step = 0
            self.stake_atual     = (self.config or BotConfig).STAKE_INICIAL
        else:
            if self.martingale_step < self.max_martingale_steps:
                self.martingale_step += 1
                self.stake_atual = round((self.config or BotConfig).STAKE_INICIAL * (self.multiplicador_martingale ** self.martingale_step), 2)
                print(f"📈 Martingale passo {self.martingale_step}: stake = ${self.stake_atual}")
            else:
                self.martingale_step = 0
                self.stake_atual     = (self.config or BotConfig).STAKE_INICIAL
                print(f"🔄 Martingale resetado após {self.max_martingale_steps} passos")

    def should_enter(self, tick_data):
        """Decide se deve entrar em trade"""
        # Atualiza o historico ANTES de checar se esta pronto -- senao o
        # historico fica preso em zero para sempre (nunca acumula ticks).
        self.update_tick(tick_data)
        if not self.is_ready():
            return False, None, 0.0
        trend   = self.calculate_trend(self.lookback_period)
        pattern = self.detect_pattern("consecutive")
        if trend == "UP":
            consecutive = pattern.get("consecutive_ups", 0)
            if consecutive >= self.min_consecutive:
                confidence = min(consecutive / (self.lookback_period * 1.5), 1.0)
                if confidence >= self.confidence_threshold:
                    self.last_signal = "CALL"
                    self.signal_count += 1
                    return True, "CALL", confidence
        elif trend == "DOWN":
            consecutive = pattern.get("consecutive_downs", 0)
            if consecutive >= self.min_consecutive:
                confidence = min(consecutive / (self.lookback_period * 1.5), 1.0)
                if confidence >= self.confidence_threshold:
                    self.last_signal = "PUT"
                    self.signal_count += 1
                    return True, "PUT", confidence
        return False, None, 0.0

    def get_contract_params(self, direction):
        """Retorna parâmetros do contrato"""
        return {
            "contract_type": direction,
            "duration":      (self.config or BotConfig).DURATION,
            "duration_unit": (self.config or BotConfig).DURATION_UNIT,
            "symbol":        (self.config or BotConfig).DEFAULT_SYMBOL,
            "basis":         (self.config or BotConfig).BASIS
        }


class AlphaBot1Reverse(AlphaBot1):
    def __init__(self, trading_mode=None, risk_mode=None):
        super().__init__(trading_mode, risk_mode)
        self.name = "Alpha Bot 1 Reverse"

    def should_enter(self, tick_data):
        entered, direction, confidence = super().should_enter(tick_data)
        if entered and direction:
            direction = "PUT" if direction == "CALL" else "CALL"
        return entered, direction, confidence


class AlphaBot1MA(AlphaBot1):
    def __init__(self, trading_mode=None, risk_mode=None):
        super().__init__(trading_mode, risk_mode)
        self.name = "Alpha Bot 1 MA"
