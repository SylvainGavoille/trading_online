"""Test du capital disponible et capitalisation"""

from portfolio_manager import PortfolioManager
from risk_profile_manager import RiskProfileManager

# Initialiser les gestionnaires
pm = PortfolioManager()
rm = RiskProfileManager()

# Récupérer le cash disponible
cash = rm.get_available_cash()
capital_initial = rm.get_capital_initial()

# Récupérer le résumé avec cash
summary = pm.get_portfolio_summary(available_cash=cash)

print("=== Test Capital et Capitalisation ===\n")
print(f"Capital initial: ${capital_initial:,.2f}")
print(f"Capital disponible: ${summary['available_cash']:,.2f}")
print(f"Capital investi: ${summary['total_invested']:,.2f}")
print(f"Valeur positions: ${summary['total_value']:,.2f}")
print(f"Capitalisation totale: ${summary['total_capitalization']:,.2f}")
print(f"Plus-value nette: ${summary['total_pnl']:,.2f}")
print(f"Nombre de positions: {summary['num_positions']}")

print("\nOK: Integration successful!")
