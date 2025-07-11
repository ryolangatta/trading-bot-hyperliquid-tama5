"""
MACD Strategy for ARB
Long/Short strategy using MACD crossover signals with histogram confirmation
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from risk.fee_calculator import FeeCalculator
from data_types import Candle, Signal


class MACDStrategy:
    """MACD Strategy for ARB token"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Hardcoded symbol and timeframe as per CLAUDE.md specification
        self.symbol = "ARB"
        self.timeframe = "1h"
        
        # MACD Parameters (12, 26, 9)
        self.fast_period = 12
        self.slow_period = 26
        self.signal_period = 9
        
        # Risk Management - optimized from backtesting
        self.take_profit_pct = 0.02  # 2% take profit
        self.stop_loss_pct = 0.01    # 1% stop loss
        self.max_hold_hours = 24     # Maximum position hold time
        
        # Fee calculator for trade filtering
        self.fee_calculator = FeeCalculator(config)
        
        # Internal state
        self.candles: List[Candle] = []
        self.ema_fast: List[float] = []
        self.ema_slow: List[float] = []
        self.macd_line: List[float] = []
        self.signal_line: List[float] = []
        self.histogram: List[float] = []
        self.current_position = None
        self.last_signal = None
        self.position_entry_time = None
        
        # EMA smoothing factors
        self.alpha_fast = 2.0 / (self.fast_period + 1)
        self.alpha_slow = 2.0 / (self.slow_period + 1)
        self.alpha_signal = 2.0 / (self.signal_period + 1)
        
        self.logger.info(f"MACD ARB Strategy initialized")
        self.logger.info(f"Symbol: {self.symbol}, Timeframe: {self.timeframe}")
        self.logger.info(f"MACD Parameters: Fast={self.fast_period}, Slow={self.slow_period}, Signal={self.signal_period}")
        self.logger.info(f"Risk Management: SL={self.stop_loss_pct*100:.1f}%, TP={self.take_profit_pct*100:.1f}%")
        
    def calculate_ema(self, prices: List[float], period: int, alpha: float = None) -> float:
        """
        Calculate Exponential Moving Average
        
        Args:
            prices: List of prices
            period: EMA period
            alpha: Smoothing factor (optional)
            
        Returns:
            Current EMA value
        """
        if alpha is None:
            alpha = 2.0 / (period + 1)
            
        if len(prices) < period:
            return np.mean(prices) if prices else 0.0
            
        # Initialize with SMA for first calculation
        if len(prices) == period:
            return np.mean(prices)
            
        # Use previous EMA for calculation
        previous_ema = self.ema_fast[-1] if period == self.fast_period and self.ema_fast else \
                      self.ema_slow[-1] if period == self.slow_period and self.ema_slow else \
                      self.signal_line[-1] if period == self.signal_period and self.signal_line else \
                      np.mean(prices[-period:])
        
        current_price = prices[-1]
        return alpha * current_price + (1 - alpha) * previous_ema
        
    def update_candles(self, new_candle: Candle) -> None:
        """Update candle data and calculate MACD indicators"""
        self.candles.append(new_candle)
        
        # Keep only necessary candles for calculations
        max_candles = max(self.slow_period, self.signal_period) * 3
        if len(self.candles) > max_candles:
            self.candles = self.candles[-max_candles:]
            
        # Calculate EMAs and MACD
        if len(self.candles) >= self.slow_period:
            close_prices = [candle.close for candle in self.candles]
            
            # Calculate Fast EMA (12)
            fast_ema = self.calculate_ema(close_prices, self.fast_period, self.alpha_fast)
            self.ema_fast.append(fast_ema)
            
            # Calculate Slow EMA (26)
            slow_ema = self.calculate_ema(close_prices, self.slow_period, self.alpha_slow)
            self.ema_slow.append(slow_ema)
            
            # Calculate MACD Line (Fast EMA - Slow EMA)
            macd_value = fast_ema - slow_ema
            self.macd_line.append(macd_value)
            
            # Calculate Signal Line (EMA of MACD)
            if len(self.macd_line) >= self.signal_period:
                signal_value = self.calculate_ema(self.macd_line, self.signal_period, self.alpha_signal)
                self.signal_line.append(signal_value)
                
                # Calculate Histogram (MACD - Signal)
                histogram_value = macd_value - signal_value
                self.histogram.append(histogram_value)
                
                # Keep arrays aligned
                if len(self.histogram) > len(self.signal_line):
                    self.histogram = self.histogram[-len(self.signal_line):]
                    
            # Keep arrays aligned with reasonable size
            max_values = max_candles
            if len(self.ema_fast) > max_values:
                self.ema_fast = self.ema_fast[-max_values:]
            if len(self.ema_slow) > max_values:
                self.ema_slow = self.ema_slow[-max_values:]
            if len(self.macd_line) > max_values:
                self.macd_line = self.macd_line[-max_values:]
            if len(self.signal_line) > max_values:
                self.signal_line = self.signal_line[-max_values:]
            if len(self.histogram) > max_values:
                self.histogram = self.histogram[-max_values:]
                
        self.logger.debug(f"Updated candles: {len(self.candles)}, MACD values: {len(self.macd_line)}, Signal values: {len(self.signal_line)}")
        
    def generate_signal(self) -> Optional[Signal]:
        """
        Generate trading signal based on MACD crossover
        
        Returns:
            Signal object or None if no signal
        """
        if len(self.macd_line) < 2 or len(self.signal_line) < 2 or len(self.histogram) < 2:
            return None
            
        current_macd = self.macd_line[-1]
        previous_macd = self.macd_line[-2]
        current_signal = self.signal_line[-1]
        previous_signal = self.signal_line[-2]
        current_histogram = self.histogram[-1]
        previous_histogram = self.histogram[-2]
        
        current_price = self.candles[-1].close
        current_time = self.candles[-1].timestamp
        
        # Check stop loss and take profit first if we have a position
        if self.current_position:
            if self.should_stop_loss(current_price):
                signal = Signal(
                    action='SELL' if self.current_position.get('side') == 'long' else 'BUY',
                    price=current_price,
                    timestamp=current_time,
                    macd_value=current_macd,
                    signal_value=current_signal,
                    histogram_value=current_histogram,
                    confidence=1.0,
                    reason="Stop loss triggered (1% loss)"
                )
                self.logger.warning(f"STOP LOSS signal generated: Price=${current_price:.4f}")
                self.last_signal = signal
                return signal
                
            if self.should_take_profit(current_price):
                signal = Signal(
                    action='SELL' if self.current_position.get('side') == 'long' else 'BUY',
                    price=current_price,
                    timestamp=current_time,
                    macd_value=current_macd,
                    signal_value=current_signal,
                    histogram_value=current_histogram,
                    confidence=1.0,
                    reason="Take profit triggered (2% gain)"
                )
                self.logger.info(f"TAKE PROFIT signal generated: Price=${current_price:.4f}")
                self.last_signal = signal
                return signal
                
            # Check maximum hold time
            if self.should_exit_on_time():
                signal = Signal(
                    action='SELL' if self.current_position.get('side') == 'long' else 'BUY',
                    price=current_price,
                    timestamp=current_time,
                    macd_value=current_macd,
                    signal_value=current_signal,
                    histogram_value=current_histogram,
                    confidence=0.8,
                    reason="Maximum hold time reached (24h)"
                )
                self.logger.info(f"TIME EXIT signal generated: Price=${current_price:.4f}")
                self.last_signal = signal
                return signal
        
        # MACD Crossover Logic
        
        # Long Entry: MACD crosses above Signal AND histogram turns positive
        if (previous_macd <= previous_signal and current_macd > current_signal and 
            current_histogram > 0 and not self.current_position):
            
            # Additional confirmation: MACD line moving away from zero
            if current_macd > previous_macd:
                # Check if trade would be profitable after fees
                expected_exit_price = current_price * (1 + self.take_profit_pct)
                should_execute, fee_calc = self.fee_calculator.should_execute_trade(
                    entry_price=current_price,
                    expected_exit_price=expected_exit_price,
                    position_size=1000.0
                )
                
                if not should_execute:
                    self.logger.warning(f"LONG signal skipped due to fees - MACD={current_macd:.6f}, Price=${current_price:.4f}")
                    return None
                    
                signal = Signal(
                    action='BUY',
                    price=current_price,
                    timestamp=current_time,
                    macd_value=current_macd,
                    signal_value=current_signal,
                    histogram_value=current_histogram,
                    confidence=min(1.0, abs(current_histogram) / 0.001),  # Higher confidence with stronger histogram
                    reason=f"MACD bullish crossover: MACD={current_macd:.6f} > Signal={current_signal:.6f}, Histogram={current_histogram:.6f}"
                )
                
                self.logger.info(f"LONG signal generated: MACD={current_macd:.6f}, Signal={current_signal:.6f}, Histogram={current_histogram:.6f}, Price=${current_price:.4f}")
                self.last_signal = signal
                return signal
        
        # Short Entry: MACD crosses below Signal AND histogram turns negative
        elif (previous_macd >= previous_signal and current_macd < current_signal and 
              current_histogram < 0 and not self.current_position):
            
            # Additional confirmation: MACD line moving away from zero
            if current_macd < previous_macd:
                # Check if trade would be profitable after fees
                expected_exit_price = current_price * (1 - self.take_profit_pct)
                should_execute, fee_calc = self.fee_calculator.should_execute_trade(
                    entry_price=current_price,
                    expected_exit_price=expected_exit_price,
                    position_size=1000.0
                )
                
                if not should_execute:
                    self.logger.warning(f"SHORT signal skipped due to fees - MACD={current_macd:.6f}, Price=${current_price:.4f}")
                    return None
                    
                signal = Signal(
                    action='SELL',
                    price=current_price,
                    timestamp=current_time,
                    macd_value=current_macd,
                    signal_value=current_signal,
                    histogram_value=current_histogram,
                    confidence=min(1.0, abs(current_histogram) / 0.001),  # Higher confidence with stronger histogram
                    reason=f"MACD bearish crossover: MACD={current_macd:.6f} < Signal={current_signal:.6f}, Histogram={current_histogram:.6f}"
                )
                
                self.logger.info(f"SHORT signal generated: MACD={current_macd:.6f}, Signal={current_signal:.6f}, Histogram={current_histogram:.6f}, Price=${current_price:.4f}")
                self.last_signal = signal
                return signal
        
        # Exit signals for existing positions
        elif self.current_position:
            position_side = self.current_position.get('side')
            
            # Exit long position: MACD crosses below Signal
            if (position_side == 'long' and previous_macd >= previous_signal and 
                current_macd < current_signal):
                
                signal = Signal(
                    action='SELL',
                    price=current_price,
                    timestamp=current_time,
                    macd_value=current_macd,
                    signal_value=current_signal,
                    histogram_value=current_histogram,
                    confidence=0.8,
                    reason=f"MACD bearish crossover (exit long): MACD={current_macd:.6f} < Signal={current_signal:.6f}"
                )
                
                self.logger.info(f"EXIT LONG signal generated: MACD={current_macd:.6f}, Signal={current_signal:.6f}, Price=${current_price:.4f}")
                self.last_signal = signal
                return signal
            
            # Exit short position: MACD crosses above Signal
            elif (position_side == 'short' and previous_macd <= previous_signal and 
                  current_macd > current_signal):
                
                signal = Signal(
                    action='BUY',
                    price=current_price,
                    timestamp=current_time,
                    macd_value=current_macd,
                    signal_value=current_signal,
                    histogram_value=current_histogram,
                    confidence=0.8,
                    reason=f"MACD bullish crossover (exit short): MACD={current_macd:.6f} > Signal={current_signal:.6f}"
                )
                
                self.logger.info(f"EXIT SHORT signal generated: MACD={current_macd:.6f}, Signal={current_signal:.6f}, Price=${current_price:.4f}")
                self.last_signal = signal
                return signal
        
        return None
        
    def set_position(self, position: Optional[Dict]) -> None:
        """Update current position status"""
        self.current_position = position
        if position:
            self.position_entry_time = datetime.now()
            self.logger.info(f"Position updated: {position}")
        else:
            self.position_entry_time = None
            self.logger.info("Position cleared")
            
    def get_current_macd(self) -> Optional[float]:
        """Get current MACD value"""
        return self.macd_line[-1] if self.macd_line else None
        
    def get_current_signal(self) -> Optional[float]:
        """Get current Signal line value"""
        return self.signal_line[-1] if self.signal_line else None
        
    def get_current_histogram(self) -> Optional[float]:
        """Get current Histogram value"""
        return self.histogram[-1] if self.histogram else None
        
    def get_strategy_status(self) -> Dict:
        """Get current strategy status"""
        return {
            'strategy_name': 'MACD_ARB',
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'current_macd': self.get_current_macd(),
            'current_signal': self.get_current_signal(),
            'current_histogram': self.get_current_histogram(),
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
            'signal_period': self.signal_period,
            'candles_count': len(self.candles),
            'has_position': self.current_position is not None,
            'position_side': self.current_position.get('side') if self.current_position else None,
            'last_signal': {
                'action': self.last_signal.action,
                'price': self.last_signal.price,
                'timestamp': self.last_signal.timestamp.isoformat(),
                'macd_value': self.last_signal.macd_value,
                'signal_value': self.last_signal.signal_value,
                'histogram_value': self.last_signal.histogram_value
            } if self.last_signal else None
        }
        
    def should_stop_loss(self, current_price: float) -> bool:
        """Check if stop loss should be triggered"""
        if not self.current_position:
            return False
            
        entry_price = self.current_position.get('entry_price', 0)
        position_side = self.current_position.get('side')
        
        if entry_price <= 0:
            return False
            
        if position_side == 'long':
            stop_loss_price = entry_price * (1 - self.stop_loss_pct)
            if current_price <= stop_loss_price:
                self.logger.warning(f"Long stop loss triggered: Current={current_price:.4f}, Stop={stop_loss_price:.4f}")
                return True
        elif position_side == 'short':
            stop_loss_price = entry_price * (1 + self.stop_loss_pct)
            if current_price >= stop_loss_price:
                self.logger.warning(f"Short stop loss triggered: Current={current_price:.4f}, Stop={stop_loss_price:.4f}")
                return True
                
        return False
        
    def should_take_profit(self, current_price: float) -> bool:
        """Check if take profit should be triggered"""
        if not self.current_position:
            return False
            
        entry_price = self.current_position.get('entry_price', 0)
        position_side = self.current_position.get('side')
        
        if entry_price <= 0:
            return False
            
        if position_side == 'long':
            take_profit_price = entry_price * (1 + self.take_profit_pct)
            if current_price >= take_profit_price:
                self.logger.info(f"Long take profit triggered: Current={current_price:.4f}, Target={take_profit_price:.4f}")
                return True
        elif position_side == 'short':
            take_profit_price = entry_price * (1 - self.take_profit_pct)
            if current_price <= take_profit_price:
                self.logger.info(f"Short take profit triggered: Current={current_price:.4f}, Target={take_profit_price:.4f}")
                return True
                
        return False
        
    def should_exit_on_time(self) -> bool:
        """Check if position should be exited due to time limit"""
        if not self.current_position or not self.position_entry_time:
            return False
            
        time_held = datetime.now() - self.position_entry_time
        if time_held.total_seconds() > self.max_hold_hours * 3600:
            self.logger.info(f"Position held for {time_held.total_seconds()/3600:.1f} hours, exiting")
            return True
            
        return False
        
    def calculate_position_size(self, capital: float, current_price: float) -> float:
        """
        Calculate position size based on configured sizing method
        
        Args:
            capital: Total account capital
            current_price: Current market price
            
        Returns:
            Position size (quantity) to trade
        """
        if capital <= 0 or current_price <= 0:
            self.logger.error(f"Invalid parameters: capital={capital}, price={current_price}")
            return 0.0
        
        try:
            # Use dollar amount if configured, otherwise use percentage
            if hasattr(self.config, 'position_size_usd') and self.config.position_size_usd is not None:
                risk_amount = self.config.position_size_usd
                self.logger.info(f"Using fixed dollar amount: ${risk_amount:.2f}")
                
                if risk_amount <= 0:
                    return 0.0
                    
                if risk_amount > capital * 0.5:
                    risk_amount = capital * 0.5
                    self.logger.warning(f"Risk amount capped at 50% of capital: ${risk_amount:.2f}")
                    
            else:
                # Default to 2% of capital per trade
                risk_pct = getattr(self.config, 'position_size_percent', 0.02)
                risk_amount = capital * risk_pct
                self.logger.info(f"Using percentage-based sizing: {risk_pct:.1%} of ${capital:.2f} = ${risk_amount:.2f}")
            
            # Calculate quantity
            quantity = risk_amount / current_price
            quantity = round(quantity, 6)
            
            if quantity < 0.000001:
                self.logger.warning(f"Calculated quantity too small: {quantity}")
                return 0.0
            
            self.logger.info(f"Position sizing: Capital=${capital:.2f}, Risk=${risk_amount:.2f}, Price=${current_price:.6f}, Quantity={quantity}")
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error in position size calculation: {e}")
            return 0.0
    
    def validate_signal(self, signal: Signal) -> bool:
        """Validate signal before execution"""
        if not signal:
            return False
            
        # Check signal age
        signal_age = datetime.now() - signal.timestamp
        if signal_age.total_seconds() > 300:  # 5 minutes max
            self.logger.warning(f"Signal too old: {signal_age.total_seconds():.0f}s")
            return False
            
        # Check confidence threshold
        if signal.confidence < 0.3:
            self.logger.warning(f"Signal confidence too low: {signal.confidence:.2f}")
            return False
            
        return True