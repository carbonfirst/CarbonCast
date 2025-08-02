#!/usr/bin/env python3
"""
Completed Request Integration Module for RDA Automation System

This module integrates the Completed Request Scanner into the existing
batch automation system to automatically handle completed requests that
were submitted outside the current batch workflow.

This solves the critical integration gap where:
- Batch System Flow: Control files → Requests → Monitoring → Download
- External Requests Flow: Direct submissions → Database → NO MONITORING → NO DOWNLOAD

The integration ensures that ALL completed requests are automatically downloaded,
regardless of how they were submitted to the system.
"""

import os
import sys
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from completed_request_scanner import CompletedRequestScanner, create_completed_request_scanner


class CompletedRequestIntegration:
    """
    Integration component that adds completed request scanning to the automation system.
    
    This component can be integrated into the existing batch automation system
    to automatically detect and download completed requests that were missed
    by the normal batch workflow.
    """
    
    def __init__(self, db_path: str = "./data/automation_state.db", 
                 scan_interval_minutes: int = 30):
        """
        Initialize the integration component.
        
        Args:
            db_path: Path to the automation state database
            scan_interval_minutes: How often to scan for completed requests
        """
        self.db_path = db_path
        self.scan_interval_minutes = scan_interval_minutes
        self.scanner = create_completed_request_scanner(db_path)
        self.logger = self._setup_logging()
        
        # Integration state
        self.last_scan_time = None
        self.total_requests_processed = 0
        self.integration_active = False
        
        self.logger.info("Completed Request Integration initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the integration component."""
        logger = logging.getLogger('completed_request_integration')
        
        if not logger.handlers:
            # Create logs directory
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            
            # File handler
            log_file = logs_dir / f"completed_request_integration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_file)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)
            logger.addHandler(file_handler)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(logging.INFO)
            logger.addHandler(console_handler)
            
            logger.setLevel(logging.DEBUG)
        
        return logger
    
    def should_run_scan(self) -> bool:
        """
        Determine if it's time to run a completed request scan.
        
        Returns:
            True if a scan should be performed
        """
        if not self.last_scan_time:
            return True
        
        time_since_last_scan = datetime.now() - self.last_scan_time
        return time_since_last_scan.total_seconds() >= (self.scan_interval_minutes * 60)
    
    def run_integration_cycle(self) -> Dict:
        """
        Run a single integration cycle to check for and download completed requests.
        
        This method is designed to be called periodically by the main automation system.
        
        Returns:
            Dictionary with cycle results
        """
        cycle_start = time.time()
        
        try:
            self.logger.info("🔄 Running completed request integration cycle...")
            
            # Check if it's time to scan
            if not self.should_run_scan():
                time_until_next = (self.scan_interval_minutes * 60) - (datetime.now() - self.last_scan_time).total_seconds()
                self.logger.debug(f"⏰ Next scan in {time_until_next/60:.1f} minutes")
                return {
                    'cycle_completed': True,
                    'scan_performed': False,
                    'reason': 'Not time for scan yet',
                    'next_scan_in_minutes': time_until_next / 60
                }
            
            # Perform scan and download
            self.logger.info("🔍 Scanning for completed requests that need downloading...")
            scan_results, download_results = self.scanner.scan_and_download_all()
            
            # Update integration state
            self.last_scan_time = datetime.now()
            self.total_requests_processed += download_results.successful_downloads
            
            cycle_duration = time.time() - cycle_start
            
            # Log results
            if download_results.successful_downloads > 0:
                self.logger.info(f"✅ Integration cycle completed: {download_results.successful_downloads} requests downloaded")
            else:
                self.logger.info("✅ Integration cycle completed: No requests needed downloading")
            
            return {
                'cycle_completed': True,
                'scan_performed': True,
                'scan_results': {
                    'total_completed_found': scan_results.total_completed_found,
                    'never_downloaded_count': scan_results.never_downloaded_count,
                    'scan_duration': scan_results.scan_duration
                },
                'download_results': {
                    'attempted_downloads': download_results.attempted_downloads,
                    'successful_downloads': download_results.successful_downloads,
                    'failed_downloads': download_results.failed_downloads,
                    'download_duration': download_results.download_duration
                },
                'cycle_duration': cycle_duration,
                'next_scan_time': self.last_scan_time.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error in integration cycle: {e}")
            return {
                'cycle_completed': False,
                'error': str(e),
                'cycle_duration': time.time() - cycle_start
            }
    
    def get_integration_status(self) -> Dict:
        """
        Get current status of the integration component.
        
        Returns:
            Dictionary with integration status
        """
        return {
            'integration_active': self.integration_active,
            'db_path': str(self.db_path),
            'scan_interval_minutes': self.scan_interval_minutes,
            'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'total_requests_processed': self.total_requests_processed,
            'next_scan_due': self.should_run_scan(),
            'scanner_status': self.scanner.get_scanner_status()
        }
    
    def force_scan_and_download(self) -> Dict:
        """
        Force an immediate scan and download cycle, ignoring the normal schedule.
        
        Returns:
            Dictionary with results
        """
        self.logger.info("🚀 Forcing immediate scan and download cycle...")
        
        # Temporarily reset last scan time to force scan
        original_last_scan = self.last_scan_time
        self.last_scan_time = None
        
        try:
            result = self.run_integration_cycle()
            return result
        finally:
            # If the forced scan failed, restore the original last scan time
            if not result.get('cycle_completed', False):
                self.last_scan_time = original_last_scan
    
    def start_integration(self):
        """Mark integration as active."""
        self.integration_active = True
        self.logger.info("🟢 Completed request integration started")
    
    def stop_integration(self):
        """Mark integration as inactive."""
        self.integration_active = False
        self.logger.info("🔴 Completed request integration stopped")


def create_completed_request_integration(db_path: str = "./data/automation_state.db",
                                       scan_interval_minutes: int = 30) -> CompletedRequestIntegration:
    """
    Factory function to create a CompletedRequestIntegration instance.
    
    Args:
        db_path: Path to the automation state database
        scan_interval_minutes: How often to scan for completed requests
        
    Returns:
        Configured CompletedRequestIntegration instance
    """
    return CompletedRequestIntegration(db_path, scan_interval_minutes)


# Integration helper functions for existing automation systems

def add_to_batch_automation_system(batch_system, scan_interval_minutes: int = 30):
    """
    Add completed request integration to an existing BatchAutomationSystem.
    
    This function modifies the existing batch automation system to include
    completed request scanning in its main processing loop.
    
    Args:
        batch_system: Instance of BatchAutomationSystem
        scan_interval_minutes: How often to scan for completed requests
    """
    # Get database path from batch system
    db_path = getattr(batch_system, 'db_path', './data/automation_state.db')
    
    # Create integration component
    integration = create_completed_request_integration(db_path, scan_interval_minutes)
    
    # Add integration to batch system
    batch_system.completed_request_integration = integration
    
    # Monkey patch the monitor_active_requests method to include integration
    original_monitor = batch_system.monitor_active_requests
    
    def enhanced_monitor_active_requests():
        """Enhanced monitoring that includes completed request integration."""
        # Run original monitoring
        original_monitor()
        
        # Run integration cycle
        if hasattr(batch_system, 'completed_request_integration'):
            integration_result = batch_system.completed_request_integration.run_integration_cycle()
            
            # Log integration results if any downloads occurred
            if integration_result.get('scan_performed') and integration_result.get('download_results', {}).get('successful_downloads', 0) > 0:
                downloads = integration_result['download_results']['successful_downloads']
                batch_system.logger.info(f"🔄 Completed Request Integration: Downloaded {downloads} additional requests")
    
    # Replace the method
    batch_system.monitor_active_requests = enhanced_monitor_active_requests
    
    # Start integration
    integration.start_integration()
    
    batch_system.logger.info("✅ Completed Request Integration added to batch automation system")
    
    return integration


def add_to_integrated_batch_system(integrated_system, scan_interval_minutes: int = 30):
    """
    Add completed request integration to an existing IntegratedBatchSystem.
    
    Args:
        integrated_system: Instance of IntegratedBatchSystem
        scan_interval_minutes: How often to scan for completed requests
    """
    # Get database path
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "automation_state.db")
    
    # Create integration component
    integration = create_completed_request_integration(db_path, scan_interval_minutes)
    
    # Add integration to integrated system
    integrated_system.completed_request_integration = integration
    
    # Enhance the main processing loop
    original_process_all = integrated_system.process_all_control_files
    
    def enhanced_process_all_control_files():
        """Enhanced processing that includes completed request integration."""
        # Start integration
        if hasattr(integrated_system, 'completed_request_integration'):
            integrated_system.completed_request_integration.start_integration()
        
        # Run original processing with integration
        try:
            original_process_all()
        finally:
            # Stop integration
            if hasattr(integrated_system, 'completed_request_integration'):
                integrated_system.completed_request_integration.stop_integration()
    
    # Replace the method
    integrated_system.process_all_control_files = enhanced_process_all_control_files
    
    integrated_system.logger.info("✅ Completed Request Integration added to integrated batch system")
    
    return integration


if __name__ == '__main__':
    """Test the integration component."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Completed Request Integration')
    parser.add_argument('--test-cycle', action='store_true',
                       help='Test a single integration cycle')
    parser.add_argument('--status', action='store_true',
                       help='Show integration status')
    parser.add_argument('--force-scan', action='store_true',
                       help='Force immediate scan and download')
    
    args = parser.parse_args()
    
    # Create integration instance
    integration = create_completed_request_integration()
    
    if args.status:
        status = integration.get_integration_status()
        print("\n" + "="*80)
        print("🔄 COMPLETED REQUEST INTEGRATION STATUS")
        print("="*80)
        print(f"Integration Active: {status['integration_active']}")
        print(f"Database Path: {status['db_path']}")
        print(f"Scan Interval: {status['scan_interval_minutes']} minutes")
        print(f"Last Scan: {status['last_scan_time'] or 'Never'}")
        print(f"Total Processed: {status['total_requests_processed']} requests")
        print(f"Next Scan Due: {'Yes' if status['next_scan_due'] else 'No'}")
        print("="*80)
        
    elif args.test_cycle:
        print("🔄 Testing integration cycle...")
        result = integration.run_integration_cycle()
        print(f"\n📊 Cycle Result: {result}")
        
    elif args.force_scan:
        print("🚀 Forcing scan and download...")
        result = integration.force_scan_and_download()
        print(f"\n📊 Force Scan Result: {result}")
        
    else:
        parser.print_help()