#!/usr/bin/env python3
"""
Fix Completed Requests Module

This module provides functionality to scan for completed RDA requests in the database
and download their associated files. It integrates with the existing automation system
to handle completed requests that may not have been downloaded yet.

Functions:
    - get_completed_requests_from_database(): Get list of completed requests from database
    - download_all_completed_requests(): Download all completed requests
    - show_status(): Display status of completed requests
    - verify_downloads(): Verify that downloads completed successfully
    - download_specific_requests(): Download specific requests by their indices
"""

import os
import sys
import sqlite3
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from rdams_client import get_status, download, get_filelist
except ImportError:
    print("Warning: Could not import rdams_client functionality")
    # Define fallback functions
    def get_status(request_idx):
        return {"status": "unknown", "error": "rdams_client not available"}
    
    def download(request_idx, out_dir='./'):
        print(f"Warning: Cannot download request {request_idx} - rdams_client not available")
        return {"error": "rdams_client not available"}
    
    def get_filelist(request_idx):
        return {"data": [], "error": "rdams_client not available"}


def setup_logging() -> logging.Logger:
    """Setup logging for the fix completed requests module."""
    logger = logging.getLogger('fix_completed_requests')
    
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
        
        logger.setLevel(logging.INFO)
    
    return logger


def get_completed_requests_from_database(db_path: str = "src/python/data/automation_state.db") -> List[Dict]:
    """
    Get completed requests from the database that may need downloading.
    
    Args:
        db_path: Path to the automation state database
        
    Returns:
        List of dictionaries containing completed request information
    """
    logger = setup_logging()
    
    try:
        if not os.path.exists(db_path):
            logger.warning(f"Database file does not exist: {db_path}")
            return []
        
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            # Query for completed requests that haven't been downloaded yet
            query = """
            SELECT 
                id,
                request_id,
                request_index,
                control_file_path,
                region,
                variable_type,
                status,
                submission_time,
                completion_time,
                download_time,
                download_directory,
                file_size,
                processing_duration,
                error_message,
                retry_count,
                dsid,
                date_rqst,
                date_ready,
                date_purge,
                location,
                created_at,
                updated_at
            FROM rda_requests 
            WHERE status IN ('completed', 'ready', 'finished')
            AND (download_time IS NULL OR download_time = '')
            ORDER BY completion_time DESC
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            completed_requests = []
            for row in rows:
                request_dict = {
                    'id': row['id'],
                    'request_id': row['request_id'],
                    'request_index': row['request_index'],
                    'control_file_path': row['control_file_path'],
                    'region': row['region'],
                    'variable_type': row['variable_type'],
                    'status': row['status'],
                    'submission_time': row['submission_time'],
                    'completion_time': row['completion_time'],
                    'download_time': row['download_time'],
                    'download_directory': row['download_directory'],
                    'file_size': row['file_size'],
                    'processing_duration': row['processing_duration'],
                    'error_message': row['error_message'],
                    'retry_count': row['retry_count'],
                    'dsid': row['dsid'],
                    'date_rqst': row['date_rqst'],
                    'date_ready': row['date_ready'],
                    'date_purge': row['date_purge'],
                    'location': row['location'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                completed_requests.append(request_dict)
            
            logger.info(f"Found {len(completed_requests)} completed requests needing download")
            return completed_requests
            
    except Exception as e:
        logger.error(f"Error getting completed requests from database: {e}")
        return []


def download_all_completed_requests(db_path: str = "src/python/data/automation_state.db"):
    """
    Download all completed requests found in the database.
    
    Args:
        db_path: Path to the automation state database
    """
    logger = setup_logging()
    
    try:
        logger.info("🚀 Starting download of all completed requests...")
        
        # Get completed requests
        completed_requests = get_completed_requests_from_database(db_path)
        
        if not completed_requests:
            logger.info("No completed requests found that need downloading")
            return
        
        logger.info(f"Found {len(completed_requests)} requests to download")
        
        # Download each request
        successful_downloads = 0
        failed_downloads = 0
        
        for request in completed_requests:
            request_index = request.get('request_index')
            request_id = request.get('request_id', 'unknown')
            
            if not request_index:
                logger.warning(f"Skipping request {request_id} - no request_index")
                failed_downloads += 1
                continue
            
            try:
                logger.info(f"📥 Downloading request {request_index} ({request_id})...")
                
                # Create download directory if specified
                download_dir = request.get('download_directory', './downloads')
                if download_dir and download_dir != './':
                    os.makedirs(download_dir, exist_ok=True)
                    result = download(str(request_index), download_dir)
                else:
                    result = download(str(request_index))
                
                # Update database with download time
                _update_download_time(db_path, request['id'], datetime.now().isoformat())
                
                successful_downloads += 1
                logger.info(f"✅ Successfully downloaded request {request_index}")
                
            except Exception as e:
                logger.error(f"❌ Failed to download request {request_index}: {e}")
                failed_downloads += 1
        
        logger.info(f"🎉 Download completed: {successful_downloads} successful, {failed_downloads} failed")
        
    except Exception as e:
        logger.error(f"Error in download_all_completed_requests: {e}")


def show_status(db_path: str = "src/python/data/automation_state.db"):
    """
    Show status of completed requests in the database.
    
    Args:
        db_path: Path to the automation state database
    """
    logger = setup_logging()
    
    try:
        completed_requests = get_completed_requests_from_database(db_path)
        
        print("\n" + "="*80)
        print("🔄 COMPLETED REQUESTS STATUS")
        print("="*80)
        
        if not completed_requests:
            print("No completed requests found that need downloading")
            print("="*80)
            return
        
        print(f"Total completed requests needing download: {len(completed_requests)}")
        print()
        
        # Group by region
        by_region = {}
        for request in completed_requests:
            region = request.get('region', 'unknown')
            if region not in by_region:
                by_region[region] = []
            by_region[region].append(request)
        
        for region, requests in by_region.items():
            print(f"📍 Region: {region} ({len(requests)} requests)")
            for request in requests[:5]:  # Show first 5 requests per region
                request_index = request.get('request_index', 'N/A')
                variable_type = request.get('variable_type', 'N/A')
                completion_time = request.get('completion_time', 'N/A')
                print(f"  • Request {request_index} - {variable_type} - Completed: {completion_time}")
            
            if len(requests) > 5:
                print(f"  ... and {len(requests) - 5} more requests")
            print()
        
        print("="*80)
        
    except Exception as e:
        logger.error(f"Error showing status: {e}")


def verify_downloads(db_path: str = "src/python/data/automation_state.db"):
    """
    Verify that downloads completed successfully by checking file existence.
    
    Args:
        db_path: Path to the automation state database
    """
    logger = setup_logging()
    
    try:
        logger.info("🔍 Verifying downloads...")
        
        if not os.path.exists(db_path):
            logger.warning(f"Database file does not exist: {db_path}")
            return
        
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query for requests that have been downloaded
            query = """
            SELECT 
                request_id,
                request_index,
                download_directory,
                download_time,
                region,
                variable_type
            FROM rda_requests 
            WHERE download_time IS NOT NULL AND download_time != ''
            ORDER BY download_time DESC
            LIMIT 50
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            if not rows:
                logger.info("No downloaded requests found to verify")
                return
            
            verified_count = 0
            missing_count = 0
            
            for row in rows:
                request_index = row['request_index']
                download_dir = row['download_directory'] or './downloads'
                
                if not request_index:
                    continue
                
                # Check if download directory exists and has files
                if os.path.exists(download_dir):
                    files = list(Path(download_dir).glob('*'))
                    if files:
                        verified_count += 1
                        logger.debug(f"✅ Verified request {request_index} - {len(files)} files in {download_dir}")
                    else:
                        missing_count += 1
                        logger.warning(f"⚠️  Request {request_index} - directory exists but no files found")
                else:
                    missing_count += 1
                    logger.warning(f"❌ Request {request_index} - download directory not found: {download_dir}")
            
            logger.info(f"📊 Verification complete: {verified_count} verified, {missing_count} missing/incomplete")
            
    except Exception as e:
        logger.error(f"Error verifying downloads: {e}")


def download_specific_requests(request_indices: List[str], db_path: str = "src/python/data/automation_state.db"):
    """
    Download specific requests by their indices.
    
    Args:
        request_indices: List of request indices to download
        db_path: Path to the automation state database
    """
    logger = setup_logging()
    
    try:
        logger.info(f"🎯 Downloading specific requests: {', '.join(request_indices)}")
        
        successful_downloads = 0
        failed_downloads = 0
        
        for request_index in request_indices:
            try:
                logger.info(f"📥 Downloading request {request_index}...")
                
                # Get request info from database if available
                download_dir = _get_download_directory(db_path, request_index)
                
                if download_dir and download_dir != './':
                    os.makedirs(download_dir, exist_ok=True)
                    result = download(str(request_index), download_dir)
                else:
                    result = download(str(request_index))
                
                # Update database with download time if request exists in database
                _update_download_time_by_index(db_path, request_index, datetime.now().isoformat())
                
                successful_downloads += 1
                logger.info(f"✅ Successfully downloaded request {request_index}")
                
            except Exception as e:
                logger.error(f"❌ Failed to download request {request_index}: {e}")
                failed_downloads += 1
        
        logger.info(f"🎉 Specific download completed: {successful_downloads} successful, {failed_downloads} failed")
        
    except Exception as e:
        logger.error(f"Error in download_specific_requests: {e}")


def _update_download_time(db_path: str, request_id: int, download_time: str):
    """Update the download time for a specific request in the database."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE rda_requests SET download_time = ?, updated_at = ? WHERE id = ?",
                (download_time, datetime.now().isoformat(), request_id)
            )
            conn.commit()
    except Exception as e:
        logger = setup_logging()
        logger.error(f"Error updating download time: {e}")


def _update_download_time_by_index(db_path: str, request_index: str, download_time: str):
    """Update the download time for a specific request by request_index."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE rda_requests SET download_time = ?, updated_at = ? WHERE request_index = ?",
                (download_time, datetime.now().isoformat(), request_index)
            )
            conn.commit()
    except Exception as e:
        logger = setup_logging()
        logger.error(f"Error updating download time by index: {e}")


def _get_download_directory(db_path: str, request_index: str) -> Optional[str]:
    """Get the download directory for a specific request."""
    try:
        if not os.path.exists(db_path):
            return None
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT download_directory FROM rda_requests WHERE request_index = ?",
                (request_index,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception:
        return None


if __name__ == '__main__':
    """Command line interface for fix_completed_requests module."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix Completed Requests - Download completed RDA requests')
    parser.add_argument('--db-path', 
                       default='src/python/data/automation_state.db',
                       help='Path to the automation state database')
    parser.add_argument('--download-all', action='store_true',
                       help='Download all completed requests')
    parser.add_argument('--show-status', action='store_true',
                       help='Show status of completed requests')
    parser.add_argument('--verify-downloads', action='store_true',
                       help='Verify that downloads completed successfully')
    parser.add_argument('--download-specific', nargs='+', metavar='REQUEST_INDEX',
                       help='Download specific requests by their indices')
    
    args = parser.parse_args()
    
    if args.show_status:
        show_status(args.db_path)
    elif args.download_all:
        download_all_completed_requests(args.db_path)
    elif args.verify_downloads:
        verify_downloads(args.db_path)
    elif args.download_specific:
        download_specific_requests(args.download_specific, args.db_path)
    else:
        parser.print_help()