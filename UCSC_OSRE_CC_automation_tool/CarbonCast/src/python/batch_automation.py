#!/usr/bin/env python3
"""
Comprehensive Batch Automation System for RDA Control Files

This system automatically processes all control files in the control_files directory,
submits them to RDA, monitors their progress, and downloads completed requests with
proper REGION_NAME/weather_variable_type organization.

Usage:
    python batch_automation.py --process-all-control-files
    python batch_automation.py --resume
    python batch_automation.py --status
    python batch_automation.py --monitor-only
"""

import os
import sys
import json
import time
import logging
import argparse
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rdams_client
from coordinate_utils import get_region_and_variable_from_request_enhanced
from simple_automation import EnhancedAutomationSystem
from region_detection_utils import extract_region_and_variable_from_request, create_download_directory_path


@dataclass
class RequestStatus:
    """Data class to track request status."""
    control_file: str
    request_id: Optional[str] = None
    status: str = "pending"  # pending, submitted, processing, completed, failed, downloaded
    submission_time: Optional[str] = None
    completion_time: Optional[str] = None
    download_time: Optional[str] = None
    region: str = "UNKNOWN"
    variable_type: str = "unknown"
    download_directory: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    last_check_time: Optional[str] = None


class BatchAutomationSystem:
    """Comprehensive batch automation system for RDA control files."""
    
    def __init__(self, config_file: str = "automation_config.json"):
        """Initialize the batch automation system."""
        self.config = self._load_config(config_file)
        self.logger = self._setup_logging()
        self.automation_system = EnhancedAutomationSystem(
            self.config['directories']['base_download_dir']
        )
        
        # State management
        self.state_file = Path("batch_automation_state.json")
        self.requests_state: Dict[str, RequestStatus] = {}
        self.running = False
        self.paused = False
        
        # Threading
        self.executor = ThreadPoolExecutor(
            max_workers=self.config['automation']['max_concurrent_requests']
        )
        # RLock: _save_state snapshots under this lock and can be invoked
        # from the signal handler, which may interrupt a lock-holding
        # section of the main thread — a plain Lock would deadlock there
        self.status_lock = threading.RLock()
        
        # Load existing state
        self._load_state()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Batch Automation System initialized")
    
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file.

        The path is tried as given (CWD-relative/absolute), then against the
        repo's config/ directory, so running from src/python/ or the repo root
        both find CarbonCast/config/automation_config.json instead of
        silently falling back to defaults.
        """
        candidates = [
            Path(config_file),
            Path(__file__).resolve().parents[2] / 'config' / Path(config_file).name,
        ]
        for candidate in candidates:
            try:
                with open(candidate, 'r') as f:
                    return json.load(f)
            except FileNotFoundError:
                continue

        print(f"Config file not found in {[str(c) for c in candidates]}; using defaults")
        # Return default configuration
        return {
            "automation": {
                "max_concurrent_requests": 10,
                "check_interval_seconds": 300,
                "retry_attempts": 3,
                "retry_delay_seconds": 60,
                "download_timeout_seconds": 3600
            },
            "directories": {
                "base_download_dir": "./downloaded_files",
                "logs_dir": "./logs",
                "control_files_dir": "./control_files"
            }
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logs_dir = Path(self.config['directories']['logs_dir'])
        logs_dir.mkdir(exist_ok=True)
        
        # Create logger
        logger = logging.getLogger('batch_automation')
        logger.setLevel(logging.INFO)
        
        # Create formatters
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # File handler
        log_file = logs_dir / f"batch_automation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
        self._save_state()
        sys.exit(0)
    
    def _load_state(self):
        """Load existing automation state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)
                
                # Convert dictionaries back to RequestStatus objects
                for control_file, status_dict in state_data.items():
                    request_status = RequestStatus(**status_dict)
                    # Recover requests wedged in a transient state by a
                    # crash/kill mid-operation; nothing will ever move
                    # "downloading" forward after a restart
                    if request_status.status == "downloading":
                        request_status.status = "ready_for_download"
                        request_status.error_message = "Recovered from interrupted download"
                    elif request_status.status == "submitting":
                        request_status.status = "pending"
                        request_status.error_message = "Recovered from interrupted submission"
                    self.requests_state[control_file] = request_status

                self.logger.info(f"Loaded state for {len(self.requests_state)} requests")
            except Exception as e:
                self.logger.error(f"Error loading state: {e}")
                self.requests_state = {}
    
    def _save_state(self):
        """Save current automation state (atomically).

        Writes to a temp file and renames it into place so a crash or
        SIGKILL mid-write can't leave a truncated/corrupt JSON that
        wipes all request state on the next start.
        """
        try:
            # Snapshot under the lock so a thread mutating requests_state
            # mid-serialization can't corrupt the dump
            with self.status_lock:
                state_data = {
                    control_file: asdict(status)
                    for control_file, status in self.requests_state.items()
                }

            tmp_file = self.state_file.with_suffix('.json.tmp')
            with open(tmp_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, self.state_file)

            self.logger.debug("State saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")
    
    def reset_changed_control_files(self) -> int:
        """Reset state entries whose control file changed since they ran.

        State is keyed by ctl-file path, so weekly regeneration (same
        filenames, new date ranges) would otherwise leave entries stuck at
        "downloaded" and the new date window would never be submitted.
        An entry is reset to pending when the ctl file's mtime is newer
        than the entry's most recent lifecycle timestamp.
        """
        reset_count = 0
        with self.status_lock:
            for control_file, request_status in self.requests_state.items():
                if not os.path.exists(control_file):
                    continue
                timestamps = [
                    t for t in (
                        request_status.download_time,
                        request_status.completion_time,
                        request_status.submission_time,
                    ) if t
                ]
                if not timestamps:
                    continue
                try:
                    last_activity = max(
                        datetime.fromisoformat(t).timestamp() for t in timestamps
                    )
                except ValueError:
                    continue
                if os.path.getmtime(control_file) > last_activity:
                    self.requests_state[control_file] = RequestStatus(
                        control_file=control_file,
                        region=request_status.region,
                        variable_type=request_status.variable_type,
                        download_directory=request_status.download_directory,
                    )
                    reset_count += 1

        if reset_count:
            self.logger.info(
                f"Reset {reset_count} requests whose control files changed since last run"
            )
            self._save_state()
        return reset_count

    def discover_control_files(self) -> List[str]:
        """Discover all control files in the control_files directory."""
        control_files_dir = Path(self.config['directories']['control_files_dir'])
        
        if not control_files_dir.exists():
            self.logger.error(f"Control files directory not found: {control_files_dir}")
            return []
        
        # Find all .ctl files
        control_files = list(control_files_dir.glob("*.ctl"))
        control_file_paths = [str(cf) for cf in control_files]
        
        self.logger.info(f"Discovered {len(control_file_paths)} control files")
        return control_file_paths
    
    def initialize_requests(self, control_files: List[str]):
        """Initialize request status for all control files."""
        for control_file in control_files:
            if control_file not in self.requests_state:
                self.requests_state[control_file] = RequestStatus(
                    control_file=control_file,
                    status="pending"
                )
        
        self.logger.info(f"Initialized {len(control_files)} requests")
    
    def extract_region_and_variable_from_control_file(self, control_file: str) -> Tuple[str, str]:
        """Extract region and variable from control file name and content."""
        try:
            # Extract from filename pattern: REGION_VARIABLE_control.ctl
            filename = Path(control_file).name
            self.logger.debug(f"Processing control file: {filename}")
            
            # Handle the standard pattern: REGION_VARIABLE_control.ctl
            if filename.endswith('_control.ctl'):
                base_name = filename[:-12]  # Remove '_control.ctl'
                parts = base_name.split('_')
                self.logger.debug(f"Filename parts after removing '_control.ctl': {parts}")
                
                if len(parts) >= 2:
                    region = parts[0].upper()
                    variable = parts[1].lower()
                    
                    self.logger.info(f"Successfully extracted from filename: {region}/{variable} from {filename}")
                    return region, variable
                elif len(parts) == 1:
                    # Handle edge case where there might be only region
                    self.logger.warning(f"Only one part found in filename: {parts}")
            
            # Alternative parsing: try splitting by underscores and look for control.ctl
            if '.ctl' in filename:
                # Remove .ctl extension first
                base_name = filename[:-4]  # Remove '.ctl'
                parts = base_name.split('_')
                self.logger.debug(f"All filename parts: {parts}")
                
                # Look for 'control' in the parts and extract region/variable before it
                if 'control' in parts:
                    control_index = parts.index('control')
                    if control_index >= 2:
                        region = parts[0].upper()
                        variable = parts[1].lower()
                        self.logger.info(f"Extracted using control index method: {region}/{variable} from {filename}")
                        return region, variable
                
                # Fallback: assume first two parts are region and variable
                if len(parts) >= 2:
                    region = parts[0].upper()
                    variable = parts[1].lower()
                    self.logger.info(f"Extracted using fallback method: {region}/{variable} from {filename}")
                    return region, variable
            
            # Final fallback: read control file content
            try:
                self.logger.debug(f"Attempting to read control file content for {control_file}")
                control_params = rdams_client.read_control_file(control_file)
                
                # Create a mock request object for the enhanced detection
                mock_request = {
                    'request_index': f"CONTROL_{Path(control_file).stem}",
                    'rinfo': f"nlat={control_params.get('nlat', '')};slat={control_params.get('slat', '')};wlon={control_params.get('wlon', '')};elon={control_params.get('elon', '')}",
                    'subset_info': {
                        'note': f"Parameter(s):\n{control_params.get('param', '')}"
                    },
                    'title': f"Control file: {filename}",
                    'description': f"Automated processing of {filename}"
                }
                
                region, variable = get_region_and_variable_from_request_enhanced(mock_request)
                self.logger.info(f"Extracted from content analysis: {region}/{variable}")
                return region, variable
                
            except Exception as e:
                self.logger.warning(f"Error reading control file {control_file}: {e}")
        
        except Exception as e:
            self.logger.error(f"Error extracting region/variable from {control_file}: {e}")
        
        # Final fallback - log the issue
        self.logger.error(f"Could not extract region/variable from {control_file}, returning UNKNOWN/unknown")
        return "UNKNOWN", "unknown"
    
    def submit_request(self, control_file: str) -> bool:
        """Submit a single control file to RDA."""
        try:
            with self.status_lock:
                request_status = self.requests_state[control_file]
                if request_status.status != "pending":
                    return False
                
                request_status.status = "submitting"
            
            # CRITICAL FIX: Check request count before submission
            current_request_count = self._get_current_request_count()
            if current_request_count >= 10:
                self.logger.warning(f"Cannot submit {control_file}: Already at 10-request limit ({current_request_count} active)")
                
                # Try crisis resolution first
                self.logger.info("🚨 Attempting automatic crisis resolution...")
                crisis_result = self.resolve_request_limit_crisis()
                
                if crisis_result.get('success', False):
                    self.logger.info(f"✅ Crisis resolved: {crisis_result.get('initial_requests', 0)} → {crisis_result.get('final_requests', 0)} requests")
                    current_request_count = self._get_current_request_count()
                else:
                    self.logger.warning("⚠️ Crisis resolution failed, trying aggressive purging...")
                    # Fallback to aggressive purging
                    purged_count = self._aggressive_purge_completed_requests()
                    if purged_count > 0:
                        self.logger.info(f"Purged {purged_count} completed requests, retrying submission")
                        current_request_count = self._get_current_request_count()
                
                if current_request_count >= 10:
                    with self.status_lock:
                        request_status.status = "pending"  # Reset to pending for retry
                        request_status.error_message = f"Request limit reached ({current_request_count}/10) - Crisis resolution failed"
                    return False
            
            self.logger.info(f"Submitting control file: {control_file} (Current requests: {current_request_count}/10)")
            
            # Submit using rdams_client
            result = rdams_client.submit(control_file)

            # Request ID location differs by API generation: the legacy
            # rda.ucar.edu API returned top-level 'request_index'; the gdex
            # API nests it as data.request_id. Missing this meant successful
            # submissions were recorded as failures while the request lived
            # on untracked at NCAR, silently burning the 10-request quota.
            request_id = None
            if isinstance(result, dict):
                if result.get('request_index'):
                    request_id = str(result['request_index'])
                elif isinstance(result.get('data'), dict) and result['data'].get('request_id'):
                    request_id = str(result['data']['request_id'])

            if request_id:
                
                # Extract region and variable
                region, variable = self.extract_region_and_variable_from_control_file(control_file)
                
                # Create download directory using standardized path
                download_dir = create_download_directory_path("downloaded_files", region, variable)
                os.makedirs(download_dir, exist_ok=True)
                
                with self.status_lock:
                    request_status.request_id = request_id
                    request_status.status = "submitted"
                    request_status.submission_time = datetime.now().isoformat()
                    request_status.region = region
                    request_status.variable_type = variable
                    request_status.download_directory = str(download_dir)
                
                self.logger.info(f"Successfully submitted {control_file} -> Request ID: {request_id}")
                return True
            else:
                # IMPROVED ERROR HANDLING: Check for HTTP 400 (limit violation)
                error_msg = f"Submission failed: {result}"
                if isinstance(result, dict) and result.get('http_response') == 400:
                    error_msg = "HTTP 400: Request limit exceeded or API violation"
                    self.logger.error(f"API LIMIT VIOLATION for {control_file}: {error_msg}")
                
                with self.status_lock:
                    request_status.status = "failed"
                    request_status.error_message = error_msg
                
                self.logger.error(f"Failed to submit {control_file}: {error_msg}")
                return False
        
        except Exception as e:
            error_msg = f"Exception during submission: {e}"
            with self.status_lock:
                request_status = self.requests_state[control_file]
                request_status.status = "failed"
                request_status.error_message = error_msg
            
            self.logger.error(f"Error submitting {control_file}: {e}")
            return False
    
    def check_request_status(self, control_file: str) -> bool:
        """Check the status of a submitted request."""
        try:
            with self.status_lock:
                request_status = self.requests_state[control_file]
                if not request_status.request_id or request_status.status in ["downloaded", "failed"]:
                    return False
            
            request_id = request_status.request_id
            self.logger.debug(f"Checking status for request {request_id}")

            # Get status from RDA
            status_result = rdams_client.get_status(request_id)

            if not status_result:
                return False

            # Top-level API errors (e.g. 421 "Request Index not found" during
            # the indexing lag right after submission, or rate limiting) are
            # transient — do NOT mark the request failed, just retry later.
            if str(status_result.get('status', '')).lower() == 'error':
                self.logger.warning(
                    f"Transient status API error for request {request_id}: "
                    f"{status_result.get('error_messages')}"
                )
                return False

            # gdex may return data as a dict or a single-element list
            data = status_result.get('data')
            if isinstance(data, list):
                data = data[0] if data else {}
            if not isinstance(data, dict):
                return False

            # gdex status vocabulary: 'Queued for Processing', 'Processing',
            # 'Completed', 'Error', 'Set for Purge' — match by substring.
            rda_status = str(data.get('status', '')).lower()

            with self.status_lock:
                request_status.last_check_time = datetime.now().isoformat()

                if rda_status == 'completed':
                    # CRITICAL FIX: Only mark as "ready_for_download", not "completed"
                    # This prevents the race condition where status shows completed but files aren't downloaded
                    if request_status.status != "ready_for_download":
                        request_status.status = "ready_for_download"
                        request_status.completion_time = datetime.now().isoformat()
                        self.logger.info(f"Request {request_id} ready for download")
                    return True
                elif any(t in rda_status for t in ('queue', 'process', 'running', 'building')):
                    request_status.status = "processing"
                elif any(t in rda_status for t in ('error', 'fail')):
                    # Grace period: freshly submitted requests can briefly
                    # report an error state before the subset job registers.
                    # Only trust a failure reading once the request is >5 min old.
                    age_ok = True
                    if request_status.submission_time:
                        try:
                            submitted = datetime.fromisoformat(request_status.submission_time)
                            age_ok = (datetime.now() - submitted).total_seconds() > 300
                        except ValueError:
                            pass
                    if age_ok:
                        request_status.status = "failed"
                        request_status.error_message = f"RDA status: {rda_status}"
                        self.logger.error(f"Request {request_id} failed with status: {rda_status}")
                    else:
                        self.logger.warning(
                            f"Request {request_id} reports '{rda_status}' shortly after "
                            f"submission — treating as transient"
                        )

            return False
        
        except Exception as e:
            self.logger.error(f"Error checking status for {control_file}: {e}")
            return False
    
    def download_completed_request(self, control_file: str) -> bool:
        """Download files for a completed request."""
        try:
            with self.status_lock:
                request_status = self.requests_state[control_file]
                # CRITICAL FIX: Check for "ready_for_download" status instead of "completed"
                if request_status.status != "ready_for_download" or not request_status.request_id:
                    return False
                
                request_status.status = "downloading"
            
            request_id = request_status.request_id
            download_dir = request_status.download_directory
            
            self.logger.info(f"Downloading request {request_id} to {download_dir}")
            
            # Ensure download directory exists
            os.makedirs(download_dir, exist_ok=True)
            
            # Download using rdams_client with proper path handling
            download_result = rdams_client.download(request_id, download_dir + "/")

            # Only treat the download as successful when files actually landed
            # on disk — a truthy filelist response with zero downloaded files
            # previously marked requests "downloaded" and then purged them,
            # permanently losing the data.
            summary = (download_result or {}).get('download_summary', {})
            if summary.get('complete'):
                with self.status_lock:
                    # CRITICAL FIX: Only mark as "downloaded" AFTER successful download
                    request_status.status = "downloaded"
                    request_status.download_time = datetime.now().isoformat()
                
                self.logger.info(f"Successfully downloaded request {request_id} to {download_dir}")
                
                # Auto-purge after successful download if enabled
                if self.config['automation'].get('auto_purge_after_download', True):
                    self.logger.info(f"Auto-purging request {request_id} after successful download")
                    purge_success = self.purge_request(control_file, "after successful download")
                    if not purge_success:
                        self.logger.warning(f"Failed to auto-purge request {request_id}, but download was successful")
                
                return True
            else:
                with self.status_lock:
                    # Reset to ready_for_download for retry, not "completed"
                    request_status.status = "ready_for_download"
                    request_status.error_message = (
                        f"Download incomplete: {summary.get('downloaded', 0)}"
                        f"/{summary.get('expected', '?')} files"
                    )

                self.logger.error(
                    f"Failed to download request {request_id}: "
                    f"{summary.get('downloaded', 0)}/{summary.get('expected', '?')} files"
                )
                return False
        
        except Exception as e:
            error_msg = f"Exception during download: {e}"
            with self.status_lock:
                request_status = self.requests_state[control_file]
                # Reset to ready_for_download for retry
                request_status.status = "ready_for_download"
                request_status.error_message = error_msg
            
            self.logger.error(f"Error downloading {control_file}: {e}")
            return False
    
    def purge_request(self, control_file: str, reason: str = "automatic") -> bool:
        """
        FIXED VERSION: Purge a request from RDA to free up request slots.
        
        Now properly handles RDA's two-stage purge process where "Set for Purge" is success.
        """
        try:
            with self.status_lock:
                request_status = self.requests_state[control_file]
                if not request_status.request_id:
                    self.logger.warning(f"No request ID found for {control_file}, cannot purge")
                    return False
            
            request_id = request_status.request_id
            
            self.logger.info(f"Initiating purge for request {request_id} ({reason}) for {control_file}")
            
            # FIXED: Use the corrected rdams_client.purge_request (no retry needed for "Set for Purge")
            try:
                # Call rdams_client.purge_request with string conversion
                purge_success = rdams_client.purge_request(str(request_id))
                
                # FIXED: purge_request now returns True for successful purge initiation
                if purge_success:
                    self.logger.info(f"Successfully initiated purge for request {request_id} for {control_file}")
                    
                    # Update request status to indicate it was purged
                    with self.status_lock:
                        request_status.status = f"{request_status.status}_purged"
                        request_status.completion_time = datetime.now().isoformat()
                    
                    return True
                else:
                    self.logger.error(f"Failed to initiate purge for request {request_id}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Exception during purge of request {request_id}: {e}")
                return False
        
        except Exception as e:
            self.logger.error(f"Error in purge_request for {control_file}: {e}")
            return False
    
    def _get_current_request_count(self) -> int:
        """Get current number of active requests from RDA (excluding requests set for purge)."""
        try:
            status_result = rdams_client.get_status()
            if status_result and 'data' in status_result:
                # FIXED: Only count requests that are NOT "Set for Purge"
                # Requests with "Set for Purge" status should not count toward the 10-request limit
                active_requests = []
                status_breakdown = {}
                
                for request in status_result['data']:
                    status = request.get('status', '').lower()
                    status_breakdown[status] = status_breakdown.get(status, 0) + 1
                    
                    # Only count requests that are truly active (not set for purge)
                    if 'set for purge' not in status and 'purge' not in status:
                        active_requests.append(request)
                
                active_count = len(active_requests)
                total_count = len(status_result['data'])
                
                self.logger.info(f"RDA Request Status Breakdown: {status_breakdown} (Active: {active_count}/{total_count})")
                
                return active_count
            return 0
        except Exception as e:
            self.logger.error(f"Error getting current request count: {e}")
            return 10  # Assume worst case to prevent submissions
    
    def _aggressive_purge_completed_requests(self) -> int:
        """
        FIXED VERSION: SAFELY purge completed requests that have been downloaded to free up slots.
        
        Now properly handles "Set for Purge" as success.
        """
        purged_count = 0
        try:
            self.logger.warning("🚨 SAFE EMERGENCY PURGING: Attempting to purge downloaded completed requests")
            status_result = rdams_client.get_status()
            if status_result and 'data' in status_result:
                safe_to_purge = []
                
                for request in status_result['data']:
                    status = request.get('status', '').lower()
                    request_id = str(request['request_index'])
                    
                    # RULE 1: Always safe to purge error requests
                    if status in ['error', 'failed']:
                        safe_to_purge.append((request_id, 'error'))
                        self.logger.info(f"Found ERROR request safe to purge: {request_id}")
                    
                    # RULE 2: Only purge completed requests if downloaded
                    elif status == 'completed':
                        is_downloaded = False
                        for control_file, file_status in self.requests_state.items():
                            if (file_status.request_id == request_id and
                                file_status.status in ["downloaded", "downloaded_purged"]):
                                is_downloaded = True
                                break
                        
                        if is_downloaded:
                            safe_to_purge.append((request_id, 'completed_downloaded'))
                            self.logger.info(f"Found COMPLETED+DOWNLOADED request safe to purge: {request_id}")
                        else:
                            self.logger.warning(f"⚠️ COMPLETED request NOT SAFE to purge (not downloaded): {request_id}")
                    
                    # FIXED: Don't try to purge requests already "Set for Purge"
                    elif "set for purge" in status:
                        self.logger.info(f"ℹ️ Request {request_id} already set for purge - skipping")
                
                self.logger.info(f"🔥 Safe emergency purging {len(safe_to_purge)} requests")
                
                for request_id, purge_reason in safe_to_purge:
                    try:
                        self.logger.info(f"🔥 Safe emergency purging request: {request_id} (reason: {purge_reason})")
                        
                        # FIXED: Use the corrected rdams_client.purge_request
                        purge_result = rdams_client.purge_request(str(request_id))
                        
                        # FIXED: purge_request now returns True for successful purge initiation
                        if purge_result:
                            purged_count += 1
                            self.logger.info(f"✅ Safe emergency purge initiated for request {request_id}")
                            
                            # Update local state if we have it
                            for control_file, status in self.requests_state.items():
                                if status.request_id == request_id:
                                    with self.status_lock:
                                        if purge_reason == 'error':
                                            status.status = "failed_purged"
                                        else:
                                            status.status = "downloaded_purged"
                                    break
                        else:
                            self.logger.error(f"❌ Failed to initiate safe emergency purge for request {request_id}")
                            
                        # Small delay between purges
                        time.sleep(1)
                        
                    except Exception as e:
                        self.logger.error(f"❌ Exception during safe emergency purge of {request_id}: {e}")
                
                self.logger.warning(f"🚨 SAFE EMERGENCY PURGING COMPLETED: {purged_count}/{len(safe_to_purge)} requests purge initiated")
            return purged_count
        except Exception as e:
            self.logger.error(f"Error in safe aggressive purging: {e}")
            return 0
    
    def resolve_request_limit_crisis(self) -> Dict:
        """
        Resolve the crisis when there are too many active requests (>10).
        
        This method safely downloads and purges completed requests to bring
        the system within the 10-request limit.
        
        Returns:
            Dictionary with resolution results
        """
        try:
            self.logger.warning("🚨 CRISIS RESOLUTION: Attempting to resolve request limit crisis")
            
            # Get current RDA status
            status_result = rdams_client.get_status()
            if not status_result or 'data' not in status_result:
                return {'success': False, 'error': 'Failed to get RDA status'}
            
            requests = status_result['data']
            total_requests = len(requests)
            
            if total_requests <= 10:
                self.logger.info(f"✅ System already within limits: {total_requests}/10 requests")
                return {'success': True, 'message': 'System already within limits', 'requests_count': total_requests}
            
            self.logger.warning(f"🚨 CRISIS DETECTED: {total_requests}/10 requests (over limit)")
            
            # Find completed requests
            completed_requests = [req for req in requests if req.get('status', '').lower() == 'completed']
            
            if not completed_requests:
                self.logger.error("❌ No completed requests available for crisis resolution")
                return {'success': False, 'error': 'No completed requests to download/purge'}
            
            self.logger.info(f"🎯 Found {len(completed_requests)} completed requests for crisis resolution")
            
            # Download and purge completed requests
            downloaded_count = 0
            purged_count = 0
            
            for request_data in completed_requests:
                request_id = str(request_data.get('request_index', ''))
                
                try:
                    # Try to download the request
                    self.logger.info(f"📥 Crisis download: Request {request_id}")
                    
                    # Extract region and variable for proper organization
                    region, variable = extract_region_and_variable_from_request(request_data)
                    
                    # Create organized download directory (not just CRISIS_RESOLUTION)
                    if region != "UNKNOWN" and variable != "unknown":
                        temp_download_dir = create_download_directory_path("downloaded_files", region, variable)
                    else:
                        # Fallback to crisis resolution directory if detection fails
                        temp_download_dir = os.path.join("downloaded_files", "CRISIS_RESOLUTION", request_id)
                    
                    os.makedirs(temp_download_dir, exist_ok=True)
                    self.logger.info(f"📁 Crisis download directory: {temp_download_dir} (region={region}, variable={variable})")
                    
                    # Download using rdams_client
                    download_result = rdams_client.download(request_id, temp_download_dir + "/")

                    # Require verified on-disk files before purging — purging a
                    # request whose download silently failed loses the data
                    if (download_result or {}).get('download_summary', {}).get('complete'):
                        downloaded_count += 1
                        self.logger.info(f"✅ Crisis download successful: Request {request_id}")
                        
                        # Now safely purge the downloaded request
                        self.logger.info(f"🔥 Crisis purge: Request {request_id}")
                        purge_result = rdams_client.purge_request(str(request_id))
                        
                        if purge_result:
                            purged_count += 1
                            self.logger.info(f"✅ Crisis purge successful: Request {request_id}")
                        else:
                            self.logger.error(f"❌ Crisis purge failed: Request {request_id}")
                    else:
                        self.logger.error(f"❌ Crisis download failed: Request {request_id}")
                
                except Exception as e:
                    self.logger.error(f"❌ Crisis resolution error for request {request_id}: {e}")
                
                # Small delay between operations
                time.sleep(2)
            
            # Check final status
            final_status = rdams_client.get_status()
            final_count = len(final_status['data']) if final_status and 'data' in final_status else total_requests
            
            success = final_count <= 10
            
            result = {
                'success': success,
                'initial_requests': total_requests,
                'final_requests': final_count,
                'requests_freed': total_requests - final_count,
                'downloaded_count': downloaded_count,
                'purged_count': purged_count,
                'within_limits': success
            }
            
            if success:
                self.logger.info(f"✅ CRISIS RESOLVED: {total_requests} → {final_count} requests")
            else:
                self.logger.warning(f"⚠️ CRISIS PARTIALLY RESOLVED: {total_requests} → {final_count} requests")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ CRITICAL ERROR in crisis resolution: {e}")
            return {'success': False, 'error': str(e)}
    
    def process_pending_submissions(self):
        """Process all pending submissions with rate limiting."""
        pending_requests = [
            cf for cf, status in self.requests_state.items()
            if status.status == "pending"
        ]
        
        if not pending_requests:
            return
        
        self.logger.info(f"Processing {len(pending_requests)} pending submissions")
        
        # Submit requests with rate limiting
        futures = []
        for control_file in pending_requests:
            if not self.running:
                break
            
            future = self.executor.submit(self.submit_request, control_file)
            futures.append(future)
            
            # Rate limiting
            time.sleep(1)  # 1 second between submissions
        
        # Wait for submissions to complete
        for future in as_completed(futures):
            if not self.running:
                break
            try:
                future.result()
            except Exception as e:
                self.logger.error(f"Submission future failed: {e}")
    
    def monitor_active_requests(self):
        """Monitor all active requests for completion."""
        active_requests = [
            cf for cf, status in self.requests_state.items()
            if status.status in ["submitted", "processing"]
        ]
        
        # Also check for requests ready for download
        ready_for_download = [
            cf for cf, status in self.requests_state.items()
            if status.status == "ready_for_download"
        ]
        
        if not active_requests and not ready_for_download:
            return
        
        self.logger.info(f"Monitoring {len(active_requests)} active requests, {len(ready_for_download)} ready for download")
        
        # Check status of active requests
        futures = []
        for control_file in active_requests:
            if not self.running:
                break
            
            future = self.executor.submit(self.check_request_status, control_file)
            futures.append(future)
        
        # Process requests that became ready for download
        newly_ready_requests = []
        for future in as_completed(futures):
            if not self.running:
                break
            try:
                if future.result():  # Request became ready for download
                    # Find which request became ready
                    for cf, status in self.requests_state.items():
                        if status.status == "ready_for_download" and cf not in ready_for_download:
                            newly_ready_requests.append(cf)
            except Exception as e:
                self.logger.error(f"Status check future failed: {e}")
        
        # Combine all requests ready for download
        all_ready_requests = ready_for_download + newly_ready_requests
        
        # Download ready requests
        if all_ready_requests:
            self.logger.info(f"Downloading {len(all_ready_requests)} ready requests")
            download_futures = []
            
            for control_file in all_ready_requests:
                if not self.running:
                    break
                
                future = self.executor.submit(self.download_completed_request, control_file)
                download_futures.append(future)
            
            # Wait for downloads to complete
            for future in as_completed(download_futures):
                if not self.running:
                    break
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Download future failed: {e}")
    
    def retry_failed_requests(self):
        """Retry failed requests that haven't exceeded retry limit."""
        max_retries = self.config['automation']['retry_attempts']
        retry_delay = self.config['automation']['retry_delay_seconds']
        
        failed_requests = [
            cf for cf, status in self.requests_state.items()
            if status.status == "failed" and status.retry_count < max_retries
        ]
        
        if not failed_requests:
            return
        
        self.logger.info(f"Retrying {len(failed_requests)} failed requests")
        
        for control_file in failed_requests:
            if not self.running:
                break
            
            with self.status_lock:
                request_status = self.requests_state[control_file]
                request_status.retry_count += 1
                request_status.status = "pending"
                request_status.error_message = None
            
            self.logger.info(f"Retrying {control_file} (attempt {request_status.retry_count})")
            
            # Add delay between retries
            time.sleep(retry_delay)
    
    def purge_failed_requests(self):
        """Purge failed requests that have exceeded retry limit to free up slots."""
        if not self.config['automation'].get('auto_purge_failed_requests', True):
            return
        
        max_retries = self.config['automation']['retry_attempts']
        
        # Find requests that have failed and exceeded retry limit
        failed_requests = [
            cf for cf, status in self.requests_state.items()
            if status.status == "failed" and status.retry_count >= max_retries and status.request_id
        ]
        
        if not failed_requests:
            return
        
        self.logger.info(f"Purging {len(failed_requests)} failed requests that exceeded retry limit")
        
        for control_file in failed_requests:
            if not self.running:
                break
            
            request_status = self.requests_state[control_file]
            self.logger.info(f"Purging failed request {request_status.request_id} for {control_file} (retries: {request_status.retry_count}/{max_retries})")
            
            purge_success = self.purge_request(control_file, f"failed after {request_status.retry_count} retries")
            if purge_success:
                self.logger.info(f"Successfully purged failed request for {control_file}")
            else:
                self.logger.warning(f"Failed to purge failed request for {control_file}")
    
    def print_status_summary(self):
        """Print a summary of current status."""
        status_counts = {}
        for status in self.requests_state.values():
            status_counts[status.status] = status_counts.get(status.status, 0) + 1
        
        total_requests = len(self.requests_state)
        
        print("\n" + "="*60)
        print("BATCH AUTOMATION STATUS SUMMARY")
        print("="*60)
        print(f"Total Requests: {total_requests}")
        
        for status, count in sorted(status_counts.items()):
            percentage = (count / total_requests * 100) if total_requests > 0 else 0
            print(f"  {status.capitalize()}: {count} ({percentage:.1f}%)")
        
        # Calculate progress
        completed = status_counts.get("downloaded", 0) + status_counts.get("downloaded_purged", 0)
        progress = (completed / total_requests * 100) if total_requests > 0 else 0
        print(f"\nOverall Progress: {completed}/{total_requests} ({progress:.1f}%)")
        
        # Estimate completion time
        if completed > 0 and completed < total_requests:
            # Simple estimation based on current rate
            processing_time = datetime.now()
            # This is a simplified estimation - in reality you'd track timing better
            print(f"Estimated completion: In progress...")
        
        print("="*60)
    
    def _all_requests_complete(self) -> bool:
        """Check if all requests are complete."""
        incomplete_statuses = ["pending", "submitted", "processing", "ready_for_download"]
        
        for status in self.requests_state.values():
            if status.status in incomplete_statuses:
                return False
        
        return True
    
    def run_batch_processing(self):
        """Main batch processing loop."""
        self.logger.info("Starting batch processing...")
        self.running = True
        
        # Discover and initialize control files
        control_files = self.discover_control_files()
        if not control_files:
            self.logger.error("No control files found")
            return
        
        self.initialize_requests(control_files)
        
        check_interval = self.config['automation']['check_interval_seconds']
        
        try:
            while self.running:
                if self.paused:
                    time.sleep(10)
                    continue
                
                self.logger.info("Processing cycle started")
                
                # Process pending submissions
                self.process_pending_submissions()
                
                # Monitor active requests
                self.monitor_active_requests()
                
                # Retry failed requests
                self.retry_failed_requests()
                
                # Purge failed requests if enabled
                self.purge_failed_requests()
                
                # Save state
                self._save_state()
                
                # Print status summary
                self.print_status_summary()
                
                # Check if all requests are complete
                all_complete = all(
                    status.status in ["downloaded", "failed", "downloaded_purged", "failed_purged"]
                    for status in self.requests_state.values()
                )
                
                if all_complete:
                    self.logger.info("All requests processed!")
                    break
                
                # Wait before next cycle
                self.logger.info(f"Waiting {check_interval} seconds before next cycle...")
                time.sleep(check_interval)
        
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal, shutting down...")
        finally:
            self.running = False
            self._save_state()
            self.executor.shutdown(wait=True)
            self.logger.info("Batch processing completed")
    
    def resume_processing(self):
        """Resume processing from saved state."""
        self.logger.info("Resuming batch processing from saved state...")
        self.run_batch_processing()
    
    def monitor_only(self):
        """Monitor existing requests without submitting new ones."""
        self.logger.info("Starting monitor-only mode...")
        self.running = True
        
        check_interval = self.config['automation']['check_interval_seconds']
        
        try:
            while self.running:
                # Only monitor and download, no new submissions
                self.monitor_active_requests()
                self._save_state()
                self.print_status_summary()
                
                # Check if monitoring is still needed
                active_requests = [
                    cf for cf, status in self.requests_state.items()
                    if status.status in ["submitted", "processing", "ready_for_download"]
                ]
                
                if not active_requests:
                    self.logger.info("No active requests to monitor")
                    break
                
                time.sleep(check_interval)
        
        except KeyboardInterrupt:
            self.logger.info("Monitor interrupted")
        finally:
            self.running = False
            self._save_state()


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Comprehensive Batch Automation System for RDA')
    parser.add_argument('--process-all-control-files', action='store_true',
                       help='Process all control files from scratch')
    parser.add_argument('--resume', action='store_true',
                       help='Resume processing from saved state')
    parser.add_argument('--status', action='store_true',
                       help='Show current status summary')
    parser.add_argument('--monitor-only', action='store_true',
                       help='Monitor existing requests without submitting new ones')
    parser.add_argument('--resolve-crisis', action='store_true',
                       help='Manually resolve request limit crisis by downloading and purging completed requests')
    parser.add_argument('--reprocess-changed', action='store_true',
                       help='Reset requests whose control files were modified after they completed '
                            '(needed for weekly regenerated ctl files)')
    parser.add_argument('--config', default='automation_config.json',
                       help='Configuration file path')
    parser.add_argument('--control-files-dir', default=None,
                       help='Override the config control_files_dir (e.g. for single-file tests)')

    args = parser.parse_args()

    # Initialize system
    system = BatchAutomationSystem(args.config)
    if args.control_files_dir:
        system.config['directories']['control_files_dir'] = args.control_files_dir

    if args.reprocess_changed:
        system.reset_changed_control_files()

    if args.status:
        system.print_status_summary()
    elif args.monitor_only:
        system.monitor_only()
    elif args.resume:
        system.resume_processing()
    elif args.process_all_control_files:
        system.run_batch_processing()
    elif args.resolve_crisis:
        print("🚨 MANUAL CRISIS RESOLUTION")
        print("=" * 50)
        result = system.resolve_request_limit_crisis()
        print("\n" + "=" * 50)
        print("CRISIS RESOLUTION RESULTS")
        print("=" * 50)
        if result['success']:
            print("✅ SUCCESS: Crisis resolved!")
            print(f"📊 Requests: {result.get('initial_requests', 0)} → {result.get('final_requests', 0)}")
            print(f"📥 Downloads: {result.get('downloaded_count', 0)}")
            print(f"🔥 Purges: {result.get('purged_count', 0)}")
            print("🚀 New requests can now be submitted!")
        else:
            print("❌ CRISIS NOT RESOLVED")
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
        print("=" * 50)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()