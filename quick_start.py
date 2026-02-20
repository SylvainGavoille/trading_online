"""
Script de demarrage rapide pour Quantum Trader
Affiche la configuration et guide l'utilisateur
"""
import yaml

def print_separator():
    print("=" * 70)

def load_config():
    with open('src/config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def main():
    print_separator()
    print("     QUANTUM TRADER - Systeme de Trading Multi-Agents")
    print_separator()

    # Charger la config
    print("\n[1] Configuration chargee:")
    config = load_config()
    print(f"    - Endpoint: {config['api']['tws_endpoint']}")
    print(f"    - Port: {config['api']['port']} (IB Gateway Paper Trading)")
    print(f"    - Max position: {config['risk_management']['position_limits']['max_position_size']} actions")
    print(f"    - Max drawdown: {config['risk_management']['loss_limits']['max_drawdown']*100}%")
    print(f"    - Max trades/jour: {config['risk_management']['trade_frequency']['max_daily_trades']}")

    # Afficher les prochaines etapes
    print("\n[2] Avant de commencer:")
    print("    - Verifiez la connexion: uv run test_connection.py")
    print("    - Diagnostic complet: uv run diagnose_connection.py")

    print("\n[3] Systeme pret!")
    print_separator()
    print("\nPROCHAINES ETAPES:")
    print("\n1. MODE FORMATION (recommande pour debuter):")
    print("   cd training")
    print("   python server.py")
    print("   Puis ouvrir http://localhost:7555")

    print("\n2. LANCER LE TRADER (mode paper):")
    print("   uv run run_trader.py --symbols AAPL MSFT --mode paper")

    print("\n3. PERSONNALISER LA CONFIG:")
    print("   Editez src/config/config.yaml")

    print("\n4. DOCUMENTATION:")
    print("   Voir le dossier docs/ pour plus d'infos")

    print_separator()
    print("\nATTENTION: Commencez TOUJOURS en mode paper trading!")
    print_separator()

if __name__ == "__main__":
    main()
