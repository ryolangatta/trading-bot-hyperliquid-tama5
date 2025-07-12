"""
Discord webhook notifications for Hyperliquid Trading Bot
Sends status updates, trade alerts, and ROI graphs
"""

import json
import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dataclasses import dataclass
from collections import deque
import time


@dataclass
class NotificationMessage:
    """Discord notification message"""
    title: str
    description: str
    color: int
    fields: Dict[str, Any] = None
    image_data: bytes = None


class DiscordNotifier:
    """Handles Discord webhook notifications with strict rate limiting"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.webhook_url = config.discord_webhook_url
        
        # Status tracking - bot status updates with ROI graphs every 10 minutes
        self.last_status_update = datetime.now()
        
        # Discord rate limiting (30 requests per minute)
        self.rate_limit_window = 60  # seconds
        self.max_requests_per_window = 30
        self.request_timestamps = deque(maxlen=self.max_requests_per_window)
        self.rate_limit_lock = asyncio.Lock()
        
        # Retry and backoff configuration
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 60.0
        
        # Colors for different message types
        self.colors = {
            'success': 0x00FF00,   # Green
            'error': 0xFF0000,     # Red
            'warning': 0xFFFF00,   # Yellow
            'info': 0x0099FF,      # Blue
            'trade': 0xFF9900,     # Orange
            'roi': 0x9900FF        # Purple
        }
        
        if not self.webhook_url:
            self.logger.warning("Discord webhook URL not configured")
        else:
            self.logger.info("Discord notifier initialized with rate limiting")
            
    async def _enforce_rate_limit(self) -> None:
        """Enforce Discord rate limiting (30 requests per minute)"""
        async with self.rate_limit_lock:
            current_time = time.time()
            
            # Remove timestamps older than the rate limit window
            while self.request_timestamps and (current_time - self.request_timestamps[0]) > self.rate_limit_window:
                self.request_timestamps.popleft()
            
            # Check if we've hit the rate limit
            if len(self.request_timestamps) >= self.max_requests_per_window:
                # Calculate wait time until the oldest request expires
                oldest_request = self.request_timestamps[0]
                wait_time = self.rate_limit_window - (current_time - oldest_request)
                
                if wait_time > 0:
                    self.logger.warning(f"Discord rate limit reached, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    
                    # Clean up expired timestamps after waiting
                    current_time = time.time()
                    while self.request_timestamps and (current_time - self.request_timestamps[0]) > self.rate_limit_window:
                        self.request_timestamps.popleft()
            
            # Record this request timestamp
            self.request_timestamps.append(current_time)

    async def send_notification(self, message: NotificationMessage) -> bool:
        """Send notification to Discord with rate limiting and retries"""
        if not self.webhook_url:
            self.logger.warning("Discord webhook not configured - notification skipped")
            return False
        
        for attempt in range(self.max_retries):
            try:
                # Enforce rate limiting before each request
                await self._enforce_rate_limit()
                
                embed = {
                    "title": message.title,
                    "description": message.description,
                    "color": message.color,
                    "timestamp": datetime.now().isoformat(),
                    "footer": {
                        "text": "Hyperliquid Trading Bot v5.2.0"
                    }
                }
                
                # Add fields if provided
                if message.fields:
                    embed["fields"] = []
                    for name, value in message.fields.items():
                        embed["fields"].append({
                            "name": name,
                            "value": str(value),
                            "inline": True
                        })
                        
                payload = {"embeds": [embed]}
                
                timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    # Send image if provided
                    if message.image_data:
                        # Create multipart data
                        data = aiohttp.FormData()
                        data.add_field('payload_json', json.dumps(payload))
                        data.add_field('file', message.image_data, filename='chart.png', content_type='image/png')
                        
                        async with session.post(self.webhook_url, data=data) as response:
                            if response.status == 204:
                                self.logger.debug("Discord notification sent successfully (with image)")
                                return True
                            elif response.status == 429:
                                # Rate limited by Discord
                                retry_after = int(response.headers.get('Retry-After', 60))
                                self.logger.warning(f"Discord rate limited, retry after {retry_after}s")
                                await asyncio.sleep(retry_after)
                                continue
                            else:
                                self.logger.error(f"Discord notification failed: {response.status}")
                                if attempt == self.max_retries - 1:
                                    return False
                    else:
                        # Send text-only message
                        async with session.post(self.webhook_url, json=payload) as response:
                            if response.status == 204:
                                self.logger.debug("Discord notification sent successfully")
                                return True
                            elif response.status == 429:
                                # Rate limited by Discord
                                retry_after = int(response.headers.get('Retry-After', 60))
                                self.logger.warning(f"Discord rate limited, retry after {retry_after}s")
                                await asyncio.sleep(retry_after)
                                continue
                            else:
                                self.logger.error(f"Discord notification failed: {response.status}")
                                if attempt == self.max_retries - 1:
                                    return False
                                
            except asyncio.TimeoutError:
                self.logger.warning(f"Discord notification timeout (attempt {attempt + 1})")
                if attempt == self.max_retries - 1:
                    return False
            except Exception as e:
                self.logger.error(f"Discord notification error (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    return False
            
            # Exponential backoff for retries
            if attempt < self.max_retries - 1:
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                await asyncio.sleep(delay)
        
        return False
            
    async def send_bot_status(self, status_data: Dict[str, Any]) -> None:
        """Send bot status update with ROI graph"""
        try:
            current_time = datetime.now()
            
            # Check if it's time for status update
            if (current_time - self.last_status_update).total_seconds() < self.config.discord_status_interval:
                return
                
            # Handle None values safely
            current_stoch_rsi = status_data.get('current_stoch_rsi')
            current_rsi = status_data.get('current_rsi')
            stoch_rsi_display = f"{current_stoch_rsi:.2f}" if current_stoch_rsi is not None else "Calculating..."
            rsi_display = f"{current_rsi:.2f}" if current_rsi is not None else "Calculating..."
            
            # Format wallet balance
            wallet_balance = status_data.get('wallet_balance', 0)
            available_balance = status_data.get('available_balance', 0)
            
            # Generate ROI chart if ROI data is available
            chart_data = None
            roi_fields = {}
            roi_data = status_data.get('roi_data')
            trade_history = status_data.get('trade_history', [])
            
            if roi_data and trade_history:
                chart_data = self._generate_roi_chart(roi_data, trade_history)
                
                # Add ROI summary fields to status
                total_roi = roi_data.get('total_roi', 0) or 0
                current_balance = roi_data.get('current_balance', 0) or 0
                win_rate = roi_data.get('win_rate', 0) or 0
                total_trades = roi_data.get('total_trades', 0) or 0
                
                roi_fields = {
                    "📈 Total ROI": f"{total_roi:.2f}%",
                    "🏆 Win Rate": f"{win_rate:.1f}%",
                    "📊 Total Trades": str(total_trades)
                }
            
            # Combine status fields with ROI fields
            fields = {
                "Status": "🟢 RUNNING" if status_data.get('running') else "🔴 STOPPED",
                "Mode": "📊 LIVE" if not self.config.dry_run else "🧪 DRY RUN",
                "Environment": "🌐 MAINNET" if not self.config.testnet else "🧪 TESTNET",
                "Strategy": status_data.get('strategy', 'N/A'),
                "Stochastic RSI": stoch_rsi_display,
                "RSI": rsi_display,
                "Position": "📈 LONG" if status_data.get('has_position') else "💰 NO POSITION",
                **roi_fields,  # Include ROI summary fields
                "Wallet Balance": f"${wallet_balance:,.2f} USDT",
                "Available": f"${available_balance:,.2f} USDT",
                "Uptime": self._format_duration(status_data.get('uptime_seconds', 0)),
                "Errors (1h)": status_data.get('recent_errors', 0),
                "Circuit Breaker": "🔴 ACTIVE" if status_data.get('circuit_breaker_active') else "🟢 INACTIVE"
            }
            
            message = NotificationMessage(
                title="🤖 Bot Status Update with ROI Graph",
                description=f"Hyperliquid Trading Bot Status & Performance - {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                color=self.colors['info'],
                fields=fields,
                image_data=chart_data  # Include ROI chart
            )
            
            await self.send_notification(message)
            self.last_status_update = current_time
            
        except Exception as e:
            self.logger.error(f"Failed to send bot status: {e}")
            
    async def send_trade_alert(self, trade_data: Dict[str, Any]) -> None:
        """Send trade execution alert"""
        try:
            action = trade_data.get('action', 'UNKNOWN')
            symbol = trade_data.get('symbol', 'UNKNOWN')
            price = trade_data.get('price', 0)
            size = trade_data.get('size', 0)
            pnl = trade_data.get('pnl', 0)
            
            if action == 'BUY':
                title = "🟢 LONG ENTRY"
                color = self.colors['success']
            elif action == 'SELL':
                title = "🔴 POSITION CLOSED"
                color = self.colors['trade']
            else:
                title = f"📊 {action}"
                color = self.colors['info']
                
            # Get wallet balance from trade data
            wallet_balance = trade_data.get('wallet_balance', 0)
            available_balance = trade_data.get('available_balance', 0)
            
            fields = {
                "Symbol": symbol,
                "Action": action,
                "Price": f"${price:.4f}",
                "Size": f"{size:.2f}",
                "Mode": "📊 LIVE" if not self.config.dry_run else "🧪 DRY RUN",
                "Wallet Balance": f"${wallet_balance:,.2f} USDT",
                "Available": f"${available_balance:,.2f} USDT"
            }
            
            if pnl != 0:
                fields["PnL"] = f"${pnl:.2f}"
                fields["ROI"] = f"{(pnl/1000)*100:.2f}%"  # Assuming $1000 base
                
            message = NotificationMessage(
                title=title,
                description=f"Trade executed on {symbol}",
                color=color,
                fields=fields
            )
            
            await self.send_notification(message)
            
        except Exception as e:
            self.logger.error(f"Failed to send trade alert: {e}")
            
    async def send_error_alert(self, error_data: Dict[str, Any]) -> None:
        """Send error alert"""
        try:
            error_type = error_data.get('error_type', 'UNKNOWN')
            message = error_data.get('message', 'Unknown error')
            severity = error_data.get('severity', 'ERROR')
            
            if severity == 'CRITICAL':
                color = self.colors['error']
                title = "🚨 CRITICAL ERROR"
            else:
                color = self.colors['warning']
                title = "⚠️ ERROR ALERT"
                
            fields = {
                "Error Type": error_type,
                "Severity": severity,
                "Time": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
                "Circuit Breaker": "🔴 ACTIVE" if error_data.get('circuit_breaker_active') else "🟢 INACTIVE"
            }
            
            message = NotificationMessage(
                title=title,
                description=message,
                color=color,
                fields=fields
            )
            
            await self.send_notification(message)
            
        except Exception as e:
            self.logger.error(f"Failed to send error alert: {e}")
            
    def _generate_roi_chart(self, roi_data: Dict[str, Any], trade_history: list) -> Optional[bytes]:
        """Generate ROI chart as PNG bytes"""
        try:
            if not trade_history:
                return None
                
            # Extract data for plotting
            dates = []
            cumulative_roi = []
            running_balance = roi_data.get('initial_balance', 1000.0)
            
            for trade in trade_history[-30:]:  # Last 30 trades
                dates.append(datetime.fromisoformat(trade['exit_time']))
                running_balance += trade['pnl'] - trade['fees']
                roi = (running_balance - roi_data.get('initial_balance', 1000.0)) / roi_data.get('initial_balance', 1000.0) * 100
                cumulative_roi.append(roi)
                
            if not dates:
                return None
                
            # Create chart
            plt.figure(figsize=(12, 6))
            plt.plot(dates, cumulative_roi, linewidth=2, color='#0099FF')
            plt.fill_between(dates, cumulative_roi, alpha=0.3, color='#0099FF')
            
            plt.title('Cumulative ROI Performance', fontsize=16, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('ROI (%)', fontsize=12)
            plt.grid(True, alpha=0.3)
            
            # Format x-axis
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=2))
            plt.xticks(rotation=45)
            
            # Add current ROI as annotation
            if cumulative_roi:
                plt.annotate(f'Current ROI: {cumulative_roi[-1]:.1f}%',
                           xy=(dates[-1], cumulative_roi[-1]),
                           xytext=(10, 10), textcoords='offset points',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                           fontsize=10, fontweight='bold')
            
            plt.tight_layout()
            
            # Save to bytes
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            chart_data = buffer.read()
            buffer.close()
            plt.close()
            
            return chart_data
            
        except Exception as e:
            self.logger.error(f"Failed to generate ROI chart: {e}")
            return None
            
    def _format_duration(self, seconds: int) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds//60}m {seconds%60}s"
        elif seconds < 86400:
            return f"{seconds//3600}h {(seconds%3600)//60}m"
        else:
            return f"{seconds//86400}d {(seconds%86400)//3600}h"