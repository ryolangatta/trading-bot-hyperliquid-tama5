#!/usr/bin/env python3
"""Manual signal injection for testing bot order execution"""

import asyncio
import logging
import sys
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from config import Config
from bot_orchestrator import BotOrchestrator
from utils.logger import setup_logger

@dataclass
class ManualSignal:
    """Manual trading signal"""
    signal_type: str  # 'BUY' or 'SELL'
    symbol: str
    price: float
    timestamp: datetime
    confidence: float = 1.0
    reason: str = "Manual signal"

class ManualSignalInjector:
    """Inject manual trading signals into the bot"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.bot = None
        
    async def initialize(self):
        """Initialize the bot orchestrator"""
        self.logger.info("Initializing bot orchestrator...")
        
        # Initialize error monitor
        from utils.error_monitor import ErrorMonitor
        error_monitor = ErrorMonitor(self.config)
        
        self.bot = BotOrchestrator(self.config, self.config.strategy_name, error_monitor)
        await self.bot.initialize()
        self.logger.info("Bot orchestrator ready for manual signals")
        
    async def send_buy_signal(self, price: Optional[float] = None, reason: str = "Manual BUY"):
        """Send a manual BUY signal"""
        if not self.bot:
            raise RuntimeError("Bot not initialized")
            
        # Get current price if not provided or if price is 0 (market order)
        if price is None or price == 0:
            market_data = await self.bot.hyperliquid_client.get_market_data(self.config.symbol)
            price = market_data.price
            self.logger.info(f"Using current market price: ${price:.4f}")
        
        signal = ManualSignal(
            signal_type='BUY',
            symbol=self.config.symbol,
            price=price,
            timestamp=datetime.now(),
            reason=reason
        )
        
        self.logger.info(f"🟢 MANUAL BUY SIGNAL: {signal.symbol} @ ${signal.price:.4f}")
        self.logger.info(f"Reason: {signal.reason}")
        
        # Execute the signal through bot's buy logic
        await self._execute_buy_signal(signal)
        
    async def send_sell_signal(self, price: Optional[float] = None, reason: str = "Manual SELL"):
        """Send a manual SELL signal"""
        if not self.bot:
            raise RuntimeError("Bot not initialized")
            
        # Get current price if not provided or if price is 0 (market order)
        if price is None or price == 0:
            market_data = await self.bot.hyperliquid_client.get_market_data(self.config.symbol)
            price = market_data.price
            self.logger.info(f"Using current market price: ${price:.4f}")
        
        signal = ManualSignal(
            signal_type='SELL',
            symbol=self.config.symbol,
            price=price,
            timestamp=datetime.now(),
            reason=reason
        )
        
        self.logger.info(f"🔴 MANUAL SELL SIGNAL: {signal.symbol} @ ${signal.price:.4f}")
        self.logger.info(f"Reason: {signal.reason}")
        
        # Execute the signal through bot's sell logic
        await self._execute_sell_signal(signal)
        
    async def _execute_buy_signal(self, signal: ManualSignal):
        """Execute buy signal through bot orchestrator"""
        try:
            # Check if we already have a position
            current_position = self.bot.state_manager.get_current_position()
            if current_position:
                self.logger.warning(f"Already have position: {current_position.symbol} {current_position.size}")
                response = input("Continue with BUY anyway? (yes/no): ")
                if response.lower() != 'yes':
                    self.logger.info("BUY signal cancelled")
                    return
            
            # Get account info
            account_info = await self.bot.hyperliquid_client.get_account_info()
            available_balance = account_info.get('available_balance', 0)
            
            if available_balance <= 0:
                self.logger.error("No available balance for trading")
                return
                
            # Calculate position size
            if self.config.position_size_usd:
                position_size = self.config.position_size_usd / signal.price
                self.logger.info(f"Using fixed USD position size: ${self.config.position_size_usd:.2f} = {position_size:.6f} {signal.symbol}")
            else:
                risk_amount = available_balance * (self.config.position_size_percent / 100)
                position_size = risk_amount * self.config.leverage / signal.price
                self.logger.info(f"Using percentage position size: {self.config.position_size_percent}% = {position_size:.6f} {signal.symbol}")
            
            # Check minimum position size
            notional_value = position_size * signal.price
            min_notional = 10.0
            if notional_value < min_notional:
                self.logger.warning(f"Position size too small: ${notional_value:.2f} < ${min_notional:.2f}. Adjusting to minimum.")
                position_size = min_notional / signal.price
                notional_value = min_notional
            
            self.logger.info(f"Position size: {position_size:.6f} {signal.symbol} (${notional_value:.2f})")
            
            # Confirm order
            if not self.config.dry_run:
                self.logger.warning("⚠️  LIVE TRADING MODE - This will place a REAL order!")
                response = input(f"Place BUY order for {position_size:.6f} {signal.symbol} @ ${signal.price:.4f}? (yes/no): ")
                if response.lower() != 'yes':
                    self.logger.info("Order cancelled")
                    return
            
            # Place order
            self.logger.info("Placing BUY order (MARKET)...")
            order_result = await self.bot.hyperliquid_client.place_order(
                symbol=signal.symbol,
                side='buy',
                size=position_size,
                price=None,  # Market orders don't need a price
                order_type='market'
            )
            
            if order_result.success:
                if order_result.filled_size > 0:
                    self.logger.info("✅ BUY ORDER FILLED!")
                    self.logger.info(f"Order ID: {order_result.order_id}")
                    self.logger.info(f"Filled: {order_result.filled_size} @ ${order_result.filled_price}")
                    self.logger.info(f"Fees: ${order_result.fees}")
                else:
                    self.logger.info("✅ BUY ORDER PLACED (LIMIT ORDER)")
                    self.logger.info(f"Order ID: {order_result.order_id}")
                    self.logger.info(f"Status: Waiting for fill at your limit price")
                    self.logger.info(f"Filled: {order_result.filled_size} (order pending)")
                    self.logger.warning("⏳ This is normal - limit orders wait for market price to reach your target")
                
                # Update bot state if successful
                if order_result.filled_size > 0:
                    from state.position import Position
                    new_position = Position(
                        symbol=signal.symbol,
                        size=order_result.filled_size,
                        entry_price=order_result.filled_price,
                        entry_time=datetime.now(),
                        side='long'
                    )
                    self.bot.state_manager.set_current_position(new_position)
                    await self.bot.state_manager.save_state()
                    self.logger.info("Position recorded in bot state")
            else:
                self.logger.error(f"❌ BUY ORDER FAILED: {order_result.error_message}")
                
        except Exception as e:
            self.logger.error(f"Error executing BUY signal: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
    async def _execute_sell_signal(self, signal: ManualSignal):
        """Execute sell signal through bot orchestrator"""
        try:
            # Check if we have a position to sell
            current_position = self.bot.state_manager.get_current_position()
            if not current_position or current_position.size <= 0:
                self.logger.warning("No position to sell")
                response = input("Place SELL order anyway? (yes/no): ")
                if response.lower() != 'yes':
                    self.logger.info("SELL signal cancelled")
                    return
                    
                # Get a default position size for manual sell
                if self.config.position_size_usd:
                    position_size = self.config.position_size_usd / signal.price
                else:
                    account_info = await self.bot.hyperliquid_client.get_account_info()
                    available_balance = account_info.get('available_balance', 0)
                    risk_amount = available_balance * (self.config.position_size_percent / 100)
                    position_size = risk_amount * self.config.leverage / signal.price
            else:
                position_size = abs(current_position.size)
                self.logger.info(f"Selling existing position: {position_size} {signal.symbol}")
            
            # Check minimum position size
            notional_value = position_size * signal.price
            min_notional = 10.0
            if notional_value < min_notional:
                self.logger.warning(f"Position size too small: ${notional_value:.2f} < ${min_notional:.2f}. Adjusting to minimum.")
                position_size = min_notional / signal.price
                notional_value = min_notional
            
            self.logger.info(f"Position size: {position_size:.6f} {signal.symbol} (${notional_value:.2f})")
            
            # Confirm order
            if not self.config.dry_run:
                self.logger.warning("⚠️  LIVE TRADING MODE - This will place a REAL order!")
                response = input(f"Place SELL order for {position_size:.6f} {signal.symbol} @ ${signal.price:.4f}? (yes/no): ")
                if response.lower() != 'yes':
                    self.logger.info("Order cancelled")
                    return
            
            # Place order
            self.logger.info("Placing SELL order (MARKET)...")
            order_result = await self.bot.hyperliquid_client.place_order(
                symbol=signal.symbol,
                side='sell',
                size=position_size,
                price=None,  # Market orders don't need a price
                order_type='market'
            )
            
            if order_result.success:
                if order_result.filled_size > 0:
                    self.logger.info("✅ SELL ORDER FILLED!")
                    self.logger.info(f"Order ID: {order_result.order_id}")
                    self.logger.info(f"Filled: {order_result.filled_size} @ ${order_result.filled_price}")
                    self.logger.info(f"Fees: ${order_result.fees}")
                else:
                    self.logger.info("✅ SELL ORDER PLACED (LIMIT ORDER)")
                    self.logger.info(f"Order ID: {order_result.order_id}")
                    self.logger.info(f"Status: Waiting for fill at your limit price")
                    self.logger.info(f"Filled: {order_result.filled_size} (order pending)")
                    self.logger.warning("⏳ This is normal - limit orders wait for market price to reach your target")
                
                # Update bot state if successful
                if order_result.filled_size > 0 and current_position:
                    # Close position
                    self.bot.state_manager.set_current_position(None)
                    await self.bot.state_manager.save_state()
                    self.logger.info("Position closed in bot state")
            else:
                self.logger.error(f"❌ SELL ORDER FAILED: {order_result.error_message}")
                
        except Exception as e:
            self.logger.error(f"Error executing SELL signal: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
    async def cleanup(self):
        """Cleanup resources"""
        if self.bot:
            await self.bot.cleanup()

async def main():
    """Main function for manual signal injection"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 manual_signal.py buy [price] [reason]")
        print("  python3 manual_signal.py sell [price] [reason]")
        print("  python3 manual_signal.py status")
        print("")
        print("Examples:")
        print("  python3 manual_signal.py buy 15.50 'Testing rounding fix'")
        print("  python3 manual_signal.py sell")
        print("  python3 manual_signal.py status")
        return
    
    command = sys.argv[1].lower()
    price = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].replace('.', '').isdigit() else None
    reason = ' '.join(sys.argv[3:]) if len(sys.argv) > 3 else f"Manual {command.upper()}"
    
    # Setup
    config = Config()
    setup_logger(config.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info(f"=== MANUAL SIGNAL INJECTION ===")
    logger.info(f"Mode: {'DRY RUN' if config.dry_run else 'LIVE TRADING'}")
    logger.info(f"Network: {'TESTNET' if config.testnet else 'MAINNET'}")
    logger.info(f"Symbol: {config.symbol}")
    
    injector = ManualSignalInjector(config)
    
    try:
        await injector.initialize()
        
        if command == 'buy':
            await injector.send_buy_signal(price, reason)
        elif command == 'sell':
            await injector.send_sell_signal(price, reason)
        elif command == 'status':
            # Show current bot status
            current_position = injector.bot.state_manager.get_current_position()
            if current_position:
                logger.info(f"Current Position: {current_position.symbol} {current_position.size} @ ${current_position.entry_price}")
            else:
                logger.info("No current position")
                
            account_info = await injector.bot.hyperliquid_client.get_account_info()
            logger.info(f"Account Balance: ${account_info.get('balance', 0):.2f}")
            logger.info(f"Available Balance: ${account_info.get('available_balance', 0):.2f}")
        else:
            logger.error(f"Unknown command: {command}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        await injector.cleanup()

if __name__ == "__main__":
    asyncio.run(main())