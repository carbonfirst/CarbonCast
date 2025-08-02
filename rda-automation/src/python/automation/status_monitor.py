#!/usr/bin/env python3
"""
RDA Automation System - Status Monitor Module

This module provides automatic status monitoring, error detection, and retry coordination
for the RDA automation system. It integrates with the existing error_manager and retry_manager
modules to provide a comprehensive error handling and recovery system.

Key Features:
- Automatic status checking using rdams_client.py -get_status
- Detection of "Queued for Processing", "completed", and "error" status types
- Automatic purging of error requests
- Integration with retry management system
- Prevention of infinite retry loops
- Comprehensive logging and metrics tracking
- Proper handling of purged requests (which no longer exist in RDA system)
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rdams_client
from automation.error_manager import ErrorManager, create_error_manager
from automation.retry_manager import RetryManager, create_retry_manager, create_unified_error_retry_workflow


@dataclass
class StatusCheckResult:
    """Result of a status check operation."""
    request_id: str
    status: str
    raw_response: Dict[str, Any]
    timestamp: str
    error_message: Optional[str] = None
    needs_purging: bool = False
    needs_retry: bool = False
    request_exists: bool = True  # Track if request still exists in RDA system


@dataclass
class MonitorConfig:
    """Configuration for status monitoring."""
    check_interval_seconds: int = 300
    max_consecutive_errors: int = 3
    error_status_patterns: List[str] = None
    completed_status_patterns: List[str] = None
    processing_status_patterns: List[str] = None
    auto_purge_errors: bool = True
    auto_retry_purged: bool = True
    max_retry_attempts: int = 5
    retry_delay_multiplier: float = 1.5
    status_timeout_seconds: int = 30
    
    def __post_init__(self):
        if self.error_status_patterns is None:
            self.error_status_patterns = ["error", "Error", "failed", "Failed", "cancelled", "Cancelled"]
        if self.completed_status_patterns is None:
            self.completed_status_patterns = ["completed", "Completed", "finished", "Finished", "done", "Done"]
        if self.processing_status_patterns is None:
            self.processing_status_patterns = [
                "queued for processing", "Queued for Processing", "processing", "Processing",
                "running", "Running", "queued", "Queued", "in progress", "In Progress", "active", "Active"
            ]


class StatusMonitor:
    """
    Monitors RDA request status and coordinates error detection and retry workflows.
    
    This class provides the main integration point between status checking,
    error detection, and retry management.
    """
    
    def __init__(self, db_path: str, batch_system=None, queue_manager=None, 
                 config: Optional[MonitorConfig] = None):
        """
        Initialize the StatusMonitor.
        
        Args:
            db_path: Path to the SQLite database file
            batch_system: Optional BatchAutomationSystem instance
            queue_manager: Optional IntelligentQueueManager instance
            config: Configuration for monitoring behavior
        """
        self.db_path = db_path
        self.config = config or MonitorConfig()
        self.logger = self._setup_logging()
        
        # Initialize error and retry managers
        self.error_manager = create_error_manager(db_path)
        self.retry_manager = create_retry_manager(db_path, batch_system, queue_manager)
        
        # Store references to batch system and queue manager
        self.batch_system = batch_system
        self.queue_manager = queue_manager
        
        # Monitoring state
        self.monitoring_active = False
        self.monitor_thread = None
        self.status_cache = {}
        self.consecutive_errors = {}
        self.purged_requests = set()  # Track requests we've purged
        
        # Threading
        self.monitor_lock = threading.Lock()
        
        self.logger.info("StatusMonitor initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the status monitor."""
        logger = logging.getLogger('rda_automation.status_monitor')
        
        # Only add handler if it doesn't already exist
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def check_request_status_via_client(self, request_id: str) -> StatusCheckResult:
        """
        Check request status using rdams_client.py -get_status command.
        
        Args:
            request_id: RDA request ID to check
            
        Returns:
            StatusCheckResult with status information
        """
        try:
            self.logger.debug(f"Checking status for request {request_id}")
            
            # Use rdams_client directly (more reliable than subprocess)
            status_result = rdams_client.get_status(request_id)
            
            # Handle case where request doesn't exist (likely purged)
            if not status_result:
                return StatusCheckResult(
                    request_id=request_id,
                    status="purged",
                    raw_response={},
                    timestamp=datetime.now().isoformat(),
                    request_exists=False,
                    error_message="Request no longer exists in RDA system (likely purged)"
                )
            
            # Handle error responses or empty data
            if 'data' not in status_result or not status_result['data']:
                # Check if this indicates the request was purged/doesn't exist
                if 'error' in status_result or 'message' in status_result:
                    error_msg = status_result.get('message', status_result.get('error', 'Unknown error'))
                    
                    # Common patterns that indicate request doesn't exist
                    not_found_patterns = [
                        'not found', 'does not exist', 'invalid request', 
                        'request not found', 'no such request'
                    ]
                    
                    if any(pattern in error_msg.lower() for pattern in not_found_patterns):
                        return StatusCheckResult(
                            request_id=request_id,
                            status="purged",
                            raw_response=status_result,
                            timestamp=datetime.now().isoformat(),
                            request_exists=False,
                            error_message=f"Request not found in RDA system: {error_msg}"
                        )
                
                return StatusCheckResult(
                    request_id=request_id,
                    status="unknown",
                    raw_response=status_result,
                    timestamp=datetime.now().isoformat(),
                    error_message="No data in status response"
                )
            
            # Extract status information
            data = status_result['data']
            raw_status = data.get('status', '').lower().strip()
            
            # Normalize status
            normalized_status = self._normalize_status(raw_status)
            
            # Determine if action is needed
            needs_purging = normalized_status == "error"
            needs_retry = False  # Will be determined by error manager
            
            result = StatusCheckResult(
                request_id=request_id,
                status=normalized_status,
                raw_response=status_result,
                timestamp=datetime.now().isoformat(),
                needs_purging=needs_purging,
                needs_retry=needs_retry,
                request_exists=True
            )
            
            self.logger.debug(f"Status check result for {request_id}: {normalized_status}")
            return result
            
        except Exception as e:
            error_msg = f"Error checking status for request {request_id}: {e}"
            self.logger.error(error_msg)
            
            return StatusCheckResult(
                request_id=request_id,
                status="check_failed",
                raw_response={},
                timestamp=datetime.now().isoformat(),
                error_message=error_msg
            )
    
    def _normalize_status(self, raw_status: str) -> str:
        """
        Normalize raw status string to standard categories.
        
        FIXED VERSION: Properly handles "Set for Purge" as a success state.
        
        Args:
            raw_status: Raw status string from RDA
            
        Returns:
            Normalized status: "queued", "processing", "completed", "purged", "error", or "unknown"
        """
        raw_status = raw_status.lower().strip()
        
        # FIXED: Handle "Set for Purge" as successful purge initiation
        if "set for purge" in raw_status or "purge" in raw_status:
            return "purged"
        
        # Check for error patterns (but exclude purge-related "errors")
        for pattern in self.config.error_status_patterns:
            if pattern.lower() in raw_status:
                # Don't treat purge-related responses as errors
                if "purge" not in raw_status:
                    return "error"
        
        # Check for completed patterns
        for pattern in self.config.completed_status_patterns:
            if pattern.lower() in raw_status:
                return "completed"
        
        # Check for processing patterns
        for pattern in self.config.processing_status_patterns:
            if pattern.lower() in raw_status:
                if "queued" in raw_status:
                    return "queued"
                else:
                    return "processing"
        
        # Default to unknown
        self.logger.warning(f"Unknown status pattern: '{raw_status}'")
        return "unknown"
    
    def check_all_active_requests(self) -> Dict[str, StatusCheckResult]:
        """
        Check status of all active requests in the system.
        
        Returns:
            Dictionary mapping request IDs to StatusCheckResult objects
        """
        results = {}
        
        try:
            # Get all active requests from batch system if available
            if self.batch_system:
                active_requests = [
                    (cf, status.request_id) for cf, status in self.batch_system.requests_state.items()
                    if status.request_id and status.status in ["submitted", "processing"]
                ]
                self.logger.info(f"Found {len(active_requests)} active requests from batch system")
                
                # Enhanced diagnostic logging
                if not active_requests:
                    total_requests = len(self.batch_system.requests_state)
                    self.logger.warning(f"No active requests found in batch system (total requests: {total_requests})")
                    
                    # Log status distribution for debugging
                    status_counts = {}
                    for cf, status in self.batch_system.requests_state.items():
                        status_key = f"{status.status}|{status.request_id is not None}"
                        status_counts[status_key] = status_counts.get(status_key, 0) + 1
                    
                    self.logger.info(f"Request status distribution: {status_counts}")
            else:
                # Fallback: get from database
                active_requests = self._get_active_requests_from_db()
                self.logger.info(f"Found {len(active_requests)} active requests from database")
            
            self.logger.info(f"Checking status for {len(active_requests)} active requests")
            
            for control_file, request_id in active_requests:
                if request_id:
                    self.logger.debug(f"Checking status for request {request_id} (control file: {control_file})")
                    result = self.check_request_status_via_client(request_id)
                    results[request_id] = result
                    
                    # Log status result
                    self.logger.info(f"Request {request_id} status: {result.status} (exists: {result.request_exists})")
                    
                    # Update cache
                    with self.monitor_lock:
                        self.status_cache[request_id] = result
                        
                        # Track purged requests
                        if not result.request_exists:
                            self.purged_requests.add(request_id)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error checking all active requests: {e}")
            return {}
    
    def _get_active_requests_from_db(self) -> List[Tuple[str, str]]:
        """Get active requests from database as fallback."""
        try:
            import sqlite3
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT file_path, request_id
                    FROM file_status
                    WHERE status IN ('submitted', 'processing')
                    AND request_id IS NOT NULL
                """)
                
                return [(row[0], row[1]) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Error getting active requests from database: {e}")
            return []
    
    def check_all_rda_requests(self) -> Dict[str, StatusCheckResult]:
        """
        Check status of ALL requests in RDA system, not just locally tracked ones.
        This is crucial for detecting error requests that may not be in local state.
        
        Returns:
            Dictionary mapping request IDs to StatusCheckResult objects
        """
        results = {}
        
        try:
            self.logger.info("Fetching ALL requests from RDA system for comprehensive error detection")
            
            # Get all requests directly from RDA
            rda_status = rdams_client.get_status()
            
            if not rda_status or 'data' not in rda_status:
                self.logger.error("Failed to get RDA status or no data returned")
                return {}
            
            all_requests = rda_status['data']
            self.logger.info(f"Found {len(all_requests)} total requests in RDA system")
            
            # Process each request
            for request_data in all_requests:
                request_id = request_data.get('request_id', '').replace('SAVADI', '')
                if not request_id:
                    continue
                
                raw_status = request_data.get('status', '').strip()
                normalized_status = self._normalize_status(raw_status)
                
                result = StatusCheckResult(
                    request_id=request_id,
                    status=normalized_status,
                    raw_response=request_data,
                    timestamp=datetime.now().isoformat(),
                    needs_purging=(normalized_status == "error"),
                    request_exists=True
                )
                
                results[request_id] = result
                
                # Log important status changes
                if normalized_status == "error":
                    self.logger.warning(f"🚨 ERROR REQUEST DETECTED: {request_id} - Status: {raw_status}")
                elif normalized_status == "completed":
                    self.logger.info(f"✅ COMPLETED REQUEST: {request_id}")
                else:
                    self.logger.debug(f"Request {request_id}: {raw_status} -> {normalized_status}")
            
            # Update cache
            with self.monitor_lock:
                self.status_cache.update(results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error checking all RDA requests: {e}")
            return {}
    
    def process_status_results(self, status_results: Dict[str, StatusCheckResult]) -> Dict[str, Any]:
        """
        Process status check results and trigger appropriate actions.
        
        Args:
            status_results: Dictionary of request ID to StatusCheckResult
            
        Returns:
            Dictionary containing processing results and statistics
        """
        processing_stats = {
            "total_checked": len(status_results),
            "completed": 0,
            "errors_detected": 0,
            "purged_confirmed": 0,
            "retries_scheduled": 0,
            "timestamp": datetime.now().isoformat()
        }
        
        error_requests = []
        completed_requests = []
        purged_requests = []
        
        # Categorize results
        for request_id, result in status_results.items():
            if result.status == "completed":
                completed_requests.append(result)
                processing_stats["completed"] += 1
            elif result.status == "error":
                error_requests.append(result)
                processing_stats["errors_detected"] += 1
            elif result.status == "purged" or not result.request_exists:
                purged_requests.append(result)
                processing_stats["purged_confirmed"] += 1
        
        # Handle confirmed purged requests
        if purged_requests:
            self.logger.info(f"Confirmed {len(purged_requests)} requests have been purged from RDA system")
            self._handle_purged_requests(purged_requests)
        
        # Process error requests with automatic purging
        if error_requests and self.config.auto_purge_errors:
            self.logger.warning(f"🚨 Processing {len(error_requests)} ERROR requests for automatic purging")
            
            # Update database to mark requests as failed
            self._update_request_status_in_db(error_requests)
            
            # Automatically purge error requests directly
            purged_count = 0
            for error_result in error_requests:
                try:
                    self.logger.warning(f"🔥 Auto-purging ERROR request: {error_result.request_id}")
                    
                    # FIXED: Use the corrected rdams_client.purge_request that properly handles "Set for Purge"
                    purge_success = rdams_client.purge_request(error_result.request_id)
                    
                    # FIXED: purge_request now returns True for successful purge initiation (including "Set for Purge")
                    if purge_success:
                        purged_count += 1
                        self.logger.info(f"✅ Successfully initiated purge for error request {error_result.request_id}")
                        
                        # Track as purged
                        with self.monitor_lock:
                            self.purged_requests.add(error_result.request_id)
                    else:
                        self.logger.error(f"❌ Failed to initiate purge for error request {error_result.request_id}")
                        
                except Exception as e:
                    self.logger.error(f"❌ Exception purging error request {error_result.request_id}: {e}")
                
                # Small delay between purges to be respectful to the API
                time.sleep(1)
            
            processing_stats["purged_count"] = purged_count
            self.logger.info(f"🔥 Auto-purge completed: {purged_count}/{len(error_requests)} error requests purge initiated")
            
            # Run unified error detection and retry workflow for additional processing
            try:
                workflow_result = create_unified_error_retry_workflow(
                    db_path=self.db_path,
                    batch_system=self.batch_system,
                    queue_manager=self.queue_manager
                )
                
                if workflow_result.get('workflow_completed', False):
                    retry_count = workflow_result.get('retry_results', {}).get('scheduled', 0)
                    processing_stats["retries_scheduled"] = retry_count
                    
                    self.logger.info(f"Workflow completed: {retry_count} retries scheduled")
            except Exception as e:
                self.logger.error(f"Error in unified workflow: {e}")
        
        # Update batch system status for completed requests - SAFE PURGING ONLY
        if completed_requests and self.batch_system:
            self._update_batch_system_completed(completed_requests)
            
            # SAFE PURGING: Only purge completed requests that have been downloaded
            safe_to_purge_requests = []
            for completed_result in completed_requests:
                # Check if this request has been downloaded in our batch system
                is_downloaded = False
                for control_file, status in self.batch_system.requests_state.items():
                    if (status.request_id == completed_result.request_id and
                        status.status in ["downloaded", "downloaded_purged"]):
                        is_downloaded = True
                        break
                
                if is_downloaded:
                    safe_to_purge_requests.append(completed_result)
                    self.logger.info(f"✅ Request {completed_result.request_id} is safe to purge (already downloaded)")
                else:
                    self.logger.warning(f"⚠️ Request {completed_result.request_id} is completed but NOT downloaded - will NOT purge")
                    
                    # CRITICAL BRIDGE ACTIVATION: Trigger immediate download for undownloaded completed requests
                    self.logger.info(f"🔗 BRIDGE ACTIVATION: Triggering download for undownloaded completed request {completed_result.request_id}")
                    
                    # Find the control file for this request
                    control_file_for_download = None
                    for cf, status in self.batch_system.requests_state.items():
                        if status.request_id == completed_result.request_id:
                            control_file_for_download = cf
                            break
                    
                    if not control_file_for_download:
                        # Create a temporary control file name for orphaned requests
                        control_file_for_download = f"STATUS_MONITOR_BRIDGE_{completed_result.request_id}.ctl"
                        self.logger.info(f"🔗 BRIDGE: Created temporary control file name: {control_file_for_download}")
                    
                    # Trigger immediate download through the bridge
                    bridge_success = self._trigger_immediate_download(control_file_for_download, completed_result.request_id)
                    
                    if bridge_success:
                        self.logger.info(f"✅ BRIDGE SUCCESS: Successfully downloaded completed request {completed_result.request_id}")
                        # Update the completed request to be safe for purging
                        safe_to_purge_requests.append(completed_result)
                    else:
                        self.logger.warning(f"⚠️ BRIDGE FAILED: Could not download completed request {completed_result.request_id}")
            
            if safe_to_purge_requests:
                self.logger.info(f"🔥 Safe auto-purging {len(safe_to_purge_requests)} downloaded completed requests")
                
                purged_completed_count = 0
                for completed_result in safe_to_purge_requests:
                    try:
                        self.logger.info(f"🔥 Safe auto-purging downloaded completed request: {completed_result.request_id}")
                        
                        # FIXED: Use the corrected rdams_client.purge_request
                        import rdams_client
                        purge_success = rdams_client.purge_request(completed_result.request_id)
                        
                        # FIXED: purge_request now returns True for successful purge initiation
                        if purge_success:
                            purged_completed_count += 1
                            self.logger.info(f"✅ Successfully initiated purge for downloaded completed request {completed_result.request_id}")
                            
                            # Track as purged
                            with self.monitor_lock:
                                self.purged_requests.add(completed_result.request_id)
                                
                            # Update batch system to reflect purged status
                            if self.batch_system:
                                for control_file, status in self.batch_system.requests_state.items():
                                    if status.request_id == completed_result.request_id:
                                        with self.batch_system.status_lock:
                                            status.status = "downloaded_purged"  # Mark as downloaded and purged
                                        break
                        else:
                            self.logger.error(f"❌ Failed to initiate purge for downloaded completed request {completed_result.request_id}")
                            
                    except Exception as e:
                        self.logger.error(f"❌ Exception purging downloaded completed request {completed_result.request_id}: {e}")
                    
                    # Small delay between purges to be respectful to the API
                    time.sleep(1)
                
                processing_stats["purged_completed_count"] = purged_completed_count
                self.logger.info(f"🔥 Safe completed request auto-purge: {purged_completed_count}/{len(safe_to_purge_requests)} downloaded requests purge initiated")
            else:
                self.logger.info("ℹ️ No completed requests are safe to purge (none have been downloaded yet)")
                processing_stats["purged_completed_count"] = 0
        
        return processing_stats
    
    def _handle_purged_requests(self, purged_requests: List[StatusCheckResult]):
        """
        Handle requests that have been confirmed as purged from RDA system.
        
        Args:
            purged_requests: List of StatusCheckResult objects for purged requests
        """
        try:
            import sqlite3
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for result in purged_requests:
                    # Update database to reflect purged status
                    cursor.execute("""
                        UPDATE file_status 
                        SET status = 'purged', 
                            error_message = ?,
                            completed_at = ?
                        WHERE request_id = ?
                    """, (
                        result.error_message or "Request confirmed purged from RDA system",
                        result.timestamp,
                        result.request_id
                    ))
                    
                    # Update batch system if available
                    if self.batch_system:
                        for control_file, status in self.batch_system.requests_state.items():
                            if status.request_id == result.request_id:
                                with self.batch_system.status_lock:
                                    status.status = "failed"  # Mark as failed so it can be retried
                                    status.error_message = "Request was purged from RDA system"
                                    status.completion_time = result.timestamp
                                
                                self.logger.info(f"Updated batch system status for {control_file} - request was purged")
                                break
                
                conn.commit()
                self.logger.info(f"Updated {len(purged_requests)} purged requests in database")
                
        except Exception as e:
            self.logger.error(f"Error handling purged requests: {e}")
    
    def _update_request_status_in_db(self, error_requests: List[StatusCheckResult]):
        """Update request status in database for error requests."""
        try:
            import sqlite3
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for result in error_requests:
                    cursor.execute("""
                        UPDATE file_status 
                        SET status = 'failed', 
                            error_message = ?,
                            completed_at = ?
                        WHERE request_id = ?
                    """, (
                        result.error_message or f"RDA status: {result.status}",
                        result.timestamp,
                        result.request_id
                    ))
                
                conn.commit()
                self.logger.info(f"Updated {len(error_requests)} requests to failed status in database")
                
        except Exception as e:
            self.logger.error(f"Error updating request status in database: {e}")
    
    def _update_batch_system_completed(self, completed_requests: List[StatusCheckResult]):
        """Update batch system status for completed requests and trigger downloads."""
        try:
            if not self.batch_system:
                return
            
            for result in completed_requests:
                # Find the control file for this request ID
                for control_file, status in self.batch_system.requests_state.items():
                    if status.request_id == result.request_id:
                        with self.batch_system.status_lock:
                            # CRITICAL FIX: Set to "ready_for_download" instead of "completed"
                            # This matches what batch_automation.py expects for download triggering
                            status.status = "ready_for_download"
                            status.completion_time = result.timestamp
                        
                        self.logger.info(f"🚀 BRIDGE ACTIVATED: Updated {control_file} to ready_for_download - triggering download")
                        
                        # CRITICAL INTEGRATION: Immediately trigger download for this request
                        self._trigger_immediate_download(control_file, result.request_id)
                        break
                        
        except Exception as e:
            self.logger.error(f"Error updating batch system status: {e}")
    
    def _trigger_immediate_download(self, control_file: str, request_id: str):
        """
        CRITICAL BRIDGE FUNCTION: Immediately trigger download for completed requests.
        
        This is the missing bridge between status detection and download execution.
        Enhanced to handle both batch system integration and direct download fallback.
        """
        try:
            self.logger.info(f"🔗 BRIDGE: Triggering immediate download for request {request_id} ({control_file})")
            
            # ENHANCED BRIDGE: Check if batch system is available and has the request
            if not self.batch_system:
                self.logger.warning(f"⚠️ BRIDGE: No batch system available, attempting direct download")
                return self._direct_download_fallback(control_file, request_id)
            
            # Check if the control file exists in batch system state
            if control_file not in self.batch_system.requests_state:
                self.logger.warning(f"⚠️ BRIDGE: Control file {control_file} not in batch system state, creating entry")
                # Create a temporary entry for the completed request
                self._create_batch_system_entry(control_file, request_id)
            
            # Ensure the request is in the correct state for download
            with self.batch_system.status_lock:
                status = self.batch_system.requests_state[control_file]
                if status.status != "ready_for_download":
                    self.logger.info(f"🔄 BRIDGE: Setting {control_file} to ready_for_download state")
                    status.status = "ready_for_download"
                    status.request_id = request_id
                    status.completion_time = datetime.now().isoformat()
            
            # Use the batch system's download method
            download_success = self.batch_system.download_completed_request(control_file)
            
            if download_success:
                self.logger.info(f"✅ BRIDGE SUCCESS: Downloaded request {request_id} successfully via batch system")
                return True
            else:
                self.logger.warning(f"⚠️ BRIDGE: Batch system download failed, attempting direct download fallback")
                return self._direct_download_fallback(control_file, request_id)
                            
        except Exception as e:
            self.logger.error(f"❌ BRIDGE ERROR: Failed to trigger download for {control_file}: {e}")
            
            # Fallback to direct download
            self.logger.info(f"🔄 BRIDGE FALLBACK: Attempting direct download for {control_file}")
            return self._direct_download_fallback(control_file, request_id)
    
    def _create_batch_system_entry(self, control_file: str, request_id: str):
        """Create a batch system entry for a completed request detected by status monitor."""
        try:
            # Import RequestStatus from batch_automation
            from batch_automation import RequestStatus
            
            # Extract region and variable from request ID or control file
            region, variable = self._extract_region_variable_from_request(request_id, control_file)
            
            # Create download directory
            download_dir = f"downloaded_files/{region}/{variable}"
            import os
            os.makedirs(download_dir, exist_ok=True)
            
            # Create request status entry
            request_status = RequestStatus(
                control_file=control_file,
                request_id=request_id,
                status="ready_for_download",
                region=region,
                variable_type=variable,
                download_directory=download_dir,
                completion_time=datetime.now().isoformat()
            )
            
            with self.batch_system.status_lock:
                self.batch_system.requests_state[control_file] = request_status
            
            self.logger.info(f"✅ BRIDGE: Created batch system entry for {control_file} -> {region}/{variable}")
            
        except Exception as e:
            self.logger.error(f"❌ BRIDGE: Failed to create batch system entry for {control_file}: {e}")
    
    def _extract_region_variable_from_request(self, request_id: str, control_file: str):
        """Extract region and variable from request information."""
        try:
            # Try to get request details from RDA
            status_result = rdams_client.get_status(request_id)
            if status_result and 'data' in status_result:
                request_data = status_result['data']
                
                # Use coordinate_utils for enhanced detection
                from coordinate_utils import get_region_and_variable_from_request_enhanced
                region, variable = get_region_and_variable_from_request_enhanced(request_data)
                
                if region != "UNKNOWN" and variable != "unknown":
                    return region, variable
            
            # Fallback: extract from control file name if available
            if control_file and "_" in control_file:
                parts = control_file.replace(".ctl", "").replace("_control", "").split("_")
                if len(parts) >= 2:
                    return parts[0].upper(), parts[1].lower()
            
        except Exception as e:
            self.logger.warning(f"Could not extract region/variable for {request_id}: {e}")
        
        # Final fallback
        return "UNKNOWN", "unknown"
    
    def _direct_download_fallback(self, control_file: str, request_id: str):
        """Direct download fallback when batch system is unavailable or fails."""
        try:
            self.logger.info(f"🔄 DIRECT DOWNLOAD: Attempting direct download for request {request_id}")
            
            # Extract region and variable for proper organization
            region, variable = self._extract_region_variable_from_request(request_id, control_file)
            
            # Create download directory
            download_dir = f"downloaded_files/{region}/{variable}"
            import os
            os.makedirs(download_dir, exist_ok=True)
            
            # Download using rdams_client directly
            download_result = rdams_client.download(request_id, download_dir + "/")
            
            if download_result:
                self.logger.info(f"✅ DIRECT DOWNLOAD SUCCESS: Downloaded request {request_id} to {download_dir}")
                
                # Update batch system if available
                if self.batch_system and control_file in self.batch_system.requests_state:
                    with self.batch_system.status_lock:
                        status = self.batch_system.requests_state[control_file]
                        status.status = "downloaded"
                        status.download_time = datetime.now().isoformat()
                        status.download_directory = download_dir
                
                return True
            else:
                self.logger.error(f"❌ DIRECT DOWNLOAD FAILED: Could not download request {request_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ DIRECT DOWNLOAD ERROR: {e}")
            return False
    
    def start_monitoring(self, interval_seconds: Optional[int] = None):
        """
        Start continuous status monitoring in a background thread.
        
        Args:
            interval_seconds: Override default check interval
        """
        if self.monitoring_active:
            self.logger.warning("Monitoring is already active")
            return
        
        check_interval = interval_seconds or self.config.check_interval_seconds
        
        def monitor_loop():
            self.logger.info(f"Starting status monitoring loop (interval: {check_interval}s)")
            
            while self.monitoring_active:
                try:
                    self.logger.info("🔄 Starting comprehensive monitoring cycle")
                    
                    # Check locally tracked active requests
                    local_status_results = self.check_all_active_requests()
                    
                    # Check ALL RDA requests for comprehensive error detection
                    all_rda_results = self.check_all_rda_requests()
                    
                    # Combine results, prioritizing RDA data
                    status_results = {**local_status_results, **all_rda_results}
                    
                    if status_results:
                        # Enhanced logging for error detection
                        error_requests = [r for r in status_results.values() if r.status == "error"]
                        if error_requests:
                            self.logger.warning(f"🚨 Found {len(error_requests)} ERROR requests in monitoring cycle!")
                        
                        # Process results and trigger actions
                        processing_stats = self.process_status_results(status_results)
                        
                        self.logger.info(f"✅ Comprehensive monitoring cycle completed: {processing_stats}")
                    else:
                        self.logger.debug("No requests found in monitoring cycle")
                    
                    # Wait for next cycle
                    time.sleep(check_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(min(check_interval, 60))  # Wait at least 60 seconds on error
            
            self.logger.info("Status monitoring loop stopped")
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("Status monitoring started")
    
    def stop_monitoring(self):
        """Stop continuous status monitoring."""
        if not self.monitoring_active:
            return
        
        self.logger.info("Stopping status monitoring...")
        self.monitoring_active = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
        
        self.logger.info("Status monitoring stopped")
    
    def run_single_monitoring_cycle(self) -> Dict[str, Any]:
        """
        Run a single monitoring cycle manually.
        
        Returns:
            Dictionary containing cycle results and statistics
        """
        self.logger.info("🔄 Running comprehensive monitoring cycle")
        
        try:
            # First check locally tracked active requests
            local_status_results = self.check_all_active_requests()
            
            # Then check ALL RDA requests for comprehensive error detection
            all_rda_results = self.check_all_rda_requests()
            
            # Combine results, prioritizing RDA data
            status_results = {**local_status_results, **all_rda_results}
            
            if not status_results:
                self.logger.warning("No requests found in either local tracking or RDA system")
                return {
                    "cycle_completed": True,
                    "message": "No requests to monitor",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Process results with enhanced error handling
            processing_stats = self.process_status_results(status_results)
            
            # Enhanced logging for error detection
            error_requests = [r for r in status_results.values() if r.status == "error"]
            if error_requests:
                self.logger.warning(f"🚨 Found {len(error_requests)} ERROR requests that need purging!")
                for req in error_requests:
                    self.logger.warning(f"   - Request {req.request_id}: {req.status}")
            
            # Add detailed results
            cycle_result = {
                "cycle_completed": True,
                "processing_stats": processing_stats,
                "total_requests_checked": len(status_results),
                "local_requests": len(local_status_results),
                "rda_requests": len(all_rda_results),
                "error_requests_found": len(error_requests),
                "status_results": {
                    request_id: {
                        "status": result.status,
                        "needs_purging": result.needs_purging,
                        "request_exists": result.request_exists,
                        "timestamp": result.timestamp
                    }
                    for request_id, result in status_results.items()
                },
                "timestamp": datetime.now().isoformat()
            }
            
            self.logger.info(f"✅ Comprehensive monitoring cycle completed: {processing_stats}")
            return cycle_result
            
        except Exception as e:
            error_msg = f"Error in single monitoring cycle: {e}"
            self.logger.error(error_msg)
            
            return {
                "cycle_completed": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
    
    def resolve_stuck_completed_requests(self, request_ids: List[str] = None) -> Dict[str, Any]:
        """
        CRISIS RESOLUTION: Handle stuck completed requests that haven't been downloaded.
        
        This method specifically addresses the current crisis where requests 804683, 804681, 804680
        are completed but not downloaded due to the integration gap.
        
        Args:
            request_ids: Optional list of specific request IDs to resolve. If None, finds all stuck requests.
            
        Returns:
            Dictionary containing resolution results
        """
        try:
            self.logger.warning("🚨 CRISIS RESOLUTION: Starting resolution of stuck completed requests")
            
            # If specific request IDs provided, use them; otherwise find all stuck requests
            if request_ids:
                target_requests = request_ids
                self.logger.info(f"🎯 Targeting specific requests: {target_requests}")
            else:
                # Find all completed requests that haven't been downloaded
                target_requests = []
                
                # Check RDA system for completed requests
                rda_status = rdams_client.get_status()
                if rda_status and 'data' in rda_status:
                    for request_data in rda_status['data']:
                        status = request_data.get('status', '').lower()
                        request_id = str(request_data.get('request_index', '')).replace('SAVADI', '')
                        
                        if status == 'completed' and request_id:
                            # Check if this request is in our batch system and not downloaded
                            is_downloaded = False
                            for control_file, file_status in (self.batch_system.requests_state.items() if self.batch_system else []):
                                if (file_status.request_id == request_id and
                                    file_status.status in ["downloaded", "downloaded_purged"]):
                                    is_downloaded = True
                                    break
                            
                            if not is_downloaded:
                                target_requests.append(request_id)
                                self.logger.warning(f"🚨 Found stuck completed request: {request_id}")
                
                self.logger.info(f"🔍 Found {len(target_requests)} stuck completed requests")
            
            if not target_requests:
                return {
                    "success": True,
                    "message": "No stuck completed requests found",
                    "resolved_count": 0,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Resolve each stuck request
            resolved_count = 0
            failed_resolutions = []
            
            for request_id in target_requests:
                try:
                    self.logger.info(f"🔧 CRISIS RESOLUTION: Processing stuck request {request_id}")
                    
                    # Find the control file for this request ID
                    control_file = None
                    if self.batch_system:
                        for cf, status in self.batch_system.requests_state.items():
                            if status.request_id == request_id:
                                control_file = cf
                                break
                    
                    if not control_file:
                        # Create a temporary control file entry for orphaned requests
                        control_file = f"CRISIS_RESOLUTION_{request_id}.ctl"
                        self.logger.warning(f"⚠️ Creating temporary entry for orphaned request: {control_file}")
                        
                        if self.batch_system:
                            # Initialize a basic request status for this orphaned request
                            from batch_automation import RequestStatus
                            temp_status = RequestStatus(
                                control_file=control_file,
                                request_id=request_id,
                                status="ready_for_download",
                                region="UNKNOWN",
                                variable_type="unknown",
                                download_directory=f"downloaded_files/CRISIS_RESOLUTION/{request_id}"
                            )
                            
                            with self.batch_system.status_lock:
                                self.batch_system.requests_state[control_file] = temp_status
                    
                    # Update status to ready_for_download
                    if self.batch_system and control_file in self.batch_system.requests_state:
                        with self.batch_system.status_lock:
                            status = self.batch_system.requests_state[control_file]
                            status.status = "ready_for_download"
                            status.completion_time = datetime.now().isoformat()
                        
                        self.logger.info(f"✅ Updated {control_file} to ready_for_download")
                        
                        # Trigger immediate download
                        self._trigger_immediate_download(control_file, request_id)
                        
                        # Check if download was successful by checking the final status
                        if (control_file in self.batch_system.requests_state and
                            self.batch_system.requests_state[control_file].status in ["downloaded", "downloaded_purged"]):
                            resolved_count += 1
                            self.logger.info(f"✅ CRISIS RESOLVED: Successfully processed request {request_id}")
                        else:
                            failed_resolutions.append(request_id)
                            self.logger.error(f"❌ CRISIS PARTIAL: Failed to download request {request_id}")
                    else:
                        failed_resolutions.append(request_id)
                        self.logger.error(f"❌ CRISIS FAILED: Could not find or create control file for request {request_id}")
                
                except Exception as e:
                    failed_resolutions.append(request_id)
                    self.logger.error(f"❌ CRISIS ERROR: Exception resolving request {request_id}: {e}")
                
                # Small delay between resolutions
                time.sleep(1)
            
            # Generate resolution report
            result = {
                "success": resolved_count > 0,
                "total_requests": len(target_requests),
                "resolved_count": resolved_count,
                "failed_count": len(failed_resolutions),
                "failed_requests": failed_resolutions,
                "resolution_rate": (resolved_count / len(target_requests) * 100) if target_requests else 0,
                "timestamp": datetime.now().isoformat()
            }
            
            if resolved_count > 0:
                self.logger.info(f"🎉 CRISIS RESOLUTION COMPLETED: {resolved_count}/{len(target_requests)} requests resolved ({result['resolution_rate']:.1f}%)")
            else:
                self.logger.error(f"❌ CRISIS RESOLUTION FAILED: No requests could be resolved")
            
            if failed_resolutions:
                self.logger.warning(f"⚠️ PARTIAL RESOLUTION: {len(failed_resolutions)} requests still need attention: {failed_resolutions}")
            
            return result
            
        except Exception as e:
            error_msg = f"Critical error in crisis resolution: {e}"
            self.logger.error(f"❌ {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_monitoring_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive monitoring statistics.
        
        Returns:
            Dictionary containing monitoring statistics
        """
        try:
            # Get error manager statistics
            error_stats = self.error_manager.get_error_statistics()
            
            # Get retry manager statistics
            retry_stats = self.retry_manager.get_retry_statistics()
            
            # Get current status cache info
            cache_stats = {
                "cached_requests": len(self.status_cache),
                "purged_requests_tracked": len(self.purged_requests),
                "last_update": max([r.timestamp for r in self.status_cache.values()]) if self.status_cache else None,
                "status_distribution": {}
            }
            
            # Calculate status distribution from cache
            for result in self.status_cache.values():
                status = result.status
                cache_stats["status_distribution"][status] = cache_stats["status_distribution"].get(status, 0) + 1
            
            return {
                "monitoring_active": self.monitoring_active,
                "config": asdict(self.config),
                "error_statistics": error_stats,
                "retry_statistics": retry_stats,
                "cache_statistics": cache_stats,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting monitoring statistics: {e}")
            return {"error": str(e), "generated_at": datetime.now().isoformat()}


def create_status_monitor(db_path: str = "src/python/data/automation_state.db",
                         batch_system=None, queue_manager=None,
                         check_interval_seconds: int = 300) -> StatusMonitor:
    """
    Factory function to create a StatusMonitor with common configuration.
    
    Args:
        db_path: Path to the SQLite database file
        batch_system: Optional BatchAutomationSystem instance
        queue_manager: Optional IntelligentQueueManager instance
        check_interval_seconds: Status check interval in seconds
        
    Returns:
        Configured StatusMonitor instance
    """
    config = MonitorConfig(check_interval_seconds=check_interval_seconds)
    return StatusMonitor(db_path, batch_system, queue_manager, config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='RDA Status Monitor with Crisis Resolution')
    parser.add_argument('--start-monitoring', action='store_true',
                       help='Start continuous monitoring')
    parser.add_argument('--single-cycle', action='store_true',
                       help='Run a single monitoring cycle')
    parser.add_argument('--stats', action='store_true',
                       help='Show monitoring statistics')
    parser.add_argument('--resolve-crisis', action='store_true',
                       help='Resolve stuck completed requests (crisis resolution)')
    parser.add_argument('--resolve-specific', nargs='+',
                       help='Resolve specific request IDs (e.g., --resolve-specific 804683 804681 804680)')
    parser.add_argument('--interval', type=int, default=300,
                       help='Monitoring interval in seconds')
    
    args = parser.parse_args()
    
    # Create status monitor with batch system integration
    try:
        from batch_automation import BatchAutomationSystem
        batch_system = BatchAutomationSystem()
        monitor = create_status_monitor(
            batch_system=batch_system,
            check_interval_seconds=args.interval
        )
    except Exception as e:
        print(f"Warning: Could not initialize batch system integration: {e}")
        monitor = create_status_monitor(check_interval_seconds=args.interval)
    
    try:
        if args.start_monitoring:
            print("=== Starting Continuous Status Monitoring with Download Bridge ===")
            monitor.start_monitoring()
            
            # Keep running until interrupted
            try:
                while monitor.monitoring_active:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping monitoring...")
                monitor.stop_monitoring()
        
        elif args.single_cycle:
            print("=== Running Single Monitoring Cycle with Download Bridge ===")
            result = monitor.run_single_monitoring_cycle()
            print(json.dumps(result, indent=2))
        
        elif args.resolve_crisis:
            print("🚨 === CRISIS RESOLUTION: Resolving All Stuck Completed Requests ===")
            result = monitor.resolve_stuck_completed_requests()
            print("\n" + "="*60)
            print("CRISIS RESOLUTION RESULTS")
            print("="*60)
            print(json.dumps(result, indent=2))
            
            if result.get('success', False):
                print(f"\n✅ SUCCESS: {result.get('resolved_count', 0)}/{result.get('total_requests', 0)} requests resolved")
                if result.get('failed_requests'):
                    print(f"⚠️ ATTENTION NEEDED: {len(result['failed_requests'])} requests still need manual intervention")
                    print(f"Failed requests: {result['failed_requests']}")
            else:
                print(f"\n❌ CRISIS RESOLUTION FAILED: {result.get('error', 'Unknown error')}")
        
        elif args.resolve_specific:
            print(f"🎯 === TARGETED CRISIS RESOLUTION: Resolving Specific Requests {args.resolve_specific} ===")
            result = monitor.resolve_stuck_completed_requests(request_ids=args.resolve_specific)
            print("\n" + "="*60)
            print("TARGETED RESOLUTION RESULTS")
            print("="*60)
            print(json.dumps(result, indent=2))
            
            if result.get('success', False):
                print(f"\n✅ SUCCESS: {result.get('resolved_count', 0)}/{result.get('total_requests', 0)} requests resolved")
            else:
                print(f"\n❌ TARGETED RESOLUTION FAILED: {result.get('error', 'Unknown error')}")
        
        elif args.stats:
            print("=== Monitoring Statistics ===")
            stats = monitor.get_monitoring_statistics()
            print(json.dumps(stats, indent=2))
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("CRISIS RESOLUTION EXAMPLES")
            print("="*60)
            print("# Resolve all stuck completed requests:")
            print("python automation/status_monitor.py --resolve-crisis")
            print("\n# Resolve specific stuck requests:")
            print("python automation/status_monitor.py --resolve-specific 804683 804681 804680")
            print("\n# Start monitoring with automatic download bridge:")
            print("python automation/status_monitor.py --start-monitoring")
            print("="*60)
            
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(monitor, 'monitoring_active') and monitor.monitoring_active:
            monitor.stop_monitoring()