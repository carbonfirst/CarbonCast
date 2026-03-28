#!/usr/bin/env python3
"""
Enhanced Upload Files Script for RDA Automation System

Provides both standalone functionality and integration with the automation framework.
Supports batch processing, error handling, state management, and configuration-driven operation.

This script can be used standalone or integrated with the automation system.
"""

import argparse
import json
import logging
import os
import pathlib
import shutil
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from logger_utils import get_logger

# Import rdams_client
import rdams_client as rc

# Try to import automation components (optional for standalone use)
try:
    from automation.config_manager import ConfigManager
    from automation.state_manager import StateManager, FileStatus
    from automation.error_handler import ErrorHandler, ErrorContext
    from automation.rate_limiter import RateLimiter
    from automation.date_manager import DateManager, DateRange
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    # Define dummy DateRange for type hints when automation is not available
    class DateRange:
        pass


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Configured logger instance
    """
    return get_logger(
        __name__,
        level=getattr(logging, log_level.upper(), logging.INFO),
        log_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'upload_files.log')
    )


def copy_and_overwrite(src_path: pathlib.Path, dst_path: pathlib.Path) -> None:
    """
    Read the entire contents of *src_path* and overwrite *dst_path* with them.

    If *dst_path* doesn't exist it will be created; if it does exist
    it is truncated to zero bytes before writing the new data.
    
    Args:
        src_path: Source file path
        dst_path: Destination file path
    """
    if not src_path.is_file():
        sys.exit(f"Error: source file '{src_path}' does not exist or is not a file.")

    # Make sure the destination directory exists
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    # Open destination in write-binary mode — this clears it automatically
    with src_path.open("rb") as src, dst_path.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)  # stream in 1-MiB chunks

    print(f"Copied '{src_path}' → '{dst_path}' (overwrote any previous contents).")


def discover_control_files(control_files_dir: str = None) -> List[str]:
    """
    Discover control files in the specified directory.
    
    Args:
        control_files_dir: Directory containing control files
        
    Returns:
        List of control file paths
    """
    # Use proper path resolution
    if control_files_dir is None:
        # Default to control_files directory relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        control_files_dir = os.path.join(script_dir, "control_files")
    
    control_dir = Path(control_files_dir)
    if not control_dir.exists():
        return []
    
    control_files = []
    for file_path in control_dir.glob("*.ctl"):
        if file_path.is_file():
            control_files.append(str(file_path))
    
    return sorted(control_files)


def extract_region_parameter(file_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract region and parameter from control file path.
    
    Args:
        file_path: Path to control file
        
    Returns:
        Tuple of (region, parameter)
    """
    try:
        filename = Path(file_path).stem
        # Expected format: REGION_parameter_control
        parts = filename.split('_')
        if len(parts) >= 2:
            region = parts[0]
            parameter = parts[1]
            return region, parameter
    except Exception:
        pass
    
    return None, None


def submit_single_file(file_path: str,
                      dest_file: str = None,
                      rate_limit_delay: float = 1.0,
                      logger: Optional[logging.Logger] = None,
                      date_range: Optional[DateRange] = None) -> Dict[str, Any]:
    """
    Submit a single control file.
    
    Args:
        file_path: Path to control file to submit
        dest_file: Destination file path for submission
        rate_limit_delay: Delay between submissions in seconds
        logger: Optional logger instance
        
    Returns:
        Dictionary with submission result
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    result = {
        'success': False,
        'file_path': file_path,
        'request_id': None,
        'error_message': None,
        'response_data': None,
        'date_modified': False,
        'modified_file': None
    }
    
    try:
        # Handle date modification if date_range is provided
        file_to_submit = file_path
        if date_range and AUTOMATION_AVAILABLE:
            try:
                date_manager = DateManager(logger=logger)
                modified_file = date_manager.modify_ctl_file_dates(file_path, date_range)
                file_to_submit = modified_file
                result['date_modified'] = True
                result['modified_file'] = modified_file
                logger.info(f"Applied date range {date_range} to {file_path}")
            except Exception as e:
                logger.warning(f"Failed to apply date range to {file_path}: {e}")
                # Continue with original file
        
        # Handle destination file path
        if dest_file is None:
            # Default to current directory
            dest_file = os.path.join(os.getcwd(), "ds0841.1_control.ctl")
        
        # Copy file to destination
        source_file = pathlib.Path(file_to_submit)
        dest_file_path = pathlib.Path(dest_file)
        
        copy_and_overwrite(source_file, dest_file_path)
        
        # Submit the file
        logger.info(f"Submitting {file_path}...")
        response = rc.submit(dest_file_path)
        
        # Parse response
        if isinstance(response, dict):
            result['response_data'] = response
            
            if response.get('http_response') == 200:
                # Extract request ID
                request_id = None
                if 'request_id' in response:
                    request_id = str(response['request_id'])
                elif 'id' in response:
                    request_id = str(response['id'])
                elif 'request_index' in response:
                    request_id = str(response['request_index'])
                
                result['success'] = True
                result['request_id'] = request_id
                logger.info(f"Successfully submitted {file_path} -> Request ID: {request_id}")
            else:
                result['error_message'] = f"HTTP {response.get('http_response')}: {response.get('message', 'Unknown error')}"
                logger.error(f"Failed to submit {file_path}: {result['error_message']}")
        else:
            # Handle non-dict response
            result['success'] = True
            result['response_data'] = {'raw_response': str(response)}
            logger.info(f"Submitted {file_path} (raw response)")
        
        # Rate limiting delay
        if rate_limit_delay > 0:
            time.sleep(rate_limit_delay)
            
    except Exception as e:
        result['error_message'] = str(e)
        logger.error(f"Exception submitting {file_path}: {e}")
    
    return result


def submit_batch_files(file_paths: List[str],
                      dest_file: str = None,
                      rate_limit_delay: float = 1.0,
                      session_id: Optional[str] = None,
                      state_manager: Optional[Any] = None,
                      logger: Optional[logging.Logger] = None,
                      date_range: Optional[DateRange] = None) -> Dict[str, Any]:
    """
    Submit a batch of control files.
    
    Args:
        file_paths: List of control file paths to submit
        dest_file: Destination file path for submission
        rate_limit_delay: Delay between submissions in seconds
        session_id: Optional session ID for state tracking
        state_manager: Optional state manager for tracking
        logger: Optional logger instance
        
    Returns:
        Dictionary with batch submission results
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    results = {
        'success': True,
        'submitted_files': [],
        'failed_files': [],
        'request_ids': [],
        'errors': [],
        'total_files': len(file_paths),
        'start_time': datetime.now(timezone.utc).isoformat(),
        'end_time': None
    }
    
    logger.info(f"Starting batch submission of {len(file_paths)} files")
    
    for file_path in file_paths:
        try:
            # Update state if available
            if state_manager and session_id:
                state_manager.update_file_status(
                    session_id, file_path, FileStatus.SUBMITTED
                )
            
            # Submit the file
            result = submit_single_file(
                file_path, dest_file, rate_limit_delay, logger, date_range
            )
            
            if result['success']:
                results['submitted_files'].append(file_path)
                if result['request_id']:
                    results['request_ids'].append(result['request_id'])
                
                # Update state
                if state_manager and session_id:
                    state_manager.update_file_status(
                        session_id, file_path, FileStatus.PROCESSING,
                        request_id=result['request_id']
                    )
            else:
                results['failed_files'].append(file_path)
                results['errors'].append(f"{file_path}: {result['error_message']}")
                
                # Update state
                if state_manager and session_id:
                    state_manager.update_file_status(
                        session_id, file_path, FileStatus.FAILED,
                        error_message=result['error_message']
                    )
                    
        except Exception as e:
            results['failed_files'].append(file_path)
            results['errors'].append(f"{file_path}: {str(e)}")
            logger.error(f"Unexpected error processing {file_path}: {e}")
    
    # Update overall success
    results['success'] = len(results['submitted_files']) > 0
    results['end_time'] = datetime.now(timezone.utc).isoformat()
    
    logger.info(f"Batch submission completed: {len(results['submitted_files'])} succeeded, "
                f"{len(results['failed_files'])} failed")
    
    return results


def load_file_list_from_config(config_path: str) -> List[str]:
    """
    Load file list from configuration file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        List of file paths
    """
    try:
        config_file = Path(config_path)
        if config_file.suffix.lower() == '.json':
            with open(config_file, 'r') as f:
                config = json.load(f)
        elif config_file.suffix.lower() in ['.yaml', '.yml']:
            import yaml
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
        else:
            # Assume text file with one path per line
            with open(config_file, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        
        # Extract file paths from config
        if isinstance(config, dict):
            return config.get('files_to_upload', [])
        elif isinstance(config, list):
            return config
        else:
            return []
            
    except Exception as e:
        print(f"Error loading config file {config_path}: {e}")
        return []


def run_legacy_mode() -> int:
    """
    Run in legacy mode (original functionality).
    
    Returns:
        Exit code
    """
    print("Running in legacy mode...")
    
    # Original hardcoded file list
    files_to_upload = [
        "AZPS_temp_control.ctl", "AZPS_dswrf_control.ctl", 
        "AZPS_wind_control.ctl",
        "WACM_temp_control.ctl",
        "WACM_rain_control.ctl",
        "WACM_wind_control.ctl",
        "WACM_dswrf_control.ctl", 
        "TVA_temp_control.ctl"
    ]
    
    # Convert to full paths
    control_files_dir = Path("../control_files")
    full_paths = []
    for file in files_to_upload:
        file_path = control_files_dir / file
        if file_path.exists():
            full_paths.append(str(file_path))
        else:
            print(f"Warning: File not found: {file_path}")
    
    if not full_paths:
        print("No files found to upload")
        return 1
    
    # Submit files
    results = submit_batch_files(full_paths)
    
    # Print results
    print(f"\nResults:")
    print(f"  Submitted: {len(results['submitted_files'])}")
    print(f"  Failed: {len(results['failed_files'])}")
    print(f"  Request IDs: {results['request_ids']}")
    
    if results['errors']:
        print(f"  Errors:")
        for error in results['errors']:
            print(f"    - {error}")
    
    return 0 if results['success'] else 1


def run_automation_mode(config_manager: Any,
                       state_manager: Any,
                       session_id: str,
                       file_paths: List[str],
                       logger: logging.Logger,
                       date_range: Optional[DateRange] = None) -> Dict[str, Any]:
    """
    Run in automation mode with full integration.
    
    Args:
        config_manager: Configuration manager instance
        state_manager: State manager instance
        session_id: Session ID for tracking
        file_paths: List of file paths to submit
        logger: Logger instance
        
    Returns:
        Dictionary with results
    """
    logger.info("Running in automation mode...")
    
    # Get configuration
    dest_file = config_manager.get('upload.dest_file', './ds0841.1_control.ctl')
    rate_limit_delay = config_manager.get('upload.rate_limit_delay', 1.0)
    
    # Submit files with automation integration
    results = submit_batch_files(
        file_paths=file_paths,
        dest_file=dest_file,
        rate_limit_delay=rate_limit_delay,
        session_id=session_id,
        state_manager=state_manager,
        logger=logger,
        date_range=date_range
    )
    
    return results


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Upload RDA control files with automation support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Legacy mode (original functionality)
  python upload_files.py --legacy

  # Upload specific files
  python upload_files.py --files file1.ctl file2.ctl file3.ctl

  # Auto-discover and upload all control files
  python upload_files.py --auto-discover

  # Upload from configuration file
  python upload_files.py --config upload_config.json

  # Upload with custom destination and rate limiting
  python upload_files.py --files *.ctl --dest-file custom.ctl --rate-limit 3.0

  # Automation mode (requires automation framework)
  python upload_files.py --automation --session-id abc123 --auto-discover
        """
    )
    
    # Operation mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--legacy', action='store_true',
                           help='Run in legacy mode (original functionality)')
    mode_group.add_argument('--automation', action='store_true',
                           help='Run in automation mode (requires automation framework)')
    
    # File selection
    file_group = parser.add_mutually_exclusive_group()
    file_group.add_argument('--files', nargs='+', metavar='FILE',
                           help='Specific control files to upload')
    file_group.add_argument('--auto-discover', action='store_true',
                           help='Auto-discover control files in control_files directory')
    file_group.add_argument('--config', metavar='FILE',
                           help='Load file list from configuration file')
    
    # Upload options
    parser.add_argument('--dest-file', default=None,
                       help='Destination file for submission (default: ./ds0841.1_control.ctl)')
    parser.add_argument('--rate-limit', type=float, default=1.0, metavar='SECONDS',
                       help='Delay between submissions in seconds (default: 1.0)')
    parser.add_argument('--control-files-dir', default=None,
                       help='Directory containing control files (default: ./src/python/control_files)')
    
    # Automation options
    parser.add_argument('--session-id', metavar='ID',
                       help='Session ID for automation tracking')
    parser.add_argument('--config-file', metavar='FILE',
                       help='Automation configuration file')
    
    # Date range options
    date_group = parser.add_argument_group('Date Range Options')
    date_group.add_argument('--start-date',
                           help='Start date for CTL file processing (formats: YYYY-MM-DD, YYYYMMDDHHMM, "last 7 days", etc.)')
    date_group.add_argument('--end-date',
                           help='End date for CTL file processing (formats: YYYY-MM-DD, YYYYMMDDHHMM, etc.)')
    date_group.add_argument('--date-range',
                           help='Date range string (e.g., "2021-01-01 to 2021-12-31", "202101010000/to/202112310000", "last 30 days")')
    date_group.add_argument('--ctl-date-format',
                           help='CTL date format string (e.g., "202101010000/to/202112310000")')
    date_group.add_argument('--date-suggestions', action='store_true',
                           help='Show common date range suggestions and exit')
    
    # Output options
    parser.add_argument('--output', metavar='FILE',
                       help='Save results to JSON file')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Set logging level')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.log_level)
    
    # Ensure logs directory exists
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(script_dir, 'logs')
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        # Handle date range arguments
        date_range = None
        if args.date_suggestions:
            # Show date suggestions and exit
            if AUTOMATION_AVAILABLE:
                temp_date_manager = DateManager()
                suggestions = temp_date_manager.get_date_suggestions()
                print("Common Date Range Suggestions:")
                for name, range_str in suggestions.items():
                    print(f"  {name}: {range_str}")
            else:
                print("Date management features require automation components")
            return 0
        
        if args.ctl_date_format:
            # Parse CTL date format string
            if AUTOMATION_AVAILABLE:
                try:
                    temp_date_manager = DateManager()
                    date_range = temp_date_manager.parse_ctl_date_format(args.ctl_date_format)
                    print(f"📅 Using CTL date format: {date_range}")
                except Exception as e:
                    print(f"❌ Error parsing CTL date format '{args.ctl_date_format}': {e}")
                    return 1
            else:
                print("❌ CTL date format features require automation components")
                return 1
        elif args.date_range:
            # Parse date range string
            if AUTOMATION_AVAILABLE:
                try:
                    temp_date_manager = DateManager()
                    date_range = temp_date_manager.parse_date_range_string(args.date_range)
                    print(f"📅 Using date range: {date_range}")
                except Exception as e:
                    print(f"❌ Error parsing date range '{args.date_range}': {e}")
                    return 1
            else:
                print("❌ Date range features require automation components")
                return 1
        elif args.start_date and args.end_date:
            # Parse start and end dates
            if AUTOMATION_AVAILABLE:
                try:
                    temp_date_manager = DateManager()
                    date_range = temp_date_manager.parse_date_range(args.start_date, args.end_date)
                    print(f"📅 Using date range: {date_range}")
                except Exception as e:
                    print(f"❌ Error parsing date range '{args.start_date}' to '{args.end_date}': {e}")
                    return 1
            else:
                print("❌ Date range features require automation components")
                return 1
        elif args.start_date or args.end_date:
            print("❌ Both --start-date and --end-date must be provided together")
            return 1
        
        # Handle legacy mode
        if args.legacy:
            return run_legacy_mode()
        
        # Determine file list
        file_paths = []
        
        if args.files:
            file_paths = args.files
        elif args.auto_discover:
            file_paths = discover_control_files(args.control_files_dir)
            if not file_paths:
                logger.error(f"No control files found in {args.control_files_dir}")
                return 1
        elif args.config:
            file_paths = load_file_list_from_config(args.config)
            if not file_paths:
                logger.error(f"No files loaded from config {args.config}")
                return 1
        else:
            # Default: auto-discover
            file_paths = discover_control_files(args.control_files_dir)
            if not file_paths:
                logger.error("No files specified and auto-discovery found no files")
                return 1
        
        logger.info(f"Found {len(file_paths)} files to upload")
        if date_range:
            logger.info(f"Will apply date range: {date_range.start_date.strftime('%Y-%m-%d')} to {date_range.end_date.strftime('%Y-%m-%d')}")
        
        # Handle automation mode
        if args.automation:
            if not AUTOMATION_AVAILABLE:
                logger.error("Automation mode requested but automation components not available")
                return 1
            
            if not args.session_id:
                logger.error("Session ID required for automation mode")
                return 1
            
            # Initialize automation components
            config_manager = ConfigManager(args.config_file)
            state_manager = StateManager(config_manager)
            
            results = run_automation_mode(
                config_manager, state_manager, args.session_id, file_paths, logger, date_range
            )
        else:
            # Standard mode
            # Handle default dest_file
            dest_file = args.dest_file
            if dest_file is None:
                dest_file = os.path.join(os.getcwd(), "ds0841.1_control.ctl")
            
            results = submit_batch_files(
                file_paths=file_paths,
                dest_file=dest_file,
                rate_limit_delay=args.rate_limit,
                logger=logger,
                date_range=date_range
            )
        
        # Save results to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to {args.output}")
        
        # Print summary
        print(f"\nUpload Summary:")
        print(f"  Total files: {results.get('total_files', len(file_paths))}")
        print(f"  Submitted: {len(results.get('submitted_files', []))}")
        print(f"  Failed: {len(results.get('failed_files', []))}")
        print(f"  Request IDs: {len(results.get('request_ids', []))}")
        
        if results.get('errors'):
            print(f"  Errors:")
            for error in results['errors'][:5]:  # Show first 5 errors
                print(f"    - {error}")
            if len(results['errors']) > 5:
                print(f"    ... and {len(results['errors']) - 5} more errors")
        
        return 0 if results.get('success', False) else 1
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())