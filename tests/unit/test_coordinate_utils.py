#!/usr/bin/env python3
"""
Unit tests for coordinate utilities module.

This module tests the coordinate utility functions used throughout
the RDA automation system for handling geographic coordinates.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add src/python to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python'))

try:
    from coordinate_utils import (
        parse_coordinates, validate_coordinate_range, 
        format_coordinate_string, calculate_coordinate_bounds
    )
    COORDINATE_UTILS_AVAILABLE = True
except ImportError:
    COORDINATE_UTILS_AVAILABLE = False


@unittest.skipUnless(COORDINATE_UTILS_AVAILABLE, "coordinate_utils module not available")
class TestCoordinateUtils(unittest.TestCase):
    """Unit tests for coordinate utility functions."""
    
    def test_parse_coordinates_valid_input(self):
        """Test parsing valid coordinate strings."""
        # Test latitude/longitude parsing
        test_cases = [
            ("40.7128,-74.0060", (40.7128, -74.0060)),
            ("0.0,0.0", (0.0, 0.0)),
            ("90.0,180.0", (90.0, 180.0)),
            ("-90.0,-180.0", (-90.0, -180.0))
        ]
        
        for coord_string, expected in test_cases:
            with self.subTest(coord_string=coord_string):
                result = parse_coordinates(coord_string)
                self.assertEqual(result, expected)
    
    def test_parse_coordinates_invalid_input(self):
        """Test parsing invalid coordinate strings."""
        invalid_inputs = [
            "invalid",
            "40.7128",  # Missing longitude
            "40.7128,-74.0060,extra",  # Too many values
            "abc,def",  # Non-numeric values
            ""  # Empty string
        ]
        
        for invalid_input in invalid_inputs:
            with self.subTest(invalid_input=invalid_input):
                with self.assertRaises((ValueError, IndexError)):
                    parse_coordinates(invalid_input)
    
    def test_validate_coordinate_range(self):
        """Test coordinate range validation."""
        # Valid coordinates
        valid_coords = [
            (0.0, 0.0),
            (90.0, 180.0),
            (-90.0, -180.0),
            (45.0, -120.0)
        ]
        
        for lat, lon in valid_coords:
            with self.subTest(lat=lat, lon=lon):
                self.assertTrue(validate_coordinate_range(lat, lon))
        
        # Invalid coordinates
        invalid_coords = [
            (91.0, 0.0),    # Latitude too high
            (-91.0, 0.0),   # Latitude too low
            (0.0, 181.0),   # Longitude too high
            (0.0, -181.0),  # Longitude too low
        ]
        
        for lat, lon in invalid_coords:
            with self.subTest(lat=lat, lon=lon):
                self.assertFalse(validate_coordinate_range(lat, lon))
    
    def test_format_coordinate_string(self):
        """Test coordinate string formatting."""
        test_cases = [
            ((40.7128, -74.0060), "40.7128,-74.0060"),
            ((0.0, 0.0), "0.0,0.0"),
            ((90.0, 180.0), "90.0,180.0"),
            ((-90.0, -180.0), "-90.0,-180.0")
        ]
        
        for coords, expected in test_cases:
            with self.subTest(coords=coords):
                result = format_coordinate_string(*coords)
                self.assertEqual(result, expected)
    
    def test_calculate_coordinate_bounds(self):
        """Test coordinate bounds calculation."""
        # Test with a list of coordinates
        coordinates = [
            (40.0, -74.0),
            (41.0, -73.0),
            (39.0, -75.0)
        ]
        
        bounds = calculate_coordinate_bounds(coordinates)
        
        self.assertEqual(bounds['min_lat'], 39.0)
        self.assertEqual(bounds['max_lat'], 41.0)
        self.assertEqual(bounds['min_lon'], -75.0)
        self.assertEqual(bounds['max_lon'], -73.0)
    
    def test_calculate_coordinate_bounds_single_point(self):
        """Test coordinate bounds calculation with single point."""
        coordinates = [(40.0, -74.0)]
        
        bounds = calculate_coordinate_bounds(coordinates)
        
        self.assertEqual(bounds['min_lat'], 40.0)
        self.assertEqual(bounds['max_lat'], 40.0)
        self.assertEqual(bounds['min_lon'], -74.0)
        self.assertEqual(bounds['max_lon'], -74.0)
    
    def test_calculate_coordinate_bounds_empty_list(self):
        """Test coordinate bounds calculation with empty list."""
        with self.assertRaises(ValueError):
            calculate_coordinate_bounds([])


class TestCoordinateUtilsMocked(unittest.TestCase):
    """Unit tests for coordinate utilities with mocked dependencies."""
    
    @patch('coordinate_utils.validate_coordinate_range')
    def test_parse_coordinates_with_validation(self, mock_validate):
        """Test coordinate parsing with mocked validation."""
        mock_validate.return_value = True
        
        # This test demonstrates how to use mocks in unit tests
        # even when the actual module might not be available
        if COORDINATE_UTILS_AVAILABLE:
            result = parse_coordinates("40.7128,-74.0060")
            self.assertEqual(result, (40.7128, -74.0060))
            mock_validate.assert_called_once_with(40.7128, -74.0060)
        else:
            self.skipTest("coordinate_utils module not available")


if __name__ == '__main__':
    unittest.main()