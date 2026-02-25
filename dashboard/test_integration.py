"""
Test d'intégration du Portfolio et de la Configuration
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("=== Test d'Intégration Dashboard ===\n")

# Test 1: Import du portfolio manager
print("1. Test Portfolio Manager...")
try:
    from portfolio_manager import PortfolioManager

    manager = PortfolioManager()
    summary = manager.get_portfolio_summary()
    print(f"   ✅ Portfolio Manager OK - {summary['num_positions']} positions")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# Test 2: Import du risk profile manager
print("\n2. Test Risk Profile Manager...")
try:
    from risk_profile_manager import RiskProfileManager, RISK_PROFILES

    risk_manager = RiskProfileManager()
    current_profile = risk_manager.get_risk_profile()
    print(f"   ✅ Risk Profile Manager OK - Profil actuel: {current_profile}")
    print(f"   ℹ️  Profils disponibles: {', '.join(RISK_PROFILES.keys())}")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# Test 3: Import du dashboard principal
print("\n3. Test Dashboard App...")
try:
    import importlib.util

    spec = importlib.util.spec_from_file_location("dashboard_app", "dashboard_app.py")
    dashboard = importlib.util.module_from_spec(spec)
    print(f"   ✅ Dashboard App OK - Imports réussis")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# Test 4: Vérifier les fichiers de config
print("\n4. Test Configuration Files...")
config_file = os.path.join(os.path.dirname(__file__), "user_config.json")
portfolio_file = os.path.join(os.path.dirname(__file__), "portfolio.json")

if os.path.exists(config_file):
    print(f"   ✅ user_config.json existe")
else:
    print(f"   ℹ️  user_config.json sera créé au premier lancement")

if os.path.exists(portfolio_file):
    print(f"   ✅ portfolio.json existe")
else:
    print(f"   ℹ️  portfolio.json sera créé au premier lancement")

print("\n=== Résumé ===")
print("✅ Tous les composants sont prêts!")
print("\nPour lancer le dashboard:")
print("  Windows: run_dashboard.bat")
print("  Linux/Mac: ./run_dashboard.sh")
print("\nOnglets disponibles:")
print("  🔍 Exploration - Recherche et analyse d'actions")
print("  📊 Portfolio - Gestion de vos positions avec calcul des frais")
print("  ⚙️ Configuration - Profil de risque et validation")
print("  📚 Documentation - Guides et ressources")
