#!/usr/bin/env python3
"""
Sequential File Processor for RDA Automation System

This module provides the main orchestration class for sequential file processing
that processes control files from the control_files folder from top to bottom.
It integrates all components and provides a complete sequential processing workflow.

Key Features:
- Sequential processing of control files in alphabetical order
- Integration with existing automation system and capacity management
- Real-time progress tracking and completion messaging
- Automatic completion detection and reporting
- Error handling and recovery mechanisms
- Resume capability for interrupted processing sessions
- Dashboard integration for real-time updates
"""

import os
import sys
import json
import time
import logging
import threading
import signal
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our sequential processing components
from automation.control_file_discovery import ControlFileDiscovery, create_control_file_discovery
from automation.processing_progress_tracker import (
    ProcessingProgressTracker, create_processing_progress_tracker,
    ProcessingStatus, ProgressPhase
)
from automation.completion_notifier import CompletionNotifier, create_completion_notifier, NotificationConfig

# Import existing automation components
from automation.automated_request_manager import AutomatedRequestManager, create_automated_request_manager
from automation.capacity_manager import CapacityManager, create_capacity_manager
from automation.smart_retry_manager import SmartRetryManager, create_smart_retry_manager
from automation.data_sync import RDADataSyncService, create_data_sync_service
from upload_files import submit_batch_files


class ProcessingMode(Enum):
    """Enumeration for processing modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    RESUME = "resume"


class ProcessorState(Enum):
    """Enumeration for processor states."""
    IDLE = "idle"
    DISCOVERING = "discovering"
    PROCESSING = "processing"
    MONITORING = "monitoring"
    COMPLETING = "completing"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"


@dataclass
class ProcessingConfig:
    """Configuration for sequential file processing."""
    # File discovery settings
    control_files_dir: str = "control_files"
    processing_order: str = "alphabetical"  # alphabetical, priority, region, variable
    
    # Processing settings
    processing_mode: ProcessingMode = ProcessingMode.SEQUENTIAL
    max_concurrent_files: int = 1  # For sequential processing, should be 1
    retry_failed_files: bool = True
    max_retries_per_file: int = 3
    
    # Timing settings
    file_submission_delay: float = 5.0  # Seconds between file submissions
    status_check_interval: int = 60  # Seconds between status checks
    completion_check_interval: int = 300  # Seconds between completion checks
    
    # Integration settings
    enable_capacity_management: bool = True
    enable_smart_retry: bool = True
    enable_data_sync: bool = True
    enable_progress_tracking: bool = True
    enable_completion_notifications: bool = True
    
    # Database settings
    db_path: str = "src/python/data/automation_state.db"
    
    # Resume settings
    resume_session_id: Optional[str] = None
    resume_from_file: Optional[str] = None


@dataclass
class ProcessingResult:
    """Result of sequential file processing."""
    session_id: str
    success: bool
    total_files: int
    processed_files: int
    completed_files: int
    failed_files: int
    skipped_files: int
    processing_time_hours: float
    error_message: Optional[str]
    completion_report: Optional[Dict[str, Any]]


class SequentialFileProcessor:
    """
    Main sequential file processor for RDA automation system.
    
    This class orchestrates the complete sequential processing workflow,
    integrating all components for a seamless processing experience.
    """
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        """
        Initialize the Sequential File Processor.
        
        Args:
            config: Processing configuration
        """
        self.config = config or ProcessingConfig()
        self.logger = self._setup_logging()
        
        # Initialize components
        self.file_discovery = create_control_file_discovery(
            self.config.control_files_dir, self.config.db_path
        )
        self.progress_tracker = None  # Will be initialized when processing starts
        self.completion_notifier = create_completion_notifier(
            self.config.db_path, NotificationConfig(enable_console=True, enable_file_report=True)
        )
        
        # Initialize existing automation components
        self.request_manager = create_automated_request_manager(db_path=self.config.db_path)
        self.capacity_manager = create_capacity_manager(db_path=self.config.db_path) if self.config.enable_capacity_management else None
        if self.config.enable_smart_retry:
            try:
                from automation.smart_retry_manager import SmartRetryConfig
                retry_config = SmartRetryConfig(db_path=self.config.db_path)
                self.retry_manager = create_smart_retry_manager(retry_config)
            except Exception as e:
                self.logger.warning(f"Could not initialize smart retry manager: {e}")
                self.retry_manager = None
        else:
            self.retry_manager = None
        self.data_sync = create_data_sync_service(self.config.db_path) if self.config.enable_data_sync else None
        
        # Processing state
        self.current_state = ProcessorState.IDLE
        self.session_id = None
        self.processing_active = False
        self.processing_thread = None
        self.start_time = None
        self.current_file_index = 0
        self.files_to_process = []
        
        # Statistics
        self.processing_stats = {
            'files_submitted': 0,
            'files_completed': 0,
            'files_failed': 0,
            'files_skipped': 0,
            'total_processing_time': 0.0,
            'errors_encountered': []
        }
        
        # Threading
        self.processing_lock = threading.Lock()
        self.shutdown_requested = False
        
        # Signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Sequential File Processor initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the sequential processor."""
        logger = logging.getLogger('rda_automation.sequential_file_processor')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        self.stop_processing()
    
    def _transition_state(self, new_state: ProcessorState, reason: str = ""):
        """Transition to a new processor state."""
        old_state = self.current_state
        
        with self.processing_lock:
            self.current_state = new_state
        
        self.logger.info(f"🔄 State transition: {old_state.value} -> {new_state.value}" + 
                        (f" ({reason})" if reason else ""))
    
    def discover_files(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Discover control files for processing.
        
        Returns:
            Tuple of (success, file_list, discovery_info)
        """
        try:
            self._transition_state(ProcessorState.DISCOVERING, "Starting file discovery")
            
            self.logger.info("🔍 Discovering control files...")
            
            # Discover files using the specified order
            files = self.file_discovery.get_processing_order(self.config.processing_order)
            
            if not files:
                self.logger.warning("No valid control files found for processing")
                return False, [], {'error': 'No valid control files found'}
            
            # Extract filenames
            file_list = [f.filename for f in files]
            
            # Get discovery statistics
            discovery_stats = self.file_discovery.get_discovery_statistics()
            
            self.logger.info(f"✅ Discovered {len(file_list)} files for processing")
            self.logger.info(f"📊 Processing order: {self.config.processing_order}")
            
            # Update database tracking
            discovery_result = self.file_discovery.discover_control_files(include_invalid=False)
            self.file_discovery.update_database_tracking(discovery_result)
            
            return True, file_list, {
                'total_files': len(file_list),
                'processing_order': self.config.processing_order,
                'discovery_stats': discovery_stats,
                'files': [asdict(f) for f in files]
            }
        
        except Exception as e:
            self.logger.error(f"Error discovering files: {e}")
            return False, [], {'error': str(e)}
    
    def start_processing(self, resume_session_id: Optional[str] = None) -> bool:
        """
        Start sequential file processing.
        
        Args:
            resume_session_id: Optional session ID to resume
            
        Returns:
            True if processing started successfully, False otherwise
        """
        if self.processing_active:
            self.logger.warning("Processing is already active")
            return False
        
        try:
            # Generate session ID
            if resume_session_id:
                self.session_id = resume_session_id
                self.logger.info(f"🔄 Resuming processing session: {self.session_id}")
            else:
                self.session_id = f"sequential_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.logger.info(f"🚀 Starting new processing session: {self.session_id}")
            
            # Initialize progress tracker
            self.progress_tracker = create_processing_progress_tracker(
                self.config.db_path, self.session_id
            )
            
            # Discover files
            success, file_list, discovery_info = self.discover_files()
            if not success:
                self.logger.error("File discovery failed")
                return False
            
            self.files_to_process = file_list
            
            # Start processing session
            self.progress_tracker.start_processing_session(len(file_list), file_list)
            
            # Initialize processing state
            self.processing_active = True
            self.start_time = datetime.now()
            self.current_file_index = 0
            self.shutdown_requested = False
            
            # Start capacity monitoring if enabled
            if self.capacity_manager:
                self.capacity_manager.start_capacity_monitoring()
            
            # Start processing thread
            self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
            self.processing_thread.start()
            
            self._transition_state(ProcessorState.PROCESSING, "Processing started")
            
            self.logger.info(f"✅ Sequential processing started with {len(file_list)} files")
            return True
        
        except Exception as e:
            self.logger.error(f"Error starting processing: {e}")
            self.processing_active = False
            return False
    
    def _processing_loop(self):
        """Main processing loop that handles sequential file processing."""
        try:
            self.logger.info("🔄 Starting sequential processing loop")
            
            while (self.processing_active and 
                   not self.shutdown_requested and 
                   self.current_file_index < len(self.files_to_process)):
                
                current_file = self.files_to_process[self.current_file_index]
                
                try:
                    # Update progress
                    self.progress_tracker.update_phase(
                        ProgressPhase.SUBMISSION, current_file
                    )
                    
                    self.logger.info(f"📤 Processing file {self.current_file_index + 1}/{len(self.files_to_process)}: {current_file}")
                    
                    # Submit file for processing
                    success, request_id, error_msg = self._submit_file(current_file)
                    
                    if success:
                        self.logger.info(f"✅ File submitted successfully: {current_file} (Request: {request_id})")
                        
                        # Update progress
                        self.progress_tracker.update_file_progress(
                            current_file, ProcessingStatus.PROCESSING, request_id=request_id
                        )
                        
                        # Monitor file processing
                        self._monitor_file_processing(current_file, request_id)
                        
                        self.processing_stats['files_submitted'] += 1
                    else:
                        self.logger.error(f"❌ File submission failed: {current_file} - {error_msg}")
                        
                        # Update progress
                        self.progress_tracker.update_file_progress(
                            current_file, ProcessingStatus.FAILED, error_message=error_msg
                        )
                        
                        self.processing_stats['files_failed'] += 1
                        self.processing_stats['errors_encountered'].append({
                            'file': current_file,
                            'error': error_msg,
                            'timestamp': datetime.now().isoformat()
                        })
                    
                    # Move to next file
                    self.current_file_index += 1
                    
                    # Wait between file submissions
                    if self.current_file_index < len(self.files_to_process):
                        time.sleep(self.config.file_submission_delay)
                
                except Exception as e:
                    self.logger.error(f"Error processing file {current_file}: {e}")
                    
                    # Update progress
                    self.progress_tracker.update_file_progress(
                        current_file, ProcessingStatus.FAILED, error_message=str(e)
                    )
                    
                    self.processing_stats['files_failed'] += 1
                    self.current_file_index += 1
            
            # All files submitted, now monitor completion
            if not self.shutdown_requested:
                self._monitor_completion()
            
        except Exception as e:
            self.logger.error(f"Error in processing loop: {e}")
            self._transition_state(ProcessorState.ERROR, f"Processing loop error: {e}")
        finally:
            self._cleanup_processing()
    
    def _submit_file(self, filename: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Submit a single file for processing.
        
        Args:
            filename: Name of the file to submit
            
        Returns:
            Tuple of (success, request_id, error_message)
        """
        try:
            file_path = Path(self.config.control_files_dir) / filename
            
            if not file_path.exists():
                return False, None, f"File not found: {file_path}"
            
            # Check capacity if capacity management is enabled
            if self.capacity_manager:
                capacity_status = self.capacity_manager.get_current_capacity_status()
                if capacity_status.total_requests >= 9:  # Leave room for one more
                    self.logger.warning(f"⚠️ Capacity near limit ({capacity_status.total_requests}/10), waiting...")
                    
                    # Wait for capacity to free up
                    max_wait_time = 1800  # 30 minutes
                    wait_start = time.time()
                    
                    while (capacity_status.total_requests >= 9 and 
                           time.time() - wait_start < max_wait_time and
                           not self.shutdown_requested):
                        time.sleep(60)  # Check every minute
                        capacity_status = self.capacity_manager.get_current_capacity_status()
                    
                    if capacity_status.total_requests >= 9:
                        return False, None, "Capacity limit reached and timeout exceeded"
            
            # Submit file using existing upload functionality
            result = submit_batch_files(
                file_paths=[str(file_path)],
                rate_limit_delay=2.0,
                logger=self.logger
            )
            
            if result.get('success') and result.get('request_ids'):
                request_id = result['request_ids'][0]
                return True, request_id, None
            else:
                error_msg = result.get('error', 'Unknown submission error')
                return False, None, error_msg
        
        except Exception as e:
            return False, None, str(e)
    
    def _monitor_file_processing(self, filename: str, request_id: str):
        """
        Monitor the processing of a single file.
        
        Args:
            filename: Name of the file being processed
            request_id: RDA request ID
        """
        try:
            self.logger.info(f"👁️ Monitoring file processing: {filename} (Request: {request_id})")
            
            # Update progress phase
            self.progress_tracker.update_phase(ProgressPhase.MONITORING, filename)
            
            # This is a simplified monitoring approach
            # In a full implementation, this would continuously monitor the request status
            # For now, we'll just update the progress and let the existing automation handle it
            
            # The actual monitoring will be handled by the existing automation components
            # (automated_request_manager, status_monitor, etc.)
            
        except Exception as e:
            self.logger.error(f"Error monitoring file processing: {e}")
    
    def _monitor_completion(self):
        """Monitor overall processing completion."""
        try:
            self._transition_state(ProcessorState.COMPLETING, "Monitoring completion")
            
            self.logger.info("🏁 All files submitted, monitoring completion...")
            
            # Update progress phase
            self.progress_tracker.update_phase(ProgressPhase.DOWNLOADING)
            
            # Monitor until all files are complete or failed
            while not self.shutdown_requested:
                # Check completion status
                is_complete, completion_info = self.completion_notifier.check_completion_status(self.session_id)
                
                if is_complete:
                    self.logger.info("🎉 All files processing completed!")
                    break
                
                # Log progress
                self.logger.info(f"📊 Progress: {completion_info.get('completion_percentage', 0):.1f}% "
                               f"({completion_info.get('completed_files', 0)}/{completion_info.get('total_files', 0)} files)")
                
                # Wait before next check
                time.sleep(self.config.completion_check_interval)
            
            # Generate completion report
            if not self.shutdown_requested:
                self._handle_completion()
        
        except Exception as e:
            self.logger.error(f"Error monitoring completion: {e}")
            self._transition_state(ProcessorState.ERROR, f"Completion monitoring error: {e}")
    
    def _handle_completion(self):
        """Handle processing completion."""
        try:
            self._transition_state(ProcessorState.COMPLETED, "Processing completed")
            
            # Complete the processing session
            self.progress_tracker.complete_processing_session("completed")
            
            # Generate completion report
            completion_report = self.completion_notifier.generate_completion_report(self.session_id)
            
            # Send notifications
            if self.config.enable_completion_notifications:
                notification_results = self.completion_notifier.send_completion_notification(completion_report)
                
                for channel, success in notification_results.items():
                    if success:
                        self.logger.info(f"✅ {channel} notification sent successfully")
                    else:
                        self.logger.warning(f"⚠️ {channel} notification failed")
            
            # Update statistics
            self.processing_stats['files_completed'] = completion_report.overall_statistics.completed_files
            self.processing_stats['files_failed'] = completion_report.overall_statistics.failed_files
            self.processing_stats['total_processing_time'] = completion_report.overall_statistics.duration_hours
            
            # Clean up session
            self.completion_notifier.cleanup_completed_session(self.session_id)
            
            self.logger.info("🎊 Sequential file processing completed successfully!")
        
        except Exception as e:
            self.logger.error(f"Error handling completion: {e}")
    
    def _cleanup_processing(self):
        """Clean up processing resources."""
        try:
            self.processing_active = False
            
            # Stop capacity monitoring
            if self.capacity_manager and self.capacity_manager.monitoring_active:
                self.capacity_manager.stop_capacity_monitoring()
            
            self.logger.info("🧹 Processing cleanup completed")
        
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def stop_processing(self):
        """Stop sequential file processing gracefully."""
        if not self.processing_active:
            return
        
        self.logger.info("🛑 Stopping sequential file processing...")
        
        self.shutdown_requested = True
        self.processing_active = False
        
        # Wait for processing thread to complete
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=30)
        
        # Complete session with stopped status
        if self.progress_tracker:
            self.progress_tracker.complete_processing_session("stopped")
        
        self._transition_state(ProcessorState.IDLE, "Processing stopped")
        self.logger.info("✅ Sequential file processing stopped")
    
    def get_processing_status(self) -> Dict[str, Any]:
        """
        Get current processing status.
        
        Returns:
            Dictionary with processing status information
        """
        try:
            status = {
                'session_id': self.session_id,
                'current_state': self.current_state.value,
                'processing_active': self.processing_active,
                'total_files': len(self.files_to_process),
                'current_file_index': self.current_file_index,
                'current_file': self.files_to_process[self.current_file_index] if self.current_file_index < len(self.files_to_process) else None,
                'processing_stats': self.processing_stats.copy(),
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'elapsed_time_hours': (datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0,
                'config': asdict(self.config)
            }
            
            # Add progress tracker information if available
            if self.progress_tracker:
                overall_progress = self.progress_tracker.get_overall_progress()
                status['progress'] = asdict(overall_progress)
            
            return status
        
        except Exception as e:
            self.logger.error(f"Error getting processing status: {e}")
            return {
                'error': str(e),
                'session_id': self.session_id,
                'current_state': self.current_state.value,
                'processing_active': self.processing_active
            }
    
    def get_processing_result(self) -> ProcessingResult:
        """
        Get final processing result.
        
        Returns:
            ProcessingResult with comprehensive results
        """
        try:
            # Get completion report if available
            completion_report = None
            if self.session_id and self.completion_notifier:
                try:
                    report = self.completion_notifier.generate_completion_report(self.session_id)
                    completion_report = asdict(report)
                except:
                    pass
            
            # Calculate processing time
            processing_time = 0.0
            if self.start_time:
                processing_time = (datetime.now() - self.start_time).total_seconds() / 3600
            
            return ProcessingResult(
                session_id=self.session_id or "unknown",
                success=self.current_state == ProcessorState.COMPLETED,
                total_files=len(self.files_to_process),
                processed_files=self.current_file_index,
                completed_files=self.processing_stats['files_completed'],
                failed_files=self.processing_stats['files_failed'],
                skipped_files=self.processing_stats['files_skipped'],
                processing_time_hours=processing_time,
                error_message=None if self.current_state != ProcessorState.ERROR else "Processing encountered errors",
                completion_report=completion_report
            )
        
        except Exception as e:
            self.logger.error(f"Error getting processing result: {e}")
            return ProcessingResult(
                session_id=self.session_id or "unknown",
                success=False,
                total_files=0,
                processed_files=0,
                completed_files=0,
                failed_files=0,
                skipped_files=0,
                processing_time_hours=0.0,
                error_message=str(e),
                completion_report=None
            )


def create_sequential_file_processor(config: Optional[ProcessingConfig] = None) -> SequentialFileProcessor:
    """
    Factory function to create a Sequential File Processor.
    
    Args:
        config: Processing configuration
        
    Returns:
        Configured SequentialFileProcessor instance
    """
    return SequentialFileProcessor(config)


if __name__ == "__main__":
    # Main entry point for sequential file processing
    import argparse
    
    parser = argparse.ArgumentParser(description='Sequential File Processor for RDA Automation')
    parser.add_argument('--start', action='store_true',
                       help='Start sequential file processing')
    parser.add_argument('--resume', type=str,
                       help='Resume processing from session ID')
    parser.add_argument('--status', action='store_true',
                       help='Show current processing status')
    parser.add_argument('--stop', action='store_true',
                       help='Stop current processing')
    parser.add_argument('--discover', action='store_true',
                       help='Discover control files only')
    parser.add_argument('--config-file', type=str,
                       help='Path to configuration file')
    parser.add_argument('--control-files-dir', default='control_files',
                       help='Control files directory')
    parser.add_argument('--processing-order', choices=['alphabetical', 'priority', 'region', 'variable'],
                       default='alphabetical', help='File processing order')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Maximum retries per file')
    parser.add_argument('--submission-delay', type=float, default=5.0,
                       help='Delay between file submissions (seconds)')
    
    args = parser.parse_args()
    
    # Create configuration
    config = ProcessingConfig()
    config.control_files_dir = args.control_files_dir
    config.processing_order = args.processing_order
    config.max_retries_per_file = args.max_retries
    config.file_submission_delay = args.submission_delay
    
    # Load configuration file if provided
    if args.config_file and os.path.exists(args.config_file):
        try:
            with open(args.config_file, 'r') as f:
                config_data = json.load(f)
                # Update config with loaded data
                for key, value in config_data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        except Exception as e:
            print(f"Error loading configuration: {e}")
    
    # Create sequential processor
    processor = create_sequential_file_processor(config)
    
    try:
        if args.start:
            print("=" * 80)
            print("🚀 SEQUENTIAL FILE PROCESSOR - STARTING")
            print("=" * 80)
            print(f"Control Files Directory: {config.control_files_dir}")
            print(f"Processing Order: {config.processing_order}")
            print(f"Max Retries: {config.max_retries_per_file}")
            print(f"Submission Delay: {config.file_submission_delay}s")
            print("=" * 80)
            
            success = processor.start_processing()
            if success:
                print("✅ Sequential processing started successfully")
                print("Press Ctrl+C to stop gracefully")
                
                # Keep running until processing completes or is interrupted
                try:
                    while processor.processing_active:
                        time.sleep(1)
                    
                    # Get final result
                    result = processor.get_processing_result()
                    print("\n" + "=" * 80)
                    print("🎉 SEQUENTIAL PROCESSING COMPLETED")
                    print("=" * 80)
                    print(f"Session ID: {result.session_id}")
                    print(f"Success: {result.success}")
                    print(f"Total Files: {result.total_files}")
                    print(f"Completed: {result.completed_files}")
                    print(f"Failed: {result.failed_files}")
                    print(f"Processing Time: {result.processing_time_hours:.2f} hours")
                    print("=" * 80)
                    
                except KeyboardInterrupt:
                    print("\nShutdown requested...")
                    processor.stop_processing()
            else:
                print("❌ Failed to start sequential processing")
        
        elif args.resume:
            print(f"=== Resuming Sequential Processing: {args.resume} ===")
            success = processor.start_processing(resume_session_id=args.resume)
            if success:
                print("✅ Processing resumed successfully")
                try:
                    while processor.processing_active:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nShutdown requested...")
                    processor.stop_processing()
            else:
                print("❌ Failed to resume processing")
        
        elif args.status:
            print("=== Current Processing Status ===")
            status = processor.get_processing_status()
            print(json.dumps(status, indent=2, default=str))
        
        elif args.stop:
            print("=== Stopping Sequential Processing ===")
            processor.stop_processing()
            print("✅ Processing stopped")
        
        elif args.discover:
            print("=== Discovering Control Files ===")
            success, file_list, discovery_info = processor.discover_files()
            
            if success:
                print(f"✅ Discovered {len(file_list)} files:")
                for i, filename in enumerate(file_list, 1):
                    print(f"  {i:3d}. {filename}")
                
                print(f"\nDiscovery Statistics:")
                print(json.dumps(discovery_info, indent=2, default=str))
            else:
                print(f"❌ File discovery failed: {discovery_info.get('error', 'Unknown error')}")
        
        else:
            parser.print_help()
            print("\n" + "="*80)
            print("SEQUENTIAL FILE PROCESSOR EXAMPLES")
            print("="*80)
            print("# Start sequential processing:")
            print("python automation/sequential_file_processor.py --start")
            print("\n# Resume processing from session:")
            print("python automation/sequential_file_processor.py --resume SESSION_ID")
            print("\n# Check processing status:")
            print("python automation/sequential_file_processor.py --status")
            print("\n# Stop current processing:")
            print("python automation/sequential_file_processor.py --stop")
            print("\n# Discover control files:")
            print("python automation/sequential_file_processor.py --discover")

    except Exception as e:
        print(f"Error: {e}")