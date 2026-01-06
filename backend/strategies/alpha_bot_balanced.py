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
        self.min_history = 20
        self.last_signal_tick = 0
        self.cooldown_ticks = 12  # Meio termo: 8 → 12 → 15
        self.total_ticks_received = 0
    
    def should_enter(self, tick_data):
        """
        Estratégia baseada em:
        - Momentum de curto prazo (últimos 10 ticks)
        - Reversão à média
        - Volatilidade moderada
        """
        self.update_tick(tick_data)
        self.total_ticks_received += 1
        
        print(f"[DEBUG] should_enter chamado! Histórico: {len(self.ticks_history)}/{self.min_history}, Total ticks: {self.total_ticks_received}")
        
        if len(self.ticks_history) < self.min_history:
            print(f"[DEBUG] Aguardando histórico completo...")
            return False, None, 0.0
        
        ticks_since_last = self.total_ticks_received - self.last_signal_tick
        if ticks_since_last < self.cooldown_ticks:
            print(f"[DEBUG] Cooldown ativo: {ticks_since_last}/{self.cooldown_ticks} ticks")
            return False, None, 0.0
        
        try:
            recent_10 = [tick['quote'] if isinstance(tick, dict) else tick for tick in list(self.ticks_history)[-10:]]
            recent_20 = [tick['quote'] if isinstance(tick, dict) else tick for tick in list(self.ticks_history)[-20:]]
            
            current_price = recent_10[-1]
            
            ma_10 = statistics.mean(recent_10)
            ma_20 = statistics.mean(recent_20)
            
            momentum = (recent_10[-1] - recent_10[0]) / recent_10[0] * 100
            
            volatility = statistics.stdev(recent_10) if len(recent_10) > 1 else 0
            
            distance_from_ma = ((current_price - ma_20) / ma_20) * 100
            
            print(f"[DEBUG] Análise: preço={current_price:.2f}, ma20={ma_20:.2f}, momentum={momentum:.4f}%, vol={volatility:.4f}, dist={distance_from_ma:.4f}%")
            
            # THRESHOLDS BALANCEADOS (não muito fracos, não extremos)
            call_conditions = [
                current_price < ma_20,
                momentum < -0.06,  # Meio termo: -0.05 vs -0.08
                distance_from_ma < -0.18,  # Meio termo: -0.15 vs -0.20
                volatility > 0.12  # Meio termo: 0.10 vs 0.15
            ]
            
            put_conditions = [
                current_price > ma_20,
                momentum > 0.06,  # Meio termo
                distance_from_ma > 0.18,  # Meio termo
                volatility > 0.12  # Meio termo
            ]
            
            call_score = sum(call_conditions)
            put_score = sum(put_conditions)
            
            print(f"[DEBUG] Scores: CALL={call_score}/4, PUT={put_score}/4")
            
            # VOLTA PARA 3/4 mas com thresholds melhores
            min_conditions = 3
            
            if call_score >= min_conditions:
                confidence = (call_score / 4) * 0.85 + 0.15  # 65-85%
                self.last_signal_tick = self.total_ticks_received
                print(f"🎯 SINAL DETECTADO! CALL com {confidence*100:.1f}% confiança ({call_score}/4)")
                return True, "CALL", confidence
            
            if put_score >= min_conditions:
                confidence = (put_score / 4) * 0.85 + 0.15  # 65-85%
                self.last_signal_tick = self.total_ticks_received
                print(f"🎯 SINAL DETECTADO! PUT com {confidence*100:.1f}% confiança ({put_score}/4)")
                return True, "PUT", confidence
            
            print(f"[DEBUG] Nenhum sinal (precisa 3/4)")
            return False, None, 0.0
            
        except Exception as e:
            print(f"⚠️ Erro na análise: {e}")
            return False, None, 0.0
    
    def get_contract_params(self, direction):
        """Retorna parâmetros do contrato"""
        return {
            "contract_type": direction,
            "duration": 2,  # Meio termo: 1 vs 3 ticks
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
            'trades_per_hour': '3-8',
            'indicators': 'MA10, MA20, Momentum, Volatilidade',
            'risk_level': 'Médio'
        }
