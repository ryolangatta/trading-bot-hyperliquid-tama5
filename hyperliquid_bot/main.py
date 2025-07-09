#!/usr/bin/env python3
"""
Hyperliquid Trading Bot - Entry Point
Professional-grade execution-only crypto trading bot for Hyperliquid
"""

import argparse
import asyncio
import logging
import sys
import os
from datetime import datetime

from config import Config
from bot_orchestrator import BotOrchestrator
from utils.logger import setup_logger
from utils.error_monitor import ErrorMonitor
from notifications.discord_notifier import DiscordNotifier


async def main():
    """Main entry point for the trading bot"""
    parser = argparse.ArgumentParser(description='Hyperliquid Trading Bot')
    parser.add_argument('--config', default='.env', help='Path to config file')
    parser.add_argument('--strategy', default='stochastic_rsi_link', help='Strategy to run')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logger(args.log_level)
    
    try:
        # Load configuration
        config = Config(args.config)
        
        # Override dry-run if specified via CLI
        if args.dry_run:
            config.dry_run = True
            
        # Validate configuration
        config.validate()
        
        logger.info(f"Starting Hyperliquid Trading Bot v5.1.0")
        logger.info(f"Strategy: {args.strategy}")
        logger.info(f"Mode: {'DRY_RUN' if config.dry_run else 'LIVE'}")
        logger.info(f"Environment: {'TESTNET' if config.testnet else 'MAINNET'}")
        
        # Initialize error monitor
        error_monitor = ErrorMonitor(config)
        
        # Initialize bot orchestrator
        bot = BotOrchestrator(config, args.strategy, error_monitor)
        
        # Start the bot
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


async def cleanup_resources(config=None, error_monitor=None, discord_notifier=None):
    """Comprehensive resource cleanup"""
    try:
        # Give components time to finish current operations
        await asyncio.sleep(1)
        
        # Close any open file handles
        if config and hasattr(config, 'cleanup'):
            await config.cleanup()
            
        # Cleanup error monitor
        if error_monitor and hasattr(error_monitor, 'cleanup'):
            error_monitor.cleanup()
            
        # Close Discord connections
        if discord_notifier and hasattr(discord_notifier, 'cleanup'):
            await discord_notifier.cleanup()
            
        # Force garbage collection
        import gc
        gc.collect()
        
        logging.info("Resource cleanup completed")
        
    except Exception as e:
        logging.warning(f"Error during resource cleanup: {e}")


async def send_notification_with_fallback(discord_notifier, message, max_retries=3):
    """Send Discord notification with retry fallback"""
    if not discord_notifier:
        return False
        
    for attempt in range(max_retries):
        try:
            await discord_notifier.send_notification(message)
            return True
        except Exception as e:
            logging.warning(f"Discord notification attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
    # Final fallback - try with minimal message
    try:
        from notifications.discord_notifier import NotificationMessage
        fallback_message = NotificationMessage(
            title="Bot Alert",
            description="Critical error occurred - check logs",
            color=0xFF0000
        )
        await discord_notifier.send_notification(fallback_message)
        return True
    except:
        return False


async def safe_main():
    """Production-grade main wrapper with comprehensive error handling"""
    config = None
    error_monitor = None
    discord_notifier = None
    restart_count = 0
    max_restarts = 3
    
    try:
        # Minimal setup for error tracking
        config = Config('.env')
        error_monitor = ErrorMonitor(config)
        discord_notifier = DiscordNotifier(config)
        
        # Run the main bot logic
        await main()
        
    except KeyboardInterrupt:
        logging.info("Bot stopped by user - performing graceful shutdown")
        await cleanup_resources(config, error_monitor, discord_notifier)
        sys.exit(0)
        
    except Exception as e:
        logging.critical(f"Bot crashed with fatal error: {e}", exc_info=True)
        
        try:
            # Record the error
            if error_monitor:
                error_monitor.record_error("FATAL_CRASH", str(e), "CRITICAL")
            
            # Send comprehensive crash alert
            if discord_notifier:
                from notifications.discord_notifier import NotificationMessage
                crash_message = NotificationMessage(
                    title="🚨 Critical Bot Crash",
                    description=f"Bot crashed with fatal error",
                    color=0xFF0000,
                    fields={
                        "Error Type": type(e).__name__,
                        "Error Message": str(e)[:500],
                        "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
                        "Circuit Breaker": "ACTIVE" if error_monitor and error_monitor.is_circuit_breaker_active() else "INACTIVE",
                        "Environment": "TESTNET" if config and config.testnet else "MAINNET"
                    }
                )
                
                await send_notification_with_fallback(discord_notifier, crash_message)
            
            # Check circuit breaker
            if error_monitor and error_monitor.is_circuit_breaker_active():
                logging.critical("Circuit breaker active - Bot will not restart")
                
                if discord_notifier:
                    from notifications.discord_notifier import NotificationMessage
                    circuit_message = NotificationMessage(
                        title="🛑 Circuit Breaker Active",
                        description="Bot stopped due to excessive errors. Manual intervention required.",
                        color=0xFF0000,
                        fields={
                            "Action Required": "Manual reset needed",
                            "Error Threshold": str(config.circuit_breaker_errors) if config else "Unknown",
                            "Time Window": f"{config.circuit_breaker_window_hours}h" if config else "Unknown"
                        }
                    )
                    await send_notification_with_fallback(discord_notifier, circuit_message)
                
                await cleanup_resources(config, error_monitor, discord_notifier)
                sys.exit(1)
            
            # Check restart limits
            restart_count += 1
            if restart_count > max_restarts:
                logging.critical(f"Max restart attempts ({max_restarts}) exceeded")
                
                if discord_notifier:
                    from notifications.discord_notifier import NotificationMessage
                    max_restart_message = NotificationMessage(
                        title="🛑 Max Restarts Exceeded",
                        description=f"Bot failed to restart after {max_restarts} attempts",
                        color=0xFF0000
                    )
                    await send_notification_with_fallback(discord_notifier, max_restart_message)
                
                await cleanup_resources(config, error_monitor, discord_notifier)
                sys.exit(1)
            
            # Attempt self-restart
            logging.info(f"Attempting bot self-restart (attempt {restart_count}/{max_restarts})...")
            
            if discord_notifier:
                from notifications.discord_notifier import NotificationMessage
                restart_message = NotificationMessage(
                    title="🔄 Bot Restarting",
                    description=f"Bot attempting self-restart after crash (attempt {restart_count}/{max_restarts})",
                    color=0xFFFF00,
                    fields={
                        "Restart Count": f"{restart_count}/{max_restarts}",
                        "Error": str(e)[:200],
                        "Delay": "5 seconds"
                    }
                )
                await send_notification_with_fallback(discord_notifier, restart_message)
            
            # Cleanup resources before restart
            await cleanup_resources(config, error_monitor, discord_notifier)
            
            # Wait before restart with increasing delay
            restart_delay = min(5 * restart_count, 30)  # 5s, 10s, 15s, max 30s
            await asyncio.sleep(restart_delay)
            
            # Restart the bot
            python = sys.executable
            os.execl(python, python, *sys.argv)
            
        except Exception as cleanup_error:
            logging.critical(f"Error during crash handling: {cleanup_error}", exc_info=True)
            # Force exit if cleanup fails
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(safe_main())