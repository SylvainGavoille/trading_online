"""
Kill Switch - Emergency Stop System
Provides circuit breaker functionality to halt all trading operations
"""
import logging
from datetime import datetime, UTC
from typing import Optional, Dict, Any
from enum import Enum


class KillSwitchReason(Enum):
    """Reasons for kill switch activation"""
    MAX_DRAWDOWN = "max_drawdown_exceeded"
    DAILY_LOSS = "daily_loss_limit_exceeded"
    SYSTEM_ERROR = "critical_system_error"
    CONNECTION_LOST = "broker_connection_lost"
    MANUAL = "manual_activation"
    REPEATED_FAILURES = "repeated_trade_failures"


class KillSwitch:
    """
    Emergency stop system for trading operations

    Once activated, prevents all new trades until manually reset
    """

    def __init__(self, config: dict):
        """
        Initialize kill switch

        Args:
            config: Trading configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.is_active = False
        self.activation_time: Optional[datetime] = None
        self.reason: Optional[KillSwitchReason] = None
        self.details: Optional[str] = None
        self.failure_count = 0
        self.max_failures = 5  # Activate after 5 consecutive failures

    def activate(self, reason: KillSwitchReason, details: str = "") -> None:
        """
        Activate the kill switch

        Args:
            reason: Reason for activation
            details: Additional details about the activation
        """
        if not self.is_active:
            self.is_active = True
            self.activation_time = datetime.now(UTC)
            self.reason = reason
            self.details = details

            # Log critical alert
            self.logger.critical("=" * 70)
            self.logger.critical("🚨 KILL SWITCH ACTIVATED 🚨")
            self.logger.critical("=" * 70)
            self.logger.critical(f"Reason: {reason.value}")
            self.logger.critical(f"Details: {details}")
            self.logger.critical(f"Time: {self.activation_time.isoformat()}")
            self.logger.critical("ALL TRADING OPERATIONS HALTED")
            self.logger.critical("Manual reset required to resume trading")
            self.logger.critical("=" * 70)

    def check_and_activate_if_needed(self, portfolio: Dict[str, Any]) -> bool:
        """
        Check conditions and activate kill switch if necessary

        Args:
            portfolio: Current portfolio state

        Returns:
            True if kill switch was activated, False otherwise
        """
        if self.is_active:
            return True

        # Check max drawdown
        if self._check_max_drawdown_breach(portfolio):
            max_dd = self.config['risk_management']['loss_limits']['max_drawdown']
            current_dd = self._calculate_drawdown(portfolio)
            self.activate(
                KillSwitchReason.MAX_DRAWDOWN,
                f"Drawdown {current_dd:.2%} exceeded limit {max_dd:.2%}"
            )
            return True

        # Check daily loss limit with buffer
        if self._check_daily_loss_breach(portfolio):
            limit = self.config['risk_management']['loss_limits']['daily_loss_limit']
            current_loss = portfolio.get('daily_loss', 0)
            self.activate(
                KillSwitchReason.DAILY_LOSS,
                f"Daily loss ${current_loss:.2f} exceeded critical threshold ${limit * 1.5:.2f}"
            )
            return True

        return False

    def _check_max_drawdown_breach(self, portfolio: Dict[str, Any]) -> bool:
        """Check if max drawdown has been breached"""
        try:
            max_drawdown = self.config['risk_management']['loss_limits']['max_drawdown']
            current_drawdown = self._calculate_drawdown(portfolio)

            # Activate if drawdown exceeds limit
            return current_drawdown > max_drawdown

        except Exception as e:
            self.logger.error(f"Error checking drawdown: {e}")
            return False

    def _calculate_drawdown(self, portfolio: Dict[str, Any]) -> float:
        """Calculate current drawdown"""
        peak_value = portfolio.get('peak_value', portfolio.get('total_value', 0))
        current_value = portfolio.get('total_value', 0)

        if peak_value <= 0:
            return 0.0

        drawdown = (peak_value - current_value) / peak_value
        return max(0.0, drawdown)  # Ensure non-negative

    def _check_daily_loss_breach(self, portfolio: Dict[str, Any]) -> bool:
        """Check if daily loss has exceeded critical threshold (1.5x limit)"""
        try:
            daily_loss_limit = self.config['risk_management']['loss_limits']['daily_loss_limit']
            daily_loss = portfolio.get('daily_loss', 0)

            # Critical threshold is 1.5x the configured limit
            critical_threshold = daily_loss_limit * 1.5

            return daily_loss > critical_threshold

        except Exception as e:
            self.logger.error(f"Error checking daily loss: {e}")
            return False

    def record_failure(self) -> None:
        """
        Record a trade failure
        Activates kill switch after repeated failures
        """
        self.failure_count += 1

        if self.failure_count >= self.max_failures:
            self.activate(
                KillSwitchReason.REPEATED_FAILURES,
                f"{self.failure_count} consecutive trade failures detected"
            )

    def reset_failures(self) -> None:
        """Reset failure counter after successful trade"""
        self.failure_count = 0

    def is_trading_allowed(self) -> bool:
        """
        Check if trading is currently allowed

        Returns:
            True if trading allowed, False if kill switch active
        """
        if self.is_active:
            self.logger.warning(
                f"Trading blocked by kill switch: {self.reason.value if self.reason else 'unknown'}"
            )
            return False
        return True

    def reset(self, authorized: bool = False) -> bool:
        """
        Reset the kill switch (requires manual authorization)

        Args:
            authorized: Must be True to confirm manual reset

        Returns:
            True if reset successful, False otherwise
        """
        if not authorized:
            self.logger.error("Kill switch reset requires explicit authorization")
            return False

        if self.is_active:
            self.logger.warning("=" * 70)
            self.logger.warning("KILL SWITCH RESET")
            self.logger.warning(f"Previous reason: {self.reason.value if self.reason else 'unknown'}")
            self.logger.warning(f"Reset time: {datetime.now(UTC).isoformat()}")
            self.logger.warning("Trading operations resuming")
            self.logger.warning("=" * 70)

            self.is_active = False
            self.activation_time = None
            self.reason = None
            self.details = None
            self.failure_count = 0

            return True

        self.logger.info("Kill switch was not active")
        return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get current kill switch status

        Returns:
            Dictionary with kill switch status information
        """
        return {
            'is_active': self.is_active,
            'reason': self.reason.value if self.reason else None,
            'details': self.details,
            'activation_time': self.activation_time.isoformat() if self.activation_time else None,
            'failure_count': self.failure_count,
            'max_failures': self.max_failures
        }
