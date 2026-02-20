import logging
from typing import Dict, Any, Optional
from datetime import datetime, UTC, timedelta
from collections import defaultdict

class RiskValidator:
    """Handles validation of trading risks and compliance"""
    
    def __init__(self, config: dict):
        """
        Initialize risk validator with configuration
        
        Args:
            config: Trading configuration dictionary
        """
        self.config = config
        self.risk_config = config['risk_management']
        self.logger = logging.getLogger(__name__)
        
        # Initialize trade frequency tracking
        self.trade_history = defaultdict(list)
        
        # Validate configuration
        if not self._validate_config():
            raise ValueError("Invalid risk management configuration")
    
    def _validate_config(self) -> bool:
        """Validate risk management configuration"""
        try:
            required_sections = ['position_limits', 'stop_loss', 'loss_limits', 'trade_frequency']
            if not all(section in self.risk_config for section in required_sections):
                self.logger.error("Missing required risk management sections")
                return False
            
            # Validate position limits
            position_limits = self.risk_config['position_limits']
            if not all(key in position_limits for key in ['max_position_size', 'max_portfolio_exposure']):
                self.logger.error("Invalid position limits configuration")
                return False
            
            # Validate stop loss
            stop_loss = self.risk_config['stop_loss']
            if not all(key in stop_loss for key in ['atr_multiplier', 'max_loss_per_trade']):
                self.logger.error("Invalid stop loss configuration")
                return False
            
            # Validate loss limits
            loss_limits = self.risk_config['loss_limits']
            if 'daily_loss_limit' not in loss_limits:
                self.logger.error("Invalid loss limits configuration")
                return False
            
            # Validate trade frequency
            trade_frequency = self.risk_config['trade_frequency']
            if 'max_daily_trades' not in trade_frequency:
                self.logger.error("Invalid trade frequency configuration")
                return False
            
            return True
            
        except Exception as e:
            self.logger.exception(f"Error validating configuration: {str(e)}")
            return False
    
    def validate_trade(self, trade_params: Dict[str, Any], portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate trade against risk management rules
        
        Args:
            trade_params: Trade parameters including size, price, etc.
            portfolio: Current portfolio state
            
        Returns:
            Validation result with approval status and details
        """
        self.logger.info(f"Validating trade for {trade_params['symbol']}")
        
        # Initialize risk check results
        risk_parameters = {
            'position_size_check': 'Invalid',
            'portfolio_exposure_check': 'Invalid',
            'stop_loss_level_check': 'Invalid',
            'risk_reward_ratio_check': 'Invalid',
            'compliance': 'Rejected'
        }
        
        try:
            # Position Size Check
            position_check = self._check_position_size(trade_params)
            if not position_check['approved']:
                return self._create_rejection_response(risk_parameters, position_check['reason'])
            risk_parameters['position_size_check'] = 'Valid'
            
            # Portfolio Exposure Check
            exposure_check = self._check_portfolio_exposure(trade_params, portfolio)
            if not exposure_check['approved']:
                return self._create_rejection_response(risk_parameters, exposure_check['reason'])
            risk_parameters['portfolio_exposure_check'] = 'Valid'
            
            # Stop Loss Check
            stop_loss_check = self._check_stop_loss(trade_params, portfolio)
            if not stop_loss_check['approved']:
                return self._create_rejection_response(risk_parameters, stop_loss_check['reason'])
            risk_parameters['stop_loss_level_check'] = 'Valid'
            
            # Risk/Reward Check
            risk_reward_check = self._check_risk_reward_ratio(trade_params)
            if not risk_reward_check['approved']:
                return self._create_rejection_response(risk_parameters, risk_reward_check['reason'])
            risk_parameters['risk_reward_ratio_check'] = 'Valid'
            
            # Daily Loss Limit Check
            loss_check = self._check_daily_loss_limit(portfolio)
            if not loss_check['approved']:
                return self._create_rejection_response(risk_parameters, loss_check['reason'])
                
            # Trade Frequency Check
            frequency_check = self._check_trade_frequency(trade_params['symbol'])
            if not frequency_check['approved']:
                return self._create_rejection_response(risk_parameters, frequency_check['reason'])
            
            # Record trade if all checks pass
            self._record_trade(trade_params['symbol'])
            
            # All checks passed
            risk_parameters['compliance'] = 'Approved'
            return {
                'approved': True,
                'risk_parameters': risk_parameters,
                'reason': 'All risk management checks passed'
            }
            
        except Exception as e:
            self.logger.exception(f"Error during risk validation: {str(e)}")
            return self._create_rejection_response(
                risk_parameters,
                f"Error during risk validation: {str(e)}"
            )
    
    def _record_trade(self, symbol: str) -> None:
        """Record a trade for frequency tracking"""
        current_time = datetime.now(UTC)
        self.trade_history[symbol].append(current_time)
        
        # Clean up old trade records
        cutoff_time = current_time - timedelta(days=1)
        self.trade_history[symbol] = [
            t for t in self.trade_history[symbol]
            if t > cutoff_time
        ]
    
    def _check_trade_frequency(self, symbol: str) -> Dict[str, Any]:
        """Check if within trade frequency limits"""
        current_time = datetime.now(UTC)
        cutoff_time = current_time - timedelta(days=1)
        
        # Count trades in the last 24 hours
        recent_trades = sum(
            1 for trade_time in self.trade_history[symbol]
            if trade_time > cutoff_time
        )
        
        max_daily_trades = self.risk_config['trade_frequency']['max_daily_trades']
        
        if recent_trades < max_daily_trades:
            return {'approved': True}
        return {
            'approved': False,
            'reason': f'Maximum daily trades ({max_daily_trades}) exceeded for {symbol}'
        }
    
    def _check_position_size(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate position size against limits"""
        max_position_size = self.risk_config['position_limits']['max_position_size']
        if trade_params['size'] <= max_position_size:
            return {'approved': True}
        return {
            'approved': False,
            'reason': f'Position size {trade_params["size"]} exceeds maximum limit of {max_position_size}'
        }
    
    def _check_portfolio_exposure(self, trade_params: Dict[str, Any], 
                                portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Validate portfolio exposure"""
        total_value = portfolio.get('total_value', 0)
        if total_value <= 0:
            return {
                'approved': False,
                'reason': 'Invalid portfolio value'
            }
            
        position_value = trade_params['size'] * trade_params['price']
        exposure = position_value / total_value
        max_exposure = self.risk_config['position_limits']['max_portfolio_exposure']
        
        if exposure <= max_exposure:
            return {'approved': True}
        return {
            'approved': False,
            'reason': f'Portfolio exposure {exposure:.2%} exceeds maximum limit of {max_exposure:.2%}'
        }
    
    def _check_stop_loss(self, trade_params: Dict[str, Any], 
                        portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Validate stop loss levels"""
        current_price = trade_params['price']
        stop_loss = trade_params['stop_loss']
        position_size = trade_params['size']
        
        potential_loss = (current_price - stop_loss) * position_size
        max_loss_amount = portfolio['total_value'] * self.risk_config['stop_loss']['max_loss_per_trade']
        
        if potential_loss <= max_loss_amount:
            return {'approved': True}
        return {
            'approved': False,
            'reason': f'Potential loss ${potential_loss:.2f} exceeds maximum allowed loss of ${max_loss_amount:.2f}'
        }
    
    def _check_risk_reward_ratio(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate risk/reward ratio"""
        current_price = trade_params['price']
        stop_loss = trade_params['stop_loss']
        target_price = trade_params['target_price']
        position_size = trade_params['size']
        
        potential_loss = (current_price - stop_loss) * position_size
        potential_reward = (target_price - current_price) * position_size
        
        if potential_loss <= 0:
            return {
                'approved': False,
                'reason': 'Invalid stop loss level'
            }
            
        risk_reward_ratio = potential_reward / potential_loss
        min_ratio = self.risk_config.get('risk_reward', {}).get('min_ratio', 2.0)
        
        if risk_reward_ratio >= min_ratio:
            return {'approved': True}
        return {
            'approved': False,
            'reason': f'Risk/reward ratio {risk_reward_ratio:.2f} is below minimum threshold of {min_ratio}'
        }
    
    def _check_daily_loss_limit(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Check if within daily loss limits"""
        daily_loss = portfolio.get('daily_loss', 0)
        daily_loss_limit = self.risk_config['loss_limits']['daily_loss_limit']
        
        if daily_loss <= daily_loss_limit:
            return {'approved': True}
        return {
            'approved': False,
            'reason': f'Daily loss ${daily_loss:.2f} exceeds limit of ${daily_loss_limit:.2f}'
        }
    
    def _create_rejection_response(self, risk_parameters: Dict[str, str], 
                                 reason: str) -> Dict[str, Any]:
        """Create standardized rejection response"""
        self.logger.warning(f"Trade rejected: {reason}")
        return {
            'approved': False,
            'risk_parameters': risk_parameters,
            'reason': reason
        }
