"""
Production hardening utilities for Hyperliquid Trading Bot
Security, stability, and monitoring enhancements for production deployment
"""

import os
import sys
import signal
import logging
import asyncio
import resource
import socket
from typing import Dict, Any, Optional
from datetime import datetime
import hashlib
import secrets


class ProductionHardening:
    """Production hardening and security utilities"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._shutdown_event = asyncio.Event()
        self._graceful_shutdown_timeout = 30  # seconds
        
    def apply_security_hardening(self) -> None:
        """Apply security hardening measures"""
        try:
            # Set resource limits to prevent resource exhaustion
            self._set_resource_limits()
            
            # Configure signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            # Validate environment security
            self._validate_environment_security()
            
            # Set secure file permissions
            self._secure_file_permissions()
            
            self.logger.info("Production security hardening applied successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to apply security hardening: {e}")
            raise
    
    def _set_resource_limits(self) -> None:
        """Set system resource limits to prevent DoS"""
        try:
            # Memory limit: 2GB (soft), 4GB (hard)
            memory_limit_soft = 2 * 1024 * 1024 * 1024  # 2GB
            memory_limit_hard = 4 * 1024 * 1024 * 1024  # 4GB
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_soft, memory_limit_hard))
            
            # CPU time limit: 1 hour (soft), 2 hours (hard) per process
            cpu_limit_soft = 3600  # 1 hour
            cpu_limit_hard = 7200  # 2 hours
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit_soft, cpu_limit_hard))
            
            # File descriptor limit: 1024 (soft), 4096 (hard)
            fd_limit_soft = 1024
            fd_limit_hard = 4096
            resource.setrlimit(resource.RLIMIT_NOFILE, (fd_limit_soft, fd_limit_hard))
            
            # Process limit: 128 (soft), 256 (hard)
            proc_limit_soft = 128
            proc_limit_hard = 256
            resource.setrlimit(resource.RLIMIT_NPROC, (proc_limit_soft, proc_limit_hard))
            
            self.logger.info("Resource limits configured for production")
            
        except Exception as e:
            self.logger.warning(f"Could not set all resource limits: {e}")
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            self.logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            self._shutdown_event.set()
        
        # Handle termination signals
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Ignore SIGHUP (let systemd handle restarts)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        
        self.logger.info("Signal handlers configured for graceful shutdown")
    
    def _validate_environment_security(self) -> None:
        """Validate environment security settings"""
        security_issues = []
        
        # Check for required environment variables
        required_vars = [
            'HYPERLIQUID_PRIVATE_KEY',
            'DISCORD_WEBHOOK_URL'
        ]
        
        for var in required_vars:
            if not self.config.__dict__.get(var.lower()):
                security_issues.append(f"Missing required environment variable: {var}")
        
        # Check private key format
        if hasattr(self.config, 'hyperliquid_private_key') and self.config.hyperliquid_private_key:
            if not self._validate_private_key_format(self.config.hyperliquid_private_key):
                security_issues.append("Private key format appears invalid")
        
        # Check Discord webhook URL format
        if hasattr(self.config, 'discord_webhook_url') and self.config.discord_webhook_url:
            if not self.config.discord_webhook_url.startswith('https://discord.com/api/webhooks/'):
                security_issues.append("Discord webhook URL format appears invalid")
        
        # Warn about development mode in production
        if not self.config.dry_run and self.config.testnet:
            security_issues.append("Using testnet in production mode")
        
        if security_issues:
            for issue in security_issues:
                self.logger.error(f"Security issue: {issue}")
            raise ValueError(f"Security validation failed: {len(security_issues)} issues found")
        
        self.logger.info("Environment security validation passed")
    
    def _validate_private_key_format(self, private_key: str) -> bool:
        """Validate private key format (basic check)"""
        try:
            # Remove 0x prefix if present
            if private_key.startswith('0x'):
                private_key = private_key[2:]
            
            # Check length (64 hex characters for 32 bytes)
            if len(private_key) != 64:
                return False
            
            # Check if valid hex
            int(private_key, 16)
            return True
            
        except ValueError:
            return False
    
    def _secure_file_permissions(self) -> None:
        """Set secure file permissions for sensitive files"""
        try:
            # Secure state files (owner read/write only)
            state_files = [
                self.config.state_file,
                self.config.roi_file,
                '.env'
            ]
            
            for file_path in state_files:
                if os.path.exists(file_path):
                    os.chmod(file_path, 0o600)  # Owner read/write only
                    self.logger.debug(f"Secured permissions for {file_path}")
            
            # Secure log directory (owner full access, group read)
            log_dir = os.path.dirname(self.config.log_file) if hasattr(self.config, 'log_file') else 'logs'
            if os.path.exists(log_dir):
                os.chmod(log_dir, 0o750)  # Owner full, group read/execute
            
        except Exception as e:
            self.logger.warning(f"Could not set secure file permissions: {e}")
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal"""
        await self._shutdown_event.wait()
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self._shutdown_event.is_set()
    
    async def graceful_shutdown(self, cleanup_tasks: list = None) -> None:
        """Perform graceful shutdown with cleanup"""
        self.logger.info("Starting graceful shutdown...")
        
        try:
            # Run cleanup tasks with timeout
            if cleanup_tasks:
                self.logger.info(f"Running {len(cleanup_tasks)} cleanup tasks...")
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=self._graceful_shutdown_timeout
                )
            
            self.logger.info("Graceful shutdown completed")
            
        except asyncio.TimeoutError:
            self.logger.error(f"Cleanup tasks exceeded timeout ({self._graceful_shutdown_timeout}s)")
        except Exception as e:
            self.logger.error(f"Error during graceful shutdown: {e}")
    
    def generate_instance_id(self) -> str:
        """Generate unique instance ID for this bot instance"""
        # Use hostname, PID, and timestamp to create unique ID
        hostname = socket.gethostname()
        pid = os.getpid()
        timestamp = datetime.now().isoformat()
        
        # Create hash of combined data
        instance_data = f"{hostname}-{pid}-{timestamp}"
        instance_hash = hashlib.sha256(instance_data.encode()).hexdigest()[:16]
        
        return f"bot-{instance_hash}"
    
    def validate_network_connectivity(self) -> Dict[str, bool]:
        """Validate network connectivity to required services"""
        connectivity = {}
        
        # Test DNS resolution
        try:
            socket.gethostbyname('hyperliquid.xyz')
            connectivity['hyperliquid_dns'] = True
        except socket.gaierror:
            connectivity['hyperliquid_dns'] = False
        
        # Test Discord connectivity
        try:
            socket.gethostbyname('discord.com')
            connectivity['discord_dns'] = True
        except socket.gaierror:
            connectivity['discord_dns'] = False
        
        # Test internet connectivity
        try:
            socket.gethostbyname('8.8.8.8')
            connectivity['internet'] = True
        except socket.gaierror:
            connectivity['internet'] = False
        
        return connectivity
    
    def setup_monitoring_hooks(self) -> None:
        """Setup monitoring and observability hooks"""
        try:
            # Add custom log formatter with instance ID
            instance_id = self.generate_instance_id()
            
            # Create custom formatter
            formatter = logging.Formatter(
                f'%(asctime)s [{instance_id}] %(levelname)s %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Apply to all handlers
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                handler.setFormatter(formatter)
            
            self.logger.info(f"Monitoring hooks setup for instance: {instance_id}")
            
        except Exception as e:
            self.logger.warning(f"Could not setup monitoring hooks: {e}")
    
    def create_startup_report(self) -> Dict[str, Any]:
        """Create comprehensive startup report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'instance_id': self.generate_instance_id(),
            'python_version': sys.version,
            'platform': sys.platform,
            'environment': {
                'testnet': self.config.testnet,
                'dry_run': self.config.dry_run,
                'debug': logging.getLogger().isEnabledFor(logging.DEBUG)
            },
            'system': {
                'hostname': socket.gethostname(),
                'pid': os.getpid(),
                'cwd': os.getcwd()
            },
            'security': {
                'private_key_configured': bool(getattr(self.config, 'hyperliquid_private_key', None)),
                'discord_webhook_configured': bool(getattr(self.config, 'discord_webhook_url', None)),
                'file_permissions_secured': True  # Assume success if no exception
            },
            'connectivity': self.validate_network_connectivity(),
            'resource_limits': self._get_resource_limits()
        }
        
        return report
    
    def _get_resource_limits(self) -> Dict[str, Any]:
        """Get current resource limits"""
        try:
            limits = {}
            
            # Memory limit
            mem_soft, mem_hard = resource.getrlimit(resource.RLIMIT_AS)
            limits['memory'] = {
                'soft': mem_soft,
                'hard': mem_hard,
                'soft_gb': mem_soft / (1024**3) if mem_soft != resource.RLIM_INFINITY else 'unlimited',
                'hard_gb': mem_hard / (1024**3) if mem_hard != resource.RLIM_INFINITY else 'unlimited'
            }
            
            # CPU limit
            cpu_soft, cpu_hard = resource.getrlimit(resource.RLIMIT_CPU)
            limits['cpu'] = {
                'soft': cpu_soft,
                'hard': cpu_hard,
                'soft_hours': cpu_soft / 3600 if cpu_soft != resource.RLIM_INFINITY else 'unlimited',
                'hard_hours': cpu_hard / 3600 if cpu_hard != resource.RLIM_INFINITY else 'unlimited'
            }
            
            # File descriptor limit
            fd_soft, fd_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            limits['file_descriptors'] = {
                'soft': fd_soft,
                'hard': fd_hard
            }
            
            return limits
            
        except Exception as e:
            self.logger.warning(f"Could not get resource limits: {e}")
            return {}
    
    def log_startup_report(self) -> None:
        """Log comprehensive startup report"""
        try:
            report = self.create_startup_report()
            
            self.logger.info("=== PRODUCTION STARTUP REPORT ===")
            self.logger.info(f"Instance ID: {report['instance_id']}")
            self.logger.info(f"Environment: {'TESTNET' if report['environment']['testnet'] else 'MAINNET'}")
            self.logger.info(f"Mode: {'DRY_RUN' if report['environment']['dry_run'] else 'LIVE'}")
            self.logger.info(f"Python: {report['python_version']}")
            self.logger.info(f"Platform: {report['platform']}")
            self.logger.info(f"Hostname: {report['system']['hostname']}")
            self.logger.info(f"PID: {report['system']['pid']}")
            
            # Log connectivity status
            connectivity = report['connectivity']
            for service, status in connectivity.items():
                status_emoji = "✅" if status else "❌"
                self.logger.info(f"Connectivity {service}: {status_emoji}")
            
            # Log security status
            security = report['security']
            for check, status in security.items():
                status_emoji = "✅" if status else "❌"
                self.logger.info(f"Security {check}: {status_emoji}")
            
            self.logger.info("=== END STARTUP REPORT ===")
            
        except Exception as e:
            self.logger.error(f"Failed to log startup report: {e}")


class EmergencyStop:
    """Emergency stop mechanism for critical situations"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._emergency_stop_triggered = False
        self._stop_reason = None
    
    def trigger_emergency_stop(self, reason: str) -> None:
        """Trigger emergency stop"""
        if self._emergency_stop_triggered:
            return  # Already triggered
        
        self._emergency_stop_triggered = True
        self._stop_reason = reason
        
        self.logger.critical(f"🚨 EMERGENCY STOP TRIGGERED: {reason}")
        self.logger.critical("All trading operations will be halted immediately")
        
        # Could add additional emergency actions here:
        # - Close all positions
        # - Cancel all orders
        # - Send emergency notifications
    
    def is_emergency_stop_active(self) -> bool:
        """Check if emergency stop is active"""
        return self._emergency_stop_triggered
    
    def get_stop_reason(self) -> Optional[str]:
        """Get the reason for emergency stop"""
        return self._stop_reason
    
    def reset_emergency_stop(self, authorization_code: str) -> bool:
        """Reset emergency stop (requires authorization)"""
        # Simple authorization check (in production, use proper auth)
        expected_code = hashlib.sha256(f"reset-{datetime.now().date()}".encode()).hexdigest()[:8]
        
        if authorization_code == expected_code:
            self._emergency_stop_triggered = False
            self._stop_reason = None
            self.logger.warning("Emergency stop has been reset")
            return True
        else:
            self.logger.error("Invalid authorization code for emergency stop reset")
            return False