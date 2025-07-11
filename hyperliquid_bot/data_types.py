"""
Common data types for the Hyperliquid Trading Bot
Shared classes and structures used across multiple modules
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Candle:
    """OHLCV candle data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Signal:
    """Trading signal representation"""
    action: str  # 'BUY', 'SELL', 'HOLD'
    price: float
    timestamp: datetime
    confidence: float
    reason: str
    # Stochastic RSI fields (optional)
    stoch_rsi_value: Optional[float] = None
    rsi_value: Optional[float] = None
    # MACD fields (optional)
    macd_value: Optional[float] = None
    signal_value: Optional[float] = None
    histogram_value: Optional[float] = None


@dataclass
class MarketData:
    """Market data snapshot"""
    symbol: str
    price: float
    bid: float
    ask: float
    volume_24h: float
    timestamp: datetime