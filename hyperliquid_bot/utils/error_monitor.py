"""
Error monitoring and circuit breaker for Hyperliquid Trading Bot
Tracks errors and auto-pauses trading after 5+ errors when threshold is exceeded
"""

import time
import logging
import threading
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque, defaultdict


@dataclass
class ErrorEvent:
    """Represents a single error event"""
    timestamp: datetime
    error_type: str
    message: str
    severity: str
    error_hash: str = ""
    count: int = 1


class ErrorMonitor:
    """Thread-safe error monitoring and circuit breaker implementation"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Thread-safe error storage with automatic cleanup
        self.errors: deque = deque(maxlen=1000)  # Limit memory usage
        self.error_deduplication: Dict[str, ErrorEvent] = {}
        
        # Thread-safe circuit breaker state
        self._circuit_breaker_active = False
        self._circuit_breaker_activated_at: Optional[datetime] = None
        self._circuit_breaker_reset_at: Optional[datetime] = None
        
        # Thread synchronization
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._state_lock = threading.Lock()  # Separate lock for circuit breaker state
        
        # Error rate limiting
        self._error_rate_limiter = defaultdict(lambda: deque(maxlen=100))
        self._rate_limit_window = 60  # seconds
        self._max_errors_per_window = 20
        
        # Auto-cleanup timer with proper shutdown handling
        self._cleanup_timer = None
        self._cleanup_shutdown_event = threading.Event()
        self._start_cleanup_timer()
        
    def record_error(self, error_type: str, message: str, severity: str = 'ERROR') -> None:
        """Thread-safe error recording with deduplication and rate limiting"""
        
        # Rate limiting check
        if not self._should_record_error(error_type):
            return
            
        # Create error hash for deduplication
        error_hash = hashlib.md5(f"{error_type}:{message}".encode()).hexdigest()
        
        with self._lock:
            # Check for duplicate errors
            if error_hash in self.error_deduplication:
                existing_error = self.error_deduplication[error_hash]
                existing_error.count += 1
                existing_error.timestamp = datetime.utcnow()  # Use UTC
                self.logger.warning(f"Duplicate error #{existing_error.count}: {error_type}")
                return
                
            # Create new error event
            error_event = ErrorEvent(
                timestamp=datetime.utcnow(),  # Use UTC for consistency
                error_type=error_type,
                message=message[:500],  # Truncate long messages
                severity=severity,
                error_hash=error_hash,
                count=1
            )
            
            # Store error
            self.errors.append(error_event)
            self.error_deduplication[error_hash] = error_event
            
            # Log error
            self.logger.error(f"Error recorded: {error_type} - {message[:200]}")
            
            # Update rate limiter
            self._error_rate_limiter[error_type].append(datetime.utcnow())
            
        # Check circuit breaker (outside lock to avoid deadlock)
        self._check_circuit_breaker()
        
    def _should_record_error(self, error_type: str) -> bool:
        """Check if error should be recorded based on rate limiting"""
        current_time = datetime.utcnow()
        error_times = self._error_rate_limiter[error_type]
        
        # Remove old entries
        while error_times and (current_time - error_times[0]).total_seconds() > self._rate_limit_window:
            error_times.popleft()
            
        # Check rate limit
        if len(error_times) >= self._max_errors_per_window:
            self.logger.warning(f"Rate limit exceeded for error type: {error_type}")
            return False
            
        return True
        
    def _start_cleanup_timer(self) -> None:
        """Start automatic cleanup timer with proper shutdown handling"""
        def cleanup_thread():
            while not self._cleanup_shutdown_event.is_set():
                # Wait for 5 minutes or until shutdown event is set
                if self._cleanup_shutdown_event.wait(timeout=300):
                    break  # Shutdown event was set
                    
                try:
                    self.cleanup_old_errors()
                except Exception as e:
                    self.logger.error(f"Error during automatic cleanup: {e}")
            
            self.logger.debug("Error monitor cleanup thread stopped")
                    
        self._cleanup_timer = threading.Thread(target=cleanup_thread, daemon=True, name="ErrorMonitorCleanup")
        self._cleanup_timer.start()
        
    def _check_circuit_breaker(self) -> None:
        """Thread-safe circuit breaker check"""
        with self._state_lock:
            if self._circuit_breaker_active:
                return
                
            # Count errors within the time window
            window_start = datetime.utcnow() - timedelta(hours=self.config.circuit_breaker_window_hours)
            
            recent_errors = 0
            with self._lock:
                for error in self.errors:
                    if (error.timestamp >= window_start and 
                        error.severity in ['ERROR', 'CRITICAL']):
                        recent_errors += error.count  # Count duplicates
                        
            if recent_errors >= self.config.circuit_breaker_errors:
                self._activate_circuit_breaker()
        
    @property
    def circuit_breaker_active(self) -> bool:
        """Thread-safe circuit breaker status"""
        with self._state_lock:
            return self._circuit_breaker_active
            
    def _activate_circuit_breaker(self) -> None:
        """Thread-safe circuit breaker activation"""
        with self._state_lock:
            if self._circuit_breaker_active:
                return  # Already active
                
            self._circuit_breaker_active = True
            self._circuit_breaker_activated_at = datetime.utcnow()
            self._circuit_breaker_reset_at = datetime.utcnow() + timedelta(hours=1)
            
            self.logger.critical("CIRCUIT BREAKER ACTIVATED - Trading paused due to excessive errors")
            self.logger.critical(f"Trading will resume at {self._circuit_breaker_reset_at}")
        
    def is_circuit_breaker_active(self) -> bool:
        """Thread-safe check if circuit breaker is currently active with auto-reset"""
        with self._state_lock:
            if not self._circuit_breaker_active:
                return False
                
            # Check if it's time to reset
            if datetime.utcnow() >= self._circuit_breaker_reset_at:
                self._reset_circuit_breaker_internal()
                return False
                
            return True
        
    def _reset_circuit_breaker_internal(self) -> None:
        """Internal circuit breaker reset (called with lock held)"""
        self._circuit_breaker_active = False
        self._circuit_breaker_activated_at = None
        self._circuit_breaker_reset_at = None
        self.logger.info("Circuit breaker auto-reset - Trading resumed")
        
    def _reset_circuit_breaker(self) -> None:
        """Public circuit breaker reset method"""
        with self._state_lock:
            self._reset_circuit_breaker_internal()
        
    def get_error_count(self, hours: int = 1) -> int:
        """Thread-safe error count within specified hours"""
        window_start = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            count = 0
            for error in self.errors:
                if error.timestamp >= window_start:
                    count += error.count  # Include duplicate count
            return count
        
    def get_error_summary(self) -> Dict[str, Any]:
        """Thread-safe error summary"""
        window_start = datetime.utcnow() - timedelta(hours=24)
        
        with self._lock:
            error_types = {}
            total_errors = 0
            
            for error in self.errors:
                if error.timestamp >= window_start:
                    error_types[error.error_type] = error_types.get(error.error_type, 0) + error.count
                    total_errors += error.count
                    
        with self._state_lock:
            return {
                'total_errors_24h': total_errors,
                'error_types': error_types,
                'circuit_breaker_active': self._circuit_breaker_active,
                'circuit_breaker_activated_at': self._circuit_breaker_activated_at,
                'circuit_breaker_reset_at': self._circuit_breaker_reset_at
            }
        
    def cleanup_old_errors(self, hours: int = 48) -> None:
        """Thread-safe cleanup of old errors"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            # Clean up main error list
            old_count = len(self.errors)
            self.errors = deque(
                (error for error in self.errors if error.timestamp >= cutoff_time),
                maxlen=1000
            )
            
            # Clean up deduplication cache
            expired_hashes = []
            for error_hash, error in self.error_deduplication.items():
                if error.timestamp < cutoff_time:
                    expired_hashes.append(error_hash)
                    
            for error_hash in expired_hashes:
                del self.error_deduplication[error_hash]
                
            # Clean up rate limiter
            current_time = datetime.utcnow()
            for error_type, timestamps in self._error_rate_limiter.items():
                while timestamps and (current_time - timestamps[0]).total_seconds() > self._rate_limit_window:
                    timestamps.popleft()
                    
            new_count = len(self.errors)
            if old_count != new_count:
                self.logger.debug(f"Cleaned up {old_count - new_count} old errors")
        
    def force_reset_circuit_breaker(self) -> None:
        """Force reset circuit breaker (for manual override)"""
        self.logger.warning("Circuit breaker manually reset")
        self._reset_circuit_breaker()
        
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get detailed circuit breaker status"""
        with self._state_lock:
            return {
                'active': self._circuit_breaker_active,
                'activated_at': self._circuit_breaker_activated_at.isoformat() if self._circuit_breaker_activated_at else None,
                'reset_at': self._circuit_breaker_reset_at.isoformat() if self._circuit_breaker_reset_at else None,
                'error_threshold': self.config.circuit_breaker_errors,
                'window_hours': self.config.circuit_breaker_window_hours
            }
            
    def cleanup(self) -> None:
        """Proper cleanup method to stop background threads"""
        try:
            # Signal shutdown to cleanup thread
            if hasattr(self, '_cleanup_shutdown_event'):
                self._cleanup_shutdown_event.set()
            
            # Wait for cleanup thread to finish (with timeout)
            if hasattr(self, '_cleanup_timer') and self._cleanup_timer and self._cleanup_timer.is_alive():
                self._cleanup_timer.join(timeout=5.0)
                if self._cleanup_timer.is_alive():
                    self.logger.warning("Cleanup thread did not stop within timeout")
            
            # Clear collections to free memory
            with self._lock:
                self.errors.clear()
                self.error_deduplication.clear()
                for error_queue in self._error_rate_limiter.values():
                    error_queue.clear()
                self._error_rate_limiter.clear()
            
            self.logger.debug("Error monitor cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error during error monitor cleanup: {e}")

    def __del__(self):
        """Cleanup on destruction"""
        try:
            self.cleanup()
        except:
            pass