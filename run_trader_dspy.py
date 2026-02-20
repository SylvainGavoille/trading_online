"""
Quantum Trader avec DSPy
Plus flexible que Swarm - supporte multiple LLMs
"""
import argparse
import yaml
import logging
import time
from datetime import datetime
import pandas as pd

from src.trading.trading_agents_dspy import TradingSystemDSPy
from src.analysis.technical_analysis import TechnicalAnalysis
from src.api.ib_connector import IBClient


def setup_logging():
    """Configure le logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def load_config():
    """Charge la configuration"""
    try:
        with open('src/config/config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError("config.yaml not found in src/config/")


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description='Quantum Trader avec DSPy - Multi-LLM support'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        required=True,
        help='Symboles à trader (ex: AAPL MSFT GOOGL)'
    )
    parser.add_argument(
        '--mode',
        choices=['paper', 'live'],
        default='paper',
        help='Mode de trading'
    )
    parser.add_argument(
        '--llm',
        choices=['openai', 'anthropic', 'ollama'],
        default='openai',
        help='Provider LLM à utiliser'
    )
    parser.add_argument(
        '--model',
        default='gpt-4o-mini',
        help='Modèle à utiliser (ex: gpt-4o-mini, claude-3-5-sonnet-20241022, llama3)'
    )
    parser.add_argument(
        '--cycles',
        type=int,
        default=0,
        help='Nombre de cycles (0 = infini)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Intervalle entre cycles en secondes'
    )
    parser.add_argument(
        '--skip-sentiment',
        action='store_true',
        help='Skip sentiment analysis (reduce API costs)'
    )

    args = parser.parse_args()
    logger = setup_logging()

    # Afficher bannière
    print("=" * 70)
    print("       QUANTUM TRADER - DSPy Version (Multi-LLM)")
    print("=" * 70)
    print(f"\nMode: {args.mode.upper()}")
    print(f"Symboles: {', '.join(args.symbols)}")
    print(f"LLM: {args.llm} / {args.model}")
    print(f"Intervalle: {args.interval}s")
    print(f"Cycles: {'Infini' if args.cycles == 0 else args.cycles}")
    print(f"Sentiment: {'Désactivé' if args.skip_sentiment else 'Activé'}")
    print("\n" + "=" * 70)

    # Charger configuration
    logger.info("Loading configuration...")
    config = load_config()

    # Initialiser DSPy Trading System
    logger.info(f"Initializing DSPy Trading System with {args.llm}/{args.model}...")
    trading_system = TradingSystemDSPy(
        config=config,
        llm_provider=args.llm,
        model=args.model
    )

    # Connexion IB
    logger.info("Connecting to Interactive Brokers...")
    ib_client = IBClient(config)
    if not ib_client.connect_and_run():
        logger.error("Failed to connect to IB. Exiting.")
        return 1

    # Boucle de trading
    cycle = 0
    try:
        while True:
            cycle += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"CYCLE {cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*70}")

            for symbol in args.symbols:
                try:
                    logger.info(f"\nAnalyzing {symbol}...")

                    # 1. Récupérer données du marché
                    market_data = ib_client.get_market_data(symbol)
                    if not market_data or len(market_data.get('close', [])) < 10:
                        logger.warning(f"Insufficient data for {symbol}")
                        continue

                    # Convertir en DataFrame
                    df = pd.DataFrame(market_data)

                    # 2. Calculer indicateurs (Python pur - pas d'API)
                    tech_analyzer = TechnicalAnalysis(df)
                    rsi = tech_analyzer.rsi(period=14)
                    macd_line, signal_line = tech_analyzer.macd()
                    bb_upper, bb_lower = tech_analyzer.bollinger_bands()
                    sma_20 = tech_analyzer.sma(period=20)

                    current_price = df['close'].iloc[-1]

                    indicators = {
                        'rsi': rsi.iloc[-1] if not rsi.empty else None,
                        'macd': (macd_line.iloc[-1] - signal_line.iloc[-1]) if not macd_line.empty else None,
                        'price': current_price,
                        'sma_20': sma_20.iloc[-1] if not sma_20.empty else None,
                        'bb_upper': bb_upper.iloc[-1] if not bb_upper.empty else None,
                        'bb_lower': bb_lower.iloc[-1] if not bb_lower.empty else None,
                    }

                    # 3. Analyse technique avec DSPy (utilise LLM)
                    logger.info(f"  Running technical analysis with DSPy...")
                    tech_result = trading_system.analyze_technical(
                        symbol=symbol,
                        market_data=df,
                        indicators=indicators
                    )

                    print(f"\n  {symbol} - Technical Analysis:")
                    print(f"    Signal: {tech_result['signal']}")
                    print(f"    Confidence: {tech_result['confidence']:.2%}")
                    print(f"    Reasoning: {tech_result.get('reasoning', 'N/A')[:100]}...")

                    # 4. Analyse de sentiment (optionnel)
                    if not args.skip_sentiment:
                        logger.info(f"  Running sentiment analysis with DSPy...")
                        sentiment_result = trading_system.analyze_sentiment(
                            symbol=symbol,
                            news_data=None,  # TODO: Intégrer API news
                            social_data=None  # TODO: Intégrer API social
                        )

                        print(f"\n  {symbol} - Sentiment Analysis:")
                        print(f"    Sentiment: {sentiment_result['sentiment']}")
                        print(f"    Confidence: {sentiment_result['confidence']:.2%}")

                    # 5. Décision de trading basée sur les signaux
                    # TODO: Combiner tech + sentiment, valider risque, exécuter

                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    continue

            # Vérifier si on doit continuer
            if args.cycles > 0 and cycle >= args.cycles:
                logger.info(f"Completed {args.cycles} cycles. Exiting.")
                break

            # Attendre avant le prochain cycle
            if args.cycles == 0 or cycle < args.cycles:
                logger.info(f"Waiting {args.interval}s before next cycle...")
                time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("\nTrading interrupted by user")
    except Exception as e:
        logger.error(f"Error in trading loop: {e}", exc_info=True)
    finally:
        logger.info("Disconnecting from IB...")
        ib_client.disconnect()
        logger.info("Shutdown complete")

    return 0


if __name__ == "__main__":
    exit(main())
