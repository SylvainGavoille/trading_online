"""
Quantum Trader LITE - Sans agents OpenAI
Version économique : 0$ en frais API !
"""
import argparse
import yaml
import logging
import time
from datetime import datetime
from src.trading.trading_engine_lite import TradingEngineLite


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
        description='Quantum Trader LITE - Trading sans frais API OpenAI'
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
        help='Mode de trading (paper ou live)'
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
        help='Intervalle entre cycles en secondes (défaut: 60)'
    )

    args = parser.parse_args()
    logger = setup_logging()

    # Afficher bannière
    print("=" * 70)
    print("       QUANTUM TRADER LITE - Version Sans API OpenAI")
    print("=" * 70)
    print(f"\nMode: {args.mode.upper()}")
    print(f"Symboles: {', '.join(args.symbols)}")
    print(f"Intervalle: {args.interval}s")
    print(f"Cycles: {'Infini' if args.cycles == 0 else args.cycles}")
    print("\n💰 Coût API OpenAI: 0$ (analyse technique en Python pur)")
    print("⚡ Pas de clé API OpenAI requise !")
    print("\n" + "=" * 70)

    # Charger configuration
    logger.info("Loading configuration...")
    config = load_config()

    # Initialiser le moteur
    logger.info("Initializing Trading Engine Lite...")
    engine = TradingEngineLite(config)

    # Connexion IB
    logger.info("Connecting to Interactive Brokers...")
    if not engine.connect():
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

            # Exécuter le cycle de trading
            results = engine.run_trading_cycle(args.symbols)

            # Afficher résumé
            print(f"\n📊 Résumé Cycle {cycle}:")
            print(f"   - Symboles analysés: {results['symbols_analyzed']}")
            print(f"   - Trades exécutés: {results['trades_executed']}")
            print(f"   - Trades rejetés: {results['trades_rejected']}")

            # Détails par symbole
            for symbol, detail in results['details'].items():
                if 'analysis' in detail and detail['analysis']['status'] == 'success':
                    analysis = detail['analysis']
                    print(f"\n   {symbol}:")
                    print(f"      Signal: {analysis['signal']} (confiance: {analysis['confidence']:.2%})")
                    print(f"      RSI: {analysis['indicators']['rsi']:.1f}")
                    print(f"      Prix: ${analysis['indicators']['price']:.2f}")

                    if 'execution' in detail:
                        exec_status = detail['execution']['status']
                        if exec_status == 'success':
                            print(f"      ✅ Trade exécuté")
                        elif exec_status == 'rejected':
                            print(f"      ❌ Trade rejeté: {detail['execution']['reason']}")

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
        engine.disconnect()
        logger.info("Shutdown complete")

    return 0


if __name__ == "__main__":
    exit(main())
