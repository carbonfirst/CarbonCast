#!/usr/bin/env python3
"""
Smart Retry Manager for RDA Automation System

This module provides the main orchestration layer for the smart retry system,
integrating all components including retry strategies, circuit breakers, queue
processing, and capacity management for intelligent failure handling.

Key Features:
- Unified interface for smart retry operations
- Integration with all retry system components
- Intelligent error classification and retry decision making
- Rate limiting and capacity-aware processing
- Comprehensive monitoring and metrics collection
- Dynamic configuration management
- Integration with existing automation components
"""

import logging
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Import existing automation components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger

from automation.retry_strategy_engine import (
    RetryStrategyEngine, RetryContext, ErrorCategory, ErrorSeverity,
    StrategyConfig, create_retry_strategy_engine
)
from automation.circuit_breaker_manager import (
    CircuitBreakerManager, CircuitBreakerConfig, FailureType,
    create_circuit_breaker_manager
)
from automation.retry_queue_processor import (
    RetryQueueProcessor, QueueProcessorConfig, QueueItem, QueueStatus,
    create_retry_queue_processor
)
from automation.enhanced_database_schema import (
    EnhancedDatabaseSchema, create_enhanced_schema_manager
)
from automation.capacity_manager import CapacityManager, create_capacity_manager
from automation.error_manager import ErrorManager, create_error_manager


@dataclass
class SmartRetryConfig:
    """Comprehensive configuration for smart retry system."""
    # Database configuration
    db_path: str = "src/python/data/automation_state.db"
    
    # Component configurations
    strategy_config: Optional[StrategyConfig] = None
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    queue_processor_config: Optional[QueueProcessorConfig] = None
    
    # Smart retry specific settings
    max_concurrent_retries: int = 5
    retry_batch_size: int = 10
    processing_interval: int = 60
    
    # Rate limiting
    rate_limit_requests_per_minute: int = 30
    rate_limit_window_size: int = 60
    
    # Capacity management
    capacity_threshold: int = 9
    capacity_check_interval: int = 30
    
    # Error classification
    transient_error_patterns: List[str] = None
    persistent_error_patterns: List[str] = None
    
    # Monitoring and metrics
    metrics_retention_hours: int = 24
    enable_detailed_logging: bool = True
    enable_performance_monitoring: bool = True
    
    # Integration settings
    integrate_with_existing_retry: bool = True
    integrate_with_capacity_manager: bool = True
    integrate_with_error_manager: bool = True
    
    def __post_init__(self):
        """Initialize default configurations."""
        if self.transient_error_patterns is None:
            self.transient_error_patterns = [
                "Connection timeout",
                "HTTP 503",
                "HTTP 502",
                "HTTP 504",
                "Network unreachable",
                "Temporary failure"
            ]
        
        if self.persistent_error_patterns is None:
            self.persistent_error_patterns = [
                "HTTP 400",
                "HTTP 401",
                "HTTP 403",
                "HTTP 404",
                "Invalid credentials",
                "Permission denied",
                "Validation error"
            ]


@dataclass
class RetryRequest:
    """Request for smart retry processing."""
    request_id: str
    region: str
    variable_type: str
    file_path: str
    error_message: str
    error_type: str
    attempt_number: int = 1
    max_attempts: int = 5
    priority: int = 5
    context_data: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


@dataclass
class SmartRetryResult:
    """Result of smart retry processing."""
    request_id: str
    success: bool
    action_taken: str
    retry_scheduled: bool
    next_retry_time: Optional[str]
    circuit_breaker_status: str
    eligibility_score: float
    success_probability: float
    processing_time: float
    error_message: Optional[str]
    metadata: Dict[str, Any]
    timestamp: str


class SmartRetryManager:
    """
    Main orchestration layer for the smart retry system that integrates
    all components for intelligent failure handling and retry processing.
    """
    
    def __init__(self, config: Optional[SmartRetryConfig] = None):
        """
        Initialize the Smart Retry Manager.
        
        Args:
            config: Configuration for smart retry system
        """
        self.config = config or SmartRetryConfig()
        self.logger = self._setup_logging()
        
        # Initialize database schema
        self.schema_manager = create_enhanced_schema_manager(self.config.db_path)
        self._ensure_enhanced_schema()
        
        # Initialize core components
        self.strategy_engine = create_retry_strategy_engine(
            self.config.db_path, 
            self.config.strategy_config
        )
        
        self.circuit_breaker_manager = create_circuit_breaker_manager(
            self.config.db_path,
            self.config.circuit_breaker_config
        )
        
        self.queue_processor = create_retry_queue_processor(
            self.config.db_path,
            self.config.queue_processor_config
        )
        
        # Initialize integration components if enabled
        self.capacity_manager = None
        self.error_manager = None
        
        if self.config.integrate_with_capacity_manager:
            try:
                self.capacity_manager = create_capacity_manager(db_path=self.config.db_path)
            except Exception as e:
                self.logger.warning(f"Could not initialize capacity manager: {e}")
        
        if self.config.integrate_with_error_manager:
            try:
                self.error_manager = create_error_manager(self.config.db_path)
            except Exception as e:
                self.logger.warning(f"Could not initialize error manager: {e}")
        
        # Processing state
        self.processing_active = False
        self.processing_thread = None
        
        # Rate limiting
        self.rate_limiter = self._create_rate_limiter()
        
        # Metrics and monitoring
        self.metrics = {
            'total_requests': 0,
            'successful_retries': 0,
            'failed_retries': 0,
            'circuit_breaker_blocks': 0,
            'rate_limit_blocks': 0,
            'capacity_blocks': 0,
            'average_processing_time': 0.0,
            'last_processing_time': None
        }
        
        # Threading
        self.manager_lock = threading.Lock()
        
        self.logger.info("Smart Retry Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('smart_retry.manager', level=logging.DEBUG)
    
    def _ensure_enhanced_schema(self):
        """Ensure enhanced database schema is created."""
        try:
            success = self.schema_manager.create_enhanced_tables()
            if success:
                self.logger.info("Enhanced database schema verified")
            else:
                self.logger.error("Failed to create enhanced database schema")
        except Exception as e:
            self.logger.error(f"Error ensuring enhanced schema: {e}")
    
    def _create_rate_limiter(self):
        """Create rate limiter for retry processing."""
        from collections import deque
        return {
            'window': deque(),
            'lock': threading.Lock()
        }
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows processing."""
        with self.rate_limiter['lock']:
            current_time = time.time()
            window_start = current_time - self.config.rate_limit_window_size
            
            # Remove old entries
            while (self.rate_limiter['window'] and 
                   self.rate_limiter['window'][0] < window_start):
                self.rate_limiter['window'].popleft()
            
            # Check if we can process
            if len(self.rate_limiter['window']) >= self.config.rate_limit_requests_per_minute:
                self.metrics['rate_limit_blocks'] += 1
                return False
            
            # Add current request
            self.rate_limiter['window'].append(current_time)
            return True
    
    def _classify_error(self, error_message: str, error_type: str) -> Tuple[ErrorCategory, ErrorSeverity]:
        """
        Classify error based on message and type.
        
        Args:
            error_message: Error message text
            error_type: Error type identifier
            
        Returns:
            Tuple of (ErrorCategory, ErrorSeverity)
        """
        error_message_lower = error_message.lower()
        error_type_lower = error_type.lower()
        
        # Check for transient errors
        for pattern in self.config.transient_error_patterns:
            if pattern.lower() in error_message_lower:
                return ErrorCategory.TRANSIENT, ErrorSeverity.MEDIUM
        
        # Check for persistent errors
        for pattern in self.config.persistent_error_patterns:
            if pattern.lower() in error_message_lower:
                return ErrorCategory.PERSISTENT, ErrorSeverity.HIGH
        
        # Classify by error type
        if 'timeout' in error_type_lower or 'timeout' in error_message_lower:
            return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM
        elif 'rate' in error_type_lower and 'limit' in error_type_lower:
            return ErrorCategory.RATE_LIMIT, ErrorSeverity.LOW
        elif 'auth' in error_type_lower or 'credential' in error_message_lower:
            return ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH
        elif 'validation' in error_type_lower or 'invalid' in error_message_lower:
            return ErrorCategory.VALIDATION, ErrorSeverity.HIGH
        elif 'resource' in error_type_lower or 'capacity' in error_message_lower:
            return ErrorCategory.RESOURCE, ErrorSeverity.MEDIUM
        elif 'system' in error_type_lower or 'internal' in error_message_lower:
            return ErrorCategory.SYSTEM, ErrorSeverity.HIGH
        
        # Default classification
        return ErrorCategory.TRANSIENT, ErrorSeverity.MEDIUM
    
    def _get_system_context(self) -> Dict[str, Any]:
        """Get current system context for retry decisions."""
        context = {
            'system_load': 0.5,  # Default
            'capacity_available': 10,  # Default
            'timestamp': datetime.now().isoformat()
        }
        
        # Get capacity information if available
        if self.capacity_manager:
            try:
                capacity_status = self.capacity_manager.get_current_capacity_status()
                context['system_load'] = min(capacity_status.total_requests / 10.0, 1.0)
                context['capacity_available'] = capacity_status.available_slots
            except Exception as e:
                self.logger.debug(f"Could not get capacity status: {e}")
        
        return context
    
    def process_retry_request(self, retry_request: RetryRequest) -> SmartRetryResult:
        """
        Process a single retry request through the smart retry system.
        
        Args:
            retry_request: Retry request to process
            
        Returns:
            Smart retry result with processing details
        """
        start_time = time.time()
        
        try:
            with self.manager_lock:
                self.metrics['total_requests'] += 1
            
            # Check rate limiting
            if not self._check_rate_limit():
                return SmartRetryResult(
                    request_id=retry_request.request_id,
                    success=False,
                    action_taken="rate_limited",
                    retry_scheduled=False,
                    next_retry_time=None,
                    circuit_breaker_status="unknown",
                    eligibility_score=0.0,
                    success_probability=0.0,
                    processing_time=time.time() - start_time,
                    error_message="Rate limit exceeded",
                    metadata={'rate_limit_hit': True},
                    timestamp=datetime.now().isoformat()
                )
            
            # Check circuit breaker
            can_execute = self.circuit_breaker_manager.can_execute_request(
                retry_request.region, "rda_api"
            )
            
            if not can_execute:
                self.metrics['circuit_breaker_blocks'] += 1
                return SmartRetryResult(
                    request_id=retry_request.request_id,
                    success=False,
                    action_taken="circuit_breaker_blocked",
                    retry_scheduled=False,
                    next_retry_time=None,
                    circuit_breaker_status="open",
                    eligibility_score=0.0,
                    success_probability=0.0,
                    processing_time=time.time() - start_time,
                    error_message="Circuit breaker is open",
                    metadata={'circuit_breaker_blocked': True},
                    timestamp=datetime.now().isoformat()
                )
            
            # Classify error
            error_category, error_severity = self._classify_error(
                retry_request.error_message, 
                retry_request.error_type
            )
            
            # Get system context
            system_context = self._get_system_context()
            
            # Create retry context
            retry_context = RetryContext(
                request_id=retry_request.request_id,
                error_type=retry_request.error_type,
                error_category=error_category,
                error_severity=error_severity,
                error_message=retry_request.error_message,
                attempt_number=retry_request.attempt_number,
                max_attempts=retry_request.max_attempts,
                region=retry_request.region,
                variable_type=retry_request.variable_type,
                file_path=retry_request.file_path,
                historical_success_rate=0.7,  # Could be calculated from history
                system_load=system_context['system_load'],
                capacity_available=system_context['capacity_available'],
                priority_level=retry_request.priority,
                metadata=retry_request.context_data
            )
            
            # Make retry decision
            retry_decision = self.strategy_engine.create_retry_decision(retry_context)
            
            if retry_decision.should_retry:
                # Create queue item
                queue_item = QueueItem(
                    original_request_id=retry_request.request_id,
                    queue_priority=retry_request.priority,
                    retry_attempt=retry_request.attempt_number,
                    max_retry_attempts=retry_request.max_attempts,
                    retry_strategy=retry_decision.strategy_used.value,
                    base_delay_seconds=60,  # From config
                    current_delay_seconds=retry_decision.delay_seconds,
                    next_retry_time=retry_decision.next_retry_time,
                    queue_status=QueueStatus.PENDING,
                    request_data=json.dumps({
                        'region': retry_request.region,
                        'variable_type': retry_request.variable_type,
                        'file_path': retry_request.file_path,
                        'error_message': retry_request.error_message,
                        'error_type': retry_request.error_type
                    }),
                    context_data=json.dumps(retry_request.context_data or {}),
                    region=retry_request.region,
                    variable_type=retry_request.variable_type,
                    file_path=retry_request.file_path,
                    eligibility_score=retry_decision.eligibility_score,
                    success_probability=retry_decision.success_probability,
                    last_error_message=retry_request.error_message,
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                )
                
                # Add to queue
                queue_success = self.queue_processor.add_to_queue(queue_item)
                
                if queue_success:
                    self.metrics['successful_retries'] += 1
                    action_taken = "retry_scheduled"
                else:
                    self.metrics['failed_retries'] += 1
                    action_taken = "queue_full"
                
                return SmartRetryResult(
                    request_id=retry_request.request_id,
                    success=queue_success,
                    action_taken=action_taken,
                    retry_scheduled=queue_success,
                    next_retry_time=retry_decision.next_retry_time if queue_success else None,
                    circuit_breaker_status="closed",
                    eligibility_score=retry_decision.eligibility_score,
                    success_probability=retry_decision.success_probability,
                    processing_time=time.time() - start_time,
                    error_message=None if queue_success else "Failed to add to queue",
                    metadata={
                        'retry_decision': asdict(retry_decision),
                        'system_context': system_context,
                        'error_classification': {
                            'category': error_category.value,
                            'severity': error_severity.value
                        }
                    },
                    timestamp=datetime.now().isoformat()
                )
            else:
                # Retry not recommended
                self.metrics['failed_retries'] += 1
                return SmartRetryResult(
                    request_id=retry_request.request_id,
                    success=False,
                    action_taken="retry_not_recommended",
                    retry_scheduled=False,
                    next_retry_time=None,
                    circuit_breaker_status="closed",
                    eligibility_score=retry_decision.eligibility_score,
                    success_probability=retry_decision.success_probability,
                    processing_time=time.time() - start_time,
                    error_message=retry_decision.reasoning,
                    metadata={
                        'retry_decision': asdict(retry_decision),
                        'system_context': system_context,
                        'error_classification': {
                            'category': error_category.value,
                            'severity': error_severity.value
                        }
                    },
                    timestamp=datetime.now().isoformat()
                )
                
        except Exception as e:
            self.logger.error(f"Error processing retry request {retry_request.request_id}: {e}")
            self.metrics['failed_retries'] += 1
            
            return SmartRetryResult(
                request_id=retry_request.request_id,
                success=False,
                action_taken="processing_error",
                retry_scheduled=False,
                next_retry_time=None,
                circuit_breaker_status="unknown",
                eligibility_score=0.0,
                success_probability=0.0,
                processing_time=time.time() - start_time,
                error_message=str(e),
                metadata={'processing_error': True},
                timestamp=datetime.now().isoformat()
            )
    
    def process_batch_retry_requests(self, retry_requests: List[RetryRequest]) -> List[SmartRetryResult]:
        """
        Process multiple retry requests in batch.
        
        Args:
            retry_requests: List of retry requests to process
            
        Returns:
            List of smart retry results
        """
        results = []
        
        self.logger.info(f"Processing batch of {len(retry_requests)} retry requests")
        
        for retry_request in retry_requests:
            try:
                result = self.process_retry_request(retry_request)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error processing retry request {retry_request.request_id}: {e}")
                results.append(SmartRetryResult(
                    request_id=retry_request.request_id,
                    success=False,
                    action_taken="batch_processing_error",
                    retry_scheduled=False,
                    next_retry_time=None,
                    circuit_breaker_status="unknown",
                    eligibility_score=0.0,
                    success_probability=0.0,
                    processing_time=0.0,
                    error_message=str(e),
                    metadata={'batch_processing_error': True},
                    timestamp=datetime.now().isoformat()
                ))
        
        successful_results = len([r for r in results if r.success])
        self.logger.info(f"Batch processing completed: {successful_results}/{len(results)} successful")
        
        return results
    
    def start_processing(self):
        """Start continuous retry processing."""
        if self.processing_active:
            self.logger.warning("Smart retry processing is already active")
            return
        
        def processing_loop():
            self.logger.info(f"Starting smart retry processing loop (interval: {self.config.processing_interval}s)")
            
            while self.processing_active:
                try:
                    # Start queue processor if not already running
                    if not self.queue_processor.processing_active:
                        self.queue_processor.start_processing()
                    
                    # Update metrics
                    with self.manager_lock:
                        self.metrics['last_processing_time'] = datetime.now().isoformat()
                    
                    # Wait for next cycle
                    time.sleep(self.config.processing_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in smart retry processing loop: {e}")
                    time.sleep(min(self.config.processing_interval, 60))
            
            self.logger.info("Smart retry processing loop stopped")
        
        self.processing_active = True
        self.processing_thread = threading.Thread(target=processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.logger.info("Smart retry processing started")
    
    def stop_processing(self):
        """Stop continuous retry processing."""
        if not self.processing_active:
            return
        
        self.logger.info("Stopping smart retry processing...")
        self.processing_active = False
        
        # Stop queue processor
        if self.queue_processor.processing_active:
            self.queue_processor.stop_processing()
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=10)
        
        self.logger.info("Smart retry processing stopped")
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            Dictionary containing system status information
        """
        try:
            # Get component statuses
            queue_status = self.queue_processor.get_queue_status()
            circuit_status = self.circuit_breaker_manager.get_circuit_status()
            strategy_stats = self.strategy_engine.get_strategy_statistics()
            
            # Get capacity status if available
            capacity_status = None
            if self.capacity_manager:
                try:
                    capacity_status = self.capacity_manager.get_current_capacity_status()
                except Exception as e:
                    self.logger.debug(f"Could not get capacity status: {e}")
            
            return {
                'smart_retry_manager': {
                    'processing_active': self.processing_active,
                    'metrics': self.metrics.copy(),
                    'configuration': asdict(self.config)
                },
                'queue_processor': queue_status,
                'circuit_breakers': circuit_status,
                'retry_strategies': strategy_stats,
                'capacity_manager': asdict(capacity_status) if capacity_status else None,
                'database_stats': self.schema_manager.get_database_statistics(),
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def record_retry_outcome(self, request_id: str, region: str, success: bool, 
                           response_time: float = 0.0, error_type: Optional[str] = None):
        """
        Record the outcome of a retry attempt for circuit breaker and metrics.
        
        Args:
            request_id: Request identifier
            region: Region for the request
            success: Whether the retry was successful
            response_time: Response time in seconds
            error_type: Type of error if failed
        """
        try:
            if success:
                self.circuit_breaker_manager.record_request_success(
                    region, "rda_api", response_time
                )
                self.logger.info(f"Recorded successful retry for {request_id} in {region}")
            else:
                failure_type = FailureType.UNKNOWN
                if error_type:
                    # Map error type to failure type
                    error_type_lower = error_type.lower()
                    if 'timeout' in error_type_lower:
                        failure_type = FailureType.TIMEOUT
                    elif 'connection' in error_type_lower:
                        failure_type = FailureType.CONNECTION_ERROR
                    elif 'server' in error_type_lower or '5' in error_type_lower:
                        failure_type = FailureType.SERVER_ERROR
                    elif 'rate' in error_type_lower:
                        failure_type = FailureType.RATE_LIMIT
                    elif 'auth' in error_type_lower:
                        failure_type = FailureType.AUTHENTICATION
                    elif 'validation' in error_type_lower:
                        failure_type = FailureType.VALIDATION
                
                self.circuit_breaker_manager.record_request_failure(
                    region, "rda_api", failure_type, response_time
                )
                self.logger.warning(f"Recorded failed retry for {request_id} in {region}: {error_type}")
                
        except Exception as e:
            self.logger.error(f"Error recording retry outcome: {e}")


def create_smart_retry_manager(config: Optional[SmartRetryConfig] = None) -> SmartRetryManager:
    """
    Factory function to create a Smart Retry Manager.
    
    Args:
        config: Configuration for smart retry system
        
    Returns:
        Configured SmartRetryManager instance
    """
    return SmartRetryManager(config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Smart Retry Manager')
    parser.add_argument('--start-processing', action='store_true',
                       help='Start continuous retry processing')
    parser.add_argument('--test-retry', action='store_true',
                       help='Test retry processing with sample request')
    parser.add_argument('--status', action='store_true',
                       help='Show system status')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Database path')
    
    args = parser.parse_args()
    
    # Create configuration
    config = SmartRetryConfig(db_path=args.db_path)
    
    # Create smart retry manager
    manager = create_smart_retry_manager(config)
    
    try:
        if args.start_processing:
            print("=== Starting Smart Retry Processing ===")
            manager.start_processing()
            
            # Keep running until interrupted
            try:
                while manager.processing_active:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping smart retry processing...")
                manager.stop_processing()
        
        elif args.test_retry:
            print("=== Testing Smart Retry ===")
            
            # Create test retry request
            test_request = RetryRequest(
                request_id="test_001",
                region="CISO",
                variable_type="dswrf",
                file_path="/path/to/test/file.ctl",
                error_message="HTTP 503: Service temporarily unavailable",
                error_type="HTTP_503",
                attempt_number=1,
                max_attempts=5,
                priority=3,
                context_data={'test': True}
            )
            
            # Process the request
            result = manager.process_retry_request(test_request)
            
            print(f"Retry Result:")
            print(f"  Success: {result.success}")
            print(f"  Action: {result.action_taken}")
            print(f"  Retry Scheduled: {result.retry_scheduled}")
            print(f"  Next Retry: {result.next_retry_time}")
            print(f"  Success Probability: {result.success_probability:.3f}")
            print(f"  Eligibility Score: {result.eligibility_score:.3f}")
            
        elif args.status:
            print("=== Smart Retry System Status ===")
            status = manager.get_system_status()
            print(json.dumps(status, indent=2))
        
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(manager, 'processing_active') and manager.processing_active:
            manager.stop_processing()