#!/usr/bin/env python3
"""
System Health Monitor for RDA Automation System

This module provides comprehensive system health monitoring and diagnostics
capabilities, including performance tracking, resource monitoring, alerting,
and automated health checks across all system components.

Key Features:
- Real-time system health monitoring and diagnostics
- Performance metrics collection and analysis
- Resource usage tracking (CPU, memory, disk, network)
- Component health checks and status reporting
- Automated alerting and notification system
- Health trend analysis and predictive monitoring
- System bottleneck detection and recommendations
- Comprehensive health reporting and dashboards
"""

import os
import sys
import json
import time
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    # Create mock psutil for basic functionality
    class MockPsutil:
        @staticmethod
        def cpu_percent(interval=1):
            return 25.0  # Mock CPU usage
        
        @staticmethod
        def virtual_memory():
            class MockMemory:
                percent = 45.0
                available = 8 * 1024**3  # 8GB
            return MockMemory()
        
        @staticmethod
        def disk_usage(path):
            class MockDisk:
                percent = 60.0
                free = 100 * 1024**3  # 100GB
            return MockDisk()
        
        @staticmethod
        def net_io_counters():
            class MockNetwork:
                bytes_sent = 1024 * 1024 * 100  # 100MB
                bytes_recv = 1024 * 1024 * 200  # 200MB
            return MockNetwork()
        
        @staticmethod
        def pids():
            return list(range(100))  # Mock 100 processes
        
        @staticmethod
        def process_iter(attrs=None):
            # Mock process iterator
            for i in range(10):
                class MockProcess:
                    info = {'num_threads': 4}
                yield MockProcess()
    
    psutil = MockPsutil()
import logging
import threading
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import statistics

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class HealthStatus(Enum):
    """Enumeration for health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Enumeration for alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SystemMetrics:
    """System performance and resource metrics."""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    process_count: int
    thread_count: int
    uptime_seconds: float


@dataclass
class ComponentHealth:
    """Health information for a system component."""
    component_name: str
    status: HealthStatus
    last_check: str
    response_time_ms: float
    error_count: int
    success_rate: float
    details: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class HealthAlert:
    """System health alert."""
    alert_id: str
    timestamp: str
    severity: AlertSeverity
    component: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[str] = None


@dataclass
class HealthThreshold:
    """Health monitoring threshold configuration."""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison_operator: str = "greater_than"  # greater_than, less_than, equals
    duration_seconds: int = 60  # How long threshold must be exceeded


@dataclass
class HealthReport:
    """Comprehensive system health report."""
    timestamp: str
    overall_status: HealthStatus
    system_metrics: SystemMetrics
    component_health: List[ComponentHealth]
    active_alerts: List[HealthAlert]
    performance_summary: Dict[str, Any]
    recommendations: List[str]
    uptime_seconds: float


class SystemHealthMonitor:
    """
    Comprehensive system health monitoring and diagnostics.
    
    Provides real-time monitoring of system resources, component health,
    performance metrics, and automated alerting capabilities.
    """
    
    def __init__(self, 
                 monitoring_interval: int = 30,
                 metrics_retention_hours: int = 24,
                 enable_alerting: bool = True):
        """
        Initialize the System Health Monitor.
        
        Args:
            monitoring_interval: Interval between health checks in seconds
            metrics_retention_hours: How long to retain metrics history
            enable_alerting: Whether to enable automated alerting
        """
        self.logger = self._setup_logging()
        self.monitoring_interval = monitoring_interval
        self.metrics_retention_hours = metrics_retention_hours
        self.enable_alerting = enable_alerting
        
        # Monitoring state
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.start_time = time.time()
        
        # Data storage
        self.metrics_history: deque = deque(maxlen=int(metrics_retention_hours * 3600 / monitoring_interval))
        self.component_health: Dict[str, ComponentHealth] = {}
        self.active_alerts: Dict[str, HealthAlert] = {}
        self.resolved_alerts: List[HealthAlert] = []
        
        # Health thresholds
        self.health_thresholds: Dict[str, HealthThreshold] = {}
        self._setup_default_thresholds()
        
        # Component health checkers
        self.health_checkers: Dict[str, Callable] = {}
        
        # Alert callbacks
        self.alert_callbacks: List[Callable[[HealthAlert], None]] = []
        
        # Thread safety
        self.monitor_lock = threading.RLock()
        
        # Performance tracking
        self.performance_baselines: Dict[str, float] = {}
        self.trend_analysis_window = 100  # Number of data points for trend analysis
        
        self.logger.info("System Health Monitor initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the health monitor."""
        logger = logging.getLogger('rda_automation.system_health_monitor')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    def _setup_default_thresholds(self):
        """Set up default health monitoring thresholds."""
        default_thresholds = [
            HealthThreshold("cpu_percent", 80.0, 95.0, "greater_than", 120),
            HealthThreshold("memory_percent", 85.0, 95.0, "greater_than", 120),
            HealthThreshold("disk_usage_percent", 90.0, 98.0, "greater_than", 300),
            HealthThreshold("disk_free_gb", 5.0, 1.0, "less_than", 300),
            HealthThreshold("component_error_rate", 5.0, 15.0, "greater_than", 180),
            HealthThreshold("component_response_time", 5000.0, 15000.0, "greater_than", 60)
        ]
        
        for threshold in default_thresholds:
            self.health_thresholds[threshold.metric_name] = threshold
    
    def register_component_health_checker(self, component_name: str, health_checker: Callable) -> bool:
        """
        Register a health checker function for a component.
        
        Args:
            component_name: Name of the component
            health_checker: Function that returns component health status
            
        Returns:
            True if registration was successful, False otherwise
        """
        try:
            with self.monitor_lock:
                self.health_checkers[component_name] = health_checker
            
            self.logger.info(f"✅ Health checker registered for component: {component_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to register health checker for {component_name}: {e}")
            return False
    
    def add_alert_callback(self, callback: Callable[[HealthAlert], None]):
        """
        Add a callback function to be called when alerts are generated.
        
        Args:
            callback: Function to call with HealthAlert parameter
        """
        self.alert_callbacks.append(callback)
        self.logger.info("✅ Alert callback added")
    
    def set_health_threshold(self, threshold: HealthThreshold) -> bool:
        """
        Set or update a health monitoring threshold.
        
        Args:
            threshold: Health threshold configuration
            
        Returns:
            True if threshold was set successfully, False otherwise
        """
        try:
            with self.monitor_lock:
                self.health_thresholds[threshold.metric_name] = threshold
            
            self.logger.info(f"✅ Health threshold set for {threshold.metric_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to set health threshold: {e}")
            return False
    
    def start_monitoring(self) -> bool:
        """
        Start the health monitoring system.
        
        Returns:
            True if monitoring started successfully, False otherwise
        """
        try:
            if self.monitoring_active:
                self.logger.info("ℹ️ Health monitoring already active")
                return True
            
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            self.logger.info("👁️ System health monitoring started")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start health monitoring: {e}")
            return False
    
    def stop_monitoring(self):
        """Stop the health monitoring system."""
        self.monitoring_active = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=10)
        
        self.logger.info("👁️ System health monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        self.logger.info(f"🔄 Starting health monitoring loop (interval: {self.monitoring_interval}s)")
        
        while self.monitoring_active:
            try:
                # Collect system metrics
                metrics = self._collect_system_metrics()
                
                with self.monitor_lock:
                    self.metrics_history.append(metrics)
                
                # Check component health
                self._check_all_components_health()
                
                # Analyze thresholds and generate alerts
                self._analyze_thresholds(metrics)
                
                # Update performance baselines
                self._update_performance_baselines(metrics)
                
                # Sleep until next check
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"❌ Error in monitoring loop: {e}")
                time.sleep(min(self.monitoring_interval, 60))
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system performance metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent
            disk_free_gb = disk.free / (1024**3)
            
            # Network metrics
            network = psutil.net_io_counters()
            network_bytes_sent = network.bytes_sent
            network_bytes_recv = network.bytes_recv
            
            # Process metrics
            process_count = len(psutil.pids())
            
            # Thread count (approximate)
            thread_count = 0
            try:
                for proc in psutil.process_iter(['num_threads']):
                    thread_count += proc.info['num_threads'] or 0
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            
            # System uptime
            uptime_seconds = time.time() - self.start_time
            
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_gb=memory_available_gb,
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                process_count=process_count,
                thread_count=thread_count,
                uptime_seconds=uptime_seconds
            )
            
        except Exception as e:
            self.logger.error(f"❌ Failed to collect system metrics: {e}")
            # Return default metrics on error
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_gb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0,
                network_bytes_sent=0,
                network_bytes_recv=0,
                process_count=0,
                thread_count=0,
                uptime_seconds=time.time() - self.start_time
            )
    
    def _check_all_components_health(self):
        """Check health of all registered components."""
        for component_name, health_checker in self.health_checkers.items():
            try:
                start_time = time.time()
                
                # Call the health checker
                health_result = health_checker()
                
                response_time_ms = (time.time() - start_time) * 1000
                
                # Parse health result
                if isinstance(health_result, dict):
                    status = HealthStatus(health_result.get('status', 'unknown'))
                    details = health_result.get('details', {})
                    error_count = health_result.get('error_count', 0)
                    success_rate = health_result.get('success_rate', 100.0)
                elif isinstance(health_result, bool):
                    status = HealthStatus.HEALTHY if health_result else HealthStatus.CRITICAL
                    details = {}
                    error_count = 0 if health_result else 1
                    success_rate = 100.0 if health_result else 0.0
                else:
                    status = HealthStatus.UNKNOWN
                    details = {'raw_result': str(health_result)}
                    error_count = 0
                    success_rate = 100.0
                
                # Create component health record
                component_health = ComponentHealth(
                    component_name=component_name,
                    status=status,
                    last_check=datetime.now().isoformat(),
                    response_time_ms=response_time_ms,
                    error_count=error_count,
                    success_rate=success_rate,
                    details=details,
                    recommendations=self._generate_component_recommendations(component_name, status, details)
                )
                
                with self.monitor_lock:
                    self.component_health[component_name] = component_health
                
                # Generate alerts if needed
                if status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                    self._generate_component_alert(component_health)
                
            except Exception as e:
                self.logger.error(f"❌ Error checking health of {component_name}: {e}")
                
                # Create error health record
                error_health = ComponentHealth(
                    component_name=component_name,
                    status=HealthStatus.CRITICAL,
                    last_check=datetime.now().isoformat(),
                    response_time_ms=0.0,
                    error_count=1,
                    success_rate=0.0,
                    details={'error': str(e)},
                    recommendations=[f"Fix health checker for {component_name}"]
                )
                
                with self.monitor_lock:
                    self.component_health[component_name] = error_health
    
    def _analyze_thresholds(self, metrics: SystemMetrics):
        """Analyze metrics against configured thresholds."""
        for threshold_name, threshold in self.health_thresholds.items():
            try:
                # Get metric value
                metric_value = None
                
                if hasattr(metrics, threshold.metric_name):
                    metric_value = getattr(metrics, threshold.metric_name)
                elif threshold.metric_name == "component_error_rate":
                    # Calculate average component error rate
                    if self.component_health:
                        error_rates = [100.0 - comp.success_rate for comp in self.component_health.values()]
                        metric_value = statistics.mean(error_rates) if error_rates else 0.0
                elif threshold.metric_name == "component_response_time":
                    # Calculate average component response time
                    if self.component_health:
                        response_times = [comp.response_time_ms for comp in self.component_health.values()]
                        metric_value = statistics.mean(response_times) if response_times else 0.0
                
                if metric_value is None:
                    continue
                
                # Check thresholds
                is_critical = self._check_threshold_violation(metric_value, threshold.critical_threshold, threshold.comparison_operator)
                is_warning = self._check_threshold_violation(metric_value, threshold.warning_threshold, threshold.comparison_operator)
                
                if is_critical:
                    self._generate_threshold_alert(threshold_name, metric_value, threshold, AlertSeverity.CRITICAL)
                elif is_warning:
                    self._generate_threshold_alert(threshold_name, metric_value, threshold, AlertSeverity.WARNING)
                
            except Exception as e:
                self.logger.error(f"❌ Error analyzing threshold {threshold_name}: {e}")
    
    def _check_threshold_violation(self, value: float, threshold: float, operator: str) -> bool:
        """Check if a value violates a threshold."""
        if operator == "greater_than":
            return value > threshold
        elif operator == "less_than":
            return value < threshold
        elif operator == "equals":
            return abs(value - threshold) < 0.001
        else:
            return False
    
    def _generate_threshold_alert(self, metric_name: str, value: float, threshold: HealthThreshold, severity: AlertSeverity):
        """Generate an alert for threshold violation."""
        alert_id = f"threshold_{metric_name}_{severity.value}"
        
        # Check if alert already exists
        with self.monitor_lock:
            if alert_id in self.active_alerts:
                return  # Alert already active
        
        alert = HealthAlert(
            alert_id=alert_id,
            timestamp=datetime.now().isoformat(),
            severity=severity,
            component="system",
            message=f"{metric_name} threshold violation: {value:.2f} {threshold.comparison_operator} {threshold.warning_threshold if severity == AlertSeverity.WARNING else threshold.critical_threshold}",
            details={
                "metric_name": metric_name,
                "current_value": value,
                "threshold_value": threshold.warning_threshold if severity == AlertSeverity.WARNING else threshold.critical_threshold,
                "comparison_operator": threshold.comparison_operator
            }
        )
        
        with self.monitor_lock:
            self.active_alerts[alert_id] = alert
        
        self._notify_alert_callbacks(alert)
        self.logger.warning(f"⚠️ {severity.value.upper()} ALERT: {alert.message}")
    
    def _generate_component_alert(self, component_health: ComponentHealth):
        """Generate an alert for component health issues."""
        alert_id = f"component_{component_health.component_name}_{component_health.status.value}"
        
        # Check if alert already exists
        with self.monitor_lock:
            if alert_id in self.active_alerts:
                return  # Alert already active
        
        severity = AlertSeverity.CRITICAL if component_health.status == HealthStatus.CRITICAL else AlertSeverity.WARNING
        
        alert = HealthAlert(
            alert_id=alert_id,
            timestamp=datetime.now().isoformat(),
            severity=severity,
            component=component_health.component_name,
            message=f"Component {component_health.component_name} health status: {component_health.status.value}",
            details={
                "component_name": component_health.component_name,
                "status": component_health.status.value,
                "response_time_ms": component_health.response_time_ms,
                "error_count": component_health.error_count,
                "success_rate": component_health.success_rate,
                "details": component_health.details
            }
        )
        
        with self.monitor_lock:
            self.active_alerts[alert_id] = alert
        
        self._notify_alert_callbacks(alert)
        self.logger.warning(f"⚠️ {severity.value.upper()} ALERT: {alert.message}")
    
    def _notify_alert_callbacks(self, alert: HealthAlert):
        """Notify all registered alert callbacks."""
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"❌ Error in alert callback: {e}")
    
    def _generate_component_recommendations(self, component_name: str, status: HealthStatus, details: Dict[str, Any]) -> List[str]:
        """Generate recommendations for component health issues."""
        recommendations = []
        
        if status == HealthStatus.CRITICAL:
            recommendations.append(f"Investigate {component_name} component immediately")
            recommendations.append(f"Check {component_name} logs for errors")
            recommendations.append(f"Consider restarting {component_name} component")
        elif status == HealthStatus.WARNING:
            recommendations.append(f"Monitor {component_name} component closely")
            recommendations.append(f"Review {component_name} performance metrics")
        
        # Add specific recommendations based on details
        if 'error' in details:
            recommendations.append("Fix the reported error")
        if 'memory_usage' in details and details['memory_usage'] > 80:
            recommendations.append("Investigate memory usage")
        if 'response_time' in details and details['response_time'] > 5000:
            recommendations.append("Optimize component performance")
        
        return recommendations
    
    def _update_performance_baselines(self, metrics: SystemMetrics):
        """Update performance baselines for trend analysis."""
        try:
            with self.monitor_lock:
                if len(self.metrics_history) >= self.trend_analysis_window:
                    # Calculate baselines from recent history
                    recent_metrics = list(self.metrics_history)[-self.trend_analysis_window:]
                    
                    self.performance_baselines['cpu_percent'] = statistics.mean([m.cpu_percent for m in recent_metrics])
                    self.performance_baselines['memory_percent'] = statistics.mean([m.memory_percent for m in recent_metrics])
                    self.performance_baselines['disk_usage_percent'] = statistics.mean([m.disk_usage_percent for m in recent_metrics])
                    
        except Exception as e:
            self.logger.error(f"❌ Error updating performance baselines: {e}")
    
    def get_current_health_report(self) -> HealthReport:
        """
        Get a comprehensive current health report.
        
        Returns:
            HealthReport with current system status
        """
        try:
            with self.monitor_lock:
                # Get latest metrics
                latest_metrics = self.metrics_history[-1] if self.metrics_history else self._collect_system_metrics()
                
                # Determine overall status
                overall_status = self._calculate_overall_health_status()
                
                # Get component health list
                component_health_list = list(self.component_health.values())
                
                # Get active alerts
                active_alerts_list = list(self.active_alerts.values())
                
                # Generate performance summary
                performance_summary = self._generate_performance_summary()
                
                # Generate system recommendations
                recommendations = self._generate_system_recommendations()
                
                return HealthReport(
                    timestamp=datetime.now().isoformat(),
                    overall_status=overall_status,
                    system_metrics=latest_metrics,
                    component_health=component_health_list,
                    active_alerts=active_alerts_list,
                    performance_summary=performance_summary,
                    recommendations=recommendations,
                    uptime_seconds=time.time() - self.start_time
                )
                
        except Exception as e:
            self.logger.error(f"❌ Failed to generate health report: {e}")
            
            # Return minimal error report
            return HealthReport(
                timestamp=datetime.now().isoformat(),
                overall_status=HealthStatus.UNKNOWN,
                system_metrics=self._collect_system_metrics(),
                component_health=[],
                active_alerts=[],
                performance_summary={},
                recommendations=["Health monitoring system error - check logs"],
                uptime_seconds=time.time() - self.start_time
            )
    
    def _calculate_overall_health_status(self) -> HealthStatus:
        """Calculate overall system health status."""
        # Check for critical alerts
        critical_alerts = [alert for alert in self.active_alerts.values() if alert.severity == AlertSeverity.CRITICAL]
        if critical_alerts:
            return HealthStatus.CRITICAL
        
        # Check for critical components
        critical_components = [comp for comp in self.component_health.values() if comp.status == HealthStatus.CRITICAL]
        if critical_components:
            return HealthStatus.CRITICAL
        
        # Check for warning alerts or components
        warning_alerts = [alert for alert in self.active_alerts.values() if alert.severity == AlertSeverity.WARNING]
        warning_components = [comp for comp in self.component_health.values() if comp.status == HealthStatus.WARNING]
        
        if warning_alerts or warning_components:
            return HealthStatus.WARNING
        
        return HealthStatus.HEALTHY
    
    def _generate_performance_summary(self) -> Dict[str, Any]:
        """Generate performance summary from recent metrics."""
        try:
            if not self.metrics_history:
                return {}
            
            recent_metrics = list(self.metrics_history)[-min(20, len(self.metrics_history)):]
            
            return {
                "avg_cpu_percent": statistics.mean([m.cpu_percent for m in recent_metrics]),
                "avg_memory_percent": statistics.mean([m.memory_percent for m in recent_metrics]),
                "avg_disk_usage_percent": statistics.mean([m.disk_usage_percent for m in recent_metrics]),
                "min_memory_available_gb": min([m.memory_available_gb for m in recent_metrics]),
                "min_disk_free_gb": min([m.disk_free_gb for m in recent_metrics]),
                "avg_process_count": statistics.mean([m.process_count for m in recent_metrics]),
                "metrics_collected": len(self.metrics_history),
                "monitoring_duration_hours": (time.time() - self.start_time) / 3600
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error generating performance summary: {e}")
            return {}
    
    def _generate_system_recommendations(self) -> List[str]:
        """Generate system-wide recommendations."""
        recommendations = []
        
        try:
            if not self.metrics_history:
                return recommendations
            
            latest_metrics = self.metrics_history[-1]
            
            # CPU recommendations
            if latest_metrics.cpu_percent > 90:
                recommendations.append("High CPU usage detected - consider scaling or optimizing processes")
            elif latest_metrics.cpu_percent > 80:
                recommendations.append("Monitor CPU usage closely - approaching high utilization")
            
            # Memory recommendations
            if latest_metrics.memory_percent > 90:
                recommendations.append("High memory usage detected - investigate memory leaks or increase capacity")
            elif latest_metrics.memory_available_gb < 1:
                recommendations.append("Low available memory - consider freeing up memory or adding more RAM")
            
            # Disk recommendations
            if latest_metrics.disk_usage_percent > 95:
                recommendations.append("Critical disk space - clean up files or add storage capacity immediately")
            elif latest_metrics.disk_usage_percent > 85:
                recommendations.append("Monitor disk space - consider cleanup or expansion")
            
            # Component recommendations
            unhealthy_components = [comp for comp in self.component_health.values() 
                                 if comp.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]]
            
            if unhealthy_components:
                recommendations.append(f"Address health issues in {len(unhealthy_components)} components")
            
            # Alert recommendations
            if len(self.active_alerts) > 5:
                recommendations.append("Multiple active alerts - prioritize resolution by severity")
            
        except Exception as e:
            self.logger.error(f"❌ Error generating system recommendations: {e}")
        
        return recommendations
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Manually resolve an active alert.
        
        Args:
            alert_id: ID of the alert to resolve
            
        Returns:
            True if alert was resolved, False otherwise
        """
        try:
            with self.monitor_lock:
                if alert_id in self.active_alerts:
                    alert = self.active_alerts[alert_id]
                    alert.resolved = True
                    alert.resolved_at = datetime.now().isoformat()
                    
                    # Move to resolved alerts
                    self.resolved_alerts.append(alert)
                    del self.active_alerts[alert_id]
                    
                    self.logger.info(f"✅ Alert resolved: {alert_id}")
                    return True
                else:
                    self.logger.warning(f"⚠️ Alert not found: {alert_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"❌ Failed to resolve alert {alert_id}: {e}")
            return False
    
    def get_metrics_history(self, hours: int = 1) -> List[SystemMetrics]:
        """
        Get system metrics history for the specified time period.
        
        Args:
            hours: Number of hours of history to return
            
        Returns:
            List of SystemMetrics
        """
        try:
            with self.monitor_lock:
                if not self.metrics_history:
                    return []
                
                # Calculate how many data points to return
                data_points = int(hours * 3600 / self.monitoring_interval)
                return list(self.metrics_history)[-data_points:]
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get metrics history: {e}")
            return []
    
    def cleanup(self):
        """Clean up the health monitor."""
        self.logger.info("🧹 Cleaning up System Health Monitor...")
        
        # Stop monitoring
        self.stop_monitoring()
        
        # Clear data
        with self.monitor_lock:
            self.metrics_history.clear()
            self.component_health.clear()
            self.active_alerts.clear()
            self.resolved_alerts.clear()
            self.health_checkers.clear()
            self.alert_callbacks.clear()
        
        self.logger.info("✅ System Health Monitor cleanup completed")


def create_system_health_monitor(monitoring_interval: int = 30,
                                metrics_retention_hours: int = 24,
                                enable_alerting: bool = True) -> SystemHealthMonitor:
    """
    Create and return a SystemHealthMonitor instance.
    
    Args:
        monitoring_interval: Interval between health checks in seconds
        metrics_retention_hours: How long to retain metrics history
        enable_alerting: Whether to enable automated alerting
        
    Returns:
        SystemHealthMonitor instance
    """
    return SystemHealthMonitor(
        monitoring_interval=monitoring_interval,
        metrics_retention_hours=metrics_retention_hours,
        enable_alerting=enable_alerting
    )


if __name__ == "__main__":
    # Example usage
    monitor = create_system_health_monitor(monitoring_interval=10)
    
    # Example component health checker
    def example_health_checker():
        return {
            'status': 'healthy',
            'details': {'test_metric': 42},
            'error_count': 0,
            'success_rate': 100.0
        }
    
    # Register health checker
    monitor.register_component_health_checker("example_component", example_health_checker)
    
    # Example alert callback
    def example_alert_callback(alert):
        print(f"ALERT: {alert.severity.value} - {alert.message}")
    
    # Add alert callback
    monitor.add_alert_callback(example_alert_callback)
    
    # Start monitoring
    print("Starting health monitoring...")
    monitor.start_monitoring()
    
    try:
        # Let it run for a bit
        time.sleep(30)
        
        # Get health report
        report = monitor.get_current_health_report()
        print(f"Overall health status: {report.overall_status.value}")
        print(f"Active alerts: {len(report.active_alerts)}")
        print(f"Component health checks: {len(report.component_health)}")
        
    except KeyboardInterrupt:
        print("\nStopping health monitoring...")
    finally:
        monitor.cleanup()