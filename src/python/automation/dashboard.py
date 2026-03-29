#!/usr/bin/env python3
"""
Enhanced RDA Automation Dashboard

This module provides a comprehensive web-based dashboard for monitoring the RDA automation system
with detailed insights into current requests, regional performance, weather variable analysis,
error management, and retry statistics.

Key Features:
- Current Active Requests with region and weather variable details
- Regional Performance Metrics and insights
- Weather Variable Analysis and performance comparison
- Error Analysis Dashboard with error_manager integration
- Retry Metrics with retry_manager integration
- Real-time updates and interactive filtering
- Comprehensive API endpoints for data access
"""

import os
import sys
import json
import sqlite3
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import threading
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger

# Import existing modules
from automation.error_manager import ErrorManager, create_error_manager
from automation.retry_manager import RetryManager, create_retry_manager
from automation.data_sync import RDADataSyncService, create_data_sync_service
from automation.real_time_sync_engine import RealTimeSyncEngine, create_real_time_sync_engine, DataFreshnessLevel, SyncStatus
from automation.unknown_region_resolver import EnhancedUnknownRegionResolver

# Note: Removed unused error dashboard/visualization imports
# The dashboard now uses only the core working monitoring system

# Import timeline validation services
from automation.timeline_validator import (
    create_timestamp_validation_service,
    create_timeline_validation_rules,
    TimestampValidationService,
    TimelineValidationRules
)
from automation.processing_time_calculator import create_processing_time_calculator, EnhancedProcessingTimeCalculator


@dataclass
class CurrentRequest:
    """Data class for current request information from rda_requests table."""
    id: int
    request_index: str
    request_id: str
    dsid: Optional[str]
    status: str
    date_rqst: Optional[str]
    date_ready: Optional[str]
    date_purge: Optional[str]
    location: Optional[str]
    ncar_contact: Optional[str]
    rinfo: Optional[str]
    subset_note: Optional[str]
    region: Optional[str] = None
    variable_type: Optional[str] = None
    processing_time_hours: Optional[float] = None


@dataclass
class RegionalMetrics:
    """Data class for regional performance metrics from rda_requests."""
    region: str
    total_requests: int
    completed_requests: int
    queued_requests: int
    purged_requests: int
    processing_requests: int
    success_rate: float
    average_processing_time: float
    most_common_variable: str
    date_range: str


@dataclass
class WeatherVariableMetrics:
    """Data class for weather variable performance metrics from rda_requests."""
    variable_type: str
    total_requests: int
    completed_requests: int
    queued_requests: int
    purged_requests: int
    processing_requests: int
    success_rate: float
    average_processing_time: float
    most_active_regions: List[str]
    date_range: str


class EnhancedRDADashboard:
    """
    Enhanced RDA Automation Dashboard with comprehensive metrics and insights.
    
    Provides real-time monitoring of current requests, regional performance,
    weather variable analysis, error management, and retry statistics.
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db", auto_sync: bool = True):
        """
        Initialize the Enhanced RDA Dashboard with Real-Time Sync Engine.
        
        Args:
            db_path: Path to the SQLite database file
            auto_sync: Whether to automatically sync data on startup
        """
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Initialize real-time sync engine (replaces basic data sync service)
        sync_config = {
            'immediate_sync_on_access': True,
            'auto_refresh_stale_data': True,
            'freshness_thresholds': {
                'fresh': 0,         # Immediate sync - no cache delay
                'acceptable': 30,   # 30 seconds acceptable
                'stale': 300,       # 5 minutes stale
                'critical': 1800    # 30 minutes critical
            }
        }
        self.real_time_sync = create_real_time_sync_engine(db_path, sync_config)
        
        # Keep reference to data sync service for compatibility
        self.data_sync_service = self.real_time_sync.data_sync_service
        
        # Perform initial data sync if requested
        if auto_sync:
            self.logger.info("Performing initial real-time data synchronization...")
            sync_result = self.real_time_sync.perform_immediate_sync("dashboard_startup")
            if sync_result.success:
                self.logger.info(f"Initial sync completed: {sync_result.total_requests} requests")
            else:
                self.logger.warning(f"Initial sync failed: {sync_result.error_message}")
        
        # Initialize Flask app
        # Get the absolute path to templates directory
        current_dir = Path(__file__).parent.parent  # Go up from automation/ to src/python/
        template_dir = current_dir / 'templates'
        static_dir = current_dir / 'static'
        
        self.app = Flask(__name__,
                        template_folder=str(template_dir),
                        static_folder=str(static_dir))
        CORS(self.app)  # Enable CORS for API endpoints
        
        # Initialize error and retry managers with thread-safe approach
        try:
            self.error_manager = create_error_manager(db_path)
            # Create retry manager without batch system to avoid signal handler conflicts in threads
            from automation.retry_manager import RetryManager
            self.retry_manager = RetryManager(db_path, batch_system=None, queue_manager=None, config=None)
        except Exception as e:
            self.logger.warning(f"Could not initialize error/retry managers: {e}")
            # Create minimal fallback managers
            self.error_manager = type('ErrorManager', (), {
                'get_error_statistics': lambda: {},
                'get_error_summary': lambda: {}
            })()
            self.retry_manager = type('RetryManager', (), {
                'get_retry_statistics': lambda: {},
                'get_retry_summary': lambda: {}
            })()
        
        # Note: Removed unused error dashboard/visualization APIs
        # The dashboard now relies on the core working error handling and monitoring system
        self.logger.info("Dashboard initialized with core monitoring system")
        
        # Initialize unknown region resolver
        try:
            self.unknown_region_resolver = EnhancedUnknownRegionResolver(db_path)
        except Exception as e:
            self.logger.warning(f"Could not initialize unknown region resolver: {e}")
            # Create minimal fallback resolver
            self.unknown_region_resolver = type('UnknownRegionResolver', (), {
                'detect_unknown_regions': lambda: [],
                'get_unknown_regions_status': lambda: {},
                'resolve_all_unknown_regions': lambda: {'success': False, 'error': 'Resolver not available'},
                'manual_override_region': lambda *args: {'success': False, 'error': 'Resolver not available'}
            })()
        
        # Initialize timeline validation services
        try:
            self.timestamp_validator = create_timestamp_validation_service()
            self.timeline_validator = create_timeline_validation_rules()
            self.processing_time_calculator = create_processing_time_calculator()
            self.logger.info("Timeline validation services initialized successfully")
        except Exception as e:
            self.logger.warning(f"Could not initialize timeline validation services: {e}")
            # Create minimal fallback services
            self.timestamp_validator = type('TimestampValidator', (), {
                'parse_timestamp': lambda self, ts, field: type('ParsedTimestamp', (), {
                    'value': None, 'is_valid': False, 'issues': [], 'confidence_score': 0.0
                })()
            })()
            self.timeline_validator = type('TimelineValidator', (), {
                'validate_timeline': lambda self, *args, **kwargs: type('TimelineValidationResult', (), {
                    'is_valid': False, 'issues': [], 'processing_time_hours': None
                })()
            })()
            self.processing_time_calculator = type('ProcessingTimeCalculator', (), {
                'calculate_processing_time': lambda self, *args, **kwargs: type('ProcessingTimeResult', (), {
                    'processing_time_hours': None, 'status': 'invalid', 'issues': []
                })()
            })()
        
        # Setup routes
        self._setup_routes()
        
        # Remove traditional caching - use real-time sync instead
        # Cache is now handled by the real-time sync engine with immediate updates
        
        self.logger.info("Enhanced RDA Dashboard with Real-Time Sync initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.dashboard', level=logging.INFO)
    
    def _safe_parse_datetime(self, date_str: str, field_name: str = "timestamp") -> Optional[datetime]:
        """
        Enhanced datetime parsing using the timeline validation service.
        
        This method now uses the centralized TimestampValidationService for consistent
        and robust timestamp parsing with comprehensive error handling.
        
        Args:
            date_str: Date string to parse
            field_name: Name of the field being parsed (for error reporting)
            
        Returns:
            Parsed datetime object or None if parsing fails
        """
        try:
            parsed_result = self.timestamp_validator.parse_timestamp(date_str, field_name)
            
            # Log validation issues if any
            if parsed_result.issues:
                for issue in parsed_result.issues:
                    if issue.severity.value in ['error', 'critical']:
                        self.logger.warning(f"Timestamp parsing issue for {field_name}: {issue.message}")
                    elif issue.severity.value == 'warning':
                        self.logger.debug(f"Timestamp parsing warning for {field_name}: {issue.message}")
            
            # Log low confidence parsing
            if parsed_result.is_valid and parsed_result.confidence_score < 0.7:
                self.logger.debug(f"Low confidence timestamp parsing for {field_name}: {parsed_result.confidence_score:.2f}")
            
            return parsed_result.value
            
        except Exception as e:
            self.logger.error(f"Error in enhanced timestamp parsing for {field_name}: {e}")
            return None

    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _trigger_sync_if_needed(self, trigger_reason: str = "data_access") -> None:
        """Trigger real-time sync if data is stale."""
        try:
            # Check if sync is needed and trigger immediately
            if self.real_time_sync.should_trigger_sync(trigger_reason):
                self.real_time_sync.perform_immediate_sync(trigger_reason)
        except Exception as e:
            self.logger.error(f"Error triggering sync: {e}")
    
    def _get_data_freshness_info(self) -> Dict[str, Any]:
        """Get current data freshness information."""
        try:
            freshness = self.real_time_sync.get_data_freshness()
            return {
                'level': freshness.level.value,
                'last_update': freshness.last_update.isoformat() if freshness.last_update else None,
                'age_seconds': freshness.age_seconds,
                'warning_message': freshness.warning_message,
                'is_fresh': freshness.level == DataFreshnessLevel.FRESH
            }
        except Exception as e:
            self.logger.error(f"Error getting freshness info: {e}")
            return {
                'level': 'unknown',
                'last_update': None,
                'age_seconds': float('inf'),
                'warning_message': 'Unable to determine data freshness',
                'is_fresh': False
            }
    
    def _parse_rinfo_parameters(self, rinfo: str) -> Dict[str, Any]:
        """
        Parse rinfo parameter string into a structured dictionary.
        
        Args:
            rinfo: Semicolon-delimited parameter string
            
        Returns:
            Dictionary with parsed parameters
        """
        if not rinfo:
            return {}
        
        params = {}
        try:
            for param in rinfo.split(';'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Try to convert numeric values
                    try:
                        if '.' in value:
                            params[key] = float(value)
                        else:
                            params[key] = int(value)
                    except ValueError:
                        params[key] = value
        except Exception as e:
            self.logger.warning(f"Error parsing rinfo '{rinfo}': {e}")
        
        return params
    
    def _format_subset_info(self, subset_info: Dict[str, Any], rinfo: str = None) -> Dict[str, Any]:
        """
        Format subset_info for better display in the dashboard with enhanced coordinate extraction.
        
        Args:
            subset_info: Raw subset_info dictionary from get_status
            rinfo: Optional rinfo string for precise coordinate extraction
            
        Returns:
            Formatted subset information with enhanced spatial bounds
        """
        if not subset_info:
            return {}
        
        formatted = {
            'raw_note': subset_info.get('note', ''),
            'parameters': [],
            'levels': [],
            'products': [],
            'date_range': {},
            'spatial_bounds': {}
        }
        
        note = subset_info.get('note', '')
        if note:
            # Extract date range - enhanced to handle both formats
            formatted['date_range'] = self._extract_date_range_enhanced(note)
            
            # Extract parameters
            param_section = re.search(r'Parameter\(s\):\s*\n(.*?)(?=\n  [A-Z]|\n\n|$)', note, re.DOTALL)
            if param_section:
                params_text = param_section.group(1).strip()
                formatted['parameters'] = [line.strip() for line in params_text.split('\n') if line.strip()]
            
            # Extract levels
            level_section = re.search(r'Level\(s\):\s*\n(.*?)(?=\n  [A-Z]|\n\n|$)', note, re.DOTALL)
            if level_section:
                levels_text = level_section.group(1).strip()
                formatted['levels'] = [line.strip() for line in levels_text.split('\n') if line.strip()]
        
        # Enhanced spatial bounds extraction - prioritize rinfo over subset_note
        formatted['spatial_bounds'] = self._extract_enhanced_spatial_bounds(rinfo, note)
        
        return formatted
    
    def _extract_enhanced_spatial_bounds(self, rinfo: str = None, subset_note: str = None) -> Dict[str, Any]:
        """
        Enhanced spatial bounds extraction that prioritizes rinfo over subset_note.
        
        Args:
            rinfo: Optional rinfo string with precise coordinates
            subset_note: Optional subset_note string with rounded coordinates
            
        Returns:
            Dictionary with spatial bounds or empty dict if none found
        """
        # Method 1: Try rinfo first (most precise coordinates)
        if rinfo:
            params = self._parse_rinfo_parameters(rinfo)
            
            # Check if we have all coordinate parameters
            if all(coord in params for coord in ['nlat', 'slat', 'wlon', 'elon']):
                return {
                    'north_lat': float(params['nlat']),
                    'south_lat': float(params['slat']),
                    'west_lon': float(params['wlon']),
                    'east_lon': float(params['elon']),
                    'source': 'rinfo',
                    'precision': 'high'
                }
        
        # Method 2: Fall back to subset_note parsing (rounded coordinates)
        if subset_note:
            spatial_match = re.search(r'Latitudes \(top/bottom\): ([\d.-]+) / ([\d.-]+)\s*\n\s*Longitudes \(left/right\): ([\d.-]+) / ([\d.-]+)', subset_note)
            if spatial_match:
                return {
                    'north_lat': float(spatial_match.group(1)),
                    'south_lat': float(spatial_match.group(2)),
                    'west_lon': float(spatial_match.group(3)),
                    'east_lon': float(spatial_match.group(4)),
                    'source': 'subset_note',
                    'precision': 'rounded'
                }
        
        # Method 3: Return empty dict if no coordinates found
        return {}
    
    def _extract_date_range_enhanced(self, note: str) -> Dict[str, Any]:
        """
        Enhanced date range extraction that handles both formats:
        - Format 1: "Date range: YYYYMMDDHHMM to YYYYMMDDHHMM" (legacy format)
        - Format 2: "Start date: YYYY-MM-DD HH:MM" and "End date: YYYY-MM-DD HH:MM" (new format)
        
        Args:
            note: The subset note string to parse
            
        Returns:
            Dictionary with date range information or empty dict if none found
        """
        if not note:
            return {}
        
        # Method 1: Try legacy format first (for backward compatibility)
        # Format: "Date range: 202101010000 to 202112310000"
        legacy_match = re.search(r'Date range: (\d{12}) to (\d{12})', note)
        if legacy_match:
            start_raw = legacy_match.group(1)
            end_raw = legacy_match.group(2)
            
            try:
                # Convert YYYYMMDDHHMM to formatted string
                formatted_start = f"{start_raw[:4]}-{start_raw[4:6]}-{start_raw[6:8]} {start_raw[8:10]}:{start_raw[10:12]}"
                formatted_end = f"{end_raw[:4]}-{end_raw[4:6]}-{end_raw[6:8]} {end_raw[8:10]}:{end_raw[10:12]}"
                
                return {
                    'start': start_raw,
                    'end': end_raw,
                    'formatted_start': formatted_start,
                    'formatted_end': formatted_end,
                    'format_type': 'legacy',
                    'source': 'date_range_pattern'
                }
            except (IndexError, ValueError) as e:
                self.logger.warning(f"Error parsing legacy date format '{start_raw}' to '{end_raw}': {e}")
        
        # Method 2: Try new format with separate start and end dates
        # Format: "- Start date:  2021-01-01 00:00" and "- End date:    2021-12-31 00:00"
        # Note: Handle variable whitespace between "date:" and the actual date
        start_match = re.search(r'Start date:\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', note)
        end_match = re.search(r'End date:\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', note)
        
        if start_match and end_match:
            start_formatted = start_match.group(1)
            end_formatted = end_match.group(1)
            
            try:
                # Convert YYYY-MM-DD HH:MM to YYYYMMDDHHMM format for consistency
                start_parts = start_formatted.replace('-', '').replace(' ', '').replace(':', '')
                end_parts = end_formatted.replace('-', '').replace(' ', '').replace(':', '')
                
                return {
                    'start': start_parts,
                    'end': end_parts,
                    'formatted_start': start_formatted,
                    'formatted_end': end_formatted,
                    'format_type': 'new',
                    'source': 'start_end_date_pattern'
                }
            except (IndexError, ValueError) as e:
                self.logger.warning(f"Error parsing new date format '{start_formatted}' to '{end_formatted}': {e}")
        
        # Method 3: Try to find individual start or end dates (partial match)
        if start_match and not end_match:
            start_formatted = start_match.group(1)
            try:
                start_parts = start_formatted.replace('-', '').replace(' ', '').replace(':', '')
                return {
                    'start': start_parts,
                    'end': 'undefined',
                    'formatted_start': start_formatted,
                    'formatted_end': 'undefined',
                    'format_type': 'partial_new',
                    'source': 'start_date_only',
                    'warning': 'End date not found'
                }
            except (IndexError, ValueError) as e:
                self.logger.warning(f"Error parsing partial start date '{start_formatted}': {e}")
        
        if end_match and not start_match:
            end_formatted = end_match.group(1)
            try:
                end_parts = end_formatted.replace('-', '').replace(' ', '').replace(':', '')
                return {
                    'start': 'undefined',
                    'end': end_parts,
                    'formatted_start': 'undefined',
                    'formatted_end': end_formatted,
                    'format_type': 'partial_new',
                    'source': 'end_date_only',
                    'warning': 'Start date not found'
                }
            except (IndexError, ValueError) as e:
                self.logger.warning(f"Error parsing partial end date '{end_formatted}': {e}")
        
        # Method 4: Return empty dict if no date patterns found
        self.logger.debug(f"No date range patterns found in note: {note[:100]}...")
        return {
            'start': 'undefined',
            'end': 'undefined',
            'formatted_start': 'undefined',
            'formatted_end': 'undefined',
            'format_type': 'none',
            'source': 'no_pattern_found',
            'warning': 'No date range patterns detected'
        }
    
    def _extract_region_from_rinfo(self, rinfo: str) -> Optional[str]:
        """Extract region from rinfo parameter string."""
        if not rinfo:
            return None
        
        try:
            # Parse rinfo parameters like "nlat=42;slat=32;wlon=-124.75;elon=-113.5"
            params = {}
            for param in rinfo.split(';'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key.strip()] = float(value.strip())
            
            # Simple region detection based on coordinates
            wlon = params.get('wlon', 0)
            elon = params.get('elon', 0)
            slat = params.get('slat', 0)
            nlat = params.get('nlat', 0)
            
            # US region detection based on coordinate ranges
            if -130 <= wlon <= -110 and 30 <= slat <= 50:
                if -125 <= wlon <= -115:
                    return "CISO"  # California region
                elif -115 <= wlon <= -105:
                    return "AZPS"  # Arizona/Southwest
            elif -110 <= wlon <= -90 and 25 <= slat <= 45:
                return "ERCOT"  # Texas region
            elif -90 <= wlon <= -70 and 35 <= slat <= 50:
                return "PJM"    # Eastern region
            
            return "UNKNOWN"
        except:
            return "UNKNOWN"
    
    def _extract_variable_from_subset_note(self, subset_note: str) -> Optional[str]:
        """Extract variable type from subset_note."""
        if not subset_note:
            return None
        
        note_lower = subset_note.lower()
        
        # Map common variable patterns
        if any(term in note_lower for term in ['solar', 'radiation', 'dswrf', 'shortwave']):
            return "dswrf"
        elif any(term in note_lower for term in ['wind', 'ugrd', 'vgrd']):
            return "ugrd_vgrd"
        elif any(term in note_lower for term in ['rain', 'precip', 'apcp']):
            return "apcp"
        elif any(term in note_lower for term in ['temp', 'temperature', 'tmp']):
            return "tmp_dpt"
        else:
            return "unknown"
    
    def _get_variable_display_name(self, variable_type: str) -> str:
        """Get human-readable display name for variable type."""
        display_names = {
            'dswrf': 'Solar Radiation',
            'ugrd_vgrd': 'Wind Speed',
            'tmp_dpt': 'Temperature',
            'apcp': 'Precipitation',
            'unknown': 'Unknown Variable'
        }
        return display_names.get(variable_type, variable_type.upper())
    
    def _format_processing_time_display(self, processing_time_hours: Optional[float]) -> str:
        """Format processing time for human-readable display."""
        if processing_time_hours is None:
            return "N/A"
        
        if processing_time_hours < 0:
            return "Invalid"
        elif processing_time_hours < 1:
            minutes = processing_time_hours * 60
            return f"{minutes:.1f} minutes"
        elif processing_time_hours < 24:
            return f"{processing_time_hours:.1f} hours"
        else:
            days = processing_time_hours / 24
            return f"{days:.1f} days"
    
    def _calculate_completion_trend(self, completion_dates: List[str]) -> Dict[str, Any]:
        """
        Calculate completion trend from a list of completion dates.
        
        Args:
            completion_dates: List of completion date strings
            
        Returns:
            Dictionary with trend information
        """
        if not completion_dates:
            return {
                'trend_type': 'no_data',
                'requests_per_day': 0.0,
                'total_days': 0,
                'peak_day': None,
                'trend_direction': 'stable'
            }
        
        try:
            # Parse dates and count by day
            from collections import defaultdict
            daily_counts = defaultdict(int)
            
            for date_str in completion_dates:
                if date_str:
                    parsed_date = self._safe_parse_datetime(date_str, 'completion_date')
                    if parsed_date:
                        day_key = parsed_date.strftime('%Y-%m-%d')
                        daily_counts[day_key] += 1
            
            if not daily_counts:
                return {
                    'trend_type': 'no_valid_dates',
                    'requests_per_day': 0.0,
                    'total_days': 0,
                    'peak_day': None,
                    'trend_direction': 'stable'
                }
            
            # Calculate statistics
            total_days = len(daily_counts)
            total_requests = sum(daily_counts.values())
            requests_per_day = total_requests / total_days if total_days > 0 else 0.0
            
            # Find peak day
            peak_day = max(daily_counts.items(), key=lambda x: x[1])
            
            # Determine trend direction (simple linear trend)
            sorted_days = sorted(daily_counts.items())
            if len(sorted_days) >= 3:
                first_half = sorted_days[:len(sorted_days)//2]
                second_half = sorted_days[len(sorted_days)//2:]
                
                first_avg = sum(count for _, count in first_half) / len(first_half)
                second_avg = sum(count for _, count in second_half) / len(second_half)
                
                if second_avg > first_avg * 1.2:
                    trend_direction = 'increasing'
                elif second_avg < first_avg * 0.8:
                    trend_direction = 'decreasing'
                else:
                    trend_direction = 'stable'
            else:
                trend_direction = 'insufficient_data'
            
            return {
                'trend_type': 'calculated',
                'requests_per_day': requests_per_day,
                'total_days': total_days,
                'peak_day': {
                    'date': peak_day[0],
                    'count': peak_day[1]
                },
                'trend_direction': trend_direction,
                'daily_breakdown': dict(daily_counts)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating completion trend: {e}")
            return {
                'trend_type': 'error',
                'requests_per_day': 0.0,
                'total_days': 0,
                'peak_day': None,
                'trend_direction': 'unknown',
                'error': str(e)
            }
    
    def _calculate_date_span_days(self, start_date: str, end_date: str) -> Optional[int]:
        """
        Calculate the number of days between two date strings.
        
        Args:
            start_date: Start date string
            end_date: End date string
            
        Returns:
            Number of days between dates, or None if calculation fails
        """
        if not start_date or not end_date:
            return None
        
        try:
            start_dt = self._safe_parse_datetime(start_date, 'start_date')
            end_dt = self._safe_parse_datetime(end_date, 'end_date')
            
            if start_dt and end_dt:
                delta = end_dt - start_dt
                return delta.days
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error calculating date span: {e}")
            return None
    
    def _analyze_completion_trend(self, formatted_trends: List[Dict[str, Any]]) -> str:
        """
        Analyze completion trend direction from formatted trend data.
        
        Args:
            formatted_trends: List of formatted trend dictionaries
            
        Returns:
            Trend direction string: 'increasing', 'decreasing', 'stable', or 'insufficient_data'
        """
        if not formatted_trends or len(formatted_trends) < 3:
            return 'insufficient_data'
        
        try:
            # Sort trends by date to ensure chronological order
            sorted_trends = sorted(formatted_trends, key=lambda x: x['date'])
            
            # Calculate simple linear trend using first and last values
            first_half = sorted_trends[:len(sorted_trends)//2]
            second_half = sorted_trends[len(sorted_trends)//2:]
            
            first_avg = sum(t['daily_completions'] for t in first_half) / len(first_half)
            second_avg = sum(t['daily_completions'] for t in second_half) / len(second_half)
            
            # Determine trend direction with threshold
            change_ratio = second_avg / first_avg if first_avg > 0 else 1.0
            
            if change_ratio > 1.2:  # 20% increase
                return 'increasing'
            elif change_ratio < 0.8:  # 20% decrease
                return 'decreasing'
            else:
                return 'stable'
                
        except Exception as e:
            self.logger.error(f"Error analyzing completion trend: {e}")
            return 'unknown'
    
    def get_current_requests(self, status_filter: Optional[str] = None,
                           region_filter: Optional[str] = None,
                           variable_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get current active requests from rda_requests table with complete get_status information.
        
        Args:
            status_filter: Optional status filter
            region_filter: Optional region filter (extracted from rinfo)
            variable_filter: Optional variable filter (extracted from subset_note)
            
        Returns:
            List of dictionaries with complete request information including parsed get_status data
        """
        # Trigger sync if needed for fresh data
        self._trigger_sync_if_needed("get_current_requests")
        
        try:
            query = """
                SELECT r.id, r.request_index, r.request_id, r.dsid, r.status,
                       r.date_rqst, r.date_ready, r.date_purge, r.location,
                       r.ncar_contact, r.rinfo, r.subset_note,
                       r.region, r.variable_type, r.raw_response
                FROM rda_requests r
                WHERE 1=1
            """
            params = []
            
            if status_filter:
                query += " AND r.status = ?"
                params.append(status_filter)
            
            if region_filter:
                query += " AND r.region = ?"
                params.append(region_filter)
            
            if variable_filter:
                query += " AND r.variable_type = ?"
                params.append(variable_filter)
            
            query += " ORDER BY r.date_rqst DESC"
            
            with self._get_db_connection() as conn:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
            
            current_requests = []
            for row in rows:
                # Parse raw_response JSON to get complete get_status data
                complete_data = {}
                if row['raw_response']:
                    try:
                        complete_data = json.loads(row['raw_response'])
                    except json.JSONDecodeError:
                        self.logger.warning(f"Failed to parse raw_response for {row['request_id']}")
                
                # Calculate processing time using enhanced processing time calculator
                processing_time = None
                processing_time_result = None
                timeline_validation_issues = []
                
                try:
                    # Use the enhanced processing time calculator
                    processing_time_result = self.processing_time_calculator.calculate_processing_time(
                        date_rqst=row['date_rqst'],
                        date_ready=row['date_ready'],
                        date_purge=row['date_purge'],
                        request_status=row['status'],
                        request_id=row['request_id']
                    )
                    
                    # Extract processing time and validation issues
                    processing_time = processing_time_result.processing_time_hours
                    timeline_validation_issues = processing_time_result.issues
                    
                    # Log critical timeline validation issues
                    for issue in timeline_validation_issues:
                        if issue.severity.value == 'critical':
                            self.logger.warning(f"Critical timeline issue for {row['request_id']}: {issue.message}")
                        elif issue.severity.value == 'error':
                            self.logger.debug(f"Timeline error for {row['request_id']}: {issue.message}")
                    
                    # Log low confidence calculations
                    if processing_time_result.confidence_score < 0.7:
                        self.logger.debug(f"Low confidence processing time for {row['request_id']}: {processing_time_result.confidence_score:.2f}")
                        
                except Exception as e:
                    self.logger.error(f"Error in enhanced processing time calculation for {row['request_id']}: {e}")
                    processing_time = None
                
                # Extract region and variable from rinfo and subset_note if not in control_files_tracking
                region = row['region'] or self._extract_region_from_rinfo(row['rinfo'])
                variable_type = row['variable_type'] or self._extract_variable_from_subset_note(row['subset_note'])
                
                # Format dates for consistent display
                formatted_date_rqst = None
                formatted_date_ready = None
                formatted_date_purge = None
                
                if row['date_rqst']:
                    parsed_rqst = self._safe_parse_datetime(row['date_rqst'], 'date_rqst')
                    if parsed_rqst:
                        formatted_date_rqst = parsed_rqst.isoformat()
                
                if row['date_ready']:
                    parsed_ready = self._safe_parse_datetime(row['date_ready'], 'date_ready')
                    if parsed_ready:
                        formatted_date_ready = parsed_ready.isoformat()
                
                if row['date_purge']:
                    parsed_purge = self._safe_parse_datetime(row['date_purge'], 'date_purge')
                    if parsed_purge:
                        formatted_date_purge = parsed_purge.isoformat()
                
                # Create enhanced request object with complete get_status information
                request_obj = {
                    'id': row['id'],
                    'request_index': row['request_index'],
                    'request_id': row['request_id'],
                    'dsid': row['dsid'],
                    'status': row['status'],
                    'date_rqst': formatted_date_rqst,
                    'date_ready': formatted_date_ready,
                    'date_purge': formatted_date_purge,
                    'location': row['location'],
                    'ncar_contact': row['ncar_contact'],
                    'rinfo': row['rinfo'],
                    'subset_note': row['subset_note'],
                    'region': region,
                    'variable_type': variable_type,
                    'processing_time_hours': processing_time,
                    # Enhanced timeline information with validation data
                    'timeline': {
                        'requested': formatted_date_rqst,
                        'ready': formatted_date_ready,
                        'purge': formatted_date_purge,
                        'processing_time_hours': processing_time,
                        'processing_time_display': self._format_processing_time_display(processing_time),
                        'status': row['status'],
                        # Timeline validation information
                        'validation': {
                            'has_issues': len(timeline_validation_issues) > 0,
                            'issue_count': len(timeline_validation_issues),
                            'critical_issues': len([i for i in timeline_validation_issues if i.severity.value == 'critical']),
                            'confidence_score': processing_time_result.confidence_score if processing_time_result else 0.0,
                            'calculation_mode': processing_time_result.calculation_mode.value if processing_time_result else 'unknown',
                            'calculation_status': processing_time_result.status.value if processing_time_result else 'invalid'
                        }
                    },
                    # Complete get_status information
                    'complete_status_data': complete_data,
                    'subset_info': complete_data.get('subset_info', {}),
                    'NCAR_contact': complete_data.get('NCAR_contact', row['ncar_contact']),
                    # Parsed rinfo parameters for easy display
                    'rinfo_params': self._parse_rinfo_parameters(row['rinfo']),
                    # Formatted subset details
                    'formatted_subset_info': self._format_subset_info(complete_data.get('subset_info', {}), row['rinfo'])
                }
                current_requests.append(request_obj)
            
            return current_requests
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error getting current requests: {e}")
            return []
    
    def get_regional_metrics(self) -> List[RegionalMetrics]:
        """
        Get regional performance metrics from rda_requests and control_files_tracking with real-time sync.
        
        Returns:
            List of RegionalMetrics objects
        """
        # Trigger sync if needed for fresh data
        self._trigger_sync_if_needed("get_regional_metrics")
        
        try:
            # Get regional metrics directly from rda_requests since regional_progress table is removed
            regional_metrics = self._get_regional_metrics_from_rda_requests()
            return regional_metrics
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error getting regional metrics: {e}")
            return []
    
    def _get_regional_metrics_from_rda_requests(self) -> List[RegionalMetrics]:
        """Fallback method to get regional metrics directly from rda_requests."""
        try:
            query = """
                SELECT
                    COALESCE(cf.region, 'UNKNOWN') as region,
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN LOWER(r.status) = 'completed' THEN 1 END) as completed_requests,
                    COUNT(CASE WHEN LOWER(r.status) LIKE '%queued%' THEN 1 END) as queued_requests,
                    COUNT(CASE WHEN LOWER(r.status) = 'processing' THEN 1 END) as processing_requests,
                    COUNT(CASE WHEN LOWER(r.status) LIKE '%purge%' THEN 1 END) as purged_requests,
                    COALESCE(cf.variable_type, 'unknown') as variable_type,
                    MIN(r.date_rqst) as first_request,
                    MAX(r.date_rqst) as last_request
                FROM rda_requests r
                LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                GROUP BY COALESCE(cf.region, 'UNKNOWN'), COALESCE(cf.variable_type, 'unknown')
                ORDER BY region
            """
            
            with self._get_db_connection() as conn:
                cursor = conn.execute(query)
                rows = cursor.fetchall()
            
            # Aggregate by region
            region_data = {}
            for row in rows:
                region = row['region']
                if region not in region_data:
                    region_data[region] = {
                        'total_requests': 0,
                        'completed_requests': 0,
                        'queued_requests': 0,
                        'processing_requests': 0,
                        'purged_requests': 0,
                        'variables': {},
                        'first_request': row['first_request'],
                        'last_request': row['last_request']
                    }
                
                data = region_data[region]
                data['total_requests'] += row['total_requests']
                data['completed_requests'] += row['completed_requests']
                data['queued_requests'] += row['queued_requests']
                data['processing_requests'] += row['processing_requests']
                data['purged_requests'] += row['purged_requests']
                data['variables'][row['variable_type']] = row['total_requests']
                
                # Update date range
                if row['first_request'] and (not data['first_request'] or row['first_request'] < data['first_request']):
                    data['first_request'] = row['first_request']
                if row['last_request'] and (not data['last_request'] or row['last_request'] > data['last_request']):
                    data['last_request'] = row['last_request']
            
            # Create RegionalMetrics objects
            regional_metrics = []
            for region, data in region_data.items():
                total = data['total_requests']
                completed = data['completed_requests']
                purged = data['purged_requests']
                
                success_rate = (completed / (completed + purged) * 100) if (completed + purged) > 0 else 0
                
                # Find most common variable
                most_common_variable = "N/A"
                if data['variables']:
                    most_common_variable = max(data['variables'].items(), key=lambda x: x[1])[0]
                
                # Format date range
                date_range = "N/A"
                if data['first_request'] and data['last_request']:
                    try:
                        first_dt = self._safe_parse_datetime(data['first_request'], 'first_request')
                        first = first_dt.strftime('%Y-%m-%d') if first_dt else 'N/A'
                        last_dt = self._safe_parse_datetime(data['last_request'], 'last_request')
                        last = last_dt.strftime('%Y-%m-%d') if last_dt else 'N/A'
                        date_range = f"{first} to {last}"
                    except:
                        pass
                
                metrics = RegionalMetrics(
                    region=region,
                    total_requests=total,
                    completed_requests=completed,
                    queued_requests=data['queued_requests'],
                    purged_requests=purged,
                    processing_requests=data['processing_requests'],
                    success_rate=success_rate,
                    average_processing_time=0.0,  # Not calculated in fallback
                    most_common_variable=most_common_variable,
                    date_range=date_range
                )
                regional_metrics.append(metrics)
            
            return regional_metrics
            
        except Exception as e:
            self.logger.error(f"Error in fallback regional metrics: {e}")
            return []
    
    def get_weather_variable_metrics(self) -> List[WeatherVariableMetrics]:
        """
        Get weather variable performance metrics from rda_requests data with real-time sync.
        
        Returns:
            List of WeatherVariableMetrics objects
        """
        # Trigger sync if needed for fresh data
        self._trigger_sync_if_needed("get_weather_variable_metrics")
        
        try:
            query = """
                SELECT
                    COALESCE(cf.variable_type, 'unknown') as variable_type,
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN LOWER(r.status) = 'completed' THEN 1 END) as completed_requests,
                    COUNT(CASE WHEN LOWER(r.status) LIKE '%queued%' THEN 1 END) as queued_requests,
                    COUNT(CASE WHEN LOWER(r.status) = 'processing' THEN 1 END) as processing_requests,
                    COUNT(CASE WHEN LOWER(r.status) LIKE '%purge%' THEN 1 END) as purged_requests,
                    COALESCE(cf.region, 'UNKNOWN') as region,
                    MIN(r.date_rqst) as first_request,
                    MAX(r.date_rqst) as last_request
                FROM rda_requests r
                LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                GROUP BY COALESCE(cf.variable_type, 'unknown'), COALESCE(cf.region, 'UNKNOWN')
                ORDER BY variable_type
            """
            
            with self._get_db_connection() as conn:
                cursor = conn.execute(query)
                rows = cursor.fetchall()
            
            # Aggregate data by variable type
            variable_data = {}
            for row in rows:
                variable_type = row['variable_type']
                if variable_type not in variable_data:
                    variable_data[variable_type] = {
                        'total_requests': 0,
                        'completed_requests': 0,
                        'queued_requests': 0,
                        'processing_requests': 0,
                        'purged_requests': 0,
                        'regions': {},
                        'first_request': row['first_request'],
                        'last_request': row['last_request']
                    }
                
                data = variable_data[variable_type]
                data['total_requests'] += row['total_requests']
                data['completed_requests'] += row['completed_requests']
                data['queued_requests'] += row['queued_requests']
                data['processing_requests'] += row['processing_requests']
                data['purged_requests'] += row['purged_requests']
                
                # Track regions
                region = row['region']
                data['regions'][region] = data['regions'].get(region, 0) + row['total_requests']
                
                # Update date range
                if row['first_request'] and (not data['first_request'] or row['first_request'] < data['first_request']):
                    data['first_request'] = row['first_request']
                if row['last_request'] and (not data['last_request'] or row['last_request'] > data['last_request']):
                    data['last_request'] = row['last_request']
            
            # Create WeatherVariableMetrics objects
            variable_metrics = []
            for variable_type, data in variable_data.items():
                total = data['total_requests']
                completed = data['completed_requests']
                purged = data['purged_requests']
                
                success_rate = (completed / (completed + purged) * 100) if (completed + purged) > 0 else 0
                
                # Get most active regions (top 3)
                most_active_regions = sorted(data['regions'].items(), key=lambda x: x[1], reverse=True)[:3]
                most_active_regions = [region for region, count in most_active_regions]
                
                # Format date range
                date_range = "N/A"
                if data['first_request'] and data['last_request']:
                    try:
                        first_dt = self._safe_parse_datetime(data['first_request'], 'first_request')
                        first = first_dt.strftime('%Y-%m-%d') if first_dt else 'N/A'
                        last_dt = self._safe_parse_datetime(data['last_request'], 'last_request')
                        last = last_dt.strftime('%Y-%m-%d') if last_dt else 'N/A'
                        date_range = f"{first} to {last}"
                    except:
                        pass
                
                metrics = WeatherVariableMetrics(
                    variable_type=variable_type,
                    total_requests=total,
                    completed_requests=completed,
                    queued_requests=data['queued_requests'],
                    purged_requests=purged,
                    processing_requests=data['processing_requests'],
                    success_rate=success_rate,
                    average_processing_time=0.0,  # Not calculated from rda_requests
                    most_active_regions=most_active_regions,
                    date_range=date_range
                )
                variable_metrics.append(metrics)
            
            return variable_metrics
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error getting weather variable metrics: {e}")
            return []
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard summary with all key metrics from rda_requests and real-time sync status.
        Enhanced with progress tracking data and error tracking integration.
        
        Returns:
            Dictionary containing dashboard summary data with freshness information and progress tracking
        """
        # Trigger sync if needed for fresh data
        self._trigger_sync_if_needed("get_dashboard_summary")
        
        try:
            # Get basic statistics from rda_requests with enhanced progress tracking
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN LOWER(r.status) LIKE '%queued%' THEN 1 END) as queued,
                        COUNT(CASE WHEN LOWER(r.status) = 'processing' THEN 1 END) as processing,
                        COUNT(CASE WHEN LOWER(r.status) = 'completed' THEN 1 END) as completed,
                        COUNT(CASE WHEN LOWER(r.status) LIKE '%purge%' OR r.date_purge IS NOT NULL THEN 1 END) as purged,
                        COUNT(DISTINCT COALESCE(cf.region, 'UNKNOWN')) as unique_regions,
                        COUNT(DISTINCT COALESCE(cf.variable_type, 'unknown')) as unique_variables,
                        COUNT(DISTINCT r.dsid) as unique_datasets
                    FROM rda_requests r
                    LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                """)
                stats = cursor.fetchone()
            
            # Calculate enhanced progress metrics
            total = stats['total_requests']
            completed = stats['completed']
            purged = stats['purged']
            processing = stats['processing']
            queued = stats['queued']
            
            # Progress tracking calculations
            files_done = completed
            files_remaining = total - completed
            progress_percentage = (completed / total * 100) if total > 0 else 0
            
            # Calculate completion rate (excluding purged as they're not "successful")
            active_requests = total - purged
            completion_rate = (completed / active_requests * 100) if active_requests > 0 else 0
            
            # Calculate success rate (completed vs total processed)
            processed_requests = completed + purged
            success_rate = (completed / processed_requests * 100) if processed_requests > 0 else 0
            
            # Get status distribution for the fresh data
            status_distribution = {}
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count
                    FROM rda_requests
                    GROUP BY status
                    ORDER BY count DESC
                """)
                for row in cursor.fetchall():
                    status_distribution[row['status']] = row['count']
            
            # Get error and retry statistics (if available)
            error_stats = {}
            retry_stats = {}
            try:
                error_stats = self.error_manager.get_error_statistics()
                retry_stats = self.retry_manager.get_retry_statistics()
            except:
                # Error/retry managers may not be available with new schema
                pass
            
            # Get real-time sync status and data freshness
            sync_status = self.real_time_sync.get_live_sync_status()
            freshness_info = self._get_data_freshness_info()
            sync_metrics = self.real_time_sync.get_sync_metrics()
            
            # Note: Using core error handling system instead of removed error dashboard API
            error_summary = {}
            
            return {
                'overview': {
                    'total_requests': total,
                    'queued_requests': queued,
                    'processing_requests': processing,
                    'completed_requests': completed,
                    'purged_requests': purged,
                    'completion_rate': completion_rate,
                    'success_rate': success_rate,
                    'progress_percentage': progress_percentage,
                    'unique_regions': stats['unique_regions'],
                    'unique_variables': stats['unique_variables'],
                    'unique_datasets': stats['unique_datasets']
                },
                'error_summary': error_summary,
                'progress_tracking': {
                    'files_done': files_done,
                    'files_remaining': files_remaining,
                    'progress_percentage': progress_percentage,
                    'completion_rate': completion_rate,
                    'total_files': total,
                    'active_files': active_requests,
                    'status_breakdown': {
                        'completed': completed,
                        'processing': processing,
                        'queued': queued,
                        'purged': purged
                    }
                },
                'status_distribution': status_distribution,
                'error_statistics': error_stats,
                'retry_statistics': retry_stats,
                'sync_status': {
                    'current_status': sync_status.status.value,
                    'last_sync': sync_status.last_sync.isoformat() if sync_status.last_sync else None,
                    'sync_count': sync_status.sync_count,
                    'error_count': sync_status.error_count,
                    'last_error': sync_status.last_error
                },
                'data_freshness': freshness_info,
                'sync_metrics': sync_metrics,
                'last_updated': datetime.now().isoformat(),
                'data_source': 'rda_requests (real-time sync with progress tracking)'
            }
            
        except Exception as e:
            self.logger.error(f"Error getting dashboard summary: {e}")
            return {
                'overview': {},
                'status_distribution': {},
                'error_statistics': {},
                'retry_statistics': {},
                'sync_status': {
                    'current_status': 'error',
                    'last_sync': None,
                    'sync_count': 0,
                    'error_count': 1,
                    'last_error': str(e)
                },
                'data_freshness': {
                    'level': 'critical',
                    'last_update': None,
                    'age_seconds': float('inf'),
                    'warning_message': f'Error getting dashboard data: {str(e)}',
                    'is_fresh': False
                },
                'last_updated': datetime.now().isoformat(),
                'error': str(e)
            }

    def get_scheduler_payload_v1(self) -> Dict[str, Any]:
        self._trigger_sync_if_needed("scheduler_api_v1")
        now_iso = datetime.now().isoformat()
        try:
            with self._get_db_connection() as conn:
                row = conn.execute(
                    """
                    SELECT payload_json, model_version, freshness_timestamp, updated_at
                    FROM scheduler_inference_outputs
                    WHERE output_key = 'latest'
                    LIMIT 1
                    """
                ).fetchone()

                if row:
                    payload = json.loads(row['payload_json'])
                    freshness_ts = row['freshness_timestamp'] or now_iso
                    freshness_age = (datetime.now() - self._safe_parse_datetime(freshness_ts, 'freshness_timestamp')).total_seconds() if self._safe_parse_datetime(freshness_ts, 'freshness_timestamp') else float('inf')
                    payload.update({
                        'api_version': 'v1',
                        'served_at': now_iso,
                        'freshness_age_seconds': freshness_age
                    })
                    return payload

                fallback = conn.execute(
                    """
                    SELECT
                        COUNT(*) AS total_requests,
                        SUM(CASE WHEN LOWER(status)='completed' THEN 1 ELSE 0 END) AS completed_requests,
                        SUM(CASE WHEN LOWER(status) LIKE '%fail%' THEN 1 ELSE 0 END) AS failed_requests,
                        MAX(updated_at) AS max_updated_at
                    FROM rda_requests
                    """
                ).fetchone()

                freshness_ts = fallback['max_updated_at'] if fallback and fallback['max_updated_at'] else now_iso
                return {
                    'api_version': 'v1',
                    'generated_at': now_iso,
                    'served_at': now_iso,
                    'freshness_timestamp': freshness_ts,
                    'freshness_age_seconds': (datetime.now() - self._safe_parse_datetime(freshness_ts, 'freshness_timestamp')).total_seconds() if self._safe_parse_datetime(freshness_ts, 'freshness_timestamp') else float('inf'),
                    'model_version': 'baseline-v0',
                    'metrics': {
                        'total_requests': int(fallback['total_requests'] or 0),
                        'completed_requests': int(fallback['completed_requests'] or 0),
                        'failed_requests': int(fallback['failed_requests'] or 0)
                    }
                }
        except Exception as e:
            self.logger.error(f"Error getting scheduler payload: {e}")
            return {
                'api_version': 'v1',
                'generated_at': now_iso,
                'served_at': now_iso,
                'error': str(e),
                'model_version': 'unknown',
                'freshness_timestamp': None,
                'freshness_age_seconds': float('inf'),
                'metrics': {}
            }
    
    def _setup_routes(self):
        """Setup Flask routes for the dashboard."""
        
        @self.app.route('/')
        def dashboard():
            """Main dashboard page with complete get_status information and immediate sync trigger."""
            # Trigger sync on dashboard access (0-second delay)
            sync_result = self.real_time_sync.sync_on_dashboard_access()
            return render_template('enhanced_dashboard_with_complete_status.html')
        
        @self.app.route('/api/summary')
        def api_summary():
            """API endpoint for dashboard summary with real-time sync."""
            return jsonify(self.get_dashboard_summary())
        
        @self.app.route('/api/sync-status')
        def api_sync_status():
            """API endpoint for real-time sync status."""
            try:
                sync_status = self.real_time_sync.get_live_sync_status()
                return jsonify({
                    'status': sync_status.status.value,
                    'last_sync': sync_status.last_sync.isoformat() if sync_status.last_sync else None,
                    'sync_count': sync_status.sync_count,
                    'error_count': sync_status.error_count,
                    'last_error': sync_status.last_error,
                    'data_freshness': {
                        'level': sync_status.data_freshness.level.value,
                        'age_seconds': sync_status.data_freshness.age_seconds,
                        'warning_message': sync_status.data_freshness.warning_message,
                        'is_fresh': sync_status.data_freshness.level == DataFreshnessLevel.FRESH
                    },
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/trigger-sync', methods=['POST'])
        def api_trigger_sync():
            """API endpoint to manually trigger immediate sync."""
            try:
                trigger_reason = request.json.get('reason', 'manual_trigger') if request.is_json else 'manual_trigger'
                sync_result = self.real_time_sync.perform_immediate_sync(trigger_reason)
                
                return jsonify({
                    'success': sync_result.success,
                    'timestamp': sync_result.timestamp,
                    'duration_seconds': sync_result.duration_seconds,
                    'total_requests': sync_result.total_requests,
                    'error_message': sync_result.error_message,
                    'sync_trigger': sync_result.sync_trigger
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/data-freshness')
        def api_data_freshness():
            """API endpoint for data freshness information."""
            try:
                freshness_info = self._get_data_freshness_info()
                return jsonify(freshness_info)
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/v1/scheduler/payload')
        def api_scheduler_payload_v1():
            return jsonify(self.get_scheduler_payload_v1())
        
        @self.app.route('/api/current-requests')
        def api_current_requests():
            """API endpoint for current active requests with complete get_status information."""
            status_filter = request.args.get('status')
            region_filter = request.args.get('region')
            parameter_filter = request.args.get('parameter')
            
            requests = self.get_current_requests(status_filter, region_filter, parameter_filter)
            return jsonify(requests)  # Already returns dictionaries with complete data
        
        @self.app.route('/api/regional-metrics')
        def api_regional_metrics():
            """API endpoint for regional performance data."""
            metrics = self.get_regional_metrics()
            return jsonify([asdict(metric) for metric in metrics])
        
        @self.app.route('/api/weather-variable-metrics')
        def api_weather_variable_metrics():
            """API endpoint for weather variable performance."""
            metrics = self.get_weather_variable_metrics()
            return jsonify([asdict(metric) for metric in metrics])
        
        @self.app.route('/api/error-metrics')
        def api_error_metrics():
            """API endpoint for error and retry statistics."""
            error_stats = self.error_manager.get_error_statistics()
            retry_stats = self.retry_manager.get_retry_statistics()
            
            return jsonify({
                'error_statistics': error_stats,
                'retry_statistics': retry_stats,
                'timestamp': datetime.now().isoformat()
            })
        
        @self.app.route('/api/filters')
        def api_filters():
            """API endpoint for available filter options from rda_requests."""
            try:
                with self._get_db_connection() as conn:
                    # Get unique regions from control_files_tracking
                    cursor = conn.execute("""
                        SELECT DISTINCT COALESCE(cf.region, 'UNKNOWN') as region
                        FROM rda_requests r
                        LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                        ORDER BY region
                    """)
                    regions = [row['region'] for row in cursor.fetchall()]
                    
                    # Get unique variable types
                    cursor = conn.execute("""
                        SELECT DISTINCT COALESCE(cf.variable_type, 'unknown') as variable_type
                        FROM rda_requests r
                        LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                        ORDER BY variable_type
                    """)
                    variables = [row['variable_type'] for row in cursor.fetchall()]
                    
                    # Get unique statuses from rda_requests
                    cursor = conn.execute("SELECT DISTINCT status FROM rda_requests ORDER BY status")
                    statuses = [row['status'] for row in cursor.fetchall()]
                
                return jsonify({
                    'regions': regions,
                    'variables': variables,
                    'statuses': statuses
                })
                
            except Exception as e:
                self.logger.error(f"Error getting filter options: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/error-tracking/summary')
        def api_error_tracking_summary():
            """API endpoint for error tracking summary data."""
            try:
                # Get error statistics from error manager
                error_stats = {}
                try:
                    error_stats = self.error_manager.get_error_statistics()
                except Exception as e:
                    self.logger.warning(f"Could not get error statistics: {e}")
                
                # Get retry statistics from retry manager
                retry_stats = {}
                try:
                    retry_stats = self.retry_manager.get_retry_statistics()
                except Exception as e:
                    self.logger.warning(f"Could not get retry statistics: {e}")
                
                # Build error tracking summary in expected format
                summary = {
                    'total_errors': error_stats.get('total_errors', 0),
                    'active_errors': error_stats.get('active_errors', 0),
                    'resolved_errors': error_stats.get('resolved_errors', 0),
                    'critical_errors': error_stats.get('critical_errors', 0),
                    'error_rate_24h': error_stats.get('error_rate_24h', 0.0),
                    'resolution_rate': error_stats.get('resolution_rate', 0.0),
                    'most_common_error_type': error_stats.get('most_common_error_type', 'Unknown'),
                    'most_affected_region': error_stats.get('most_affected_region', 'Unknown'),
                    'average_resolution_time_hours': error_stats.get('average_resolution_time_hours', 0.0)
                }
                
                return jsonify({
                    'summary': summary,
                    'retry_statistics': retry_stats,
                    'timestamp': datetime.now().isoformat(),
                    'data_source': 'error_manager_and_retry_manager'
                })
                
            except Exception as e:
                self.logger.error(f"Error getting error tracking summary: {e}")
                return jsonify({
                    'summary': {
                        'total_errors': 0,
                        'active_errors': 0,
                        'resolved_errors': 0,
                        'critical_errors': 0,
                        'error_rate_24h': 0.0,
                        'resolution_rate': 0.0,
                        'most_common_error_type': 'Unknown',
                        'most_affected_region': 'Unknown',
                        'average_resolution_time_hours': 0.0
                    },
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        @self.app.route('/api/live-data')
        def api_live_data():
            """API endpoint for complete live data refresh with real-time sync."""
            try:
                # Perform immediate sync with real-time engine
                sync_result = self.real_time_sync.perform_immediate_sync("api_live_data")
                
                # Get sync status and freshness info
                sync_status = self.real_time_sync.get_live_sync_status()
                freshness_info = self._get_data_freshness_info()
                
                # Return refreshed data with enhanced sync information
                return jsonify({
                    'sync_result': {
                        'success': sync_result.success,
                        'timestamp': sync_result.timestamp,
                        'duration_seconds': sync_result.duration_seconds,
                        'total_requests': sync_result.total_requests,
                        'error_message': sync_result.error_message,
                        'sync_trigger': sync_result.sync_trigger
                    },
                    'sync_status': {
                        'current_status': sync_status.status.value,
                        'sync_count': sync_status.sync_count,
                        'error_count': sync_status.error_count
                    },
                    'data_freshness': freshness_info,
                    'summary': self.get_dashboard_summary(),
                    'current_requests': self.get_current_requests(),
                    'regional_metrics': [asdict(metric) for metric in self.get_regional_metrics()],
                    'weather_variable_metrics': [asdict(metric) for metric in self.get_weather_variable_metrics()],
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error in live data refresh: {e}")
                return jsonify({
                    'error': str(e),
                    'sync_status': {'current_status': 'error'},
                    'data_freshness': {
                        'level': 'critical',
                        'warning_message': f'Error refreshing data: {str(e)}',
                        'is_fresh': False
                    },
                    'timestamp': datetime.now().isoformat()
                }), 500
       
        @self.app.route('/api/unknown-regions')
        def api_unknown_regions():
            """API endpoint for unknown regions status and data with complete get_status information."""
            try:
                status = self.unknown_region_resolver.get_unknown_regions_status()
                unknown_requests = self.unknown_region_resolver.detect_unknown_regions()
                
                # Enhance unknown requests with complete get_status data
                enhanced_unknown_requests = []
                for req in unknown_requests:
                    # Get complete data from rda_requests table
                    with self._get_db_connection() as conn:
                        cursor = conn.execute("""
                            SELECT raw_response, dsid, location, ncar_contact, date_rqst, date_ready, date_purge, status
                            FROM rda_requests
                            WHERE request_id = ?
                        """, (req.request_id,))
                        row = cursor.fetchone()
                    
                    complete_data = {}
                    if row and row['raw_response']:
                        try:
                            complete_data = json.loads(row['raw_response'])
                        except json.JSONDecodeError:
                            self.logger.warning(f"Failed to parse raw_response for {req.request_id}")
                    
                    enhanced_req = {
                        'request_id': req.request_id,
                        'request_index': req.request_index,
                        'rinfo': req.rinfo,
                        'subset_note': req.subset_note,
                        'assigned_name': req.assigned_name,
                        'resolved_region': req.resolved_region,
                        'resolved_variable': req.resolved_variable,
                        'manual_override': req.manual_override,
                        'created_at': req.created_at,
                        'updated_at': req.updated_at,
                        # Complete get_status information
                        'complete_status_data': complete_data,
                        'subset_info': complete_data.get('subset_info', {}),
                        'dsid': complete_data.get('dsid', row['dsid'] if row else None),
                        'location': complete_data.get('location', row['location'] if row else None),
                        'NCAR_contact': complete_data.get('NCAR_contact', row['ncar_contact'] if row else None),
                        'date_rqst': complete_data.get('date_rqst', row['date_rqst'] if row else None),
                        'date_ready': complete_data.get('date_ready', row['date_ready'] if row else None),
                        'date_purge': complete_data.get('date_purge', row['date_purge'] if row else None),
                        'status': complete_data.get('status', row['status'] if row else None),
                        # Parsed rinfo parameters for easy display
                        'rinfo_params': self._parse_rinfo_parameters(req.rinfo),
                        # Formatted subset details
                        'formatted_subset_info': self._format_subset_info(complete_data.get('subset_info', {}), req.rinfo)
                    }
                    enhanced_unknown_requests.append(enhanced_req)
                
                return jsonify({
                    'status': status,
                    'unknown_requests': enhanced_unknown_requests,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error getting unknown regions: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/unknown-regions/resolve-all', methods=['POST'])
        def api_resolve_all_unknown():
            """API endpoint to resolve all unknown regions."""
            try:
                result = self.unknown_region_resolver.resolve_all_unknown_regions()
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error resolving all unknown regions: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/unknown-regions/manual-override', methods=['POST'])
        def api_manual_override():
            """API endpoint for manual region override."""
            try:
                data = request.get_json()
                if not data or not all(k in data for k in ['request_id', 'region', 'variable']):
                    return jsonify({'error': 'Missing required fields: request_id, region, variable'}), 400
                
                result = self.unknown_region_resolver.manual_override_region(
                    data['request_id'],
                    data['region'],
                    data['variable'],
                    data.get('override_by', 'dashboard_user')
                )
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error in manual override: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/completed-regions')
        def api_completed_regions():
            """Enhanced API endpoint for completed regions data with pagination, filtering, and detailed metadata."""
            try:
                self.logger.info("DEBUG: Enhanced /api/completed-regions endpoint called")
                # Trigger sync if needed for fresh data
                self._trigger_sync_if_needed("get_completed_regions")
                
                # Parse query parameters for pagination and filtering
                page = request.args.get('page', 1, type=int)
                per_page = min(request.args.get('per_page', 50, type=int), 200)  # Max 200 per page
                region_filter = request.args.get('region')
                variable_filter = request.args.get('variable')
                date_from = request.args.get('date_from')  # Format: YYYY-MM-DD
                date_to = request.args.get('date_to')      # Format: YYYY-MM-DD
                sort_by = request.args.get('sort_by', 'completion_time')  # completion_time, region, variable, processing_time
                sort_order = request.args.get('sort_order', 'desc')  # asc, desc
                include_details = request.args.get('include_details', 'true').lower() == 'true'
                
                # Enhanced parameter validation with detailed error messages
                validation_errors = []
                
                if page < 1:
                    validation_errors.append('Page must be >= 1')
                if page > 10000:  # Reasonable upper limit
                    validation_errors.append('Page must be <= 10000')
                    
                if per_page < 1:
                    validation_errors.append('per_page must be >= 1')
                if per_page > 200:  # Already enforced above, but explicit validation
                    validation_errors.append('per_page must be <= 200')
                    
                valid_sort_options = ['completion_time', 'region', 'variable', 'processing_time', 'file_count']
                if sort_by not in valid_sort_options:
                    validation_errors.append(f'Invalid sort_by parameter. Valid options: {", ".join(valid_sort_options)}')
                    
                if sort_order not in ['asc', 'desc']:
                    validation_errors.append('Invalid sort_order parameter. Valid options: asc, desc')
                
                # Validate date formats if provided
                if date_from:
                    try:
                        datetime.strptime(date_from, '%Y-%m-%d')
                    except ValueError:
                        validation_errors.append('Invalid date_from format. Use YYYY-MM-DD')
                
                if date_to:
                    try:
                        datetime.strptime(date_to, '%Y-%m-%d')
                    except ValueError:
                        validation_errors.append('Invalid date_to format. Use YYYY-MM-DD')
                
                # Validate date range logic
                if date_from and date_to:
                    try:
                        from_date = datetime.strptime(date_from, '%Y-%m-%d')
                        to_date = datetime.strptime(date_to, '%Y-%m-%d')
                        if from_date > to_date:
                            validation_errors.append('date_from must be earlier than or equal to date_to')
                        
                        # Check for reasonable date range (not more than 5 years)
                        if (to_date - from_date).days > 1825:  # 5 years
                            validation_errors.append('Date range cannot exceed 5 years')
                    except ValueError:
                        pass  # Already caught above
                
                # Return validation errors if any
                if validation_errors:
                    return jsonify({
                        'error': 'Validation failed',
                        'validation_errors': validation_errors,
                        'timestamp': datetime.now().isoformat()
                    }), 400
                
                # Build dynamic query with filters
                base_query = """
                    SELECT
                        r.id,
                        r.request_id,
                        r.request_index,
                        r.region,
                        r.variable_type,
                        r.status,
                        r.date_rqst,
                        r.date_ready,
                        r.date_purge,
                        r.completion_time,
                        r.download_time,
                        r.download_directory,
                        r.file_size,
                        r.processing_duration,
                        r.rinfo,
                        r.subset_note,
                        r.raw_response,
                        r.dsid,
                        r.location,
                        r.ncar_contact,
                        cf.region as cf_region,
                        cf.variable_type as cf_variable_type,
                        cf.filename as cf_filename
                    FROM rda_requests r
                    LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                    WHERE (LOWER(r.status) IN ('completed', 'ready', 'online') OR r.date_ready IS NOT NULL)
                """
                
                query_params = []
                
                # Add filters
                if region_filter:
                    base_query += " AND (COALESCE(cf.region, r.region) = ? OR COALESCE(cf.region, r.region) LIKE ?)"
                    query_params.extend([region_filter, f"%{region_filter}%"])
                
                if variable_filter:
                    base_query += " AND (COALESCE(cf.variable_type, r.variable_type) = ? OR COALESCE(cf.variable_type, r.variable_type) LIKE ?)"
                    query_params.extend([variable_filter, f"%{variable_filter}%"])
                
                if date_from:
                    try:
                        # Validate date format
                        datetime.strptime(date_from, '%Y-%m-%d')
                        base_query += " AND DATE(COALESCE(r.completion_time, r.date_ready)) >= ?"
                        query_params.append(date_from)
                    except ValueError:
                        return jsonify({'error': 'Invalid date_from format. Use YYYY-MM-DD'}), 400
                
                if date_to:
                    try:
                        # Validate date format
                        datetime.strptime(date_to, '%Y-%m-%d')
                        base_query += " AND DATE(COALESCE(r.completion_time, r.date_ready)) <= ?"
                        query_params.append(date_to)
                    except ValueError:
                        return jsonify({'error': 'Invalid date_to format. Use YYYY-MM-DD'}), 400
                
                # Add sorting
                sort_column_map = {
                    'completion_time': 'COALESCE(r.completion_time, r.date_ready)',
                    'region': 'COALESCE(cf.region, r.region)',
                    'variable': 'COALESCE(cf.variable_type, r.variable_type)',
                    'processing_time': 'r.processing_duration',
                    'file_count': 'r.file_size'
                }
                
                sort_column = sort_column_map.get(sort_by, 'COALESCE(r.completion_time, r.date_ready)')
                base_query += f" ORDER BY {sort_column} {sort_order.upper()}"
                
                # Get total count for pagination
                count_query = f"""
                    SELECT COUNT(*) as total
                    FROM rda_requests r
                    LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                    WHERE (LOWER(r.status) IN ('completed', 'ready', 'online') OR r.date_ready IS NOT NULL)
                """
                
                # Apply same filters to count query
                count_params = []
                if region_filter:
                    count_query += " AND (COALESCE(cf.region, r.region) = ? OR COALESCE(cf.region, r.region) LIKE ?)"
                    count_params.extend([region_filter, f"%{region_filter}%"])
                
                if variable_filter:
                    count_query += " AND (COALESCE(cf.variable_type, r.variable_type) = ? OR COALESCE(cf.variable_type, r.variable_type) LIKE ?)"
                    count_params.extend([variable_filter, f"%{variable_filter}%"])
                
                if date_from:
                    count_query += " AND DATE(COALESCE(r.completion_time, r.date_ready)) >= ?"
                    count_params.append(date_from)
                
                if date_to:
                    count_query += " AND DATE(COALESCE(r.completion_time, r.date_ready)) <= ?"
                    count_params.append(date_to)
                
                # Execute queries
                with self._get_db_connection() as conn:
                    # Get total count
                    cursor = conn.execute(count_query, count_params)
                    total_count = cursor.fetchone()['total']
                    
                    # Get paginated results
                    offset = (page - 1) * per_page
                    paginated_query = base_query + f" LIMIT ? OFFSET ?"
                    query_params.extend([per_page, offset])
                    
                    cursor = conn.execute(paginated_query, query_params)
                    completed_requests = cursor.fetchall()
                
                if not completed_requests:
                    self.logger.info("DEBUG: No completed requests found in database")
                    return jsonify({
                        'completed_regions': [],
                        'pagination': {
                            'page': page,
                            'per_page': per_page,
                            'total_count': 0,
                            'total_pages': 0,
                            'has_next': False,
                            'has_prev': False
                        },
                        'filters': {
                            'region': region_filter,
                            'variable': variable_filter,
                            'date_from': date_from,
                            'date_to': date_to,
                            'sort_by': sort_by,
                            'sort_order': sort_order
                        },
                        'statistics': {
                            'total_completed_requests': 0,
                            'total_downloaded_files': 0,
                            'unique_regions': 0,
                            'unique_variables': 0,
                            'regions_with_downloads': 0,
                            'download_completion_rate': 0.0,
                            'avg_processing_hours': 0.0
                        },
                        'timestamp': datetime.now().isoformat(),
                        'data_source': 'enhanced_database_with_pagination_and_filtering'
                    })
                
                # Calculate pagination info
                total_pages = (total_count + per_page - 1) // per_page
                has_next = page < total_pages
                has_prev = page > 1
                
                # Process completed requests with enhanced metadata
                completed_regions = []
                total_downloaded_files = 0
                
                # Group completed requests by region for better organization
                from collections import defaultdict
                region_data = defaultdict(lambda: {
                    'requests': [],
                    'variable_breakdown': defaultdict(int),
                    'total_requests': 0,
                    'downloaded_files': 0,
                    'total_file_size': 0,
                    'processing_times': [],
                    'first_completion': None,
                    'last_completion': None,
                    'download_directories': set(),
                    'completion_dates': []
                })
                
                for request_item in completed_requests:
                    # Get region name (prioritize control_files_tracking, then rda_requests, then extract from rinfo)
                    region = request_item['cf_region'] or request_item['region'] or self._extract_region_from_rinfo(request_item['rinfo']) or 'UNKNOWN'
                    
                    # Get variable type (prioritize control_files_tracking, then rda_requests, then extract from subset_note)
                    variable_type = request_item['cf_variable_type'] or request_item['variable_type'] or self._extract_variable_from_subset_note(request_item['subset_note']) or 'unknown'
                    
                    # Add to region data
                    region_info = region_data[region]
                    region_info['requests'].append(request_item)
                    region_info['variable_breakdown'][variable_type] += 1
                    region_info['total_requests'] += 1
                    
                    # Track file information with enhanced metadata
                    if request_item['file_size']:
                        region_info['total_file_size'] += request_item['file_size']
                    
                    # Track processing times with validation
                    if request_item['processing_duration'] and request_item['processing_duration'] > 0:
                        region_info['processing_times'].append(request_item['processing_duration'])
                    
                    # Track completion times with enhanced timeline tracking
                    completion_time = request_item['completion_time'] or request_item['date_ready']
                    if completion_time:
                        region_info['completion_dates'].append(completion_time)
                        if not region_info['first_completion'] or completion_time < region_info['first_completion']:
                            region_info['first_completion'] = completion_time
                        if not region_info['last_completion'] or completion_time > region_info['last_completion']:
                            region_info['last_completion'] = completion_time
                    
                    # Track download directories
                    if request_item['download_directory']:
                        region_info['download_directories'].add(request_item['download_directory'])
                
                # Process each region with enhanced metadata and filesystem verification
                for region, info in region_data.items():
                    # Count actual downloaded files by checking filesystem
                    downloaded_file_count = 0
                    has_actual_downloads = False
                    
                    # Check common download directory patterns
                    download_paths_to_check = [
                        f'downloaded_files/{region}',
                        f'downloaded_files/{region.lower()}',
                        f'downloaded_files/{region.upper()}',
                        f'data/downloaded/{region}',
                        f'downloads/{region}'
                    ]
                    
                    # Also check any specific download directories from the database
                    for download_dir in info['download_directories']:
                        if download_dir:
                            download_paths_to_check.append(download_dir)
                    
                    # Count files in download directories
                    for download_path in download_paths_to_check:
                        if os.path.exists(download_path) and os.path.isdir(download_path):
                            has_actual_downloads = True
                            for root, dirs, files in os.walk(download_path):
                                for file in files:
                                    if file.endswith(('.nc', '.grb', '.grib', '.grib2', '.dat', '.bin', '.tar', '.gz', '.bz2', '.zip')):
                                        downloaded_file_count += 1
                    
                    # If no files found in filesystem, use request count as estimate
                    if downloaded_file_count == 0:
                        downloaded_file_count = info['total_requests']
                    
                    info['downloaded_files'] = downloaded_file_count
                    info['has_actual_downloads'] = has_actual_downloads
                    
                    # Calculate enhanced statistics
                    success_rate = 100.0  # All requests in this query are completed
                    completion_percentage = 100.0  # All requests are completed
                    
                    # Calculate average processing time with validation
                    avg_processing_time = 0.0
                    median_processing_time = 0.0
                    if info['processing_times']:
                        avg_processing_time = sum(info['processing_times']) / len(info['processing_times'])
                        sorted_times = sorted(info['processing_times'])
                        n = len(sorted_times)
                        median_processing_time = sorted_times[n//2] if n % 2 == 1 else (sorted_times[n//2-1] + sorted_times[n//2]) / 2
                    
                    # Get most common variable
                    most_common_variable = 'unknown'
                    if info['variable_breakdown']:
                        most_common_variable = max(info['variable_breakdown'].items(), key=lambda x: x[1])[0]
                    
                    # Calculate completion trends (requests per day)
                    completion_trend = self._calculate_completion_trend(info['completion_dates'])
                    
                    # Format region name for display
                    region_name = region.replace('_', ' ').title() if region != 'UNKNOWN' else 'Unknown Region'
                    
                    # Create enhanced region summary with comprehensive metadata
                    region_summary = {
                        'region': region,
                        'region_name': region_name,
                        'total_requests': info['total_requests'],
                        'completed_requests': info['total_requests'],  # All are completed
                        'downloaded_files': downloaded_file_count,
                        'success_rate': success_rate,
                        'completion_percentage': completion_percentage,
                        'variable_breakdown': dict(info['variable_breakdown']),
                        'most_common_variable': most_common_variable,
                        'processing_time_stats': {
                            'average_hours': avg_processing_time,
                            'median_hours': median_processing_time,
                            'min_hours': min(info['processing_times']) if info['processing_times'] else 0,
                            'max_hours': max(info['processing_times']) if info['processing_times'] else 0,
                            'total_samples': len(info['processing_times'])
                        },
                        'file_stats': {
                            'total_size_bytes': info['total_file_size'],
                            'total_size_mb': info['total_file_size'] / (1024 * 1024) if info['total_file_size'] else 0,
                            'average_size_bytes': info['total_file_size'] / info['total_requests'] if info['total_requests'] > 0 else 0
                        },
                        'timeline': {
                            'first_completion': info['first_completion'],
                            'last_completion': info['last_completion'],
                            'completion_span_days': self._calculate_date_span_days(info['first_completion'], info['last_completion']),
                            'completion_trend': completion_trend
                        },
                        'download_info': {
                            'has_actual_downloads': has_actual_downloads,
                            'download_directories': list(info['download_directories']),
                            'directory_count': len(info['download_directories'])
                        }
                    }
                    
                    # Add detailed requests only if requested (to reduce response size)
                    if include_details:
                        region_summary['sample_requests'] = [
                            {
                                'request_id': req_item['request_id'],
                                'request_index': req_item['request_index'],
                                'variable_type': req_item['cf_variable_type'] or req_item['variable_type'] or 'unknown',
                                'completion_time': req_item['completion_time'] or req_item['date_ready'],
                                'file_size': req_item['file_size'],
                                'processing_duration': req_item['processing_duration']
                            }
                            for req_item in info['requests'][:5]  # Show first 5 requests as samples
                        ]
                        
                        region_summary['detailed_requests'] = [
                            {
                                'id': req_item['id'],
                                'request_id': req_item['request_id'],
                                'request_index': req_item['request_index'],
                                'dsid': req_item['dsid'],
                                'status': req_item['status'],
                                'date_rqst': req_item['date_rqst'],
                                'date_ready': req_item['date_ready'],
                                'date_purge': req_item['date_purge'],
                                'location': req_item['location'],
                                'ncar_contact': req_item['ncar_contact'],
                                'rinfo': req_item['rinfo'],
                                'subset_note': req_item['subset_note'],
                                'region': req_item['cf_region'] or req_item['region'] or self._extract_region_from_rinfo(req_item['rinfo']) or 'UNKNOWN',
                                'variable_type': req_item['cf_variable_type'] or req_item['variable_type'] or self._extract_variable_from_subset_note(req_item['subset_note']) or 'unknown',
                                'processing_time_hours': req_item['processing_duration'],
                                'completion_time': req_item['completion_time'] or req_item['date_ready'],
                                'file_size': req_item['file_size'],
                                'download_directory': req_item['download_directory'],
                                # Parse raw_response JSON to get complete get_status data
                                'complete_status_data': json.loads(req_item['raw_response']) if req_item['raw_response'] else {},
                                'subset_info': json.loads(req_item['raw_response']).get('subset_info', {}) if req_item['raw_response'] else {},
                                'NCAR_contact': json.loads(req_item['raw_response']).get('NCAR_contact', req_item['ncar_contact']) if req_item['raw_response'] else req_item['ncar_contact'],
                                # Parsed rinfo parameters for easy display
                                'rinfo_params': self._parse_rinfo_parameters(req_item['rinfo']),
                                # Formatted subset details
                                'formatted_subset_info': self._format_subset_info(
                                    json.loads(req_item['raw_response']).get('subset_info', {}) if req_item['raw_response'] else {},
                                    req_item['rinfo']
                                ),
                                # Enhanced timeline information
                                'timeline': {
                                    'requested': req_item['date_rqst'],
                                    'ready': req_item['date_ready'],
                                    'purge': req_item['date_purge'],
                                    'processing_time_hours': req_item['processing_duration'],
                                    'processing_time_display': self._format_processing_time_display(req_item['processing_duration']),
                                    'status': req_item['status']
                                }
                            }
                            for req_item in info['requests']  # Include ALL requests with full details
                        ]
                    
                    self.logger.info(f"DEBUG: Created enhanced region summary for {region}: {len(info['requests'])} requests")
                    completed_regions.append(region_summary)
                    total_downloaded_files += downloaded_file_count
                
                # Sort regions based on the requested sort order
                if sort_by == 'region':
                    completed_regions.sort(key=lambda x: x['region'], reverse=(sort_order == 'desc'))
                elif sort_by == 'variable':
                    completed_regions.sort(key=lambda x: x['most_common_variable'], reverse=(sort_order == 'desc'))
                elif sort_by == 'processing_time':
                    completed_regions.sort(key=lambda x: x['processing_time_stats']['average_hours'], reverse=(sort_order == 'desc'))
                elif sort_by == 'file_count':
                    completed_regions.sort(key=lambda x: x['downloaded_files'], reverse=(sort_order == 'desc'))
                else:  # Default: completion_time
                    completed_regions.sort(key=lambda x: x['timeline']['last_completion'] or '', reverse=(sort_order == 'desc'))
                
                # Calculate comprehensive statistics
                unique_regions = len(completed_regions)
                regions_with_downloads = sum(1 for region in completed_regions if region['download_info']['has_actual_downloads'])
                
                # Count unique variables
                unique_variables = set()
                for region in completed_regions:
                    unique_variables.update(region['variable_breakdown'].keys())
                
                # Calculate enhanced statistics
                download_completion_rate = (regions_with_downloads / unique_regions * 100) if unique_regions > 0 else 0.0
                
                # Calculate processing time statistics
                all_processing_times = []
                for region in completed_regions:
                    if region['processing_time_stats']['average_hours'] > 0:
                        all_processing_times.append(region['processing_time_stats']['average_hours'])
                
                avg_processing_hours = sum(all_processing_times) / len(all_processing_times) if all_processing_times else 0.0
                
                # Calculate file size statistics
                total_file_size = sum(region['file_stats']['total_size_bytes'] for region in completed_regions)
                
                # Build comprehensive response
                result = {
                    'completed_regions': completed_regions,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total_count': total_count,
                        'total_pages': total_pages,
                        'has_next': has_next,
                        'has_prev': has_prev,
                        'showing_count': len(completed_requests)
                    },
                    'filters': {
                        'region': region_filter,
                        'variable': variable_filter,
                        'date_from': date_from,
                        'date_to': date_to,
                        'sort_by': sort_by,
                        'sort_order': sort_order,
                        'include_details': include_details
                    },
                    'statistics': {
                        'filtered_results': {
                            'total_completed_requests': sum(region['total_requests'] for region in completed_regions),
                            'total_downloaded_files': total_downloaded_files,
                            'unique_regions': unique_regions,
                            'unique_variables': len(unique_variables),
                            'regions_with_downloads': regions_with_downloads,
                            'download_completion_rate': download_completion_rate,
                            'avg_processing_hours': avg_processing_hours,
                            'total_file_size_bytes': total_file_size,
                            'total_file_size_gb': total_file_size / (1024**3) if total_file_size > 0 else 0
                        },
                        'overall_totals': {
                            'total_in_database': total_count,
                            'showing_in_page': len(completed_requests)
                        }
                    },
                    'metadata': {
                        'query_performance': {
                            'total_count_query_time': 'measured_in_ms',  # Could add actual timing
                            'data_query_time': 'measured_in_ms'
                        },
                        'data_freshness': self._get_data_freshness_info(),
                        'include_details': include_details
                    },
                    'timestamp': datetime.now().isoformat(),
                    'data_source': 'enhanced_database_with_pagination_and_filtering'
                }
                
                self.logger.info(f"DEBUG: Returning enhanced completed regions data: {len(completed_regions)} regions, page {page}/{total_pages}")
                return jsonify(result)
                
            except Exception as e:
                self.logger.error(f"Error getting completed regions from database: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/completed-regions/summary')
        def api_completed_regions_summary():
            """New API endpoint for completed regions summary with statistics and trends."""
            try:
                self.logger.info("DEBUG: /api/completed-regions/summary endpoint called")
                # Trigger sync if needed for fresh data
                self._trigger_sync_if_needed("get_completed_regions_summary")
                
                # Get comprehensive statistics from completed requests
                with self._get_db_connection() as conn:
                    # Overall completion statistics
                    cursor = conn.execute("""
                        SELECT
                            COUNT(*) as total_completed_requests,
                            COUNT(DISTINCT COALESCE(cf.region, r.region, 'UNKNOWN')) as total_regions_completed,
                            COUNT(DISTINCT COALESCE(cf.variable_type, r.variable_type, 'unknown')) as total_variables_completed,
                            MIN(COALESCE(r.completion_time, r.date_ready)) as earliest_completion,
                            MAX(COALESCE(r.completion_time, r.date_ready)) as latest_completion,
                            AVG(r.processing_duration) as avg_processing_hours,
                            SUM(r.file_size) as total_file_size_bytes
                        FROM rda_requests r
                        LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                        WHERE (LOWER(r.status) IN ('completed', 'ready', 'online') OR r.date_ready IS NOT NULL)
                    """)
                    overall_stats = cursor.fetchone()
                    
                    # Most frequently completed region/variable combinations
                    cursor = conn.execute("""
                        SELECT
                            COALESCE(cf.region, r.region, 'UNKNOWN') as region,
                            COALESCE(cf.variable_type, r.variable_type, 'unknown') as variable_type,
                            COUNT(*) as completion_count,
                            AVG(r.processing_duration) as avg_processing_time,
                            MAX(COALESCE(r.completion_time, r.date_ready)) as last_completion
                        FROM rda_requests r
                        LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                        WHERE (LOWER(r.status) IN ('completed', 'ready', 'online') OR r.date_ready IS NOT NULL)
                        GROUP BY COALESCE(cf.region, r.region, 'UNKNOWN'), COALESCE(cf.variable_type, r.variable_type, 'unknown')
                        ORDER BY completion_count DESC
                        LIMIT 10
                    """)
                    frequent_combinations = cursor.fetchall()
                    
                    # Recent completion trends (last 30 days)
                    cursor = conn.execute("""
                        SELECT
                            DATE(COALESCE(r.completion_time, r.date_ready)) as completion_date,
                            COUNT(*) as daily_completions,
                            COUNT(DISTINCT COALESCE(cf.region, r.region, 'UNKNOWN')) as regions_completed,
                            AVG(r.processing_duration) as avg_processing_time
                        FROM rda_requests r
                        LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                        WHERE (LOWER(r.status) IN ('completed', 'ready', 'online') OR r.date_ready IS NOT NULL)
                            AND DATE(COALESCE(r.completion_time, r.date_ready)) >= DATE('now', '-30 days')
                        GROUP BY DATE(COALESCE(r.completion_time, r.date_ready))
                        ORDER BY completion_date DESC
                    """)
                    recent_trends = cursor.fetchall()
                    
                    # Performance metrics by region
                    cursor = conn.execute("""
                        SELECT
                            COALESCE(cf.region, r.region, 'UNKNOWN') as region,
                            COUNT(*) as total_completions,
                            AVG(r.processing_duration) as avg_processing_time,
                            MIN(r.processing_duration) as min_processing_time,
                            MAX(r.processing_duration) as max_processing_time,
                            SUM(r.file_size) as total_file_size,
                            COUNT(DISTINCT COALESCE(cf.variable_type, r.variable_type, 'unknown')) as variables_count
                        FROM rda_requests r
                        LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                        WHERE (LOWER(r.status) IN ('completed', 'ready', 'online') OR r.date_ready IS NOT NULL)
                            AND r.processing_duration IS NOT NULL
                        GROUP BY COALESCE(cf.region, r.region, 'UNKNOWN')
                        ORDER BY total_completions DESC
                    """)
                    regional_performance = cursor.fetchall()
                
                # Calculate completion timeline span
                timeline_span_days = None
                if overall_stats['earliest_completion'] and overall_stats['latest_completion']:
                    timeline_span_days = self._calculate_date_span_days(
                        overall_stats['earliest_completion'],
                        overall_stats['latest_completion']
                    )
                
                # Calculate completion rate (completions per day)
                completion_rate_per_day = 0.0
                if timeline_span_days and timeline_span_days > 0:
                    completion_rate_per_day = overall_stats['total_completed_requests'] / timeline_span_days
                
                # Format frequent combinations
                formatted_combinations = []
                for combo in frequent_combinations:
                    formatted_combinations.append({
                        'region': combo['region'],
                        'variable_type': combo['variable_type'],
                        'variable_display_name': self._get_variable_display_name(combo['variable_type']),
                        'completion_count': combo['completion_count'],
                        'avg_processing_time_hours': combo['avg_processing_time'] or 0.0,
                        'avg_processing_time_display': self._format_processing_time_display(combo['avg_processing_time']),
                        'last_completion': combo['last_completion']
                    })
                
                # Format recent trends
                formatted_trends = []
                for trend in recent_trends:
                    formatted_trends.append({
                        'date': trend['completion_date'],
                        'daily_completions': trend['daily_completions'],
                        'regions_completed': trend['regions_completed'],
                        'avg_processing_time_hours': trend['avg_processing_time'] or 0.0,
                        'avg_processing_time_display': self._format_processing_time_display(trend['avg_processing_time'])
                    })
                
                # Format regional performance
                formatted_regional_performance = []
                for region in regional_performance:
                    formatted_regional_performance.append({
                        'region': region['region'],
                        'region_name': region['region'].replace('_', ' ').title() if region['region'] != 'UNKNOWN' else 'Unknown Region',
                        'total_completions': region['total_completions'],
                        'performance_metrics': {
                            'avg_processing_time_hours': region['avg_processing_time'] or 0.0,
                            'min_processing_time_hours': region['min_processing_time'] or 0.0,
                            'max_processing_time_hours': region['max_processing_time'] or 0.0,
                            'avg_processing_time_display': self._format_processing_time_display(region['avg_processing_time']),
                            'processing_time_range': f"{self._format_processing_time_display(region['min_processing_time'])} - {self._format_processing_time_display(region['max_processing_time'])}"
                        },
                        'file_metrics': {
                            'total_file_size_bytes': region['total_file_size'] or 0,
                            'total_file_size_mb': (region['total_file_size'] or 0) / (1024 * 1024),
                            'avg_file_size_bytes': (region['total_file_size'] or 0) / region['total_completions'] if region['total_completions'] > 0 else 0
                        },
                        'variables_count': region['variables_count']
                    })
                
                # Calculate success rates and trends
                success_rate = 100.0  # All requests in this query are completed
                
                # Build comprehensive summary response
                summary_response = {
                    'overall_statistics': {
                        'total_completed_requests': overall_stats['total_completed_requests'],
                        'total_regions_completed': overall_stats['total_regions_completed'],
                        'total_variables_completed': overall_stats['total_variables_completed'],
                        'success_rate': success_rate,
                        'timeline': {
                            'earliest_completion': overall_stats['earliest_completion'],
                            'latest_completion': overall_stats['latest_completion'],
                            'timeline_span_days': timeline_span_days,
                            'completion_rate_per_day': completion_rate_per_day
                        },
                        'performance_summary': {
                            'avg_processing_hours': overall_stats['avg_processing_hours'] or 0.0,
                            'avg_processing_display': self._format_processing_time_display(overall_stats['avg_processing_hours']),
                            'total_file_size_bytes': overall_stats['total_file_size_bytes'] or 0,
                            'total_file_size_gb': (overall_stats['total_file_size_bytes'] or 0) / (1024**3)
                        }
                    },
                    'completion_trends': {
                        'recent_activity': formatted_trends,
                        'trend_analysis': {
                            'total_days_analyzed': len(formatted_trends),
                            'avg_daily_completions': sum(t['daily_completions'] for t in formatted_trends) / len(formatted_trends) if formatted_trends else 0,
                            'peak_day': max(formatted_trends, key=lambda x: x['daily_completions']) if formatted_trends else None,
                            'trend_direction': self._analyze_completion_trend(formatted_trends)
                        }
                    },
                    'most_frequent_combinations': formatted_combinations,
                    'regional_performance': formatted_regional_performance,
                    'performance_insights': {
                        'fastest_region': min(formatted_regional_performance, key=lambda x: x['performance_metrics']['avg_processing_time_hours']) if formatted_regional_performance else None,
                        'most_active_region': max(formatted_regional_performance, key=lambda x: x['total_completions']) if formatted_regional_performance else None,
                        'largest_files_region': max(formatted_regional_performance, key=lambda x: x['file_metrics']['total_file_size_bytes']) if formatted_regional_performance else None
                    },
                    'metadata': {
                        'data_freshness': self._get_data_freshness_info(),
                        'analysis_scope': 'all_completed_requests',
                        'recent_trends_days': 30
                    },
                    'timestamp': datetime.now().isoformat(),
                    'data_source': 'comprehensive_database_analysis'
                }
                
                self.logger.info(f"DEBUG: Returning completed regions summary: {overall_stats['total_completed_requests']} total completions")
                return jsonify(summary_response)
                
            except Exception as e:
                self.logger.error(f"Error getting completed regions summary: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/resolution-details/<request_id>')
        def api_resolution_details(request_id):
            """API endpoint for detailed resolution information."""
            try:
                details = self.unknown_region_resolver.get_resolution_details(request_id)
                return jsonify(details)
            except Exception as e:
                self.logger.error(f"Error getting resolution details: {e}")
                return jsonify({'error': str(e)}), 500
        
        # Note: Removed unused error dashboard/visualization API endpoints
        # The dashboard now uses only the core working error handling and monitoring system
        
        # Enhanced API endpoints with progress tracking
        @self.app.route('/api/status')
        def api_status():
            """API endpoint for system status overview with progress tracking."""
            try:
                # Get basic system status with progress tracking
                with self._get_db_connection() as conn:
                    cursor = conn.execute("""
                        SELECT
                            COUNT(*) as total_requests,
                            COUNT(CASE WHEN LOWER(status) = 'completed' THEN 1 END) as completed,
                            COUNT(CASE WHEN LOWER(status) = 'processing' THEN 1 END) as processing,
                            COUNT(CASE WHEN LOWER(status) LIKE '%queued%' THEN 1 END) as queued,
                            COUNT(CASE WHEN LOWER(status) LIKE '%purge%' THEN 1 END) as purged
                        FROM rda_requests
                    """)
                    stats = cursor.fetchone()
                
                # Calculate progress metrics
                total = stats['total_requests']
                completed = stats['completed']
                remaining = total - completed
                progress_percentage = (completed / total * 100) if total > 0 else 0
                
                # Get sync status
                sync_status = self.real_time_sync.get_live_sync_status()
                freshness_info = self._get_data_freshness_info()
                
                return jsonify({
                    'system_status': 'operational',
                    'database_status': 'connected',
                    'total_requests': total,
                    'completed_requests': completed,
                    'remaining_requests': remaining,
                    'processing_requests': stats['processing'],
                    'queued_requests': stats['queued'],
                    'purged_requests': stats['purged'],
                    'progress_tracking': {
                        'files_done': completed,
                        'files_remaining': remaining,
                        'progress_percentage': progress_percentage,
                        'completion_status': 'in_progress' if remaining > 0 else 'completed'
                    },
                    'sync_status': {
                        'status': sync_status.status.value,
                        'last_sync': sync_status.last_sync.isoformat() if sync_status.last_sync else None,
                        'sync_count': sync_status.sync_count,
                        'error_count': sync_status.error_count
                    },
                    'data_freshness': freshness_info,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error getting system status: {e}")
                return jsonify({
                    'system_status': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        @self.app.route('/api/variable-summary')
        def api_variable_summary():
            """API endpoint for weather variable summary."""
            try:
                # Get variable summary from weather variable metrics
                variable_metrics = self.get_weather_variable_metrics()
                
                # Transform to summary format
                variable_summary = []
                for metric in variable_metrics:
                    variable_summary.append({
                        'variable_type': metric.variable_type,
                        'display_name': self._get_variable_display_name(metric.variable_type),
                        'total_requests': metric.total_requests,
                        'completed_requests': metric.completed_requests,
                        'success_rate': metric.success_rate,
                        'most_active_regions': metric.most_active_regions,
                        'date_range': metric.date_range
                    })
                
                return jsonify({
                    'variable_summary': variable_summary,
                    'total_variables': len(variable_summary),
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error getting variable summary: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/recent-activity')
        def api_recent_activity():
            """API endpoint for recent activity feed."""
            try:
                limit = request.args.get('limit', 50, type=int)
                
                # Get recent requests with activity
                with self._get_db_connection() as conn:
                    cursor = conn.execute("""
                        SELECT
                            r.request_id,
                            r.request_index,
                            r.status,
                            r.date_rqst,
                            r.date_ready,
                            r.completion_time,
                            r.region,
                            r.variable_type,
                            cf.region as cf_region,
                            cf.variable_type as cf_variable_type
                        FROM rda_requests r
                        LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                        ORDER BY
                            CASE
                                WHEN r.completion_time IS NOT NULL THEN r.completion_time
                                WHEN r.date_ready IS NOT NULL THEN r.date_ready
                                WHEN r.date_rqst IS NOT NULL THEN r.date_rqst
                                ELSE '1970-01-01'
                            END DESC
                        LIMIT ?
                    """, (limit,))
                    recent_requests = cursor.fetchall()
                
                # Format activity feed
                activity_feed = []
                for req in recent_requests:
                    region = req['cf_region'] or req['region'] or 'UNKNOWN'
                    variable = req['cf_variable_type'] or req['variable_type'] or 'unknown'
                    
                    # Determine activity type and timestamp
                    if req['completion_time']:
                        activity_type = 'completed'
                        timestamp = req['completion_time']
                    elif req['date_ready']:
                        activity_type = 'ready'
                        timestamp = req['date_ready']
                    elif req['date_rqst']:
                        activity_type = 'submitted'
                        timestamp = req['date_rqst']
                    else:
                        activity_type = 'unknown'
                        timestamp = None
                    
                    activity_feed.append({
                        'request_id': req['request_id'],
                        'request_index': req['request_index'],
                        'activity_type': activity_type,
                        'status': req['status'],
                        'region': region,
                        'variable_type': variable,
                        'variable_display_name': self._get_variable_display_name(variable),
                        'timestamp': timestamp,
                        'formatted_timestamp': self._safe_parse_datetime(timestamp, 'activity_timestamp').strftime('%Y-%m-%d %H:%M:%S') if timestamp and self._safe_parse_datetime(timestamp, 'activity_timestamp') else 'N/A'
                    })
                
                return jsonify({
                    'recent_activity': activity_feed,
                    'total_items': len(activity_feed),
                    'limit': limit,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error getting recent activity: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/progress-tracking')
        def api_progress_tracking():
            """API endpoint for comprehensive progress tracking data."""
            try:
                # Trigger sync if needed for fresh data
                self._trigger_sync_if_needed("get_progress_tracking")
                
                # Get comprehensive progress statistics
                with self._get_db_connection() as conn:
                    cursor = conn.execute("""
                        SELECT
                            COUNT(*) as total_requests,
                            COUNT(CASE WHEN LOWER(r.status) = 'completed' THEN 1 END) as completed,
                            COUNT(CASE WHEN LOWER(r.status) = 'processing' THEN 1 END) as processing,
                            COUNT(CASE WHEN LOWER(r.status) LIKE '%queued%' THEN 1 END) as queued,
                            COUNT(CASE WHEN LOWER(r.status) LIKE '%purge%' THEN 1 END) as purged,
                            COUNT(DISTINCT COALESCE(cf.region, 'UNKNOWN')) as unique_regions,
                            COUNT(DISTINCT COALESCE(cf.variable_type, 'unknown')) as unique_variables
                        FROM rda_requests r
                        LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                    """)
                    stats = cursor.fetchone()
                
                # Calculate progress metrics
                total = stats['total_requests']
                completed = stats['completed']
                processing = stats['processing']
                queued = stats['queued']
                purged = stats['purged']
                
                files_done = completed
                files_remaining = total - completed
                progress_percentage = (completed / total * 100) if total > 0 else 0
                
                # Get regional progress breakdown
                cursor = conn.execute("""
                    SELECT
                        COALESCE(cf.region, 'UNKNOWN') as region,
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN LOWER(r.status) = 'completed' THEN 1 END) as completed_requests,
                        COUNT(CASE WHEN LOWER(r.status) = 'processing' THEN 1 END) as processing_requests,
                        COUNT(CASE WHEN LOWER(r.status) LIKE '%queued%' THEN 1 END) as queued_requests
                    FROM rda_requests r
                    LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                    GROUP BY COALESCE(cf.region, 'UNKNOWN')
                    ORDER BY completed_requests DESC
                """)
                regional_progress = []
                for row in cursor.fetchall():
                    region_total = row['total_requests']
                    region_completed = row['completed_requests']
                    region_progress = (region_completed / region_total * 100) if region_total > 0 else 0
                    
                    regional_progress.append({
                        'region': row['region'],
                        'total_requests': region_total,
                        'completed_requests': region_completed,
                        'processing_requests': row['processing_requests'],
                        'queued_requests': row['queued_requests'],
                        'files_done': region_completed,
                        'files_remaining': region_total - region_completed,
                        'progress_percentage': region_progress
                    })
                
                # Get variable progress breakdown
                cursor = conn.execute("""
                    SELECT
                        COALESCE(cf.variable_type, 'unknown') as variable_type,
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN LOWER(r.status) = 'completed' THEN 1 END) as completed_requests,
                        COUNT(CASE WHEN LOWER(r.status) = 'processing' THEN 1 END) as processing_requests,
                        COUNT(CASE WHEN LOWER(r.status) LIKE '%queued%' THEN 1 END) as queued_requests
                    FROM rda_requests r
                    LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                    GROUP BY COALESCE(cf.variable_type, 'unknown')
                    ORDER BY completed_requests DESC
                """)
                variable_progress = []
                for row in cursor.fetchall():
                    var_total = row['total_requests']
                    var_completed = row['completed_requests']
                    var_progress = (var_completed / var_total * 100) if var_total > 0 else 0
                    
                    variable_progress.append({
                        'variable_type': row['variable_type'],
                        'variable_display_name': self._get_variable_display_name(row['variable_type']),
                        'total_requests': var_total,
                        'completed_requests': var_completed,
                        'processing_requests': row['processing_requests'],
                        'queued_requests': row['queued_requests'],
                        'files_done': var_completed,
                        'files_remaining': var_total - var_completed,
                        'progress_percentage': var_progress
                    })
                
                return jsonify({
                    'overall_progress': {
                        'total_files': total,
                        'files_done': files_done,
                        'files_remaining': files_remaining,
                        'progress_percentage': progress_percentage,
                        'status_breakdown': {
                            'completed': completed,
                            'processing': processing,
                            'queued': queued,
                            'purged': purged
                        }
                    },
                    'regional_progress': regional_progress,
                    'variable_progress': variable_progress,
                    'summary_stats': {
                        'unique_regions': stats['unique_regions'],
                        'unique_variables': stats['unique_variables'],
                        'completion_status': 'completed' if files_remaining == 0 else 'in_progress'
                    },
                    'timestamp': datetime.now().isoformat(),
                    'data_source': 'rda_requests (progress tracking)'
                })
                
            except Exception as e:
                self.logger.error(f"Error getting progress tracking data: {e}")
                return jsonify({'error': str(e)}), 500
        
        # Timeline Validation API Endpoints
        @self.app.route('/api/timeline-validation/statistics')
        def api_timeline_validation_statistics():
            """API endpoint for timeline validation statistics."""
            try:
                # Get statistics from validation services
                timestamp_stats = self.timestamp_validator.get_parsing_statistics()
                timeline_stats = self.timeline_validator.get_validation_statistics()
                processing_stats = self.processing_time_calculator.get_calculation_statistics()
                
                return jsonify({
                    'timestamp_parsing': timestamp_stats,
                    'timeline_validation': timeline_stats,
                    'processing_time_calculation': processing_stats.to_dict(),
                    'summary': {
                        'total_timestamp_attempts': timestamp_stats['total_attempts'],
                        'timestamp_success_rate': timestamp_stats['success_rate_percentage'],
                        'total_timeline_validations': timeline_stats['total_validations'],
                        'timeline_success_rate': timeline_stats['success_rate_percentage'],
                        'total_processing_calculations': processing_stats.total_calculations,
                        'processing_success_rate': (processing_stats.successful_calculations / processing_stats.total_calculations * 100) if processing_stats.total_calculations > 0 else 0
                    },
                    'generated_at': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error getting timeline validation statistics: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/timeline-validation/health-check')
        def api_timeline_validation_health():
            """API endpoint for timeline validation health check."""
            try:
                # Test the validation services with sample data
                test_timestamp = "2024-01-15T10:30:00Z"
                test_result = self.timestamp_validator.parse_timestamp(test_timestamp, "health_check")
                
                health_status = {
                    'timestamp_validator': {
                        'status': 'healthy' if test_result.is_valid else 'degraded',
                        'confidence': test_result.confidence_score,
                        'issues': len(test_result.issues)
                    },
                    'timeline_validator': {
                        'status': 'healthy',  # Basic health check
                        'service_available': hasattr(self.timeline_validator, 'validate_timeline')
                    },
                    'processing_calculator': {
                        'status': 'healthy',  # Basic health check
                        'service_available': hasattr(self.processing_time_calculator, 'calculate_processing_time')
                    },
                    'overall_health': 'healthy',
                    'last_check': datetime.now().isoformat()
                }
                
                # Determine overall health
                if not test_result.is_valid or test_result.confidence_score < 0.5:
                    health_status['overall_health'] = 'degraded'
                
                return jsonify(health_status)
            except Exception as e:
                self.logger.error(f"Error in timeline validation health check: {e}")
                return jsonify({
                    'overall_health': 'unhealthy',
                    'error': str(e),
                    'last_check': datetime.now().isoformat()
                }), 500
        
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({'error': 'Not found'}), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({'error': 'Internal server error'}), 500
    
    def _calculate_system_health_score(self, error_summary: Dict[str, Any],
                                     retry_status: Dict[str, Any],
                                     overall_progress: Dict[str, Any]) -> float:
        """
        Calculate overall system health score (0-100).
        
        Args:
            error_summary: Error summary data
            retry_status: Retry queue status data
            overall_progress: Overall progress data
            
        Returns:
            Health score between 0 and 100
        """
        try:
            base_score = 100.0
            
            # Deduct points for errors
            if 'summary' in error_summary:
                error_data = error_summary['summary']
                active_errors = error_data.get('active_errors', 0)
                critical_errors = error_data.get('critical_errors', 0)
                error_rate = error_data.get('error_rate_24h', 0)
                
                # Deduct points based on error severity
                base_score -= min(active_errors * 2, 20)  # Max 20 points for active errors
                base_score -= min(critical_errors * 5, 25)  # Max 25 points for critical errors
                base_score -= min(error_rate * 1, 15)  # Max 15 points for error rate
            
            # Deduct points for retry queue issues
            if 'queue_status' in retry_status:
                queue_data = retry_status['queue_status']
                failed_items = queue_data.get('failed_items', 0)
                success_rate = queue_data.get('success_rate', 100)
                
                base_score -= min(failed_items * 1, 10)  # Max 10 points for failed retries
                base_score -= min((100 - success_rate) * 0.2, 10)  # Max 10 points for low success rate
            
            # Deduct points for slow progress
            if 'progress' in overall_progress:
                progress_data = overall_progress['progress']
                completion_percentage = progress_data.get('completion_percentage', 0)
                processing_rate = progress_data.get('processing_rate_per_hour', 0)
                
                # Deduct points if progress is very slow
                if processing_rate < 0.5:  # Less than 0.5 files per hour
                    base_score -= 10
            
            return max(0.0, min(100.0, base_score))
            
        except Exception as e:
            self.logger.error(f"Error calculating system health score: {e}")
            return 50.0  # Default neutral score
    
    def _generate_system_alerts(self, error_summary: Dict[str, Any],
                              retry_status: Dict[str, Any],
                              overall_progress: Dict[str, Any],
                              regional_health: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate system alerts based on current metrics.
        
        Args:
            error_summary: Error summary data
            retry_status: Retry queue status data
            overall_progress: Overall progress data
            regional_health: Regional health data
            
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        try:
            # Critical error alerts
            if 'summary' in error_summary:
                error_data = error_summary['summary']
                critical_errors = error_data.get('critical_errors', 0)
                error_rate = error_data.get('error_rate_24h', 0)
                
                if critical_errors > 5:
                    alerts.append({
                        'level': 'critical',
                        'category': 'errors',
                        'title': 'High Critical Error Count',
                        'message': f'{critical_errors} critical errors detected',
                        'action': 'Review and resolve critical errors immediately',
                        'timestamp': datetime.now().isoformat()
                    })
                
                if error_rate > 10:
                    alerts.append({
                        'level': 'warning',
                        'category': 'errors',
                        'title': 'High Error Rate',
                        'message': f'Error rate: {error_rate:.1f} errors/hour',
                        'action': 'Investigate error patterns and root causes',
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Retry queue alerts
            if 'queue_status' in retry_status:
                queue_data = retry_status['queue_status']
                pending_items = queue_data.get('pending_items', 0)
                success_rate = queue_data.get('success_rate', 100)
                
                if pending_items > 100:
                    alerts.append({
                        'level': 'warning',
                        'category': 'retry_queue',
                        'title': 'Large Retry Queue',
                        'message': f'{pending_items} items pending retry',
                        'action': 'Monitor retry queue processing and capacity',
                        'timestamp': datetime.now().isoformat()
                    })
                
                if success_rate < 70:
                    alerts.append({
                        'level': 'critical',
                        'category': 'retry_queue',
                        'title': 'Low Retry Success Rate',
                        'message': f'Retry success rate: {success_rate:.1f}%',
                        'action': 'Review retry strategies and error patterns',
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Progress alerts
            if 'progress' in overall_progress:
                progress_data = overall_progress['progress']
                processing_rate = progress_data.get('processing_rate_per_hour', 0)
                
                if processing_rate < 0.1:
                    alerts.append({
                        'level': 'warning',
                        'category': 'progress',
                        'title': 'Slow Processing Rate',
                        'message': f'Processing rate: {processing_rate:.2f} files/hour',
                        'action': 'Check system capacity and processing bottlenecks',
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Regional health alerts
            if 'regional_health' in regional_health:
                for region_data in regional_health['regional_health']:
                    health_score = region_data.get('health_score', 100)
                    if health_score < 50:
                        alerts.append({
                            'level': 'warning',
                            'category': 'regional_health',
                            'title': f'Poor Regional Health: {region_data["region"]}',
                            'message': f'Health score: {health_score:.1f}/100',
                            'action': f'Review errors and processing for {region_data["region"]}',
                            'timestamp': datetime.now().isoformat()
                        })
            
            # Data freshness alerts
            freshness_info = self._get_data_freshness_info()
            if not freshness_info.get('is_fresh', True):
                level = 'critical' if freshness_info.get('level') == 'critical' else 'warning'
                alerts.append({
                    'level': level,
                    'category': 'data_freshness',
                    'title': 'Stale Data Detected',
                    'message': freshness_info.get('warning_message', 'Data is not fresh'),
                    'action': 'Trigger data sync or check sync engine status',
                    'timestamp': datetime.now().isoformat()
                })
            
        except Exception as e:
            self.logger.error(f"Error generating system alerts: {e}")
            alerts.append({
                'level': 'error',
                'category': 'system',
                'title': 'Alert Generation Error',
                'message': f'Error generating alerts: {str(e)}',
                'action': 'Check dashboard system health',
                'timestamp': datetime.now().isoformat()
            })
        
        return alerts
    
    def create_dashboard_template(self):
        """Create enhanced HTML template for the dashboard."""
        # Use absolute path to templates directory
        current_dir = Path(__file__).parent.parent  # Go up from automation/ to src/python/
        template_dir = current_dir / 'templates'
        template_dir.mkdir(exist_ok=True)
        
        # Create enhanced template with real-time sync indicators
        enhanced_template = '''<!DOCTYPE html>
<html>
<head>
    <title>Enhanced RDA Dashboard - Real-Time Sync</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center; position: relative; }
        
        /* Real-time sync status indicators */
        .sync-status-bar {
            background: rgba(255,255,255,0.1);
            padding: 10px 20px;
            border-radius: 8px;
            margin-top: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        .sync-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9em;
        }
        .sync-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        .sync-dot.fresh { background: #28a745; }
        .sync-dot.acceptable { background: #ffc107; }
        .sync-dot.stale { background: #fd7e14; }
        .sync-dot.critical { background: #dc3545; }
        .sync-dot.syncing { background: #007bff; animation: spin 1s linear infinite; }
        .sync-dot.error { background: #dc3545; animation: flash 1s infinite; }
        
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes flash { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        
        .freshness-warning {
            background: rgba(255, 193, 7, 0.2);
            color: #856404;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.85em;
            margin-top: 10px;
            border-left: 4px solid #ffc107;
        }
        .freshness-critical {
            background: rgba(220, 53, 69, 0.2);
            color: #721c24;
            border-left-color: #dc3545;
        }
        
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); position: relative; }
        .metric-value { font-size: 2em; font-weight: bold; color: #2196F3; }
        .metric-label { color: #666; margin-top: 5px; }
        
        /* Enhanced buttons */
        .refresh-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            border: 2px solid rgba(255,255,255,0.3);
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 0 5px;
        }
        .refresh-btn:hover { background: rgba(255,255,255,0.3); }
        .refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .sync-btn {
            background: rgba(40, 167, 69, 0.8);
            border-color: rgba(40, 167, 69, 0.8);
        }
        .sync-btn:hover { background: rgba(40, 167, 69, 1); }
        
        .table-container { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; overflow: hidden; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: 600; }
        .status-badge { padding: 4px 8px; border-radius: 12px; font-size: 0.8em; }
        .status-processing { background: #cce5ff; color: #004085; }
        .status-completed { background: #d4edda; color: #155724; }
        .status-failed { background: #f8d7da; color: #721c24; }
        .status-pending { background: #fff3cd; color: #856404; }
        
        /* Loading states */
        .loading { opacity: 0.6; pointer-events: none; }
        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #007bff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌦️ Enhanced RDA Automation Dashboard</h1>
        <p>Real-time monitoring of weather data requests</p>
        <button class="refresh-btn" onclick="refreshData()">🔄 Refresh Data</button>
        <p>Last updated: <span id="lastUpdate">Loading...</span></p>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-value" id="totalRequests">-</div>
            <div class="metric-label">Total Requests</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="completedRequests">-</div>
            <div class="metric-label">Completed</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="processingRequests">-</div>
            <div class="metric-label">Processing</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="failedRequests">-</div>
            <div class="metric-label">Purged</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="uniqueRegions">-</div>
            <div class="metric-label">Active Regions</div>
        </div>
    </div>
    
    <div class="table-container">
        <h3 style="padding: 20px; margin: 0; background: #f8f9fa;">📋 Current Requests</h3>
        <table id="requestsTable">
            <thead>
                <tr>
                    <th>Region</th>
                    <th>Weather Variable</th>
                    <th>Status</th>
                    <th>Submitted</th>
                    <th>Processing Time</th>
                    <th>Request Index</th>
                </tr>
            </thead>
            <tbody id="requestsTableBody">
                <tr><td colspan="6" style="text-align: center; padding: 40px;">Loading requests...</td></tr>
            </tbody>
        </table>
    </div>
    
    <div class="table-container">
        <h3 style="padding: 20px; margin: 0; background: #f8f9fa;">🗺️ Regional Performance</h3>
        <table id="regionalTable">
            <thead>
                <tr>
                    <th>Region</th>
                    <th>Total Requests</th>
                    <th>Success Rate</th>
                    <th>Most Common Variable</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody id="regionalTableBody">
                <tr><td colspan="5" style="text-align: center; padding: 40px;">Loading regional data...</td></tr>
            </tbody>
        </table>
    </div>
    
    <div class="table-container">
        <h3 style="padding: 20px; margin: 0; background: #f8f9fa;">🌡️ Weather Variable Analysis</h3>
        <table id="variableTable">
            <thead>
                <tr>
                    <th>Weather Variable</th>
                    <th>Total Requests</th>
                    <th>Success Rate</th>
                    <th>Most Active Regions</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody id="variableTableBody">
                <tr><td colspan="5" style="text-align: center; padding: 40px;">Loading weather variable data...</td></tr>
            </tbody>
        </table>
    </div>
    
    <script>
        function formatTime(timeStr) {
            if (!timeStr) return 'N/A';
            return new Date(timeStr).toLocaleString();
        }
        
        function formatProcessingTime(hours) {
            if (!hours) return 'N/A';
            if (hours < 1) return Math.round(hours * 60) + ' min';
            return hours.toFixed(1) + ' hrs';
        }
        
        function getStatusBadge(status) {
            return `<span class="status-badge status-${status}">${status.charAt(0).toUpperCase() + status.slice(1)}</span>`;
        }
        
        function getParameterDisplayName(param) {
            const names = {
                'dswrf': 'Solar Radiation',
                'ugrd_vgrd': 'Wind Speed',
                'tmp_dpt': 'Temperature',
                'apcp': 'Precipitation'
            };
            return names[param] || param.toUpperCase();
        }
        
        async function refreshData() {
            try {
                // Update summary metrics
                const summaryResponse = await fetch('/api/summary');
                const summaryData = await summaryResponse.json();
                updateSummaryMetrics(summaryData);
                
                // Update current requests
                const requestsResponse = await fetch('/api/current-requests');
                const requestsData = await requestsResponse.json();
                updateRequestsTable(requestsData);
                
                // Update regional metrics
                const regionalResponse = await fetch('/api/regional-metrics');
                const regionalData = await regionalResponse.json();
                updateRegionalTable(regionalData);
                
                // Update weather variable metrics
                const variableResponse = await fetch('/api/weather-variable-metrics');
                const variableData = await variableResponse.json();
                updateVariableTable(variableData);
                
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Error refreshing data:', error);
            }
        }
        
        function updateSummaryMetrics(data) {
            const overview = data.overview;
            document.getElementById('totalRequests').textContent = overview.total_requests || 0;
            document.getElementById('completedRequests').textContent = overview.completed_requests || 0;
            document.getElementById('processingRequests').textContent = (overview.processing_requests || 0) + (overview.queued_requests || 0);
            document.getElementById('failedRequests').textContent = overview.purged_requests || 0;
            document.getElementById('uniqueRegions').textContent = overview.unique_regions || 0;
        }
        
        function updateRequestsTable(requests) {
            const tbody = document.getElementById('requestsTableBody');
            if (requests.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 40px;">No requests found</td></tr>';
                return;
            }
            
            tbody.innerHTML = requests.map(req => `
                <tr>
                    <td>${req.region || 'UNKNOWN'}</td>
                    <td>${getParameterDisplayName(req.variable_type || 'unknown')}</td>
                    <td>${getStatusBadge(req.status)}</td>
                    <td>${formatTime(req.date_rqst)}</td>
                    <td>${formatProcessingTime(req.processing_time_hours)}</td>
                    <td>${req.request_index}</td>
                </tr>
            `).join('');
        }
        
        function updateRegionalTable(regions) {
            const tbody = document.getElementById('regionalTableBody');
            if (regions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 40px;">No regional data found</td></tr>';
                return;
            }
            
            tbody.innerHTML = regions.map(region => `
                <tr>
                    <td><strong>${region.region}</strong></td>
                    <td>${region.total_requests}</td>
                    <td>${region.success_rate.toFixed(1)}%</td>
                    <td>${getParameterDisplayName(region.most_common_variable)}</td>
                    <td>
                        <small>
                            ✅ ${region.completed_requests} |
                            🔄 ${region.processing_requests} |
                            🗑️ ${region.purged_requests}
                        </small>
                    </td>
                </tr>
            `).join('');
        }
        
        function updateVariableTable(variables) {
            const tbody = document.getElementById('variableTableBody');
            if (variables.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 40px;">No weather variable data found</td></tr>';
                return;
            }
            
            tbody.innerHTML = variables.map(variable => `
                <tr>
                    <td><strong>${getParameterDisplayName(variable.variable_type)}</strong></td>
                    <td>${variable.total_requests}</td>
                    <td>${variable.success_rate.toFixed(1)}%</td>
                    <td>${variable.most_active_regions.join(', ')}</td>
                    <td>
                        <small>
                            ✅ ${variable.completed_requests} |
                            🔄 ${variable.processing_requests} |
                            🗑️ ${variable.purged_requests}
                        </small>
                    </td>
                </tr>
            `).join('');
        }
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            refreshData();
            // Auto-refresh every 30 seconds
            setInterval(refreshData, 30000);
        });
    </script>
</body>
</html>'''
        
        # Template file already exists - no need to recreate it
        pass
        
        self.logger.info(f"Created enhanced dashboard template at {template_dir / 'enhanced_dashboard.html'}")
    
    def start_dashboard(self, host: str = '0.0.0.0', port: int = 8080, debug: bool = False):
        """
        Start the enhanced dashboard server with automatic port conflict resolution.
        
        Args:
            host: Host to bind to
            port: Port to bind to (will auto-increment if in use)
            debug: Enable debug mode
        """
        self.create_dashboard_template()
        
        # Try multiple ports to avoid conflicts (especially port 5000 on macOS)
        max_attempts = 10
        current_port = port
        
        for attempt in range(max_attempts):
            try:
                self.logger.info(f"Starting Enhanced RDA Dashboard on http://{host}:{current_port}")
                self.app.run(host=host, port=current_port, debug=debug, use_reloader=False, threaded=True)
                break
            except OSError as e:
                if "Address already in use" in str(e):
                    if current_port == 5000:
                        self.logger.warning(f"Port 5000 is in use (likely AirPlay Receiver on macOS), trying port 8080")
                        current_port = 8080
                    else:
                        self.logger.warning(f"Port {current_port} is in use, trying port {current_port + 1}")
                        current_port += 1
                    
                    if attempt == max_attempts - 1:
                        self.logger.error(f"Could not find available port after {max_attempts} attempts")
                        raise
                else:
                    raise


def create_dashboard(db_path: str = "src/python/data/automation_state.db") -> EnhancedRDADashboard:
    """
    Factory function to create an Enhanced RDA Dashboard.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Configured EnhancedRDADashboard instance
    """
    return EnhancedRDADashboard(db_path)


def main():
    """Main function for running the dashboard."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced RDA Automation Dashboard')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Path to database file')
    
    args = parser.parse_args()
    
    # Create and start dashboard
    dashboard = create_dashboard(args.db_path)
    
    print(f"""
🌦️  Enhanced RDA Automation Dashboard
=====================================

Starting dashboard server...
URL: http://{args.host}:{args.port}
Database: {args.db_path}
Debug Mode: {args.debug}

Features:
- 📊 Real-time overview metrics
- 📋 Current requests with region and weather variable details
- 🗺️  Regional performance insights
- 🌡️  Weather variable analysis
- ⚠️  Error and retry statistics

Press Ctrl+C to stop the server.
""")
    
    try:
        dashboard.start_dashboard(args.host, args.port, args.debug)
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")


if __name__ == '__main__':
    main()
            