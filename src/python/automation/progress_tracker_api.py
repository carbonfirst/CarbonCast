#!/usr/bin/env python3
"""
Progress Tracker API for RDA Automation System

This module provides specialized API endpoints for comprehensive progress tracking
and monitoring. It dynamically calculates progress based on control files and
provides real-time completion estimates and trend analysis.

Key Features:
- Dynamic progress calculation based on control_files folder contents
- Real-time completion status across all regions and weather variables
- Progress as both absolute numbers and percentages
- Estimated completion times based on current processing rates
- Regional and variable-specific progress breakdowns
- Historical progress trends and analytics
"""

import os
import sys
import json
import sqlite3
import logging
import glob
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import threading
import re

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.enhanced_database_schema import create_enhanced_schema_manager


@dataclass
class ProgressSnapshot:
    """Data class for progress snapshot information."""
    timestamp: str
    total_control_files: int
    completed_files: int
    downloaded_files: int
    missing_files: int
    completion_percentage: float
    download_percentage: float
    estimated_completion_time: Optional[str]
    processing_rate_per_hour: float


@dataclass
class RegionalProgress:
    """Data class for regional progress information."""
    region: str
    region_name: str
    total_control_files: int
    completed_files: int
    downloaded_files: int
    missing_files: int
    success_rate: float
    completion_percentage: float
    variable_breakdown: Dict[str, int]
    first_discovered: Optional[str]
    last_updated: str
    estimated_completion: Optional[str]


@dataclass
class VariableProgress:
    """Data class for weather variable progress information."""
    variable_type: str
    variable_name: str
    total_files: int
    completed_files: int
    downloaded_files: int
    completion_percentage: float
    active_regions: List[str]
    fastest_region: Optional[str]
    slowest_region: Optional[str]
    average_processing_time: float


class ProgressTrackerAPI:
    """
    Specialized API for progress tracking and monitoring.
    
    Provides dynamic progress calculation, completion estimates,
    and comprehensive progress analytics.
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db", 
                 control_files_path: str = "./control_files"):
        """
        Initialize the Progress Tracker API.
        
        Args:
            db_path: Path to the SQLite database file
            control_files_path: Path to the control files directory
        """
        self.db_path = db_path
        self.control_files_path = control_files_path
        self.logger = self._setup_logging()
        
        # Initialize database schema manager
        self.schema_manager = create_enhanced_schema_manager(db_path)
        
        # Thread safety
        self.api_lock = threading.Lock()
        
        # Cache for control files analysis
        self._control_files_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 300  # 5 minutes
        
        self.logger.info("Progress Tracker API initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the progress tracker API."""
        logger = logging.getLogger('progress_tracker_api')
        
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
    
    def _analyze_control_files(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Analyze control files directory to get comprehensive file information.
        
        Args:
            force_refresh: Force refresh of cached data
            
        Returns:
            Dictionary containing control files analysis
        """
        current_time = datetime.now()
        
        # Check cache validity
        if (not force_refresh and self._control_files_cache and self._cache_timestamp and
            (current_time - self._cache_timestamp).total_seconds() < self._cache_ttl):
            return self._control_files_cache
        
        try:
            control_files_analysis = {
                'total_files': 0,
                'regions': {},
                'variables': {},
                'region_variable_matrix': {},
                'file_list': [],
                'analysis_timestamp': current_time.isoformat()
            }
            
            # Check if control files directory exists
            if not os.path.exists(self.control_files_path):
                self.logger.warning(f"Control files directory not found: {self.control_files_path}")
                return control_files_analysis
            
            # Get all .ctl files
            control_files = glob.glob(os.path.join(self.control_files_path, "*.ctl"))
            control_files_analysis['total_files'] = len(control_files)
            
            regions = defaultdict(int)
            variables = defaultdict(int)
            region_variable_matrix = defaultdict(lambda: defaultdict(int))
            
            for file_path in control_files:
                filename = os.path.basename(file_path)
                file_info = {
                    'filename': filename,
                    'full_path': file_path,
                    'size': os.path.getsize(file_path),
                    'modified_time': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                }
                
                # Parse filename to extract region and variable
                # Expected format: REGION_variable_control.ctl
                match = re.match(r'^([A-Z0-9]+)_([a-z]+)_control\.ctl$', filename)
                if match:
                    region = match.group(1)
                    variable = match.group(2)
                    
                    file_info['region'] = region
                    file_info['variable'] = variable
                    
                    regions[region] += 1
                    variables[variable] += 1
                    region_variable_matrix[region][variable] += 1
                else:
                    # Try alternative parsing for different filename patterns
                    parts = filename.replace('.ctl', '').split('_')
                    if len(parts) >= 2:
                        region = parts[0]
                        variable = '_'.join(parts[1:-1]) if len(parts) > 2 else parts[1]
                        
                        file_info['region'] = region
                        file_info['variable'] = variable
                        
                        regions[region] += 1
                        variables[variable] += 1
                        region_variable_matrix[region][variable] += 1
                    else:
                        file_info['region'] = 'UNKNOWN'
                        file_info['variable'] = 'unknown'
                
                control_files_analysis['file_list'].append(file_info)
            
            # Convert defaultdicts to regular dicts
            control_files_analysis['regions'] = dict(regions)
            control_files_analysis['variables'] = dict(variables)
            control_files_analysis['region_variable_matrix'] = {
                region: dict(variables) for region, variables in region_variable_matrix.items()
            }
            
            # Cache the results
            self._control_files_cache = control_files_analysis
            self._cache_timestamp = current_time
            
            self.logger.info(f"Analyzed {len(control_files)} control files: "
                           f"{len(regions)} regions, {len(variables)} variables")
            
            return control_files_analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing control files: {e}")
            return {
                'total_files': 0,
                'regions': {},
                'variables': {},
                'region_variable_matrix': {},
                'file_list': [],
                'error': str(e),
                'analysis_timestamp': current_time.isoformat()
            }
    
    def get_overall_progress(self) -> Dict[str, Any]:
        """
        Get overall system progress across all regions and variables.
        
        Returns:
            Dictionary containing overall progress information
        """
        try:
            # Get control files analysis
            control_files_analysis = self._analyze_control_files()
            total_control_files = control_files_analysis['total_files']
            
            if total_control_files == 0:
                return {
                    'progress': {
                        'total_control_files': 0,
                        'completed_files': 0,
                        'downloaded_files': 0,
                        'missing_files': 0,
                        'completion_percentage': 0.0,
                        'download_percentage': 0.0
                    },
                    'error': 'No control files found',
                    'generated_at': datetime.now().isoformat()
                }
            
            # Get progress from database (if progress snapshots exist)
            completed_files = 0
            downloaded_files = 0
            
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Try to get latest progress snapshot
                    cursor.execute("""
                        SELECT 
                            completed_requests,
                            total_requests
                        FROM progress_snapshots
                        WHERE snapshot_type = 'overall'
                        ORDER BY snapshot_timestamp DESC
                        LIMIT 1
                    """)
                    
                    snapshot = cursor.fetchone()
                    if snapshot:
                        completed_files = snapshot['completed_requests'] or 0
                        # Use total from snapshot if available, otherwise use control files count
                        if snapshot['total_requests']:
                            total_control_files = max(total_control_files, snapshot['total_requests'])
                    
                    # Also check downloaded files directory
                    downloaded_files = self._count_downloaded_files()
                    
            except Exception as e:
                self.logger.debug(f"Could not get progress from database: {e}")
            
            # Calculate metrics
            missing_files = max(0, total_control_files - completed_files)
            completion_percentage = (completed_files / total_control_files * 100) if total_control_files > 0 else 0
            download_percentage = (downloaded_files / total_control_files * 100) if total_control_files > 0 else 0
            
            # Estimate completion time based on current rate
            estimated_completion_time = self._estimate_completion_time(
                total_control_files, completed_files
            )
            
            # Calculate processing rate
            processing_rate = self._calculate_processing_rate()
            
            return {
                'progress': {
                    'total_control_files': total_control_files,
                    'completed_files': completed_files,
                    'downloaded_files': downloaded_files,
                    'missing_files': missing_files,
                    'completion_percentage': round(completion_percentage, 2),
                    'download_percentage': round(download_percentage, 2),
                    'estimated_completion_time': estimated_completion_time,
                    'processing_rate_per_hour': round(processing_rate, 2)
                },
                'breakdown': {
                    'total_regions': len(control_files_analysis['regions']),
                    'total_variables': len(control_files_analysis['variables']),
                    'regions_with_files': len([r for r, count in control_files_analysis['regions'].items() if count > 0])
                },
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting overall progress: {e}")
            return {
                'progress': {},
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def get_regional_progress(self) -> Dict[str, Any]:
        """
        Get detailed progress breakdown by region.
        
        Returns:
            Dictionary containing regional progress information
        """
        try:
            # Get control files analysis
            control_files_analysis = self._analyze_control_files()
            
            regional_progress = []
            
            for region, total_files in control_files_analysis['regions'].items():
                if region == 'UNKNOWN':
                    continue
                
                # Get variable breakdown for this region
                variable_breakdown = control_files_analysis['region_variable_matrix'].get(region, {})
                
                # Get completion data from database or filesystem
                completed_files, downloaded_files = self._get_region_completion_data(region)
                
                missing_files = max(0, total_files - completed_files)
                success_rate = (completed_files / total_files * 100) if total_files > 0 else 0
                completion_percentage = success_rate
                
                # Estimate completion time for this region
                estimated_completion = self._estimate_region_completion_time(
                    region, total_files, completed_files
                )
                
                regional_progress.append({
                    'region': region,
                    'region_name': self._get_region_display_name(region),
                    'total_control_files': total_files,
                    'completed_files': completed_files,
                    'downloaded_files': downloaded_files,
                    'missing_files': missing_files,
                    'success_rate': round(success_rate, 1),
                    'completion_percentage': round(completion_percentage, 1),
                    'variable_breakdown': variable_breakdown,
                    'first_discovered': None,  # Could be enhanced with filesystem timestamps
                    'last_updated': datetime.now().isoformat(),
                    'estimated_completion': estimated_completion
                })
            
            # Sort by completion percentage (descending)
            regional_progress.sort(key=lambda x: x['completion_percentage'], reverse=True)
            
            return {
                'regional_progress': regional_progress,
                'summary': {
                    'total_regions': len(regional_progress),
                    'completed_regions': len([r for r in regional_progress if r['completion_percentage'] == 100]),
                    'in_progress_regions': len([r for r in regional_progress if 0 < r['completion_percentage'] < 100]),
                    'pending_regions': len([r for r in regional_progress if r['completion_percentage'] == 0])
                },
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting regional progress: {e}")
            return {
                'regional_progress': [],
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def get_variable_progress(self) -> Dict[str, Any]:
        """
        Get detailed progress breakdown by weather variable.
        
        Returns:
            Dictionary containing variable progress information
        """
        try:
            # Get control files analysis
            control_files_analysis = self._analyze_control_files()
            
            variable_progress = []
            
            for variable, total_files in control_files_analysis['variables'].items():
                if variable == 'unknown':
                    continue
                
                # Get regions that have this variable
                active_regions = []
                for region, variables in control_files_analysis['region_variable_matrix'].items():
                    if variable in variables:
                        active_regions.append(region)
                
                # Get completion data for this variable across all regions
                completed_files, downloaded_files = self._get_variable_completion_data(variable)
                
                completion_percentage = (completed_files / total_files * 100) if total_files > 0 else 0
                
                # Find fastest and slowest regions for this variable
                fastest_region, slowest_region = self._get_variable_region_performance(variable, active_regions)
                
                # Calculate average processing time
                avg_processing_time = self._get_variable_avg_processing_time(variable)
                
                variable_progress.append({
                    'variable_type': variable,
                    'variable_name': self._get_variable_display_name(variable),
                    'total_files': total_files,
                    'completed_files': completed_files,
                    'downloaded_files': downloaded_files,
                    'completion_percentage': round(completion_percentage, 1),
                    'active_regions': active_regions,
                    'fastest_region': fastest_region,
                    'slowest_region': slowest_region,
                    'average_processing_time': round(avg_processing_time, 2)
                })
            
            # Sort by completion percentage (descending)
            variable_progress.sort(key=lambda x: x['completion_percentage'], reverse=True)
            
            return {
                'variable_progress': variable_progress,
                'summary': {
                    'total_variables': len(variable_progress),
                    'completed_variables': len([v for v in variable_progress if v['completion_percentage'] == 100]),
                    'in_progress_variables': len([v for v in variable_progress if 0 < v['completion_percentage'] < 100]),
                    'pending_variables': len([v for v in variable_progress if v['completion_percentage'] == 0])
                },
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting variable progress: {e}")
            return {
                'variable_progress': [],
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def get_progress_trends(self, hours_back: int = 24, interval_hours: int = 1) -> Dict[str, Any]:
        """
        Get progress trends over time.
        
        Args:
            hours_back: Number of hours to analyze
            interval_hours: Interval for trend buckets
            
        Returns:
            Dictionary containing progress trend data
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get progress snapshots from database
                cursor.execute("""
                    SELECT 
                        snapshot_timestamp,
                        total_requests,
                        completed_requests,
                        success_rate,
                        throughput_per_hour
                    FROM progress_snapshots
                    WHERE snapshot_type = 'overall'
                    AND snapshot_timestamp >= ?
                    ORDER BY snapshot_timestamp ASC
                """, ((datetime.now() - timedelta(hours=hours_back)).isoformat(),))
                
                snapshots = cursor.fetchall()
                
                trends = []
                for snapshot in snapshots:
                    completion_percentage = (
                        snapshot['completed_requests'] / snapshot['total_requests'] * 100
                        if snapshot['total_requests'] > 0 else 0
                    )
                    
                    trends.append({
                        'timestamp': snapshot['snapshot_timestamp'],
                        'total_requests': snapshot['total_requests'],
                        'completed_requests': snapshot['completed_requests'],
                        'completion_percentage': round(completion_percentage, 2),
                        'success_rate': snapshot['success_rate'],
                        'throughput_per_hour': snapshot['throughput_per_hour']
                    })
                
                # Calculate trend analysis
                trend_analysis = self._analyze_progress_trends(trends)
                
                return {
                    'trends': trends,
                    'analysis': trend_analysis,
                    'time_window': {
                        'hours_back': hours_back,
                        'interval_hours': interval_hours,
                        'total_snapshots': len(trends)
                    },
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting progress trends: {e}")
            return {
                'trends': [],
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def create_progress_snapshot(self, snapshot_type: str = "overall") -> Dict[str, Any]:
        """
        Create a progress snapshot for trend analysis.
        
        Args:
            snapshot_type: Type of snapshot to create
            
        Returns:
            Dictionary containing snapshot creation result
        """
        try:
            # Get current progress data
            overall_progress = self.get_overall_progress()
            
            if 'error' in overall_progress:
                return {
                    'success': False,
                    'error': overall_progress['error']
                }
            
            progress_data = overall_progress['progress']
            
            # Calculate additional metrics
            throughput_per_hour = progress_data.get('processing_rate_per_hour', 0)
            success_rate = progress_data.get('completion_percentage', 0)
            
            # Insert snapshot into database
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO progress_snapshots (
                        snapshot_type, snapshot_scope, snapshot_timestamp,
                        total_requests, completed_requests, failed_requests,
                        success_rate, throughput_per_hour, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    snapshot_type,
                    "system_wide",
                    datetime.now().isoformat(),
                    progress_data['total_control_files'],
                    progress_data['completed_files'],
                    progress_data['missing_files'],
                    success_rate,
                    throughput_per_hour,
                    json.dumps({
                        'downloaded_files': progress_data['downloaded_files'],
                        'download_percentage': progress_data['download_percentage'],
                        'estimated_completion_time': progress_data['estimated_completion_time']
                    })
                ))
                
                snapshot_id = cursor.lastrowid
                conn.commit()
                
                return {
                    'success': True,
                    'snapshot_id': snapshot_id,
                    'snapshot_type': snapshot_type,
                    'timestamp': datetime.now().isoformat(),
                    'data': progress_data
                }
                
        except Exception as e:
            self.logger.error(f"Error creating progress snapshot: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _count_downloaded_files(self) -> int:
        """Count actual downloaded files from filesystem."""
        try:
            downloaded_files_dir = "downloaded_files"
            if not os.path.exists(downloaded_files_dir):
                return 0
            
            total_files = 0
            for root, dirs, files in os.walk(downloaded_files_dir):
                # Count common weather data file formats
                for file in files:
                    if file.endswith(('.nc', '.grb', '.grib', '.dat', '.bin', '.h5', '.hdf')):
                        total_files += 1
            
            return total_files
            
        except Exception as e:
            self.logger.error(f"Error counting downloaded files: {e}")
            return 0
    
    def _get_region_completion_data(self, region: str) -> Tuple[int, int]:
        """Get completion data for a specific region."""
        # This is a simplified implementation
        # In a real system, this would query the database for actual completion data
        
        # Check if region has downloaded files
        downloaded_files_dir = f"downloaded_files/{region}"
        downloaded_files = 0
        
        if os.path.exists(downloaded_files_dir):
            for root, dirs, files in os.walk(downloaded_files_dir):
                downloaded_files += len([f for f in files if f.endswith(('.nc', '.grb', '.grib', '.dat', '.bin'))])
        
        # For now, assume completed_files equals downloaded_files
        # This could be enhanced with database queries
        completed_files = downloaded_files
        
        return completed_files, downloaded_files
    
    def _get_variable_completion_data(self, variable: str) -> Tuple[int, int]:
        """Get completion data for a specific variable across all regions."""
        completed_files = 0
        downloaded_files = 0
        
        # This is a simplified implementation
        # In a real system, this would aggregate data across all regions for this variable
        
        try:
            downloaded_files_dir = "downloaded_files"
            if os.path.exists(downloaded_files_dir):
                for region_dir in os.listdir(downloaded_files_dir):
                    region_path = os.path.join(downloaded_files_dir, region_dir)
                    if os.path.isdir(region_path):
                        # Look for variable-specific subdirectory
                        variable_path = os.path.join(region_path, variable)
                        if os.path.exists(variable_path):
                            for root, dirs, files in os.walk(variable_path):
                                file_count = len([f for f in files if f.endswith(('.nc', '.grb', '.grib', '.dat', '.bin'))])
                                downloaded_files += file_count
                                completed_files += file_count
        except Exception as e:
            self.logger.debug(f"Error getting variable completion data for {variable}: {e}")
        
        return completed_files, downloaded_files
    
    def _estimate_completion_time(self, total_files: int, completed_files: int) -> Optional[str]:
        """Estimate completion time based on current processing rate."""
        if completed_files >= total_files:
            return None  # Already completed
        
        remaining_files = total_files - completed_files
        processing_rate = self._calculate_processing_rate()
        
        if processing_rate <= 0:
            return None  # Cannot estimate
        
        hours_remaining = remaining_files / processing_rate
        estimated_completion = datetime.now() + timedelta(hours=hours_remaining)
        
        return estimated_completion.isoformat()
    
    def _estimate_region_completion_time(self, region: str, total_files: int, completed_files: int) -> Optional[str]:
        """Estimate completion time for a specific region."""
        # Simplified implementation - could be enhanced with region-specific rates
        return self._estimate_completion_time(total_files, completed_files)
    
    def _calculate_processing_rate(self) -> float:
        """Calculate current processing rate (files per hour)."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get recent progress snapshots to calculate rate
                cursor.execute("""
                    SELECT 
                        snapshot_timestamp,
                        completed_requests
                    FROM progress_snapshots
                    WHERE snapshot_type = 'overall'
                    AND snapshot_timestamp >= ?
                    ORDER BY snapshot_timestamp DESC
                    LIMIT 10
                """, ((datetime.now() - timedelta(hours=24)).isoformat(),))
                
                snapshots = cursor.fetchall()
                
                if len(snapshots) < 2:
                    return 1.0  # Default rate
                
                # Calculate rate based on most recent snapshots
                latest = snapshots[0]
                previous = snapshots[-1]
                
                time_diff = datetime.fromisoformat(latest['snapshot_timestamp']) - datetime.fromisoformat(previous['snapshot_timestamp'])
                hours_diff = time_diff.total_seconds() / 3600
                
                if hours_diff > 0:
                    files_diff = latest['completed_requests'] - previous['completed_requests']
                    return max(0, files_diff / hours_diff)
                
        except Exception as e:
            self.logger.debug(f"Error calculating processing rate: {e}")
        
        return 1.0  # Default rate
    
    def _get_variable_region_performance(self, variable: str, regions: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Get fastest and slowest regions for a variable."""
        # Simplified implementation
        # In a real system, this would analyze completion rates per region
        return None, None
    
    def _get_variable_avg_processing_time(self, variable: str) -> float:
        """Get average processing time for a variable."""
        # Simplified implementation
        return 2.5  # Default 2.5 hours
    
    def _get_region_display_name(self, region: str) -> str:
        """Get display name for a region."""
        region_names = {
            'CISO': 'California ISO',
            'ERCOT': 'Electric Reliability Council of Texas',
            'PJM': 'PJM Interconnection',
            'MISO': 'Midcontinent ISO',
            'NYISO': 'New York ISO',
            'ISNE': 'ISO New England',
            'PACW': 'PacifiCorp West',
            'AECI': 'Associated Electric Cooperative',
            'AL': 'Alabama',
            'AT': 'Austria',
            'BE': 'Belgium'
        }
        return region_names.get(region, region.replace('_', ' ').title())
    
    def _get_variable_display_name(self, variable: str) -> str:
        """Get display name for a weather variable."""
        variable_names = {
            'dswrf': 'Downward Solar Radiation Flux',
            'ugrd_vgrd': 'Wind Speed',
            'apcp': 'Accumulated Precipitation',
            'tmp_dpt': 'Temperature',
            'ugrd': 'U-Component Wind',
            'vgrd': 'V-Component Wind'
        }
        return variable_names.get(variable, variable.replace('_', ' ').title())
    
    def _analyze_progress_trends(self, trends: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze progress trends for insights."""
        if len(trends) < 2:
            return {
                'trend_direction': 'insufficient_data',
                'trend_strength': 0,
                'velocity': 0,
                'acceleration': 0
            }
        
        # Calculate trend direction and strength
        recent_progress = [t['completion_percentage'] for t in trends[-5:]]
        older_progress = [t['completion_percentage'] for t in trends[:5]]
        
        recent_avg = sum(recent_progress) / len(recent_progress)
        older_avg = sum(older_progress) / len(older_progress)
        
        if recent_avg > older_avg * 1.1:
            trend_direction = 'accelerating'
        elif recent_avg < older_avg * 0.9:
            trend_direction = 'decelerating'
        else:
            trend_direction = 'steady'
        
        # Calculate velocity (progress per hour)
        if len(trends) >= 2:
            time_diff = datetime.fromisoformat(trends[-1]['timestamp']) - datetime.fromisoformat(trends[0]['timestamp'])
            hours_diff = time_diff.total_seconds() / 3600
            progress_diff = trends[-1]['completion_percentage'] - trends[0]['completion_percentage']
            velocity = progress_diff / hours_diff if hours_diff > 0 else 0
        else:
            velocity = 0
        
        return {
            'trend_direction': trend_direction,
            'trend_strength': abs(recent_avg - older_avg),
            'velocity': round(velocity, 4),
            'acceleration': 0,  # Could be calculated with more sophisticated analysis
            'recent_average': round(recent_avg, 2),
            'historical_average': round(older_avg, 2)
        }


def create_progress_tracker_api(db_path: str = "src/python/data/automation_state.db",
                               control_files_path: str = "./control_files") -> ProgressTrackerAPI:
    """
    Factory function to create a Progress Tracker API.
    
    Args:
        db_path: Path to the SQLite database file
        control_files_path: Path to the control files directory
        
    Returns:
        Configured ProgressTrackerAPI instance
    """
    return ProgressTrackerAPI(db_path, control_files_path)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Progress Tracker API')
    parser.add_argument('--test-overall', action='store_true',
                       help='Test overall progress endpoint')
    parser.add_argument('--test-regional', action='store_true',
                       help='Test regional progress endpoint')
    parser.add_argument('--test-variable', action='store_true',
                       help='Test variable progress endpoint')
    parser.add_argument('--test-trends', action='store_true',
                       help='Test progress trends endpoint')
    parser.add_argument('--create-snapshot', action='store_true',
                       help='Create progress snapshot')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Database path')
    parser.add_argument('--control-files-path', default='./control_files',
                       help='Control files directory path')
    
    args = parser.parse_args()
    
    # Create progress tracker API
    api = create_progress_tracker_api(args.db_path, args.control_files_path)
    
    try:
        if args.test_overall:
            print("=== Testing Overall Progress ===")
            progress = api.get_overall_progress()
            print(json.dumps(progress, indent=2))
            
        elif args.test_regional:
            print("=== Testing Regional Progress ===")
            regional = api.get_regional_progress()
            print(json.dumps(regional, indent=2))
            
        elif args.test_variable:
            print("=== Testing Variable Progress ===")
            variable = api.get_variable_progress()
            print(json.dumps(variable, indent=2))
            
        elif args.test_trends:
            print("=== Testing Progress Trends ===")
            trends = api.get_progress_trends(hours_back=24)
            print(json.dumps(trends, indent=2))
            
        elif args.create_snapshot:
            print("=== Creating Progress Snapshot ===")
            snapshot = api.create_progress_snapshot()
            print(json.dumps(snapshot, indent=2))
            
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")