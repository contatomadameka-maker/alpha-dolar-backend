"""
Sistema de Stop Loss e Take Profit
Alpha Dolar 2.0
FIX 28/02: Lógica DC Bot — perda acumulada desde último ganho, reseta ao ganhar
           Corrige bug abs(saldo_liquido) que parava o bot com LUCRO
"""
from datetime import datetime

try:
    from ..config import BotConfig
except ImportError:
    from config import BotConfig

class StopLoss:
    """Gerencia limites de perda e ganho"""

    def __init__(self, limite_perda=None, lucro_alvo=None, stop_loss_type=None, max_consecutive_losses=None):
        self.limite_perda = limite_perda or BotConfig.LIMITE_PERDA
        self.lucro_alvo = lucro_alvo or BotConfig.LUCRO_ALVO
        self.stop_loss_type = stop_loss_type or BotConfig.STOP_LOSS_TYPE
        self.max_consecutive_losses = max_consecutive_losses or BotConfig.MAX_CONSECUTIVE_LOSSES

        # Estatísticas
        self.lucro_total = 0.0
        self.perda_total = 0.0
        self.saldo_liquido = 0.0
        self.vitorias = 0
        self.derrotas = 0
        self.perdas_consecutivas = 0
        self.vitorias_consecutivas = 0
        self.max_perdas_consecutivas = 0
        self.max_vitorias_consecutivas = 0

        # ✅ DC Bot: perda acumulada desde o último ganho (reseta ao ganhar)
        self._perda_desde_ultimo_ganho = 0.0

        # Histórico
        self.historico_trades = []
        self.inicio_sessao = datetime.now()

    def registrar_trade(self, profit, vitoria=True):
        if vitoria:
            self.vitorias += 1
            self.lucro_total += abs(profit)
            self.vitorias_consecutivas += 1
            self.perdas_consecutivas = 0
            # ✅ DC Bot: reseta ao ganhar
            self._perda_desde_ultimo_ganho = 0.0
            if self.vitorias_consecutivas > self.max_vitorias_consecutivas:
                self.max_vitorias_consecutivas = self.vitorias_consecutivas
        else:
            self.derrotas += 1
            self.perda_total += abs(profit)
            self.perdas_consecutivas += 1
            self.vitorias_consecutivas = 0
            # ✅ DC Bot: acumula perda desde último ganho
            self._perda_desde_ultimo_ganho += abs(profit)
            if self.perdas_consecutivas > self.max_perdas_consecutivas:
                self.max_perdas_consecutivas = self.perdas_consecutivas

        self.saldo_liquido += profit

        trade_info = {
            "timestamp": datetime.now(),
            "profit": profit,
            "vitoria": vitoria,
            "saldo_liquido": self.saldo_liquido,
            "perdas_consecutivas": self.perdas_consecutivas,
            "vitorias_consecutivas": self.vitorias_consecutivas,
            "perda_desde_ultimo_ganho": round(self._perda_desde_ultimo_ganho, 2),
        }
        self.historico_trades.append(trade_info)
        return trade_info

    def deve_parar(self, proximo_stake: float = 0.0):
        """
        ✅ FIX DC Bot: usa _perda_desde_ultimo_ganho em vez de abs(saldo_liquido)
           - Para APENAS quando há perda real acumulada >= limite
           - NÃO para quando há lucro (bug anterior com abs())
           - proximo_stake: verificação preventiva ANTES de abrir o trade
        """
        # Take profit
        if self.saldo_liquido >= self.lucro_alvo:
            return True, f"🎯 Lucro alvo atingido! ${self.saldo_liquido:.2f}"

        # Stop loss por valor
        if self.stop_loss_type in ("value", None, ""):
            # ✅ Perda já atingiu o limite
            if self._perda_desde_ultimo_ganho >= self.limite_perda:
                return True, f"🛑 Limite de perda atingido! Perda acumulada: ${self._perda_desde_ultimo_ganho:.2f}"
            # ✅ Preventivo: perda + próximo stake ultrapassaria o limite
            if proximo_stake > 0 and (self._perda_desde_ultimo_ganho + proximo_stake) > self.limite_perda:
                return True, (
                    f"🛑 Stop preventivo: perda=${self._perda_desde_ultimo_ganho:.2f} + "
                    f"stake=${proximo_stake:.2f} > limite=${self.limite_perda:.2f}"
                )

        # Stop loss por perdas consecutivas
        elif self.stop_loss_type == "consecutive_losses":
            if self.perdas_consecutivas >= self.max_consecutive_losses:
                return True, f"🛑 {self.perdas_consecutivas} perdas consecutivas!"

        return False, ""

    def pode_operar(self, saldo_atual):
        if saldo_atual < BotConfig.MIN_BALANCE:
            return False, f"⚠️ Saldo abaixo do mínimo! ${saldo_atual:.2f} < ${BotConfig.MIN_BALANCE:.2f}"
        deve_parar, motivo = self.deve_parar()
        if deve_parar:
            return False, motivo
        return True, "✅ Pode operar"

    def get_win_rate(self):
        total = self.vitorias + self.derrotas
        if total == 0:
            return 0.0
        return (self.vitorias / total) * 100

    def get_estatisticas(self):
        total_trades = self.vitorias + self.derrotas
        tempo_sessao = datetime.now() - self.inicio_sessao
        return {
            "saldo_liquido":              round(self.saldo_liquido, 2),
            "lucro_total":                round(self.lucro_total, 2),
            "perda_total":                round(self.perda_total, 2),
            "total_trades":               total_trades,
            "vitorias":                   self.vitorias,
            "derrotas":                   self.derrotas,
            "win_rate":                   round(self.get_win_rate(), 2),
            "perdas_consecutivas":        self.perdas_consecutivas,
            "vitorias_consecutivas":      self.vitorias_consecutivas,
            "max_perdas_consecutivas":    self.max_perdas_consecutivas,
            "max_vitorias_consecutivas":  self.max_vitorias_consecutivas,
            "tempo_sessao":               str(tempo_sessao).split('.')[0],
            "lucro_alvo":                 self.lucro_alvo,
            "limite_perda":               self.limite_perda,
            # ✅ DC Bot: perda real desde último ganho
            "perda_desde_ultimo_ganho":   round(self._perda_desde_ultimo_ganho, 2),
            "distancia_lucro_alvo":       round(self.lucro_alvo - self.saldo_liquido, 2),
            "distancia_limite_perda":     round(self.limite_perda - self._perda_desde_ultimo_ganho, 2),
        }

    def reset(self):
        self.lucro_total = 0.0
        self.perda_total = 0.0
        self.saldo_liquido = 0.0
        self.vitorias = 0
        self.derrotas = 0
        self.perdas_consecutivas = 0
        self.vitorias_consecutivas = 0
        self.max_perdas_consecutivas = 0
        self.max_vitorias_consecutivas = 0
        self._perda_desde_ultimo_ganho = 0.0
        self.historico_trades = []
        self.inicio_sessao = datetime.now()

    def reset_diario(self):
        self.saldo_liquido = 0.0
        self.perdas_consecutivas = 0
        self.vitorias_consecutivas = 0
        self._perda_desde_ultimo_ganho = 0.0
        self.inicio_sessao = datetime.now()


class TrailingStop:
    """Stop Loss Dinâmico (Trailing Stop)"""

    def __init__(self, trailing_distance=None, activation_profit=None):
        self.trailing_distance = trailing_distance or 10.0
        self.activation_profit = activation_profit or 5.0
        self.stop_loss_nivel = None
        self.maior_lucro = 0.0
        self.ativado = False

    def atualizar(self, lucro_atual):
        if not self.ativado and lucro_atual >= self.activation_profit:
            self.ativado = True
            self.stop_loss_nivel = lucro_atual - self.trailing_distance
        if self.ativado:
            if lucro_atual > self.maior_lucro:
                self.maior_lucro = lucro_atual
                self.stop_loss_nivel = lucro_atual - self.trailing_distance
        return {
            "ativado": self.ativado,
            "stop_loss_nivel": self.stop_loss_nivel,
            "maior_lucro": self.maior_lucro,
            "lucro_atual": lucro_atual
        }

    def deve_parar(self, lucro_atual):
        if self.ativado and self.stop_loss_nivel is not None:
            return lucro_atual <= self.stop_loss_nivel
        return False

    def reset(self):
        self.stop_loss_nivel = None
        self.maior_lucro = 0.0
        self.ativado = False


class SessionManager:
    """Gerencia sessões de trading (diário, semanal, mensal)"""

    def __init__(self):
        self.sessao_diaria   = StopLoss()
        self.sessao_semanal  = StopLoss()
        self.sessao_mensal   = StopLoss()
        self.sessao_total    = StopLoss()
        self.ultimo_dia      = datetime.now().day
        self.ultima_semana   = datetime.now().isocalendar()[1]
        self.ultimo_mes      = datetime.now().month

    def registrar_trade(self, profit, vitoria=True):
        agora = datetime.now()
        if agora.day != self.ultimo_dia:
            self.sessao_diaria.reset_diario()
            self.ultimo_dia = agora.day
        if agora.isocalendar()[1] != self.ultima_semana:
            self.sessao_semanal.reset_diario()
            self.ultima_semana = agora.isocalendar()[1]
        if agora.month != self.ultimo_mes:
            self.sessao_mensal.reset_diario()
            self.ultimo_mes = agora.month
        self.sessao_diaria.registrar_trade(profit, vitoria)
        self.sessao_semanal.registrar_trade(profit, vitoria)
        self.sessao_mensal.registrar_trade(profit, vitoria)
        self.sessao_total.registrar_trade(profit, vitoria)

    def get_resumo(self):
        return {
            "hoje":   self.sessao_diaria.get_estatisticas(),
            "semana": self.sessao_semanal.get_estatisticas(),
            "mes":    self.sessao_mensal.get_estatisticas(),
            "total":  self.sessao_total.get_estatisticas()
        }
