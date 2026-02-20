"""
IBKR Fee Calculator
Calculates Interactive Brokers commission fees for accurate P&L tracking
"""
import logging
from typing import Dict, Any
from enum import Enum


class IBKRPlan(Enum):
    """IBKR pricing plans"""
    PRO = "pro"
    LITE = "lite"
    TIERED = "tiered"


class FeeCalculator:
    """
    Calculates IBKR trading fees and commissions

    IBKR Pro (Fixed):
    - US Stocks: $0.005 per share
    - Minimum: $1.00 per order
    - Maximum: 1% of trade value

    IBKR Lite:
    - US Stocks: $0 commission
    - May have routing fees
    """

    def __init__(self, config: dict):
        """
        Initialize fee calculator

        Args:
            config: Trading configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Get fee configuration
        fee_config = config.get('fees', {})
        self.plan = IBKRPlan(fee_config.get('ibkr_plan', 'pro'))
        self.per_share_rate = fee_config.get('per_share_rate', 0.005)
        self.min_commission = fee_config.get('min_commission', 1.00)
        self.max_commission_pct = fee_config.get('max_commission_pct', 0.01)

        # Additional fees
        self.sec_fee_rate = fee_config.get('sec_fee_rate', 0.0000278)  # SEC fee
        self.finra_taf_rate = fee_config.get('finra_taf_rate', 0.000166)  # FINRA TAF

        self.logger.info(f"Fee calculator initialized with plan: {self.plan.value}")

    def calculate_commission(self, quantity: int, price: float, order_type: str = 'market') -> float:
        """
        Calculate IBKR commission for a trade

        Args:
            quantity: Number of shares
            price: Price per share
            order_type: Type of order (market, limit, etc.)

        Returns:
            Commission amount in USD
        """
        if self.plan == IBKRPlan.LITE:
            # IBKR Lite has zero commissions
            return 0.0

        # IBKR Pro: $0.005 per share
        commission = quantity * self.per_share_rate

        # Apply minimum commission
        commission = max(commission, self.min_commission)

        # Apply maximum commission (1% of trade value)
        trade_value = quantity * price
        max_commission = trade_value * self.max_commission_pct
        commission = min(commission, max_commission)

        return round(commission, 2)

    def calculate_regulatory_fees(self, quantity: int, price: float, side: str) -> Dict[str, float]:
        """
        Calculate regulatory fees (SEC, FINRA)

        Args:
            quantity: Number of shares
            price: Price per share
            side: 'buy' or 'sell'

        Returns:
            Dictionary with fee breakdown
        """
        trade_value = quantity * price
        fees = {
            'sec_fee': 0.0,
            'finra_taf': 0.0,
            'total_regulatory': 0.0
        }

        if side.lower() == 'sell':
            # SEC fee only applies to sells
            # Rate: $27.80 per $1,000,000 of principal = 0.00002780
            fees['sec_fee'] = round(trade_value * self.sec_fee_rate, 2)

            # FINRA TAF (Trading Activity Fee) only on sells
            # Rate: $0.000166 per share
            fees['finra_taf'] = round(quantity * self.finra_taf_rate, 2)

        fees['total_regulatory'] = fees['sec_fee'] + fees['finra_taf']
        return fees

    def calculate_total_fees(self, quantity: int, price: float, side: str,
                            order_type: str = 'market') -> Dict[str, float]:
        """
        Calculate all fees for a trade

        Args:
            quantity: Number of shares
            price: Price per share
            side: 'buy' or 'sell'
            order_type: Type of order

        Returns:
            Dictionary with complete fee breakdown
        """
        # Commission
        commission = self.calculate_commission(quantity, price, order_type)

        # Regulatory fees
        regulatory = self.calculate_regulatory_fees(quantity, price, side)

        # Total
        total_fees = commission + regulatory['total_regulatory']

        result = {
            'commission': commission,
            'sec_fee': regulatory['sec_fee'],
            'finra_taf': regulatory['finra_taf'],
            'total_regulatory': regulatory['total_regulatory'],
            'total_fees': round(total_fees, 2),
            'trade_value': round(quantity * price, 2)
        }

        self.logger.debug(
            f"Fees for {side} {quantity} @ ${price:.2f}: "
            f"Commission=${result['commission']:.2f}, "
            f"Regulatory=${result['total_regulatory']:.2f}, "
            f"Total=${result['total_fees']:.2f}"
        )

        return result

    def calculate_round_trip_fees(self, quantity: int, entry_price: float,
                                  exit_price: float) -> Dict[str, float]:
        """
        Calculate total fees for a complete round trip (buy + sell)

        Args:
            quantity: Number of shares
            entry_price: Entry price
            exit_price: Exit price

        Returns:
            Dictionary with round trip fee breakdown
        """
        # Entry fees (buy)
        entry_fees = self.calculate_total_fees(quantity, entry_price, 'buy')

        # Exit fees (sell)
        exit_fees = self.calculate_total_fees(quantity, exit_price, 'sell')

        # Combined
        result = {
            'entry_fees': entry_fees['total_fees'],
            'exit_fees': exit_fees['total_fees'],
            'total_round_trip_fees': round(
                entry_fees['total_fees'] + exit_fees['total_fees'], 2
            ),
            'entry_commission': entry_fees['commission'],
            'exit_commission': exit_fees['commission'],
            'total_commission': round(
                entry_fees['commission'] + exit_fees['commission'], 2
            ),
            'total_regulatory': round(
                entry_fees['total_regulatory'] + exit_fees['total_regulatory'], 2
            )
        }

        return result

    def calculate_net_pnl(self, quantity: int, entry_price: float,
                         exit_price: float) -> Dict[str, float]:
        """
        Calculate net profit/loss after all fees

        Args:
            quantity: Number of shares
            entry_price: Entry price
            exit_price: Exit price

        Returns:
            Dictionary with P&L breakdown including fees
        """
        # Gross P&L (before fees)
        gross_pnl = (exit_price - entry_price) * quantity

        # Fees
        fees = self.calculate_round_trip_fees(quantity, entry_price, exit_price)

        # Net P&L (after fees)
        net_pnl = gross_pnl - fees['total_round_trip_fees']

        # Percentage returns
        cost_basis = quantity * entry_price
        gross_return_pct = (gross_pnl / cost_basis) * 100 if cost_basis > 0 else 0
        net_return_pct = (net_pnl / cost_basis) * 100 if cost_basis > 0 else 0

        result = {
            'quantity': quantity,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'gross_pnl': round(gross_pnl, 2),
            'total_fees': fees['total_round_trip_fees'],
            'net_pnl': round(net_pnl, 2),
            'gross_return_pct': round(gross_return_pct, 2),
            'net_return_pct': round(net_return_pct, 2),
            'fee_impact_pct': round(
                (fees['total_round_trip_fees'] / abs(gross_pnl) * 100)
                if gross_pnl != 0 else 0, 2
            )
        }

        self.logger.info(
            f"P&L: {quantity} shares @ ${entry_price:.2f} → ${exit_price:.2f}: "
            f"Gross=${result['gross_pnl']:.2f}, "
            f"Fees=${result['total_fees']:.2f}, "
            f"Net=${result['net_pnl']:.2f} ({result['net_return_pct']:.2f}%)"
        )

        return result

    def adjust_target_for_fees(self, entry_price: float, quantity: int,
                               min_profit_pct: float = 0.5) -> float:
        """
        Calculate minimum target price to achieve desired profit after fees

        Args:
            entry_price: Entry price
            quantity: Number of shares
            min_profit_pct: Minimum desired profit percentage

        Returns:
            Minimum target price to achieve profit after fees
        """
        # Calculate fees for round trip at entry price (conservative estimate)
        fees = self.calculate_round_trip_fees(quantity, entry_price, entry_price)
        total_fees = fees['total_round_trip_fees']

        # Calculate cost basis
        cost_basis = quantity * entry_price

        # Required gross profit to achieve net profit after fees
        required_net_profit = cost_basis * (min_profit_pct / 100)
        required_gross_profit = required_net_profit + total_fees

        # Target price
        target_price = entry_price + (required_gross_profit / quantity)

        self.logger.debug(
            f"Target price adjusted for fees: "
            f"Entry=${entry_price:.2f}, "
            f"Fees=${total_fees:.2f}, "
            f"Target=${target_price:.2f} "
            f"(for {min_profit_pct}% net profit)"
        )

        return round(target_price, 2)

    def get_fee_summary(self) -> Dict[str, Any]:
        """
        Get fee configuration summary

        Returns:
            Dictionary with fee structure information
        """
        return {
            'plan': self.plan.value,
            'per_share_rate': self.per_share_rate,
            'min_commission': self.min_commission,
            'max_commission_pct': self.max_commission_pct,
            'sec_fee_rate': self.sec_fee_rate,
            'finra_taf_rate': self.finra_taf_rate,
            'description': self._get_plan_description()
        }

    def _get_plan_description(self) -> str:
        """Get description of current fee plan"""
        if self.plan == IBKRPlan.LITE:
            return "IBKR Lite: $0 commissions"
        elif self.plan == IBKRPlan.PRO:
            return f"IBKR Pro: ${self.per_share_rate} per share (min ${self.min_commission}, max {self.max_commission_pct*100}%)"
        else:
            return "IBKR Tiered pricing"
