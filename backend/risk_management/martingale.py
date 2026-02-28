"""
Sistema de Martingale para gestão de progressão
Alpha Dolar 2.0
PATCH 28/02: reset() exposto, step nunca fica negativo, get_info() sempre seguro
"""
try:
    from ..config import BotConfig
except ImportError:
    from config import BotConfig


class Martingale:
    """Gerencia progressão de stake com Martingale"""

    def __init__(self, stake_inicial=None, multiplicador=None, max_steps=None):
        self.stake_inicial = stake_inicial or BotConfig.STAKE_INICIAL
        self.multiplicador = multiplicador or BotConfig.MULTIPLICADOR_MARTINGALE
        self.max_steps     = max_steps or BotConfig.MAX_MARTINGALE_STEPS

        self.stake_atual       = self.stake_inicial
        self.step_atual        = 0
        self.total_investido   = 0.0
        self.ciclos_completos  = 0

    def calcular_proximo_stake(self, vitoria=False):
        """
        Calcula o próximo stake baseado em vitória ou derrota.
        FIX: ao atingir max_steps, reseta sem silenciosamente desaparecer.
        """
        if vitoria:
            self.stake_atual  = self.stake_inicial
            self.step_atual   = 0
            self.ciclos_completos += 1
        else:
            if self.step_atual < self.max_steps:
                self.step_atual  += 1
                self.stake_atual  = round(self.stake_inicial * (self.multiplicador ** self.step_atual), 2)
            else:
                # FIX: atingiu max_steps → reseta ciclo mas NÃO zera perda_acumulada no bot
                # (isso é responsabilidade do bot.py, não do Martingale)
                self.stake_atual = self.stake_inicial
                self.step_atual  = 0
                self.ciclos_completos += 1
                print(f"[martingale] ⚠️ Max steps atingido — resetando ciclo (ciclo #{self.ciclos_completos})")

        return round(self.stake_atual, 2)

    def reset(self):
        """Reset completo do martingale — chamado pelo bot.py quando necessário"""
        self.stake_atual      = self.stake_inicial
        self.step_atual       = 0
        self.total_investido  = 0.0
        # FIX: não reseta ciclos_completos — mantém histórico

    def pode_continuar(self, saldo_disponivel):
        """Verifica se tem saldo suficiente para o próximo stake de recuperação"""
        # Calcula qual seria o stake do próximo step
        proximo_step  = min(self.step_atual + 1, self.max_steps)
        proximo_stake = round(self.stake_inicial * (self.multiplicador ** proximo_step), 2)
        return saldo_disponivel >= proximo_stake

    def registrar_trade(self, valor):
        """Registra valor investido em trade"""
        self.total_investido += valor

    def get_info(self):
        """Retorna informações do estado atual — sempre seguro"""
        proximo_step  = min(self.step_atual + 1, self.max_steps)
        proximo_stake = round(self.stake_inicial * (self.multiplicador ** proximo_step), 2)
        return {
            "stake_atual":            round(self.stake_atual, 2),
            "step_atual":             self.step_atual,
            "max_steps":              self.max_steps,
            "total_investido":        round(self.total_investido, 2),
            "ciclos_completos":       self.ciclos_completos,
            "proximo_stake_derrota":  proximo_stake,
            "stake_inicial":          round(self.stake_inicial, 2),
        }


class AntiMartingale(Martingale):
    """
    Sistema Anti-Martingale (Paroli) — aumenta após vitória, reseta após derrota.
    """

    def calcular_proximo_stake(self, vitoria=False):
        if vitoria:
            if self.step_atual < self.max_steps:
                self.step_atual  += 1
                self.stake_atual  = round(self.stake_inicial * (self.multiplicador ** self.step_atual), 2)
            else:
                self.stake_atual = self.stake_inicial
                self.step_atual  = 0
                self.ciclos_completos += 1
        else:
            self.stake_atual = self.stake_inicial
            self.step_atual  = 0
        return round(self.stake_atual, 2)


class DAlembert:
    """
    Sistema D'Alembert — progressão aritmética, mais conservador que Martingale.
    """

    def __init__(self, stake_inicial=None, incremento=None, max_steps=None):
        self.stake_inicial    = stake_inicial or BotConfig.STAKE_INICIAL
        self.incremento       = incremento or 1.0
        self.max_steps        = max_steps or BotConfig.MAX_MARTINGALE_STEPS

        self.stake_atual      = self.stake_inicial
        self.step_atual       = 0
        self.total_investido  = 0.0
        self.ciclos_completos = 0

    def calcular_proximo_stake(self, vitoria=False):
        if vitoria:
            if self.step_atual > 0:
                self.step_atual -= 1
                self.stake_atual -= self.incremento
            else:
                self.ciclos_completos += 1
            self.stake_atual = max(self.stake_atual, self.stake_inicial)
        else:
            if self.step_atual < self.max_steps:
                self.step_atual  += 1
                self.stake_atual += self.incremento
            else:
                self.stake_atual = self.stake_inicial
                self.step_atual  = 0
        return round(self.stake_atual, 2)

    def reset(self):
        self.stake_atual     = self.stake_inicial
        self.step_atual      = 0
        self.total_investido = 0.0

    def pode_continuar(self, saldo_disponivel):
        return saldo_disponivel >= (self.stake_atual + self.incremento)

    def registrar_trade(self, valor):
        self.total_investido += valor

    def get_info(self):
        return {
            "stake_atual":             round(self.stake_atual, 2),
            "step_atual":              self.step_atual,
            "max_steps":               self.max_steps,
            "total_investido":         round(self.total_investido, 2),
            "ciclos_completos":        self.ciclos_completos,
            "proximo_stake_derrota":   round(self.stake_atual + self.incremento, 2),
            "proximo_stake_vitoria":   round(max(self.stake_atual - self.incremento, self.stake_inicial), 2),
        }


class Fibonacci:
    """
    Sistema Fibonacci — 1,1,2,3,5,8,13,21...
    Após vitória volta 2 passos; após derrota avança 1.
    """

    def __init__(self, stake_inicial=None, max_steps=None):
        self.stake_inicial    = stake_inicial or BotConfig.STAKE_INICIAL
        self.max_steps        = max_steps or 10
        self.fibonacci        = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

        self.step_atual       = 0
        self.stake_atual      = self.stake_inicial
        self.total_investido  = 0.0
        self.ciclos_completos = 0

    def calcular_proximo_stake(self, vitoria=False):
        if vitoria:
            self.step_atual = max(0, self.step_atual - 2)
            if self.step_atual == 0:
                self.ciclos_completos += 1
        else:
            if self.step_atual < len(self.fibonacci) - 1 and self.step_atual < self.max_steps:
                self.step_atual += 1
            else:
                self.step_atual = 0

        self.stake_atual = round(self.stake_inicial * self.fibonacci[self.step_atual], 2)
        return self.stake_atual

    def reset(self):
        self.step_atual      = 0
        self.stake_atual     = self.stake_inicial
        self.total_investido = 0.0

    def pode_continuar(self, saldo_disponivel):
        proximo_step  = min(self.step_atual + 1, len(self.fibonacci) - 1)
        proximo_stake = self.stake_inicial * self.fibonacci[proximo_step]
        return saldo_disponivel >= proximo_stake

    def registrar_trade(self, valor):
        self.total_investido += valor

    def get_info(self):
        return {
            "stake_atual":      round(self.stake_atual, 2),
            "step_atual":       self.step_atual,
            "fibonacci_atual":  self.fibonacci[self.step_atual],
            "max_steps":        self.max_steps,
            "total_investido":  round(self.total_investido, 2),
            "ciclos_completos": self.ciclos_completos,
        }


# ===== TESTE =====
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎰 TESTE DE SISTEMAS DE PROGRESSÃO")
    print("="*60 + "\n")

    print("📊 MARTINGALE (stake_inicial=0.35, mult=2.27, max=3):")
    print("-" * 50)
    m = Martingale(stake_inicial=0.35, multiplicador=2.27, max_steps=3)
    for i, won in enumerate([False, False, False, True]):
        stake = m.calcular_proximo_stake(won)
        m.registrar_trade(stake)
        print(f"  Trade {i+1}: {'✅ WIN' if won else '❌ LOSS'} → stake: ${stake:.2f} | step: {m.step_atual} | info: {m.get_info()}")

    print(f"\n  Sequência real do log:")
    m2 = Martingale(stake_inicial=0.35, multiplicador=2.27, max_steps=3)
    for won in [False, False, False, False]:  # 4 derrotas seguidas como no log
        stake = m2.calcular_proximo_stake(won)
        m2.registrar_trade(stake)
        print(f"  LOSS → próximo stake: ${stake:.2f} | step: {m2.step_atual}/{m2.max_steps}")
