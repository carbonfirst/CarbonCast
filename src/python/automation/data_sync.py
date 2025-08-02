#!/usr/bin/env python3
"""
RDA Data Synchronization Service

This module provides comprehensive data synchronization between the live RDA API
and the dashboard database. It fetches current request status, transforms the data,
and populates all required database tables with accurate region detection.

Key Features:
- Live data fetching from rdams_client.py -get_status
- Enhanced region detection with comprehensive US region mapping
- Data transformation from API format to dashboard schema
- Automatic database population and updates
- Real-time synchronization capabilities
"""

import os
import sys
import json
import sqlite3
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import re

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rdams_client import get_status
from enhanced_coordinate_utils import get_region_and_variable_from_request_enhanced


@dataclass
class RDARequest:
    """Data class for RDA request information from live API."""
    request_index: str
    request_id: str
    dsid: str
    status: str
    date_rqst: Optional[str]
    date_ready: Optional[str]
    date_purge: Optional[str]
    location: Optional[str]
    ncar_contact: Optional[str]
    rinfo: str
    subset_note: str
    raw_response: str


class RDADataSyncService:
    """
    Comprehensive RDA Data Synchronization Service.
    
    Handles fetching live data from RDA API, transforming it to dashboard format,
    and populating all required database tables with enhanced region detection.
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db"):
        """
        Initialize the RDA Data Sync Service.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Enhanced region mapping with comprehensive US coverage
        self.region_definitions = {
            # Major Grid Operators and ISOs
            'ERCOT': {
                'name': 'Electric Reliability Council of Texas',
                'bounds': {'lat_min': 25.5, 'lat_max': 36.5, 'lon_min': -106.5, 'lon_max': -93.5},
                'priority': 1
            },
            'CISO': {
                'name': 'California Independent System Operator',
                'bounds': {'lat_min': 32.0, 'lat_max': 42.0, 'lon_min': -125.0, 'lon_max': -114.0},
                'priority': 1
            },
            'PJM': {
                'name': 'PJM Interconnection',
                'bounds': {'lat_min': 35.0, 'lat_max': 48.0, 'lon_min': -91.0, 'lon_max': -66.0},
                'priority': 1
            },
            'NYISO': {
                'name': 'New York Independent System Operator',
                'bounds': {'lat_min': 40.0, 'lat_max': 45.5, 'lon_min': -80.0, 'lon_max': -71.5},
                'priority': 2
            },
            'ISNE': {
                'name': 'ISO New England',
                'bounds': {'lat_min': 41.0, 'lat_max': 47.5, 'lon_min': -73.5, 'lon_max': -66.5},
                'priority': 2
            },
            'MISO': {
                'name': 'Midcontinent Independent System Operator',
                'bounds': {'lat_min': 35.0, 'lat_max': 49.0, 'lon_min': -104.0, 'lon_max': -82.0},
                'priority': 3
            },
            'SPP': {
                'name': 'Southwest Power Pool',
                'bounds': {'lat_min': 33.0, 'lat_max': 43.0, 'lon_min': -106.0, 'lon_max': -89.0},
                'priority': 3
            },
            
            # Regional Utilities
            'AZPS': {
                'name': 'Arizona Public Service',
                'bounds': {'lat_min': 31.0, 'lat_max': 37.0, 'lon_min': -115.0, 'lon_max': -109.0},
                'priority': 2
            },
            'NEVP': {
                'name': 'Nevada Power',
                'bounds': {'lat_min': 35.0, 'lat_max': 42.0, 'lon_min': -120.0, 'lon_max': -114.0},
                'priority': 2
            },
            'PACW': {
                'name': 'PacifiCorp West',
                'bounds': {'lat_min': 37.0, 'lat_max': 49.0, 'lon_min': -125.0, 'lon_max': -111.0},
                'priority': 2
            },
            'WACM': {
                'name': 'Western Area Colorado Missouri',
                'bounds': {'lat_min': 37.0, 'lat_max': 45.0, 'lon_min': -109.0, 'lon_max': -94.0},
                'priority': 2
            },
            'PSCO': {
                'name': 'Public Service Company of Colorado',
                'bounds': {'lat_min': 37.0, 'lat_max': 41.0, 'lon_min': -109.0, 'lon_max': -102.0},
                'priority': 2
            },
            
            # Southeastern Utilities
            'DUK': {
                'name': 'Duke Energy',
                'bounds': {'lat_min': 33.0, 'lat_max': 37.0, 'lon_min': -84.0, 'lon_max': -75.0},
                'priority': 2
            },
            'FPL': {
                'name': 'Florida Power & Light',
                'bounds': {'lat_min': 24.5, 'lat_max': 31.0, 'lon_min': -87.5, 'lon_max': -80.0},
                'priority': 2
            },
            'FPC': {
                'name': 'Florida Power Corporation',
                'bounds': {'lat_min': 25.0, 'lat_max': 30.0, 'lon_min': -85.0, 'lon_max': -81.0},
                'priority': 2
            },
            
            # International (European regions from the data)
            'DE': {
                'name': 'Germany',
                'bounds': {'lat_min': 47.0, 'lat_max': 55.0, 'lon_min': 5.0, 'lon_max': 15.0},
                'priority': 4
            },
            'FR': {
                'name': 'France',
                'bounds': {'lat_min': 42.0, 'lat_max': 51.5, 'lon_min': -5.0, 'lon_max': 8.0},
                'priority': 4
            },
            'GB': {
                'name': 'Great Britain',
                'bounds': {'lat_min': 49.5, 'lat_max': 61.0, 'lon_min': -8.0, 'lon_max': 2.0},
                'priority': 4
            },
            'NL': {
                'name': 'Netherlands',
                'bounds': {'lat_min': 50.5, 'lat_max': 54.0, 'lon_min': 3.0, 'lon_max': 7.5},
                'priority': 4
            }
        }
        
        self.logger.info("RDA Data Sync Service initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the data sync service."""
        logger = logging.getLogger('rda_automation.data_sync')
        
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
    
    def fetch_live_data(self) -> List[RDARequest]:
        """
        Fetch live data from RDA API using rdams_client.py.
        
        Returns:
            List of RDARequest objects with current status
        """
        try:
            self.logger.info("Fetching live data from RDA API...")
            
            # Get live status data
            api_response = get_status()
            
            if api_response.get('status') != 'ok':
                self.logger.error(f"API returned error status: {api_response}")
                return []
            
            requests = []
            for item in api_response.get('data', []):
                # Extract subset note from subset_info
                subset_note = ""
                if 'subset_info' in item and 'note' in item['subset_info']:
                    subset_note = item['subset_info']['note']
                
                request = RDARequest(
                    request_index=str(item['request_index']),
                    request_id=item['request_id'],
                    dsid=item['dsid'],
                    status=item['status'],
                    date_rqst=item.get('date_rqst'),
                    date_ready=item.get('date_ready'),
                    date_purge=item.get('date_purge'),
                    location=item.get('location'),
                    ncar_contact=item.get('NCAR_contact'),
                    rinfo=item.get('rinfo', ''),
                    subset_note=subset_note,
                    raw_response=json.dumps(item)
                )
                requests.append(request)
            
            self.logger.info(f"Successfully fetched {len(requests)} requests from RDA API")
            return requests
            
        except Exception as e:
            self.logger.error(f"Error fetching live data: {e}")
            return []
    
    def _extract_region_from_coordinates(self, lat_min: float, lat_max: float, 
                                       lon_min: float, lon_max: float) -> str:
        """
        Enhanced region detection based on coordinate bounds.
        
        Args:
            lat_min, lat_max: Latitude bounds
            lon_min, lon_max: Longitude bounds
            
        Returns:
            Region identifier string
        """
        # Calculate center point for region matching
        center_lat = (lat_min + lat_max) / 2
        center_lon = (lon_min + lon_max) / 2
        
        # Find matching regions by priority
        matching_regions = []
        
        for region_code, region_info in self.region_definitions.items():
            bounds = region_info['bounds']
            
            # Check if center point falls within region bounds
            if (bounds['lat_min'] <= center_lat <= bounds['lat_max'] and
                bounds['lon_min'] <= center_lon <= bounds['lon_max']):
                matching_regions.append((region_code, region_info['priority']))
        
        if matching_regions:
            # Return highest priority match (lowest priority number)
            matching_regions.sort(key=lambda x: x[1])
            return matching_regions[0][0]
        
        # Fallback to geographic regions if no specific utility match
        if lon_min >= -130 and lon_max <= -100:  # Western US
            if lat_min >= 32:
                return "PACW"  # Pacific West
            else:
                return "AZPS"  # Southwest
        elif lon_min >= -100 and lon_max <= -90:  # Central US
            if lat_min >= 35:
                return "MISO"  # Midwest
            else:
                return "ERCOT"  # Texas/South Central
        elif lon_min >= -90 and lon_max <= -65:  # Eastern US
            if lat_min >= 40:
                return "NYISO"  # Northeast
            else:
                return "PJM"  # Mid-Atlantic/Southeast
        elif lon_min >= -10 and lon_max <= 30:  # Europe
            if lat_min >= 50:
                return "DE"  # Northern Europe
            else:
                return "FR"  # Southern Europe
        
        return "UNKNOWN"
    
    def _extract_region_from_rinfo(self, rinfo: str) -> str:
        """
        Extract region from rinfo parameter string with enhanced detection.
        
        Args:
            rinfo: Semicolon-delimited parameter string
            
        Returns:
            Region identifier string
        """
        if not rinfo:
            return "UNKNOWN"
        
        try:
            # Parse rinfo parameters
            params = {}
            for param in rinfo.split(';'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    try:
                        params[key.strip()] = float(value.strip())
                    except ValueError:
                        params[key.strip()] = value.strip()
            
            # Extract coordinate bounds
            nlat = params.get('nlat', 0)
            slat = params.get('slat', 0)
            wlon = params.get('wlon', 0)
            elon = params.get('elon', 0)
            
            if all(isinstance(x, (int, float)) for x in [nlat, slat, wlon, elon]):
                return self._extract_region_from_coordinates(slat, nlat, wlon, elon)
            
        except Exception as e:
            self.logger.warning(f"Error parsing rinfo '{rinfo}': {e}")
        
        return "UNKNOWN"
    
    def _extract_variable_from_subset_note(self, subset_note: str) -> str:
        """
        Extract weather variable type from subset_note with enhanced detection.
        
        Args:
            subset_note: Human-readable subset description
            
        Returns:
            Variable type identifier
        """
        if not subset_note:
            return "unknown"
        
        note_lower = subset_note.lower()
        
        # Enhanced variable detection patterns with meteorological codes
        variable_patterns = {
            'dswrf': [
                'downward shortwave radiation', 'solar radiation', 'dswrf',
                'shortwave', 'solar', 'radiation flux'
            ],
            'ugrd_vgrd': [
                'wind', 'u-component', 'v-component', 'ugrd', 'vgrd',
                'wind speed', 'wind direction'
            ],
            'apcp': [
                'precipitation', 'rain', 'apcp', 'total precipitation',
                'accumulation', 'precip'
            ],
            'tmp_dpt': [
                'temperature', 'tmp', 'dewpoint', 'dewpoint temperature',
                '2 m', 'surface temperature', 'dpt'
            ]
        }
        
        # Check for variable patterns
        for var_type, patterns in variable_patterns.items():
            if any(pattern in note_lower for pattern in patterns):
                return var_type
        
        return "unknown"
    
    def sync_rda_requests_table(self, live_requests: List[RDARequest]) -> int:
        """
        Synchronize the rda_requests table with live data using robust region mapping.
        
        Args:
            live_requests: List of current RDA requests from API
            
        Returns:
            Number of records updated/inserted
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Clear existing data to ensure fresh sync
                cursor.execute("DELETE FROM rda_requests")
                
                # Insert current live data with robust region detection
                insert_count = 0
                for request in live_requests:
                    # Use robust region mapping for each request
                    mock_request = {
                        'request_index': request.request_index,
                        'request_id': request.request_id,
                        'rinfo': request.rinfo,
                        'subset_info': {'note': request.subset_note},
                        'raw_data': json.loads(request.raw_response) if request.raw_response else {}
                    }
                    
                    # Apply robust region detection
                    try:
                        region, variable = get_region_and_variable_from_request_enhanced(mock_request)
                        self.logger.info(f"Robust mapping applied: {request.request_id} -> {region}/{variable}")
                    except Exception as e:
                        self.logger.warning(f"Robust mapping failed for {request.request_id}, using fallback: {e}")
                        # Fallback to basic detection if robust mapping fails
                        region = self._extract_region_from_rinfo(request.rinfo)
                        variable = self._extract_variable_from_subset_note(request.subset_note)
                    
                    cursor.execute("""
                        INSERT INTO rda_requests (
                            request_index, request_id, dsid, status,
                            date_rqst, date_ready, date_purge, location,
                            ncar_contact, rinfo, subset_note, raw_response,
                            region, variable_type, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        request.request_index,
                        request.request_id,
                        request.dsid,
                        request.status,
                        request.date_rqst,
                        request.date_ready,
                        request.date_purge,
                        request.location,
                        request.ncar_contact,
                        request.rinfo,
                        request.subset_note,
                        request.raw_response,
                        region,  # Now using robust region mapping
                        variable,  # Now using robust variable detection
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    ))
                    insert_count += 1
                
                conn.commit()
                self.logger.info(f"Synchronized {insert_count} records in rda_requests table with robust region mapping")
                return insert_count
                
        except Exception as e:
            self.logger.error(f"Error syncing rda_requests table: {e}")
            return 0
    
    def sync_control_files_tracking_table(self, live_requests: List[RDARequest]) -> int:
        """
        Populate control_files_tracking table with region and variable data.
        
        This method creates one record per unique region/variable combination,
        with the most recent request_index for that combination.
        
        Args:
            live_requests: List of current RDA requests from API
            
        Returns:
            Number of records updated/inserted
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Clear existing data
                cursor.execute("DELETE FROM control_files_tracking")
                
                # Group requests by region/variable combination to handle UNIQUE constraint
                region_variable_map = {}
                
                for request in live_requests:
                    # Use robust region mapping for each request
                    mock_request = {
                        'request_index': request.request_index,
                        'request_id': request.request_id,
                        'rinfo': request.rinfo,
                        'subset_info': {'note': request.subset_note},
                        'raw_data': json.loads(request.raw_response) if request.raw_response else {}
                    }
                    
                    # Apply robust region detection
                    try:
                        region, variable_type = get_region_and_variable_from_request_enhanced(mock_request)
                    except Exception as e:
                        self.logger.warning(f"Robust mapping failed for {request.request_id}, using fallback: {e}")
                        # Fallback to basic detection if robust mapping fails
                        region = self._extract_region_from_rinfo(request.rinfo)
                        variable_type = self._extract_variable_from_subset_note(request.subset_note)
                    
                    # Generate file path and filename for the control file
                    control_file_path = f"control_files/{region}_{variable_type}_control.ctl"
                    filename = f"{region}_{variable_type}_control.ctl"
                    
                    # Store the most recent request for each region/variable combination
                    key = (region, variable_type, control_file_path)
                    if key not in region_variable_map or request.request_index > region_variable_map[key].request_index:
                        region_variable_map[key] = request
                
                # Insert one record per unique region/variable combination
                insert_count = 0
                for (region, variable_type, control_file_path), request in region_variable_map.items():
                    filename = f"{region}_{variable_type}_control.ctl"
                    
                    self.logger.debug(f"Inserting control file tracking: {region}/{variable_type} -> {request.request_index}")
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO control_files_tracking (
                            file_path, filename, region, variable_type,
                            discovered_at, status, request_index, request_id,
                            control_file_path, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        control_file_path,  # file_path (required)
                        filename,           # filename (required)
                        region,
                        variable_type,
                        datetime.now().isoformat(),  # discovered_at (required)
                        request.status,
                        request.request_index,
                        request.request_id,
                        control_file_path,  # control_file_path (the new column we added)
                        datetime.now().isoformat(),  # created_at
                        datetime.now().isoformat()   # updated_at
                    ))
                    insert_count += 1
                
                conn.commit()
                self.logger.info(f"Synchronized {insert_count} records in control_files_tracking table")
                return insert_count
                
        except Exception as e:
            self.logger.error(f"Error syncing control_files_tracking table: {e}")
            return 0
    
    # regional_progress table has been removed - this method is no longer needed
    def sync_regional_progress_table(self, live_requests: List[RDARequest]) -> int:
        """
        DEPRECATED: regional_progress table has been removed.
        This method now returns 0 and logs a warning.
        
        Args:
            live_requests: List of current RDA requests from API
            
        Returns:
            Always returns 0 (no regions updated)
        """
        self.logger.warning("sync_regional_progress_table called but regional_progress table has been removed")
        return 0
    
    def perform_full_sync(self) -> Dict[str, Any]:
        """
        Perform a complete data synchronization from live RDA API.
        
        Returns:
            Dictionary with sync results and statistics
        """
        start_time = datetime.now()
        self.logger.info("Starting full data synchronization...")
        
        try:
            # Fetch live data
            live_requests = self.fetch_live_data()
            
            if not live_requests:
                return {
                    'success': False,
                    'error': 'No live data available',
                    'timestamp': start_time.isoformat()
                }
            
            # Sync all tables (regional_progress table removed)
            rda_count = self.sync_rda_requests_table(live_requests)
            control_count = self.sync_control_files_tracking_table(live_requests)
            regional_count = 0  # regional_progress table removed
            
            # Calculate statistics
            status_counts = {}
            region_counts = {}
            variable_counts = {}
            
            for request in live_requests:
                # Status distribution
                status = request.status
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # Region distribution
                region = self._extract_region_from_rinfo(request.rinfo)
                region_counts[region] = region_counts.get(region, 0) + 1
                
                # Variable distribution
                variable = self._extract_variable_from_subset_note(request.subset_note)
                variable_counts[variable] = variable_counts.get(variable, 0) + 1
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                'success': True,
                'timestamp': start_time.isoformat(),
                'duration_seconds': duration,
                'total_requests': len(live_requests),
                'tables_synced': {
                    'rda_requests': rda_count,
                    'control_files_tracking': control_count,
                    'regional_progress': regional_count  # Always 0 now
                },
                'statistics': {
                    'status_distribution': status_counts,
                    'region_distribution': region_counts,
                    'variable_distribution': variable_counts
                },
                'data_source': 'live_rda_api'
            }
            
            self.logger.info(f"Full sync completed successfully in {duration:.2f} seconds")
            self.logger.info(f"Synced {len(live_requests)} requests across {len(region_counts)} regions")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error during full sync: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': start_time.isoformat()
            }


def create_data_sync_service(db_path: str = "src/python/data/automation_state.db") -> RDADataSyncService:
    """
    Factory function to create an RDA Data Sync Service.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Configured RDADataSyncService instance
    """
    return RDADataSyncService(db_path)


def main():
    """Main function for running data synchronization."""
    import argparse
    
    parser = argparse.ArgumentParser(description='RDA Data Synchronization Service')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Path to database file')
    parser.add_argument('--sync', action='store_true',
                       help='Perform full data synchronization')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuous sync every 5 minutes')
    
    args = parser.parse_args()
    
    # Create sync service
    sync_service = create_data_sync_service(args.db_path)
    
    if args.sync:
        print("🔄 Starting RDA Data Synchronization...")
        result = sync_service.perform_full_sync()
        
        if result['success']:
            print(f"✅ Sync completed successfully!")
            print(f"📊 Total requests: {result['total_requests']}")
            print(f"🗺️  Regions: {len(result['statistics']['region_distribution'])}")
            print(f"🌡️  Variables: {len(result['statistics']['variable_distribution'])}")
            print(f"⏱️  Duration: {result['duration_seconds']:.2f} seconds")
        else:
            print(f"❌ Sync failed: {result.get('error', 'Unknown error')}")
    
    elif args.continuous:
        print("🔄 Starting continuous data synchronization (every 5 minutes)...")
        import time
        
        while True:
            try:
                result = sync_service.perform_full_sync()
                if result['success']:
                    print(f"✅ Sync completed: {result['total_requests']} requests")
                else:
                    print(f"❌ Sync failed: {result.get('error', 'Unknown error')}")
                
                print("⏳ Waiting 5 minutes for next sync...")
                time.sleep(300)  # 5 minutes
                
            except KeyboardInterrupt:
                print("\n👋 Continuous sync stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in continuous sync: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()