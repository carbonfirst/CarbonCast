#!/usr/bin/env python3
"""
Advanced Rate Limiting System for RDA API Management

This module implements intelligent rate limiting that respects RDA API limits,
provides adaptive rate limiting based on API responses, and includes circuit
breaker patterns for handling "too many requests" errors.

Key Features:
- Adaptive rate limiting (10-60 requests per minute based on API responses)
- Circuit breaker for API failures (open/half-open/closed states)
- Exponential backoff with jitter for retry strategies
- Request queuing and throttling to prevent API overload
- Real-time monitoring of rate limit status and API health
"""

import time
import threading
import logging
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import asyncio
from logger_utils import get_logger


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    FIXED = "fixed"
    ADAPTIVE = "adaptive"
    BURST_ALLOWANCE = "burst_allowance"
    PREDICTIVE = "predictive"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class RateLimitLevel(Enum):
    """Rate limit severity levels."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    # Base rate limits
    requests_per_minute: int = 10
    requests_per_hour: int = 600
    burst_allowance: int = 5
    
    # Adaptive settings
    adaptive_enabled: bool = True
    min_requests_per_minute: int = 5
    max_requests_per_minute: int = 60
    adaptation_factor: float = 0.1
    
    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 300
    half_open_max_calls: int = 3
    
    # Backoff settings
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 300.0
    backoff_multiplier: float = 2.0
    jitter_enabled: bool = True
    
    # Monitoring
    monitoring_window_minutes: int = 15
    health_check_interval_seconds: int = 60


@dataclass
class RateLimitStatus:
    """Current rate limit status."""
    current_level: RateLimitLevel
    requests_remaining: int
    reset_time: datetime
    circuit_state: CircuitState
    adaptive_rate: int
    health_score: float
    last_request_time: Optional[datetime] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0


@dataclass
class RequestAttempt:
    """Record of a request attempt."""
    timestamp: datetime
    success: bool
    response_time: float
    status_code: Optional[int] = None
    error_type: Optional[str] = None
    retry_count: int = 0


class RateLimiter:
    """
    Advanced rate limiter with adaptive behavior and circuit breaker patterns.
    
    This class provides comprehensive rate limiting functionality including:
    - Adaptive rate adjustment based on API responses
    - Circuit breaker pattern for failure handling
    - Exponential backoff with jitter
    - Request queuing and throttling
    - Real-time health monitoring
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize the rate limiter.
        
        Args:
            config: Rate limiting configuration
        """
        self.config = config or RateLimitConfig()
        self.logger = self._setup_logging()
        
        # Rate limiting state
        self.current_rate = self.config.requests_per_minute
        self.request_history: deque = deque(maxlen=1000)
        self.failure_history: deque = deque(maxlen=100)
        
        # Circuit breaker state
        self.circuit_state = CircuitState.CLOSED
        self.circuit_failure_count = 0
        self.circuit_last_failure_time: Optional[datetime] = None
        self.circuit_next_attempt_time: Optional[datetime] = None
        
        # Threading
        self.lock = threading.RLock()
        self.request_queue: deque = deque()
        self.active_requests = 0
        
        # Monitoring
        self.status = RateLimitStatus(
            current_level=RateLimitLevel.NORMAL,
            requests_remaining=self.config.requests_per_minute,
            reset_time=datetime.now() + timedelta(minutes=1),
            circuit_state=self.circuit_state,
            adaptive_rate=self.current_rate,
            health_score=1.0
        )
        
        # Callbacks
        self.rate_limit_callbacks: List[Callable] = []
        self.circuit_breaker_callbacks: List[Callable] = []
        
        self.logger.info("RateLimiter initialized with adaptive rate limiting and circuit breaker")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.rate_limiter', level=logging.INFO)
    
    def can_make_request(self) -> Tuple[bool, Optional[float]]:
        """
        Check if a request can be made now.
        
        Returns:
            Tuple of (can_make_request, wait_time_seconds)
        """
        with self.lock:
            # Check circuit breaker
            if self.circuit_state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    wait_time = self._calculate_circuit_wait_time()
                    return False, wait_time
            
            # Check rate limits
            now = datetime.now()
            self._cleanup_old_requests(now)
            
            # Count recent requests
            minute_ago = now - timedelta(minutes=1)
            recent_requests = len([r for r in self.request_history if r.timestamp > minute_ago])
            
            if recent_requests >= self.current_rate:
                # Calculate wait time until next slot is available
                oldest_in_window = min([r.timestamp for r in self.request_history if r.timestamp > minute_ago])
                wait_time = (oldest_in_window + timedelta(minutes=1) - now).total_seconds()
                return False, max(0, wait_time)
            
            return True, 0.0
    
    def acquire_request_slot(self, request_id: str = None) -> bool:
        """
        Acquire a slot for making a request.
        
        Args:
            request_id: Optional identifier for the request
            
        Returns:
            True if slot acquired, False otherwise
        """
        can_request, wait_time = self.can_make_request()
        
        if not can_request:
            self.logger.debug(f"Request slot denied, wait time: {wait_time:.2f}s")
            return False
        
        with self.lock:
            self.active_requests += 1
            self.status.requests_remaining = max(0, self.current_rate - len(self.request_history))
            
        self.logger.debug(f"Request slot acquired (active: {self.active_requests})")
        return True
    
    def record_request_result(self, success: bool, response_time: float, 
                            status_code: Optional[int] = None, 
                            error_type: Optional[str] = None):
        """
        Record the result of a request for adaptive rate limiting.
        
        Args:
            success: Whether the request was successful
            response_time: Request response time in seconds
            status_code: HTTP status code
            error_type: Type of error if request failed
        """
        now = datetime.now()
        
        attempt = RequestAttempt(
            timestamp=now,
            success=success,
            response_time=response_time,
            status_code=status_code,
            error_type=error_type
        )
        
        with self.lock:
            self.request_history.append(attempt)
            self.active_requests = max(0, self.active_requests - 1)
            
            # Update status
            self.status.total_requests += 1
            if success:
                self.status.successful_requests += 1
            else:
                self.status.failed_requests += 1
                self.failure_history.append(attempt)
            
            self.status.last_request_time = now
            
            # Handle circuit breaker logic
            self._update_circuit_breaker(success, status_code, error_type)
            
            # Update adaptive rate limiting
            if self.config.adaptive_enabled:
                self._update_adaptive_rate(success, response_time, status_code)
            
            # Update health score and level
            self._update_health_metrics()
        
        self.logger.debug(f"Request result recorded: success={success}, "
                         f"response_time={response_time:.2f}s, status={status_code}")
    
    def _update_circuit_breaker(self, success: bool, status_code: Optional[int], 
                              error_type: Optional[str]):
        """Update circuit breaker state based on request result."""
        if not self.config.circuit_breaker_enabled:
            return
        
        if success:
            # Reset failure count on success
            if self.circuit_state == CircuitState.HALF_OPEN:
                # Successful request in half-open state, close circuit
                self._transition_to_closed()
            elif self.circuit_state == CircuitState.CLOSED:
                # Reset failure count
                self.circuit_failure_count = 0
        else:
            # Handle failure
            is_circuit_breaker_error = (
                status_code in [429, 503, 502, 504] or
                error_type in ['timeout', 'connection_error', 'rate_limit']
            )
            
            if is_circuit_breaker_error:
                self.circuit_failure_count += 1
                self.circuit_last_failure_time = datetime.now()
                
                if (self.circuit_state == CircuitState.CLOSED and 
                    self.circuit_failure_count >= self.config.failure_threshold):
                    self._transition_to_open()
                elif self.circuit_state == CircuitState.HALF_OPEN:
                    # Failure in half-open state, back to open
                    self._transition_to_open()
    
    def _update_adaptive_rate(self, success: bool, response_time: float, 
                            status_code: Optional[int]):
        """Update adaptive rate limiting based on API responses."""
        if not self.config.adaptive_enabled:
            return
        
        # Calculate adjustment factor
        adjustment = 0.0
        
        if success:
            # Successful request - consider increasing rate
            if response_time < 1.0:  # Fast response
                adjustment = self.config.adaptation_factor
            elif response_time < 3.0:  # Normal response
                adjustment = self.config.adaptation_factor * 0.5
            # Slow response - no adjustment
        else:
            # Failed request - decrease rate
            if status_code == 429:  # Too many requests
                adjustment = -self.config.adaptation_factor * 2.0
            elif status_code in [503, 502, 504]:  # Server errors
                adjustment = -self.config.adaptation_factor * 1.5
            else:
                adjustment = -self.config.adaptation_factor * 0.5
        
        # Apply adjustment
        if adjustment != 0:
            old_rate = self.current_rate
            self.current_rate = max(
                self.config.min_requests_per_minute,
                min(self.config.max_requests_per_minute, 
                    self.current_rate + adjustment)
            )
            
            if abs(self.current_rate - old_rate) > 0.1:
                self.logger.info(f"Adaptive rate adjusted: {old_rate:.1f} → {self.current_rate:.1f} req/min")
                self.status.adaptive_rate = int(self.current_rate)
    
    def _update_health_metrics(self):
        """Update health score and rate limit level."""
        now = datetime.now()
        
        # Calculate health score based on recent success rate
        recent_window = now - timedelta(minutes=self.config.monitoring_window_minutes)
        recent_requests = [r for r in self.request_history if r.timestamp > recent_window]
        
        if recent_requests:
            success_rate = len([r for r in recent_requests if r.success]) / len(recent_requests)
            
            # Factor in circuit breaker state
            circuit_penalty = {
                CircuitState.CLOSED: 0.0,
                CircuitState.HALF_OPEN: 0.2,
                CircuitState.OPEN: 0.5
            }
            
            self.status.health_score = max(0.0, success_rate - circuit_penalty[self.circuit_state])
        else:
            self.status.health_score = 1.0
        
        # Determine rate limit level
        if self.circuit_state == CircuitState.OPEN:
            self.status.current_level = RateLimitLevel.EMERGENCY
        elif self.status.health_score < 0.5:
            self.status.current_level = RateLimitLevel.CRITICAL
        elif self.status.health_score < 0.7:
            self.status.current_level = RateLimitLevel.WARNING
        else:
            self.status.current_level = RateLimitLevel.NORMAL
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.circuit_next_attempt_time is None:
            return True
        return datetime.now() >= self.circuit_next_attempt_time
    
    def _calculate_circuit_wait_time(self) -> float:
        """Calculate wait time for circuit breaker reset."""
        if self.circuit_next_attempt_time is None:
            return 0.0
        return max(0.0, (self.circuit_next_attempt_time - datetime.now()).total_seconds())
    
    def _transition_to_open(self):
        """Transition circuit breaker to open state."""
        self.circuit_state = CircuitState.OPEN
        self.circuit_next_attempt_time = (
            datetime.now() + timedelta(seconds=self.config.recovery_timeout_seconds)
        )
        
        self.logger.warning(f"Circuit breaker OPENED - failures: {self.circuit_failure_count}")
        self._notify_circuit_breaker_callbacks('opened')
    
    def _transition_to_half_open(self):
        """Transition circuit breaker to half-open state."""
        self.circuit_state = CircuitState.HALF_OPEN
        self.circuit_next_attempt_time = None
        
        self.logger.info("Circuit breaker HALF-OPEN - testing recovery")
        self._notify_circuit_breaker_callbacks('half_open')
    
    def _transition_to_closed(self):
        """Transition circuit breaker to closed state."""
        self.circuit_state = CircuitState.CLOSED
        self.circuit_failure_count = 0
        self.circuit_next_attempt_time = None
        
        self.logger.info("Circuit breaker CLOSED - recovery successful")
        self._notify_circuit_breaker_callbacks('closed')
    
    def _cleanup_old_requests(self, now: datetime):
        """Clean up old request records."""
        cutoff = now - timedelta(hours=1)
        
        # Clean request history
        while self.request_history and self.request_history[0].timestamp < cutoff:
            self.request_history.popleft()
        
        # Clean failure history
        while self.failure_history and self.failure_history[0].timestamp < cutoff:
            self.failure_history.popleft()
    
    def calculate_backoff_delay(self, attempt_count: int) -> float:
        """
        Calculate exponential backoff delay with jitter.
        
        Args:
            attempt_count: Number of retry attempts
            
        Returns:
            Delay in seconds
        """
        base_delay = self.config.base_backoff_seconds * (
            self.config.backoff_multiplier ** attempt_count
        )
        
        # Cap at maximum
        delay = min(base_delay, self.config.max_backoff_seconds)
        
        # Add jitter if enabled
        if self.config.jitter_enabled:
            jitter = delay * 0.1 * random.random()
            delay += jitter
        
        return delay
    
    def add_rate_limit_callback(self, callback: Callable):
        """Add callback for rate limit events."""
        self.rate_limit_callbacks.append(callback)
    
    def add_circuit_breaker_callback(self, callback: Callable):
        """Add callback for circuit breaker events."""
        self.circuit_breaker_callbacks.append(callback)
    
    def _notify_rate_limit_callbacks(self, event_type: str, **kwargs):
        """Notify rate limit callbacks."""
        for callback in self.rate_limit_callbacks:
            try:
                callback(event_type, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in rate limit callback: {e}")
    
    def _notify_circuit_breaker_callbacks(self, event_type: str, **kwargs):
        """Notify circuit breaker callbacks."""
        for callback in self.circuit_breaker_callbacks:
            try:
                callback(event_type, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in circuit breaker callback: {e}")
    
    def get_status(self) -> RateLimitStatus:
        """Get current rate limiter status."""
        with self.lock:
            # Update requests remaining
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)
            recent_requests = len([r for r in self.request_history if r.timestamp > minute_ago])
            
            self.status.requests_remaining = max(0, int(self.current_rate) - recent_requests)
            self.status.reset_time = now + timedelta(minutes=1)
            self.status.circuit_state = self.circuit_state
            self.status.adaptive_rate = int(self.current_rate)
            
            return self.status
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get detailed analytics about rate limiting performance."""
        with self.lock:
            now = datetime.now()
            
            # Recent performance metrics
            recent_window = now - timedelta(minutes=self.config.monitoring_window_minutes)
            recent_requests = [r for r in self.request_history if r.timestamp > recent_window]
            
            if recent_requests:
                success_rate = len([r for r in recent_requests if r.success]) / len(recent_requests)
                avg_response_time = sum(r.response_time for r in recent_requests) / len(recent_requests)
                
                # Status code distribution
                status_codes = {}
                for request in recent_requests:
                    if request.status_code:
                        status_codes[request.status_code] = status_codes.get(request.status_code, 0) + 1
            else:
                success_rate = 1.0
                avg_response_time = 0.0
                status_codes = {}
            
            return {
                "current_rate": self.current_rate,
                "circuit_state": self.circuit_state.value,
                "health_score": self.status.health_score,
                "rate_limit_level": self.status.current_level.value,
                "recent_performance": {
                    "success_rate": success_rate,
                    "average_response_time": avg_response_time,
                    "total_requests": len(recent_requests),
                    "status_code_distribution": status_codes
                },
                "circuit_breaker": {
                    "failure_count": self.circuit_failure_count,
                    "last_failure": self.circuit_last_failure_time.isoformat() if self.circuit_last_failure_time else None,
                    "next_attempt": self.circuit_next_attempt_time.isoformat() if self.circuit_next_attempt_time else None
                },
                "total_stats": {
                    "total_requests": self.status.total_requests,
                    "successful_requests": self.status.successful_requests,
                    "failed_requests": self.status.failed_requests
                },
                "generated_at": now.isoformat()
            }
    
    def reset_circuit_breaker(self):
        """Manually reset the circuit breaker."""
        with self.lock:
            self.logger.info("Manually resetting circuit breaker")
            self._transition_to_closed()
    
    def adjust_rate_limit(self, new_rate: int):
        """
        Manually adjust the rate limit.
        
        Args:
            new_rate: New requests per minute limit
        """
        with self.lock:
            old_rate = self.current_rate
            self.current_rate = max(
                self.config.min_requests_per_minute,
                min(self.config.max_requests_per_minute, new_rate)
            )
            
            self.logger.info(f"Rate limit manually adjusted: {old_rate:.1f} → {self.current_rate:.1f} req/min")
            self.status.adaptive_rate = int(self.current_rate)


def create_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """
    Factory function to create a RateLimiter instance.
    
    Args:
        config: Optional rate limiting configuration
        
    Returns:
        RateLimiter instance
    """
    return RateLimiter(config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Rate Limiter Testing')
    parser.add_argument('--test-basic', action='store_true',
                       help='Test basic rate limiting')
    parser.add_argument('--test-adaptive', action='store_true',
                       help='Test adaptive rate limiting')
    parser.add_argument('--test-circuit-breaker', action='store_true',
                       help='Test circuit breaker functionality')
    parser.add_argument('--show-status', action='store_true',
                       help='Show current rate limiter status')
    
    args = parser.parse_args()
    
    # Create rate limiter with test configuration
    config = RateLimitConfig(
        requests_per_minute=5,  # Low limit for testing
        adaptive_enabled=True,
        circuit_breaker_enabled=True,
        failure_threshold=3
    )
    
    rate_limiter = create_rate_limiter(config)
    
    try:
        if args.test_basic:
            print("=== Testing Basic Rate Limiting ===")
            
            for i in range(10):
                can_request, wait_time = rate_limiter.can_make_request()
                print(f"Request {i+1}: {'✅' if can_request else '❌'} "
                      f"(wait: {wait_time:.2f}s)")
                
                if can_request:
                    rate_limiter.acquire_request_slot(f"test_{i}")
                    # Simulate successful request
                    rate_limiter.record_request_result(True, 0.5, 200)
                else:
                    time.sleep(min(wait_time, 2.0))  # Wait up to 2 seconds
        
        elif args.test_adaptive:
            print("=== Testing Adaptive Rate Limiting ===")
            
            # Simulate various response patterns
            scenarios = [
                (True, 0.3, 200, "fast_success"),
                (True, 1.5, 200, "normal_success"),
                (False, 5.0, 429, "rate_limited"),
                (False, 10.0, 503, "server_error"),
                (True, 0.8, 200, "recovery")
            ]
            
            for success, response_time, status_code, scenario in scenarios:
                print(f"\nScenario: {scenario}")
                print(f"Before: Rate = {rate_limiter.current_rate:.1f} req/min")
                
                rate_limiter.record_request_result(success, response_time, status_code)
                
                print(f"After: Rate = {rate_limiter.current_rate:.1f} req/min")
                print(f"Health Score: {rate_limiter.status.health_score:.2f}")
        
        elif args.test_circuit_breaker:
            print("=== Testing Circuit Breaker ===")
            
            # Simulate failures to trigger circuit breaker
            for i in range(5):
                print(f"\nFailure {i+1}:")
                rate_limiter.record_request_result(False, 10.0, 503, "server_error")
                print(f"Circuit State: {rate_limiter.circuit_state.value}")
                print(f"Failure Count: {rate_limiter.circuit_failure_count}")
            
            # Test request blocking
            can_request, wait_time = rate_limiter.can_make_request()
            print(f"\nCan make request after failures: {'✅' if can_request else '❌'}")
            print(f"Wait time: {wait_time:.2f}s")
        
        elif args.show_status:
            print("=== Rate Limiter Status ===")
            status = rate_limiter.get_status()
            analytics = rate_limiter.get_analytics()
            
            print(f"Current Rate: {analytics['current_rate']:.1f} req/min")
            print(f"Circuit State: {analytics['circuit_state']}")
            print(f"Health Score: {analytics['health_score']:.2f}")
            print(f"Rate Limit Level: {analytics['rate_limit_level']}")
            print(f"Requests Remaining: {status.requests_remaining}")
            
            print("\nRecent Performance:")
            perf = analytics['recent_performance']
            print(f"  Success Rate: {perf['success_rate']:.1%}")
            print(f"  Avg Response Time: {perf['average_response_time']:.2f}s")
            print(f"  Total Requests: {perf['total_requests']}")
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("RATE LIMITER EXAMPLES")
            print("="*60)
            print("# Test basic rate limiting:")
            print("python automation/rate_limiter.py --test-basic")
            print("\n# Test adaptive rate limiting:")
            print("python automation/rate_limiter.py --test-adaptive")
            print("\n# Test circuit breaker:")
            print("python automation/rate_limiter.py --test-circuit-breaker")
            print("\n# Show current status:")
            print("python automation/rate_limiter.py --show-status")
            print("="*60)
            
    except Exception as e:
        print(f"Error: {e}")