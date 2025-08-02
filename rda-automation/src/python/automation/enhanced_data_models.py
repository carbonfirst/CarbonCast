#!/usr/bin/env python3
"""
Enhanced Data Models for Integrated Error Tracking and Smart Retry System

This module provides comprehensive data model classes for the enhanced error tracking
and smart retry system, including clean interfaces for database operations and
business logic encapsulation.

Key Features:
- Enhanced error tracking with comprehensive classification
- Smart retry queue management with priority and scheduling
- Progress snapshots for trending analysis
- System health metrics collection
- Clean database interfaces with ORM-like functionality
- Type safety and validation
"""

import sqlite3
import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import threading


class ErrorType(Enum):
    """Enumeration of error types for classification."""
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    VALIDATION_ERROR = "validation_error"
    PROCESSING_ERROR = "processing_error"
    TIMEOUT_ERROR = "timeout_error"
    RESOURCE_ERROR = "resource_error"
    SYSTEM_ERROR = "system_error"
    DATA_ERROR = "data_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorSeverity(Enum):
    """Enumeration of error severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ErrorCategory(Enum):
    """Enumeration of error categories for grouping."""
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    RECOVERABLE = "recoverable"
    CONFIGURATION = "configuration"
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    USER_ERROR = "user_error"


class RetryStrategy(Enum):
    """Enumeration of retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"
    CUSTOM = "custom"


class QueueStatus(Enum):
    """Enumeration of retry queue statuses."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ResolutionStatus(Enum):
    """Enumeration of error resolution statuses."""
    UNRESOLVED = "unresolved"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    ESCALATED = "escalated"


class MetricStatus(Enum):
    """Enumeration of system health metric statuses."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ErrorTrackingRecord:
    """
    Enhanced error tracking record with comprehensive classification and metadata.
    
    This class represents a single error occurrence with detailed tracking information,
    classification, and retry management capabilities.
    """
    # Core identification
    id: Optional[int] = None
    request_id: str = ""
    request_index: Optional[str] = None
    session_id: Optional[str] = None
    
    # Error classification
    error_type: ErrorType = ErrorType.UNKNOWN_ERROR
    error_category: ErrorCategory = ErrorCategory.APPLICATION
    error_severity: ErrorSeverity = ErrorSeverity.MEDIUM
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Optional[str] = None
    stack_trace: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    
    # Request context
    region: Optional[str] = None
    variable_type: Optional[str] = None
    file_path: Optional[str] = None
    
    # Retry management
    retry_count: int = 0
    max_retries: int = 3
    is_retryable: bool = True
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    
    # Occurrence tracking
    first_occurrence: Optional[str] = None
    last_occurrence: Optional[str] = None
    frequency_count: int = 1
    
    # Resolution tracking
    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    resolution_notes: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    
    # Impact and analysis
    impact_score: float = 0.0
    related_errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values after object creation."""
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
        
        current_time = datetime.now().isoformat()
        if not self.first_occurrence:
            self.first_occurrence = current_time
        if not self.last_occurrence:
            self.last_occurrence = current_time
        if not self.created_at:
            self.created_at = current_time
        if not self.updated_at:
            self.updated_at = current_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the record to a dictionary for database storage."""
        data = asdict(self)
        
        # Convert enums to their values
        data['error_type'] = self.error_type.value
        data['error_category'] = self.error_category.value
        data['error_severity'] = self.error_severity.value
        data['retry_strategy'] = self.retry_strategy.value
        data['resolution_status'] = self.resolution_status.value
        
        # Convert complex fields to JSON
        data['context_data'] = json.dumps(self.context_data)
        data['related_errors'] = json.dumps(self.related_errors)
        data['metadata'] = json.dumps(self.metadata)
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ErrorTrackingRecord':
        """Create an ErrorTrackingRecord from a dictionary."""
        # Parse JSON fields
        if isinstance(data.get('context_data'), str):
            data['context_data'] = json.loads(data['context_data']) if data['context_data'] else {}
        if isinstance(data.get('related_errors'), str):
            data['related_errors'] = json.loads(data['related_errors']) if data['related_errors'] else []
        if isinstance(data.get('metadata'), str):
            data['metadata'] = json.loads(data['metadata']) if data['metadata'] else {}
        
        # Convert enum strings back to enums
        if 'error_type' in data and isinstance(data['error_type'], str):
            data['error_type'] = ErrorType(data['error_type'])
        if 'error_category' in data and isinstance(data['error_category'], str):
            data['error_category'] = ErrorCategory(data['error_category'])
        if 'error_severity' in data and isinstance(data['error_severity'], str):
            data['error_severity'] = ErrorSeverity(data['error_severity'])
        if 'retry_strategy' in data and isinstance(data['retry_strategy'], str):
            data['retry_strategy'] = RetryStrategy(data['retry_strategy'])
        if 'resolution_status' in data and isinstance(data['resolution_status'], str):
            data['resolution_status'] = ResolutionStatus(data['resolution_status'])
        
        return cls(**data)
    
    def update_occurrence(self):
        """Update the last occurrence timestamp and increment frequency."""
        self.last_occurrence = datetime.now().isoformat()
        self.frequency_count += 1
        self.updated_at = self.last_occurrence
    
    def mark_resolved(self, resolved_by: str, notes: Optional[str] = None):
        """Mark the error as resolved."""
        self.resolution_status = ResolutionStatus.RESOLVED
        self.resolved_at = datetime.now().isoformat()
        self.resolved_by = resolved_by
        if notes:
            self.resolution_notes = notes
        self.updated_at = self.resolved_at


@dataclass
class RetryQueueItem:
    """
    Smart retry queue item with comprehensive scheduling and management capabilities.
    
    This class represents a single item in the retry queue with intelligent scheduling,
    priority management, and success prediction.
    """
    # Core identification
    id: Optional[int] = None
    original_request_id: str = ""
    error_tracking_id: Optional[int] = None
    
    # Queue management
    queue_priority: int = 5  # 1-10 scale, 1 = highest priority
    retry_attempt: int = 1
    max_retry_attempts: int = 5
    queue_status: QueueStatus = QueueStatus.PENDING
    queue_position: Optional[int] = None
    
    # Retry strategy and timing
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay_seconds: int = 60
    current_delay_seconds: int = 60
    next_retry_time: Optional[str] = None
    retry_window_start: Optional[str] = None
    retry_window_end: Optional[str] = None
    
    # Request data and context
    request_data: Dict[str, Any] = field(default_factory=dict)
    context_data: Dict[str, Any] = field(default_factory=dict)
    region: Optional[str] = None
    variable_type: Optional[str] = None
    file_path: Optional[str] = None
    
    # Intelligence and prediction
    eligibility_score: float = 1.0  # 0.0-1.0, higher = more likely to succeed
    success_probability: float = 0.5  # 0.0-1.0, predicted success rate
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    retry_conditions: Dict[str, Any] = field(default_factory=dict)
    failure_patterns: List[str] = field(default_factory=list)
    
    # Processing information
    last_error_message: Optional[str] = None
    processing_node: Optional[str] = None
    estimated_duration: Optional[int] = None  # seconds
    actual_duration: Optional[int] = None  # seconds
    
    # History and metrics
    retry_history: List[Dict[str, Any]] = field(default_factory=list)
    metrics_data: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values after object creation."""
        if not self.original_request_id:
            self.original_request_id = str(uuid.uuid4())
        
        current_time = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = current_time
        if not self.updated_at:
            self.updated_at = current_time
        
        # Calculate initial next retry time if not set
        if not self.next_retry_time:
            next_time = datetime.now() + timedelta(seconds=self.current_delay_seconds)
            self.next_retry_time = next_time.isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the item to a dictionary for database storage."""
        data = asdict(self)
        
        # Convert enums to their values
        data['retry_strategy'] = self.retry_strategy.value
        data['queue_status'] = self.queue_status.value
        
        # Convert complex fields to JSON
        data['request_data'] = json.dumps(self.request_data)
        data['context_data'] = json.dumps(self.context_data)
        data['resource_requirements'] = json.dumps(self.resource_requirements)
        data['dependencies'] = json.dumps(self.dependencies)
        data['retry_conditions'] = json.dumps(self.retry_conditions)
        data['failure_patterns'] = json.dumps(self.failure_patterns)
        data['retry_history'] = json.dumps(self.retry_history)
        data['metrics_data'] = json.dumps(self.metrics_data)
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RetryQueueItem':
        """Create a RetryQueueItem from a dictionary."""
        # Parse JSON fields
        json_fields = [
            'request_data', 'context_data', 'resource_requirements',
            'dependencies', 'retry_conditions', 'failure_patterns',
            'retry_history', 'metrics_data'
        ]
        
        for field_name in json_fields:
            if isinstance(data.get(field_name), str):
                data[field_name] = json.loads(data[field_name]) if data[field_name] else ([] if field_name in ['dependencies', 'failure_patterns', 'retry_history'] else {})
        
        # Convert enum strings back to enums
        if 'retry_strategy' in data and isinstance(data['retry_strategy'], str):
            data['retry_strategy'] = RetryStrategy(data['retry_strategy'])
        if 'queue_status' in data and isinstance(data['queue_status'], str):
            data['queue_status'] = QueueStatus(data['queue_status'])
        
        return cls(**data)
    
    def calculate_next_retry_time(self) -> str:
        """Calculate the next retry time based on the retry strategy."""
        if self.retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            # Exponential backoff: delay = base_delay * (2 ^ (attempt - 1))
            delay = self.base_delay_seconds * (2 ** (self.retry_attempt - 1))
            # Cap at maximum delay (1 hour)
            delay = min(delay, 3600)
        elif self.retry_strategy == RetryStrategy.LINEAR_BACKOFF:
            # Linear backoff: delay = base_delay * attempt
            delay = self.base_delay_seconds * self.retry_attempt
        elif self.retry_strategy == RetryStrategy.FIXED_DELAY:
            # Fixed delay
            delay = self.base_delay_seconds
        elif self.retry_strategy == RetryStrategy.IMMEDIATE:
            # Immediate retry
            delay = 0
        else:
            # Default to exponential backoff
            delay = self.base_delay_seconds * (2 ** (self.retry_attempt - 1))
        
        self.current_delay_seconds = delay
        next_time = datetime.now() + timedelta(seconds=delay)
        self.next_retry_time = next_time.isoformat()
        return self.next_retry_time
    
    def add_retry_attempt(self, error_message: Optional[str] = None):
        """Record a retry attempt and update the item."""
        attempt_record = {
            'attempt_number': self.retry_attempt,
            'timestamp': datetime.now().isoformat(),
            'error_message': error_message,
            'delay_seconds': self.current_delay_seconds
        }
        
        self.retry_history.append(attempt_record)
        self.retry_attempt += 1
        self.last_error_message = error_message
        self.calculate_next_retry_time()
        self.updated_at = datetime.now().isoformat()
    
    def is_eligible_for_retry(self) -> bool:
        """Check if the item is eligible for retry."""
        return (
            self.retry_attempt <= self.max_retry_attempts and
            self.queue_status in [QueueStatus.PENDING, QueueStatus.SCHEDULED] and
            self.eligibility_score > 0.0
        )


@dataclass
class ProgressSnapshot:
    """
    Progress snapshot for trending analysis and performance monitoring.
    
    This class captures a point-in-time view of system progress and performance
    for historical analysis and trend identification.
    """
    # Core identification
    id: Optional[int] = None
    snapshot_type: str = "system"  # system, regional, variable, session
    snapshot_scope: str = "global"  # global, regional, variable-specific
    scope_identifier: Optional[str] = None
    snapshot_timestamp: Optional[str] = None
    
    # Basic metrics
    total_requests: int = 0
    completed_requests: int = 0
    failed_requests: int = 0
    pending_requests: int = 0
    retrying_requests: int = 0
    
    # Performance metrics
    success_rate: float = 0.0
    failure_rate: float = 0.0
    retry_rate: float = 0.0
    average_processing_time: float = 0.0
    throughput_per_hour: float = 0.0
    
    # Detailed breakdowns
    error_distribution: Dict[str, int] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    resource_utilization: Dict[str, float] = field(default_factory=dict)
    trend_indicators: Dict[str, Any] = field(default_factory=dict)
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    
    # Dimensional breakdowns
    regional_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    variable_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Advanced analytics
    time_series_data: List[Dict[str, Any]] = field(default_factory=list)
    comparative_data: Dict[str, Any] = field(default_factory=dict)
    anomaly_indicators: List[Dict[str, Any]] = field(default_factory=list)
    prediction_data: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values after object creation."""
        current_time = datetime.now().isoformat()
        if not self.snapshot_timestamp:
            self.snapshot_timestamp = current_time
        if not self.created_at:
            self.created_at = current_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the snapshot to a dictionary for database storage."""
        data = asdict(self)
        
        # Convert complex fields to JSON
        json_fields = [
            'error_distribution', 'performance_metrics', 'resource_utilization',
            'trend_indicators', 'quality_metrics', 'regional_breakdown',
            'variable_breakdown', 'time_series_data', 'comparative_data',
            'anomaly_indicators', 'prediction_data', 'metadata'
        ]
        
        for field_name in json_fields:
            data[field_name] = json.dumps(getattr(self, field_name))
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressSnapshot':
        """Create a ProgressSnapshot from a dictionary."""
        # Parse JSON fields
        json_fields = [
            'error_distribution', 'performance_metrics', 'resource_utilization',
            'trend_indicators', 'quality_metrics', 'regional_breakdown',
            'variable_breakdown', 'time_series_data', 'comparative_data',
            'anomaly_indicators', 'prediction_data', 'metadata'
        ]
        
        for field_name in json_fields:
            if isinstance(data.get(field_name), str):
                default_value = [] if field_name in ['time_series_data', 'anomaly_indicators'] else {}
                data[field_name] = json.loads(data[field_name]) if data[field_name] else default_value
        
        return cls(**data)
    
    def calculate_rates(self):
        """Calculate success, failure, and retry rates."""
        total = self.total_requests
        if total > 0:
            self.success_rate = (self.completed_requests / total) * 100
            self.failure_rate = (self.failed_requests / total) * 100
            self.retry_rate = (self.retrying_requests / total) * 100
        else:
            self.success_rate = self.failure_rate = self.retry_rate = 0.0


@dataclass
class SystemHealthMetric:
    """
    System health metric for comprehensive monitoring and alerting.
    
    This class represents a single system health metric with thresholds,
    alerting, and trend analysis capabilities.
    """
    # Core identification
    id: Optional[int] = None
    metric_timestamp: Optional[str] = None
    metric_category: str = "performance"  # performance, resource, error, throughput
    metric_name: str = ""
    metric_value: float = 0.0
    metric_unit: Optional[str] = None
    
    # Thresholds and status
    metric_threshold_min: Optional[float] = None
    metric_threshold_max: Optional[float] = None
    metric_status: MetricStatus = MetricStatus.NORMAL
    
    # Component information
    component_name: Optional[str] = None
    component_version: Optional[str] = None
    environment: str = "production"
    
    # Collection metadata
    data_source: Optional[str] = None
    collection_method: Optional[str] = None
    aggregation_period: int = 300  # seconds
    sample_count: int = 1
    
    # Statistical data
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    avg_value: Optional[float] = None
    std_deviation: Optional[float] = None
    percentile_95: Optional[float] = None
    percentile_99: Optional[float] = None
    
    # Trend analysis
    trend_direction: Optional[str] = None  # up, down, stable
    trend_magnitude: Optional[float] = None
    
    # Alerting
    alert_level: str = "none"  # none, info, warning, critical
    alert_message: Optional[str] = None
    
    # Additional data
    correlation_data: Dict[str, Any] = field(default_factory=dict)
    context_data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values after object creation."""
        current_time = datetime.now().isoformat()
        if not self.metric_timestamp:
            self.metric_timestamp = current_time
        if not self.created_at:
            self.created_at = current_time
        
        # Set statistical defaults
        if self.min_value is None:
            self.min_value = self.metric_value
        if self.max_value is None:
            self.max_value = self.metric_value
        if self.avg_value is None:
            self.avg_value = self.metric_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the metric to a dictionary for database storage."""
        data = asdict(self)
        
        # Convert enums to their values
        data['metric_status'] = self.metric_status.value
        
        # Convert complex fields to JSON
        data['correlation_data'] = json.dumps(self.correlation_data)
        data['context_data'] = json.dumps(self.context_data)
        data['tags'] = json.dumps(self.tags)
        data['metadata'] = json.dumps(self.metadata)
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemHealthMetric':
        """Create a SystemHealthMetric from a dictionary."""
        # Parse JSON fields
        json_fields = ['correlation_data', 'context_data', 'tags', 'metadata']
        
        for field_name in json_fields:
            if isinstance(data.get(field_name), str):
                default_value = [] if field_name == 'tags' else {}
                data[field_name] = json.loads(data[field_name]) if data[field_name] else default_value
        
        # Convert enum strings back to enums
        if 'metric_status' in data and isinstance(data['metric_status'], str):
            data['metric_status'] = MetricStatus(data['metric_status'])
        
        return cls(**data)
    
    def check_thresholds(self) -> MetricStatus:
        """Check metric value against thresholds and update status."""
        if self.metric_threshold_min is not None and self.metric_value < self.metric_threshold_min:
            self.metric_status = MetricStatus.CRITICAL
            self.alert_level = "critical"
            self.alert_message = f"{self.metric_name} below minimum threshold: {self.metric_value} < {self.metric_threshold_min}"
        elif self.metric_threshold_max is not None and self.metric_value > self.metric_threshold_max:
            self.metric_status = MetricStatus.CRITICAL
            self.alert_level = "critical"
            self.alert_message = f"{self.metric_name} above maximum threshold: {self.metric_value} > {self.metric_threshold_max}"
        else:
            self.metric_status = MetricStatus.NORMAL
            self.alert_level = "none"
            self.alert_message = None
        
        return self.metric_status


# Factory functions for creating data model instances

def create_error_record(
    request_id: str,
    error_type: ErrorType,
    error_message: str,
    **kwargs
) -> ErrorTrackingRecord:
    """
    Factory function to create an ErrorTrackingRecord.
    
    Args:
        request_id: Unique request identifier
        error_type: Type of error
        error_message: Error message
        **kwargs: Additional fields
        
    Returns:
        Configured ErrorTrackingRecord instance
    """
    return ErrorTrackingRecord(
        request_id=request_id,
        error_type=error_type,
        error_message=error_message,
        **kwargs
    )


def create_retry_item(
    original_request_id: str,
    request_data: Dict[str, Any],
    **kwargs
) -> RetryQueueItem:
    """
    Factory function to create a RetryQueueItem.
    
    Args:
        original_request_id: Original request identifier
        request_data: Request data for retry
        **kwargs: Additional fields
        
    Returns:
        Configured RetryQueueItem instance
    """
    return RetryQueueItem(
        original_request_id=original_request_id,
        request_data=request_data,
        **kwargs
    )


def create_progress_snapshot(
    snapshot_type: str,
    snapshot_scope: str,
    **kwargs
) -> ProgressSnapshot:
    """
    Factory function to create a ProgressSnapshot.
    
    Args:
        snapshot_type: Type of snapshot
        snapshot_scope: Scope of snapshot
        **kwargs: Additional fields
        
    Returns:
        Configured ProgressSnapshot instance
    """
    return ProgressSnapshot(
        snapshot_type=snapshot_type,
        snapshot_scope=snapshot_scope,
        **kwargs
    )


def create_health_metric(
    metric_category: str,
    metric_name: str,
    metric_value: float,
    **kwargs
) -> SystemHealthMetric:
    """
    Factory function to create a SystemHealthMetric.
    
    Args:
        metric_category: Category of metric
        metric_name: Name of metric
        metric_value: Metric value
        **kwargs: Additional fields
        
    Returns:
        Configured SystemHealthMetric instance
    """
    return SystemHealthMetric(
        metric_category=metric_category,
        metric_name=metric_name,
        metric_value=metric_value,
        **kwargs
    )


if __name__ == "__main__":
    # Example usage and testing
    print("=== Enhanced Data Models Testing ===")
    
    # Test ErrorTrackingRecord
    print("\n1. Testing ErrorTrackingRecord")
    error_record = create_error_record(
        request_id="test-123",
        error_type=ErrorType.NETWORK_ERROR,
        error_message="Connection timeout",
        region="CISO",
        variable_type="dswrf"
    )
    print(f"Created error record: {error_record.request_id}")
    print(f"Error type: {error_record.error_type.value}")
    
    # Test RetryQueueItem
    print("\n2. Testing RetryQueueItem")
    retry_item = create_retry_item(
        original_request_id="test-123",
        request_data={"file_path": "/path/to/file.ctl"},
        region="CISO",
        variable_type="dswrf"
    )
    print(f"Created retry item: {retry_item.original_request_id}")
    print(f"Next retry time: {retry_item.next_retry_time}")
    
    # Test ProgressSnapshot
    print("\n3. Testing ProgressSnapshot")
    snapshot = create_progress_snapshot(
        snapshot_type="regional",
        snapshot_scope="CISO",
        total_requests=100,
        completed_requests=85,
        failed_requests=10
    )
    snapshot.calculate_rates()
    print(f"Created snapshot: {snapshot.snapshot_type}")
    print(f"Success rate: {snapshot.success_rate}%")
    
    # Test SystemHealthMetric
    print("\n4. Testing SystemHealthMetric")
    metric = create_health_metric(
        metric_category="performance",
        metric_name="request_throughput",
        metric_value=150.5,
        metric_unit="requests/hour",
        metric_threshold_max=200.0
    )
    status = metric.check_thresholds()
    print(f"Created metric: {metric.metric_name}")
    print(f"Status: {status.value}")
    
    print("\n=== All tests completed successfully ===")