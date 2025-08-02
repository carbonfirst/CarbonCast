#!/usr/bin/env python3
"""
Comprehensive Tracking and Logging System for RDA Automation

This module provides complete coverage tracking, regional progress monitoring,
and smart verification of control file processing to ensure no files are left behind.

Key Features:
- Complete control file discovery and coverage verification
- Detailed regional progress tracking with timestamps
- Smart detection of missing or unprocessed control files
- Comprehensive logging with regional insights
- Dashboard integration for regional progress visualization
- Automated alerts for unprocessed files
"""

import os
import sys
import json
import time
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import threading
import glob

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coordinate_utils import get_region_and_variable_from_request_enhanced


@dataclass
class ControlFileInfo:
    """Comprehensive information about a control file."""
    file_path: str
    filename: str
    region: str
    variable_type: str
    discovered_at: str
    file_size: int
    last_modified: str
    status: str = "discovered"  # discovered, queued, submitted, processing, completed, failed, missing
    request_id: Optional[str] = None
    submission_time: Optional[str] = None
    completion_time: Optional[str] = None
    download_time: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    processing_duration: Optional[float] = None  # hours
    download_directory: Optional[str] = None


@dataclass
class RegionalProgress:
    """Detailed progress tracking for a specific region."""
    region: str
    region_name: str
    total_control_files: int = 0
    discovered_files: int = 0
    queued_files: int = 0
    submitted_files: int = 0
    processing_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    downloaded_files: int = 0
    missing_files: int = 0
    
    # Weather variable breakdown
    variable_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Timing information
    first_discovered: Optional[str] = None
    last_updated: Optional[str] = None
    
    # Progress metrics
    completion_percentage: float = 0.0
    success_rate: float = 0.0
    average_processing_time: float = 0.0
    
    # Error tracking
    common_errors: List[str] = field(default_factory=list)
    retry_statistics: Dict[str, int] = field(default_factory=dict)


@dataclass
class CoverageReport:
    """Comprehensive coverage report for all control files."""
    total_control_files_discovered: int
    total_regions: int
    total_variables: int
    coverage_percentage: float
    missing_files: List[str]
    unprocessed_files: List[str]
    failed_files: List[str]
    regional_coverage: Dict[str, RegionalProgress]
    variable_coverage: Dict[str, Dict[str, int]]
    generated_at: str
    scan_duration: float
    alerts: List[str] = field(default_factory=list)


class ComprehensiveTracker:
    """
    Comprehensive tracking system for complete control file coverage and regional progress.
    
    This class ensures that every single control file is discovered, tracked, and processed
    with detailed logging and progress monitoring by region and weather variable.
    """
    
    def __init__(self, 
                 control_files_dir: str = "./control_files",
                 db_path: str = "./data/automation_state.db",
                 config: Optional[Dict] = None):
        """
        Initialize the comprehensive tracker.
        
        Args:
            control_files_dir: Directory containing control files
            db_path: Path to SQLite database for tracking
            config: Optional configuration dictionary
        """
        self.control_files_dir = Path(control_files_dir)
        self.db_path = db_path
        self.config = config or {}
        self.logger = self._setup_logging()
        
        # Tracking data structures
        self.control_files_registry: Dict[str, ControlFileInfo] = {}
        self.regional_progress: Dict[str, RegionalProgress] = {}
        self.coverage_history: List[CoverageReport] = []
        
        # Threading for concurrent operations
        self.tracker_lock = threading.Lock()
        
        # Initialize database
        self._initialize_tracking_database()
        
        # Load existing tracking data
        self._load_tracking_state()
        
        self.logger.info("Comprehensive Tracker initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup comprehensive logging for the tracker."""
        logger = logging.getLogger('comprehensive_tracker')
        
        if not logger.handlers:
            # Create logs directory
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            
            # File handler for comprehensive tracking logs
            log_file = logs_dir / f"comprehensive_tracking_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
    
    def _initialize_tracking_database(self):
        """Initialize SQLite database for comprehensive tracking."""
        try:
            # Ensure data directory exists
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Control files tracking table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS control_files_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT UNIQUE NOT NULL,
                        filename TEXT NOT NULL,
                        region TEXT NOT NULL,
                        variable_type TEXT NOT NULL,
                        discovered_at TEXT NOT NULL,
                        file_size INTEGER,
                        last_modified TEXT,
                        status TEXT DEFAULT 'discovered',
                        request_id TEXT,
                        submission_time TEXT,
                        completion_time TEXT,
                        download_time TEXT,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        processing_duration REAL,
                        download_directory TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # regional_progress table has been removed - no longer creating it
                # This table caused schema errors and has been replaced with filesystem scanning
                pass
                
                # Coverage reports table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS coverage_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        total_control_files_discovered INTEGER,
                        total_regions INTEGER,
                        total_variables INTEGER,
                        coverage_percentage REAL,
                        missing_files TEXT,  -- JSON
                        unprocessed_files TEXT,  -- JSON
                        failed_files TEXT,  -- JSON
                        regional_coverage TEXT,  -- JSON
                        variable_coverage TEXT,  -- JSON
                        scan_duration REAL,
                        alerts TEXT,  -- JSON
                        generated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_control_files_region ON control_files_tracking(region)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_control_files_variable ON control_files_tracking(variable_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_control_files_status ON control_files_tracking(status)")
                # regional_progress table removed - no index needed
                pass
                
                conn.commit()
                self.logger.info("Tracking database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Error initializing tracking database: {e}")
            raise
    
    def discover_all_control_files(self, force_rescan: bool = False) -> Dict[str, ControlFileInfo]:
        """
        Discover and catalog ALL control files in the control files directory.
        
        Args:
            force_rescan: Force a complete rescan even if files are already tracked
            
        Returns:
            Dictionary mapping file paths to ControlFileInfo objects
        """
        scan_start = time.time()
        self.logger.info(f"🔍 Starting comprehensive control file discovery in {self.control_files_dir}")
        
        if not self.control_files_dir.exists():
            self.logger.error(f"Control files directory not found: {self.control_files_dir}")
            return {}
        
        discovered_files = {}
        new_files_count = 0
        updated_files_count = 0
        
        try:
            # Use multiple patterns to ensure we catch all control files
            patterns = [
                "*.ctl",
                "*_control.ctl",
                "*control*.ctl",
                "**/*.ctl"  # Recursive search
            ]
            
            all_control_files = set()
            for pattern in patterns:
                files = list(self.control_files_dir.glob(pattern))
                all_control_files.update(files)
                self.logger.debug(f"Pattern '{pattern}' found {len(files)} files")
            
            self.logger.info(f"📁 Found {len(all_control_files)} total control files")
            
            for control_file_path in all_control_files:
                try:
                    file_path_str = str(control_file_path)
                    filename = control_file_path.name
                    
                    # Skip if already processed and not forcing rescan
                    if not force_rescan and file_path_str in self.control_files_registry:
                        discovered_files[file_path_str] = self.control_files_registry[file_path_str]
                        continue
                    
                    # Get file metadata
                    file_stat = control_file_path.stat()
                    file_size = file_stat.st_size
                    last_modified = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    
                    # Extract region and variable type
                    region, variable_type = self._extract_region_and_variable(control_file_path)
                    
                    # Create ControlFileInfo
                    control_info = ControlFileInfo(
                        file_path=file_path_str,
                        filename=filename,
                        region=region,
                        variable_type=variable_type,
                        discovered_at=datetime.now().isoformat(),
                        file_size=file_size,
                        last_modified=last_modified
                    )
                    
                    discovered_files[file_path_str] = control_info
                    
                    # Track if this is new or updated
                    if file_path_str not in self.control_files_registry:
                        new_files_count += 1
                        self.logger.info(f"📄 NEW: {filename} -> {region}/{variable_type}")
                    else:
                        updated_files_count += 1
                        self.logger.debug(f"📄 UPDATED: {filename} -> {region}/{variable_type}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing control file {control_file_path}: {e}")
                    continue
            
            # Update registry
            with self.tracker_lock:
                self.control_files_registry.update(discovered_files)
            
            # Save to database
            self._save_control_files_to_db(discovered_files.values())
            
            scan_duration = time.time() - scan_start
            self.logger.info(f"✅ Control file discovery completed in {scan_duration:.2f}s")
            self.logger.info(f"📊 Summary: {len(discovered_files)} total, {new_files_count} new, {updated_files_count} updated")
            
            return discovered_files
            
        except Exception as e:
            self.logger.error(f"Error during control file discovery: {e}")
            return {}
    
    def _extract_region_and_variable(self, control_file_path: Path) -> Tuple[str, str]:
        """
        Extract region and variable type from control file.
        
        Args:
            control_file_path: Path to the control file
            
        Returns:
            Tuple of (region, variable_type)
        """
        try:
            filename = control_file_path.name
            
            # Method 1: Parse filename pattern (REGION_VARIABLE_control.ctl)
            if filename.endswith('_control.ctl'):
                base_name = filename[:-12]  # Remove '_control.ctl'
                parts = base_name.split('_')
                if len(parts) >= 2:
                    region = parts[0].upper()
                    variable = parts[1].lower()
                    self.logger.debug(f"Extracted from filename: {region}/{variable}")
                    return region, variable
            
            # Method 2: Parse alternative patterns
            if filename.endswith('.ctl'):
                base_name = filename[:-4]  # Remove '.ctl'
                parts = base_name.split('_')
                
                # Look for 'control' keyword and extract before it
                if 'control' in parts:
                    control_index = parts.index('control')
                    if control_index >= 2:
                        region = parts[0].upper()
                        variable = parts[1].lower()
                        self.logger.debug(f"Extracted using control keyword: {region}/{variable}")
                        return region, variable
                
                # Fallback: assume first two parts
                if len(parts) >= 2:
                    region = parts[0].upper()
                    variable = parts[1].lower()
                    self.logger.debug(f"Extracted using fallback: {region}/{variable}")
                    return region, variable
            
            # Method 3: Read control file content and analyze
            try:
                with open(control_file_path, 'r') as f:
                    content = f.read()
                
                # Parse control file parameters
                params = {}
                for line in content.split('\n'):
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        params[key.strip()] = value.strip()
                
                # Create mock request for enhanced detection
                mock_request = {
                    'request_index': f"CONTROL_{control_file_path.stem}",
                    'rinfo': f"nlat={params.get('nlat', '')};slat={params.get('slat', '')};wlon={params.get('wlon', '')};elon={params.get('elon', '')}",
                    'subset_info': {
                        'note': f"Parameter(s):\n{params.get('param', '')}"
                    },
                    'title': f"Control file: {filename}",
                    'description': f"Automated processing of {filename}"
                }
                
                region, variable = get_region_and_variable_from_request_enhanced(mock_request)
                self.logger.debug(f"Extracted from content analysis: {region}/{variable}")
                return region, variable
                
            except Exception as e:
                self.logger.warning(f"Error reading control file content for {filename}: {e}")
            
            # Final fallback
            self.logger.warning(f"Could not extract region/variable from {filename}, using UNKNOWN/unknown")
            return "UNKNOWN", "unknown"
            
        except Exception as e:
            self.logger.error(f"Error extracting region/variable from {control_file_path}: {e}")
            return "UNKNOWN", "unknown"
    
    def _save_control_files_to_db(self, control_files: List[ControlFileInfo]):
        """Save control file information to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for control_info in control_files:
                    cursor.execute("""
                        INSERT OR REPLACE INTO control_files_tracking
                        (file_path, filename, region, variable_type, discovered_at,
                         file_size, last_modified, status, request_id, submission_time,
                         completion_time, error_message, retry_count,
                         processing_duration, download_directory, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        control_info.file_path,
                        control_info.filename,
                        control_info.region,
                        control_info.variable_type,
                        control_info.discovered_at,
                        control_info.file_size,
                        control_info.last_modified,
                        control_info.status,
                        control_info.request_id,
                        control_info.submission_time,
                        control_info.completion_time,
                        # control_info.download_time,  # Removed download_time tracking
                        control_info.error_message,
                        control_info.retry_count,
                        control_info.processing_duration,
                        control_info.download_directory,
                        datetime.now().isoformat()
                    ))
                
                conn.commit()
                self.logger.debug(f"Saved {len(control_files)} control files to database")
                
        except Exception as e:
            self.logger.error(f"Error saving control files to database: {e}")
    
    def _load_tracking_state(self):
        """Load existing tracking state from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Load control files
                cursor.execute("SELECT * FROM control_files_tracking")
                rows = cursor.fetchall()
                
                columns = [desc[0] for desc in cursor.description]
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    
                    control_info = ControlFileInfo(
                        file_path=row_dict['file_path'],
                        filename=row_dict['filename'],
                        region=row_dict['region'],
                        variable_type=row_dict['variable_type'],
                        discovered_at=row_dict['discovered_at'],
                        file_size=row_dict['file_size'],
                        last_modified=row_dict['last_modified'],
                        status=row_dict['status'],
                        request_id=row_dict['request_id'],
                        submission_time=row_dict['submission_time'],
                        completion_time=row_dict['completion_time'],
                        download_time=None,  # Removed download_time tracking
                        error_message=row_dict['error_message'],
                        retry_count=row_dict['retry_count'] or 0,
                        processing_duration=row_dict['processing_duration'],
                        download_directory=row_dict['download_directory']
                    )
                    
                    self.control_files_registry[control_info.file_path] = control_info
                
                self.logger.info(f"Loaded {len(self.control_files_registry)} control files from database")
                
        except Exception as e:
            self.logger.warning(f"Could not load tracking state from database: {e}")
    
    def update_control_file_status(self, file_path: str, status: str, **kwargs):
        """
        Update the status of a control file with additional information.
        
        Args:
            file_path: Path to the control file
            status: New status
            **kwargs: Additional fields to update
        """
        try:
            with self.tracker_lock:
                if file_path in self.control_files_registry:
                    control_info = self.control_files_registry[file_path]
                    control_info.status = status
                    
                    # Update additional fields
                    for key, value in kwargs.items():
                        if hasattr(control_info, key):
                            setattr(control_info, key, value)
                    
                    # Update database
                    self._update_control_file_in_db(control_info)
                    
                    self.logger.info(f"📊 Updated {control_info.filename}: {status}")
                    
                    # Update regional progress
                    self._update_regional_progress(control_info.region)
                else:
                    self.logger.warning(f"Control file not found in registry: {file_path}")
                    
        except Exception as e:
            self.logger.error(f"Error updating control file status: {e}")
    
    def _update_control_file_in_db(self, control_info: ControlFileInfo):
        """Update control file information in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE control_files_tracking
                    SET status = ?, request_id = ?, submission_time = ?,
                        completion_time = ?, error_message = ?,
                        retry_count = ?, processing_duration = ?, download_directory = ?,
                        updated_at = ?
                    WHERE file_path = ?
                """, (
                    control_info.status,
                    control_info.request_id,
                    control_info.submission_time,
                    control_info.completion_time,
                    # control_info.download_time,  # Removed download_time tracking
                    control_info.error_message,
                    control_info.retry_count,
                    control_info.processing_duration,
                    control_info.download_directory,
                    datetime.now().isoformat(),
                    control_info.file_path
                ))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error updating control file in database: {e}")
    
    def _update_regional_progress(self, region: str):
        """Update regional progress statistics."""
        try:
            # Get all control files for this region
            region_files = [
                cf for cf in self.control_files_registry.values()
                if cf.region == region
            ]
            
            if not region_files:
                return
            
            # Calculate statistics
            total_files = len(region_files)
            status_counts = defaultdict(int)
            variable_breakdown = defaultdict(lambda: defaultdict(int))
            processing_times = []
            errors = []
            
            for cf in region_files:
                status_counts[cf.status] += 1
                variable_breakdown[cf.variable_type][cf.status] += 1
                
                if cf.processing_duration:
                    processing_times.append(cf.processing_duration)
                
                if cf.error_message:
                    errors.append(cf.error_message)
            
            # Calculate metrics
            completed = status_counts.get('completed', 0) + status_counts.get('downloaded', 0)
            failed = status_counts.get('failed', 0)
            completion_percentage = (completed / total_files * 100) if total_files > 0 else 0
            success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            # Get region name from config
            region_name = self.config.get('regions', {}).get(region, {}).get('name', region)
            
            # Create or update regional progress
            progress = RegionalProgress(
                region=region,
                region_name=region_name,
                total_control_files=total_files,
                discovered_files=status_counts.get('discovered', 0),
                queued_files=status_counts.get('queued', 0),
                submitted_files=status_counts.get('submitted', 0),
                processing_files=status_counts.get('processing', 0),
                completed_files=status_counts.get('completed', 0),
                failed_files=status_counts.get('failed', 0),
                downloaded_files=status_counts.get('downloaded', 0),
                missing_files=status_counts.get('missing', 0),
                variable_breakdown=dict(variable_breakdown),
                last_updated=datetime.now().isoformat(),
                completion_percentage=completion_percentage,
                success_rate=success_rate,
                average_processing_time=avg_processing_time,
                common_errors=list(set(errors))[:5]  # Top 5 unique errors
            )
            
            # Set first discovered time if not set
            if region not in self.regional_progress:
                progress.first_discovered = min(cf.discovered_at for cf in region_files)
            else:
                progress.first_discovered = self.regional_progress[region].first_discovered
            
            with self.tracker_lock:
                self.regional_progress[region] = progress
            
            # Save to database
            self._save_regional_progress_to_db(progress)
            
        except Exception as e:
            self.logger.error(f"Error updating regional progress for {region}: {e}")
    
    def _save_regional_progress_to_db(self, progress: RegionalProgress):
        """DEPRECATED: regional_progress table has been removed."""
        self.logger.warning("_save_regional_progress_to_db called but regional_progress table has been removed")
        # No longer saving to database - regional progress is now tracked in memory only
        pass
    
    def generate_comprehensive_coverage_report(self) -> CoverageReport:
        """
        Generate a comprehensive coverage report showing complete status of all control files.
        
        Returns:
            CoverageReport with detailed coverage information
        """
        report_start = time.time()
        self.logger.info("📋 Generating comprehensive coverage report...")
        
        try:
            # Ensure we have the latest data
            self.discover_all_control_files()
            
            # Calculate overall statistics
            total_files = len(self.control_files_registry)
            regions = set(cf.region for cf in self.control_files_registry.values())
            variables = set(cf.variable_type for cf in self.control_files_registry.values())
            
            # Categorize files
            missing_files = []
            unprocessed_files = []
            failed_files = []
            
            status_counts = defaultdict(int)
            for cf in self.control_files_registry.values():
                status_counts[cf.status] += 1
                
                if cf.status == 'missing':
                    missing_files.append(cf.file_path)
                elif cf.status in ['discovered', 'queued']:
                    unprocessed_files.append(cf.file_path)
                elif cf.status == 'failed':
                    failed_files.append(cf.file_path)
            
            # Calculate coverage percentage
            processed_files = status_counts.get('completed', 0) + status_counts.get('downloaded', 0)
            coverage_percentage = (processed_files / total_files * 100) if total_files > 0 else 0
            
            # Update all regional progress
            for region in regions:
                self._update_regional_progress(region)
            
            # Variable coverage breakdown
            variable_coverage = defaultdict(lambda: defaultdict(int))
            for cf in self.control_files_registry.values():
                variable_coverage[cf.variable_type][cf.status] += 1
            
            # Generate alerts
            alerts = []
            if missing_files:
                alerts.append(f"⚠️ {len(missing_files)} control files are missing")
            if len(unprocessed_files) > 0:
                alerts.append(f"📋 {len(unprocessed_files)} control files are unprocessed")
            if len(failed_files) > 10:  # Alert if many failures
                alerts.append(f"❌ {len(failed_files)} control files have failed")
            
            # Check for regions with low completion rates
            for region, progress in self.regional_progress.items():
                if progress.completion_percentage < 50 and progress.total_control_files > 0:
                    alerts.append(f"🔴 Region {region} has low completion rate: {progress.completion_percentage:.1f}%")
            
            # Create coverage report
            report = CoverageReport(
                total_control_files_discovered=total_files,
                total_regions=len(regions),
                total_variables=len(variables),
                coverage_percentage=coverage_percentage,
                missing_files=missing_files,
                unprocessed_files=unprocessed_files,
                failed_files=failed_files,
                regional_coverage=dict(self.regional_progress),
                variable_coverage=dict(variable_coverage),
                generated_at=datetime.now().isoformat(),
                scan_duration=time.time() - report_start,
                alerts=alerts
            )
            
            # Save report to database
            self._save_coverage_report_to_db(report)
            
            # Add to history
            self.coverage_history.append(report)
            
            # Keep only last 10 reports in memory
            if len(self.coverage_history) > 10:
                self.coverage_history = self.coverage_history[-10:]
            
            self.logger.info(f"✅ Coverage report generated: {coverage_percentage:.1f}% coverage, {len(alerts)} alerts")
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating coverage report: {e}")
            # Return empty report on error
            return CoverageReport(
                total_control_files_discovered=0,
                total_regions=0,
                total_variables=0,
                coverage_percentage=0.0,
                missing_files=[],
                unprocessed_files=[],
                failed_files=[],
                regional_coverage={},
                variable_coverage={},
                generated_at=datetime.now().isoformat(),
                scan_duration=time.time() - report_start,
                alerts=[f"Error generating report: {e}"]
            )
    
    def _save_coverage_report_to_db(self, report: CoverageReport):
        """Save coverage report to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO coverage_reports
                    (total_control_files_discovered, total_regions, total_variables,
                     coverage_percentage, missing_files, unprocessed_files, failed_files,
                     regional_coverage, variable_coverage, scan_duration, alerts, generated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report.total_control_files_discovered,
                    report.total_regions,
                    report.total_variables,
                    report.coverage_percentage,
                    json.dumps(report.missing_files),
                    json.dumps(report.unprocessed_files),
                    json.dumps(report.failed_files),
                    json.dumps({k: asdict(v) for k, v in report.regional_coverage.items()}),
                    json.dumps(report.variable_coverage),
                    report.scan_duration,
                    json.dumps(report.alerts),
                    report.generated_at
                ))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error saving coverage report to database: {e}")
    
    def verify_control_file_coverage(self, expected_regions: Optional[List[str]] = None,
                                   expected_variables: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Verify that all expected control files are present and accounted for.
        
        Args:
            expected_regions: List of expected regions (optional)
            expected_variables: List of expected weather variables (optional)
            
        Returns:
            Dictionary with verification results
        """
        self.logger.info("🔍 Verifying control file coverage...")
        
        try:
            # Discover all files first
            discovered_files = self.discover_all_control_files()
            
            # Get actual regions and variables
            actual_regions = set(cf.region for cf in discovered_files.values())
            actual_variables = set(cf.variable_type for cf in discovered_files.values())
            
            verification_results = {
                "verification_timestamp": datetime.now().isoformat(),
                "total_files_found": len(discovered_files),
                "actual_regions": sorted(actual_regions),
                "actual_variables": sorted(actual_variables),
                "coverage_issues": [],
                "missing_combinations": [],
                "unexpected_files": [],
                "verification_passed": True
            }
            
            # Check expected regions
            if expected_regions:
                missing_regions = set(expected_regions) - actual_regions
                unexpected_regions = actual_regions - set(expected_regions)
                
                if missing_regions:
                    verification_results["coverage_issues"].append(
                        f"Missing regions: {sorted(missing_regions)}"
                    )
                    verification_results["verification_passed"] = False
                
                if unexpected_regions:
                    verification_results["coverage_issues"].append(
                        f"Unexpected regions: {sorted(unexpected_regions)}"
                    )
            
            # Check expected variables
            if expected_variables:
                missing_variables = set(expected_variables) - actual_variables
                unexpected_variables = actual_variables - set(expected_variables)
                
                if missing_variables:
                    verification_results["coverage_issues"].append(
                        f"Missing variables: {sorted(missing_variables)}"
                    )
                    verification_results["verification_passed"] = False
                
                if unexpected_variables:
                    verification_results["coverage_issues"].append(
                        f"Unexpected variables: {sorted(unexpected_variables)}"
                    )
            
            # Check for missing region/variable combinations
            if expected_regions and expected_variables:
                expected_combinations = set()
                for region in expected_regions:
                    for variable in expected_variables:
                        expected_combinations.add((region, variable))
                
                actual_combinations = set()
                for cf in discovered_files.values():
                    actual_combinations.add((cf.region, cf.variable_type))
                
                missing_combinations = expected_combinations - actual_combinations
                if missing_combinations:
                    verification_results["missing_combinations"] = [
                        f"{region}_{variable}" for region, variable in sorted(missing_combinations)
                    ]
                    verification_results["verification_passed"] = False
            
            # Log results
            if verification_results["verification_passed"]:
                self.logger.info("✅ Control file coverage verification PASSED")
            else:
                self.logger.warning("⚠️ Control file coverage verification FAILED")
                for issue in verification_results["coverage_issues"]:
                    self.logger.warning(f"  - {issue}")
            
            return verification_results
            
        except Exception as e:
            self.logger.error(f"Error during coverage verification: {e}")
            return {
                "verification_timestamp": datetime.now().isoformat(),
                "error": str(e),
                "verification_passed": False
            }
    
    def get_unprocessed_files(self) -> List[ControlFileInfo]:
        """Get list of control files that haven't been processed yet."""
        unprocessed_statuses = ['discovered', 'queued']
        return [
            cf for cf in self.control_files_registry.values()
            if cf.status in unprocessed_statuses
        ]
    
    def get_failed_files(self) -> List[ControlFileInfo]:
        """Get list of control files that have failed processing."""
        return [
            cf for cf in self.control_files_registry.values()
            if cf.status == 'failed'
        ]
    
    def get_regional_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of progress by region."""
        summary = {}
        
        for region, progress in self.regional_progress.items():
            summary[region] = {
                "region_name": progress.region_name,
                "total_files": progress.total_control_files,
                "completion_percentage": progress.completion_percentage,
                "success_rate": progress.success_rate,
                "status_breakdown": {
                    "discovered": progress.discovered_files,
                    "queued": progress.queued_files,
                    "submitted": progress.submitted_files,
                    "processing": progress.processing_files,
                    "completed": progress.completed_files,
                    "failed": progress.failed_files,
                    "downloaded": progress.downloaded_files
                },
                "variable_breakdown": progress.variable_breakdown,
                "last_updated": progress.last_updated
            }
        
        return summary
    
    def get_tracking_statistics(self) -> Dict[str, Any]:
        """Get comprehensive tracking statistics."""
        try:
            total_files = len(self.control_files_registry)
            if total_files == 0:
                return {"error": "No control files tracked"}
            
            # Status distribution
            status_counts = defaultdict(int)
            for cf in self.control_files_registry.values():
                status_counts[cf.status] += 1
            
            # Regional distribution
            regional_counts = defaultdict(int)
            for cf in self.control_files_registry.values():
                regional_counts[cf.region] += 1
            
            # Variable distribution
            variable_counts = defaultdict(int)
            for cf in self.control_files_registry.values():
                variable_counts[cf.variable_type] += 1
            
            # Calculate overall metrics
            completed = status_counts.get('completed', 0) + status_counts.get('downloaded', 0)
            failed = status_counts.get('failed', 0)
            processing = status_counts.get('processing', 0) + status_counts.get('submitted', 0)
            pending = status_counts.get('discovered', 0) + status_counts.get('queued', 0)
            
            completion_rate = (completed / total_files * 100) if total_files > 0 else 0
            failure_rate = (failed / total_files * 100) if total_files > 0 else 0
            
            return {
                "timestamp": datetime.now().isoformat(),
                "total_control_files": total_files,
                "completion_rate": completion_rate,
                "failure_rate": failure_rate,
                "status_distribution": dict(status_counts),
                "regional_distribution": dict(regional_counts),
                "variable_distribution": dict(variable_counts),
                "summary": {
                    "completed": completed,
                    "failed": failed,
                    "processing": processing,
                    "pending": pending
                },
                "regions_tracked": len(self.regional_progress),
                "latest_coverage_report": self.coverage_history[-1] if self.coverage_history else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting tracking statistics: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
    
    def sync_with_batch_system(self, batch_system):
        """
        Synchronize tracking data with the batch automation system.
        
        Args:
            batch_system: BatchAutomationSystem instance
        """
        try:
            self.logger.info("🔄 Synchronizing with batch automation system...")
            
            sync_count = 0
            for control_file, request_status in batch_system.requests_state.items():
                if control_file in self.control_files_registry:
                    # Update tracking info from batch system
                    updates = {
                        'status': request_status.status,
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
                            start = datetime.fromisoformat(request_status.submission_time)
                            end = datetime.fromisoformat(request_status.completion_time)
                            duration_hours = (end - start).total_seconds() / 3600
                            updates['processing_duration'] = duration_hours
                        except:
                            pass
                    
                    self.update_control_file_status(control_file, request_status.status, **updates)
                    sync_count += 1
                else:
                    self.logger.warning(f"Control file in batch system not found in tracker: {control_file}")
            
            self.logger.info(f"✅ Synchronized {sync_count} control files with batch system")
            
        except Exception as e:
            self.logger.error(f"Error synchronizing with batch system: {e}")
    
    def generate_alerts(self) -> List[str]:
        """Generate alerts for issues that need attention."""
        alerts = []
        
        try:
            # Check for unprocessed files
            unprocessed = self.get_unprocessed_files()
            if len(unprocessed) > 0:
                alerts.append(f"📋 {len(unprocessed)} control files are still unprocessed")
            
            # Check for failed files
            failed = self.get_failed_files()
            if len(failed) > 0:
                alerts.append(f"❌ {len(failed)} control files have failed processing")
            
            # Check for regions with issues
            for region, progress in self.regional_progress.items():
                if progress.total_control_files > 0:
                    if progress.completion_percentage < 25:
                        alerts.append(f"🔴 Region {region} has very low completion: {progress.completion_percentage:.1f}%")
                    elif progress.failure_rate > 50:
                        alerts.append(f"⚠️ Region {region} has high failure rate: {progress.success_rate:.1f}% success")
            
            # Check for stalled processing
            current_time = datetime.now()
            for cf in self.control_files_registry.values():
                if cf.status == 'processing' and cf.submission_time:
                    try:
                        submission_time = datetime.fromisoformat(cf.submission_time)
                        hours_processing = (current_time - submission_time).total_seconds() / 3600
                        if hours_processing > 24:  # Processing for more than 24 hours
                            alerts.append(f"⏰ {cf.filename} has been processing for {hours_processing:.1f} hours")
                    except:
                        pass
            
        except Exception as e:
            alerts.append(f"Error generating alerts: {e}")
        
        return alerts
    
    def print_comprehensive_status(self):
        """Print a comprehensive status report to console."""
        try:
            print("\n" + "="*100)
            print("COMPREHENSIVE TRACKING SYSTEM STATUS")
            print("="*100)
            
            # Overall statistics
            stats = self.get_tracking_statistics()
            if "error" not in stats:
                print(f"📊 Total Control Files: {stats['total_control_files']}")
                print(f"✅ Completion Rate: {stats['completion_rate']:.1f}%")
                print(f"❌ Failure Rate: {stats['failure_rate']:.1f}%")
                print(f"🗺️ Regions Tracked: {stats['regions_tracked']}")
                
                print(f"\n📈 Status Distribution:")
                for status, count in stats['status_distribution'].items():
                    percentage = (count / stats['total_control_files'] * 100)
                    print(f"  {status.capitalize()}: {count} ({percentage:.1f}%)")
                
                print(f"\n🌍 Regional Distribution:")
                for region, count in sorted(stats['regional_distribution'].items()):
                    print(f"  {region}: {count} files")
                
                print(f"\n🌡️ Variable Distribution:")
                for variable, count in sorted(stats['variable_distribution'].items()):
                    print(f"  {variable}: {count} files")
            
            # Regional progress
            print(f"\n🗺️ REGIONAL PROGRESS SUMMARY:")
            print("-" * 80)
            for region, progress in sorted(self.regional_progress.items()):
                print(f"{region:8} | {progress.completion_percentage:6.1f}% | "
                      f"{progress.completed_files:3}/{progress.total_control_files:3} | "
                      f"Success: {progress.success_rate:5.1f}% | "
                      f"Variables: {len(progress.variable_breakdown)}")
            
            # Alerts
            alerts = self.generate_alerts()
            if alerts:
                print(f"\n🚨 ALERTS ({len(alerts)}):")
                print("-" * 50)
                for alert in alerts:
                    print(f"  {alert}")
            else:
                print(f"\n✅ No alerts - system is running smoothly!")
            
            print("="*100)
            
        except Exception as e:
            print(f"Error printing status: {e}")


def create_comprehensive_tracker(control_files_dir: str = "./control_files",
                               db_path: str = "./data/automation_state.db",
                               config: Optional[Dict] = None) -> ComprehensiveTracker:
    """
    Factory function to create a ComprehensiveTracker instance.
    
    Args:
        control_files_dir: Directory containing control files
        db_path: Path to SQLite database
        config: Optional configuration dictionary
        
    Returns:
        Configured ComprehensiveTracker instance
    """
    return ComprehensiveTracker(control_files_dir, db_path, config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Comprehensive Control File Tracker')
    parser.add_argument('--discover', action='store_true',
                       help='Discover all control files')
    parser.add_argument('--report', action='store_true',
                       help='Generate coverage report')
    parser.add_argument('--verify', action='store_true',
                       help='Verify control file coverage')
    parser.add_argument('--status', action='store_true',
                       help='Show comprehensive status')
    parser.add_argument('--control-files-dir', default='./control_files',
                       help='Control files directory')
    parser.add_argument('--db-path', default='./data/automation_state.db',
                       help='Database path')
    
    args = parser.parse_args()
    
    # Create tracker
    tracker = create_comprehensive_tracker(args.control_files_dir, args.db_path)
    
    try:
        if args.discover:
            print("=== Discovering Control Files ===")
            files = tracker.discover_all_control_files(force_rescan=True)
            print(f"Discovered {len(files)} control files")
            
        elif args.report:
            print("=== Generating Coverage Report ===")
            report = tracker.generate_comprehensive_coverage_report()
            print(f"Coverage: {report.coverage_percentage:.1f}%")
            print(f"Regions: {report.total_regions}")
            print(f"Variables: {report.total_variables}")
            if report.alerts:
                print("Alerts:")
                for alert in report.alerts:
                    print(f"  - {alert}")
                    
        elif args.verify:
            print("=== Verifying Coverage ===")
            # Example expected regions and variables
            expected_regions = ['CISO', 'ERCOT', 'PJM', 'MISO']
            expected_variables = ['dswrf', 'ugrd_vgrd', 'tmp_dpt', 'apcp']
            
            results = tracker.verify_control_file_coverage(expected_regions, expected_variables)
            print(f"Verification: {'PASSED' if results['verification_passed'] else 'FAILED'}")
            if results.get('coverage_issues'):
                for issue in results['coverage_issues']:
                    print(f"  - {issue}")
                    
        elif args.status:
            print("=== Comprehensive Status ===")
            tracker.print_comprehensive_status()
            
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")