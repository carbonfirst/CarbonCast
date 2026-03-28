#!/usr/bin/env python3
"""
Enhanced Request Monitor for RDA Automation System

This module provides advanced request count monitoring with intelligent change detection,
adaptive monitoring intervals, and event-driven architecture. It serves as the foundation
for dynamic batch processing and capacity management.

Key Features:
- Real-time request count monitoring with intelligent change detection
- Adaptive monitoring intervals (5-30 seconds based on activity)
- Event-driven architecture with callback system
- Integration with existing batch automation components
- Request count drop detection (below 10 threshold)
- Comprehensive analytics and reporting
- Thread-safe operations with proper error handling
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import deque
import statistics

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger

import rdams_client
from automation.event_system import (
    EventDispatcher, EventType, EventPriority, RequestCountEvent, 
    ProcessingTriggerEvent, create_event_dispatcher, create_request_count_filter
)
from automation.monitoring_config import (
    EnhancedMonitoringConfig, MonitoringConfigManager, ThresholdConfig,
    create_monitoring_config_manager, create_default_monitoring_config
)


class RequestCountStatus(Enum):
    """Enumeration for request count status levels."""
    VERY_LOW = "very_low"      # 0-2 requests
    LOW = "low"                # 3-5 requests
    NORMAL = "normal"          # 6-8 requests
    HIGH = "high"              # 9 requests
    CRITICAL = "critical"      # 10+ requests


class ChangeDirection(Enum):
    """Enumeration for change directions."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


@dataclass
class RequestCountSnapshot:
    """Snapshot of request count at a specific time."""
    timestamp: str
    total_requests: int
    requests_by_status: Dict[str, int]
    status_level: RequestCountStatus
    source: str = "enhanced_monitor"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestCountChange:
    """Represents a change in request count."""
    previous_snapshot: RequestCountSnapshot
    current_snapshot: RequestCountSnapshot
    change_delta: int
    change_direction: ChangeDirection
    change_percentage: float
    threshold_crossed: Optional[str] = None
    significance_score: float = 0.0
    
    @property
    def is_significant(self) -> bool:
        """Check if this change is considered significant."""
        return abs(self.change_delta) >= 1 or self.threshold_crossed is not None


@dataclass
class TriggerContext:
    """Context information for processing triggers."""
    trigger_type: str
    trigger_reason: str
    current_count: int
    previous_count: int
    threshold_name: Optional[str]
    urgency_level: str
    suggested_actions: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitoringStatistics:
    """Statistics for monitoring operations."""
    total_monitoring_cycles: int = 0
    significant_changes_detected: int = 0
    thresholds_crossed: int = 0
    events_dispatched: int = 0
    triggers_generated: int = 0
    average_request_count: float = 0.0
    monitoring_uptime: float = 0.0
    last_change_time: Optional[str] = None
    error_count: int = 0


class EnhancedRequestMonitor:
    """
    Enhanced request monitor with intelligent change detection and event-driven architecture.
    
    This class provides comprehensive request count monitoring with adaptive intervals,
    threshold management, and integration with the existing automation system.
    """
    
    def __init__(self, 
                 config: Optional[EnhancedMonitoringConfig] = None,
                 event_dispatcher: Optional[EventDispatcher] = None,
                 db_path: str = "src/python/data/automation_state.db"):
        """
        Initialize the Enhanced Request Monitor.
        
        Args:
            config: Monitoring configuration
            event_dispatcher: Event dispatcher for notifications
            db_path: Path to the SQLite database
        """
        self.logger = self._setup_logging()
        self.db_path = db_path
        
        # Configuration
        self.config = config or create_default_monitoring_config()
        self.config_manager = create_monitoring_config_manager()
        
        # Event system
        self.event_dispatcher = event_dispatcher or create_event_dispatcher()
        self._setup_event_callbacks()
        
        # Monitoring state
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.current_interval = self.config.adaptive_intervals.base_interval
        
        # Request count tracking
        self.current_snapshot: Optional[RequestCountSnapshot] = None
        self.previous_snapshot: Optional[RequestCountSnapshot] = None
        self.snapshot_history: deque = deque(maxlen=100)
        
        # Change detection
        self.last_significant_change: Optional[RequestCountChange] = None
        self.change_history: deque = deque(maxlen=50)
        
        # Statistics
        self.statistics = MonitoringStatistics()
        self.start_time: Optional[float] = None
        
        # Threading
        self.monitor_lock = threading.RLock()
        
        # Integration components (will be set by integration layer)
        self.batch_system = None
        self.capacity_manager = None
        self.status_monitor = None
        
        self.logger.info("EnhancedRequestMonitor initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.enhanced_request_monitor', level=logging.INFO)
    
    def _setup_event_callbacks(self):
        """Set up event system callbacks."""
        if self.config.event_system.enabled:
            # Subscribe to our own request count events for logging
            if self.config.event_system.enable_logging_callback:
                self.event_dispatcher.subscribe(
                    callback=self._log_event_callback,
                    event_filter=create_request_count_filter(),
                    subscription_id="enhanced_monitor_logging"
                )
    
    def _log_event_callback(self, event):
        """Callback for logging events."""
        if hasattr(event, 'current_count') and hasattr(event, 'previous_count'):
            self.logger.info(f"📊 Request count changed: {event.previous_count} → {event.current_count} (Δ{event.change_delta})")
    
    def set_integration_components(self, 
                                 batch_system=None, 
                                 capacity_manager=None, 
                                 status_monitor=None):
        """
        Set integration components for enhanced monitoring.
        
        Args:
            batch_system: BatchAutomationSystem instance
            capacity_manager: CapacityManager instance
            status_monitor: StatusMonitor instance
        """
        self.batch_system = batch_system
        self.capacity_manager = capacity_manager
        self.status_monitor = status_monitor
        
        self.logger.info("✅ Integration components configured")
    
    def get_current_request_count(self) -> Tuple[int, Dict[str, int]]:
        """
        Get current request count from RDA system.
        
        Returns:
            Tuple of (total_count, requests_by_status)
        """
        try:
            # Try to get from batch system first (more efficient)
            if self.batch_system:
                total_count = self.batch_system._get_current_request_count()
                
                # Get detailed status breakdown
                requests_by_status = {
                    "submitted": 0,
                    "processing": 0,
                    "completed": 0,
                    "error": 0,
                    "unknown": 0
                }
                
                # Count requests by status from batch system
                for status_obj in self.batch_system.requests_state.values():
                    status = status_obj.status.lower()
                    if status in ["submitted", "processing"]:
                        if status == "submitted":
                            requests_by_status["submitted"] += 1
                        else:
                            requests_by_status["processing"] += 1
                
                return total_count, requests_by_status
            
            # Fallback to direct RDA API call
            status_result = rdams_client.get_status()
            
            if not status_result or 'data' not in status_result:
                self.logger.warning("⚠️ No data returned from RDA status check")
                return 0, {}
            
            requests_data = status_result['data']
            total_count = len(requests_data)
            
            # Categorize requests by status
            requests_by_status = {
                "submitted": 0,
                "processing": 0,
                "completed": 0,
                "error": 0,
                "unknown": 0
            }
            
            for request in requests_data:
                status = request.get('status', '').lower().strip()
                
                if 'completed' in status:
                    requests_by_status["completed"] += 1
                elif 'processing' in status or 'queued' in status:
                    requests_by_status["processing"] += 1
                elif 'error' in status or 'failed' in status:
                    requests_by_status["error"] += 1
                elif 'submitted' in status:
                    requests_by_status["submitted"] += 1
                else:
                    requests_by_status["unknown"] += 1
            
            return total_count, requests_by_status
            
        except Exception as e:
            self.logger.error(f"❌ Error getting current request count: {e}")
            with self.monitor_lock:
                self.statistics.error_count += 1
            return 0, {}
    
    def create_snapshot(self) -> RequestCountSnapshot:
        """
        Create a snapshot of current request count status.
        
        Returns:
            RequestCountSnapshot with current state
        """
        try:
            total_count, requests_by_status = self.get_current_request_count()
            
            # Determine status level
            if total_count <= 2:
                status_level = RequestCountStatus.VERY_LOW
            elif total_count <= 5:
                status_level = RequestCountStatus.LOW
            elif total_count <= 8:
                status_level = RequestCountStatus.NORMAL
            elif total_count == 9:
                status_level = RequestCountStatus.HIGH
            else:
                status_level = RequestCountStatus.CRITICAL
            
            snapshot = RequestCountSnapshot(
                timestamp=datetime.now().isoformat(),
                total_requests=total_count,
                requests_by_status=requests_by_status,
                status_level=status_level,
                metadata={
                    "monitoring_interval": self.current_interval,
                    "active_requests": requests_by_status.get("submitted", 0) + requests_by_status.get("processing", 0)
                }
            )
            
            return snapshot
            
        except Exception as e:
            self.logger.error(f"❌ Error creating snapshot: {e}")
            # Return empty snapshot on error
            return RequestCountSnapshot(
                timestamp=datetime.now().isoformat(),
                total_requests=0,
                requests_by_status={},
                status_level=RequestCountStatus.VERY_LOW
            )
    
    def detect_change(self, current: RequestCountSnapshot, previous: RequestCountSnapshot) -> Optional[RequestCountChange]:
        """
        Detect and analyze changes between snapshots.
        
        Args:
            current: Current snapshot
            previous: Previous snapshot
            
        Returns:
            RequestCountChange if significant change detected, None otherwise
        """
        try:
            change_delta = current.total_requests - previous.total_requests
            
            # Determine change direction
            if change_delta > 0:
                direction = ChangeDirection.INCREASING
            elif change_delta < 0:
                direction = ChangeDirection.DECREASING
            else:
                direction = ChangeDirection.STABLE
            
            # Calculate change percentage
            if previous.total_requests > 0:
                change_percentage = (change_delta / previous.total_requests) * 100
            else:
                change_percentage = 100.0 if change_delta > 0 else 0.0
            
            # Check for threshold crossings
            threshold_crossed = self._check_threshold_crossings(current, previous)
            
            # Calculate significance score
            significance_score = self._calculate_significance_score(change_delta, change_percentage, threshold_crossed)
            
            change = RequestCountChange(
                previous_snapshot=previous,
                current_snapshot=current,
                change_delta=change_delta,
                change_direction=direction,
                change_percentage=change_percentage,
                threshold_crossed=threshold_crossed,
                significance_score=significance_score
            )
            
            return change if change.is_significant else None
            
        except Exception as e:
            self.logger.error(f"❌ Error detecting change: {e}")
            return None
    
    def _check_threshold_crossings(self, current: RequestCountSnapshot, previous: RequestCountSnapshot) -> Optional[str]:
        """Check if any thresholds were crossed."""
        try:
            active_thresholds = self.config.get_active_thresholds()
            
            for threshold in active_thresholds:
                if threshold.threshold_type.value == "request_count":
                    threshold_value = int(threshold.value)
                    
                    # Check different comparison types
                    if threshold.comparison == "less_than":
                        if previous.total_requests >= threshold_value and current.total_requests < threshold_value:
                            return threshold.name
                    elif threshold.comparison == "greater_than":
                        if previous.total_requests <= threshold_value and current.total_requests > threshold_value:
                            return threshold.name
                    elif threshold.comparison == "equals":
                        if previous.total_requests != threshold_value and current.total_requests == threshold_value:
                            return threshold.name
                    elif threshold.comparison == "greater_than_or_equal":
                        if previous.total_requests < threshold_value and current.total_requests >= threshold_value:
                            return threshold.name
                    elif threshold.comparison == "less_than_or_equal":
                        if previous.total_requests > threshold_value and current.total_requests <= threshold_value:
                            return threshold.name
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error checking threshold crossings: {e}")
            return None
    
    def _calculate_significance_score(self, change_delta: int, change_percentage: float, threshold_crossed: Optional[str]) -> float:
        """Calculate significance score for a change."""
        score = 0.0
        
        # Base score from absolute change
        score += abs(change_delta) * 10
        
        # Additional score from percentage change
        score += abs(change_percentage) * 2
        
        # High score for threshold crossings
        if threshold_crossed:
            score += 50
        
        # Special scoring for critical levels
        if abs(change_delta) >= 3:
            score += 25
        
        return min(score, 100.0)  # Cap at 100
    
    def process_change(self, change: RequestCountChange) -> List[TriggerContext]:
        """
        Process a detected change and generate appropriate triggers.
        
        Args:
            change: The detected change
            
        Returns:
            List of trigger contexts generated
        """
        triggers = []
        
        try:
            current_count = change.current_snapshot.total_requests
            previous_count = change.previous_snapshot.total_requests
            
            # Generate triggers based on change characteristics
            
            # 1. Low request count trigger (below 10)
            if current_count < 10 and change.change_direction == ChangeDirection.DECREASING:
                triggers.append(TriggerContext(
                    trigger_type="low_request_count",
                    trigger_reason=f"Request count dropped to {current_count} (below 10 threshold)",
                    current_count=current_count,
                    previous_count=previous_count,
                    threshold_name="low_request_count",
                    urgency_level="high" if current_count < 5 else "normal",
                    suggested_actions=[
                        "trigger_upload_automation",
                        "check_available_control_files",
                        "increase_monitoring_frequency"
                    ]
                ))
            
            # 2. Capacity approaching trigger
            if current_count >= 8 and change.change_direction == ChangeDirection.INCREASING:
                triggers.append(TriggerContext(
                    trigger_type="approaching_capacity",
                    trigger_reason=f"Request count increased to {current_count} (approaching 10 limit)",
                    current_count=current_count,
                    previous_count=previous_count,
                    threshold_name="approaching_capacity",
                    urgency_level="high",
                    suggested_actions=[
                        "increase_monitoring_frequency",
                        "prepare_capacity_management",
                        "monitor_completion_rates"
                    ]
                ))
            
            # 3. At capacity trigger
            if current_count >= 10:
                triggers.append(TriggerContext(
                    trigger_type="at_capacity",
                    trigger_reason=f"Request count at or above capacity limit ({current_count}/10)",
                    current_count=current_count,
                    previous_count=previous_count,
                    threshold_name="at_capacity",
                    urgency_level="critical",
                    suggested_actions=[
                        "activate_capacity_management",
                        "process_completed_requests",
                        "purge_error_requests",
                        "maximum_monitoring_frequency"
                    ]
                ))
            
            # 4. Significant drop trigger
            if change.change_delta <= -3:
                triggers.append(TriggerContext(
                    trigger_type="significant_drop",
                    trigger_reason=f"Significant request count drop: {change.change_delta}",
                    current_count=current_count,
                    previous_count=previous_count,
                    threshold_name=None,
                    urgency_level="high",
                    suggested_actions=[
                        "investigate_completion_cause",
                        "trigger_upload_automation",
                        "maintain_target_capacity"
                    ]
                ))
            
            # 5. Threshold-specific triggers
            if change.threshold_crossed:
                threshold = self.config.get_threshold_by_name(change.threshold_crossed)
                if threshold:
                    triggers.append(TriggerContext(
                        trigger_type="threshold_crossed",
                        trigger_reason=f"Threshold '{threshold.name}' crossed: {threshold.description}",
                        current_count=current_count,
                        previous_count=previous_count,
                        threshold_name=change.threshold_crossed,
                        urgency_level="normal",
                        suggested_actions=[f"execute_{threshold.action.value}"]
                    ))
            
            return triggers
            
        except Exception as e:
            self.logger.error(f"❌ Error processing change: {e}")
            return []
    
    def dispatch_events(self, change: RequestCountChange, triggers: List[TriggerContext]):
        """
        Dispatch events for the detected change and triggers.
        
        Args:
            change: The detected change
            triggers: Generated triggers
        """
        try:
            if not self.config.event_system.enabled:
                return
            
            # Dispatch request count change event
            count_event = self.event_dispatcher.create_request_count_event(
                source_component="enhanced_request_monitor",
                previous_count=change.previous_snapshot.total_requests,
                current_count=change.current_snapshot.total_requests,
                threshold_crossed=change.threshold_crossed,
                priority=EventPriority.HIGH if change.significance_score > 50 else EventPriority.NORMAL
            )
            
            self.event_dispatcher.dispatch_event(count_event)
            
            # Dispatch trigger events
            for trigger in triggers:
                trigger_event = self.event_dispatcher.create_processing_trigger_event(
                    source_component="enhanced_request_monitor",
                    trigger_type=trigger.trigger_type,
                    trigger_reason=trigger.trigger_reason,
                    suggested_action=", ".join(trigger.suggested_actions),
                    urgency_level=trigger.urgency_level,
                    priority=EventPriority.CRITICAL if trigger.urgency_level == "critical" else EventPriority.HIGH
                )
                
                self.event_dispatcher.dispatch_event(trigger_event)
            
            with self.monitor_lock:
                self.statistics.events_dispatched += len(triggers) + 1
                self.statistics.triggers_generated += len(triggers)
            
        except Exception as e:
            self.logger.error(f"❌ Error dispatching events: {e}")
    
    def update_monitoring_interval(self, current_count: int):
        """
        Update monitoring interval based on current request count.
        
        Args:
            current_count: Current request count
        """
        try:
            new_interval = self.config.calculate_monitoring_interval(current_count)
            
            if new_interval != self.current_interval:
                old_interval = self.current_interval
                self.current_interval = new_interval
                
                self.logger.info(f"📊 Monitoring interval adjusted: {old_interval}s → {new_interval}s (count: {current_count})")
            
        except Exception as e:
            self.logger.error(f"❌ Error updating monitoring interval: {e}")
    
    def run_monitoring_cycle(self) -> Dict[str, Any]:
        """
        Run a single monitoring cycle.
        
        Returns:
            Dictionary with cycle results
        """
        cycle_start = time.time()
        
        try:
            with self.monitor_lock:
                self.statistics.total_monitoring_cycles += 1
            
            # Create current snapshot
            current_snapshot = self.create_snapshot()
            
            # Store snapshots
            self.previous_snapshot = self.current_snapshot
            self.current_snapshot = current_snapshot
            self.snapshot_history.append(current_snapshot)
            
            # Update monitoring interval
            self.update_monitoring_interval(current_snapshot.total_requests)
            
            # Detect changes if we have a previous snapshot
            change = None
            triggers = []
            
            if self.previous_snapshot:
                change = self.detect_change(current_snapshot, self.previous_snapshot)
                
                if change:
                    self.logger.info(f"🔍 Significant change detected: {change.change_delta} requests (score: {change.significance_score:.1f})")
                    
                    # Store change
                    self.last_significant_change = change
                    self.change_history.append(change)
                    
                    # Process change and generate triggers
                    triggers = self.process_change(change)
                    
                    # Dispatch events
                    self.dispatch_events(change, triggers)
                    
                    with self.monitor_lock:
                        self.statistics.significant_changes_detected += 1
                        self.statistics.last_change_time = current_snapshot.timestamp
                        
                        if change.threshold_crossed:
                            self.statistics.thresholds_crossed += 1
            
            # Update statistics
            with self.monitor_lock:
                if self.snapshot_history:
                    total_requests = [s.total_requests for s in self.snapshot_history]
                    self.statistics.average_request_count = statistics.mean(total_requests)
                
                if self.start_time:
                    self.statistics.monitoring_uptime = time.time() - self.start_time
            
            cycle_time = time.time() - cycle_start
            
            return {
                "success": True,
                "cycle_duration": cycle_time,
                "current_snapshot": asdict(current_snapshot),
                "change_detected": change is not None,
                "change_details": asdict(change) if change else None,
                "triggers_generated": len(triggers),
                "trigger_details": [asdict(t) for t in triggers],
                "next_interval": self.current_interval,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Error in monitoring cycle: {e}"
            self.logger.error(f"❌ {error_msg}")
            
            with self.monitor_lock:
                self.statistics.error_count += 1
            
            return {
                "success": False,
                "error": error_msg,
                "cycle_duration": time.time() - cycle_start,
                "timestamp": datetime.now().isoformat()
            }
    
    def start_monitoring(self):
        """Start continuous monitoring in background thread."""
        if self.monitoring_active:
            self.logger.warning("⚠️ Monitoring is already active")
            return
        
        def monitoring_loop():
            self.logger.info(f"🚀 Enhanced request monitoring started (base interval: {self.current_interval}s)")
            self.start_time = time.time()
            
            while self.monitoring_active:
                try:
                    # Run monitoring cycle
                    cycle_result = self.run_monitoring_cycle()
                    
                    if cycle_result["success"]:
                        # Log cycle results
                        snapshot = cycle_result["current_snapshot"]
                        self.logger.debug(f"📊 Monitoring cycle: {snapshot['total_requests']} requests, "
                                        f"status: {snapshot['status_level']}, "
                                        f"next: {cycle_result['next_interval']}s")
                        
                        if cycle_result["change_detected"]:
                            change = cycle_result["change_details"]
                            self.logger.info(f"🔄 Change: {change['change_delta']} requests, "
                                           f"triggers: {cycle_result['triggers_generated']}")
                    else:
                        self.logger.error(f"❌ Monitoring cycle failed: {cycle_result.get('error', 'Unknown error')}")
                    
                    # Wait for next cycle
                    time.sleep(self.current_interval)
                    
                except Exception as e:
                    self.logger.error(f"❌ Error in monitoring loop: {e}")
                    time.sleep(min(self.current_interval, 60))  # Wait at least 60 seconds on error
            
            self.logger.info("🛑 Enhanced request monitoring stopped")
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("✅ Enhanced request monitoring thread started")
    
    def stop_monitoring(self):
        """Stop continuous monitoring."""
        if not self.monitoring_active:
            return
        
        self.logger.info("🛑 Stopping enhanced request monitoring...")
        self.monitoring_active = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
        
        self.logger.info("✅ Enhanced request monitoring stopped")
    
    def get_current_status(self) -> Dict[str, Any]:
        """
        Get current monitoring status and statistics.
        
        Returns:
            Dictionary with current status information
        """
        try:
            with self.monitor_lock:
                current_snapshot_dict = asdict(self.current_snapshot) if self.current_snapshot else None
                last_change_dict = asdict(self.last_significant_change) if self.last_significant_change else None
                
                return {
                    "monitoring_active": self.monitoring_active,
                    "current_interval": self.current_interval,
                    "current_snapshot": current_snapshot_dict,
                    "last_significant_change": last_change_dict,
                    "statistics": asdict(self.statistics),
                    "configuration": {
                        "mode": self.config.monitoring_mode.value,
                        "enabled": self.config.enabled,
                        "adaptive_intervals_enabled": self.config.adaptive_intervals.enabled,
                        "event_system_enabled": self.config.event_system.enabled
                    },
                    "integration_status": {
                        "batch_system": self.batch_system is not None,
                        "capacity_manager": self.capacity_manager is not None,
                        "status_monitor": self.status_monitor is not None
                    },
                    "generated_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"❌ Error getting current status: {e}")
            return {"error": str(e), "generated_at": datetime.now().isoformat()}
    
    def get_analytics(self) -> Dict[str, Any]:
        """
        Get comprehensive analytics and insights.
        
        Returns:
            Dictionary with analytics data
        """
        try:
            with self.monitor_lock:
                # Calculate trends from snapshot history
                trends = {}
                if len(self.snapshot_history) >= 2:
                    recent_counts = [s.total_requests for s in list(self.snapshot_history)[-10:]]
                    
                    if len(recent_counts) >= 2:
                        # Simple trend calculation
                        first_half = recent_counts[:len(recent_counts)//2]
                        second_half = recent_counts[len(recent_counts)//2:]
                        
                        first_avg = statistics.mean(first_half)
                        second_avg = statistics.mean(second_half)
                        
                        if second_avg > first_avg + 0.5:
                            trends["direction"] = "increasing"
                        elif second_avg < first_avg - 0.5:
                            trends["direction"] = "decreasing"
                        else:
                            trends["direction"] = "stable"
                        
                        trends["recent_average"] = statistics.mean(recent_counts)
                        trends["recent_min"] = min(recent_counts)
                        trends["recent_max"] = max(recent_counts)
                
                # Change analysis
                change_analysis = {}
                if self.change_history:
                    recent_changes = list(self.change_history)[-20:]
                    
                    change_analysis["total_changes"] = len(recent_changes)
                    change_analysis["average_change_magnitude"] = statistics.mean([abs(c.change_delta) for c in recent_changes])
                    change_analysis["largest_increase"] = max([c.change_delta for c in recent_changes if c.change_delta > 0], default=0)
                    change_analysis["largest_decrease"] = min([c.change_delta for c in recent_changes if c.change_delta < 0], default=0)
                    
                    # Threshold crossing analysis
                    threshold_crossings = [c for c in recent_changes if c.threshold_crossed]
                    change_analysis["threshold_crossings"] = len(threshold_crossings)
                    
                    if threshold_crossings:
                        # Find most frequently crossed threshold
                        threshold_counts = {}
                        for change in threshold_crossings:
                            threshold_counts[change.threshold_crossed] = threshold_counts.get(change.threshold_crossed, 0) + 1
                        change_analysis["most_crossed_threshold"] = max(threshold_counts, key=threshold_counts.get)
                    else:
                        change_analysis["most_crossed_threshold"] = None
                
                return {
                    "monitoring_statistics": asdict(self.statistics),
                    "trends": trends,
                    "change_analysis": change_analysis,
                    "snapshot_history_size": len(self.snapshot_history),
                    "change_history_size": len(self.change_history),
                    "current_configuration": {
                        "monitoring_mode": self.config.monitoring_mode.value,
                        "adaptive_intervals": asdict(self.config.adaptive_intervals),
                        "active_thresholds": len(self.config.get_active_thresholds())
                    },
                    "generated_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"❌ Error getting analytics: {e}")
            return {"error": str(e), "generated_at": datetime.now().isoformat()}
    
    def cleanup(self):
        """Clean up the enhanced request monitor."""
        self.logger.info("🧹 Cleaning up EnhancedRequestMonitor...")
        
        # Stop monitoring
        self.stop_monitoring()
        
        # Clean up event system
        if self.event_dispatcher:
            self.event_dispatcher.cleanup()
        
        # Clear data structures
        with self.monitor_lock:
            self.snapshot_history.clear()
            self.change_history.clear()
            self.current_snapshot = None
            self.previous_snapshot = None
            self.last_significant_change = None
        
        self.logger.info("✅ EnhancedRequestMonitor cleanup completed")


def create_enhanced_request_monitor(config: Optional[EnhancedMonitoringConfig] = None,
                                  event_dispatcher: Optional[EventDispatcher] = None,
                                  db_path: str = "src/python/data/automation_state.db") -> EnhancedRequestMonitor:
    """
    Factory function to create an EnhancedRequestMonitor.
    
    Args:
        config: Monitoring configuration
        event_dispatcher: Event dispatcher for notifications
        db_path: Path to the SQLite database
        
    Returns:
        EnhancedRequestMonitor instance
    """
    return EnhancedRequestMonitor(
        config=config,
        event_dispatcher=event_dispatcher,
        db_path=db_path
    )


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Request Monitor')
    parser.add_argument('--start-monitoring', action='store_true',
                       help='Start continuous monitoring')
    parser.add_argument('--single-cycle', action='store_true',
                       help='Run a single monitoring cycle')
    parser.add_argument('--status', action='store_true',
                       help='Show current status')
    parser.add_argument('--analytics', action='store_true',
                       help='Show analytics')
    parser.add_argument('--config-file', type=str,
                       help='Configuration file path')
    
    args = parser.parse_args()
    
    # Create configuration
    if args.config_file:
        config = EnhancedMonitoringConfig.load_from_file(args.config_file)
    else:
        config = create_default_monitoring_config()
    
    # Create enhanced request monitor
    monitor = create_enhanced_request_monitor(config=config)
    
    try:
        if args.start_monitoring:
            print("=== Starting Enhanced Request Monitoring ===")
            monitor.start_monitoring()
            
            # Keep running until interrupted
            try:
                while monitor.monitoring_active:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping monitoring...")
                monitor.stop_monitoring()
        
        elif args.single_cycle:
            print("=== Running Single Monitoring Cycle ===")
            result = monitor.run_monitoring_cycle()
            print(json.dumps(result, indent=2))
        
        elif args.status:
            print("=== Current Monitoring Status ===")
            status = monitor.get_current_status()
            print(json.dumps(status, indent=2))
        
        elif args.analytics:
            print("=== Monitoring Analytics ===")
            analytics = monitor.get_analytics()
            print(json.dumps(analytics, indent=2))
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("ENHANCED REQUEST MONITOR EXAMPLES")
            print("="*60)
            print("# Start continuous monitoring:")
            print("python automation/enhanced_request_monitor.py --start-monitoring")
            print("\n# Run single monitoring cycle:")
            print("python automation/enhanced_request_monitor.py --single-cycle")
            print("\n# Check current status:")
            print("python automation/enhanced_request_monitor.py --status")
            print("\n# Show analytics:")
            print("python automation/enhanced_request_monitor.py --analytics")
            print("="*60)
            
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(monitor, 'monitoring_active') and monitor.monitoring_active:
            monitor.stop_monitoring()
    finally:
        monitor.cleanup()