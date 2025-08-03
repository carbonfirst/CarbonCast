#!/usr/bin/env python3
"""
Enhanced Processing Time Calculator for RDA Automation Dashboard

This module provides status-aware processing time calculation with comprehensive
validation and edge case handling. It works in conjunction with the timeline
validation service to ensure accurate processing time calculations.

Key Features:
- Status-aware processing time calculation based on request lifecycle
- Edge case handling for invalid time ranges and missing timestamps
- Validation that end_time >= start_time before calculation
- Comprehensive error handling and recovery mechanisms
- Support for different calculation modes (completed, ongoing, estimated)
- Detailed metrics and statistics for monitoring calculation accuracy
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum

# Import the timeline validation service
from .timeline_validator import (
    TimestampValidationService, 
    TimelineValidationRules,
    ParsedTimestamp,
    ValidationIssue,
    ValidationSeverity
)


class ProcessingTimeMode(Enum):
    """Processing time calculation modes."""
    COMPLETED = "completed"  # Request is completed, use actual times
    ONGOING = "ongoing"      # Request is still processing, use current time
    ESTIMATED = "estimated"  # Estimate based on historical data
    FAILED = "failed"        # Request failed, calculate time to failure


class ProcessingTimeStatus(Enum):
    """Status of processing time calculation."""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INVALID = "invalid"


@dataclass
class ProcessingTimeResult:
    """Data class for processing time calculation results."""
    processing_time_hours: Optional[float]
    processing_time_seconds: Optional[float]
    calculation_mode: ProcessingTimeMode
    status: ProcessingTimeStatus
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    request_status: str
    issues: List[ValidationIssue]
    confidence_score: float  # 0.0 to 1.0
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'processing_time_hours': self.processing_time_hours,
            'processing_time_seconds': self.processing_time_seconds,
            'processing_time_display': self.get_display_string(),
            'calculation_mode': self.calculation_mode.value,
            'status': self.status.value,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'request_status': self.request_status,
            'issues': [asdict(issue) for issue in self.issues],
            'confidence_score': self.confidence_score,
            'metadata': self.metadata
        }
    
    def get_display_string(self) -> str:
        """Get human-readable display string for processing time."""
        if self.processing_time_hours is None:
            return "N/A"
        
        if self.processing_time_hours < 0:
            return "Invalid"
        elif self.processing_time_hours < 1:
            minutes = self.processing_time_hours * 60
            return f"{minutes:.1f} minutes"
        elif self.processing_time_hours < 24:
            return f"{self.processing_time_hours:.1f} hours"
        else:
            days = self.processing_time_hours / 24
            return f"{days:.1f} days"


@dataclass
class ProcessingTimeStatistics:
    """Statistics for processing time calculations."""
    total_calculations: int
    successful_calculations: int
    failed_calculations: int
    average_processing_time_hours: float
    median_processing_time_hours: float
    min_processing_time_hours: float
    max_processing_time_hours: float
    mode_distribution: Dict[str, int]
    status_distribution: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class EnhancedProcessingTimeCalculator:
    """
    Enhanced processing time calculator with status-aware calculation and validation.
    
    This calculator replaces the problematic processing time calculation logic
    in the dashboard with a more robust, accurate, and auditable approach.
    """
    
    def __init__(self):
        """Initialize the processing time calculator."""
        self.logger = self._setup_logging()
        self.timestamp_service = TimestampValidationService()
        self.timeline_rules = TimelineValidationRules()
        
        # Statistics for monitoring calculation performance
        self.calculation_stats = {
            'total_calculations': 0,
            'successful_calculations': 0,
            'failed_calculations': 0,
            'mode_usage': {mode: 0 for mode in ProcessingTimeMode},
            'status_distribution': {status: 0 for status in ProcessingTimeStatus},
            'processing_times': [],  # Store for statistical analysis
            'common_issues': {}
        }
        
        # Configuration for calculation behavior
        self.config = {
            'max_reasonable_processing_hours': 24 * 365,  # 1 year
            'min_reasonable_processing_seconds': 1,       # 1 second
            'ongoing_calculation_buffer_minutes': 5,      # Buffer for ongoing calculations
            'confidence_threshold': 0.7,                  # Minimum confidence for reliable results
            'enable_estimation': True,                     # Enable estimation for incomplete data
            'default_estimation_hours': 24                 # Default estimation when no data available
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the calculator."""
        logger = logging.getLogger('rda_automation.processing_time_calculator')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def calculate_processing_time(self, 
                                 date_rqst: Union[str, datetime, None],
                                 date_ready: Union[str, datetime, None],
                                 date_purge: Union[str, datetime, None],
                                 request_status: str,
                                 request_id: str = "unknown") -> ProcessingTimeResult:
        """
        Calculate processing time with status-aware logic and comprehensive validation.
        
        Args:
            date_rqst: Request timestamp
            date_ready: Ready timestamp
            date_purge: Purge timestamp
            request_status: Current status of the request
            request_id: Request ID for error reporting
            
        Returns:
            ProcessingTimeResult with calculation results and validation issues
        """
        self.calculation_stats['total_calculations'] += 1
        issues = []
        metadata = {
            'request_id': request_id,
            'calculation_timestamp': datetime.now().isoformat()
        }
        
        # Validate timeline first
        timeline_result = self.timeline_rules.validate_timeline(
            date_rqst, date_ready, date_purge, request_id
        )
        
        # Extract validated timestamps
        start_time = timeline_result.requested_time.value if timeline_result.requested_time else None
        ready_time = timeline_result.ready_time.value if timeline_result.ready_time else None
        purge_time = timeline_result.purge_time.value if timeline_result.purge_time else None
        
        # Add timeline validation issues
        issues.extend(timeline_result.issues)
        
        # Determine calculation mode based on status and available timestamps
        calculation_mode = self._determine_calculation_mode(
            request_status, start_time, ready_time, purge_time
        )
        
        self.calculation_stats['mode_usage'][calculation_mode] += 1
        metadata['calculation_mode'] = calculation_mode.value
        
        # Perform calculation based on mode
        result = self._calculate_by_mode(
            calculation_mode, start_time, ready_time, purge_time, 
            request_status, issues, metadata
        )
        
        # Update statistics
        self._update_statistics(result)
        
        return result
    
    def _determine_calculation_mode(self, 
                                   request_status: str,
                                   start_time: Optional[datetime],
                                   ready_time: Optional[datetime],
                                   purge_time: Optional[datetime]) -> ProcessingTimeMode:
        """
        Determine the appropriate calculation mode based on status and available timestamps.
        
        Args:
            request_status: Current status of the request
            start_time: Parsed start timestamp
            ready_time: Parsed ready timestamp
            purge_time: Parsed purge timestamp
            
        Returns:
            ProcessingTimeMode for the calculation
        """
        status_lower = request_status.lower()
        
        # Completed requests with ready time
        if status_lower in ['completed', 'ready', 'online'] and ready_time:
            return ProcessingTimeMode.COMPLETED
        
        # Failed or purged requests
        if status_lower in ['failed', 'error', 'cancelled'] or 'purge' in status_lower:
            return ProcessingTimeMode.FAILED
        
        # Ongoing processing requests
        if status_lower in ['processing', 'running', 'active']:
            return ProcessingTimeMode.ONGOING
        
        # Queued requests or incomplete data - use estimation
        if status_lower in ['queued', 'pending', 'submitted'] or not ready_time:
            return ProcessingTimeMode.ESTIMATED
        
        # Default to ongoing for unknown statuses
        return ProcessingTimeMode.ONGOING
    
    def _calculate_by_mode(self, 
                          mode: ProcessingTimeMode,
                          start_time: Optional[datetime],
                          ready_time: Optional[datetime],
                          purge_time: Optional[datetime],
                          request_status: str,
                          issues: List[ValidationIssue],
                          metadata: Dict[str, Any]) -> ProcessingTimeResult:
        """
        Calculate processing time based on the determined mode.
        
        Args:
            mode: Calculation mode
            start_time: Parsed start timestamp
            ready_time: Parsed ready timestamp
            purge_time: Parsed purge timestamp
            request_status: Current status of the request
            issues: List of validation issues
            metadata: Metadata dictionary
            
        Returns:
            ProcessingTimeResult with calculation results
        """
        if mode == ProcessingTimeMode.COMPLETED:
            return self._calculate_completed_time(
                start_time, ready_time, request_status, issues, metadata
            )
        elif mode == ProcessingTimeMode.ONGOING:
            return self._calculate_ongoing_time(
                start_time, request_status, issues, metadata
            )
        elif mode == ProcessingTimeMode.FAILED:
            return self._calculate_failed_time(
                start_time, ready_time, purge_time, request_status, issues, metadata
            )
        elif mode == ProcessingTimeMode.ESTIMATED:
            return self._calculate_estimated_time(
                start_time, request_status, issues, metadata
            )
        else:
            # Fallback case
            return self._create_invalid_result(
                request_status, issues, metadata, f"Unknown calculation mode: {mode}"
            )
    
    def _calculate_completed_time(self, 
                                 start_time: Optional[datetime],
                                 ready_time: Optional[datetime],
                                 request_status: str,
                                 issues: List[ValidationIssue],
                                 metadata: Dict[str, Any]) -> ProcessingTimeResult:
        """Calculate processing time for completed requests."""
        if not start_time or not ready_time:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                issue_type="missing_timestamps_completed",
                message="Cannot calculate completed processing time: missing start or ready time",
                suggested_fix="Ensure both request and ready timestamps are available"
            ))
            return self._create_invalid_result(request_status, issues, metadata)
        
        # Remove timezone info for calculation
        calc_start = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
        calc_ready = ready_time.replace(tzinfo=None) if ready_time.tzinfo else ready_time
        
        # Validate chronological order
        if calc_ready < calc_start:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                issue_type="invalid_time_order_completed",
                message=f"Ready time ({calc_ready}) is before start time ({calc_start})",
                suggested_fix="Fix timestamp chronological order"
            ))
            return self._create_invalid_result(request_status, issues, metadata)
        
        # Calculate processing time
        time_diff = calc_ready - calc_start
        processing_seconds = time_diff.total_seconds()
        processing_hours = processing_seconds / 3600
        
        # Validate reasonable processing time
        status, confidence = self._validate_processing_time(
            processing_hours, processing_seconds, issues
        )
        
        metadata.update({
            'calculation_method': 'actual_completion_time',
            'time_difference_seconds': processing_seconds
        })
        
        return ProcessingTimeResult(
            processing_time_hours=processing_hours,
            processing_time_seconds=processing_seconds,
            calculation_mode=ProcessingTimeMode.COMPLETED,
            status=status,
            start_time=start_time,
            end_time=ready_time,
            request_status=request_status,
            issues=issues,
            confidence_score=confidence,
            metadata=metadata
        )
    
    def _calculate_ongoing_time(self, 
                               start_time: Optional[datetime],
                               request_status: str,
                               issues: List[ValidationIssue],
                               metadata: Dict[str, Any]) -> ProcessingTimeResult:
        """Calculate processing time for ongoing requests."""
        if not start_time:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                issue_type="missing_start_time_ongoing",
                message="Cannot calculate ongoing processing time: missing start time",
                suggested_fix="Ensure request timestamp is available"
            ))
            return self._create_invalid_result(request_status, issues, metadata)
        
        # Use current time as end time with buffer
        current_time = datetime.now()
        buffer_time = timedelta(minutes=self.config['ongoing_calculation_buffer_minutes'])
        calc_end_time = current_time - buffer_time
        
        # Remove timezone info for calculation
        calc_start = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
        
        # Validate that start time is not in the future
        if calc_start > current_time:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                issue_type="future_start_time_ongoing",
                message=f"Start time ({calc_start}) is in the future",
                suggested_fix="Verify timestamp accuracy"
            ))
            # Use current time as a fallback
            calc_start = current_time - timedelta(minutes=1)
        
        # Calculate processing time
        time_diff = calc_end_time - calc_start
        processing_seconds = time_diff.total_seconds()
        processing_hours = processing_seconds / 3600
        
        # Validate reasonable processing time
        status, confidence = self._validate_processing_time(
            processing_hours, processing_seconds, issues
        )
        
        # Lower confidence for ongoing calculations
        confidence *= 0.8
        
        metadata.update({
            'calculation_method': 'ongoing_with_current_time',
            'current_time_used': current_time.isoformat(),
            'buffer_minutes': self.config['ongoing_calculation_buffer_minutes']
        })
        
        return ProcessingTimeResult(
            processing_time_hours=processing_hours,
            processing_time_seconds=processing_seconds,
            calculation_mode=ProcessingTimeMode.ONGOING,
            status=status,
            start_time=start_time,
            end_time=calc_end_time,
            request_status=request_status,
            issues=issues,
            confidence_score=confidence,
            metadata=metadata
        )
    
    def _calculate_failed_time(self, 
                              start_time: Optional[datetime],
                              ready_time: Optional[datetime],
                              purge_time: Optional[datetime],
                              request_status: str,
                              issues: List[ValidationIssue],
                              metadata: Dict[str, Any]) -> ProcessingTimeResult:
        """Calculate processing time for failed requests."""
        if not start_time:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                issue_type="missing_start_time_failed",
                message="Cannot calculate failed processing time: missing start time",
                suggested_fix="Ensure request timestamp is available"
            ))
            return self._create_invalid_result(request_status, issues, metadata)
        
        # Determine end time for failed request
        end_time = None
        calculation_method = "unknown"
        
        if purge_time:
            end_time = purge_time
            calculation_method = "time_to_purge"
        elif ready_time:
            end_time = ready_time
            calculation_method = "time_to_ready_before_failure"
        else:
            # Use current time as fallback
            end_time = datetime.now()
            calculation_method = "time_to_current_failure"
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                issue_type="estimated_failure_time",
                message="Using current time as failure time estimate",
                suggested_fix="Provide actual failure timestamp if available"
            ))
        
        # Remove timezone info for calculation
        calc_start = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
        calc_end = end_time.replace(tzinfo=None) if end_time.tzinfo else end_time
        
        # Validate chronological order
        if calc_end < calc_start:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                issue_type="invalid_time_order_failed",
                message=f"End time ({calc_end}) is before start time ({calc_start})",
                suggested_fix="Fix timestamp chronological order"
            ))
            return self._create_invalid_result(request_status, issues, metadata)
        
        # Calculate processing time
        time_diff = calc_end - calc_start
        processing_seconds = time_diff.total_seconds()
        processing_hours = processing_seconds / 3600
        
        # Validate reasonable processing time
        status, confidence = self._validate_processing_time(
            processing_hours, processing_seconds, issues
        )
        
        # Lower confidence for failed calculations
        confidence *= 0.7
        
        metadata.update({
            'calculation_method': calculation_method,
            'failure_status': request_status
        })
        
        return ProcessingTimeResult(
            processing_time_hours=processing_hours,
            processing_time_seconds=processing_seconds,
            calculation_mode=ProcessingTimeMode.FAILED,
            status=status,
            start_time=start_time,
            end_time=end_time,
            request_status=request_status,
            issues=issues,
            confidence_score=confidence,
            metadata=metadata
        )
    
    def _calculate_estimated_time(self, 
                                 start_time: Optional[datetime],
                                 request_status: str,
                                 issues: List[ValidationIssue],
                                 metadata: Dict[str, Any]) -> ProcessingTimeResult:
        """Calculate estimated processing time for incomplete requests."""
        if not self.config['enable_estimation']:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                issue_type="estimation_disabled",
                message="Processing time estimation is disabled",
                suggested_fix="Enable estimation in configuration or provide actual timestamps"
            ))
            return self._create_invalid_result(request_status, issues, metadata)
        
        # Use historical average or default estimation
        estimated_hours = self._get_historical_average() or self.config['default_estimation_hours']
        estimated_seconds = estimated_hours * 3600
        
        # If we have start time, calculate elapsed time and adjust estimate
        if start_time:
            current_time = datetime.now()
            calc_start = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
            
            if calc_start <= current_time:
                elapsed_time = current_time - calc_start
                elapsed_hours = elapsed_time.total_seconds() / 3600
                
                # Use elapsed time if it's reasonable, otherwise use estimate
                if elapsed_hours > 0 and elapsed_hours < self.config['max_reasonable_processing_hours']:
                    estimated_hours = max(elapsed_hours, estimated_hours * 0.5)
                    estimated_seconds = estimated_hours * 3600
                    metadata['estimation_method'] = 'elapsed_time_adjusted'
                else:
                    metadata['estimation_method'] = 'historical_average'
            else:
                metadata['estimation_method'] = 'future_start_time_fallback'
        else:
            metadata['estimation_method'] = 'default_estimation'
        
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            issue_type="estimated_processing_time",
            message=f"Processing time estimated at {estimated_hours:.1f} hours",
            suggested_fix="Provide actual timestamps for accurate calculation"
        ))
        
        metadata.update({
            'estimated_hours': estimated_hours,
            'estimation_confidence': 'low'
        })
        
        return ProcessingTimeResult(
            processing_time_hours=estimated_hours,
            processing_time_seconds=estimated_seconds,
            calculation_mode=ProcessingTimeMode.ESTIMATED,
            status=ProcessingTimeStatus.WARNING,
            start_time=start_time,
            end_time=None,
            request_status=request_status,
            issues=issues,
            confidence_score=0.3,  # Low confidence for estimates
            metadata=metadata
        )
    
    def _validate_processing_time(self, 
                                 processing_hours: float,
                                 processing_seconds: float,
                                 issues: List[ValidationIssue]) -> Tuple[ProcessingTimeStatus, float]:
        """
        Validate calculated processing time for reasonableness.
        
        Args:
            processing_hours: Calculated processing time in hours
            processing_seconds: Calculated processing time in seconds
            issues: List to append validation issues to
            
        Returns:
            Tuple of (ProcessingTimeStatus, confidence_score)
        """
        status = ProcessingTimeStatus.SUCCESS
        confidence = 1.0
        
        # Check for negative time
        if processing_seconds < 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                issue_type="negative_processing_time",
                message=f"Negative processing time: {processing_hours:.2f} hours",
                suggested_fix="Fix chronological order of timestamps"
            ))
            return ProcessingTimeStatus.INVALID, 0.0
        
        # Check for unreasonably short time
        if processing_seconds < self.config['min_reasonable_processing_seconds']:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                issue_type="very_short_processing_time",
                message=f"Very short processing time: {processing_seconds:.1f} seconds",
                suggested_fix="Verify timestamp precision and accuracy"
            ))
            status = ProcessingTimeStatus.WARNING
            confidence *= 0.8
        
        # Check for unreasonably long time
        if processing_hours > self.config['max_reasonable_processing_hours']:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                issue_type="excessive_processing_time",
                message=f"Excessive processing time: {processing_hours:.1f} hours ({processing_hours/24:.1f} days)",
                suggested_fix="Verify timestamp accuracy and check for system issues"
            ))
            status = ProcessingTimeStatus.WARNING
            confidence *= 0.6
        
        # Check for moderately long time (more than 7 days)
        elif processing_hours > 24 * 7:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                issue_type="long_processing_time",
                message=f"Long processing time: {processing_hours:.1f} hours ({processing_hours/24:.1f} days)",
                suggested_fix="Consider if this processing time is expected for this type of request"
            ))
            confidence *= 0.9
        
        return status, confidence
    
    def _create_invalid_result(self, 
                              request_status: str,
                              issues: List[ValidationIssue],
                              metadata: Dict[str, Any],
                              additional_message: str = None) -> ProcessingTimeResult:
        """Create an invalid processing time result."""
        if additional_message:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                issue_type="calculation_failed",
                message=additional_message,
                suggested_fix="Review input data and calculation parameters"
            ))
        
        return ProcessingTimeResult(
            processing_time_hours=None,
            processing_time_seconds=None,
            calculation_mode=ProcessingTimeMode.FAILED,
            status=ProcessingTimeStatus.INVALID,
            start_time=None,
            end_time=None,
            request_status=request_status,
            issues=issues,
            confidence_score=0.0,
            metadata=metadata
        )
    
    def _get_historical_average(self) -> Optional[float]:
        """Get historical average processing time from stored calculations."""
        if not self.calculation_stats['processing_times']:
            return None
        
        # Filter out invalid times
        valid_times = [t for t in self.calculation_stats['processing_times'] 
                      if t > 0 and t < self.config['max_reasonable_processing_hours']]
        
        if not valid_times:
            return None
        
        return sum(valid_times) / len(valid_times)
    
    def _update_statistics(self, result: ProcessingTimeResult):
        """Update calculation statistics."""
        if result.status == ProcessingTimeStatus.INVALID:
            self.calculation_stats['failed_calculations'] += 1
        else:
            self.calculation_stats['successful_calculations'] += 1
            
            # Store processing time for historical analysis
            if result.processing_time_hours is not None and result.processing_time_hours > 0:
                self.calculation_stats['processing_times'].append(result.processing_time_hours)
                
                # Keep only recent times (last 1000 calculations)
                if len(self.calculation_stats['processing_times']) > 1000:
                    self.calculation_stats['processing_times'] = \
                        self.calculation_stats['processing_times'][-1000:]
        
        # Update status distribution
        self.calculation_stats['status_distribution'][result.status] += 1
        
        # Track common issues
        for issue in result.issues:
            if issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
                issue_key = issue.issue_type
                self.calculation_stats['common_issues'][issue_key] = \
                    self.calculation_stats['common_issues'].get(issue_key, 0) + 1
    
    def get_calculation_statistics(self) -> ProcessingTimeStatistics:
        """
        Get comprehensive calculation statistics.
        
        Returns:
            ProcessingTimeStatistics with detailed metrics
        """
        valid_times = [t for t in self.calculation_stats['processing_times'] 
                      if t > 0 and t < self.config['max_reasonable_processing_hours']]
        
        if valid_times:
            avg_time = sum(valid_times) / len(valid_times)
            sorted_times = sorted(valid_times)
            median_time = sorted_times[len(sorted_times) // 2]
            min_time = min(valid_times)
            max_time = max(valid_times)
        else:
            avg_time = median_time = min_time = max_time = 0.0
        
        return ProcessingTimeStatistics(
            total_calculations=self.calculation_stats['total_calculations'],
            successful_calculations=self.calculation_stats['successful_calculations'],
            failed_calculations=self.calculation_stats['failed_calculations'],
            average_processing_time_hours=avg_time,
            median_processing_time_hours=median_time,
            min_processing_time_hours=min_time,
            max_processing_time_hours=max_time,
            mode_distribution={mode.value: count for mode, count in self.calculation_stats['mode_usage'].items()},
            status_distribution={status.value: count for status, count in self.calculation_stats['status_distribution'].items()}
        )
    
    def batch_calculate_processing_times(self, 
                                        requests: List[Dict[str, Any]]) -> List[ProcessingTimeResult]:
        """
        Calculate processing times for a batch of requests.
        
        Args:
            requests: List of request dictionaries with timestamp and status information
            
        Returns:
            List of ProcessingTimeResult objects
        """
        results = []
        
        for request in requests:
            try:
                result = self.calculate_processing_time(
                    date_rqst=request.get('date_rqst'),
                    date_ready=request.get('date_ready'),
                    date_purge=request.get('date_purge'),
                    request_status=request.get('status', 'unknown'),
                    request_id=request.get('request_id', 'unknown')
                )
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error calculating processing time for request {request.get('request_id', 'unknown')}: {e}")
                # Create error result
                error_result = self._create_invalid_result(
                    request.get('status', 'unknown'),
                    [ValidationIssue(
                        severity=ValidationSeverity.CRITICAL,
                        issue_type="calculation_exception",
                        message=f"Exception during calculation: {str(e)}",
                        suggested_fix="Review input data and check for data corruption"
                    )],
                    {'request_id': request.get('request_id', 'unknown')},
                    f"Calculation failed with exception: {str(e)}"
                )
                results.append(error_result)
        
        return results


def create_processing_time_calculator() -> EnhancedProcessingTimeCalculator:
    """
    Factory function to create an EnhancedProcessingTimeCalculator instance.
    
    Returns:
        Configured EnhancedProcessingTimeCalculator instance
    """
    return EnhancedProcessingTimeCalculator()


# Example usage and testing
if __name__ == '__main__':
    # Example usage of the processing time calculator
    calculator = create_processing_time_calculator()
    
    # Test cases
    test_cases = [
        {
            'name': 'Completed Request',
            'date_rqst': '2024-01-15T10:00:00Z',
            'date_ready': '2024-01-15T14:30:00Z',
            'date_purge': '2024-01-22T10:00:00Z',
            'status': 'completed',
            'request_id': 'test_001'
        },
        {
            'name': 'Ongoing Request',
            'date_rqst': '2024-01-15T10:00:00Z',
            'date_ready': None,
            'date_purge': None,
            'status': 'processing',
            'request_id': 'test_002'
        },
        {
            'name': 'Failed Request',
            'date_rqst': '2024-01-15T10:00:00Z',
            'date_ready': None,
            'date_purge': '2024-01-15T12:00:00Z',
            'status': 'failed',
            'request_id': 'test_003'
        },
        {
            'name': 'Invalid Timeline',
            'date_rqst': '2024-01-15T14:00:00Z',
            'date_ready': '2024-01-15T10:00:00Z',  # Ready before request
            'date_purge': None,
            'status': 'completed',
            'request_id': 'test_004'
        }
    ]
    
    print("=== Processing Time Calculator Tests ===")
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        result = calculator.calculate_processing_time(
            date_rqst=test_case['date_rqst'],
            date_ready=test_case['date_ready'],
            date_purge=test_case['date_purge'],
            request_status=test_case['status'],
            request_id=test_case['request_id']
        )
        
        print(f"  Status: {result.status.value}")
        print(f"  Mode: {result.calculation_mode.value}")
        print(f"  Processing Time: {result.get_display_string()}")
        print(f"  Confidence: {result.confidence_score:.2f}")
        print(f"  Issues: {len(result.issues)}")
        
        if result.issues:
            for issue in result.issues:
                print(f"    - {issue.severity.value}: {issue.message}")
    
    # Display statistics
    print("\n=== Calculator Statistics ===")
    stats = calculator.get_calculation_statistics()
    print(f"Total Calculations: {stats.total_calculations}")
    print(f"Success Rate: {(stats.successful_calculations / stats.total_calculations * 100):.1f}%")
    print(f"Average Processing Time: {stats.average_processing_time_hours:.2f} hours")