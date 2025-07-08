"""
Fee calculator for Hyperliquid Trading Bot
Calculates trading fees and filters unprofitable trades
No trade should execute if net expected gain is negative
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal, getcontext, ROUND_HALF_UP


@dataclass
class FeeCalculation:
    """Results of fee calculation"""
    entry_fee: float
    exit_fee: float
    total_fee: float
    net_profit: float
    is_profitable: bool
    fee_ratio: float


class FeeCalculator:
    """Calculates trading fees and determines trade profitability with high precision"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Set decimal precision for financial calculations (8 decimal places)
        getcontext().prec = 28
        getcontext().rounding = ROUND_HALF_UP
        
        # Hardcoded Hyperliquid fee rates (as per specification) - use Decimal for precision
        self.maker_fee_rate = Decimal(str(config.maker_fee_rate))  # 0.02%
        self.taker_fee_rate = Decimal(str(config.taker_fee_rate))  # 0.05%
        
        self.logger.info(f"Fee Calculator initialized with high precision - Maker: {self.maker_fee_rate}%, Taker: {self.taker_fee_rate}%")
        
    def calculate_trade_fees(self, 
                           entry_price: float, 
                           exit_price: float, 
                           position_size: float,
                           is_entry_maker: bool = True,
                           is_exit_maker: bool = False) -> FeeCalculation:
        """
        Calculate total fees for a complete trade (entry + exit) with high precision
        
        Args:
            entry_price: Price at which position is entered
            exit_price: Price at which position is exited
            position_size: Size of the position in USD
            is_entry_maker: Whether entry order is maker (True) or taker (False)
            is_exit_maker: Whether exit order is maker (True) or taker (False)
            
        Returns:
            FeeCalculation object with detailed fee breakdown
        """
        # Convert inputs to Decimal for precise calculations
        entry_price_d = Decimal(str(entry_price))
        exit_price_d = Decimal(str(exit_price))
        position_size_d = Decimal(str(position_size))
        
        # Input validation for precision issues
        if entry_price_d <= 0:
            raise ValueError(f"Invalid entry price: {entry_price}")
        if exit_price_d <= 0:
            raise ValueError(f"Invalid exit price: {exit_price}")
        if position_size_d <= 0:
            raise ValueError(f"Invalid position size: {position_size}")
        
        # Calculate entry fee with precise arithmetic
        entry_fee_rate = self.maker_fee_rate if is_entry_maker else self.taker_fee_rate
        entry_fee_d = position_size_d * entry_fee_rate
        
        # Calculate exit fee with precise arithmetic
        exit_fee_rate = self.maker_fee_rate if is_exit_maker else self.taker_fee_rate
        exit_fee_d = position_size_d * exit_fee_rate
        
        # Total fees
        total_fee_d = entry_fee_d + exit_fee_d
        
        # Calculate gross profit/loss with precise arithmetic
        price_diff = exit_price_d - entry_price_d
        gross_profit_d = (price_diff / entry_price_d) * position_size_d
        
        # Calculate net profit after fees
        net_profit_d = gross_profit_d - total_fee_d
        
        # Determine if trade is profitable - filter trades where expected return < fees
        is_profitable = net_profit_d > 0
        
        # Calculate fee ratio (fees as percentage of position size)
        fee_ratio_d = total_fee_d / position_size_d
        
        # Convert back to float for compatibility, with proper rounding
        return FeeCalculation(
            entry_fee=float(entry_fee_d.quantize(Decimal('0.00000001'))),
            exit_fee=float(exit_fee_d.quantize(Decimal('0.00000001'))),
            total_fee=float(total_fee_d.quantize(Decimal('0.00000001'))),
            net_profit=float(net_profit_d.quantize(Decimal('0.00000001'))),
            is_profitable=is_profitable,
            fee_ratio=float(fee_ratio_d.quantize(Decimal('0.00000001')))
        )
        
    def should_execute_trade(self, 
                           entry_price: float, 
                           expected_exit_price: float, 
                           position_size: float,
                           min_profit_threshold: float = 0.001) -> Tuple[bool, FeeCalculation]:
        """
        Determine if a trade should be executed based on expected profitability with high precision
        
        Args:
            entry_price: Intended entry price
            expected_exit_price: Expected exit price based on strategy
            position_size: Position size in USD
            min_profit_threshold: Minimum profit threshold (default 0.1%)
            
        Returns:
            Tuple of (should_execute, fee_calculation)
        """
        try:
            # Assume entry is maker (limit order) and exit is taker (market order)
            # This is conservative - actual fees might be lower
            fee_calc = self.calculate_trade_fees(
                entry_price=entry_price,
                exit_price=expected_exit_price,
                position_size=position_size,
                is_entry_maker=True,
                is_exit_maker=False
            )
            
            # Use Decimal for precise threshold comparison
            position_size_d = Decimal(str(position_size))
            net_profit_d = Decimal(str(fee_calc.net_profit))
            min_threshold_d = Decimal(str(min_profit_threshold))
            
            # Check if trade meets minimum profit threshold
            profit_ratio_d = net_profit_d / position_size_d
            should_execute = profit_ratio_d >= min_threshold_d
            
            # Convert to float for logging
            profit_ratio = float(profit_ratio_d.quantize(Decimal('0.000001')))
            
            if not should_execute:
                self.logger.warning(
                    f"Trade filtered out - Expected return < fees: Expected profit: {profit_ratio:.6f}%, "
                    f"Fees: {fee_calc.fee_ratio:.6f}%, "
                    f"Net profit: ${fee_calc.net_profit:.6f}"
                )
            else:
                self.logger.info(
                    f"Trade approved - Expected profit: {profit_ratio:.6f}%, "
                    f"Fees: {fee_calc.fee_ratio:.6f}%, "
                    f"Net profit: ${fee_calc.net_profit:.6f}"
                )
                
            return should_execute, fee_calc
            
        except (ValueError, ZeroDivisionError) as e:
            self.logger.error(f"Error in trade execution check: {e}")
            return False, FeeCalculation(0, 0, 0, 0, False, 0)
        
    def estimate_minimum_price_move(self, position_size: float) -> float:
        """
        Estimate minimum price move required to break even on fees with high precision
        
        Args:
            position_size: Position size in USD
            
        Returns:
            Minimum price move percentage required to break even
        """
        # Assume worst case: both entry and exit are taker orders
        total_fee_rate_d = self.taker_fee_rate * Decimal('2')
        
        # Minimum price move needed to cover fees
        min_move_percentage = float(total_fee_rate_d.quantize(Decimal('0.000001')))
        
        self.logger.debug(f"Minimum price move to break even: {min_move_percentage:.6f}%")
        
        return min_move_percentage
        
    def get_fee_summary(self) -> Dict[str, float]:
        """Get current fee rates summary with high precision"""
        return {
            'maker_fee_rate': float(self.maker_fee_rate.quantize(Decimal('0.000001'))),
            'taker_fee_rate': float(self.taker_fee_rate.quantize(Decimal('0.000001'))),
            'worst_case_round_trip': float((self.taker_fee_rate * Decimal('2')).quantize(Decimal('0.000001'))),
            'best_case_round_trip': float((self.maker_fee_rate * Decimal('2')).quantize(Decimal('0.000001')))
        }