"""
Render self-restart logic for critical failures
Handles restart mechanisms as required by CLAUDE.md specification

References:
- Render Documentation: https://render.com/docs
- Background Workers: https://render.com/docs/background-workers
"""

import os
import sys
import logging
import signal
import asyncio
from typing import Optional
from datetime import datetime, timedelta


class RenderRestartManager:
    """
    Manages self-restart logic for Render deployment
    As required by CLAUDE.md specification
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.restart_count = 0
        self.max_restarts = 3
        self.restart_window = timedelta(hours=1)
        self.last_restart_time = None
        
        # Detect if running on Render
        self.is_render = self._detect_render_environment()
        
        if self.is_render:
            self.logger.info("Running on Render - self-restart enabled")
        else:
            self.logger.info("Not running on Render - self-restart disabled")
            
    def _detect_render_environment(self) -> bool:
        """
        Detect if running on Render platform
        Reference: https://render.com/docs/environment-variables
        """
        render_indicators = [
            'RENDER',
            'RENDER_SERVICE_ID',
            'RENDER_SERVICE_NAME',
            'RENDER_EXTERNAL_URL'
        ]
        
        for indicator in render_indicators:
            if os.getenv(indicator):
                return True
                
        return False
        
    def should_attempt_restart(self, error_type: str) -> bool:
        """
        Determine if restart should be attempted based on error type and history
        """
        if not self.is_render:
            return False
            
        # Critical errors that warrant restart
        critical_errors = [
            'HYPERLIQUID_CONNECTION',
            'SDK_INITIALIZATION',
            'FATAL_CRASH',
            'MEMORY_ERROR',
            'NETWORK_FAILURE'
        ]
        
        if error_type not in critical_errors:
            return False
            
        # Check restart limits
        current_time = datetime.now()
        
        # Reset restart count if enough time has passed
        if (self.last_restart_time and 
            current_time - self.last_restart_time > self.restart_window):
            self.restart_count = 0
            
        # Don't restart if we've hit the limit
        if self.restart_count >= self.max_restarts:
            self.logger.error(f"Max restarts ({self.max_restarts}) reached in {self.restart_window}")
            return False
            
        return True
        
    async def attempt_restart(self, error_message: str, error_type: str = 'CRITICAL') -> None:
        """
        Attempt to restart the bot process on Render
        Reference: https://render.com/docs/background-workers
        """
        if not self.should_attempt_restart(error_type):
            self.logger.warning("Restart not attempted - conditions not met")
            return
            
        self.restart_count += 1
        self.last_restart_time = datetime.now()
        
        self.logger.critical(f"Attempting restart #{self.restart_count} due to: {error_message}")
        
        try:
            # Send Discord notification about restart attempt
            await self._notify_restart_attempt(error_message, error_type)
            
            # Wait a moment for logs to flush
            await asyncio.sleep(2)
            
            # Perform graceful shutdown
            await self._graceful_shutdown()
            
            # Exit with specific code that Render will restart
            # Reference: Render automatically restarts background workers on exit
            self.logger.critical("Initiating restart...")
            sys.exit(1)  # Non-zero exit code triggers Render restart
            
        except Exception as e:
            self.logger.error(f"Failed to restart: {e}")
            # Force exit if graceful restart fails
            os._exit(1)
            
    async def _notify_restart_attempt(self, error_message: str, error_type: str) -> None:
        """Send Discord notification about restart attempt"""
        try:
            # Import here to avoid circular dependencies
            from notifications.discord_notifier import DiscordNotifier, NotificationMessage
            
            notifier = DiscordNotifier(self.config)
            
            message = NotificationMessage(
                title="🔄 Bot Restart Attempt",
                description=f"Critical failure detected - attempting restart #{self.restart_count}",
                color=0xFF9900,  # Orange
                fields={
                    "Error Type": error_type,
                    "Error Message": error_message[:500],  # Truncate long messages
                    "Restart Count": f"{self.restart_count}/{self.max_restarts}",
                    "Environment": "Render" if self.is_render else "Local",
                    "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
                }
            )
            
            await notifier.send_notification(message)
            
        except Exception as e:
            self.logger.error(f"Failed to send restart notification: {e}")
            
    async def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown before restart"""
        try:
            self.logger.info("Performing graceful shutdown...")
            
            # Give components time to cleanup
            await asyncio.sleep(1)
            
            # Flush logs
            for handler in logging.getLogger().handlers:
                handler.flush()
                
        except Exception as e:
            self.logger.error(f"Error during graceful shutdown: {e}")
            
    def setup_signal_handlers(self) -> None:
        """
        Setup signal handlers for graceful restart
        Reference: https://render.com/docs/background-workers
        """
        if not self.is_render:
            return
            
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum} - preparing for restart")
            # Render will restart the process
            sys.exit(0)
            
        # Handle SIGTERM (Render sends this before restart)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Handle SIGINT for manual interruption
        signal.signal(signal.SIGINT, signal_handler)
        
    def get_restart_status(self) -> dict:
        """Get current restart status for monitoring"""
        return {
            'is_render': self.is_render,
            'restart_count': self.restart_count,
            'max_restarts': self.max_restarts,
            'last_restart_time': self.last_restart_time.isoformat() if self.last_restart_time else None,
            'restart_window_hours': self.restart_window.total_seconds() / 3600
        }
        
    def reset_restart_count(self) -> None:
        """Reset restart count (for manual intervention)"""
        self.restart_count = 0
        self.last_restart_time = None
        self.logger.info("Restart count reset")