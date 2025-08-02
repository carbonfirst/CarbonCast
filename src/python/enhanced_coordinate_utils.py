#!/usr/bin/env python3
"""
Enhanced Coordinate Utilities for RDA Automation System

This module provides enhanced coordinate utilities that use the robust region mapper
for improved region detection with fuzzy matching and precision handling.
"""

import logging
from typing import Dict, Tuple, Optional
from robust_region_mapper import create_robust_region_mapper, RobustRegionMapper

logger = logging.getLogger(__name__)


class EnhancedCoordinateUtils:
    """Enhanced coordinate utilities using robust region mapper."""
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db"):
        """Initialize enhanced coordinate utilities."""
        self.robust_mapper = create_robust_region_mapper(db_path)
        self.logger = logger
    
    def get_region_and_variable_from_request_enhanced(self, request: Dict) -> Tuple[str, str]:
        """
        Enhanced function to extract region and weather variable from request metadata.
        Uses the robust region mapper for improved accuracy.
        
        Args:
            request: Request dictionary
            
        Returns:
            Tuple of (region_name, variable_name)
        """
        try:
            # Use robust region mapper for detection
            detection_result = self.robust_mapper.robust_region_detection(request)
            
            region = detection_result.region
            variable = detection_result.variable
            
            self.logger.info(f"Enhanced detection result: region='{region}', variable='{variable}' "
                           f"(confidence: {detection_result.confidence:.2f}, "
                           f"method: {detection_result.detection_method})")
            
            return region, variable
            
        except Exception as e:
            self.logger.error(f"Error in enhanced region/variable extraction: {e}")
            return "UNKNOWN", "unknown"
    
    def extract_coordinates_from_rinfo(self, rinfo: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Extract coordinates from the rinfo field using robust parsing.
        
        Args:
            rinfo: The rinfo string containing coordinate information
            
        Returns:
            Tuple of (nlat, slat, wlon, elon) or None if not found
        """
        return self.robust_mapper.parse_coordinates_from_rinfo(rinfo)
    
    def map_coordinates_to_region(self, coordinates: Tuple[float, float, float, float]) -> Optional[str]:
        """
        Map coordinates to a region name using robust fuzzy matching.
        
        Args:
            coordinates: Tuple of (nlat, slat, wlon, elon)
            
        Returns:
            Region name or None if not found
        """
        try:
            coordinate_match = self.robust_mapper.find_matching_region_fuzzy(coordinates)
            if coordinate_match:
                self.logger.info(f"Robust coordinate match: {coordinates} -> {coordinate_match.region} "
                               f"({coordinate_match.match_type}, confidence: {coordinate_match.confidence:.2f})")
                return coordinate_match.region
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in robust coordinate mapping: {e}")
            return None
    
    def validate_region_detection(self, request: Dict, 
                                expected_region: Optional[str] = None,
                                expected_variable: Optional[str] = None) -> Dict:
        """
        Validate region detection accuracy.
        
        Args:
            request: Request dictionary
            expected_region: Expected region name
            expected_variable: Expected variable name
            
        Returns:
            Validation results dictionary
        """
        return self.robust_mapper.validate_detection_accuracy(
            request, expected_region, expected_variable
        )


# Global instance for backward compatibility
_enhanced_utils = None

def get_enhanced_coordinate_utils(db_path: str = "src/python/data/automation_state.db") -> EnhancedCoordinateUtils:
    """Get or create enhanced coordinate utilities instance."""
    global _enhanced_utils
    if _enhanced_utils is None:
        _enhanced_utils = EnhancedCoordinateUtils(db_path)
    return _enhanced_utils


def get_region_and_variable_from_request_enhanced(request: Dict) -> Tuple[str, str]:
    """
    Enhanced function to extract region and weather variable from request metadata.
    This function maintains backward compatibility while using the robust region mapper.
    
    Args:
        request: Request dictionary
        
    Returns:
        Tuple of (region_name, variable_name)
    """
    utils = get_enhanced_coordinate_utils()
    return utils.get_region_and_variable_from_request_enhanced(request)


def extract_coordinates_from_rinfo(rinfo: str) -> Optional[Tuple[float, float, float, float]]:
    """
    Extract coordinates from the rinfo field using robust parsing.
    Maintains backward compatibility.
    
    Args:
        rinfo: The rinfo string containing coordinate information
        
    Returns:
        Tuple of (nlat, slat, wlon, elon) or None if not found
    """
    utils = get_enhanced_coordinate_utils()
    return utils.extract_coordinates_from_rinfo(rinfo)


def map_coordinates_to_region(coordinates: Tuple[float, float, float, float]) -> Optional[str]:
    """
    Map coordinates to a region name using robust fuzzy matching.
    Maintains backward compatibility.
    
    Args:
        coordinates: Tuple of (nlat, slat, wlon, elon)
        
    Returns:
        Region name or None if not found
    """
    utils = get_enhanced_coordinate_utils()
    return utils.map_coordinates_to_region(coordinates)


if __name__ == "__main__":
    # Example usage and testing
    import json
    
    # Test coordinate extraction and mapping
    test_rinfo = "nlat=42.0;slat=32.0;wlon=-124.75;elon=-113.5"
    coordinates = extract_coordinates_from_rinfo(test_rinfo)
    
    if coordinates:
        print(f"Extracted coordinates: {coordinates}")
        region = map_coordinates_to_region(coordinates)
        print(f"Mapped to region: {region}")
    
    # Test request processing
    test_request = {
        'request_index': 'TEST_001',
        'rinfo': test_rinfo,
        'subset_info': {'note': 'Downward shortwave radiation flux'},
        'title': 'Solar radiation data',
        'description': 'Test request for solar data'
    }
    
    region, variable = get_region_and_variable_from_request_enhanced(test_request)
    print(f"Request detection result: region='{region}', variable='{variable}'")
    
    # Test validation
    utils = get_enhanced_coordinate_utils()
    validation = utils.validate_region_detection(test_request, "CISO", "dswrf")
    print(f"Validation result: {json.dumps(validation, indent=2)}")