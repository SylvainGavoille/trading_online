"""
Test de l'intégration IBKR pour le portfolio
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.api.ib_connector import IBClient
from portfolio_manager import PortfolioManager, configure_ibkr_client
from risk_profile_manager import RiskProfileManager
import yaml


def load_config():
    """Charge la configuration"""
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "config", "config.yaml"
    )
    with open(config_path, "r") as file:
        return yaml.safe_load(file)


def test_ibkr_connection():
    """Test de connexion IBKR"""
    print("=== Test Connexion IBKR ===\n")

    try:
        config = load_config()
        client = IBClient(config)

        print(
            f"Tentative de connexion à {config['api']['tws_endpoint']}:{config['api']['port']}..."
        )

        if client.connect_and_run():
            print("✅ Connexion IBKR réussie!")

            # Configurer le client dans le portfolio manager
            configure_ibkr_client(client)

            # Test récupération des positions
            print("\n=== Récupération des Positions ===")
            positions = client.get_account_positions(timeout=10.0)

            if positions:
                print(f"\n✅ {len(positions)} position(s) trouvée(s):\n")
                for symbol, pos in positions.items():
                    print(f"  {symbol}:")
                    print(f"    - Quantité: {pos['position']}")
                    print(f"    - Prix moyen: ${pos['avg_cost']:.2f}")
                    print(f"    - Type: {pos['sec_type']}")
                    print()
            else:
                print("ℹ️  Aucune position trouvée dans le compte IBKR")

            # Test récupération du cash
            print("=== Récupération du Cash ===")
            account_summary = client.get_account_summary(timeout=10.0)

            if account_summary:
                print("\n✅ Résumé du compte:")
                for key, value in account_summary.items():
                    if isinstance(value, float):
                        print(f"  {key}: ${value:,.2f}")
                    else:
                        print(f"  {key}: {value}")

            # Test avec PortfolioManager
            print("\n=== Test PortfolioManager avec IBKR ===")
            pm = PortfolioManager(use_ibkr=True)

            summary = pm.get_portfolio_summary(available_cash=0)

            print(f"\nRésumé du portfolio:")
            print(f"  Positions: {summary['num_positions']}")
            print(f"  Capital investi: ${summary['total_invested']:,.2f}")
            print(f"  Valeur actuelle: ${summary['total_value']:,.2f}")
            print(f"  Plus-value: ${summary['total_pnl']:,.2f}")

            # Récupérer le cash depuis IBKR
            cash = pm.get_account_cash_from_ibkr()
            if cash is not None:
                print(f"  Cash disponible: ${cash:,.2f}")

            # Déconnexion
            client.disconnect()
            print("\n✅ Déconnexion réussie")

        else:
            print("❌ Échec de la connexion IBKR")
            print("\nVérifiez que:")
            print("  1. TWS ou IB Gateway est lancé")
            print("  2. Le port est correct dans config.yaml")
            print(
                "  3. L'API est activée dans TWS (File > Global Configuration > API > Settings)"
            )

    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback

        traceback.print_exc()


def test_offline_mode():
    """Test du mode hors ligne (sans IBKR)"""
    print("\n\n=== Test Mode Hors Ligne ===\n")

    pm = PortfolioManager(use_ibkr=False)
    rm = RiskProfileManager()

    cash = rm.get_available_cash()
    summary = pm.get_portfolio_summary(available_cash=cash)

    print(f"Positions (depuis JSON): {summary['num_positions']}")
    print(f"Capital disponible: ${cash:,.2f}")
    print(f"Capitalisation totale: ${summary['total_capitalization']:,.2f}")

    print("\n✅ Mode hors ligne fonctionne")


if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║  Test Intégration IBKR Portfolio        ║")
    print("╚══════════════════════════════════════════╝\n")

    # Test connexion IBKR
    test_ibkr_connection()

    # Test mode hors ligne
    test_offline_mode()

    print("\n" + "=" * 50)
    print("Tests terminés!")
