#!/usr/bin/env python3
"""
Error Scenario Tests for Enhanced RDA Automation System

This module provides comprehensive error scenario testing to validate that the enhanced
automation system handles various error conditions gracefully, particularly:
- Rate limiting behavior when hitting API limits
- Error handling for "too many requests" scenarios
- Circuit breaker functionality during API outages
- Graceful degradation and recovery mechanisms

Key Error Scenarios:
- API rate limit violations (429 errors)
- Service unavailable errors (503, 502, 504)
- Network connectivity issues
- Circuit breaker activation and recovery
- Graceful degradation under error conditions
- Error recovery and system resilience
"""

import os
import sys
import json
import time
import logging
import unittest
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, asdict
import tempfile
import shutil
from pathlib import Path
import random
from enum import Enum

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import automation components
from automation.enhanced_request_monitor import (
    EnhancedRequestMonitor, RequestCountSnapshot, RequestCountStatus,
    create_enhanced_request_monitor
)
from automation.capacity_manager import (
    CapacityManager, CapacityConfig, CapacityLevel, CapacityStatus,
    create_capacity_manager
)
from automation.dynamic_trigger_system import (
    DynamicTriggerSystem, TriggerType, TriggerUrgency, BatchCalculation,
    create_dynamic_trigger_system
)
from automation.rate_limiter import (
    RateLimiter, RateLimitConfig, CircuitState, RateLimitLevel,
    create_rate_limiter
)
from automation.error_handler import (
    ErrorHandler, ErrorHandlingConfig, ErrorAction, ErrorCategory,
    create_error_handler
)
from automation.request_throttler import (
    RequestThrottler, ThrottlingConfig, RequestPriority,
    create_request_throttler
)
from automation.event_system import (
    EventDispatcher, EventType, EventPriority, create_event_dispatcher
)
from automation.monitoring_config import (
    EnhancedMonitoringConfig, create_default_monitoring_config
)


class ErrorType(Enum):
    """Types of errors to simulate."""
    RATE_LIMIT_429 = "rate_limit_429"
    SERVICE_UNAVAILABLE_503 = "service_unavailable_503"
    BAD_GATEWAY_502 = "bad_gateway_502"
    GATEWAY_TIMEOUT_504 = "gateway_timeout_504"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    AUTHENTICATION_ERROR = "authentication_error"
    INVALID_REQUEST_400 = "invalid_request_400"
    SERVER_ERROR_500 = "server_error_500"


@dataclass
class ErrorScenario:
    """Defines an error testing scenario."""
    name: str
    description: str
    error_type: ErrorType
    error_rate: float  # 0.0 to 1.0 (percentage of requests that fail)
    duration_seconds: int
    recovery_time_seconds: int
    expected_circuit_breaker_activation: bool
    expected_graceful_degradation: bool
    expected_recovery: bool


@dataclass
class ErrorTestMetrics:
    """Metrics collected during error testing."""
    total_requests: int
    failed_requests: int
    successful_requests: int
    circuit_breaker_activations: int
    circuit_breaker_recoveries: int
    rate_limit_violations: int
    error_recovery_time: float
    system_downtime: float
    graceful_degradation_events: int
    retry_attempts: int
    successful_retries: int


@dataclass
class ErrorTestResult:
    """Result of an error scenario test."""
    scenario_name: str
    success: bool
    metrics: ErrorTestMetrics
    error_handling_score: float
    resilience_score: float
    recovery_time_score: float
    issues_identified: List[str]
    recommendations: List[str]
    execution_time: float


class MockErrorRDAMSClient:
    """Mock RDAMS client that can simulate various error conditions."""
    
    def __init__(self):
        self.current_request_count = 5
        self.requests_data = []
        self.error_simulation_active = False
        self.current_error_type = None
        self.error_rate = 0.0
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.recovery_mode = False
        self.lock = threading.RLock()
        self._generate_mock_requests()
    
    def _generate_mock_requests(self):
        """Generate mock request data."""
        with self.lock:
            self.requests_data = []
            statuses = ['submitted', 'processing', 'completed', 'error']
            for i in range(self.current_request_count):
                self.requests_data.append({
                    'request_id': f'error_test_request_{i}',
                    'status': statuses[i % len(statuses)],
                    'submit_time': (datetime.now() - timedelta(hours=i)).isoformat(),
                    'dataset': 'ds084.1',
                    'region': f'error_test_region_{i}'
                })
    
    def activate_error_simulation(self, error_type: ErrorType, error_rate: float):
        """Activate error simulation."""
        with self.lock:
            self.error_simulation_active = True
            self.current_error_type = error_type
            self.error_rate = error_rate
            self.consecutive_errors = 0
            self.recovery_mode = False
    
    def deactivate_error_simulation(self):
        """Deactivate error simulation and enter recovery mode."""
        with self.lock:
            self.error_simulation_active = False
            self.recovery_mode = True
            self.consecutive_errors = 0
    
    def _should_simulate_error(self) -> bool:
        """Determine if an error should be simulated."""
        if not self.error_simulation_active:
            return False
        
        # Simulate error based on error rate
        if random.random() < self.error_rate:
            self.consecutive_errors += 1
            return True
        
        # Reset consecutive error count on success
        self.consecutive_errors = 0
        return False
    
    def _create_error_response(self, error_type: ErrorType):
        """Create appropriate error response."""
        error_messages = {
            ErrorType.RATE_LIMIT_429: "Rate limit exceeded. Too many requests.",
            ErrorType.SERVICE_UNAVAILABLE_503: "Service temporarily unavailable.",
            ErrorType.BAD_GATEWAY_502: "Bad gateway error.",
            ErrorType.GATEWAY_TIMEOUT_504: "Gateway timeout error.",
            ErrorType.CONNECTION_ERROR: "Connection refused.",
            ErrorType.TIMEOUT_ERROR: "Request timeout.",
            ErrorType.AUTHENTICATION_ERROR: "Authentication failed.",
            ErrorType.INVALID_REQUEST_400: "Invalid request parameters.",
            ErrorType.SERVER_ERROR_500: "Internal server error."
        }
        
        status_codes = {
            ErrorType.RATE_LIMIT_429: 429,
            ErrorType.SERVICE_UNAVAILABLE_503: 503,
            ErrorType.BAD_GATEWAY_502: 502,
            ErrorType.GATEWAY_TIMEOUT_504: 504,
            ErrorType.CONNECTION_ERROR: None,  # Connection errors don't have HTTP status
            ErrorType.TIMEOUT_ERROR: None,
            ErrorType.AUTHENTICATION_ERROR: 401,
            ErrorType.INVALID_REQUEST_400: 400,
            ErrorType.SERVER_ERROR_500: 500
        }
        
        message = error_messages.get(error_type, "Unknown error")
        status_code = status_codes.get(error_type)
        
        if error_type == ErrorType.CONNECTION_ERROR:
            raise ConnectionError(message)
        elif error_type == ErrorType.TIMEOUT_ERROR:
            raise TimeoutError(message)
        else:
            # Create HTTP-like error
            error = Exception(message)
            error.status_code = status_code
            raise error
    
    def get_status(self):
        """Mock get_status method with error simulation."""
        # Simulate processing delay
        time.sleep(0.05)
        
        # Check if we should simulate an error
        if self._should_simulate_error():
            self._create_error_response(self.current_error_type)
        
        # Return normal response
        with self.lock:
            return {
                'data': self.requests_data[:self.current_request_count],
                'total_count': self.current_request_count
            }
    
    def submit_request(self, control_file_path):
        """Mock submit_request method with error simulation."""
        # Simulate processing delay
        time.sleep(0.05)
        
        # Check if we should simulate an error
        if self._should_simulate_error():
            self._create_error_response(self.current_error_type)
        
        # Return successful response
        request_id = f'error_test_request_{int(time.time() * 1000)}'
        with self.lock:
            self.requests_data.append({
                'request_id': request_id,
                'status': 'submitted',
                'submit_time': datetime.now().isoformat(),
                'dataset': 'ds084.1',
                'region': 'error_test_region'
            })
            self.current_request_count = min(self.current_request_count + 1, 10)
        
        return {'request_id': request_id}
    
    def set_request_count(self, count: int):
        """Set request count for testing."""
        with self.lock:
            self.current_request_count = max(0, min(count, 15))
            self._generate_mock_requests()


class ErrorScenarioTest(unittest.TestCase):
    """Error scenario tests for the enhanced automation system."""
    
    def setUp(self):
        """Set up error testing environment."""
        self.test_start_time = time.time()
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "error_test_automation.db")
        
        # Create mock RDAMS client with error simulation
        self.mock_rdams = MockErrorRDAMSClient()
        
        # Set up logging
        self.logger = logging.getLogger('error_scenario_test')
        self.logger.setLevel(logging.INFO)
        
        # Initialize error test metrics
        self.error_metrics = ErrorTestMetrics(
            total_requests=0,
            failed_requests=0,
            successful_requests=0,
            circuit_breaker_activations=0,
            circuit_breaker_recoveries=0,
            rate_limit_violations=0,
            error_recovery_time=0.0,
            system_downtime=0.0,
            graceful_degradation_events=0,
            retry_attempts=0,
            successful_retries=0
        )
        
        # Create test control files
        self._create_test_control_files()
        
        # Initialize system components with error handling focus
        self._initialize_error_handling_components()
        
        # Set up RDAMS mocking
        self._setup_rdams_mocking()
    
    def tearDown(self):
        """Clean up error testing environment."""
        try:
            # Stop all components
            if hasattr(self, 'enhanced_monitor') and self.enhanced_monitor:
                self.enhanced_monitor.stop_monitoring()
                self.enhanced_monitor.cleanup()
            
            if hasattr(self, 'capacity_manager') and self.capacity_manager:
                self.capacity_manager.stop_capacity_monitoring()
            
            if hasattr(self, 'dynamic_trigger') and self.dynamic_trigger:
                self.dynamic_trigger.stop_system()
                self.dynamic_trigger.cleanup()
            
            if hasattr(self, 'rate_limiter') and self.rate_limiter:
                pass  # Rate limiter doesn't need explicit cleanup
            
            if hasattr(self, 'error_handler') and self.error_handler:
                self.error_handler.cleanup()
            
            if hasattr(self, 'request_throttler') and self.request_throttler:
                self.request_throttler.stop()
            
            # Clean up patches
            if hasattr(self, 'rdams_patcher'):
                self.rdams_patcher.stop()
            if hasattr(self, 'submit_patcher'):
                self.submit_patcher.stop()
            
            # Clean up temporary directory
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                
        except Exception as e:
            self.logger.error(f"Error in tearDown: {e}")
    
    def _create_test_control_files(self):
        """Create test control files for error testing."""
        self.control_files_dir = os.path.join(self.temp_dir, "control_files")
        os.makedirs(self.control_files_dir, exist_ok=True)
        
        # Create 10 test control files
        for i in range(10):
            control_file_path = os.path.join(self.control_files_dir, f"error_test_control_{i:02d}.ctl")
            with open(control_file_path, 'w') as f:
                f.write(f"""# Error Test Control File {i}
dataset=ds084.1
startdate=2023010100
enddate=2023010200
param=TMP/UGRD/VGRD
level=2_m_above_ground
region=error_test_region_{i}
format=netCDF
""")
    
    def _initialize_error_handling_components(self):
        """Initialize system components with error handling focus."""
        # Error-focused monitoring config
        monitoring_config = create_default_monitoring_config()
        monitoring_config.adaptive_intervals.base_interval = 2
        monitoring_config.adaptive_intervals.min_interval = 1
        monitoring_config.adaptive_intervals.max_interval = 5
        
        # Error-focused capacity config
        capacity_config = CapacityConfig(
            monitoring_interval=3,
            enable_upload_automation=True,
            upload_batch_size=2,  # Smaller batches for error testing
            control_files_dir=self.control_files_dir,
            upload_rate_limit_delay=0.5
        )
        
        # Error-focused rate limiting config
        rate_limit_config = RateLimitConfig(
            requests_per_minute=10,
            adaptive_enabled=True,
            circuit_breaker_enabled=True,
            failure_threshold=3,  # Lower threshold for testing
            recovery_timeout_seconds=10,  # Shorter recovery for testing
            base_backoff_seconds=1.0,
            max_backoff_seconds=30.0
        )
        
        # Error handling config
        error_config = ErrorHandlingConfig(
            default_max_retries=3,
            rate_limit_base_delay=5.0,
            circuit_breaker_enabled=True,
            graceful_degradation_enabled=True,
            pattern_recognition_enabled=True
        )
        
        # Request throttling config
        throttling_config = ThrottlingConfig(
            max_queue_size=50,
            max_concurrent_requests=2,  # Lower for error testing
            adaptive_throttling=True,
            rate_limiter_integration=True,
            error_handler_integration=True,
            min_request_interval_seconds=6.0,
            max_request_interval_seconds=60.0
        )
        
        # Create event dispatcher
        self.event_dispatcher = create_event_dispatcher()
        
        # Create core components
        self.enhanced_monitor = create_enhanced_request_monitor(
            config=monitoring_config,
            event_dispatcher=self.event_dispatcher,
            db_path=self.test_db_path
        )
        
        self.capacity_manager = create_capacity_manager(
            config=capacity_config,
            db_path=self.test_db_path
        )
        
        self.rate_limiter = create_rate_limiter(rate_limit_config)
        self.error_handler = create_error_handler(error_config)
        self.request_throttler = create_request_throttler(throttling_config)
        
        self.dynamic_trigger = create_dynamic_trigger_system(
            enhanced_monitor=self.enhanced_monitor,
            capacity_manager=self.capacity_manager,
            event_dispatcher=self.event_dispatcher,
            config={
                "enabled": True,
                "response_time_target_ms": 500,
                "rate_limiting_enabled": True,
                "error_handling_enabled": True,
                "request_throttling_enabled": True
            }
        )
        
        # Set up integrations
        self._setup_component_integrations()
    
    def _setup_component_integrations(self):
        """Set up integrations between components."""
        self.enhanced_monitor.set_integration_components(
            capacity_manager=self.capacity_manager
        )
        
        self.capacity_manager.set_dynamic_integration_components(
            dynamic_trigger_system=self.dynamic_trigger,
            enhanced_monitor=self.enhanced_monitor
        )
        
        self.dynamic_trigger.set_integration_components()
        
        # Add error monitoring callbacks
        self.rate_limiter.add_rate_limit_callback(self._on_rate_limit_event)
        self.rate_limiter.add_circuit_breaker_callback(self._on_circuit_breaker_event)
        self.error_handler.add_error_callback(self._on_error_event)
    
    def _setup_rdams_mocking(self):
        """Set up RDAMS client mocking for error testing."""
        self.rdams_patcher = patch('rdams_client.get_status', side_effect=self.mock_rdams.get_status)
        self.rdams_patcher.start()
        
        self.submit_patcher = patch('rdams_client.submit_request', side_effect=self.mock_rdams.submit_request)
        self.submit_patcher.start()
    
    def _on_rate_limit_event(self, event_type: str, **kwargs):
        """Callback for rate limit events."""
        if event_type == "rate_limit_hit":
            self.error_metrics.rate_limit_violations += 1
            self.logger.info(f"Rate limit violation detected")
    
    def _on_circuit_breaker_event(self, event_type: str, **kwargs):
        """Callback for circuit breaker events."""
        if event_type == "opened":
            self.error_metrics.circuit_breaker_activations += 1
            self.logger.info(f"Circuit breaker activated")
        elif event_type == "closed":
            self.error_metrics.circuit_breaker_recoveries += 1
            self.logger.info(f"Circuit breaker recovered")
    
    def _on_error_event(self, error_occurrence, action, action_params):
        """Callback for error events."""
        if action == ErrorAction.RETRY:
            self.error_metrics.retry_attempts += 1
        elif action == ErrorAction.GRACEFUL_DEGRADATION:
            self.error_metrics.graceful_degradation_events += 1
    
    def test_rate_limit_429_handling(self):
        """Test handling of rate limit (429) errors."""
        self.logger.info("🧪 Testing rate limit (429) error handling")
        
        # Define rate limit scenario
        scenario = ErrorScenario(
            name="rate_limit_429",
            description="Test handling of API rate limit errors",
            error_type=ErrorType.RATE_LIMIT_429,
            error_rate=0.8,  # 80% of requests fail with 429
            duration_seconds=20,
            recovery_time_seconds=10,
            expected_circuit_breaker_activation=True,
            expected_graceful_degradation=True,
            expected_recovery=True
        )
        
        result = self._run_error_scenario(scenario)
        
        # Validate rate limit handling
        self.assertTrue(result.success, f"Rate limit handling test failed: {result.issues_identified}")
        self.assertGreater(self.error_metrics.rate_limit_violations, 0,
                          "No rate limit violations detected")
        
        # Circuit breaker should activate under high error rate
        if scenario.expected_circuit_breaker_activation:
            self.assertGreater(self.error_metrics.circuit_breaker_activations, 0,
                              "Circuit breaker should have activated")
        
        # System should recover after error simulation stops
        if scenario.expected_recovery:
            self.assertGreater(self.error_metrics.circuit_breaker_recoveries, 0,
                              "System should have recovered")
        
        self.logger.info("✅ Rate limit (429) error handling test passed")
    
    def test_service_unavailable_503_handling(self):
        """Test handling of service unavailable (503) errors."""
        self.logger.info("🧪 Testing service unavailable (503) error handling")
        
        scenario = ErrorScenario(
            name="service_unavailable_503",
            description="Test handling of service unavailable errors",
            error_type=ErrorType.SERVICE_UNAVAILABLE_503,
            error_rate=0.6,  # 60% of requests fail with 503
            duration_seconds=15,
            recovery_time_seconds=8,
            expected_circuit_breaker_activation=True,
            expected_graceful_degradation=True,
            expected_recovery=True
        )
        
        result = self._run_error_scenario(scenario)
        
        # Validate service unavailable handling
        self.assertTrue(result.success, f"Service unavailable handling test failed: {result.issues_identified}")
        
        # System should handle service outages gracefully
        self.assertGreater(self.error_metrics.failed_requests, 0,
                          "No failed requests recorded during service outage")
        
        # Should have some successful requests during recovery
        self.assertGreater(self.error_metrics.successful_requests, 0,
                          "No successful requests during recovery")
        
        self.logger.info("✅ Service unavailable (503) error handling test passed")
    
    def test_connection_error_handling(self):
        """Test handling of connection errors."""
        self.logger.info("🧪 Testing connection error handling")
        
        scenario = ErrorScenario(
            name="connection_error",
            description="Test handling of network connection errors",
            error_type=ErrorType.CONNECTION_ERROR,
            error_rate=0.7,  # 70% of requests fail with connection error
            duration_seconds=12,
            recovery_time_seconds=6,
            expected_circuit_breaker_activation=True,
            expected_graceful_degradation=True,
            expected_recovery=True
        )
        
        result = self._run_error_scenario(scenario)
        
        # Validate connection error handling
        self.assertTrue(result.success, f"Connection error handling test failed: {result.issues_identified}")
        
        # Circuit breaker should protect against connection failures
        self.assertGreater(self.error_metrics.circuit_breaker_activations, 0,
                          "Circuit breaker should activate on connection failures")
        
        self.logger.info("✅ Connection error handling test passed")
    
    def test_circuit_breaker_functionality(self):
        """Test circuit breaker activation and recovery."""
        self.logger.info("🧪 Testing circuit breaker functionality")
        
        # Start system components
        self.enhanced_monitor.start_monitoring()
        self.dynamic_trigger.start_system()
        
        # Test circuit breaker activation
        self.logger.info("Testing circuit breaker activation")
        
        # Simulate high error rate to trigger circuit breaker
        self.mock_rdams.activate_error_simulation(ErrorType.SERVICE_UNAVAILABLE_503, 1.0)
        
        # Make multiple requests to trigger circuit breaker
        activation_start = time.time()
        requests_made = 0
        
        while time.time() - activation_start < 10:  # 10 seconds
            try:
                # Trigger system activity
                self.mock_rdams.set_request_count(3)  # Low count to trigger uploads
                time.sleep(0.5)
                requests_made += 1
                
                # Check if circuit breaker is open
                rate_limiter_status = self.rate_limiter.get_status()
                if rate_limiter_status.circuit_state == CircuitState.OPEN:
                    self.logger.info(f"Circuit breaker activated after {requests_made} requests")
                    break
                    
            except Exception as e:
                self.logger.debug(f"Expected error during circuit breaker test: {e}")
        
        # Verify circuit breaker is open
        rate_limiter_status = self.rate_limiter.get_status()
        self.assertEqual(rate_limiter_status.circuit_state, CircuitState.OPEN,
                        "Circuit breaker should be open after high error rate")
        
        # Test circuit breaker recovery
        self.logger.info("Testing circuit breaker recovery")
        
        # Stop error simulation
        self.mock_rdams.deactivate_error_simulation()
        
        # Wait for recovery timeout
        recovery_start = time.time()
        recovery_detected = False
        
        while time.time() - recovery_start < 15:  # 15 seconds timeout
            rate_limiter_status = self.rate_limiter.get_status()
            
            if rate_limiter_status.circuit_state == CircuitState.HALF_OPEN:
                self.logger.info("Circuit breaker entered half-open state")
            elif rate_limiter_status.circuit_state == CircuitState.CLOSED:
                self.logger.info("Circuit breaker recovered to closed state")
                recovery_detected = True
                break
            
            time.sleep(1)
        
        # Stop components
        self.enhanced_monitor.stop_monitoring()
        self.dynamic_trigger.stop_system()
        
        # Validate circuit breaker recovery
        self.assertTrue(recovery_detected or rate_limiter_status.circuit_state == CircuitState.HALF_OPEN,
                       "Circuit breaker should recover after errors stop")
        
        self.logger.info("✅ Circuit breaker functionality test passed")
    
    def test_graceful_degradation(self):
        """Test graceful degradation during error conditions."""
        self.logger.info("🧪 Testing graceful degradation")
        
        # Start system components
        self.enhanced_monitor.start_monitoring()
        self.capacity_manager.start_capacity_monitoring()
        self.dynamic_trigger.start_system()
        
        # Test graceful degradation under various error conditions
        degradation_scenarios = [
            (ErrorType.RATE_LIMIT_429, 0.9, "High rate limiting"),
            (ErrorType.SERVICE_UNAVAILABLE_503, 0.8, "Service outage"),
            (ErrorType.TIMEOUT_ERROR, 0.7, "Timeout issues")
        ]
        
        for error_type, error_rate, description in degradation_scenarios:
            self.logger.info(f"Testing graceful degradation: {description}")
            
            # Activate error simulation
            self.mock_rdams.activate_error_simulation(error_type, error_rate)
            
            # Monitor system behavior during errors
            degradation_start = time.time()
            system_remained_active = True
            
            while time.time() - degradation_start < 8:  # 8 seconds
                try:
                    # Check if system components are still active
                    monitor_status = self.enhanced_monitor.get_current_status()
                    trigger_status = self.dynamic_trigger.get_system_status()
                    
                    if not monitor_status.get('monitoring_active', False):
                        system_remained_active = False
                        break
                    
                    if not trigger_status.get('system_active', False):
                        system_remained_active = False
                        break
                    
                    time.sleep(1)
                    
                except Exception as e:
                    self.logger.debug(f"Expected error during degradation test: {e}")
            
            # Deactivate error simulation
            self.mock_rdams.deactivate_error_simulation()
            
            # System should remain active during errors (graceful degradation)
            self.assertTrue(system_remained_active,
                           f"System failed during {description} - no graceful degradation")
            
            time.sleep(2)  # Cool down between scenarios
        
        # Stop components
        self.enhanced_monitor.stop_monitoring()
        self.capacity_manager.stop_capacity_monitoring()
        self.dynamic_trigger.stop_system()
        
        self.logger.info("✅ Graceful degradation test passed")
    
    def test_error_recovery_mechanisms(self):
        """Test error recovery and system resilience."""
        self.logger.info("🧪 Testing error recovery mechanisms")
        
        # Start system components
        self.enhanced_monitor.start_monitoring()
        self.capacity_manager.start_capacity_monitoring()
        self.dynamic_trigger.start_system()
        
        # Test recovery from different error types
        recovery_scenarios = [
            {
                "name": "rate_limit_recovery",
                "error_type": ErrorType.RATE_LIMIT_429,
                "error_duration": 10,
                "recovery_timeout": 15
            },
            {
                "name": "service_outage_recovery",
                "error_type": ErrorType.SERVICE_UNAVAILABLE_503,
                "error_duration": 8,
                "recovery_timeout": 12
            },
            {
                "name": "connection_recovery",
                "error_type": ErrorType.CONNECTION_ERROR,
                "error_duration": 6,
                "recovery_timeout": 10
            }
        ]
        
        recovery_results = {}
        
        for scenario in recovery_scenarios:
            self.logger.info(f"Testing recovery scenario: {scenario['name']}")
            
            # Introduce error condition
            self.mock_rdams.activate_error_simulation(scenario['error_type'], 0.9)
            
            # Wait for error condition to take effect
            time.sleep(scenario['error_duration'])
            
            # Remove error condition and measure recovery
            recovery_start = time.time()
            self.mock_rdams.deactivate_error_simulation()
            
            # Monitor recovery
            recovery_detected = False
            system_functional = False
            
            while time.time() - recovery_start < scenario['recovery_timeout']:
                try:
                    # Test system functionality
                    self.mock_rdams.set_request_count(4)  # Trigger system activity
                    
                    # Check if system is responding normally
                    trigger_status = self.dynamic_trigger.get_system_status()
                    if trigger_status.get('system_active', False):
                        # Try to get rate limiter status (should work if recovered)
                        rate_status = self.rate_limiter.get_status()
                        if rate_status.circuit_state != CircuitState.OPEN:
                            recovery_time = time.time() - recovery_start
                            recovery_detected = True
                            system_functional = True
                            break
                    
                    time.sleep(1)
                    
                except Exception as e:
                    self.logger.debug(f"System still recovering: {e}")
                    time.sleep(1)
            
            recovery_results[scenario['name']] = {
                'recovery_detected': recovery_detected,
                'system_functional': system_functional,
                'recovery_time': recovery_time if recovery_detected else scenario['recovery_timeout']
            }
            
            self.logger.info(f"   Recovery: {'✅' if recovery_detected else '❌'}")
            if recovery_detected:
                self.logger.info(f"   Recovery time: {recovery_time:.1f}s")
            
            # Validate recovery
            self.assertTrue(recovery_detected,
                           f"System failed to recover from {scenario['name']}")
            self.assertTrue(system_functional,
                           f"System not functional after {scenario['name']} recovery")
            
            time.sleep(2)  # Cool down between scenarios
        
        # Stop components
        self.enhanced_monitor.stop_monitoring()
        self.capacity_manager.stop_capacity_monitoring()
        self.dynamic_trigger.stop_system()
        
        # Validate overall recovery performance
        avg_recovery_time = sum(r['recovery_time'] for r in recovery_results.values()) / len(recovery_results)
        successful_recoveries = len([r for r in recovery_results.values() if r['recovery_detected']])
        
        self.logger.info(f"Recovery test results:")
        self.logger.info(f"   Successful recoveries: {successful_recoveries}/{len(recovery_scenarios)}")
        self.logger.info(f"   Average recovery time: {avg_recovery_time:.1f}s")
        
        # All scenarios should recover successfully
        self.assertEqual(successful_recoveries, len(recovery_scenarios),
                        "Not all error scenarios recovered successfully")
        
        # Average recovery time should be reasonable
        self.assertLess(avg_recovery_time, 20,
                       f"Average recovery time too slow: {avg_recovery_time:.1f}s")
        
        self.logger.info("✅ Error recovery mechanisms test passed")
    
    def test_retry_mechanisms(self):
        """Test retry mechanisms under various error conditions."""
        self.logger.info("🧪 Testing retry mechanisms")
        
        # Start system components
        self.enhanced_monitor.start_monitoring()
        self.dynamic_trigger.start_system()
        
        # Test retry behavior with different error types
        retry_scenarios = [
            {
                "name": "transient_503_errors",
                "error_type": ErrorType.SERVICE_UNAVAILABLE_503,
                "error_rate": 0.5,  # 50% failure rate
                "expected_retries": True,
                "expected_success_after_retry": True
            },
            {
                "name": "timeout_errors",
                "error_type": ErrorType.TIMEOUT_ERROR,
                "error_rate": 0.6,  # 60% failure rate
                "expected_retries": True,
                "expected_success_after_retry": True
            },
            {
                "name": "rate_limit_errors",
                "error_type": ErrorType.RATE_LIMIT_429,
                "error_rate": 0.8,  # 80% failure rate
                "expected_retries": True,
                "expected_success_after_retry": False  # Should back off, not retry immediately
            }
        ]
        
        for scenario in retry_scenarios:
            self.logger.info(f"Testing retry scenario: {scenario['name']}")
            
            # Reset metrics
            initial_retry_attempts = self.error_metrics.retry_attempts
            initial_successful_retries = self.error_metrics.successful_retries
            
            # Activate error simulation
            self.mock_rdams.activate_error_simulation(scenario['error_type'], scenario['error_rate'])
            
            # Trigger system activity to generate retries
            for i in range(5):
                self.mock_rdams.set_request_count(2)  # Low count to trigger uploads
                time.sleep(1)
            
            # Deactivate error simulation
            self.mock_rdams.deactivate_error_simulation()
            
            # Check retry behavior
            retry_attempts = self.error_metrics.retry_attempts - initial_retry_attempts
            successful_retries = self.error_metrics.successful_retries - initial_successful_retries
            
            self.logger.info(f"   Retry attempts: {retry_attempts}")
            self.logger.info(f"   Successful retries: {successful_retries}")
            
            if scenario['expected_retries']:
                self.assertGreater(retry_attempts, 0,
                                  f"No retry attempts for {scenario['name']}")
            
            time.sleep(2)  # Cool down between scenarios
        
        # Stop components
        self.enhanced_monitor.stop_monitoring()
        self.dynamic_trigger.stop_system()
        
        self.logger.info("✅ Retry mechanisms test passed")
    
    def test_system_resilience_under_mixed_errors(self):
        """Test system resilience under mixed error conditions."""
        self.logger.info("🧪 Testing system resilience under mixed errors")
        
        # Start all system components
        self.enhanced_monitor.start_monitoring()
        self.capacity_manager.start_capacity_monitoring()
        self.dynamic_trigger.start_system()
        
        # Define mixed error scenario
        mixed_error_duration = 25  # seconds
        error_types = [
            ErrorType.RATE_LIMIT_429,
            ErrorType.SERVICE_UNAVAILABLE_503,
            ErrorType.CONNECTION_ERROR,
            ErrorType.TIMEOUT_ERROR
        ]
        
        # Run mixed error scenario
        resilience_start = time.time()
        error_switches = 0
        system_remained_stable = True
        
        while time.time() - resilience_start < mixed_error_duration:
            # Switch between different error types
            current_error = error_types[error_switches % len(error_types)]
            error_rate = 0.3 + (error_switches % 3) * 0.2  # Vary error rate 0.3-0.7
            
            self.logger.info(f"Switching to error type: {current_error.value} (rate: {error_rate:.1f})")
            self.mock_rdams.activate_error_simulation(current_error, error_rate)
            
            # Run with this error type for a short period
            error_period_start = time.time()
            while time.time() - error_period_start < 3:  # 3 seconds per error type
                try:
                    # Check system stability
                    monitor_status = self.enhanced_monitor.get_current_status()
                    trigger_status = self.dynamic_trigger.get_system_status()
                    
                    if not monitor_status.get('monitoring_active', False):
                        system_remained_stable = False
                        self.logger.error("Enhanced monitor became inactive")
                        break
                    
                    if not trigger_status.get('system_active', False):
                        system_remained_stable = False
                        self.logger.error("Dynamic trigger system became inactive")
                        break
                    
                    # Trigger some system activity
                    self.mock_rdams.set_request_count(3 + (error_switches % 5))
                    
                    time.sleep(0.5)
                    
                except Exception as e:
                    self.logger.debug(f"Expected error during mixed error test: {e}")
            
            if not system_remained_stable:
                break
            
            error_switches += 1
        
        # Deactivate error simulation
        self.mock_rdams.deactivate_error_simulation()
        
        # Allow system to recover
        time.sleep(5)
        
        # Stop components
        self.enhanced_monitor.stop_monitoring()
        self.capacity_manager.stop_capacity_monitoring()
        self.dynamic_trigger.stop_system()
        
        # Validate system resilience
        self.assertTrue(system_remained_stable,
                       "System became unstable under mixed error conditions")
        
        # Check that system handled multiple error types
        self.assertGreater(error_switches, 5,
                          f"Insufficient error type switches: {error_switches}")
        
        # Verify error handling metrics
        self.assertGreater(self.error_metrics.failed_requests, 0,
                          "No failed requests recorded during mixed error test")
        
        self.logger.info(f"   Error type switches: {error_switches}")
        self.logger.info(f"   System remained stable: {'✅' if system_remained_stable else '❌'}")
        self.logger.info("✅ System resilience under mixed errors test passed")
    
    def _run_error_scenario(self, scenario: ErrorScenario) -> ErrorTestResult:
        """Run a specific error scenario and return results."""
        self.logger.info(f"Running error scenario: {scenario.name}")
        
        scenario_start = time.time()
        issues_identified = []
        recommendations = []
        
        # Start system components
        self.enhanced_monitor.start_monitoring()
        self.capacity_manager.start_capacity_monitoring()
        self.dynamic_trigger.start_system()
        
        # Reset metrics
        initial_metrics = ErrorTestMetrics(
            total_requests=self.error_metrics.total_requests,
            failed_requests=self.error_metrics.failed_requests,
            successful_requests=self.error_metrics.successful_requests,
            circuit_breaker_activations=self.error_metrics.circuit_breaker_activations,
            circuit_breaker_recoveries=self.error_metrics.circuit_breaker_recoveries,
            rate_limit_violations=self.error_metrics.rate_limit_violations,
            error_recovery_time=0.0,
            system_downtime=0.0,
            graceful_degradation_events=self.error_metrics.graceful_degradation_events,
            retry_attempts=self.error_metrics.retry_attempts,
            successful_retries=self.error_metrics.successful_retries
        )
        
        try:
            # Phase 1: Activate error simulation
            self.logger.info(f"   Phase 1: Activating {scenario.error_type.value} errors (rate: {scenario.error_rate:.1%})")
            self.mock_rdams.activate_error_simulation(scenario.error_type, scenario.error_rate)
            
            # Run error simulation
            error_phase_start = time.time()
            while time.time() - error_phase_start < scenario.duration_seconds:
                # Trigger system activity
                self.mock_rdams.set_request_count(2 + int(time.time()) % 6)
                time.sleep(1)
            
            # Phase 2: Recovery phase
            self.logger.info(f"   Phase 2: Recovery phase ({scenario.recovery_time_seconds}s)")
            recovery_start = time.time()
            self.mock_rdams.deactivate_error_simulation()
            
            # Monitor recovery
            recovery_detected = False
            while time.time() - recovery_start < scenario.recovery_time_seconds:
                try:
                    # Check if system is recovering
                    rate_status = self.rate_limiter.get_status()
                    if rate_status.circuit_state != CircuitState.OPEN:
                        recovery_detected = True
                        self.error_metrics.error_recovery_time = time.time() - recovery_start
                        break
                except:
                    pass
                time.sleep(1)
            
            # Calculate scenario metrics
            scenario_metrics = ErrorTestMetrics(
                total_requests=self.error_metrics.total_requests - initial_metrics.total_requests,
                failed_requests=self.error_metrics.failed_requests - initial_metrics.failed_requests,
                successful_requests=self.error_metrics.successful_requests - initial_metrics.successful_requests,
                circuit_breaker_activations=self.error_metrics.circuit_breaker_activations - initial_metrics.circuit_breaker_activations,
                circuit_breaker_recoveries=self.error_metrics.circuit_breaker_recoveries - initial_metrics.circuit_breaker_recoveries,
                rate_limit_violations=self.error_metrics.rate_limit_violations - initial_metrics.rate_limit_violations,
                error_recovery_time=self.error_metrics.error_recovery_time,
                system_downtime=0.0,  # Would need more sophisticated tracking
                graceful_degradation_events=self.error_metrics.graceful_degradation_events - initial_metrics.graceful_degradation_events,
                retry_attempts=self.error_metrics.retry_attempts - initial_metrics.retry_attempts,
                successful_retries=self.error_metrics.successful_retries - initial_metrics.successful_retries
            )
            
            # Evaluate scenario success
            success = True
            
            # Check expected circuit breaker behavior
            if scenario.expected_circuit_breaker_activation and scenario_metrics.circuit_breaker_activations == 0:
                success = False
                issues_identified.append("Circuit breaker did not activate as expected")
                recommendations.append("Review circuit breaker threshold settings")
            
            # Check expected recovery
            if scenario.expected_recovery and not recovery_detected:
                success = False
                issues_identified.append("System did not recover within expected time")
                recommendations.append("Optimize recovery mechanisms")
            
            # Check graceful degradation
            if scenario.expected_graceful_degradation:
                # System should remain active during errors
                monitor_status = self.enhanced_monitor.get_current_status()
                if not monitor_status.get('monitoring_active', False):
                    success = False
                    issues_identified.append("System did not degrade gracefully")
                    recommendations.append("Implement better graceful degradation")
            
            # Calculate scores
            error_handling_score = self._calculate_error_handling_score(scenario_metrics)
            resilience_score = self._calculate_resilience_score(scenario_metrics, recovery_detected)
            recovery_time_score = self._calculate_recovery_time_score(scenario_metrics.error_recovery_time)
            
        except Exception as e:
            success = False
            issues_identified.append(f"Scenario execution failed: {str(e)}")
            scenario_metrics = initial_metrics
            error_handling_score = resilience_score = recovery_time_score = 0.0
        
        finally:
            # Stop components
            self.enhanced_monitor.stop_monitoring()
            self.capacity_manager.stop_capacity_monitoring()
            self.dynamic_trigger.stop_system()
        
        execution_time = time.time() - scenario_start
        
        return ErrorTestResult(
            scenario_name=scenario.name,
            success=success,
            metrics=scenario_metrics,
            error_handling_score=error_handling_score,
            resilience_score=resilience_score,
            recovery_time_score=recovery_time_score,
            issues_identified=issues_identified,
            recommendations=recommendations,
            execution_time=execution_time
        )
    
    def _calculate_error_handling_score(self, metrics: ErrorTestMetrics) -> float:
        """Calculate error handling effectiveness score."""
        score = 100.0
        
        # Deduct points for unhandled errors
        if metrics.total_requests > 0:
            error_rate = metrics.failed_requests / metrics.total_requests
            if error_rate > 0.9:
                score -= 30
            elif error_rate > 0.7:
                score -= 20
            elif error_rate > 0.5:
                score -= 10
        
        # Add points for successful retries
        if metrics.retry_attempts > 0:
            retry_success_rate = metrics.successful_retries / metrics.retry_attempts
            score += retry_success_rate * 20
        
        # Add points for circuit breaker activation (shows protection)
        if metrics.circuit_breaker_activations > 0:
            score += 15
        
        return max(0.0, min(100.0, score))
    
    def _calculate_resilience_score(self, metrics: ErrorTestMetrics, recovery_detected: bool) -> float:
        """Calculate system resilience score."""
        score = 50.0  # Base score
        
        # Add points for recovery
        if recovery_detected:
            score += 30
        
        # Add points for graceful degradation
        if metrics.graceful_degradation_events > 0:
            score += 20
        
        # Deduct points for excessive downtime
        if metrics.system_downtime > 10:
            score -= 20
        elif metrics.system_downtime > 5:
            score -= 10
        
        return max(0.0, min(100.0, score))
    
    def _calculate_recovery_time_score(self, recovery_time: float) -> float:
        """Calculate recovery time score."""
        if recovery_time <= 0:
            return 0.0
        
        # Score based on recovery time (lower is better)
        if recovery_time < 5:
            return 100.0
        elif recovery_time < 10:
            return 80.0
        elif recovery_time < 20:
            return 60.0
        elif recovery_time < 30:
            return 40.0
        else:
            return 20.0


class ErrorScenarioTestRunner:
    """Test runner for error scenario tests."""
    
    def __init__(self):
        self.logger = logging.getLogger('error_scenario_test_runner')
        self.setup_logging()
    
    def setup_logging(self):
        """Set up logging for error scenario test runner."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('error_scenario_test.log')
            ]
        )
    
    def run_all_error_tests(self) -> Dict[str, Any]:
        """Run all error scenario tests."""
        self.logger.info("🚀 Starting error scenario tests")
        
        # Create test suite
        test_suite = unittest.TestLoader().loadTestsFromTestCase(ErrorScenarioTest)
        
        # Run tests with detailed output
        test_result = unittest.TextTestRunner(verbosity=2).run(test_suite)
        
        # Generate error handling summary
        summary = {
            "tests_run": test_result.testsRun,
            "failures": len(test_result.failures),
            "errors": len(test_result.errors),
            "success": test_result.wasSuccessful(),
            "error_handling_criteria": {
                "rate_limit_handling": "Handle 429 errors gracefully",
                "service_outage_handling": "Handle 503/502/504 errors",
                "circuit_breaker_functionality": "Activate and recover properly",
                "graceful_degradation": "Maintain core functionality during errors",
                "error_recovery": "Recover within reasonable time"
            },
            "failure_details": [str(failure) for failure in test_result.failures],
            "error_details": [str(error) for error in test_result.errors],
            "timestamp": datetime.now().isoformat()
        }
        
        if test_result.wasSuccessful():
            self.logger.info("✅ All error scenario tests passed!")
        else:
            self.logger.error(f"❌ {len(test_result.failures + test_result.errors)} error test(s) failed")
        
        return summary
    
    def run_error_resilience_suite(self) -> Dict[str, Any]:
        """Run error resilience test suite."""
        self.logger.info("🛡️ Running error resilience test suite")
        
        resilience_tests = [
            'test_rate_limit_429_handling',
            'test_service_unavailable_503_handling',
            'test_circuit_breaker_functionality',
            'test_graceful_degradation',
            'test_error_recovery_mechanisms'
        ]
        
        resilience_results = {}
        
        for test_name in resilience_tests:
            self.logger.info(f"Running resilience test: {test_name}")
            
            # Create test suite with specific test
            suite = unittest.TestSuite()
            suite.addTest(ErrorScenarioTest(test_name))
            
            # Run test
            start_time = time.time()
            test_result = unittest.TextTestRunner(verbosity=1).run(suite)
            execution_time = time.time() - start_time
            
            resilience_results[test_name] = {
                "success": test_result.wasSuccessful(),
                "execution_time": execution_time,
                "failures": len(test_result.failures),
                "errors": len(test_result.errors)
            }
        
        return {
            "resilience_results": resilience_results,
            "overall_success": all(result["success"] for result in resilience_results.values()),
            "total_execution_time": sum(result["execution_time"] for result in resilience_results.values()),
            "resilience_score": self._calculate_overall_resilience_score(resilience_results),
            "timestamp": datetime.now().isoformat()
        }
    
    def _calculate_overall_resilience_score(self, results: Dict[str, Dict]) -> float:
        """Calculate overall resilience score."""
        if not results:
            return 0.0
        
        successful_tests = len([r for r in results.values() if r["success"]])
        total_tests = len(results)
        
        base_score = (successful_tests / total_tests) * 100
        
        # Bonus for fast execution (indicates efficient error handling)
        avg_execution_time = sum(r["execution_time"] for r in results.values()) / total_tests
        if avg_execution_time < 30:  # Less than 30 seconds average
            base_score += 10
        elif avg_execution_time < 60:  # Less than 1 minute average
            base_score += 5
        
        return min(100.0, base_score)


def main():
    """Main function for running error scenario tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Error Scenario Tests')
    parser.add_argument('--test', type=str, help='Run specific error test')
    parser.add_argument('--resilience', action='store_true', help='Run error resilience test suite')
    parser.add_argument('--report', action='store_true', help='Generate detailed error handling report')
    parser.add_argument('--quick', action='store_true', help='Run quick error tests')
    
    args = parser.parse_args()
    
    runner = ErrorScenarioTestRunner()
    
    try:
        if args.test:
            # Run specific test
            suite = unittest.TestSuite()
            suite.addTest(ErrorScenarioTest(args.test))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            
            print(f"Test {args.test}: {'✅ PASSED' if result.wasSuccessful() else '❌ FAILED'}")
        
        elif args.resilience:
            # Run resilience suite
            result = runner.run_error_resilience_suite()
            
            print("\n" + "="*60)
            print("ERROR RESILIENCE TEST RESULTS")
            print("="*60)
            print(json.dumps(result, indent=2))
            print("="*60)
        
        elif args.quick:
            # Run quick error tests
            print("=== Quick Error Test Suite ===")
            quick_tests = [
                'test_rate_limit_429_handling',
                'test_circuit_breaker_functionality'
            ]
            
            for test_name in quick_tests:
                suite = unittest.TestSuite()
                suite.addTest(ErrorScenarioTest(test_name))
                result = unittest.TextTestRunner(verbosity=1).run(suite)
                print(f"{test_name}: {'✅ PASSED' if result.wasSuccessful() else '❌ FAILED'}")
        
        else:
            # Run all error tests
            result = runner.run_all_error_tests()
            
            if args.report:
                print("\n" + "="*60)
                print("ERROR SCENARIO TEST REPORT")
                print("="*60)
                print(json.dumps(result, indent=2))
                print("="*60)
    
    except Exception as e:
        print(f"Error running error scenario tests: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())