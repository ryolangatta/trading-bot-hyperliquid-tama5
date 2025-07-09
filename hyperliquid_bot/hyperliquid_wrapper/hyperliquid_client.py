"""
Hyperliquid API client wrapper using official hyperliquid-python-sdk
Handles authentication, order execution, and market data

References:
- Official SDK: https://github.com/hyperliquid-dex/hyperliquid-python-sdk
- API Documentation: https://hyperliquid.gitbook.io/hyperliquid-docs
"""

import logging
import asyncio
import time
import random
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import aiohttp

# Import common data types
from data_types import Candle, MarketData


class ErrorType(Enum):
    """Classification of error types for retry logic"""
    TRANSIENT = "transient"        # Temporary errors that should be retried
    PERMANENT = "permanent"        # Permanent errors that should not be retried
    RATE_LIMIT = "rate_limit"      # Rate limit errors requiring backoff
    NETWORK = "network"            # Network connectivity errors
    AUTHENTICATION = "auth"        # Authentication errors
    

class RetryConfig:
    """Configuration for retry logic"""
    def __init__(self, config):
        self.max_retries = config.retry_attempts
        self.base_delay = config.retry_delay
        self.max_delay = 60.0  # Maximum delay of 60 seconds
        self.jitter_factor = 0.1  # 10% jitter
        self.backoff_multiplier = 2.0
        self.rate_limit_delay = 10.0  # Extra delay for rate limits
        
        # Permanent error indicators
        self.permanent_errors = {
            "invalid_signature",
            "invalid_api_key", 
            "insufficient_funds",
            "invalid_symbol",
            "order_not_found",
            "unauthorized",
            "forbidden"
        }
        
        # Rate limit indicators
        self.rate_limit_errors = {
            "rate_limit_exceeded",
            "too_many_requests",
            "429"
        }


# Official Hyperliquid Python SDK imports
try:
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    from eth_account import Account
except ImportError as e:
    logging.error(f"Official hyperliquid-python-sdk not installed: {e}")
    logging.error("Please install with: pip install hyperliquid-python-sdk")
    raise


@dataclass
class OrderResult:
    """Order execution result"""
    success: bool
    order_id: Optional[str]
    error_message: Optional[str]
    filled_size: float
    filled_price: float
    fees: float


class HyperliquidClient:
    """
    Hyperliquid API client wrapper using official SDK
    
    References official documentation at:
    https://hyperliquid.gitbook.io/hyperliquid-docs
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.retry_config = RetryConfig(config)
        
        # Connection pooling for HTTP sessions
        self._session = None
        self._session_lock = asyncio.Lock()
        
        # Connection pool configuration
        self.connector_config = {
            'limit': 100,  # Total connection pool size
            'limit_per_host': 30,  # Max connections per host
            'ttl_dns_cache': 300,  # DNS cache TTL (5 minutes)
            'use_dns_cache': True,
            'keepalive_timeout': 60,  # Keep-alive timeout
            'enable_cleanup_closed': True
        }
        
        # Initialize official SDK components
        try:
            # Info client for market data (read-only)
            self.info = Info(base_url=self._get_base_url())
            
            # Exchange client for trading (requires wallet)
            if config.hyperliquid_private_key:
                self.logger.info(f"Private key provided: {'Yes' if config.hyperliquid_private_key else 'No'}")
                self.logger.info(f"Private key starts with 0x: {config.hyperliquid_private_key.startswith('0x') if config.hyperliquid_private_key else 'N/A'}")
                self.logger.info(f"Private key length: {len(config.hyperliquid_private_key) if config.hyperliquid_private_key else 0}")
                
                # Create wallet from private key
                try:
                    wallet = Account.from_key(config.hyperliquid_private_key)
                    self.logger.info(f"Wallet created successfully - Address: {wallet.address}")
                    self.exchange = Exchange(
                        wallet=wallet,
                        base_url=self._get_base_url(),
                        vault_address=config.hyperliquid_vault_address
                    )
                    self.logger.info("Exchange client initialized successfully")
                except Exception as e:
                    self.logger.error(f"Failed to create wallet from private key: {e}")
                    self.exchange = None
            else:
                self.logger.warning("No private key provided - trading will be disabled")
                self.exchange = None
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Hyperliquid SDK: {e}")
            raise
            
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
        
        self.logger.info(f"Hyperliquid client initialized with official SDK and connection pooling")
        self.logger.info(f"Environment: {'TESTNET' if config.testnet else 'MAINNET'}")
        
    def _get_base_url(self) -> Optional[str]:
        """Get base URL based on testnet/mainnet configuration"""
        if self.config.testnet:
            return constants.TESTNET_API_URL if hasattr(constants, 'TESTNET_API_URL') else None
        else:
            return constants.MAINNET_API_URL if hasattr(constants, 'MAINNET_API_URL') else None
            
    async def _rate_limit(self) -> None:
        """Apply rate limiting as per Hyperliquid documentation"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
            
        self.last_request_time = time.time()
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a reusable HTTP session with connection pooling"""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                # Create TCP connector with connection pooling
                connector = aiohttp.TCPConnector(**self.connector_config)
                
                # Create session with timeout configuration
                timeout = aiohttp.ClientTimeout(
                    total=30,  # Total timeout
                    connect=10,  # Connection timeout
                    sock_read=20  # Socket read timeout
                )
                
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers={
                        'User-Agent': 'Hyperliquid-Trading-Bot/5.0.0',
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }
                )
                
                self.logger.debug("Created new HTTP session with connection pooling")
                
            return self._session
        
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error for retry logic"""
        error_str = str(error).lower()
        
        # Check for permanent errors
        if any(perm_error in error_str for perm_error in self.retry_config.permanent_errors):
            return ErrorType.PERMANENT
            
        # Check for rate limit errors
        if any(rate_error in error_str for rate_error in self.retry_config.rate_limit_errors):
            return ErrorType.RATE_LIMIT
            
        # Check for authentication errors
        if any(auth_term in error_str for auth_term in ["auth", "signature", "key"]):
            return ErrorType.AUTHENTICATION
            
        # Check for network errors
        if any(net_term in error_str for net_term in ["timeout", "connection", "network", "dns"]):
            return ErrorType.NETWORK
            
        # Default to transient for retryable errors
        return ErrorType.TRANSIENT
        
    def _calculate_backoff_delay(self, attempt: int, error_type: ErrorType) -> float:
        """Calculate backoff delay with jitter"""
        base_delay = self.retry_config.base_delay
        
        # Add extra delay for rate limits
        if error_type == ErrorType.RATE_LIMIT:
            base_delay += self.retry_config.rate_limit_delay
            
        # Exponential backoff with jitter
        delay = base_delay * (self.retry_config.backoff_multiplier ** attempt)
        
        # Add jitter to prevent thundering herd
        jitter = delay * self.retry_config.jitter_factor * random.random()
        delay += jitter
        
        # Cap maximum delay
        delay = min(delay, self.retry_config.max_delay)
        
        return delay

    async def _execute_with_exponential_backoff(self, func, *args, **kwargs):
        """
        Production-grade exponential backoff with error classification
        """
        max_retries = self.retry_config.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                # Apply rate limiting
                await self._rate_limit()
                
                # Add timeout to prevent hanging
                timeout = 30.0  # 30 second timeout
                
                # Execute the function with timeout
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                else:
                    result = await asyncio.wait_for(
                        asyncio.create_task(asyncio.to_thread(func, *args, **kwargs)), 
                        timeout=timeout
                    )
                    
                return result
                
            except Exception as e:
                error_type = self._classify_error(e)
                
                # Don't retry permanent errors
                if error_type == ErrorType.PERMANENT:
                    self.logger.error(f"Permanent error in {func.__name__}: {e}")
                    raise
                
                # Don't retry authentication errors
                if error_type == ErrorType.AUTHENTICATION:
                    self.logger.error(f"Authentication error in {func.__name__}: {e}")
                    raise
                
                # Max retries reached
                if attempt == max_retries:
                    self.logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}")
                    raise
                    
                # Calculate delay with jitter
                delay = self._calculate_backoff_delay(attempt, error_type)
                
                self.logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__} "
                    f"(Error: {error_type.value}): {e}. Retrying in {delay:.2f}s..."
                )
                
                await asyncio.sleep(delay)
                
    async def get_market_data(self, symbol: str) -> MarketData:
        """
        Get current market data for symbol using official SDK
        Reference: https://hyperliquid.gitbook.io/hyperliquid-docs
        """
        try:
            async def _get_data():
                # Get all mids (current prices) - convert to async
                all_mids = await asyncio.to_thread(self.info.all_mids)
                
                if symbol not in all_mids:
                    raise ValueError(f"Symbol {symbol} not found in market data")
                    
                current_price = float(all_mids[symbol])
                
                # Get 24h volume data - convert to async
                meta = await asyncio.to_thread(self.info.meta)
                volume_24h = 0.0
                
                # Find symbol in meta data for volume
                for universe_item in meta.get('universe', []):
                    if universe_item.get('name') == symbol:
                        volume_24h = float(universe_item.get('dayNtlVlm', 0))
                        break
                        
                # Get orderbook for bid/ask - convert to async
                book = await asyncio.to_thread(self.info.l2_snapshot, symbol)
                # levels[0] = asks (higher prices), levels[1] = bids (lower prices)
                bid = float(book['levels'][1][0]['px']) if book['levels'][1] else current_price
                ask = float(book['levels'][0][0]['px']) if book['levels'][0] else current_price
                
                return MarketData(
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.now(),
                    bid=bid,
                    ask=ask,
                    volume_24h=volume_24h
                )
                
            return await self._execute_with_exponential_backoff(_get_data)
            
        except Exception as e:
            self.logger.error(f"Failed to get market data for {symbol}: {e}")
            raise
            
    async def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get historical candle data using official SDK
        Reference: https://hyperliquid.gitbook.io/hyperliquid-docs
        """
        try:
            async def _get_candles():
                # Convert timeframe to SDK format
                interval_map = {
                    '1m': '1m',
                    '5m': '5m',
                    '15m': '15m',
                    '30m': '30m',
                    '1h': '1h',
                    '4h': '4h',
                    '1d': '1d'
                }
                
                sdk_interval = interval_map.get(timeframe, '30m')
                
                # Calculate start time for requested number of candles
                end_time = int(datetime.now().timestamp() * 1000)
                
                # Get candle snapshot - convert to async
                candle_data = await asyncio.to_thread(
                    self.info.candle_snapshot,
                    coin=symbol,
                    interval=sdk_interval,
                    startTime=end_time - (limit * self._get_interval_ms(timeframe)),
                    endTime=end_time
                )
                
                candles = []
                for candle in candle_data:
                    candles.append({
                        'timestamp': datetime.fromtimestamp(candle['t'] / 1000),
                        'open': float(candle['o']),
                        'high': float(candle['h']),
                        'low': float(candle['l']),
                        'close': float(candle['c']),
                        'volume': float(candle['v'])
                    })
                    
                return candles
                
            return await self._execute_with_exponential_backoff(_get_candles)
            
        except Exception as e:
            self.logger.error(f"Failed to get candles for {symbol}: {e}")
            raise
            
    def _get_interval_ms(self, timeframe: str) -> int:
        """Convert timeframe to milliseconds"""
        intervals = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000
        }
        return intervals.get(timeframe, 30 * 60 * 1000)
        
    async def place_order(self, 
                         symbol: str, 
                         side: str, 
                         size: float, 
                         price: Optional[float] = None,
                         order_type: str = 'limit',
                         time_in_force: str = 'GTC') -> OrderResult:
        """
        Place an order using official SDK
        Reference: https://hyperliquid.gitbook.io/hyperliquid-docs
        """
        try:
            if self.config.dry_run:
                # Simulate order execution in dry run mode
                self.logger.info(f"DRY RUN: {side} {size} {symbol} @ ${price if price else 'market'}")
                return OrderResult(
                    success=True,
                    order_id=f"dry_run_{int(time.time())}",
                    error_message=None,
                    filled_size=size,
                    filled_price=price or 0,
                    fees=size * 0.0002  # Estimate fees
                )
                
            if not self.exchange:
                raise ValueError("Exchange client not initialized - missing private key")
                
            async def _place_order():
                # Import required types
                from hyperliquid.utils.signing import OrderType
                
                # Place order using official SDK with correct parameters
                is_buy = side.lower() == 'buy'
                sz = size
                limit_px = price
                
                # Create proper OrderType structure based on order_type
                if order_type.lower() == 'limit':
                    # Convert time_in_force to proper format
                    tif_map = {
                        'GTC': 'Gtc',  # Good till canceled
                        'IOC': 'Ioc',  # Immediate or cancel  
                        'ALO': 'Alo'   # Add liquidity only
                    }
                    tif = tif_map.get(time_in_force.upper(), 'Gtc')
                    order_type_obj = {"limit": {"tif": tif}}
                else:
                    # For market orders or other types, use trigger with market
                    order_type_obj = {"trigger": {"isMarket": True, "tpsl": "tp"}}
                
                # Use the correct SDK method signature
                result = await asyncio.to_thread(
                    self.exchange.order,
                    symbol,       # name (asset symbol)
                    is_buy,       # is_buy
                    sz,           # sz (size)
                    limit_px,     # limit_px (price)
                    order_type_obj, # order_type (OrderType structure)
                    False,        # reduce_only (default False)
                    None,         # cloid (client order ID, optional)
                    None          # builder (builder info, optional)
                )
                
                # Log the raw result for debugging
                self.logger.info(f"Order result type: {type(result)}, value: {result}")
                
                # Handle different response formats
                if isinstance(result, dict):
                    if result.get('status') == 'ok':
                        response_data = result.get('response', {}).get('data', {})
                        
                        return OrderResult(
                            success=True,
                            order_id=response_data.get('oid'),
                            error_message=None,
                            filled_size=float(response_data.get('totalSz', 0)),
                            filled_price=float(response_data.get('avgPx', 0)),
                            fees=float(response_data.get('fee', 0))
                        )
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        return OrderResult(
                            success=False,
                            order_id=None,
                            error_message=error_msg,
                            filled_size=0,
                            filled_price=0,
                            fees=0
                        )
                elif isinstance(result, str):
                    # Handle string response (might be an error message)
                    return OrderResult(
                        success=False,
                        order_id=None,
                        error_message=f"SDK returned string: {result}",
                        filled_size=0,
                        filled_price=0,
                        fees=0
                    )
                else:
                    return OrderResult(
                        success=False,
                        order_id=None,
                        error_message=f"Unexpected response type: {type(result)}",
                        filled_size=0,
                        filled_price=0,
                        fees=0
                    )
                    
            return await self._execute_with_exponential_backoff(_place_order)
            
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                error_message=str(e),
                filled_size=0,
                filled_price=0,
                fees=0
            )
            
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order using official SDK
        Reference: https://hyperliquid.gitbook.io/hyperliquid-docs
        """
        try:
            if not self.exchange:
                raise ValueError("Exchange client not initialized")
                
            async def _cancel_order():
                cancel_request = {
                    'coin': symbol,
                    'oid': order_id
                }
                
                result = await asyncio.to_thread(self.exchange.cancel, cancel_request)
                return result and result.get('status') == 'ok'
                
            return await self._execute_with_exponential_backoff(_cancel_order)
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
            
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current position for symbol using official SDK
        Reference: https://hyperliquid.gitbook.io/hyperliquid-docs
        """
        try:
            async def _get_position():
                user_state = await asyncio.to_thread(
                    self.info.user_state,
                    self.config.hyperliquid_vault_address or self.exchange.wallet.address
                )
                
                # Look for position in asset positions
                for position in user_state.get('assetPositions', []):
                    pos_data = position.get('position', {})
                    if pos_data.get('coin') == symbol:
                        return {
                            'symbol': symbol,
                            'size': float(pos_data.get('szi', 0)),
                            'entry_price': float(pos_data.get('entryPx', 0)),
                            'unrealized_pnl': float(pos_data.get('unrealizedPnl', 0)),
                            'leverage': float(pos_data.get('leverage', {}).get('value', 0))
                        }
                        
                return None
                
            return await self._execute_with_exponential_backoff(_get_position)
            
        except Exception as e:
            self.logger.error(f"Failed to get position for {symbol}: {e}")
            return None
            
    async def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information using official SDK
        Reference: https://hyperliquid.gitbook.io/hyperliquid-docs
        """
        try:
            async def _get_account():
                # Use main wallet address for queries, not API wallet address
                query_address = (
                    self.config.hyperliquid_vault_address or 
                    self.config.hyperliquid_main_address or 
                    self.exchange.wallet.address
                )
                self.logger.info(f"Querying account info for address: {query_address}")
                
                user_state = await asyncio.to_thread(
                    self.info.user_state,
                    query_address
                )
                
                margin_summary = user_state.get('marginSummary', {})
                
                # Calculate available balance correctly
                account_value = float(margin_summary.get('accountValue', 0))
                total_margin_used = float(margin_summary.get('totalMarginUsed', 0))
                available_balance = max(0, account_value - total_margin_used)
                
                return {
                    'balance': account_value,
                    'available_balance': available_balance,
                    'total_margin_used': total_margin_used,
                    'positions': len(user_state.get('assetPositions', []))
                }
                
            return await self._execute_with_exponential_backoff(_get_account)
            
        except Exception as e:
            self.logger.error(f"Failed to get account info: {e}")
            self.logger.error(f"Error type: {type(e).__name__}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            return {}
            
    async def health_check(self) -> bool:
        """
        Check API connectivity using official SDK
        Reference: https://hyperliquid.gitbook.io/hyperliquid-docs
        """
        try:
            async def _health_check():
                # Simple connectivity test using meta endpoint - convert to async
                meta = await asyncio.to_thread(self.info.meta)
                return 'universe' in meta
                
            return await self._execute_with_exponential_backoff(_health_check)
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
            
    async def connect(self) -> None:
        """Initialize connection and session pooling"""
        try:
            # Pre-initialize the session
            session = await self._get_session()
            self.logger.info("Hyperliquid client connected using official SDK with connection pooling")
        except Exception as e:
            self.logger.error(f"Failed to initialize connection: {e}")
            raise
        
    async def disconnect(self) -> None:
        """Close connection and cleanup resources"""
        try:
            # Close HTTP session and cleanup connection pool
            async with self._session_lock:
                if self._session and not self._session.closed:
                    await self._session.close()
                    self._session = None
                    self.logger.debug("HTTP session closed and connection pool cleaned up")
            
            # Cleanup any open connections/sessions
            if hasattr(self, 'exchange') and self.exchange:
                # SDK cleanup if available
                pass
                
            if hasattr(self, 'info') and self.info:
                # Info client cleanup if available
                pass
                
            self.logger.info("Hyperliquid client disconnected and resources cleaned up")
            
        except Exception as e:
            self.logger.error(f"Error during client disconnect: {e}")
            
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with guaranteed cleanup"""
        await self.disconnect()
        
    def __del__(self):
        """Cleanup on garbage collection"""
        try:
            # Best effort cleanup
            if hasattr(self, '_session') and self._session and not self._session.closed:
                # Can't await in __del__, so just close without cleanup
                import warnings
                warnings.warn("HTTP session not properly closed, use async context manager")
                
            if hasattr(self, 'exchange'):
                del self.exchange
            if hasattr(self, 'info'):
                del self.info
        except:
            pass
        
    async def get_candle_data(self, symbol: str, timeframe: str, count: int = 100) -> List:
        """Get historical candle data"""
        try:
            async def _get_candles():
                # Get current time in milliseconds for endTime
                import time
                end_time = int(time.time() * 1000)
                
                # Convert timeframe to interval (30m -> 30m, 1h -> 1h, etc.) - convert to async
                candles = await asyncio.to_thread(self.info.candles_snapshot, symbol, timeframe, end_time, count)
                
                result = []
                
                for candle_data in candles:
                    candle = Candle(
                        timestamp=datetime.fromtimestamp(candle_data['t'] / 1000),
                        open=float(candle_data['o']),
                        high=float(candle_data['h']),
                        low=float(candle_data['l']),
                        close=float(candle_data['c']),
                        volume=float(candle_data['v'])
                    )
                    result.append(candle)
                    
                return result
                
            return await self._execute_with_exponential_backoff(_get_candles)
            
        except Exception as e:
            self.logger.error(f"Failed to get candle data for {symbol}: {e}")
            return []