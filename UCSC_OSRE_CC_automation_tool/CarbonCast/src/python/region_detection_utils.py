#!/usr/bin/env python3
"""
Robust Region Detection Utilities for RDA Automation System

This module provides utilities for extracting region names from RDA request data
by parsing coordinate information and mapping it to proper region names.
"""

import re
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Import the enhanced coordinate utilities
try:
    from enhanced_coordinate_utils import get_region_and_variable_from_request_enhanced
    ENHANCED_AVAILABLE = True
    logger.info("Enhanced coordinate utilities available - using robust region mapping")
except ImportError:
    try:
        from coordinate_utils import get_region_and_variable_from_request_enhanced
        ENHANCED_AVAILABLE = True
        logger.warning("Using legacy coordinate_utils - consider upgrading to enhanced_coordinate_utils")
    except ImportError:
        logger.warning("Could not import coordinate utilities, using fallback methods")
        get_region_and_variable_from_request_enhanced = None
        ENHANCED_AVAILABLE = False


def extract_region_and_variable_from_request(request_data: Dict) -> Tuple[str, str]:
    """
    Extract region and weather variable from RDA request data.
    
    This is the main function that should be used throughout the codebase
    for consistent region detection. Now uses robust region mapping for
    improved coordinate precision handling.
    
    Args:
        request_data: Request data dictionary from RDA API
        
    Returns:
        Tuple of (region_name, variable_name)
    """
    try:
        # Method 1: Use the enhanced coordinate utilities if available (PREFERRED)
        if ENHANCED_AVAILABLE and get_region_and_variable_from_request_enhanced:
            region, variable = get_region_and_variable_from_request_enhanced(request_data)
            if region != "UNKNOWN" and variable != "unknown":
                logger.info(f"Successfully detected region='{region}', variable='{variable}' using robust method")
                return region, variable
            elif region != "UNKNOWN":
                # Got region but not variable, try to get variable from legacy methods
                variable = extract_variable_from_request(request_data)
                logger.info(f"Detected region='{region}' (robust), variable='{variable}' (legacy)")
                return region, variable
        
        # Method 2: Fallback to direct coordinate parsing (LEGACY)
        region = extract_region_from_coordinates(request_data)
        variable = extract_variable_from_request(request_data)
        
        if region != "UNKNOWN" or variable != "unknown":
            logger.info(f"Detected region='{region}', variable='{variable}' using legacy fallback method")
            return region, variable
        
        # Method 3: Final fallback
        logger.warning(f"Could not detect region/variable for request {request_data.get('request_index', 'UNKNOWN')}")
        return "UNKNOWN", "unknown"
        
    except Exception as e:
        logger.error(f"Error in region/variable extraction: {e}")
        return "UNKNOWN", "unknown"


def extract_region_from_coordinates(request_data: Dict) -> str:
    """
    Extract region from coordinate information in request data.
    
    Args:
        request_data: Request data dictionary from RDA API
        
    Returns:
        Region name or "UNKNOWN" if not found
    """
    try:
        # Extract coordinates from rinfo field
        rinfo = request_data.get('rinfo', '')
        if not rinfo:
            return "UNKNOWN"
        
        # Parse coordinate parameters from rinfo
        coordinates = parse_coordinates_from_rinfo(rinfo)
        if not coordinates:
            return "UNKNOWN"
        
        # Map coordinates to region
        region = map_coordinates_to_region_name(coordinates)
        return region
        
    except Exception as e:
        logger.error(f"Error extracting region from coordinates: {e}")
        return "UNKNOWN"


def parse_coordinates_from_rinfo(rinfo: str) -> Optional[Tuple[float, float, float, float]]:
    """
    Parse coordinate information from rinfo string.
    
    Args:
        rinfo: The rinfo string containing coordinate and other parameters
        
    Returns:
        Tuple of (nlat, slat, wlon, elon) or None if not found
    """
    try:
        # Pattern to match coordinates in rinfo field
        # Example: "nlat=42.0;slat=32.0;wlon=-124.75;elon=-113.5"
        pattern = r'nlat=([-\d.]+);slat=([-\d.]+);wlon=([-\d.]+);elon=([-\d.]+)'
        match = re.search(pattern, rinfo)
        
        if match:
            nlat, slat, wlon, elon = map(float, match.groups())
            logger.debug(f"Parsed coordinates: nlat={nlat}, slat={slat}, wlon={wlon}, elon={elon}")
            return (nlat, slat, wlon, elon)
        else:
            logger.debug(f"No coordinate pattern found in rinfo: {rinfo[:100]}...")
            return None
            
    except Exception as e:
        logger.error(f"Error parsing coordinates from rinfo: {e}")
        return None


def map_coordinates_to_region_name(coordinates: Tuple[float, float, float, float]) -> str:
    """
    Map coordinates to region name using the comprehensive region mapping.
    
    Args:
        coordinates: Tuple of (nlat, slat, wlon, elon)
        
    Returns:
        Region name or "UNKNOWN" if not found
    """
    try:
        nlat, slat, wlon, elon = coordinates
        
        # Comprehensive region coordinate mappings
        # Format: region_name: (nlat, slat, wlon, elon)
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
        
        # Try exact match first
        for region_name, (ref_nlat, ref_slat, ref_wlon, ref_elon) in REGION_COORDINATES.items():
            if (nlat == ref_nlat and slat == ref_slat and 
                wlon == ref_wlon and elon == ref_elon):
                logger.debug(f"Found exact coordinate match: {coordinates} -> {region_name}")
                return region_name
        
        # Try approximate matching with tolerance
        tolerance = 0.5  # Allow small differences
        for region_name, (ref_nlat, ref_slat, ref_wlon, ref_elon) in REGION_COORDINATES.items():
            if (abs(nlat - ref_nlat) <= tolerance and 
                abs(slat - ref_slat) <= tolerance and
                abs(wlon - ref_wlon) <= tolerance and 
                abs(elon - ref_elon) <= tolerance):
                logger.debug(f"Found approximate coordinate match: {coordinates} -> {region_name}")
                return region_name
        
        logger.warning(f"No region found for coordinates: {coordinates}")
        return "UNKNOWN"
        
    except Exception as e:
        logger.error(f"Error mapping coordinates to region: {e}")
        return "UNKNOWN"


def extract_variable_from_request(request_data: Dict) -> str:
    """
    Extract weather variable from request data.
    
    Args:
        request_data: Request data dictionary from RDA API
        
    Returns:
        Weather variable name or "unknown" if not found
    """
    try:
        # Extract from subset_info note
        subset_info = request_data.get('subset_info', {})
        if isinstance(subset_info, dict) and 'note' in subset_info:
            note = subset_info['note']
            variable = extract_variable_from_subset_note(note)
            if variable != "unknown":
                return variable
        
        # Fallback to other fields
        title = request_data.get('title', '').lower()
        description = request_data.get('description', '').lower()
        text_content = f"{title} {description}"
        
        # Variable detection patterns
        if any(term in text_content for term in ['solar', 'radiation', 'dswrf', 'shortwave']):
            return "dswrf"
        elif any(term in text_content for term in ['wind', 'ugrd', 'vgrd']):
            return "ugrd_vgrd"
        elif any(term in text_content for term in ['rain', 'precip', 'apcp']):
            return "apcp"
        elif any(term in text_content for term in ['temp', 'temperature', 'tmp']):
            return "tmp_dpt"
        
        return "unknown"
        
    except Exception as e:
        logger.error(f"Error extracting variable from request: {e}")
        return "unknown"


def extract_variable_from_subset_note(subset_note: str) -> str:
    """
    Extract weather variable from subset note.
    
    Args:
        subset_note: The subset note string
        
    Returns:
        Weather variable name or "unknown" if not found
    """
    if not subset_note:
        return "unknown"
    
    note_lower = subset_note.lower()
    
    # Enhanced variable detection patterns
    if any(term in note_lower for term in ['downward shortwave radiation flux', 'solar', 'radiation', 'dswrf', 'shortwave']):
        return "dswrf"
    elif any(term in note_lower for term in ['wind', 'ugrd', 'vgrd', 'u-component', 'v-component']):
        return "ugrd_vgrd"
    elif any(term in note_lower for term in ['total precipitation', 'rain', 'precip', 'apcp']):
        return "apcp"
    elif any(term in note_lower for term in ['temperature', 'temp', 'tmp']):
        return "tmp_dpt"
    else:
        return "unknown"


def create_download_directory_path(base_dir: str, region: str, variable: str) -> str:
    """
    Create standardized download directory path.
    
    Args:
        base_dir: Base download directory
        region: Region name
        variable: Weather variable name
        
    Returns:
        Full path to download directory
    """
    import os
    return os.path.join(base_dir, region, variable)


def validate_region_detection(request_data: Dict) -> Dict:
    """
    Validate region detection and provide detailed information.
    
    Args:
        request_data: Request data dictionary from RDA API
        
    Returns:
        Dictionary with validation results
    """
    try:
        request_id = request_data.get('request_index', 'UNKNOWN')
        
        # Extract region and variable
        region, variable = extract_region_and_variable_from_request(request_data)
        
        # Extract coordinate information
        rinfo = request_data.get('rinfo', '')
        coordinates = parse_coordinates_from_rinfo(rinfo) if rinfo else None
        
        # Extract subset info
        subset_info = request_data.get('subset_info', {})
        subset_note = subset_info.get('note', '') if isinstance(subset_info, dict) else ''
        
        return {
            'request_id': request_id,
            'region': region,
            'variable': variable,
            'coordinates': coordinates,
            'has_rinfo': bool(rinfo),
            'has_subset_note': bool(subset_note),
            'detection_successful': region != "UNKNOWN" and variable != "unknown",
            'rinfo_sample': rinfo[:100] + '...' if len(rinfo) > 100 else rinfo,
            'subset_note_sample': subset_note[:100] + '...' if len(subset_note) > 100 else subset_note
        }
        
    except Exception as e:
        return {
            'request_id': request_data.get('request_index', 'UNKNOWN'),
            'error': str(e),
            'detection_successful': False
        }