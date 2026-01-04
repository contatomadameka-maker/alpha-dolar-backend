"""
Configurações do Alpha Dolar 2.0
"""
import os

class BotConfig:
    """Configurações do bot de trading"""
    
    # Token Deriv (vem de variável de ambiente)
    DERIV_TOKEN = os.getenv('DERIV_TOKEN', '')
    
    # Configurações de trading
    DEFAULT_SYMBOL = "R_100"
    STAKE_INICIAL = 0.35
    LUCRO_ALVO = 2.0
    LIMITE_PERDA = 5.0
    BASIS = "stake"
    
    # Configurações de martingale
    MARTINGALE_MULTIPLIER = 2.0
    MAX_MARTINGALE_STEPS = 3
    
    # Configurações de conexão
    DERIV_WEBSOCKET_URL = "wss://ws.binaryws.com/websockets/v3"
    TIMEOUT_SECONDS = 30
    
    # Logging
    LOG_LEVEL = "INFO"
    
    @classmethod
    def validate(cls):
        """Valida se as configurações estão corretas"""
        if not cls.DERIV_TOKEN:
            raise ValueError("DERIV_TOKEN não configurado!")
        
        if cls.STAKE_INICIAL <= 0:
            raise ValueError("STAKE_INICIAL deve ser maior que zero")
        
        return True

# Função fora da classe
def validate_config():
    """Valida se as configurações estão corretas"""
    if not BotConfig.DERIV_TOKEN:
        raise ValueError("DERIV_TOKEN não configurado!")
    
    if BotConfig.STAKE_INICIAL <= 0:
        raise ValueError("STAKE_INICIAL deve ser maior que zero")
    
    return True
