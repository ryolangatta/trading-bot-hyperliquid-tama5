"""
Production health checker for Hyperliquid Trading Bot
Monitors system health, API connectivity, and trading prerequisites
"""

import asyncio
import logging
import psutil
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class HealthStatus(Enum):
    """Health check status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result"""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    details: Dict[str, Any] = None
    response_time_ms: float = 0.0


class HealthChecker:
    """Comprehensive health monitoring for trading bot"""
    
    def __init__(self, config, hyperliquid_client=None, error_monitor=None):
        self.config = config
        self.hyperliquid_client = hyperliquid_client
        self.error_monitor = error_monitor
        self.logger = logging.getLogger(__name__)
        
        # Health check thresholds
        self.cpu_threshold = 80.0  # 80% CPU usage warning
        self.memory_threshold = 85.0  # 85% memory usage warning
        self.disk_threshold = 90.0  # 90% disk usage warning
        self.api_timeout_threshold = 5.0  # 5 second API response warning
        self.error_rate_threshold = 10  # 10 errors per hour warning
        
        # Health check intervals
        self.system_check_interval = 60  # 1 minute
        self.api_check_interval = 300  # 5 minutes
        self.trading_check_interval = 120  # 2 minutes
        
        # Last check timestamps
        self.last_system_check = datetime.min
        self.last_api_check = datetime.min
        self.last_trading_check = datetime.min
        
        self.logger.info("Health checker initialized")
    
    async def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all health checks and return results"""
        checks = {}
        
        try:
            # System health checks
            system_checks = await self._check_system_health()
            checks.update(system_checks)
            
            # API connectivity checks
            if self.hyperliquid_client:
                api_checks = await self._check_api_health()
                checks.update(api_checks)
            
            # Trading-specific checks
            trading_checks = await self._check_trading_health()
            checks.update(trading_checks)
            
            # Error monitoring checks
            if self.error_monitor:
                error_checks = await self._check_error_health()
                checks.update(error_checks)
                
        except Exception as e:
            self.logger.error(f"Error during health checks: {e}")
            checks["health_check_error"] = HealthCheck(
                name="Health Check System",
                status=HealthStatus.CRITICAL,
                message=f"Health check system failure: {e}",
                timestamp=datetime.now()
            )
        
        return checks
    
    async def _check_system_health(self) -> Dict[str, HealthCheck]:
        """Check system resource health"""
        checks = {}
        current_time = datetime.now()
        
        # Skip if checked recently
        if (current_time - self.last_system_check).total_seconds() < self.system_check_interval:
            return checks
        
        try:
            # CPU usage check
            cpu_percent = psutil.cpu_percent(interval=1)
            checks["cpu_usage"] = HealthCheck(
                name="CPU Usage",
                status=HealthStatus.CRITICAL if cpu_percent > 95 else 
                       HealthStatus.WARNING if cpu_percent > self.cpu_threshold else HealthStatus.HEALTHY,
                message=f"CPU usage: {cpu_percent:.1f}%",
                timestamp=current_time,
                details={"cpu_percent": cpu_percent, "threshold": self.cpu_threshold}
            )
            
            # Memory usage check
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            checks["memory_usage"] = HealthCheck(
                name="Memory Usage",
                status=HealthStatus.CRITICAL if memory_percent > 95 else
                       HealthStatus.WARNING if memory_percent > self.memory_threshold else HealthStatus.HEALTHY,
                message=f"Memory usage: {memory_percent:.1f}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)",
                timestamp=current_time,
                details={
                    "memory_percent": memory_percent,
                    "used_gb": memory.used / (1024**3),
                    "total_gb": memory.total / (1024**3),
                    "threshold": self.memory_threshold
                }
            )
            
            # Disk usage check
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            checks["disk_usage"] = HealthCheck(
                name="Disk Usage",
                status=HealthStatus.CRITICAL if disk_percent > 95 else
                       HealthStatus.WARNING if disk_percent > self.disk_threshold else HealthStatus.HEALTHY,
                message=f"Disk usage: {disk_percent:.1f}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)",
                timestamp=current_time,
                details={
                    "disk_percent": disk_percent,
                    "used_gb": disk.used / (1024**3),
                    "total_gb": disk.total / (1024**3),
                    "threshold": self.disk_threshold
                }
            )
            
            # Network connectivity check
            network_stats = psutil.net_io_counters()
            checks["network"] = HealthCheck(
                name="Network",
                status=HealthStatus.HEALTHY,
                message=f"Network active: {network_stats.bytes_sent / (1024**2):.1f}MB sent, {network_stats.bytes_recv / (1024**2):.1f}MB received",
                timestamp=current_time,
                details={
                    "bytes_sent": network_stats.bytes_sent,
                    "bytes_received": network_stats.bytes_recv
                }
            )
            
            self.last_system_check = current_time
            
        except Exception as e:
            self.logger.error(f"System health check failed: {e}")
            checks["system_error"] = HealthCheck(
                name="System Health",
                status=HealthStatus.CRITICAL,
                message=f"System health check failed: {e}",
                timestamp=current_time
            )
        
        return checks
    
    async def _check_api_health(self) -> Dict[str, HealthCheck]:
        """Check API connectivity and response times"""
        checks = {}
        current_time = datetime.now()
        
        # Skip if checked recently
        if (current_time - self.last_api_check).total_seconds() < self.api_check_interval:
            return checks
        
        try:
            # API connectivity check
            start_time = time.time()
            api_healthy = await self.hyperliquid_client.health_check()
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            checks["api_connectivity"] = HealthCheck(
                name="API Connectivity",
                status=HealthStatus.HEALTHY if api_healthy else HealthStatus.CRITICAL,
                message=f"API {'connected' if api_healthy else 'disconnected'} (response: {response_time:.0f}ms)",
                timestamp=current_time,
                response_time_ms=response_time,
                details={
                    "connected": api_healthy,
                    "response_time_ms": response_time,
                    "threshold_ms": self.api_timeout_threshold * 1000
                }
            )
            
            # API response time check
            if api_healthy:
                checks["api_response_time"] = HealthCheck(
                    name="API Response Time",
                    status=HealthStatus.WARNING if response_time > self.api_timeout_threshold * 1000 else HealthStatus.HEALTHY,
                    message=f"API response time: {response_time:.0f}ms",
                    timestamp=current_time,
                    response_time_ms=response_time
                )
            
            self.last_api_check = current_time
            
        except Exception as e:
            self.logger.error(f"API health check failed: {e}")
            checks["api_error"] = HealthCheck(
                name="API Health",
                status=HealthStatus.CRITICAL,
                message=f"API health check failed: {e}",
                timestamp=current_time
            )
        
        return checks
    
    async def _check_trading_health(self) -> Dict[str, HealthCheck]:
        """Check trading-specific health requirements"""
        checks = {}
        current_time = datetime.now()
        
        # Skip if checked recently
        if (current_time - self.last_trading_check).total_seconds() < self.trading_check_interval:
            return checks
        
        try:
            # Configuration validation
            config_issues = []
            
            if not self.config.hyperliquid_private_key:
                config_issues.append("Missing private key")
            
            if not self.config.discord_webhook_url:
                config_issues.append("Missing Discord webhook")
            
            checks["configuration"] = HealthCheck(
                name="Configuration",
                status=HealthStatus.CRITICAL if config_issues else HealthStatus.HEALTHY,
                message=f"Configuration {'invalid' if config_issues else 'valid'}: {', '.join(config_issues) if config_issues else 'All required settings present'}",
                timestamp=current_time,
                details={"issues": config_issues}
            )
            
            # Account balance check (if API available)
            if self.hyperliquid_client:
                try:
                    account_info = await self.hyperliquid_client.get_account_info()
                    balance = account_info.get('balance', 0)
                    available = account_info.get('available_balance', 0)
                    
                    min_balance = 10.0  # Minimum $10 balance
                    checks["account_balance"] = HealthCheck(
                        name="Account Balance",
                        status=HealthStatus.CRITICAL if balance < min_balance else 
                               HealthStatus.WARNING if available < min_balance else HealthStatus.HEALTHY,
                        message=f"Balance: ${balance:.2f}, Available: ${available:.2f}",
                        timestamp=current_time,
                        details={
                            "balance": balance,
                            "available": available,
                            "min_balance": min_balance
                        }
                    )
                except Exception as e:
                    checks["account_balance"] = HealthCheck(
                        name="Account Balance",
                        status=HealthStatus.WARNING,
                        message=f"Cannot check balance: {e}",
                        timestamp=current_time
                    )
            
            # Environment check
            environment = "TESTNET" if self.config.testnet else "MAINNET"
            mode = "DRY_RUN" if self.config.dry_run else "LIVE"
            
            checks["environment"] = HealthCheck(
                name="Environment",
                status=HealthStatus.HEALTHY,
                message=f"Running on {environment} in {mode} mode",
                timestamp=current_time,
                details={
                    "environment": environment,
                    "mode": mode,
                    "testnet": self.config.testnet,
                    "dry_run": self.config.dry_run
                }
            )
            
            self.last_trading_check = current_time
            
        except Exception as e:
            self.logger.error(f"Trading health check failed: {e}")
            checks["trading_error"] = HealthCheck(
                name="Trading Health",
                status=HealthStatus.CRITICAL,
                message=f"Trading health check failed: {e}",
                timestamp=current_time
            )
        
        return checks
    
    async def _check_error_health(self) -> Dict[str, HealthCheck]:
        """Check error monitoring and circuit breaker status"""
        checks = {}
        current_time = datetime.now()
        
        try:
            # Error rate check
            error_count = self.error_monitor.get_error_count(hours=1)
            checks["error_rate"] = HealthCheck(
                name="Error Rate",
                status=HealthStatus.WARNING if error_count > self.error_rate_threshold else HealthStatus.HEALTHY,
                message=f"Errors in last hour: {error_count}",
                timestamp=current_time,
                details={
                    "error_count": error_count,
                    "threshold": self.error_rate_threshold
                }
            )
            
            # Circuit breaker status
            circuit_breaker_active = self.error_monitor.is_circuit_breaker_active()
            checks["circuit_breaker"] = HealthCheck(
                name="Circuit Breaker",
                status=HealthStatus.CRITICAL if circuit_breaker_active else HealthStatus.HEALTHY,
                message=f"Circuit breaker: {'ACTIVE' if circuit_breaker_active else 'INACTIVE'}",
                timestamp=current_time,
                details={"active": circuit_breaker_active}
            )
            
        except Exception as e:
            self.logger.error(f"Error health check failed: {e}")
            checks["error_monitor_error"] = HealthCheck(
                name="Error Monitoring",
                status=HealthStatus.WARNING,
                message=f"Error monitoring check failed: {e}",
                timestamp=current_time
            )
        
        return checks
    
    def get_overall_status(self, checks: Dict[str, HealthCheck]) -> HealthStatus:
        """Determine overall system health status"""
        if not checks:
            return HealthStatus.UNKNOWN
        
        statuses = [check.status for check in checks.values()]
        
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
    
    def format_health_report(self, checks: Dict[str, HealthCheck]) -> str:
        """Format health checks into a readable report"""
        overall_status = self.get_overall_status(checks)
        
        report = [
            f"🏥 HEALTH REPORT - {overall_status.value.upper()}",
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Total Checks: {len(checks)}",
            "",
        ]
        
        # Group by status
        status_groups = {
            HealthStatus.CRITICAL: [],
            HealthStatus.WARNING: [],
            HealthStatus.HEALTHY: []
        }
        
        for check in checks.values():
            if check.status in status_groups:
                status_groups[check.status].append(check)
        
        # Add critical issues first
        if status_groups[HealthStatus.CRITICAL]:
            report.append("🚨 CRITICAL ISSUES:")
            for check in status_groups[HealthStatus.CRITICAL]:
                report.append(f"  ❌ {check.name}: {check.message}")
            report.append("")
        
        # Add warnings
        if status_groups[HealthStatus.WARNING]:
            report.append("⚠️ WARNINGS:")
            for check in status_groups[HealthStatus.WARNING]:
                report.append(f"  ⚠️ {check.name}: {check.message}")
            report.append("")
        
        # Add healthy checks (summary)
        healthy_count = len(status_groups[HealthStatus.HEALTHY])
        if healthy_count > 0:
            report.append(f"✅ HEALTHY CHECKS: {healthy_count}")
            report.append("")
        
        return "\n".join(report)
    
    async def continuous_monitoring(self, interval: int = 300) -> None:
        """Run continuous health monitoring in background"""
        self.logger.info(f"Starting continuous health monitoring (interval: {interval}s)")
        
        while True:
            try:
                checks = await self.run_all_checks()
                overall_status = self.get_overall_status(checks)
                
                # Log summary
                critical_count = sum(1 for check in checks.values() if check.status == HealthStatus.CRITICAL)
                warning_count = sum(1 for check in checks.values() if check.status == HealthStatus.WARNING)
                
                if critical_count > 0:
                    self.logger.error(f"Health check: {critical_count} critical issues, {warning_count} warnings")
                elif warning_count > 0:
                    self.logger.warning(f"Health check: {warning_count} warnings")
                else:
                    self.logger.debug("Health check: All systems healthy")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in continuous health monitoring: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying