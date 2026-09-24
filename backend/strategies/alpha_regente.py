"""Alpha Regente — detecta o regime do mercado (Tendencia / Lateral /
Disparada) e escolhe o mecanismo certo para cada um: Multiplier para
tendencia clara, Rise/Fall para mercado lateral, e evita entrar durante
uma disparada. Reaproveita a mesma matematica do radar do Alpha Esquadrao.
Alpha Dolar 2.0"""
from .base_strategy import BaseStrategy
try:
    from ..config import BotConfig
except ImportError:
    from config import BotConfig
import statistics


class AlphaRegente(BaseStrategy):
    def __init__(self, trading_mode=None, risk_mode=None):
        super().__init__(name="Alpha Regente")
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

        # Limiares do regime -- calibraveis, comecam conservadores
        self.TENDENCIA_MIN = 65.0     # forca de tendencia (0-100) para considerar Multiplier
        self.DISPARADA_MOMENTUM = 0.8  # variacao % brusca numa janela curta = disparada, evita entrar

        self.ultimo_regime = 'lateral'
        self.ultimo_regime_motivo = ''

        print(f"👑 Alpha Regente | Modo: {trading_mode or 'balanced'} | decide Multiplier x Rise/Fall pelo regime ao vivo")

    def _volatilidade(self, precos):
        if len(precos) < 10:
            return 0.0
        media = statistics.mean(precos)
        if media == 0:
            return 0.0
        return (statistics.pstdev(precos) / media) * 100

    def _forca_tendencia(self, precos):
        if len(precos) < 10:
            return 0.0
        subidas = descidas = 0
        for i in range(1, len(precos)):
            if precos[i] > precos[i - 1]:
                subidas += 1
            elif precos[i] < precos[i - 1]:
                descidas += 1
        total = subidas + descidas or 1
        return abs(subidas - descidas) / total * 100

    def _momentum_curto(self, precos_curtos):
        if len(precos_curtos) < 4 or precos_curtos[0] == 0:
            return 0.0
        return abs((precos_curtos[-1] - precos_curtos[0]) / precos_curtos[0]) * 100

    def _detectar_regime(self):
        """Le os ticks recentes e decide Tendencia / Lateral / Disparada,
        guardando o resultado para get_contract_params usar em seguida."""
        precos_longos = self.get_tick_prices(40)
        precos_curtos = self.get_tick_prices(6)

        momentum = self._momentum_curto(precos_curtos)
        if momentum >= self.DISPARADA_MOMENTUM:
            self.ultimo_regime = 'disparada'
            self.ultimo_regime_motivo = f'variacao brusca de {momentum:.2f}% nos ultimos ticks'
            return

        forca = self._forca_tendencia(precos_longos)
        if forca >= self.TENDENCIA_MIN:
            self.ultimo_regime = 'tendencia'
            self.ultimo_regime_motivo = f'forca de tendencia {forca:.0f}%'
            return

        self.ultimo_regime = 'lateral'
        self.ultimo_regime_motivo = f'sem tendencia clara ({forca:.0f}%)'

    def should_enter(self, tick_data):
        self.update_tick(tick_data)
        self._detectar_regime()

        if not self.is_ready():
            return False, None, 0.0

        if self.ultimo_regime == 'disparada':
            # Seguranca: nao entra durante um movimento brusco e imprevisivel
            return False, None, 0.0

        trend = self.calculate_trend(self.lookback_period)
        pattern = self.detect_pattern("consecutive")

        if trend == "UP":
            consecutive = pattern.get("consecutive_ups", 0)
            direction = "CALL"
        elif trend == "DOWN":
            consecutive = pattern.get("consecutive_downs", 0)
            direction = "PUT"
        else:
            return False, None, 0.0

        if consecutive < self.min_consecutive:
            return False, None, 0.0

        confidence = min(consecutive / (self.lookback_period * 1.5), 1.0)
        if confidence < self.confidence_threshold:
            return False, None, 0.0

        self.last_signal = direction
        self.signal_count += 1
        return True, direction, confidence

    def get_contract_params(self, direction):
        cfg = self.config or BotConfig

        if self.ultimo_regime == 'tendencia':
            stake_base = getattr(cfg, 'STAKE_INICIAL', 1.0)
            return {
                "contract_type": "MULTUP" if direction == "CALL" else "MULTDOWN",
                "symbol": cfg.DEFAULT_SYMBOL,
                "multiplier": getattr(cfg, 'REGENTE_MULTIPLIER', 20),
                "stop_loss": getattr(cfg, 'REGENTE_STOP_USD', round(stake_base * 3, 2)),
                "take_profit": getattr(cfg, 'REGENTE_TP_USD', round(stake_base * 2, 2)),
            }

        return {
            "contract_type": direction,
            "duration": getattr(cfg, 'DURATION', 1),
            "duration_unit": getattr(cfg, 'DURATION_UNIT', 't'),
            "symbol": cfg.DEFAULT_SYMBOL,
            "basis": getattr(cfg, 'BASIS', 'stake'),
        }

    def get_info(self):
        return {
            'name': self.name, 'tier': 'FREE',
            'regime_atual': self.ultimo_regime,
            'regime_motivo': self.ultimo_regime_motivo,
        }
