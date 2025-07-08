"""
Discord command listener for manual trading signals
Implements webhook-based command processing for the trading bot
"""

import json
import logging
import asyncio
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
import aiohttp
from aiohttp import web
import hashlib
import hmac


@dataclass
class ManualSignal:
    """Manual trading signal from Discord"""
    command: str  # 'BUY' or 'SELL'
    symbol: str
    user_id: str
    username: str
    timestamp: datetime
    processed: bool = False


class DiscordCommandListener:
    """Listens for Discord commands via webhook and creates manual signals"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Manual signal queue
        self.signal_queue: List[ManualSignal] = []
        self.processed_signals: List[ManualSignal] = []
        
        # Authorized users (loaded from config)
        self.authorized_users = self._load_authorized_users()
        
        # Webhook server
        self.app = web.Application()
        self.runner = None
        self.site = None
        
        # Discord webhook secret for verification (optional)
        self.webhook_secret = os.getenv('DISCORD_WEBHOOK_SECRET', '')
        
        # Setup routes
        self._setup_routes()
        
        self.logger.info("Discord command listener initialized")
        
    def _load_authorized_users(self) -> List[str]:
        """Load authorized Discord user IDs from environment"""
        users_str = os.getenv('DISCORD_AUTHORIZED_USERS', '')
        if not users_str:
            self.logger.warning("No authorized users configured - commands will be rejected")
            return []
            
        users = [u.strip() for u in users_str.split(',') if u.strip()]
        self.logger.info(f"Loaded {len(users)} authorized users")
        return users
        
    def _setup_routes(self):
        """Setup webhook routes"""
        self.app.router.add_post('/discord/commands', self.handle_discord_command)
        self.app.router.add_get('/health', self.health_check)
        
    async def start_server(self, host: str = '0.0.0.0', port: int = 8080):
        """Start the webhook server"""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, host, port)
            await self.site.start()
            self.logger.info(f"Discord command listener started on {host}:{port}")
        except Exception as e:
            self.logger.error(f"Failed to start webhook server: {e}")
            raise
            
    async def stop_server(self):
        """Stop the webhook server"""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            self.logger.info("Discord command listener stopped")
        except Exception as e:
            self.logger.error(f"Error stopping webhook server: {e}")
            
    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({'status': 'ok', 'timestamp': datetime.now().isoformat()})
        
    async def handle_discord_command(self, request):
        """Handle incoming Discord command webhook"""
        try:
            # Verify webhook signature if secret is configured
            if self.webhook_secret:
                signature = request.headers.get('X-Discord-Signature')
                if not self._verify_signature(await request.read(), signature):
                    return web.json_response({'error': 'Invalid signature'}, status=401)
                    
            # Parse webhook data
            data = await request.json()
            
            # Extract command data
            # This assumes a Discord bot or webhook that sends commands in a specific format
            # Adjust based on your Discord integration setup
            user_id = data.get('user_id', '')
            username = data.get('username', 'Unknown')
            content = data.get('content', '').strip().upper()
            
            # Check authorization
            if user_id not in self.authorized_users:
                self.logger.warning(f"Unauthorized command from user {username} ({user_id})")
                return web.json_response({'error': 'Unauthorized'}, status=403)
                
            # Parse command
            parts = content.split()
            if len(parts) < 1:
                return web.json_response({'error': 'Invalid command format'}, status=400)
                
            command = parts[0]
            
            # Validate command
            if command not in ['BUY', 'SELL']:
                return web.json_response({'error': 'Invalid command. Use BUY or SELL'}, status=400)
                
            # Create manual signal
            signal = ManualSignal(
                command=command,
                symbol=self.config.symbol,  # Use configured symbol
                user_id=user_id,
                username=username,
                timestamp=datetime.now()
            )
            
            # Add to queue
            self.signal_queue.append(signal)
            self.logger.info(f"Manual {command} signal queued from {username}")
            
            # Send response
            return web.json_response({
                'status': 'success',
                'message': f'{command} signal queued for {self.config.symbol}',
                'signal_id': len(self.signal_queue)
            })
            
        except Exception as e:
            self.logger.error(f"Error handling Discord command: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
            
    def _verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify Discord webhook signature"""
        if not self.webhook_secret or not signature:
            return True  # Skip verification if not configured
            
        expected_sig = hmac.new(
            self.webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_sig, signature)
        
    def get_pending_signal(self) -> Optional[ManualSignal]:
        """Get next pending manual signal"""
        for signal in self.signal_queue:
            if not signal.processed:
                return signal
        return None
        
    def mark_signal_processed(self, signal: ManualSignal):
        """Mark a signal as processed"""
        signal.processed = True
        self.processed_signals.append(signal)
        
        # Keep only last 100 processed signals
        if len(self.processed_signals) > 100:
            self.processed_signals = self.processed_signals[-100:]
            
        # Remove from queue
        if signal in self.signal_queue:
            self.signal_queue.remove(signal)
            
    def get_signal_stats(self) -> Dict[str, Any]:
        """Get statistics about manual signals"""
        return {
            'pending_signals': len([s for s in self.signal_queue if not s.processed]),
            'processed_signals': len(self.processed_signals),
            'last_signal': self.processed_signals[-1].timestamp.isoformat() if self.processed_signals else None
        }


# Alternative: Direct Discord webhook integration (no separate server)
class DiscordWebhookCommands:
    """Simple Discord webhook command processor using polling"""
    
    def __init__(self, config, discord_notifier):
        self.config = config
        self.discord_notifier = discord_notifier
        self.logger = logging.getLogger(__name__)
        
        # Manual signal queue
        self.signal_queue: List[ManualSignal] = []
        
        # Authorized users
        self.authorized_users = self._load_authorized_users()
        
        # Command channel webhook URL (separate from notification webhook)
        self.command_webhook_url = os.getenv('DISCORD_COMMAND_WEBHOOK_URL', '')
        
        self.logger.info("Discord webhook command processor initialized")
        
    def _load_authorized_users(self) -> List[str]:
        """Load authorized Discord user IDs from environment"""
        import os
        users_str = os.getenv('DISCORD_AUTHORIZED_USERS', '')
        if not users_str:
            self.logger.warning("No authorized users configured - manual commands disabled")
            return []
            
        users = [u.strip() for u in users_str.split(',') if u.strip()]
        self.logger.info(f"Loaded {len(users)} authorized users for manual commands")
        return users
        
    async def send_command_prompt(self):
        """Send a message to Discord showing available commands"""
        if not self.command_webhook_url:
            return
            
        message = {
            "embeds": [{
                "title": "🤖 Manual Trading Commands Available",
                "description": "Authorized users can send manual trading signals:",
                "color": 0x0099FF,
                "fields": [
                    {
                        "name": "Commands",
                        "value": "• **BUY** - Open a long position\n• **SELL** - Close current position",
                        "inline": False
                    },
                    {
                        "name": "Usage",
                        "value": "Simply type `BUY` or `SELL` in this channel",
                        "inline": False
                    },
                    {
                        "name": "Status",
                        "value": f"Symbol: {self.config.symbol}\nMode: {'LIVE' if not self.config.dry_run else 'DRY RUN'}",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "Only authorized users can execute commands"
                }
            }]
        }
        
        async with aiohttp.ClientSession() as session:
            await session.post(self.command_webhook_url, json=message)
            
    def queue_manual_signal(self, command: str, user_id: str, username: str) -> bool:
        """Queue a manual signal for processing"""
        if user_id not in self.authorized_users:
            self.logger.warning(f"Unauthorized manual command from {username} ({user_id})")
            return False
            
        signal = ManualSignal(
            command=command.upper(),
            symbol=self.config.symbol,
            user_id=user_id,
            username=username,
            timestamp=datetime.now()
        )
        
        self.signal_queue.append(signal)
        self.logger.info(f"Manual {command} signal queued from {username}")
        return True
        
    def get_pending_signal(self) -> Optional[ManualSignal]:
        """Get next pending manual signal"""
        if self.signal_queue:
            return self.signal_queue[0]
        return None
        
    def remove_signal(self, signal: ManualSignal):
        """Remove processed signal from queue"""
        if signal in self.signal_queue:
            self.signal_queue.remove(signal)


import os  # Add this import at the top of the file