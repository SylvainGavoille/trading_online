"""
IBKR Fee Calculator - Complete Implementation
Supports IBKR Lite, Pro Fixed, and Pro Tiered pricing plans
"""
import logging
from typing import Dict, Any, Optional
from enum import Enum
from collections import defaultdict
from datetime import datetime, UTC, timedelta


class IBKRPlan(Enum):
    """IBKR pricing plans"""
    LITE = "lite"           # $0 commission
    PRO_FIXED = "pro_fixed"  # Fixed $0.005/share
    PRO_TIERED = "pro_tiered"  # Volume-based tiers with rebates


class FeeCalculator:
    """
    Calculates IBKR trading fees for all pricing plans

    Plans:
    1. IBKR Lite: $0 commission on US stocks/ETFs
    2. IBKR Pro Fixed: $0.005/share (min $1, max 1%)
    3. IBKR Pro Tiered: Volume-based rates with rebates
    """

    # Tiered rate structure (monthly volume)
    TIERED_RATES = [
        {'min_volume': 0, 'max_volume': 50000, 'rate': 0.0035, 'rebate': 0.0001},
        {'min_volume': 50000, 'max_volume': 200000, 'rate': 0.0025, 'rebate': 0.0002},
        {'min_volume': 200000, 'max_volume': 1000000, 'rate': 0.0018, 'rebate': 0.0003},
        {'min_volume': 1000000, 'max_volume': float('inf'), 'rate': 0.0015, 'rebate': 0.0004}
    ]

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
        plan_str = fee_config.get('ibkr_plan', 'pro_fixed')

        # Map plan names
        plan_mapping = {
            'lite': IBKRPlan.LITE,
            'pro': IBKRPlan.PRO_FIXED,
            'pro_fixed': IBKRPlan.PRO_FIXED,
            'tiered': IBKRPlan.PRO_TIERED,
            'pro_tiered': IBKRPlan.PRO_TIERED
        }
        self.plan = plan_mapping.get(plan_str, IBKRPlan.PRO_FIXED)

        # Pro Fixed rates
        self.per_share_rate = fee_config.get('per_share_rate', 0.005)
        self.min_commission = fee_config.get('min_commission', 1.00)
        self.max_commission_pct = fee_config.get('max_commission_pct', 0.01)

        # Regulatory fees (same for all plans)
        self.sec_fee_rate = fee_config.get('sec_fee_rate', 0.0000278)  # $27.80 per $1M
        self.finra_taf_rate = fee_config.get('finra_taf_rate', 0.000166)  # $0.166 per 1000 shares

        # Volume tracking for tiered pricing
        self.monthly_volume = defaultdict(int)  # symbol -> volume
        self.last_reset = datetime.now(UTC)

        self.logger.info(f"Fee calculator initialized with plan: {self.plan.value}")

    def calculate_commission(self, quantity: int, price: float,
                            order_type: str = 'market',
                            provides_liquidity: bool = False) -> Dict[str, float]:
        """
        Calculate IBKR commission for a trade

        Args:
            quantity: Number of shares
            price: Price per share
            order_type: Type of order (market, limit, etc.)
            provides_liquidity: True if limit order adds liquidity (for tiered)

        Returns:
            Dictionary with commission breakdown
        """
        if self.plan == IBKRPlan.LITE:
            return self._calculate_lite_commission(quantity, price)
        elif self.plan == IBKRPlan.PRO_FIXED:
            return self._calculate_fixed_commission(quantity, price)
        elif self.plan == IBKRPlan.PRO_TIERED:
            return self._calculate_tiered_commission(quantity, price, provides_liquidity)

        return {'commission': 0.0, 'rebate': 0.0, 'net_commission': 0.0}

    def _calculate_lite_commission(self, quantity: int, price: float) -> Dict[str, float]:
        """
        IBKR Lite: $0 commission on US stocks/ETFs

        Returns:
            Commission breakdown (all zeros)
        """
        return {
            'commission': 0.0,
            'rebate': 0.0,
            'net_commission': 0.0,
            'plan': 'lite',
            'note': 'Zero commission on US stocks/ETFs'
        }

    def _calculate_fixed_commission(self, quantity: int, price: float) -> Dict[str, float]:
        """
        IBKR Pro Fixed: $0.005 per share (min $1, max 1%)

        Args:
            quantity: Number of shares
            price: Price per share

        Returns:
            Commission breakdown
        """
        # Base commission: $0.005 per share
        commission = quantity * self.per_share_rate

        # Apply minimum
        commission = max(commission, self.min_commission)

        # Apply maximum (1% of trade value)
        trade_value = quantity * price
        max_commission = trade_value * self.max_commission_pct
        commission = min(commission, max_commission)

        return {
            'commission': round(commission, 2),
            'rebate': 0.0,
            'net_commission': round(commission, 2),
            'plan': 'pro_fixed',
            'rate_per_share': self.per_share_rate,
            'min_applied': commission == self.min_commission,
            'max_applied': commission == max_commission
        }

    def _calculate_tiered_commission(self, quantity: int, price: float,
                                    provides_liquidity: bool = False) -> Dict[str, float]:
        """
        IBKR Pro Tiered: Volume-based rates with potential rebates

        Args:
            quantity: Number of shares
            price: Price per share
            provides_liquidity: True if limit order adds liquidity

        Returns:
            Commission breakdown with rebates
        """
        # Reset monthly volume if new month
        self._check_monthly_reset()

        # Get current monthly volume
        current_volume = sum(self.monthly_volume.values())

        # Find applicable tier
        tier = self._get_tier(current_volume)
        rate = tier['rate']
        rebate_rate = tier['rebate'] if provides_liquidity else 0.0

        # Calculate commission
        commission = quantity * rate

        # Calculate rebate (if provides liquidity)
        rebate = quantity * rebate_rate if provides_liquidity else 0.0

        # Net commission (can be negative with rebates!)
        net_commission = commission - rebate

        # Apply minimum $0.35 per order (for tiered)
        min_commission_tiered = 0.35
        if net_commission > 0:
            net_commission = max(net_commission, min_commission_tiered)
            commission = net_commission + rebate

        return {
            'commission': round(commission, 4),
            'rebate': round(rebate, 4),
            'net_commission': round(net_commission, 4),
            'plan': 'pro_tiered',
            'rate_per_share': rate,
            'rebate_per_share': rebate_rate,
            'monthly_volume': current_volume,
            'tier': tier,
            'provides_liquidity': provides_liquidity
        }

    def _get_tier(self, volume: int) -> Dict[str, Any]:
        """
        Get applicable tier based on monthly volume

        Args:
            volume: Current monthly volume

        Returns:
            Tier information
        """
        for tier in self.TIERED_RATES:
            if tier['min_volume'] <= volume < tier['max_volume']:
                return tier

        # Default to highest tier
        return self.TIERED_RATES[-1]

    def _check_monthly_reset(self):
        """Reset monthly volume if new month started"""
        now = datetime.now(UTC)
        if now.month != self.last_reset.month or now.year != self.last_reset.year:
            self.monthly_volume.clear()
            self.last_reset = now
            self.logger.info("Monthly volume reset")

    def record_trade_volume(self, symbol: str, quantity: int):
        """
        Record trade volume for tiered pricing

        Args:
            symbol: Trading symbol
            quantity: Number of shares traded
        """
        if self.plan == IBKRPlan.PRO_TIERED:
            self.monthly_volume[symbol] += quantity
            total_volume = sum(self.monthly_volume.values())
            self.logger.debug(f"Recorded {quantity} shares for {symbol}. Total monthly: {total_volume}")

    def calculate_regulatory_fees(self, quantity: int, price: float, side: str) -> Dict[str, float]:
        """
        Calculate regulatory fees (SEC, FINRA)
        Same for all plans

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
            # SEC fee: $27.80 per $1,000,000
            fees['sec_fee'] = round(trade_value * self.sec_fee_rate, 2)

            # FINRA TAF: $0.166 per 1000 shares
            fees['finra_taf'] = round(quantity * self.finra_taf_rate, 2)

        fees['total_regulatory'] = fees['sec_fee'] + fees['finra_taf']
        return fees

    def calculate_total_fees(self, quantity: int, price: float, side: str,
                            order_type: str = 'market',
                            provides_liquidity: bool = False) -> Dict[str, float]:
        """
        Calculate all fees for a trade

        Args:
            quantity: Number of shares
            price: Price per share
            side: 'buy' or 'sell'
            order_type: Type of order
            provides_liquidity: True if adds liquidity (for tiered)

        Returns:
            Dictionary with complete fee breakdown
        """
        # Commission
        commission_detail = self.calculate_commission(
            quantity, price, order_type, provides_liquidity
        )

        # Regulatory fees
        regulatory = self.calculate_regulatory_fees(quantity, price, side)

        # Total
        gross_commission = commission_detail.get('commission', 0.0)
        rebate = commission_detail.get('rebate', 0.0)
        net_commission = commission_detail.get('net_commission', 0.0)

        total_fees = net_commission + regulatory['total_regulatory']

        result = {
            'gross_commission': gross_commission,
            'rebate': rebate,
            'net_commission': net_commission,
            'sec_fee': regulatory['sec_fee'],
            'finra_taf': regulatory['finra_taf'],
            'total_regulatory': regulatory['total_regulatory'],
            'total_fees': round(total_fees, 2),
            'trade_value': round(quantity * price, 2),
            'plan': self.plan.value,
            'commission_detail': commission_detail
        }

        self.logger.debug(
            f"Fees ({self.plan.value}) for {side} {quantity} @ ${price:.2f}: "
            f"Comm=${net_commission:.2f}, Reg=${result['total_regulatory']:.2f}, "
            f"Total=${result['total_fees']:.2f}"
        )

        return result

    def calculate_round_trip_fees(self, quantity: int, entry_price: float,
                                  exit_price: float,
                                  entry_provides_liquidity: bool = False,
                                  exit_provides_liquidity: bool = True) -> Dict[str, float]:
        """
        Calculate total fees for a complete round trip (buy + sell)

        Args:
            quantity: Number of shares
            entry_price: Entry price
            exit_price: Exit price
            entry_provides_liquidity: If entry adds liquidity (limit buy)
            exit_provides_liquidity: If exit adds liquidity (limit sell)

        Returns:
            Dictionary with round trip fee breakdown
        """
        # Entry fees (buy)
        entry_fees = self.calculate_total_fees(
            quantity, entry_price, 'buy', 'limit' if entry_provides_liquidity else 'market',
            entry_provides_liquidity
        )

        # Exit fees (sell)
        exit_fees = self.calculate_total_fees(
            quantity, exit_price, 'sell', 'limit' if exit_provides_liquidity else 'market',
            exit_provides_liquidity
        )

        # Record volume for tiered
        self.record_trade_volume('round_trip', quantity * 2)  # Buy + sell

        # Combined
        result = {
            'entry_fees': entry_fees['total_fees'],
            'exit_fees': exit_fees['total_fees'],
            'total_round_trip_fees': round(
                entry_fees['total_fees'] + exit_fees['total_fees'], 2
            ),
            'entry_commission': entry_fees['net_commission'],
            'exit_commission': exit_fees['net_commission'],
            'total_commission': round(
                entry_fees['net_commission'] + exit_fees['net_commission'], 2
            ),
            'total_rebates': round(
                entry_fees.get('rebate', 0.0) + exit_fees.get('rebate', 0.0), 4
            ),
            'total_regulatory': round(
                entry_fees['total_regulatory'] + exit_fees['total_regulatory'], 2
            ),
            'plan': self.plan.value,
            'entry_detail': entry_fees,
            'exit_detail': exit_fees
        }

        return result

    def calculate_net_pnl(self, quantity: int, entry_price: float,
                         exit_price: float,
                         entry_provides_liquidity: bool = False,
                         exit_provides_liquidity: bool = True) -> Dict[str, float]:
        """
        Calculate net profit/loss after all fees

        Args:
            quantity: Number of shares
            entry_price: Entry price
            exit_price: Exit price
            entry_provides_liquidity: If entry adds liquidity
            exit_provides_liquidity: If exit adds liquidity

        Returns:
            Dictionary with P&L breakdown including fees
        """
        # Gross P&L (before fees)
        gross_pnl = (exit_price - entry_price) * quantity

        # Fees
        fees = self.calculate_round_trip_fees(
            quantity, entry_price, exit_price,
            entry_provides_liquidity, exit_provides_liquidity
        )

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
            'total_rebates': fees.get('total_rebates', 0.0),
            'net_pnl': round(net_pnl, 2),
            'gross_return_pct': round(gross_return_pct, 2),
            'net_return_pct': round(net_return_pct, 2),
            'fee_impact_pct': round(
                (fees['total_round_trip_fees'] / abs(gross_pnl) * 100)
                if gross_pnl != 0 else 0, 2
            ),
            'plan': self.plan.value,
            'fees_detail': fees
        }

        self.logger.info(
            f"P&L ({self.plan.value}): {quantity} @ ${entry_price:.2f} → ${exit_price:.2f}: "
            f"Gross=${result['gross_pnl']:.2f}, Fees=${result['total_fees']:.2f}, "
            f"Rebates=${result['total_rebates']:.4f}, Net=${result['net_pnl']:.2f} "
            f"({result['net_return_pct']:.2f}%)"
        )

        return result

    def adjust_target_for_fees(self, entry_price: float, quantity: int,
                               min_profit_pct: float = 0.5,
                               provides_liquidity: bool = True) -> float:
        """
        Calculate minimum target price to achieve desired profit after fees

        Args:
            entry_price: Entry price
            quantity: Number of shares
            min_profit_pct: Minimum desired profit percentage
            provides_liquidity: If using limit orders

        Returns:
            Minimum target price to achieve profit after fees
        """
        # Estimate fees at entry price
        fees = self.calculate_round_trip_fees(
            quantity, entry_price, entry_price, provides_liquidity, provides_liquidity
        )
        total_fees = fees['total_round_trip_fees']

        # Calculate cost basis
        cost_basis = quantity * entry_price

        # Required net profit
        required_net_profit = cost_basis * (min_profit_pct / 100)
        required_gross_profit = required_net_profit + total_fees

        # Target price
        target_price = entry_price + (required_gross_profit / quantity)

        self.logger.debug(
            f"Target ({self.plan.value}): Entry=${entry_price:.2f}, Fees=${total_fees:.2f}, "
            f"Target=${target_price:.2f} (for {min_profit_pct}% net)"
        )

        return round(target_price, 2)

    def get_fee_summary(self) -> Dict[str, Any]:
        """Get fee configuration summary"""
        summary = {
            'plan': self.plan.value,
            'description': self._get_plan_description()
        }

        if self.plan == IBKRPlan.PRO_FIXED:
            summary.update({
                'per_share_rate': self.per_share_rate,
                'min_commission': self.min_commission,
                'max_commission_pct': self.max_commission_pct
            })
        elif self.plan == IBKRPlan.PRO_TIERED:
            summary.update({
                'tiers': self.TIERED_RATES,
                'current_monthly_volume': sum(self.monthly_volume.values()),
                'current_tier': self._get_tier(sum(self.monthly_volume.values()))
            })

        summary.update({
            'sec_fee_rate': self.sec_fee_rate,
            'finra_taf_rate': self.finra_taf_rate
        })

        return summary

    def _get_plan_description(self) -> str:
        """Get description of current fee plan"""
        if self.plan == IBKRPlan.LITE:
            return "IBKR Lite: $0 commissions on US stocks/ETFs"
        elif self.plan == IBKRPlan.PRO_FIXED:
            return (f"IBKR Pro Fixed: ${self.per_share_rate:.4f}/share "
                   f"(min ${self.min_commission}, max {self.max_commission_pct*100}%)")
        elif self.plan == IBKRPlan.PRO_TIERED:
            tier = self._get_tier(sum(self.monthly_volume.values()))
            return (f"IBKR Pro Tiered: ${tier['rate']:.4f}/share at current volume "
                   f"(rebate: ${tier['rebate']:.4f}/share if providing liquidity)")
        return "Unknown plan"
