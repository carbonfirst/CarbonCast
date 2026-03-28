#!/usr/bin/env python3
"""
Upload Automation Integration Module for RDA Automation System

This module provides centralized upload automation functionality that integrates
with the capacity manager, workflow orchestrator, and upload_files script to
provide seamless automated request submission when capacity is available.

Key Features:
- Capacity-based upload triggering
- Integration with existing automation components
- Upload monitoring and error handling
- Intelligent scheduling and coordination
- Comprehensive logging and reporting
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
from enum import Enum
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger

from upload_files import submit_batch_files, discover_control_files
from automation.capacity_manager import CapacityManager, CapacityStatus, CapacityAction


class UploadTriggerReason(Enum):
    """Enumeration for upload trigger reasons."""
    CAPACITY_AVAILABLE = "capacity_available"
    MANUAL_TRIGGER = "manual_trigger"
    SCHEDULED_UPLOAD = "scheduled_upload"
    CRISIS_RECOVERY = "crisis_recovery"


class UploadStatus(Enum):
    """Enumeration for upload status."""
    READY = "ready"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"
    INSUFFICIENT_CAPACITY = "insufficient_capacity"
    NO_FILES = "no_files"


@dataclass
class UploadConfig:
    """Configuration for upload automation - AGGRESSIVE 10-REQUEST TARGETING."""
    # Core settings - AGGRESSIVE
    enabled: bool = True
    capacity_threshold: int = 10  # Changed from 9 to 10 - upload even at 10 requests
    batch_size: int = 10  # Increased from 2 to 10 for aggressive uploading
    rate_limit_delay: float = 0.5  # Reduced from 2.0 to 0.5 for faster uploads
    
    # File management
    control_files_dir: str = "src/python/incoming"
    processed_files_dir: str = "src/python/processed"
    failed_files_dir: str = "src/python/failed_uploads"
    
    # Scheduling - AGGRESSIVE
    min_upload_interval: int = 30  # Reduced from 300 to 30 seconds for frequent uploads
    max_daily_uploads: int = 1000  # Increased from 50 to 1000 for maximum throughput
    upload_window_start: int = 0  # Changed from 6 to 0 - upload 24/7
    upload_window_end: int = 24  # Changed from 22 to 24 - upload 24/7
    
    # Error handling - AGGRESSIVE
    max_retry_attempts: int = 5  # Increased from 3 to 5
    retry_delay: int = 60  # Reduced from 600 to 60 seconds for faster retries
    
    # Integration
    db_path: str = "src/python/data/automation_state.db"


@dataclass
class UploadResult:
    """Result of an upload operation."""
    upload_id: str
    trigger_reason: UploadTriggerReason
    status: UploadStatus
    files_attempted: int
    files_submitted: int
    files_failed: int
    request_ids: List[str]
    error_messages: List[str]
    start_time: str
    end_time: str
    duration: float
    capacity_before: int
    capacity_after: int


@dataclass
class UploadMonitoringInfo:
    """Upload monitoring information."""
    total_uploads_today: int
    successful_uploads: int
    failed_uploads: int
    last_upload_time: Optional[str]
    next_eligible_upload: Optional[str]
    available_files: int
    current_capacity: int
    upload_enabled: bool
    in_upload_window: bool


class UploadAutomationManager:
    """
    Centralized upload automation manager.
    
    Coordinates upload automation across all system components with
    intelligent scheduling, capacity management, and error handling.
    """
    
    def __init__(self, config: Optional[UploadConfig] = None,
                 capacity_manager: Optional[CapacityManager] = None):
        """
        Initialize the Upload Automation Manager.
        
        Args:
            config: Upload automation configuration
            capacity_manager: Capacity manager instance
        """
        self.config = config or UploadConfig()
        self.capacity_manager = capacity_manager
        self.logger = self._setup_logging()
        
        # Upload state
        self.upload_active = False
        self.last_upload_time = None
        self.upload_history = []
        self.daily_upload_count = 0
        self.failed_files_cache = {}
        
        # Statistics
        self.upload_stats = {
            'total_uploads': 0,
            'successful_uploads': 0,
            'failed_uploads': 0,
            'total_files_submitted': 0,
            'total_files_failed': 0,
            'last_reset_date': datetime.now().date().isoformat()
        }
        
        # Threading
        self.upload_lock = threading.Lock()
        
        # Ensure directories exist
        self._ensure_directories()
        
        self.logger.info("Upload Automation Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.upload_automation', level=logging.INFO)
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        directories = [
            self.config.control_files_dir,
            self.config.processed_files_dir,
            self.config.failed_files_dir
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def _reset_daily_stats_if_needed(self):
        """Reset daily statistics if it's a new day."""
        today = datetime.now().date().isoformat()
        if self.upload_stats['last_reset_date'] != today:
            self.daily_upload_count = 0
            self.upload_stats['last_reset_date'] = today
            self.logger.info("Daily upload statistics reset")
    
    def _is_in_upload_window(self) -> bool:
        """Check if current time is within the upload window."""
        current_hour = datetime.now().hour
        return self.config.upload_window_start <= current_hour < self.config.upload_window_end
    
    def _can_upload_now(self) -> Tuple[bool, str]:
        """
        Check if uploads can be performed now.
        
        Returns:
            Tuple of (can_upload, reason)
        """
        if not self.config.enabled:
            return False, "Upload automation is disabled"
        
        if not self._is_in_upload_window():
            return False, f"Outside upload window ({self.config.upload_window_start}-{self.config.upload_window_end})"
        
        self._reset_daily_stats_if_needed()
        
        if self.daily_upload_count >= self.config.max_daily_uploads:
            return False, f"Daily upload limit reached ({self.daily_upload_count}/{self.config.max_daily_uploads})"
        
        if self.last_upload_time:
            time_since_last = time.time() - self.last_upload_time
            if time_since_last < self.config.min_upload_interval:
                remaining = self.config.min_upload_interval - time_since_last
                return False, f"Too soon since last upload ({remaining:.0f}s remaining)"
        
        if self.upload_active:
            return False, "Upload already in progress"
        
        return True, "Ready to upload"
    
    def get_upload_monitoring_info(self) -> UploadMonitoringInfo:
        """
        Get current upload monitoring information.
        
        Returns:
            UploadMonitoringInfo object
        """
        try:
            # Get capacity information
            current_capacity = 0
            if self.capacity_manager:
                capacity_status = self.capacity_manager.get_current_capacity_status()
                current_capacity = capacity_status.total_requests
            
            # Count available files
            available_files = len(discover_control_files(self.config.control_files_dir))
            
            # Calculate next eligible upload time
            next_eligible_upload = None
            if self.last_upload_time:
                next_time = self.last_upload_time + self.config.min_upload_interval
                if next_time > time.time():
                    next_eligible_upload = datetime.fromtimestamp(next_time).isoformat()
            
            # Reset daily stats if needed
            self._reset_daily_stats_if_needed()
            
            return UploadMonitoringInfo(
                total_uploads_today=self.daily_upload_count,
                successful_uploads=self.upload_stats['successful_uploads'],
                failed_uploads=self.upload_stats['failed_uploads'],
                last_upload_time=datetime.fromtimestamp(self.last_upload_time).isoformat() if self.last_upload_time else None,
                next_eligible_upload=next_eligible_upload,
                available_files=available_files,
                current_capacity=current_capacity,
                upload_enabled=self.config.enabled,
                in_upload_window=self._is_in_upload_window()
            )
            
        except Exception as e:
            self.logger.error(f"Error getting upload monitoring info: {e}")
            return UploadMonitoringInfo(
                total_uploads_today=0,
                successful_uploads=0,
                failed_uploads=0,
                last_upload_time=None,
                next_eligible_upload=None,
                available_files=0,
                current_capacity=0,
                upload_enabled=False,
                in_upload_window=False
            )
    
    def trigger_upload(self, trigger_reason: UploadTriggerReason = UploadTriggerReason.MANUAL_TRIGGER,
                      max_files: Optional[int] = None) -> UploadResult:
        """
        Trigger an upload operation.
        
        Args:
            trigger_reason: Reason for triggering the upload
            max_files: Maximum number of files to upload (overrides config)
            
        Returns:
            UploadResult with operation details
        """
        upload_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()
        
        try:
            with self.upload_lock:
                self.logger.info(f"🚀 Starting upload operation: {upload_id} (reason: {trigger_reason.value})")
                
                # Check if upload is allowed
                can_upload, reason = self._can_upload_now()
                if not can_upload:
                    self.logger.info(f"🚫 Upload blocked: {reason}")
                    return UploadResult(
                        upload_id=upload_id,
                        trigger_reason=trigger_reason,
                        status=UploadStatus.DISABLED,
                        files_attempted=0,
                        files_submitted=0,
                        files_failed=0,
                        request_ids=[],
                        error_messages=[reason],
                        start_time=datetime.fromtimestamp(start_time).isoformat(),
                        end_time=datetime.now().isoformat(),
                        duration=time.time() - start_time,
                        capacity_before=0,
                        capacity_after=0
                    )
                
                # Get current capacity
                capacity_before = 0
                if self.capacity_manager:
                    capacity_status = self.capacity_manager.get_current_capacity_status()
                    capacity_before = capacity_status.total_requests
                    
                    # AGGRESSIVE: Allow uploads even at capacity threshold to maintain 10 requests
                    if capacity_before > self.config.capacity_threshold:
                        self.logger.info(f"🚫 Upload blocked: capacity too high ({capacity_before} > {self.config.capacity_threshold})")
                        return UploadResult(
                            upload_id=upload_id,
                            trigger_reason=trigger_reason,
                            status=UploadStatus.INSUFFICIENT_CAPACITY,
                            files_attempted=0,
                            files_submitted=0,
                            files_failed=0,
                            request_ids=[],
                            error_messages=[f"Capacity too high: {capacity_before}/{self.config.capacity_threshold}"],
                            start_time=datetime.fromtimestamp(start_time).isoformat(),
                            end_time=datetime.now().isoformat(),
                            duration=time.time() - start_time,
                            capacity_before=capacity_before,
                            capacity_after=capacity_before
                        )
                
                # Discover files to upload
                control_files = discover_control_files(self.config.control_files_dir)
                if not control_files:
                    self.logger.info("📭 No control files available for upload")
                    return UploadResult(
                        upload_id=upload_id,
                        trigger_reason=trigger_reason,
                        status=UploadStatus.NO_FILES,
                        files_attempted=0,
                        files_submitted=0,
                        files_failed=0,
                        request_ids=[],
                        error_messages=["No control files available"],
                        start_time=datetime.fromtimestamp(start_time).isoformat(),
                        end_time=datetime.now().isoformat(),
                        duration=time.time() - start_time,
                        capacity_before=capacity_before,
                        capacity_after=capacity_before
                    )
                
                # AGGRESSIVE: Determine batch size to fill available slots
                available_slots = max(0, 10 - capacity_before)
                if max_files is not None:
                    batch_size = min(max_files, available_slots, self.config.batch_size)
                else:
                    batch_size = min(available_slots, self.config.batch_size, len(control_files))
                
                # AGGRESSIVE: Always try to upload at least 1 file if available
                if batch_size == 0 and len(control_files) > 0:
                    batch_size = 1
                    self.logger.info(f"🔥 AGGRESSIVE: No slots but forcing 1 file upload to maintain pressure")
                
                files_to_upload = control_files[:batch_size]
                
                self.logger.info(f"📤 AGGRESSIVE Upload: {len(files_to_upload)} files (capacity: {capacity_before}/10, target: 10)")
                
                # Mark upload as active
                self.upload_active = True
                
                try:
                    # Perform the upload
                    upload_result = submit_batch_files(
                        file_paths=files_to_upload,
                        rate_limit_delay=self.config.rate_limit_delay,
                        logger=self.logger
                    )
                    
                    # Process results
                    files_submitted = len(upload_result.get('submitted_files', []))
                    files_failed = len(upload_result.get('failed_files', []))
                    request_ids = upload_result.get('request_ids', [])
                    error_messages = upload_result.get('errors', [])
                    
                    # Move processed files
                    self._move_processed_files(
                        upload_result.get('submitted_files', []),
                        upload_result.get('failed_files', [])
                    )
                    
                    # Update statistics
                    self.daily_upload_count += 1
                    self.upload_stats['total_uploads'] += 1
                    self.upload_stats['total_files_submitted'] += files_submitted
                    self.upload_stats['total_files_failed'] += files_failed
                    
                    if files_submitted > 0:
                        self.upload_stats['successful_uploads'] += 1
                        status = UploadStatus.COMPLETED
                        self.logger.info(f"✅ Upload completed: {files_submitted} files submitted")
                    else:
                        self.upload_stats['failed_uploads'] += 1
                        status = UploadStatus.FAILED
                        self.logger.warning(f"⚠️ Upload failed: no files submitted")
                    
                    # Update last upload time
                    self.last_upload_time = time.time()
                    
                    # Get final capacity
                    capacity_after = capacity_before
                    if self.capacity_manager:
                        final_capacity_status = self.capacity_manager.get_current_capacity_status()
                        capacity_after = final_capacity_status.total_requests
                    
                    return UploadResult(
                        upload_id=upload_id,
                        trigger_reason=trigger_reason,
                        status=status,
                        files_attempted=len(files_to_upload),
                        files_submitted=files_submitted,
                        files_failed=files_failed,
                        request_ids=request_ids,
                        error_messages=error_messages,
                        start_time=datetime.fromtimestamp(start_time).isoformat(),
                        end_time=datetime.now().isoformat(),
                        duration=time.time() - start_time,
                        capacity_before=capacity_before,
                        capacity_after=capacity_after
                    )
                    
                finally:
                    self.upload_active = False
                    
        except Exception as e:
            self.upload_active = False
            error_msg = f"Upload operation failed: {str(e)}"
            self.logger.error(error_msg)
            
            return UploadResult(
                upload_id=upload_id,
                trigger_reason=trigger_reason,
                status=UploadStatus.FAILED,
                files_attempted=0,
                files_submitted=0,
                files_failed=0,
                request_ids=[],
                error_messages=[error_msg],
                start_time=datetime.fromtimestamp(start_time).isoformat(),
                end_time=datetime.now().isoformat(),
                duration=time.time() - start_time,
                capacity_before=0,
                capacity_after=0
            )
    
    def _move_processed_files(self, submitted_files: List[str], failed_files: List[str]):
        """Move processed files to appropriate directories."""
        try:
            # Move successfully submitted files
            for file_path in submitted_files:
                try:
                    source = Path(file_path)
                    if source.exists():
                        dest = Path(self.config.processed_files_dir) / source.name
                        source.rename(dest)
                        self.logger.debug(f"Moved submitted file: {source} -> {dest}")
                except Exception as e:
                    self.logger.warning(f"Failed to move submitted file {file_path}: {e}")
            
            # Move failed files
            for file_path in failed_files:
                try:
                    source = Path(file_path)
                    if source.exists():
                        dest = Path(self.config.failed_files_dir) / source.name
                        source.rename(dest)
                        self.logger.debug(f"Moved failed file: {source} -> {dest}")
                except Exception as e:
                    self.logger.warning(f"Failed to move failed file {file_path}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error moving processed files: {e}")
    
    def get_upload_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive upload statistics.
        
        Returns:
            Dictionary with upload statistics
        """
        try:
            monitoring_info = self.get_upload_monitoring_info()
            
            return {
                'statistics': self.upload_stats.copy(),
                'monitoring': asdict(monitoring_info),
                'configuration': asdict(self.config),
                'current_status': {
                    'upload_active': self.upload_active,
                    'last_upload_time': datetime.fromtimestamp(self.last_upload_time).isoformat() if self.last_upload_time else None,
                    'upload_history_length': len(self.upload_history)
                },
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting upload statistics: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }


def create_upload_automation_manager(config: Optional[UploadConfig] = None,
                                   capacity_manager: Optional[CapacityManager] = None) -> UploadAutomationManager:
    """
    Factory function to create an Upload Automation Manager.
    
    Args:
        config: Upload automation configuration
        capacity_manager: Capacity manager instance
        
    Returns:
        Configured UploadAutomationManager instance
    """
    return UploadAutomationManager(config, capacity_manager)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Upload Automation Manager')
    parser.add_argument('--trigger-upload', action='store_true',
                       help='Trigger a manual upload')
    parser.add_argument('--status', action='store_true',
                       help='Show upload status')
    parser.add_argument('--statistics', action='store_true',
                       help='Show upload statistics')
    parser.add_argument('--max-files', type=int,
                       help='Maximum files to upload')
    
    args = parser.parse_args()
    
    # Create upload automation manager
    manager = create_upload_automation_manager()
    
    try:
        if args.trigger_upload:
            print("=== Triggering Manual Upload ===")
            result = manager.trigger_upload(
                trigger_reason=UploadTriggerReason.MANUAL_TRIGGER,
                max_files=args.max_files
            )
            print(json.dumps(asdict(result), indent=2, default=str))
        
        elif args.status:
            print("=== Upload Status ===")
            status = manager.get_upload_monitoring_info()
            print(json.dumps(asdict(status), indent=2, default=str))
        
        elif args.statistics:
            print("=== Upload Statistics ===")
            stats = manager.get_upload_statistics()
            print(json.dumps(stats, indent=2, default=str))
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("UPLOAD AUTOMATION MANAGER EXAMPLES")
            print("="*60)
            print("# Trigger manual upload:")
            print("python automation/upload_automation.py --trigger-upload")
            print("\n# Show upload status:")
            print("python automation/upload_automation.py --status")
            print("\n# Show upload statistics:")
            print("python automation/upload_automation.py --statistics")
            print("\n# Upload specific number of files:")
            print("python automation/upload_automation.py --trigger-upload --max-files 3")
            print("="*60)
            
    except Exception as e:
        print(f"Error: {e}")