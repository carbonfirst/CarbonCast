#!/usr/bin/env python3
"""
Processing Progress Tracker for Sequential File Processing

This module provides comprehensive progress tracking and metrics for the sequential
file processing system. It tracks completion status, progress metrics, and provides
real-time updates to the dashboard system.

Key Features:
- Real-time progress tracking for sequential file processing
- Comprehensive metrics collection and analysis
- Integration with existing database schema
- Dashboard-compatible progress updates
- Estimated completion time calculations
- Regional and variable-type progress breakdown
- Performance metrics and trend analysis
"""

import os
import sys
import json
import time
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ProcessingStatus(Enum):
    """Enumeration for processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProgressPhase(Enum):
    """Enumeration for progress phases."""
    DISCOVERY = "discovery"
    SUBMISSION = "submission"
    MONITORING = "monitoring"
    DOWNLOADING = "downloading"
    ORGANIZATION = "organization"
    COMPLETED = "completed"


@dataclass
class FileProcessingProgress:
    """Progress information for a single file."""
    filename: str
    region: str
    variable_type: str
    status: ProcessingStatus
    request_id: Optional[str] = None
    submission_time: Optional[str] = None
    completion_time: Optional[str] = None
    processing_duration: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    downloaded_files: int = 0
    total_expected_files: int = 0


@dataclass
class RegionalProgress:
    """Progress information for a region."""
    region: str
    region_name: str
    total_control_files: int
    submitted_files: int
    completed_files: int
    downloaded_files: int
    failed_files: int
    success_rate: float
    completion_percentage: float
    estimated_completion_time: Optional[str]
    variable_breakdown: Dict[str, int]
    last_updated: str


@dataclass
class OverallProgress:
    """Overall progress information for sequential processing."""
    session_id: str
    total_files: int
    processed_files: int
    completed_files: int
    failed_files: int
    skipped_files: int
    current_phase: ProgressPhase
    current_file: Optional[str]
    progress_percentage: float
    estimated_completion_time: Optional[str]
    processing_rate_per_hour: float
    elapsed_time_hours: float
    remaining_time_hours: Optional[float]
    start_time: str
    last_updated: str


@dataclass
class ProgressMetrics:
    """Comprehensive progress metrics."""
    overall_progress: OverallProgress
    regional_progress: List[RegionalProgress]
    file_progress: List[FileProcessingProgress]
    performance_metrics: Dict[str, Any]
    trend_analysis: Dict[str, Any]
    generated_at: str


class ProcessingProgressTracker:
    """
    Comprehensive progress tracker for sequential file processing.
    
    This class provides real-time progress tracking, metrics collection,
    and dashboard integration for the sequential file processing system.
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db",
                 session_id: Optional[str] = None):
        """
        Initialize the Processing Progress Tracker.
        
        Args:
            db_path: Path to the SQLite database file
            session_id: Unique session identifier for this processing run
        """
        self.db_path = db_path
        self.session_id = session_id or f"sequential_processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.logger = self._setup_logging()
        
        # Progress tracking state
        self.start_time = datetime.now()
        self.current_phase = ProgressPhase.DISCOVERY
        self.current_file = None
        self.file_progress = {}  # filename -> FileProcessingProgress
        self.regional_progress = {}  # region -> RegionalProgress
        
        # Performance tracking
        self.processing_history = []
        self.phase_timings = {}
        
        # Threading for thread-safe operations
        self.progress_lock = threading.Lock()
        
        # Initialize database schema
        self._initialize_progress_tables()
        
        self.logger.info(f"Processing Progress Tracker initialized with session: {self.session_id}")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the progress tracker."""
        logger = logging.getLogger('rda_automation.processing_progress_tracker')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_progress_tables(self):
        """Initialize database tables for progress tracking."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Sequential processing sessions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sequential_processing_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT UNIQUE NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        total_files INTEGER DEFAULT 0,
                        completed_files INTEGER DEFAULT 0,
                        failed_files INTEGER DEFAULT 0,
                        current_phase TEXT DEFAULT 'discovery',
                        current_file TEXT,
                        progress_percentage REAL DEFAULT 0.0,
                        processing_rate_per_hour REAL DEFAULT 0.0,
                        estimated_completion_time TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # File processing progress table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS file_processing_progress (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        region TEXT NOT NULL,
                        variable_type TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        request_id TEXT,
                        submission_time TEXT,
                        completion_time TEXT,
                        processing_duration REAL,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        downloaded_files INTEGER DEFAULT 0,
                        total_expected_files INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sequential_processing_sessions(session_id)
                    )
                """)
                
                # Regional progress summary table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sequential_regional_progress (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        region TEXT NOT NULL,
                        region_name TEXT,
                        total_control_files INTEGER DEFAULT 0,
                        submitted_files INTEGER DEFAULT 0,
                        completed_files INTEGER DEFAULT 0,
                        downloaded_files INTEGER DEFAULT 0,
                        failed_files INTEGER DEFAULT 0,
                        success_rate REAL DEFAULT 0.0,
                        completion_percentage REAL DEFAULT 0.0,
                        estimated_completion_time TEXT,
                        variable_breakdown TEXT,
                        last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sequential_processing_sessions(session_id),
                        UNIQUE(session_id, region)
                    )
                """)
                
                # Progress snapshots for trend analysis
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS progress_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        snapshot_time TEXT NOT NULL,
                        phase TEXT NOT NULL,
                        progress_percentage REAL NOT NULL,
                        files_processed INTEGER NOT NULL,
                        processing_rate_per_hour REAL NOT NULL,
                        estimated_completion_time TEXT,
                        performance_metrics TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sequential_processing_sessions(session_id)
                    )
                """)
                
                conn.commit()
                self.logger.debug("Progress tracking tables initialized")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing progress tables: {e}")
            raise
    
    def start_processing_session(self, total_files: int, file_list: List[str]):
        """
        Start a new sequential processing session.
        
        Args:
            total_files: Total number of files to process
            file_list: List of filenames to process
        """
        try:
            with self.progress_lock:
                self.start_time = datetime.now()
                self.current_phase = ProgressPhase.DISCOVERY
                
                # Initialize file progress tracking
                for filename in file_list:
                    # Extract region and variable from filename
                    parts = filename.replace('.ctl', '').split('_')
                    if len(parts) >= 2:
                        region = parts[0]
                        variable_type = parts[1]
                    else:
                        region = "UNKNOWN"
                        variable_type = "unknown"
                    
                    self.file_progress[filename] = FileProcessingProgress(
                        filename=filename,
                        region=region,
                        variable_type=variable_type,
                        status=ProcessingStatus.PENDING
                    )
                
                # Initialize regional progress
                self._update_regional_progress()
            
            # Record session in database
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO sequential_processing_sessions
                    (session_id, start_time, total_files, current_phase, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    self.session_id,
                    self.start_time.isoformat(),
                    total_files,
                    self.current_phase.value,
                    'active'
                ))
                conn.commit()
            
            self.logger.info(f"Started processing session: {self.session_id} with {total_files} files")
            
        except Exception as e:
            self.logger.error(f"Error starting processing session: {e}")
            raise
    
    def update_phase(self, new_phase: ProgressPhase, current_file: Optional[str] = None):
        """
        Update the current processing phase.
        
        Args:
            new_phase: New processing phase
            current_file: Currently processing file (optional)
        """
        try:
            with self.progress_lock:
                old_phase = self.current_phase
                self.current_phase = new_phase
                self.current_file = current_file
                
                # Record phase timing
                now = datetime.now()
                if old_phase != new_phase:
                    self.phase_timings[old_phase.value] = (now - self.start_time).total_seconds()
            
            # Update database
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sequential_processing_sessions
                    SET current_phase = ?, current_file = ?, updated_at = ?
                    WHERE session_id = ?
                """, (
                    new_phase.value,
                    current_file,
                    datetime.now().isoformat(),
                    self.session_id
                ))
                conn.commit()
            
            self.logger.info(f"Phase updated: {old_phase.value} -> {new_phase.value}" + 
                           (f" (file: {current_file})" if current_file else ""))
            
        except Exception as e:
            self.logger.error(f"Error updating phase: {e}")
    
    def update_file_progress(self, filename: str, status: ProcessingStatus,
                           request_id: Optional[str] = None,
                           error_message: Optional[str] = None,
                           downloaded_files: int = 0,
                           total_expected_files: int = 0):
        """
        Update progress for a specific file.
        
        Args:
            filename: Name of the file being processed
            status: New processing status
            request_id: RDA request ID (if available)
            error_message: Error message (if failed)
            downloaded_files: Number of files downloaded
            total_expected_files: Total expected files for this request
        """
        try:
            with self.progress_lock:
                if filename not in self.file_progress:
                    self.logger.warning(f"File not found in progress tracking: {filename}")
                    return
                
                file_progress = self.file_progress[filename]
                old_status = file_progress.status
                
                # Update file progress
                file_progress.status = status
                file_progress.request_id = request_id
                file_progress.error_message = error_message
                file_progress.downloaded_files = downloaded_files
                file_progress.total_expected_files = total_expected_files
                
                # Update timing information
                now = datetime.now()
                if status == ProcessingStatus.PROCESSING and old_status == ProcessingStatus.PENDING:
                    file_progress.submission_time = now.isoformat()
                elif status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
                    file_progress.completion_time = now.isoformat()
                    if file_progress.submission_time:
                        submission_time = datetime.fromisoformat(file_progress.submission_time)
                        file_progress.processing_duration = (now - submission_time).total_seconds() / 3600
                
                # Update retry count for failed status
                if status == ProcessingStatus.FAILED:
                    file_progress.retry_count += 1
                
                # Update regional progress
                self._update_regional_progress()
            
            # Update database
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO file_processing_progress
                    (session_id, filename, region, variable_type, status, request_id,
                     submission_time, completion_time, processing_duration, error_message,
                     retry_count, downloaded_files, total_expected_files, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.session_id,
                    file_progress.filename,
                    file_progress.region,
                    file_progress.variable_type,
                    file_progress.status.value,
                    file_progress.request_id,
                    file_progress.submission_time,
                    file_progress.completion_time,
                    file_progress.processing_duration,
                    file_progress.error_message,
                    file_progress.retry_count,
                    file_progress.downloaded_files,
                    file_progress.total_expected_files,
                    datetime.now().isoformat()
                ))
                conn.commit()
            
            self.logger.info(f"File progress updated: {filename} -> {status.value}" + 
                           (f" (request: {request_id})" if request_id else ""))
            
        except Exception as e:
            self.logger.error(f"Error updating file progress: {e}")
    
    def _update_regional_progress(self):
        """Update regional progress summaries."""
        try:
            # Group files by region
            regional_data = {}
            
            for file_progress in self.file_progress.values():
                region = file_progress.region
                if region not in regional_data:
                    regional_data[region] = {
                        'total_files': 0,
                        'submitted_files': 0,
                        'completed_files': 0,
                        'downloaded_files': 0,
                        'failed_files': 0,
                        'variables': {}
                    }
                
                data = regional_data[region]
                data['total_files'] += 1
                
                # Count by status
                if file_progress.status == ProcessingStatus.PROCESSING:
                    data['submitted_files'] += 1
                elif file_progress.status == ProcessingStatus.COMPLETED:
                    data['completed_files'] += 1
                    data['downloaded_files'] += file_progress.downloaded_files
                elif file_progress.status == ProcessingStatus.FAILED:
                    data['failed_files'] += 1
                
                # Track variables
                var_type = file_progress.variable_type
                data['variables'][var_type] = data['variables'].get(var_type, 0) + 1
            
            # Update regional progress objects
            for region, data in regional_data.items():
                total = data['total_files']
                completed = data['completed_files']
                failed = data['failed_files']
                
                success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
                completion_percentage = (completed / total * 100) if total > 0 else 0
                
                # Estimate completion time based on current rate
                estimated_completion = None
                if completed > 0 and total > completed:
                    elapsed_hours = (datetime.now() - self.start_time).total_seconds() / 3600
                    rate_per_hour = completed / elapsed_hours if elapsed_hours > 0 else 0
                    if rate_per_hour > 0:
                        remaining_hours = (total - completed) / rate_per_hour
                        estimated_completion = (datetime.now() + timedelta(hours=remaining_hours)).isoformat()
                
                self.regional_progress[region] = RegionalProgress(
                    region=region,
                    region_name=region.replace('_', ' ').title(),
                    total_control_files=total,
                    submitted_files=data['submitted_files'],
                    completed_files=completed,
                    downloaded_files=data['downloaded_files'],
                    failed_files=failed,
                    success_rate=success_rate,
                    completion_percentage=completion_percentage,
                    estimated_completion_time=estimated_completion,
                    variable_breakdown=data['variables'],
                    last_updated=datetime.now().isoformat()
                )
            
            # Update database
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                for region_progress in self.regional_progress.values():
                    cursor.execute("""
                        INSERT OR REPLACE INTO sequential_regional_progress
                        (session_id, region, region_name, total_control_files, submitted_files,
                         completed_files, downloaded_files, failed_files, success_rate,
                         completion_percentage, estimated_completion_time, variable_breakdown, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.session_id,
                        region_progress.region,
                        region_progress.region_name,
                        region_progress.total_control_files,
                        region_progress.submitted_files,
                        region_progress.completed_files,
                        region_progress.downloaded_files,
                        region_progress.failed_files,
                        region_progress.success_rate,
                        region_progress.completion_percentage,
                        region_progress.estimated_completion_time,
                        json.dumps(region_progress.variable_breakdown),
                        region_progress.last_updated
                    ))
                conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error updating regional progress: {e}")
    
    def get_overall_progress(self) -> OverallProgress:
        """
        Get overall progress information.
        
        Returns:
            OverallProgress object with current status
        """
        try:
            with self.progress_lock:
                total_files = len(self.file_progress)
                processed_files = len([f for f in self.file_progress.values() 
                                     if f.status != ProcessingStatus.PENDING])
                completed_files = len([f for f in self.file_progress.values() 
                                     if f.status == ProcessingStatus.COMPLETED])
                failed_files = len([f for f in self.file_progress.values() 
                                  if f.status == ProcessingStatus.FAILED])
                skipped_files = len([f for f in self.file_progress.values() 
                                   if f.status == ProcessingStatus.SKIPPED])
                
                progress_percentage = (processed_files / total_files * 100) if total_files > 0 else 0
                
                # Calculate processing rate
                elapsed_time = datetime.now() - self.start_time
                elapsed_hours = elapsed_time.total_seconds() / 3600
                processing_rate = completed_files / elapsed_hours if elapsed_hours > 0 else 0
                
                # Estimate completion time
                estimated_completion = None
                remaining_time_hours = None
                if processing_rate > 0 and completed_files < total_files:
                    remaining_files = total_files - completed_files
                    remaining_time_hours = remaining_files / processing_rate
                    estimated_completion = (datetime.now() + timedelta(hours=remaining_time_hours)).isoformat()
                
                return OverallProgress(
                    session_id=self.session_id,
                    total_files=total_files,
                    processed_files=processed_files,
                    completed_files=completed_files,
                    failed_files=failed_files,
                    skipped_files=skipped_files,
                    current_phase=self.current_phase,
                    current_file=self.current_file,
                    progress_percentage=progress_percentage,
                    estimated_completion_time=estimated_completion,
                    processing_rate_per_hour=processing_rate,
                    elapsed_time_hours=elapsed_hours,
                    remaining_time_hours=remaining_time_hours,
                    start_time=self.start_time.isoformat(),
                    last_updated=datetime.now().isoformat()
                )
        
        except Exception as e:
            self.logger.error(f"Error getting overall progress: {e}")
            # Return default progress object
            return OverallProgress(
                session_id=self.session_id,
                total_files=0,
                processed_files=0,
                completed_files=0,
                failed_files=0,
                skipped_files=0,
                current_phase=ProgressPhase.DISCOVERY,
                current_file=None,
                progress_percentage=0.0,
                estimated_completion_time=None,
                processing_rate_per_hour=0.0,
                elapsed_time_hours=0.0,
                remaining_time_hours=None,
                start_time=datetime.now().isoformat(),
                last_updated=datetime.now().isoformat()
            )
    
    def get_comprehensive_metrics(self) -> ProgressMetrics:
        """
        Get comprehensive progress metrics.
        
        Returns:
            ProgressMetrics object with all tracking information
        """
        try:
            overall_progress = self.get_overall_progress()
            
            # Get performance metrics
            performance_metrics = self._calculate_performance_metrics()
            
            # Get trend analysis
            trend_analysis = self._calculate_trend_analysis()
            
            return ProgressMetrics(
                overall_progress=overall_progress,
                regional_progress=list(self.regional_progress.values()),
                file_progress=list(self.file_progress.values()),
                performance_metrics=performance_metrics,
                trend_analysis=trend_analysis,
                generated_at=datetime.now().isoformat()
            )
        
        except Exception as e:
            self.logger.error(f"Error getting comprehensive metrics: {e}")
            return ProgressMetrics(
                overall_progress=self.get_overall_progress(),
                regional_progress=[],
                file_progress=[],
                performance_metrics={},
                trend_analysis={},
                generated_at=datetime.now().isoformat()
            )
    
    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics."""
        try:
            completed_files = [f for f in self.file_progress.values() 
                             if f.status == ProcessingStatus.COMPLETED and f.processing_duration]
            
            if not completed_files:
                return {
                    'average_processing_time_hours': 0.0,
                    'fastest_processing_time_hours': 0.0,
                    'slowest_processing_time_hours': 0.0,
                    'total_processing_time_hours': 0.0,
                    'files_with_timing_data': 0
                }
            
            processing_times = [f.processing_duration for f in completed_files]
            
            return {
                'average_processing_time_hours': sum(processing_times) / len(processing_times),
                'fastest_processing_time_hours': min(processing_times),
                'slowest_processing_time_hours': max(processing_times),
                'total_processing_time_hours': sum(processing_times),
                'files_with_timing_data': len(completed_files),
                'processing_efficiency': len(completed_files) / len(self.file_progress) if self.file_progress else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def _calculate_trend_analysis(self) -> Dict[str, Any]:
        """Calculate trend analysis."""
        try:
            # This would typically analyze historical snapshots
            # For now, provide basic trend information
            
            elapsed_hours = (datetime.now() - self.start_time).total_seconds() / 3600
            completed_count = len([f for f in self.file_progress.values() 
                                 if f.status == ProcessingStatus.COMPLETED])
            
            return {
                'processing_trend': 'increasing' if completed_count > 0 else 'stable',
                'completion_velocity': completed_count / elapsed_hours if elapsed_hours > 0 else 0,
                'phase_timings': self.phase_timings.copy(),
                'session_duration_hours': elapsed_hours
            }
        
        except Exception as e:
            self.logger.error(f"Error calculating trend analysis: {e}")
            return {}
    
    def create_progress_snapshot(self) -> bool:
        """
        Create a progress snapshot for trend analysis.
        
        Returns:
            True if snapshot was created successfully, False otherwise
        """
        try:
            overall_progress = self.get_overall_progress()
            performance_metrics = self._calculate_performance_metrics()
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO progress_snapshots
                    (session_id, snapshot_time, phase, progress_percentage, files_processed,
                     processing_rate_per_hour, estimated_completion_time, performance_metrics)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.session_id,
                    datetime.now().isoformat(),
                    overall_progress.current_phase.value,
                    overall_progress.progress_percentage,
                    overall_progress.processed_files,
                    overall_progress.processing_rate_per_hour,
                    overall_progress.estimated_completion_time,
                    json.dumps(performance_metrics)
                ))
                conn.commit()
            
            self.logger.debug("Progress snapshot created")
            return True
        
        except Exception as e:
            self.logger.error(f"Error creating progress snapshot: {e}")
            return False
    
    def complete_processing_session(self, final_status: str = "completed"):
        """
        Complete the processing session.
        
        Args:
            final_status: Final status of the session
        """
        try:
            end_time = datetime.now()
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sequential_processing_sessions
                    SET end_time = ?, status = ?, updated_at = ?
                    WHERE session_id = ?
                """, (
                    end_time.isoformat(),
                    final_status,
                    end_time.isoformat(),
                    self.session_id
                ))
                conn.commit()
            
            # Create final snapshot
            self.create_progress_snapshot()
            
            duration = end_time - self.start_time
            self.logger.info(f"Processing session completed: {self.session_id} "
                           f"(duration: {duration.total_seconds()/3600:.2f}h, status: {final_status})")
        
        except Exception as e:
            self.logger.error(f"Error completing processing session: {e}")


def create_processing_progress_tracker(db_path: str = "src/python/data/automation_state.db",
                                     session_id: Optional[str] = None) -> ProcessingProgressTracker:
    """
    Factory function to create a Processing Progress Tracker.
    
    Args:
        db_path: Path to the SQLite database file
        session_id: Unique session identifier for this processing run
        
    Returns:
        Configured ProcessingProgressTracker instance
    """
    return ProcessingProgressTracker(db_path, session_id)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Processing Progress Tracker')
    parser.add_argument('--session-id', type=str,
                       help='Session ID to track')
    parser.add_argument('--start-session', action='store_true',
                       help='Start a new processing session')
    parser.add_argument('--progress', action='store_true',
                       help='Show current progress')
    parser.add_argument('--metrics', action='store_true',
                       help='Show comprehensive metrics')
    parser.add_argument('--snapshot', action='store_true',
                       help='Create progress snapshot')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Database path')
    
    args = parser.parse_args()
    
    # Create progress tracker
    tracker = create_processing_progress_tracker(args.db_path, args.session_id)
    
    try:
        if args.start_session:
            print("=== Starting New Processing Session ===")
            # Example file list
            test_files = ["ERCOT_wind_control.ctl", "CISO_dswrf_control.ctl", "PJM_rain_control.ctl"]
            tracker.start_processing_session(len(test_files), test_files)
            print(f"Session started: {tracker.session_id}")
        
        elif args.progress:
            print("=== Current Progress ===")
            progress = tracker.get_overall_progress()
            print(f"Session: {progress.session_id}")
            print(f"Phase: {progress.current_phase.value}")
            print(f"Progress: {progress.progress_percentage:.1f}%")
            print(f"Files: {progress.completed_files}/{progress.total_files}")
            print(f"Rate: {progress.processing_rate_per_hour:.2f} files/hour")
            if progress.estimated_completion_time:
                print(f"ETA: {progress.estimated_completion_time}")
        
        elif args.metrics:
            print("=== Comprehensive Metrics ===")
            metrics = tracker.get_comprehensive_metrics()
            print(json.dumps(asdict(metrics), indent=2, default=str))
        
        elif args.snapshot:
            print("=== Creating Progress Snapshot ===")
            success = tracker.create_progress_snapshot()
            print(f"Snapshot created: {'✅ Success' if success else '❌ Failed'}")
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("PROCESSING PROGRESS TRACKER EXAMPLES")
            print("="*60)
            print("# Start new session:")
            print("python automation/processing_progress_tracker.py --start-session")
            print("\n# Show current progress:")
            print("python automation/processing_progress_tracker.py --progress --session-id SESSION_ID")
            print("\n# Show comprehensive metrics:")
            print("python automation/processing_progress_tracker.py --metrics --session-id SESSION_ID")
            print("\n# Create progress snapshot:")
            print("python automation/processing_progress_tracker.py --snapshot --session-id SESSION_ID")
            print("="*60)
    
    except Exception as e:
        print(f"Error: {e}")
        if args.start_session:
            print("=== Starting New Processing Session ===")
            # Example file list
            test_files = ["ERCOT_wind_control.ctl", "CISO_dswrf_control.ctl", "PJM_rain_control.ctl"]
            tracker.start_processing_session(len(test_files), test_files)
            print(f"Session started: {tracker.session_id}")
        
        elif args.progress:
            print("=== Current Progress ===")
            progress = tracker.get_overall_progress()