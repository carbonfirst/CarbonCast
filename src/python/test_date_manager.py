#!/usr/bin/env python3
"""
Test script for the Date Manager functionality.

This script demonstrates the date range selection feature and allows testing
of various date input formats and validation.

Usage:
    python test_date_manager.py
"""

import sys
import logging
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from automation.date_manager import create_date_manager, DateValidationError

def test_date_parsing():
    """Test various date parsing formats."""
    print("🧪 Testing Date Parsing Functionality")
    print("=" * 50)
    
    # Initialize date manager
    date_manager = create_date_manager()
    
    # Test cases
    test_cases = [
        "2023",
        "2023-01-01 to 2023-12-31",
        "January 2023 to December 2023",
        "Q1 2024",
        "2023-06",
        "last 30 days",
        "last 6 months",
        "202301010000/to/202312310000",
        "June 2023",
        "Q4 2023"
    ]
    
    print("Testing various date input formats:\n")
    
    for i, test_input in enumerate(test_cases, 1):
        print(f"{i:2d}. Testing: '{test_input}'")
        
        try:
            date_range = date_manager.parse_date_range_string(test_input)
            
            print(f"    ✅ Parsed successfully:")
            print(f"       📅 Range: {date_range.to_readable_format()}")
            print(f"       📊 Duration: {date_range.duration_days()} days")
            print(f"       🔧 CTL format: {date_range.to_ctl_format()}")
            print(f"       📝 Format: {date_range.format_used.value}")
            
            # Validate
            validation = date_manager.get_validation_result(date_range)
            if not validation.is_valid:
                print(f"       ❌ Validation issues: {', '.join(validation.issues)}")
            if validation.warnings:
                print(f"       ⚠️  Warnings: {', '.join(validation.warnings)}")
            
        except DateValidationError as e:
            print(f"    ❌ Parse error: {e}")
        except Exception as e:
            print(f"    ❌ Unexpected error: {e}")
        
        print()

def test_control_file_update():
    """Test control file update functionality."""
    print("🧪 Testing Control File Update")
    print("=" * 40)
    
    # Check if we have control files to test with
    control_files_dir = Path("control_files")
    if not control_files_dir.exists():
        print("❌ No control_files directory found")
        print("💡 Create some test control files to test this functionality")
        return
    
    control_files = list(control_files_dir.glob("*.ctl"))
    if not control_files:
        print("❌ No control files found in control_files directory")
        return
    
    print(f"📁 Found {len(control_files)} control files")
    
    # Initialize date manager
    date_manager = create_date_manager()
    
    # Show current dates in first few files
    print("\n📅 Current dates in control files:")
    for i, file_path in enumerate(control_files[:3], 1):
        current_date = date_manager.extract_date_from_ctl(str(file_path))
        print(f"  {i}. {file_path.name}: {current_date or 'No date found'}")
    
    if len(control_files) > 3:
        print(f"  ... and {len(control_files) - 3} more files")
    
    print("\n💡 To test file updates, run the main automation script:")
    print("   python start_automation.py")

def test_date_suggestions():
    """Test date suggestions functionality."""
    print("🧪 Testing Date Suggestions")
    print("=" * 35)
    
    date_manager = create_date_manager()
    suggestions = date_manager.get_date_suggestions()
    
    print("📋 Available date suggestions:")
    for name, date_str in suggestions.items():
        display_name = name.replace('_', ' ').title()
        print(f"  • {display_name}: {date_str}")
        
        # Try to parse each suggestion
        try:
            date_range = date_manager.parse_date_range_string(date_str)
            print(f"    → {date_range.to_readable_format()} ({date_range.duration_days()} days)")
        except Exception as e:
            print(f"    ❌ Error parsing: {e}")
    
    print()

def interactive_test():
    """Interactive testing mode."""
    print("🧪 Interactive Date Testing Mode")
    print("=" * 40)
    print("Enter date ranges to test parsing and validation.")
    print("Type 'quit' to exit, 'help' for examples.")
    print()
    
    date_manager = create_date_manager()
    
    while True:
        try:
            user_input = input("📅 Enter date range: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            elif user_input.lower() == 'help':
                print("\nExample formats:")
                print("  • 2023")
                print("  • 2023-01-01 to 2023-12-31")
                print("  • January 2023 to December 2023")
                print("  • Q1 2024")
                print("  • last 30 days")
                print("  • 2023-06")
                print()
                continue
            elif not user_input:
                continue
            
            try:
                date_range = date_manager.parse_date_range_string(user_input)
                
                print(f"✅ Parsed: {date_range.to_readable_format()}")
                print(f"   Duration: {date_range.duration_days()} days")
                print(f"   CTL format: {date_range.to_ctl_format()}")
                print(f"   Format used: {date_range.format_used.value}")
                
                # Validate
                validation = date_manager.get_validation_result(date_range)
                if not validation.is_valid:
                    print(f"   ❌ Issues: {', '.join(validation.issues)}")
                if validation.warnings:
                    print(f"   ⚠️  Warnings: {', '.join(validation.warnings)}")
                
            except DateValidationError as e:
                print(f"❌ Parse error: {e}")
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
            
            print()
            
        except KeyboardInterrupt:
            break
    
    print("\n👋 Goodbye!")

def main():
    """Main test function."""
    print("🌦️  RDA Date Manager Test Suite")
    print("=" * 60)
    print()
    
    # Setup logging
    from logger_utils import configure_root_logging
    configure_root_logging(level=logging.WARNING)  # Reduce noise during testing
    
    try:
        # Run tests
        test_date_parsing()
        print()
        
        test_date_suggestions()
        print()
        
        test_control_file_update()
        print()
        
        # Ask if user wants interactive mode
        response = input("🤔 Run interactive testing mode? (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            print()
            interactive_test()
        
        print("\n✅ Test suite completed!")
        
    except KeyboardInterrupt:
        print("\n👋 Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()