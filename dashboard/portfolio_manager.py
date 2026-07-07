"""
Gestionnaire de Portfolio pour le Dashboard Streamlit
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import json
import os

from gcs_data import read_price_history_from_gcs
from risk_profile_manager import RiskProfileManager

_ib_client = None


def _latest_close_from_gcs(symbol: str, day: str) -> Optional[float]:
    """Return the most recent GCS close for *symbol* up to *day* (YYYY-MM-DD).

    Looks back ~7 calendar days from *day*. Returns None if no data is found.
    The *day* argument exists so the Streamlit cache key rolls over daily.
    """
    from datetime import date, timedelta

    end_d = date.fromisoformat(day)
    start_d = end_d - timedelta(days=7)
    gcs_df = read_price_history_from_gcs(symbol, start_d, end_d)
    if gcs_df is not None and not gcs_df.empty and "Close" in gcs_df.columns:
        return float(gcs_df["Close"].iloc[-1])
    return None


# Wrap the per-symbol GCS lookup in Streamlit's data cache so repeated reruns
# don't re-hit GCS for the same (symbol, day). When not running under Streamlit
# (e.g. the __main__ test), fall back to the uncached function.
try:
    import streamlit as st

    _cached_latest_close = st.cache_data(ttl=900)(_latest_close_from_gcs)
except Exception:  # pragma: no cover - non-Streamlit context
    _cached_latest_close = _latest_close_from_gcs


def _configured_ibkr_plan() -> str:
    """Return the IBKR plan configured by the user (user_config.json).

    Falls back to "Lite" if the config can't be read.
    """
    try:
        return RiskProfileManager().config.get("ibkr_plan", "Lite")
    except Exception:
        return "Lite"


def configure_ibkr_client(client) -> None:
    """Injecte le client IBClient dans le gestionnaire de portfolio."""
    global _ib_client
    _ib_client = client


class PortfolioManager:
    """Gestion du portfolio et calcul des performances"""

    # Frais IBKR selon les plans
    IBKR_FEES = {
        "Lite": {
            "stock": 0.0,  # 0$ commission (mais routing fees possibles)
            "min_per_order": 0.0,
            "max_per_order": 0.0,
        },
        "Pro Fixed": {
            "stock": 0.005,  # $0.005 par action
            "min_per_order": 1.0,  # Minimum $1
            "max_per_order": lambda shares, price: min(
                shares * 0.005, 0.01 * shares * price
            ),  # Max 1% de la valeur
        },
        "Pro Tiered": {
            "stock": lambda shares: (
                0.0035 if shares <= 10000 else (0.0020 if shares <= 20000 else 0.0015)
            ),
            "min_per_order": 0.35,
            "max_per_order": lambda shares, price: 0.01 * shares * price,  # Max 1%
        },
    }

    def __init__(self, portfolio_file: str = "portfolio.json", use_ibkr: bool = True):
        """
        Initialise le gestionnaire de portfolio

        Args:
            portfolio_file: Chemin vers le fichier de portfolio
            use_ibkr: Si True, utilise les données IBKR si disponibles
        """
        self.portfolio_file = os.path.join(os.path.dirname(__file__), portfolio_file)
        self.use_ibkr = use_ibkr
        self.positions = self.load_portfolio()

    def load_portfolio(self) -> List[Dict]:
        """
        Charge le portfolio depuis IBKR uniquement.

        Returns:
            Liste des positions (vide si compte IBKR sans positions)
        """
        if self.use_ibkr and _ib_client is not None:
            result = self._load_from_ibkr()
            if result is not None:
                print(f"✅ Portfolio chargé depuis IBKR: {len(result)} positions")
                return result
        return []

    def _load_from_ibkr(self) -> Optional[List[Dict]]:
        """
        Charge les positions depuis IBKR API.

        Returns:
            Liste des positions, [] si compte sans positions, None si erreur
        """
        if _ib_client is None:
            return None

        try:
            ibkr_positions = _ib_client.get_account_positions(timeout=10.0)

            if not ibkr_positions:
                return []  # Compte valide mais sans positions ouvertes

            # Le plan IBKR n'est pas exposé par l'API des positions : on utilise
            # le plan configuré par l'utilisateur pour calculer des frais réalistes.
            plan = _configured_ibkr_plan()

            positions = []
            for symbol, pos_info in ibkr_positions.items():
                if pos_info["position"] <= 0:
                    continue
                positions.append(
                    {
                        "symbol": symbol,
                        "shares": int(pos_info["position"]),
                        "avg_price": float(pos_info["avg_cost"]),
                        "date_bought": datetime.now().strftime("%Y-%m-%d"),
                        "ibkr_plan": plan,
                        "from_ibkr": True,
                    }
                )
            return positions
        except Exception as e:
            print(f"⚠️ Erreur lors du chargement depuis IBKR: {e}")
            return None

    def save_portfolio(self):
        """Sauvegarde le portfolio dans le fichier JSON"""
        try:
            with open(self.portfolio_file, "w") as f:
                json.dump(self.positions, f, indent=2)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du portfolio: {e}")

    def add_position(
        self,
        symbol: str,
        shares: int,
        avg_price: float,
        date_bought: str,
        ibkr_plan: str = "Lite",
    ):
        """
        Ajoute une position au portfolio

        Args:
            symbol: Symbole de l'action
            shares: Nombre d'actions
            avg_price: Prix moyen d'achat
            date_bought: Date d'achat (YYYY-MM-DD)
            ibkr_plan: Plan IBKR utilisé
        """
        position = {
            "symbol": symbol,
            "shares": shares,
            "avg_price": avg_price,
            "date_bought": date_bought,
            "ibkr_plan": ibkr_plan,
        }
        self.positions.append(position)
        self.save_portfolio()

    def remove_position(self, symbol: str):
        """Supprime une position du portfolio"""
        self.positions = [p for p in self.positions if p["symbol"] != symbol]
        self.save_portfolio()

    def calculate_fees(
        self, shares: int, price: float, plan: str, is_buy: bool = True
    ) -> float:
        """
        Calcule les frais de transaction IBKR

        Args:
            shares: Nombre d'actions
            price: Prix par action
            plan: Plan IBKR (Lite, Pro Fixed, Pro Tiered)
            is_buy: True pour achat, False pour vente

        Returns:
            Montant des frais
        """
        if plan not in self.IBKR_FEES:
            return 0.0

        fees_config = self.IBKR_FEES[plan]

        # Lite : 0$ commission mais routing fees
        if plan == "Lite":
            # TODO: estimer les routing fees IBKR Lite (variables selon l'order
            # flow / la venue). Retourne 0.0 pour l'instant, ce qui sous-estime
            # légèrement les frais réels des positions sur le plan Lite.
            routing_fee = 0.0
            return routing_fee

        # Pro Fixed
        if plan == "Pro Fixed":
            fee_per_share = fees_config["stock"]
            total_fee = shares * fee_per_share
            min_fee = fees_config["min_per_order"]
            max_fee = fees_config["max_per_order"](shares, price)
            return max(min_fee, min(total_fee, max_fee))

        # Pro Tiered
        if plan == "Pro Tiered":
            fee_per_share = fees_config["stock"](shares)
            total_fee = shares * fee_per_share
            min_fee = fees_config["min_per_order"]
            max_fee = fees_config["max_per_order"](shares, price)
            return max(min_fee, min(total_fee, max_fee))

        return 0.0

    def get_current_prices(self) -> Dict[str, float]:
        """
        Récupère les prix actuels de toutes les positions depuis GCS.
        Fallback : avg_price si GCS n'a pas de données.
        """
        from datetime import date, timedelta

        prices = {}
        day = (date.today() - timedelta(days=1)).isoformat()

        for position in self.positions:
            symbol = position["symbol"]
            fallback = position["avg_price"]

            try:
                close = _cached_latest_close(symbol, day)
                if close is not None:
                    prices[symbol] = close
                    continue
            except Exception as e:
                print(f"GCS prix manquant pour {symbol}: {e}")

            prices[symbol] = fallback

        return prices

    def calculate_portfolio_stats(self) -> pd.DataFrame:
        """
        Calcule les statistiques du portfolio

        Returns:
            DataFrame avec toutes les métriques
        """
        if not self.positions:
            return pd.DataFrame()

        # Récupérer les prix actuels
        current_prices = self.get_current_prices()

        data = []
        for position in self.positions:
            symbol = position["symbol"]
            shares = position["shares"]
            avg_price = position["avg_price"]
            current_price = current_prices.get(symbol, avg_price)
            plan = position.get("ibkr_plan", "Lite")

            # Valeurs de base
            cost_basis = shares * avg_price
            current_value = shares * current_price

            # Frais d'achat
            buy_fees = self.calculate_fees(shares, avg_price, plan, is_buy=True)

            # Frais de vente (estimés)
            sell_fees = self.calculate_fees(shares, current_price, plan, is_buy=False)

            # Total des frais
            total_fees = buy_fees + sell_fees

            # Plus-value brute (sans frais)
            gross_pnl = current_value - cost_basis

            # Plus-value nette (après frais)
            net_pnl = gross_pnl - total_fees

            # % gain IBKR (affiché sans frais)
            ibkr_gain_pct = ((current_price - avg_price) / avg_price) * 100

            # % gain réel (après frais) : rapporté à la mise réelle, c.-à-d. le
            # coût d'achat + les frais d'achat (capital effectivement engagé).
            capital_outlay = cost_basis + buy_fees
            real_gain_pct = (net_pnl / capital_outlay) * 100 if capital_outlay > 0 else 0.0

            data.append(
                {
                    "Symbole": symbol,
                    "Actions": shares,
                    "Prix Achat": avg_price,
                    "Prix Actuel": current_price,
                    "Valeur Investie": cost_basis,
                    "Valeur Actuelle": current_value,
                    "Frais Achat": buy_fees,
                    "Frais Vente (est.)": sell_fees,
                    "Frais Totaux": total_fees,
                    "Plus-Value ($)": net_pnl,
                    "Gain IBKR (%)": ibkr_gain_pct,
                    "Gain Réel (%)": real_gain_pct,
                    "Plan IBKR": plan,
                    "Date Achat": position["date_bought"],
                }
            )

        df = pd.DataFrame(data)

        # Trier par gain réel décroissant
        df = df.sort_values("Gain Réel (%)", ascending=False)

        return df

    def get_account_cash_from_ibkr(self) -> Optional[float]:
        """
        Récupère le cash disponible depuis IBKR

        Returns:
            Montant du cash disponible ou None si non disponible
        """
        if not self.use_ibkr or _ib_client is None or not _ib_client.isConnected():
            return None

        try:
            account_summary = _ib_client.get_account_summary(timeout=10.0)
            # TotalCashValue = cash total du compte
            cash = account_summary.get("TotalCashValue")
            if cash is not None:
                print(f"✅ Cash IBKR récupéré: ${cash:,.2f}")
                return float(cash)
        except Exception as e:
            print(f"⚠️ Erreur lors de la récupération du cash IBKR: {e}")

        return None

    def get_portfolio_summary(self, available_cash: float = 0) -> Dict:
        """
        Retourne un résumé du portfolio

        Args:
            available_cash: Capital disponible non investi

        Returns:
            Dict avec toutes les métriques du portfolio
        """
        if not self.positions:
            return {
                "total_invested": 0,
                "total_value": 0,
                "total_pnl": 0,
                "total_fees": 0,
                "total_gain_pct": 0,
                "num_positions": 0,
                "available_cash": available_cash,
                "total_capitalization": available_cash,
            }

        df = self.calculate_portfolio_stats()

        total_invested = df["Valeur Investie"].sum()
        total_value = df["Valeur Actuelle"].sum()
        total_pnl = df["Plus-Value ($)"].sum()
        total_fees = df["Frais Totaux"].sum()

        # Capitalisation totale = valeur des positions + cash disponible
        total_capitalization = total_value + available_cash

        return {
            "total_invested": total_invested,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_fees": total_fees,
            "total_gain_pct": (
                (total_pnl / total_invested * 100) if total_invested > 0 else 0
            ),
            "num_positions": len(df),
            "available_cash": available_cash,
            "total_capitalization": total_capitalization,
        }


def create_sample_portfolio():
    """Crée un portfolio d'exemple pour tester"""
    manager = PortfolioManager()

    # Exemples de positions
    sample_positions = [
        {
            "symbol": "AAPL",
            "shares": 10,
            "avg_price": 150.00,
            "date_bought": "2024-01-15",
            "ibkr_plan": "Lite",
        },
        {
            "symbol": "MSFT",
            "shares": 5,
            "avg_price": 350.00,
            "date_bought": "2024-02-20",
            "ibkr_plan": "Pro Fixed",
        },
        {
            "symbol": "GOOGL",
            "shares": 8,
            "avg_price": 140.00,
            "date_bought": "2024-03-10",
            "ibkr_plan": "Lite",
        },
    ]

    for pos in sample_positions:
        manager.add_position(**pos)

    print("Portfolio d'exemple créé avec 3 positions")
    return manager


if __name__ == "__main__":
    # Test du gestionnaire
    manager = create_sample_portfolio()

    print("\n=== Portfolio Stats ===")
    df = manager.calculate_portfolio_stats()
    print(df.to_string())

    print("\n=== Portfolio Summary ===")
    summary = manager.get_portfolio_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")
