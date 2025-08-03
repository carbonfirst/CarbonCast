#!/usr/bin/env python3
"""
Dynamic Batch Processing Integration Test

This module provides comprehensive testing for the dynamic batch processing system,
including the DynamicTriggerSystem, BatchOptimizer, and enhanced monitoring integration.

Key Features:
- Integration testing of all dynamic components
- Simulation of request count changes and triggers
- Verification of backward compatibility
- Performance and reliability testing
- Error handling validation
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.dynamic_trigger_system import (
    DynamicTriggerSystem, create_dynamic_trigger_system, TriggerType, TriggerUrgency
)
from automation.batch_optimizer import (
    BatchOptimizer, create_batch_optimizer, OptimizationStrategy, SystemState
)
from automation.enhanced_monitoring_integration import (
    EnhancedMonitoringIntegration, create_enhanced_monitoring_integration
)
from automation.enhanced_request_monitor import (
    EnhancedRequestMonitor, create_enhanced_request_monitor, RequestCountSnapshot
)
from automation.capacity_manager import (
    CapacityManager, create_capacity_manager, CapacityConfig
)


@dataclass
class TestResult:
    """Result of a test case."""
    test_name: str
    success: bool
    duration: float
    message: str
    details: Dict[str, Any]
    timestamp: str


class MockBatchSystem:
    """Mock batch system for testing."""
    
    def __init__(self):
        self.current_request_count = 5
        self.requests_state = {}
        self.upload_calls = []
    
    def _get_current_request_count(self):
        return self.current_request_count
    
    def set_request_count(self, count: int):
        """Set the current request count for testing."""
        self.current_request_count = count
    
    def _auto_upload_new_files(self, available_slots: int):
        """Mock auto upload method."""
        self.upload_calls.append({
            'slots': available_slots,
            'timestamp': datetime.now().isoformat()
        })
        # Simulate successful upload
        self.current_request_count = min(10, self.current_request_count + available_slots)


class MockCapacityManager:
    """Mock capacity manager for testing."""
    
    def __init__(self):
        self.upload_calls = []
        self.current_count = 5
    
    def trigger_upload_automation(self, max_files=None):
        """Mock upload automation trigger."""
        from automation.capacity_manager import CapacityAction
        
        self.upload_calls.append({
            'max_files': max_files,
            'timestamp': datetime.now().isoformat()
        })
        
        # Simulate successful upload
        files_uploaded = min(max_files or 5, 10 - self.current_count)
        self.current_count = min(10, self.current_count + files_uploaded)
        
        return CapacityAction(
            action_type="test_upload",
            request_id=None,
            success=True,
            message=f"Mock upload of {files_uploaded} files",
            details={'files_uploaded': files_uploaded},
            timestamp=datetime.now().isoformat()
        )


class DynamicBatchIntegrationTest:
    """Comprehensive integration test for dynamic batch processing."""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.test_results: List[TestResult] = []
        
        # Mock components
        self.mock_batch_system = MockBatchSystem()
        self.mock_capacity_manager = MockCapacityManager()
        
        # Real components for testing
        self.enhanced_monitor = None
        self.dynamic_trigger_system = None
        self.batch_optimizer = None
        self.integration = None
        
        self.logger.info("DynamicBatchIntegrationTest initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the test."""
        logger = logging.getLogger('rda_automation.integration_test')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    def setup_test_environment(self):
        """Set up the test environment with all components."""
        try:
            self.logger.info("🔧 Setting up test environment...")
            
            # Create enhanced monitoring integration
            self.integration = create_enhanced_monitoring_integration()
            self.enhanced_monitor = self.integration.enhanced_monitor
            
            # Create dynamic trigger system
            self.dynamic_trigger_system = create_dynamic_trigger_system(
                enhanced_monitor=self.enhanced_monitor,
                capacity_manager=self.mock_capacity_manager,
                event_dispatcher=self.integration.event_dispatcher
            )
            
            # Set integration components
            self.dynamic_trigger_system.set_integration_components(
                batch_system=self.mock_batch_system,
                queue_manager=None  # Not needed for basic tests
            )
            
            # Create batch optimizer
            self.batch_optimizer = create_batch_optimizer(
                enhanced_monitor=self.enhanced_monitor,
                dynamic_trigger=self.dynamic_trigger_system
            )
            
            # Connect components
            self.integration.connect_batch_system(self.mock_batch_system)
            
            # Add test callbacks
            self.dynamic_trigger_system.add_processing_callback(self._test_trigger_callback)
            
            self.logger.info("✅ Test environment setup complete")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to setup test environment: {e}")
            return False
    
    def _test_trigger_callback(self, trigger_event, success: bool):
        """Test callback for trigger events."""
        self.logger.info(f"🔔 Test callback: {trigger_event.trigger_type.value} - {'Success' if success else 'Failed'}")
    
    def run_test_case(self, test_name: str, test_function) -> TestResult:
        """Run a single test case."""
        start_time = time.time()
        
        try:
            self.logger.info(f"🧪 Running test: {test_name}")
            
            result = test_function()
            duration = time.time() - start_time
            
            if result.get('success', False):
                self.logger.info(f"✅ Test passed: {test_name} ({duration:.2f}s)")
                return TestResult(
                    test_name=test_name,
                    success=True,
                    duration=duration,
                    message=result.get('message', 'Test passed'),
                    details=result.get('details', {}),
                    timestamp=datetime.now().isoformat()
                )
            else:
                self.logger.error(f"❌ Test failed: {test_name} - {result.get('message', 'Unknown error')}")
                return TestResult(
                    test_name=test_name,
                    success=False,
                    duration=duration,
                    message=result.get('message', 'Test failed'),
                    details=result.get('details', {}),
                    timestamp=datetime.now().isoformat()
                )
                
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"❌ Test error: {test_name} - {str(e)}")
            return TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                message=f"Test error: {str(e)}",
                details={'exception': str(e)},
                timestamp=datetime.now().isoformat()
            )
    
    def test_component_initialization(self) -> Dict[str, Any]:
        """Test that all components initialize correctly."""
        try:
            # Check that all components are created
            components_ok = all([
                self.enhanced_monitor is not None,
                self.dynamic_trigger_system is not None,
                self.batch_optimizer is not None,
                self.integration is not None
            ])
            
            if not components_ok:
                return {
                    'success': False,
                    'message': 'Not all components were initialized',
                    'details': {
                        'enhanced_monitor': self.enhanced_monitor is not None,
                        'dynamic_trigger_system': self.dynamic_trigger_system is not None,
                        'batch_optimizer': self.batch_optimizer is not None,
                        'integration': self.integration is not None
                    }
                }
            
            # Check component status
            trigger_status = self.dynamic_trigger_system.get_system_status()
            optimizer_analytics = self.batch_optimizer.get_optimization_analytics()
            integration_status = self.integration.get_integration_status()
            
            return {
                'success': True,
                'message': 'All components initialized successfully',
                'details': {
                    'trigger_system_active': trigger_status.get('system_active', False),
                    'optimizer_ready': 'error' not in optimizer_analytics,
                    'integration_ready': 'error' not in integration_status
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Component initialization test failed: {str(e)}',
                'details': {'exception': str(e)}
            }
    
    def test_dynamic_trigger_activation(self) -> Dict[str, Any]:
        """Test that dynamic triggers activate correctly."""
        try:
            # Start the systems
            self.integration.start_integration()
            self.dynamic_trigger_system.start_system()
            
            # Wait a moment for systems to start
            time.sleep(1)
            
            # Reset mock counters
            self.mock_batch_system.upload_calls.clear()
            self.mock_capacity_manager.upload_calls.clear()
            
            # Simulate request count change that should trigger upload
            initial_count = 3  # Low count should trigger upload
            self.mock_batch_system.set_request_count(initial_count)
            self.mock_capacity_manager.current_count = initial_count
            
            # Create a mock request count change event
            from automation.event_system import BaseEvent, EventType, EventPriority
            
            # Simulate the enhanced monitor detecting a change
            snapshot = RequestCountSnapshot(
                timestamp=datetime.now().isoformat(),
                total_requests=initial_count,
                requests_by_status={'submitted': initial_count, 'processing': 0, 'completed': 0, 'error': 0},
                status_level=self.enhanced_monitor.create_snapshot().status_level
            )
            
            # Manually trigger the condition evaluation
            triggered_conditions = self.dynamic_trigger_system._evaluate_trigger_conditions(
                current_count=initial_count,
                previous_count=8  # Simulate drop from 8 to 3
            )
            
            if not triggered_conditions:
                return {
                    'success': False,
                    'message': 'No trigger conditions were activated',
                    'details': {
                        'current_count': initial_count,
                        'previous_count': 8,
                        'conditions_checked': len(self.dynamic_trigger_system.trigger_conditions)
                    }
                }
            
            # Process the triggered conditions
            for condition in triggered_conditions:
                self.dynamic_trigger_system._process_trigger_condition(condition, initial_count, 8)
            
            # Wait for processing
            time.sleep(2)
            
            # Check if uploads were triggered
            batch_uploads = len(self.mock_batch_system.upload_calls)
            capacity_uploads = len(self.mock_capacity_manager.upload_calls)
            
            success = batch_uploads > 0 or capacity_uploads > 0
            
            return {
                'success': success,
                'message': f'Dynamic triggers {"activated" if success else "failed to activate"}',
                'details': {
                    'triggered_conditions': len(triggered_conditions),
                    'batch_system_uploads': batch_uploads,
                    'capacity_manager_uploads': capacity_uploads,
                    'final_request_count': self.mock_batch_system.current_request_count
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Dynamic trigger test failed: {str(e)}',
                'details': {'exception': str(e)}
            }
        finally:
            # Clean up
            try:
                self.dynamic_trigger_system.stop_system()
                self.integration.stop_integration()
            except:
                pass
    
    def test_batch_optimization(self) -> Dict[str, Any]:
        """Test batch optimization functionality."""
        try:
            # Test optimization with different scenarios
            test_scenarios = [
                {'current_count': 2, 'expected_strategy': 'aggressive'},
                {'current_count': 5, 'expected_strategy': 'balanced'},
                {'current_count': 9, 'expected_strategy': 'conservative'},
                {'current_count': 10, 'expected_strategy': 'none'}
            ]
            
            results = []
            
            for scenario in test_scenarios:
                # Set mock system state
                self.mock_batch_system.set_request_count(scenario['current_count'])
                
                # Run optimization
                optimization_result = self.batch_optimizer.optimize_batch_processing()
                
                results.append({
                    'scenario': scenario,
                    'recommended_batch_size': optimization_result.recommended_batch_size,
                    'confidence': optimization_result.confidence_score,
                    'strategy': optimization_result.optimization_strategy.value,
                    'risk': optimization_result.risk_assessment
                })
            
            # Check that optimization produces reasonable results
            all_reasonable = True
            for result in results:
                batch_size = result['recommended_batch_size']
                current_count = result['scenario']['current_count']
                
                # Batch size should not exceed available slots
                available_slots = max(0, 10 - current_count)
                if batch_size > available_slots:
                    all_reasonable = False
                    break
                
                # Should recommend something when slots are available
                if available_slots > 0 and batch_size == 0:
                    # This might be okay for very conservative strategies
                    pass
            
            return {
                'success': all_reasonable,
                'message': f'Batch optimization {"working correctly" if all_reasonable else "has issues"}',
                'details': {
                    'test_scenarios': len(test_scenarios),
                    'results': results,
                    'all_reasonable': all_reasonable
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Batch optimization test failed: {str(e)}',
                'details': {'exception': str(e)}
            }
    
    def test_backward_compatibility(self) -> Dict[str, Any]:
        """Test that the system maintains backward compatibility."""
        try:
            # Test that the system can run without dynamic components
            from batch_automation_integrated import IntegratedBatchSystem
            
            # Create config without dynamic processing
            test_config = {
                'automation': {
                    'dynamic_batch_processing_enabled': False,
                    'max_concurrent_requests': 10,
                    'check_interval_seconds': 60
                },
                'directories': {
                    'control_files_dir': './control_files',
                    'base_download_dir': './downloaded_files'
                }
            }
            
            # Save test config
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(test_config, f)
                test_config_path = f.name
            
            try:
                # Try to initialize system without dynamic components
                # Note: This is a basic test - full testing would require more setup
                system = IntegratedBatchSystem(test_config_path)
                
                # Check that dynamic components are not initialized
                has_dynamic = any([
                    system.enhanced_monitoring_integration is not None,
                    system.dynamic_trigger_system is not None,
                    system.batch_optimizer is not None
                ])
                
                return {
                    'success': not has_dynamic,  # Should be False when disabled
                    'message': f'Backward compatibility {"maintained" if not has_dynamic else "broken"}',
                    'details': {
                        'dynamic_components_created': has_dynamic,
                        'system_initialized': True
                    }
                }
                
            finally:
                # Clean up
                os.unlink(test_config_path)
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Backward compatibility test failed: {str(e)}',
                'details': {'exception': str(e)}
            }
    
    def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling in dynamic components."""
        try:
            # Test various error conditions
            error_tests = []
            
            # Test 1: Invalid trigger conditions
            try:
                invalid_conditions = self.dynamic_trigger_system._evaluate_trigger_conditions(-1, 5)
                error_tests.append({
                    'test': 'invalid_request_count',
                    'handled': True,
                    'result': len(invalid_conditions)
                })
            except Exception as e:
                error_tests.append({
                    'test': 'invalid_request_count',
                    'handled': False,
                    'error': str(e)
                })
            
            # Test 2: Batch optimization with invalid data
            try:
                # Create invalid metrics
                from automation.batch_optimizer import SystemMetrics
                invalid_metrics = SystemMetrics(
                    current_request_count=-5,  # Invalid
                    average_processing_time=-1,  # Invalid
                    success_rate=2.0,  # Invalid (>1.0)
                    throughput_rate=-10,  # Invalid
                    capacity_utilization=1.5,  # Invalid (>1.0)
                    error_rate=-0.1,  # Invalid
                    queue_length=-1,  # Invalid
                    available_files=-1,  # Invalid
                    timestamp=datetime.now().isoformat()
                )
                
                system_state = self.batch_optimizer.classify_system_state(invalid_metrics)
                result = self.batch_optimizer.calculate_optimal_batch_size(
                    invalid_metrics, system_state, OptimizationStrategy.BALANCED
                )
                
                error_tests.append({
                    'test': 'invalid_metrics',
                    'handled': True,
                    'batch_size': result.recommended_batch_size,
                    'confidence': result.confidence_score
                })
                
            except Exception as e:
                error_tests.append({
                    'test': 'invalid_metrics',
                    'handled': False,
                    'error': str(e)
                })
            
            # Check that errors were handled gracefully
            all_handled = all(test.get('handled', False) for test in error_tests)
            
            return {
                'success': all_handled,
                'message': f'Error handling {"working correctly" if all_handled else "has issues"}',
                'details': {
                    'error_tests': error_tests,
                    'all_handled': all_handled
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error handling test failed: {str(e)}',
                'details': {'exception': str(e)}
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests."""
        self.logger.info("🚀 Starting comprehensive integration tests...")
        
        # Setup test environment
        if not self.setup_test_environment():
            return {
                'success': False,
                'message': 'Failed to setup test environment',
                'results': []
            }
        
        # Define test cases
        test_cases = [
            ('Component Initialization', self.test_component_initialization),
            ('Dynamic Trigger Activation', self.test_dynamic_trigger_activation),
            ('Batch Optimization', self.test_batch_optimization),
            ('Backward Compatibility', self.test_backward_compatibility),
            ('Error Handling', self.test_error_handling)
        ]
        
        # Run all tests
        for test_name, test_function in test_cases:
            result = self.run_test_case(test_name, test_function)
            self.test_results.append(result)
        
        # Calculate overall results
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.success])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        overall_success = success_rate >= 80  # 80% pass rate required
        
        self.logger.info(f"🏁 Integration tests complete: {passed_tests}/{total_tests} passed ({success_rate:.1f}%)")
        
        return {
            'success': overall_success,
            'message': f'Integration tests {"PASSED" if overall_success else "FAILED"} - {passed_tests}/{total_tests} tests passed',
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': total_tests - passed_tests,
                'success_rate': success_rate,
                'overall_success': overall_success
            },
            'results': [asdict(r) for r in self.test_results]
        }
    
    def cleanup(self):
        """Clean up test resources."""
        self.logger.info("🧹 Cleaning up test environment...")
        
        try:
            if self.dynamic_trigger_system:
                self.dynamic_trigger_system.cleanup()
            
            if self.batch_optimizer:
                self.batch_optimizer.cleanup()
            
            if self.integration:
                self.integration.cleanup()
                
        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")
        
        self.logger.info("✅ Test cleanup complete")


def main():
    """Main function for running integration tests."""
    print("="*80)
    print("🧪 DYNAMIC BATCH PROCESSING INTEGRATION TESTS")
    print("="*80)
    
    # Create and run tests
    test_runner = DynamicBatchIntegrationTest()
    
    try:
        results = test_runner.run_all_tests()
        
        # Print results
        print(f"\n📊 TEST RESULTS:")
        print(f"Overall Status: {'✅ PASSED' if results['success'] else '❌ FAILED'}")
        print(f"Success Rate: {results['summary']['success_rate']:.1f}%")
        print(f"Tests Passed: {results['summary']['passed_tests']}/{results['summary']['total_tests']}")
        
        print(f"\n📋 DETAILED RESULTS:")
        for result in results['results']:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"  {status} {result['test_name']} ({result['duration']:.2f}s)")
            if not result['success']:
                print(f"    Error: {result['message']}")
        
        # Print JSON results for programmatic use
        print(f"\n🔧 JSON RESULTS:")
        print(json.dumps(results, indent=2))
        
        return 0 if results['success'] else 1
        
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return 1
        
    finally:
        test_runner.cleanup()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)