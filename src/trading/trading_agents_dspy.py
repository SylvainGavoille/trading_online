"""
Trading Agents avec DSPy
Remplace Swarm par DSPy pour plus de flexibilité
Supporte: OpenAI, Anthropic, local models, etc.
"""
import logging
from typing import Dict, Any, Optional
import pandas as pd
import dspy
from datetime import datetime


# ===== Signatures DSPy =====

class TechnicalAnalysis(dspy.Signature):
    """Analyse technique des données de marché"""
    market_data: str = dspy.InputField(desc="Données OHLCV et indicateurs calculés")
    indicators: str = dspy.InputField(desc="RSI, MACD, Bollinger Bands, SMA, EMA")

    signal: str = dspy.OutputField(desc="Signal: BUY, SELL, ou NEUTRAL")
    confidence: float = dspy.OutputField(desc="Confiance entre 0.0 et 1.0")
    reasoning: str = dspy.OutputField(desc="Explication de la décision")


class SentimentAnalysis(dspy.Signature):
    """Analyse du sentiment de marché"""
    symbol: str = dspy.InputField(desc="Symbole de l'action")
    news_data: str = dspy.InputField(desc="Articles de presse récents")
    social_data: str = dspy.InputField(desc="Données des réseaux sociaux")

    sentiment: str = dspy.OutputField(desc="Sentiment: BULLISH, BEARISH, ou NEUTRAL")
    confidence: float = dspy.OutputField(desc="Confiance entre 0.0 et 1.0")
    key_factors: str = dspy.OutputField(desc="Facteurs clés influençant le sentiment")


class RiskValidation(dspy.Signature):
    """Validation des risques d'un trade"""
    trade_params: str = dspy.InputField(desc="Paramètres du trade proposé")
    portfolio: str = dspy.InputField(desc="État actuel du portfolio")
    risk_limits: str = dspy.InputField(desc="Limites de risque configurées")

    approved: bool = dspy.OutputField(desc="Trade approuvé: true ou false")
    risk_score: float = dspy.OutputField(desc="Score de risque entre 0.0 et 1.0")
    reason: str = dspy.OutputField(desc="Raison de l'approbation ou du rejet")


# ===== Modules DSPy =====

class TechnicalAgent(dspy.Module):
    """Agent d'analyse technique utilisant DSPy"""

    def __init__(self):
        super().__init__()
        self.analyze = dspy.ChainOfThought(TechnicalAnalysis)

    def forward(self, market_data: str, indicators: str):
        """
        Analyse les données techniques

        Args:
            market_data: Données OHLCV
            indicators: Indicateurs calculés

        Returns:
            Prédiction DSPy avec signal, confiance, raisonnement
        """
        return self.analyze(market_data=market_data, indicators=indicators)


class SentimentAgent(dspy.Module):
    """Agent d'analyse de sentiment utilisant DSPy"""

    def __init__(self):
        super().__init__()
        self.analyze = dspy.ChainOfThought(SentimentAnalysis)

    def forward(self, symbol: str, news_data: str, social_data: str):
        """
        Analyse le sentiment du marché

        Args:
            symbol: Symbole de l'action
            news_data: Nouvelles récentes
            social_data: Données sociales

        Returns:
            Prédiction DSPy avec sentiment, confiance, facteurs
        """
        return self.analyze(symbol=symbol, news_data=news_data, social_data=social_data)


class RiskAgent(dspy.Module):
    """Agent de validation des risques utilisant DSPy"""

    def __init__(self):
        super().__init__()
        self.validate = dspy.ChainOfThought(RiskValidation)

    def forward(self, trade_params: str, portfolio: str, risk_limits: str):
        """
        Valide les risques d'un trade

        Args:
            trade_params: Paramètres du trade
            portfolio: Portfolio actuel
            risk_limits: Limites de risque

        Returns:
            Prédiction DSPy avec approbation, score risque, raison
        """
        return self.validate(
            trade_params=trade_params,
            portfolio=portfolio,
            risk_limits=risk_limits
        )


# ===== Trading System avec DSPy =====

class TradingSystemDSPy:
    """
    Système de trading utilisant DSPy au lieu de Swarm

    Avantages DSPy vs Swarm:
    - Support multi-LLM (OpenAI, Anthropic, local models)
    - Optimisation automatique des prompts
    - Compilation et fine-tuning
    - Meilleure gestion des coûts
    """

    def __init__(self, config: dict, llm_provider: str = "openai", model: str = "gpt-4o-mini"):
        """
        Initialise le système de trading DSPy

        Args:
            config: Configuration du système
            llm_provider: Provider LLM (openai, anthropic, local, etc.)
            model: Modèle à utiliser
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Configurer DSPy avec le LLM
        self._configure_llm(llm_provider, model)

        # Initialiser les agents DSPy
        self.technical_agent = TechnicalAgent()
        self.sentiment_agent = SentimentAgent()
        self.risk_agent = RiskAgent()

        self.logger.info(f"Trading System DSPy initialized with {llm_provider}/{model}")

    def _configure_llm(self, provider: str, model: str):
        """
        Configure le LLM pour DSPy

        Args:
            provider: Provider (openai, anthropic, etc.)
            model: Nom du modèle
        """
        if provider == "openai":
            lm = dspy.LM(model=f'openai/{model}')
        elif provider == "anthropic":
            lm = dspy.LM(model=f'anthropic/{model}')
        elif provider == "ollama":
            # Pour modèles locaux via Ollama
            lm = dspy.LM(model=f'ollama/{model}')
        else:
            # Par défaut OpenAI
            lm = dspy.LM(model=f'openai/{model}')

        dspy.configure(lm=lm)
        self.logger.info(f"DSPy configured with {provider}/{model}")

    def analyze_technical(self, symbol: str, market_data: pd.DataFrame,
                         indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyse technique d'un symbole

        Args:
            symbol: Symbole de l'action
            market_data: DataFrame avec OHLCV
            indicators: Indicateurs calculés (RSI, MACD, etc.)

        Returns:
            Résultat de l'analyse avec signal et confiance
        """
        try:
            # Préparer les données pour le LLM
            market_summary = self._format_market_data(market_data)
            indicators_summary = self._format_indicators(indicators)

            # Appeler l'agent technique DSPy
            result = self.technical_agent(
                market_data=market_summary,
                indicators=indicators_summary
            )

            return {
                'symbol': symbol,
                'signal': result.signal,
                'confidence': float(result.confidence),
                'reasoning': result.reasoning,
                'status': 'success'
            }

        except Exception as e:
            self.logger.error(f"Error in technical analysis for {symbol}: {e}")
            return {
                'symbol': symbol,
                'signal': 'NEUTRAL',
                'confidence': 0.0,
                'status': 'error',
                'error': str(e)
            }

    def analyze_sentiment(self, symbol: str, news_data: Optional[list] = None,
                         social_data: Optional[list] = None) -> Dict[str, Any]:
        """
        Analyse de sentiment pour un symbole

        Args:
            symbol: Symbole de l'action
            news_data: Liste d'articles de presse
            social_data: Données des réseaux sociaux

        Returns:
            Résultat de l'analyse avec sentiment et confiance
        """
        try:
            # Formater les données
            news_summary = self._format_news(news_data) if news_data else "No recent news"
            social_summary = self._format_social(social_data) if social_data else "No social data"

            # Appeler l'agent de sentiment DSPy
            result = self.sentiment_agent(
                symbol=symbol,
                news_data=news_summary,
                social_data=social_summary
            )

            return {
                'symbol': symbol,
                'sentiment': result.sentiment,
                'confidence': float(result.confidence),
                'key_factors': result.key_factors,
                'status': 'success'
            }

        except Exception as e:
            self.logger.error(f"Error in sentiment analysis for {symbol}: {e}")
            return {
                'symbol': symbol,
                'sentiment': 'NEUTRAL',
                'confidence': 0.0,
                'status': 'error',
                'error': str(e)
            }

    def validate_risk(self, trade_params: Dict[str, Any],
                     portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valide les risques d'un trade

        Args:
            trade_params: Paramètres du trade proposé
            portfolio: État actuel du portfolio

        Returns:
            Résultat de la validation avec approbation et raison
        """
        try:
            # Formater les données
            trade_summary = self._format_trade_params(trade_params)
            portfolio_summary = self._format_portfolio(portfolio)
            risk_limits = self._format_risk_limits()

            # Appeler l'agent de risque DSPy
            result = self.risk_agent(
                trade_params=trade_summary,
                portfolio=portfolio_summary,
                risk_limits=risk_limits
            )

            return {
                'approved': bool(result.approved),
                'risk_score': float(result.risk_score),
                'reason': result.reason,
                'status': 'success'
            }

        except Exception as e:
            self.logger.error(f"Error in risk validation: {e}")
            return {
                'approved': False,
                'risk_score': 1.0,
                'reason': f"Error: {str(e)}",
                'status': 'error'
            }

    # ===== Méthodes de formatage =====

    def _format_market_data(self, df: pd.DataFrame) -> str:
        """Formate les données de marché pour le LLM"""
        if df.empty or len(df) < 5:
            return "Insufficient data"

        recent = df.tail(5)
        return f"""
Recent market data (last 5 periods):
- Open: {recent['open'].tolist()}
- High: {recent['high'].tolist()}
- Low: {recent['low'].tolist()}
- Close: {recent['close'].tolist()}
- Volume: {recent['volume'].tolist()}

Current price: ${recent['close'].iloc[-1]:.2f}
Price change: ${recent['close'].iloc[-1] - recent['close'].iloc[0]:.2f}
        """

    def _format_indicators(self, indicators: Dict[str, Any]) -> str:
        """Formate les indicateurs techniques"""
        return f"""
Technical Indicators:
- RSI (14): {indicators.get('rsi', 'N/A')}
- MACD: {indicators.get('macd', 'N/A')}
- SMA 20: ${indicators.get('sma_20', 'N/A')}
- Bollinger Upper: ${indicators.get('bb_upper', 'N/A')}
- Bollinger Lower: ${indicators.get('bb_lower', 'N/A')}
- Current Price: ${indicators.get('price', 'N/A')}
        """

    def _format_news(self, news_data: list) -> str:
        """Formate les nouvelles"""
        if not news_data:
            return "No recent news available"

        summaries = [f"- {item.get('title', 'N/A')}: {item.get('summary', 'N/A')}"
                    for item in news_data[:5]]
        return "\n".join(summaries)

    def _format_social(self, social_data: list) -> str:
        """Formate les données sociales"""
        if not social_data:
            return "No social media data available"

        summaries = [f"- {item.get('platform', 'Unknown')}: {item.get('text', 'N/A')}"
                    for item in social_data[:5]]
        return "\n".join(summaries)

    def _format_trade_params(self, params: Dict[str, Any]) -> str:
        """Formate les paramètres du trade"""
        return f"""
Trade Parameters:
- Symbol: {params.get('symbol', 'N/A')}
- Action: {params.get('action', 'N/A')}
- Quantity: {params.get('quantity', 'N/A')} shares
- Price: ${params.get('price', 'N/A')}
- Stop Loss: ${params.get('stop_loss', 'N/A')}
- Take Profit: ${params.get('take_profit', 'N/A')}
- Risk: ${params.get('quantity', 0) * abs(params.get('price', 0) - params.get('stop_loss', 0))}
        """

    def _format_portfolio(self, portfolio: Dict[str, Any]) -> str:
        """Formate l'état du portfolio"""
        return f"""
Portfolio Status:
- Total Value: ${portfolio.get('total_value', 'N/A')}
- Cash: ${portfolio.get('cash', 'N/A')}
- Positions: {len(portfolio.get('positions', []))}
- Current Exposure: {portfolio.get('exposure_percent', 'N/A')}%
        """

    def _format_risk_limits(self) -> str:
        """Formate les limites de risque"""
        risk_config = self.config.get('risk_management', {})
        return f"""
Risk Limits:
- Max Position Size: {risk_config.get('position_limits', {}).get('max_position_size', 'N/A')} shares
- Max Portfolio Exposure: {risk_config.get('position_limits', {}).get('max_portfolio_exposure', 'N/A') * 100}%
- Daily Loss Limit: ${risk_config.get('loss_limits', {}).get('daily_loss_limit', 'N/A')}
- Max Drawdown: {risk_config.get('loss_limits', {}).get('max_drawdown', 'N/A') * 100}%
- Min Risk/Reward: {risk_config.get('risk_reward', {}).get('min_ratio', 'N/A')}:1
        """
