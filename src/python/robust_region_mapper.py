#!/usr/bin/env python3
"""
Robust Region Mapping System for RDA Automation

This module provides a unified, authoritative coordinate mapping system that consolidates
all existing coordinate systems and handles precision mismatches robustly.

Key Features:
- Single authoritative coordinate source
- Fuzzy coordinate matching with configurable tolerance
- Control file coordinate parsing
- Priority-based detection logic
- Handles coordinate precision differences
"""

import os
import re
import math
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Tuple, Optional, List, Any
from dataclasses import dataclass
from datetime import datetime
from logger_utils import get_logger

logger = logging.getLogger(__name__)


@dataclass
class CoordinateMatch:
    """Result of coordinate matching operation."""
    region: str
    confidence: float
    match_type: str  # 'exact', 'fuzzy', 'control_file', 'fallback'
    coordinates: Tuple[float, float, float, float]
    tolerance_used: float
    source: str


@dataclass
class RegionDetectionResult:
    """Complete result of region detection."""
    region: str
    variable: str
    confidence: float
    detection_method: str
    coordinate_match: Optional[CoordinateMatch]
    raw_data: Dict[str, Any]


class RobustRegionMapper:
    """
    Unified coordinate mapping system that consolidates all coordinate sources
    and provides robust matching with fuzzy logic.
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db"):
        """Initialize the robust region mapper."""
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Unified authoritative coordinate system
        # This consolidates all coordinate definitions into a single source
        self.authoritative_coordinates = {
            # North American Grid Operators and ISOs
            "CISO": (42.0, 32.0, -124.75, -113.5),
            "PJM": (43.0, 34.25, -91.0, -73.5),
            "ERCOT": (36.5, 25.25, -104.5, -93.25),
            "ISNE": (48.0, 40.0, -74.25, -66.5),
            "MISO": (50.0, 28.5, -107.75, -81.75),
            "NYISO": (45.5, 40.0, -80.25, -71.25),
            
            # Regional Utilities
            "BANC": (41.75, 37.0, -124.0, -120.0),
            "BPAT": (49.5, 39.5, -125.25, -105.5),
            "SWPP": (49.5, 30.25, -107.75, -89.5),
            "SOCO": (35.5, 29.25, -90.5, -80.25),
            "FPL": (31.25, 24.0, -83.5, -79.5),
            "LDWP": (38.0, 33.25, -119.0, -117.0),
            "TIDC": (38.25, 36.75, -121.75, -119.75),
            "DUK": (37.0, 33.0, -84.75, -77.75),
            "SC": (35.25, 31.5, -82.75, -78.0),
            "SCEG": (35.25, 31.5, -83.0, -78.75),
            "SPA": (40.75, 34.25, -98.0, -89.0),
            "FMPP": (30.75, 24.0, -83.0, -79.5),
            "FPC": (31.25, 25.75, -86.5, -80.0),
            "TAL": (31.25, 29.75, -84.75, -83.5),
            "TEC": (29.0, 27.0, -83.25, -81.25),
            "AECI": (41.75, 34.25, -98.5, -88.5),
            "LGEE": (39.5, 36.0, -89.75, -82.25),
            "DOPD": (49.5, 46.75, -120.75, -118.25),
            "GCPD": (48.5, 46.25, -120.5, -118.5),
            "GRID": (46.25, 44.75, -119.75, -118.25),
            "IPCO": (47.25, 41.5, -120.5, -111.0),
            "NEVP": (42.5, 34.5, -122.0, -111.0),
            "NWMT": (49.5, 43.25, -116.5, -103.5),
            "PACE": (45.5, 33.0, -115.75, -104.25),
            "PACW": (47.5, 38.75, -124.75, -115.75),
            "PGE": (46.5, 44.25, -124.25, -121.25),
            "PSCO": (41.75, 35.75, -109.5, -102.0),
            "PSEI": (49.5, 45.75, -123.75, -119.75),
            "SCL": (48.25, 47.0, -123.0, -121.75),
            "TPWR": (48.25, 45.75, -124.0, -120.5),
            "WACM": (48.0, 35.5, -114.5, -95.75),
            "AZPS": (36.75, 30.75, -115.25, -108.75),
            "EPE": (34.0, 26.75, -108.75, -98.25),
            "PNM": (44.5, 30.75, -123.5, -101.5),
            "SRP": (34.5, 32.0, -113.75, -110.5),
            "TEPC": (36.75, 31.25, -115.25, -110.0),
            "WALC": (44.0, 30.75, -124.25, -105.0),
            "TVA": (38.0, 31.75, -90.75, -81.25),
            
            # European Regions
            "AL": (42.75, 39.5, 19.25, 21.0),
            "AT": (49.0, 46.5, 9.5, 17.0),
            "BE": (51.5, 49.5, 2.5, 6.25),
            "BG": (44.25, 41.25, 22.25, 28.5),
            "HR": (46.5, 42.5, 13.75, 19.5),
            "DK": (57.75, 54.5, 7.5, 13.25),
            "EE": (59.5, 57.5, 23.25, 28.25),
            "FI": (70.0, 59.75, 20.5, 31.5),
            "FR": (51.25, 42.25, -5.25, 8.25),
            "DE": (55.25, 47.25, 5.75, 15.0),
            "GR": (41.75, 35.0, 20.25, 26.5),
            "HU": (48.5, 45.75, 16.25, 22.75),
            "IE": (55.25, 51.75, -10.0, -6.0),
            "IT": (47.0, 36.5, 6.75, 18.5),
            "LV": (58.0, 55.5, 21.0, 28.25),
            "LT": (56.25, 54.0, 21.0, 26.5),
            "NL": (53.5, 50.75, 3.25, 7.0),
            "PL": (54.75, 49.0, 14.0, 24.0),
            "PT": (42.75, 36.5, -10.0, -5.75),
            "RO": (48.25, 43.75, 20.25, 29.5),
            "RS": (46.25, 42.25, 18.75, 23.0),
            "SK": (49.5, 47.75, 16.75, 22.5),
            "SI": (46.75, 45.5, 13.75, 16.5),
            "ES": (43.75, 36.0, -9.25, 3.5),
            "SE": (69.0, 55.25, 11.25, 21.25),
            "CH": (47.75, 45.75, 6.0, 10.5),
            "CZ": (51.0, 48.5, 12.25, 18.75),
            "GB": (61.0, 49.75, -8.25, 2.25)
        }
        
        # Variable mapping patterns
        self.variable_patterns = {
            'dswrf': ['dswrf', 'downward shortwave radiation', 'solar radiation', 'shortwave', 'solar'],
            'ugrd_vgrd': ['wind', 'ugrd', 'vgrd', 'u-component', 'v-component', 'u grd', 'v grd'],
            'apcp': ['rain', 'apcp', 'precipitation', 'precip', 'a pcp', 'total precipitation'],
            'tmp_dpt': ['temp', 'tmp', 'temperature', 'dpt', 'tmp/dpt', 'dewpoint']
        }
        
        # Fuzzy matching tolerances (in degrees)
        self.tolerance_levels = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
        
        self.logger.info("Robust Region Mapper initialized with unified coordinate system")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.robust_region_mapper', level=logging.INFO)
    
    def parse_coordinates_from_rinfo(self, rinfo: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Parse coordinates from rinfo string with enhanced pattern matching.
        
        Args:
            rinfo: The rinfo parameter string
            
        Returns:
            Tuple of (nlat, slat, wlon, elon) or None if not found
        """
        if not rinfo:
            return None
        
        try:
            # Enhanced pattern to handle various formats
            patterns = [
                r'nlat=([-\d.]+);slat=([-\d.]+);wlon=([-\d.]+);elon=([-\d.]+)',
                r'nlat=([-\d.]+).*?slat=([-\d.]+).*?wlon=([-\d.]+).*?elon=([-\d.]+)',
                r'nlat:\s*([-\d.]+).*?slat:\s*([-\d.]+).*?wlon:\s*([-\d.]+).*?elon:\s*([-\d.]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, rinfo, re.DOTALL)
                if match:
                    nlat, slat, wlon, elon = map(float, match.groups())
                    self.logger.debug(f"Parsed coordinates: nlat={nlat}, slat={slat}, wlon={wlon}, elon={elon}")
                    return (nlat, slat, wlon, elon)
            
            self.logger.debug(f"No coordinate pattern found in rinfo: {rinfo[:100]}...")
            return None
            
        except Exception as e:
            self.logger.error(f"Error parsing coordinates from rinfo: {e}")
            return None
    
    def parse_coordinates_from_control_file(self, control_file_path: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Parse coordinates directly from control file.
        
        Args:
            control_file_path: Path to the control file
            
        Returns:
            Tuple of (nlat, slat, wlon, elon) or None if not found
        """
        try:
            if not os.path.exists(control_file_path):
                return None
            
            coordinates = {}
            with open(control_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        if key in ['nlat', 'slat', 'wlon', 'elon']:
                            try:
                                coordinates[key] = float(value.strip())
                            except ValueError:
                                continue
            
            if all(key in coordinates for key in ['nlat', 'slat', 'wlon', 'elon']):
                result = (coordinates['nlat'], coordinates['slat'], 
                         coordinates['wlon'], coordinates['elon'])
                self.logger.debug(f"Parsed control file coordinates: {result}")
                return result
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error parsing control file {control_file_path}: {e}")
            return None
    
    def find_matching_region_fuzzy(self, coordinates: Tuple[float, float, float, float]) -> Optional[CoordinateMatch]:
        """
        Find matching region using fuzzy coordinate matching with multiple tolerance levels.
        
        Args:
            coordinates: Tuple of (nlat, slat, wlon, elon)
            
        Returns:
            CoordinateMatch object or None if no match found
        """
        nlat, slat, wlon, elon = coordinates
        
        # Try exact match first
        for region, (ref_nlat, ref_slat, ref_wlon, ref_elon) in self.authoritative_coordinates.items():
            if (nlat == ref_nlat and slat == ref_slat and 
                wlon == ref_wlon and elon == ref_elon):
                return CoordinateMatch(
                    region=region,
                    confidence=1.0,
                    match_type='exact',
                    coordinates=coordinates,
                    tolerance_used=0.0,
                    source='authoritative'
                )
        
        # Try fuzzy matching with increasing tolerance
        for tolerance in self.tolerance_levels[1:]:  # Skip 0.0 as we already tried exact
            for region, (ref_nlat, ref_slat, ref_wlon, ref_elon) in self.authoritative_coordinates.items():
                if (abs(nlat - ref_nlat) <= tolerance and 
                    abs(slat - ref_slat) <= tolerance and
                    abs(wlon - ref_wlon) <= tolerance and 
                    abs(elon - ref_elon) <= tolerance):
                    
                    # Calculate confidence based on how close the match is
                    max_diff = max(
                        abs(nlat - ref_nlat),
                        abs(slat - ref_slat),
                        abs(wlon - ref_wlon),
                        abs(elon - ref_elon)
                    )
                    confidence = max(0.1, 1.0 - (max_diff / tolerance))
                    
                    return CoordinateMatch(
                        region=region,
                        confidence=confidence,
                        match_type='fuzzy',
                        coordinates=coordinates,
                        tolerance_used=tolerance,
                        source='authoritative'
                    )
        
        return None
    
    def scan_control_files_for_coordinates(self, incoming_dir: str = "src/python/incoming") -> Dict[str, Tuple[float, float, float, float]]:
        """
        Scan all control files in incoming directory to build dynamic coordinate mapping.
        
        Args:
            incoming_dir: Directory containing control files
            
        Returns:
            Dictionary mapping filenames to coordinates
        """
        control_file_coordinates = {}
        
        try:
            incoming_path = Path(incoming_dir)
            if not incoming_path.exists():
                self.logger.warning(f"Incoming directory not found: {incoming_dir}")
                return control_file_coordinates
            
            for control_file in incoming_path.glob("*.ctl"):
                coordinates = self.parse_coordinates_from_control_file(str(control_file))
                if coordinates:
                    control_file_coordinates[control_file.name] = coordinates
                    self.logger.debug(f"Found coordinates in {control_file.name}: {coordinates}")
            
            self.logger.info(f"Scanned {len(control_file_coordinates)} control files with coordinates")
            
        except Exception as e:
            self.logger.error(f"Error scanning control files: {e}")
        
        return control_file_coordinates
    
    def detect_region_from_coordinates(self, coordinates: Tuple[float, float, float, float], 
                                     control_file_path: Optional[str] = None) -> CoordinateMatch:
        """
        Detect region from coordinates using priority-based matching.
        
        Args:
            coordinates: Tuple of (nlat, slat, wlon, elon)
            control_file_path: Optional path to control file for additional context
            
        Returns:
            CoordinateMatch with best match found
        """
        # Priority 1: Try fuzzy matching against authoritative coordinates
        match = self.find_matching_region_fuzzy(coordinates)
        if match:
            self.logger.info(f"Found {match.match_type} match: {coordinates} -> {match.region} "
                           f"(confidence: {match.confidence:.2f}, tolerance: {match.tolerance_used})")
            return match
        
        # Priority 2: Try control file based matching if available
        if control_file_path:
            control_coords = self.parse_coordinates_from_control_file(control_file_path)
            if control_coords:
                control_match = self.find_matching_region_fuzzy(control_coords)
                if control_match:
                    control_match.source = 'control_file'
                    control_match.confidence *= 0.9  # Slightly lower confidence
                    self.logger.info(f"Found control file match: {control_coords} -> {control_match.region}")
                    return control_match
        
        # Priority 3: Geographic fallback based on coordinate ranges
        nlat, slat, wlon, elon = coordinates
        center_lat = (nlat + slat) / 2
        center_lon = (wlon + elon) / 2
        
        fallback_region = self._geographic_fallback(center_lat, center_lon)
        
        return CoordinateMatch(
            region=fallback_region,
            confidence=0.3,
            match_type='fallback',
            coordinates=coordinates,
            tolerance_used=float('inf'),
            source='geographic_fallback'
        )
    
    def _geographic_fallback(self, lat: float, lon: float) -> str:
        """Geographic fallback logic for unknown coordinates."""
        # North America
        if -180 <= lon <= -50:
            if lat >= 49:  # Northern US/Canada
                if lon <= -120:
                    return "PACW"
                elif lon <= -100:
                    return "MISO"
                else:
                    return "NYISO"
            elif lat >= 40:  # Northern US
                if lon <= -120:
                    return "CISO"
                elif lon <= -100:
                    return "MISO"
                else:
                    return "PJM"
            elif lat >= 30:  # Southern US
                if lon <= -120:
                    return "CISO"
                elif lon <= -100:
                    return "ERCOT"
                else:
                    return "FPL"
            else:  # Very southern
                return "FPL"
        
        # Europe
        elif -10 <= lon <= 40:
            if lat >= 55:
                return "DE"  # Northern Europe
            elif lat >= 45:
                return "FR"  # Central Europe
            else:
                return "ES"  # Southern Europe
        
        return "UNKNOWN"
    
    def detect_variable_from_request(self, request_data: Dict) -> str:
        """
        Detect weather variable from request data.
        
        Args:
            request_data: Request data dictionary
            
        Returns:
            Variable name or "unknown"
        """
        try:
            # Check subset_info note
            subset_info = request_data.get('subset_info', {})
            if isinstance(subset_info, dict) and 'note' in subset_info:
                note = subset_info['note'].lower()
                for var_type, patterns in self.variable_patterns.items():
                    if any(pattern in note for pattern in patterns):
                        return var_type
            
            # Check title and description
            title = request_data.get('title', '').lower()
            description = request_data.get('description', '').lower()
            text_content = f"{title} {description}"
            
            for var_type, patterns in self.variable_patterns.items():
                if any(pattern in text_content for pattern in patterns):
                    return var_type
            
            return "unknown"
            
        except Exception as e:
            self.logger.error(f"Error detecting variable: {e}")
            return "unknown"
    
    def detect_variable_from_control_file(self, control_file_path: str) -> str:
        """
        Detect variable from control file.
        
        Args:
            control_file_path: Path to control file
            
        Returns:
            Variable name or "unknown"
        """
        try:
            if not os.path.exists(control_file_path):
                return "unknown"
            
            # Extract from filename
            filename = Path(control_file_path).stem.lower()
            for var_type, patterns in self.variable_patterns.items():
                if any(pattern in filename for pattern in patterns):
                    return var_type
            
            # Extract from file content
            with open(control_file_path, 'r') as f:
                content = f.read().lower()
                for var_type, patterns in self.variable_patterns.items():
                    if any(pattern in content for pattern in patterns):
                        return var_type
            
            return "unknown"
            
        except Exception as e:
            self.logger.error(f"Error detecting variable from control file: {e}")
            return "unknown"
    
    def robust_region_detection(self, request_data: Dict, 
                              control_file_path: Optional[str] = None) -> RegionDetectionResult:
        """
        Main robust region detection function that prioritizes coordinate-based detection.
        
        Args:
            request_data: Request data dictionary
            control_file_path: Optional path to control file
            
        Returns:
            RegionDetectionResult with comprehensive detection information
        """
        request_id = request_data.get('request_index', 'UNKNOWN')
        
        # Method 1: Coordinate-based detection (HIGHEST PRIORITY)
        rinfo = request_data.get('rinfo', '')
        coordinates = self.parse_coordinates_from_rinfo(rinfo)
        
        coordinate_match = None
        if coordinates:
            coordinate_match = self.detect_region_from_coordinates(coordinates, control_file_path)
            if coordinate_match.region != "UNKNOWN":
                variable = self.detect_variable_from_request(request_data)
                if control_file_path:
                    control_var = self.detect_variable_from_control_file(control_file_path)
                    if control_var != "unknown":
                        variable = control_var
                
                return RegionDetectionResult(
                    region=coordinate_match.region,
                    variable=variable,
                    confidence=coordinate_match.confidence,
                    detection_method=f"coordinate_{coordinate_match.match_type}",
                    coordinate_match=coordinate_match,
                    raw_data={
                        "coordinates": coordinates,
                        "rinfo": rinfo,
                        "control_file": control_file_path,
                        "tolerance_used": coordinate_match.tolerance_used
                    }
                )
        
        # Method 2: Control file based detection
        if control_file_path:
            control_coords = self.parse_coordinates_from_control_file(control_file_path)
            if control_coords:
                control_match = self.detect_region_from_coordinates(control_coords)
                if control_match.region != "UNKNOWN":
                    variable = self.detect_variable_from_control_file(control_file_path)
                    
                    return RegionDetectionResult(
                        region=control_match.region,
                        variable=variable,
                        confidence=control_match.confidence * 0.9,
                        detection_method="control_file_coordinates",
                        coordinate_match=control_match,
                        raw_data={
                            "control_coordinates": control_coords,
                            "control_file": control_file_path
                        }
                    )
        
        # Method 3: Database lookup (LOWER PRIORITY - only if coordinates fail)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT region, variable_type
                    FROM control_files_tracking
                    WHERE request_index = ? OR request_id = ?
                    AND region != 'UNKNOWN' AND region IS NOT NULL
                """, (request_id, request_id))
                
                row = cursor.fetchone()
                if row and row['region']:
                    return RegionDetectionResult(
                        region=row['region'],
                        variable=row['variable_type'] or "unknown",
                        confidence=0.7,
                        detection_method="database_lookup",
                        coordinate_match=None,
                        raw_data={"source": "control_files_tracking"}
                    )
        except Exception as e:
            self.logger.warning(f"Database lookup failed: {e}")
        
        # Method 4: Fallback detection
        variable = self.detect_variable_from_request(request_data)
        fallback_region = "UNKNOWN"
        
        # Try to extract any geographic hints
        if coordinates:
            fallback_match = self.detect_region_from_coordinates(coordinates)
            fallback_region = fallback_match.region
        
        return RegionDetectionResult(
            region=fallback_region,
            variable=variable,
            confidence=0.1,
            detection_method="fallback",
            coordinate_match=coordinate_match,
            raw_data={
                "request_id": request_id,
                "coordinates": coordinates,
                "rinfo": rinfo
            }
        )
    
    def validate_detection_accuracy(self, request_data: Dict, 
                                  expected_region: Optional[str] = None,
                                  expected_variable: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate detection accuracy against expected results.
        
        Args:
            request_data: Request data dictionary
            expected_region: Expected region name
            expected_variable: Expected variable name
            
        Returns:
            Validation results dictionary
        """
        result = self.robust_region_detection(request_data)
        
        validation = {
            'request_id': request_data.get('request_index', 'UNKNOWN'),
            'detected_region': result.region,
            'detected_variable': result.variable,
            'confidence': result.confidence,
            'detection_method': result.detection_method,
            'coordinate_match_info': {
                'match_type': result.coordinate_match.match_type if result.coordinate_match else None,
                'tolerance_used': result.coordinate_match.tolerance_used if result.coordinate_match else None,
                'source': result.coordinate_match.source if result.coordinate_match else None
            } if result.coordinate_match else None
        }
        
        if expected_region:
            validation['region_correct'] = result.region == expected_region
            validation['expected_region'] = expected_region
        
        if expected_variable:
            validation['variable_correct'] = result.variable == expected_variable
            validation['expected_variable'] = expected_variable
        
        return validation


def create_robust_region_mapper(db_path: str = "src/python/data/automation_state.db") -> RobustRegionMapper:
    """
    Factory function to create a RobustRegionMapper instance.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        Configured RobustRegionMapper instance
    """
    return RobustRegionMapper(db_path)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Robust Region Mapper')
    parser.add_argument('--test-coordinates', nargs=4, type=float, metavar=('NLAT', 'SLAT', 'WLON', 'ELON'),
                       help='Test coordinate matching with nlat slat wlon elon')
    parser.add_argument('--scan-control-files', action='store_true',
                       help='Scan control files for coordinates')
    parser.add_argument('--test-request', type=str,
                       help='Test detection for request ID')
    
    args = parser.parse_args()
    
    mapper = create_robust_region_mapper()
    
    if args.test_coordinates:
        nlat, slat, wlon, elon = args.test_coordinates
        coordinates = (nlat, slat, wlon, elon)
        print(f"Testing coordinates: {coordinates}")
        
        match = mapper.find_matching_region_fuzzy(coordinates)
        if match:
            print(f"Match found: {match.region}")
            print(f"Confidence: {match.confidence:.2f}")
            print(f"Match type: {match.match_type}")
            print(f"Tolerance used: {match.tolerance_used}")
        else:
            print("No match found")
    
    elif args.scan_control_files:
        print("Scanning control files...")
        control_coords = mapper.scan_control_files_for_coordinates()
        print(json.dumps(control_coords, indent=2))
    
    elif args.test_request:
        print(f"Testing request detection for: {args.test_request}")
        # This would need actual request data - placeholder for now
        