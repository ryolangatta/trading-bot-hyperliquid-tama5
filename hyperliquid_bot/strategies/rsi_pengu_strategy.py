"""
Stochastic RSI Strategy for PENGU
Long only strategy using Stochastic RSI indicator for entry/exit signals
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from risk.fee_calculator import FeeCalculator


@dataclass
class Signal:
    """Trading signal representation"""
    action: str  # 'BUY', 'SELL', 'HOLD'
    price: float
    timestamp: datetime
    stoch_rsi_value: float
    rsi_value: float
    confidence: float
    reason: str


@dataclass
class Candle:
    """OHLCV candle data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class StochasticRSIStrategy:
    """Stochastic RSI Strategy for PENGU token"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Hardcoded symbol and timeframe as per CLAUDE.md specification
        self.symbol = "PENGU"
        self.timeframe = "30m"
        self.rsi_period = 14  # Fixed RSI period
        self.stoch_period = 14  # Fixed Stochastic period
        self.stoch_rsi_oversold = 20  # Oversold threshold
        self.stoch_rsi_overbought = 80  # Overbought threshold
        
        # Risk Management - hardcoded as per CLAUDE.md specification
        self.stop_loss_pct = 0.03  # 3% stop loss
        self.position_risk_pct = 0.02  # 2% of capital per trade
        
        # Fee calculator for trade filtering
        self.fee_calculator = FeeCalculator(config)
        
        # Internal state
        self.candles: List[Candle] = []
        self.rsi_values: List[float] = []
        self.stoch_rsi_values: List[float] = []
        self.current_position = None
        self.last_signal = None
        
        self.logger.info(f"Stochastic RSI PENGU Strategy initialized")
        self.logger.info(f"Symbol: {self.symbol}, Timeframe: {self.timeframe}")
        self.logger.info(f"RSI Period: {self.rsi_period}, Stochastic Period: {self.stoch_period}")
        self.logger.info(f"Stochastic RSI Oversold: {self.stoch_rsi_oversold}, Overbought: {self.stoch_rsi_overbought}")
        self.logger.info(f"Risk Management: Stop Loss={self.stop_loss_pct*100:.1f}%, Position Risk={self.position_risk_pct*100:.1f}% of capital")
        
    def calculate_rsi(self, prices: List[float], period: int = None) -> float:
        """
        Calculate RSI (Relative Strength Index) using Wilder's smoothing method
        
        Args:
            prices: List of closing prices
            period: RSI period (default from config)
            
        Returns:
            RSI value (0-100)
        """
        if period is None:
            period = self.rsi_period
            
        if len(prices) < period + 1:
            return 50.0  # Neutral RSI when insufficient data
            
        prices = np.array(prices)
        deltas = np.diff(prices)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Use Wilder's smoothing (EMA with alpha = 1/period) for proper RSI calculation
        # Initialize with SMA for first calculation
        if not hasattr(self, '_rsi_avg_gains') or len(self.candles) <= period:
            # First calculation uses SMA
            if len(gains) >= period:
                self._rsi_avg_gains = np.mean(gains[-period:])
                self._rsi_avg_losses = np.mean(losses[-period:])
            else:
                return 50.0  # Not enough data
        else:
            # Subsequent calculations use Wilder's smoothing
            alpha = 1.0 / period
            current_gain = gains[-1] if len(gains) > 0 else 0
            current_loss = losses[-1] if len(losses) > 0 else 0
            
            self._rsi_avg_gains = alpha * current_gain + (1 - alpha) * self._rsi_avg_gains
            self._rsi_avg_losses = alpha * current_loss + (1 - alpha) * self._rsi_avg_losses
        
        # Calculate RSI
        if self._rsi_avg_losses == 0:
            return 100.0
            
        rs = self._rsi_avg_gains / self._rsi_avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def calculate_stochastic_rsi(self, rsi_values: List[float], period: int = None) -> float:
        """
        Calculate Stochastic RSI indicator
        
        Args:
            rsi_values: List of RSI values
            period: Stochastic period (default from config)
            
        Returns:
            Stochastic RSI value (0-100)
        """
        if period is None:
            period = self.stoch_period
            
        if len(rsi_values) < period:
            return 50.0  # Neutral when insufficient data
            
        # Get the last 'period' RSI values
        recent_rsi = rsi_values[-period:]
        
        # Calculate the highest and lowest RSI values in the period
        highest_rsi = max(recent_rsi)
        lowest_rsi = min(recent_rsi)
        current_rsi = rsi_values[-1]
        
        # Calculate Stochastic RSI
        if highest_rsi == lowest_rsi:
            # Avoid division by zero
            return 50.0
            
        stoch_rsi = ((current_rsi - lowest_rsi) / (highest_rsi - lowest_rsi)) * 100
        
        return float(stoch_rsi)
        
    def update_candles(self, new_candle: Candle) -> None:
        """Update candle data and calculate indicators"""
        self.candles.append(new_candle)
        
        # Keep only necessary candles for calculations
        max_candles = max(self.rsi_period, self.stoch_period) * 3  # Keep extra for stability
        if len(self.candles) > max_candles:
            self.candles = self.candles[-max_candles:]
            
        # Calculate RSI for current candles
        if len(self.candles) >= self.rsi_period + 1:
            close_prices = [candle.close for candle in self.candles]
            current_rsi = self.calculate_rsi(close_prices)
            self.rsi_values.append(current_rsi)
            
            # Keep RSI values aligned with candles
            if len(self.rsi_values) > len(self.candles):
                self.rsi_values = self.rsi_values[-len(self.candles):]
                
            # Calculate Stochastic RSI if we have enough RSI values
            if len(self.rsi_values) >= self.stoch_period:
                current_stoch_rsi = self.calculate_stochastic_rsi(self.rsi_values)
                self.stoch_rsi_values.append(current_stoch_rsi)
                
                # Keep Stochastic RSI values aligned
                if len(self.stoch_rsi_values) > len(self.rsi_values):
                    self.stoch_rsi_values = self.stoch_rsi_values[-len(self.rsi_values):]
                
        self.logger.debug(f"Updated candles: {len(self.candles)}, RSI values: {len(self.rsi_values)}, Stochastic RSI values: {len(self.stoch_rsi_values)}")
        
    def generate_signal(self) -> Optional[Signal]:
        """
        Generate trading signal based on Stochastic RSI
        
        Returns:
            Signal object or None if no signal
        """
        if len(self.stoch_rsi_values) < 2:
            return None
            
        current_stoch_rsi = self.stoch_rsi_values[-1]
        current_rsi = self.rsi_values[-1] if self.rsi_values else 50.0
        current_price = self.candles[-1].close
        current_time = self.candles[-1].timestamp
        
        # Check stop loss first if we have a position
        if self.current_position and self.should_stop_loss(current_price):
            signal = Signal(
                action='SELL',
                price=current_price,
                timestamp=current_time,
                stoch_rsi_value=current_stoch_rsi,
                rsi_value=current_rsi,
                confidence=1.0,  # High confidence for stop loss
                reason="Stop loss triggered (3% below entry)"
            )
            self.logger.warning(f"STOP LOSS signal generated: Price=${current_price:.4f}")
            self.last_signal = signal
            return signal
        
        # Long only strategy logic - BUY when Stochastic RSI < 20 (oversold)
        if current_stoch_rsi <= self.stoch_rsi_oversold and not self.current_position:
            # Estimate expected gain for fee calculation (5% target for mean reversion)
            expected_gain_pct = 0.05
            expected_exit_price = current_price * (1 + expected_gain_pct)
            
            # Check if trade would be profitable after fees
            # Using a dummy position size of 1000 USD for calculation
            should_execute, fee_calc = self.fee_calculator.should_execute_trade(
                entry_price=current_price,
                expected_exit_price=expected_exit_price,
                position_size=1000.0  # Normalized to 1000 USD
            )
            
            if not should_execute:
                self.logger.warning(f"BUY signal skipped due to fees - Stochastic RSI={current_stoch_rsi:.2f}, Price=${current_price:.4f}")
                return None
                
            # BUY signal when Stochastic RSI < 20 and no position
            signal = Signal(
                action='BUY',
                price=current_price,
                timestamp=current_time,
                stoch_rsi_value=current_stoch_rsi,
                rsi_value=current_rsi,
                confidence=min(1.0, (self.stoch_rsi_oversold - current_stoch_rsi) / 20),  # Higher confidence when more oversold
                reason=f"Stochastic RSI oversold: {current_stoch_rsi:.2f} <= {self.stoch_rsi_oversold}"
            )
            
            self.logger.info(f"BUY signal generated: Stochastic RSI={current_stoch_rsi:.2f}, RSI={current_rsi:.2f}, Price=${current_price:.4f}")
            self.last_signal = signal
            return signal
            
        elif current_stoch_rsi >= self.stoch_rsi_overbought and self.current_position:
            # Calculate actual gain based on entry price
            entry_price = self.current_position.get('entry_price', current_price)
            actual_gain_pct = (current_price - entry_price) / entry_price
            
            # Check if trade would be profitable after fees
            should_execute, fee_calc = self.fee_calculator.should_execute_trade(
                entry_price=entry_price,
                expected_exit_price=current_price,
                position_size=1000.0  # Normalized to 1000 USD
            )
            
            if not should_execute:
                self.logger.warning(f"SELL signal skipped due to fees - Stochastic RSI={current_stoch_rsi:.2f}, Price=${current_price:.4f}, Gain={actual_gain_pct:.2%}")
                return None
                
            # SELL signal when Stochastic RSI > 80 (overbought) and have position
            signal = Signal(
                action='SELL',
                price=current_price,
                timestamp=current_time,
                stoch_rsi_value=current_stoch_rsi,
                rsi_value=current_rsi,
                confidence=min(1.0, (current_stoch_rsi - self.stoch_rsi_overbought) / 20),  # Higher confidence when more overbought
                reason=f"Stochastic RSI overbought: {current_stoch_rsi:.2f} >= {self.stoch_rsi_overbought}"
            )
            
            self.logger.info(f"SELL signal generated: Stochastic RSI={current_stoch_rsi:.2f}, RSI={current_rsi:.2f}, Price=${current_price:.4f}")
            self.last_signal = signal
            return signal
            
        return None
        
    def set_position(self, position: Optional[Dict]) -> None:
        """Update current position status"""
        self.current_position = position
        if position:
            self.logger.info(f"Position updated: {position}")
        else:
            self.logger.info("Position cleared")
            
    def get_current_rsi(self) -> Optional[float]:
        """Get current RSI value"""
        return self.rsi_values[-1] if self.rsi_values else None
        
    def get_current_stoch_rsi(self) -> Optional[float]:
        """Get current Stochastic RSI value"""
        return self.stoch_rsi_values[-1] if self.stoch_rsi_values else None
        
    def get_strategy_status(self) -> Dict:
        """Get current strategy status"""
        return {
            'strategy_name': 'STOCHASTIC_RSI_PENGU',
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'current_rsi': self.get_current_rsi(),
            'current_stoch_rsi': self.get_current_stoch_rsi(),
            'stoch_rsi_oversold': self.stoch_rsi_oversold,
            'stoch_rsi_overbought': self.stoch_rsi_overbought,
            'candles_count': len(self.candles),
            'has_position': self.current_position is not None,
            'last_signal': {
                'action': self.last_signal.action,
                'price': self.last_signal.price,
                'timestamp': self.last_signal.timestamp.isoformat(),
                'stoch_rsi_value': self.last_signal.stoch_rsi_value,
                'rsi_value': self.last_signal.rsi_value
            } if self.last_signal else None
        }
        
    def should_stop_loss(self, current_price: float) -> bool:
        """
        Check if stop loss should be triggered
        
        Args:
            current_price: Current market price
            
        Returns:
            True if stop loss should be triggered
        """
        if not self.current_position:
            return False
            
        entry_price = self.current_position.get('entry_price', 0)
        if entry_price <= 0:
            return False
            
        # Calculate stop loss price using hardcoded percentage
        stop_loss_price = entry_price * (1 - self.stop_loss_pct)
        
        if current_price <= stop_loss_price:
            self.logger.warning(f"Stop loss triggered: Current={current_price:.4f}, Stop={stop_loss_price:.4f} (3% below entry)")
            return True
            
        return False
        
    def calculate_position_size(self, capital: float, current_price: float) -> float:
        """
        Calculate position size based on configured sizing method (dollar amount or percentage)
        
        Args:
            capital: Total account capital
            current_price: Current market price
            
        Returns:
            Position size (quantity) to trade
        """
        # Input validation to prevent crashes
        if capital <= 0:
            self.logger.error(f"Invalid capital for position sizing: {capital}")
            return 0.0
            
        if current_price <= 0:
            self.logger.error(f"Invalid price for position sizing: {current_price}")
            return 0.0
        
        try:
            # Determine sizing method: dollar amount takes priority over percentage
            if self.config.position_size_usd is not None:
                # Use fixed dollar amount
                risk_amount = self.config.position_size_usd
                self.logger.info(f"Using fixed dollar amount: ${risk_amount:.2f}")
                
                # Validate dollar amount is reasonable
                if risk_amount <= 0:
                    self.logger.error(f"Invalid dollar amount: ${risk_amount:.2f}")
                    return 0.0
                    
                if risk_amount > capital * 0.5:  # Don't risk more than 50% of capital
                    self.logger.warning(f"Dollar amount ${risk_amount:.2f} exceeds 50% of capital ${capital:.2f}")
                    risk_amount = capital * 0.5
                    
            else:
                # Use percentage-based sizing (original method)
                if self.position_risk_pct <= 0 or self.position_risk_pct > 1:
                    self.logger.error(f"Invalid position risk percentage: {self.position_risk_pct}")
                    return 0.0
                    
                risk_amount = capital * self.position_risk_pct
                self.logger.info(f"Using percentage-based sizing: {self.position_risk_pct:.1%} of ${capital:.2f} = ${risk_amount:.2f}")
            
            # Ensure minimum trade size
            if risk_amount < 1.0:  # Minimum $1 risk
                self.logger.warning(f"Risk amount too small: ${risk_amount:.2f}, minimum $1 required")
                return 0.0
            
            # Calculate quantity with proper precision for crypto
            quantity = risk_amount / current_price
            
            # Round to appropriate precision (6 decimal places for crypto)
            quantity = round(quantity, 6)
            
            # Ensure minimum quantity
            if quantity < 0.000001:  # Minimum viable quantity
                self.logger.warning(f"Calculated quantity too small: {quantity}")
                return 0.0
            
            self.logger.info(f"Position sizing: Capital=${capital:.2f}, Risk=${risk_amount:.2f}, Price=${current_price:.6f}, Quantity={quantity}")
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error in position size calculation: {e}")
            return 0.0
    
    def validate_signal(self, signal: Signal) -> bool:
        """
        Validate signal before execution
        
        Args:
            signal: Signal to validate
            
        Returns:
            True if signal is valid
        """
        if not signal:
            return False
            
        # Check signal age (should be recent)
        signal_age = datetime.now() - signal.timestamp
        if signal_age.total_seconds() > 300:  # 5 minutes max
            self.logger.warning(f"Signal too old: {signal_age.total_seconds():.0f}s")
            return False
            
        # Check confidence threshold
        if signal.confidence < 0.3:  # Minimum 30% confidence
            self.logger.warning(f"Signal confidence too low: {signal.confidence:.2f}")
            return False
            
        return True