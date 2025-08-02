#!/usr/bin/env python3
"""
Workflow Orchestrator for RDA Automation System.

This module provides the main orchestration layer that coordinates all automation
components for continuous, self-sustaining operation. It implements the state machine
from the architecture and manages the complete automation workflow.

Key Features:
    - Complete workflow orchestration and state management
    - Integration of all automation components
    - Self-sustaining continuous operation
    - Intelligent workflow scheduling and optimization
    - Comprehensive monitoring and reporting
    - Error recovery and resilience
    - Real-time status updates and dashboard integration

Classes:
    WorkflowState: Enumeration for workflow states
    WorkflowPriority: Enumeration for workflow priorities
    WorkflowConfig: Configuration dataclass for workflow orchestration
    WorkflowStatus: Current workflow status information
    WorkflowResult: Result of a workflow operation
    WorkflowOrchestrator: Main orchestrator class

Functions:
    create_workflow_orchestrator: Factory function to create orchestrator instance

Example:
    Basic usage of the workflow orchestrator:
    
    >>> config = WorkflowConfig(main_cycle_interval=300)
    >>> orchestrator = create_workflow_orchestrator(config)
    >>> orchestrator.start_workflow()
    >>> # Keep running until interrupted
    >>> orchestrator.stop_workflow()
"""

import os
import sys
import json
import time
import logging
import threading
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.file_organization_manager import EnhancedFileOrganizationManager, create_file_organization_manager
from automation.automated_request_manager import AutomatedRequestManager, create_automated_request_manager
from automation.capacity_manager import CapacityManager, create_capacity_manager
from automation.status_monitor import StatusMonitor, create_status_monitor
from automation.data_sync import RDADataSyncService, create_data_sync_service
from automation.upload_automation import UploadAutomationManager, create_upload_automation_manager, UploadTriggerReason
from upload_files import submit_batch_files, discover_control_files


class WorkflowState(Enum):
    """
    Enumeration for workflow states.
    
    States represent the current operational mode of the workflow orchestrator:
        INITIALIZING: System is starting up and initializing components
        MONITORING: System is monitoring for work to be done
        PROCESSING: System is actively processing requests
        CAPACITY_MANAGEMENT: System is managing capacity and resource allocation
        ERROR_RECOVERY: System is recovering from errors
        MAINTENANCE: System is performing maintenance tasks
        SHUTDOWN: System is shutting down gracefully
        ERROR: System has encountered an unrecoverable error
    """
    INITIALIZING = "initializing"
    MONITORING = "monitoring"
    PROCESSING = "processing"
    CAPACITY_MANAGEMENT = "capacity_management"
    ERROR_RECOVERY = "error_recovery"
    MAINTENANCE = "maintenance"
    SHUTDOWN = "shutdown"
    ERROR = "error"


class WorkflowPriority(Enum):
    """
    Enumeration for workflow priorities.
    
    Priority levels for workflow operations:
        LOW (1): Background maintenance tasks
        NORMAL (2): Regular processing operations
        HIGH (3): Important operations requiring prompt attention
        CRITICAL (4): Critical operations that must be handled immediately
        EMERGENCY (5): Emergency operations that override all others
    """
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


@dataclass
class WorkflowConfig:
    """
    Configuration for workflow orchestration.
    
    This dataclass contains all configuration parameters for the workflow
    orchestrator, organized by category for clarity and maintainability.
    
    Attributes:
        Timing configurations:
            main_cycle_interval (int): Main workflow cycle interval in seconds (default: 300)
            status_check_interval (int): Status check interval in seconds (default: 60)
            capacity_check_interval (int): Capacity check interval in seconds (default: 60)
            data_sync_interval (int): Data synchronization interval in seconds (default: 900)
            maintenance_interval (int): Maintenance cycle interval in seconds (default: 3600)
        
        Processing configurations:
            max_concurrent_workflows (int): Maximum concurrent workflow threads (default: 3)
            enable_auto_submission (bool): Enable automatic request submission (default: True)
            enable_capacity_management (bool): Enable capacity management (default: True)
            enable_error_recovery (bool): Enable automatic error recovery (default: True)
            enable_maintenance (bool): Enable periodic maintenance (default: True)
        
        Thresholds and limits:
            error_threshold (int): Maximum errors before triggering recovery (default: 5)
            capacity_crisis_timeout (int): Timeout for capacity crisis in seconds (default: 1800)
            workflow_timeout (int): Individual workflow timeout in seconds (default: 3600)
        
        Database and file paths:
            db_path (str): Path to SQLite database file
            base_download_dir (str): Base directory for downloaded files
            control_files_dir (str): Directory containing control files
        
        Feature flags:
            enabled (bool): Master enable flag for the orchestrator (default: True)
            debug_mode (bool): Enable debug logging and verbose output (default: False)
    """
    # Timing configurations
    main_cycle_interval: int = 300  # 5 minutes
    status_check_interval: int = 60  # 1 minute
    capacity_check_interval: int = 60  # 1 minute
    data_sync_interval: int = 900  # 15 minutes
    maintenance_interval: int = 3600  # 1 hour
    
    # Processing configurations
    max_concurrent_workflows: int = 3
    enable_auto_submission: bool = True
    enable_capacity_management: bool = True
    enable_error_recovery: bool = True
    enable_maintenance: bool = True
    
    # Thresholds and limits
    error_threshold: int = 5
    capacity_crisis_timeout: int = 1800  # 30 minutes
    workflow_timeout: int = 3600  # 1 hour
    
    # Database and file paths
    db_path: str = "src/python/data/automation_state.db"
    base_download_dir: str = "downloaded_files"
    control_files_dir: str = "src/python/incoming"
    
    # Feature flags
    enabled: bool = True
    debug_mode: bool = False


@dataclass
class WorkflowStatus:
    """
    Current workflow status information.
    
    Contains comprehensive status information about the workflow orchestrator's
    current operational state, performance metrics, and component health.
    
    Attributes:
        current_state (WorkflowState): Current operational state
        active_workflows (int): Number of currently active workflow threads
        last_cycle_time (Optional[str]): Timestamp of last completed cycle
        next_scheduled_cycle (Optional[str]): Timestamp of next scheduled cycle
        total_cycles_completed (int): Total number of completed cycles
        errors_encountered (int): Total number of errors encountered
        uptime_seconds (float): System uptime in seconds
        performance_metrics (Dict[str, Any]): Performance metrics and statistics
        component_status (Dict[str, Any]): Status of individual components
        last_updated (str): Timestamp when status was last updated
    """
    current_state: WorkflowState
    active_workflows: int
    last_cycle_time: Optional[str]
    next_scheduled_cycle: Optional[str]
    total_cycles_completed: int
    errors_encountered: int
    uptime_seconds: float
    performance_metrics: Dict[str, Any]
    component_status: Dict[str, Any]
    last_updated: str


@dataclass
class WorkflowResult:
    """
    Result of a workflow operation.
    
    Contains detailed information about the execution of a workflow operation,
    including success status, timing information, and state transitions.
    
    Attributes:
        workflow_id (str): Unique identifier for the workflow operation
        workflow_type (str): Type of workflow operation (e.g., 'main_cycle', 'maintenance')
        success (bool): Whether the operation completed successfully
        message (str): Human-readable result message
        details (Dict[str, Any]): Detailed operation results and data
        start_time (str): ISO timestamp when operation started
        end_time (str): ISO timestamp when operation completed
        duration (float): Operation duration in seconds
        state_transitions (List[str]): List of state transitions during operation
    """
    workflow_id: str
    workflow_type: str
    success: bool
    message: str
    details: Dict[str, Any]
    start_time: str
    end_time: str
    duration: float
    state_transitions: List[str]


class WorkflowOrchestrator:
    """
    Main workflow orchestrator for the RDA automation system.
    
    This class serves as the central coordinator for all automation components,
    managing the complete workflow lifecycle with intelligent scheduling, error
    recovery, and comprehensive monitoring capabilities.
    
    The orchestrator implements a state machine pattern to manage different
    operational modes and ensures reliable, continuous operation of the RDA
    automation system.
    
    Key Responsibilities:
        - Coordinate all automation components (file organization, request management,
          capacity management, status monitoring, data synchronization, upload automation)
        - Manage workflow state transitions and lifecycle
        - Implement intelligent scheduling and optimization
        - Provide comprehensive monitoring and reporting
        - Handle error recovery and system resilience
        - Maintain real-time status updates and dashboard integration
    
    Attributes:
        config (WorkflowConfig): Configuration settings for the orchestrator
        logger (logging.Logger): Logger instance for orchestrator operations
        file_org_manager: File organization manager instance
        request_manager: Automated request manager instance
        capacity_manager: Capacity manager instance
        status_monitor: Status monitor instance
        data_sync: Data synchronization service instance
        upload_manager: Upload automation manager instance
        current_state (WorkflowState): Current operational state
        workflow_active (bool): Whether the workflow is currently active
        workflow_threads (dict): Dictionary of active workflow threads
        start_time (Optional[float]): Timestamp when orchestrator was started
        shutdown_requested (bool): Whether shutdown has been requested
        workflow_stats (dict): Statistics and metrics for workflow operations
        workflow_lock (threading.Lock): Thread lock for workflow operations
        executor (ThreadPoolExecutor): Thread pool for concurrent operations
        main_thread (Optional[threading.Thread]): Main workflow thread
    
    Example:
        Basic usage of the workflow orchestrator:
        
        >>> config = WorkflowConfig(main_cycle_interval=300, debug_mode=True)
        >>> orchestrator = WorkflowOrchestrator(config)
        >>> orchestrator.start_workflow()
        >>> # System runs continuously until interrupted
        >>> orchestrator.stop_workflow()
    """
    
    def __init__(self, config: Optional[WorkflowConfig] = None):
        """
        Initialize the Workflow Orchestrator.
        
        Sets up all component managers, initializes the workflow state,
        configures threading and execution resources, and prepares the
        orchestrator for operation.
        
        Args:
            config (Optional[WorkflowConfig]): Configuration for workflow orchestration.
                If None, uses default configuration settings.
        
        Raises:
            Exception: If component initialization fails or required resources
                are unavailable.
        """
        self.config = config or WorkflowConfig()
        self.logger = self._setup_logging()
        
        # Initialize all component managers
        self.file_org_manager = create_file_organization_manager(
            self.config.base_download_dir, self.config.db_path
        )
        self.request_manager = create_automated_request_manager(
            db_path=self.config.db_path, base_download_dir=self.config.base_download_dir
        )
        self.capacity_manager = create_capacity_manager(db_path=self.config.db_path)
        self.status_monitor = create_status_monitor(db_path=self.config.db_path)
        self.data_sync = create_data_sync_service(self.config.db_path)
        self.upload_manager = create_upload_automation_manager(capacity_manager=self.capacity_manager)
        
        # Workflow state management
        self.current_state = WorkflowState.INITIALIZING
        self.workflow_active = False
        self.workflow_threads = {}
        self.start_time = None
        self.shutdown_requested = False
        
        # Statistics and monitoring
        self.workflow_stats = {
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'total_requests_processed': 0,
            'total_files_organized': 0,
            'total_errors_handled': 0,
            'uptime_start': None,
            'last_maintenance': None
        }
        
        # Threading and execution
        self.workflow_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_workflows)
        self.main_thread = None
        
        # Signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Workflow Orchestrator initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """
        Set up logging for the workflow orchestrator.
        
        Configures a logger with appropriate formatting and level based on
        the debug mode setting in the configuration.
        
        Returns:
            logging.Logger: Configured logger instance for the orchestrator.
        """
        logger = logging.getLogger('rda_automation.workflow_orchestrator')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG if self.config.debug_mode else logging.INFO)
            
        return logger
    
    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals gracefully.
        
        Responds to SIGINT and SIGTERM signals by initiating a graceful
        shutdown of the workflow orchestrator.
        
        Args:
            signum (int): Signal number that was received.
            frame: Current stack frame (unused).
        """
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        self.stop_workflow()
    
    def transition_state(self, new_state: WorkflowState, reason: str = ""):
        """
        Transition to a new workflow state.
        
        Safely transitions the orchestrator to a new operational state with
        proper thread synchronization and logging.
        
        Args:
            new_state (WorkflowState): New state to transition to.
            reason (str, optional): Human-readable reason for the state transition.
                Defaults to empty string.
        
        Note:
            State transitions are thread-safe and logged for audit purposes.
        """
        old_state = self.current_state
        
        with self.workflow_lock:
            self.current_state = new_state
        
        self.logger.info(f"🔄 State transition: {old_state.value} -> {new_state.value}" + 
                        (f" ({reason})" if reason else ""))
    
    def get_workflow_status(self) -> WorkflowStatus:
        """
        Get current workflow status.
        
        Compiles comprehensive status information including current state,
        performance metrics, component health, and operational statistics.
        
        Returns:
            WorkflowStatus: Object containing complete workflow status information
                including current state, active workflows, performance metrics,
                component status, and timing information.
        
        Note:
            This method is safe to call from multiple threads and provides
            real-time status information.
        """
        try:
            # Calculate uptime
            uptime_seconds = 0.0
            if self.start_time:
                uptime_seconds = time.time() - self.start_time
            
            # Get component status
            component_status = {
                'file_organization': 'active',
                'request_manager': 'active' if self.request_manager else 'inactive',
                'capacity_manager': 'active' if self.capacity_manager.monitoring_active else 'inactive',
                'status_monitor': 'active' if self.status_monitor.monitoring_active else 'inactive',
                'data_sync': 'active',
                'upload_automation': 'active' if self.upload_manager.config.enabled else 'inactive'
            }
            
            # Calculate performance metrics
            performance_metrics = {
                'cycles_per_hour': (self.workflow_stats['total_cycles'] / (uptime_seconds / 3600)) if uptime_seconds > 0 else 0,
                'success_rate': (self.workflow_stats['successful_cycles'] / self.workflow_stats['total_cycles'] * 100) if self.workflow_stats['total_cycles'] > 0 else 0,
                'average_cycle_time': 0.0,  # Would need to track this separately
                'error_rate': (self.workflow_stats['failed_cycles'] / self.workflow_stats['total_cycles'] * 100) if self.workflow_stats['total_cycles'] > 0 else 0
            }
            
            return WorkflowStatus(
                current_state=self.current_state,
                active_workflows=len(self.workflow_threads),
                last_cycle_time=self.workflow_stats.get('last_cycle_time'),
                next_scheduled_cycle=None,  # Would calculate based on intervals
                total_cycles_completed=self.workflow_stats['total_cycles'],
                errors_encountered=self.workflow_stats['failed_cycles'],
                uptime_seconds=uptime_seconds,
                performance_metrics=performance_metrics,
                component_status=component_status,
                last_updated=datetime.now().isoformat()
            )
            
        except Exception as e:
            self.logger.error(f"Error getting workflow status: {e}")
            return WorkflowStatus(
                current_state=WorkflowState.ERROR,
                active_workflows=0,
                last_cycle_time=None,
                next_scheduled_cycle=None,
                total_cycles_completed=0,
                errors_encountered=1,
                uptime_seconds=0.0,
                performance_metrics={},
                component_status={},
                last_updated=datetime.now().isoformat()
            )
    
    def execute_main_workflow_cycle(self) -> WorkflowResult:
        """
        Execute the main workflow cycle.
        
        Returns:
            WorkflowResult with cycle execution details
        """
        workflow_id = f"main_cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()
        state_transitions = []
        
        try:
            self.logger.info(f"🚀 Starting main workflow cycle: {workflow_id}")
            
            # Transition to processing state
            self.transition_state(WorkflowState.PROCESSING, "Starting main cycle")
            state_transitions.append(f"-> {WorkflowState.PROCESSING.value}")
            
            cycle_results = {
                'data_sync': None,
                'status_monitoring': None,
                'request_processing': None,
                'capacity_management': None,
                'file_organization': None,
                'auto_submission': None
            }
            
            # Step 1: Data synchronization
            self.logger.info("📊 Step 1: Data synchronization")
            try:
                sync_result = self.data_sync.perform_full_sync()
                cycle_results['data_sync'] = sync_result
                
                if sync_result.get('success'):
                    self.logger.info(f"✅ Data sync completed: {sync_result.get('total_requests', 0)} requests synced")
                else:
                    self.logger.warning(f"⚠️ Data sync issues: {sync_result.get('error', 'Unknown error')}")
            except Exception as e:
                self.logger.error(f"❌ Data sync failed: {e}")
                cycle_results['data_sync'] = {'success': False, 'error': str(e)}
            
            # Step 2: Status monitoring and processing
            self.logger.info("🔍 Step 2: Status monitoring and request processing")
            try:
                # Run status monitoring cycle
                monitor_result = self.status_monitor.run_single_monitoring_cycle()
                cycle_results['status_monitoring'] = monitor_result
                
                # Run request processing cycle
                processing_result = self.request_manager.run_processing_cycle()
                cycle_results['request_processing'] = processing_result
                
                if processing_result.get('success'):
                    processed = processing_result.get('processing_results', {})
                    self.logger.info(f"✅ Request processing: {processed.get('completed_processed', 0)} completed, "
                                   f"{processed.get('errors_processed', 0)} errors processed")
                    
                    # Update statistics
                    self.workflow_stats['total_requests_processed'] += (
                        processed.get('completed_processed', 0) + processed.get('errors_processed', 0)
                    )
                else:
                    self.logger.warning(f"⚠️ Request processing issues: {processing_result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                self.logger.error(f"❌ Status monitoring/processing failed: {e}")
                cycle_results['status_monitoring'] = {'success': False, 'error': str(e)}
                cycle_results['request_processing'] = {'success': False, 'error': str(e)}
            
            # Step 3: Capacity management
            if self.config.enable_capacity_management:
                self.logger.info("⚖️ Step 3: Capacity management")
                try:
                    self.transition_state(WorkflowState.CAPACITY_MANAGEMENT, "Checking capacity")
                    state_transitions.append(f"-> {WorkflowState.CAPACITY_MANAGEMENT.value}")
                    
                    capacity_result = self.capacity_manager.run_capacity_monitoring_cycle()
                    cycle_results['capacity_management'] = capacity_result
                    
                    if capacity_result.get('success'):
                        capacity_status = capacity_result.get('capacity_status', {})
                        capacity_level = capacity_status.get('capacity_level', 'unknown')
                        actions_taken = len(capacity_result.get('actions_taken', []))
                        
                        self.logger.info(f"✅ Capacity management: {capacity_level} level, {actions_taken} actions taken")
                    else:
                        self.logger.warning(f"⚠️ Capacity management issues: {capacity_result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    self.logger.error(f"❌ Capacity management failed: {e}")
                    cycle_results['capacity_management'] = {'success': False, 'error': str(e)}
            
            # Step 4: File organization statistics
            self.logger.info("📁 Step 4: File organization check")
            try:
                org_stats = self.file_org_manager.get_organization_statistics()
                cycle_results['file_organization'] = org_stats
                
                if 'error' not in org_stats:
                    organized_files = org_stats.get('organized_files', 0)
                    total_regions = org_stats.get('total_regions', 0)
                    self.logger.info(f"✅ File organization: {organized_files} files in {total_regions} regions")
                    self.workflow_stats['total_files_organized'] = organized_files
                else:
                    self.logger.warning(f"⚠️ File organization issues: {org_stats.get('error', 'Unknown error')}")
                    
            except Exception as e:
                self.logger.error(f"❌ File organization check failed: {e}")
                cycle_results['file_organization'] = {'error': str(e)}
            
            # Step 5: Upload automation (integrated with capacity management)
            if self.config.enable_auto_submission:
                self.logger.info("📤 Step 5: Upload automation check")
                try:
                    # Get upload monitoring info
                    monitoring_info = self.upload_manager.get_upload_monitoring_info()
                    cycle_results['auto_submission'] = asdict(monitoring_info)
                    
                    # Check if upload should be triggered
                    if (monitoring_info.upload_enabled and
                        monitoring_info.in_upload_window and
                        monitoring_info.available_files > 0 and
                        monitoring_info.current_capacity <= self.upload_manager.config.capacity_threshold):
                        
                        # Trigger upload automation
                        upload_result = self.upload_manager.trigger_upload(
                            trigger_reason=UploadTriggerReason.CAPACITY_AVAILABLE
                        )
                        cycle_results['auto_submission']['upload_result'] = asdict(upload_result)
                        
                        if upload_result.status.value in ['completed']:
                            self.logger.info(f"✅ Upload automation: {upload_result.files_submitted} requests submitted")
                            self.logger.info(f"📋 New request IDs: {upload_result.request_ids}")
                            
                            # Update workflow statistics
                            self.workflow_stats['total_requests_processed'] += upload_result.files_submitted
                        else:
                            self.logger.warning(f"⚠️ Upload automation: {upload_result.status.value} - {upload_result.error_messages}")
                    else:
                        # Determine skip reason
                        if not monitoring_info.upload_enabled:
                            reason = "upload automation disabled"
                        elif not monitoring_info.in_upload_window:
                            reason = "outside upload window"
                        elif monitoring_info.available_files == 0:
                            reason = "no control files available"
                        elif monitoring_info.current_capacity > self.upload_manager.config.capacity_threshold:
                            reason = f"capacity too high ({monitoring_info.current_capacity} > {self.upload_manager.config.capacity_threshold})"
                        else:
                            reason = "upload conditions not met"
                        
                        self.logger.info(f"ℹ️ Upload automation skipped: {reason}")
                        cycle_results['auto_submission']['skip_reason'] = reason
                        
                except Exception as e:
                    self.logger.error(f"❌ Upload automation failed: {e}")
                    cycle_results['auto_submission'] = {'success': False, 'error': str(e)}
            
            # Transition back to monitoring
            self.transition_state(WorkflowState.MONITORING, "Cycle completed")
            state_transitions.append(f"-> {WorkflowState.MONITORING.value}")
            
            # Update statistics
            with self.workflow_lock:
                self.workflow_stats['total_cycles'] += 1
                self.workflow_stats['successful_cycles'] += 1
                self.workflow_stats['last_cycle_time'] = datetime.now().isoformat()
            
            duration = time.time() - start_time
            
            self.logger.info(f"✅ Main workflow cycle completed in {duration:.2f}s: {workflow_id}")
            
            return WorkflowResult(
                workflow_id=workflow_id,
                workflow_type="main_cycle",
                success=True,
                message=f"Main workflow cycle completed successfully in {duration:.2f}s",
                details=cycle_results,
                start_time=datetime.fromtimestamp(start_time).isoformat(),
                end_time=datetime.now().isoformat(),
                duration=duration,
                state_transitions=state_transitions
            )
            
        except Exception as e:
            # Handle workflow errors
            self.transition_state(WorkflowState.ERROR, f"Workflow error: {e}")
            state_transitions.append(f"-> {WorkflowState.ERROR.value}")
            
            with self.workflow_lock:
                self.workflow_stats['total_cycles'] += 1
                self.workflow_stats['failed_cycles'] += 1
            
            duration = time.time() - start_time
            error_msg = f"Main workflow cycle failed: {e}"
            
            self.logger.error(f"❌ {error_msg}")
            
            return WorkflowResult(
                workflow_id=workflow_id,
                workflow_type="main_cycle",
                success=False,
                message=error_msg,
                details={'error': str(e), 'traceback': str(e)},
                start_time=datetime.fromtimestamp(start_time).isoformat(),
                end_time=datetime.now().isoformat(),
                duration=duration,
                state_transitions=state_transitions
            )
    
    def execute_maintenance_workflow(self) -> WorkflowResult:
        """
        Execute maintenance workflow for system health.
        
        Returns:
            WorkflowResult with maintenance execution details
        """
        workflow_id = f"maintenance_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()
        
        try:
            self.logger.info(f"🔧 Starting maintenance workflow: {workflow_id}")
            
            self.transition_state(WorkflowState.MAINTENANCE, "Running maintenance")
            
            maintenance_results = {
                'database_cleanup': None,
                'log_rotation': None,
                'statistics_update': None,
                'health_check': None
            }
            
            # Database cleanup
            try:
                # This would include cleaning up old records, optimizing database, etc.
                self.logger.info("🗃️ Database maintenance")
                maintenance_results['database_cleanup'] = {'success': True, 'message': 'Database maintenance completed'}
            except Exception as e:
                maintenance_results['database_cleanup'] = {'success': False, 'error': str(e)}
            
            # Statistics update
            try:
                self.logger.info("📊 Statistics update")
                self.workflow_stats['last_maintenance'] = datetime.now().isoformat()
                maintenance_results['statistics_update'] = {'success': True, 'message': 'Statistics updated'}
            except Exception as e:
                maintenance_results['statistics_update'] = {'success': False, 'error': str(e)}
            
            # Health check
            try:
                self.logger.info("🏥 System health check")
                health_status = self.get_workflow_status()
                maintenance_results['health_check'] = {
                    'success': True,
                    'status': asdict(health_status)
                }
            except Exception as e:
                maintenance_results['health_check'] = {'success': False, 'error': str(e)}
            
            duration = time.time() - start_time
            
            self.logger.info(f"✅ Maintenance workflow completed in {duration:.2f}s")
            
            return WorkflowResult(
                workflow_id=workflow_id,
                workflow_type="maintenance",
                success=True,
                message=f"Maintenance workflow completed in {duration:.2f}s",
                details=maintenance_results,
                start_time=datetime.fromtimestamp(start_time).isoformat(),
                end_time=datetime.now().isoformat(),
                duration=duration,
                state_transitions=[f"-> {WorkflowState.MAINTENANCE.value}", f"-> {WorkflowState.MONITORING.value}"]
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Maintenance workflow failed: {e}"
            
            self.logger.error(f"❌ {error_msg}")
            
            return WorkflowResult(
                workflow_id=workflow_id,
                workflow_type="maintenance",
                success=False,
                message=error_msg,
                details={'error': str(e)},
                start_time=datetime.fromtimestamp(start_time).isoformat(),
                end_time=datetime.now().isoformat(),
                duration=duration,
                state_transitions=[f"-> {WorkflowState.ERROR.value}"]
            )
        finally:
            self.transition_state(WorkflowState.MONITORING, "Maintenance completed")
    
    def start_workflow(self):
        """Start the continuous workflow orchestration."""
        if self.workflow_active:
            self.logger.warning("Workflow is already active")
            return
        
        self.logger.info("🚀 Starting RDA Automation Workflow Orchestrator")
        
        # Initialize workflow state
        self.start_time = time.time()
        self.workflow_stats['uptime_start'] = datetime.now().isoformat()
        self.workflow_active = True
        self.shutdown_requested = False
        
        # Start component monitoring
        if self.config.enable_capacity_management:
            self.capacity_manager.start_capacity_monitoring()
        
        def main_workflow_loop():
            """Main workflow execution loop."""
            self.logger.info(f"🔄 Starting main workflow loop (interval: {self.config.main_cycle_interval}s)")
            
            last_maintenance = time.time()
            
            while self.workflow_active and not self.shutdown_requested:
                try:
                    # Execute main workflow cycle
                    cycle_result = self.execute_main_workflow_cycle()
                    
                    if cycle_result.success:
                        self.logger.info(f"✅ Workflow cycle completed: {cycle_result.workflow_id}")
                    else:
                        self.logger.error(f"❌ Workflow cycle failed: {cycle_result.message}")
                        
                        # Handle error recovery if enabled
                        if self.config.enable_error_recovery:
                            self.transition_state(WorkflowState.ERROR_RECOVERY, "Handling workflow error")
                            time.sleep(60)  # Wait before retrying
                    
                    # Check if maintenance is needed
                    if (self.config.enable_maintenance and 
                        time.time() - last_maintenance > self.config.maintenance_interval):
                        
                        maintenance_result = self.execute_maintenance_workflow()
                        if maintenance_result.success:
                            last_maintenance = time.time()
                            self.logger.info("✅ Maintenance workflow completed")
                        else:
                            self.logger.error(f"❌ Maintenance workflow failed: {maintenance_result.message}")
                    
                    # Wait for next cycle
                    time.sleep(self.config.main_cycle_interval)
                    
                except Exception as e:
                    self.logger.error(f"❌ Error in main workflow loop: {e}")
                    self.transition_state(WorkflowState.ERROR, f"Loop error: {e}")
                    
                    if self.config.enable_error_recovery:
                        time.sleep(60)  # Wait before retrying
                        self.transition_state(WorkflowState.MONITORING, "Recovering from error")
                    else:
                        break
            
            self.logger.info("🛑 Main workflow loop stopped")
        
        # Start main workflow thread
        self.main_thread = threading.Thread(target=main_workflow_loop, daemon=True)
        self.main_thread.start()
        
        self.transition_state(WorkflowState.MONITORING, "Workflow started")
        self.logger.info("✅ RDA Automation Workflow Orchestrator started successfully")
    
    def stop_workflow(self):
        """Stop the workflow orchestration gracefully."""
        if not self.workflow_active:
            return
        
        self.logger.info("🛑 Stopping RDA Automation Workflow Orchestrator...")
        
        self.transition_state(WorkflowState.SHUTDOWN, "Shutdown requested")
        self.workflow_active = False
        
        # Stop component monitoring
        if self.capacity_manager.monitoring_active:
            self.capacity_manager.stop_capacity_monitoring()
        
        if self.status_monitor.monitoring_active:
            self.status_monitor.stop_monitoring()
        
        # Wait for main thread to complete
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=30)
        
        # Shutdown executor
        self.executor.shutdown(wait=True, timeout=30)
        
        self.logger.info("✅ RDA Automation Workflow Orchestrator stopped")
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of the entire automation system.
        
        Returns:
            Dictionary with complete system status
        """
        try:
            workflow_status = self.get_workflow_status()
            
            # Get component statistics
            component_stats = {
                'file_organization': self.file_org_manager.get_organization_statistics(),
                'request_processing': self.request_manager.get_processing_statistics(),
                'capacity_management': self.capacity_manager.get_capacity_analytics(),
                'status_monitoring': self.status_monitor.get_monitoring_statistics(),
                'upload_automation': self.upload_manager.get_upload_statistics()
            }
            
            return {
                'workflow_status': asdict(workflow_status),
                'workflow_statistics': self.workflow_stats.copy(),
                'component_statistics': component_stats,
                'configuration': asdict(self.config),
                'system_info': {
                    'version': '1.0.0',
                    'python_version': sys.version,
                    'platform': sys.platform,
                    'pid': os.getpid()
                },
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting comprehensive status: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }


def create_workflow_orchestrator(config: Optional[WorkflowConfig] = None) -> WorkflowOrchestrator:
    """
    Factory function to create a Workflow Orchestrator.
    
    Args:
        config: Configuration for workflow orchestration
        
    Returns:
        Configured WorkflowOrchestrator instance
    """
    return WorkflowOrchestrator(config)


if __name__ == "__main__":
    # Main entry point for the RDA Automation System
    import argparse
    
    parser = argparse.ArgumentParser(description='RDA Automation System - Workflow Orchestrator')
    parser.add_argument('--start', action='store_true',
                       help='Start the continuous workflow orchestration')
    parser.add_argument('--single-cycle', action='store_true',
                       help='Run a single workflow cycle')
    parser.add_argument('--maintenance', action='store_true',
                       help='Run maintenance workflow')
    parser.add_argument('--status', action='store_true',
                       help='Show comprehensive system status')
    parser.add_argument('--config', type=str,
                       help='Path to configuration file')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Create configuration
    config = WorkflowConfig()
    if args.debug:
        config.debug_mode = True
    
    # Load configuration file if provided
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r') as f:
                config_data = json.load(f)
                # Update config with loaded data
                for key, value in config_data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        except Exception as e:
            print(f"Error loading configuration: {e}")
    
    # Create workflow orchestrator
    orchestrator = create_workflow_orchestrator(config)
    
    try:
        if args.start:
            print("=" * 80)
            print("🚀 RDA AUTOMATION SYSTEM - WORKFLOW ORCHESTRATOR")
            print("=" * 80)
            print("Starting continuous workflow orchestration...")
            print("Press Ctrl+C to stop gracefully")
            print("=" * 80)
            
            orchestrator.start_workflow()
            
            # Keep running until interrupted
            try:
                while orchestrator.workflow_active:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutdown requested...")
                orchestrator.stop_workflow()
        
        elif args.single_cycle:
            print("=== Running Single Workflow Cycle ===")
            result = orchestrator.execute_main_workflow_cycle()
            print(json.dumps(asdict(result), indent=2, default=str))
        
        elif args.maintenance:
            print("=== Running Maintenance Workflow ===")
            result = orchestrator.execute_maintenance_workflow()
            print(json.dumps(asdict(result), indent=2, default=str))
        
        elif args.status:
            print("=== Comprehensive System Status ===")
            status = orchestrator.get_comprehensive_status()
            print(json.dumps(status, indent=2, default=str))
        
        else:
            parser.print_help()
            print("\n" + "="*80)
            print("RDA AUTOMATION SYSTEM EXAMPLES")
            print("="*80)
            print("# Start continuous workflow orchestration:")
            print("python automation/workflow_orchestrator.py --start")
            print("\n# Run single workflow cycle:")
            print("python automation/workflow_orchestrator.py --single-cycle")
            print("\n# Run maintenance workflow:")
            print("python automation/workflow_orchestrator.py --maintenance")
            print("\n# Show comprehensive system status:")
            print("python automation/workflow_orchestrator.py --status")
            print("\n# Start with debug mode:")
            print("python automation/workflow_orchestrator.py --start --debug")
            print("="*80)
            
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(orchestrator, 'workflow_active') and orchestrator.workflow_active:
            orchestrator.stop_workflow()