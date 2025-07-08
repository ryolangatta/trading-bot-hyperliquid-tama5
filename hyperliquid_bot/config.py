"""
Configuration management for Hyperliquid Trading Bot
Loads environment variables and provides validation
"""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    """Configuration class for the trading bot"""
    
    def __init__(self, env_file: str = '.env'):
        """Initialize configuration from environment file"""
        load_dotenv(env_file)
        
        # Trading configuration
        self.dry_run: bool = os.getenv('DRY_RUN', 'True').lower() == 'true'
        self.testnet: bool = os.getenv('TESTNET', 'True').lower() == 'true'
        self.leverage: int = int(os.getenv('LEVERAGE', '10'))
        
        # Hyperliquid API configuration
        self.hyperliquid_private_key: str = os.getenv('HYPERLIQUID_PRIVATE_KEY', '')
        self.hyperliquid_main_address: str = os.getenv('HYPERLIQUID_MAIN_ADDRESS', '')
        self.hyperliquid_vault_address: Optional[str] = os.getenv('HYPERLIQUID_VAULT_ADDRESS')
        
        # Strategy configuration
        self.strategy_name: str = os.getenv('STRATEGY_NAME', 'rsi_pengu')
        self.symbol: str = os.getenv('SYMBOL', 'LINK')
        self.timeframe: str = os.getenv('TIMEFRAME', '30m')
        
        # Stochastic RSI Strategy parameters
        self.rsi_period: int = int(os.getenv('RSI_PERIOD', '14'))
        self.stoch_period: int = int(os.getenv('STOCH_PERIOD', '14'))
        self.stoch_rsi_oversold: float = float(os.getenv('STOCH_RSI_OVERSOLD', '20'))
        self.stoch_rsi_overbought: float = float(os.getenv('STOCH_RSI_OVERBOUGHT', '80'))
        # Legacy RSI parameters (DEPRECATED - use STOCH_RSI parameters instead)
        # Kept for backward compatibility only - will be removed in future versions
        self.rsi_oversold: float = float(os.getenv('RSI_OVERSOLD', '30'))
        self.rsi_overbought: float = float(os.getenv('RSI_OVERBOUGHT', '70'))
        
        # Risk management
        self.position_size_percent: float = float(os.getenv('POSITION_SIZE_PERCENT', '1.0'))
        self.position_size_usd: Optional[float] = float(os.getenv('POSITION_SIZE_USD')) if os.getenv('POSITION_SIZE_USD') else None
        self.stop_loss_percent: float = float(os.getenv('STOP_LOSS_PERCENT', '2.5'))
        self.max_drawdown_percent: float = float(os.getenv('MAX_DRAWDOWN_PERCENT', '50.0'))
        
        # Error handling
        self.circuit_breaker_errors: int = int(os.getenv('CIRCUIT_BREAKER_ERRORS', '5'))
        self.circuit_breaker_window_hours: int = int(os.getenv('CIRCUIT_BREAKER_WINDOW_HOURS', '1'))
        self.retry_attempts: int = int(os.getenv('RETRY_ATTEMPTS', '3'))
        self.retry_delay: float = float(os.getenv('RETRY_DELAY', '1.0'))
        
        # Discord notifications
        self.discord_webhook_url: str = os.getenv('DISCORD_WEBHOOK_URL', '')
        self.discord_status_interval: int = int(os.getenv('DISCORD_STATUS_INTERVAL', '600'))  # 10 minutes
        self.discord_roi_interval: int = int(os.getenv('DISCORD_ROI_INTERVAL', '3600'))  # 1 hour
        
        # Logging
        self.log_level: str = os.getenv('LOG_LEVEL', 'INFO')
        self.log_file: str = os.getenv('LOG_FILE', 'bot.log')
        self.log_max_size: int = int(os.getenv('LOG_MAX_SIZE', '5242880'))  # 5MB
        self.log_backup_count: int = int(os.getenv('LOG_BACKUP_COUNT', '3'))
        
        # State management
        self.state_file: str = os.getenv('STATE_FILE', 'state/bot_state.json')
        self.roi_file: str = os.getenv('ROI_FILE', 'state/roi_data.json')
        
        # Fee configuration (hardcoded as per specification)
        self.maker_fee_rate: float = 0.0002  # 0.02% maker fee
        self.taker_fee_rate: float = 0.0005  # 0.05% taker fee
        
    def validate(self) -> None:
        """Validate configuration parameters"""
        errors = []
        
        # Required API credentials
        if not self.hyperliquid_private_key:
            errors.append("HYPERLIQUID_PRIVATE_KEY is required")
            
        # Discord webhook
        if not self.discord_webhook_url:
            errors.append("DISCORD_WEBHOOK_URL is required")
            
        # Strategy parameters validation
        if self.rsi_period < 1:
            errors.append("RSI_PERIOD must be greater than 0")
            
        if self.stoch_period < 1:
            errors.append("STOCH_PERIOD must be greater than 0")
            
        if not (0 < self.stoch_rsi_oversold < 100):
            errors.append("STOCH_RSI_OVERSOLD must be between 0 and 100")
            
        if not (0 < self.stoch_rsi_overbought < 100):
            errors.append("STOCH_RSI_OVERBOUGHT must be between 0 and 100")
            
        if self.stoch_rsi_oversold >= self.stoch_rsi_overbought:
            errors.append("STOCH_RSI_OVERSOLD must be less than STOCH_RSI_OVERBOUGHT")
            
        # Legacy RSI validation (DEPRECATED - kept for backward compatibility)
        if not (0 < self.rsi_oversold < 100):
            import logging
            logging.warning("RSI_OVERSOLD parameter is deprecated, use STOCH_RSI_OVERSOLD instead")
            errors.append("RSI_OVERSOLD must be between 0 and 100")
            
        if not (0 < self.rsi_overbought < 100):
            import logging
            logging.warning("RSI_OVERBOUGHT parameter is deprecated, use STOCH_RSI_OVERBOUGHT instead")
            errors.append("RSI_OVERBOUGHT must be between 0 and 100")
            
        if self.rsi_oversold >= self.rsi_overbought:
            errors.append("RSI_OVERSOLD must be less than RSI_OVERBOUGHT")
            
        # Risk management validation
        if not (0 < self.position_size_percent <= 10):
            errors.append("POSITION_SIZE_PERCENT must be between 0 and 10")
            
        if not (0 < self.stop_loss_percent <= 20):
            errors.append("STOP_LOSS_PERCENT must be between 0 and 20")
            
        if self.leverage < 1 or self.leverage > 50:
            errors.append("LEVERAGE must be between 1 and 50")
            
        # Error handling validation
        if self.circuit_breaker_errors < 1:
            errors.append("CIRCUIT_BREAKER_ERRORS must be greater than 0")
            
        if self.circuit_breaker_window_hours < 1:
            errors.append("CIRCUIT_BREAKER_WINDOW_HOURS must be greater than 0")
            
        if errors:
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")
            
    def mask_secrets(self) -> dict:
        """Return configuration with masked secrets for logging"""
        config_dict = self.__dict__.copy()
        
        # Mask sensitive information completely
        if self.hyperliquid_private_key:
            config_dict['hyperliquid_private_key'] = "***MASKED***"
            
        if self.discord_webhook_url:
            config_dict['discord_webhook_url'] = "***MASKED***"
            
        return config_dict