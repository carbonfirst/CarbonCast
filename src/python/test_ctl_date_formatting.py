#!/usr/bin/env python3
"""
Comprehensive test script to verify CTL date formatting fix.

This script tests:
1. CTL Format Verification - to_ctl_format() produces correct format
2. Various Input Formats - different inputs produce correct CTL output
3. Integration Test - batch update workflow works correctly
4. Regression Test - other functionality still works
5. Format Adherence - strictly follows YYYYMMDD0000 pattern
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

from automation.date_manager import create_date_manager, DateValidationError, DateRange

def test_ctl_format_verification():
    """Test 1: CTL Format Verification"""
    print("🧪 Test 1: CTL Format Verification")
    print("=" * 50)
    
    date_manager = create_date_manager()
    
    # Test cases with expected CTL format
    test_cases = [
        ("2023", "202301010000/to/202312310000"),
        ("2024-01-01 to 2024-03-31", "202401010000/to/202403310000"),
        ("Q1 2023", "202301010000/to/202303310000"),
        ("2023-06", "202306010000/to/202306300000"),
        ("January 2023 to March 2023", "202301010000/to/202303310000"),
    ]
    
    all_passed = True
    
    for input_str, expected_ctl in test_cases:
        try:
            date_range = date_manager.parse_date_range_string(input_str)
            actual_ctl = date_range.to_ctl_format()
            
            if actual_ctl == expected_ctl:
                print(f"  ✅ '{input_str}' -> {actual_ctl}")
            else:
                print(f"  ❌ '{input_str}' -> Expected: {expected_ctl}, Got: {actual_ctl}")
                all_passed = False
                
        except Exception as e:
            print(f"  ❌ '{input_str}' -> Error: {e}")
            all_passed = False
    
    print(f"\nTest 1 Result: {'✅ PASSED' if all_passed else '❌ FAILED'}")
    return all_passed

def test_format_pattern_adherence():
    """Test 2: Validate YYYYMMDD0000 pattern adherence"""
    print("\n🧪 Test 2: Format Pattern Adherence")
    print("=" * 50)
    
    import re
    date_manager = create_date_manager()
    
    # Pattern to match YYYYMMDD0000/to/YYYYMMDD0000
    ctl_pattern = r'^\d{8}0000/to/\d{8}0000$'
    
    test_inputs = [
        "2021", "2022", "2023", "2024",
        "Q1 2023", "Q2 2023", "Q3 2023", "Q4 2023",
        "2023-01", "2023-06", "2023-12",
        "2024-01-01 to 2024-12-31",
        "January 2023 to December 2023"
    ]
    
    all_passed = True
    
    for input_str in test_inputs:
        try:
            date_range = date_manager.parse_date_range_string(input_str)
            ctl_format = date_range.to_ctl_format()
            
            if re.match(ctl_pattern, ctl_format):
                # Verify time portion is exactly 0000
                parts = ctl_format.split('/to/')
                start_time = parts[0][-4:]  # Last 4 characters
                end_time = parts[1][-4:]    # Last 4 characters
                
                if start_time == "0000" and end_time == "0000":
                    print(f"  ✅ '{input_str}' -> {ctl_format} (time: {start_time}/{end_time})")
                else:
                    print(f"  ❌ '{input_str}' -> {ctl_format} (time not 0000: {start_time}/{end_time})")
                    all_passed = False
            else:
                print(f"  ❌ '{input_str}' -> {ctl_format} (pattern mismatch)")
                all_passed = False
                
        except Exception as e:
            print(f"  ❌ '{input_str}' -> Error: {e}")
            all_passed = False
    
    print(f"\nTest 2 Result: {'✅ PASSED' if all_passed else '❌ FAILED'}")
    return all_passed

def test_various_input_formats():
    """Test 3: Various Input Formats"""
    print("\n🧪 Test 3: Various Input Formats")
    print("=" * 50)
    
    date_manager = create_date_manager()
    
    # Test specific cases mentioned in requirements
    specific_tests = [
        {
            'input': '2023',
            'expected': '202301010000/to/202312310000',
            'description': 'Year shorthand'
        },
        {
            'input': '2024-01-01 to 2024-03-31',
            'expected': '202401010000/to/202403310000',
            'description': 'ISO date range'
        },
        {
            'input': 'Q1 2023',
            'expected': '202301010000/to/202303310000',
            'description': 'Quarter notation'
        }
    ]
    
    all_passed = True
    
    for test in specific_tests:
        try:
            date_range = date_manager.parse_date_range_string(test['input'])
            actual = date_range.to_ctl_format()
            
            if actual == test['expected']:
                print(f"  ✅ {test['description']}: '{test['input']}' -> {actual}")
            else:
                print(f"  ❌ {test['description']}: '{test['input']}' -> Expected: {test['expected']}, Got: {actual}")
                all_passed = False
                
        except Exception as e:
            print(f"  ❌ {test['description']}: '{test['input']}' -> Error: {e}")
            all_passed = False
    
    print(f"\nTest 3 Result: {'✅ PASSED' if all_passed else '❌ FAILED'}")
    return all_passed

def test_integration_workflow():
    """Test 4: Integration Test with Control Files"""
    print("\n🧪 Test 4: Integration Test with Control Files")
    print("=" * 50)
    
    date_manager = create_date_manager()
    
    # Create temporary control files for testing
    temp_dir = tempfile.mkdtemp(prefix='ctl_test_')
    
    try:
        # Create test control files
        test_files = []
        for i in range(3):
            test_file = Path(temp_dir) / f"test_{i}.ctl"
            with open(test_file, 'w') as f:
                f.write(f"# Test control file {i}\n")
                f.write("dataset=ds084.1\n")
                f.write("date=202101010000/to/202112310000\n")  # Original format
                f.write("param=11/2/0\n")
                f.write("level=ISBL:1000\n")
            test_files.append(str(test_file))
        
        print(f"Created {len(test_files)} test control files")
        
        # Test batch update
        test_date_range = date_manager.parse_date_range_string('2024')
        expected_ctl = test_date_range.to_ctl_format()
        
        print(f"Testing batch update with: {expected_ctl}")
        
        result = date_manager.batch_modify_ctl_files(test_files, test_date_range)
        
        if result.success:
            print(f"✅ Batch update successful: {result.files_updated}/{result.total_files} files updated")
            
            # Verify each file was updated correctly
            all_correct = True
            for file_path in test_files:
                actual_date = date_manager.extract_date_from_ctl(file_path)
                if actual_date == expected_ctl:
                    print(f"  ✅ {Path(file_path).name}: {actual_date}")
                else:
                    print(f"  ❌ {Path(file_path).name}: Expected {expected_ctl}, got {actual_date}")
                    all_correct = False
            
            if all_correct:
                print("✅ All files updated with correct CTL format")
                return True
            else:
                print("❌ Some files have incorrect CTL format")
                return False
        else:
            print(f"❌ Batch update failed: {result.error_message}")
            return False
            
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_regression_functionality():
    """Test 5: Regression Test - Other Functionality"""
    print("\n🧪 Test 5: Regression Test - Other Functionality")
    print("=" * 50)
    
    date_manager = create_date_manager()
    
    # Test that other methods still work correctly
    tests = [
        {
            'name': 'Readable format conversion',
            'test': lambda: date_manager.parse_date_range_string('2023').to_readable_format(),
            'expected': '2023-01-01 to 2023-12-31'
        },
        {
            'name': 'Duration calculation',
            'test': lambda: date_manager.parse_date_range_string('2023-01-01 to 2023-01-31').duration_days(),
            'expected': 30
        },
        {
            'name': 'Date validation',
            'test': lambda: date_manager.validate_date_range(date_manager.parse_date_range_string('2023')),
            'expected': True
        },
        {
            'name': 'CTL format parsing',
            'test': lambda: date_manager.parse_date_range_string('202301010000/to/202312310000').to_readable_format(),
            'expected': '2023-01-01 to 2023-12-31'
        }
    ]
    
    all_passed = True
    
    for test in tests:
        try:
            result = test['test']()
            if result == test['expected']:
                print(f"  ✅ {test['name']}: {result}")
            else:
                print(f"  ❌ {test['name']}: Expected {test['expected']}, got {result}")
                all_passed = False
        except Exception as e:
            print(f"  ❌ {test['name']}: Error - {e}")
            all_passed = False
    
    print(f"\nTest 5 Result: {'✅ PASSED' if all_passed else '❌ FAILED'}")
    return all_passed

def main():
    """Run all tests"""
    print("🧪 CTL Date Formatting Fix Verification")
    print("=" * 60)
    print("Testing that to_ctl_format() produces YYYYMMDD0000/to/YYYYMMDD0000")
    print()
    
    # Run all tests
    test_results = [
        test_ctl_format_verification(),
        test_format_pattern_adherence(),
        test_various_input_formats(),
        test_integration_workflow(),
        test_regression_functionality()
    ]
    
    # Summary
    passed_count = sum(test_results)
    total_count = len(test_results)
    
    print("\n" + "=" * 60)
    print("🏁 TEST SUMMARY")
    print("=" * 60)
    print(f"Tests passed: {passed_count}/{total_count}")
    
    if passed_count == total_count:
        print("🎉 ALL TESTS PASSED - CTL date formatting fix is working correctly!")
        print("✅ Format strictly adheres to YYYYMMDD0000/to/YYYYMMDD0000 pattern")
        print("✅ All input formats produce correct CTL output")
        print("✅ Integration workflow works correctly")
        print("✅ No regression in other functionality")
        return True
    else:
        print("❌ SOME TESTS FAILED - Issues detected with CTL date formatting")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)