"""
Logging utilities for Hyperliquid Trading Bot
Provides structured logging with rotation and secret masking
"""

import logging
import logging.handlers
import os
import re
from pathlib import Path
from typing import Optional


class SecretMaskingFormatter(logging.Formatter):
    """Custom formatter that masks sensitive information in log messages"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Patterns to mask sensitive information
        self.secret_patterns = [
            (re.compile(r'private_key[\'"]?\s*[:=]\s*[\'"]?([a-fA-F0-9]{64})[\'"]?', re.IGNORECASE), 'private_key=***MASKED***'),
            (re.compile(r'password[\'"]?\s*[:=]\s*[\'"]?([^\s\'"]+)[\'"]?', re.IGNORECASE), 'password=***MASKED***'),
            (re.compile(r'secret[\'"]?\s*[:=]\s*[\'"]?([^\s\'"]+)[\'"]?', re.IGNORECASE), 'secret=***MASKED***'),
            (re.compile(r'token[\'"]?\s*[:=]\s*[\'"]?([^\s\'"]+)[\'"]?', re.IGNORECASE), 'token=***MASKED***'),
            (re.compile(r'key[\'"]?\s*[:=]\s*[\'"]?([a-fA-F0-9]{32,})[\'"]?', re.IGNORECASE), 'key=***MASKED***'),
            (re.compile(r'webhook[\'"]?\s*[:=]\s*[\'"]?(https://[^\s\'"]+)[\'"]?', re.IGNORECASE), 'webhook=***MASKED***'),
        ]
        
    def format(self, record):
        # Get the original formatted message
        msg = super().format(record)
        
        # Apply secret masking patterns
        for pattern, replacement in self.secret_patterns:
            msg = pattern.sub(replacement, msg)
            
        return msg


def setup_logger(log_level: str = 'INFO', 
                log_file: Optional[str] = None,
                max_bytes: int = 5 * 1024 * 1024,  # 5MB
                backup_count: int = 3) -> logging.Logger:
    """
    Setup structured logging with rotation and secret masking
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        
    Returns:
        Configured logger instance
    """
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter with secret masking
    formatter = SecretMaskingFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation (if log_file specified)
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Log configuration
    logger.info(f"Logger initialized - Level: {log_level}")
    if log_file:
        logger.info(f"Log file: {log_file} (max: {max_bytes/1024/1024:.1f}MB, backups: {backup_count})")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module"""
    return logging.getLogger(name)