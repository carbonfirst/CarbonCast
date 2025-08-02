#!/usr/bin/env python3
"""
Automated Request Manager for RDA Automation System.

This module provides comprehensive automated request management including
continuous status monitoring, automatic processing of completed requests,
error handling, and intelligent capacity management.

The AutomatedRequestManager serves as the central component for managing
the complete lifecycle of RDA requests from submission through completion,
with robust error handling and recovery mechanisms.

Key Features:
    - Continuous status monitoring via rdams_client.py -get_status
    - Automated download and organization of completed requests
    - Error detection and automatic purging with resubmission logic
    - Integration with file organization system
    - Capacity management and intelligent scheduling
    - Comprehensive logging and metrics tracking
    - Thread-safe concurrent processing

Classes:
    RequestProcessingConfig: Configuration dataclass for request processing
    ProcessingResult: Result of a request processing operation
    AutomatedRequestManager: Main request management class

Functions:
    create_automated_request_manager: Factory function to create manager instance

Example:
    Basic usage of the automated request manager:
    
    >>> config = RequestProcessingConfig(status_check_interval=300)
    >>> manager = create_automated_request_manager(config)
    >>> manager.start_continuous_processing()
    >>> # System processes requests continuously
    >>> manager.stop_continuous_processing()
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rdams_client
from automation.file_organization_manager import EnhancedFileOrganizationManager, create_file_organization_manager
from automation.status_monitor import StatusMonitor, create_status_monitor
from automation.error_manager import ErrorManager, create_error_manager
from automation.retry_manager import RetryManager, create_retry_manager
from automation.data_sync import RDADataSyncService, create_data_sync_service


@dataclass
class RequestProcessingConfig:
    """
    Configuration for automated request processing.
    
    This dataclass contains all configuration parameters for the automated
    request manager, controlling timing, concurrency, and processing behavior.
    
    Attributes:
        status_check_interval (int): Interval between status checks in seconds (default: 300)
        max_concurrent_downloads (int): Maximum concurrent download operations (default: 3)
        auto_purge_completed (bool): Automatically purge completed requests (default: True)
        auto_purge_errors (bool): Automatically purge error requests (default: True)
        auto_resubmit_errors (bool): Automatically resubmit error requests (default: True)
        download_timeout_seconds (int): Timeout for download operations (default: 1800)
        max_retry_attempts (int): Maximum retry attempts for failed operations (default: 3)
        capacity_threshold (int): Request count threshold for capacity management (default: 9)
        enabled (bool): Master enable flag for the request manager (default: True)
    """
    status_check_interval: int = 300  # 5 minutes
    max_concurrent_downloads: int = 3
    auto_purge_completed: bool = True
    auto_purge_errors: bool = True
    auto_resubmit_errors: bool = True
    download_timeout_seconds: int = 1800  # 30 minutes
    max_retry_attempts: int = 3
    capacity_threshold: int = 9  # Start managing when >= 9 requests
    enabled: bool = True


@dataclass
class ProcessingResult:
    """
    Result of request processing operation.
    
    Contains detailed information about the processing of a single request,
    including success status, timing information, and operation details.
    
    Attributes:
        request_id (str): Unique identifier for the processed request
        action (str): Type of action performed (download, purge, resubmit, skip)
        success (bool): Whether the operation completed successfully
        message (str): Human-readable result message
        details (Dict[str, Any]): Detailed operation results and metadata
        timestamp (str): ISO timestamp when operation completed
        processing_time (float): Operation duration in seconds (default: 0.0)
    """
    request_id: str
    action: str  # download, purge, resubmit, skip
    success: bool
    message: str
    details: Dict[str, Any]
    timestamp: str
    processing_time: float = 0.0


class AutomatedRequestManager:
    """
    Comprehensive automated request manager for the RDA automation system.
    
    This class handles the complete lifecycle of RDA requests including continuous
    status monitoring, automated downloads, error handling, and intelligent
    capacity management. It serves as the central coordinator for request
    processing operations.
    
    The manager implements a robust processing pipeline that:
        - Continuously monitors request status via RDA API
        - Automatically downloads and organizes completed requests
        - Handles error requests with purging and resubmission logic
        - Manages system capacity to prevent overload
        - Provides comprehensive metrics and statistics
    
    Key Responsibilities:
        - Status monitoring and request categorization
        - Automated download and file organization
        - Error detection and recovery mechanisms
        - Capacity management and throttling
        - Integration with file organization and retry systems
        - Performance monitoring and statistics collection
    
    Attributes:
        config (RequestProcessingConfig): Configuration settings
        db_path (str): Path to SQLite database file
        base_download_dir (str): Base directory for organized downloads
        logger (logging.Logger): Logger instance for manager operations
        file_org_manager: File organization manager instance
        status_monitor: Status monitor instance
        error_manager: Error manager instance
        retry_manager: Retry manager instance
        data_sync: Data synchronization service instance
        processing_active (bool): Whether continuous processing is active
        processing_thread (Optional[threading.Thread]): Processing thread
        processing_stats (dict): Processing statistics and metrics
        processing_lock (threading.Lock): Thread lock for processing operations
        executor (ThreadPoolExecutor): Thread pool for concurrent operations
    
    Example:
        Basic usage of the automated request manager:
        
        >>> config = RequestProcessingConfig(status_check_interval=300)
        >>> manager = AutomatedRequestManager(config)
        >>> manager.start_continuous_processing()
        >>> # System processes requests continuously
        >>> manager.stop_continuous_processing()
    """
    
    def __init__(self, config: Optional[RequestProcessingConfig] = None,
                 db_path: str = "src/python/data/automation_state.db",
                 base_download_dir: str = "downloaded_files"):
        """
        Initialize the Automated Request Manager.
        
        Sets up all component managers, initializes processing state,
        configures threading resources, and prepares the manager for operation.
        
        Args:
            config (Optional[RequestProcessingConfig]): Configuration for request
                processing. If None, uses default configuration settings.
            db_path (str): Path to the SQLite database file for state persistence.
            base_download_dir (str): Base directory for organized file downloads.
        
        Raises:
            Exception: If component initialization fails or required resources
                are unavailable.
        """
        self.config = config or RequestProcessingConfig()
        self.db_path = db_path
        self.base_download_dir = base_download_dir
        self.logger = self._setup_logging()
        
        # Initialize component managers
        self.file_org_manager = create_file_organization_manager(base_download_dir, db_path)
        self.status_monitor = create_status_monitor(db_path)
        self.error_manager = create_error_manager(db_path)
        self.retry_manager = create_retry_manager(db_path)
        self.data_sync = create_data_sync_service(db_path)
        
        # Processing state
        self.processing_active = False
        self.processing_thread = None
        self.processing_stats = {
            'total_processed': 0,
            'downloads_completed': 0,
            'errors_purged': 0,
            'requests_resubmitted': 0,
            'last_processing_time': None
        }
        
        # Threading
        self.processing_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_downloads)
        
        self.logger.info("Automated Request Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """
        Set up logging for the automated request manager.
        
        Configures a logger with appropriate formatting for request
        management operations.
        
        Returns:
            logging.Logger: Configured logger instance for the manager.
        """
        logger = logging.getLogger('rda_automation.automated_request_manager')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def get_all_request_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all requests in the RDA system.
        
        Fetches current status from the RDA system via rdams_client and
        categorizes requests by their current state for processing.
        
        Returns:
            Dict[str, Any]: Dictionary with categorized request information
                containing the following keys:
                - completed: List of completed requests ready for download
                - processing: List of requests currently being processed
                - queued: List of queued requests waiting for processing
                - error: List of requests with errors requiring attention
                - unknown: List of requests with unrecognized status
                - total_count: Total number of requests
                - timestamp: When the status was retrieved
        
        Note:
            This method makes an API call to the RDA system and may take
            several seconds to complete depending on system load.
        """
        try:
            self.logger.info("Fetching comprehensive request status from RDA system")
            
            # Get all requests from RDA
            rda_status = rdams_client.get_status()
            
            if not rda_status or 'data' not in rda_status:
                self.logger.error("Failed to get RDA status or no data returned")
                return {}
            
            # Categorize requests
            categorized_requests = {
                'completed': [],
                'processing': [],
                'queued': [],
                'error': [],
                'unknown': [],
                'total_count': len(rda_status['data']),
                'timestamp': datetime.now().isoformat()
            }
            
            for request_data in rda_status['data']:
                request_id = str(request_data.get('request_index', ''))
                status = request_data.get('status', '').lower().strip()
                
                request_info = {
                    'request_id': request_id,
                    'request_index': request_data.get('request_index'),
                    'status': status,
                    'date_rqst': request_data.get('date_rqst'),
                    'date_ready': request_data.get('date_ready'),
                    'dsid': request_data.get('dsid'),
                    'raw_data': request_data
                }
                
                # Categorize based on status
                if 'completed' in status:
                    categorized_requests['completed'].append(request_info)
                elif 'error' in status or 'failed' in status or 'cancelled' in status:
                    categorized_requests['error'].append(request_info)
                elif 'processing' in status or 'running' in status:
                    categorized_requests['processing'].append(request_info)
                elif 'queued' in status:
                    categorized_requests['queued'].append(request_info)
                else:
                    categorized_requests['unknown'].append(request_info)
            
            self.logger.info(f"Status summary: {len(categorized_requests['completed'])} completed, "
                           f"{len(categorized_requests['error'])} errors, "
                           f"{len(categorized_requests['processing'])} processing, "
                           f"{len(categorized_requests['queued'])} queued")
            
            return categorized_requests
            
        except Exception as e:
            self.logger.error(f"Error getting request status: {e}")
            return {}
    
    def process_completed_requests(self, completed_requests: List[Dict[str, Any]]) -> List[ProcessingResult]:
        """
        Process completed requests by downloading and organizing files.
        
        Downloads files for all completed requests concurrently, organizes
        them using the file organization manager, and optionally purges
        the requests from the RDA system.
        
        Args:
            completed_requests (List[Dict[str, Any]]): List of completed request
                information dictionaries containing request metadata.
            
        Returns:
            List[ProcessingResult]: List of ProcessingResult objects containing
                detailed information about each processing operation, including
                success status, file counts, and error messages.
        
        Note:
            This method processes requests concurrently up to the configured
            max_concurrent_downloads limit and includes timeout handling.
        """
        results = []
        
        if not completed_requests:
            return results
        
        self.logger.info(f"Processing {len(completed_requests)} completed requests")
        
        # Process requests concurrently
        futures = []
        for request_info in completed_requests:
            future = self.executor.submit(self._process_single_completed_request, request_info)
            futures.append((future, request_info))
        
        # Collect results
        for future, request_info in futures:
            try:
                result = future.result(timeout=self.config.download_timeout_seconds)
                results.append(result)
                
                if result.success:
                    self.processing_stats['downloads_completed'] += 1
                    self.logger.info(f"✅ Successfully processed completed request {result.request_id}")
                else:
                    self.logger.error(f"❌ Failed to process completed request {result.request_id}: {result.message}")
                    
            except Exception as e:
                error_result = ProcessingResult(
                    request_id=request_info['request_id'],
                    action="download",
                    success=False,
                    message=f"Exception during processing: {e}",
                    details={'error': str(e)},
                    timestamp=datetime.now().isoformat()
                )
                results.append(error_result)
                self.logger.error(f"❌ Exception processing request {request_info['request_id']}: {e}")
        
        return results
    
    def _process_single_completed_request(self, request_info: Dict[str, Any]) -> ProcessingResult:
        """Process a single completed request."""
        start_time = time.time()
        request_id = request_info['request_id']
        
        try:
            self.logger.info(f"🔄 Processing completed request {request_id}")
            
            # Create absolute path for temp downloads
            import tempfile
            temp_dir = os.path.abspath("./temp_downloads")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Download and organize files
            organization_results = self.file_org_manager.organize_request_download(
                request_id, download_directory=temp_dir
            )
            
            # Check if download was successful
            successful_downloads = [r for r in organization_results if r.success]
            total_files_attempted = len(organization_results)
            
            self.logger.info(f"📊 Organization results for {request_id}: {len(successful_downloads)}/{total_files_attempted} files successfully organized")
            
            # Log detailed results for debugging
            for i, result in enumerate(organization_results):
                if result.success:
                    self.logger.info(f"  ✅ File {i+1}: {result.original_path} -> {result.organized_path}")
                else:
                    self.logger.error(f"  ❌ File {i+1}: {result.original_path} - {result.error_message}")
            
            if successful_downloads:
                # Auto-purge completed request if configured
                purge_success = False
                if self.config.auto_purge_completed:
                    try:
                        purge_result = rdams_client.purge_request(request_id)
                        purge_success = bool(purge_result)
                        
                        if purge_success:
                            self.logger.info(f"🔥 Auto-purged completed request {request_id}")
                        else:
                            self.logger.warning(f"⚠️ Failed to auto-purge completed request {request_id}")
                    except Exception as e:
                        self.logger.error(f"❌ Error auto-purging request {request_id}: {e}")
                
                processing_time = time.time() - start_time
                
                return ProcessingResult(
                    request_id=request_id,
                    action="download_and_purge" if purge_success else "download",
                    success=True,
                    message=f"Successfully organized {len(successful_downloads)}/{total_files_attempted} files" +
                           (" and purged request" if purge_success else ""),
                    details={
                        'total_files_attempted': total_files_attempted,
                        'successfully_organized': len(successful_downloads),
                        'organization_results': [asdict(r) for r in organization_results],
                        'purged': purge_success
                    },
                    timestamp=datetime.now().isoformat(),
                    processing_time=processing_time
                )
            else:
                # Enhanced error reporting when no files were organized
                error_details = {
                    'total_files_attempted': total_files_attempted,
                    'successfully_organized': 0,
                    'organization_results': [asdict(r) for r in organization_results],
                    'common_errors': []
                }
                
                # Collect common error patterns
                error_messages = [r.error_message for r in organization_results if r.error_message]
                if error_messages:
                    error_details['common_errors'] = error_messages[:3]  # First 3 errors
                
                return ProcessingResult(
                    request_id=request_id,
                    action="download",
                    success=False,
                    message=f"Failed to organize any files ({total_files_attempted} attempted). Check file paths and download directory.",
                    details=error_details,
                    timestamp=datetime.now().isoformat(),
                    processing_time=time.time() - start_time
                )
                
        except Exception as e:
            return ProcessingResult(
                request_id=request_id,
                action="download",
                success=False,
                message=f"Error processing completed request: {e}",
                details={'error': str(e)},
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - start_time
            )
    
    def process_error_requests(self, error_requests: List[Dict[str, Any]]) -> List[ProcessingResult]:
        """
        Process error requests by purging and optionally resubmitting.
        
        Args:
            error_requests: List of error request information
            
        Returns:
            List of ProcessingResult objects
        """
        results = []
        
        if not error_requests:
            return results
        
        self.logger.warning(f"🚨 Processing {len(error_requests)} error requests")
        
        for request_info in error_requests:
            request_id = request_info['request_id']
            start_time = time.time()
            
            try:
                # Auto-purge error request
                purge_success = False
                if self.config.auto_purge_errors:
                    try:
                        purge_result = rdams_client.purge_request(request_id)
                        purge_success = bool(purge_result)
                        
                        if purge_success:
                            self.logger.info(f"🔥 Auto-purged error request {request_id}")
                            self.processing_stats['errors_purged'] += 1
                        else:
                            self.logger.warning(f"⚠️ Failed to auto-purge error request {request_id}")
                    except Exception as e:
                        self.logger.error(f"❌ Error auto-purging request {request_id}: {e}")
                
                # Attempt resubmission if configured and purge was successful
                resubmit_success = False
                if self.config.auto_resubmit_errors and purge_success:
                    try:
                        # Get original request information for resubmission
                        resubmission_data = self._prepare_resubmission_data(request_info)
                        
                        if resubmission_data:
                            # Use retry manager to handle resubmission
                            retry_result = self.retry_manager.process_retry_requests([resubmission_data])
                            resubmit_success = retry_result.get('scheduled', 0) > 0
                            
                            if resubmit_success:
                                self.logger.info(f"🔄 Scheduled resubmission for error request {request_id}")
                                self.processing_stats['requests_resubmitted'] += 1
                    except Exception as e:
                        self.logger.error(f"❌ Error resubmitting request {request_id}: {e}")
                
                action = "purge_and_resubmit" if (purge_success and resubmit_success) else \
                        "purge" if purge_success else "error_handling"
                
                result = ProcessingResult(
                    request_id=request_id,
                    action=action,
                    success=purge_success,
                    message=f"Purged: {purge_success}, Resubmitted: {resubmit_success}",
                    details={
                        'purged': purge_success,
                        'resubmitted': resubmit_success,
                        'original_status': request_info['status']
                    },
                    timestamp=datetime.now().isoformat(),
                    processing_time=time.time() - start_time
                )
                
                results.append(result)
                
            except Exception as e:
                error_result = ProcessingResult(
                    request_id=request_id,
                    action="error_handling",
                    success=False,
                    message=f"Exception during error processing: {e}",
                    details={'error': str(e)},
                    timestamp=datetime.now().isoformat(),
                    processing_time=time.time() - start_time
                )
                results.append(error_result)
                self.logger.error(f"❌ Exception processing error request {request_id}: {e}")
        
        return results
    
    def _prepare_resubmission_data(self, request_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Prepare resubmission data for an error request."""
        try:
            # Try to get original control file information
            request_id = request_info['request_id']
            
            # Get region/variable information
            detection_info = self.file_org_manager.detect_region_variable_multi_source(request_id)
            
            return {
                'original_id': request_id,
                'session_id': f"auto_resubmit_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'file_path': f"auto_resubmit_{request_id}.ctl",
                'region': detection_info.region,
                'parameter': detection_info.variable,
                'original_error': f"RDA status: {request_info['status']}",
                'retry_count': 0,
                'purged_at': datetime.now().isoformat(),
                'resubmission_ready': True
            }
            
        except Exception as e:
            self.logger.error(f"Error preparing resubmission data for {request_info['request_id']}: {e}")
            return None
    
    def check_capacity_and_manage(self, total_requests: int) -> Dict[str, Any]:
        """
        Check request capacity and manage if approaching limits.
        
        Args:
            total_requests: Total number of active requests
            
        Returns:
            Dictionary with capacity management results
        """
        capacity_info = {
            'total_requests': total_requests,
            'capacity_threshold': self.config.capacity_threshold,
            'at_capacity': total_requests >= 10,
            'approaching_capacity': total_requests >= self.config.capacity_threshold,
            'action_taken': None,
            'timestamp': datetime.now().isoformat()
        }
        
        if capacity_info['at_capacity']:
            self.logger.warning(f"🚨 AT CAPACITY: {total_requests}/10 requests active")
            capacity_info['action_taken'] = "capacity_crisis_mode"
            
            # In capacity crisis, prioritize completing existing requests
            # Don't submit new requests until capacity is available
            
        elif capacity_info['approaching_capacity']:
            self.logger.info(f"⚠️ APPROACHING CAPACITY: {total_requests}/10 requests active")
            capacity_info['action_taken'] = "capacity_management_mode"
            
            # In capacity management mode, be more aggressive about processing
            # completed and error requests to free up slots
        
        return capacity_info
    
    def run_processing_cycle(self) -> Dict[str, Any]:
        """
        Run a single automated processing cycle.
        
        Returns:
            Dictionary with cycle results and statistics
        """
        cycle_start = time.time()
        self.logger.info("🔄 Starting automated request processing cycle")
        
        try:
            # Get comprehensive request status
            status_info = self.get_all_request_status()
            
            if not status_info:
                return {
                    'success': False,
                    'error': 'Failed to get request status',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Check capacity
            capacity_info = self.check_capacity_and_manage(status_info['total_count'])
            
            # Process completed requests
            completed_results = self.process_completed_requests(status_info.get('completed', []))
            
            # Process error requests
            error_results = self.process_error_requests(status_info.get('error', []))
            
            # Update processing stats
            with self.processing_lock:
                self.processing_stats['total_processed'] += len(completed_results) + len(error_results)
                self.processing_stats['last_processing_time'] = datetime.now().isoformat()
            
            # Compile cycle results
            cycle_time = time.time() - cycle_start
            
            cycle_results = {
                'success': True,
                'cycle_duration': cycle_time,
                'status_summary': {
                    'total_requests': status_info['total_count'],
                    'completed': len(status_info.get('completed', [])),
                    'errors': len(status_info.get('error', [])),
                    'processing': len(status_info.get('processing', [])),
                    'queued': len(status_info.get('queued', []))
                },
                'processing_results': {
                    'completed_processed': len(completed_results),
                    'errors_processed': len(error_results),
                    'successful_downloads': len([r for r in completed_results if r.success]),
                    'successful_error_handling': len([r for r in error_results if r.success])
                },
                'capacity_info': capacity_info,
                'processing_stats': self.processing_stats.copy(),
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"✅ Processing cycle completed in {cycle_time:.2f}s: "
                           f"{len(completed_results)} completed, {len(error_results)} errors processed")
            
            return cycle_results
            
        except Exception as e:
            error_msg = f"Error in processing cycle: {e}"
            self.logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'cycle_duration': time.time() - cycle_start,
                'timestamp': datetime.now().isoformat()
            }
    
    def start_continuous_processing(self):
        """Start continuous automated processing in background thread."""
        if self.processing_active:
            self.logger.warning("Continuous processing is already active")
            return
        
        def processing_loop():
            self.logger.info(f"Starting continuous processing loop (interval: {self.config.status_check_interval}s)")
            
            while self.processing_active:
                try:
                    # Run processing cycle
                    cycle_result = self.run_processing_cycle()
                    
                    if cycle_result['success']:
                        self.logger.info(f"✅ Cycle completed: {cycle_result['processing_results']}")
                    else:
                        self.logger.error(f"❌ Cycle failed: {cycle_result.get('error', 'Unknown error')}")
                    
                    # Wait for next cycle
                    time.sleep(self.config.status_check_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in processing loop: {e}")
                    time.sleep(min(self.config.status_check_interval, 60))  # Wait at least 60 seconds on error
            
            self.logger.info("Continuous processing loop stopped")
        
        self.processing_active = True
        self.processing_thread = threading.Thread(target=processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.logger.info("Continuous automated processing started")
    
    def stop_continuous_processing(self):
        """Stop continuous automated processing."""
        if not self.processing_active:
            return
        
        self.logger.info("Stopping continuous processing...")
        self.processing_active = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=10)
        
        self.logger.info("Continuous processing stopped")
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            # Get file organization statistics
            org_stats = self.file_org_manager.get_organization_statistics()
            
            # Get status monitoring statistics
            monitor_stats = self.status_monitor.get_monitoring_statistics()
            
            # Get error management statistics
            error_stats = self.error_manager.get_error_statistics()
            
            # Get retry statistics
            retry_stats = self.retry_manager.get_retry_statistics()
            
            return {
                'processing_active': self.processing_active,
                'config': asdict(self.config),
                'processing_stats': self.processing_stats.copy(),
                'file_organization': org_stats,
                'status_monitoring': monitor_stats,
                'error_management': error_stats,
                'retry_management': retry_stats,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting processing statistics: {e}")
            return {'error': str(e), 'generated_at': datetime.now().isoformat()}


def create_automated_request_manager(config: Optional[RequestProcessingConfig] = None,
                                   db_path: str = "src/python/data/automation_state.db",
                                   base_download_dir: str = "downloaded_files") -> AutomatedRequestManager:
    """
    Factory function to create an Automated Request Manager.
    
    Args:
        config: Configuration for request processing
        db_path: Path to the SQLite database file
        base_download_dir: Base directory for organized downloads
        
    Returns:
        Configured AutomatedRequestManager instance
    """
    return AutomatedRequestManager(config, db_path, base_download_dir)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated Request Manager')
    parser.add_argument('--start-continuous', action='store_true',
                       help='Start continuous automated processing')
    parser.add_argument('--single-cycle', action='store_true',
                       help='Run a single processing cycle')
    parser.add_argument('--stats', action='store_true',
                       help='Show processing statistics')
    parser.add_argument('--status-check', action='store_true',
                       help='Check current request status')
    parser.add_argument('--interval', type=int, default=300,
                       help='Processing interval in seconds')
    
    args = parser.parse_args()
    
    # Create configuration
    config = RequestProcessingConfig(status_check_interval=args.interval)
    
    # Create automated request manager
    manager = create_automated_request_manager(config)
    
    try:
        if args.start_continuous:
            print("=== Starting Continuous Automated Processing ===")
            manager.start_continuous_processing()
            
            # Keep running until interrupted
            try:
                while manager.processing_active:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping automated processing...")
                manager.stop_continuous_processing()
        
        elif args.single_cycle:
            print("=== Running Single Processing Cycle ===")
            result = manager.run_processing_cycle()
            print(json.dumps(result, indent=2))
        
        elif args.status_check:
            print("=== Current Request Status ===")
            status = manager.get_all_request_status()
            print(json.dumps(status, indent=2))
        
        elif args.stats:
            print("=== Processing Statistics ===")
            stats = manager.get_processing_statistics()
            print(json.dumps(stats, indent=2))
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("AUTOMATED REQUEST MANAGER EXAMPLES")
            print("="*60)
            print("# Start continuous processing:")
            print("python automation/automated_request_manager.py --start-continuous")
            print("\n# Run single processing cycle:")
            print("python automation/automated_request_manager.py --single-cycle")
            print("\n# Check current request status:")
            print("python automation/automated_request_manager.py --status-check")
            print("\n# Show processing statistics:")
            print("python automation/automated_request_manager.py --stats")
            print("="*60)
            
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(manager, 'processing_active') and manager.processing_active:
            manager.stop_continuous_processing()