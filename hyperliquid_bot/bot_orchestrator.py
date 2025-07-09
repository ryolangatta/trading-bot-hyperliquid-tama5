"""
Bot Orchestrator for Hyperliquid Trading Bot
Main execution engine that coordinates all components
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass
class OperationResult:
    """Result of bot operations with error context"""
    success: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    execution_time: float = 0.0


class CriticalError(Exception):
    """Exception for critical errors that should trigger restart"""
    pass


class RecoverableError(Exception):
    """Exception for recoverable errors that should be retried"""
    pass


from strategies.rsi_pengu_strategy import StochasticRSIStrategy, Candle, Signal
from hyperliquid_wrapper.hyperliquid_client import HyperliquidClient
from risk.fee_calculator import FeeCalculator
from state.state_manager import StateManager, Position, Trade
from notifications.discord_notifier import DiscordNotifier, NotificationMessage
from notifications.discord_commands import DiscordWebhookCommands
from utils.error_monitor import ErrorMonitor
from utils.render_restart import RenderRestartManager


class BotOrchestrator:
    """Main bot orchestrator - coordinates all components"""
    
    def __init__(self, config, strategy_name: str, error_monitor: ErrorMonitor):
        self.config = config
        self.strategy_name = strategy_name
        self.error_monitor = error_monitor
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.strategy = None
        self.hyperliquid_client = None
        self.fee_calculator = None
        self.state_manager = None
        self.discord_notifier = None
        self.discord_commands = None
        self.restart_manager = None
        
        # Runtime state
        self.running = False
        self.start_time = datetime.now()
        self.last_candle_time = None
        self.last_status_update = datetime.now()
        self.last_roi_update = datetime.now()
        
        # Statistics
        self.total_signals = 0
        self.executed_trades = 0
        self.filtered_trades = 0
        
        self.logger.info(f"Bot orchestrator initialized for strategy: {strategy_name}")
        
    @asynccontextmanager
    async def error_context(self, operation_name: str, critical: bool = False):
        """Context manager for comprehensive error handling"""
        start_time = datetime.utcnow()
        
        try:
            self.logger.debug(f"Starting operation: {operation_name}")
            yield
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self.logger.debug(f"Operation {operation_name} completed in {execution_time:.3f}s")
            
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_type = type(e).__name__
            
            # Log with full context
            self.logger.error(
                f"Operation {operation_name} failed after {execution_time:.3f}s: {e}",
                exc_info=True
            )
            
            # Record error in monitor
            severity = "CRITICAL" if critical else "ERROR"
            self.error_monitor.record_error(f"{operation_name.upper()}_ERROR", str(e), severity)
            
            # Re-raise with appropriate classification
            if critical or isinstance(e, CriticalError):
                raise CriticalError(f"{operation_name} failed: {e}") from e
            elif isinstance(e, RecoverableError):
                raise
            else:
                # Default to recoverable for most errors
                raise RecoverableError(f"{operation_name} failed: {e}") from e
                
    async def safe_operation(self, operation_name: str, operation_func, *args, **kwargs) -> OperationResult:
        """Execute operation with comprehensive error handling and recovery"""
        max_retries = 3
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                async with self.error_context(operation_name, critical=False):
                    start_time = datetime.utcnow()
                    result = await operation_func(*args, **kwargs)
                    execution_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    return OperationResult(
                        success=True,
                        retry_count=retry_count,
                        execution_time=execution_time
                    )
                    
            except RecoverableError as e:
                retry_count += 1
                if retry_count > max_retries:
                    return OperationResult(
                        success=False,
                        error_type="MAX_RETRIES_EXCEEDED",
                        error_message=str(e),
                        retry_count=retry_count
                    )
                    
                # Exponential backoff
                delay = min(2.0 ** retry_count, 30.0)
                self.logger.warning(f"Retrying {operation_name} in {delay}s (attempt {retry_count}/{max_retries})")
                await asyncio.sleep(delay)
                
            except CriticalError as e:
                return OperationResult(
                    success=False,
                    error_type="CRITICAL_ERROR",
                    error_message=str(e),
                    retry_count=retry_count
                )
                
        return OperationResult(
            success=False,
            error_type="UNKNOWN_ERROR",
            error_message="Operation failed after all retries",
            retry_count=retry_count
        )
        
    async def initialize(self) -> None:
        """Initialize all components"""
        try:
            self.logger.info("Initializing bot components...")
            
            # Initialize strategy
            if self.strategy_name == 'rsi_pengu':
                self.strategy = StochasticRSIStrategy(self.config)
            else:
                raise ValueError(f"Unknown strategy: {self.strategy_name}")
                
            # Initialize Hyperliquid client
            self.hyperliquid_client = HyperliquidClient(self.config)
            await self.hyperliquid_client.connect()
            
            # Initialize fee calculator
            self.fee_calculator = FeeCalculator(self.config)
            
            # Initialize state manager
            self.state_manager = StateManager(self.config)
            
            # Initialize Discord notifier
            self.discord_notifier = DiscordNotifier(self.config)
            
            # Initialize Discord command processor
            self.discord_commands = DiscordWebhookCommands(self.config, self.discord_notifier)
            
            # Initialize restart manager (Render-specific)
            self.restart_manager = RenderRestartManager(self.config)
            self.restart_manager.setup_signal_handlers()
            
            # Restore position state
            current_position = self.state_manager.get_current_position()
            if current_position:
                self.strategy.set_position({
                    'symbol': current_position.symbol,
                    'size': current_position.size,
                    'entry_price': current_position.entry_price,
                    'entry_time': current_position.entry_time,
                    'leverage': current_position.leverage
                })
                self.logger.info(f"Restored position: {current_position.symbol} {current_position.size} @ ${current_position.entry_price}")
                
            # Health check
            if not await self.hyperliquid_client.health_check():
                raise Exception("Hyperliquid API health check failed")
                
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize bot: {e}")
            self.error_monitor.record_error("INITIALIZATION", str(e), "CRITICAL")
            
            # Attempt restart if on Render and critical failure
            if self.restart_manager and self.restart_manager.should_attempt_restart("INITIALIZATION"):
                await self.restart_manager.attempt_restart(str(e), "INITIALIZATION")
            
            raise
            
    async def run(self) -> None:
        """Main bot execution loop"""
        try:
            await self.initialize()
            
            # Get initial account balance
            self.logger.info("Fetching account information from Hyperliquid...")
            account_info = await self.hyperliquid_client.get_account_info()
            wallet_balance = account_info.get('balance', 0)
            available_balance = account_info.get('available_balance', 0)
            self.logger.info(f"Account info retrieved - Balance: ${wallet_balance:.2f}, Available: ${available_balance:.2f}")
            
            # Send startup notification
            startup_message = NotificationMessage(
                title='🚀 Bot Started',
                description=f'Hyperliquid Trading Bot v5.1.0 started with {self.strategy_name} strategy',
                color=0x00FF00,
                fields={
                    'Mode': 'DRY RUN' if self.config.dry_run else 'LIVE',
                    'Environment': 'TESTNET' if self.config.testnet else 'MAINNET',
                    'Strategy': self.strategy_name,
                    'Symbol': self.config.symbol,
                    'Wallet Balance': f'${wallet_balance:,.2f} USDC',
                    'Available': f'${available_balance:,.2f} USDC'
                }
            )
            await self.discord_notifier.send_notification(startup_message)
            
            self.running = True
            self.logger.info("Bot execution started")
            
            while self.running:
                try:
                    # Check circuit breaker
                    if self.error_monitor.is_circuit_breaker_active():
                        self.logger.warning("Circuit breaker active - trading paused")
                        await asyncio.sleep(60)  # Wait 1 minute before checking again
                        continue
                        
                    # Execute main trading cycle with comprehensive error handling
                    result = await self.safe_operation("trading_cycle", self._execute_trading_cycle)
                    
                    if not result.success:
                        if result.error_type == "CRITICAL_ERROR":
                            raise CriticalError(f"Critical trading cycle failure: {result.error_message}")
                        else:
                            self.logger.warning(f"Trading cycle failed: {result.error_message}")
                            
                    # Send periodic status updates (non-critical)
                    await self.safe_operation("status_updates", self._send_periodic_updates)
                    
                    # Cleanup old errors (non-critical)
                    try:
                        self.error_monitor.cleanup_old_errors()
                    except Exception as e:
                        self.logger.warning(f"Error cleanup failed: {e}")
                    
                    # Wait before next cycle
                    await asyncio.sleep(30)  # 30 second cycle
                    
                except CriticalError as e:
                    self.logger.critical(f"Critical error in main loop: {e}")
                    raise  # Let this propagate to trigger restart
                    
                except Exception as e:
                    self.logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                    self.error_monitor.record_error("MAIN_LOOP_UNEXPECTED", str(e), "ERROR")
                    await asyncio.sleep(60)  # Wait longer on unexpected errors
                    
        except Exception as e:
            self.logger.critical(f"Fatal error in bot execution: {e}")
            self.error_monitor.record_error("FATAL", str(e), "CRITICAL")
            
            # Send critical error notification
            if self.discord_notifier:
                await self.discord_notifier.send_error_alert({
                    'error_type': 'FATAL',
                    'message': str(e),
                    'severity': 'CRITICAL',
                    'circuit_breaker_active': self.error_monitor.is_circuit_breaker_active()
                })
            
            # Attempt restart if on Render and critical failure
            if self.restart_manager and self.restart_manager.should_attempt_restart("FATAL_CRASH"):
                await self.restart_manager.attempt_restart(str(e), "FATAL_CRASH")
            
            raise
            
        finally:
            await self.cleanup()
            
    async def _execute_trading_cycle(self) -> None:
        """Execute one complete trading cycle"""
        try:
            # Get latest market data
            market_data = await self.hyperliquid_client.get_market_data(self.config.symbol)
            
            # Check for manual signals first (priority over automated signals)
            manual_signal = self.discord_commands.get_pending_signal()
            if manual_signal:
                await self._process_manual_signal(manual_signal, market_data.price)
                return  # Skip automated signals this cycle
            
            # Create candle from current market data (simplified for demo)
            # NOTE: For production, implement proper OHLCV candle aggregation
            candle = Candle(
                timestamp=market_data.timestamp,
                open=market_data.price,  # Using current price as approximation
                high=market_data.ask,    # Use ask as high
                low=market_data.bid,     # Use bid as low
                close=market_data.price, # Current price as close
                volume=market_data.volume_24h
            )
            
            # Only update if this is a new candle (based on timeframe)
            if self._is_new_candle(candle.timestamp):
                self.strategy.update_candles(candle)
                self.last_candle_time = candle.timestamp
                
                # Generate trading signal
                signal = self.strategy.generate_signal()
                
                if signal:
                    self.total_signals += 1
                    self.logger.info(f"Signal generated: {signal.action} at ${signal.price:.4f}")
                    
                    # Validate signal
                    if self.strategy.validate_signal(signal):
                        await self._execute_signal(signal)
                    else:
                        self.logger.warning("Signal validation failed")
                        
            # Check for stop loss
            current_position = self.state_manager.get_current_position()
            if current_position and self.strategy.should_stop_loss(market_data.price):
                await self._execute_stop_loss(market_data.price)
                
        except Exception as e:
            self.logger.error(f"Error in trading cycle: {e}")
            self.error_monitor.record_error("TRADING_CYCLE", str(e), "ERROR")
            
    def _is_new_candle(self, timestamp: datetime) -> bool:
        """Check if this is a new candle based on timeframe"""
        if not self.last_candle_time:
            return True
            
        # Parse timeframe (e.g., '30m' -> 30 minutes)
        timeframe = self.config.timeframe
        if timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
            interval = timedelta(minutes=minutes)
        elif timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            interval = timedelta(hours=hours)
        else:
            interval = timedelta(minutes=30)  # Default to 30 minutes
            
        return timestamp >= self.last_candle_time + interval
        
    async def _execute_signal(self, signal) -> None:
        """Execute a trading signal"""
        try:
            current_position = self.state_manager.get_current_position()
            
            if signal.action == 'BUY' and not current_position:
                await self._execute_buy(signal)
            elif signal.action == 'SELL' and current_position:
                await self._execute_sell(signal)
            else:
                self.logger.debug(f"Signal ignored: {signal.action} (position status: {current_position is not None})")
                
        except Exception as e:
            self.logger.error(f"Error executing signal: {e}")
            self.error_monitor.record_error("SIGNAL_EXECUTION", str(e), "ERROR")
            
    async def _execute_buy(self, signal) -> None:
        """Execute buy order"""
        try:
            # Calculate position size
            account_info = await self.hyperliquid_client.get_account_info()
            available_balance = account_info.get('available_balance', 0)
            
            if available_balance <= 0:
                self.logger.warning("No available balance for trading")
                return
                
            # Calculate position size - USD takes priority over percentage
            if self.config.position_size_usd:
                # Use fixed USD amount
                position_size = self.config.position_size_usd / signal.price
                self.logger.info(f"Using fixed USD position size: ${self.config.position_size_usd:.2f} = {position_size:.6f} {self.config.symbol}")
            else:
                # Use percentage-based sizing
                risk_amount = available_balance * (self.config.position_size_percent / 100)
                position_size = risk_amount * self.config.leverage / signal.price
                self.logger.info(f"Using percentage position size: {self.config.position_size_percent}% of ${available_balance:.2f} = {position_size:.6f} {self.config.symbol}")
            
            # Check minimum position size (Hyperliquid requires minimum $10 notional)
            notional_value = position_size * signal.price
            min_notional = 10.0  # $10 minimum
            if notional_value < min_notional:
                self.logger.warning(f"Position size too small: ${notional_value:.2f} < ${min_notional:.2f} minimum. Adjusting to minimum.")
                position_size = min_notional / signal.price
                notional_value = min_notional
            
            # Check fee profitability
            expected_exit_price = signal.price * (1 + 0.05)  # Assume 5% profit target
            should_execute, fee_calc = self.fee_calculator.should_execute_trade(
                entry_price=signal.price,
                expected_exit_price=expected_exit_price,
                position_size=position_size * signal.price  # fee_calculator expects USD value
            )
            
            if not should_execute:
                self.filtered_trades += 1
                self.logger.warning(f"Trade filtered due to fees: Expected profit ${fee_calc.net_profit:.2f}")
                return
                
            # Execute order
            order_result = await self.hyperliquid_client.place_order(
                symbol=self.config.symbol,
                side='buy',
                size=position_size,
                price=signal.price,
                order_type='limit'
            )
            
            if order_result.success:
                # Record position
                position = Position(
                    symbol=self.config.symbol,
                    side='long',
                    size=order_result.filled_size,
                    entry_price=order_result.filled_price,
                    entry_time=datetime.now(),
                    leverage=self.config.leverage
                )
                
                self.state_manager.set_position(position)
                self.strategy.set_position({
                    'symbol': position.symbol,
                    'size': position.size,
                    'entry_price': position.entry_price,
                    'entry_time': position.entry_time,
                    'leverage': position.leverage
                })
                
                self.executed_trades += 1
                
                # Get updated account balance
                account_info = await self.hyperliquid_client.get_account_info()
                
                # Send Discord notification
                await self.discord_notifier.send_trade_alert({
                    'action': 'BUY',
                    'symbol': self.config.symbol,
                    'price': order_result.filled_price,
                    'size': order_result.filled_size,
                    'pnl': 0,
                    'wallet_balance': account_info.get('balance', 0),
                    'available_balance': account_info.get('available_balance', 0)
                })
                
                self.logger.info(f"BUY order executed: {order_result.filled_size} @ ${order_result.filled_price:.4f}")
                
            else:
                self.logger.error(f"BUY order failed: {order_result.error_message}")
                self.error_monitor.record_error("ORDER_EXECUTION", order_result.error_message, "ERROR")
                
        except Exception as e:
            self.logger.error(f"Error executing buy: {e}")
            self.error_monitor.record_error("BUY_EXECUTION", str(e), "ERROR")
            
    async def _execute_sell(self, signal) -> None:
        """Execute sell order"""
        try:
            current_position = self.state_manager.get_current_position()
            if not current_position:
                self.logger.warning("No position to sell")
                return
                
            # Execute order
            order_result = await self.hyperliquid_client.place_order(
                symbol=self.config.symbol,
                side='sell',
                size=current_position.size,
                price=signal.price,
                order_type='limit'
            )
            
            if order_result.success:
                # Calculate PnL and ROI correctly
                price_difference = order_result.filled_price - current_position.entry_price
                pnl = price_difference * current_position.size  # Actual dollar PnL
                roi = (price_difference / current_position.entry_price) * 100  # Percentage ROI
                
                # Record trade
                trade = Trade(
                    symbol=self.config.symbol,
                    side='long',
                    entry_price=current_position.entry_price,
                    exit_price=order_result.filled_price,
                    size=current_position.size,
                    entry_time=current_position.entry_time,
                    exit_time=datetime.now(),
                    pnl=pnl,
                    fees=order_result.fees,
                    roi=roi
                )
                
                self.state_manager.add_trade(trade)
                self.state_manager.set_position(None)
                self.strategy.set_position(None)
                
                self.executed_trades += 1
                
                # Get updated account balance
                account_info = await self.hyperliquid_client.get_account_info()
                
                # Send Discord notification
                await self.discord_notifier.send_trade_alert({
                    'action': 'SELL',
                    'symbol': self.config.symbol,
                    'price': order_result.filled_price,
                    'size': order_result.filled_size,
                    'pnl': pnl,
                    'wallet_balance': account_info.get('balance', 0),
                    'available_balance': account_info.get('available_balance', 0)
                })
                
                self.logger.info(f"SELL order executed: {order_result.filled_size} @ ${order_result.filled_price:.4f}, PnL: ${pnl:.2f}")
                
            else:
                self.logger.error(f"SELL order failed: {order_result.error_message}")
                self.error_monitor.record_error("ORDER_EXECUTION", order_result.error_message, "ERROR")
                
        except Exception as e:
            self.logger.error(f"Error executing sell: {e}")
            self.error_monitor.record_error("SELL_EXECUTION", str(e), "ERROR")
            
    async def _execute_stop_loss(self, current_price: float) -> None:
        """Execute stop loss order"""
        try:
            self.logger.warning(f"Executing stop loss at ${current_price:.4f}")
            
            # Create a sell signal for stop loss
            stop_loss_signal = Signal(
                action='SELL',
                price=current_price,
                timestamp=datetime.now(),
                stoch_rsi_value=self.strategy.get_current_stoch_rsi() or 0,
                rsi_value=self.strategy.get_current_rsi() or 0,
                confidence=1.0,
                reason="Stop loss triggered"
            )
            
            await self._execute_sell(stop_loss_signal)
            
        except Exception as e:
            self.logger.error(f"Error executing stop loss: {e}")
            self.error_monitor.record_error("STOP_LOSS", str(e), "ERROR")
            
    async def _process_manual_signal(self, manual_signal, current_price: float) -> None:
        """Process a manual trading signal from Discord"""
        try:
            self.logger.info(f"Processing manual {manual_signal.command} signal from {manual_signal.username}")
            
            # Create a trading signal from the manual command
            signal = Signal(
                action=manual_signal.command,  # 'BUY' or 'SELL'
                price=current_price,
                timestamp=datetime.now(),
                stoch_rsi_value=self.strategy.get_current_stoch_rsi() or 0,
                rsi_value=self.strategy.get_current_rsi() or 0,
                confidence=1.0,
                reason=f"Manual command from {manual_signal.username}"
            )
            
            # Check current position status
            current_position = self.state_manager.get_current_position()
            
            # Validate manual signal based on position status
            if manual_signal.command == 'BUY' and current_position:
                self.logger.warning("Manual BUY ignored - already in position")
                await self._send_manual_signal_feedback(manual_signal, "BUY ignored - already in position", False)
            elif manual_signal.command == 'SELL' and not current_position:
                self.logger.warning("Manual SELL ignored - no position to close")
                await self._send_manual_signal_feedback(manual_signal, "SELL ignored - no position to close", False)
            else:
                # Execute the manual signal
                await self._execute_signal(signal)
                await self._send_manual_signal_feedback(manual_signal, f"{manual_signal.command} order executed", True)
            
            # Remove the signal from queue
            self.discord_commands.remove_signal(manual_signal)
            
        except Exception as e:
            self.logger.error(f"Error processing manual signal: {e}")
            self.error_monitor.record_error("MANUAL_SIGNAL", str(e), "ERROR")
            await self._send_manual_signal_feedback(manual_signal, f"Error: {str(e)}", False)
            
    async def _send_manual_signal_feedback(self, manual_signal, message: str, success: bool) -> None:
        """Send feedback about manual signal execution to Discord"""
        try:
            color = 0x00FF00 if success else 0xFF0000
            title = "✅ Manual Signal Executed" if success else "❌ Manual Signal Failed"
            
            feedback_message = NotificationMessage(
                title=title,
                description=f"Manual {manual_signal.command} command processed",
                color=color,
                fields={
                    "Command": manual_signal.command,
                    "User": manual_signal.username,
                    "Result": message,
                    "Symbol": self.config.symbol,
                    "Mode": "LIVE" if not self.config.dry_run else "DRY RUN"
                }
            )
            
            await self.discord_notifier.send_notification(feedback_message)
            
        except Exception as e:
            self.logger.error(f"Error sending manual signal feedback: {e}")
            
    async def _send_periodic_updates(self) -> None:
        """Send periodic status updates"""
        try:
            current_time = datetime.now()
            
            # Status updates every 10 minutes
            if (current_time - self.last_status_update).total_seconds() >= self.config.discord_status_interval:
                await self._send_status_update()
                self.last_status_update = current_time
                
            # ROI updates every hour
            if (current_time - self.last_roi_update).total_seconds() >= self.config.discord_roi_interval:
                await self._send_roi_update()
                self.last_roi_update = current_time
                
        except Exception as e:
            self.logger.error(f"Error sending periodic updates: {e}")
            
    async def _send_status_update(self) -> None:
        """Send bot status update"""
        try:
            uptime_seconds = (datetime.now() - self.start_time).total_seconds()
            
            # Get account balance
            account_info = await self.hyperliquid_client.get_account_info()
            wallet_balance = account_info.get('balance', 0)
            available_balance = account_info.get('available_balance', 0)
            
            status_data = {
                'running': self.running,
                'strategy': self.strategy_name,
                'current_rsi': self.strategy.get_current_rsi(),
                'has_position': self.state_manager.get_current_position() is not None,
                'uptime_seconds': uptime_seconds,
                'recent_errors': self.error_monitor.get_error_count(1),
                'circuit_breaker_active': self.error_monitor.is_circuit_breaker_active(),
                'wallet_balance': wallet_balance,
                'available_balance': available_balance
            }
            
            await self.discord_notifier.send_bot_status(status_data)
            
        except Exception as e:
            self.logger.error(f"Error sending status update: {e}")
            
    async def _send_roi_update(self) -> None:
        """Send ROI performance update"""
        try:
            roi_data = self.state_manager.get_performance_summary()
            recent_trades = self.state_manager.get_recent_trades(30)  # Last 30 days
            
            # Convert trades to dict format for Discord
            trade_history = []
            for trade in recent_trades:
                trade_history.append({
                    'exit_time': trade.exit_time.isoformat(),
                    'pnl': trade.pnl,
                    'fees': trade.fees,
                    'roi': trade.roi
                })
                
            await self.discord_notifier.send_roi_graph(roi_data, trade_history)
            
        except Exception as e:
            self.logger.error(f"Error sending ROI update: {e}")
            
    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            self.running = False
            
            if self.hyperliquid_client:
                await self.hyperliquid_client.disconnect()
                
            self.logger.info("Bot cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            
    def stop(self) -> None:
        """Stop the bot"""
        self.logger.info("Stopping bot...")
        self.running = False