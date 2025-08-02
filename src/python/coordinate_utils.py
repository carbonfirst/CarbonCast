#!/usr/bin/env python3
"""
Coordinate Utilities for RDA Automation System

This module provides utilities for extracting coordinates from request data
and mapping them to region names for proper file organization.

DEPRECATED: This module is being replaced by robust_region_mapper.py and
enhanced_coordinate_utils.py for improved coordinate precision handling.
"""

import re
import math
import logging
from typing import Dict, Tuple, Optional, List

logger = logging.getLogger(__name__)

# Import the enhanced coordinate utilities for improved functionality
try:
    from enhanced_coordinate_utils import get_region_and_variable_from_request_enhanced as _enhanced_detection
    ENHANCED_AVAILABLE = True
    logger.info("Enhanced coordinate utilities available - using robust region mapping")
except ImportError:
    ENHANCED_AVAILABLE = False
    logger.warning("Enhanced coordinate utilities not available - using legacy methods")

# Comprehensive region coordinate mappings extracted from download_files.py
REGION_COORDINATES = {
    # North American Regions
    "CISO": (42, 32, -124.75, -113.5),
    "PJM": (43, 34.25, -91, -73.5),
    "ERCOT": (36.5, 25.25, -104.5, -93.25),
    "ISNE": (48, 40, -74.25, -66.5),
    "MISO": (50.00, 28.50, -107.75, -81.75),
    "BPAT": (49.50, 39.50, -125.25, -105.50),
    "SWPP": (49.50, 30.25, -107.75, -89.50),
    "SOCO": (35.50, 29.25, -90.50, -80.25),
    "FPL": (31.25, 24.00, -83.50, -79.50),
    "NYISO": (45.50, 40.00, -80.25, -71.25),
    "BANC": (41.75, 37.00, -124.00, -120.00),
    "LDWP": (38.00, 33.25, -119.00, -117.00),
    "TIDC": (38.25, 36.75, -121.75, -119.75),
    "DUK": (37.00, 33.00, -84.75, -77.75),
    "SC": (35.25, 31.50, -82.75, -78.00),
    "SCEG": (35.25, 31.50, -83.00, -78.75),
    "SPA": (40.75, 34.25, -98.00, -89.00),
    "FMPP": (30.75, 24.00, -83.00, -79.50),
    "FPC": (31.25, 25.75, -86.50, -80.00),
    "TAL": (31.25, 29.75, -84.75, -83.50),
    "TEC": (29.00, 27.00, -83.25, -81.25),
    "AECI": (41.75, 34.25, -98.50, -88.50),
    "LGEE": (39.50, 36.00, -89.75, -82.25),
    "DOPD": (49.50, 46.75, -120.75, -118.25),
    "GCPD": (48.50, 46.25, -120.50, -118.50),
    "GRID": (46.25, 44.75, -119.75, -118.25),
    "IPCO": (47.25, 41.50, -120.50, -111.00),
    "NEVP": (42.50, 34.50, -122.00, -111.00),
    "NWMT": (49.50, 43.25, -116.50, -103.50),
    "PACE": (45.50, 33.00, -115.75, -104.25),
    "PACW": (47.50, 38.75, -124.75, -115.75),
    "PGE": (46.50, 44.25, -124.25, -121.25),
    "PSCO": (41.75, 35.75, -109.50, -102.00),
    "PSEI": (49.50, 45.75, -123.75, -119.75),
    "SCL": (48.25, 47.00, -123.00, -121.75),
    "TPWR": (48.25, 45.75, -124.00, -120.50),
    "WACM": (48.00, 35.50, -114.50, -95.75),
    "AZPS": (36.75, 30.75, -115.25, -108.75),
    "EPE": (34.00, 26.75, -108.75, -98.25),
    "PNM": (44.50, 30.75, -123.50, -101.50),
    "SRP": (34.50, 32.00, -113.75, -110.50),
    "TEPC": (36.75, 31.25, -115.25, -110.00),
    "WALC": (44.00, 30.75, -124.25, -105.00),
    "TVA": (38.00, 31.75, -90.75, -81.25),
    
    # European Regions
    "AL": (42.75, 39.50, 19.25, 21.00),
    "AT": (49.00, 46.50, 9.50, 17.00),
    "BE": (51.50, 49.50, 2.50, 6.25),
    "BG": (44.25, 41.25, 22.25, 28.50),
    "HR": (46.50, 42.50, 13.75, 19.50),
    "DK": (57.75, 54.50, 7.50, 13.25),
    "EE": (59.50, 57.50, 23.25, 28.25),
    "FI": (70.00, 59.75, 20.50, 31.50),
    "FR": (51.25, 42.25, -5.25, 8.25),
    "DE": (55.25, 47.25, 5.75, 15),
    "GR": (41.75, 35.00, 20.25, 26.50),
    "HU": (48.50, 45.75, 16.25, 22.75),
    "IE": (55.25, 51.75, -10.00, -6.00),
    "IT": (47.00, 36.50, 6.75, 18.50),
    "LV": (58.00, 55.50, 21.00, 28.25),
    "LT": (56.25, 54.00, 21.00, 26.50),
    "NL": (53.50, 50.75, 3.25, 7.00),
    "PL": (54.75, 49, 14, 24),
    "PT": (42.75, 36.50, -10.00, -5.75),
    "RO": (48.25, 43.75, 20.25, 29.50),
    "RS": (46.25, 42.25, 18.75, 23.00),
    "SK": (49.50, 47.75, 16.75, 22.50),
    "SI": (46.75, 45.50, 13.75, 16.50),
    "ES": (43.75, 36.00, -9.25, 3.50),
    "SE": (69, 55.25, 11.25, 21.25),
    "CH": (47.75, 45.75, 6.00, 10.50),
    "CZ": (51.00, 48.50, 12.25, 18.75),
    "GB": (61, 49.75, -8.25, 2.25)
}

# Create reverse lookup dictionary: coordinates -> region
COORDINATE_TO_REGION = {coords: region for region, coords in REGION_COORDINATES.items()}

# Weather variable mappings
WEATHER_VARIABLE_MAPPINGS = {
    "Temperature": "temp",
    "Downward shortwave radiation flux": "dswrf",
    "u-component of wind": "wind",
    "v-component of wind": "wind", 
    "Total precipitation": "rain",
    "TMP/DPT": "temp",
    "DSWRF": "dswrf",
    "U GRD/V GRD": "wind",
    "A PCP": "rain",
    "tmp": "temp",
    "dswrf": "dswrf",
    "ugrd": "wind",
    "vgrd": "wind",
    "apcp": "rain"
}


def extract_coordinates_from_rinfo(rinfo: str) -> Optional[Tuple[float, float, float, float]]:
    """
    Extract coordinates from the rinfo field.
    
    Args:
        rinfo: The rinfo string containing coordinate information
        
    Returns:
        Tuple of (nlat, slat, wlon, elon) or None if not found
    """
    try:
        # Pattern to match coordinates in rinfo field
        pattern = r'nlat=([-\d.]+);slat=([-\d.]+);wlon=([-\d.]+);elon=([-\d.]+)'
        match = re.search(pattern, rinfo)
        
        if match:
            nlat, slat, wlon, elon = map(float, match.groups())
            logger.debug(f"Extracted coordinates from rinfo: nlat={nlat}, slat={slat}, wlon={wlon}, elon={elon}")
            return (nlat, slat, wlon, elon)
        else:
            logger.warning(f"No coordinates found in rinfo: {rinfo}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting coordinates from rinfo: {e}")
        return None


def map_coordinates_to_region(coordinates: Tuple[float, float, float, float]) -> Optional[str]:
    """
    Map coordinates to a region name using exact matching.
    
    Args:
        coordinates: Tuple of (nlat, slat, wlon, elon)
        
    Returns:
        Region name or None if not found
    """
    try:
        # Try exact match first
        if coordinates in COORDINATE_TO_REGION:
            region = COORDINATE_TO_REGION[coordinates]
            logger.debug(f"Found exact coordinate match: {coordinates} -> {region}")
            return region
        
        # Try approximate matching with tolerance
        nlat, slat, wlon, elon = coordinates
        tolerance = 0.5  # Allow small differences
        
        for (ref_nlat, ref_slat, ref_wlon, ref_elon), region in COORDINATE_TO_REGION.items():
            if (abs(nlat - ref_nlat) <= tolerance and 
                abs(slat - ref_slat) <= tolerance and
                abs(wlon - ref_wlon) <= tolerance and 
                abs(elon - ref_elon) <= tolerance):
                logger.debug(f"Found approximate coordinate match: {coordinates} -> {region}")
                return region
        
        logger.warning(f"No region found for coordinates: {coordinates}")
        return None
        
    except Exception as e:
        logger.error(f"Error mapping coordinates to region: {e}")
        return None


def extract_parameter_from_subset_info(subset_info: Dict) -> Optional[str]:
    """
    Extract weather parameter from subset_info.
    
    Args:
        subset_info: Dictionary containing subset information
        
    Returns:
        Weather parameter name or None if not found
    """
    try:
        if not subset_info or 'note' not in subset_info:
            return None
            
        note = subset_info['note']
        lines = note.splitlines()
        
        for i, line in enumerate(lines):
            if "Parameter(s):" in line and i + 1 < len(lines):
                parameter = lines[i + 1].strip()
                logger.debug(f"Extracted parameter from subset_info: {parameter}")
                return parameter
                
        logger.warning(f"No parameter found in subset_info: {subset_info}")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting parameter from subset_info: {e}")
        return None


def map_parameter_to_variable_type(parameter: str) -> str:
    """
    Map a parameter name to a standardized weather variable type.
    
    Args:
        parameter: Parameter name from request
        
    Returns:
        Standardized weather variable type
    """
    if not parameter:
        return "unknown"
        
    parameter_upper = parameter.upper()
    
    # Check direct mappings
    for key, value in WEATHER_VARIABLE_MAPPINGS.items():
        if key.upper() in parameter_upper or parameter_upper in key.upper():
            logger.debug(f"Mapped parameter '{parameter}' to variable type '{value}'")
            return value
    
    # Fallback patterns
    if any(term in parameter_upper for term in ['TEMP', 'TMP']):
        return "temp"
    elif any(term in parameter_upper for term in ['WIND', 'GRD', 'UGRD', 'VGRD']):
        return "wind"
    elif any(term in parameter_upper for term in ['RAIN', 'PRECIP', 'APCP']):
        return "rain"
    elif any(term in parameter_upper for term in ['SOLAR', 'RADIATION', 'DSWRF']):
        return "dswrf"
    
    logger.warning(f"Could not map parameter '{parameter}' to known variable type")
    return "unknown"


def generate_control_file_location_patterns() -> List[Tuple[str, str, str]]:
    """
    Generate location patterns for control file matching (similar to download_files.py logic).
    
    Returns:
        List of tuples (region, lat_pattern, lon_pattern)
    """
    patterns = []
    
    for region, (nlat, slat, wlon, elon) in REGION_COORDINATES.items():
        nlat_int = int(nlat)
        slat_int = int(slat)
        
        # Generate different longitude ceiling/floor combinations
        wlon_c = math.ceil(wlon)
        elon_f = math.floor(elon)
        elon_c = math.ceil(elon)
        wlon_f = math.floor(wlon)
        
        lat_pattern = f"Latitudes (top/bottom): {nlat_int} / {slat_int}"
        
        # Add all longitude combinations
        lon_patterns = [
            f"Longitudes (left/right): {wlon_c} / {elon_f}",
            f"Longitudes (left/right): {wlon_c} / {elon_c}",
            f"Longitudes (left/right): {wlon_f} / {elon_f}",
            f"Longitudes (left/right): {wlon_f} / {elon_c}"
        ]
        
        for lon_pattern in lon_patterns:
            patterns.append((region, lat_pattern, lon_pattern))
    
    return patterns


def extract_region_from_subset_info_patterns(subset_info: Dict) -> Optional[str]:
    """
    Extract region from subset_info using pattern matching (fallback method).
    
    Args:
        subset_info: Dictionary containing subset information
        
    Returns:
        Region name or None if not found
    """
    try:
        if not subset_info or 'note' not in subset_info:
            return None
            
        note = subset_info['note']
        patterns = generate_control_file_location_patterns()
        
        for region, lat_pattern, lon_pattern in patterns:
            if lat_pattern in note and lon_pattern in note:
                logger.debug(f"Found region '{region}' using pattern matching")
                return region
        
        logger.warning(f"No region found using pattern matching in subset_info")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting region from subset_info patterns: {e}")
        return None


def get_region_and_variable_from_request_enhanced(request: Dict) -> Tuple[str, str]:
    """
    Enhanced function to extract region and weather variable from request metadata.
    Now uses the robust region mapper for improved coordinate precision handling.
    
    Args:
        request: Request dictionary
        
    Returns:
        Tuple of (region_name, variable_name)
    """
    # Use enhanced coordinate utilities if available
    if ENHANCED_AVAILABLE:
        try:
            return _enhanced_detection(request)
        except Exception as e:
            logger.error(f"Error using enhanced detection, falling back to legacy: {e}")
    
    # Legacy fallback implementation
    region = "UNKNOWN"
    variable = "unknown"
    
    try:
        logger.debug(f"Processing request: {request.get('request_index', 'NO_ID')} (LEGACY MODE)")
        
        # Method 1: Extract coordinates from rinfo field
        rinfo = request.get('rinfo', '')
        if rinfo:
            coordinates = extract_coordinates_from_rinfo(rinfo)
            if coordinates:
                mapped_region = map_coordinates_to_region(coordinates)
                if mapped_region:
                    region = mapped_region
                    logger.info(f"Found region '{region}' using coordinate mapping (LEGACY)")
        
        # Method 2: Fallback to subset_info pattern matching
        if region == "UNKNOWN":
            subset_info = request.get('subset_info', {})
            if subset_info:
                pattern_region = extract_region_from_subset_info_patterns(subset_info)
                if pattern_region:
                    region = pattern_region
                    logger.info(f"Found region '{region}' using pattern matching (LEGACY)")
        
        # Method 3: Final fallback to text matching in title/description
        if region == "UNKNOWN":
            title = request.get('title', '').upper()
            description = request.get('description', '').upper()
            
            for region_key in REGION_COORDINATES.keys():
                if region_key in title or region_key in description:
                    region = region_key
                    logger.info(f"Found region '{region}' using text matching (LEGACY)")
                    break
        
        # Extract weather variable
        subset_info = request.get('subset_info', {})
        if subset_info:
            parameter = extract_parameter_from_subset_info(subset_info)
            if parameter:
                variable = map_parameter_to_variable_type(parameter)
                logger.info(f"Found variable '{variable}' from parameter '{parameter}' (LEGACY)")
        
        # Fallback variable detection from title/description
        if variable == "unknown":
            title = request.get('title', '').upper()
            description = request.get('description', '').upper()
            text_content = f"{title} {description}"
            
            for param_key in WEATHER_VARIABLE_MAPPINGS.keys():
                if param_key.upper() in text_content:
                    variable = WEATHER_VARIABLE_MAPPINGS[param_key]
                    logger.info(f"Found variable '{variable}' using text matching (LEGACY)")
                    break
        
        logger.info(f"Final result (LEGACY): region='{region}', variable='{variable}'")
        return region, variable
        
    except Exception as e:
        logger.error(f"Error in legacy region/variable extraction: {e}")
        return "UNKNOWN", "unknown"