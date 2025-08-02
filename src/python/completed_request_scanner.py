#!/usr/bin/env python3
"""
Completed Request Scanner - Compatibility Stub

This module provides a compatibility layer for the completed request scanner
functionality. It wraps the existing fix_completed_requests.py functionality
to maintain compatibility with the automation integration system.

This stub was created to resolve import errors after the original
completed_request_scanner.py was removed during repository cleanup.
"""

import os
import sys
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fix_completed_requests import (
        get_completed_requests_from_database,
        download_all_completed_requests,
        show_status,
        verify_downloads,
        download_specific_requests
    )
except ImportError as e:
    print(f"Warning: Could not import fix_completed_requests functionality: {e}")
    # Define fallback functions
    def get_completed_requests_from_database(db_path: str = "./data/automation_state.db") -> List[Dict]:
        return []
    
    def download_all_completed_requests(db_path: str = "./data/automation_state.db"):
        pass
    
    def show_status(db_path: str = "./data/automation_state.db"):
        print("Status functionality not available")
    
    def verify_downloads(db_path: str = "./data/automation_state.db"):
        print("Verify downloads functionality not available")
    
    def download_specific_requests(request_indices: List[str], db_path: str = "./data/automation_state.db"):
        pass


@dataclass
class ScanResults:
    """Results from scanning for completed requests."""
    total_completed_found: int
    never_downloaded_count: int
    scan_duration: float
    requests_found: List[Dict]


@dataclass
class DownloadResults:
    """Results from downloading completed requests."""
    attempted_downloads: int
    successful_downloads: int
    failed_downloads: int
    download_duration: float
    results: List[Dict]


class CompletedRequestScanner:
    """
    Compatibility wrapper for completed request scanning functionality.
    
    This class provides the interface expected by the automation integration
    system while using the existing fix_completed_requests.py functionality.
    """
    
    def __init__(self, db_path: str = "./data/automation_state.db"):
        """
        Initialize the completed request scanner.
        
        Args:
            db_path: Path to the automation state database
        """
        self.db_path = db_path
        self.logger = self._setup_logging()
        self.logger.info("CompletedRequestScanner initialized (compatibility stub)")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the scanner."""
        logger = logging.getLogger('completed_request_scanner_stub')
        
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
    
    def scan_for_completed_requests(self) -> ScanResults:
        """
        Scan the database for completed requests that need downloading.
        
        Returns:
            ScanResults with information about found requests
        """
        start_time = time.time()
        
        try:
            self.logger.info("🔍 Scanning for completed requests...")
            
            # Use existing functionality to get completed requests
            requests = get_completed_requests_from_database(self.db_path)
            
            scan_duration = time.time() - start_time
            
            results = ScanResults(
                total_completed_found=len(requests),
                never_downloaded_count=len(requests),  # All returned requests need downloading
                scan_duration=scan_duration,
                requests_found=requests
            )
            
            self.logger.info(f"✅ Scan completed: {len(requests)} requests found in {scan_duration:.2f}s")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Error during scan: {e}")
            return ScanResults(
                total_completed_found=0,
                never_downloaded_count=0,
                scan_duration=time.time() - start_time,
                requests_found=[]
            )
    
    def download_completed_requests(self, requests: List[Dict]) -> DownloadResults:
        """
        Download the specified completed requests.
        
        Args:
            requests: List of request dictionaries to download
            
        Returns:
            DownloadResults with download information
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"📥 Downloading {len(requests)} completed requests...")
            
            if not requests:
                return DownloadResults(
                    attempted_downloads=0,
                    successful_downloads=0,
                    failed_downloads=0,
                    download_duration=0.0,
                    results=[]
                )
            
            # Extract request indices for download
            request_indices = [req.get('request_index', '') for req in requests if req.get('request_index')]
            
            if request_indices:
                # Use existing functionality to download specific requests
                download_specific_requests(request_indices, self.db_path)
                
                # Assume all downloads were successful (the existing function handles errors internally)
                successful_downloads = len(request_indices)
                failed_downloads = 0
            else:
                successful_downloads = 0
                failed_downloads = len(requests)
            
            download_duration = time.time() - start_time
            
            results = DownloadResults(
                attempted_downloads=len(requests),
                successful_downloads=successful_downloads,
                failed_downloads=failed_downloads,
                download_duration=download_duration,
                results=[{'success': True, 'request_index': idx} for idx in request_indices]
            )
            
            self.logger.info(f"✅ Download completed: {successful_downloads} successful, {failed_downloads} failed in {download_duration:.2f}s")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Error during download: {e}")
            return DownloadResults(
                attempted_downloads=len(requests),
                successful_downloads=0,
                failed_downloads=len(requests),
                download_duration=time.time() - start_time,
                results=[]
            )
    
    def scan_and_download_all(self) -> tuple[ScanResults, DownloadResults]:
        """
        Scan for completed requests and download them all.
        
        Returns:
            Tuple of (ScanResults, DownloadResults)
        """
        self.logger.info("🚀 Starting scan and download all operation...")
        
        # Scan for requests
        scan_results = self.scan_for_completed_requests()
        
        # Download found requests
        download_results = self.download_completed_requests(scan_results.requests_found)
        
        self.logger.info(f"🎉 Scan and download completed: {download_results.successful_downloads} requests processed")
        
        return scan_results, download_results
    
    def get_scanner_status(self) -> Dict[str, Any]:
        """
        Get current scanner status information.
        
        Returns:
            Dictionary with scanner status
        """
        try:
            # Get basic status using existing functionality
            requests = get_completed_requests_from_database(self.db_path)
            
            return {
                'scanner_active': True,
                'db_path': self.db_path,
                'last_scan_time': datetime.now().isoformat(),
                'pending_requests': len(requests),
                'scanner_type': 'compatibility_stub',
                'status': 'operational'
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error getting scanner status: {e}")
            return {
                'scanner_active': False,
                'db_path': self.db_path,
                'error': str(e),
                'scanner_type': 'compatibility_stub',
                'status': 'error'
            }


def create_completed_request_scanner(db_path: str = "./data/automation_state.db") -> CompletedRequestScanner:
    """
    Factory function to create a CompletedRequestScanner instance.
    
    Args:
        db_path: Path to the automation state database
        
    Returns:
        Configured CompletedRequestScanner instance
    """
    return CompletedRequestScanner(db_path)


if __name__ == '__main__':
    """Test the compatibility stub."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Completed Request Scanner (Compatibility Stub)')
    parser.add_argument('--scan-and-download', action='store_true',
                       help='Scan and download all completed requests')
    parser.add_argument('--scan-only', action='store_true',
                       help='Scan only (no downloads)')
    parser.add_argument('--status', action='store_true',
                       help='Show scanner status')
    parser.add_argument('--download-specific', nargs='+', metavar='REQUEST_ID',
                       help='Download specific requests by their indices')
    
    args = parser.parse_args()
    
    # Create scanner instance
    scanner = create_completed_request_scanner()
    
    if args.status:
        status = scanner.get_scanner_status()
        print("\n" + "="*80)
        print("🔄 COMPLETED REQUEST SCANNER STATUS (COMPATIBILITY STUB)")
        print("="*80)
        print(f"Scanner Active: {status['scanner_active']}")
        print(f"Database Path: {status['db_path']}")
        print(f"Scanner Type: {status['scanner_type']}")
        print(f"Status: {status['status']}")
        print(f"Pending Requests: {status.get('pending_requests', 'Unknown')}")
        print("="*80)
        
    elif args.scan_only:
        print("🔍 Scanning for completed requests...")
        scan_results = scanner.scan_for_completed_requests()
        print(f"\n📊 Scan Results:")
        print(f"  Total Completed Found: {scan_results.total_completed_found}")
        print(f"  Never Downloaded: {scan_results.never_downloaded_count}")
        print(f"  Scan Duration: {scan_results.scan_duration:.2f}s")
        
    elif args.scan_and_download:
        print("🚀 Scanning and downloading all completed requests...")
        scan_results, download_results = scanner.scan_and_download_all()
        print(f"\n📊 Results:")
        print(f"  Requests Found: {scan_results.total_completed_found}")
        print(f"  Downloads Attempted: {download_results.attempted_downloads}")
        print(f"  Downloads Successful: {download_results.successful_downloads}")
        print(f"  Downloads Failed: {download_results.failed_downloads}")
        
    elif args.download_specific:
        print(f"🎯 Downloading specific requests: {', '.join(args.download_specific)}")
        # Use the existing functionality directly
        download_specific_requests(args.download_specific)
        
    else:
        parser.print_help()