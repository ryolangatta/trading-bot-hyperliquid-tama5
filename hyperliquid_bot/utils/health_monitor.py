"""
Production-grade health monitoring system for Hyperliquid Trading Bot
Monitors system resources, API health, and component status
"""

import asyncio
import logging
import psutil
import time
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthMetric:
    name: str
    value: float
    unit: str
    status: HealthStatus
    threshold_warning: float
    threshold_critical: float
    timestamp: datetime


@dataclass
class ComponentHealth:
    component: str
    status: HealthStatus
    metrics: List[HealthMetric]
    last_check: datetime
    error_message: Optional[str] = None


class HealthMonitor:
    """Comprehensive health monitoring for production deployment"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Health data
        self.component_health: Dict[str, ComponentHealth] = {}
        self.system_metrics: List[HealthMetric] = []
        
        # Monitoring configuration
        self.check_interval = 30  # seconds
        self.metric_retention_hours = 24
        
        # Thresholds
        self.thresholds = {
            'cpu_percent': {'warning': 80.0, 'critical': 95.0},
            'memory_percent': {'warning': 85.0, 'critical': 95.0},
            'disk_percent': {'warning': 90.0, 'critical': 98.0},
            'api_response_time': {'warning': 5.0, 'critical': 10.0},  # seconds
            'error_rate': {'warning': 0.1, 'critical': 0.2},  # errors per minute
        }
        
        # Monitoring state
        self._monitoring = False
        self._monitor_task = None
        self._lock = threading.Lock()
        
    async def start_monitoring(self) -> None:
        """Start continuous health monitoring"""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Health monitoring started")
        
    async def stop_monitoring(self) -> None:
        """Stop health monitoring"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Health monitoring stopped")
        
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        while self._monitoring:
            try:
                await self._collect_system_metrics()
                await self._check_component_health()
                await self._cleanup_old_metrics()
                
                # Check for critical conditions
                await self._evaluate_health_alerts()
                
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")
                
            await asyncio.sleep(self.check_interval)
            
    async def _collect_system_metrics(self) -> None:
        """Collect system resource metrics"""
        try:
            timestamp = datetime.utcnow()
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_metric = HealthMetric(
                name="cpu_usage",
                value=cpu_percent,
                unit="percent",
                status=self._evaluate_threshold(cpu_percent, 'cpu_percent'),
                threshold_warning=self.thresholds['cpu_percent']['warning'],
                threshold_critical=self.thresholds['cpu_percent']['critical'],
                timestamp=timestamp
            )
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_metric = HealthMetric(
                name="memory_usage",
                value=memory.percent,
                unit="percent",
                status=self._evaluate_threshold(memory.percent, 'memory_percent'),
                threshold_warning=self.thresholds['memory_percent']['warning'],
                threshold_critical=self.thresholds['memory_percent']['critical'],
                timestamp=timestamp
            )
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_metric = HealthMetric(
                name="disk_usage",
                value=disk_percent,
                unit="percent",
                status=self._evaluate_threshold(disk_percent, 'disk_percent'),
                threshold_warning=self.thresholds['disk_percent']['warning'],
                threshold_critical=self.thresholds['disk_percent']['critical'],
                timestamp=timestamp
            )
            
            # Network connections
            connections = len(psutil.net_connections())
            connection_metric = HealthMetric(
                name="network_connections",
                value=connections,
                unit="count",
                status=HealthStatus.HEALTHY,  # No thresholds for connections
                threshold_warning=0,
                threshold_critical=0,
                timestamp=timestamp
            )
            
            with self._lock:
                self.system_metrics.extend([cpu_metric, memory_metric, disk_metric, connection_metric])
                
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            
    def _evaluate_threshold(self, value: float, threshold_key: str) -> HealthStatus:
        """Evaluate value against thresholds"""
        thresholds = self.thresholds.get(threshold_key, {})
        
        if value >= thresholds.get('critical', float('inf')):
            return HealthStatus.CRITICAL
        elif value >= thresholds.get('warning', float('inf')):
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
            
    async def _check_component_health(self) -> None:
        """Check health of individual components"""
        timestamp = datetime.utcnow()
        
        # This would be called by individual components to report their health
        # For now, we'll check if components are registered
        
        components = ['hyperliquid_client', 'strategy', 'state_manager', 'discord_notifier']
        
        for component in components:
            if component not in self.component_health:
                self.component_health[component] = ComponentHealth(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    metrics=[],
                    last_check=timestamp,
                    error_message="Component not yet registered"
                )
                
    async def _cleanup_old_metrics(self) -> None:
        """Remove old metrics to prevent memory growth"""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.metric_retention_hours)
        
        with self._lock:
            self.system_metrics = [
                metric for metric in self.system_metrics 
                if metric.timestamp >= cutoff_time
            ]
            
    async def _evaluate_health_alerts(self) -> None:
        """Evaluate if health alerts should be sent"""
        # Check for critical system conditions
        recent_metrics = self._get_recent_metrics(minutes=5)
        
        critical_metrics = [
            metric for metric in recent_metrics 
            if metric.status == HealthStatus.CRITICAL
        ]
        
        if critical_metrics:
            self.logger.warning(f"Critical system conditions detected: {len(critical_metrics)} metrics")
            # This could trigger Discord alerts if integrated
            
    def _get_recent_metrics(self, minutes: int = 10) -> List[HealthMetric]:
        """Get metrics from the last N minutes"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        with self._lock:
            return [
                metric for metric in self.system_metrics 
                if metric.timestamp >= cutoff_time
            ]
            
    def register_component_health(self, component: str, status: HealthStatus, 
                                 metrics: List[HealthMetric] = None, 
                                 error_message: str = None) -> None:
        """Register component health status"""
        self.component_health[component] = ComponentHealth(
            component=component,
            status=status,
            metrics=metrics or [],
            last_check=datetime.utcnow(),
            error_message=error_message
        )
        
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health summary"""
        recent_metrics = self._get_recent_metrics(minutes=5)
        
        # Calculate overall status
        statuses = [metric.status for metric in recent_metrics]
        statuses.extend([comp.status for comp in self.component_health.values()])
        
        if HealthStatus.CRITICAL in statuses:
            overall_status = HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            overall_status = HealthStatus.WARNING
        elif HealthStatus.HEALTHY in statuses:
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNKNOWN
            
        # Get latest system metrics
        latest_metrics = {}
        for metric_name in ['cpu_usage', 'memory_usage', 'disk_usage']:
            matching_metrics = [m for m in recent_metrics if m.name == metric_name]
            if matching_metrics:
                latest_metric = max(matching_metrics, key=lambda x: x.timestamp)
                latest_metrics[metric_name] = {
                    'value': latest_metric.value,
                    'unit': latest_metric.unit,
                    'status': latest_metric.status.value
                }
                
        return {
            'overall_status': overall_status.value,
            'timestamp': datetime.utcnow().isoformat(),
            'system_metrics': latest_metrics,
            'components': {
                comp.component: {
                    'status': comp.status.value,
                    'last_check': comp.last_check.isoformat(),
                    'error_message': comp.error_message
                }
                for comp in self.component_health.values()
            }
        }
        
    def get_detailed_metrics(self, hours: int = 1) -> Dict[str, Any]:
        """Get detailed metrics for analysis"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            filtered_metrics = [
                metric for metric in self.system_metrics 
                if metric.timestamp >= cutoff_time
            ]
            
        # Group by metric name
        grouped_metrics = {}
        for metric in filtered_metrics:
            if metric.name not in grouped_metrics:
                grouped_metrics[metric.name] = []
            grouped_metrics[metric.name].append({
                'timestamp': metric.timestamp.isoformat(),
                'value': metric.value,
                'status': metric.status.value
            })
            
        return {
            'time_range_hours': hours,
            'metrics': grouped_metrics,
            'component_health': {
                comp.component: {
                    'status': comp.status.value,
                    'last_check': comp.last_check.isoformat(),
                    'metrics_count': len(comp.metrics)
                }
                for comp in self.component_health.values()
            }
        }
        
    async def health_check_api_endpoint(self, url: str, timeout: float = 5.0) -> HealthMetric:
        """Perform health check on API endpoint"""
        start_time = time.time()
        
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.get(url) as response:
                    response_time = time.time() - start_time
                    
                    status = self._evaluate_threshold(response_time, 'api_response_time')
                    
                    return HealthMetric(
                        name=f"api_response_time_{url.split('/')[-1]}",
                        value=response_time,
                        unit="seconds",
                        status=status,
                        threshold_warning=self.thresholds['api_response_time']['warning'],
                        threshold_critical=self.thresholds['api_response_time']['critical'],
                        timestamp=datetime.utcnow()
                    )
                    
        except Exception as e:
            return HealthMetric(
                name=f"api_response_time_{url.split('/')[-1]}",
                value=timeout + 1,  # Indicate timeout exceeded
                unit="seconds",
                status=HealthStatus.CRITICAL,
                threshold_warning=self.thresholds['api_response_time']['warning'],
                threshold_critical=self.thresholds['api_response_time']['critical'],
                timestamp=datetime.utcnow()
            )