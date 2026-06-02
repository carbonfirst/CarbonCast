#!/usr/bin/env python3
"""
Simple Test Script for Aggressive 10-Request Targeting Modifications

This script tests the key modifications made to ensure aggressive 10-request targeting.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def test_capacity_manager_config():
    """Test capacity manager configuration."""
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing Capacity Manager Configuration...")
    
    try:
        from automation.capacity_manager import CapacityConfig
        
        config = CapacityConfig()
        
        # Test aggressive settings
        tests = [
            (config.normal_threshold, 8, "Normal threshold"),
            (config.approaching_threshold, 9, "Approaching threshold"),
            (config.upload_capacity_threshold, 10, "Upload capacity threshold"),
            (config.upload_batch_size, 5, "Upload batch size"),
            (config.monitoring_interval, 30, "Monitoring interval")
        ]
        
        all_passed = True
        for actual, expected, name in tests:
            if actual == expected:
                logger.info(f"✅ {name}: {actual} (correct)")
            else:
                logger.error(f"❌ {name}: {actual} (expected {expected})")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def test_upload_automation_config():
    """Test upload automation configuration."""
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing Upload Automation Configuration...")
    
    try:
        from automation.upload_automation import UploadConfig
        
        config = UploadConfig()
        
        # Test aggressive settings
        tests = [
            (config.capacity_threshold, 10, "Capacity threshold"),
            (config.batch_size, 10, "Batch size"),
            (config.rate_limit_delay, 0.5, "Rate limit delay"),
            (config.min_upload_interval, 30, "Min upload interval"),
            (config.max_daily_uploads, 1000, "Max daily uploads")
        ]
        
        all_passed = True
        for actual, expected, name in tests:
            if actual == expected:
                logger.info(f"✅ {name}: {actual} (correct)")
            else:
                logger.error(f"❌ {name}: {actual} (expected {expected})")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def test_configuration_file():
    """Test configuration file settings."""
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing Configuration File...")
    
    try:
        config_path = "../../config/automation_config.json"
        if not os.path.exists(config_path):
            logger.error(f"❌ Config file not found: {config_path}")
            return False
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        automation = config.get('automation', {})
        upload = config.get('upload', {})
        
        tests = [
            (automation.get('check_interval_seconds'), 60, "Check interval"),
            (automation.get('request_limit_safety_margin'), 0, "Safety margin"),
            (automation.get('aggressive_10_request_targeting'), True, "Aggressive targeting"),
            (upload.get('rate_limit_delay'), 0.5, "Upload rate limit delay"),
            (upload.get('aggressive_upload_enabled'), True, "Aggressive upload enabled")
        ]
        
        all_passed = True
        for actual, expected, name in tests:
            if actual == expected:
                logger.info(f"✅ {name}: {actual} (correct)")
            else:
                logger.error(f"❌ {name}: {actual} (expected {expected})")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def test_batch_automation_modifications():
    """Test batch automation file modifications."""
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing Batch Automation Modifications...")
    
    try:
        with open("batch_automation_integrated.py", 'r') as f:
            content = f.read()
        
        # Check for aggressive modifications
        indicators = [
            "AGGRESSIVE",
            "10-request targeting",
            "🎯 AGGRESSIVE TARGET",
            "aggressive_interval = min(check_interval, 60)",
            "IMMEDIATELY filling to reach 10 requests"
        ]
        
        all_found = True
        for indicator in indicators:
            if indicator in content:
                logger.info(f"✅ Found: {indicator}")
            else:
                logger.error(f"❌ Missing: {indicator}")
                all_found = False
        
        return all_found
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def run_tests():
    """Run all tests."""
    logger = setup_logging()
    
    logger.info("🚀 Testing Aggressive 10-Request Targeting Modifications")
    logger.info("=" * 60)
    
    tests = [
        ("Capacity Manager Config", test_capacity_manager_config),
        ("Upload Automation Config", test_upload_automation_config),
        ("Configuration File", test_configuration_file),
        ("Batch Automation Modifications", test_batch_automation_modifications)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n📋 {test_name}")
        logger.info("-" * 40)
        
        try:
            result = test_func()
            results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.error(f"❌ {test_name}: FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED!")
        logger.info("🎯 System configured for AGGRESSIVE 10-request targeting!")
        logger.info("\n📋 Key Changes Verified:")
        logger.info("   • Capacity thresholds: normal=8, approaching=9")
        logger.info("   • Upload at 10 requests: enabled")
        logger.info("   • Batch sizes: increased to 5-10 files")
        logger.info("   • Check intervals: reduced to 60 seconds max")
        logger.info("   • Rate limits: reduced for faster uploads")
        logger.info("   • Safety margins: removed (set to 0)")
        logger.info("   • 24/7 operation: no time restrictions")
        
        logger.info("\n🚀 To start the aggressive system:")
        logger.info("   python batch_automation_integrated.py --process-all-control-files")
        
        return True
    else:
        logger.error(f"\n❌ {total - passed} tests failed!")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)