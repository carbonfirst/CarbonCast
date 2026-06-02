#!/usr/bin/env python3
"""
Comprehensive Error Handler for RDA API Management

This module implements advanced error handling specifically designed for RDA API
interactions, including rate limit error handling, graceful degradation, intelligent
retry mechanisms, and error pattern recognition with adaptive responses.

Key Features:
- Specific handling for RDA rate limit errors and "too many requests" responses
- Graceful degradation when hitting API limits
- Intelligent retry mechanisms with backoff strategies
- Error pattern recognition and adaptive response
- Integration with rate limiting and circuit breaker systems
- Comprehensive error classification and logging
"""

import time
import logging
import traceback
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import json
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    FATAL = "fatal"


class ErrorCategory(Enum):
    """Error categories for classification."""
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    VALIDATION_ERROR = "validation_error"
    QUOTA_ERROR = "quota_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    UNKNOWN = "unknown"


class RetryStrategy(Enum):
    """Retry strategies for different error types."""
    NO_RETRY = "no_retry"
    IMMEDIATE = "immediate"
    LINEAR_BACKOFF = "linear_backoff"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    ADAPTIVE_BACKOFF = "adaptive_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"


class ErrorAction(Enum):
    """Actions to take when errors occur."""
    RETRY = "retry"
    ABORT = "abort"
    DEGRADE = "degrade"
    ESCALATE = "escalate"
    WAIT_AND_RETRY = "wait_and_retry"
    CIRCUIT_BREAK = "circuit_break"
    FALLBACK = "fallback"


@dataclass
class ErrorPattern:
    """Pattern for error recognition and handling."""
    name: str
    category: ErrorCategory
    severity: ErrorSeverity
    status_codes: List[int] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)
    exception_types: List[str] = field(default_factory=list)
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 300.0
    action: ErrorAction = ErrorAction.RETRY
    degradation_level: Optional[str] = None


@dataclass
class ErrorOccurrence:
    """Record of an error occurrence."""
    timestamp: datetime
    error_pattern: ErrorPattern
    original_exception: Optional[Exception]
    status_code: Optional[int]
    error_message: str
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    resolution_time: Optional[datetime] = None
    resolved: bool = False


@dataclass
class ErrorHandlingConfig:
    """Configuration for error handling."""
    # Retry settings
    default_max_retries: int = 3
    default_base_delay: float = 1.0
    default_max_delay: float = 300.0
    retry_jitter_enabled: bool = True
    
    # Rate limit specific
    rate_limit_base_delay: float = 60.0
    rate_limit_max_delay: float = 1800.0
    rate_limit_backoff_multiplier: float = 1.5
    
    # Circuit breaker integration
    circuit_breaker_enabled: bool = True
    error_threshold_for_circuit: int = 5
    
    # Monitoring and alerting
    error_tracking_window_minutes: int = 60
    alert_threshold_errors_per_minute: int = 10
    pattern_recognition_enabled: bool = True
    
    # Degradation settings
    graceful_degradation_enabled: bool = True
    degradation_timeout_seconds: int = 300


class ErrorHandler:
    """
    Comprehensive error handler for RDA API interactions.
    
    This class provides intelligent error handling with pattern recognition,
    adaptive retry strategies, and integration with rate limiting systems.
    """
    
    def __init__(self, config: Optional[ErrorHandlingConfig] = None):
        """
        Initialize the error handler.
        
        Args:
            config: Error handling configuration
        """
        self.config = config or ErrorHandlingConfig()
        self.logger = self._setup_logging()
        
        # Error tracking
        self.error_history: deque = deque(maxlen=1000)
        self.error_patterns = self._initialize_error_patterns()
        self.pattern_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'last_occurrence': None,
            'success_rate': 0.0,
            'avg_resolution_time': 0.0
        })
        
        # Threading
        self.lock = threading.RLock()
        
        # Callbacks and integrations
        self.error_callbacks: List[Callable] = []
        self.rate_limiter = None
        self.circuit_breaker = None
        
        # Degradation state
        self.degradation_active = False
        self.degradation_level = None
        self.degradation_start_time: Optional[datetime] = None
        
        self.logger.info("ErrorHandler initialized with comprehensive error handling")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the error handler."""
        logger = logging.getLogger('rda_automation.error_handler')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    def _initialize_error_patterns(self) -> List[ErrorPattern]:
        """Initialize predefined error patterns for RDA API."""
        patterns = [
            # Rate limiting errors
            ErrorPattern(
                name="rda_rate_limit_429",
                category=ErrorCategory.RATE_LIMIT,
                severity=ErrorSeverity.HIGH,
                status_codes=[429],
                error_messages=["too many requests", "rate limit exceeded", "quota exceeded"],
                retry_strategy=RetryStrategy.ADAPTIVE_BACKOFF,
                max_retries=5,
                base_delay=60.0,
                max_delay=1800.0,
                action=ErrorAction.WAIT_AND_RETRY
            ),
            
            # Server unavailable
            ErrorPattern(
                name="rda_service_unavailable",
                category=ErrorCategory.SERVICE_UNAVAILABLE,
                severity=ErrorSeverity.CRITICAL,
                status_codes=[503, 502, 504],
                error_messages=["service unavailable", "bad gateway", "gateway timeout"],
                retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=3,
                base_delay=30.0,
                max_delay=600.0,
                action=ErrorAction.CIRCUIT_BREAK
            ),
            
            # Authentication errors
            ErrorPattern(
                name="rda_authentication_error",
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.CRITICAL,
                status_codes=[401],
                error_messages=["unauthorized", "invalid token", "authentication failed"],
                retry_strategy=RetryStrategy.NO_RETRY,
                action=ErrorAction.ESCALATE
            ),
            
            # Authorization errors
            ErrorPattern(
                name="rda_authorization_error",
                category=ErrorCategory.AUTHORIZATION,
                severity=ErrorSeverity.HIGH,
                status_codes=[403],
                error_messages=["forbidden", "access denied", "insufficient permissions"],
                retry_strategy=RetryStrategy.NO_RETRY,
                action=ErrorAction.ESCALATE
            ),
            
            # Client errors
            ErrorPattern(
                name="rda_client_error",
                category=ErrorCategory.CLIENT_ERROR,
                severity=ErrorSeverity.MEDIUM,
                status_codes=[400, 404, 422],
                error_messages=["bad request", "not found", "unprocessable entity"],
                retry_strategy=RetryStrategy.NO_RETRY,
                action=ErrorAction.ABORT
            ),
            
            # Network errors
            ErrorPattern(
                name="network_connection_error",
                category=ErrorCategory.NETWORK_ERROR,
                severity=ErrorSeverity.HIGH,
                exception_types=["ConnectionError", "ConnectTimeout"],
                retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=3,
                base_delay=5.0,
                max_delay=60.0,
                action=ErrorAction.RETRY
            ),
            
            # Timeout errors
            ErrorPattern(
                name="request_timeout",
                category=ErrorCategory.TIMEOUT_ERROR,
                severity=ErrorSeverity.MEDIUM,
                exception_types=["Timeout", "ReadTimeout"],
                retry_strategy=RetryStrategy.LINEAR_BACKOFF,
                max_retries=2,
                base_delay=10.0,
                max_delay=120.0,
                action=ErrorAction.RETRY
            ),
            
            # Quota errors
            ErrorPattern(
                name="rda_quota_exceeded",
                category=ErrorCategory.QUOTA_ERROR,
                severity=ErrorSeverity.CRITICAL,
                status_codes=[429],
                error_messages=["quota exceeded", "monthly limit", "daily limit"],
                retry_strategy=RetryStrategy.NO_RETRY,
                action=ErrorAction.DEGRADE,
                degradation_level="quota_limited"
            )
        ]
        
        return patterns
    
    def set_integrations(self, rate_limiter=None, circuit_breaker=None):
        """
        Set integration components.
        
        Args:
            rate_limiter: RateLimiter instance
            circuit_breaker: Circuit breaker instance
        """
        self.rate_limiter = rate_limiter
        self.circuit_breaker = circuit_breaker
        
        self.logger.info("✅ Error handler integrations configured")
    
    def handle_error(self, exception: Exception, context: Dict[str, Any] = None) -> Tuple[ErrorAction, Dict[str, Any]]:
        """
        Handle an error and determine the appropriate action.
        
        Args:
            exception: The exception that occurred
            context: Additional context about the error
            
        Returns:
            Tuple of (action, action_parameters)
        """
        context = context or {}
        
        try:
            # Classify the error
            error_pattern = self._classify_error(exception, context)
            
            # Record the error occurrence
            error_occurrence = ErrorOccurrence(
                timestamp=datetime.now(),
                error_pattern=error_pattern,
                original_exception=exception,
                status_code=context.get('status_code'),
                error_message=str(exception),
                context=context
            )
            
            with self.lock:
                self.error_history.append(error_occurrence)
                self._update_pattern_stats(error_pattern.name, error_occurrence)
            
            # Determine action based on pattern and current state
            action, action_params = self._determine_action(error_pattern, error_occurrence, context)
            
            # Log the error and action
            self._log_error_and_action(error_occurrence, action, action_params)
            
            # Notify callbacks
            self._notify_error_callbacks(error_occurrence, action, action_params)
            
            # Update integrations
            self._update_integrations(error_pattern, error_occurrence)
            
            return action, action_params
            
        except Exception as e:
            self.logger.error(f"❌ Error in error handler: {e}")
            return ErrorAction.ABORT, {"reason": "error_handler_failure"}
    
    def _classify_error(self, exception: Exception, context: Dict[str, Any]) -> ErrorPattern:
        """Classify an error based on patterns."""
        status_code = context.get('status_code')
        error_message = str(exception).lower()
        exception_type = type(exception).__name__
        
        # Try to match against known patterns
        for pattern in self.error_patterns:
            # Check status code match
            if status_code and status_code in pattern.status_codes:
                # Additional message validation for rate limits
                if pattern.category == ErrorCategory.RATE_LIMIT:
                    if any(msg in error_message for msg in pattern.error_messages):
                        return pattern
                elif pattern.category == ErrorCategory.QUOTA_ERROR:
                    if any(msg in error_message for msg in pattern.error_messages):
                        return pattern
                else:
                    return pattern
            
            # Check error message match
            if any(msg in error_message for msg in pattern.error_messages):
                return pattern
            
            # Check exception type match
            if exception_type in pattern.exception_types:
                return pattern
        
        # Default pattern for unknown errors
        return ErrorPattern(
            name="unknown_error",
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            max_retries=1,
            action=ErrorAction.RETRY
        )
    
    def _determine_action(self, pattern: ErrorPattern, occurrence: ErrorOccurrence, 
                         context: Dict[str, Any]) -> Tuple[ErrorAction, Dict[str, Any]]:
        """Determine the appropriate action for an error."""
        action_params = {}
        
        # Check if we're in degradation mode
        if self.degradation_active and pattern.category != ErrorCategory.RATE_LIMIT:
            return ErrorAction.DEGRADE, {"level": self.degradation_level}
        
        # Handle rate limiting specifically
        if pattern.category == ErrorCategory.RATE_LIMIT:
            return self._handle_rate_limit_error(pattern, occurrence, context)
        
        # Handle quota errors
        if pattern.category == ErrorCategory.QUOTA_ERROR:
            return self._handle_quota_error(pattern, occurrence, context)
        
        # Handle authentication/authorization errors
        if pattern.category in [ErrorCategory.AUTHENTICATION, ErrorCategory.AUTHORIZATION]:
            return ErrorAction.ESCALATE, {
                "reason": f"{pattern.category.value}_error",
                "requires_manual_intervention": True
            }
        
        # Handle client errors (no retry)
        if pattern.category == ErrorCategory.CLIENT_ERROR:
            return ErrorAction.ABORT, {"reason": "client_error_no_retry"}
        
        # Handle server errors with circuit breaker consideration
        if pattern.category in [ErrorCategory.SERVER_ERROR, ErrorCategory.SERVICE_UNAVAILABLE]:
            if self._should_trigger_circuit_breaker(pattern):
                return ErrorAction.CIRCUIT_BREAK, {"pattern": pattern.name}
            else:
                return self._calculate_retry_action(pattern, occurrence, context)
        
        # Default retry logic
        return self._calculate_retry_action(pattern, occurrence, context)
    
    def _handle_rate_limit_error(self, pattern: ErrorPattern, occurrence: ErrorOccurrence, 
                                context: Dict[str, Any]) -> Tuple[ErrorAction, Dict[str, Any]]:
        """Handle rate limiting errors specifically."""
        # Extract retry-after header if available
        retry_after = context.get('retry_after')
        if retry_after:
            try:
                wait_time = float(retry_after)
            except (ValueError, TypeError):
                wait_time = self.config.rate_limit_base_delay
        else:
            # Calculate adaptive backoff
            wait_time = self._calculate_rate_limit_backoff(occurrence.retry_count)
        
        # Update rate limiter if available
        if self.rate_limiter:
            self.rate_limiter.record_request_result(
                success=False,
                response_time=context.get('response_time', 0),
                status_code=occurrence.status_code,
                error_type='rate_limit'
            )
        
        return ErrorAction.WAIT_AND_RETRY, {
            "wait_time": wait_time,
            "reason": "rate_limit_exceeded",
            "adaptive": True
        }
    
    def _handle_quota_error(self, pattern: ErrorPattern, occurrence: ErrorOccurrence, 
                           context: Dict[str, Any]) -> Tuple[ErrorAction, Dict[str, Any]]:
        """Handle quota exceeded errors."""
        # Activate degradation mode
        self._activate_degradation(pattern.degradation_level or "quota_limited")
        
        return ErrorAction.DEGRADE, {
            "level": self.degradation_level,
            "reason": "quota_exceeded",
            "estimated_recovery_time": self._estimate_quota_recovery_time(context)
        }
    
    def _calculate_retry_action(self, pattern: ErrorPattern, occurrence: ErrorOccurrence, 
                               context: Dict[str, Any]) -> Tuple[ErrorAction, Dict[str, Any]]:
        """Calculate retry action based on pattern and history."""
        retry_count = context.get('retry_count', 0)
        
        if retry_count >= pattern.max_retries:
            return ErrorAction.ABORT, {"reason": "max_retries_exceeded"}
        
        # Calculate delay based on strategy
        delay = self._calculate_retry_delay(pattern, retry_count)
        
        return ErrorAction.RETRY, {
            "delay": delay,
            "retry_count": retry_count + 1,
            "strategy": pattern.retry_strategy.value
        }
    
    def _calculate_retry_delay(self, pattern: ErrorPattern, retry_count: int) -> float:
        """Calculate retry delay based on strategy."""
        if pattern.retry_strategy == RetryStrategy.NO_RETRY:
            return 0.0
        elif pattern.retry_strategy == RetryStrategy.IMMEDIATE:
            return 0.0
        elif pattern.retry_strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = pattern.base_delay * (retry_count + 1)
        elif pattern.retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = pattern.base_delay * (2 ** retry_count)
        elif pattern.retry_strategy == RetryStrategy.ADAPTIVE_BACKOFF:
            # Adaptive based on recent success rate
            success_rate = self._get_pattern_success_rate(pattern.name)
            multiplier = 2.0 if success_rate < 0.5 else 1.5
            delay = pattern.base_delay * (multiplier ** retry_count)
        else:
            delay = pattern.base_delay
        
        # Apply jitter if enabled
        if self.config.retry_jitter_enabled:
            import random
            jitter = delay * 0.1 * random.random()
            delay += jitter
        
        return min(delay, pattern.max_delay)
    
    def _calculate_rate_limit_backoff(self, retry_count: int) -> float:
        """Calculate backoff for rate limit errors."""
        base_delay = self.config.rate_limit_base_delay
        multiplier = self.config.rate_limit_backoff_multiplier
        
        delay = base_delay * (multiplier ** retry_count)
        return min(delay, self.config.rate_limit_max_delay)
    
    def _should_trigger_circuit_breaker(self, pattern: ErrorPattern) -> bool:
        """Check if circuit breaker should be triggered."""
        if not self.config.circuit_breaker_enabled:
            return False
        
        # Count recent errors of this pattern
        now = datetime.now()
        window_start = now - timedelta(minutes=self.config.error_tracking_window_minutes)
        
        recent_errors = [
            e for e in self.error_history
            if (e.timestamp > window_start and 
                e.error_pattern.name == pattern.name and
                not e.resolved)
        ]
        
        return len(recent_errors) >= self.config.error_threshold_for_circuit
    
    def _activate_degradation(self, level: str):
        """Activate graceful degradation mode."""
        if not self.config.graceful_degradation_enabled:
            return
        
        with self.lock:
            self.degradation_active = True
            self.degradation_level = level
            self.degradation_start_time = datetime.now()
        
        self.logger.warning(f"🔻 Graceful degradation activated: {level}")
    
    def _deactivate_degradation(self):
        """Deactivate graceful degradation mode."""
        with self.lock:
            if self.degradation_active:
                duration = (datetime.now() - self.degradation_start_time).total_seconds()
                self.logger.info(f"🔺 Graceful degradation deactivated after {duration:.1f}s")
                
                self.degradation_active = False
                self.degradation_level = None
                self.degradation_start_time = None
    
    def _estimate_quota_recovery_time(self, context: Dict[str, Any]) -> Optional[datetime]:
        """Estimate when quota might be recovered."""
        # This would typically parse quota reset headers or use known reset times
        reset_header = context.get('quota_reset')
        if reset_header:
            try:
                # Assume Unix timestamp
                return datetime.fromtimestamp(float(reset_header))
            except (ValueError, TypeError):
                pass
        
        # Default to next hour boundary
        now = datetime.now()
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    def _update_pattern_stats(self, pattern_name: str, occurrence: ErrorOccurrence):
        """Update statistics for error patterns."""
        stats = self.pattern_stats[pattern_name]
        stats['count'] += 1
        stats['last_occurrence'] = occurrence.timestamp
        
        # Calculate success rate (simplified)
        recent_occurrences = [
            e for e in self.error_history
            if e.error_pattern.name == pattern_name
        ]
        
        if recent_occurrences:
            resolved_count = len([e for e in recent_occurrences if e.resolved])
            stats['success_rate'] = resolved_count / len(recent_occurrences)
    
    def _get_pattern_success_rate(self, pattern_name: str) -> float:
        """Get success rate for a pattern."""
        return self.pattern_stats[pattern_name].get('success_rate', 0.5)
    
    def _update_integrations(self, pattern: ErrorPattern, occurrence: ErrorOccurrence):
        """Update integrated systems based on error."""
        # Update circuit breaker if available
        if self.circuit_breaker and pattern.action == ErrorAction.CIRCUIT_BREAK:
            try:
                self.circuit_breaker.record_failure()
            except Exception as e:
                self.logger.error(f"Error updating circuit breaker: {e}")
    
    def _log_error_and_action(self, occurrence: ErrorOccurrence, action: ErrorAction, 
                             action_params: Dict[str, Any]):
        """Log error occurrence and determined action."""
        severity_emoji = {
            ErrorSeverity.LOW: "ℹ️",
            ErrorSeverity.MEDIUM: "⚠️",
            ErrorSeverity.HIGH: "🚨",
            ErrorSeverity.CRITICAL: "💥",
            ErrorSeverity.FATAL: "☠️"
        }
        
        action_emoji = {
            ErrorAction.RETRY: "🔄",
            ErrorAction.ABORT: "❌",
            ErrorAction.DEGRADE: "🔻",
            ErrorAction.ESCALATE: "🚨",
            ErrorAction.WAIT_AND_RETRY: "⏳",
            ErrorAction.CIRCUIT_BREAK: "🔌",
            ErrorAction.FALLBACK: "🔀"
        }
        
        emoji = severity_emoji.get(occurrence.error_pattern.severity, "❓")
        action_emoji_str = action_emoji.get(action, "❓")
        
        log_message = (
            f"{emoji} Error: {occurrence.error_pattern.name} | "
            f"Action: {action_emoji_str} {action.value} | "
            f"Message: {occurrence.error_message}"
        )
        
        if action_params:
            log_message += f" | Params: {action_params}"
        
        # Log at appropriate level
        if occurrence.error_pattern.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
            self.logger.error(log_message)
        elif occurrence.error_pattern.severity == ErrorSeverity.HIGH:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def _notify_error_callbacks(self, occurrence: ErrorOccurrence, action: ErrorAction, 
                               action_params: Dict[str, Any]):
        """Notify registered error callbacks."""
        for callback in self.error_callbacks:
            try:
                callback(occurrence, action, action_params)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
    
    def add_error_callback(self, callback: Callable):
        """Add callback for error events."""
        self.error_callbacks.append(callback)
    
    def mark_error_resolved(self, error_id: str):
        """Mark an error as resolved."""
        with self.lock:
            for error in self.error_history:
                if id(error) == hash(error_id):  # Simple ID matching
                    error.resolved = True
                    error.resolution_time = datetime.now()
                    break
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        with self.lock:
            now = datetime.now()
            
            # Recent errors (last hour)
            hour_ago = now - timedelta(hours=1)
            recent_errors = [e for e in self.error_history if e.timestamp > hour_ago]
            
            # Error distribution by category
            category_distribution = defaultdict(int)
            severity_distribution = defaultdict(int)
            
            for error in recent_errors:
                category_distribution[error.error_pattern.category.value] += 1
                severity_distribution[error.error_pattern.severity.value] += 1
            
            # Pattern statistics
            pattern_stats = dict(self.pattern_stats)
            
            return {
                "total_errors": len(self.error_history),
                "recent_errors_1h": len(recent_errors),
                "error_rate_per_minute": len(recent_errors) / 60.0,
                "category_distribution": dict(category_distribution),
                "severity_distribution": dict(severity_distribution),
                "pattern_statistics": pattern_stats,
                "degradation_status": {
                    "active": self.degradation_active,
                    "level": self.degradation_level,
                    "duration_seconds": (
                        (now - self.degradation_start_time).total_seconds()
                        if self.degradation_start_time else None
                    )
                },
                "generated_at": now.isoformat()
            }
    
    def check_degradation_recovery(self) -> bool:
        """Check if system can recover from degradation."""
        if not self.degradation_active:
            return True
        
        # Check if degradation timeout has passed
        if self.degradation_start_time:
            elapsed = (datetime.now() - self.degradation_start_time).total_seconds()
            if elapsed > self.config.degradation_timeout_seconds:
                self._deactivate_degradation()
                return True
        
        # Check if error conditions have improved
        recent_errors = self._get_recent_critical_errors()
        if len(recent_errors) == 0:
            self._deactivate_degradation()
            return True
        
        return False
    
    def _get_recent_critical_errors(self) -> List[ErrorOccurrence]:
        """Get recent critical errors."""
        now = datetime.now()
        window_start = now - timedelta(minutes=10)
        
        return [
            e for e in self.error_history
            if (e.timestamp > window_start and 
                e.error_pattern.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL] and
                not e.resolved)
        ]
    
    def reset_error_state(self):
        """Reset error handler state."""
        with self.lock:
            self.error_history.clear()
            self.pattern_stats.clear()
            self._deactivate_degradation()
        
        self.logger.info("🔄 Error handler state reset")


def create_error_handler(config: Optional[ErrorHandlingConfig] = None) -> ErrorHandler:
    """
    Factory function to create an ErrorHandler instance.
    
    Args:
        config: Optional error handling configuration
        
    Returns:
        ErrorHandler instance
    """
    return ErrorHandler(config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Error Handler Testing')
    parser.add_argument('--test-classification', action='store_true',
                       help='Test error classification')
    parser.add_argument('--test-rate-limits', action='store_true',
                       help='Test rate limit error handling')
    parser.add_argument('--test-degradation', action='store_true',
                       help='Test graceful degradation')
    parser.add_argument('--show-stats', action='store_true',
                       help='Show error statistics')
    
    args = parser.parse_args()
    
    # Create error handler
    error_handler = create_error_handler()
    
    try:
        if args.test_classification:
            print("=== Testing Error Classification ===")
            
            # Test various error scenarios
            test_errors = [
                (requests.exceptions.HTTPError("429 Too Many Requests"), {"status_code": 429}),
                (requests.exceptions.HTTPError("503 Service Unavailable"), {"status_code": 503}),
                (requests.exceptions.HTTPError("401 Unauthorized"), {"status_code": 401}),
                (requests.exceptions.ConnectionError("Connection failed"), {}),
                (requests.exceptions.Timeout("Request timeout"), {}),
            ]
            
            for exception, context in test_errors:
                action, params = error_handler.handle_error(exception, context)
                print(f"Error: {exception} → Action: {action.value} | Params: {params}")
        
        elif args.test_rate_limits:
            print("=== Testing Rate Limit Handling ===")
            
            # Simulate rate limit errors
            for i in range(3):
                exception = requests.exceptions.HTTPError("429 Too Many Requests")
                context = {"status_code": 429, "retry_count": i}
                
                action, params = error_handler.handle_error(exception, context)
                print(f"Rate limit attempt {i+1}: {action.value} | Wait: {params.get('wait_time', 0):.1f}s")
        
        elif args.test_degradation:
            print("=== Testing Graceful Degradation ===")
            
            # Simulate quota exceeded error
            exception = requests.exceptions.HTTPError("429 Quota Exceeded")
            context = {"status_code": 429, "error_message": "monthly quota exceeded"}
            
            action, params = error_handler.handle_error(exception, context)
            print(f"Quota error: {action.value} | Level: {params.get('level')}")
            
            # Check degradation status
            stats = error_handler.get_error_statistics()
            print(f"Degradation active: {stats['degradation_status']['active']}")
        
        elif args.show_stats:
            print("=== Error Handler Statistics ===")
            stats = error_handler.get_error_statistics()
            
            print(f"Total errors: {stats['total_errors']}")
            print(f"Recent errors (1h): {stats['recent_errors_1h']}")
            print(f"Error rate: {stats['error_rate_per_minute']:.2f}/min")
            
            print("\nCategory distribution:")
            for category, count in stats['category_distribution'].items():
                print(f"  {category}: {count}")
            
            print("\nSeverity distribution:")
            for severity, count in stats['severity_distribution'].items():
                print(f"  {severity}: {count}")
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("ERROR HANDLER EXAMPLES")
            print("="*60)
            print("# Test error classification:")
            print("python automation/error_handler.py --test-classification")
            print("\n# Test rate limit handling:")
            print("python automation/error_handler.py --test-rate-limits")
            print("\n# Test graceful degradation:")
            print("python automation/error_handler.py --test-degradation")
            print("\n# Show error statistics:")
            print("python automation/error_handler.py --show-stats")
            print("="*60)
            
    except Exception as e:
        print(f"Error: {e}")