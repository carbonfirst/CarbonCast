#!/usr/bin/env python3
"""
Capacity Manager for RDA Automation System

This module provides intelligent capacity management for the RDA system's 10-request limit.
It monitors request capacity, implements crisis resolution strategies, and optimizes
request throughput while respecting system constraints.

Key Features:
- Real-time capacity monitoring and alerting
- Crisis resolution when at 10-request limit
- Intelligent request prioritization and scheduling
- Automatic capacity optimization strategies
- Integration with automated request processing
- Comprehensive capacity analytics and reporting
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger

import rdams_client
from automation.automated_request_manager import AutomatedRequestManager, create_automated_request_manager
from upload_files import submit_batch_files, discover_control_files


class CapacityLevel(Enum):
    """Enumeration for capacity levels."""
    NORMAL = "normal"          # 0-6 requests
    APPROACHING = "approaching" # 7-9 requests
    CRITICAL = "critical"      # 10 requests
    CRISIS = "crisis"          # 10+ requests (at/over limit)


class PriorityLevel(Enum):
    """Enumeration for request priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


@dataclass
class CapacityConfig:
    """Configuration for capacity management."""
    normal_threshold: int = 8  # Increased from 6 to be more aggressive
    approaching_threshold: int = 9  # Increased from 7 to be more aggressive
    critical_threshold: int = 10
    crisis_threshold: int = 10
    monitoring_interval: int = 30  # Reduced from 60 to 30 seconds for faster response
    crisis_resolution_timeout: int = 1800  # 30 minutes
    aggressive_processing_enabled: bool = True
    auto_purge_completed: bool = True
    auto_purge_errors: bool = True
    priority_boost_at_critical: bool = True
    emergency_processing_enabled: bool = True
    # Upload automation settings - AGGRESSIVE SETTINGS FOR 10-REQUEST TARGET
    enable_upload_automation: bool = True
    upload_capacity_threshold: int = 10  # Changed from 9 to 10 - upload even at 10 requests
    upload_batch_size: int = 5  # Increased from 2 to 5 for more aggressive uploading
    upload_rate_limit_delay: float = 1.0  # Reduced from 2.0 to 1.0 for faster uploads
    control_files_dir: str = "src/python/incoming"


@dataclass
class CapacityStatus:
    """Current capacity status information."""
    total_requests: int
    capacity_level: CapacityLevel
    available_slots: int
    requests_by_status: Dict[str, int]
    priority_requests: int
    estimated_completion_time: Optional[str]
    crisis_duration: Optional[float]  # seconds in crisis mode
    last_updated: str


@dataclass
class CapacityAction:
    """Capacity management action taken."""
    action_type: str
    request_id: Optional[str]
    success: bool
    message: str
    details: Dict[str, Any]
    timestamp: str
    processing_time: float = 0.0


class CapacityManager:
    """
    Intelligent capacity manager for RDA request limits.
    
    Monitors and manages the 10-request capacity limit with intelligent
    strategies for optimization and crisis resolution.
    """
    
    def __init__(self, config: Optional[CapacityConfig] = None,
                 db_path: str = "src/python/data/automation_state.db"):
        """
        Initialize the Capacity Manager.
        
        Args:
            config: Configuration for capacity management
            db_path: Path to the SQLite database file
        """
        self.config = config or CapacityConfig()
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Initialize automated request manager
        self.request_manager = create_automated_request_manager(db_path=db_path)
        
        # Capacity monitoring state
        self.monitoring_active = False
        self.monitoring_thread = None
        self.current_status = None
        self.crisis_start_time = None
        self.capacity_history = []
        
        # Statistics
        self.capacity_stats = {
            'total_monitoring_cycles': 0,
            'crisis_episodes': 0,
            'total_crisis_time': 0.0,
            'actions_taken': 0,
            'successful_actions': 0,
            'last_crisis_resolution': None
        }
        
        # Threading
        self.capacity_lock = threading.Lock()
        
        # Dynamic system integration
        self.dynamic_trigger_system = None
        self.batch_optimizer = None
        self.enhanced_monitor = None
        
        # Dynamic triggering callbacks
        self.capacity_change_callbacks: List[Callable] = []
        self.trigger_callbacks: List[Callable] = []
        
        self.logger.info("Capacity Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.capacity_manager', level=logging.INFO)
    
    def set_dynamic_integration_components(self,
                                         dynamic_trigger_system=None,
                                         batch_optimizer=None,
                                         enhanced_monitor=None):
        """
        Set dynamic system integration components.
        
        Args:
            dynamic_trigger_system: DynamicTriggerSystem instance
            batch_optimizer: BatchOptimizer instance
            enhanced_monitor: EnhancedRequestMonitor instance
        """
        self.dynamic_trigger_system = dynamic_trigger_system
        self.batch_optimizer = batch_optimizer
        self.enhanced_monitor = enhanced_monitor
        
        self.logger.info("✅ Dynamic integration components configured for capacity manager")
    
    def add_capacity_change_callback(self, callback: Callable):
        """
        Add a callback for capacity changes.
        
        Args:
            callback: Function to call with (previous_count, current_count, capacity_level)
        """
        self.capacity_change_callbacks.append(callback)
        self.logger.info("✅ Capacity change callback added")
    
    def add_trigger_callback(self, callback: Callable):
        """
        Add a callback for trigger events.
        
        Args:
            callback: Function to call with (trigger_type, action_taken, success)
        """
        self.trigger_callbacks.append(callback)
        self.logger.info("✅ Trigger callback added")
    
    def _notify_capacity_change(self, previous_status: CapacityStatus, current_status: CapacityStatus):
        """Notify callbacks of capacity changes."""
        try:
            if previous_status and current_status:
                if previous_status.total_requests != current_status.total_requests:
                    for callback in self.capacity_change_callbacks:
                        try:
                            callback(
                                previous_status.total_requests,
                                current_status.total_requests,
                                current_status.capacity_level
                            )
                        except Exception as e:
                            self.logger.error(f"❌ Error in capacity change callback: {e}")
        except Exception as e:
            self.logger.error(f"❌ Error notifying capacity change: {e}")
    
    def _notify_trigger_event(self, trigger_type: str, action_taken: str, success: bool):
        """Notify callbacks of trigger events."""
        try:
            for callback in self.trigger_callbacks:
                try:
                    callback(trigger_type, action_taken, success)
                except Exception as e:
                    self.logger.error(f"❌ Error in trigger callback: {e}")
        except Exception as e:
            self.logger.error(f"❌ Error notifying trigger event: {e}")
    
    def get_current_capacity_status(self) -> CapacityStatus:
        """
        Get current capacity status from RDA system.
        
        Returns:
            CapacityStatus object with current information
        """
        try:
            # Get comprehensive request status
            status_info = self.request_manager.get_all_request_status()
            
            if not status_info:
                self.logger.error("Failed to get request status for capacity monitoring")
                return CapacityStatus(
                    total_requests=0,
                    capacity_level=CapacityLevel.NORMAL,
                    available_slots=10,
                    requests_by_status={},
                    priority_requests=0,
                    estimated_completion_time=None,
                    crisis_duration=None,
                    last_updated=datetime.now().isoformat()
                )
            
            total_requests = status_info['total_count']
            available_slots = max(0, 10 - total_requests)
            
            # Determine capacity level
            if total_requests >= self.config.crisis_threshold:
                capacity_level = CapacityLevel.CRISIS
            elif total_requests >= self.config.critical_threshold:
                capacity_level = CapacityLevel.CRITICAL
            elif total_requests >= self.config.approaching_threshold:
                capacity_level = CapacityLevel.APPROACHING
            else:
                capacity_level = CapacityLevel.NORMAL
            
            # Calculate requests by status
            requests_by_status = {
                'completed': len(status_info.get('completed', [])),
                'processing': len(status_info.get('processing', [])),
                'queued': len(status_info.get('queued', [])),
                'error': len(status_info.get('error', [])),
                'unknown': len(status_info.get('unknown', []))
            }
            
            # Calculate priority requests (completed + error that need immediate action)
            priority_requests = requests_by_status['completed'] + requests_by_status['error']
            
            # Estimate completion time based on processing requests
            estimated_completion_time = None
            if requests_by_status['processing'] > 0:
                # Rough estimate: assume 2 hours average processing time
                estimated_hours = requests_by_status['processing'] * 2
                estimated_completion = datetime.now() + timedelta(hours=estimated_hours)
                estimated_completion_time = estimated_completion.isoformat()
            
            # Calculate crisis duration
            crisis_duration = None
            if capacity_level == CapacityLevel.CRISIS:
                if self.crisis_start_time is None:
                    self.crisis_start_time = time.time()
                crisis_duration = time.time() - self.crisis_start_time
            else:
                if self.crisis_start_time is not None:
                    # Crisis ended, record duration
                    crisis_duration = time.time() - self.crisis_start_time
                    self.capacity_stats['total_crisis_time'] += crisis_duration
                    self.crisis_start_time = None
            
            capacity_status = CapacityStatus(
                total_requests=total_requests,
                capacity_level=capacity_level,
                available_slots=available_slots,
                requests_by_status=requests_by_status,
                priority_requests=priority_requests,
                estimated_completion_time=estimated_completion_time,
                crisis_duration=crisis_duration,
                last_updated=datetime.now().isoformat()
            )
            
            # Update current status
            with self.capacity_lock:
                self.current_status = capacity_status
                self.capacity_history.append(capacity_status)
                
                # Keep only last 100 status records
                if len(self.capacity_history) > 100:
                    self.capacity_history = self.capacity_history[-100:]
            
            return capacity_status
            
        except Exception as e:
            self.logger.error(f"Error getting capacity status: {e}")
            return CapacityStatus(
                total_requests=0,
                capacity_level=CapacityLevel.NORMAL,
                available_slots=10,
                requests_by_status={},
                priority_requests=0,
                estimated_completion_time=None,
                crisis_duration=None,
                last_updated=datetime.now().isoformat()
            )
    
    def execute_capacity_strategy(self, capacity_status: CapacityStatus) -> List[CapacityAction]:
        """
        Execute appropriate capacity management strategy based on current status.
        
        Args:
            capacity_status: Current capacity status
            
        Returns:
            List of CapacityAction objects representing actions taken
        """
        actions = []
        
        try:
            if capacity_status.capacity_level == CapacityLevel.CRISIS:
                actions.extend(self._execute_crisis_strategy(capacity_status))
            elif capacity_status.capacity_level == CapacityLevel.CRITICAL:
                actions.extend(self._execute_critical_strategy(capacity_status))
            elif capacity_status.capacity_level == CapacityLevel.APPROACHING:
                actions.extend(self._execute_approaching_strategy(capacity_status))
            else:
                actions.extend(self._execute_normal_strategy(capacity_status))
            
            # Update statistics
            with self.capacity_lock:
                self.capacity_stats['actions_taken'] += len(actions)
                self.capacity_stats['successful_actions'] += len([a for a in actions if a.success])
            
            return actions
            
        except Exception as e:
            self.logger.error(f"Error executing capacity strategy: {e}")
            return []
    
    def _execute_crisis_strategy(self, capacity_status: CapacityStatus) -> List[CapacityAction]:
        """Execute crisis strategy when at 10-request limit."""
        actions = []
        
        self.logger.warning(f"🚨 CAPACITY CRISIS: {capacity_status.total_requests}/10 requests active")
        
        # Record crisis episode
        with self.capacity_lock:
            if self.crisis_start_time is None:
                self.capacity_stats['crisis_episodes'] += 1
        
        # Strategy 1: Aggressively process completed requests
        if capacity_status.requests_by_status.get('completed', 0) > 0:
            self.logger.warning("🔥 CRISIS ACTION: Aggressively processing completed requests")
            
            # Get completed requests and process them immediately
            status_info = self.request_manager.get_all_request_status()
            completed_requests = status_info.get('completed', [])
            
            if completed_requests:
                start_time = time.time()
                results = self.request_manager.process_completed_requests(completed_requests)
                processing_time = time.time() - start_time
                
                successful_downloads = len([r for r in results if r.success])
                
                action = CapacityAction(
                    action_type="crisis_process_completed",
                    request_id=None,
                    success=successful_downloads > 0,
                    message=f"Processed {successful_downloads}/{len(completed_requests)} completed requests",
                    details={
                        'completed_requests': len(completed_requests),
                        'successful_downloads': successful_downloads,
                        'results': [asdict(r) for r in results]
                    },
                    timestamp=datetime.now().isoformat(),
                    processing_time=processing_time
                )
                actions.append(action)
        
        # Strategy 2: Aggressively purge error requests
        if capacity_status.requests_by_status.get('error', 0) > 0:
            self.logger.warning("🔥 CRISIS ACTION: Aggressively purging error requests")
            
            status_info = self.request_manager.get_all_request_status()
            error_requests = status_info.get('error', [])
            
            if error_requests:
                start_time = time.time()
                results = self.request_manager.process_error_requests(error_requests)
                processing_time = time.time() - start_time
                
                successful_purges = len([r for r in results if r.success])
                
                action = CapacityAction(
                    action_type="crisis_purge_errors",
                    request_id=None,
                    success=successful_purges > 0,
                    message=f"Purged {successful_purges}/{len(error_requests)} error requests",
                    details={
                        'error_requests': len(error_requests),
                        'successful_purges': successful_purges,
                        'results': [asdict(r) for r in results]
                    },
                    timestamp=datetime.now().isoformat(),
                    processing_time=processing_time
                )
                actions.append(action)
        
        # Strategy 3: Emergency processing if enabled
        if self.config.emergency_processing_enabled and not actions:
            self.logger.warning("🚨 CRISIS ACTION: Emergency processing - forcing request completion")
            
            # This is a last resort - try to force completion of oldest processing requests
            # by checking if they might be stuck and need intervention
            action = self._attempt_emergency_processing(capacity_status)
            if action:
                actions.append(action)
        
        return actions
    
    def _execute_critical_strategy(self, capacity_status: CapacityStatus) -> List[CapacityAction]:
        """Execute critical strategy when at 9 requests."""
        actions = []
        
        self.logger.warning(f"⚠️ CAPACITY CRITICAL: {capacity_status.total_requests}/10 requests active")
        
        # Strategy: Proactively process priority requests
        if capacity_status.priority_requests > 0:
            self.logger.info("🔄 CRITICAL ACTION: Processing priority requests proactively")
            
            # Run a processing cycle with higher urgency
            start_time = time.time()
            cycle_result = self.request_manager.run_processing_cycle()
            processing_time = time.time() - start_time
            
            action = CapacityAction(
                action_type="critical_priority_processing",
                request_id=None,
                success=cycle_result.get('success', False),
                message=f"Priority processing cycle completed",
                details=cycle_result,
                timestamp=datetime.now().isoformat(),
                processing_time=processing_time
            )
            actions.append(action)
        
        return actions
    
    def _execute_approaching_strategy(self, capacity_status: CapacityStatus) -> List[CapacityAction]:
        """Execute approaching strategy when at 7-9 requests."""
        actions = []
        
        self.logger.info(f"📊 CAPACITY APPROACHING: {capacity_status.total_requests}/10 requests active")
        
        # Strategy: Optimize processing to prevent reaching critical levels
        if self.config.aggressive_processing_enabled:
            # Increase processing frequency for completed and error requests
            if capacity_status.priority_requests > 0:
                self.logger.info("⚡ APPROACHING ACTION: Optimizing request processing")
                
                start_time = time.time()
                cycle_result = self.request_manager.run_processing_cycle()
                processing_time = time.time() - start_time
                
                action = CapacityAction(
                    action_type="approaching_optimize_processing",
                    request_id=None,
                    success=cycle_result.get('success', False),
                    message="Optimization processing cycle completed",
                    details=cycle_result,
                    timestamp=datetime.now().isoformat(),
                    processing_time=processing_time
                )
                actions.append(action)
        
        return actions
    
    def _execute_normal_strategy(self, capacity_status: CapacityStatus) -> List[CapacityAction]:
        """Execute normal strategy when capacity is normal - AGGRESSIVE 10-REQUEST TARGETING."""
        actions = []
        
        self.logger.debug(f"✅ CAPACITY NORMAL: {capacity_status.total_requests}/10 requests active")
        
        # AGGRESSIVE STRATEGY 1: Always try to upload when below 10 requests
        if self.config.enable_upload_automation and capacity_status.total_requests < 10:
            available_slots = 10 - capacity_status.total_requests
            self.logger.info(f"🚀 AGGRESSIVE UPLOAD: {available_slots} slots available, attempting to fill all slots")
            
            upload_action = self._attempt_upload_automation(capacity_status)
            if upload_action:
                actions.append(upload_action)
        
        # AGGRESSIVE STRATEGY 2: Process priority requests immediately (reduced threshold)
        if capacity_status.priority_requests > 0:  # Changed from > 2 to > 0 for immediate processing
            self.logger.info("🔄 AGGRESSIVE ACTION: Immediate priority request processing")
            
            start_time = time.time()
            cycle_result = self.request_manager.run_processing_cycle()
            processing_time = time.time() - start_time
            
            action = CapacityAction(
                action_type="aggressive_priority_processing",
                request_id=None,
                success=cycle_result.get('success', False),
                message="Aggressive priority processing completed",
                details=cycle_result,
                timestamp=datetime.now().isoformat(),
                processing_time=processing_time
            )
            actions.append(action)
        
        return actions
    
    def _attempt_emergency_processing(self, capacity_status: CapacityStatus) -> Optional[CapacityAction]:
        """Attempt emergency processing for stuck requests."""
        try:
            self.logger.warning("🚨 EMERGENCY: Attempting to resolve stuck requests")
            
            # This is a placeholder for emergency processing logic
            # In a real implementation, this might involve:
            # 1. Checking for requests that have been processing too long
            # 2. Attempting to cancel stuck requests
            # 3. Force-purging requests that appear to be in limbo
            
            start_time = time.time()
            
            # For now, just log the attempt
            self.logger.warning("🚨 Emergency processing attempted - manual intervention may be required")
            
            return CapacityAction(
                action_type="emergency_processing",
                request_id=None,
                success=False,  # Mark as unsuccessful since this is a placeholder
                message="Emergency processing attempted - manual intervention may be required",
                details={
                    'capacity_status': asdict(capacity_status),
                    'note': 'This is a placeholder for emergency processing logic'
                },
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Error in emergency processing: {e}")
            return None
    
    def _attempt_upload_automation(self, capacity_status: CapacityStatus) -> Optional[CapacityAction]:
        """
        Attempt to upload new requests when capacity allows.
        
        Args:
            capacity_status: Current capacity status
            
        Returns:
            CapacityAction if upload was attempted, None otherwise
        """
        try:
            # AGGRESSIVE CAPACITY CHECK: Allow uploads even at 10 requests to maintain maximum throughput
            if capacity_status.total_requests > self.config.upload_capacity_threshold:
                self.logger.debug(f"🚫 Upload skipped: {capacity_status.total_requests} requests active "
                                f"(threshold: {self.config.upload_capacity_threshold})")
                return None
            
            # Discover available control files
            control_files = discover_control_files(self.config.control_files_dir)
            
            if not control_files:
                self.logger.debug("📤 No control files found for upload")
                return None
            
            # AGGRESSIVE UPLOAD STRATEGY: Calculate maximum files to upload to reach exactly 10 requests
            available_slots = max(0, 10 - capacity_status.total_requests)
            max_uploadable = min(
                len(control_files),
                self.config.upload_batch_size,
                max(available_slots, 1)  # Always try to upload at least 1 file if any available
            )
            
            # AGGRESSIVE: Even if no slots, try to upload 1 file to maintain pressure
            if max_uploadable <= 0 and len(control_files) > 0:
                max_uploadable = 1
                self.logger.info(f"🔥 AGGRESSIVE UPLOAD: No slots available but forcing 1 file upload to maintain 10-request target")
            
            # Select files to upload
            files_to_upload = control_files[:max_uploadable]
            
            self.logger.info(f"📤 UPLOAD AUTOMATION: Uploading {len(files_to_upload)} files "
                           f"(capacity: {capacity_status.total_requests}/10)")
            
            start_time = time.time()
            
            # Submit the files
            upload_result = submit_batch_files(
                file_paths=files_to_upload,
                rate_limit_delay=self.config.upload_rate_limit_delay,
                logger=self.logger
            )
            
            processing_time = time.time() - start_time
            
            # Determine success
            success = upload_result.get('success', False)
            submitted_count = len(upload_result.get('submitted_files', []))
            failed_count = len(upload_result.get('failed_files', []))
            
            if success and submitted_count > 0:
                self.logger.info(f"✅ Upload automation successful: {submitted_count} files submitted")
                message = f"Successfully uploaded {submitted_count} files"
            else:
                self.logger.warning(f"⚠️ Upload automation issues: {failed_count} failures")
                message = f"Upload completed with {failed_count} failures"
            
            return CapacityAction(
                action_type="upload_automation",
                request_id=None,
                success=success,
                message=message,
                details={
                    'files_attempted': len(files_to_upload),
                    'files_submitted': submitted_count,
                    'files_failed': failed_count,
                    'request_ids': upload_result.get('request_ids', []),
                    'upload_result': upload_result,
                    'capacity_before': capacity_status.total_requests,
                    'available_slots_before': capacity_status.available_slots
                },
                timestamp=datetime.now().isoformat(),
                processing_time=processing_time
            )
            
        except Exception as e:
            self.logger.error(f"Error in upload automation: {e}")
            return CapacityAction(
                action_type="upload_automation",
                request_id=None,
                success=False,
                message=f"Upload automation failed: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now().isoformat(),
                processing_time=0.0
            )
    
    def trigger_upload_automation(self, max_files: Optional[int] = None) -> CapacityAction:
        """
        Manually trigger upload automation.
        
        Args:
            max_files: Maximum number of files to upload (overrides config)
            
        Returns:
            CapacityAction with upload results
        """
        try:
            # Get current capacity status
            capacity_status = self.get_current_capacity_status()
            
            # Temporarily override batch size if specified
            original_batch_size = self.config.upload_batch_size
            if max_files is not None:
                self.config.upload_batch_size = max_files
            
            try:
                # Attempt upload
                result = self._attempt_upload_automation(capacity_status)
                
                if result is None:
                    return CapacityAction(
                        action_type="manual_upload_trigger",
                        request_id=None,
                        success=False,
                        message="Upload not triggered - insufficient capacity or no files available",
                        details={
                            'capacity_status': asdict(capacity_status),
                            'reason': 'capacity_or_files'
                        },
                        timestamp=datetime.now().isoformat(),
                        processing_time=0.0
                    )
                
                # Update action type to indicate manual trigger
                result.action_type = "manual_upload_trigger"
                return result
                
            finally:
                # Restore original batch size
                self.config.upload_batch_size = original_batch_size
                
        except Exception as e:
            self.logger.error(f"Error in manual upload trigger: {e}")
            return CapacityAction(
                action_type="manual_upload_trigger",
                request_id=None,
                success=False,
                message=f"Manual upload trigger failed: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now().isoformat(),
                processing_time=0.0
            )
    
    def get_upload_status(self) -> Dict[str, Any]:
        """
        Get current upload automation status.
        
        Returns:
            Dictionary with upload status information
        """
        try:
            capacity_status = self.get_current_capacity_status()
            control_files = discover_control_files(self.config.control_files_dir)
            
            # Calculate upload readiness
            can_upload = (
                self.config.enable_upload_automation and
                capacity_status.total_requests <= self.config.upload_capacity_threshold and
                len(control_files) > 0 and
                capacity_status.available_slots > 0
            )
            
            max_uploadable = 0
            if can_upload:
                max_uploadable = min(
                    len(control_files),
                    self.config.upload_batch_size,
                    capacity_status.available_slots
                )
            
            return {
                'upload_enabled': self.config.enable_upload_automation,
                'can_upload': can_upload,
                'capacity_status': asdict(capacity_status),
                'available_control_files': len(control_files),
                'control_files': control_files[:10],  # Show first 10 files
                'max_uploadable': max_uploadable,
                'upload_threshold': self.config.upload_capacity_threshold,
                'upload_batch_size': self.config.upload_batch_size,
                'control_files_dir': self.config.control_files_dir,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting upload status: {e}")
            return {
                'error': str(e),
                'last_updated': datetime.now().isoformat()
            }
    
    def run_capacity_monitoring_cycle(self) -> Dict[str, Any]:
        """
        Run a single capacity monitoring cycle.
        
        Returns:
            Dictionary with cycle results
        """
        cycle_start = time.time()
        
        try:
            # Get current capacity status
            capacity_status = self.get_current_capacity_status()
            
            # Execute appropriate strategy
            actions = self.execute_capacity_strategy(capacity_status)
            
            # Update statistics
            with self.capacity_lock:
                self.capacity_stats['total_monitoring_cycles'] += 1
            
            cycle_time = time.time() - cycle_start
            
            # Log capacity status
            level_emoji = {
                CapacityLevel.NORMAL: "✅",
                CapacityLevel.APPROACHING: "📊",
                CapacityLevel.CRITICAL: "⚠️",
                CapacityLevel.CRISIS: "🚨"
            }
            
            emoji = level_emoji.get(capacity_status.capacity_level, "❓")
            self.logger.info(f"{emoji} Capacity: {capacity_status.total_requests}/10 "
                           f"({capacity_status.capacity_level.value}) - "
                           f"{len(actions)} actions taken")
            
            return {
                'success': True,
                'cycle_duration': cycle_time,
                'capacity_status': asdict(capacity_status),
                'actions_taken': [asdict(action) for action in actions],
                'statistics': self.capacity_stats.copy(),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Error in capacity monitoring cycle: {e}"
            self.logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'cycle_duration': time.time() - cycle_start,
                'timestamp': datetime.now().isoformat()
            }
    
    def start_capacity_monitoring(self):
        """Start continuous capacity monitoring in background thread."""
        if self.monitoring_active:
            self.logger.warning("Capacity monitoring is already active")
            return
        
        def monitoring_loop():
            self.logger.info(f"Starting capacity monitoring loop (interval: {self.config.monitoring_interval}s)")
            
            while self.monitoring_active:
                try:
                    # Run monitoring cycle
                    cycle_result = self.run_capacity_monitoring_cycle()
                    
                    if cycle_result['success']:
                        capacity_level = cycle_result['capacity_status']['capacity_level']
                        actions_count = len(cycle_result['actions_taken'])
                        
                        if capacity_level in ['crisis', 'critical']:
                            self.logger.warning(f"🚨 Capacity monitoring: {capacity_level} level, {actions_count} actions")
                        else:
                            self.logger.debug(f"✅ Capacity monitoring: {capacity_level} level, {actions_count} actions")
                    else:
                        self.logger.error(f"❌ Capacity monitoring cycle failed: {cycle_result.get('error', 'Unknown error')}")
                    
                    # Wait for next cycle
                    time.sleep(self.config.monitoring_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in capacity monitoring loop: {e}")
                    time.sleep(min(self.config.monitoring_interval, 60))  # Wait at least 60 seconds on error
            
            self.logger.info("Capacity monitoring loop stopped")
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        self.logger.info("Capacity monitoring started")
    
    def stop_capacity_monitoring(self):
        """Stop continuous capacity monitoring."""
        if not self.monitoring_active:
            return
        
        self.logger.info("Stopping capacity monitoring...")
        self.monitoring_active = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=10)
        
        self.logger.info("Capacity monitoring stopped")
    
    def get_capacity_analytics(self) -> Dict[str, Any]:
        """
        Get comprehensive capacity analytics.
        
        Returns:
            Dictionary with capacity analytics
        """
        try:
            current_status = self.current_status
            
            # Calculate capacity trends
            capacity_trends = {}
            if len(self.capacity_history) > 1:
                recent_history = self.capacity_history[-10:]  # Last 10 readings
                
                capacity_trends = {
                    'average_requests': sum(s.total_requests for s in recent_history) / len(recent_history),
                    'max_requests': max(s.total_requests for s in recent_history),
                    'min_requests': min(s.total_requests for s in recent_history),
                    'trend_direction': 'stable'  # Could be calculated based on slope
                }
                
                # Simple trend calculation
                if len(recent_history) >= 3:
                    first_third = sum(s.total_requests for s in recent_history[:3]) / 3
                    last_third = sum(s.total_requests for s in recent_history[-3:]) / 3
                    
                    if last_third > first_third + 1:
                        capacity_trends['trend_direction'] = 'increasing'
                    elif last_third < first_third - 1:
                        capacity_trends['trend_direction'] = 'decreasing'
            
            # Calculate time in each capacity level
            level_distribution = {}
            if self.capacity_history:
                for level in CapacityLevel:
                    count = len([s for s in self.capacity_history if s.capacity_level == level])
                    level_distribution[level.value] = {
                        'count': count,
                        'percentage': (count / len(self.capacity_history)) * 100
                    }
            
            return {
                'current_status': asdict(current_status) if current_status else None,
                'monitoring_active': self.monitoring_active,
                'statistics': self.capacity_stats.copy(),
                'capacity_trends': capacity_trends,
                'level_distribution': level_distribution,
                'history_length': len(self.capacity_history),
                'config': asdict(self.config),
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting capacity analytics: {e}")
            return {'error': str(e), 'generated_at': datetime.now().isoformat()}


def create_capacity_manager(config: Optional[CapacityConfig] = None,
                          db_path: str = "src/python/data/automation_state.db") -> CapacityManager:
    """
    Factory function to create a Capacity Manager.
    
    Args:
        config: Configuration for capacity management
        db_path: Path to the SQLite database file
        
    Returns:
        Configured CapacityManager instance
    """
    return CapacityManager(config, db_path)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Capacity Manager')
    parser.add_argument('--start-monitoring', action='store_true',
                       help='Start continuous capacity monitoring')
    parser.add_argument('--single-cycle', action='store_true',
                       help='Run a single monitoring cycle')
    parser.add_argument('--status', action='store_true',
                       help='Show current capacity status')
    parser.add_argument('--analytics', action='store_true',
                       help='Show capacity analytics')
    parser.add_argument('--interval', type=int, default=60,
                       help='Monitoring interval in seconds')
    
    args = parser.parse_args()
    
    # Create configuration
    config = CapacityConfig(monitoring_interval=args.interval)
    
    # Create capacity manager
    manager = create_capacity_manager(config)
    
    try:
        if args.start_monitoring:
            print("=== Starting Continuous Capacity Monitoring ===")
            manager.start_capacity_monitoring()
            
            # Keep running until interrupted
            try:
                while manager.monitoring_active:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping capacity monitoring...")
                manager.stop_capacity_monitoring()
        
        elif args.single_cycle:
            print("=== Running Single Capacity Monitoring Cycle ===")
            result = manager.run_capacity_monitoring_cycle()
            print(json.dumps(result, indent=2))
        
        elif args.status:
            print("=== Current Capacity Status ===")
            status = manager.get_current_capacity_status()
            print(json.dumps(asdict(status), indent=2))
        
        elif args.analytics:
            print("=== Capacity Analytics ===")
            analytics = manager.get_capacity_analytics()
            print(json.dumps(analytics, indent=2))
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("CAPACITY MANAGER EXAMPLES")
            print("="*60)
            print("# Start continuous monitoring:")
            print("python automation/capacity_manager.py --start-monitoring")
            print("\n# Run single monitoring cycle:")
            print("python automation/capacity_manager.py --single-cycle")
            print("\n# Check current capacity status:")
            print("python automation/capacity_manager.py --status")
            print("\n# Show capacity analytics:")
            print("python automation/capacity_manager.py --analytics")
            print("="*60)
            
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(manager, 'monitoring_active') and manager.monitoring_active:
            manager.stop_capacity_monitoring()