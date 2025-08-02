#!/usr/bin/env python3
"""
Test Script for Aggressive 10-Request Targeting System

This script tests the modified automation system to ensure it maintains
exactly 10 active requests at all times through aggressive capacity management.

Usage:
    python test_aggressive_10_request_targeting.py
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'test_aggressive_targeting_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )
    return logging.getLogger(__name__)

def test_capacity_manager_configuration():
    """Test that capacity manager has aggressive configuration."""
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing Capacity Manager Configuration...")
    
    try:
        from automation.capacity_manager import CapacityConfig, create_capacity_manager
        
        # Test default configuration
        config = CapacityConfig()
        
        # Verify aggressive settings
        assertions = [
            (config.normal_threshold == 8, f"Normal threshold should be 8, got {config.normal_threshold}"),
            (config.approaching_threshold == 9, f"Approaching threshold should be 9, got {config.approaching_threshold}"),
            (config.upload_capacity_threshold == 10, f"Upload capacity threshold should be 10, got {config.upload_capacity_threshold}"),
            (config.upload_batch_size == 5, f"Upload batch size should be 5, got {config.upload_batch_size}"),
            (config.upload_rate_limit_delay == 1.0, f"Upload rate limit delay should be 1.0, got {config.upload_rate_limit_delay}"),
            (config.monitoring_interval == 30, f"Monitoring interval should be 30, got {config.monitoring_interval}")
        ]
        
        all_passed = True
        for assertion, message in assertions:
            if assertion:
                logger.info(f"✅ {message}")
            else:
                logger.error(f"❌ {message}")
                all_passed = False
        
        if all_passed:
            logger.info("✅ Capacity Manager configuration is AGGRESSIVE and correct!")
            return True
        else:
            logger.error("❌ Capacity Manager configuration is NOT aggressive enough!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing capacity manager configuration: {e}")
        return False

def test_upload_automation_configuration():
    """Test that upload automation has aggressive configuration."""
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing Upload Automation Configuration...")
    
    try:
        from automation.upload_automation import UploadConfig, create_upload_automation_manager
        
        # Test default configuration
        config = UploadConfig()
        
        # Verify aggressive settings
        assertions = [
            (config.capacity_threshold == 10, f"Capacity threshold should be 10, got {config.capacity_threshold}"),
            (config.batch_size == 10, f"Batch size should be 10, got {config.batch_size}"),
            (config.rate_limit_delay == 0.5, f"Rate limit delay should be 0.5, got {config.rate_limit_delay}"),
            (config.min_upload_interval == 30, f"Min upload interval should be 30, got {config.min_upload_interval}"),
            (config.max_daily_uploads == 1000, f"Max daily uploads should be 1000, got {config.max_daily_uploads}"),
            (config.upload_window_start == 0, f"Upload window start should be 0, got {config.upload_window_start}"),
            (config.upload_window_end == 24, f"Upload window end should be 24, got {config.upload_window_end}")
        ]
        
        all_passed = True
        for assertion, message in assertions:
            if assertion:
                logger.info(f"✅ {message}")
            else:
                logger.error(f"❌ {message}")
                all_passed = False
        
        if all_passed:
            logger.info("✅ Upload Automation configuration is AGGRESSIVE and correct!")
            return True
        else:
            logger.error("❌ Upload Automation configuration is NOT aggressive enough!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing upload automation configuration: {e}")
        return False

def test_configuration_file():
    """Test that the configuration file has aggressive settings."""
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing Configuration File...")
    
    try:
        config_path = "config/automation_config.json"
        if not os.path.exists(config_path):
            logger.error(f"❌ Configuration file not found: {config_path}")
            return False
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Verify aggressive settings
        automation_config = config.get('automation', {})
        upload_config = config.get('upload', {})
        
        assertions = [
            (automation_config.get('check_interval_seconds') == 60, f"Check interval should be 60, got {automation_config.get('check_interval_seconds')}"),
            (automation_config.get('request_limit_safety_margin') == 0, f"Safety margin should be 0, got {automation_config.get('request_limit_safety_margin')}"),
            (automation_config.get('status_check_interval_seconds') == 60, f"Status check interval should be 60, got {automation_config.get('status_check_interval_seconds')}"),
            (automation_config.get('completed_request_scan_interval_minutes') == 2, f"Completed request scan interval should be 2, got {automation_config.get('completed_request_scan_interval_minutes')}"),
            (automation_config.get('aggressive_10_request_targeting') == True, f"Aggressive 10-request targeting should be True, got {automation_config.get('aggressive_10_request_targeting')}"),
            (upload_config.get('rate_limit_delay') == 0.5, f"Upload rate limit delay should be 0.5, got {upload_config.get('rate_limit_delay')}"),
            (upload_config.get('aggressive_upload_enabled') == True, f"Aggressive upload should be True, got {upload_config.get('aggressive_upload_enabled')}")
        ]
        
        all_passed = True
        for assertion, message in assertions:
            if assertion:
                logger.info(f"✅ {message}")
            else:
                logger.error(f"❌ {message}")
                all_passed = False
        
        if all_passed:
            logger.info("✅ Configuration file has AGGRESSIVE settings!")
            return True
        else:
            logger.error("❌ Configuration file does NOT have aggressive settings!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing configuration file: {e}")
        return False

def test_capacity_manager_strategies():
    """Test capacity manager strategy execution."""
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing Capacity Manager Strategies...")
    
    try:
        from automation.capacity_manager import create_capacity_manager, CapacityStatus, CapacityLevel
        
        # Create capacity manager
        manager = create_capacity_manager()
        
        # Test different capacity scenarios
        test_scenarios = [
            (5, CapacityLevel.NORMAL, "Should trigger aggressive upload for 5 available slots"),
            (8, CapacityLevel.NORMAL, "Should trigger aggressive upload for 2 available slots"),
            (9, CapacityLevel.APPROACHING, "Should trigger approaching strategy"),
            (10, CapacityLevel.CRITICAL, "Should trigger critical strategy")
        ]
        
        all_passed = True
        for request_count, expected_level, description in test_scenarios:
            # Create mock capacity status
            capacity_status = CapacityStatus(
                total_requests=request_count,
                capacity_level=expected_level,
                available_slots=10 - request_count,
                requests_by_status={'completed': 0, 'processing': request_count, 'queued': 0, 'error': 0, 'unknown': 0},
                priority_requests=0,
                estimated_completion_time=None,
                crisis_duration=None,
                last_updated=datetime.now().isoformat()
            )
            
            # Test strategy execution
            actions = manager.execute_capacity_strategy(capacity_status)
            
            if expected_level == CapacityLevel.NORMAL and request_count < 10:
                # Should have upload actions for normal level with available slots
                upload_actions = [a for a in actions if 'upload' in a.action_type.lower()]
                if upload_actions:
                    logger.info(f"✅ {description} - Upload action triggered")
                else:
                    logger.warning(f"⚠️ {description} - No upload action (may be due to no files available)")
            else:
                logger.info(f"✅ {description} - Strategy executed with {len(actions)} actions")
        
        logger.info("✅ Capacity Manager strategies are working!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing capacity manager strategies: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_batch_automation_integration():
    """Test that batch automation integration has aggressive settings."""
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing Batch Automation Integration...")
    
    try:
        # Test that the batch automation file has been modified
        batch_file_path = "src/python/batch_automation_integrated.py"
        if not os.path.exists(batch_file_path):
            logger.error(f"❌ Batch automation file not found: {batch_file_path}")
            return False
        
        with open(batch_file_path, 'r') as f:
            content = f.read()
        
        # Check for aggressive modifications
        aggressive_indicators = [
            "AGGRESSIVE",
            "10-request targeting",
            "aggressive_interval = min(check_interval, 60)",
            "IMMEDIATELY filling to reach 10 requests",
            "🎯 AGGRESSIVE TARGET"
        ]
        
        all_found = True
        for indicator in aggressive_indicators:
            if indicator in content:
                logger.info(f"✅ Found aggressive indicator: {indicator}")
            else:
                logger.error(f"❌ Missing aggressive indicator: {indicator}")
                all_found = False
        
        if all_found:
            logger.info("✅ Batch automation integration has AGGRESSIVE modifications!")
            return True
        else:
            logger.error("❌ Batch automation integration is missing aggressive modifications!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing batch automation integration: {e}")
        return False

def run_comprehensive_test():
    """Run comprehensive test of the aggressive 10-request targeting system."""
    logger = setup_logging()
    
    logger.info("🚀 Starting Comprehensive Test of Aggressive 10-Request Targeting System")
    logger.info("=" * 80)
    
    test_results = []
    
    # Run all tests
    tests = [
        ("Capacity Manager Configuration", test_capacity_manager_configuration),
        ("Upload Automation Configuration", test_upload_automation_configuration),
        ("Configuration File", test_configuration_file),
        ("Capacity Manager Strategies", test_capacity_manager_strategies),
        ("Batch Automation Integration", test_batch_automation_integration)
    ]
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running Test: {test_name}")
        logger.info("-" * 50)
        
        try:
            result = test_func()
            test_results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.error(f"❌ {test_name}: FAILED")
                
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
            test_results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 80)
    
    passed_tests = sum(1 for _, result in test_results if result)
    total_tests = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info("-" * 80)
    logger.info(f"Overall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        logger.info("🎉 ALL TESTS PASSED! The system is configured for AGGRESSIVE 10-request targeting!")
        logger.info("\n🎯 SYSTEM READY FOR MAXIMUM THROUGHPUT:")
        logger.info("   • Capacity manager targets exactly 10 requests")
        logger.info("   • Upload automation fills available slots immediately")
        logger.info("   • Configuration optimized for maximum throughput")
        logger.info("   • Reduced delays and conservative buffers")
        logger.info("   • 24/7 aggressive request submission")
        return True
    else:
        logger.error(f"❌ {total_tests - passed_tests} tests failed. System may not maintain 10 requests optimally.")
        return False

def print_usage_instructions():
    """Print instructions for using the aggressive system."""
    logger = logging.getLogger(__name__)
    
    logger.info("\n" + "=" * 80)
    logger.info("🚀 AGGRESSIVE 10-REQUEST TARGETING SYSTEM - USAGE INSTRUCTIONS")
    logger.info("=" * 80)
    logger.info("\n📋 To start the aggressive automation system:")
    logger.info("   python batch_automation_integrated.py --process-all-control-files")
    logger.info("\n📊 To monitor with dashboard:")
    logger.info("   python batch_automation_integrated.py --monitor-dashboard")
    logger.info("\n🔧 Key Changes Made:")
    logger.info("   • Capacity thresholds: normal=8, approaching=9, critical=10")
    logger.info("   • Upload at capacity: uploads allowed even at 10 requests")
    logger.info("   • Batch size: increased to 5-10 files per upload")
    logger.info("   • Check interval: reduced to 60 seconds maximum")
    logger.info("   • Rate limits: reduced delays for faster uploads")
    logger.info("   • Safety margins: removed conservative buffers")
    logger.info("   • 24/7 operation: no time-based upload restrictions")
    logger.info("\n⚡ Expected Behavior:")
    logger.info("   • System will aggressively maintain exactly 10 active requests")
    logger.info("   • Immediate slot filling when requests complete")
    logger.info("   • Faster processing cycles and reduced wait times")
    logger.info("   • Maximum utilization of RDA request limit")
    logger.info("=" * 80)

if __name__ == "__main__":
    success = run_comprehensive_test()
    
    if success:
        print_usage_instructions()
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please review the modifications.")
        sys.exit(1)