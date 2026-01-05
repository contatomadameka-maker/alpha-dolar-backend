"""
Alpha Bot Balanced - Estratégia Intermediária
Balanceada entre velocidade e precisão
Win Rate esperado: 55-60%
Frequência: 2-5 trades/hora
"""
from .base_strategy import BaseStrategy
from ..config import BotConfig
import statistics
class AlphaBotBalanced(BaseStrategy):
    """Estratégia balanceada - nem muito lenta, nem muito agressiva"""
    def __init__(self):
        super().__init__(name="Alpha Bot Balanced")
        self.min_history = 20  # Só precisa de 20 ticks (vs 100+ do AlphaBot1)
        self.last_signal_tick = 0
        self.cooldown_ticks = 8  # Espera 8 ticks entre sinais
    def should_enter(self, tick_data):
        """
        Estratégia baseada em:
        - Momentum de curto prazo (últimos 10 ticks)
        - Reversão à média
        - Volatilidade moderada
        """
        self.update_tick(tick_data)
        # Precisa de histórico mínimo
        if len(self.ticks_history) < self.min_history:
            return False, None, 0.0
        # Cooldown entre operações
        ticks_since_last = len(self.ticks_history) - self.last_signal_tick
        if ticks_since_last < self.cooldown_ticks:
            return False, None, 0.0
        try:
            # Pega últimos ticks
            min_conditions = 3
            recent_10 = self.ticks_history[-10:]  # Curtíssimo prazo
            recent_20 = self.ticks_history[-20:]  # Curto prazo

            current_price = recent_10[-1]

            # Calcula médias
            ma_10 = statistics.mean(recent_10)
            ma_20 = statistics.mean(recent_20)

            # Calcula momentum (velocidade de mudança)
            momentum = (recent_10[-1] - recent_10[0]) / recent_10[0] * 100

            # Calcula volatilidade (desvio padrão)
            volatility = statistics.stdev(recent_10) if len(recent_10) > 1 else 0

            # Distância da média de 20
            distance_from_ma = ((current_price - ma_20) / ma_20) * 100

            # ==== LÓGICA DE ENTRADA ====

            # Sinal de CALL (compra)
            call_conditions = [
                current_price < ma_20,  # Preço abaixo da média (oversold)
                momentum < -0.05,  # Momentum negativo (caindo)
                distance_from_ma < -0.15,  # Pelo menos 0.15% abaixo da média
                volatility > 0.1  # Volatilidade mínima
            ]

            # Sinal de PUT (venda)
            put_conditions = [
                current_price > ma_20,  # Preço acima da média (overbought)
                momentum > 0.05,  # Momentum positivo (subindo)
                distance_from_ma > 0.15,  # Pelo menos 0.15% acima da média
                volatility > 0.1  # Volatilidade mínima
            ]

            # Conta quantas condições foram atendidas
            call_score = sum(call_conditions)
            put_score = sum(put_conditions)

            # Precisa de pelo menos 3 de 4 condições
            min_conditions = 3

            if call_score >= min_conditions:
                confidence = (call_score / 4) * 0.85 + 0.15  # 65-85%
                self.last_signal_tick = len(self.ticks_history)
                return True, "CALL", confidence

            if put_score >= min_conditions:
                confidence = (put_score / 4) * 0.85 + 0.15  # 65-85%
                self.last_signal_tick = len(self.ticks_history)
                return True, "PUT", confidence

            # Nenhum sinal forte
            return False, None, 0.0

        except Exception as e:
            print(f"⚠️ Erro na análise: {e}")
            return False, None, 0.0

    def get_contract_params(self, direction):
        """Retorna parâmetros do contrato"""
        return {
            "contract_type": direction,
            "duration": 1,  # 1 tick
            "duration_unit": "t",
            "symbol": BotConfig.DEFAULT_SYMBOL,
            "basis": BotConfig.BASIS
        }

    def get_info(self):
        """Informações da estratégia"""
        return {
            'name': self.name,
            'tier': 'Intermediária',
            'min_history': self.min_history,
            'cooldown': self.cooldown_ticks,
            'expected_win_rate': '55-60%',
            'trades_per_hour': '2-5',
            'indicators': 'MA10, MA20, Momentum, Volatilidade',
            'risk_level': 'Médio'
        }
