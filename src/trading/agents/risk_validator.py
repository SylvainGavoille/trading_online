import logging
from typing import Dict, Any, Optional
from datetime import datetime, UTC, timedelta
from collections import defaultdict
from src.trading.fee_calculator import FeeCalculator

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

        # Initialize fee calculator
        self.fee_calculator = FeeCalculator(config)

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

            # Max Drawdown Check
            drawdown_check = self._check_max_drawdown(portfolio)
            if not drawdown_check['approved']:
                return self._create_rejection_response(risk_parameters, drawdown_check['reason'])

            # Trade Frequency Check
            frequency_check = self._check_trade_frequency(trade_params['symbol'])
            if not frequency_check['approved']:
                return self._create_rejection_response(risk_parameters, frequency_check['reason'])
            
            # NOTE: la fréquence de trading n'est PLUS enregistrée ici. Valider un
            # trade ne signifie pas qu'il sera exécuté ; enregistrer la fréquence
            # avant l'exécution gonfle artificiellement le compteur et peut bloquer
            # des trades légitimes. L'appelant doit invoquer record_trade(symbol)
            # uniquement après confirmation du fill (cf. trading_engine_lite).

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
    
    def record_trade(self, symbol: str) -> None:
        """
        Enregistre un trade exécuté pour le suivi de fréquence.

        À appeler UNIQUEMENT après confirmation du fill, jamais à la validation.
        """
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
    
    def _is_short_trade(self, trade_params: Dict[str, Any]) -> bool:
        """
        Determine whether the trade is a short (SELL) position.

        Le sens du trade est lu depuis 'action' (BUY/SELL, fourni par
        trading_engine_lite) ou, à défaut, depuis 'order_type'. Si aucun n'est
        fourni, on suppose un trade long (BUY) par défaut.
        """
        direction = (trade_params.get('action') or '').strip().upper()
        if direction in ('BUY', 'LONG'):
            return False
        if direction in ('SELL', 'SHORT'):
            return True

        order_type = (trade_params.get('order_type') or '').strip().upper()
        if order_type in ('SELL', 'SHORT'):
            return True
        return False

    def _check_stop_loss(self, trade_params: Dict[str, Any],
                        portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Validate stop loss levels (side-aware)"""
        current_price = trade_params['price']
        stop_loss = trade_params['stop_loss']
        position_size = trade_params['size']
        is_short = self._is_short_trade(trade_params)

        # Valider le sens du stop : sous le prix pour un BUY, au-dessus pour un SELL
        if is_short and stop_loss <= current_price:
            return {
                'approved': False,
                'reason': 'Invalid stop loss level: for a SELL, stop must be above entry price'
            }
        if not is_short and stop_loss >= current_price:
            return {
                'approved': False,
                'reason': 'Invalid stop loss level: for a BUY, stop must be below entry price'
            }

        # Perte potentielle = magnitude de l'écart au stop (valable long et short)
        risk_per_share = abs(current_price - stop_loss)
        potential_loss = risk_per_share * position_size
        max_loss_amount = portfolio['total_value'] * self.risk_config['stop_loss']['max_loss_per_trade']

        if potential_loss <= max_loss_amount:
            return {'approved': True}
        return {
            'approved': False,
            'reason': f'Potential loss ${potential_loss:.2f} exceeds maximum allowed loss of ${max_loss_amount:.2f}'
        }

    def _check_risk_reward_ratio(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate risk/reward ratio (including fees, side-aware)"""
        current_price = trade_params['price']
        stop_loss = trade_params['stop_loss']
        target_price = trade_params['target_price']
        position_size = trade_params['size']
        is_short = self._is_short_trade(trade_params)

        # Valider le sens du stop avant de calculer le ratio
        if is_short and stop_loss <= current_price:
            return {
                'approved': False,
                'reason': 'Invalid stop loss level: for a SELL, stop must be above entry price'
            }
        if not is_short and stop_loss >= current_price:
            return {
                'approved': False,
                'reason': 'Invalid stop loss level: for a BUY, stop must be below entry price'
            }

        # Risque et reward par action en magnitude (valable long et short)
        risk_per_share = abs(current_price - stop_loss)
        reward_per_share = abs(target_price - current_price)
        potential_loss_gross = risk_per_share * position_size
        potential_reward_gross = reward_per_share * position_size

        if potential_loss_gross <= 0:
            return {
                'approved': False,
                'reason': 'Invalid stop loss level'
            }

        # Calculate fees for round trip
        fees = self.fee_calculator.calculate_round_trip_fees(
            position_size,
            current_price,
            target_price
        )
        total_fees = fees['total_round_trip_fees']

        # Net profit/loss (after fees)
        potential_loss_net = potential_loss_gross + total_fees
        potential_reward_net = potential_reward_gross - total_fees

        # Risk/reward ratio (net)
        risk_reward_ratio_net = potential_reward_net / potential_loss_net
        min_ratio = self.risk_config.get('risk_reward', {}).get('min_ratio', 2.0)

        self.logger.debug(
            f"Risk/Reward - Gross: {potential_reward_gross / potential_loss_gross:.2f}, "
            f"Net (after fees): {risk_reward_ratio_net:.2f}, "
            f"Fees: ${total_fees:.2f}"
        )

        if risk_reward_ratio_net >= min_ratio:
            return {'approved': True}
        return {
            'approved': False,
            'reason': (
                f'Risk/reward ratio {risk_reward_ratio_net:.2f} (after ${total_fees:.2f} fees) '
                f'is below minimum threshold of {min_ratio}'
            )
        }
    
    def _check_daily_loss_limit(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Check if within daily loss limits"""
        # La convention de signe de 'daily_loss' est ambiguë selon la source
        # (perte positive ou P&L négatif). On normalise en magnitude : seules les
        # pertes comptent, et on les compare à la magnitude de la limite.
        daily_loss = abs(portfolio.get('daily_loss', 0))
        daily_loss_limit = abs(self.risk_config['loss_limits']['daily_loss_limit'])

        if daily_loss <= daily_loss_limit:
            return {'approved': True}
        return {
            'approved': False,
            'reason': f'Daily loss ${daily_loss:.2f} exceeds limit of ${daily_loss_limit:.2f}'
        }

    def _check_max_drawdown(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Check if within maximum drawdown limits"""
        peak_value = portfolio.get('peak_value', portfolio.get('total_value', 0))
        current_value = portfolio.get('total_value', 0)

        if peak_value <= 0:
            return {
                'approved': False,
                'reason': 'Invalid portfolio peak value'
            }

        # Calculate current drawdown
        drawdown = (peak_value - current_value) / peak_value
        max_drawdown = self.risk_config['loss_limits']['max_drawdown']

        if drawdown <= max_drawdown:
            return {'approved': True}
        return {
            'approved': False,
            'reason': f'Current drawdown {drawdown:.2%} exceeds maximum allowed {max_drawdown:.2%}'
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
