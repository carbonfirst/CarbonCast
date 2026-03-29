#!/usr/bin/env python3
"""
Integrated Batch Automation System - Main Entry Point

This is the main entry point that integrates all components of the batch automation
system: core automation, intelligent queuing, monitoring, and web dashboard.

Usage:
    python batch_automation_integrated.py --process-all-control-files
    python batch_automation_integrated.py --resume
    python batch_automation_integrated.py --monitor-dashboard
    python batch_automation_integrated.py --status
"""

import os
import sys
import json
import time
import logging
import argparse
import threading
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import signal

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logger_utils import get_logger

from batch_automation import BatchAutomationSystem
from batch_queue_manager import IntelligentQueueManager
from batch_monitor import BatchMonitor
from automation.status_monitor import StatusMonitor, create_status_monitor
from automation.comprehensive_tracker import ComprehensiveTracker, create_comprehensive_tracker
from automation.completed_request_integration import CompletedRequestIntegration, create_completed_request_integration
from automation.enhanced_monitoring_integration import EnhancedMonitoringIntegration, create_enhanced_monitoring_integration
from automation.dynamic_trigger_system import DynamicTriggerSystem, create_dynamic_trigger_system
from automation.batch_optimizer import BatchOptimizer, create_batch_optimizer
from automation.capacity_manager import CapacityManager, create_capacity_manager
from directory_utils import setup_directories

# Import upload_files functionality for auto-upload integration
try:
    import upload_files
    UPLOAD_FILES_AVAILABLE = True
except ImportError:
    UPLOAD_FILES_AVAILABLE = False


class IntegratedBatchSystem:
    """Integrated batch automation system with all components."""
    
    def __init__(self, config_file: str = "automation_config.json"):
        """Initialize the integrated system."""
        self.config_file = config_file
        self.logger = self._setup_logging()
        
        # Ensure all required directories exist before initializing components
        self.logger.info("Setting up required directories...")
        try:
            setup_success = setup_directories(logger=self.logger)
            if setup_success:
                self.logger.info("✅ All required directories are ready")
            else:
                self.logger.warning("⚠️ Some directory setup issues occurred")
        except Exception as e:
            self.logger.error(f"Directory setup error: {e}")
            # Continue initialization even if directory setup has issues
        
        # Initialize core components
        self.batch_system = BatchAutomationSystem(config_file)
        self.queue_manager = IntelligentQueueManager(self.batch_system)
        self.monitor = BatchMonitor(self.batch_system, self.queue_manager)
        
        # Access config from batch_system after it's initialized
        self.config = self.batch_system.config
        
        # Initialize status monitor for automatic error detection and retry
        db_path = "src/python/data/automation_state.db"
        self.status_monitor = create_status_monitor(
            db_path=db_path,
            batch_system=self.batch_system,
            queue_manager=self.queue_manager,
            check_interval_seconds=self.config.get('automation', {}).get('status_check_interval_seconds', 180)
        )
        
        # Initialize comprehensive tracker for complete coverage monitoring
        self.comprehensive_tracker = create_comprehensive_tracker(
            control_files_dir=self.config.get('directories', {}).get('control_files_dir', './control_files'),
            db_path=db_path,
            config=self.config
        )
        
        # Initialize completed request integration for automatic download of completed requests
        scan_interval_minutes = self.config.get('automation', {}).get('completed_request_scan_interval_minutes', 5)
        self.completed_request_integration = create_completed_request_integration(
            db_path=db_path,
            scan_interval_minutes=scan_interval_minutes
        )
        
        # Initialize enhanced monitoring integration with dynamic triggering
        self.enhanced_monitoring_integration = None
        self.dynamic_trigger_system = None
        self.batch_optimizer = None
        self.capacity_manager_enhanced = None
        
        # Check if dynamic batch processing is enabled
        dynamic_enabled = self.config.get('automation', {}).get('dynamic_batch_processing_enabled', True)
        if dynamic_enabled:
            self.logger.info("🚀 Initializing dynamic batch processing components...")
            self._initialize_dynamic_components(db_path)
        
        # System state
        self.running = False
        self.web_dashboard_thread = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Integrated Batch Automation System initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('integrated_batch_system', level=logging.INFO)
    
    def _initialize_dynamic_components(self, db_path: str):
        """Initialize dynamic batch processing components."""
        try:
            # Create enhanced capacity manager
            from automation.capacity_manager import CapacityConfig
            capacity_config = CapacityConfig(
                enable_upload_automation=self.config.get('automation', {}).get('auto_upload_enabled', True),
                upload_batch_size=self.config.get('automation', {}).get('max_upload_batch_size', 10),
                upload_rate_limit_delay=self.config.get('upload', {}).get('rate_limit_delay', 0.5),
                control_files_dir=self.config.get('directories', {}).get('control_files_dir', './control_files')
            )
            self.capacity_manager_enhanced = create_capacity_manager(config=capacity_config, db_path=db_path)
            
            # Create enhanced monitoring integration
            self.enhanced_monitoring_integration = create_enhanced_monitoring_integration()
            
            # Connect components to enhanced monitoring
            self.enhanced_monitoring_integration.connect_batch_system(self.batch_system)
            self.enhanced_monitoring_integration.connect_capacity_manager(self.capacity_manager_enhanced)
            self.enhanced_monitoring_integration.connect_status_monitor(self.status_monitor)
            self.enhanced_monitoring_integration.connect_queue_manager(self.queue_manager)
            
            # Create dynamic trigger system
            self.dynamic_trigger_system = create_dynamic_trigger_system(
                enhanced_monitor=self.enhanced_monitoring_integration.enhanced_monitor,
                capacity_manager=self.capacity_manager_enhanced,
                event_dispatcher=self.enhanced_monitoring_integration.event_dispatcher
            )
            
            # Set integration components for dynamic trigger system
            self.dynamic_trigger_system.set_integration_components(
                batch_system=self.batch_system,
                queue_manager=self.queue_manager
            )
            
            # Create batch optimizer
            from automation.batch_optimizer import OptimizationConfig
            optimizer_config = OptimizationConfig(
                target_utilization=0.9,  # Target 90% of 10-request capacity
                optimization_interval=self.config.get('automation', {}).get('check_interval_seconds', 60),
                learning_enabled=True
            )
            self.batch_optimizer = create_batch_optimizer(
                config=optimizer_config,
                capacity_manager=self.capacity_manager_enhanced,
                enhanced_monitor=self.enhanced_monitoring_integration.enhanced_monitor,
                dynamic_trigger=self.dynamic_trigger_system
            )
            
            # Set integration components for batch optimizer
            self.batch_optimizer.set_integration_components(
                batch_system=self.batch_system,
                queue_manager=self.queue_manager
            )
            
            # Add processing callbacks
            self.dynamic_trigger_system.add_processing_callback(self._handle_dynamic_trigger_callback)
            
            self.logger.info("✅ Dynamic batch processing components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize dynamic components: {e}")
            # Continue without dynamic components
            self.enhanced_monitoring_integration = None
            self.dynamic_trigger_system = None
            self.batch_optimizer = None
            self.capacity_manager_enhanced = None
    
    def _handle_dynamic_trigger_callback(self, trigger_event, success: bool):
        """Handle callbacks from dynamic trigger system."""
        try:
            batch_size = trigger_event.batch_calculation.recommended_batch_size
            trigger_type = trigger_event.trigger_type.value
            
            if success:
                self.logger.info(f"✅ Dynamic trigger executed successfully: {trigger_type} "
                               f"(batch size: {batch_size})")
                
                # Record performance for batch optimizer
                if self.batch_optimizer and batch_size > 0:
                    # Estimate processing time and success rate (simplified)
                    processing_time = batch_size * 2.0  # rough estimate
                    success_rate = 0.9  # assume high success rate for successful triggers
                    
                    self.batch_optimizer.record_performance(
                        batch_size=batch_size,
                        processing_time=processing_time,
                        success_rate=success_rate,
                        strategy=trigger_event.batch_calculation.calculation_strategy
                    )
            else:
                self.logger.warning(f"⚠️ Dynamic trigger failed: {trigger_type} "
                                  f"(batch size: {batch_size})")
                
                # Record failure for batch optimizer
                if self.batch_optimizer and batch_size > 0:
                    self.batch_optimizer.record_performance(
                        batch_size=batch_size,
                        processing_time=0.0,
                        success_rate=0.0,
                        strategy=trigger_event.batch_calculation.calculation_strategy
                    )
            
        except Exception as e:
            self.logger.error(f"❌ Error in dynamic trigger callback: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown()
        sys.exit(0)
    
    def process_all_control_files(self):
        """Process all control files with integrated system."""
        self.logger.info("Starting integrated batch processing of all control files...")
        
        try:
            # Discover control files (only if not resuming)
            if not hasattr(self, '_resuming_from_state'):
                # Use comprehensive tracker for complete control file discovery
                self.logger.info("🔍 Discovering control files with comprehensive tracker...")
                discovered_files = self.comprehensive_tracker.discover_all_control_files(force_rescan=True)
                
                if not discovered_files:
                    self.logger.error("No control files found")
                    return
                
                control_files = list(discovered_files.keys())
                self.logger.info(f"Found {len(control_files)} control files across {len(set(cf.region for cf in discovered_files.values()))} regions")
                
                # Generate initial coverage report
                coverage_report = self.comprehensive_tracker.generate_comprehensive_coverage_report()
                self.logger.info(f"📊 Initial coverage: {coverage_report.coverage_percentage:.1f}% ({len(coverage_report.alerts)} alerts)")
                
                # Initialize batch system
                self.batch_system.initialize_requests(control_files)
                
                # Add to intelligent queue
                self.queue_manager.add_to_queue(control_files)
            else:
                self.logger.info("Resuming from saved state - skipping discovery and initialization")
                # Sync comprehensive tracker with existing batch system state
                self._sync_comprehensive_tracker_with_batch_system()
            
            # Start monitoring
            self.monitor.start_monitoring(update_interval=60)
            
            # Start automatic status monitoring for error detection and retry
            self.status_monitor.start_monitoring()
            
            # Start completed request integration
            self.completed_request_integration.start_integration()
            
            # Start enhanced monitoring and dynamic trigger system if available
            if self.enhanced_monitoring_integration:
                self.logger.info("🚀 Starting enhanced monitoring integration...")
                self.enhanced_monitoring_integration.start_integration()
                
                if self.dynamic_trigger_system:
                    self.logger.info("🎯 Starting dynamic trigger system...")
                    self.dynamic_trigger_system.start_system()
                
                if self.batch_optimizer:
                    self.logger.info("📊 Starting batch optimizer monitoring...")
                    self.batch_optimizer.start_optimization_monitoring()
                
                if self.capacity_manager_enhanced:
                    self.logger.info("⚡ Starting enhanced capacity monitoring...")
                    self.capacity_manager_enhanced.start_capacity_monitoring()
            
            # Start web dashboard in background - ALWAYS for all automation commands
            self._start_web_dashboard_background()
            
            # Main processing loop with intelligent queuing - AGGRESSIVE 10-REQUEST TARGETING
            self.running = True
            # AGGRESSIVE: Reduced check interval from 300 to 60 seconds for faster response
            check_interval = min(self.batch_system.config['automation']['check_interval_seconds'], 60)
            
            while self.running:
                self.logger.info("=== AGGRESSIVE Processing Cycle Started ===")
                
                # Check current request count and automatically upload files if slots available
                current_request_count = self.batch_system._get_current_request_count()
                self.logger.info(f"🎯 AGGRESSIVE TARGET: {current_request_count}/10 requests active")
                
                # AGGRESSIVE INTEGRATION: Always try to maintain exactly 10 requests
                if current_request_count < 10:
                    available_slots = 10 - current_request_count
                    self.logger.info(f"🚀 AGGRESSIVE UPLOAD: {available_slots} slots available - IMMEDIATELY filling to reach 10 requests")
                    
                    # Call upload_files.py functionality to submit new requests AGGRESSIVELY
                    self._auto_upload_new_files(available_slots)
                elif current_request_count == 10:
                    self.logger.info(f"🎯 PERFECT: Exactly 10 requests active - maintaining target")
                else:
                    self.logger.warning(f"⚠️ OVER CAPACITY: {current_request_count} requests active - this should not happen")
                
                # Get next requests from intelligent queue
                next_requests = self.queue_manager.get_next_requests()
                
                if next_requests:
                    self.logger.info(f"Processing {len(next_requests)} requests from queue")
                    
                    # Submit requests
                    for queued_request in next_requests:
                        if not self.running:
                            break
                        
                        success = self.batch_system.submit_request(queued_request.control_file)
                        if not success:
                            self.queue_manager.mark_request_completed(queued_request.control_file, success=False)
                        
                        # Rate limiting
                        time.sleep(2)
                
                # Monitor active requests
                self.batch_system.monitor_active_requests()
                
                # Sync comprehensive tracker with batch system status
                self._sync_comprehensive_tracker_with_batch_system()
                
                # Run automatic error detection and retry cycle
                self._run_error_detection_and_retry_cycle()
                
                # Run completed request integration cycle to download completed requests
                self._run_completed_request_integration_cycle()
                
                # Update queue with completed/failed requests
                self._sync_queue_with_batch_system()
                
                # Retry failed requests through queue manager
                self.queue_manager.requeue_failed_requests()
                
                # Optimize queue order
                self.queue_manager.optimize_queue_order()
                
                # Save states
                self.batch_system._save_state()
                self.queue_manager._save_queue_state()
                
                # Print comprehensive status
                self._print_integrated_status()
                
                # Check if all requests are complete
                if self._all_requests_complete():
                    self.logger.info("🎉 All requests processed successfully!")
                    break
                
                # AGGRESSIVE: Reduced wait time for faster response
                aggressive_interval = min(check_interval, 60)  # Never wait more than 60 seconds
                self.logger.info(f"⚡ AGGRESSIVE: Waiting {aggressive_interval} seconds before next cycle (reduced for 10-request targeting)...")
                time.sleep(aggressive_interval)
        
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            self.logger.error(f"Error in integrated processing: {e}")
        finally:
            self.shutdown()
    
    def _auto_upload_new_files(self, available_slots: int):
        """
        AGGRESSIVELY upload new files when request slots are available.
        
        This implements AGGRESSIVE integration to call upload_files.py functionality
        to maintain exactly 10 active requests at all times.
        
        Args:
            available_slots: Number of available request slots (10 - current_request_count)
        """
        try:
            # Check if auto-upload is enabled in configuration
            auto_upload_enabled = self.config.get('automation', {}).get('auto_upload_enabled', True)
            if not auto_upload_enabled:
                self.logger.debug("Auto-upload is disabled in configuration")
                return
            
            # Check if upload_files module is available
            if not UPLOAD_FILES_AVAILABLE:
                self.logger.error("❌ upload_files module not available for auto-upload functionality")
                return
            
            self.logger.info(f"🔍 AGGRESSIVE Auto-upload: Checking for new control files to submit ({available_slots} slots available)")
            
            # Discover available control files using upload_files functionality
            control_files_dir = self.config.get('directories', {}).get('control_files_dir', './control_files')
            
            # Use the incoming directory as the primary source for new files
            incoming_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "incoming")
            if os.path.exists(incoming_dir):
                control_files_dir = incoming_dir
                self.logger.info(f"📂 Using incoming directory for auto-upload: {control_files_dir}")
            
            discovered_files = upload_files.discover_control_files(control_files_dir)
            
            if not discovered_files:
                self.logger.info("📂 No new control files found for auto-upload")
                return
            
            # Filter out files that are already being processed
            new_files = []
            for file_path in discovered_files:
                if file_path not in self.batch_system.requests_state:
                    new_files.append(file_path)
                else:
                    # Check if the file failed and can be retried
                    status = self.batch_system.requests_state[file_path].status
                    if status in ["failed", "pending"]:
                        new_files.append(file_path)
                        self.logger.info(f"🔄 Including failed/pending file for retry: {file_path}")
            
            if not new_files:
                self.logger.info("📋 All discovered control files are already in processing queue")
                return
            
            # AGGRESSIVE: Try to fill ALL available slots to reach exactly 10 requests
            files_to_submit = new_files[:available_slots]
            
            self.logger.info(f"🚀 AGGRESSIVE Auto-upload: Found {len(new_files)} new files, submitting {len(files_to_submit)} to reach 10-request target")
            
            # Get configuration for upload_files - AGGRESSIVE SETTINGS
            dest_file = self.config.get('upload', {}).get('dest_file', './ds0841.1_control.ctl')
            rate_limit_delay = min(self.config.get('upload', {}).get('rate_limit_delay', 2.0), 1.0)  # Reduced delay for aggressive uploading
            
            # Submit the batch of files using upload_files functionality
            self.logger.info(f"📤 Submitting {len(files_to_submit)} files via upload_files.py integration...")
            
            results = upload_files.submit_batch_files(
                file_paths=files_to_submit,
                dest_file=dest_file,
                rate_limit_delay=rate_limit_delay,
                logger=self.logger
            )
            
            # Process results and update batch system state
            if results.get('success', False):
                submitted_files = results.get('submitted_files', [])
                failed_files = results.get('failed_files', [])
                request_ids = results.get('request_ids', [])
                
                self.logger.info(f"✅ Auto-upload completed: {len(submitted_files)} submitted, {len(failed_files)} failed")
                self.logger.info(f"📋 Request IDs generated: {request_ids}")
                
                # Add successfully submitted files to batch system and queue
                if submitted_files:
                    # Initialize these files in the batch system
                    self.batch_system.initialize_requests(submitted_files)
                    
                    # Update request status with submission details
                    for i, file_path in enumerate(submitted_files):
                        if i < len(request_ids) and request_ids[i]:
                            # Use proper context manager handling for status_lock
                            if hasattr(self.batch_system.status_lock, '__enter__'):
                                with self.batch_system.status_lock:
                                    if file_path in self.batch_system.requests_state:
                                        request_status = self.batch_system.requests_state[file_path]
                                        request_status.request_id = str(request_ids[i])
                                        request_status.status = "submitted"
                                        request_status.submission_time = datetime.now().isoformat()
                            else:
                                # Fallback for mock objects or non-context manager locks
                                if file_path in self.batch_system.requests_state:
                                    request_status = self.batch_system.requests_state[file_path]
                                    request_status.request_id = str(request_ids[i])
                                    request_status.status = "submitted"
                                    request_status.submission_time = datetime.now().isoformat()
                    
                    # Add to intelligent queue for monitoring
                    self.queue_manager.add_to_queue(submitted_files)
                    
                    self.logger.info(f"📋 Added {len(submitted_files)} auto-uploaded files to monitoring queue")
                
                # Log any failures with detailed error information
                if failed_files:
                    self.logger.warning(f"⚠️ Auto-upload failures: {len(failed_files)} files failed to submit")
                    for error in results.get('errors', [])[:5]:  # Show first 5 errors
                        self.logger.warning(f"   - {error}")
                    
                    # Mark failed files in batch system
                    for file_path in failed_files:
                        if file_path in self.batch_system.requests_state:
                            # Use proper context manager handling for status_lock
                            if hasattr(self.batch_system.status_lock, '__enter__'):
                                with self.batch_system.status_lock:
                                    request_status = self.batch_system.requests_state[file_path]
                                    request_status.status = "failed"
                                    request_status.error_message = "Auto-upload submission failed"
                            else:
                                # Fallback for mock objects or non-context manager locks
                                request_status = self.batch_system.requests_state[file_path]
                                request_status.status = "failed"
                                request_status.error_message = "Auto-upload submission failed"
            else:
                self.logger.error("❌ Auto-upload batch submission failed completely")
                
                # Mark all files as failed
                for file_path in files_to_submit:
                    if file_path not in self.batch_system.requests_state:
                        self.batch_system.initialize_requests([file_path])
                    
                    # Use proper context manager handling for status_lock
                    if hasattr(self.batch_system.status_lock, '__enter__'):
                        with self.batch_system.status_lock:
                            request_status = self.batch_system.requests_state[file_path]
                            request_status.status = "failed"
                            request_status.error_message = "Auto-upload batch submission failed"
                    else:
                        # Fallback for mock objects or non-context manager locks
                        request_status = self.batch_system.requests_state[file_path]
                        request_status.status = "failed"
                        request_status.error_message = "Auto-upload batch submission failed"
                
        except Exception as e:
            self.logger.error(f"❌ Critical error in auto-upload functionality: {e}")
            import traceback
            self.logger.error(f"Auto-upload traceback: {traceback.format_exc()}")
            
            # Ensure system continues running despite auto-upload errors
            self.logger.info("🔄 Continuing with normal processing despite auto-upload error")
    
    def _start_web_dashboard_background(self):
        """Start web dashboard in background thread with enhanced user feedback."""
        import webbrowser
        import time
        import socket
        
        def run_dashboard():
            try:
                # Import the enhanced dashboard
                from automation.dashboard import create_dashboard
                
                # Get the correct path to the database file
                current_dir = os.path.dirname(os.path.abspath(__file__))
                db_path = "src/python/data/automation_state.db"
                
                # Create enhanced dashboard instance
                dashboard = create_dashboard(db_path)
                
                # Ensure templates are created before starting server
                dashboard.create_dashboard_template()
                
                self.logger.info("Dashboard instance created, starting Flask server...")
                
                # Start dashboard on port 5001 with proper error handling
                dashboard.start_dashboard(host='0.0.0.0', port=5001, debug=False)
            except Exception as e:
                self.logger.error(f"Error running web dashboard: {e}")
                import traceback
                self.logger.error(f"Dashboard traceback: {traceback.format_exc()}")
        
        def wait_for_dashboard_ready():
            """Wait for dashboard to be ready before opening browser."""
            max_attempts = 30  # Wait up to 30 seconds
            for attempt in range(max_attempts):
                try:
                    # Test if dashboard is responding
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex(('localhost', 5001))
                    sock.close()
                    
                    if result == 0:  # Connection successful
                        self.logger.info("Dashboard is ready, opening browser...")
                        try:
                            dashboard_url = "http://localhost:5001"
                            webbrowser.open(dashboard_url)
                            self.logger.info(f"🌐 Dashboard opened in browser: {dashboard_url}")
                        except Exception as e:
                            self.logger.warning(f"Could not automatically open browser: {e}")
                        return
                except:
                    pass
                
                time.sleep(1)  # Wait 1 second before next attempt
            
            self.logger.warning("Dashboard did not become ready within 30 seconds")
        
        # Start dashboard in background thread (non-daemon to ensure it stays alive)
        self.web_dashboard_thread = threading.Thread(target=run_dashboard, daemon=False)
        self.web_dashboard_thread.start()
        
        # Wait a moment for thread to start
        time.sleep(1)
        
        # Start browser opening thread
        browser_thread = threading.Thread(target=wait_for_dashboard_ready, daemon=True)
        browser_thread.start()
        
        # Enhanced user feedback
        print("\n" + "="*80)
        print("🌦️  ENHANCED RDA AUTOMATION DASHBOARD STARTING")
        print("="*80)
        print(f"📊 Dashboard URL: http://localhost:5001")
        print(f"🌐 Browser will open automatically when dashboard is ready...")
        print(f"📈 Features available:")
        print(f"   • Real-time request monitoring")
        print(f"   • Regional performance metrics")
        print(f"   • Weather variable analysis")
        print(f"   • Error and retry statistics")
        print(f"   • Interactive filtering and charts")
        print("="*80)
        print()
        
        self.logger.info("Enhanced web dashboard thread started, waiting for server to be ready...")
    
    def _run_error_detection_and_retry_cycle(self):
        """Run automatic error detection and retry cycle."""
        try:
            self.logger.debug("Running error detection and retry cycle")
            
            # Run a single monitoring cycle to check for errors and handle retries
            cycle_result = self.status_monitor.run_single_monitoring_cycle()
            
            if cycle_result.get('cycle_completed', False):
                processing_stats = cycle_result.get('processing_stats', {})
                
                if processing_stats.get('errors_detected', 0) > 0 or processing_stats.get('purged_confirmed', 0) > 0:
                    self.logger.info(f"Error detection cycle: {processing_stats.get('errors_detected', 0)} errors detected, "
                                   f"{processing_stats.get('purged_confirmed', 0)} purged confirmed, "
                                   f"{processing_stats.get('retries_scheduled', 0)} retries scheduled")
                
                # If retries were scheduled, we may need to add them back to the queue
                if processing_stats.get('retries_scheduled', 0) > 0:
                    self._sync_retries_with_queue()
            
        except Exception as e:
            self.logger.error(f"Error in error detection and retry cycle: {e}")
    
    def _run_completed_request_integration_cycle(self):
        """
        Run completed request integration cycle to automatically download completed requests.
        
        This addresses the critical integration gap where completed requests that exist in the
        database are not being automatically downloaded because there's no component monitoring
        the database for completed requests that were submitted outside the current batch workflow.
        """
        try:
            self.logger.debug("Running completed request integration cycle")
            
            # Run integration cycle to check for and download completed requests
            cycle_result = self.completed_request_integration.run_integration_cycle()
            
            if cycle_result.get('cycle_completed', False):
                if cycle_result.get('scan_performed', False):
                    download_results = cycle_result.get('download_results', {})
                    successful_downloads = download_results.get('successful_downloads', 0)
                    failed_downloads = download_results.get('failed_downloads', 0)
                    
                    if successful_downloads > 0:
                        self.logger.info(f"🔄 Completed Request Integration: Successfully downloaded {successful_downloads} completed requests")
                        
                        # Log details about what was downloaded
                        scan_results = cycle_result.get('scan_results', {})
                        total_found = scan_results.get('total_completed_found', 0)
                        self.logger.info(f"📊 Found {total_found} completed requests in database, downloaded {successful_downloads}")
                    
                    if failed_downloads > 0:
                        self.logger.warning(f"⚠️ Completed Request Integration: {failed_downloads} downloads failed")
                else:
                    # Not time for scan yet
                    next_scan_minutes = cycle_result.get('next_scan_in_minutes', 0)
                    if next_scan_minutes > 0:
                        self.logger.debug(f"Next completed request scan in {next_scan_minutes:.1f} minutes")
            else:
                # Cycle failed
                error = cycle_result.get('error', 'Unknown error')
                self.logger.error(f"❌ Completed request integration cycle failed: {error}")
            
        except Exception as e:
            self.logger.error(f"❌ Error in completed request integration cycle: {e}")
            import traceback
            self.logger.error(f"Completed request integration traceback: {traceback.format_exc()}")
            
            # Ensure system continues running despite integration errors
            self.logger.info("🔄 Continuing with normal processing despite completed request integration error")
    
    def _sync_retries_with_queue(self):
        """Sync retry attempts with the queue manager."""
        try:
            # Get retry statistics to see if there are ready retries
            retry_stats = self.status_monitor.retry_manager.get_retry_statistics()
            
            # Check for ready retries that should be added to the queue
            ready_retries = self.status_monitor.retry_manager.get_ready_retries()
            
            if ready_retries:
                self.logger.info(f"Adding {len(ready_retries)} ready retries to queue")
                
                # Add retry control files back to the queue with high priority
                retry_control_files = [retry.file_path for retry in ready_retries]
                
                # Update batch system to mark these as pending for resubmission
                for control_file in retry_control_files:
                    if control_file in self.batch_system.requests_state:
                        # Use proper context manager handling for status_lock
                        if hasattr(self.batch_system.status_lock, '__enter__'):
                            with self.batch_system.status_lock:
                                request_status = self.batch_system.requests_state[control_file]
                                request_status.status = "pending"
                                request_status.request_id = None  # Clear old request ID
                                request_status.error_message = None
                        else:
                            # Fallback for mock objects or non-context manager locks
                            request_status = self.batch_system.requests_state[control_file]
                            request_status.status = "pending"
                            request_status.request_id = None  # Clear old request ID
                            request_status.error_message = None
                
                # Add to queue manager
                self.queue_manager.add_to_queue(retry_control_files)
                
                self.logger.info(f"Successfully added {len(retry_control_files)} retry requests to queue")
                
        except Exception as e:
            self.logger.error(f"Error syncing retries with queue: {e}")
    
    def _sync_comprehensive_tracker_with_batch_system(self):
        """Sync comprehensive tracker with batch system status."""
        try:
            self.logger.debug("Syncing comprehensive tracker with batch system...")
            
            # Sync all control files from batch system to comprehensive tracker
            for control_file, request_status in self.batch_system.requests_state.items():
                # Update comprehensive tracker with current status
                updates = {
                    'request_id': request_status.request_id,
                    'submission_time': request_status.submission_time,
                    'completion_time': request_status.completion_time,
                    'download_time': request_status.download_time,
                    'error_message': request_status.error_message,
                    'retry_count': request_status.retry_count,
                    'download_directory': request_status.download_directory
                }
                
                # Calculate processing duration if possible
                if request_status.submission_time and request_status.completion_time:
                    try:
                        from datetime import datetime
                        start = datetime.fromisoformat(request_status.submission_time)
                        end = datetime.fromisoformat(request_status.completion_time)
                        duration_hours = (end - start).total_seconds() / 3600
                        updates['processing_duration'] = duration_hours
                    except:
                        pass
                
                # Update comprehensive tracker
                self.comprehensive_tracker.update_control_file_status(
                    control_file, request_status.status, **updates
                )
            
            self.logger.debug("Comprehensive tracker sync completed")
            
        except Exception as e:
            self.logger.error(f"Error syncing comprehensive tracker: {e}")
    
    def _sync_queue_with_batch_system(self):
        """Sync queue manager with batch system status."""
        for control_file, status in self.batch_system.requests_state.items():
            if status.status == "downloaded":
                self.queue_manager.mark_request_completed(control_file, success=True)
            elif status.status == "failed":
                self.queue_manager.mark_request_completed(control_file, success=False)
    
    def _all_requests_complete(self) -> bool:
        """Check if all requests are complete."""
        incomplete_statuses = ["pending", "submitted", "processing", "ready_for_download"]
        
        for status in self.batch_system.requests_state.values():
            if status.status in incomplete_statuses:
                return False
        
        return True
    
    def _print_integrated_status(self):
        """Print comprehensive integrated status."""
        print("\n" + "="*100)
        print("INTEGRATED BATCH AUTOMATION SYSTEM STATUS")
        print("="*100)
        
        # Batch system status
        self.batch_system.print_status_summary()
        
        # Queue manager status
        self.queue_manager.print_queue_status()
        
        # Monitor status
        self.monitor.print_progress_report()
        
        # Comprehensive tracker status
        self._print_comprehensive_tracker_summary()
        
        # Status monitor statistics
        self._print_status_monitor_summary()
        
        # Completed request integration status
        self._print_completed_request_integration_summary()
        
        print("="*100)
    
    def resume_processing(self):
        """Resume processing from saved state."""
        self.logger.info("Resuming integrated batch processing from saved state...")
        
        # Load existing states
        self.batch_system._load_state()
        self.queue_manager._load_queue_state()
        
        # Set flag to indicate we're resuming from state
        self._resuming_from_state = True
        
        # Continue processing (dashboard will be started in process_all_control_files)
        self.process_all_control_files()
    
    def monitor_dashboard_only(self):
        """Run only monitoring and dashboard without processing."""
        import webbrowser
        import time
        import socket
        
        self.logger.info("Starting monitor and dashboard mode...")
        
        try:
            # Import the enhanced dashboard
            from automation.dashboard import create_dashboard
            
            # Get the correct path to the database file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = "src/python/data/automation_state.db"
            
            # Create enhanced dashboard instance
            dashboard = create_dashboard(db_path)
            
            # Ensure templates are created
            dashboard.create_dashboard_template()
            
            # Enhanced user feedback
            print("\n" + "="*80)
            print("🌦️  RDA AUTOMATION DASHBOARD - MONITOR MODE")
            print("="*80)
            print(f"📊 Dashboard URL: http://localhost:5001")
            print(f"🔍 Mode: Monitor Only (no new processing)")
            print(f"📈 Features available:")
            print(f"   • Real-time request monitoring")
            print(f"   • Regional performance metrics")
            print(f"   • Weather variable analysis")
            print(f"   • Error and retry statistics")
            print(f"   • Interactive filtering and charts")
            print("="*80)
            print(f"🌐 Dashboard will open in browser when ready...")
            print(f"⏹️  Press Ctrl+C to stop the dashboard")
            print("="*80)
            print()
            
            # Open browser automatically after dashboard is ready
            def open_browser_when_ready():
                # Wait for dashboard to be ready
                max_attempts = 15  # Wait up to 15 seconds
                for attempt in range(max_attempts):
                    try:
                        # Test if dashboard is responding
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex(('localhost', 5001))
                        sock.close()
                        
                        if result == 0:  # Connection successful
                            try:
                                dashboard_url = "http://localhost:5001"
                                webbrowser.open(dashboard_url)
                                self.logger.info(f"🌐 Dashboard opened in browser: {dashboard_url}")
                            except Exception as e:
                                self.logger.warning(f"Could not automatically open browser: {e}")
                            return
                    except:
                        pass
                    
                    time.sleep(1)  # Wait 1 second before next attempt
                
                self.logger.warning("Dashboard did not become ready within 15 seconds")
            
            browser_thread = threading.Thread(target=open_browser_when_ready, daemon=True)
            browser_thread.start()
            
            # Start monitoring
            self.monitor.start_monitoring(update_interval=30)
            
            # Start web dashboard (blocking) - this will run until interrupted
            self.logger.info("Starting dashboard server...")
            dashboard.start_dashboard(host='0.0.0.0', port=5001, debug=False)
        
        except KeyboardInterrupt:
            print("\n👋 Dashboard stopped by user")
            self.logger.info("Monitor dashboard interrupted")
        except Exception as e:
            print(f"❌ Error running dashboard: {e}")
            self.logger.error(f"Error in monitor dashboard mode: {e}")
            import traceback
            self.logger.error(f"Dashboard traceback: {traceback.format_exc()}")
        finally:
            if hasattr(self.monitor, 'monitoring_active'):
                self.monitor.stop_monitoring()
    
    def show_status(self):
        """Show current status of all components."""
        self.logger.info("Showing current system status...")
        
        # Load current states
        self.batch_system._load_state()
        self.queue_manager._load_queue_state()
        
        # Print integrated status
        self._print_integrated_status()
    
    def _print_status_monitor_summary(self):
        """Print status monitor summary."""
        try:
            stats = self.status_monitor.get_monitoring_statistics()
            
            print("\n" + "-"*60)
            print("STATUS MONITOR & ERROR DETECTION")
            print("-"*60)
            
            print(f"Monitoring Active: {'Yes' if stats.get('monitoring_active', False) else 'No'}")
            
            error_stats = stats.get('error_statistics', {})
            if error_stats:
                print(f"Total Failed Requests: {error_stats.get('total_failed_requests', 0)}")
                print(f"Requests Exceeding Retries: {error_stats.get('requests_exceeding_retries', 0)}")
            
            retry_stats = stats.get('retry_statistics', {})
            if retry_stats and retry_stats.get('metrics'):
                metrics = retry_stats['metrics']
                print(f"Total Retry Attempts: {metrics.get('total_retries_attempted', 0)}")
                print(f"Successful Retries: {metrics.get('total_retries_successful', 0)}")
                print(f"Retry Success Rate: {metrics.get('success_rate', 0):.1%}")
            
            cache_stats = stats.get('cache_statistics', {})
            if cache_stats:
                print(f"Cached Status Checks: {cache_stats.get('cached_requests', 0)}")
                print(f"Purged Requests Tracked: {cache_stats.get('purged_requests_tracked', 0)}")
            
        except Exception as e:
            print(f"Error getting status monitor summary: {e}")
    
    def _print_comprehensive_tracker_summary(self):
        """Print comprehensive tracker summary."""
        try:
            print("\n" + "-"*60)
            print("COMPREHENSIVE COVERAGE TRACKING")
            print("-"*60)
            
            # Get tracking statistics
            stats = self.comprehensive_tracker.get_tracking_statistics()
            
            if "error" not in stats:
                print(f"Total Control Files: {stats['total_control_files']}")
                print(f"Completion Rate: {stats['completion_rate']:.1f}%")
                print(f"Failure Rate: {stats['failure_rate']:.1f}%")
                print(f"Regions Tracked: {stats['regions_tracked']}")
                
                # Show top regions by file count
                regional_dist = stats.get('regional_distribution', {})
                if regional_dist:
                    top_regions = sorted(regional_dist.items(), key=lambda x: x[1], reverse=True)[:5]
                    print(f"Top Regions: {', '.join([f'{r}({c})' for r, c in top_regions])}")
                
                # Show variable distribution
                var_dist = stats.get('variable_distribution', {})
                if var_dist:
                    print(f"Variables: {', '.join([f'{v}({c})' for v, c in var_dist.items()])}")
                
                # Show alerts
                alerts = self.comprehensive_tracker.generate_alerts()
                if alerts:
                    print(f"Active Alerts: {len(alerts)}")
                    for alert in alerts[:3]:  # Show first 3 alerts
                        print(f"  • {alert}")
                    if len(alerts) > 3:
                        print(f"  • ... and {len(alerts) - 3} more alerts")
                else:
                    print("✅ No active alerts")
            else:
                print(f"Error getting tracker statistics: {stats.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"Error getting comprehensive tracker summary: {e}")
    
    def _print_completed_request_integration_summary(self):
        """Print completed request integration summary."""
        try:
            print("\n" + "-"*60)
            print("COMPLETED REQUEST INTEGRATION")
            print("-"*60)
            
            # Get integration status
            status = self.completed_request_integration.get_integration_status()
            
            print(f"Integration Active: {'Yes' if status.get('integration_active', False) else 'No'}")
            print(f"Scan Interval: {status.get('scan_interval_minutes', 0)} minutes")
            print(f"Last Scan: {status.get('last_scan_time', 'Never')}")
            print(f"Total Processed: {status.get('total_requests_processed', 0)} requests")
            print(f"Next Scan Due: {'Yes' if status.get('next_scan_due', False) else 'No'}")
            
            # Get scanner status from the integration
            scanner_status = status.get('scanner_status', {})
            if scanner_status:
                completed_requests = scanner_status.get('completed_requests', {})
                if completed_requests:
                    never_downloaded = completed_requests.get('never_downloaded', 0)
                    already_downloaded = completed_requests.get('already_downloaded', 0)
                    
                    if never_downloaded > 0:
                        print(f"⚠️ Requests Needing Download: {never_downloaded}")
                    else:
                        print("✅ All completed requests have been downloaded")
                    
                    print(f"Total Completed Requests: {completed_requests.get('total_completed', 0)}")
                    print(f"Already Downloaded: {already_downloaded}")
            
        except Exception as e:
            print(f"Error getting completed request integration summary: {e}")
    
    def _print_dynamic_batch_processing_summary(self):
        """Print dynamic batch processing summary."""
        try:
            print("\n" + "-"*60)
            print("DYNAMIC BATCH PROCESSING")
            print("-"*60)
            
            if not self.enhanced_monitoring_integration:
                print("Dynamic batch processing: Disabled")
                return
            
            # Enhanced monitoring status
            integration_status = self.enhanced_monitoring_integration.get_integration_status()
            print(f"Enhanced Monitoring: {'Active' if integration_status.get('integration_active', False) else 'Inactive'}")
            
            # Dynamic trigger system status
            if self.dynamic_trigger_system:
                trigger_status = self.dynamic_trigger_system.get_system_status()
                print(f"Dynamic Triggers: {'Active' if trigger_status.get('system_active', False) else 'Inactive'}")
                
                stats = trigger_status.get('statistics', {})
                print(f"Total Triggers Fired: {stats.get('total_triggers_fired', 0)}")
                print(f"Successful Triggers: {stats.get('successful_triggers', 0)}")
                print(f"Average Response Time: {stats.get('average_response_time', 0):.2f}s")
                
                # Show trigger type distribution
                triggers_by_type = stats.get('triggers_by_type', {})
                if triggers_by_type:
                    top_triggers = sorted(triggers_by_type.items(), key=lambda x: x[1], reverse=True)[:3]
                    print(f"Top Trigger Types: {', '.join([f'{t}({c})' for t, c in top_triggers])}")
            else:
                print("Dynamic Triggers: Not initialized")
            
            # Batch optimizer status
            if self.batch_optimizer:
                optimizer_analytics = self.batch_optimizer.get_optimization_analytics()
                if 'error' not in optimizer_analytics:
                    perf_summary = optimizer_analytics.get('performance_summary', {})
                    print(f"Batch Optimizer: Active")
                    print(f"Average Batch Size: {perf_summary.get('average_batch_size', 0):.1f}")
                    print(f"Average Success Rate: {perf_summary.get('average_success_rate', 0):.1%}")
                    print(f"Current Strategy: {optimizer_analytics.get('current_strategy', 'unknown')}")
                else:
                    print("Batch Optimizer: Error getting analytics")
            else:
                print("Batch Optimizer: Not initialized")
            
            # Enhanced capacity manager status
            if self.capacity_manager_enhanced:
                capacity_analytics = self.capacity_manager_enhanced.get_capacity_analytics()
                if 'error' not in capacity_analytics:
                    current_status = capacity_analytics.get('current_status')
                    if current_status:
                        print(f"Enhanced Capacity: {current_status.get('total_requests', 0)}/10 requests")
                        print(f"Capacity Level: {current_status.get('capacity_level', 'unknown')}")
                    
                    monitoring_stats = capacity_analytics.get('monitoring_statistics', {})
                    print(f"Capacity Monitoring Cycles: {monitoring_stats.get('total_monitoring_cycles', 0)}")
                    print(f"Crisis Episodes: {monitoring_stats.get('crisis_episodes', 0)}")
                else:
                    print("Enhanced Capacity: Error getting analytics")
            else:
                print("Enhanced Capacity: Not initialized")
            
        except Exception as e:
            print(f"Error getting dynamic batch processing summary: {e}")
    
    def generate_comprehensive_coverage_report(self):
        """Generate and return comprehensive coverage report."""
        try:
            return self.comprehensive_tracker.generate_comprehensive_coverage_report()
        except Exception as e:
            self.logger.error(f"Error generating comprehensive coverage report: {e}")
            return None
    
    def get_regional_summary(self):
        """Get regional progress summary."""
        try:
            return self.comprehensive_tracker.get_regional_summary()
        except Exception as e:
            self.logger.error(f"Error getting regional summary: {e}")
            return {}
    
    def get_unprocessed_files(self):
        """Get list of unprocessed control files."""
        try:
            return self.comprehensive_tracker.get_unprocessed_files()
        except Exception as e:
            self.logger.error(f"Error getting unprocessed files: {e}")
            return []
    
    def verify_control_file_coverage(self, expected_regions=None, expected_variables=None):
        """Verify control file coverage against expected regions and variables."""
        try:
            return self.comprehensive_tracker.verify_control_file_coverage(
                expected_regions, expected_variables
            )
        except Exception as e:
            self.logger.error(f"Error verifying control file coverage: {e}")
            return {"verification_passed": False, "error": str(e)}
    
    def shutdown(self):
        """Graceful shutdown of all components."""
        self.logger.info("Shutting down integrated system...")
        
        self.running = False
        
        # Stop dynamic components first
        if self.enhanced_monitoring_integration:
            self.logger.info("🛑 Stopping enhanced monitoring integration...")
            self.enhanced_monitoring_integration.stop_integration()
        
        if self.dynamic_trigger_system:
            self.logger.info("🛑 Stopping dynamic trigger system...")
            self.dynamic_trigger_system.stop_system()
        
        if self.batch_optimizer:
            self.logger.info("🛑 Stopping batch optimizer...")
            self.batch_optimizer.stop_optimization_monitoring()
        
        if self.capacity_manager_enhanced:
            self.logger.info("🛑 Stopping enhanced capacity manager...")
            self.capacity_manager_enhanced.stop_capacity_monitoring()
        
        # Stop status monitoring
        if hasattr(self.status_monitor, 'monitoring_active'):
            self.status_monitor.stop_monitoring()
        
        # Stop completed request integration
        if hasattr(self.completed_request_integration, 'integration_active'):
            self.completed_request_integration.stop_integration()
        
        # Stop monitoring
        if hasattr(self.monitor, 'monitoring_active'):
            self.monitor.stop_monitoring()
        
        # Save all states
        self.batch_system._save_state()
        self.queue_manager._save_queue_state()
        
        # Cleanup dynamic components
        if self.enhanced_monitoring_integration:
            self.enhanced_monitoring_integration.cleanup()
        
        if self.dynamic_trigger_system:
            self.dynamic_trigger_system.cleanup()
        
        if self.batch_optimizer:
            self.batch_optimizer.cleanup()
        
        # Shutdown executor
        if hasattr(self.batch_system, 'executor'):
            self.batch_system.executor.shutdown(wait=True)
        
        self.logger.info("Integrated system shutdown complete")


def create_requirements_file():
    """Create requirements.txt file for the system."""
    requirements = [
        "requests>=2.25.0",
        "flask>=2.0.0",
        "psutil>=5.8.0",
        "pyyaml>=5.4.0",
        "jsonschema>=3.2.0"
    ]
    
    with open("requirements.txt", 'w') as f:
        f.write("\n".join(requirements))
    
    print("Created requirements.txt file")


def create_setup_script():
    """Create setup script for easy installation."""
    setup_script = """#!/bin/bash
# Setup script for Batch Automation System

echo "Setting up Batch Automation System..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p logs
mkdir -p downloaded_files
mkdir -p templates

# Set permissions
chmod +x batch_automation_integrated.py
chmod +x batch_automation.py
chmod +x batch_queue_manager.py
chmod +x batch_monitor.py

echo "Setup complete!"
echo ""
echo "To run the system:"
echo "  source venv/bin/activate"
echo "  python batch_automation_integrated.py --process-all-control-files"
echo ""
echo "To view the dashboard:"
echo "  python batch_automation_integrated.py --monitor-dashboard"
"""
    
    with open("setup.sh", 'w') as f:
        f.write(setup_script)
    
    # Make executable
    os.chmod("setup.sh", 0o755)
    print("Created setup.sh script")


def create_user_guide():
    """Create comprehensive user guide."""
    user_guide = """# Batch Automation System User Guide

## Overview

The Batch Automation System is a comprehensive solution for processing large numbers of RDA (Research Data Archive) control files automatically. It provides intelligent queuing, progress monitoring, and a web-based dashboard.

## Features

- **Automated Processing**: Processes all control files in the control_files directory
- **Intelligent Queuing**: Prioritizes requests based on region importance and variable type
- **Rate Limiting**: Respects RDA system limits and prevents overwhelming the service
- **Progress Monitoring**: Real-time monitoring with detailed progress reports
- **Web Dashboard**: Interactive web interface for monitoring progress
- **Resume Capability**: Can resume processing from interruptions
- **File Organization**: Automatically organizes downloads by REGION_NAME/weather_variable_type

## Quick Start

1. **Setup**:
   ```bash
   ./setup.sh
   source venv/bin/activate
   ```

2. **Process All Control Files**:
   ```bash
   python batch_automation_integrated.py --process-all-control-files
   ```

3. **Monitor Progress**:
   - Console: Progress reports are printed every cycle
   - Web Dashboard: Visit http://localhost:5000

## Command Line Options

### Main Commands

- `--process-all-control-files`: Start processing all control files from scratch
- `--resume`: Resume processing from saved state
- `--monitor-dashboard`: Run only monitoring and web dashboard
- `--status`: Show current status summary

### Examples

```bash
# Start full processing
python batch_automation_integrated.py --process-all-control-files

# Resume interrupted processing
python batch_automation_integrated.py --resume

# Monitor existing processing
python batch_automation_integrated.py --monitor-dashboard

# Check current status
python batch_automation_integrated.py --status
```

## Configuration

The system uses `automation_config.json` for configuration:

```json
{
  "automation": {
    "max_concurrent_requests": 5,
    "check_interval_seconds": 300,
    "retry_attempts": 3,
    "retry_delay_seconds": 60
  },
  "directories": {
    "base_download_dir": "./downloaded_files",
    "logs_dir": "./logs",
    "control_files_dir": "./control_files"
  }
}
```

## File Organization

Downloaded files are automatically organized as:
```
downloaded_files/
├── CISO/
│   ├── dswrf/
│   ├── wind/
│   └── temp/
├── ERCOT/
│   ├── rain/
│   └── wind/
└── PJM/
    ├── temp/
    └── rain/
```

## Monitoring and Progress Tracking

### Console Output
- Real-time progress reports every processing cycle
- Status summaries showing pending, processing, completed, and failed requests
- Estimated completion times
- Success rates and performance metrics

### Web Dashboard
- Interactive charts showing progress over time
- Real-time status updates
- System performance metrics
- Queue statistics

### Log Files
- Detailed logs in the `logs/` directory
- Separate log files for each component
- Timestamped entries for debugging

## Intelligent Queuing

The system uses intelligent queuing to optimize processing:

- **Priority Levels**: HIGH, NORMAL, LOW based on region importance
- **Resource Management**: Limits concurrent requests per region/variable
- **Dependency Handling**: Manages request dependencies
- **Load Balancing**: Distributes load across different regions and variables

## Error Handling and Recovery

- **Automatic Retries**: Failed requests are automatically retried
- **State Persistence**: System state is saved regularly
- **Graceful Shutdown**: Handles interruptions gracefully
- **Resume Capability**: Can resume from any point

## Troubleshooting

### Common Issues

1. **No Control Files Found**:
   - Check that control files are in the `control_files/` directory
   - Ensure files have `.ctl` extension

2. **Authentication Errors**:
   - Verify `rdams_token.txt` contains valid token
   - Check RDA account permissions

3. **Download Failures**:
   - Check network connectivity
   - Verify disk space availability
   - Check RDA service status

4. **Web Dashboard Not Loading**:
   - Ensure port 5000 is available
   - Check firewall settings
   - Verify Flask installation

### Log Analysis

Check log files in the `logs/` directory:
- `integrated_system_*.log`: Main system logs
- `batch_automation_*.log`: Core automation logs

### Performance Tuning

Adjust configuration parameters:
- `max_concurrent_requests`: Increase for faster processing (respect RDA limits)
- `check_interval_seconds`: Decrease for more frequent status checks
- `retry_attempts`: Increase for better reliability

## Advanced Usage

### Custom Configuration

Create custom configuration files:
```bash
python batch_automation_integrated.py --config custom_config.json --process-all-control-files
```

### Selective Processing

Process specific regions or variables by modifying control files directory structure.

### Integration with Other Systems

The system provides APIs and can be integrated with other workflow management systems.

## Support and Maintenance

- Monitor system resources (CPU, memory, disk space)
- Regularly clean up old log files
- Update RDA tokens as needed
- Check for system updates

## Best Practices

1. **Before Starting**:
   - Verify RDA token is valid
   - Check available disk space
   - Review control files for accuracy

2. **During Processing**:
   - Monitor progress through web dashboard
   - Check logs for any errors
   - Avoid interrupting unless necessary

3. **After Completion**:
   - Verify all files downloaded correctly
   - Archive or backup downloaded data
   - Clean up temporary files

## Contact and Support

For issues or questions:
- Check log files for error details
- Review this user guide
- Contact system administrator
"""
    
    with open("USER_GUIDE.md", 'w') as f:
        f.write(user_guide)
    
    print("Created USER_GUIDE.md")


def main():
    """Main function for integrated system."""
    parser = argparse.ArgumentParser(
        description='Integrated Batch Automation System for RDA Control Files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --process-all-control-files    # Process all control files
  %(prog)s --resume                       # Resume from saved state
  %(prog)s --monitor-dashboard            # Monitor with web dashboard
  %(prog)s --status                       # Show current status
  %(prog)s --setup                        # Create setup files
        """
    )
    
    parser.add_argument('--process-all-control-files', action='store_true',
                       help='Process all control files with integrated system')
    parser.add_argument('--resume', action='store_true',
                       help='Resume processing from saved state')
    parser.add_argument('--monitor-dashboard', action='store_true',
                       help='Run monitoring and web dashboard only')
    parser.add_argument('--status', action='store_true',
                       help='Show current status of all components')
    parser.add_argument('--setup', action='store_true',
                       help='Create setup files (requirements.txt, setup.sh, user guide)')
    parser.add_argument('--config', default='automation_config.json',
                       help='Configuration file path')
    
    args = parser.parse_args()
    
    if args.setup:
        print("Creating setup files...")
        create_requirements_file()
        create_setup_script()
        create_user_guide()
        print("Setup files created successfully!")
        print("\nNext steps:")
        print("1. Run: ./setup.sh")
        print("2. Run: source venv/bin/activate")
        print("3. Run: python batch_automation_integrated.py --process-all-control-files")
        return
    
    # Initialize integrated system
    system = IntegratedBatchSystem(args.config)
    
    try:
        if args.process_all_control_files:
            system.process_all_control_files()
        elif args.resume:
            system.resume_processing()
        elif args.monitor_dashboard:
            system.monitor_dashboard_only()
        elif args.status:
            system.show_status()
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        system.shutdown()
    except Exception as e:
        print(f"Error: {e}")
        system.shutdown()
        sys.exit(1)


if __name__ == '__main__':
    main()