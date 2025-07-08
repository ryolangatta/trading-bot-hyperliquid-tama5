"""
State management for Hyperliquid Trading Bot
Handles persistence of positions, ROI, and trading state
"""

import json
import logging
import os
import fcntl
import tempfile
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from threading import Lock


@dataclass
class Position:
    """Current position information"""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    entry_time: datetime
    leverage: int
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class Trade:
    """Completed trade record"""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    fees: float
    roi: float


@dataclass
class ROIData:
    """ROI tracking data"""
    initial_balance: float
    current_balance: float
    total_pnl: float
    total_fees: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    max_drawdown: float
    max_drawdown_date: datetime
    last_updated: datetime


class StateManager:
    """Manages bot state persistence and recovery"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.lock = Lock()
        
        # File paths
        self.state_file = Path(config.state_file)
        self.roi_file = Path(config.roi_file)
        
        # Ensure directories exist
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.roi_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Current state
        self.current_position: Optional[Position] = None
        self.roi_data: Optional[ROIData] = None
        self.trades: List[Trade] = []
        
        # Load existing state
        self._load_state()
        self._load_roi_data()
        
        self.logger.info("State manager initialized")
        
    def _load_state(self) -> None:
        """Load state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    
                # Load current position
                if data.get('current_position'):
                    pos_data = data['current_position']
                    pos_data['entry_time'] = datetime.fromisoformat(pos_data['entry_time'])
                    self.current_position = Position(**pos_data)
                    
                # Load trades
                if data.get('trades'):
                    self.trades = []
                    for trade_data in data['trades']:
                        trade_data['entry_time'] = datetime.fromisoformat(trade_data['entry_time'])
                        trade_data['exit_time'] = datetime.fromisoformat(trade_data['exit_time'])
                        self.trades.append(Trade(**trade_data))
                        
                self.logger.info(f"State loaded: Position={self.current_position is not None}, Trades={len(self.trades)}")
                
        except Exception as e:
            self.logger.error(f"Failed to load state: {e}")
            
    def _load_roi_data(self) -> None:
        """Load ROI data from file"""
        try:
            if self.roi_file.exists():
                with open(self.roi_file, 'r') as f:
                    data = json.load(f)
                    
                data['max_drawdown_date'] = datetime.fromisoformat(data['max_drawdown_date'])
                data['last_updated'] = datetime.fromisoformat(data['last_updated'])
                self.roi_data = ROIData(**data)
                
                roi_pct = (self.roi_data.total_pnl/self.roi_data.initial_balance*100) if self.roi_data.initial_balance > 0 else 0.0
                self.logger.info(f"ROI data loaded: Balance=${self.roi_data.current_balance:.2f}, ROI={roi_pct:.2f}%")
                
        except Exception as e:
            self.logger.error(f"Failed to load ROI data: {e}")
            
    def save_state(self) -> None:
        """Save current state to file"""
        with self.lock:
            try:
                data = {
                    'current_position': asdict(self.current_position) if self.current_position else None,
                    'trades': [asdict(trade) for trade in self.trades],
                    'last_updated': datetime.now().isoformat()
                }
                
                # Convert datetime objects to ISO format
                if data['current_position']:
                    data['current_position']['entry_time'] = data['current_position']['entry_time'].isoformat()
                    
                for trade in data['trades']:
                    trade['entry_time'] = trade['entry_time'].isoformat()
                    trade['exit_time'] = trade['exit_time'].isoformat()
                    
                # Atomic write using temporary file with file locking
                state_dir = os.path.dirname(self.state_file)
                os.makedirs(state_dir, exist_ok=True)
                
                # Create temporary file with exclusive lock
                fd, temp_path = tempfile.mkstemp(dir=state_dir, suffix='.tmp')
                
                try:
                    with os.fdopen(fd, 'w') as temp_file:
                        # Apply exclusive lock to prevent concurrent access
                        fcntl.flock(temp_file.fileno(), fcntl.LOCK_EX)
                        
                        # Write data
                        json.dump(data, temp_file, indent=2)
                        temp_file.flush()
                        
                        # Force write to disk
                        os.fsync(temp_file.fileno())
                    
                    # Atomic move to final location
                    os.replace(temp_path, self.state_file)
                    temp_path = None  # Successfully moved
                    
                except Exception as e:
                    # Clean up temp file on error
                    if temp_path and os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise
                    
                self.logger.debug("State saved atomically")
                
            except Exception as e:
                self.logger.error(f"Failed to save state: {e}")
                # Clean up temp file if it exists
                temp_file = self.state_file + '.tmp'
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                
    def save_roi_data(self) -> None:
        """Save ROI data to file with atomic write and file locking"""
        with self.lock:
            try:
                if self.roi_data:
                    data = asdict(self.roi_data)
                    data['max_drawdown_date'] = data['max_drawdown_date'].isoformat()
                    data['last_updated'] = data['last_updated'].isoformat()
                    
                    # Atomic write using temporary file with file locking
                    roi_dir = os.path.dirname(self.roi_file)
                    os.makedirs(roi_dir, exist_ok=True)
                    
                    # Create temporary file with exclusive lock
                    fd, temp_path = tempfile.mkstemp(dir=roi_dir, suffix='.tmp')
                    
                    try:
                        with os.fdopen(fd, 'w') as temp_file:
                            # Apply exclusive lock to prevent concurrent access
                            fcntl.flock(temp_file.fileno(), fcntl.LOCK_EX)
                            
                            # Write data
                            json.dump(data, temp_file, indent=2)
                            temp_file.flush()
                            
                            # Force write to disk
                            os.fsync(temp_file.fileno())
                        
                        # Atomic move to final location
                        os.replace(temp_path, self.roi_file)
                        temp_path = None  # Successfully moved
                        
                    except Exception as e:
                        # Clean up temp file on error
                        if temp_path and os.path.exists(temp_path):
                            os.unlink(temp_path)
                        raise
                        
                    self.logger.debug("ROI data saved atomically")
                    
            except Exception as e:
                self.logger.error(f"Failed to save ROI data: {e}")
                
    def set_position(self, position: Optional[Position]) -> None:
        """Update current position"""
        with self.lock:
            self.current_position = position
            self.save_state()
            
            if position:
                self.logger.info(f"Position updated: {position.symbol} {position.side} {position.size} @ ${position.entry_price:.4f}")
            else:
                self.logger.info("Position cleared")
                
    def add_trade(self, trade: Trade) -> None:
        """Add completed trade"""
        with self.lock:
            self.trades.append(trade)
            self.save_state()
            
            # Update ROI data
            self.update_roi_data(trade)
            
            self.logger.info(f"Trade added: {trade.symbol} {trade.side} PnL=${trade.pnl:.2f} ROI={trade.roi:.2f}%")
            
    def update_roi_data(self, trade: Trade) -> None:
        """Update ROI data with new trade"""
        if not self.roi_data:
            # Initialize ROI data if first trade
            self.roi_data = ROIData(
                initial_balance=1000.0,  # Default starting balance
                current_balance=1000.0,
                total_pnl=0.0,
                total_fees=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                max_drawdown=0.0,
                max_drawdown_date=datetime.now(),
                last_updated=datetime.now()
            )
            
        # Update with trade data
        self.roi_data.current_balance += trade.pnl - trade.fees
        self.roi_data.total_pnl += trade.pnl
        self.roi_data.total_fees += trade.fees
        self.roi_data.total_trades += 1
        
        if trade.pnl > 0:
            self.roi_data.winning_trades += 1
        else:
            self.roi_data.losing_trades += 1
            
        # Update max drawdown
        current_drawdown = (self.roi_data.initial_balance - self.roi_data.current_balance) / self.roi_data.initial_balance
        if current_drawdown > self.roi_data.max_drawdown:
            self.roi_data.max_drawdown = current_drawdown
            self.roi_data.max_drawdown_date = datetime.now()
            
        self.roi_data.last_updated = datetime.now()
        self.save_roi_data()
        
    def get_current_position(self) -> Optional[Position]:
        """Get current position"""
        return self.current_position
        
    def get_roi_data(self) -> Optional[ROIData]:
        """Get ROI data"""
        return self.roi_data
        
    def get_recent_trades(self, days: int = 7) -> List[Trade]:
        """Get recent trades within specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return [trade for trade in self.trades if trade.exit_time >= cutoff_date]
        
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        if not self.roi_data:
            return {"status": "no_data"}
            
        total_roi = (self.roi_data.current_balance - self.roi_data.initial_balance) / self.roi_data.initial_balance * 100
        win_rate = (self.roi_data.winning_trades / self.roi_data.total_trades * 100) if self.roi_data.total_trades > 0 else 0
        
        return {
            "initial_balance": self.roi_data.initial_balance,
            "current_balance": self.roi_data.current_balance,
            "total_roi": total_roi,
            "total_pnl": self.roi_data.total_pnl,
            "total_fees": self.roi_data.total_fees,
            "total_trades": self.roi_data.total_trades,
            "winning_trades": self.roi_data.winning_trades,
            "losing_trades": self.roi_data.losing_trades,
            "win_rate": win_rate,
            "max_drawdown": self.roi_data.max_drawdown * 100,
            "max_drawdown_date": self.roi_data.max_drawdown_date.isoformat(),
            "last_updated": self.roi_data.last_updated.isoformat()
        }
        
    def reset_state(self) -> None:
        """Reset all state (for testing purposes)"""
        with self.lock:
            self.current_position = None
            self.roi_data = None
            self.trades = []
            
            # Delete state files
            if self.state_file.exists():
                self.state_file.unlink()
            if self.roi_file.exists():
                self.roi_file.unlink()
                
            self.logger.warning("State reset - all data cleared")