#!/usr/bin/env python3
"""
Request Throttling System for RDA API Management

This module implements intelligent request throttling and queuing mechanisms
that work with the rate limiter and error handler to provide optimal request
management for the RDA API.

Key Features:
- Request queuing and throttling mechanisms
- Intelligent request scheduling to avoid API limits
- Request priority management for critical operations
- Integration with rate limiting and error handling systems
- Monitoring and alerting for throttling situations
- Adaptive throttling based on API health and performance
"""

import time
import threading
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import heapq
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from logger_utils import get_logger


class RequestPriority(Enum):
    """Request priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


class ThrottleMode(Enum):
    """Throttling modes."""
    DISABLED = "disabled"
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    EMERGENCY = "emergency"


class RequestStatus(Enum):
    """Request status in the throttling system."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    THROTTLED = "throttled"


@dataclass
class ThrottledRequest:
    """Represents a throttled request."""
    request_id: str
    priority: RequestPriority
    request_func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: RequestStatus = RequestStatus.QUEUED
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Optional[Exception] = None
    
    def __lt__(self, other):
        """For priority queue ordering."""
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value  # Higher priority first
        return self.created_at < other.created_at  # FIFO for same priority


@dataclass
class ThrottlingConfig:
    """Configuration for request throttling."""
    # Queue settings
    max_queue_size: int = 1000
    max_concurrent_requests: int = 5
    default_timeout_seconds: float = 300.0
    
    # Throttling behavior
    throttle_mode: ThrottleMode = ThrottleMode.BALANCED
    adaptive_throttling: bool = True
    min_request_interval_seconds: float = 1.0
    max_request_interval_seconds: float = 60.0
    
    # Priority settings
    priority_boost_threshold_minutes: int = 30
    emergency_queue_size_limit: int = 50
    
    # Integration settings
    rate_limiter_integration: bool = True
    error_handler_integration: bool = True
    circuit_breaker_respect: bool = True
    
    # Monitoring
    performance_tracking_enabled: bool = True
    queue_health_monitoring: bool = True
    alert_on_queue_full: bool = True


@dataclass
class ThrottlingMetrics:
    """Metrics for throttling performance."""
    total_requests: int = 0
    queued_requests: int = 0
    processing_requests: int = 0
    completed_requests: int = 0
    failed_requests: int = 0
    cancelled_requests: int = 0
    
    average_queue_time: float = 0.0
    average_processing_time: float = 0.0
    current_queue_size: int = 0
    max_queue_size_reached: int = 0
    
    throttling_events: int = 0
    rate_limit_delays: int = 0
    circuit_breaker_blocks: int = 0
    
    last_request_time: Optional[datetime] = None
    system_start_time: datetime = field(default_factory=datetime.now)


class RequestThrottler:
    """
    Intelligent request throttling system that manages API request flow.
    
    This class provides comprehensive request management including queuing,
    prioritization, throttling, and integration with rate limiting and error
    handling systems.
    """
    
    def __init__(self, config: Optional[ThrottlingConfig] = None):
        """
        Initialize the request throttler.
        
        Args:
            config: Throttling configuration
        """
        self.config = config or ThrottlingConfig()
        self.logger = self._setup_logging()
        
        # Request queue (priority queue)
        self.request_queue: List[ThrottledRequest] = []
        self.request_lookup: Dict[str, ThrottledRequest] = {}
        
        # Processing state
        self.active_requests: Dict[str, ThrottledRequest] = {}
        self.completed_requests: deque = deque(maxlen=1000)
        
        # Threading
        self.queue_lock = threading.RLock()
        self.processing_lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_requests)
        self.futures: Dict[str, Future] = {}
        
        # Control flags
        self.running = False
        self.paused = False
        self.processor_thread: Optional[threading.Thread] = None
        
        # Metrics and monitoring
        self.metrics = ThrottlingMetrics()
        self.performance_history: deque = deque(maxlen=100)
        
        # Integration components
        self.rate_limiter = None
        self.error_handler = None
        self.circuit_breaker = None
        
        # Callbacks
        self.request_callbacks: List[Callable] = []
        self.throttling_callbacks: List[Callable] = []
        
        # Adaptive throttling state
        self.current_interval = self.config.min_request_interval_seconds
        self.last_request_time: Optional[datetime] = None
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        
        self.logger.info("RequestThrottler initialized with intelligent queuing and throttling")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.request_throttler', level=logging.INFO)
    
    def set_integrations(self, rate_limiter=None, error_handler=None, circuit_breaker=None):
        """
        Set integration components.
        
        Args:
            rate_limiter: RateLimiter instance
            error_handler: ErrorHandler instance
            circuit_breaker: Circuit breaker instance
        """
        self.rate_limiter = rate_limiter
        self.error_handler = error_handler
        self.circuit_breaker = circuit_breaker
        
        self.logger.info("✅ Request throttler integrations configured")
    
    def start(self):
        """Start the request throttling system."""
        if self.running:
            self.logger.warning("⚠️ Request throttler is already running")
            return
        
        self.running = True
        self.paused = False
        
        # Start the request processor thread
        self.processor_thread = threading.Thread(
            target=self._process_requests,
            name="RequestThrottlerProcessor",
            daemon=True
        )
        self.processor_thread.start()
        
        self.logger.info("🚀 Request throttler started")
    
    def stop(self):
        """Stop the request throttling system."""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel all pending requests
        with self.queue_lock:
            for request in self.request_queue:
                request.status = RequestStatus.CANCELLED
                request.completed_at = datetime.now()
        
        # Wait for processor thread to finish
        if self.processor_thread and self.processor_thread.is_alive():
            self.processor_thread.join(timeout=5.0)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        self.logger.info("🛑 Request throttler stopped")
    
    def pause(self):
        """Pause request processing."""
        self.paused = True
        self.logger.info("⏸️ Request throttler paused")
    
    def resume(self):
        """Resume request processing."""
        self.paused = False
        self.logger.info("▶️ Request throttler resumed")
    
    def submit_request(self, 
                      request_func: Callable,
                      args: tuple = (),
                      kwargs: dict = None,
                      priority: RequestPriority = RequestPriority.NORMAL,
                      timeout: Optional[float] = None,
                      max_retries: int = 3,
                      context: Dict[str, Any] = None) -> str:
        """
        Submit a request for throttled execution.
        
        Args:
            request_func: Function to execute
            args: Function arguments
            kwargs: Function keyword arguments
            priority: Request priority
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            context: Additional context information
            
        Returns:
            Request ID for tracking
        """
        kwargs = kwargs or {}
        context = context or {}
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Create throttled request
        request = ThrottledRequest(
            request_id=request_id,
            priority=priority,
            request_func=request_func,
            args=args,
            kwargs=kwargs,
            timeout_seconds=timeout or self.config.default_timeout_seconds,
            max_retries=max_retries,
            context=context
        )
        
        # Check queue capacity
        with self.queue_lock:
            if len(self.request_queue) >= self.config.max_queue_size:
                if priority in [RequestPriority.CRITICAL, RequestPriority.EMERGENCY]:
                    # Remove lowest priority request to make room
                    self._make_room_for_priority_request()
                else:
                    raise RuntimeError(f"Request queue is full ({self.config.max_queue_size})")
            
            # Add to queue
            heapq.heappush(self.request_queue, request)
            self.request_lookup[request_id] = request
            
            # Update metrics
            self.metrics.total_requests += 1
            self.metrics.queued_requests += 1
            self.metrics.current_queue_size = len(self.request_queue)
            self.metrics.max_queue_size_reached = max(
                self.metrics.max_queue_size_reached,
                self.metrics.current_queue_size
            )
        
        self.logger.debug(f"📥 Request queued: {request_id} (priority: {priority.name})")
        
        # Notify callbacks
        self._notify_request_callbacks('queued', request)
        
        return request_id
    
    def get_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific request.
        
        Args:
            request_id: Request ID
            
        Returns:
            Request status information or None if not found
        """
        request = self.request_lookup.get(request_id)
        if not request:
            # Check completed requests
            for completed in self.completed_requests:
                if completed.request_id == request_id:
                    request = completed
                    break
        
        if not request:
            return None
        
        return {
            "request_id": request.request_id,
            "status": request.status.value,
            "priority": request.priority.name,
            "created_at": request.created_at.isoformat(),
            "scheduled_at": request.scheduled_at.isoformat() if request.scheduled_at else None,
            "started_at": request.started_at.isoformat() if request.started_at else None,
            "completed_at": request.completed_at.isoformat() if request.completed_at else None,
            "retry_count": request.retry_count,
            "max_retries": request.max_retries,
            "error": str(request.error) if request.error else None,
            "context": request.context
        }
    
    def cancel_request(self, request_id: str) -> bool:
        """
        Cancel a pending request.
        
        Args:
            request_id: Request ID to cancel
            
        Returns:
            True if cancelled, False if not found or already processing
        """
        with self.queue_lock:
            request = self.request_lookup.get(request_id)
            if not request:
                return False
            
            if request.status in [RequestStatus.PROCESSING, RequestStatus.COMPLETED]:
                return False
            
            # Remove from queue
            try:
                self.request_queue.remove(request)
                heapq.heapify(self.request_queue)  # Restore heap property
            except ValueError:
                pass  # Already removed
            
            # Update status
            request.status = RequestStatus.CANCELLED
            request.completed_at = datetime.now()
            
            # Update metrics
            self.metrics.cancelled_requests += 1
            self.metrics.queued_requests = max(0, self.metrics.queued_requests - 1)
            self.metrics.current_queue_size = len(self.request_queue)
        
        self.logger.debug(f"❌ Request cancelled: {request_id}")
        self._notify_request_callbacks('cancelled', request)
        
        return True
    
    def _process_requests(self):
        """Main request processing loop."""
        self.logger.info("🔄 Request processor started")
        
        while self.running:
            try:
                if self.paused:
                    time.sleep(1.0)
                    continue
                
                # Get next request
                request = self._get_next_request()
                if not request:
                    time.sleep(0.1)  # Short sleep when no requests
                    continue
                
                # Check if we can process the request
                if not self._can_process_request():
                    time.sleep(0.5)  # Wait before checking again
                    continue
                
                # Process the request
                self._execute_request(request)
                
                # Apply throttling delay
                self._apply_throttling_delay()
                
            except Exception as e:
                self.logger.error(f"❌ Error in request processor: {e}")
                time.sleep(1.0)  # Error recovery delay
        
        self.logger.info("🔄 Request processor stopped")
    
    def _get_next_request(self) -> Optional[ThrottledRequest]:
        """Get the next request to process."""
        with self.queue_lock:
            if not self.request_queue:
                return None
            
            # Get highest priority request
            request = heapq.heappop(self.request_queue)
            
            # Update metrics
            self.metrics.queued_requests = max(0, self.metrics.queued_requests - 1)
            self.metrics.current_queue_size = len(self.request_queue)
            
            return request
    
    def _can_process_request(self) -> bool:
        """Check if we can process a new request."""
        # Check concurrent request limit
        with self.processing_lock:
            if len(self.active_requests) >= self.config.max_concurrent_requests:
                return False
        
        # Check rate limiter
        if self.rate_limiter and self.config.rate_limiter_integration:
            can_request, wait_time = self.rate_limiter.can_make_request()
            if not can_request:
                if wait_time > 0:
                    self.metrics.rate_limit_delays += 1
                return False
        
        # Check circuit breaker
        if self.circuit_breaker and self.config.circuit_breaker_respect:
            if hasattr(self.circuit_breaker, 'is_open') and self.circuit_breaker.is_open():
                self.metrics.circuit_breaker_blocks += 1
                return False
        
        return True
    
    def _execute_request(self, request: ThrottledRequest):
        """Execute a request."""
        request.status = RequestStatus.PROCESSING
        request.started_at = datetime.now()
        
        with self.processing_lock:
            self.active_requests[request.request_id] = request
            self.metrics.processing_requests += 1
        
        self.logger.debug(f"🔄 Processing request: {request.request_id}")
        
        # Submit to thread pool
        future = self.executor.submit(self._run_request, request)
        self.futures[request.request_id] = future
        
        # Handle completion asynchronously
        future.add_done_callback(lambda f: self._handle_request_completion(request, f))
    
    def _run_request(self, request: ThrottledRequest) -> Any:
        """Run the actual request function."""
        try:
            # Acquire rate limiter slot if available
            if self.rate_limiter and self.config.rate_limiter_integration:
                self.rate_limiter.acquire_request_slot(request.request_id)
            
            # Execute the request function
            start_time = time.time()
            result = request.request_func(*request.args, **request.kwargs)
            end_time = time.time()
            
            # Record success with rate limiter
            if self.rate_limiter and self.config.rate_limiter_integration:
                self.rate_limiter.record_request_result(
                    success=True,
                    response_time=end_time - start_time,
                    status_code=200  # Assume success
                )
            
            return result
            
        except Exception as e:
            # Record failure with rate limiter
            if self.rate_limiter and self.config.rate_limiter_integration:
                status_code = getattr(e, 'response', {}).get('status_code', 500)
                self.rate_limiter.record_request_result(
                    success=False,
                    response_time=time.time() - start_time if 'start_time' in locals() else 0,
                    status_code=status_code,
                    error_type=type(e).__name__
                )
            
            raise e
    
    def _handle_request_completion(self, request: ThrottledRequest, future: Future):
        """Handle request completion."""
        try:
            # Get result or exception
            if future.exception():
                request.error = future.exception()
                request.status = RequestStatus.FAILED
                self._handle_request_failure(request)
            else:
                request.result = future.result()
                request.status = RequestStatus.COMPLETED
                self._handle_request_success(request)
            
        except Exception as e:
            self.logger.error(f"❌ Error handling request completion: {e}")
            request.error = e
            request.status = RequestStatus.FAILED
        
        finally:
            # Clean up
            request.completed_at = datetime.now()
            
            with self.processing_lock:
                self.active_requests.pop(request.request_id, None)
                self.metrics.processing_requests = max(0, self.metrics.processing_requests - 1)
            
            self.futures.pop(request.request_id, None)
            
            # Move to completed requests
            self.completed_requests.append(request)
            
            # Update metrics
            if request.status == RequestStatus.COMPLETED:
                self.metrics.completed_requests += 1
                self.consecutive_successes += 1
                self.consecutive_failures = 0
            else:
                self.metrics.failed_requests += 1
                self.consecutive_failures += 1
                self.consecutive_successes = 0
            
            # Update performance metrics
            self._update_performance_metrics(request)
            
            # Notify callbacks
            self._notify_request_callbacks('completed', request)
    
    def _handle_request_success(self, request: ThrottledRequest):
        """Handle successful request completion."""
        self.logger.debug(f"✅ Request completed successfully: {request.request_id}")
        
        # Adaptive throttling adjustment
        if self.config.adaptive_throttling:
            self._adjust_throttling_for_success()
    
    def _handle_request_failure(self, request: ThrottledRequest):
        """Handle failed request."""
        self.logger.warning(f"❌ Request failed: {request.request_id} - {request.error}")
        
        # Handle with error handler if available
        if self.error_handler and self.config.error_handler_integration:
            try:
                action, params = self.error_handler.handle_error(
                    request.error,
                    context={
                        'request_id': request.request_id,
                        'retry_count': request.retry_count,
                        'priority': request.priority.name
                    }
                )
                
                # Handle retry action
                if action.name == 'RETRY' and request.retry_count < request.max_retries:
                    self._retry_request(request, params.get('delay', 0))
                    return
                    
            except Exception as e:
                self.logger.error(f"Error in error handler integration: {e}")
        
        # Default retry logic
        if request.retry_count < request.max_retries:
            self._retry_request(request)
        
        # Adaptive throttling adjustment
        if self.config.adaptive_throttling:
            self._adjust_throttling_for_failure()
    
    def _retry_request(self, request: ThrottledRequest, delay: float = 0):
        """Retry a failed request."""
        request.retry_count += 1
        request.status = RequestStatus.QUEUED
        request.started_at = None
        request.completed_at = None
        request.error = None
        
        # Schedule retry with delay
        if delay > 0:
            request.scheduled_at = datetime.now() + timedelta(seconds=delay)
        
        # Re-queue the request
        with self.queue_lock:
            heapq.heappush(self.request_queue, request)
            self.metrics.queued_requests += 1
            self.metrics.current_queue_size = len(self.request_queue)
        
        self.logger.debug(f"🔄 Request queued for retry: {request.request_id} "
                         f"(attempt {request.retry_count}/{request.max_retries})")
    
    def _apply_throttling_delay(self):
        """Apply throttling delay between requests."""
        if self.current_interval > 0:
            time.sleep(self.current_interval)
        
        self.last_request_time = datetime.now()
        self.metrics.last_request_time = self.last_request_time
    
    def _adjust_throttling_for_success(self):
        """Adjust throttling parameters for successful requests."""
        if self.consecutive_successes >= 5:
            # Decrease interval (increase throughput)
            self.current_interval = max(
                self.config.min_request_interval_seconds,
                self.current_interval * 0.9
            )
            self.consecutive_successes = 0
    
    def _adjust_throttling_for_failure(self):
        """Adjust throttling parameters for failed requests."""
        if self.consecutive_failures >= 3:
            # Increase interval (decrease throughput)
            self.current_interval = min(
                self.config.max_request_interval_seconds,
                self.current_interval * 1.5
            )
            self.consecutive_failures = 0
            self.metrics.throttling_events += 1
    
    def _make_room_for_priority_request(self):
        """Remove lowest priority request to make room for high priority request."""
        if not self.request_queue:
            return
        
        # Find lowest priority request
        lowest_priority_request = min(self.request_queue, key=lambda r: r.priority.value)
        
        # Remove it
        self.request_queue.remove(lowest_priority_request)
        heapq.heapify(self.request_queue)
        
        # Cancel the removed request
        lowest_priority_request.status = RequestStatus.CANCELLED
        lowest_priority_request.completed_at = datetime.now()
        
        self.logger.warning(f"⚠️ Removed low priority request to make room: "
                           f"{lowest_priority_request.request_id}")
    
    def _update_performance_metrics(self, request: ThrottledRequest):
        """Update performance metrics based on completed request."""
        if not request.started_at or not request.completed_at:
            return
        
        # Calculate times
        queue_time = (request.started_at - request.created_at).total_seconds()
        processing_time = (request.completed_at - request.started_at).total_seconds()
        
        # Update averages
        total_completed = self.metrics.completed_requests + self.metrics.failed_requests
        if total_completed > 0:
            self.metrics.average_queue_time = (
                (self.metrics.average_queue_time * (total_completed - 1) + queue_time) / total_completed
            )
            self.metrics.average_processing_time = (
                (self.metrics.average_processing_time * (total_completed - 1) + processing_time) / total_completed
            )
        
        # Store in history
        self.performance_history.append({
            'timestamp': request.completed_at,
            'queue_time': queue_time,
            'processing_time': processing_time,
            'success': request.status == RequestStatus.COMPLETED,
            'priority': request.priority.name,
            'retry_count': request.retry_count
        })
    
    def _notify_request_callbacks(self, event_type: str, request: ThrottledRequest):
        """Notify request callbacks."""
        for callback in self.request_callbacks:
            try:
                callback(event_type, request)
            except Exception as e:
                self.logger.error(f"Error in request callback: {e}")
    
    def _notify_throttling_callbacks(self, event_type: str, **kwargs):
        """Notify throttling callbacks."""
        for callback in self.throttling_callbacks:
            try:
                callback(event_type, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in throttling callback: {e}")
    
    def add_request_callback(self, callback: Callable):
        """Add callback for request events."""
        self.request_callbacks.append(callback)
    
    def add_throttling_callback(self, callback: Callable):
        """Add callback for throttling events."""
        self.throttling_callbacks.append(callback)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive throttling metrics."""
        with self.queue_lock, self.processing_lock:
            uptime = (datetime.now() - self.metrics.system_start_time).total_seconds()
            
            return {
                "queue_status": {
                    "current_size": self.metrics.current_queue_size,
                    "max_size": self.config.max_queue_size,
                    "max_reached": self.metrics.max_queue_size_reached,
                    "utilization": self.metrics.current_queue_size / self.config.max_queue_size
                },
                "processing_status": {
                    "active_requests": len(self.active_requests),
                    "max_concurrent": self.config.max_concurrent_requests,
                    "utilization": len(self.active_requests) / self.config.max_concurrent_requests
                },
                "request_statistics": {
                    "total": self.metrics.total_requests,
                    "queued": self.metrics.queued_requests,
                    "processing": self.metrics.processing_requests,
                    "completed": self.metrics.completed_requests,
                    "failed": self.metrics.failed_requests,
                    "cancelled": self.metrics.cancelled_requests,
                    "success_rate": (
                        self.metrics.completed_requests / 
                        max(1, self.metrics.completed_requests + self.metrics.failed_requests)
                    )
                },
                "performance_metrics": {
                    "average_queue_time": self.metrics.average_queue_time,
                    "average_processing_time": self.metrics.average_processing_time,
                    "requests_per_minute": (
                        (self.metrics.completed_requests + self.metrics.failed_requests) / 
                        max(1, uptime / 60)
                    )
                },
                "throttling_metrics": {
                    "current_interval": self.current_interval,
                    "throttling_events": self.metrics.throttling_events,
                    "rate_limit_delays": self.metrics.rate_limit_delays,
                    "circuit_breaker_blocks": self.metrics.circuit_breaker_blocks,
                    "consecutive_successes": self.consecutive_successes,
                    "consecutive_failures": self.consecutive_failures
                },
                "system_status": {
                    "running": self.running,
                    "paused": self.paused,
                    "uptime_seconds": uptime,
                    "last_request_time": (
                        self.metrics.last_request_time.isoformat() 
                        if self.metrics.last_request_time else None
                    )
                },
                "generated_at": datetime.now().isoformat()
            }
    
    def get_queue_status(self) -> List[Dict[str, Any]]:
        """Get status of all queued requests."""
        with self.queue_lock:
            return [
                {
                    "request_id": req.request_id,
                    "priority": req.priority.name,
                    "created_at": req.created_at.isoformat(),
                    "scheduled_at": req.scheduled_at.isoformat() if req.scheduled_at else None,
                    "retry_count": req.retry_count,
                    "context": req.context
                }
                for req in sorted(self.request_queue, key=lambda r: r.priority.value, reverse=True)
            ]
    
    def clear_completed_requests(self):
        """Clear completed request history."""
        self.completed_requests.clear()
        self.performance_history.clear()
        self.logger.info("🧹 Cleared completed request history")
    
    def set_throttle_mode(self, mode: ThrottleMode):
        """Set throttling mode."""
        self.config.throttle_mode = mode
        
        # Adjust parameters based on mode
        if mode == ThrottleMode.DISABLED:
            self.current_interval = 0.0
        elif mode == ThrottleMode.CONSERVATIVE:
            self.current_interval = self.config.max_request_interval_seconds
        elif mode == ThrottleMode.BALANCED:
            self.current_interval = (
                self.config.min_request_interval_seconds +
                self.config.max_request_interval_seconds
            ) / 2.0
        elif mode == ThrottleMode.AGGRESSIVE:
            self.current_interval = self.config.min_request_interval_seconds
        elif mode == ThrottleMode.EMERGENCY:
            self.current_interval = 0.0
            self.config.max_concurrent_requests = 1  # Single threaded in emergency
        
        self.logger.info(f"🔧 Throttle mode set to: {mode.value}")
        self._notify_throttling_callbacks('mode_changed', mode=mode)


def create_request_throttler(config: Optional[ThrottlingConfig] = None) -> RequestThrottler:
    """
    Factory function to create a RequestThrottler instance.
    
    Args:
        config: Optional throttling configuration
        
    Returns:
        RequestThrottler instance
    """
    return RequestThrottler(config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Request Throttler Testing')
    parser.add_argument('--test-basic', action='store_true',
                       help='Test basic throttling functionality')
    parser.add_argument('--test-priority', action='store_true',
                       help='Test priority queue functionality')
    parser.add_argument('--test-integration', action='store_true',
                       help='Test integration with rate limiter')
    parser.add_argument('--show-metrics', action='store_true',
                       help='Show throttling metrics')
    parser.add_argument('--stress-test', action='store_true',
                       help='Run stress test with many requests')
    
    args = parser.parse_args()
    
    # Create throttler with test configuration
    config = ThrottlingConfig(
        max_queue_size=100,
        max_concurrent_requests=3,
        min_request_interval_seconds=0.5,
        max_request_interval_seconds=5.0,
        adaptive_throttling=True
    )
    
    throttler = create_request_throttler(config)
    
    def test_request_function(request_id: str, delay: float = 1.0, should_fail: bool = False):
        """Test request function."""
        print(f"  🔄 Executing request {request_id}")
        time.sleep(delay)
        
        if should_fail:
            raise Exception(f"Test failure for {request_id}")
        
        return f"Result for {request_id}"
    
    try:
        if args.test_basic:
            print("=== Testing Basic Throttling ===")
            
            throttler.start()
            
            # Submit several requests
            request_ids = []
            for i in range(5):
                request_id = throttler.submit_request(
                    test_request_function,
                    args=(f"test_{i}", 0.5),
                    priority=RequestPriority.NORMAL
                )
                request_ids.append(request_id)
                print(f"📥 Submitted request: {request_id}")
            
            # Wait for completion
            time.sleep(10)
            
            # Check results
            for request_id in request_ids:
                status = throttler.get_request_status(request_id)
                if status:
                    print(f"📊 {request_id}: {status['status']}")
            
            throttler.stop()
        
        elif args.test_priority:
            print("=== Testing Priority Queue ===")
            
            throttler.start()
            
            # Submit requests with different priorities
            priorities = [
                (RequestPriority.LOW, "low_priority"),
                (RequestPriority.CRITICAL, "critical_priority"),
                (RequestPriority.NORMAL, "normal_priority"),
                (RequestPriority.HIGH, "high_priority"),
                (RequestPriority.EMERGENCY, "emergency_priority")
            ]
            
            request_ids = []
            for priority, name in priorities:
                request_id = throttler.submit_request(
                    test_request_function,
                    args=(name, 1.0),
                    priority=priority
                )
                request_ids.append((request_id, priority.name))
                print(f"📥 Submitted {priority.name} request: {request_id}")
            
            # Wait and check execution order
            time.sleep(15)
            
            # Show queue status
            queue_status = throttler.get_queue_status()
            print(f"\n📋 Queue status: {len(queue_status)} requests")
            for req in queue_status:
                print(f"  - {req['request_id']}: {req['priority']}")
            
            throttler.stop()
        
        elif args.test_integration:
            print("=== Testing Rate Limiter Integration ===")
            
            # Create rate limiter
            from rate_limiter import create_rate_limiter, RateLimitConfig
            
            rate_config = RateLimitConfig(
                requests_per_minute=3,  # Very low for testing
                adaptive_enabled=True
            )
            rate_limiter = create_rate_limiter(rate_config)
            
            # Set integration
            throttler.set_integrations(rate_limiter=rate_limiter)
            throttler.start()
            
            # Submit requests that will hit rate limits
            request_ids = []
            for i in range(8):
                request_id = throttler.submit_request(
                    test_request_function,
                    args=(f"rate_test_{i}", 0.2),
                    priority=RequestPriority.NORMAL
                )
                request_ids.append(request_id)
                print(f"📥 Submitted request: {request_id}")
            
            # Monitor progress
            for _ in range(30):  # Monitor for 30 seconds
                metrics = throttler.get_metrics()
                rate_status = rate_limiter.get_status()
                
                print(f"⏱️  Queue: {metrics['queue_status']['current_size']}, "
                      f"Active: {metrics['processing_status']['active_requests']}, "
                      f"Rate limit remaining: {rate_status.requests_remaining}")
                
                time.sleep(1)
                
                if metrics['queue_status']['current_size'] == 0 and metrics['processing_status']['active_requests'] == 0:
                    break
            
            throttler.stop()
        
        elif args.show_metrics:
            print("=== Throttling Metrics ===")
            
            throttler.start()
            
            # Submit some test requests
            for i in range(10):
                throttler.submit_request(
                    test_request_function,
                    args=(f"metric_test_{i}", 0.1),
                    priority=RequestPriority.NORMAL if i % 2 == 0 else RequestPriority.HIGH
                )
            
            # Wait a bit
            time.sleep(5)
            
            # Show metrics
            metrics = throttler.get_metrics()
            
            print(f"Queue Status:")
            print(f"  Current Size: {metrics['queue_status']['current_size']}")
            print(f"  Utilization: {metrics['queue_status']['utilization']:.1%}")
            
            print(f"\nProcessing Status:")
            print(f"  Active Requests: {metrics['processing_status']['active_requests']}")
            print(f"  Utilization: {metrics['processing_status']['utilization']:.1%}")
            
            print(f"\nRequest Statistics:")
            stats = metrics['request_statistics']
            print(f"  Total: {stats['total']}")
            print(f"  Completed: {stats['completed']}")
            print(f"  Failed: {stats['failed']}")
            print(f"  Success Rate: {stats['success_rate']:.1%}")
            
            print(f"\nPerformance Metrics:")
            perf = metrics['performance_metrics']
            print(f"  Avg Queue Time: {perf['average_queue_time']:.2f}s")
            print(f"  Avg Processing Time: {perf['average_processing_time']:.2f}s")
            print(f"  Requests/min: {perf['requests_per_minute']:.1f}")
            
            print(f"\nThrottling Metrics:")
            throttle = metrics['throttling_metrics']
            print(f"  Current Interval: {throttle['current_interval']:.2f}s")
            print(f"  Throttling Events: {throttle['throttling_events']}")
            print(f"  Rate Limit Delays: {throttle['rate_limit_delays']}")
            
            throttler.stop()
        
        elif args.stress_test:
            print("=== Stress Testing ===")
            
            # Configure for stress test
            stress_config = ThrottlingConfig(
                max_queue_size=500,
                max_concurrent_requests=10,
                min_request_interval_seconds=0.1,
                adaptive_throttling=True
            )
            stress_throttler = create_request_throttler(stress_config)
            stress_throttler.start()
            
            # Submit many requests
            num_requests = 100
            start_time = time.time()
            
            print(f"📤 Submitting {num_requests} requests...")
            
            request_ids = []
            for i in range(num_requests):
                try:
                    request_id = stress_throttler.submit_request(
                        test_request_function,
                        args=(f"stress_{i}", 0.1, i % 20 == 0),  # 5% failure rate
                        priority=RequestPriority.HIGH if i % 10 == 0 else RequestPriority.NORMAL
                    )
                    request_ids.append(request_id)
                except Exception as e:
                    print(f"❌ Failed to submit request {i}: {e}")
            
            submission_time = time.time() - start_time
            print(f"✅ Submitted {len(request_ids)} requests in {submission_time:.2f}s")
            
            # Monitor completion
            print("⏳ Waiting for completion...")
            
            while True:
                metrics = stress_throttler.get_metrics()
                queue_size = metrics['queue_status']['current_size']
                active = metrics['processing_status']['active_requests']
                completed = metrics['request_statistics']['completed']
                failed = metrics['request_statistics']['failed']
                
                print(f"📊 Queue: {queue_size}, Active: {active}, "
                      f"Completed: {completed}, Failed: {failed}")
                
                if queue_size == 0 and active == 0:
                    break
                
                time.sleep(2)
            
            total_time = time.time() - start_time
            final_metrics = stress_throttler.get_metrics()
            
            print(f"\n🎯 Stress Test Results:")
            print(f"  Total Time: {total_time:.2f}s")
            print(f"  Requests/sec: {num_requests/total_time:.2f}")
            print(f"  Success Rate: {final_metrics['request_statistics']['success_rate']:.1%}")
            print(f"  Avg Queue Time: {final_metrics['performance_metrics']['average_queue_time']:.2f}s")
            print(f"  Avg Processing Time: {final_metrics['performance_metrics']['average_processing_time']:.2f}s")
            
            stress_throttler.stop()
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("REQUEST THROTTLER EXAMPLES")
            print("="*60)
            print("# Test basic throttling:")
            print("python automation/request_throttler.py --test-basic")
            print("\n# Test priority queue:")
            print("python automation/request_throttler.py --test-priority")
            print("\n# Test rate limiter integration:")
            print("python automation/request_throttler.py --test-integration")
            print("\n# Show metrics:")
            print("python automation/request_throttler.py --show-metrics")
            print("\n# Run stress test:")
            print("python automation/request_throttler.py --stress-test")
            print("="*60)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'throttler' in locals() and throttler.running:
            throttler.stop()
        if 'stress_throttler' in locals() and stress_throttler.running:
            stress_throttler.stop()