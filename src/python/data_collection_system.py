#!/usr/bin/env python3
"""
RDA Data Collection and Import System

This system fetches data from rdams_client.py -get_status command and populates
the freshly reset databases with this data. It handles the complete data structure
including request_index, request_id, dsid, status, dates, location, ncar_contact,
rinfo parameters, and subset_info descriptions.

Key Features:
- Fetches fresh data from rdams_client.get_status()
- Parses JSON response format from get_status
- Maps get_status data to the new database schema
- Handles rinfo parameter string parsing for region/variable extraction
- Connects to both production and test databases
- Provides comprehensive logging and error handling
- Can be run as standalone script or integrated into automation

Usage:
    python data_collection_system.py --collect-all
    python data_collection_system.py --collect-specific <request_id>
    python data_collection_system.py --import-to-production
    python data_collection_system.py --import-to-test
    python data_collection_system.py --import-to-both
"""

import os
import sys
import json
import sqlite3
import logging
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logger_utils import get_logger

import rdams_client
from database_reset import DatabaseResetManager, create_database_reset_manager


@dataclass
class RDARequestData:
    """Data class representing a single RDA request from get_status."""
    request_index: str
    request_id: str
    dsid: Optional[str] = None
    status: str = "unknown"
    date_rqst: Optional[str] = None
    date_ready: Optional[str] = None
    date_purge: Optional[str] = None
    location: Optional[str] = None
    ncar_contact: Optional[str] = None
    rinfo: Optional[str] = None
    subset_note: Optional[str] = None
    raw_response: Optional[str] = None
    
    # Parsed from rinfo
    region: Optional[str] = None
    variable_type: Optional[str] = None
    coordinates: Optional[Dict[str, float]] = None


@dataclass
class CollectionStats:
    """Statistics for data collection operation."""
    total_requests_found: int = 0
    successfully_parsed: int = 0
    parsing_errors: int = 0
    database_inserts: int = 0
    database_updates: int = 0
    database_errors: int = 0
    collection_timestamp: str = ""


class RDADataCollector:
    """
    Collects data from rdams_client.get_status and manages database population.
    
    This class handles fetching data from the RDA system, parsing the JSON responses,
    extracting region/variable information from rinfo parameters, and populating
    the database tables with the collected data.
    """
    
    def __init__(self, data_dir: str = "./data"):
        """
        Initialize the RDA data collector.
        
        Args:
            data_dir: Directory containing database files
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Database paths
        self.production_db = self.data_dir / "automation_state.db"
        self.test_db = self.data_dir / "test_automation_state.db"
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Initialize database reset manager for schema verification
        self.db_manager = create_database_reset_manager(str(self.data_dir))
        
        self.logger.info("RDADataCollector initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_data_collector', level=logging.DEBUG)
    
    def fetch_all_rda_requests(self) -> Dict[str, Any]:
        """
        Fetch all requests from RDA system using rdams_client.get_status().
        
        Returns:
            Raw JSON response from get_status command
        """
        try:
            self.logger.info("Fetching all RDA requests using rdams_client.get_status()")
            
            # Call rdams_client.get_status() to get all requests
            status_result = rdams_client.get_status()
            
            if not status_result:
                self.logger.error("No data returned from rdams_client.get_status()")
                return {}
            
            if 'data' not in status_result:
                self.logger.error("No 'data' field in get_status response")
                self.logger.debug(f"Response structure: {list(status_result.keys())}")
                return {}
            
            requests_data = status_result['data']
            if isinstance(requests_data, list):
                self.logger.info(f"Successfully fetched {len(requests_data)} requests from RDA")
            else:
                # Handle case where data is a single request object
                requests_data = [requests_data]
                self.logger.info("Fetched single request from RDA")
            
            return {
                'data': requests_data,
                'metadata': {
                    'fetch_timestamp': datetime.now().isoformat(),
                    'total_requests': len(requests_data),
                    'source': 'rdams_client.get_status()'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching RDA requests: {e}")
            raise
    
    def fetch_specific_rda_request(self, request_id: str) -> Dict[str, Any]:
        """
        Fetch a specific request from RDA system using rdams_client.get_status(request_id).
        
        Args:
            request_id: Specific request ID to fetch
            
        Returns:
            Raw JSON response from get_status command for specific request
        """
        try:
            self.logger.info(f"Fetching specific RDA request: {request_id}")
            
            # Call rdams_client.get_status(request_id) for specific request
            status_result = rdams_client.get_status(request_id)
            
            if not status_result:
                self.logger.error(f"No data returned for request {request_id}")
                return {}
            
            if 'data' not in status_result:
                self.logger.error(f"No 'data' field in get_status response for {request_id}")
                return {}
            
            request_data = status_result['data']
            self.logger.info(f"Successfully fetched request {request_id} from RDA")
            
            return {
                'data': [request_data] if not isinstance(request_data, list) else request_data,
                'metadata': {
                    'fetch_timestamp': datetime.now().isoformat(),
                    'total_requests': 1,
                    'source': f'rdams_client.get_status({request_id})',
                    'request_id': request_id
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching request {request_id}: {e}")
            raise
    
    def parse_rinfo_parameters(self, rinfo: str) -> Tuple[Optional[str], Optional[str], Dict[str, float]]:
        """
        Parse rinfo parameter string to extract region, variable, and coordinates.
        
        Expected format: "nlat=42;slat=32;wlon=-124.75;elon=-113.5"
        
        Args:
            rinfo: Semicolon-delimited parameter string
            
        Returns:
            Tuple of (region, variable_type, coordinates_dict)
        """
        coordinates = {}
        region = None
        variable_type = None
        
        if not rinfo:
            return region, variable_type, coordinates
        
        try:
            # Parse semicolon-delimited parameters
            params = {}
            for param in rinfo.split(';'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key.strip()] = value.strip()
            
            # Extract coordinate parameters
            coord_keys = ['nlat', 'slat', 'wlon', 'elon']
            for key in coord_keys:
                if key in params:
                    try:
                        coordinates[key] = float(params[key])
                    except ValueError:
                        self.logger.warning(f"Could not parse coordinate {key}={params[key]}")
            
            # Determine region from coordinates (simplified logic)
            if coordinates:
                region = self._determine_region_from_coordinates(coordinates)
            
            # Extract variable type from other parameters
            # Look for common parameter patterns that indicate variable type
            for key, value in params.items():
                if key.lower() in ['param', 'parameter', 'var', 'variable']:
                    variable_type = self._normalize_variable_type(value)
                    break
            
            self.logger.debug(f"Parsed rinfo '{rinfo}' -> region: {region}, variable: {variable_type}, coords: {coordinates}")
            
        except Exception as e:
            self.logger.warning(f"Error parsing rinfo '{rinfo}': {e}")
        
        return region, variable_type, coordinates
    
    def _determine_region_from_coordinates(self, coordinates: Dict[str, float]) -> Optional[str]:
        """
        Determine region from coordinate bounds (simplified implementation).
        
        Args:
            coordinates: Dictionary with nlat, slat, wlon, elon values
            
        Returns:
            Region name or None
        """
        try:
            # This is a simplified region detection based on coordinate bounds
            # In a real implementation, you'd have a more sophisticated mapping
            
            nlat = coordinates.get('nlat', 0)
            slat = coordinates.get('slat', 0)
            wlon = coordinates.get('wlon', 0)
            elon = coordinates.get('elon', 0)
            
            # Simple US region detection based on coordinate ranges
            if -130 <= wlon <= -110 and 30 <= slat <= 50:
                if -125 <= wlon <= -115:
                    return "CISO"  # California region
                elif -115 <= wlon <= -105:
                    return "AZPS"  # Arizona/Southwest
            elif -110 <= wlon <= -90 and 25 <= slat <= 45:
                return "ERCOT"  # Texas region
            elif -90 <= wlon <= -70 and 35 <= slat <= 50:
                return "PJM"    # Eastern region
            
            # Default to UNKNOWN if can't determine
            return "UNKNOWN"
            
        except Exception as e:
            self.logger.warning(f"Error determining region from coordinates: {e}")
            return "UNKNOWN"
    
    def _normalize_variable_type(self, variable_str: str) -> str:
        """
        Normalize variable type string to standard format.
        
        Args:
            variable_str: Raw variable string
            
        Returns:
            Normalized variable type
        """
        if not variable_str:
            return "unknown"
        
        variable_lower = variable_str.lower().strip()
        
        # Map common variable patterns
        if any(term in variable_lower for term in ['solar', 'radiation', 'dswrf', 'shortwave']):
            return "dswrf"
        elif any(term in variable_lower for term in ['wind', 'ugrd', 'vgrd']):
            return "ugrd_vgrd"
        elif any(term in variable_lower for term in ['rain', 'precip', 'apcp']):
            return "apcp"
        elif any(term in variable_lower for term in ['temp', 'temperature', 'tmp']):
            return "tmp_dpt"
        else:
            return "unknown"
    
    def parse_subset_note(self, subset_info: Dict[str, Any]) -> Optional[str]:
        """
        Parse subset_info to extract the note/description.
        
        Args:
            subset_info: Dictionary containing subset information
            
        Returns:
            Extracted note/description or None
        """
        if not subset_info or not isinstance(subset_info, dict):
            return None
        
        # Extract note field
        note = subset_info.get('note', '')
        if note:
            # Clean up the note - remove extra whitespace and newlines
            note = ' '.join(note.split())
            return note
        
        return None
    
    def parse_rda_request(self, raw_request: Dict[str, Any]) -> RDARequestData:
        """
        Parse a single RDA request from get_status response into structured data.
        
        Args:
            raw_request: Raw request data from get_status
            
        Returns:
            Parsed RDARequestData object
        """
        try:
            # Extract basic fields
            request_index = str(raw_request.get('request_index', ''))
            request_id = str(raw_request.get('request_id', ''))
            
            # Clean request_id - remove SAVADI prefix if present
            if request_id.startswith('SAVADI'):
                request_id = request_id[6:]  # Remove 'SAVADI' prefix
            
            dsid = raw_request.get('dsid')
            status = raw_request.get('status', 'unknown')
            
            # Extract date fields
            date_rqst = raw_request.get('date_rqst')
            date_ready = raw_request.get('date_ready')
            date_purge = raw_request.get('date_purge')
            
            # Extract location and contact
            location = raw_request.get('location')
            ncar_contact = raw_request.get('ncar_contact')
            
            # Extract rinfo and parse it
            rinfo = raw_request.get('rinfo', '')
            region, variable_type, coordinates = self.parse_rinfo_parameters(rinfo)
            
            # Extract subset note
            subset_info = raw_request.get('subset_info', {})
            subset_note = self.parse_subset_note(subset_info)
            
            # Store raw response for debugging
            raw_response = json.dumps(raw_request, default=str)
            
            parsed_request = RDARequestData(
                request_index=request_index,
                request_id=request_id,
                dsid=dsid,
                status=status,
                date_rqst=date_rqst,
                date_ready=date_ready,
                date_purge=date_purge,
                location=location,
                ncar_contact=ncar_contact,
                rinfo=rinfo,
                subset_note=subset_note,
                raw_response=raw_response,
                region=region,
                variable_type=variable_type,
                coordinates=coordinates
            )
            
            self.logger.debug(f"Successfully parsed request {request_id}")
            return parsed_request
            
        except Exception as e:
            self.logger.error(f"Error parsing request data: {e}")
            self.logger.debug(f"Raw request data: {raw_request}")
            raise
    
    def collect_and_parse_all_requests(self) -> Tuple[List[RDARequestData], CollectionStats]:
        """
        Collect all RDA requests and parse them into structured data.
        
        Returns:
            Tuple of (parsed_requests_list, collection_statistics)
        """
        stats = CollectionStats(collection_timestamp=datetime.now().isoformat())
        parsed_requests = []
        
        try:
            # Fetch all requests
            raw_data = self.fetch_all_rda_requests()
            
            if not raw_data or 'data' not in raw_data:
                self.logger.warning("No data fetched from RDA")
                return parsed_requests, stats
            
            requests_data = raw_data['data']
            stats.total_requests_found = len(requests_data)
            
            self.logger.info(f"Processing {stats.total_requests_found} requests")
            
            # Parse each request
            for i, raw_request in enumerate(requests_data):
                try:
                    parsed_request = self.parse_rda_request(raw_request)
                    parsed_requests.append(parsed_request)
                    stats.successfully_parsed += 1
                    
                    if (i + 1) % 10 == 0:
                        self.logger.info(f"Processed {i + 1}/{stats.total_requests_found} requests")
                        
                except Exception as e:
                    stats.parsing_errors += 1
                    self.logger.error(f"Error parsing request {i + 1}: {e}")
                    continue
            
            self.logger.info(f"Collection completed: {stats.successfully_parsed} parsed, {stats.parsing_errors} errors")
            return parsed_requests, stats
            
        except Exception as e:
            self.logger.error(f"Error in collect_and_parse_all_requests: {e}")
            raise
    
    def collect_and_parse_specific_request(self, request_id: str) -> Tuple[List[RDARequestData], CollectionStats]:
        """
        Collect and parse a specific RDA request.
        
        Args:
            request_id: Specific request ID to collect
            
        Returns:
            Tuple of (parsed_requests_list, collection_statistics)
        """
        stats = CollectionStats(collection_timestamp=datetime.now().isoformat())
        parsed_requests = []
        
        try:
            # Fetch specific request
            raw_data = self.fetch_specific_rda_request(request_id)
            
            if not raw_data or 'data' not in raw_data:
                self.logger.warning(f"No data fetched for request {request_id}")
                return parsed_requests, stats
            
            requests_data = raw_data['data']
            stats.total_requests_found = len(requests_data)
            
            # Parse each request (should be just one)
            for raw_request in requests_data:
                try:
                    parsed_request = self.parse_rda_request(raw_request)
                    parsed_requests.append(parsed_request)
                    stats.successfully_parsed += 1
                    
                except Exception as e:
                    stats.parsing_errors += 1
                    self.logger.error(f"Error parsing request {request_id}: {e}")
                    continue
            
            self.logger.info(f"Specific collection completed for {request_id}")
            return parsed_requests, stats
            
        except Exception as e:
            self.logger.error(f"Error collecting specific request {request_id}: {e}")
            raise
    
    def verify_database_schema(self, db_path: Path) -> bool:
        """
        Verify that the database has the correct schema for data import.
        
        Args:
            db_path: Path to database file
            
        Returns:
            True if schema is compatible, False otherwise
        """
        try:
            verification_result = self.db_manager.verify_schema_compatibility(db_path)
            
            if verification_result.get('schema_compatible', False):
                self.logger.info(f"✅ Database schema verified: {db_path}")
                return True
            else:
                self.logger.error(f"❌ Database schema incompatible: {db_path}")
                for issue in verification_result.get('issues', []):
                    self.logger.error(f"  - {issue}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error verifying database schema: {e}")
            return False
    
    def import_requests_to_database(self, requests: List[RDARequestData], 
                                  db_path: Path, stats: CollectionStats) -> CollectionStats:
        """
        Import parsed requests to the specified database.
        
        Args:
            requests: List of parsed RDA requests
            db_path: Path to target database
            stats: Collection statistics to update
            
        Returns:
            Updated collection statistics
        """
        if not requests:
            self.logger.warning("No requests to import")
            return stats
        
        # Verify database schema first
        if not self.verify_database_schema(db_path):
            raise ValueError(f"Database schema incompatible: {db_path}")
        
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                self.logger.info(f"Importing {len(requests)} requests to {db_path}")
                
                for request in requests:
                    try:
                        # Check if request already exists
                        cursor.execute("""
                            SELECT id FROM rda_requests 
                            WHERE request_index = ? OR request_id = ?
                        """, (request.request_index, request.request_id))
                        
                        existing = cursor.fetchone()
                        
                        if existing:
                            # Update existing request
                            cursor.execute("""
                                UPDATE rda_requests SET
                                    dsid = ?, status = ?, date_rqst = ?, date_ready = ?, 
                                    date_purge = ?, location = ?, ncar_contact = ?, 
                                    rinfo = ?, subset_note = ?, raw_response = ?,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE request_index = ? OR request_id = ?
                            """, (
                                request.dsid, request.status, request.date_rqst, 
                                request.date_ready, request.date_purge, request.location,
                                request.ncar_contact, request.rinfo, request.subset_note,
                                request.raw_response, request.request_index, request.request_id
                            ))
                            stats.database_updates += 1
                            self.logger.debug(f"Updated existing request {request.request_id}")
                        else:
                            # Insert new request
                            cursor.execute("""
                                INSERT INTO rda_requests (
                                    request_index, request_id, dsid, status, date_rqst,
                                    date_ready, date_purge, location, ncar_contact,
                                    rinfo, subset_note, raw_response
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                request.request_index, request.request_id, request.dsid,
                                request.status, request.date_rqst, request.date_ready,
                                request.date_purge, request.location, request.ncar_contact,
                                request.rinfo, request.subset_note, request.raw_response
                            ))
                            stats.database_inserts += 1
                            self.logger.debug(f"Inserted new request {request.request_id}")
                        
                        # Also update control_files_tracking if we have region/variable info
                        if request.region and request.variable_type:
                            self._update_control_files_tracking(cursor, request)
                        
                    except Exception as e:
                        stats.database_errors += 1
                        self.logger.error(f"Error importing request {request.request_id}: {e}")
                        continue
                
                conn.commit()
                self.logger.info(f"✅ Import completed: {stats.database_inserts} inserts, {stats.database_updates} updates, {stats.database_errors} errors")
                
        except Exception as e:
            self.logger.error(f"Database import error: {e}")
            raise
        
        return stats
    
    def _update_control_files_tracking(self, cursor: sqlite3.Cursor, request: RDARequestData):
        """
        Update control_files_tracking table with request information.
        
        Args:
            cursor: Database cursor
            request: Parsed request data
        """
        try:
            # Check if there's a matching control file entry
            cursor.execute("""
                SELECT id FROM control_files_tracking 
                WHERE request_index = ? OR request_id = ?
            """, (request.request_index, request.request_id))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing entry
                cursor.execute("""
                    UPDATE control_files_tracking SET
                        status = ?, request_index = ?, request_id = ?,
                        region = ?, variable_type = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    request.status, request.request_index, request.request_id,
                    request.region, request.variable_type, existing[0]
                ))
            else:
                # Create new entry if we have enough information
                if request.region and request.variable_type:
                    # Generate a synthetic control file path
                    control_file_path = f"synthetic/{request.region}_{request.variable_type}_control.ctl"
                    
                    cursor.execute("""
                        INSERT INTO control_files_tracking (
                            file_path, filename, region, variable_type, discovered_at,
                            status, request_index, request_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        control_file_path, f"{request.region}_{request.variable_type}_control.ctl",
                        request.region, request.variable_type, datetime.now().isoformat(),
                        request.status, request.request_index, request.request_id
                    ))
            
        except Exception as e:
            self.logger.warning(f"Error updating control_files_tracking for {request.request_id}: {e}")
    
    def update_regional_progress(self, db_path: Path):
        """
        Update regional_progress table based on imported data.
        
        Args:
            db_path: Path to database file
        """
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Get regional statistics from control_files_tracking
                cursor.execute("""
                    SELECT 
                        region,
                        COUNT(*) as total_files,
                        SUM(CASE WHEN status = 'discovered' THEN 1 ELSE 0 END) as discovered,
                        SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) as queued,
                        SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) as submitted,
                        SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                        SUM(CASE WHEN status = 'downloaded' THEN 1 ELSE 0 END) as downloaded
                    FROM control_files_tracking
                    GROUP BY region
                """)
                
                regional_stats = cursor.fetchall()
                
                for stats in regional_stats:
                    region = stats[0]
                    total = stats[1]
                    discovered = stats[2]
                    queued = stats[3]
                    submitted = stats[4]
                    processing = stats[5]
                    completed = stats[6]
                    failed = stats[7]
                    downloaded = stats[8]
                    
                    completion_percentage = (downloaded / total * 100) if total > 0 else 0
                    success_rate = (downloaded / (downloaded + failed) * 100) if (downloaded + failed) > 0 else 0
                    
                    # Update or insert regional progress
                    cursor.execute("""
                        INSERT OR REPLACE INTO regional_progress (
                            region, total_control_files, discovered_files, queued_files,
                            submitted_files, processing_files, completed_files, failed_files,
                            downloaded_files, completion_percentage, success_rate,
                            last_updated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        region, total, discovered, queued, submitted, processing,
                        completed, failed, downloaded, completion_percentage,
                        success_rate, datetime.now().isoformat()
                    ))
                
                conn.commit()
                self.logger.info(f"Updated regional progress for {len(regional_stats)} regions")
                
        except Exception as e:
            self.logger.error(f"Error updating regional progress: {e}")
    
    def run_complete_data_import(self, target_databases: List[str] = None, 
                               specific_request_id: str = None) -> Dict[str, Any]:
        """
        Run complete data collection and import process.
        
        Args:
            target_databases: List of database targets ('production', 'test', or both)
            specific_request_id: Optional specific request ID to collect
            
        Returns:
            Dictionary containing import results and statistics
        """
        if target_databases is None:
            target_databases = ['production', 'test']
        
        import_results = {
            'operation': 'complete_data_import',
            'timestamp': datetime.now().isoformat(),
            'target_databases': target_databases,
            'specific_request_id': specific_request_id,
            'collection_stats': None,
            'database_results': {},
            'overall_success': False
        }
        
        try:
            self.logger.info("🔄 Starting complete data import process")
            
            # Step 1: Collect and parse requests
            if specific_request_id:
                self.logger.info(f"Collecting specific request: {specific_request_id}")
                parsed_requests, collection_stats = self.collect_and_parse_specific_request(specific_request_id)
            else:
                self.logger.info("Collecting all RDA requests")
                parsed_requests, collection_stats = self.collect_and_parse_all_requests()
            
            import_results['collection_stats'] = asdict(collection_stats)
            
            if not parsed_requests:
                self.logger.warning("No requests collected, aborting import")
                return import_results
            
            # Step 2: Import to target databases
            database_paths = {}
            if 'production' in target_databases:
                database_paths['production'] = self.production_db
            if 'test' in target_databases:
                database_paths['test'] = self.test_db
            
            all_imports_successful = True
            
            for db_name, db_path in database_paths.items():
                try:
                    self.logger.info(f"Importing to {db_name} database: {db_path}")
                    
                    # Import requests to database
                    updated_stats = self.import_requests_to_database(parsed_requests, db_path, collection_stats)
                    
                    # Update regional progress
                    self.update_regional_progress(db_path)
                    
                    import_results['database_results'][db_name] = {
                        'database_path': str(db_path),
                        'import_successful': True,
                        'inserts': updated_stats.database_inserts,
                        'updates': updated_stats.database_updates,
                        'errors': updated_stats.database_errors
                    }
                    
                    self.logger.info(f"✅ Successfully imported to {db_name} database")
                    
                except Exception as e:
                    all_imports_successful = False
                    error_msg = f"Failed to import to {db_name} database: {e}"
                    self.logger.error(error_msg)
                    
                    import_results['database_results'][db_name] = {
                        'database_path': str(db_path),
                        'import_successful': False,
                        'error': error_msg
                    }
            
            import_results['overall_success'] = all_imports_successful
            
            if all_imports_successful:
                self.logger.info("✅ Complete data import process completed successfully")
            else:
                self.logger.warning("⚠️ Data import process completed with some errors")
            
            return import_results
            
        except Exception as e:
            error_msg = f"Error in complete data import: {e}"
            self.logger.error(error_msg)
            import_results['error'] = error_msg
            return import_results
    
    def print_import_summary(self, import_results: Dict[str, Any]):
        """Print a summary of the import operation."""
        print("\n" + "="*80)
        print("RDA DATA IMPORT SUMMARY")
        print("="*80)
        
        # Collection stats
        collection_stats = import_results.get('collection_stats', {})
        print(f"\n📊 COLLECTION STATISTICS:")
        print(f"   Total Requests Found: {collection_stats.get('total_requests_found', 0)}")
        print(f"   Successfully Parsed: {collection_stats.get('successfully_parsed', 0)}")
        print(f"   Parsing Errors: {collection_stats.get('parsing_errors', 0)}")
        print(f"   Collection Time: {collection_stats.get('collection_timestamp', 'N/A')}")
        
        # Database results
        database_results = import_results.get('database_results', {})
        print(f"\n💾 DATABASE IMPORT RESULTS:")
        
        for db_name, result in database_results.items():
            success_icon = "✅" if result.get('import_successful') else "❌"
            print(f"   {success_icon} {db_name.upper()} DATABASE:")
            print(f"      Path: {result.get('database_path', 'N/A')}")
            
            if result.get('import_successful'):
                print(f"      Inserts: {result.get('inserts', 0)}")
                print(f"      Updates: {result.get('updates', 0)}")
                print(f"      Errors: {result.get('errors', 0)}")
            else:
                print(f"      Error: {result.get('error', 'Unknown error')}")
        
        # Overall status
        overall_success = import_results.get('overall_success', False)
        status_icon = "✅" if overall_success else "❌"
        print(f"\n🎯 OVERALL STATUS: {status_icon} {'SUCCESS' if overall_success else 'FAILED'}")
        
        if import_results.get('error'):
            print(f"\n❌ SYSTEM ERROR: {import_results['error']}")
        
        print("="*80)


def create_rda_data_collector(data_dir: str = "./data") -> RDADataCollector:
    """
    Factory function to create an RDADataCollector instance.
    
    Args:
        data_dir: Directory containing database files
        
    Returns:
        Configured RDADataCollector instance
    """
    return RDADataCollector(data_dir)


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='RDA Data Collection and Import System')
    parser.add_argument('--collect-all', action='store_true',
                       help='Collect all RDA requests and import to databases')
    parser.add_argument('--collect-specific', type=str,
                       help='Collect specific request ID and import to databases')
    parser.add_argument('--import-to-production', action='store_true',
                       help='Import to production database only')
    parser.add_argument('--import-to-test', action='store_true',
                       help='Import to test database only')
    parser.add_argument('--import-to-both', action='store_true',
                       help='Import to both production and test databases')
    parser.add_argument('--data-dir', default='./data',
                       help='Directory containing database files')
    parser.add_argument('--verify-schema', action='store_true',
                       help='Verify database schema compatibility only')
    
    args = parser.parse_args()
    
    # Create data collector
    collector = create_rda_data_collector(args.data_dir)
    
    try:
        if args.verify_schema:
            print("=== Verifying Database Schema Compatibility ===")
            
            prod_compatible = collector.verify_database_schema(collector.production_db)
            test_compatible = collector.verify_database_schema(collector.test_db)
            
            print(f"Production Database: {'✅ Compatible' if prod_compatible else '❌ Issues Found'}")
            print(f"Test Database: {'✅ Compatible' if test_compatible else '❌ Issues Found'}")
            
            if not (prod_compatible and test_compatible):
                print("\n⚠️ Run database_reset.py to fix schema issues")
                sys.exit(1)
        
        elif args.collect_all or args.collect_specific:
            # Determine target databases
            target_databases = []
            if args.import_to_production:
                target_databases = ['production']
            elif args.import_to_test:
                target_databases = ['test']
            elif args.import_to_both:
                target_databases = ['production', 'test']
            else:
                # Default to both if not specified
                target_databases = ['production', 'test']
            
            specific_request_id = args.collect_specific if args.collect_specific else None
            
            print("=== Starting RDA Data Collection and Import ===")
            print(f"Target Databases: {', '.join(target_databases)}")
            if specific_request_id:
                print(f"Specific Request: {specific_request_id}")
            
            # Run complete import process
            import_results = collector.run_complete_data_import(
                target_databases=target_databases,
                specific_request_id=specific_request_id
            )
            
            # Print summary
            collector.print_import_summary(import_results)
            
            # Exit with appropriate code
            if not import_results.get('overall_success', False):
                sys.exit(1)
        
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()