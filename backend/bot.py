"""
ALPHA DOLAR 2.0 - Bot de Trading Automatizado
Motor Principal do Bot
ATUALIZADO: Integração com 15 estratégias novas
PATCH 28/02: Fix travamento Martingale step 2/3
"""
import time
import sys
from datetime import datetime

try:
    from .config import BotConfig, validate_config
    from .deriv_api import DerivAPI
    from .risk_management.martingale import Martingale
    from .risk_management.stop_loss import StopLoss
except ImportError:
    from config import BotConfig, validate_config
    from deriv_api import DerivAPI
    from risk_management.martingale import Martingale
    from risk_management.stop_loss import StopLoss


class AlphaDolar:
    """Motor principal do bot Alpha Dolar 2.0"""

    def __init__(self, strategy=None, use_martingale=True, bot_number=None):
        self.bot_name = "ALPHA DOLAR 2.0"
        self.version = "2.0.0"

        self.api = DerivAPI()

        if strategy is None:
            raise ValueError("Estratégia não pode ser None!")
        self.strategy = strategy

        self.martingale = Martingale() if use_martingale else None
        self.stop_loss = StopLoss()

        self.is_running = False
        self.current_stake = BotConfig.STAKE_INICIAL
        self.waiting_contract = False
        self.current_contract_id = None

        # Martingale inteligente: rastreia perda acumulada para cálculo exato
        self.perda_acumulada = 0.0
        self.PAYOUT_RATE = 0.88  # retorno médio Deriv (88%)

        self.tick_history = []
        self.max_tick_history = 200

        self.trades_hoje = 0
        self.inicio_sessao = datetime.now()

        # ── FIX: controle de estado para detectar travamento ──────────────────
        self._ultimo_trade_time   = time.time()
        self._ultimo_tick_time    = time.time()
        self._ultimo_sinal_time   = time.time()   # FIX: rastreia último sinal gerado
        self._aguardando_sinal    = False          # FIX: flag explícita de espera de sinal
        self._sem_sinal_streak    = 0             # FIX: quantos ticks consecutivos sem sinal
        # ──────────────────────────────────────────────────────────────────────

    def print_header(self):
        print("\n" + "="*70)
        print(f"🤖 {self.bot_name} v{self.version}")
        print("="*70)
        strategy_name = getattr(self.strategy, 'name', 'Estratégia Personalizada')
        print(f"📊 Estratégia: {strategy_name}")
        if hasattr(self.strategy, 'get_info'):
            info = self.strategy.get_info()
            print(f"   Tipo: {info.get('tier', 'N/A')}")
            print(f"   Contratos: {info.get('contract_type', 'N/A')}")
            print(f"   Indicadores: {info.get('indicators', 'N/A')}")
        print(f"💰 Stake Inicial: ${BotConfig.STAKE_INICIAL}")
        print(f"🎯 Lucro Alvo: ${BotConfig.LUCRO_ALVO}")
        print(f"🛑 Limite Perda: ${BotConfig.LIMITE_PERDA}")
        print(f"⚡ Martingale: {'Ativado' if self.martingale else 'Desativado'}")
        print("="*70 + "\n")

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime('%H:%M:%S')
        emoji = {
            "INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌",
            "WARNING": "⚠️", "TRADE": "💰", "WIN": "🎉", "LOSS": "😞"
        }.get(level, "📝")
        print(f"[{timestamp}] {emoji} {message}")

    def on_tick(self, tick_data):
        # ── FIX: sempre atualizar timestamp de tick ────────────────────────────
        self._ultimo_tick_time = time.time()

        if self.waiting_contract:
            return

        if 'quote' in tick_data:
            price = float(tick_data['quote'])
            self.tick_history.append(price)
            if len(self.tick_history) > self.max_tick_history:
                self.tick_history.pop(0)

        pode_operar, motivo = self.stop_loss.pode_operar(self.api.balance)
        if not pode_operar:
            self._disparar_stop_loss(motivo)
            return

        if self.trades_hoje >= BotConfig.MAX_TRADES_PER_DAY:
            self.log(f"Limite diário de {BotConfig.MAX_TRADES_PER_DAY} trades atingido!", "WARNING")
            self.stop()
            return

        signal_data = self.analyze_strategy(tick_data)

        if signal_data and signal_data.get('signal'):
            direction = signal_data['signal']
            confidence = signal_data.get('confidence', 0)

            # FIX: resetar streak e registrar timestamp do sinal
            self._sem_sinal_streak = 0
            self._ultimo_sinal_time = time.time()
            self._aguardando_sinal = False

            self.log(f"📊 Sinal detectado: {direction} | Confiança: {confidence:.1f}%", "TRADE")
            self.executar_trade(direction, signal_data)
        else:
            # FIX: contar ticks sem sinal para detectar trava
            self._sem_sinal_streak += 1

    def analyze_strategy(self, tick_data):
        if hasattr(self.strategy, 'analyze'):
            if len(self.tick_history) < 30:
                return None
            return self.strategy.analyze(self.tick_history)
        elif hasattr(self.strategy, 'should_enter'):
            should_enter, direction, confidence = self.strategy.should_enter(tick_data)
            if should_enter and direction:
                return {
                    'signal': direction,
                    'confidence': confidence * 100,
                    'contract_type': direction,
                    'parameters': None
                }
        return None

    def _calcular_stake_recuperacao(self):
        """
        Calcula stake para recuperar perda acumulada + lucro mínimo.
        Fórmula: stake = (perda_acumulada + lucro_alvo) / payout_rate
        Onde payout_rate = 0.88 (88% de retorno na Deriv)
        """
        if self.perda_acumulada <= 0:
            return round(BotConfig.STAKE_INICIAL, 2)

        stake_ideal = (self.perda_acumulada + BotConfig.STAKE_INICIAL) / self.PAYOUT_RATE
        # FIX: round() em vez de int() — evita diferença de centavos que causava stake errado
        stake = round(stake_ideal, 2)
        stake = max(round(BotConfig.STAKE_INICIAL, 2), stake)

        # Segurança: não arrisca mais que 30% do saldo
        max_stake = self.api.balance * 0.30
        return round(min(stake, max_stake), 2)

    def _disparar_stop_loss(self, motivo="Stop Loss atingido"):
        """Para o bot imediatamente com mensagem vermelha de stop loss."""
        stats = self.stop_loss.get_estatisticas() if hasattr(self, 'stop_loss') else {}
        perda = abs(stats.get('saldo_liquido', 0))
        limite = BotConfig.LIMITE_PERDA
        self.log(f"🛑 STOP LOSS ATINGIDO! Perda: ${perda:.2f} / Limite: ${limite:.2f}", "STOP_LOSS")
        self.log(f"🛑 Bot encerrado automaticamente por proteção de capital", "STOP_LOSS")
        self.stop()

    def executar_trade(self, direction, signal_data=None):
        # Martingale inteligente: calcula stake para recuperar perda acumulada
        if self.martingale and self.perda_acumulada > 0:
            stake = self._calcular_stake_recuperacao()
        elif hasattr(self.strategy, 'get_stake'):
            stake = self.strategy.get_stake()
        elif self.martingale:
            stake = self.martingale.stake_atual
        else:
            stake = self.current_stake

        if self.api.balance < stake:
            self.log(f"Saldo insuficiente! Necessário: ${stake:.2f} | Disponível: ${self.api.balance:.2f}", "ERROR")
            # FIX: resetar perda acumulada se saldo insuficiente para evitar trava permanente
            if stake > self.api.balance * 0.50:
                self.log("⚠️ Stake muito alto para saldo! Resetando martingale para continuar.", "WARNING")
                self.perda_acumulada = 0.0
                if self.martingale:
                    self.martingale.reset()
            return

        if signal_data and signal_data.get('parameters'):
            params = signal_data['parameters'].copy()
            params['amount'] = stake
            contract_type = signal_data.get('contract_type', direction)
            barrier = params.get('barrier')
        else:
            params = self.strategy.get_contract_params(direction)
            contract_type = params.get("contract_type", direction)
            barrier = None

        log_msg = f"🎯 Executando {contract_type} | Stake: ${stake:.2f} | Perda acum: ${self.perda_acumulada:.2f}"
        if barrier is not None:
            log_msg += f" | Barreira: {barrier}"
        self.log(log_msg, "TRADE")

        proposal_params = {
            'contract_type': contract_type,
            'symbol': params.get("symbol", BotConfig.DEFAULT_SYMBOL),
            'amount': stake,
            'duration': params.get("duration", 1),
            'duration_unit': params.get("duration_unit", "t")
        }
        if barrier is not None:
            proposal_params['barrier'] = barrier

        self._ultimo_stake_usado = stake
        self.api.get_proposal(**proposal_params)
        self.waiting_contract = True
        self.trades_hoje += 1

        # FIX: registrar tempo de início do contrato para watchdog
        self._ultimo_trade_time = time.time()

        if self.martingale:
            self.martingale.registrar_trade(stake)

    def on_contract_update(self, contract_data):
        status = contract_data.get("status")

        # Libera waiting_contract em caso de erro interno
        if (contract_data.get("_timeout") or contract_data.get("_reconnect") or
                contract_data.get("_buy_error") or contract_data.get("_proposal_error")):
            self.log("⚠️ Operação interrompida — liberando bot para próximo sinal", "WARNING")
            self.waiting_contract = False
            self.current_contract_id = None
            # FIX: resetar timers para evitar watchdog falso positivo
            self._ultimo_trade_time = time.time()
            self._ultimo_sinal_time = time.time()
            return

        if status not in ["won", "lost"]:
            return

        profit = float(contract_data.get("profit", 0))
        contract_id = contract_data.get("contract_id")
        vitoria = status == "won"

        # Libera IMEDIATAMENTE — antes de qualquer processamento
        self.waiting_contract = False
        self.current_contract_id = None
        # FIX: resetar AMBOS os timers após resultado
        self._ultimo_trade_time = time.time()
        self._ultimo_sinal_time = time.time()
        self._sem_sinal_streak  = 0

        if vitoria:
            self.log(f"🎉 VITÓRIA! Lucro: ${profit:.2f} | ID: {contract_id}", "WIN")
            self.perda_acumulada = 0.0
        else:
            self.log(f"😞 DERROTA! Perda: ${profit:.2f} | ID: {contract_id}", "LOSS")
            self.perda_acumulada += abs(profit)

        # Atualiza martingale da estratégia
        if hasattr(self.strategy, 'on_trade_result'):
            self.strategy.on_trade_result(vitoria)

        if self.martingale:
            self.martingale.calcular_proximo_stake(vitoria)
            info = self.martingale.get_info()
            proximo = self._calcular_stake_recuperacao() if self.perda_acumulada > 0 else info['stake_atual']
            self.log(
                f"📊 Próximo stake: ${proximo:.2f} | Perda acum: ${self.perda_acumulada:.2f} | "
                f"Step: {info['step_atual']}/{info['max_steps']}",
                "INFO"
            )

        self.stop_loss.registrar_trade(profit, vitoria)
        stats = self.stop_loss.get_estatisticas()
        self.log(
            f"📈 Líquido: ${stats['saldo_liquido']:+.2f} | "
            f"Win Rate: {stats['win_rate']:.1f}% | "
            f"Trades: {stats['total_trades']}",
            "INFO"
        )

        deve_parar, motivo = self.stop_loss.deve_parar()
        if deve_parar:
            self._disparar_stop_loss(motivo)

    def on_balance_update(self, balance):
        self.log(f"💰 Saldo atualizado: ${balance:.2f}", "INFO")

    def start(self):
        try:
            if not validate_config():
                return False

            self.print_header()

            self.log("Conectando à Deriv API...", "INFO")
            if not self.api.connect():
                self.log("Falha na conexão!", "ERROR")
                return False

            self.log("Autorizando...", "INFO")
            if not self.api.authorize():
                self.log("Falha na autorização!", "ERROR")
                return False

            self.log(f"✅ Autorizado! Saldo: ${self.api.balance:.2f} {self.api.currency}", "SUCCESS")

            if self.api.balance <= 0:
                self.log("Saldo zerado! Impossível operar.", "ERROR")
                return False

            self.api.set_tick_callback(self.on_tick)
            self.api.set_contract_callback(self.on_contract_update)
            self.api.set_balance_callback(self.on_balance_update)

            self.api.subscribe_ticks(BotConfig.DEFAULT_SYMBOL)

            self.is_running = True
            self.api._bot_ref = self
            self.log("🚀 Bot iniciado! Aguardando sinais...", "SUCCESS")

            # Inicializar timers
            self._ultimo_trade_time = time.time()
            self._ultimo_tick_time  = time.time()
            self._ultimo_sinal_time = time.time()

            # ── Timeouts ───────────────────────────────────────────────────────
            WATCHDOG_CONTRATO   = 45   # s preso em waiting_contract → libera
            TICK_TIMEOUT        = 30   # s sem tick → re-subscribe
            # FIX: timeout de sinal varia com nível de martingale
            SINAL_TIMEOUT_NORMAL     = 90   # s sem sinal (step 0) → ok, mercado lento
            SINAL_TIMEOUT_MARTINGALE = 20   # s sem sinal (step ≥1) → suspeito, força reset
            # ──────────────────────────────────────────────────────────────────

            while self.is_running:
                time.sleep(1)
                agora = time.time()

                # ── Watchdog 1: waiting_contract preso ────────────────────────
                if self.waiting_contract:
                    tempo_preso = agora - self._ultimo_trade_time
                    if tempo_preso > WATCHDOG_CONTRATO:
                        self.log(
                            f"⏰ WATCHDOG contrato: preso {tempo_preso:.0f}s — liberando!",
                            "WARNING"
                        )
                        self.waiting_contract    = False
                        self.current_contract_id = None
                        self._ultimo_trade_time  = agora
                        self._ultimo_sinal_time  = agora  # FIX: resetar sinal também

                # ── Watchdog 2: ticks pararam (WebSocket morto) ───────────────
                sem_tick = agora - self._ultimo_tick_time
                if sem_tick > TICK_TIMEOUT and not self.waiting_contract:
                    self.log(
                        f"⚠️ WATCHDOG ticks: sem tick {sem_tick:.0f}s — reconectando!",
                        "WARNING"
                    )
                    try:
                        self.api.subscribe_ticks(BotConfig.DEFAULT_SYMBOL)
                        self._ultimo_tick_time = agora
                        self._ultimo_sinal_time = agora  # FIX: dar tempo para estabilizar
                    except Exception as e_tick:
                        self.log(f"Erro ao re-subscrever ticks: {e_tick}", "ERROR")

                # ── Watchdog 3 (FIX NOVO): bot livre mas sem gerar sinais ─────
                # Este é o bug principal: após derrota com martingale step ≥1,
                # o bot fica livre (waiting_contract=False) mas a estratégia
                # não gera sinal por tempo anormal → watchdog detecta e reseta.
                if not self.waiting_contract:
                    sem_sinal = agora - self._ultimo_sinal_time

                    # Determinar timeout baseado em step atual do martingale
                    if self.martingale:
                        info_mart = self.martingale.get_info()
                        step_atual = info_mart.get('step_atual', 0)
                    else:
                        step_atual = 0

                    timeout_sinal = (
                        SINAL_TIMEOUT_MARTINGALE if step_atual >= 1
                        else SINAL_TIMEOUT_NORMAL
                    )

                    if sem_sinal > timeout_sinal:
                        self.log(
                            f"⚠️ WATCHDOG sinal: {sem_sinal:.0f}s sem sinal | "
                            f"Step martingale: {step_atual} | "
                            f"Streak sem sinal: {self._sem_sinal_streak} ticks | "
                            f"Forçando reset de estado...",
                            "WARNING"
                        )

                        # FIX: se step ≥ 2 e tempo > 2x o timeout → situação crítica
                        # pode ser que a estratégia travou internamente
                        if step_atual >= 2 and sem_sinal > timeout_sinal * 2:
                            self.log(
                                f"🔧 AUTO-FIX crítico: step {step_atual} com "
                                f"{sem_sinal:.0f}s sem sinal. "
                                f"Resetando estado completo da estratégia...",
                                "WARNING"
                            )
                            # Resetar estado interno da estratégia se possível
                            if hasattr(self.strategy, 'reset_state'):
                                self.strategy.reset_state()
                            # Limpar histórico de ticks para forçar reacumulação
                            self.tick_history = []

                        # Sempre: resetar timer para dar nova janela
                        self._ultimo_sinal_time = agora
                        self._sem_sinal_streak  = 0

                        # Re-subscrever ticks como medida adicional
                        try:
                            self.api.subscribe_ticks(BotConfig.DEFAULT_SYMBOL)
                        except Exception:
                            pass

            return True

        except KeyboardInterrupt:
            self.log("\n⏹️ Bot interrompido pelo usuário", "WARNING")
            self.stop()
            return True
        except Exception as e:
            self.log(f"Erro fatal: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            return False

    def stop(self):
        self.is_running = False
        self.exibir_relatorio_final()
        if self.api:
            self.api.disconnect()
        self.log("Bot encerrado", "INFO")

    def exibir_relatorio_final(self):
        print("\n" + "="*70)
        print("📊 RELATÓRIO FINAL DA SESSÃO")
        print("="*70)
        stats = self.stop_loss.get_estatisticas()
        print(f"\n💰 Resultados Financeiros:")
        print(f"   Saldo Líquido: ${stats['saldo_liquido']:+.2f}")
        print(f"   Lucro Total: ${stats['lucro_total']:.2f}")
        print(f"   Perda Total: ${stats['perda_total']:.2f}")
        print(f"\n📈 Estatísticas:")
        print(f"   Total de Trades: {stats['total_trades']}")
        print(f"   Vitórias: {stats['vitorias']}")
        print(f"   Derrotas: {stats['derrotas']}")
        print(f"   Win Rate: {stats['win_rate']:.2f}%")
        print(f"\n⏱️ Tempo de Sessão: {stats['tempo_sessao']}")
        print("\n" + "="*70 + "\n")
