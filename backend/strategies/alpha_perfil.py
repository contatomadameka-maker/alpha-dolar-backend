"""Alpha Perfil — ajusta o multiplicador de recuperacao pela volatilidade real
do mercado, medida ao vivo (mesma formula do radar do Alpha Esquadrao).
Entrada por tendencia de curto prazo, no mesmo espirito do Alpha Bot 1.
Alpha Dolar 2.0"""
from .base_strategy import BaseStrategy
try:
    from ..config import BotConfig
except ImportError:
    from config import BotConfig
import statistics


class AlphaPerfil(BaseStrategy):
    def __init__(self, trading_mode=None, risk_mode=None):
        super().__init__(name="Alpha Perfil")
        self.config = None  # injetado pelo bot.py logo apos a criacao

        perfis = {
            'fast':     {'lookback_period': 3, 'min_consecutive': 1, 'confidence_threshold': 0.30},
            'faster':   {'lookback_period': 3, 'min_consecutive': 1, 'confidence_threshold': 0.30},
            'balanced': {'lookback_period': 4, 'min_consecutive': 2, 'confidence_threshold': 0.45},
            'precise':  {'lookback_period': 5, 'min_consecutive': 2, 'confidence_threshold': 0.60},
            'slow':     {'lookback_period': 6, 'min_consecutive': 3, 'confidence_threshold': 0.70},
        }
        perfil = perfis.get(trading_mode, perfis['balanced'])
        self.lookback_period = perfil['lookback_period']
        self.min_consecutive = perfil['min_consecutive']
        self.confidence_threshold = perfil['confidence_threshold']

        # Faixa de multiplicador que o Perfil escolhe sozinho, conforme a
        # volatilidade medida ao vivo -- mercado calmo usa menos, mercado
        # agitado usa mais, sempre dentro desse teto de seguranca.
        self.MULT_MIN = 1.0
        self.MULT_MAX = 3.0

        print(f"🪞 Alpha Perfil | Modo: {trading_mode or 'balanced'} | multiplicador ajustado pela volatilidade ao vivo")

    def _calcular_volatilidade(self, precos):
        """Desvio padrao percentual -- mesma formula usada no radar do Esquadrao."""
        if len(precos) < 10:
            return 0.0
        media = statistics.mean(precos)
        if media == 0:
            return 0.0
        desvio = statistics.pstdev(precos)
        return (desvio / media) * 100

    def _ajustar_multiplicador(self):
        """Escreve o multiplicador calculado direto na config compartilhada com
        o bot -- no proximo trade, o bot.py ja usa esse valor novo sozinho,
        sem precisar de nenhuma mudanca la."""
        if self.config is None:
            return
        precos = self.get_tick_prices(30)
        vol = self._calcular_volatilidade(precos)
        mult = self.MULT_MIN + min(vol / 0.5, 1.0) * (self.MULT_MAX - self.MULT_MIN)
        self.config.MULTIPLICADOR_ACELERADOR = round(mult, 2)

    def should_enter(self, tick_data):
        self.update_tick(tick_data)
        self._ajustar_multiplicador()

        if not self.is_ready():
            return False, None, 0.0

        trend = self.calculate_trend(self.lookback_period)
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
        cfg = self.config or BotConfig
        return {
            "contract_type": direction,
            "duration": getattr(cfg, 'DURATION', 1),
            "duration_unit": getattr(cfg, 'DURATION_UNIT', 't'),
            "symbol": cfg.DEFAULT_SYMBOL,
            "basis": getattr(cfg, 'BASIS', 'stake'),
        }

    def get_info(self):
        mult_atual = getattr(self.config, 'MULTIPLICADOR_ACELERADOR', None) if self.config else None
        return {'name': self.name, 'tier': 'FREE', 'multiplicador_atual': mult_atual}
