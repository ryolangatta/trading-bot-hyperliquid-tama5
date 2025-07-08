"""
ROI plotting utilities for Hyperliquid Trading Bot
Generates ROI performance charts for Discord notifications
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
from io import BytesIO
import json
from pathlib import Path


class ROIPlotter:
    """Generates ROI performance charts and analytics"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.roi_file = Path(config.roi_file)
        
    def generate_roi_plot(self, trade_history: List[Dict] = None, time_period: str = "24h") -> Optional[bytes]:
        """
        Generate ROI plot as PNG bytes
        
        Args:
            trade_history: List of trade dictionaries
            time_period: Time period to plot ("24h", "7d", "30d", "all")
            
        Returns:
            PNG image bytes or None if no data
        """
        try:
            # Load ROI data from file if not provided
            if trade_history is None:
                trade_history = self._load_roi_history()
                
            if not trade_history:
                self.logger.warning("No trade history available for ROI plot")
                return None
                
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(trade_history)
            
            # Ensure timestamp column is datetime
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            elif 'exit_time' in df.columns:
                df['timestamp'] = pd.to_datetime(df['exit_time'])
            else:
                self.logger.error("No timestamp column found in trade history")
                return None
                
            # Filter by time period
            df = self._filter_by_period(df, time_period)
            
            if df.empty:
                self.logger.warning(f"No data for period: {time_period}")
                return None
                
            # Calculate cumulative ROI
            df = self._calculate_cumulative_roi(df)
            
            # Generate the plot
            return self._create_roi_chart(df, time_period)
            
        except Exception as e:
            self.logger.error(f"Error generating ROI plot: {e}")
            return None
            
    def _load_roi_history(self) -> List[Dict]:
        """Load ROI history from file"""
        try:
            if self.roi_file.exists():
                with open(self.roi_file, 'r') as f:
                    data = json.load(f)
                    return data.get('trades', [])
            return []
        except Exception as e:
            self.logger.error(f"Error loading ROI history: {e}")
            return []
            
    def _filter_by_period(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        """Filter dataframe by time period"""
        now = datetime.now()
        
        if period == "24h":
            start_time = now - timedelta(hours=24)
        elif period == "7d":
            start_time = now - timedelta(days=7)
        elif period == "30d":
            start_time = now - timedelta(days=30)
        elif period == "all":
            return df
        else:
            start_time = now - timedelta(hours=24)  # Default to 24h
            
        return df[df['timestamp'] >= start_time]
        
    def _calculate_cumulative_roi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate cumulative ROI from trades"""
        initial_balance = self.config.position_size_percent * 100000  # Assuming $100k account
        
        # Sort by timestamp
        df = df.sort_values('timestamp')
        
        # Calculate cumulative PnL
        if 'pnl' in df.columns:
            df['cumulative_pnl'] = df['pnl'].cumsum()
        else:
            # If no PnL, try to calculate from ROI
            df['cumulative_pnl'] = 0
            
        # Include fees in calculation
        if 'fees' in df.columns:
            df['cumulative_pnl'] -= df['fees'].cumsum()
            
        # Calculate cumulative ROI percentage
        df['cumulative_roi'] = (df['cumulative_pnl'] / initial_balance) * 100
        
        return df
        
    def _create_roi_chart(self, df: pd.DataFrame, period: str) -> bytes:
        """Create the actual ROI chart"""
        # Set up the plot style
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot cumulative ROI
        ax.plot(df['timestamp'], df['cumulative_roi'], 
                linewidth=2.5, color='#00ff00', label='Cumulative ROI')
        
        # Fill area under curve
        ax.fill_between(df['timestamp'], df['cumulative_roi'], 
                       alpha=0.3, color='#00ff00')
        
        # Add zero line
        ax.axhline(y=0, color='white', linestyle='--', alpha=0.5)
        
        # Highlight positive/negative regions
        ax.fill_between(df['timestamp'], 0, df['cumulative_roi'],
                       where=(df['cumulative_roi'] >= 0),
                       color='green', alpha=0.2, interpolate=True)
        ax.fill_between(df['timestamp'], 0, df['cumulative_roi'],
                       where=(df['cumulative_roi'] < 0),
                       color='red', alpha=0.2, interpolate=True)
        
        # Format the plot
        ax.set_title(f'ROI Performance - Last {period}', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('ROI (%)', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis dates
        if period == "24h":
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
        elif period == "7d":
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator())
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
            
        plt.xticks(rotation=45)
        
        # Add statistics box
        current_roi = df['cumulative_roi'].iloc[-1] if not df.empty else 0
        max_roi = df['cumulative_roi'].max() if not df.empty else 0
        min_roi = df['cumulative_roi'].min() if not df.empty else 0
        trades_count = len(df)
        
        stats_text = f'Current: {current_roi:.2f}%\nMax: {max_roi:.2f}%\nMin: {min_roi:.2f}%\nTrades: {trades_count}'
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='black', alpha=0.8))
        
        # Add current ROI annotation
        if not df.empty:
            last_point = df.iloc[-1]
            color = 'green' if current_roi >= 0 else 'red'
            ax.annotate(f'{current_roi:.2f}%',
                       xy=(last_point['timestamp'], last_point['cumulative_roi']),
                       xytext=(10, 10), textcoords='offset points',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor=color, alpha=0.7),
                       fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        
        # Save to bytes
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', 
                   facecolor='#1a1a1a', edgecolor='none')
        buffer.seek(0)
        chart_bytes = buffer.read()
        buffer.close()
        plt.close()
        
        return chart_bytes
        
    def generate_performance_report(self, trade_history: List[Dict]) -> Dict[str, float]:
        """Generate performance statistics"""
        if not trade_history:
            return {
                'total_roi': 0.0,
                'sharpe_ratio': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'max_drawdown': 0.0,
                'total_trades': 0
            }
            
        df = pd.DataFrame(trade_history)
        
        # Calculate metrics
        total_trades = len(df)
        winning_trades = len(df[df['pnl'] > 0]) if 'pnl' in df.columns else 0
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        if 'pnl' in df.columns:
            total_pnl = df['pnl'].sum()
            total_fees = df['fees'].sum() if 'fees' in df.columns else 0
            net_pnl = total_pnl - total_fees
            
            # Calculate profit factor
            gross_profit = df[df['pnl'] > 0]['pnl'].sum() if len(df[df['pnl'] > 0]) > 0 else 0
            gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum()) if len(df[df['pnl'] < 0]) > 0 else 1
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            # Simple Sharpe ratio calculation (annualized)
            if len(df) > 1 and 'roi' in df.columns:
                returns = df['roi'].values
                sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0
            else:
                sharpe = 0
                
            # Max drawdown calculation
            cumsum = df['pnl'].cumsum()
            running_max = cumsum.expanding().max()
            drawdown = (cumsum - running_max) / running_max * 100
            max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0
            
            # Total ROI
            initial_balance = self.config.position_size_percent * 100000
            total_roi = (net_pnl / initial_balance * 100) if initial_balance > 0 else 0
            
        else:
            total_roi = 0
            sharpe = 0
            profit_factor = 0
            max_drawdown = 0
            
        return {
            'total_roi': total_roi,
            'sharpe_ratio': sharpe,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'total_trades': total_trades
        }