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
    stoch_rsi_value: float
    rsi_value: float
    confidence: float
    reason: str


@dataclass
class MarketData:
    """Market data snapshot"""
    symbol: str
    price: float
    bid: float
    ask: float
    volume_24h: float
    timestamp: datetime