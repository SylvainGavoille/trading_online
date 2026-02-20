"""
Trading Engine Lite - Sans agents OpenAI
Utilise uniquement du Python pur pour réduire les coûts à zéro
"""
import logging
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime

from src.analysis.technical_analysis import TechnicalAnalysis
from src.trading.agents.risk_validator import RiskValidator
from src.trading.agents.trade_executor import TradeExecutor
from src.trading.agents.signal_analyzer import SignalAnalyzer
from src.api.ib_connector import IBClient


class TradingEngineLite:
    """
    Moteur de trading sans agents OpenAI
    Utilise uniquement du code Python pur pour :
    - Analyse technique (RSI, MACD, Bollinger, SMA, EMA)
    - Validation des risques
    - Exécution des trades

    Coût : 0$ en API (seulement IB si live trading)
    """

    def __init__(self, config: dict):
        """
        Initialise le moteur de trading

        Args:
            config: Configuration du système
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialiser les composants (tous en Python pur)
        self.ib_client = IBClient(config)
        self.risk_validator = RiskValidator(config)
        self.signal_analyzer = SignalAnalyzer(None)

        # Trade executor sera initialisé après connexion IB
        self.trade_executor = None

        # Seuils de décision
        self.technical_threshold = config['agent_system']['confidence_thresholds']['technical']
        self.combined_threshold = config['agent_system']['confidence_thresholds']['combined']

        self.logger.info("Trading Engine Lite initialized (no OpenAI API needed)")

    def connect(self) -> bool:
        """Connecte au broker IB"""
        if self.ib_client.connect_and_run():
            self.trade_executor = TradeExecutor(self.ib_client)
            self.logger.info("Connected to IB successfully")
            return True
        else:
            self.logger.error("Failed to connect to IB")
            return False

    def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Analyse complète d'un symbole (technique uniquement)

        Args:
            symbol: Symbole à analyser (ex: AAPL)

        Returns:
            Dict avec analyse technique et signal
        """
        self.logger.info(f"Analyzing {symbol}")

        # 1. Récupérer données du marché
        market_data = self.ib_client.get_market_data(symbol)
        if not market_data or len(market_data.get('close', [])) < 10:
            self.logger.warning(f"Insufficient data for {symbol}")
            return {
                'symbol': symbol,
                'status': 'insufficient_data',
                'signal': 'NEUTRAL',
                'confidence': 0.0
            }

        # 2. Convertir en DataFrame
        df = pd.DataFrame(market_data)

        # 3. Analyse technique (Python pur - 0$ API)
        tech_analysis = TechnicalAnalysis(df)

        try:
            # Calculer le signal combiné (-1 à +1)
            technical_signal = tech_analysis.evaluate(df)

            if technical_signal is None:
                return {
                    'symbol': symbol,
                    'status': 'error',
                    'signal': 'NEUTRAL',
                    'confidence': 0.0
                }

            # Calculer les indicateurs individuels
            rsi = tech_analysis.rsi(period=self.config['technical_analysis']['indicators']['rsi']['period'])
            macd_line, signal_line = tech_analysis.macd()
            bb_upper, bb_lower = tech_analysis.bollinger_bands()
            sma_20 = tech_analysis.sma(period=20)

            current_price = df['close'].iloc[-1]

            # Déterminer le signal
            if technical_signal >= self.technical_threshold:
                signal = 'BUY'
                confidence = abs(technical_signal)
            elif technical_signal <= -self.technical_threshold:
                signal = 'SELL'
                confidence = abs(technical_signal)
            else:
                signal = 'NEUTRAL'
                confidence = abs(technical_signal)

            return {
                'symbol': symbol,
                'status': 'success',
                'signal': signal,
                'confidence': confidence,
                'technical_score': technical_signal,
                'indicators': {
                    'rsi': rsi.iloc[-1] if not rsi.empty else None,
                    'macd': (macd_line.iloc[-1] - signal_line.iloc[-1]) if not macd_line.empty else None,
                    'price': current_price,
                    'sma_20': sma_20.iloc[-1] if not sma_20.empty else None,
                    'bb_upper': bb_upper.iloc[-1] if not bb_upper.empty else None,
                    'bb_lower': bb_lower.iloc[-1] if not bb_lower.empty else None,
                },
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {e}")
            return {
                'symbol': symbol,
                'status': 'error',
                'signal': 'NEUTRAL',
                'confidence': 0.0,
                'error': str(e)
            }

    def evaluate_trade(self, symbol: str, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Évalue si un trade doit être exécuté

        Args:
            symbol: Symbole
            analysis: Résultat de l'analyse

        Returns:
            Paramètres du trade ou None si pas de trade
        """
        if analysis['status'] != 'success':
            return None

        if analysis['signal'] == 'NEUTRAL':
            self.logger.info(f"{symbol}: Signal NEUTRAL, pas de trade")
            return None

        if analysis['confidence'] < self.combined_threshold:
            self.logger.info(
                f"{symbol}: Confiance {analysis['confidence']:.2f} < seuil {self.combined_threshold}, "
                "pas de trade"
            )
            return None

        # Préparer les paramètres du trade
        action = 'BUY' if analysis['signal'] == 'BUY' else 'SELL'
        current_price = analysis['indicators']['price']

        # Calculer stop-loss (ATR basé sur volatilité)
        # Pour simplifier, on utilise un pourcentage de la bande Bollinger
        bb_range = analysis['indicators']['bb_upper'] - analysis['indicators']['bb_lower']
        atr_estimate = bb_range / 4  # Approximation simple

        atr_multiplier = self.config['risk_management']['stop_loss']['atr_multiplier']

        if action == 'BUY':
            stop_loss = current_price - (atr_estimate * atr_multiplier)
            take_profit = current_price + (atr_estimate * atr_multiplier *
                                         self.config['risk_management']['risk_reward']['target_ratio'])
        else:
            stop_loss = current_price + (atr_estimate * atr_multiplier)
            take_profit = current_price - (atr_estimate * atr_multiplier *
                                         self.config['risk_management']['risk_reward']['target_ratio'])

        # Calculer taille de position
        max_position = self.config['risk_management']['position_limits']['max_position_size']
        risk_per_trade = self.config['risk_management']['stop_loss']['max_loss_per_trade']

        # Taille basée sur le risque
        risk_amount = abs(current_price - stop_loss)
        if risk_amount > 0:
            # Supposons un capital de base (à adapter)
            capital = 100000  # TODO: Récupérer du portfolio
            max_risk_dollars = capital * risk_per_trade
            quantity = int(min(max_risk_dollars / risk_amount, max_position))
        else:
            quantity = max_position

        return {
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'confidence': analysis['confidence'],
            'technical_score': analysis['technical_score']
        }

    def execute_trade(self, trade_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Exécute un trade après validation des risques

        Args:
            trade_params: Paramètres du trade

        Returns:
            Résultat de l'exécution ou None si rejeté
        """
        symbol = trade_params['symbol']

        # 1. Validation des risques (Python pur - 0$ API)
        portfolio = self.trade_executor.get_portfolio()
        risk_result = self.risk_validator.validate_trade(trade_params, portfolio)

        if not risk_result['approved']:
            self.logger.warning(
                f"{symbol}: Trade rejected by risk validator - {risk_result['reason']}"
            )
            return {
                'status': 'rejected',
                'reason': risk_result['reason'],
                'trade_params': trade_params
            }

        # 2. Exécution (Python pur - 0$ API, juste frais IB)
        self.logger.info(f"{symbol}: Executing trade - {trade_params['action']} {trade_params['quantity']} @ {trade_params['price']}")

        execution_result = self.trade_executor.execute_trade(trade_params)

        if execution_result['status'] == 'executed':
            self.logger.info(f"{symbol}: Trade executed successfully - {execution_result}")
            return {
                'status': 'success',
                'execution': execution_result,
                'trade_params': trade_params
            }
        else:
            self.logger.error(f"{symbol}: Trade execution failed - {execution_result.get('reason')}")
            return {
                'status': 'failed',
                'reason': execution_result.get('reason'),
                'trade_params': trade_params
            }

    def run_trading_cycle(self, symbols: list) -> Dict[str, Any]:
        """
        Exécute un cycle complet de trading pour plusieurs symboles

        Args:
            symbols: Liste des symboles à trader

        Returns:
            Résultats du cycle
        """
        self.logger.info(f"Starting trading cycle for {len(symbols)} symbols")

        results = {
            'timestamp': datetime.now().isoformat(),
            'symbols_analyzed': len(symbols),
            'trades_executed': 0,
            'trades_rejected': 0,
            'details': {}
        }

        for symbol in symbols:
            try:
                # 1. Analyse (Python pur - 0$ API)
                analysis = self.analyze_symbol(symbol)

                # 2. Évaluation (Python pur - 0$ API)
                trade_params = self.evaluate_trade(symbol, analysis)

                if trade_params:
                    # 3. Exécution (Python pur - 0$ API)
                    execution_result = self.execute_trade(trade_params)

                    if execution_result['status'] == 'success':
                        results['trades_executed'] += 1
                    elif execution_result['status'] == 'rejected':
                        results['trades_rejected'] += 1

                    results['details'][symbol] = {
                        'analysis': analysis,
                        'trade_params': trade_params,
                        'execution': execution_result
                    }
                else:
                    results['details'][symbol] = {
                        'analysis': analysis,
                        'action': 'no_trade'
                    }

            except Exception as e:
                self.logger.error(f"Error processing {symbol}: {e}")
                results['details'][symbol] = {
                    'status': 'error',
                    'error': str(e)
                }

        self.logger.info(
            f"Cycle complete: {results['trades_executed']} executed, "
            f"{results['trades_rejected']} rejected"
        )

        return results

    def disconnect(self):
        """Déconnecte du broker"""
        if self.ib_client:
            self.ib_client.disconnect()
            self.logger.info("Disconnected from IB")
