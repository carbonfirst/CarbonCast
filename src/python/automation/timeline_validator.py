#!/usr/bin/env python3
"""
Timeline Validation Service for RDA Automation Dashboard

This module provides centralized timestamp parsing and timeline validation services
to fix critical timeline issues including:
- Inconsistent timestamp parsing with multiple format fallbacks
- Processing time calculation flaws that don't validate chronological order
- Missing validation for timestamp consistency (Requested ≤ Ready ≤ Purge)
- Timeline data synchronization issues during updates

Key Features:
- TimestampValidationService: Centralized timestamp parsing with robust error handling
- TimelineValidationRules: Chronological order validation and consistency checks
- Comprehensive error handling and recovery mechanisms
- Audit trail of validation issues for debugging
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from logger_utils import get_logger


class TimestampFormat(Enum):
    """Enumeration of supported timestamp formats."""
    ISO_WITH_MICROSECONDS_Z = '%Y-%m-%dT%H:%M:%S.%fZ'
    ISO_WITHOUT_MICROSECONDS_Z = '%Y-%m-%dT%H:%M:%SZ'
    ISO_WITH_MICROSECONDS_OFFSET = '%Y-%m-%dT%H:%M:%S.%f+00:00'
    ISO_WITHOUT_MICROSECONDS_OFFSET = '%Y-%m-%dT%H:%M:%S+00:00'
    ISO_WITH_MICROSECONDS = '%Y-%m-%dT%H:%M:%S.%f'
    ISO_WITHOUT_MICROSECONDS = '%Y-%m-%dT%H:%M:%S'
    STANDARD_WITH_MICROSECONDS = '%Y-%m-%d %H:%M:%S.%f'
    STANDARD_WITHOUT_MICROSECONDS = '%Y-%m-%d %H:%M:%S'
    DATE_ONLY = '%Y-%m-%d'
    RDA_COMPACT = '%Y%m%d%H%M%S'
    RDA_DATE_ONLY = '%Y%m%d'


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Data class for validation issues."""
    severity: ValidationSeverity
    issue_type: str
    message: str
    field_name: Optional[str] = None
    raw_value: Optional[str] = None
    suggested_fix: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class ParsedTimestamp:
    """Data class for parsed timestamp results."""
    value: Optional[datetime]
    original_string: str
    format_used: Optional[TimestampFormat]
    is_valid: bool
    issues: List[ValidationIssue]
    confidence_score: float  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'value': self.value.isoformat() if self.value else None,
            'original_string': self.original_string,
            'format_used': self.format_used.value if self.format_used else None,
            'is_valid': self.is_valid,
            'issues': [asdict(issue) for issue in self.issues],
            'confidence_score': self.confidence_score
        }


@dataclass
class TimelineValidationResult:
    """Data class for timeline validation results."""
    is_valid: bool
    requested_time: Optional[ParsedTimestamp]
    ready_time: Optional[ParsedTimestamp]
    purge_time: Optional[ParsedTimestamp]
    issues: List[ValidationIssue]
    chronological_order_valid: bool
    processing_time_hours: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'is_valid': self.is_valid,
            'requested_time': self.requested_time.to_dict() if self.requested_time else None,
            'ready_time': self.ready_time.to_dict() if self.ready_time else None,
            'purge_time': self.purge_time.to_dict() if self.purge_time else None,
            'issues': [asdict(issue) for issue in self.issues],
            'chronological_order_valid': self.chronological_order_valid,
            'processing_time_hours': self.processing_time_hours
        }


class TimestampValidationService:
    """
    Centralized timestamp parsing service with robust error handling.
    
    This service replaces the problematic _safe_parse_datetime() method
    with a more robust, consistent, and auditable approach.
    """
    
    def __init__(self):
        """Initialize the timestamp validation service."""
        self.logger = self._setup_logging()
        self.format_priority = [
            TimestampFormat.ISO_WITH_MICROSECONDS_Z,
            TimestampFormat.ISO_WITHOUT_MICROSECONDS_Z,
            TimestampFormat.ISO_WITH_MICROSECONDS_OFFSET,
            TimestampFormat.ISO_WITHOUT_MICROSECONDS_OFFSET,
            TimestampFormat.ISO_WITH_MICROSECONDS,
            TimestampFormat.ISO_WITHOUT_MICROSECONDS,
            TimestampFormat.STANDARD_WITH_MICROSECONDS,
            TimestampFormat.STANDARD_WITHOUT_MICROSECONDS,
            TimestampFormat.DATE_ONLY,
            TimestampFormat.RDA_COMPACT,
            TimestampFormat.RDA_DATE_ONLY
        ]
        
        # Statistics for monitoring parsing performance
        self.parsing_stats = {
            'total_attempts': 0,
            'successful_parses': 0,
            'failed_parses': 0,
            'format_usage': {fmt: 0 for fmt in TimestampFormat},
            'common_failures': {}
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.timeline_validator', level=logging.INFO)
    
    def parse_timestamp(self, timestamp_str: Union[str, None], 
                       field_name: str = "timestamp") -> ParsedTimestamp:
        """
        Parse a timestamp string with comprehensive validation and error handling.
        
        Args:
            timestamp_str: The timestamp string to parse
            field_name: Name of the field being parsed (for error reporting)
            
        Returns:
            ParsedTimestamp object with parsing results and validation issues
        """
        self.parsing_stats['total_attempts'] += 1
        issues = []
        
        # Handle None or empty strings
        if not timestamp_str:
            issue = ValidationIssue(
                severity=ValidationSeverity.WARNING,
                issue_type="missing_timestamp",
                message=f"Missing or empty timestamp for field '{field_name}'",
                field_name=field_name,
                raw_value=str(timestamp_str)
            )
            issues.append(issue)
            
            return ParsedTimestamp(
                value=None,
                original_string=str(timestamp_str),
                format_used=None,
                is_valid=False,
                issues=issues,
                confidence_score=0.0
            )
        
        # Clean the timestamp string
        cleaned_timestamp = str(timestamp_str).strip()
        
        # Try fromisoformat first (fastest for ISO dates)
        iso_result = self._try_iso_format(cleaned_timestamp, field_name)
        if iso_result.is_valid:
            self.parsing_stats['successful_parses'] += 1
            return iso_result
        else:
            issues.extend(iso_result.issues)
        
        # Try each format in priority order
        for fmt in self.format_priority:
            try:
                parsed_datetime = datetime.strptime(cleaned_timestamp, fmt.value)
                
                # Validate the parsed datetime
                validation_issues = self._validate_parsed_datetime(
                    parsed_datetime, field_name, cleaned_timestamp
                )
                issues.extend(validation_issues)
                
                # Calculate confidence score
                confidence = self._calculate_confidence_score(
                    fmt, cleaned_timestamp, validation_issues
                )
                
                self.parsing_stats['successful_parses'] += 1
                self.parsing_stats['format_usage'][fmt] += 1
                
                return ParsedTimestamp(
                    value=parsed_datetime,
                    original_string=cleaned_timestamp,
                    format_used=fmt,
                    is_valid=True,
                    issues=issues,
                    confidence_score=confidence
                )
                
            except (ValueError, TypeError) as e:
                # Continue to next format
                continue
        
        # If all formats failed, record the failure
        self.parsing_stats['failed_parses'] += 1
        failure_key = f"unparseable_{len(cleaned_timestamp)}_chars"
        self.parsing_stats['common_failures'][failure_key] = \
            self.parsing_stats['common_failures'].get(failure_key, 0) + 1
        
        critical_issue = ValidationIssue(
            severity=ValidationSeverity.CRITICAL,
            issue_type="unparseable_timestamp",
            message=f"Could not parse timestamp '{cleaned_timestamp}' for field '{field_name}' using any known format",
            field_name=field_name,
            raw_value=cleaned_timestamp,
            suggested_fix="Check timestamp format and ensure it matches expected patterns"
        )
        issues.append(critical_issue)
        
        self.logger.warning(f"Failed to parse timestamp: '{cleaned_timestamp}' for field '{field_name}'")
        
        return ParsedTimestamp(
            value=None,
            original_string=cleaned_timestamp,
            format_used=None,
            is_valid=False,
            issues=issues,
            confidence_score=0.0
        )
    
    def _try_iso_format(self, timestamp_str: str, field_name: str) -> ParsedTimestamp:
        """
        Try parsing using datetime.fromisoformat() with preprocessing.
        
        Args:
            timestamp_str: The timestamp string to parse
            field_name: Name of the field being parsed
            
        Returns:
            ParsedTimestamp object with parsing results
        """
        issues = []
        
        try:
            # Handle Z suffix by replacing with +00:00
            processed_str = timestamp_str
            if processed_str.endswith('Z'):
                processed_str = processed_str[:-1] + '+00:00'
            
            parsed_datetime = datetime.fromisoformat(processed_str)
            
            # Validate the parsed datetime
            validation_issues = self._validate_parsed_datetime(
                parsed_datetime, field_name, timestamp_str
            )
            issues.extend(validation_issues)
            
            # High confidence for ISO format
            confidence = 0.95 if not validation_issues else 0.85
            
            return ParsedTimestamp(
                value=parsed_datetime,
                original_string=timestamp_str,
                format_used=None,  # fromisoformat doesn't use specific format
                is_valid=True,
                issues=issues,
                confidence_score=confidence
            )
            
        except (ValueError, AttributeError) as e:
            issue = ValidationIssue(
                severity=ValidationSeverity.INFO,
                issue_type="iso_format_failed",
                message=f"ISO format parsing failed for '{timestamp_str}': {str(e)}",
                field_name=field_name,
                raw_value=timestamp_str
            )
            issues.append(issue)
            
            return ParsedTimestamp(
                value=None,
                original_string=timestamp_str,
                format_used=None,
                is_valid=False,
                issues=issues,
                confidence_score=0.0
            )
    
    def _validate_parsed_datetime(self, dt: datetime, field_name: str,
                                 original_str: str) -> List[ValidationIssue]:
        """
        Validate a parsed datetime for common issues.
        
        Args:
            dt: The parsed datetime object
            field_name: Name of the field being parsed
            original_str: Original timestamp string
            
        Returns:
            List of validation issues found
        """
        issues = []
        
        # Normalize datetime objects to UTC timezone-aware format for comparison
        # This fixes the timezone comparison error
        if dt.tzinfo is None:
            # If parsed datetime is timezone-naive, assume UTC
            dt_utc = dt.replace(tzinfo=timezone.utc)
        else:
            # If parsed datetime is timezone-aware, convert to UTC
            dt_utc = dt.astimezone(timezone.utc)
        
        # Get current time as timezone-aware UTC
        current_time_utc = datetime.now(timezone.utc)
        
        # Check if date is too far in the past (before 2000)
        if dt_utc.year < 2000:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                issue_type="date_too_old",
                message=f"Timestamp '{original_str}' for field '{field_name}' is before year 2000",
                field_name=field_name,
                raw_value=original_str,
                suggested_fix="Verify timestamp format and data source"
            ))
        
        # Check if date is too far in the future (more than 10 years)
        future_limit_utc = current_time_utc + timedelta(days=365 * 10)
        if dt_utc > future_limit_utc:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                issue_type="date_too_future",
                message=f"Timestamp '{original_str}' for field '{field_name}' is more than 10 years in the future",
                field_name=field_name,
                raw_value=original_str,
                suggested_fix="Verify timestamp format and data source"
            ))
        
        # Check for timezone awareness issues
        if dt.tzinfo is not None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                issue_type="timezone_aware",
                message=f"Timestamp '{original_str}' for field '{field_name}' is timezone-aware",
                field_name=field_name,
                raw_value=original_str
            ))
        
        return issues
    
    def _calculate_confidence_score(self, format_used: TimestampFormat, 
                                   timestamp_str: str, 
                                   validation_issues: List[ValidationIssue]) -> float:
        """
        Calculate confidence score for a parsed timestamp.
        
        Args:
            format_used: The format that successfully parsed the timestamp
            timestamp_str: Original timestamp string
            validation_issues: List of validation issues found
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = 0.9
        
        # Reduce confidence based on validation issues
        for issue in validation_issues:
            if issue.severity == ValidationSeverity.CRITICAL:
                base_confidence -= 0.3
            elif issue.severity == ValidationSeverity.ERROR:
                base_confidence -= 0.2
            elif issue.severity == ValidationSeverity.WARNING:
                base_confidence -= 0.1
        
        # Adjust confidence based on format specificity
        format_confidence_modifiers = {
            TimestampFormat.ISO_WITH_MICROSECONDS_Z: 0.0,  # Highest confidence
            TimestampFormat.ISO_WITHOUT_MICROSECONDS_Z: -0.05,
            TimestampFormat.ISO_WITH_MICROSECONDS_OFFSET: -0.05,
            TimestampFormat.ISO_WITHOUT_MICROSECONDS_OFFSET: -0.1,
            TimestampFormat.ISO_WITH_MICROSECONDS: -0.1,
            TimestampFormat.ISO_WITHOUT_MICROSECONDS: -0.15,
            TimestampFormat.STANDARD_WITH_MICROSECONDS: -0.2,
            TimestampFormat.STANDARD_WITHOUT_MICROSECONDS: -0.25,
            TimestampFormat.DATE_ONLY: -0.3,  # Less specific
            TimestampFormat.RDA_COMPACT: -0.2,
            TimestampFormat.RDA_DATE_ONLY: -0.35  # Lowest confidence
        }
        
        base_confidence += format_confidence_modifiers.get(format_used, -0.4)
        
        return max(0.0, min(1.0, base_confidence))
    
    def get_parsing_statistics(self) -> Dict[str, Any]:
        """
        Get parsing statistics for monitoring and debugging.
        
        Returns:
            Dictionary with parsing statistics
        """
        success_rate = 0.0
        if self.parsing_stats['total_attempts'] > 0:
            success_rate = (self.parsing_stats['successful_parses'] / 
                          self.parsing_stats['total_attempts']) * 100
        
        return {
            'total_attempts': self.parsing_stats['total_attempts'],
            'successful_parses': self.parsing_stats['successful_parses'],
            'failed_parses': self.parsing_stats['failed_parses'],
            'success_rate_percentage': success_rate,
            'format_usage': {fmt.value: count for fmt, count in self.parsing_stats['format_usage'].items()},
            'common_failures': self.parsing_stats['common_failures'],
            'generated_at': datetime.now().isoformat()
        }


class TimelineValidationRules:
    """
    Timeline validation rules for chronological order and consistency checks.
    
    This class enforces the critical requirement: date_rqst ≤ date_ready ≤ date_purge
    """
    
    def __init__(self):
        """Initialize the timeline validation rules."""
        self.logger = self._setup_logging()
        self.validation_stats = {
            'total_validations': 0,
            'valid_timelines': 0,
            'invalid_timelines': 0,
            'common_violations': {}
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.timeline_validation_rules', level=logging.INFO)
    
    def validate_timeline(self, date_rqst: Union[str, datetime, None],
                         date_ready: Union[str, datetime, None],
                         date_purge: Union[str, datetime, None],
                         request_id: str = "unknown") -> TimelineValidationResult:
        """
        Validate timeline chronological order and consistency.
        
        Args:
            date_rqst: Request timestamp (string or datetime)
            date_ready: Ready timestamp (string or datetime)
            date_purge: Purge timestamp (string or datetime)
            request_id: Request ID for error reporting
            
        Returns:
            TimelineValidationResult with validation results and issues
        """
        self.validation_stats['total_validations'] += 1
        issues = []
        
        # Parse timestamps using the validation service
        timestamp_service = TimestampValidationService()
        
        requested_time = self._parse_or_convert_timestamp(
            date_rqst, "date_rqst", timestamp_service
        )
        ready_time = self._parse_or_convert_timestamp(
            date_ready, "date_ready", timestamp_service
        )
        purge_time = self._parse_or_convert_timestamp(
            date_purge, "date_purge", timestamp_service
        )
        
        # Collect parsing issues
        if requested_time:
            issues.extend(requested_time.issues)
        if ready_time:
            issues.extend(ready_time.issues)
        if purge_time:
            issues.extend(purge_time.issues)
        
        # Validate chronological order
        chronological_valid = self._validate_chronological_order(
            requested_time, ready_time, purge_time, request_id, issues
        )
        
        # Calculate processing time if possible
        processing_time_hours = self._calculate_processing_time(
            requested_time, ready_time, issues
        )
        
        # Determine overall validity
        is_valid = (
            chronological_valid and
            (not requested_time or requested_time.is_valid) and
            (not ready_time or ready_time.is_valid) and
            (not purge_time or purge_time.is_valid)
        )
        
        if is_valid:
            self.validation_stats['valid_timelines'] += 1
        else:
            self.validation_stats['invalid_timelines'] += 1
            # Track common violations
            violation_key = self._get_violation_key(issues)
            self.validation_stats['common_violations'][violation_key] = \
                self.validation_stats['common_violations'].get(violation_key, 0) + 1
        
        return TimelineValidationResult(
            is_valid=is_valid,
            requested_time=requested_time,
            ready_time=ready_time,
            purge_time=purge_time,
            issues=issues,
            chronological_order_valid=chronological_valid,
            processing_time_hours=processing_time_hours
        )
    
    def _parse_or_convert_timestamp(self, timestamp: Union[str, datetime, None],
                                   field_name: str,
                                   service: TimestampValidationService) -> Optional[ParsedTimestamp]:
        """
        Parse or convert a timestamp to ParsedTimestamp format.
        
        Args:
            timestamp: The timestamp to parse/convert
            field_name: Name of the field
            service: TimestampValidationService instance
            
        Returns:
            ParsedTimestamp object or None
        """
        if timestamp is None:
            return None
        
        if isinstance(timestamp, datetime):
            # Convert datetime to ParsedTimestamp
            return ParsedTimestamp(
                value=timestamp,
                original_string=timestamp.isoformat(),
                format_used=None,
                is_valid=True,
                issues=[],
                confidence_score=1.0
            )
        
        # Parse string timestamp
        return service.parse_timestamp(timestamp, field_name)
    
    def _validate_chronological_order(self, requested_time: Optional[ParsedTimestamp],
                                     ready_time: Optional[ParsedTimestamp],
                                     purge_time: Optional[ParsedTimestamp],
                                     request_id: str,
                                     issues: List[ValidationIssue]) -> bool:
        """
        Validate chronological order: date_rqst ≤ date_ready ≤ date_purge
        
        Args:
            requested_time: Parsed requested timestamp
            ready_time: Parsed ready timestamp
            purge_time: Parsed purge timestamp
            request_id: Request ID for error reporting
            issues: List to append validation issues to
            
        Returns:
            True if chronological order is valid, False otherwise
        """
        chronological_valid = True
        
        # Extract datetime values for comparison
        req_dt = requested_time.value if requested_time and requested_time.is_valid else None
        ready_dt = ready_time.value if ready_time and ready_time.is_valid else None
        purge_dt = purge_time.value if purge_time and purge_time.is_valid else None
        
        # Remove timezone info for comparison if present
        if req_dt and req_dt.tzinfo:
            req_dt = req_dt.replace(tzinfo=None)
        if ready_dt and ready_dt.tzinfo:
            ready_dt = ready_dt.replace(tzinfo=None)
        if purge_dt and purge_dt.tzinfo:
            purge_dt = purge_dt.replace(tzinfo=None)
        
        # Validate: date_rqst ≤ date_ready
        if req_dt and ready_dt and req_dt > ready_dt:
            chronological_valid = False
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                issue_type="chronological_violation_req_ready",
                message=f"Request ID {request_id}: Request time ({req_dt}) is after ready time ({ready_dt})",
                field_name="date_rqst_vs_date_ready",
                suggested_fix="Verify timestamp accuracy and data source integrity"
            ))
        
        # Validate: date_ready ≤ date_purge
        if ready_dt and purge_dt and ready_dt > purge_dt:
            chronological_valid = False
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                issue_type="chronological_violation_ready_purge",
                message=f"Request ID {request_id}: Ready time ({ready_dt}) is after purge time ({purge_dt})",
                field_name="date_ready_vs_date_purge",
                suggested_fix="Verify timestamp accuracy and data source integrity"
            ))
        
        # Validate: date_rqst ≤ date_purge (transitive check)
        if req_dt and purge_dt and req_dt > purge_dt:
            chronological_valid = False
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                issue_type="chronological_violation_req_purge",
                message=f"Request ID {request_id}: Request time ({req_dt}) is after purge time ({purge_dt})",
                field_name="date_rqst_vs_date_purge",
                suggested_fix="Verify timestamp accuracy and data source integrity"
            ))
        
        return chronological_valid
    
    def _calculate_processing_time(self, requested_time: Optional[ParsedTimestamp],
                                  ready_time: Optional[ParsedTimestamp],
                                  issues: List[ValidationIssue]) -> Optional[float]:
        """
        Calculate processing time in hours with validation.
        
        Args:
            requested_time: Parsed requested timestamp
            ready_time: Parsed ready timestamp
            issues: List to append validation issues to
            
        Returns:
            Processing time in hours or None if calculation not possible
        """
        if not requested_time or not ready_time:
            return None
        
        if not requested_time.is_valid or not ready_time.is_valid:
            return None
        
        req_dt = requested_time.value
        ready_dt = ready_time.value
        
        if not req_dt or not ready_dt:
            return None
        
        # Remove timezone info for calculation
        if req_dt.tzinfo:
            req_dt = req_dt.replace(tzinfo=None)
        if ready_dt.tzinfo:
            ready_dt = ready_dt.replace(tzinfo=None)
        
        # Validate that ready_time >= requested_time
        if ready_dt < req_dt:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                issue_type="invalid_processing_time_range",
                message=f"Cannot calculate processing time: ready time ({ready_dt}) is before request time ({req_dt})",
                field_name="processing_time_calculation",
                suggested_fix="Fix chronological order of timestamps"
            ))
            return None
        
        # Calculate processing time in hours
        time_diff = ready_dt - req_dt
        processing_hours = time_diff.total_seconds() / 3600
        
        # Validate reasonable processing time
        if processing_hours < 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                issue_type="negative_processing_time",
                message=f"Negative processing time calculated: {processing_hours} hours",
                field_name="processing_time_calculation",
                suggested_fix="Fix chronological order of timestamps"
            ))
            return None
        
        if processing_hours > 24 * 365:  # More than 1 year
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                issue_type="excessive_processing_time",
                message=f"Unusually long processing time: {processing_hours:.1f} hours ({processing_hours/24:.1f} days)",
                field_name="processing_time_calculation",
                suggested_fix="Verify timestamp accuracy"
            ))
        
        return processing_hours
    
    def _get_violation_key(self, issues: List[ValidationIssue]) -> str:
        """
        Generate a key for tracking common violation patterns.
        
        Args:
            issues: List of validation issues
            
        Returns:
            String key representing the violation pattern
        """
        violation_types = [issue.issue_type for issue in issues 
                          if issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]]
        
        if not violation_types:
            return "no_violations"
        
        return "_".join(sorted(set(violation_types)))
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """
        Get validation statistics for monitoring and debugging.
        
        Returns:
            Dictionary with validation statistics
        """
        success_rate = 0.0
        if self.validation_stats['total_validations'] > 0:
            success_rate = (self.validation_stats['valid_timelines'] / 
                          self.validation_stats['total_validations']) * 100
        
        return {
            'total_validations': self.validation_stats['total_validations'],
            'valid_timelines': self.validation_stats['valid_timelines'],
            'invalid_timelines': self.validation_stats['invalid_timelines'],
            'success_rate_percentage': success_rate,
            'common_violations': self.validation_stats['common_violations'],
            'generated_at': datetime.now().isoformat()
        }


def create_timestamp_validation_service() -> TimestampValidationService:
    """
    Factory function to create a TimestampValidationService instance.
    
    Returns:
        Configured TimestampValidationService instance
    """
    return TimestampValidationService()


def create_timeline_validation_rules() -> TimelineValidationRules:
    """
    Factory function to create a TimelineValidationRules instance.
    
    Returns:
        Configured TimelineValidationRules instance
    """
    return TimelineValidationRules()


# Example usage and testing
if __name__ == '__main__':
    # Example usage of the timeline validation service
    timestamp_service = create_timestamp_validation_service()
    timeline_rules = create_timeline_validation_rules()
    
    # Test timestamp parsing
    test_timestamps = [
        "2024-01-15T10:30:00Z",
        "2024-01-15T12:45:00.123456Z",
        "2024-01-15 14:20:30",
        "20240115103000",
        "invalid_timestamp",
        None
    ]
    
    print("=== Timestamp Parsing Tests ===")
    for ts in test_timestamps:
        result = timestamp_service.parse_timestamp(ts, "test_field")
        print(f"Input: {ts}")
        print(f"  Valid: {result.is_valid}")
        print(f"  Value: {result.value}")
        print(f"  Format: {result.format_used}")
        print(f"  Confidence: {result.confidence_score:.2f}")
        print(f"  Issues: {len(result.issues)}")
        print()
    
    # Test timeline