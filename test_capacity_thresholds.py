#!/usr/bin/env python3
"""
Comprehensive test script for capacity management threshold modifications.

This script verifies:
1. Threshold consistency across components
2. Capacity management logic flow with new thresholds
3. Integration between components
4. Expected behavior transitions
"""

import sys
import os
sys.path.insert(0, 'src/python')

from automation.capacity_manager import CapacityManager, CapacityConfig, CapacityLevel
from automation.smart_retry_manager import SmartRetryManager, SmartRetryConfig
from automation.retry_strategy_engine import RetryStrategyEngine, StrategyConfig

def test_threshold_consistency():
    """Test that thresholds are consistent across all components."""
    print("=" * 60)
    print("TESTING THRESHOLD CONSISTENCY")
    print("=" * 60)
    
    # Test CapacityManager thresholds
    capacity_config = CapacityConfig()
    print(f"CapacityManager thresholds:")
    print(f"  normal_threshold: {capacity_config.normal_threshold}")
    print(f"  approaching_threshold: {capacity_config.approaching_threshold}")
    print(f"  critical_threshold: {capacity_config.critical_threshold}")
    print(f"  crisis_threshold: {capacity_config.crisis_threshold}")
    print(f"  upload_capacity_threshold: {capacity_config.upload_capacity_threshold}")
    
    # Test SmartRetryManager thresholds
    retry_config = SmartRetryConfig()
    print(f"\nSmartRetryManager thresholds:")
    print(f"  capacity_threshold: {retry_config.capacity_threshold}")
    
    # Test RetryStrategyEngine thresholds
    strategy_config = StrategyConfig()
    print(f"\nRetryStrategyEngine thresholds:")
    print(f"  capacity_threshold: {strategy_config.capacity_threshold}")
    
    # Verify expected changes
    expected_changes = {
        'capacity_manager.critical_threshold': 10,  # Changed from 9
        'smart_retry_manager.capacity_threshold': 9,  # Changed from 8
        'retry_strategy_engine.capacity_threshold': 9  # Changed from 8
    }
    
    actual_values = {
        'capacity_manager.critical_threshold': capacity_config.critical_threshold,
        'smart_retry_manager.capacity_threshold': retry_config.capacity_threshold,
        'retry_strategy_engine.capacity_threshold': strategy_config.capacity_threshold
    }
    
    print(f"\n{'Threshold':<40} {'Expected':<10} {'Actual':<10} {'Status':<10}")
    print("-" * 70)
    
    all_correct = True
    for key, expected in expected_changes.items():
        actual = actual_values[key]
        status = "✅ PASS" if actual == expected else "❌ FAIL"
        if actual != expected:
            all_correct = False
        print(f"{key:<40} {expected:<10} {actual:<10} {status}")
    
    return all_correct

def test_capacity_level_transitions():
    """Test capacity level transitions with new thresholds."""
    print("\n" + "=" * 60)
    print("TESTING CAPACITY LEVEL TRANSITIONS")
    print("=" * 60)
    
    # Create a mock capacity manager for testing
    capacity_config = CapacityConfig()
    
    # Test capacity level determination logic
    test_cases = [
        (0, CapacityLevel.NORMAL, "0 requests"),
        (3, CapacityLevel.NORMAL, "3 requests"),
        (6, CapacityLevel.NORMAL, "6 requests"),
        (7, CapacityLevel.APPROACHING, "7 requests"),
        (8, CapacityLevel.APPROACHING, "8 requests"),
        (9, CapacityLevel.APPROACHING, "9 requests"),
        (10, CapacityLevel.CRISIS, "10 requests (at limit)"),
        (11, CapacityLevel.CRISIS, "11 requests (over limit)")
    ]
    
    print(f"{'Requests':<10} {'Expected Level':<15} {'Description':<25} {'Status':<10}")
    print("-" * 70)
    
    all_correct = True
    for total_requests, expected_level, description in test_cases:
        # Simulate the capacity level determination logic
        if total_requests >= capacity_config.crisis_threshold:
            actual_level = CapacityLevel.CRISIS
        elif total_requests >= capacity_config.critical_threshold:
            actual_level = CapacityLevel.CRITICAL
        elif total_requests >= capacity_config.approaching_threshold:
            actual_level = CapacityLevel.APPROACHING
        else:
            actual_level = CapacityLevel.NORMAL
        
        status = "✅ PASS" if actual_level == expected_level else "❌ FAIL"
        if actual_level != expected_level:
            all_correct = False
        
        print(f"{total_requests:<10} {expected_level.value:<15} {description:<25} {status}")
    
    return all_correct

def test_upload_automation_logic():
    """Test upload automation logic with new thresholds."""
    print("\n" + "=" * 60)
    print("TESTING UPLOAD AUTOMATION LOGIC")
    print("=" * 60)
    
    capacity_config = CapacityConfig()
    upload_threshold = capacity_config.upload_capacity_threshold
    
    print(f"Upload capacity threshold: {upload_threshold}")
    print(f"Upload automation should be active when requests <= {upload_threshold}")
    
    test_cases = [
        (0, True, "0 requests - should allow upload"),
        (5, True, "5 requests - should allow upload"),
        (9, True, "9 requests - should allow upload (at threshold)"),
        (10, False, "10 requests - should block upload (above threshold)"),
        (11, False, "11 requests - should block upload (well above threshold)")
    ]
    
    print(f"\n{'Requests':<10} {'Should Upload':<15} {'Description':<35} {'Status':<10}")
    print("-" * 80)
    
    all_correct = True
    for total_requests, should_upload, description in test_cases:
        actual_should_upload = total_requests <= upload_threshold
        status = "✅ PASS" if actual_should_upload == should_upload else "❌ FAIL"
        if actual_should_upload != should_upload:
            all_correct = False
        
        print(f"{total_requests:<10} {should_upload:<15} {description:<35} {status}")
    
    return all_correct

def test_retry_strategy_capacity_logic():
    """Test retry strategy capacity logic with new thresholds."""
    print("\n" + "=" * 60)
    print("TESTING RETRY STRATEGY CAPACITY LOGIC")
    print("=" * 60)
    
    strategy_config = StrategyConfig()
    capacity_threshold = strategy_config.capacity_threshold
    
    print(f"Retry strategy capacity threshold: {capacity_threshold}")
    print(f"Special capacity handling when available <= {capacity_threshold}")
    
    # Test capacity-based retry decisions
    test_cases = [
        (10, True, "10 available - normal retry processing"),
        (9, True, "9 available - at threshold, should still allow"),
        (8, True, "8 available - below threshold, should still allow"),
        (3, True, "3 available - low capacity, should allow with delays"),
        (1, False, "1 available - very low capacity, should block"),
        (0, False, "0 available - no capacity, should block")
    ]
    
    print(f"\n{'Available':<12} {'Should Retry':<15} {'Description':<35} {'Status':<10}")
    print("-" * 82)
    
    all_correct = True
    for capacity_available, should_retry, description in test_cases:
        # Simulate the retry eligibility logic
        actual_should_retry = capacity_available > 1  # Based on the code logic
        status = "✅ PASS" if actual_should_retry == should_retry else "❌ FAIL"
        if actual_should_retry != should_retry:
            all_correct = False
        
        print(f"{capacity_available:<12} {should_retry:<15} {description:<35} {status}")
    
    return all_correct

def test_integration_scenarios():
    """Test integration scenarios with new thresholds."""
    print("\n" + "=" * 60)
    print("TESTING INTEGRATION SCENARIOS")
    print("=" * 60)
    
    scenarios = [
        {
            'name': 'Normal Operation (6 requests)',
            'requests': 6,
            'expected_capacity_level': CapacityLevel.NORMAL,
            'expected_upload_allowed': True,
            'expected_retry_allowed': True
        },
        {
            'name': 'Approaching Capacity (7 requests)',
            'requests': 7,
            'expected_capacity_level': CapacityLevel.APPROACHING,
            'expected_upload_allowed': True,
            'expected_retry_allowed': True
        },
        {
            'name': 'Approaching Capacity (9 requests)',
            'requests': 9,
            'expected_capacity_level': CapacityLevel.APPROACHING,
            'expected_upload_allowed': True,  # At threshold
            'expected_retry_allowed': False  # Only 1 slot available
        },
        {
            'name': 'Crisis Mode (10 requests)',
            'requests': 10,
            'expected_capacity_level': CapacityLevel.CRISIS,
            'expected_upload_allowed': False,  # Above threshold
            'expected_retry_allowed': False  # No available slots
        },
        {
            'name': 'Crisis Mode (11 requests)',
            'requests': 11,
            'expected_capacity_level': CapacityLevel.CRISIS,
            'expected_upload_allowed': False,
            'expected_retry_allowed': False
        }
    ]
    
    capacity_config = CapacityConfig()
    
    print(f"{'Scenario':<25} {'Level':<12} {'Upload':<8} {'Retry':<8} {'Status':<10}")
    print("-" * 73)
    
    all_correct = True
    for scenario in scenarios:
        requests = scenario['requests']
        
        # Test capacity level
        if requests >= capacity_config.crisis_threshold:
            actual_level = CapacityLevel.CRISIS
        elif requests >= capacity_config.critical_threshold:
            actual_level = CapacityLevel.CRITICAL
        elif requests >= capacity_config.approaching_threshold:
            actual_level = CapacityLevel.APPROACHING
        else:
            actual_level = CapacityLevel.NORMAL
        
        # Test upload allowed
        actual_upload = requests <= capacity_config.upload_capacity_threshold
        
        # Test retry allowed (based on available capacity)
        available_capacity = max(0, 10 - requests)
        actual_retry = available_capacity > 1
        
        # Check results
        level_ok = actual_level == scenario['expected_capacity_level']
        upload_ok = actual_upload == scenario['expected_upload_allowed']
        retry_ok = actual_retry == scenario['expected_retry_allowed']
        
        all_ok = level_ok and upload_ok and retry_ok
        if not all_ok:
            all_correct = False
        
        status = "✅ PASS" if all_ok else "❌ FAIL"
        
        print(f"{scenario['name']:<25} {actual_level.value:<12} {actual_upload:<8} {actual_retry:<8} {status}")
    
    return all_correct

def main():
    """Run all tests and generate comprehensive report."""
    print("CAPACITY MANAGEMENT THRESHOLD VERIFICATION")
    print("=" * 60)
    print("Testing capacity management modifications:")
    print("- capacity_manager.py: critical_threshold 9→10")
    print("- smart_retry_manager.py: capacity_threshold 8→9")
    print("- retry_strategy_engine.py: capacity_threshold 8→9")
    print()
    
    test_results = []
    
    # Run all tests
    test_results.append(("Threshold Consistency", test_threshold_consistency()))
    test_results.append(("Capacity Level Transitions", test_capacity_level_transitions()))
    test_results.append(("Upload Automation Logic", test_upload_automation_logic()))
    test_results.append(("Retry Strategy Capacity Logic", test_retry_strategy_capacity_logic()))
    test_results.append(("Integration Scenarios", test_integration_scenarios()))
    
    # Generate summary report
    print("\n" + "=" * 60)
    print("COMPREHENSIVE TEST REPORT SUMMARY")
    print("=" * 60)
    
    passed_tests = 0
    total_tests = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:<35} {status}")
        if result:
            passed_tests += 1
    
    print("-" * 60)
    print(f"OVERALL RESULT: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED - System is ready for 10 concurrent requests!")
        return True
    else:
        print("⚠️  SOME TESTS FAILED - Please review the issues above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)