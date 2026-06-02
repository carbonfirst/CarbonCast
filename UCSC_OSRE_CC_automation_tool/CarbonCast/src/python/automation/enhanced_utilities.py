#!/usr/bin/env python3
"""
Enhanced Utilities for Integrated Error Tracking and Smart Retry System

This module provides comprehensive utility functions for error classification,
retry eligibility determination, progress calculation, and health metric aggregation.

Key Features:
- Intelligent error classification and categorization
- Smart retry eligibility determination with machine learning insights
- Progress calculation and trending analysis
- Health metric aggregation and anomaly detection
- Dynamic configuration support
- Performance optimization utilities
"""

import re
import json
import logging
import sqlite3
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import math

try:
    from .enhanced_data_models import (
        ErrorType, ErrorSeverity, ErrorCategory, RetryStrategy, QueueStatus,
        ErrorTrackingRecord, RetryQueueItem, ProgressSnapshot, SystemHealthMetric,
        create_error_record, create_retry_item, create_progress_snapshot, create_health_metric
    )
except ImportError:
    # Handle direct execution
    from enhanced_data_models import (
        ErrorType, ErrorSeverity, ErrorCategory, RetryStrategy, QueueStatus,
        ErrorTrackingRecord, RetryQueueItem, ProgressSnapshot, SystemHealthMetric,
        create_error_record, create_retry_item, create_progress_snapshot, create_health_metric
    )


@dataclass
class ErrorClassificationResult:
    """Result of error classification analysis."""
    error_type: ErrorType
    error_category: ErrorCategory
    error_severity: ErrorSeverity
    is_retryable: bool
    retry_strategy: RetryStrategy
    confidence_score: float
    classification_reasons: List[str]
    suggested_actions: List[str]


@dataclass
class RetryEligibilityResult:
    """Result of retry eligibility analysis."""
    is_eligible: bool
    eligibility_score: float
    success_probability: float
    recommended_delay: int
    retry_strategy: RetryStrategy
    blocking_factors: List[str]
    enhancement_suggestions: List[str]


@dataclass
class ProgressTrendAnalysis:
    """Result of progress trend analysis."""
    current_trend: str  # improving, declining, stable, volatile
    trend_strength: float  # 0.0-1.0
    projected_completion: Optional[str]
    bottlenecks: List[str]
    performance_insights: Dict[str, Any]
    recommendations: List[str]


class ErrorClassifier:
    """
    Intelligent error classifier with pattern recognition and machine learning insights.
    
    This class provides comprehensive error classification based on error messages,
    context, patterns, and historical data.
    """
    
    # Error pattern definitions for classification
    ERROR_PATTERNS = {
        ErrorType.NETWORK_ERROR: [
            r'connection\s+(timeout|refused|reset|failed)',
            r'network\s+(unreachable|error|timeout)',
            r'socket\s+(timeout|error|closed)',
            r'dns\s+(resolution|lookup)\s+failed',
            r'http\s+[45]\d{2}',
            r'ssl\s+(handshake|certificate)\s+(failed|error)',
            r'proxy\s+(error|timeout)',
            r'host\s+(unreachable|not\s+found)'
        ],
        
        ErrorType.AUTHENTICATION_ERROR: [
            r'authentication\s+(failed|error|required)',
            r'invalid\s+(credentials|token|key)',
            r'unauthorized|401',
            r'login\s+(failed|required)',
            r'access\s+denied',
            r'permission\s+denied',
            r'forbidden|403'
        ],
        
        ErrorType.TIMEOUT_ERROR: [
            r'timeout|timed\s+out',
            r'request\s+timeout',
            r'connection\s+timeout',
            r'read\s+timeout',
            r'operation\s+timeout',
            r'deadline\s+exceeded'
        ],
        
        ErrorType.VALIDATION_ERROR: [
            r'validation\s+(failed|error)',
            r'invalid\s+(format|data|input)',
            r'malformed\s+(request|data)',
            r'schema\s+(validation|error)',
            r'bad\s+request|400',
            r'missing\s+(required|parameter)',
            r'constraint\s+(violation|error)'
        ],
        
        ErrorType.RESOURCE_ERROR: [
            r'resource\s+(not\s+found|unavailable)',
            r'out\s+of\s+(memory|disk|space)',
            r'quota\s+(exceeded|limit)',
            r'rate\s+limit\s+exceeded',
            r'service\s+unavailable|503',
            r'too\s+many\s+requests|429',
            r'capacity\s+(exceeded|limit)'
        ],
        
        ErrorType.SYSTEM_ERROR: [
            r'internal\s+(server\s+)?error|500',
            r'system\s+(error|failure)',
            r'service\s+(error|failure)',
            r'database\s+(error|connection)',
            r'file\s+(not\s+found|error)',
            r'configuration\s+error',
            r'dependency\s+(error|failure)'
        ]
    }
    
    # Severity indicators
    SEVERITY_INDICATORS = {
        ErrorSeverity.CRITICAL: [
            'critical', 'fatal', 'emergency', 'panic', 'abort',
            'corruption', r'data\s+loss', r'security\s+breach'
        ],
        ErrorSeverity.HIGH: [
            'error', 'failed', 'failure', 'exception', 'crash',
            'unavailable', 'timeout', 'denied'
        ],
        ErrorSeverity.MEDIUM: [
            'warning', 'warn', 'invalid', 'missing', 'unexpected'
        ],
        ErrorSeverity.LOW: [
            'info', 'notice', 'debug', 'trace', 'deprecated'
        ]
    }
    
    # Retry strategy recommendations
    RETRY_STRATEGIES = {
        ErrorType.NETWORK_ERROR: RetryStrategy.EXPONENTIAL_BACKOFF,
        ErrorType.TIMEOUT_ERROR: RetryStrategy.EXPONENTIAL_BACKOFF,
        ErrorType.RESOURCE_ERROR: RetryStrategy.LINEAR_BACKOFF,
        ErrorType.SYSTEM_ERROR: RetryStrategy.EXPONENTIAL_BACKOFF,
        ErrorType.AUTHENTICATION_ERROR: RetryStrategy.FIXED_DELAY,
        ErrorType.VALIDATION_ERROR: RetryStrategy.IMMEDIATE,  # Usually not retryable
        ErrorType.UNKNOWN_ERROR: RetryStrategy.EXPONENTIAL_BACKOFF
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the error classifier.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger('error_classifier')
        
        # Load custom patterns if provided
        if 'custom_patterns' in self.config:
            self._load_custom_patterns(self.config['custom_patterns'])
    
    def _load_custom_patterns(self, custom_patterns: Dict[str, List[str]]):
        """Load custom error patterns from configuration."""
        for error_type_str, patterns in custom_patterns.items():
            try:
                error_type = ErrorType(error_type_str)
                if error_type not in self.ERROR_PATTERNS:
                    self.ERROR_PATTERNS[error_type] = []
                self.ERROR_PATTERNS[error_type].extend(patterns)
            except ValueError:
                self.logger.warning(f"Unknown error type in custom patterns: {error_type_str}")
    
    def classify_error(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> ErrorClassificationResult:
        """
        Classify an error based on its message and context.
        
        Args:
            error_message: The error message to classify
            context: Optional context information
            
        Returns:
            ErrorClassificationResult with classification details
        """
        if not error_message:
            return ErrorClassificationResult(
                error_type=ErrorType.UNKNOWN_ERROR,
                error_category=ErrorCategory.APPLICATION,
                error_severity=ErrorSeverity.MEDIUM,
                is_retryable=False,
                retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                confidence_score=0.0,
                classification_reasons=["Empty error message"],
                suggested_actions=["Investigate error source"]
            )
        
        error_message_lower = error_message.lower()
        context = context or {}
        
        # Classify error type
        error_type, type_confidence, type_reasons = self._classify_error_type(error_message_lower)
        
        # Classify error severity
        error_severity, severity_confidence, severity_reasons = self._classify_error_severity(error_message_lower)
        
        # Determine error category
        error_category = self._determine_error_category(error_type, context)
        
        # Determine if retryable
        is_retryable, retry_reasons = self._determine_retryability(error_type, error_message_lower, context)
        
        # Get retry strategy
        retry_strategy = self.RETRY_STRATEGIES.get(error_type, RetryStrategy.EXPONENTIAL_BACKOFF)
        
        # Calculate overall confidence
        confidence_score = (type_confidence + severity_confidence) / 2
        
        # Generate suggested actions
        suggested_actions = self._generate_suggested_actions(error_type, error_severity, context)
        
        # Combine classification reasons
        classification_reasons = type_reasons + severity_reasons + retry_reasons
        
        return ErrorClassificationResult(
            error_type=error_type,
            error_category=error_category,
            error_severity=error_severity,
            is_retryable=is_retryable,
            retry_strategy=retry_strategy,
            confidence_score=confidence_score,
            classification_reasons=classification_reasons,
            suggested_actions=suggested_actions
        )
    
    def _classify_error_type(self, error_message: str) -> Tuple[ErrorType, float, List[str]]:
        """Classify the error type based on patterns."""
        type_scores = {}
        matching_patterns = {}
        
        for error_type, patterns in self.ERROR_PATTERNS.items():
            score = 0
            matches = []
            
            for pattern in patterns:
                if re.search(pattern, error_message, re.IGNORECASE):
                    score += 1
                    matches.append(pattern)
            
            if score > 0:
                type_scores[error_type] = score / len(patterns)
                matching_patterns[error_type] = matches
        
        if not type_scores:
            return ErrorType.UNKNOWN_ERROR, 0.0, ["No matching patterns found"]
        
        # Get the error type with highest score
        best_type = max(type_scores.keys(), key=lambda k: type_scores[k])
        confidence = type_scores[best_type]
        reasons = [f"Matched patterns: {', '.join(matching_patterns[best_type])}"]
        
        return best_type, confidence, reasons
    
    def _classify_error_severity(self, error_message: str) -> Tuple[ErrorSeverity, float, List[str]]:
        """Classify the error severity based on indicators."""
        severity_scores = {}
        
        for severity, indicators in self.SEVERITY_INDICATORS.items():
            score = 0
            for indicator in indicators:
                if re.search(indicator, error_message, re.IGNORECASE):
                    score += 1
            
            if score > 0:
                severity_scores[severity] = score / len(indicators)
        
        if not severity_scores:
            return ErrorSeverity.MEDIUM, 0.5, ["No severity indicators found, defaulting to medium"]
        
        # Get the severity with highest score
        best_severity = max(severity_scores.keys(), key=lambda k: severity_scores[k])
        confidence = severity_scores[best_severity]
        reasons = [f"Severity indicators matched for {best_severity.value}"]
        
        return best_severity, confidence, reasons
    
    def _determine_error_category(self, error_type: ErrorType, context: Dict[str, Any]) -> ErrorCategory:
        """Determine the error category based on type and context."""
        # Network and timeout errors are usually transient
        if error_type in [ErrorType.NETWORK_ERROR, ErrorType.TIMEOUT_ERROR]:
            return ErrorCategory.TRANSIENT
        
        # Resource errors can be transient or infrastructure-related
        if error_type == ErrorType.RESOURCE_ERROR:
            return ErrorCategory.INFRASTRUCTURE
        
        # Authentication errors are usually configuration-related
        if error_type == ErrorType.AUTHENTICATION_ERROR:
            return ErrorCategory.CONFIGURATION
        
        # Validation errors are usually permanent
        if error_type == ErrorType.VALIDATION_ERROR:
            return ErrorCategory.PERMANENT
        
        # System errors are usually recoverable
        if error_type == ErrorType.SYSTEM_ERROR:
            return ErrorCategory.RECOVERABLE
        
        # Default to application category
        return ErrorCategory.APPLICATION
    
    def _determine_retryability(self, error_type: ErrorType, error_message: str, 
                               context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Determine if an error is retryable."""
        reasons = []
        
        # Non-retryable patterns
        non_retryable_patterns = [
            r'invalid\s+(format|syntax|schema)',
            r'malformed\s+(request|data)',
            r'bad\s+request',
            r'not\s+found',
            r'forbidden',
            r'unauthorized',
            r'permission\s+denied'
        ]
        
        for pattern in non_retryable_patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                reasons.append(f"Non-retryable pattern matched: {pattern}")
                return False, reasons
        
        # Retryable error types
        retryable_types = [
            ErrorType.NETWORK_ERROR,
            ErrorType.TIMEOUT_ERROR,
            ErrorType.RESOURCE_ERROR,
            ErrorType.SYSTEM_ERROR
        ]
        
        if error_type in retryable_types:
            reasons.append(f"Error type {error_type.value} is generally retryable")
            return True, reasons
        
        # Check retry count from context
        retry_count = context.get('retry_count', 0)
        max_retries = context.get('max_retries', 3)
        
        if retry_count >= max_retries:
            reasons.append(f"Maximum retry count ({max_retries}) exceeded")
            return False, reasons
        
        # Default to not retryable for unknown cases
        reasons.append("Error type not in retryable categories")
        return False, reasons
    
    def _generate_suggested_actions(self, error_type: ErrorType, error_severity: ErrorSeverity,
                                   context: Dict[str, Any]) -> List[str]:
        """Generate suggested actions based on error classification."""
        actions = []
        
        # Type-specific actions
        if error_type == ErrorType.NETWORK_ERROR:
            actions.extend([
                "Check network connectivity",
                "Verify endpoint availability",
                "Consider implementing circuit breaker pattern"
            ])
        elif error_type == ErrorType.AUTHENTICATION_ERROR:
            actions.extend([
                "Verify credentials are valid",
                "Check token expiration",
                "Review authentication configuration"
            ])
        elif error_type == ErrorType.TIMEOUT_ERROR:
            actions.extend([
                "Increase timeout values",
                "Optimize request processing",
                "Implement request batching"
            ])
        elif error_type == ErrorType.RESOURCE_ERROR:
            actions.extend([
                "Check resource availability",
                "Implement rate limiting",
                "Scale resources if needed"
            ])
        elif error_type == ErrorType.VALIDATION_ERROR:
            actions.extend([
                "Review input data format",
                "Update validation rules",
                "Improve error handling"
            ])
        
        # Severity-specific actions
        if error_severity == ErrorSeverity.CRITICAL:
            actions.extend([
                "Escalate to on-call team",
                "Implement immediate mitigation",
                "Create incident report"
            ])
        elif error_severity == ErrorSeverity.HIGH:
            actions.extend([
                "Monitor error frequency",
                "Implement automated recovery",
                "Review system health"
            ])
        
        return actions


class RetryEligibilityAnalyzer:
    """
    Smart retry eligibility analyzer with machine learning insights.
    
    This class determines retry eligibility based on error patterns, historical success rates,
    system load, and intelligent prediction algorithms.
    """
    
    def __init__(self, db_path: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the retry eligibility analyzer.
        
        Args:
            db_path: Path to the database for historical analysis
            config: Optional configuration dictionary
        """
        self.db_path = db_path
        self.config = config or {}
        self.logger = logging.getLogger('retry_eligibility_analyzer')
        self.error_classifier = ErrorClassifier(config)
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def analyze_retry_eligibility(self, error_record: ErrorTrackingRecord,
                                 context: Optional[Dict[str, Any]] = None) -> RetryEligibilityResult:
        """
        Analyze retry eligibility for an error record.
        
        Args:
            error_record: Error record to analyze
            context: Optional context information
            
        Returns:
            RetryEligibilityResult with eligibility analysis
        """
        context = context or {}
        blocking_factors = []
        enhancement_suggestions = []
        
        # Basic eligibility checks
        if error_record.retry_count >= error_record.max_retries:
            blocking_factors.append(f"Maximum retries ({error_record.max_retries}) exceeded")
            return RetryEligibilityResult(
                is_eligible=False,
                eligibility_score=0.0,
                success_probability=0.0,
                recommended_delay=0,
                retry_strategy=error_record.retry_strategy,
                blocking_factors=blocking_factors,
                enhancement_suggestions=["Increase max retry limit if appropriate"]
            )
        
        if not error_record.is_retryable:
            blocking_factors.append("Error marked as non-retryable")
            return RetryEligibilityResult(
                is_eligible=False,
                eligibility_score=0.0,
                success_probability=0.0,
                recommended_delay=0,
                retry_strategy=error_record.retry_strategy,
                blocking_factors=blocking_factors,
                enhancement_suggestions=["Review error classification"]
            )
        
        # Calculate eligibility score based on multiple factors
        eligibility_factors = []
        
        # Factor 1: Error type retryability (0.0-1.0)
        type_score = self._calculate_type_retryability_score(error_record.error_type)
        eligibility_factors.append(('error_type', type_score, 0.3))
        
        # Factor 2: Historical success rate (0.0-1.0)
        historical_score = self._calculate_historical_success_rate(error_record)
        eligibility_factors.append(('historical_success', historical_score, 0.25))
        
        # Factor 3: System load factor (0.0-1.0)
        system_load_score = self._calculate_system_load_factor(context)
        eligibility_factors.append(('system_load', system_load_score, 0.2))
        
        # Factor 4: Time since last failure (0.0-1.0)
        time_factor_score = self._calculate_time_factor(error_record)
        eligibility_factors.append(('time_factor', time_factor_score, 0.15))
        
        # Factor 5: Resource availability (0.0-1.0)
        resource_score = self._calculate_resource_availability(error_record, context)
        eligibility_factors.append(('resource_availability', resource_score, 0.1))
        
        # Calculate weighted eligibility score
        eligibility_score = sum(score * weight for _, score, weight in eligibility_factors)
        
        # Calculate success probability using historical data and current conditions
        success_probability = self._calculate_success_probability(error_record, eligibility_factors)
        
        # Determine recommended delay
        recommended_delay = self._calculate_recommended_delay(error_record, eligibility_score)
        
        # Determine final eligibility
        min_eligibility_threshold = self.config.get('min_eligibility_threshold', 0.3)
        is_eligible = eligibility_score >= min_eligibility_threshold
        
        # Generate enhancement suggestions
        if eligibility_score < 0.5:
            enhancement_suggestions.extend([
                "Consider adjusting retry strategy",
                "Review error handling logic",
                "Monitor system resources"
            ])
        
        if success_probability < 0.3:
            enhancement_suggestions.append("Low success probability - investigate root cause")
        
        return RetryEligibilityResult(
            is_eligible=is_eligible,
            eligibility_score=eligibility_score,
            success_probability=success_probability,
            recommended_delay=recommended_delay,
            retry_strategy=error_record.retry_strategy,
            blocking_factors=blocking_factors,
            enhancement_suggestions=enhancement_suggestions
        )
    
    def _calculate_type_retryability_score(self, error_type: ErrorType) -> float:
        """Calculate retryability score based on error type."""
        type_scores = {
            ErrorType.NETWORK_ERROR: 0.8,
            ErrorType.TIMEOUT_ERROR: 0.9,
            ErrorType.RESOURCE_ERROR: 0.7,
            ErrorType.SYSTEM_ERROR: 0.6,
            ErrorType.AUTHENTICATION_ERROR: 0.3,
            ErrorType.VALIDATION_ERROR: 0.1,
            ErrorType.UNKNOWN_ERROR: 0.4
        }
        return type_scores.get(error_type, 0.4)
    
    def _calculate_historical_success_rate(self, error_record: ErrorTrackingRecord) -> float:
        """Calculate historical success rate for similar errors."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_retries,
                        COUNT(CASE WHEN resolution_status = 'resolved' THEN 1 END) as successful_retries
                    FROM error_tracking_enhanced 
                    WHERE error_type = ? AND region = ? AND variable_type = ?
                    AND created_at >= datetime('now', '-30 days')
                """, (error_record.error_type.value, error_record.region, error_record.variable_type))
                
                row = cursor.fetchone()
                if row and row['total_retries'] > 0:
                    return row['successful_retries'] / row['total_retries']
                
        except Exception as e:
            self.logger.warning(f"Error calculating historical success rate: {e}")
        
        # Default to moderate success rate if no historical data
        return 0.5
    
    def _calculate_system_load_factor(self, context: Dict[str, Any]) -> float:
        """Calculate system load factor affecting retry success."""
        # Check current queue size
        queue_size = context.get('current_queue_size', 0)
        max_queue_size = context.get('max_queue_size', 100)
        
        if max_queue_size > 0:
            queue_load = queue_size / max_queue_size
            # Higher load = lower score
            return max(0.0, 1.0 - queue_load)
        
        return 0.8  # Default to good system load
    
    def _calculate_time_factor(self, error_record: ErrorTrackingRecord) -> float:
        """Calculate time factor - more time since last failure = higher score."""
        try:
            last_occurrence = datetime.fromisoformat(error_record.last_occurrence)
            time_diff = datetime.now() - last_occurrence
            hours_since = time_diff.total_seconds() / 3600
            
            # Score increases with time, capped at 1.0
            return min(1.0, hours_since / 24)  # Full score after 24 hours
            
        except Exception:
            return 0.5  # Default moderate score
    
    def _calculate_resource_availability(self, error_record: ErrorTrackingRecord,
                                       context: Dict[str, Any]) -> float:
        """Calculate resource availability factor."""
        # Check if this is a resource-related error
        if error_record.error_type == ErrorType.RESOURCE_ERROR:
            # Lower score for resource errors
            return 0.4
        
        # Check system metrics if available
        cpu_usage = context.get('cpu_usage', 0.5)
        memory_usage = context.get('memory_usage', 0.5)
        
        # Higher resource usage = lower score
        resource_score = 1.0 - max(cpu_usage, memory_usage)
        return max(0.1, resource_score)
    
    def _calculate_success_probability(self, error_record: ErrorTrackingRecord,
                                     eligibility_factors: List[Tuple[str, float, float]]) -> float:
        """Calculate success probability using multiple factors."""
        # Base probability from historical data
        base_probability = self._calculate_historical_success_rate(error_record)
        
        # Adjust based on retry count (decreasing probability with more retries)
        retry_penalty = 0.1 * error_record.retry_count
        adjusted_probability = max(0.0, base_probability - retry_penalty)
        
        # Factor in current conditions
        condition_multiplier = 1.0
        for factor_name, score, _ in eligibility_factors:
            if factor_name in ['system_load', 'resource_availability']:
                condition_multiplier *= (0.5 + 0.5 * score)  # 0.5 to 1.0 range
        
        final_probability = min(1.0, adjusted_probability * condition_multiplier)
        return final_probability
    
    def _calculate_recommended_delay(self, error_record: ErrorTrackingRecord,
                                   eligibility_score: float) -> int:
        """Calculate recommended delay in seconds."""
        base_delay = 60  # 1 minute base delay
        
        # Exponential backoff based on retry count
        if error_record.retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = base_delay * (2 ** error_record.retry_count)
        elif error_record.retry_strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = base_delay * (error_record.retry_count + 1)
        elif error_record.retry_strategy == RetryStrategy.FIXED_DELAY:
            delay = base_delay
        else:
            delay = base_delay * (2 ** error_record.retry_count)
        
        # Adjust based on eligibility score (lower score = longer delay)
        if eligibility_score < 0.5:
            delay *= 2
        elif eligibility_score > 0.8:
            delay = int(delay * 0.7)
        
        # Cap at maximum delay
        max_delay = self.config.get('max_retry_delay', 3600)  # 1 hour
        return min(delay, max_delay)


class ProgressCalculator:
    """
    Progress calculation and trending analysis utility.
    
    This class provides comprehensive progress calculation, trend analysis,
    and performance insights for the automation system.
    """
    
    def __init__(self, db_path: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the progress calculator.
        
        Args:
            db_path: Path to the database
            config: Optional configuration dictionary
        """
        self.db_path = db_path
        self.config = config or {}
        self.logger = logging.getLogger('progress_calculator')
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def calculate_system_progress(self, time_window_hours: int = 24) -> ProgressSnapshot:
        """
        Calculate overall system progress.
        
        Args:
            time_window_hours: Time window for analysis in hours
            
        Returns:
            ProgressSnapshot with system progress data
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get basic metrics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                        COUNT(CASE WHEN status IN ('pending', 'queued') THEN 1 END) as pending,
                        COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing
                    FROM rda_requests
                    WHERE created_at >= datetime('now', '-{} hours')
                """.format(time_window_hours))
                
                metrics = cursor.fetchone()
                
                # Calculate rates
                total = metrics['total_requests'] or 1
                success_rate = (metrics['completed'] / total) * 100
                failure_rate = (metrics['failed'] / total) * 100
                
                # Get error distribution
                cursor.execute("""
                    SELECT error_type, COUNT(*) as count
                    FROM error_tracking_enhanced
                    WHERE created_at >= datetime('now', '-{} hours')
                    GROUP BY error_type
                """.format(time_window_hours))
                
                error_dist = {row['error_type']: row['count'] for row in cursor.fetchall()}
                
                # Calculate throughput
                throughput = metrics['completed'] / (time_window_hours or 1)
                
                snapshot = create_progress_snapshot(
                    snapshot_type="system",
                    snapshot_scope="global",
                    total_requests=metrics['total_requests'],
                    completed_requests=metrics['completed'],
                    failed_requests=metrics['failed'],
                    pending_requests=metrics['pending'],
                    retrying_requests=0,  # Would need retry queue data
                    success_rate=success_rate,
                    failure_rate=failure_rate,
                    throughput_per_hour=throughput,
                    error_distribution=error_dist
                )
                
                snapshot.calculate_rates()
                return snapshot
                
        except Exception as e:
            self.logger.error(f"Error calculating system progress: {e}")
            return create_progress_snapshot("system", "global")
    
    def analyze_progress_trend(self, scope: str, scope_id: Optional[str] = None,
                              days_back: int = 7) -> ProgressTrendAnalysis:
        """
        Analyze progress trends over time.
        
        Args:
            scope: Scope of analysis (system, regional, variable)
            scope_id: Specific identifier for scope
            days_back: Number of days to analyze
            
        Returns:
            ProgressTrendAnalysis with trend insights
        """
        try:
            # Get historical snapshots
            snapshots = self._get_historical_snapshots(scope, scope_id, days_back)
            
            if len(snapshots) < 2:
                return ProgressTrendAnalysis(
                    current_trend="insufficient_data",
                    trend_strength=0.0,
                    projected_completion=None,
                    bottlenecks=["Insufficient historical data"],
                    performance_insights={},
                    recommendations=["Collect more historical data"]
                )
            
            # Analyze trend in success rates
            success_rates = [s.success_rate for s in snapshots]
            trend_direction, trend_strength = self._calculate_trend(success_rates)
            
            # Identify bottlenecks
            bottlenecks = self._identify_bottlenecks(snapshots)
            
            # Generate performance insights
            performance_insights = self._generate_performance_insights(snapshots)
            
            # Generate recommendations
            recommendations = self._generate_trend_recommendations(trend_direction, bottlenecks, performance_insights)
            
            # Project completion time if trend is positive
            projected_completion = None
            if trend_direction == "improving" and snapshots:
                projected_completion = self._project_completion_time(snapshots)
            
            return ProgressTrendAnalysis(
                current_trend=trend_direction,
                trend_strength=trend_strength,
                projected_completion=projected_completion,
                bottlenecks=bottlenecks,
                performance_insights=performance_insights,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing progress trend: {e}")
            return ProgressTrendAnalysis(
                current_trend="error",
                trend_strength=0.0,
                projected_completion=None,
                bottlenecks=[f"Analysis error: {str(e)}"],
                performance_insights={},
                recommendations=["Review system logs"]
            )
    
    def _get_historical_snapshots(self, scope: str, scope_id: Optional[str], days_back: int) -> List[ProgressSnapshot]:
        """Get historical progress snapshots."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT * FROM progress_snapshots
                    WHERE snapshot_type = ? AND snapshot_timestamp >= datetime('now', '-{} days')
                """.format(days_back)
                
                params = [scope]
                
                if scope_id:
                    query += " AND scope_identifier = ?"
                    params.append(scope_id)
                
                query += " ORDER BY snapshot_timestamp ASC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                snapshots = []
                for row in rows:
                    snapshot = ProgressSnapshot.from_dict(dict(row))
                    snapshots.append(snapshot)
                
                return snapshots
                
        except Exception as e:
            self.logger.error(f"Error getting historical snapshots: {e}")
            return []
    
    def _calculate_trend(self, values: List[float]) -> Tuple[str, float]:
        """Calculate trend direction and strength."""
        if len(values) < 2:
            return "stable", 0.0
        
        # Calculate linear regression slope
        n = len(values)
        x_values = list(range(n))
        
        x_mean = sum(x_values) / n
        y_mean = sum(values) / n
        
        numerator = sum((x_values[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable", 0.0
        
        slope = numerator / denominator
        
        # Determine trend direction and strength
        if abs(slope) < 0.1:
            return "stable", abs(slope)
        elif slope > 0:
            return "improving", min(1.0, abs(slope))
        else:
            return "declining", min(1.0, abs(slope))
    
    def _identify_bottlenecks(self, snapshots: List[ProgressSnapshot]) -> List[str]:
        """Identify system bottlenecks from snapshots."""
        bottlenecks = []
        
        if not snapshots:
            return bottlenecks
        
        latest = snapshots[-1]
        
        # Check failure rate
        if latest.failure_rate > 20:
            bottlenecks.append(f"High failure rate: {latest.failure_rate:.1f}%")
        
        # Check throughput
        if latest.throughput_per_hour < 10:
            bottlenecks.append(f"Low throughput: {latest.throughput_per_hour:.1f} requests/hour")
        
        # Check pending requests
        if latest.pending_requests > latest.completed_requests:
            bottlenecks.append("High number of pending requests")
        
        return bottlenecks
    
    def _generate_performance_insights(self, snapshots: List[ProgressSnapshot]) -> Dict[str, Any]:
        """Generate performance insights from snapshots."""
        if not snapshots:
            return {}
        
        # Calculate averages
        avg_success_rate = statistics.mean(s.success_rate for s in snapshots)
        avg_throughput = statistics.mean(s.throughput_per_hour for s in snapshots)
        
        # Calculate variability
        success_rate_std = statistics.stdev(s.success_rate for s in snapshots) if len(snapshots) > 1 else 0
        throughput_std = statistics.stdev(s.throughput_per_hour for s in snapshots) if len(snapshots) > 1 else 0
        
        return {
            'average_success_rate': avg_success_rate,
            'average_throughput': avg_throughput,
            'success_rate_variability': success_rate_std,
            'throughput_variability': throughput_std,
            'total_snapshots_analyzed': len(snapshots)
        }
    
    def _generate_trend_recommendations(self, trend_direction: str, bottlenecks: List[str],
                                      performance_insights: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on trend analysis."""
        recommendations = []
        
        if trend_direction == "declining":
            recommendations.extend([
                "Investigate root causes of declining performance",
                "Review recent system changes",
                "Consider scaling resources"
            ])
        elif trend_direction == "stable":
            recommendations.extend([
                "Monitor for potential improvements",
                "Consider optimization opportunities"
            ])
        elif trend_direction == "improving":
            recommendations.extend([
                "Continue current optimization efforts",
                "Document successful practices"
            ])
        
        # Bottleneck-specific recommendations
        for bottleneck in bottlenecks:
            if "failure rate" in bottleneck.lower():
                recommendations.append("Focus on error reduction strategies")
            elif "throughput" in bottleneck.lower():
                recommendations.append("Optimize processing pipeline")
            elif "pending" in bottleneck.lower():
                recommendations.append("Increase processing capacity")
        
        return recommendations
    
    def _project_completion_time(self, snapshots: List[ProgressSnapshot]) -> Optional[str]:
        """Project completion time based on current trends."""
        if len(snapshots) < 2:
            return None
        
        try:
            latest = snapshots[-1]
            if latest.throughput_per_hour <= 0 or latest.pending_requests <= 0:
                return None
            
            hours_to_completion = latest.pending_requests / latest.throughput_per_hour
            completion_time = datetime.now() + timedelta(hours=hours_to_completion)
            
            return completion_time.isoformat()
            
        except Exception:
            return None


class HealthMetricAggregator:
    """
    Health metric aggregation and anomaly detection utility.
    
    This class provides comprehensive health metric collection, aggregation,
    and anomaly detection for system monitoring.
    """
    
    def __init__(self, db_path: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the health metric aggregator.
        
        Args:
            db_path: Path to the database
            config: Optional configuration dictionary
        """
        self.db_path = db_path
        self.config = config or {}
        self.logger = logging.getLogger('health_metric_aggregator')
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def collect_system_metrics(self) -> List[SystemHealthMetric]:
        """
        Collect current system health metrics.
        
        Returns:
            List of SystemHealthMetric objects
        """
        metrics = []
        
        try:
            # Database metrics
            db_metrics = self._collect_database_metrics()
            metrics.extend(db_metrics)
            
            # Queue metrics
            queue_metrics = self._collect_queue_metrics()
            metrics.extend(queue_metrics)
            
            # Error metrics
            error_metrics = self._collect_error_metrics()
            metrics.extend(error_metrics)
            
            # Performance metrics
            performance_metrics = self._collect_performance_metrics()
            metrics.extend(performance_metrics)
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
        
        return metrics
    
    def _collect_database_metrics(self) -> List[SystemHealthMetric]:
        """Collect database-related health metrics."""
        metrics = []
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Database size
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                db_size = cursor.fetchone()['size']
                
                metrics.append(create_health_metric(
                    metric_category="database",
                    metric_name="database_size_bytes",
                    metric_value=float(db_size),
                    metric_unit="bytes",
                    component_name="sqlite_database"
                ))
                
                # Table record counts
                tables = ['rda_requests', 'error_tracking_enhanced', 'retry_queue']
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                        count = cursor.fetchone()['count']
                        
                        metrics.append(create_health_metric(
                            metric_category="database",
                            metric_name=f"{table}_record_count",
                            metric_value=float(count),
                            metric_unit="records",
                            component_name=table
                        ))
                    except sqlite3.Error:
                        # Table might not exist yet
                        continue
                        
        except Exception as e:
            self.logger.error(f"Error collecting database metrics: {e}")
        
        return metrics
    
    def _collect_queue_metrics(self) -> List[SystemHealthMetric]:
        """Collect retry queue health metrics."""
        metrics = []
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if retry_queue table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='retry_queue'
                """)
                
                if not cursor.fetchone():
                    return metrics
                
                # Queue size by status
                cursor.execute("""
                    SELECT queue_status, COUNT(*) as count
                    FROM retry_queue
                    GROUP BY queue_status
                """)
                
                for row in cursor.fetchall():
                    metrics.append(create_health_metric(
                        metric_category="queue",
                        metric_name=f"retry_queue_{row['queue_status']}_count",
                        metric_value=float(row['count']),
                        metric_unit="items",
                        component_name="retry_queue"
                    ))
                
                # Average queue wait time
                cursor.execute("""
                    SELECT AVG(
                        (julianday('now') - julianday(created_at)) * 24 * 60
                    ) as avg_wait_minutes
                    FROM retry_queue
                    WHERE queue_status = 'pending'
                """)
                
                avg_wait = cursor.fetchone()['avg_wait_minutes']
                if avg_wait:
                    metrics.append(create_health_metric(
                        metric_category="queue",
                        metric_name="average_queue_wait_time",
                        metric_value=float(avg_wait),
                        metric_unit="minutes",
                        component_name="retry_queue"
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error collecting queue metrics: {e}")
        
        return metrics
    
    def _collect_error_metrics(self) -> List[SystemHealthMetric]:
        """Collect error-related health metrics."""
        metrics = []
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if error_tracking_enhanced table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='error_tracking_enhanced'
                """)
                
                if not cursor.fetchone():
                    return metrics
                
                # Error rate (last 24 hours)
                cursor.execute("""
                    SELECT COUNT(*) as error_count
                    FROM error_tracking_enhanced
                    WHERE created_at >= datetime('now', '-24 hours')
                """)
                
                error_count = cursor.fetchone()['error_count']
                metrics.append(create_health_metric(
                    metric_category="errors",
                    metric_name="error_rate_24h",
                    metric_value=float(error_count),
                    metric_unit="errors",
                    component_name="error_tracking"
                ))
                
                # Error distribution by type
                cursor.execute("""
                    SELECT error_type, COUNT(*) as count
                    FROM error_tracking_enhanced
                    WHERE created_at >= datetime('now', '-24 hours')
                    GROUP BY error_type
                """)
                
                for row in cursor.fetchall():
                    metrics.append(create_health_metric(
                        metric_category="errors",
                        metric_name=f"error_type_{row['error_type']}_count",
                        metric_value=float(row['count']),
                        metric_unit="errors",
                        component_name="error_tracking"
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error collecting error metrics: {e}")
        
        return metrics
    
    def _collect_performance_metrics(self) -> List[SystemHealthMetric]:
        """Collect performance-related health metrics."""
        metrics = []
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Request completion rate (last 24 hours)
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_requests
                    FROM rda_requests
                    WHERE created_at >= datetime('now', '-24 hours')
                """)
                
                row = cursor.fetchone()
                if row['total_requests'] > 0:
                    completion_rate = (row['completed_requests'] / row['total_requests']) * 100
                    metrics.append(create_health_metric(
                        metric_category="performance",
                        metric_name="completion_rate_24h",
                        metric_value=completion_rate,
                        metric_unit="percentage",
                        component_name="request_processing"
                    ))
                
                # Throughput (requests per hour)
                throughput = row['completed_requests'] / 24.0 if row['completed_requests'] else 0
                metrics.append(create_health_metric(
                    metric_category="performance",
                    metric_name="throughput_requests_per_hour",
                    metric_value=throughput,
                    metric_unit="requests/hour",
                    component_name="request_processing"
                ))
                
        except Exception as e:
            self.logger.error(f"Error collecting performance metrics: {e}")
        
        return metrics
    
    def detect_anomalies(self, metrics: List[SystemHealthMetric]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in health metrics.
        
        Args:
            metrics: List of health metrics to analyze
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        for metric in metrics:
            # Check threshold violations
            if metric.check_thresholds() != metric.metric_status:
                anomalies.append({
                    'type': 'threshold_violation',
                    'metric_name': metric.metric_name,
                    'metric_value': metric.metric_value,
                    'threshold_min': metric.metric_threshold_min,
                    'threshold_max': metric.metric_threshold_max,
                    'severity': metric.metric_status.value,
                    'timestamp': metric.metric_timestamp
                })
            
            # Check for unusual values based on metric type
            if self._is_anomalous_value(metric):
                anomalies.append({
                    'type': 'unusual_value',
                    'metric_name': metric.metric_name,
                    'metric_value': metric.metric_value,
                    'expected_range': self._get_expected_range(metric),
                    'severity': 'warning',
                    'timestamp': metric.metric_timestamp
                })
        
        return anomalies
    
    def _is_anomalous_value(self, metric: SystemHealthMetric) -> bool:
        """Check if a metric value is anomalous."""
        # Simple anomaly detection based on metric type
        if metric.metric_category == "errors" and metric.metric_value > 100:
            return True
        elif metric.metric_category == "performance" and "completion_rate" in metric.metric_name:
            return metric.metric_value < 50  # Less than 50% completion rate
        elif metric.metric_category == "queue" and "count" in metric.metric_name:
            return metric.metric_value > 1000  # More than 1000 items in queue
        
        return False
    
    def _get_expected_range(self, metric: SystemHealthMetric) -> Dict[str, float]:
        """Get expected range for a metric."""
        # Default expected ranges based on metric type
        ranges = {
            "completion_rate": {"min": 70.0, "max": 100.0},
            "error_rate": {"min": 0.0, "max": 50.0},
            "queue_count": {"min": 0.0, "max": 500.0},
            "throughput": {"min": 1.0, "max": 1000.0}
        }
        
        for key, range_dict in ranges.items():
            if key in metric.metric_name:
                return range_dict
        
        return {"min": 0.0, "max": float('inf')}


# Factory functions for creating utility instances

def create_error_classifier(config: Optional[Dict[str, Any]] = None) -> ErrorClassifier:
    """
    Factory function to create an ErrorClassifier.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured ErrorClassifier instance
    """
    return ErrorClassifier(config)


def create_retry_eligibility_analyzer(db_path: str, config: Optional[Dict[str, Any]] = None) -> RetryEligibilityAnalyzer:
    """
    Factory function to create a RetryEligibilityAnalyzer.
    
    Args:
        db_path: Path to the database
        config: Optional configuration dictionary
        
    Returns:
        Configured RetryEligibilityAnalyzer instance
    """
    return RetryEligibilityAnalyzer(db_path, config)


def create_progress_calculator(db_path: str, config: Optional[Dict[str, Any]] = None) -> ProgressCalculator:
    """
    Factory function to create a ProgressCalculator.
    
    Args:
        db_path: Path to the database
        config: Optional configuration dictionary
        
    Returns:
        Configured ProgressCalculator instance
    """
    return ProgressCalculator(db_path, config)


def create_health_metric_aggregator(db_path: str, config: Optional[Dict[str, Any]] = None) -> HealthMetricAggregator:
    """
    Factory function to create a HealthMetricAggregator.
    
    Args:
        db_path: Path to the database
        config: Optional configuration dictionary
        
    Returns:
        Configured HealthMetricAggregator instance
    """
    return HealthMetricAggregator(db_path, config)


if __name__ == "__main__":
    # Example usage and testing
    print("=== Enhanced Utilities Testing ===")
    
    # Test ErrorClassifier
    print("\n1. Testing ErrorClassifier")
    classifier = create_error_classifier()
    
    test_errors = [
        "Connection timeout after 30 seconds",
        "Authentication failed: invalid credentials",
        "Invalid data format in request",
        "Internal server error: database connection failed"
    ]
    
    for error_msg in test_errors:
        result = classifier.classify_error(error_msg)
        print(f"Error: {error_msg}")
        print(f"  Type: {result.error_type.value}")
        print(f"  Severity: {result.error_severity.value}")
        print(f"  Retryable: {result.is_retryable}")
        print(f"  Confidence: {result.confidence_score:.2f}")
        print()
    
    # Test HealthMetricAggregator
    print("2. Testing HealthMetricAggregator")
    aggregator = create_health_metric_aggregator("./data/automation_state.db")
    
    metrics = aggregator.collect_system_metrics()
    print(f"Collected {len(metrics)} system metrics")
    
    for metric in metrics[:3]:  # Show first 3 metrics
        print(f"  {metric.metric_name}: {metric.metric_value} {metric.metric_unit or ''}")
    
    # Test anomaly detection
    anomalies = aggregator.detect_anomalies(metrics)
    print(f"Detected {len(anomalies)} anomalies")
    
    print("\n=== All utility tests completed ===")