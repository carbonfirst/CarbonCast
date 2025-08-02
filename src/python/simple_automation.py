#!/usr/bin/env python3
"""
Simple Automation System with Enhanced Coordinate-Based Detection

This module provides automated processing of RDA requests with enhanced
region and weather variable detection using coordinate-based mapping.
"""

import os
import sys
import json
import logging
import argparse
from typing import Dict, Tuple, List, Optional
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coordinate_utils import get_region_and_variable_from_request_enhanced

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedAutomationSystem:
    """Enhanced automation system with coordinate-based detection."""
    
    def __init__(self, base_download_dir: str = "downloaded_files"):
        """
        Initialize the automation system.
        
        Args:
            base_download_dir: Base directory for downloaded files
        """
        self.base_download_dir = Path(base_download_dir)
        self.base_download_dir.mkdir(exist_ok=True)
        logger.info(f"Initialized automation system with base directory: {self.base_download_dir}")
    
    def get_region_and_variable_from_request(self, request: Dict) -> Tuple[str, str]:
        """
        Extract region and weather variable from request using enhanced detection.
        
        Args:
            request: Request dictionary containing metadata
            
        Returns:
            Tuple of (region_name, weather_variable_type)
        """
        return get_region_and_variable_from_request_enhanced(request)
    
    def create_download_directory(self, region: str, weather_variable: str) -> Path:
        """
        Create directory structure following REGION_NAME/weather_variable_type pattern.
        
        Args:
            region: Region name (e.g., "CISO", "WACM")
            weather_variable: Weather variable type (e.g., "dswrf", "temp")
            
        Returns:
            Path to the created directory
        """
        # Ensure proper formatting
        region = region.upper()
        weather_variable = weather_variable.lower()
        
        # Create directory path
        directory_path = self.base_download_dir / region / weather_variable
        directory_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created/verified directory: {directory_path}")
        return directory_path
    
    def process_request(self, request: Dict) -> Dict:
        """
        Process a single request and determine download directory.
        
        Args:
            request: Request dictionary
            
        Returns:
            Dictionary with processing results
        """
        try:
            request_id = request.get('request_index', 'UNKNOWN_ID')
            logger.info(f"Processing request: {request_id}")
            
            # Extract region and variable using enhanced detection
            region, weather_variable = self.get_region_and_variable_from_request(request)
            
            # Create directory structure
            download_dir = self.create_download_directory(region, weather_variable)
            
            result = {
                'request_id': request_id,
                'region': region,
                'weather_variable': weather_variable,
                'download_directory': str(download_dir),
                'status': 'success'
            }
            
            logger.info(f"Request {request_id} processed successfully: {region}/{weather_variable}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing request {request.get('request_index', 'UNKNOWN')}: {e}")
            return {
                'request_id': request.get('request_index', 'UNKNOWN'),
                'region': 'UNKNOWN',
                'weather_variable': 'unknown',
                'download_directory': str(self.base_download_dir / 'UNKNOWN' / 'unknown'),
                'status': 'error',
                'error': str(e)
            }
    
    def process_requests_batch(self, requests: List[Dict]) -> List[Dict]:
        """
        Process a batch of requests.
        
        Args:
            requests: List of request dictionaries
            
        Returns:
            List of processing results
        """
        results = []
        logger.info(f"Processing batch of {len(requests)} requests")
        
        for request in requests:
            result = self.process_request(request)
            results.append(result)
        
        # Log summary
        successful = sum(1 for r in results if r['status'] == 'success')
        failed = len(results) - successful
        logger.info(f"Batch processing complete: {successful} successful, {failed} failed")
        
        return results
    
    def validate_directory_structure(self) -> Dict:
        """
        Validate that directory structure follows REGION_NAME/weather_variable_type pattern.
        
        Returns:
            Validation results dictionary
        """
        validation_results = {
            'valid_directories': [],
            'invalid_directories': [],
            'unknown_directories': [],
            'total_directories': 0,
            'compliance_rate': 0.0
        }
        
        try:
            if not self.base_download_dir.exists():
                logger.warning(f"Base download directory does not exist: {self.base_download_dir}")
                return validation_results
            
            for region_dir in self.base_download_dir.iterdir():
                if not region_dir.is_dir():
                    continue
                
                region_name = region_dir.name
                
                for var_dir in region_dir.iterdir():
                    if not var_dir.is_dir():
                        continue
                    
                    var_name = var_dir.name
                    dir_path = f"{region_name}/{var_name}"
                    validation_results['total_directories'] += 1
                    
                    # Check if follows proper pattern
                    if region_name == "UNKNOWN" and var_name == "unknown":
                        validation_results['unknown_directories'].append(dir_path)
                    elif region_name.isupper() and var_name.islower() and var_name.isalpha():
                        validation_results['valid_directories'].append(dir_path)
                    else:
                        validation_results['invalid_directories'].append(dir_path)
            
            # Calculate compliance rate
            total = validation_results['total_directories']
            valid = len(validation_results['valid_directories'])
            if total > 0:
                validation_results['compliance_rate'] = (valid / total) * 100
            
            logger.info(f"Directory structure validation complete: {valid}/{total} directories compliant ({validation_results['compliance_rate']:.1f}%)")
            
        except Exception as e:
            logger.error(f"Error validating directory structure: {e}")
        
        return validation_results


def create_sample_requests() -> List[Dict]:
    """Create sample requests for testing."""
    return [
        {
            'request_index': 'WACM_DSWRF_001',
            'rinfo': 'nlat=48.0;slat=35.5;wlon=-114.5;elon=-95.75',
            'subset_info': {
                'note': 'Parameter(s):\nDownward shortwave radiation flux'
            },
            'title': 'WACM Solar Data Request',
            'description': 'Solar radiation data for WACM region'
        },
        {
            'request_index': 'AZPS_TEMP_001',
            'rinfo': 'nlat=36.75;slat=30.75;wlon=-115.25;elon=-108.75',
            'subset_info': {
                'note': 'Parameter(s):\nTemperature'
            },
            'title': 'AZPS Temperature Data Request',
            'description': 'Temperature data for AZPS region'
        },
        {
            'request_index': 'CISO_WIND_001',
            'rinfo': 'nlat=42;slat=32;wlon=-124.75;elon=-113.5',
            'subset_info': {
                'note': 'Parameter(s):\nu-component of wind'
            },
            'title': 'CISO Wind Data Request',
            'description': 'Wind component data for CISO region'
        },
        {
            'request_index': 'ERCOT_RAIN_001',
            'rinfo': 'nlat=36.5;slat=25.25;wlon=-104.5;elon=-93.25',
            'subset_info': {
                'note': 'Parameter(s):\nTotal precipitation'
            },
            'title': 'ERCOT Precipitation Data Request',
            'description': 'Precipitation data for ERCOT region'
        },
        {
            'request_index': 'PATTERN_FALLBACK_001',
            'rinfo': 'invalid_coordinates',
            'subset_info': {
                'note': 'Latitudes (top/bottom): 42 / 32\nLongitudes (left/right): -124 / -113\nParameter(s):\nTemperature'
            },
            'title': 'Pattern Matching Test',
            'description': 'Test pattern matching fallback'
        },
        {
            'request_index': 'TEXT_FALLBACK_001',
            'rinfo': 'invalid_coordinates',
            'subset_info': {
                'note': 'No coordinate patterns here'
            },
            'title': 'PJM Temperature Data Request',
            'description': 'Temperature data for analysis'
        }
    ]


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Enhanced RDA Automation System')
    parser.add_argument('--mode', choices=['test', 'automated'], default='test',
                       help='Operation mode')
    parser.add_argument('--download-dir', default='downloaded_files',
                       help='Base download directory')
    parser.add_argument('--requests-file', help='JSON file containing requests')
    parser.add_argument('--validate', action='store_true',
                       help='Validate directory structure')
    
    args = parser.parse_args()
    
    # Initialize automation system
    automation = EnhancedAutomationSystem(args.download_dir)
    
    if args.validate:
        # Validate directory structure
        print("\n" + "=" * 60)
        print("DIRECTORY STRUCTURE VALIDATION")
        print("=" * 60)
        
        validation = automation.validate_directory_structure()
        
        print(f"Total directories: {validation['total_directories']}")
        print(f"Valid directories: {len(validation['valid_directories'])}")
        print(f"Invalid directories: {len(validation['invalid_directories'])}")
        print(f"Unknown directories: {len(validation['unknown_directories'])}")
        print(f"Compliance rate: {validation['compliance_rate']:.1f}%")
        
        if validation['valid_directories']:
            print("\nValid directories:")
            for dir_path in validation['valid_directories']:
                print(f"  ✓ {dir_path}")
        
        if validation['invalid_directories']:
            print("\nInvalid directories:")
            for dir_path in validation['invalid_directories']:
                print(f"  ✗ {dir_path}")
        
        if validation['unknown_directories']:
            print("\nUnknown directories:")
            for dir_path in validation['unknown_directories']:
                print(f"  ? {dir_path}")
        
        return
    
    if args.mode == 'test':
        # Test mode with sample requests
        print("\n" + "=" * 60)
        print("ENHANCED AUTOMATION SYSTEM - TEST MODE")
        print("=" * 60)
        
        sample_requests = create_sample_requests()
        results = automation.process_requests_batch(sample_requests)
        
        print(f"\nProcessed {len(results)} requests:")
        print("-" * 60)
        
        for result in results:
            status_icon = "✓" if result['status'] == 'success' else "✗"
            print(f"{status_icon} {result['request_id']}")
            print(f"   Region: {result['region']}")
            print(f"   Variable: {result['weather_variable']}")
            print(f"   Directory: {result['download_directory']}")
            if result['status'] == 'error':
                print(f"   Error: {result['error']}")
            print()
        
        # Validate directory structure
        print("=" * 60)
        print("DIRECTORY STRUCTURE VALIDATION")
        print("=" * 60)
        
        validation = automation.validate_directory_structure()
        print(f"Compliance rate: {validation['compliance_rate']:.1f}%")
        print(f"Valid directories: {len(validation['valid_directories'])}")
        print(f"Unknown directories: {len(validation['unknown_directories'])}")
        
    elif args.mode == 'automated':
        # Automated mode with requests file
        if not args.requests_file:
            print("Error: --requests-file required for automated mode")
            sys.exit(1)
        
        try:
            with open(args.requests_file, 'r') as f:
                requests = json.load(f)
            
            results = automation.process_requests_batch(requests)
            
            # Save results
            output_file = f"automation_results_{len(results)}_requests.json"
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            print(f"Processed {len(results)} requests. Results saved to {output_file}")
            
        except Exception as e:
            print(f"Error in automated mode: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()