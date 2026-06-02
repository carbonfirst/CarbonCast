#!/usr/bin/env python3
"""
Enhanced File Organization Manager for RDA Automation System

This module provides comprehensive file organization with REGION_NAME/VARIABLE structure
and multi-source region/variable detection. It integrates with the existing automation
system to ensure proper file organization during downloads.

Key Features:
- REGION_NAME/VARIABLE directory structure creation
- Multi-source region/variable detection (4-layer detection)
- Automatic directory creation during download process
- Enhanced region detection from coordinate parsing, control file metadata, database lookup, and fallback logic
- Integration with existing rdams_client.py download functionality
- Validation and accuracy checking for region/variable detection
"""

import os
import sys
import json
import logging
import sqlite3
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rdams_client
from automation.data_sync import RDADataSyncService
from robust_region_mapper import RobustRegionMapper, create_robust_region_mapper


@dataclass
class RegionVariableInfo:
    """Data class for region and variable information."""
    region: str
    variable: str
    confidence: float  # 0.0 to 1.0
    detection_method: str  # coordinate, control_file, database, fallback
    raw_data: Dict[str, Any]


@dataclass
class FileOrganizationResult:
    """Result of file organization operation."""
    success: bool
    original_path: str
    organized_path: str
    region: str
    variable: str
    detection_method: str
    confidence: float
    error_message: Optional[str] = None


class EnhancedFileOrganizationManager:
    """
    Enhanced File Organization Manager with multi-source detection.
    
    Provides comprehensive file organization with REGION_NAME/VARIABLE structure
    using a 4-layer detection system for maximum accuracy.
    """
    
    def __init__(self, base_download_dir: str = "downloaded_files", 
                 db_path: str = "src/python/data/automation_state.db"):
        """
        Initialize the Enhanced File Organization Manager.
        
        Args:
            base_download_dir: Base directory for organized downloads
            db_path: Path to the SQLite database file
        """
        self.base_download_dir = Path(base_download_dir)
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Initialize data sync service for region definitions
        self.data_sync = RDADataSyncService(db_path)
        
        # Initialize robust region mapper for enhanced detection
        self.robust_mapper = create_robust_region_mapper(db_path)
        
        # Enhanced region definitions with comprehensive coverage
        self.region_definitions = {
            # Major Grid Operators and ISOs
            'ERCOT': {
                'name': 'Electric Reliability Council of Texas',
                'bounds': {'lat_min': 25.5, 'lat_max': 36.5, 'lon_min': -106.5, 'lon_max': -93.5},
                'priority': 1,
                'aliases': ['ERCOT', 'Texas', 'TX']
            },
            'CISO': {
                'name': 'California Independent System Operator',
                'bounds': {'lat_min': 32.0, 'lat_max': 42.0, 'lon_min': -125.0, 'lon_max': -114.0},
                'priority': 1,
                'aliases': ['CISO', 'California', 'CA', 'CAISO']
            },
            'PJM': {
                'name': 'PJM Interconnection',
                'bounds': {'lat_min': 35.0, 'lat_max': 48.0, 'lon_min': -91.0, 'lon_max': -66.0},
                'priority': 1,
                'aliases': ['PJM', 'Pennsylvania', 'PA']
            },
            'NYISO': {
                'name': 'New York Independent System Operator',
                'bounds': {'lat_min': 40.0, 'lat_max': 45.5, 'lon_min': -80.0, 'lon_max': -71.5},
                'priority': 2,
                'aliases': ['NYISO', 'New York', 'NY']
            },
            'ISNE': {
                'name': 'ISO New England',
                'bounds': {'lat_min': 41.0, 'lat_max': 47.5, 'lon_min': -73.5, 'lon_max': -66.5},
                'priority': 2,
                'aliases': ['ISNE', 'New England', 'NE']
            },
            'MISO': {
                'name': 'Midcontinent Independent System Operator',
                'bounds': {'lat_min': 35.0, 'lat_max': 49.0, 'lon_min': -104.0, 'lon_max': -82.0},
                'priority': 3,
                'aliases': ['MISO', 'Midwest']
            },
            'SPP': {
                'name': 'Southwest Power Pool',
                'bounds': {'lat_min': 33.0, 'lat_max': 43.0, 'lon_min': -106.0, 'lon_max': -89.0},
                'priority': 3,
                'aliases': ['SPP', 'Southwest']
            },
            
            # Regional Utilities
            'AZPS': {
                'name': 'Arizona Public Service',
                'bounds': {'lat_min': 31.0, 'lat_max': 37.0, 'lon_min': -115.0, 'lon_max': -109.0},
                'priority': 2,
                'aliases': ['AZPS', 'Arizona', 'AZ']
            },
            'NEVP': {
                'name': 'Nevada Power',
                'bounds': {'lat_min': 35.0, 'lat_max': 42.0, 'lon_min': -120.0, 'lon_max': -114.0},
                'priority': 2,
                'aliases': ['NEVP', 'Nevada', 'NV']
            },
            'PACW': {
                'name': 'PacifiCorp West',
                'bounds': {'lat_min': 37.0, 'lat_max': 49.0, 'lon_min': -125.0, 'lon_max': -111.0},
                'priority': 2,
                'aliases': ['PACW', 'PacifiCorp']
            },
            'WACM': {
                'name': 'Western Area Colorado Missouri',
                'bounds': {'lat_min': 37.0, 'lat_max': 45.0, 'lon_min': -109.0, 'lon_max': -94.0},
                'priority': 2,
                'aliases': ['WACM', 'Western Area']
            },
            'PSCO': {
                'name': 'Public Service Company of Colorado',
                'bounds': {'lat_min': 37.0, 'lat_max': 41.0, 'lon_min': -109.0, 'lon_max': -102.0},
                'priority': 2,
                'aliases': ['PSCO', 'Colorado', 'CO']
            },
            
            # Southeastern Utilities
            'DUK': {
                'name': 'Duke Energy',
                'bounds': {'lat_min': 33.0, 'lat_max': 37.0, 'lon_min': -84.0, 'lon_max': -75.0},
                'priority': 2,
                'aliases': ['DUK', 'Duke']
            },
            'FPL': {
                'name': 'Florida Power & Light',
                'bounds': {'lat_min': 24.5, 'lat_max': 31.0, 'lon_min': -87.5, 'lon_max': -80.0},
                'priority': 2,
                'aliases': ['FPL', 'Florida', 'FL']
            },
            'FPC': {
                'name': 'Florida Power Corporation',
                'bounds': {'lat_min': 25.0, 'lat_max': 30.0, 'lon_min': -85.0, 'lon_max': -81.0},
                'priority': 2,
                'aliases': ['FPC', 'Florida Power']
            },
            
            # International (European regions)
            'DE': {
                'name': 'Germany',
                'bounds': {'lat_min': 47.0, 'lat_max': 55.0, 'lon_min': 5.0, 'lon_max': 15.0},
                'priority': 4,
                'aliases': ['DE', 'Germany', 'Deutschland']
            },
            'FR': {
                'name': 'France',
                'bounds': {'lat_min': 42.0, 'lat_max': 51.5, 'lon_min': -5.0, 'lon_max': 8.0},
                'priority': 4,
                'aliases': ['FR', 'France']
            },
            'GB': {
                'name': 'Great Britain',
                'bounds': {'lat_min': 49.5, 'lat_max': 61.0, 'lon_min': -8.0, 'lon_max': 2.0},
                'priority': 4,
                'aliases': ['GB', 'UK', 'Great Britain', 'United Kingdom']
            },
            'NL': {
                'name': 'Netherlands',
                'bounds': {'lat_min': 50.5, 'lat_max': 54.0, 'lon_min': 3.0, 'lon_max': 7.5},
                'priority': 4,
                'aliases': ['NL', 'Netherlands', 'Holland']
            }
        }
        
        # Enhanced variable patterns for detection with meteorological codes
        self.variable_patterns = {
            'dswrf': {
                'patterns': [
                    'downward shortwave radiation', 'solar radiation', 'dswrf',
                    'shortwave', 'solar', 'radiation flux', 'surface solar',
                    'downward solar', 'sw radiation', 'solar irradiance'
                ],
                'aliases': ['dswrf'],
                'priority': 1
            },
            'ugrd_vgrd': {
                'patterns': [
                    'wind', 'u-component', 'v-component', 'ugrd', 'vgrd',
                    'wind speed', 'wind direction', 'wind velocity',
                    '10 m wind', 'surface wind', 'wind vector'
                ],
                'aliases': ['ugrd_vgrd'],
                'priority': 1
            },
            'apcp': {
                'patterns': [
                    'precipitation', 'rain', 'apcp', 'total precipitation',
                    'accumulation', 'precip', 'rainfall', 'precipitation rate',
                    'convective precipitation', 'large scale precipitation'
                ],
                'aliases': ['apcp'],
                'priority': 1
            },
            'tmp_dpt': {
                'patterns': [
                    'temperature', 'tmp', 'dewpoint', 'dewpoint temperature',
                    '2 m', 'surface temperature', '2m temperature',
                    'air temperature', 'ambient temperature', 'dpt'
                ],
                'aliases': ['tmp_dpt'],
                'priority': 1
            }
        }
        
        self.logger.info("Enhanced File Organization Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the file organization manager."""
        logger = logging.getLogger('rda_automation.file_organization')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def detect_region_variable_multi_source(self, request_id: str,
                                          control_file_path: Optional[str] = None,
                                          rinfo: Optional[str] = None,
                                          subset_note: Optional[str] = None) -> RegionVariableInfo:
        """
        Multi-source region and variable detection using robust region mapper.
        
        Args:
            request_id: RDA request ID
            control_file_path: Optional path to control file
            rinfo: Optional rinfo parameter string
            subset_note: Optional subset note description
            
        Returns:
            RegionVariableInfo with detected region and variable
        """
        # Create request data structure for robust mapper
        request_data = {
            'request_index': request_id,
            'rinfo': rinfo or '',
            'subset_info': {'note': subset_note} if subset_note else {},
            'title': '',
            'description': ''
        }
        
        # Use robust region mapper for detection
        detection_result = self.robust_mapper.robust_region_detection(
            request_data, control_file_path
        )
        
        # Convert to RegionVariableInfo format
        confidence = detection_result.confidence
        detection_method = detection_result.detection_method
        
        # Add coordinate match information to raw data
        raw_data = detection_result.raw_data.copy()
        if detection_result.coordinate_match:
            raw_data.update({
                'coordinate_match_type': detection_result.coordinate_match.match_type,
                'tolerance_used': detection_result.coordinate_match.tolerance_used,
                'match_confidence': detection_result.coordinate_match.confidence
            })
        
        result = RegionVariableInfo(
            region=detection_result.region,
            variable=detection_result.variable,
            confidence=confidence,
            detection_method=detection_method,
            raw_data=raw_data
        )
        
        self.logger.info(f"Robust detection for {request_id}: {result.region}/{result.variable} "
                        f"(confidence: {result.confidence:.2f}, method: {result.detection_method})")
        
        return result
    
    def _detect_from_coordinates(self, rinfo: str) -> Optional[RegionVariableInfo]:
        """Detect region from coordinate bounds in rinfo."""
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
                region = self._extract_region_from_coordinates(slat, nlat, wlon, elon)
                
                return RegionVariableInfo(
                    region=region,
                    variable="unknown",  # Coordinates don't indicate variable
                    confidence=0.8,
                    detection_method="coordinate",
                    raw_data={"bounds": {"nlat": nlat, "slat": slat, "wlon": wlon, "elon": elon}}
                )
        except Exception as e:
            self.logger.warning(f"Error detecting from coordinates: {e}")
        
        return None
    
    def _extract_region_from_coordinates(self, lat_min: float, lat_max: float, 
                                       lon_min: float, lon_max: float) -> str:
        """Extract region from coordinate bounds using enhanced logic."""
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
        
        # Enhanced fallback logic with more granular geographic regions
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
    
    def _detect_from_control_file(self, control_file_path: str) -> Optional[RegionVariableInfo]:
        """Detect region and variable from control file metadata."""
        try:
            # Parse filename for region/variable hints
            filename = Path(control_file_path).stem
            parts = filename.split('_')
            
            detected_region = None
            detected_variable = None
            confidence = 0.6
            
            # Check filename parts against region aliases
            for part in parts:
                part_upper = part.upper()
                for region_code, region_info in self.region_definitions.items():
                    if part_upper in [alias.upper() for alias in region_info.get('aliases', [])]:
                        detected_region = region_code
                        confidence += 0.2
                        break
                
                # Check against variable patterns
                part_lower = part.lower()
                for var_type, var_info in self.variable_patterns.items():
                    if part_lower in [alias.lower() for alias in var_info.get('aliases', [])]:
                        detected_variable = var_type
                        confidence += 0.2
                        break
            
            # Read control file content for additional hints
            try:
                with open(control_file_path, 'r') as f:
                    content = f.read().lower()
                    
                    # Look for variable patterns in content
                    if not detected_variable:
                        for var_type, var_info in self.variable_patterns.items():
                            if any(pattern in content for pattern in var_info['patterns']):
                                detected_variable = var_type
                                confidence += 0.1
                                break
            except Exception:
                pass
            
            if detected_region or detected_variable:
                return RegionVariableInfo(
                    region=detected_region or "UNKNOWN",
                    variable=detected_variable or "unknown",
                    confidence=min(confidence, 1.0),
                    detection_method="control_file",
                    raw_data={"filename": filename, "path": control_file_path}
                )
        except Exception as e:
            self.logger.warning(f"Error detecting from control file: {e}")
        
        return None
    
    def _detect_from_database(self, request_id: str) -> Optional[RegionVariableInfo]:
        """Detect region and variable from database records."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Check control_files_tracking table
                cursor.execute("""
                    SELECT region, variable_type, control_file_path
                    FROM control_files_tracking
                    WHERE request_index = ? OR request_id = ?
                """, (request_id, request_id))
                
                row = cursor.fetchone()
                if row and row['region'] and row['variable_type']:
                    return RegionVariableInfo(
                        region=row['region'],
                        variable=row['variable_type'],
                        confidence=0.9,
                        detection_method="database",
                        raw_data={"source": "control_files_tracking", "control_file": row['control_file_path']}
                    )
                
                # Check rda_requests table
                cursor.execute("""
                    SELECT rinfo, subset_note
                    FROM rda_requests
                    WHERE request_index = ? OR request_id = ?
                """, (request_id, request_id))
                
                row = cursor.fetchone()
                if row:
                    # Use our own enhanced detection logic instead of data_sync
                    region = self._extract_region_from_coordinates_rinfo(row['rinfo'] or '')
                    variable = self._extract_variable_from_subset_note_enhanced(row['subset_note'] or '')
                    
                    if region != "UNKNOWN" or variable != "unknown":
                        return RegionVariableInfo(
                            region=region,
                            variable=variable,
                            confidence=0.7,
                            detection_method="database",
                            raw_data={"source": "rda_requests", "rinfo": row['rinfo'], "subset_note": row['subset_note']}
                        )
        except Exception as e:
            self.logger.warning(f"Error detecting from database: {e}")
        
        return None
    
    def _detect_from_subset_note(self, subset_note: str) -> Optional[RegionVariableInfo]:
        """Detect variable from subset note description."""
        try:
            note_lower = subset_note.lower()
            
            # Enhanced variable detection patterns
            for var_type, var_info in self.variable_patterns.items():
                if any(pattern in note_lower for pattern in var_info['patterns']):
                    return RegionVariableInfo(
                        region="UNKNOWN",  # Subset note doesn't indicate region
                        variable=var_type,
                        confidence=0.6,
                        detection_method="subset_note",
                        raw_data={"subset_note": subset_note}
                    )
        except Exception as e:
            self.logger.warning(f"Error detecting from subset note: {e}")
        
        return None
    
    def _extract_region_from_coordinates_rinfo(self, rinfo: str) -> str:
        """Extract region from rinfo parameter string using coordinate bounds."""
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
    
    def _extract_variable_from_subset_note_enhanced(self, subset_note: str) -> str:
        """Extract variable from subset note using enhanced meteorological codes."""
        if not subset_note:
            return "unknown"
        
        note_lower = subset_note.lower()
        
        # Use our enhanced variable patterns with meteorological codes
        for var_type, var_info in self.variable_patterns.items():
            if any(pattern in note_lower for pattern in var_info['patterns']):
                return var_type
        
        return "unknown"
    
    def _fallback_detection(self, request_id: str, rinfo: Optional[str],
                          subset_note: Optional[str]) -> RegionVariableInfo:
        """Fallback detection when other methods fail."""
        # Use basic heuristics or defaults
        region = "UNKNOWN"
        variable = "unknown"
        confidence = 0.1
        
        # Try to extract any hints from available data
        raw_data = {"request_id": request_id}
        
        if rinfo:
            raw_data["rinfo"] = rinfo
            # Basic geographic fallback based on coordinate ranges
            if "nlat" in rinfo and "slat" in rinfo:
                try:
                    # Extract rough geographic region
                    if "-125" in rinfo and "-114" in rinfo:  # Western US longitude range
                        region = "CISO"
                        confidence = 0.3
                    elif "-106" in rinfo and "-93" in rinfo:  # Texas longitude range
                        region = "ERCOT"
                        confidence = 0.3
                except:
                    pass
        
        if subset_note:
            raw_data["subset_note"] = subset_note
            # Basic variable detection using meteorological codes
            note_lower = subset_note.lower()
            if "solar" in note_lower or "radiation" in note_lower:
                variable = "dswrf"
                confidence = 0.3
            elif "wind" in note_lower:
                variable = "ugrd_vgrd"
                confidence = 0.3
            elif "precip" in note_lower or "rain" in note_lower:
                variable = "apcp"
                confidence = 0.3
            elif "temp" in note_lower:
                variable = "tmp_dpt"
                confidence = 0.3
        
        return RegionVariableInfo(
            region=region,
            variable=variable,
            confidence=confidence,
            detection_method="fallback",
            raw_data=raw_data
        )
    
    def _select_best_detection(self, detection_results: List[RegionVariableInfo]) -> RegionVariableInfo:
        """Select the best detection result based on confidence and method priority."""
        if not detection_results:
            return self._fallback_detection("unknown", None, None)
        
        # Method priority weights
        method_weights = {
            "coordinate": 0.9,
            "database": 1.0,
            "control_file": 0.8,
            "subset_note": 0.6,
            "fallback": 0.1
        }
        
        # Calculate weighted scores
        scored_results = []
        for result in detection_results:
            weight = method_weights.get(result.detection_method, 0.5)
            score = result.confidence * weight
            scored_results.append((score, result))
        
        # Sort by score (highest first)
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        # Combine results for best region and variable
        best_region = None
        best_variable = None
        best_region_score = 0
        best_variable_score = 0
        
        for score, result in scored_results:
            if result.region != "UNKNOWN" and score > best_region_score:
                best_region = result.region
                best_region_score = score
            
            if result.variable != "unknown" and score > best_variable_score:
                best_variable = result.variable
                best_variable_score = score
        
        # Use the highest scoring result as base, but combine best region/variable
        base_result = scored_results[0][1]
        
        return RegionVariableInfo(
            region=best_region or base_result.region,
            variable=best_variable or base_result.variable,
            confidence=(best_region_score + best_variable_score) / 2,
            detection_method=f"multi_source({base_result.detection_method})",
            raw_data={
                "combined_from": [r.detection_method for _, r in scored_results],
                "best_region_method": next((r.detection_method for _, r in scored_results if r.region == best_region), None),
                "best_variable_method": next((r.detection_method for _, r in scored_results if r.variable == best_variable), None)
            }
        )
    
    def create_organized_directory(self, region: str, variable: str) -> Path:
        """
        Create organized directory structure: REGION_NAME/VARIABLE/
        
        Args:
            region: Region identifier
            variable: Variable type
            
        Returns:
            Path to the created directory
        """
        organized_path = self.base_download_dir / region / variable
        organized_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Created organized directory: {organized_path}")
        return organized_path
    
    def organize_downloaded_file(self, original_file_path: str, request_id: str,
                               control_file_path: Optional[str] = None,
                               rinfo: Optional[str] = None,
                               subset_note: Optional[str] = None) -> FileOrganizationResult:
        """
        Organize a downloaded file into REGION_NAME/VARIABLE structure.
        
        Args:
            original_file_path: Path to the original downloaded file
            request_id: RDA request ID
            control_file_path: Optional path to control file
            rinfo: Optional rinfo parameter string
            subset_note: Optional subset note description
            
        Returns:
            FileOrganizationResult with organization details
        """
        try:
            # Detect region and variable
            detection_info = self.detect_region_variable_multi_source(
                request_id, control_file_path, rinfo, subset_note
            )
            
            # Create organized directory
            organized_dir = self.create_organized_directory(detection_info.region, detection_info.variable)
            
            # Generate organized file path
            original_path = Path(original_file_path)
            organized_path = organized_dir / original_path.name
            
            # Move or copy file to organized location
            if original_path.exists():
                if original_path != organized_path:
                    # Move file to organized location
                    organized_path.parent.mkdir(parents=True, exist_ok=True)
                    original_path.rename(organized_path)
                    
                    self.logger.info(f"Organized file: {original_path} -> {organized_path}")
                else:
                    self.logger.info(f"File already in organized location: {organized_path}")
                
                return FileOrganizationResult(
                    success=True,
                    original_path=str(original_path),
                    organized_path=str(organized_path),
                    region=detection_info.region,
                    variable=detection_info.variable,
                    detection_method=detection_info.detection_method,
                    confidence=detection_info.confidence
                )
            else:
                error_msg = f"Original file not found: {original_file_path}"
                self.logger.error(error_msg)
                
                return FileOrganizationResult(
                    success=False,
                    original_path=original_file_path,
                    organized_path="",
                    region=detection_info.region,
                    variable=detection_info.variable,
                    detection_method=detection_info.detection_method,
                    confidence=detection_info.confidence,
                    error_message=error_msg
                )
        
        except Exception as e:
            error_msg = f"Error organizing file {original_file_path}: {e}"
            self.logger.error(error_msg)
            
            return FileOrganizationResult(
                success=False,
                original_path=original_file_path,
                organized_path="",
                region="UNKNOWN",
                variable="unknown",
                detection_method="error",
                confidence=0.0,
                error_message=error_msg
            )
    
    def organize_request_download(self, request_id: str, download_directory: str = "./") -> List[FileOrganizationResult]:
        """
        Download and organize files for a specific request.
        
        Args:
            request_id: RDA request ID to download and organize
            download_directory: Temporary download directory
            
        Returns:
            List of FileOrganizationResult objects
        """
        results = []
        
        try:
            self.logger.info(f"Starting organized download for request {request_id}")
            
            # Get request information from database
            request_info = self._get_request_info(request_id)
            
            # Ensure download directory exists and is absolute
            download_dir = os.path.abspath(download_directory)
            os.makedirs(download_dir, exist_ok=True)
            
            self.logger.info(f"Downloading to directory: {download_dir}")
            
            # Download files using rdams_client
            download_result = rdams_client.download(request_id, download_dir)
            
            if not download_result or 'data' not in download_result:
                self.logger.error(f"Failed to download files for request {request_id}")
                return []
            
            self.logger.info(f"Download result structure: {list(download_result.keys())}")
            if 'data' in download_result:
                self.logger.info(f"Download data keys: {list(download_result['data'].keys())}")
            
            # Get list of downloaded files with enhanced detection
            downloaded_files = []
            
            # Method 1: Check web_files from download result
            if 'web_files' in download_result['data']:
                self.logger.info(f"Found {len(download_result['data']['web_files'])} web_files in download result")
                for file_info in download_result['data']['web_files']:
                    expected_filename = os.path.basename(file_info['web_path'])
                    file_path = os.path.join(download_dir, expected_filename)
                    self.logger.info(f"Checking for file: {file_path}")
                    if os.path.exists(file_path):
                        downloaded_files.append(file_path)
                        self.logger.info(f"✅ Found downloaded file: {file_path}")
                    else:
                        self.logger.warning(f"❌ Expected file not found: {file_path}")
            
            # Method 2: Scan download directory for any files (fallback)
            if not downloaded_files:
                self.logger.warning("No files found via web_files method, scanning download directory...")
                try:
                    for item in os.listdir(download_dir):
                        item_path = os.path.join(download_dir, item)
                        if os.path.isfile(item_path):
                            downloaded_files.append(item_path)
                            self.logger.info(f"📁 Found file in directory scan: {item_path}")
                except Exception as e:
                    self.logger.error(f"Error scanning download directory: {e}")
            
            self.logger.info(f"Total downloaded files detected: {len(downloaded_files)}")
            
            # Organize each downloaded file
            successful_organizations = 0
            for file_path in downloaded_files:
                self.logger.info(f"🔄 Organizing file: {file_path}")
                result = self.organize_downloaded_file(
                    file_path, request_id,
                    control_file_path=request_info.get('control_file_path'),
                    rinfo=request_info.get('rinfo'),
                    subset_note=request_info.get('subset_note')
                )
                results.append(result)
                
                if result.success:
                    successful_organizations += 1
                    self.logger.info(f"✅ Successfully organized: {result.original_path} -> {result.organized_path}")
                else:
                    self.logger.error(f"❌ Failed to organize: {result.original_path} - {result.error_message}")
            
            self.logger.info(f"Organized {successful_organizations}/{len(downloaded_files)} files for request {request_id}")
            
            # Clean up temp download directory if it's empty
            try:
                if download_dir.endswith('temp_downloads') and os.path.exists(download_dir):
                    remaining_files = os.listdir(download_dir)
                    if not remaining_files:
                        os.rmdir(download_dir)
                        self.logger.info(f"Cleaned up empty temp directory: {download_dir}")
            except Exception as e:
                self.logger.warning(f"Could not clean up temp directory: {e}")
            
            return results
            
        except Exception as e:
            error_msg = f"Error in organized download for request {request_id}: {e}"
            self.logger.error(error_msg)
            
            return [FileOrganizationResult(
                success=False,
                original_path="",
                organized_path="",
                region="UNKNOWN",
                variable="unknown",
                detection_method="error",
                confidence=0.0,
                error_message=error_msg
            )]
    
    def _get_request_info(self, request_id: str) -> Dict[str, Any]:
        """Get request information from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get from rda_requests table
                cursor.execute("""
                    SELECT rinfo, subset_note
                    FROM rda_requests
                    WHERE request_index = ? OR request_id = ?
                """, (request_id, request_id))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'rinfo': row['rinfo'],
                        'subset_note': row['subset_note'],
                        'control_file_path': None
                    }
                
                # Get from control_files_tracking table
                cursor.execute("""
                    SELECT control_file_path, region, variable_type
                    FROM control_files_tracking
                    WHERE request_index = ? OR request_id = ?
                """, (request_id, request_id))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'control_file_path': row['control_file_path'],
                        'region': row['region'],
                        'variable_type': row['variable_type'],
                        'rinfo': None,
                        'subset_note': None
                    }
        except Exception as e:
            self.logger.warning(f"Error getting request info for {request_id}: {e}")
        
        return {}
    
    def validate_organization(self, organized_path: str) -> Dict[str, Any]:
        """
        Validate that file organization follows REGION_NAME/VARIABLE structure.
        
        Args:
            organized_path: Path to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            path_obj = Path(organized_path)
            
            # Check if path follows REGION_NAME/VARIABLE structure
            if len(path_obj.parts) < 2:
                return {
                    'valid': False,
                    'error': 'Path does not have enough components for REGION_NAME/VARIABLE structure'
                }
            
            # Extract region and variable from path
            region = path_obj.parts[-3] if len(path_obj.parts) >= 3 else path_obj.parts[-2]
            variable = path_obj.parts[-2] if len(path_obj.parts) >= 3 else 'unknown'
            
            # Validate region
            region_valid = region in self.region_definitions or region == "UNKNOWN"
            
            # Validate variable
            variable_valid = variable in self.variable_patterns or variable == "unknown"
            
            return {
                'valid': region_valid and variable_valid,
                'region': region,
                'variable': variable,
                'region_valid': region_valid,
                'variable_valid': variable_valid,
                'path': str(organized_path)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Error validating organization: {e}'
            }
    
    def get_organization_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about file organization.
        
        Returns:
            Dictionary with organization statistics
        """
        try:
            stats = {
                'total_regions': 0,
                'total_variables': 0,
                'region_distribution': {},
                'variable_distribution': {},
                'organized_files': 0,
                'directory_structure': {},
                'timestamp': datetime.now().isoformat()
            }
            
            if not self.base_download_dir.exists():
                return stats
            
            # Scan organized directory structure
            for region_dir in self.base_download_dir.iterdir():
                if region_dir.is_dir():
                    region_name = region_dir.name
                    stats['region_distribution'][region_name] = 0
                    stats['directory_structure'][region_name] = {}
                    
                    for variable_dir in region_dir.iterdir():
                        if variable_dir.is_dir():
                            variable_name = variable_dir.name
                            
                            # Count files in this directory
                            file_count = len([f for f in variable_dir.iterdir() if f.is_file()])
                            
                            stats['region_distribution'][region_name] += file_count
                            stats['variable_distribution'][variable_name] = stats['variable_distribution'].get(variable_name, 0) + file_count
                            stats['directory_structure'][region_name][variable_name] = file_count
                            stats['organized_files'] += file_count
            
            stats['total_regions'] = len(stats['region_distribution'])
            stats['total_variables'] = len(stats['variable_distribution'])
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting organization statistics: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}


def create_file_organization_manager(base_download_dir: str = "downloaded_files",
                                   db_path: str = "src/python/data/automation_state.db") -> EnhancedFileOrganizationManager:
    """
    Factory function to create an Enhanced File Organization Manager.
    
    Args:
        base_download_dir: Base directory for organized downloads
        db_path: Path to the SQLite database file
        
    Returns:
        Configured EnhancedFileOrganizationManager instance
    """
    return EnhancedFileOrganizationManager(base_download_dir, db_path)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced File Organization Manager')
    parser.add_argument('--test-detection', type=str,
                       help='Test multi-source detection for request ID')
    parser.add_argument('--organize-request', type=str,
                       help='Download and organize files for request ID')
    parser.add_argument('--stats', action='store_true',
                       help='Show organization statistics')
    parser.add_argument('--validate', type=str,
                       help='Validate organization of specific path')
    
    args = parser.parse_args()
    
    # Create file organization manager
    manager = create_file_organization_manager()
    
    if args.test_detection:
        print(f"=== Testing Multi-Source Detection for Request {args.test_detection} ===")
        result = manager.detect_region_variable_multi_source(args.test_detection)
        print(f"Region: {result.region}")
        print(f"Variable: {result.variable}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Detection Method: {result.detection_method}")
        print(f"Raw Data: {json.dumps(result.raw_data, indent=2)}")
    
    elif args.organize_request:
        print(f"=== Organizing Download for Request {args.organize_request} ===")
        results = manager.organize_request_download(args.organize_request)
        
        for i, result in enumerate(results, 1):
            print(f"\nFile {i}:")
            print(f"  Success: {result.success}")
            print(f"  Original: {result.original_path}")
            print(f"  Organized: {result.organized_path}")
            print(f"  Region: {result.region}")
            print(f"  Variable: {result.variable}")
            print(f"  Method: {result.detection_method}")
            print(f"  Confidence: {result.confidence:.2f}")
            if result.error_message:
                print(f"  Error: {result.error_message}")
    
    elif args.validate:
        print(f"=== Validating Organization: {args.validate} ===")
        result = manager.validate_organization(args.validate)
        print(json.dumps(result, indent=2))
    
    elif args.stats:
        print("=== Organization Statistics ===")
        stats = manager.get_organization_statistics()
        print(json.dumps(stats, indent=2))
    
    else:
        parser.print_help()
        print("\n" + "="*60)
        print("EXAMPLES")
        print("="*60)
        print("# Test detection for a specific request:")
        print("python automation/file_organization_manager.py --test-detection 804683")
        print("\n# Download and organize files for a request:")
        print("python automation/file_organization_manager.py --organize-request 804683")
        print("\n# Show organization statistics:")
        print("python automation/file_organization_manager.py --stats")
        print("\n# Validate organization of a path:")
        print("python automation/file_organization_manager.py --validate downloaded_files/CISO/dswrf/file.tar")
        print("="*60)