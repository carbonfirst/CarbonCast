#!/usr/bin/env python3
"""
Date Management Utility Script for RDA Automation System

Provides command-line utilities for date management operations including:
- Date range parsing and validation
- CTL file date modification
- Batch processing of control files
- Date format conversion
- Audit logging and cleanup
"""

import argparse
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import automation components
try:
    from automation.date_manager import DateManager, DateRange, DateValidationError, CTLFileError
    from automation.config_manager import ConfigManager
    AUTOMATION_AVAILABLE = True
except ImportError:
    print("❌ Error: Automation components not found. Please ensure the automation package is available.")
    sys.exit(1)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('./src/python/logs/date_utils.log')
        ]
    )
    return logging.getLogger(__name__)


def parse_date_range_command(args) -> DateRange:
    """Parse date range from command line arguments."""
    date_manager = DateManager()
    
    if args.date_range:
        return date_manager.parse_date_range_string(args.date_range)
    elif args.start_date and args.end_date:
        return date_manager.parse_date_range(args.start_date, args.end_date)
    else:
        raise ValueError("Either --date-range or both --start-date and --end-date must be provided")


def validate_date_range(args) -> int:
    """Validate a date range."""
    logger = setup_logging(args.log_level)
    
    try:
        date_range = parse_date_range_command(args)
        date_manager = DateManager(logger=logger)
        
        print(f"📅 Parsed Date Range:")
        print(f"  Start: {date_range.start_date}")
        print(f"  End: {date_range.end_date}")
        print(f"  Format: {date_range.format_used.value}")
        print(f"  CTL Format: {date_range.to_ctl_format()}")
        print(f"  Original Input: {date_range.original_input}")
        
        # Validate the range
        is_valid = date_manager.validate_date_range(date_range)
        
        if is_valid:
            print("✅ Date range is valid")
            return 0
        else:
            print("❌ Date range validation failed")
            return 1
            
    except Exception as e:
        print(f"❌ Error validating date range: {e}")
        return 1


def show_date_suggestions(args) -> int:
    """Show common date range suggestions."""
    try:
        date_manager = DateManager()
        suggestions = date_manager.get_date_suggestions()
        
        print("📅 Common Date Range Suggestions:")
        print()
        
        for name, range_str in suggestions.items():
            print(f"  {name.replace('_', ' ').title()}: {range_str}")
        
        print()
        print("💡 Usage Examples:")
        print("  # Use a suggestion")
        print("  python date_utils.py modify --date-range 'last 30 days' --files *.ctl")
        print()
        print("  # Custom range")
        print("  python date_utils.py modify --start-date 2021-01-01 --end-date 2021-12-31 --files *.ctl")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error showing suggestions: {e}")
        return 1


def extract_dates_from_files(args) -> int:
    """Extract current date ranges from CTL files."""
    logger = setup_logging(args.log_level)
    
    try:
        date_manager = DateManager(logger=logger)
        
        # Get file list
        if args.files:
            file_paths = args.files
        elif args.directory:
            directory = Path(args.directory)
            file_paths = [str(f) for f in directory.glob("*.ctl")]
        else:
            file_paths = [str(f) for f in Path("./src/python/control_files").glob("*.ctl")]
        
        if not file_paths:
            print("❌ No CTL files found")
            return 1
        
        print(f"📄 Extracting dates from {len(file_paths)} files:")
        print()
        
        results = []
        for file_path in file_paths:
            try:
                current_date = date_manager.extract_date_from_ctl(file_path)
                if current_date:
                    results.append({
                        'file': file_path,
                        'current_date_range': current_date,
                        'status': 'success'
                    })
                    print(f"  ✅ {Path(file_path).name}: {current_date}")
                else:
                    results.append({
                        'file': file_path,
                        'current_date_range': None,
                        'status': 'no_date_found'
                    })
                    print(f"  ⚠️  {Path(file_path).name}: No date field found")
                    
            except Exception as e:
                results.append({
                    'file': file_path,
                    'current_date_range': None,
                    'status': 'error',
                    'error': str(e)
                })
                print(f"  ❌ {Path(file_path).name}: Error - {e}")
        
        # Save results if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Results saved to {args.output}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error extracting dates: {e}")
        print(f"❌ Error: {e}")
        return 1


def modify_ctl_files(args) -> int:
    """Modify CTL files with new date ranges."""
    logger = setup_logging(args.log_level)
    
    try:
        # Parse date range
        date_range = parse_date_range_command(args)
        
        # Initialize date manager
        temp_dir = args.temp_dir if args.temp_dir else None
        date_manager = DateManager(temp_dir=temp_dir, logger=logger)
        
        # Validate date range
        if not date_manager.validate_date_range(date_range):
            print("❌ Date range validation failed")
            return 1
        
        # Get file list
        if args.files:
            file_paths = args.files
        elif args.directory:
            directory = Path(args.directory)
            file_paths = [str(f) for f in directory.glob("*.ctl")]
        else:
            file_paths = [str(f) for f in Path("./src/python/control_files").glob("*.ctl")]
        
        if not file_paths:
            print("❌ No CTL files found")
            return 1
        
        print(f"🔄 Modifying {len(file_paths)} files with date range: {date_range}")
        print(f"   CTL Format: {date_range.to_ctl_format()}")
        print()
        
        # Process files
        results = []
        success_count = 0
        
        with date_manager:  # Use context manager for cleanup
            if args.batch:
                # Batch processing
                modified_files = date_manager.batch_modify_ctl_files(
                    file_paths, date_range, session_id=args.session_id
                )
                
                for original_file, modified_file in modified_files.items():
                    if modified_file:
                        success_count += 1
                        results.append({
                            'original_file': original_file,
                            'modified_file': modified_file,
                            'status': 'success'
                        })
                        print(f"  ✅ {Path(original_file).name} -> {Path(modified_file).name}")
                    else:
                        results.append({
                            'original_file': original_file,
                            'modified_file': None,
                            'status': 'failed'
                        })
                        print(f"  ❌ {Path(original_file).name}: Failed to modify")
            else:
                # Individual processing
                for file_path in file_paths:
                    try:
                        output_path = None
                        if args.output_dir:
                            output_dir = Path(args.output_dir)
                            output_dir.mkdir(parents=True, exist_ok=True)
                            output_path = output_dir / Path(file_path).name
                        
                        modified_file = date_manager.modify_ctl_file_dates(
                            file_path, date_range, str(output_path) if output_path else None,
                            session_id=args.session_id
                        )
                        
                        success_count += 1
                        results.append({
                            'original_file': file_path,
                            'modified_file': modified_file,
                            'status': 'success'
                        })
                        print(f"  ✅ {Path(file_path).name} -> {Path(modified_file).name}")
                        
                    except Exception as e:
                        results.append({
                            'original_file': file_path,
                            'modified_file': None,
                            'status': 'error',
                            'error': str(e)
                        })
                        print(f"  ❌ {Path(file_path).name}: {e}")
            
            print()
            print(f"📊 Summary: {success_count}/{len(file_paths)} files modified successfully")
            
            # Save modification log
            if args.save_log:
                log_file = args.save_log if args.save_log != True else f"date_modifications_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
                date_manager.save_modifications_log(log_file)
                print(f"📝 Modification log saved to {log_file}")
            
            # Save results if requested
            if args.output:
                output_data = {
                    'timestamp': datetime.now().isoformat(),
                    'date_range': {
                        'start': date_range.start_date.isoformat(),
                        'end': date_range.end_date.isoformat(),
                        'ctl_format': date_range.to_ctl_format(),
                        'original_input': date_range.original_input
                    },
                    'total_files': len(file_paths),
                    'successful_modifications': success_count,
                    'results': results
                }
                
                with open(args.output, 'w') as f:
                    json.dump(output_data, f, indent=2, default=str)
                print(f"💾 Results saved to {args.output}")
            
            # Cleanup unless requested to keep files
            if not args.keep_temp:
                print("🧹 Cleaning up temporary files...")
        
        return 0 if success_count > 0 else 1
        
    except Exception as e:
        logger.error(f"Error modifying files: {e}")
        print(f"❌ Error: {e}")
        return 1


def convert_date_format(args) -> int:
    """Convert date between different formats."""
    try:
        date_manager = DateManager()
        
        # Parse input date
        input_date = date_manager.parse_date_input(args.input_date)
        
        print(f"📅 Date Conversion:")
        print(f"  Input: {args.input_date}")
        print(f"  Parsed: {input_date}")
        print()
        print(f"  Formats:")
        print(f"    YYYY-MM-DD: {input_date.strftime('%Y-%m-%d')}")
        print(f"    YYYY-MM-DD HH:MM: {input_date.strftime('%Y-%m-%d %H:%M')}")
        print(f"    YYYYMMDDHHMM: {input_date.strftime('%Y%m%d%H%M')}")
        print(f"    ISO 8601: {input_date.isoformat()}")
        print(f"    Timestamp: {input_date.timestamp()}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error converting date: {e}")
        return 1


def cleanup_temp_files(args) -> int:
    """Clean up temporary files created by date manager."""
    logger = setup_logging(args.log_level)
    
    try:
        temp_dir = args.temp_dir if args.temp_dir else None
        date_manager = DateManager(temp_dir=temp_dir, logger=logger)
        
        if args.temp_dir:
            # Clean specific directory
            temp_path = Path(args.temp_dir)
            if temp_path.exists():
                file_count = len(list(temp_path.glob("*")))
                if args.confirm or input(f"Delete {file_count} files from {temp_path}? (y/N): ").lower() == 'y':
                    import shutil
                    shutil.rmtree(temp_path)
                    print(f"✅ Cleaned up {temp_path}")
                else:
                    print("❌ Cleanup cancelled")
            else:
                print(f"⚠️  Directory {temp_path} does not exist")
        else:
            # Clean default temp directory
            date_manager.cleanup_temp_files()
            print("✅ Cleaned up temporary files")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error cleaning up: {e}")
        print(f"❌ Error: {e}")
        return 1


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Date Management Utilities for RDA Automation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show date suggestions
  python date_utils.py suggestions

  # Validate a date range
  python date_utils.py validate --date-range "last 30 days"
  python date_utils.py validate --start-date 2021-01-01 --end-date 2021-12-31

  # Extract dates from CTL files
  python date_utils.py extract --directory ./control_files --output dates.json

  # Modify CTL files with new date range
  python date_utils.py modify --date-range "2021-01-01 to 2021-12-31" --files *.ctl
  python date_utils.py modify --start-date 2021-01-01 --end-date 2021-12-31 --directory ./control_files --batch

  # Convert date format
  python date_utils.py convert --input-date "last 7 days"

  # Clean up temporary files
  python date_utils.py cleanup --temp-dir /tmp/rda_date_manager
        """
    )
    
    # Global options
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Set logging level')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Suggestions command
    suggestions_parser = subparsers.add_parser('suggestions', help='Show common date range suggestions')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate a date range')
    validate_group = validate_parser.add_mutually_exclusive_group(required=True)
    validate_group.add_argument('--date-range', help='Date range string')
    validate_group.add_argument('--start-date', help='Start date (requires --end-date)')
    validate_parser.add_argument('--end-date', help='End date (requires --start-date)')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract current dates from CTL files')
    extract_group = extract_parser.add_mutually_exclusive_group()
    extract_group.add_argument('--files', nargs='+', help='Specific CTL files')
    extract_group.add_argument('--directory', help='Directory containing CTL files')
    extract_parser.add_argument('--output', help='Save results to JSON file')
    
    # Modify command
    modify_parser = subparsers.add_parser('modify', help='Modify CTL files with new date ranges')
    modify_date_group = modify_parser.add_mutually_exclusive_group(required=True)
    modify_date_group.add_argument('--date-range', help='Date range string')
    modify_date_group.add_argument('--start-date', help='Start date (requires --end-date)')
    modify_parser.add_argument('--end-date', help='End date (requires --start-date)')
    
    modify_file_group = modify_parser.add_mutually_exclusive_group()
    modify_file_group.add_argument('--files', nargs='+', help='Specific CTL files')
    modify_file_group.add_argument('--directory', help='Directory containing CTL files')
    
    modify_parser.add_argument('--batch', action='store_true', help='Use batch processing')
    modify_parser.add_argument('--output-dir', help='Output directory for modified files')
    modify_parser.add_argument('--temp-dir', help='Temporary directory for processing')
    modify_parser.add_argument('--session-id', help='Session ID for tracking')
    modify_parser.add_argument('--save-log', nargs='?', const=True, help='Save modification log')
    modify_parser.add_argument('--keep-temp', action='store_true', help='Keep temporary files')
    modify_parser.add_argument('--output', help='Save results to JSON file')
    
    # Convert command
    convert_parser = subparsers.add_parser('convert', help='Convert date between formats')
    convert_parser.add_argument('--input-date', required=True, help='Date to convert')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up temporary files')
    cleanup_parser.add_argument('--temp-dir', help='Specific temp directory to clean')
    cleanup_parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Ensure logs directory exists
    Path('./src/python/logs').mkdir(parents=True, exist_ok=True)
    
    # Route to appropriate function
    try:
        if args.command == 'suggestions':
            return show_date_suggestions(args)
        elif args.command == 'validate':
            return validate_date_range(args)
        elif args.command == 'extract':
            return extract_dates_from_files(args)
        elif args.command == 'modify':
            return modify_ctl_files(args)
        elif args.command == 'convert':
            return convert_date_format(args)
        elif args.command == 'cleanup':
            return cleanup_temp_files(args)
        else:
            print(f"❌ Unknown command: {args.command}")
            return 1
            
    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())