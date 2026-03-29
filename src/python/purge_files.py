#!/usr/bin/env python3
"""
Purge Files Script for RDA Automation System

Provides manual and automated purging of completed RDA requests with safety checks,
confirmation mechanisms, and integration with the automation framework.

This script can be used standalone or integrated with the automation system.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import rdams_client as rc
from logger_utils import get_logger


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
        log_file='./src/python/logs/purge_files.log'
    )


def load_automation_config() -> Optional[Dict[str, Any]]:
    """
    Load automation configuration if available.
    
    Returns:
        Configuration dictionary or None if not available
    """
    try:
        # Try to load automation configuration
        config_path = Path('./src/python/config/automation_config.yaml')
        if config_path.exists():
            import yaml
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
    except Exception:
        pass
    return None


def get_request_status() -> Dict[str, Any]:
    """
    Get current status of all requests.
    
    Returns:
        Status dictionary from RDA API
    """
    try:
        return rc.get_status()
    except Exception as e:
        raise Exception(f"Failed to get request status: {e}")


def extract_request_info(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relevant information from request data.
    
    Args:
        request_data: Raw request data from API
        
    Returns:
        Processed request information
    """
    return {
        'request_index': request_data.get('request_index'),
        'status': request_data.get('status'),
        'date_submitted': request_data.get('date_submitted'),
        'date_completed': request_data.get('date_completed'),
        'file_size': request_data.get('file_size', 0),
        'subset_info': request_data.get('subset_info', {}),
        'rinfo': request_data.get('rinfo', ''),
        'wfile': request_data.get('wfile', '')
    }


def is_request_eligible_for_purge(request_info: Dict[str, Any], 
                                 min_age_hours: int = 24,
                                 require_completion: bool = True) -> tuple[bool, str]:
    """
    Check if a request is eligible for purging.
    
    Args:
        request_info: Request information dictionary
        min_age_hours: Minimum age in hours before eligible for purging
        require_completion: Whether to require completion status
        
    Returns:
        Tuple of (eligible, reason)
    """
    request_id = request_info.get('request_index')
    status = request_info.get('status')
    
    # Check completion status
    if require_completion and status != 'Completed':
        return False, f"Request {request_id} is not completed (status: {status})"
    
    # Check minimum age
    date_completed = request_info.get('date_completed')
    if date_completed:
        try:
            # Parse completion date (assuming ISO format or similar)
            if isinstance(date_completed, str):
                # Try different date formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                    try:
                        completed_dt = datetime.strptime(date_completed, fmt)
                        completed_dt = completed_dt.replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
                else:
                    # If no format matches, assume recent
                    return False, f"Request {request_id} has unparseable completion date"
            else:
                completed_dt = date_completed
                
            age = datetime.now(timezone.utc) - completed_dt
            age_hours = age.total_seconds() / 3600
            
            if age_hours < min_age_hours:
                return False, f"Request {request_id} is too recent ({age_hours:.1f}h < {min_age_hours}h)"
                
        except Exception as e:
            return False, f"Request {request_id} has invalid completion date: {e}"
    
    return True, f"Request {request_id} is eligible for purging"


def purge_request(request_id: str, session_id: Optional[str] = None, 
                 dry_run: bool = False) -> bool:
    """
    Purge a single request.
    
    Args:
        request_id: Request identifier
        session_id: Optional session identifier
        dry_run: If True, only simulate the purge
        
    Returns:
        True if purge was successful
    """
    if dry_run:
        print(f"DRY RUN: Would purge request {request_id}")
        return True
    
    try:
        success = rc.purge_request(request_id, session_id)
        if success:
            print(f"Successfully purged request {request_id}")
            return True
        else:
            print(f"Failed to purge request {request_id}")
            return False
    except Exception as e:
        print(f"Error purging request {request_id}: {e}")
        return False


def purge_completed_requests(min_age_hours: int = 24, 
                           max_requests: int = 10,
                           dry_run: bool = False,
                           interactive: bool = True,
                           status_filter: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Purge completed requests based on criteria.
    
    Args:
        min_age_hours: Minimum age in hours before eligible for purging
        max_requests: Maximum number of requests to purge
        dry_run: If True, only simulate the purges
        interactive: If True, ask for confirmation
        status_filter: Optional list of statuses to filter by
        
    Returns:
        Dictionary with purge results
    """
    logger = logging.getLogger(__name__)
    
    # Get current status
    logger.info("Fetching request status...")
    try:
        status_data = get_request_status()
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        return {'success': False, 'error': str(e)}
    
    if 'data' not in status_data:
        logger.error("No data in status response")
        return {'success': False, 'error': 'No data in status response'}
    
    # Filter eligible requests
    eligible_requests = []
    for request_data in status_data['data']:
        request_info = extract_request_info(request_data)
        
        # Apply status filter
        if status_filter and request_info['status'] not in status_filter:
            continue
        
        # Check eligibility
        eligible, reason = is_request_eligible_for_purge(
            request_info, min_age_hours=min_age_hours
        )
        
        if eligible:
            eligible_requests.append(request_info)
            logger.info(f"Eligible for purge: {request_info['request_index']} - {reason}")
        else:
            logger.debug(f"Not eligible: {reason}")
    
    if not eligible_requests:
        logger.info("No requests eligible for purging")
        return {
            'success': True,
            'purged_requests': [],
            'failed_requests': [],
            'message': 'No eligible requests found'
        }
    
    # Limit number of requests
    if len(eligible_requests) > max_requests:
        logger.info(f"Limiting purge to {max_requests} requests (found {len(eligible_requests)} eligible)")
        eligible_requests = eligible_requests[:max_requests]
    
    # Interactive confirmation
    if interactive and not dry_run:
        print(f"\nFound {len(eligible_requests)} requests eligible for purging:")
        for req in eligible_requests:
            print(f"  - Request {req['request_index']}: {req['status']} "
                  f"(completed: {req.get('date_completed', 'unknown')})")
        
        response = input(f"\nProceed with purging {len(eligible_requests)} requests? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            logger.info("Purge cancelled by user")
            return {
                'success': False,
                'purged_requests': [],
                'failed_requests': [],
                'cancelled_requests': [req['request_index'] for req in eligible_requests],
                'message': 'Cancelled by user'
            }
    
    # Execute purges
    results = {
        'success': True,
        'purged_requests': [],
        'failed_requests': [],
        'cancelled_requests': []
    }
    
    logger.info(f"Starting purge of {len(eligible_requests)} requests...")
    
    for request_info in eligible_requests:
        request_id = str(request_info['request_index'])
        
        try:
            success = purge_request(request_id, dry_run=dry_run)
            if success:
                results['purged_requests'].append(request_id)
                logger.info(f"Purged request {request_id}")
            else:
                results['failed_requests'].append(request_id)
                logger.error(f"Failed to purge request {request_id}")
                
            # Small delay between purges to be respectful to the API
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Exception purging request {request_id}: {e}")
            results['failed_requests'].append(request_id)
    
    # Update overall success
    results['success'] = len(results['failed_requests']) == 0
    
    logger.info(f"Purge completed: {len(results['purged_requests'])} purged, "
                f"{len(results['failed_requests'])} failed")
    
    return results


def purge_specific_requests(request_ids: List[str], 
                          dry_run: bool = False,
                          interactive: bool = True) -> Dict[str, Any]:
    """
    Purge specific requests by ID.
    
    Args:
        request_ids: List of request IDs to purge
        dry_run: If True, only simulate the purges
        interactive: If True, ask for confirmation
        
    Returns:
        Dictionary with purge results
    """
    logger = logging.getLogger(__name__)
    
    if not request_ids:
        return {
            'success': True,
            'purged_requests': [],
            'failed_requests': [],
            'message': 'No request IDs provided'
        }
    
    # Interactive confirmation
    if interactive and not dry_run:
        print(f"\nRequests to purge:")
        for req_id in request_ids:
            print(f"  - Request {req_id}")
        
        response = input(f"\nProceed with purging {len(request_ids)} requests? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            logger.info("Purge cancelled by user")
            return {
                'success': False,
                'purged_requests': [],
                'failed_requests': [],
                'cancelled_requests': request_ids,
                'message': 'Cancelled by user'
            }
    
    # Execute purges
    results = {
        'success': True,
        'purged_requests': [],
        'failed_requests': [],
        'cancelled_requests': []
    }
    
    logger.info(f"Starting purge of {len(request_ids)} specific requests...")
    
    for request_id in request_ids:
        try:
            success = purge_request(request_id, dry_run=dry_run)
            if success:
                results['purged_requests'].append(request_id)
                logger.info(f"Purged request {request_id}")
            else:
                results['failed_requests'].append(request_id)
                logger.error(f"Failed to purge request {request_id}")
                
            # Small delay between purges
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Exception purging request {request_id}: {e}")
            results['failed_requests'].append(request_id)
    
    # Update overall success
    results['success'] = len(results['failed_requests']) == 0
    
    logger.info(f"Specific purge completed: {len(results['purged_requests'])} purged, "
                f"{len(results['failed_requests'])} failed")
    
    return results


def list_purgeable_requests(min_age_hours: int = 24,
                           status_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    List requests that are eligible for purging.
    
    Args:
        min_age_hours: Minimum age in hours before eligible for purging
        status_filter: Optional list of statuses to filter by
        
    Returns:
        List of eligible request information
    """
    logger = logging.getLogger(__name__)
    
    try:
        status_data = get_request_status()
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        return []
    
    if 'data' not in status_data:
        logger.error("No data in status response")
        return []
    
    eligible_requests = []
    for request_data in status_data['data']:
        request_info = extract_request_info(request_data)
        
        # Apply status filter
        if status_filter and request_info['status'] not in status_filter:
            continue
        
        # Check eligibility
        eligible, reason = is_request_eligible_for_purge(
            request_info, min_age_hours=min_age_hours
        )
        
        if eligible:
            request_info['purge_reason'] = reason
            eligible_requests.append(request_info)
    
    return eligible_requests


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Purge completed RDA requests with safety checks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List purgeable requests
  python purge_files.py --list

  # Purge completed requests older than 48 hours (dry run)
  python purge_files.py --auto --min-age 48 --dry-run

  # Purge specific requests
  python purge_files.py --requests 12345 67890 --no-interactive

  # Purge up to 5 completed requests with confirmation
  python purge_files.py --auto --max-requests 5

  # Purge failed requests for cleanup
  python purge_files.py --auto --status Failed --no-interactive
        """
    )
    
    # Operation mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--list', action='store_true',
                           help='List requests eligible for purging')
    mode_group.add_argument('--auto', action='store_true',
                           help='Automatically purge eligible requests')
    mode_group.add_argument('--requests', nargs='+', metavar='ID',
                           help='Purge specific request IDs')
    
    # Filtering options
    parser.add_argument('--min-age', type=int, default=24, metavar='HOURS',
                       help='Minimum age in hours before eligible for purging (default: 24)')
    parser.add_argument('--max-requests', type=int, default=10, metavar='N',
                       help='Maximum number of requests to purge (default: 10)')
    parser.add_argument('--status', nargs='+', metavar='STATUS',
                       help='Filter by status (e.g., Completed, Failed)')
    
    # Execution options
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be purged without actually purging')
    parser.add_argument('--no-interactive', action='store_true',
                       help='Skip confirmation prompts')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Set logging level')
    
    # Output options
    parser.add_argument('--output', metavar='FILE',
                       help='Save results to JSON file')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.log_level)
    
    # Ensure logs directory exists
    Path('./src/python/logs').mkdir(parents=True, exist_ok=True)
    
    try:
        if args.list:
            # List purgeable requests
            logger.info("Listing requests eligible for purging...")
            eligible_requests = list_purgeable_requests(
                min_age_hours=args.min_age,
                status_filter=args.status
            )
            
            if not eligible_requests:
                print("No requests eligible for purging.")
                return 0
            
            print(f"\nFound {len(eligible_requests)} requests eligible for purging:")
            print("-" * 80)
            for req in eligible_requests:
                print(f"Request {req['request_index']}: {req['status']}")
                print(f"  Completed: {req.get('date_completed', 'unknown')}")
                print(f"  Size: {req.get('file_size', 0)} bytes")
                print(f"  Reason: {req.get('purge_reason', 'eligible')}")
                print()
            
            results = {'eligible_requests': eligible_requests}
            
        elif args.auto:
            # Auto-purge eligible requests
            logger.info("Starting automatic purge of eligible requests...")
            results = purge_completed_requests(
                min_age_hours=args.min_age,
                max_requests=args.max_requests,
                dry_run=args.dry_run,
                interactive=not args.no_interactive,
                status_filter=args.status
            )
            
        elif args.requests:
            # Purge specific requests
            logger.info(f"Purging specific requests: {args.requests}")
            results = purge_specific_requests(
                request_ids=args.requests,
                dry_run=args.dry_run,
                interactive=not args.no_interactive
            )
        
        # Save results to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to {args.output}")
        
        # Print summary
        if 'purged_requests' in results:
            print(f"\nSummary:")
            print(f"  Purged: {len(results.get('purged_requests', []))}")
            print(f"  Failed: {len(results.get('failed_requests', []))}")
            print(f"  Cancelled: {len(results.get('cancelled_requests', []))}")
            
            if not results.get('success', True):
                return 1
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
