"""
Módulo de Estratégias de Trading
Alpha Dolar 2.0
"""
from .base_strategy import BaseStrategy
from .alpha_bot_1 import AlphaBot1
from .alpha_bot_4_digit import AlphaBot4DigitPattern
from .digit_sniper import DigitSniper
from .digit_pulse import DigitPulse
from .mega_digit import MegaDigit1, MegaDigit2

__all__ = [
    'BaseStrategy',
    'AlphaBot1',
    'AlphaBot4DigitPattern',
    'DigitSniper',
    'DigitPulse',
    'MegaDigit1',
    'MegaDigit2',
]

def get_strategy(key):
    STRATEGY_MAP = {
        'alpha_bot_1':  AlphaBot1,
        'alpha_bot_4':  AlphaBot4DigitPattern,
        'digit_sniper': DigitSniper,
        'digit_pulse':  DigitPulse,
        'mega_digit_1': MegaDigit1,
        'mega_digit_2': MegaDigit2,
    }
    cls = STRATEGY_MAP.get(key)
    if cls is None:
        raise ValueError(f"Estratégia '{key}' não encontrada.")
    return cls()
