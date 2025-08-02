#!/usr/bin/env python3
"""
Circuit Breaker Manager for Smart Retry System

This module implements circuit breaker patterns to handle persistent failures
and prevent cascading failures in the RDA automation system. It monitors
failure patterns and automatically opens/closes circuits based on configurable
thresholds and recovery conditions.

Key Features:
- Multiple circuit breaker states (CLOSED, OPEN, HALF_OPEN)
- Configurable failure thresholds and recovery conditions
- Regional and service-specific circuit breakers
- Automatic recovery testing and state transitions
- Integration with retry system for failure prevention
- Comprehensive monitoring and alerting
"""

import time
import logging
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation, requests allowed
    OPEN = "open"           # Circuit is open, requests blocked
    HALF_OPEN = "half_open" # Testing recovery, limited requests allowed


class FailureType(Enum):
    """Types of failures tracked by circuit breaker."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    SERVER_ERROR = "server_error"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    UNKNOWN = "unknown"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5          # Failures before opening circuit
    recovery_timeout: int = 60          # Seconds before attempting recovery
    success_threshold: int = 3          # Successes needed to close circuit
    half_open_max_calls: int = 5        # Max calls allowed in half-open state
    failure_rate_threshold: float = 0.5 # Failure rate threshold (0.0-1.0)
    min_calls_threshold: int = 10       # Minimum calls before rate calculation
    sliding_window_size: int = 100      # Size of sliding window for metrics
    timeout_duration: int = 30          # Request timeout in seconds
    enabled: bool = True                # Enable/disable circuit breaker


@dataclass
class CircuitMetrics:
    """Metrics for circuit breaker monitoring."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    failure_rate: float = 0.0
    average_response_time: float = 0.0
    last_failure_time: Optional[str] = None
    last_success_time: Optional[str] = None
    state_change_count: int = 0
    time_in_open_state: float = 0.0
    recovery_attempts: int = 0


@dataclass
class CircuitEvent:
    """Event record for circuit breaker state changes."""
    circuit_id: str
    event_type: str
    old_state: CircuitState
    new_state: CircuitState
    trigger_reason: str
    metrics_snapshot: CircuitMetrics
    timestamp: str
    metadata: Dict[str, Any]


class CircuitBreaker:
    """
    Individual circuit breaker implementation with state management
    and failure tracking.
    """
    
    def __init__(self, circuit_id: str, config: CircuitBreakerConfig):
        """
        Initialize circuit breaker.
        
        Args:
            circuit_id: Unique identifier for this circuit
            config: Configuration for circuit behavior
        """
        self.circuit_id = circuit_id
        self.config = config
        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        
        # State management
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = time.time()
        self.half_open_calls = 0
        
        # Sliding window for failure rate calculation
        self.call_results = deque(maxlen=config.sliding_window_size)
        self.response_times = deque(maxlen=config.sliding_window_size)
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Event callbacks
        self.state_change_callbacks: List[Callable] = []
    
    def add_state_change_callback(self, callback: Callable):
        """Add callback for state change events."""
        self.state_change_callbacks.append(callback)
    
    def _notify_state_change(self, old_state: CircuitState, new_state: CircuitState, reason: str):
        """Notify callbacks of state changes."""
        event = CircuitEvent(
            circuit_id=self.circuit_id,
            event_type="state_change",
            old_state=old_state,
            new_state=new_state,
            trigger_reason=reason,
            metrics_snapshot=self.metrics,
            timestamp=datetime.now().isoformat(),
            metadata={}
        )
        
        for callback in self.state_change_callbacks:
            try:
                callback(event)
            except Exception as e:
                # Don't let callback errors affect circuit breaker
                pass
    
    def _update_metrics(self, success: bool, response_time: float = 0.0):
        """Update circuit metrics with call result."""
        self.metrics.total_calls += 1
        
        if success:
            self.metrics.successful_calls += 1
            self.metrics.last_success_time = datetime.now().isoformat()
        else:
            self.metrics.failed_calls += 1
            self.metrics.last_failure_time = datetime.now().isoformat()
        
        # Update sliding window
        self.call_results.append(success)
        self.response_times.append(response_time)
        
        # Calculate failure rate
        if len(self.call_results) >= self.config.min_calls_threshold:
            failures = sum(1 for result in self.call_results if not result)
            self.metrics.failure_rate = failures / len(self.call_results)
        
        # Calculate average response time
        if self.response_times:
            self.metrics.average_response_time = sum(self.response_times) / len(self.response_times)
    
    def _should_open_circuit(self) -> bool:
        """Determine if circuit should be opened based on failures."""
        # Check failure count threshold
        if self.failure_count >= self.config.failure_threshold:
            return True
        
        # Check failure rate threshold
        if (len(self.call_results) >= self.config.min_calls_threshold and
            self.metrics.failure_rate >= self.config.failure_rate_threshold):
            return True
        
        return False
    
    def _should_attempt_reset(self) -> bool:
        """Determine if circuit should attempt reset from OPEN to HALF_OPEN."""
        if self.state != CircuitState.OPEN:
            return False
        
        if self.last_failure_time is None:
            return True
        
        time_since_failure = time.time() - self.last_failure_time
        return time_since_failure >= self.config.recovery_timeout
    
    def _should_close_circuit(self) -> bool:
        """Determine if circuit should be closed from HALF_OPEN."""
        return (self.state == CircuitState.HALF_OPEN and 
                self.success_count >= self.config.success_threshold)
    
    def _transition_to_open(self, reason: str):
        """Transition circuit to OPEN state."""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.last_state_change = time.time()
        self.metrics.state_change_count += 1
        self._notify_state_change(old_state, self.state, reason)
    
    def _transition_to_half_open(self, reason: str):
        """Transition circuit to HALF_OPEN state."""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_state_change = time.time()
        self.metrics.state_change_count += 1
        self.metrics.recovery_attempts += 1
        self._notify_state_change(old_state, self.state, reason)
    
    def _transition_to_closed(self, reason: str):
        """Transition circuit to CLOSED state."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_state_change = time.time()
        self.metrics.state_change_count += 1
        self._notify_state_change(old_state, self.state, reason)
    
    def can_execute(self) -> bool:
        """
        Check if a request can be executed through this circuit.
        
        Returns:
            True if request can proceed, False if circuit is open
        """
        if not self.config.enabled:
            return True
        
        with self.lock:
            # Check if we should attempt reset from OPEN
            if self._should_attempt_reset():
                self._transition_to_half_open("Recovery timeout reached")
            
            # Handle different states
            if self.state == CircuitState.CLOSED:
                return True
            elif self.state == CircuitState.OPEN:
                # Track time in open state
                if self.last_failure_time:
                    self.metrics.time_in_open_state += time.time() - self.last_failure_time
                return False
            elif self.state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open state
                if self.half_open_calls < self.config.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False
        
        return False
    
    def record_success(self, response_time: float = 0.0):
        """
        Record a successful call through the circuit.
        
        Args:
            response_time: Response time in seconds
        """
        with self.lock:
            self.success_count += 1
            self.failure_count = max(0, self.failure_count - 1)  # Decay failure count
            self._update_metrics(True, response_time)
            
            # Check if we should close the circuit
            if self._should_close_circuit():
                self._transition_to_closed("Success threshold reached")
    
    def record_failure(self, failure_type: FailureType = FailureType.UNKNOWN, 
                      response_time: float = 0.0):
        """
        Record a failed call through the circuit.
        
        Args:
            failure_type: Type of failure that occurred
            response_time: Response time in seconds
        """
        with self.lock:
            self.failure_count += 1
            self.success_count = 0  # Reset success count on failure
            self.last_failure_time = time.time()
            self._update_metrics(False, response_time)
            
            # Check if we should open the circuit
            if self.state == CircuitState.CLOSED and self._should_open_circuit():
                self._transition_to_open(f"Failure threshold reached: {failure_type.value}")
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens the circuit
                self._transition_to_open(f"Failure during recovery: {failure_type.value}")
    
    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state
    
    def get_metrics(self) -> CircuitMetrics:
        """Get current circuit metrics."""
        with self.lock:
            return self.metrics
    
    def reset(self):
        """Manually reset circuit to CLOSED state."""
        with self.lock:
            self._transition_to_closed("Manual reset")
    
    def force_open(self, reason: str = "Manual override"):
        """Manually force circuit to OPEN state."""
        with self.lock:
            self._transition_to_open(reason)


class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers with regional and service-specific
    circuit management capabilities.
    """
    
    def __init__(self, db_path: str = "./data/automation_state.db",
                 default_config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker manager.
        
        Args:
            db_path: Path to SQLite database
            default_config: Default configuration for new circuits
        """
        self.db_path = db_path
        self.default_config = default_config or CircuitBreakerConfig()
        self.logger = self._setup_logging()
        
        # Circuit storage
        self.circuits: Dict[str, CircuitBreaker] = {}
        self.circuit_configs: Dict[str, CircuitBreakerConfig] = {}
        
        # Event storage
        self.events: List[CircuitEvent] = []
        self.max_events = 1000
        
        # Threading
        self.manager_lock = threading.Lock()
        
        # Initialize database
        self._initialize_database()
        
        self.logger.info("Circuit Breaker Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the circuit breaker manager."""
        logger = logging.getLogger('smart_retry.circuit_breaker')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_database(self):
        """Initialize database tables for circuit breaker data."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Circuit breaker state table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS circuit_breaker_state (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        circuit_id TEXT UNIQUE NOT NULL,
                        current_state TEXT NOT NULL,
                        failure_count INTEGER DEFAULT 0,
                        success_count INTEGER DEFAULT 0,
                        last_failure_time TEXT,
                        last_success_time TEXT,
                        total_calls INTEGER DEFAULT 0,
                        successful_calls INTEGER DEFAULT 0,
                        failed_calls INTEGER DEFAULT 0,
                        failure_rate REAL DEFAULT 0.0,
                        average_response_time REAL DEFAULT 0.0,
                        state_change_count INTEGER DEFAULT 0,
                        time_in_open_state REAL DEFAULT 0.0,
                        recovery_attempts INTEGER DEFAULT 0,
                        config_data TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Circuit breaker events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS circuit_breaker_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        circuit_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        old_state TEXT,
                        new_state TEXT,
                        trigger_reason TEXT,
                        metrics_snapshot TEXT,
                        metadata TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_circuit_state_id 
                    ON circuit_breaker_state(circuit_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_circuit_events_id 
                    ON circuit_breaker_events(circuit_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_circuit_events_time 
                    ON circuit_breaker_events(created_at)
                """)
                
                conn.commit()
                self.logger.debug("Circuit breaker database tables initialized")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing circuit breaker database: {e}")
            raise
    
    def _event_callback(self, event: CircuitEvent):
        """Callback for circuit breaker state change events."""
        try:
            # Store event in memory
            self.events.append(event)
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events:]
            
            # Store event in database
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO circuit_breaker_events (
                        circuit_id, event_type, old_state, new_state,
                        trigger_reason, metrics_snapshot, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.circuit_id,
                    event.event_type,
                    event.old_state.value,
                    event.new_state.value,
                    event.trigger_reason,
                    json.dumps(asdict(event.metrics_snapshot)),
                    json.dumps(event.metadata)
                ))
                conn.commit()
            
            # Log significant events
            if event.event_type == "state_change":
                if event.new_state == CircuitState.OPEN:
                    self.logger.warning(f"🔴 Circuit {event.circuit_id} OPENED: {event.trigger_reason}")
                elif event.new_state == CircuitState.CLOSED:
                    self.logger.info(f"🟢 Circuit {event.circuit_id} CLOSED: {event.trigger_reason}")
                elif event.new_state == CircuitState.HALF_OPEN:
                    self.logger.info(f"🟡 Circuit {event.circuit_id} HALF-OPEN: {event.trigger_reason}")
                    
        except Exception as e:
            self.logger.error(f"Error handling circuit breaker event: {e}")
    
    def get_or_create_circuit(self, circuit_id: str, 
                             config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Get existing circuit or create new one.
        
        Args:
            circuit_id: Unique identifier for circuit
            config: Optional custom configuration
            
        Returns:
            CircuitBreaker instance
        """
        with self.manager_lock:
            if circuit_id not in self.circuits:
                # Use provided config or default
                circuit_config = config or self.default_config
                
                # Create new circuit
                circuit = CircuitBreaker(circuit_id, circuit_config)
                circuit.add_state_change_callback(self._event_callback)
                
                # Store circuit and config
                self.circuits[circuit_id] = circuit
                self.circuit_configs[circuit_id] = circuit_config
                
                # Persist to database
                self._persist_circuit_state(circuit)
                
                self.logger.info(f"Created new circuit breaker: {circuit_id}")
            
            return self.circuits[circuit_id]
    
    def _persist_circuit_state(self, circuit: CircuitBreaker):
        """Persist circuit state to database."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                metrics = circuit.get_metrics()
                config = self.circuit_configs.get(circuit.circuit_id, self.default_config)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO circuit_breaker_state (
                        circuit_id, current_state, failure_count, success_count,
                        last_failure_time, last_success_time, total_calls,
                        successful_calls, failed_calls, failure_rate,
                        average_response_time, state_change_count,
                        time_in_open_state, recovery_attempts, config_data,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    circuit.circuit_id,
                    circuit.get_state().value,
                    circuit.failure_count,
                    circuit.success_count,
                    metrics.last_failure_time,
                    metrics.last_success_time,
                    metrics.total_calls,
                    metrics.successful_calls,
                    metrics.failed_calls,
                    metrics.failure_rate,
                    metrics.average_response_time,
                    metrics.state_change_count,
                    metrics.time_in_open_state,
                    metrics.recovery_attempts,
                    json.dumps(asdict(config))
                ))
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"Error persisting circuit state: {e}")
    
    def get_circuit_for_region(self, region: str, 
                              config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Get circuit breaker for a specific region.
        
        Args:
            region: Region identifier
            config: Optional custom configuration
            
        Returns:
            CircuitBreaker instance for the region
        """
        circuit_id = f"region_{region}"
        return self.get_or_create_circuit(circuit_id, config)
    
    def get_circuit_for_service(self, service: str, region: Optional[str] = None,
                               config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Get circuit breaker for a specific service.
        
        Args:
            service: Service identifier
            region: Optional region for service-specific circuit
            config: Optional custom configuration
            
        Returns:
            CircuitBreaker instance for the service
        """
        if region:
            circuit_id = f"service_{service}_region_{region}"
        else:
            circuit_id = f"service_{service}"
        
        return self.get_or_create_circuit(circuit_id, config)
    
    def can_execute_request(self, region: str, service: str = "rda_api") -> bool:
        """
        Check if a request can be executed based on circuit breaker states.
        
        Args:
            region: Region for the request
            service: Service for the request
            
        Returns:
            True if request can proceed, False if blocked by circuit breaker
        """
        try:
            # Check region-specific circuit
            region_circuit = self.get_circuit_for_region(region)
            if not region_circuit.can_execute():
                self.logger.debug(f"Request blocked by region circuit: {region}")
                return False
            
            # Check service-specific circuit
            service_circuit = self.get_circuit_for_service(service, region)
            if not service_circuit.can_execute():
                self.logger.debug(f"Request blocked by service circuit: {service} in {region}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking circuit breaker state: {e}")
            # Fail open - allow request if there's an error
            return True
    
    def record_request_success(self, region: str, service: str = "rda_api", 
                              response_time: float = 0.0):
        """
        Record successful request for circuit breaker tracking.
        
        Args:
            region: Region for the request
            service: Service for the request
            response_time: Response time in seconds
        """
        try:
            # Record success for region circuit
            region_circuit = self.get_circuit_for_region(region)
            region_circuit.record_success(response_time)
            
            # Record success for service circuit
            service_circuit = self.get_circuit_for_service(service, region)
            service_circuit.record_success(response_time)
            
            # Persist state changes
            self._persist_circuit_state(region_circuit)
            self._persist_circuit_state(service_circuit)
            
        except Exception as e:
            self.logger.error(f"Error recording request success: {e}")
    
    def record_request_failure(self, region: str, service: str = "rda_api",
                              failure_type: FailureType = FailureType.UNKNOWN,
                              response_time: float = 0.0):
        """
        Record failed request for circuit breaker tracking.
        
        Args:
            region: Region for the request
            service: Service for the request
            failure_type: Type of failure
            response_time: Response time in seconds
        """
        try:
            # Record failure for region circuit
            region_circuit = self.get_circuit_for_region(region)
            region_circuit.record_failure(failure_type, response_time)
            
            # Record failure for service circuit
            service_circuit = self.get_circuit_for_service(service, region)
            service_circuit.record_failure(failure_type, response_time)
            
            # Persist state changes
            self._persist_circuit_state(region_circuit)
            self._persist_circuit_state(service_circuit)
            
        except Exception as e:
            self.logger.error(f"Error recording request failure: {e}")
    
    def get_circuit_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all circuit breakers.
        
        Returns:
            Dictionary containing circuit breaker status information
        """
        try:
            status = {
                'total_circuits': len(self.circuits),
                'circuits_by_state': defaultdict(int),
                'circuit_details': {},
                'recent_events': [],
                'summary': {
                    'healthy_circuits': 0,
                    'degraded_circuits': 0,
                    'failed_circuits': 0,
                    'total_calls': 0,
                    'total_failures': 0,
                    'overall_failure_rate': 0.0
                },
                'generated_at': datetime.now().isoformat()
            }
            
            total_calls = 0
            total_failures = 0
            
            for circuit_id, circuit in self.circuits.items():
                state = circuit.get_state()
                metrics = circuit.get_metrics()
                
                # Count by state
                status['circuits_by_state'][state.value] += 1
                
                # Categorize health
                if state == CircuitState.CLOSED and metrics.failure_rate < 0.1:
                    status['summary']['healthy_circuits'] += 1
                elif state == CircuitState.HALF_OPEN or (state == CircuitState.CLOSED and metrics.failure_rate < 0.5):
                    status['summary']['degraded_circuits'] += 1
                else:
                    status['summary']['failed_circuits'] += 1
                
                # Aggregate metrics
                total_calls += metrics.total_calls
                total_failures += metrics.failed_calls
                
                # Circuit details
                status['circuit_details'][circuit_id] = {
                    'state': state.value,
                    'metrics': asdict(metrics),
                    'config': asdict(self.circuit_configs.get(circuit_id, self.default_config))
                }
            
            # Calculate overall failure rate
            if total_calls > 0:
                status['summary']['overall_failure_rate'] = total_failures / total_calls
            
            status['summary']['total_calls'] = total_calls
            status['summary']['total_failures'] = total_failures
            
            # Recent events
            status['recent_events'] = [
                asdict(event) for event in self.events[-10:]
            ]
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting circuit status: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def reset_circuit(self, circuit_id: str) -> bool:
        """
        Manually reset a circuit breaker to CLOSED state.
        
        Args:
            circuit_id: ID of circuit to reset
            
        Returns:
            True if reset successful, False otherwise
        """
        try:
            if circuit_id in self.circuits:
                circuit = self.circuits[circuit_id]
                circuit.reset()
                self._persist_circuit_state(circuit)
                self.logger.info(f"Circuit {circuit_id} manually reset")
                return True
            else:
                self.logger.warning(f"Circuit {circuit_id} not found for reset")
                return False
                
        except Exception as e:
            self.logger.error(f"Error resetting circuit {circuit_id}: {e}")
            return False
    
    def reset_all_circuits(self) -> int:
        """
        Reset all circuit breakers to CLOSED state.
        
        Returns:
            Number of circuits reset
        """
        reset_count = 0
        for circuit_id in list(self.circuits.keys()):
            if self.reset_circuit(circuit_id):
                reset_count += 1
        
        self.logger.info(f"Reset {reset_count} circuit breakers")
        return reset_count


def create_circuit_breaker_manager(db_path: str = "./data/automation_state.db",
                                  config: Optional[CircuitBreakerConfig] = None) -> CircuitBreakerManager:
    """
    Factory function to create a Circuit Breaker Manager.
    
    Args:
        db_path: Path to SQLite database
        config: Default configuration for circuit breakers
        
    Returns:
        Configured CircuitBreakerManager instance
    """
    return CircuitBreakerManager(db_path, config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Circuit Breaker Manager')
    parser.add_argument('--test-circuit', action='store_true',
                       help='Test circuit breaker functionality')
    parser.add_argument('--status', action='store_true',
                       help='Show circuit breaker status')
    parser.add_argument('--reset-all', action='store_true',
                       help='Reset all circuit breakers')
    parser.add_argument('--db-path', default='./data/automation_state.db',
                       help='Database path')
    
    args = parser.parse_args()
    
    # Create circuit breaker manager
    manager = create_circuit_breaker_manager(args.db_path)
    
    try:
        if args.test_circuit:
            print("=== Testing Circuit Breaker ===")
            
            # Test circuit for CISO region
            region = "CISO"
            circuit = manager.get_circuit_for_region(region)
            
            print(f"Initial state: {circuit.get_state().value}")
            
            # Simulate failures
            for i in range(6):
                manager.record_request_failure(region, failure_type=FailureType.SERVER_ERROR)
                print(f"After failure {i+1}: {circuit.get_state().value}")
            
            # Try to execute (should be blocked)
            can_execute = manager.can_execute_request(region)
            print(f"Can execute request: {can_execute}")
            
            # Wait and test recovery
            time.sleep(2)
            if circuit.get_state() == CircuitState.HALF_OPEN:
                # Simulate success
                manager.record_request_success(region)
                print(f"After success: {circuit.get_state().value}")
            
        elif args.status:
            print("=== Circuit Breaker Status ===")
            status = manager.get_circuit_status()
            print(json.dumps(status, indent=2))
            
        elif args.reset_all:
            print("=== Resetting All Circuit Breakers ===")
            reset_count = manager.reset_all_circuits()
            print(f"Reset {reset_count} circuit breakers")
            
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")