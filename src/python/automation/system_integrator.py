#!/usr/bin/env python3
"""
System Integrator for RDA Automation System

This module provides the main integration orchestrator that coordinates all automation
components for seamless operation. It serves as the central hub that manages component
lifecycle, configuration, and inter-component communication.

Key Features:
- Unified system initialization and startup
- Component lifecycle management and coordination
- Cross-component error propagation and handling
- Shared configuration management across all components
- Real-time status synchronization between components
- Comprehensive logging and monitoring integration
- System health monitoring and diagnostics
- Graceful shutdown and cleanup procedures
"""

import os
import sys
import json
import time
import logging
import threading
import signal
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger

# Import all automation components
from automation.sequential_file_processor import (
    SequentialFileProcessor, ProcessingConfig, create_sequential_file_processor
)
from automation.smart_retry_manager import (
    SmartRetryManager, SmartRetryConfig, create_smart_retry_manager
)
from automation.error_manager import ErrorManager, create_error_manager
from automation.dashboard_enhancements import (
    DashboardEnhancements, create_dashboard_enhancements
)
from automation.completion_notifier import (
    CompletionNotifier, NotificationConfig, create_completion_notifier
)
from automation.capacity_manager import (
    CapacityManager, CapacityConfig, create_capacity_manager
)
from automation.automated_request_manager import (
    AutomatedRequestManager, RequestProcessingConfig, create_automated_request_manager
)
from automation.data_sync import RDADataSyncService, create_data_sync_service
from automation.enhanced_database_schema import (
    EnhancedDatabaseSchema, create_enhanced_schema_manager
)
from automation.workflow_orchestrator import (
    WorkflowOrchestrator, WorkflowConfig, create_workflow_orchestrator
)


class SystemState(Enum):
    """Enumeration for system states."""
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    PROCESSING = "processing"
    MONITORING = "monitoring"
    MAINTENANCE = "maintenance"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    RECOVERY = "recovery"


class ComponentStatus(Enum):
    """Enumeration for component status."""
    INACTIVE = "inactive"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class SystemConfiguration:
    """Unified system configuration."""
    # Database settings
    db_path: str = "src/python/data/automation_state.db"
    
    # File system settings
    control_files_dir: str = "src/python/control_files"
    base_download_dir: str = "downloaded_files"
    temp_download_dir: str = "./temp_downloads"
    reports_dir: str = "reports"
    logs_dir: str = "logs"
    
    # Processing settings
    enable_sequential_processing: bool = True
    enable_smart_retry: bool = True
    enable_error_tracking: bool = True
    enable_dashboard: bool = True
    enable_completion_notifications: bool = True
    enable_capacity_management: bool = True
    enable_automated_requests: bool = True
    enable_data_sync: bool = True
    enable_workflow_orchestration: bool = True
    
    # Timing settings
    main_cycle_interval: int = 300  # 5 minutes
    status_check_interval: int = 60  # 1 minute
    data_sync_interval: int = 900  # 15 minutes
    maintenance_interval: int = 3600  # 1 hour
    
    # Performance settings
    max_concurrent_operations: int = 5
    max_retry_attempts: int = 3
    request_timeout: int = 1800  # 30 minutes
    
    # Feature flags
    debug_mode: bool = False
    enable_detailed_logging: bool = True
    enable_performance_monitoring: bool = True
    enable_health_checks: bool = True
    
    # Notification settings
    enable_email_notifications: bool = False
    email_recipients: List[str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.email_recipients is None:
            self.email_recipients = []


@dataclass
class ComponentInfo:
    """Information about a system component."""
    name: str
    instance: Any
    status: ComponentStatus
    initialized_at: Optional[str]
    last_health_check: Optional[str]
    error_count: int = 0
    last_error: Optional[str] = None
    dependencies: List[str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class SystemStatus:
    """Comprehensive system status information."""
    system_state: SystemState
    uptime_seconds: float
    total_components: int
    active_components: int
    error_components: int
    last_health_check: str
    performance_metrics: Dict[str, Any]
    component_statuses: Dict[str, Dict[str, Any]]
    system_metrics: Dict[str, Any]
    recent_errors: List[Dict[str, Any]]
    last_updated: str


class SystemIntegrator:
    """
    Main system integrator that orchestrates all automation components.
    
    This class serves as the central hub for the RDA automation system,
    managing component lifecycle, configuration, and coordination.
    """
    
    def __init__(self, config: Optional[SystemConfiguration] = None):
        """
        Initialize the System Integrator.
        
        Args:
            config: System configuration
        """
        self.config = config or SystemConfiguration()
        self.logger = self._setup_logging()
        
        # System state
        self.system_state = SystemState.INITIALIZING
        self.start_time = None
        self.shutdown_requested = False
        
        # Component management
        self.components: Dict[str, ComponentInfo] = {}
        self.component_dependencies = self._define_component_dependencies()
        
        # Threading and synchronization
        self.system_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_operations)
        self.main_thread = None
        
        # System metrics
        self.system_metrics = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'total_errors': 0,
            'last_maintenance': None,
            'component_restarts': 0
        }
        
        # Error tracking
        self.recent_errors = []
        self.max_recent_errors = 100
        
        # Signal handling
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("System Integrator initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.system_integrator', level=logging.INFO)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        self.stop_system()
    
    def _define_component_dependencies(self) -> Dict[str, List[str]]:
        """Define component dependencies for proper initialization order."""
        return {
            'database_schema': [],
            'data_sync': ['database_schema'],
            'error_manager': ['database_schema'],
            'smart_retry_manager': ['database_schema', 'error_manager'],
            'capacity_manager': ['database_schema'],
            'automated_request_manager': ['database_schema', 'capacity_manager'],
            'completion_notifier': ['database_schema'],
            'dashboard_enhancements': ['database_schema', 'error_manager'],
            'sequential_file_processor': ['database_schema', 'smart_retry_manager', 'completion_notifier'],
            'workflow_orchestrator': ['automated_request_manager', 'capacity_manager', 'data_sync']
        }
    
    def _transition_system_state(self, new_state: SystemState, reason: str = ""):
        """Transition to a new system state."""
        old_state = self.system_state
        
        with self.system_lock:
            self.system_state = new_state
        
        self.logger.info(f"🔄 System state transition: {old_state.value} -> {new_state.value}" + 
                        (f" ({reason})" if reason else ""))
    
    def _record_error(self, component_name: str, error: Exception, context: str = ""):
        """Record an error for tracking and analysis."""
        error_info = {
            'timestamp': datetime.now().isoformat(),
            'component': component_name,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context
        }
        
        with self.system_lock:
            self.recent_errors.append(error_info)
            if len(self.recent_errors) > self.max_recent_errors:
                self.recent_errors = self.recent_errors[-self.max_recent_errors:]
            
            self.system_metrics['total_errors'] += 1
            
            # Update component error count
            if component_name in self.components:
                self.components[component_name].error_count += 1
                self.components[component_name].last_error = str(error)
        
        self.logger.error(f"❌ Error in {component_name}: {error}" + 
                         (f" (Context: {context})" if context else ""))
    
    def initialize_component(self, component_name: str) -> bool:
        """
        Initialize a specific component.
        
        Args:
            component_name: Name of the component to initialize
            
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            self.logger.info(f"🔧 Initializing component: {component_name}")
            
            # Check dependencies
            dependencies = self.component_dependencies.get(component_name, [])
            for dep in dependencies:
                if dep not in self.components or self.components[dep].status != ComponentStatus.ACTIVE:
                    self.logger.error(f"❌ Dependency {dep} not available for {component_name}")
                    return False
            
            # Initialize component based on type
            component_instance = None
            
            if component_name == 'database_schema':
                component_instance = create_enhanced_schema_manager(self.config.db_path)
                # Ensure enhanced tables are created
                success = component_instance.create_enhanced_tables()
                if not success:
                    raise Exception("Failed to create enhanced database tables")
            
            elif component_name == 'data_sync':
                component_instance = create_data_sync_service(self.config.db_path)
            
            elif component_name == 'error_manager':
                component_instance = create_error_manager(
                    self.config.db_path,
                    max_retries=self.config.max_retry_attempts
                )
            
            elif component_name == 'smart_retry_manager':
                retry_config = SmartRetryConfig(
                    db_path=self.config.db_path,
                    enable_detailed_logging=self.config.enable_detailed_logging
                )
                component_instance = create_smart_retry_manager(retry_config)
            
            elif component_name == 'capacity_manager':
                capacity_config = CapacityConfig(
                    monitoring_interval=self.config.status_check_interval
                )
                component_instance = create_capacity_manager(capacity_config, self.config.db_path)
            
            elif component_name == 'automated_request_manager':
                request_config = RequestProcessingConfig(
                    status_check_interval=self.config.status_check_interval,
                    max_retry_attempts=self.config.max_retry_attempts
                )
                component_instance = create_automated_request_manager(
                    request_config, self.config.db_path, self.config.base_download_dir
                )
            
            elif component_name == 'completion_notifier':
                notification_config = NotificationConfig(
                    enable_email=self.config.enable_email_notifications,
                    email_recipients=self.config.email_recipients,
                    enable_console=True,
                    enable_file_report=True,
                    report_directory=self.config.reports_dir
                )
                component_instance = create_completion_notifier(
                    self.config.db_path, notification_config
                )
            
            elif component_name == 'dashboard_enhancements':
                component_instance = create_dashboard_enhancements(self.config.db_path)
            
            elif component_name == 'sequential_file_processor':
                processing_config = ProcessingConfig(
                    control_files_dir=self.config.control_files_dir,
                    db_path=self.config.db_path,
                    enable_smart_retry=self.config.enable_smart_retry,
                    enable_completion_notifications=self.config.enable_completion_notifications
                )
                component_instance = create_sequential_file_processor(processing_config)
            
            elif component_name == 'workflow_orchestrator':
                workflow_config = WorkflowConfig(
                    main_cycle_interval=self.config.main_cycle_interval,
                    db_path=self.config.db_path,
                    base_download_dir=self.config.base_download_dir,
                    control_files_dir=self.config.control_files_dir,
                    debug_mode=self.config.debug_mode
                )
                component_instance = create_workflow_orchestrator(workflow_config)
            
            else:
                raise ValueError(f"Unknown component: {component_name}")
            
            # Register component
            component_info = ComponentInfo(
                name=component_name,
                instance=component_instance,
                status=ComponentStatus.ACTIVE,
                initialized_at=datetime.now().isoformat(),
                last_health_check=datetime.now().isoformat(),
                dependencies=dependencies
            )
            
            self.components[component_name] = component_info
            self.logger.info(f"✅ Component {component_name} initialized successfully")
            return True
            
        except Exception as e:
            self._record_error(component_name, e, "component_initialization")
            
            # Register failed component
            component_info = ComponentInfo(
                name=component_name,
                instance=None,
                status=ComponentStatus.ERROR,
                initialized_at=None,
                last_health_check=datetime.now().isoformat(),
                error_count=1,
                last_error=str(e),
                dependencies=self.component_dependencies.get(component_name, [])
            )
            self.components[component_name] = component_info
            return False
    
    def initialize_all_components(self) -> bool:
        """
        Initialize all system components in dependency order.
        
        Returns:
            True if all components were initialized successfully, False otherwise
        """
        self.logger.info("🚀 Initializing all system components...")
        self._transition_system_state(SystemState.INITIALIZING, "Starting component initialization")
        
        # Create necessary directories
        for directory in [self.config.base_download_dir, self.config.temp_download_dir, 
                         self.config.reports_dir, self.config.logs_dir]:
            Path(directory).mkdir(parents=True, exist_ok=True)
        
        # Determine initialization order based on dependencies
        initialization_order = self._get_initialization_order()
        
        successful_components = 0
        total_components = len(initialization_order)
        
        for component_name in initialization_order:
            # Skip disabled components
            if not self._is_component_enabled(component_name):
                self.logger.info(f"⏭️ Skipping disabled component: {component_name}")
                continue
            
            success = self.initialize_component(component_name)
            if success:
                successful_components += 1
            else:
                self.logger.error(f"❌ Failed to initialize component: {component_name}")
                
                # Check if this is a critical component
                if self._is_critical_component(component_name):
                    self.logger.error(f"💥 Critical component {component_name} failed - aborting initialization")
                    self._transition_system_state(SystemState.ERROR, f"Critical component {component_name} failed")
                    return False
        
        success_rate = (successful_components / total_components) * 100 if total_components > 0 else 0
        
        if success_rate >= 80:  # Allow system to start with 80% of components working
            self.logger.info(f"✅ System initialization completed: {successful_components}/{total_components} components active ({success_rate:.1f}%)")
            return True
        else:
            self.logger.error(f"❌ System initialization failed: Only {successful_components}/{total_components} components active ({success_rate:.1f}%)")
            self._transition_system_state(SystemState.ERROR, "Insufficient components initialized")
            return False
    
    def _get_initialization_order(self) -> List[str]:
        """Get component initialization order based on dependencies."""
        # Topological sort of dependencies
        order = []
        visited = set()
        temp_visited = set()
        
        def visit(component):
            if component in temp_visited:
                raise ValueError(f"Circular dependency detected involving {component}")
            if component in visited:
                return
            
            temp_visited.add(component)
            for dependency in self.component_dependencies.get(component, []):
                visit(dependency)
            temp_visited.remove(component)
            visited.add(component)
            order.append(component)
        
        for component in self.component_dependencies.keys():
            if component not in visited:
                visit(component)
        
        return order
    
    def _is_component_enabled(self, component_name: str) -> bool:
        """Check if a component is enabled in configuration."""
        component_flags = {
            'database_schema': True,  # Always required
            'data_sync': self.config.enable_data_sync,
            'error_manager': self.config.enable_error_tracking,
            'smart_retry_manager': self.config.enable_smart_retry,
            'capacity_manager': self.config.enable_capacity_management,
            'automated_request_manager': self.config.enable_automated_requests,
            'completion_notifier': self.config.enable_completion_notifications,
            'dashboard_enhancements': self.config.enable_dashboard,
            'sequential_file_processor': self.config.enable_sequential_processing,
            'workflow_orchestrator': self.config.enable_workflow_orchestration
        }
        return component_flags.get(component_name, True)
    
    def _is_critical_component(self, component_name: str) -> bool:
        """Check if a component is critical for system operation."""
        critical_components = {
            'database_schema', 'error_manager', 'automated_request_manager'
        }
        return component_name in critical_components
    
    def start_system(self) -> bool:
        """
        Start the complete RDA automation system.
        
        Returns:
            True if system started successfully, False otherwise
        """
        try:
            self.logger.info("🚀 Starting RDA Automation System...")
            self._transition_system_state(SystemState.STARTING, "System startup initiated")
            
            self.start_time = time.time()
            
            # Initialize all components
            if not self.initialize_all_components():
                return False
            
            # Start active components
            self._start_active_components()
            
            # Start main system loop
            self._start_main_loop()
            
            self._transition_system_state(SystemState.RUNNING, "System fully operational")
            self.logger.info("✅ RDA Automation System started successfully")
            return True
            
        except Exception as e:
            self._record_error("system", e, "system_startup")
            self._transition_system_state(SystemState.ERROR, f"Startup error: {e}")
            return False
    
    def _start_active_components(self):
        """Start components that have background processing."""
        for component_name, component_info in self.components.items():
            if component_info.status != ComponentStatus.ACTIVE:
                continue
            
            try:
                instance = component_info.instance
                
                # Start components with background processing
                if component_name == 'smart_retry_manager' and hasattr(instance, 'start_processing'):
                    instance.start_processing()
                    self.logger.info(f"🔄 Started background processing for {component_name}")
                
                elif component_name == 'capacity_manager' and hasattr(instance, 'start_capacity_monitoring'):
                    instance.start_capacity_monitoring()
                    self.logger.info(f"📊 Started capacity monitoring for {component_name}")
                
                elif component_name == 'automated_request_manager' and hasattr(instance, 'start_continuous_processing'):
                    instance.start_continuous_processing()
                    self.logger.info(f"⚙️ Started continuous processing for {component_name}")
                
            except Exception as e:
                self._record_error(component_name, e, "component_startup")
    
    def _start_main_loop(self):
        """Start the main system monitoring and coordination loop."""
        def main_loop():
            self.logger.info(f"🔄 Starting main system loop (interval: {self.config.main_cycle_interval}s)")
            
            last_health_check = time.time()
            last_maintenance = time.time()
            
            while not self.shutdown_requested and self.system_state in [SystemState.RUNNING, SystemState.PROCESSING, SystemState.MONITORING]:
                try:
                    current_time = time.time()
                    
                    # Health checks
                    if current_time - last_health_check >= self.config.status_check_interval:
                        self._perform_health_checks()
                        last_health_check = current_time
                    
                    # Maintenance
                    if current_time - last_maintenance >= self.config.maintenance_interval:
                        self._perform_maintenance()
                        last_maintenance = current_time
                    
                    # System coordination
                    self._coordinate_components()
                    
                    # Update metrics
                    self._update_system_metrics()
                    
                    time.sleep(min(self.config.status_check_interval, 60))
                    
                except Exception as e:
                    self._record_error("system", e, "main_loop")
                    if self.system_state != SystemState.ERROR:
                        self._transition_system_state(SystemState.RECOVERY, "Recovering from main loop error")
                        time.sleep(60)  # Wait before retrying
                        self._transition_system_state(SystemState.RUNNING, "Recovered from error")
            
            self.logger.info("🛑 Main system loop stopped")
        
        self.main_thread = threading.Thread(target=main_loop, daemon=True)
        self.main_thread.start()
    
    def _perform_health_checks(self):
        """Perform health checks on all components."""
        if not self.config.enable_health_checks:
            return
        
        self.logger.debug("🏥 Performing system health checks...")
        
        for component_name, component_info in self.components.items():
            try:
                if component_info.status == ComponentStatus.ACTIVE:
                    # Perform component-specific health checks
                    is_healthy = self._check_component_health(component_name, component_info.instance)
                    
                    if is_healthy:
                        component_info.last_health_check = datetime.now().isoformat()
                    else:
                        self.logger.warning(f"⚠️ Health check failed for {component_name}")
                        component_info.status = ComponentStatus.ERROR
                        
            except Exception as e:
                self._record_error(component_name, e, "health_check")
    
    def _check_component_health(self, component_name: str, instance: Any) -> bool:
        """Check health of a specific component."""
        try:
            # Component-specific health checks
            if hasattr(instance, 'get_processing_status'):
                status = instance.get_processing_status()
                return 'error' not in status
            elif hasattr(instance, 'get_current_capacity_status'):
                status = instance.get_current_capacity_status()
                return status is not None
            elif hasattr(instance, 'get_system_status'):
                status = instance.get_system_status()
                return 'error' not in status
            else:
                # Basic health check - instance exists and is not None
                return instance is not None
                
        except Exception:
            return False
    
    def _perform_maintenance(self):
        """Perform system maintenance tasks."""
        self.logger.info("🔧 Performing system maintenance...")
        self._transition_system_state(SystemState.MAINTENANCE, "Running maintenance tasks")
        
        try:
            # Database maintenance
            if 'database_schema' in self.components:
                db_manager = self.components['database_schema'].instance
                if hasattr(db_manager, 'optimize_database'):
                    db_manager.optimize_database()
            
            # Clean up old errors
            with self.system_lock:
                if len(self.recent_errors) > self.max_recent_errors // 2:
                    self.recent_errors = self.recent_errors[-(self.max_recent_errors // 2):]
            
            # Update maintenance timestamp
            self.system_metrics['last_maintenance'] = datetime.now().isoformat()
            
            self.logger.info("✅ System maintenance completed")
            
        except Exception as e:
            self._record_error("system", e, "maintenance")
        finally:
            self._transition_system_state(SystemState.RUNNING, "Maintenance completed")
    
    def _coordinate_components(self):
        """Coordinate between components for optimal operation."""
        # This is where cross-component coordination logic would go
        # For example, adjusting processing rates based on capacity
        pass
    
    def _update_system_metrics(self):
        """Update system-wide metrics."""
        with self.system_lock:
            active_components = sum(1 for c in self.components.values() if c.status == ComponentStatus.ACTIVE)
            error_components = sum(1 for c in self.components.values() if c.status == ComponentStatus.ERROR)
            
            self.system_metrics.update({
                'uptime_seconds': time.time() - self.start_time if self.start_time else 0,
                'active_components': active_components,
                'error_components': error_components,
                'total_components': len(self.components),
                'last_updated': datetime.now().isoformat()
            })
    
    def get_system_status(self) -> SystemStatus:
        """
        Get comprehensive system status.
        
        Returns:
            SystemStatus object with complete system information
        """
        try:
            uptime = time.time() - self.start_time if self.start_time else 0
            
            # Component statuses
            component_statuses = {}
            active_count = 0
            error_count = 0
            
            for name, info in self.components.items():
                component_statuses[name] = {
                    'status': info.status.value,
                    'initialized_at': info.initialized_at,
                    'last_health_check': info.last_health_check,
                    'error_count': info.error_count,
                    'last_error': info.last_error,
                    'dependencies': info.dependencies
                }
                
                if info.status == ComponentStatus.ACTIVE:
                    active_count += 1
                elif info.status == ComponentStatus.ERROR:
                    error_count += 1
            
            # Performance metrics
            performance_metrics = {
                'operations_per_hour': 0,  # Would calculate from system_metrics
                'error_rate': (error_count / len(self.components) * 100) if self.components else 0,
                'uptime_hours': uptime / 3600,
                'memory_usage': 0,  # Could add memory monitoring
                'cpu_usage': 0  # Could add CPU monitoring
            }
            
            return SystemStatus(
                system_state=self.system_state,
                uptime_seconds=uptime,
                total_components=len(self.components),
                active_components=active_count,
                error_components=error_count,
                last_health_check=datetime.now().isoformat(),
                performance_metrics=performance_metrics,
                component_statuses=component_statuses,
                system_metrics=self.system_metrics.copy(),
                recent_errors=self.recent_errors[-10:],  # Last 10 errors
                last_updated=datetime.now().isoformat()
            )
            
        except Exception as e:
            self._record_error("system", e, "get_system_status")
            return SystemStatus(
                system_state=SystemState.ERROR,
                uptime_seconds=0,
                total_components=0,
                active_components=0,
                error_components=0,
                last_health_check=datetime.now().isoformat(),
                performance_metrics={},
                component_statuses={},
                system_metrics={},
                recent_errors=[],
                last_updated=datetime.now().isoformat()
            )
    
    def stop_system(self):
        """
        Stop the complete RDA automation system gracefully.
        """
        self.logger.info("🛑 Stopping RDA Automation System...")
        self._transition_system_state(SystemState.STOPPING, "System shutdown initiated")
        
        try:
            # Request shutdown
            self.shutdown_requested = True
            
            # Stop main thread
            if self.main_thread and self.main_thread.is_alive():
                self.logger.info("⏹️ Stopping main system loop...")
                self.main_thread.join(timeout=30)
                if self.main_thread.is_alive():
                    self.logger.warning("⚠️ Main thread did not stop gracefully")
            
            # Stop all components
            self._stop_all_components()
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            self._transition_system_state(SystemState.STOPPED, "System shutdown completed")
            self.logger.info("✅ RDA Automation System stopped successfully")
            
        except Exception as e:
            self._record_error("system", e, "system_shutdown")
            self._transition_system_state(SystemState.ERROR, f"Shutdown error: {e}")
    
    def _stop_all_components(self):
        """Stop all system components gracefully."""
        self.logger.info("🔌 Stopping all system components...")
        
        # Stop components in reverse dependency order
        initialization_order = self._get_initialization_order()
        stop_order = list(reversed(initialization_order))
        
        for component_name in stop_order:
            if component_name not in self.components:
                continue
            
            component_info = self.components[component_name]
            if component_info.status not in [ComponentStatus.ACTIVE, ComponentStatus.ERROR]:
                continue
            
            try:
                self.logger.info(f"🔌 Stopping component: {component_name}")
                component_info.status = ComponentStatus.STOPPING
                
                instance = component_info.instance
                if instance is None:
                    continue
                
                # Component-specific shutdown procedures
                if component_name == 'smart_retry_manager' and hasattr(instance, 'stop_processing'):
                    instance.stop_processing()
                elif component_name == 'capacity_manager' and hasattr(instance, 'stop_capacity_monitoring'):
                    instance.stop_capacity_monitoring()
                elif component_name == 'automated_request_manager' and hasattr(instance, 'stop_continuous_processing'):
                    instance.stop_continuous_processing()
                elif component_name == 'workflow_orchestrator' and hasattr(instance, 'stop_orchestration'):
                    instance.stop_orchestration()
                
                # Generic cleanup if available
                if hasattr(instance, 'cleanup'):
                    instance.cleanup()
                elif hasattr(instance, 'close'):
                    instance.close()
                
                component_info.status = ComponentStatus.STOPPED
                self.logger.info(f"✅ Component {component_name} stopped successfully")
                
            except Exception as e:
                self._record_error(component_name, e, "component_shutdown")
                component_info.status = ComponentStatus.ERROR
    
    def restart_component(self, component_name: str) -> bool:
        """
        Restart a specific component.
        
        Args:
            component_name: Name of the component to restart
            
        Returns:
            True if restart was successful, False otherwise
        """
        try:
            self.logger.info(f"🔄 Restarting component: {component_name}")
            
            if component_name not in self.components:
                self.logger.error(f"❌ Component {component_name} not found")
                return False
            
            # Stop the component first
            component_info = self.components[component_name]
            if component_info.status == ComponentStatus.ACTIVE:
                component_info.status = ComponentStatus.STOPPING
                
                # Component-specific stop procedures
                instance = component_info.instance
                if instance:
                    if hasattr(instance, 'stop_processing'):
                        instance.stop_processing()
                    elif hasattr(instance, 'cleanup'):
                        instance.cleanup()
            
            # Reinitialize the component
            success = self.initialize_component(component_name)
            
            if success:
                self.system_metrics['component_restarts'] += 1
                self.logger.info(f"✅ Component {component_name} restarted successfully")
            else:
                self.logger.error(f"❌ Failed to restart component {component_name}")
            
            return success
            
        except Exception as e:
            self._record_error(component_name, e, "component_restart")
            return False
    
    def get_component_status(self, component_name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific component.
        
        Args:
            component_name: Name of the component
            
        Returns:
            Component status dictionary or None if not found
        """
        if component_name not in self.components:
            return None
        
        component_info = self.components[component_name]
        
        status = {
            'name': component_info.name,
            'status': component_info.status.value,
            'initialized_at': component_info.initialized_at,
            'last_health_check': component_info.last_health_check,
            'error_count': component_info.error_count,
            'last_error': component_info.last_error,
            'dependencies': component_info.dependencies
        }
        
        # Add component-specific status if available
        if component_info.instance and hasattr(component_info.instance, 'get_processing_status'):
            try:
                component_status = component_info.instance.get_processing_status()
                status['component_specific'] = component_status
            except Exception as e:
                status['component_specific_error'] = str(e)
        
        return status
    
    def execute_system_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a system-wide operation.
        
        Args:
            operation: Operation to execute
            **kwargs: Operation parameters
            
        Returns:
            Operation result dictionary
        """
        try:
            self.logger.info(f"🔧 Executing system operation: {operation}")
            
            if operation == "health_check":
                self._perform_health_checks()
                return {"success": True, "message": "Health check completed"}
            
            elif operation == "maintenance":
                self._perform_maintenance()
                return {"success": True, "message": "Maintenance completed"}
            
            elif operation == "restart_component":
                component_name = kwargs.get('component_name')
                if not component_name:
                    return {"success": False, "error": "component_name required"}
                
                success = self.restart_component(component_name)
                return {
                    "success": success,
                    "message": f"Component {component_name} {'restarted' if success else 'restart failed'}"
                }
            
            elif operation == "get_metrics":
                return {
                    "success": True,
                    "metrics": self.system_metrics.copy(),
                    "recent_errors": self.recent_errors[-5:]  # Last 5 errors
                }
            
            elif operation == "process_files":
                # Trigger file processing if sequential processor is available
                if 'sequential_file_processor' in self.components:
                    processor = self.components['sequential_file_processor'].instance
                    if hasattr(processor, 'start_processing'):
                        processor.start_processing()
                        return {"success": True, "message": "File processing started"}
                
                return {"success": False, "error": "Sequential file processor not available"}
            
            elif operation == "sync_data":
                # Trigger data synchronization
                if 'data_sync' in self.components:
                    sync_service = self.components['data_sync'].instance
                    if hasattr(sync_service, 'sync_all_data'):
                        sync_service.sync_all_data()
                        return {"success": True, "message": "Data synchronization started"}
                
                return {"success": False, "error": "Data sync service not available"}
            
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
            
        except Exception as e:
            self._record_error("system", e, f"execute_operation_{operation}")
            return {"success": False, "error": str(e)}
    
    def get_component_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all components with their basic information.
        
        Returns:
            List of component information dictionaries
        """
        components = []
        
        for name, info in self.components.items():
            components.append({
                'name': name,
                'status': info.status.value,
                'initialized_at': info.initialized_at,
                'error_count': info.error_count,
                'dependencies': info.dependencies,
                'enabled': self._is_component_enabled(name),
                'critical': self._is_critical_component(name)
            })
        
        return sorted(components, key=lambda x: x['name'])
    
    def wait_for_shutdown(self):
        """
        Wait for system shutdown to complete.
        This method blocks until the system is fully stopped.
        """
        try:
            if self.main_thread and self.main_thread.is_alive():
                self.main_thread.join()
            
            self.logger.info("🏁 System shutdown complete")
            
        except KeyboardInterrupt:
            self.logger.info("⚡ Forced shutdown requested")
            self.shutdown_requested = True
            self.stop_system()


def create_system_integrator(config: Optional[SystemConfiguration] = None) -> SystemIntegrator:
    """
    Create and return a SystemIntegrator instance.
    
    Args:
        config: System configuration (optional)
        
    Returns:
        SystemIntegrator instance
    """
    return SystemIntegrator(config)


def main():
    """
    Main entry point for running the system integrator standalone.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='RDA Automation System Integrator')
    parser.add_argument('--config', type=str, help='Configuration file path')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--operation', type=str, help='Execute specific operation')
    
    args = parser.parse_args()
    
    # Create configuration
    config = SystemConfiguration()
    if args.debug:
        config.debug_mode = True
    
    # Load configuration from file if provided
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r') as f:
                config_data = json.load(f)
                for key, value in config_data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return 1
    
    # Create and start system integrator
    integrator = create_system_integrator(config)
    
    try:
        if args.operation:
            # Execute specific operation
            result = integrator.execute_system_operation(args.operation)
            print(json.dumps(result, indent=2))
            return 0 if result.get('success') else 1
        else:
            # Start full system
            if integrator.start_system():
                print("✅ RDA Automation System started successfully")
                integrator.wait_for_shutdown()
                return 0
            else:
                print("❌ Failed to start RDA Automation System")
                return 1
                
    except KeyboardInterrupt:
        print("\n⚡ Shutdown requested by user")
        integrator.stop_system()
        return 0
    except Exception as e:
        print(f"❌ System error: {e}")
        return 1
    finally:
        integrator.stop_system()


if __name__ == "__main__":
    exit(main())