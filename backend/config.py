"""
Configurações do Deriv Bot
Alpha Dolar 2.0
"""
from enum import Enum

class TradingMode(Enum):
    BAIXO_RISCO = "baixo_risco"
    PRECISO     = "preciso"
    BALANCEADO  = "balanceado"
    VELOZ       = "veloz"

class RiskManagement(Enum):
    QUANTIA_FIXA = "quantia_fixa"
    CONSERVADOR  = "conservador"
    OTIMIZADO    = "otimizado"
    AGRESSIVO    = "agressivo"

class BotConfig:
    API_TOKEN       = "a1-TD8gXQ9R8UGFLMH3rrfrJdtYQkN8k"
    APP_ID          = "128988"
    DEFAULT_SYMBOL  = "R_100"
    DEFAULT_STRATEGY = "alpha_bot_1"
    TRADING_MODE    = TradingMode.VELOZ
    RISK_MANAGEMENT = RiskManagement.CONSERVADOR

    STAKE_INICIAL   = 0.35
    LUCRO_ALVO      = 2.0
    LIMITE_PERDA    = 5.0

    USAR_MARTINGALE          = True
    MULTIPLICADOR_MARTINGALE = 2.0
    MAX_MARTINGALE_STEPS     = 3

    DURATION      = 1
    DURATION_UNIT = "t"
    BASIS         = "stake"

    MAX_TRADES_PER_DAY = 100
    MIN_BALANCE        = 0.35   # ✅ Igual ao stake mínimo da Deriv

    STOP_LOSS_TYPE         = "value"
    MAX_CONSECUTIVE_LOSSES = 5

    LOG_LEVEL   = "INFO"
    LOG_TO_FILE = True
    LOG_FILE    = "alpha_dolar.log"

    BOT_NAME    = "Alpha Dolar 2.0"
    BOT_VERSION = "2.0.0"
    BOT_AUTHOR  = "Dirlei Luis"

class StrategyConfig:
    DC_BOT_1   = {"name": "DC Bot 1",   "type": "rise_fall", "min_balance": 1.0}
    DC_BOT_2   = {"name": "DC Bot 2",   "type": "digits",    "min_balance": 1.0}
    ALPHA_MIND = {"name": "AlphaMind",  "type": "advanced",  "min_balance": 10.0, "vip": True}

class MarketConfig:
    VOLATILITY_INDICES = {
        "R_10":    {"name": "Volatility 10 Index",       "tick_interval": 2},
        "R_25":    {"name": "Volatility 25 Index",       "tick_interval": 2},
        "R_50":    {"name": "Volatility 50 Index",       "tick_interval": 2},
        "R_75":    {"name": "Volatility 75 Index",       "tick_interval": 2},
        "R_100":   {"name": "Volatility 100 Index",      "tick_interval": 2},
        "1HZ10V":  {"name": "Volatility 10 (1s) Index",  "tick_interval": 1},
        "1HZ25V":  {"name": "Volatility 25 (1s) Index",  "tick_interval": 1},
        "1HZ50V":  {"name": "Volatility 50 (1s) Index",  "tick_interval": 1},
        "1HZ75V":  {"name": "Volatility 75 (1s) Index",  "tick_interval": 1},
        "1HZ100V": {"name": "Volatility 100 (1s) Index", "tick_interval": 1},
    }
    JUMP_INDICES = {
        "JD10":  {"name": "Jump 10 Index"},
        "JD25":  {"name": "Jump 25 Index"},
        "JD50":  {"name": "Jump 50 Index"},
        "JD75":  {"name": "Jump 75 Index"},
        "JD100": {"name": "Jump 100 Index"},
    }
    CRASH_BOOM = {
        "BOOM1000":   {"name": "Boom 1000 Index"},
        "BOOM500":    {"name": "Boom 500 Index"},
        "CRASH1000":  {"name": "Crash 1000 Index"},
        "CRASH500":   {"name": "Crash 500 Index"},
    }

def validate_config():
    """
    Valida apenas parâmetros essenciais.
    ✅ NÃO compara stake com MIN_BALANCE — o stake vem do frontend e pode ser qualquer valor válido.
    """
    errors = []

    if BotConfig.STAKE_INICIAL < 0.35:
        errors.append("⚠️ Stake inicial muito baixo! Mínimo da Deriv: $0.35")

    if BotConfig.LUCRO_ALVO <= 0:
        errors.append("⚠️ Lucro alvo deve ser maior que zero!")

    if BotConfig.LIMITE_PERDA <= 0:
        errors.append("⚠️ Limite de perda deve ser maior que zero!")

    if errors:
        print("\n❌ ERROS DE CONFIGURAÇÃO:")
        for error in errors:
            print(f"  {error}")
        print()
        return False

    print("✅ Configurações validadas com sucesso!")
    return True

if __name__ == "__main__":
    validate_config()
