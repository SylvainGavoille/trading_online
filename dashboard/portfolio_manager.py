"""
Gestionnaire de Portfolio pour le Dashboard Streamlit
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import json
import os

_ib_client = None


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
            "max_per_order": 0.0
        },
        "Pro Fixed": {
            "stock": 0.005,  # $0.005 par action
            "min_per_order": 1.0,  # Minimum $1
            "max_per_order": lambda shares, price: min(shares * 0.005, 0.01 * shares * price)  # Max 1% de la valeur
        },
        "Pro Tiered": {
            "stock": lambda shares: 0.0035 if shares <= 10000 else (0.0020 if shares <= 20000 else 0.0015),
            "min_per_order": 0.35,
            "max_per_order": lambda shares, price: 0.01 * shares * price  # Max 1%
        }
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
        Charge le portfolio depuis IBKR si disponible, sinon depuis le fichier JSON

        Returns:
            Liste des positions
        """
        # Essayer d'abord de charger depuis IBKR si disponible
        if self.use_ibkr and _ib_client is not None:
            try:
                ibkr_positions = self._load_from_ibkr()
                if ibkr_positions:
                    print(f"✅ Portfolio chargé depuis IBKR: {len(ibkr_positions)} positions")
                    return ibkr_positions
            except Exception as e:
                print(f"⚠️ Erreur lors du chargement depuis IBKR: {e}")
                print("Fallback sur le fichier JSON...")

        # Fallback sur le fichier JSON
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erreur lors du chargement du portfolio: {e}")
                return []
        return []

    def _load_from_ibkr(self) -> List[Dict]:
        """
        Charge les positions depuis IBKR API

        Returns:
            Liste des positions au format standard
        """
        if _ib_client is None:
            return []

        # Récupérer les positions depuis IBKR
        ibkr_positions = _ib_client.get_account_positions(timeout=10.0)

        if not ibkr_positions:
            return []

        positions = []
        for symbol, pos_info in ibkr_positions.items():
            # Ignorer les positions courtes ou fermées
            if pos_info['position'] <= 0:
                continue

            position = {
                "symbol": symbol,
                "shares": int(pos_info['position']),
                "avg_price": float(pos_info['avg_cost']),
                "date_bought": datetime.now().strftime("%Y-%m-%d"),  # Date inconnue depuis IBKR
                "ibkr_plan": "Lite",  # Par défaut, peut être configuré
                "from_ibkr": True  # Marqueur pour indiquer la source
            }
            positions.append(position)

        return positions

    def save_portfolio(self):
        """Sauvegarde le portfolio dans le fichier JSON"""
        try:
            with open(self.portfolio_file, 'w') as f:
                json.dump(self.positions, f, indent=2)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du portfolio: {e}")

    def add_position(
        self,
        symbol: str,
        shares: int,
        avg_price: float,
        date_bought: str,
        ibkr_plan: str = "Lite"
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
            "ibkr_plan": ibkr_plan
        }
        self.positions.append(position)
        self.save_portfolio()

    def remove_position(self, symbol: str):
        """Supprime une position du portfolio"""
        self.positions = [p for p in self.positions if p["symbol"] != symbol]
        self.save_portfolio()

    def calculate_fees(self, shares: int, price: float, plan: str, is_buy: bool = True) -> float:
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
            # Routing fees approximatifs (peuvent varier)
            routing_fee = 0.0  # Simplifié pour l'exemple
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
        Récupère les prix actuels de toutes les positions.
        Priorité : store Parquet (EOD local) → avg_price en fallback.
        """
        import pandas as pd
        from datetime import date, timedelta

        prices = {}
        end_d   = date.today() - timedelta(days=1)
        start_d = end_d - timedelta(days=7)

        parquet_root = os.path.join(os.path.dirname(__file__), '..', 'price_historical')

        for position in self.positions:
            symbol   = position["symbol"]
            fallback = position["avg_price"]

            # --- Parquet (fiable, EOD) ---
            try:
                from src.data.download_history import parquet_path as _parquet_path
                frames = []
                day = start_d
                while day <= end_d:
                    path = _parquet_path(parquet_root, day, symbol)
                    if os.path.exists(path):
                        frames.append(pd.read_parquet(path))
                    day += timedelta(days=1)
                if frames:
                    df_p = pd.concat(frames, ignore_index=True)
                    df_p['date'] = pd.to_datetime(df_p['date'])
                    df_p = df_p.sort_values('date')
                    prices[symbol] = float(df_p['close'].iloc[-1])
                    continue
            except Exception as e:
                print(f"Parquet prix manquant pour {symbol}: {e}")

            # --- Fallback prix d'achat ---
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

            # % gain réel (après frais)
            real_gain_pct = (net_pnl / cost_basis) * 100

            data.append({
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
                "Date Achat": position["date_bought"]
            })

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
            cash = account_summary.get('TotalCashValue')
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
                "total_capitalization": available_cash
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
            "total_gain_pct": (total_pnl / total_invested * 100) if total_invested > 0 else 0,
            "num_positions": len(df),
            "available_cash": available_cash,
            "total_capitalization": total_capitalization
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
            "ibkr_plan": "Lite"
        },
        {
            "symbol": "MSFT",
            "shares": 5,
            "avg_price": 350.00,
            "date_bought": "2024-02-20",
            "ibkr_plan": "Pro Fixed"
        },
        {
            "symbol": "GOOGL",
            "shares": 8,
            "avg_price": 140.00,
            "date_bought": "2024-03-10",
            "ibkr_plan": "Lite"
        }
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
