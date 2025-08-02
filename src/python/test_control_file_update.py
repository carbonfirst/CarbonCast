#!/usr/bin/env python3
"""
Test script for control file batch update functionality.
"""

import sys
import os
import glob
sys.path.insert(0, os.getcwd())

from automation.date_manager import create_date_manager, DateValidationError

def test_control_file_batch_update():
    print('🧪 Testing Date Manager - Control File Batch Update')
    print('=' * 55)

    try:
        date_manager = create_date_manager()
        
        # Test 5: Control file batch update functionality
        print('Test 5: Testing control file batch update...')
        
        # First, let's check what control files exist
        control_files = glob.glob('control_files/*.ctl')
        print(f'Found {len(control_files)} control files')
        
        if len(control_files) == 0:
            print('❌ No control files found for testing')
            return False
        
        # Test with a small subset first (safety)
        test_files = control_files[:3]  # Test with first 3 files
        print(f'Testing with {len(test_files)} files: {[os.path.basename(f) for f in test_files]}')
        
        # Read original dates
        print('\nOriginal dates:')
        original_dates = {}
        for file_path in test_files:
            original_date = date_manager.extract_date_from_ctl(file_path)
            original_dates[file_path] = original_date
            print(f'  {os.path.basename(file_path)}: {original_date}')
        
        # Test date range for update
        test_date_range = date_manager.parse_date_range_string('2024')
        print(f'\nTest date range: {test_date_range.to_readable_format()}')
        print(f'CTL format: {test_date_range.to_ctl_format()}')
        
        # Perform batch update
        print('\nPerforming batch update...')
        result = date_manager.batch_modify_ctl_files(test_files, test_date_range)
        
        if result.success:
            print(f'✅ Batch update successful: {result.files_updated}/{result.total_files} files updated')
            
            # Verify the updates
            print('\nVerifying updates:')
            all_correct = True
            for file_path in test_files:
                new_date = date_manager.extract_date_from_ctl(file_path)
                expected_date = test_date_range.to_ctl_format()
                
                if new_date == expected_date:
                    print(f'  ✅ {os.path.basename(file_path)}: {new_date}')
                else:
                    print(f'  ❌ {os.path.basename(file_path)}: Expected {expected_date}, got {new_date}')
                    all_correct = False
            
            if all_correct:
                print('✅ All files updated correctly')
            else:
                print('❌ Some files were not updated correctly')
            
            # Restore original dates
            print('\nRestoring original dates...')
            for file_path in test_files:
                if original_dates[file_path]:
                    try:
                        original_range = date_manager.parse_date_range_string(original_dates[file_path])
                        restore_result = date_manager.batch_modify_ctl_files([file_path], original_range)
                        if restore_result.success:
                            print(f'  ✅ Restored {os.path.basename(file_path)}')
                        else:
                            print(f'  ❌ Failed to restore {os.path.basename(file_path)}')
                    except Exception as e:
                        print(f'  ❌ Error restoring {os.path.basename(file_path)}: {e}')
            
            return True
        else:
            print(f'❌ Batch update failed: {result.error_message}')
            
            # Show detailed error information
            if result.file_results:
                print('\nDetailed file results:')
                for file_result in result.file_results:
                    status = '✅' if file_result.success else '❌'
                    print(f'  {status} {os.path.basename(file_result.file_path)}: {file_result.error_message or "Success"}')
            
            return False
            
    except Exception as e:
        print(f'❌ CRITICAL ERROR: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_control_file_batch_update()
    if success:
        print('\n🎉 Control file batch update test completed successfully')
    else:
        print('\n❌ Control file batch update test failed')
        sys.exit(1)