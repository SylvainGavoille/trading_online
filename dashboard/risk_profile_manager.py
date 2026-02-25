"""
Risk Profile Manager for Dashboard
"""

import json
import os
from typing import Dict, Optional


# Risk profile definitions
RISK_PROFILES = {
    "Conservative": {
        "description": "Priority on capital preservation with moderate growth",
        "risk_tolerance": "Low",
        "time_horizon": "Short term (< 3 years)",
        "volatility_acceptance": "Very low (< 10% variation)",
        "loss_tolerance": "< 5% acceptable loss",
        "recommended_allocation": {
            "Stocks": "20-30%",
            "Bonds": "50-60%",
            "Cash": "10-20%",
            "Other": "< 10%",
        },
        "recommended_instruments": [
            "Dividend ETFs (VYM, SCHD)",
            "Bonds (AGG, BND)",
            "Defensive stocks (JNJ, PG, KO)",
            "Cash / Money Market",
        ],
        "avoid": [
            "High volatility stocks",
            "Cryptocurrencies",
            "Leveraged ETFs",
            "Penny stocks",
        ],
        "max_position_size": "10% of portfolio",
        "rebalancing_frequency": "Quarterly",
        "color": "#4CAF50",  # Green
    },
    "Moderate": {
        "description": "Balance between growth and security",
        "risk_tolerance": "Medium",
        "time_horizon": "Medium term (3-7 years)",
        "volatility_acceptance": "Moderate (10-20% variation)",
        "loss_tolerance": "5-15% acceptable loss",
        "recommended_allocation": {
            "Stocks": "50-60%",
            "Bonds": "25-35%",
            "Cash": "5-10%",
            "Other": "5-15%",
        },
        "recommended_instruments": [
            "Diversified ETFs (SPY, VOO, VTI)",
            "Blue-chip stocks (AAPL, MSFT, GOOGL)",
            "Sector ETFs (XLK, XLV, XLF)",
            "Bond/stock mix",
        ],
        "avoid": [
            "3x leveraged ETFs",
            "Speculative trading",
            "Excessive concentration",
        ],
        "max_position_size": "15% of portfolio",
        "rebalancing_frequency": "Semi-annual",
        "color": "#FF9800",  # Orange
    },
    "Aggressive": {
        "description": "Seeking maximum growth with acceptance of high volatility",
        "risk_tolerance": "High",
        "time_horizon": "Long term (> 7 years)",
        "volatility_acceptance": "High (> 20% variation)",
        "loss_tolerance": "> 15% acceptable loss temporarily",
        "recommended_allocation": {
            "Stocks": "70-90%",
            "Bonds": "0-10%",
            "Cash": "0-5%",
            "Other": "5-20%",
        },
        "recommended_instruments": [
            "Growth stocks (NVDA, TSLA, META)",
            "Concentrated sector ETFs (ARKK, XLK)",
            "Small/Mid caps (IWM)",
            "Emerging markets (VWO, EEM)",
            "Cryptos (BTC-USD, ETH-USD)",
        ],
        "avoid": ["Over-diversification that dilutes gains", "Too much idle cash"],
        "max_position_size": "25% of portfolio",
        "rebalancing_frequency": "Annual or opportunistic",
        "color": "#F44336",  # Red
    },
    "Very Aggressive": {
        "description": "Active trading, leverage, seeking rapid gains",
        "risk_tolerance": "Very high",
        "time_horizon": "Short/Medium term (speculative)",
        "volatility_acceptance": "Very high (> 30% variation)",
        "loss_tolerance": "20-50% acceptable loss (strict stop management)",
        "recommended_allocation": {
            "Volatile stocks": "40-60%",
            "Leveraged ETFs": "20-40%",
            "Options/Derivatives": "10-20%",
            "Cash (margin)": "5-10%",
        },
        "recommended_instruments": [
            "2x/3x leveraged ETFs (TQQQ, UPRO, SOXL)",
            "Momentum stocks (NVDA, AMD, SMCI)",
            "Volatile cryptos",
            "Options (calls/puts)",
            "Day trading / Swing trading",
        ],
        "avoid": [
            "Investing all capital at once",
            "Neglecting stop-loss orders",
            "Emotional trading",
        ],
        "max_position_size": "30% of portfolio",
        "rebalancing_frequency": "Daily/Weekly",
        "warnings": [
            "⚠️ Risk of total capital loss",
            "⚠️ Requires constant monitoring",
            "⚠️ High trading fees",
            "⚠️ Significant psychological stress",
        ],
        "color": "#9C27B0",  # Purple
    },
}


class RiskProfileManager:
    """User risk profile manager"""

    def __init__(self, config_file: str = "user_config.json"):
        """
        Initialize the manager

        Args:
            config_file: User configuration file
        """
        self.config_file = os.path.join(os.path.dirname(__file__), config_file)
        self.config = self.load_config()

    def load_config(self) -> Dict:
        """Load user configuration"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Config loading error: {e}")
                return self._default_config()
        return self._default_config()

    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            "risk_profile": "Moderate",
            "max_loss_per_trade": 2.0,  # %
            "max_portfolio_risk": 10.0,  # %
            "ibkr_plan": "Lite",
            "trading_frequency": "Medium term",
            "objectives": [],
        }

    def save_config(self):
        """Save configuration"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Config save error: {e}")

    def get_risk_profile(self) -> str:
        """Return current risk profile"""
        return self.config.get("risk_profile", "Moderate")

    def set_risk_profile(self, profile: str):
        """Set risk profile"""
        if profile in RISK_PROFILES:
            self.config["risk_profile"] = profile
            self.save_config()

    def get_profile_details(self, profile: Optional[str] = None) -> Dict:
        """Return profile details"""
        if profile is None:
            profile = self.get_risk_profile()
        return RISK_PROFILES.get(profile, RISK_PROFILES["Moderate"])

    def update_config(self, **kwargs):
        """Update configuration"""
        self.config.update(kwargs)
        self.save_config()

    def get_available_cash(self) -> Optional[float]:
        """Return available capital (None if not defined — read from IBKR)."""
        val = self.config.get("available_cash")
        return float(val) if val is not None else None

    def get_capital_initial(self) -> Optional[float]:
        """Return initial capital (None if not defined — read from IBKR)."""
        val = self.config.get("capital_initial")
        return float(val) if val is not None else None

    def get_risk_metrics(self) -> Dict:
        """Calculate current risk metrics"""
        profile = self.get_profile_details()

        return {
            "profile_name": self.get_risk_profile(),
            "risk_tolerance": profile["risk_tolerance"],
            "max_loss_per_trade": self.config.get("max_loss_per_trade", 2.0),
            "max_portfolio_risk": self.config.get("max_portfolio_risk", 10.0),
            "recommended_max_position": profile["max_position_size"],
            "rebalancing": profile["rebalancing_frequency"],
        }

    def validate_position_size(
        self, position_value: float, portfolio_value: float
    ) -> Dict:
        """
        Validate position size according to risk profile

        Returns:
            Dict with status and message
        """
        if portfolio_value == 0:
            return {"valid": False, "message": "Empty portfolio"}

        position_pct = (position_value / portfolio_value) * 100
        profile = self.get_profile_details()

        # Extract max percentage
        max_size_str = profile["max_position_size"]
        max_size_pct = float(max_size_str.replace("% of portfolio", ""))

        if position_pct > max_size_pct:
            return {
                "valid": False,
                "message": f"⚠️ Position too large ({position_pct:.1f}%) for {self.get_risk_profile()} profile (max: {max_size_pct}%)",
                "position_pct": position_pct,
                "max_allowed": max_size_pct,
            }

        return {
            "valid": True,
            "message": f"✅ Position size OK ({position_pct:.1f}%)",
            "position_pct": position_pct,
            "max_allowed": max_size_pct,
        }


if __name__ == "__main__":
    # Test
    manager = RiskProfileManager()

    print("=== Available Risk Profiles ===\n")
    for profile_name, profile_data in RISK_PROFILES.items():
        print(f"📊 {profile_name}")
        print(f"   {profile_data['description']}")
        print(f"   Tolerance: {profile_data['risk_tolerance']}")
        print(f"   Horizon: {profile_data['time_horizon']}")
        print()

    print(f"\n=== Current Profile ===")
    current = manager.get_risk_profile()
    details = manager.get_profile_details()
    print(f"Profile: {current}")
    print(f"Description: {details['description']}")

    print(f"\n=== Position Validation Test ===")
    result = manager.validate_position_size(15000, 100000)
    print(result["message"])
