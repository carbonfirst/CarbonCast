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

# Import existing modules
from automation.error_manager import ErrorManager, create_error_manager
from automation.retry_manager import RetryManager, create_retry_manager
from automation.data_sync import RDADataSyncService, create_data_sync_service
from automation.real_time_sync_engine import RealTimeSyncEngine, create_real_time_sync_engine, DataFreshnessLevel, SyncStatus
from automation.unknown_region_resolver import EnhancedUnknownRegionResolver

# Import new enhanced monitoring modules
from automation.error_dashboard_api import create_error_dashboard_api
from automation.progress_tracker_api import create_progress_tracker_api
from automation.dashboard_enhancements import create_dashboard_enhancements


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
        
        # Initialize enhanced monitoring APIs
        try:
            self.error_dashboard_api = create_error_dashboard_api(db_path)
            self.progress_tracker_api = create_progress_tracker_api(db_path)
            self.dashboard_enhancements = create_dashboard_enhancements(db_path)
            self.logger.info("Enhanced monitoring APIs initialized successfully")
        except Exception as e:
            self.logger.warning(f"Could not initialize enhanced monitoring APIs: {e}")
            # Create minimal fallback APIs
            self.error_dashboard_api = type('ErrorDashboardAPI', (), {
                'get_error_summary': lambda: {'error': 'API not available'},
                'get_live_error_feed': lambda **kwargs: {'errors': [], 'error': 'API not available'},
                'get_regional_error_health': lambda: {'regional_health': [], 'error': 'API not available'},
                'get_error_trends': lambda **kwargs: {'trends': [], 'error': 'API not available'},
                'get_retry_queue_status': lambda: {'queue_status': {}, 'error': 'API not available'}
            })()
            self.progress_tracker_api = type('ProgressTrackerAPI', (), {
                'get_overall_progress': lambda: {'progress': {}, 'error': 'API not available'},
                'get_regional_progress': lambda: {'regional_progress': [], 'error': 'API not available'},
                'get_variable_progress': lambda: {'variable_progress': [], 'error': 'API not available'},
                'get_progress_trends': lambda **kwargs: {'trends': [], 'error': 'API not available'}
            })()
            self.dashboard_enhancements = type('DashboardEnhancements', (), {
                'get_dashboard_layout': lambda: {'widgets': [], 'error': 'API not available'},
                'get_all_widget_data': lambda: {'widgets': {}, 'error': 'API not available'},
                'check_alerts': lambda: [],
                'get_dashboard_metrics': lambda: {'error': 'API not available'}
            })()
        
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
        
        # Setup routes
        self._setup_routes()
        
        # Remove traditional caching - use real-time sync instead
        # Cache is now handled by the real-time sync engine with immediate updates
        
        self.logger.info("Enhanced RDA Dashboard with Real-Time Sync initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the dashboard."""
        logger = logging.getLogger('rda_automation.dashboard')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def _safe_parse_datetime(self, date_str: str) -> Optional[datetime]:
        """
        Safely parse datetime strings with multiple format fallbacks.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not date_str:
            return None
            
        # List of common datetime formats to try
        formats_to_try = [
            # ISO formats
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ', 
            '%Y-%m-%dT%H:%M:%S.%f+00:00',
            '%Y-%m-%dT%H:%M:%S+00:00',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S',
            # Alternative formats
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            # RDA specific formats
            '%Y%m%d%H%M%S',
            '%Y%m%d'
        ]
        
        # Clean the date string
        cleaned_date = str(date_str).strip()
        
        # Try fromisoformat first (fastest for ISO dates)
        try:
            # Handle Z suffix
            if cleaned_date.endswith('Z'):
                cleaned_date = cleaned_date[:-1] + '+00:00'
            return datetime.fromisoformat(cleaned_date)
        except (ValueError, AttributeError):
            pass
        
        # Try each format
        for fmt in formats_to_try:
            try:
                return datetime.strptime(cleaned_date, fmt)
            except (ValueError, TypeError):
                continue
        
        # Log the problematic date string for debugging
        self.logger.warning(f"Could not parse date string: '{date_str}'")
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
                
                # Calculate processing time if applicable
                processing_time = None
                if row['date_rqst'] and row['status'].lower() in ['processing', 'completed']:
                    try:
                        start_time = self._safe_parse_datetime(row['date_rqst'])
                        if start_time:
                            end_time = datetime.now()
                            if row['date_ready']:
                                parsed_ready = self._safe_parse_datetime(row['date_ready'])
                                if parsed_ready:
                                    end_time = parsed_ready
                            # Remove timezone info for calculation
                            if start_time.tzinfo:
                                start_time = start_time.replace(tzinfo=None)
                            if hasattr(end_time, 'tzinfo') and end_time.tzinfo:
                                end_time = end_time.replace(tzinfo=None)
                            processing_time = (end_time - start_time).total_seconds() / 3600
                    except Exception as e:
                        self.logger.debug(f"Error calculating processing time: {e}")
                        pass
                
                # Extract region and variable from rinfo and subset_note if not in control_files_tracking
                region = row['region'] or self._extract_region_from_rinfo(row['rinfo'])
                variable_type = row['variable_type'] or self._extract_variable_from_subset_note(row['subset_note'])
                
                # Create enhanced request object with complete get_status information
                request_obj = {
                    'id': row['id'],
                    'request_index': row['request_index'],
                    'request_id': row['request_id'],
                    'dsid': row['dsid'],
                    'status': row['status'],
                    'date_rqst': row['date_rqst'],
                    'date_ready': row['date_ready'],
                    'date_purge': row['date_purge'],
                    'location': row['location'],
                    'ncar_contact': row['ncar_contact'],
                    'rinfo': row['rinfo'],
                    'subset_note': row['subset_note'],
                    'region': region,
                    'variable_type': variable_type,
                    'processing_time_hours': processing_time,
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
                        first_dt = self._safe_parse_datetime(data['first_request'])
                        first = first_dt.strftime('%Y-%m-%d') if first_dt else 'N/A'
                        last_dt = self._safe_parse_datetime(data['last_request'])
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
                        first_dt = self._safe_parse_datetime(data['first_request'])
                        first = first_dt.strftime('%Y-%m-%d') if first_dt else 'N/A'
                        last_dt = self._safe_parse_datetime(data['last_request'])
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
        
        Returns:
            Dictionary containing dashboard summary data with freshness information
        """
        # Trigger sync if needed for fresh data
        self._trigger_sync_if_needed("get_dashboard_summary")
        
        try:
            # Get basic statistics from rda_requests
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN LOWER(r.status) LIKE '%queued%' THEN 1 END) as queued,
                        COUNT(CASE WHEN LOWER(r.status) = 'processing' THEN 1 END) as processing,
                        COUNT(CASE WHEN LOWER(r.status) = 'completed' THEN 1 END) as completed,
                        COUNT(CASE WHEN LOWER(r.status) LIKE '%purge%' THEN 1 END) as purged,
                        COUNT(DISTINCT COALESCE(cf.region, 'UNKNOWN')) as unique_regions,
                        COUNT(DISTINCT COALESCE(cf.variable_type, 'unknown')) as unique_variables,
                        COUNT(DISTINCT r.dsid) as unique_datasets
                    FROM rda_requests r
                    LEFT JOIN control_files_tracking cf ON r.request_index = cf.request_index
                """)
                stats = cursor.fetchone()
            
            # Calculate rates
            total = stats['total_requests']
            completed = stats['completed']
            purged = stats['purged']
            success_rate = (completed / (completed + purged) * 100) if (completed + purged) > 0 else 0
            progress_percentage = (completed / total * 100) if total > 0 else 0
            
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
            
            return {
                'overview': {
                    'total_requests': total,
                    'queued_requests': stats['queued'],
                    'processing_requests': stats['processing'],
                    'completed_requests': completed,
                    'purged_requests': purged,
                    'success_rate': success_rate,
                    'progress_percentage': progress_percentage,
                    'unique_regions': stats['unique_regions'],
                    'unique_variables': stats['unique_variables'],
                    'unique_datasets': stats['unique_datasets']
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
                'data_source': 'rda_requests (real-time sync)'
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
            """API endpoint for completed regions data using filesystem scanning."""
            try:
                # Scan downloaded_files directory for completed regions
                import os
                import glob
                from collections import defaultdict
                
                completed_regions = []
                total_downloaded_files = 0
                
                # Check if downloaded_files directory exists
                downloaded_files_dir = 'downloaded_files'
                if not os.path.exists(downloaded_files_dir):
                    self.logger.warning(f"Downloaded files directory not found: {downloaded_files_dir}")
                    return jsonify({
                        'completed_regions': [],
                        'statistics': {
                            'total_completed_files': 0,
                            'total_downloaded_files': 0,
                            'unique_regions': 0,
                            'unique_variables': 0,
                            'regions_with_downloads': 0,
                            'download_completion_rate': 0,
                            'avg_processing_hours': 0.0
                        },
                        'timestamp': datetime.now().isoformat()
                    })
                
                # Scan each region directory
                for item in os.listdir(downloaded_files_dir):
                    region_path = os.path.join(downloaded_files_dir, item)
                    if os.path.isdir(region_path):
                        # Count files and analyze variables
                        variable_breakdown = defaultdict(int)
                        total_files = 0
                        
                        # Scan for files in region directory and subdirectories
                        for root, dirs, files in os.walk(region_path):
                            for file in files:
                                if file.endswith(('.nc', '.grb', '.grib', '.dat', '.bin', '.tar', '.gz', '.bz2', '.zip', '.grib2')):  # Common weather data formats including compressed
                                    total_files += 1
                                    
                                    # Try to extract variable type from filename or directory
                                    file_lower = file.lower()
                                    dir_name = os.path.basename(root).lower()
                                    
                                    if 'dswrf' in file_lower or 'dswrf' in dir_name or 'solar' in dir_name:
                                        variable_breakdown['dswrf'] += 1
                                    elif 'wind' in file_lower or 'wind' in dir_name or 'ugrd' in file_lower or 'vgrd' in file_lower:
                                        variable_breakdown['wind'] += 1
                                    elif 'rain' in file_lower or 'rain' in dir_name or 'apcp' in file_lower or 'precip' in dir_name:
                                        variable_breakdown['rain'] += 1
                                    elif 'temp' in file_lower or 'temp' in dir_name or 'tmp' in file_lower:
                                        variable_breakdown['temp'] += 1
                                    else:
                                        variable_breakdown['unknown'] += 1
                        
                        if total_files > 0:
                            # Get region name (try to make it more readable)
                            region_name = item.replace('_', ' ').title()
                            
                            # Get directory timestamps for first_discovered and last_updated
                            try:
                                stat_info = os.stat(region_path)
                                first_discovered = datetime.fromtimestamp(stat_info.st_ctime).isoformat()
                                last_updated = datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                            except:
                                first_discovered = None
                                last_updated = datetime.now().isoformat()
                            
                            region_data = {
                                'region': item,
                                'region_name': region_name,
                                'total_files': total_files,
                                'completed_files': total_files,  # All files in downloaded_files are completed
                                'downloaded_files': total_files,
                                'success_rate': 100.0,  # All downloaded files are successful
                                'completion_percentage': 100.0,
                                'variable_breakdown': dict(variable_breakdown),
                                'first_discovered': first_discovered,
                                'last_updated': last_updated,
                                'has_actual_downloads': True,
                                'download_directory': region_path
                            }
                            
                            completed_regions.append(region_data)
                            total_downloaded_files += total_files
                
                # Sort regions by number of downloaded files (descending)
                completed_regions.sort(key=lambda x: x['downloaded_files'], reverse=True)
                
                # Calculate overall statistics
                unique_regions = len(completed_regions)
                regions_with_downloads = len(completed_regions)  # All regions have downloads by definition
                
                # Count unique variables from all regions
                unique_variables = set()
                for region in completed_regions:
                    if region['variable_breakdown']:
                        unique_variables.update(region['variable_breakdown'].keys())
                
                # Calculate average processing hours (estimate based on file count)
                avg_processing_hours = 0.0
                if total_downloaded_files > 0:
                    # Rough estimate: assume 0.1 hours per file on average
                    avg_processing_hours = total_downloaded_files * 0.1
                
                return jsonify({
                    'completed_regions': completed_regions,
                    'statistics': {
                        'total_completed_files': total_downloaded_files,
                        'total_downloaded_files': total_downloaded_files,
                        'unique_regions': unique_regions,
                        'unique_variables': len(unique_variables),
                        'regions_with_downloads': regions_with_downloads,
                        'download_completion_rate': 100.0,  # All scanned regions have downloads
                        'avg_processing_hours': avg_processing_hours
                    },
                    'timestamp': datetime.now().isoformat(),
                    'data_source': 'filesystem_scan'
                })
                
            except Exception as e:
                self.logger.error(f"Error getting completed regions from filesystem: {e}")
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
        
        # Enhanced Error Tracking API Endpoints
        @self.app.route('/api/error-tracking/summary')
        def api_error_summary():
            """API endpoint for comprehensive error summary."""
            try:
                time_window = request.args.get('time_window_hours', 24, type=int)
                summary = self.error_dashboard_api.get_error_summary(time_window)
                return jsonify(summary)
            except Exception as e:
                self.logger.error(f"Error getting error summary: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/error-tracking/live-feed')
        def api_live_error_feed():
            """API endpoint for live error feed with filtering."""
            try:
                limit = request.args.get('limit', 50, type=int)
                region_filter = request.args.get('region')
                error_type_filter = request.args.get('error_type')
                severity_filter = request.args.get('severity')
                
                feed = self.error_dashboard_api.get_live_error_feed(
                    limit=limit,
                    region_filter=region_filter,
                    error_type_filter=error_type_filter,
                    severity_filter=severity_filter
                )
                return jsonify(feed)
            except Exception as e:
                self.logger.error(f"Error getting live error feed: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/error-tracking/regional-health')
        def api_regional_error_health():
            """API endpoint for regional error health metrics."""
            try:
                health = self.error_dashboard_api.get_regional_error_health()
                return jsonify(health)
            except Exception as e:
                self.logger.error(f"Error getting regional error health: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/error-tracking/trends')
        def api_error_trends():
            """API endpoint for error trend analysis."""
            try:
                hours_back = request.args.get('hours_back', 24, type=int)
                interval_hours = request.args.get('interval_hours', 1, type=int)
                
                trends = self.error_dashboard_api.get_error_trends(
                    hours_back=hours_back,
                    interval_hours=interval_hours
                )
                return jsonify(trends)
            except Exception as e:
                self.logger.error(f"Error getting error trends: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/error-tracking/retry-queue-status')
        def api_retry_queue_status():
            """API endpoint for retry queue status and metrics."""
            try:
                status = self.error_dashboard_api.get_retry_queue_status()
                return jsonify(status)
            except Exception as e:
                self.logger.error(f"Error getting retry queue status: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/error-tracking/patterns')
        def api_error_patterns():
            """API endpoint for error pattern analysis."""
            try:
                min_frequency = request.args.get('min_frequency', 3, type=int)
                patterns = self.error_dashboard_api.get_error_patterns(min_frequency)
                return jsonify(patterns)
            except Exception as e:
                self.logger.error(f"Error getting error patterns: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/error-tracking/resolve/<int:error_id>', methods=['POST'])
        def api_resolve_error(error_id):
            """API endpoint to resolve an error."""
            try:
                data = request.get_json()
                if not data or 'resolution_notes' not in data:
                    return jsonify({'error': 'Missing resolution_notes'}), 400
                
                result = self.error_dashboard_api.resolve_error(
                    error_id=error_id,
                    resolution_notes=data['resolution_notes'],
                    resolved_by=data.get('resolved_by', 'dashboard_user')
                )
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error resolving error {error_id}: {e}")
                return jsonify({'error': str(e)}), 500
        
        # Enhanced Progress Tracking API Endpoints
        @self.app.route('/api/progress-tracking/overall')
        def api_overall_progress():
            """API endpoint for overall system progress."""
            try:
                progress = self.progress_tracker_api.get_overall_progress()
                return jsonify(progress)
            except Exception as e:
                self.logger.error(f"Error getting overall progress: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/progress-tracking/regional')
        def api_regional_progress():
            """API endpoint for regional progress breakdown."""
            try:
                progress = self.progress_tracker_api.get_regional_progress()
                return jsonify(progress)
            except Exception as e:
                self.logger.error(f"Error getting regional progress: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/progress-tracking/variables')
        def api_variable_progress():
            """API endpoint for weather variable progress breakdown."""
            try:
                progress = self.progress_tracker_api.get_variable_progress()
                return jsonify(progress)
            except Exception as e:
                self.logger.error(f"Error getting variable progress: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/progress-tracking/trends')
        def api_progress_trends():
            """API endpoint for progress trends over time."""
            try:
                hours_back = request.args.get('hours_back', 24, type=int)
                interval_hours = request.args.get('interval_hours', 1, type=int)
                
                trends = self.progress_tracker_api.get_progress_trends(
                    hours_back=hours_back,
                    interval_hours=interval_hours
                )
                return jsonify(trends)
            except Exception as e:
                self.logger.error(f"Error getting progress trends: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/progress-tracking/create-snapshot', methods=['POST'])
        def api_create_progress_snapshot():
            """API endpoint to create a progress snapshot."""
            try:
                data = request.get_json() if request.is_json else {}
                snapshot_type = data.get('snapshot_type', 'overall')
                
                result = self.progress_tracker_api.create_progress_snapshot(snapshot_type)
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error creating progress snapshot: {e}")
                return jsonify({'error': str(e)}), 500
        
        # Enhanced System Health API Endpoints
        @self.app.route('/api/system-health/comprehensive')
        def api_comprehensive_system_health():
            """API endpoint for comprehensive system health metrics."""
            try:
                # Combine data from multiple sources
                error_summary = self.error_dashboard_api.get_error_summary()
                retry_status = self.error_dashboard_api.get_retry_queue_status()
                overall_progress = self.progress_tracker_api.get_overall_progress()
                regional_health = self.error_dashboard_api.get_regional_error_health()
                
                # Get sync status
                sync_status = self.real_time_sync.get_live_sync_status()
                freshness_info = self._get_data_freshness_info()
                
                comprehensive_health = {
                    'system_overview': {
                        'overall_health_score': self._calculate_system_health_score(
                            error_summary, retry_status, overall_progress
                        ),
                        'data_freshness': freshness_info,
                        'sync_status': {
                            'status': sync_status.status.value,
                            'last_sync': sync_status.last_sync.isoformat() if sync_status.last_sync else None,
                            'sync_count': sync_status.sync_count,
                            'error_count': sync_status.error_count
                        }
                    },
                    'error_health': error_summary,
                    'retry_health': retry_status,
                    'progress_health': overall_progress,
                    'regional_health': regional_health,
                    'alerts': self._generate_system_alerts(
                        error_summary, retry_status, overall_progress, regional_health
                    ),
                    'generated_at': datetime.now().isoformat()
                }
                
                return jsonify(comprehensive_health)
            except Exception as e:
                self.logger.error(f"Error getting comprehensive system health: {e}")
                return jsonify({'error': str(e)}), 500
        
        # Dashboard Enhancement API Endpoints
        @self.app.route('/api/dashboard/layout')
        def api_dashboard_layout():
            """API endpoint for dashboard layout configuration."""
            try:
                layout = self.dashboard_enhancements.get_dashboard_layout()
                return jsonify(layout)
            except Exception as e:
                self.logger.error(f"Error getting dashboard layout: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/dashboard/widgets')
        def api_all_widget_data():
            """API endpoint for all widget data."""
            try:
                widget_data = self.dashboard_enhancements.get_all_widget_data()
                return jsonify(widget_data)
            except Exception as e:
                self.logger.error(f"Error getting all widget data: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/dashboard/widgets/<widget_id>')
        def api_widget_data(widget_id):
            """API endpoint for specific widget data."""
            try:
                widget_data = self.dashboard_enhancements.get_widget_data(widget_id)
                return jsonify(widget_data)
            except Exception as e:
                self.logger.error(f"Error getting widget data for {widget_id}: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/dashboard/alerts')
        def api_dashboard_alerts():
            """API endpoint for dashboard alerts."""
            try:
                alerts = self.dashboard_enhancements.check_alerts()
                return jsonify({
                    'alerts': alerts,
                    'total_alerts': len(alerts),
                    'critical_alerts': len([a for a in alerts if a.get('severity') == 'critical']),
                    'warning_alerts': len([a for a in alerts if a.get('severity') == 'warning']),
                    'generated_at': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error getting dashboard alerts: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/dashboard/metrics')
        def api_dashboard_metrics():
            """API endpoint for dashboard performance metrics."""
            try:
                metrics = self.dashboard_enhancements.get_dashboard_metrics()
                return jsonify(metrics)
            except Exception as e:
                self.logger.error(f"Error getting dashboard metrics: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/dashboard/widgets/<widget_id>/config', methods=['PUT'])
        def api_update_widget_config(widget_id):
            """API endpoint to update widget configuration."""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No configuration data provided'}), 400
                
                result = self.dashboard_enhancements.update_widget_config(widget_id, data)
                return jsonify(result)
            except Exception as e:
                self.logger.error(f"Error updating widget config for {widget_id}: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/dashboard/export-config')
        def api_export_dashboard_config():
            """API endpoint to export dashboard configuration."""
            try:
                config = self.dashboard_enhancements.export_dashboard_config()
                return jsonify(config)
            except Exception as e:
                self.logger.error(f"Error exporting dashboard config: {e}")
                return jsonify({'error': str(e)}), 500
        
        # Real-time Dashboard Updates Endpoint
        @self.app.route('/api/dashboard/real-time-update')
        def api_real_time_dashboard_update():
            """API endpoint for real-time dashboard updates with all monitoring data."""
            try:
                # Trigger immediate sync for fresh data
                sync_result = self.real_time_sync.perform_immediate_sync("dashboard_real_time_update")
                
                # Get comprehensive monitoring data
                error_summary = self.error_dashboard_api.get_error_summary()
                progress_overview = self.progress_tracker_api.get_overall_progress()
                regional_health = self.error_dashboard_api.get_regional_error_health()
                retry_status = self.error_dashboard_api.get_retry_queue_status()
                active_alerts = self.dashboard_enhancements.check_alerts()
                
                # Get sync status and freshness
                sync_status = self.real_time_sync.get_live_sync_status()
                freshness_info = self._get_data_freshness_info()
                
                # Calculate system health score
                system_health_score = self._calculate_system_health_score(
                    error_summary, retry_status, progress_overview
                )
                
                real_time_update = {
                    'sync_info': {
                        'sync_result': {
                            'success': sync_result.success,
                            'timestamp': sync_result.timestamp,
                            'duration_seconds': sync_result.duration_seconds,
                            'total_requests': sync_result.total_requests,
                            'sync_trigger': sync_result.sync_trigger
                        },
                        'sync_status': {
                            'status': sync_status.status.value,
                            'last_sync': sync_status.last_sync.isoformat() if sync_status.last_sync else None,
                            'sync_count': sync_status.sync_count,
                            'error_count': sync_status.error_count
                        },
                        'data_freshness': freshness_info
                    },
                    'monitoring_data': {
                        'error_summary': error_summary,
                        'progress_overview': progress_overview,
                        'regional_health': regional_health,
                        'retry_status': retry_status,
                        'system_health_score': system_health_score
                    },
                    'alerts': {
                        'active_alerts': active_alerts,
                        'alert_counts': {
                            'total': len(active_alerts),
                            'critical': len([a for a in active_alerts if a.get('severity') == 'critical']),
                            'warning': len([a for a in active_alerts if a.get('severity') == 'warning']),
                            'info': len([a for a in active_alerts if a.get('severity') == 'info'])
                        }
                    },
                    'dashboard_status': {
                        'widgets_active': len([w for w in self.dashboard_enhancements.widget_configs.values() if w.enabled]),
                        'alerts_enabled': len([a for a in self.dashboard_enhancements.alert_configs.values() if a.enabled]),
                        'last_update': datetime.now().isoformat()
                    },
                    'generated_at': datetime.now().isoformat()
                }
                
                return jsonify(real_time_update)
                
            except Exception as e:
                self.logger.error(f"Error in real-time dashboard update: {e}")
                return jsonify({
                    'error': str(e),
                    'sync_status': {'status': 'error'},
                    'generated_at': datetime.now().isoformat()
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
            <div class="metric-value" id="successRate">-</div>
            <div class="metric-label">Success Rate</div>
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
            document.getElementById('successRate').textContent = (overview.success_rate || 0).toFixed(1) + '%';
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
        Start the enhanced dashboard server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            debug: Enable debug mode
        """
        self.create_dashboard_template()
        
        self.logger.info(f"Starting Enhanced RDA Dashboard on http://{host}:{port}")
        
        try:
            self.app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)
        except OSError as e:
            if "Address already in use" in str(e):
                self.logger.warning(f"Port {port} is in use, trying port {port + 1}")
                self.app.run(host=host, port=port + 1, debug=debug, use_reloader=False, threaded=True)
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
            