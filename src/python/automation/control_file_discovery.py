#!/usr/bin/env python3
"""
Control File Discovery Utility for Sequential File Processing

This module provides dynamic discovery and ordering of control files for the
sequential file processing system. It discovers control files from the control_files
folder and provides intelligent ordering and filtering capabilities.

Key Features:
- Dynamic discovery of control files from the control_files directory
- Alphabetical ordering for sequential processing
- Region and variable type extraction from filenames
- File validation and metadata extraction
- Integration with existing automation database schema
- Support for filtering and prioritization
"""

import os
import sys
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import re

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class ControlFileInfo:
    """Information about a discovered control file."""
    file_path: str
    filename: str
    region: str
    variable_type: str
    full_name: str
    file_size: int
    last_modified: str
    is_valid: bool
    validation_errors: List[str]
    processing_priority: int = 1
    estimated_processing_time: float = 0.0


@dataclass
class DiscoveryResult:
    """Result of control file discovery operation."""
    total_files_found: int
    valid_files: int
    invalid_files: int
    files: List[ControlFileInfo]
    discovery_time: str
    errors: List[str]
    regions_discovered: List[str]
    variable_types_discovered: List[str]


class ControlFileDiscovery:
    """
    Dynamic control file discovery utility for sequential processing.
    
    This class provides comprehensive control file discovery capabilities,
    including validation, metadata extraction, and intelligent ordering
    for sequential processing workflows.
    """
    
    def __init__(self, control_files_dir: str = "src/python/control_files",
                 db_path: str = "src/python/data/automation_state.db"):
        """
        Initialize the Control File Discovery utility.
        
        Args:
            control_files_dir: Directory containing control files
            db_path: Path to the SQLite database file
        """
        self.control_files_dir = Path(control_files_dir)
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Ensure control files directory exists
        if not self.control_files_dir.exists():
            self.logger.warning(f"Control files directory does not exist: {self.control_files_dir}")
        
        # File naming patterns for validation
        self.filename_pattern = re.compile(r'^([A-Z0-9]+)_([a-z]+)_control\.ctl$')
        
        # Variable type mappings for standardization
        self.variable_type_mappings = {
            'dswrf': 'solar_radiation',
            'ugrd_vgrd': 'wind_speed',
            'apcp': 'precipitation',
            'tmp_dpt': 'temperature'
        }
        
        # Priority mappings for different variable types
        self.variable_priorities = {
            'dswrf': 1,      # Solar radiation - highest priority
            'ugrd_vgrd': 2,  # Wind speed
            'tmp_dpt': 3,    # Temperature
            'apcp': 4        # Precipitation
        }
        
        self.logger.info("Control File Discovery initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the control file discovery."""
        logger = logging.getLogger('rda_automation.control_file_discovery')
        
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
    
    def _parse_filename(self, filename: str) -> Tuple[Optional[str], Optional[str], bool, List[str]]:
        """
        Parse control file filename to extract region and variable type.
        
        Args:
            filename: Control file filename
            
        Returns:
            Tuple of (region, variable_type, is_valid, validation_errors)
        """
        validation_errors = []
        
        # Check if filename matches expected pattern
        match = self.filename_pattern.match(filename)
        if not match:
            validation_errors.append(f"Filename does not match expected pattern: {filename}")
            return None, None, False, validation_errors
        
        region = match.group(1)
        variable_type = match.group(2)
        
        # Validate region (should be uppercase letters/numbers)
        if not re.match(r'^[A-Z0-9]+$', region):
            validation_errors.append(f"Invalid region format: {region}")
        
        # Validate variable type (should be lowercase letters)
        if not re.match(r'^[a-z]+$', variable_type):
            validation_errors.append(f"Invalid variable type format: {variable_type}")
        
        # Check if variable type is recognized
        known_variables = ['dswrf', 'ugrd_vgrd', 'apcp', 'tmp_dpt']
        if variable_type not in known_variables:
            validation_errors.append(f"Unknown variable type: {variable_type}")
        
        is_valid = len(validation_errors) == 0
        return region, variable_type, is_valid, validation_errors
    
    def _validate_control_file(self, file_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate a control file for basic requirements.
        
        Args:
            file_path: Path to the control file
            
        Returns:
            Tuple of (is_valid, validation_errors)
        """
        validation_errors = []
        
        try:
            # Check if file exists and is readable
            if not file_path.exists():
                validation_errors.append("File does not exist")
                return False, validation_errors
            
            if not file_path.is_file():
                validation_errors.append("Path is not a file")
                return False, validation_errors
            
            # Check file size (should not be empty, but also not too large)
            file_size = file_path.stat().st_size
            if file_size == 0:
                validation_errors.append("File is empty")
            elif file_size > 10 * 1024 * 1024:  # 10MB limit
                validation_errors.append(f"File is too large: {file_size} bytes")
            
            # Check file extension
            if file_path.suffix.lower() != '.ctl':
                validation_errors.append(f"Invalid file extension: {file_path.suffix}")
            
            # Try to read the file to ensure it's accessible
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Read first few lines to check basic format
                    first_lines = []
                    for i, line in enumerate(f):
                        if i >= 10:  # Only check first 10 lines
                            break
                        first_lines.append(line.strip())
                    
                    # Basic content validation (control files should have some content)
                    if len(first_lines) == 0:
                        validation_errors.append("File appears to be empty")
                    
            except UnicodeDecodeError:
                validation_errors.append("File contains invalid UTF-8 characters")
            except PermissionError:
                validation_errors.append("Permission denied reading file")
            except Exception as e:
                validation_errors.append(f"Error reading file: {str(e)}")
        
        except Exception as e:
            validation_errors.append(f"Error validating file: {str(e)}")
        
        is_valid = len(validation_errors) == 0
        return is_valid, validation_errors
    
    def _calculate_processing_priority(self, region: str, variable_type: str) -> int:
        """
        Calculate processing priority for a control file.
        
        Args:
            region: Region code
            variable_type: Variable type
            
        Returns:
            Priority score (lower numbers = higher priority)
        """
        # Base priority from variable type
        base_priority = self.variable_priorities.get(variable_type, 5)
        
        # Adjust priority based on region (some regions might be more important)
        region_adjustments = {
            'ERCOT': -1,    # Texas - high priority
            'CISO': -1,     # California - high priority
            'PJM': -1,      # Eastern US - high priority
            'MISO': -1,     # Midwest - high priority
            'ISNE': 0,      # New England - normal priority
            'NYISO': 0,     # New York - normal priority
        }
        
        priority_adjustment = region_adjustments.get(region, 0)
        final_priority = max(1, base_priority + priority_adjustment)
        
        return final_priority
    
    def _estimate_processing_time(self, region: str, variable_type: str, file_size: int) -> float:
        """
        Estimate processing time for a control file.
        
        Args:
            region: Region code
            variable_type: Variable type
            file_size: File size in bytes
            
        Returns:
            Estimated processing time in hours
        """
        # Base processing time estimates (in hours)
        base_times = {
            'dswrf': 2.0,    # Solar radiation data
            'ugrd_vgrd': 1.5, # Wind data
            'tmp_dpt': 1.0,  # Temperature data
            'apcp': 1.8      # Precipitation data
        }
        
        base_time = base_times.get(variable_type, 2.0)
        
        # Adjust based on file size (larger files take longer)
        size_factor = max(0.5, min(2.0, file_size / (1024 * 1024)))  # Scale by MB
        
        # Regional complexity factors
        region_factors = {
            'ERCOT': 1.2,    # Texas - more complex
            'CISO': 1.3,     # California - most complex
            'PJM': 1.1,      # Eastern US - slightly complex
            'MISO': 1.0,     # Midwest - normal
        }
        
        region_factor = region_factors.get(region, 1.0)
        
        estimated_time = base_time * size_factor * region_factor
        return round(estimated_time, 2)
    
    def discover_control_files(self, include_invalid: bool = False) -> DiscoveryResult:
        """
        Discover all control files in the control files directory.
        
        Args:
            include_invalid: Whether to include invalid files in results
            
        Returns:
            DiscoveryResult with discovered files and metadata
        """
        discovery_start = datetime.now()
        self.logger.info(f"Starting control file discovery in: {self.control_files_dir}")
        
        files = []
        errors = []
        regions_discovered = set()
        variable_types_discovered = set()
        
        try:
            if not self.control_files_dir.exists():
                error_msg = f"Control files directory does not exist: {self.control_files_dir}"
                self.logger.error(error_msg)
                errors.append(error_msg)
                
                return DiscoveryResult(
                    total_files_found=0,
                    valid_files=0,
                    invalid_files=0,
                    files=[],
                    discovery_time=discovery_start.isoformat(),
                    errors=errors,
                    regions_discovered=[],
                    variable_types_discovered=[]
                )
            
            # Discover all .ctl files
            control_files = list(self.control_files_dir.glob("*.ctl"))
            self.logger.info(f"Found {len(control_files)} potential control files")
            
            for file_path in control_files:
                try:
                    # Parse filename
                    region, variable_type, filename_valid, filename_errors = self._parse_filename(file_path.name)
                    
                    # Validate file
                    file_valid, file_errors = self._validate_control_file(file_path)
                    
                    # Combine validation results
                    is_valid = filename_valid and file_valid
                    validation_errors = filename_errors + file_errors
                    
                    # Get file metadata
                    file_stat = file_path.stat()
                    file_size = file_stat.st_size
                    last_modified = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    
                    # Calculate priority and estimated time
                    priority = 1
                    estimated_time = 0.0
                    if region and variable_type:
                        priority = self._calculate_processing_priority(region, variable_type)
                        estimated_time = self._estimate_processing_time(region, variable_type, file_size)
                        
                        # Track discovered regions and variables
                        regions_discovered.add(region)
                        variable_types_discovered.add(variable_type)
                    
                    # Create control file info
                    file_info = ControlFileInfo(
                        file_path=str(file_path),
                        filename=file_path.name,
                        region=region or "UNKNOWN",
                        variable_type=variable_type or "unknown",
                        full_name=f"{region}_{variable_type}" if region and variable_type else file_path.stem,
                        file_size=file_size,
                        last_modified=last_modified,
                        is_valid=is_valid,
                        validation_errors=validation_errors,
                        processing_priority=priority,
                        estimated_processing_time=estimated_time
                    )
                    
                    # Add to results if valid or if including invalid files
                    if is_valid or include_invalid:
                        files.append(file_info)
                    
                    if not is_valid:
                        self.logger.warning(f"Invalid control file: {file_path.name} - {validation_errors}")
                
                except Exception as e:
                    error_msg = f"Error processing file {file_path.name}: {str(e)}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
            
            # Sort files for sequential processing (alphabetical by filename)
            files.sort(key=lambda f: f.filename.lower())
            
            # Calculate statistics
            valid_files = len([f for f in files if f.is_valid])
            invalid_files = len([f for f in files if not f.is_valid])
            
            discovery_time = datetime.now()
            duration = (discovery_time - discovery_start).total_seconds()
            
            self.logger.info(f"Control file discovery completed in {duration:.2f}s: "
                           f"{valid_files} valid, {invalid_files} invalid files")
            
            return DiscoveryResult(
                total_files_found=len(files),
                valid_files=valid_files,
                invalid_files=invalid_files,
                files=files,
                discovery_time=discovery_time.isoformat(),
                errors=errors,
                regions_discovered=sorted(list(regions_discovered)),
                variable_types_discovered=sorted(list(variable_types_discovered))
            )
        
        except Exception as e:
            error_msg = f"Error during control file discovery: {str(e)}"
            self.logger.error(error_msg)
            errors.append(error_msg)
            
            return DiscoveryResult(
                total_files_found=0,
                valid_files=0,
                invalid_files=0,
                files=[],
                discovery_time=datetime.now().isoformat(),
                errors=errors,
                regions_discovered=[],
                variable_types_discovered=[]
            )
    
    def get_files_by_region(self, region: str, include_invalid: bool = False) -> List[ControlFileInfo]:
        """
        Get all control files for a specific region.
        
        Args:
            region: Region code to filter by
            include_invalid: Whether to include invalid files
            
        Returns:
            List of ControlFileInfo objects for the region
        """
        discovery_result = self.discover_control_files(include_invalid=include_invalid)
        
        region_files = [
            file_info for file_info in discovery_result.files
            if file_info.region.upper() == region.upper()
        ]
        
        self.logger.info(f"Found {len(region_files)} control files for region: {region}")
        return region_files
    
    def get_files_by_variable_type(self, variable_type: str, include_invalid: bool = False) -> List[ControlFileInfo]:
        """
        Get all control files for a specific variable type.
        
        Args:
            variable_type: Variable type to filter by
            include_invalid: Whether to include invalid files
            
        Returns:
            List of ControlFileInfo objects for the variable type
        """
        discovery_result = self.discover_control_files(include_invalid=include_invalid)
        
        variable_files = [
            file_info for file_info in discovery_result.files
            if file_info.variable_type.lower() == variable_type.lower()
        ]
        
        self.logger.info(f"Found {len(variable_files)} control files for variable type: {variable_type}")
        return variable_files
    
    def get_processing_order(self, prioritize_by: str = "alphabetical") -> List[ControlFileInfo]:
        """
        Get control files in processing order.
        
        Args:
            prioritize_by: Ordering method ("alphabetical", "priority", "region", "variable")
            
        Returns:
            List of ControlFileInfo objects in processing order
        """
        discovery_result = self.discover_control_files(include_invalid=False)
        valid_files = [f for f in discovery_result.files if f.is_valid]
        
        if prioritize_by == "alphabetical":
            # Default alphabetical ordering (already sorted in discover_control_files)
            ordered_files = valid_files
        elif prioritize_by == "priority":
            # Sort by processing priority, then alphabetically
            ordered_files = sorted(valid_files, key=lambda f: (f.processing_priority, f.filename.lower()))
        elif prioritize_by == "region":
            # Sort by region, then variable type, then alphabetically
            ordered_files = sorted(valid_files, key=lambda f: (f.region, f.variable_type, f.filename.lower()))
        elif prioritize_by == "variable":
            # Sort by variable type, then region, then alphabetically
            ordered_files = sorted(valid_files, key=lambda f: (f.variable_type, f.region, f.filename.lower()))
        else:
            self.logger.warning(f"Unknown prioritization method: {prioritize_by}, using alphabetical")
            ordered_files = valid_files
        
        self.logger.info(f"Generated processing order with {len(ordered_files)} files using method: {prioritize_by}")
        return ordered_files
    
    def get_discovery_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive discovery statistics.
        
        Returns:
            Dictionary with discovery statistics and metadata
        """
        try:
            discovery_result = self.discover_control_files(include_invalid=True)
            
            # Calculate additional statistics
            total_estimated_time = sum(f.estimated_processing_time for f in discovery_result.files if f.is_valid)
            
            # Group by region and variable type
            region_counts = {}
            variable_counts = {}
            
            for file_info in discovery_result.files:
                if file_info.is_valid:
                    region_counts[file_info.region] = region_counts.get(file_info.region, 0) + 1
                    variable_counts[file_info.variable_type] = variable_counts.get(file_info.variable_type, 0) + 1
            
            return {
                'discovery_summary': {
                    'total_files_found': discovery_result.total_files_found,
                    'valid_files': discovery_result.valid_files,
                    'invalid_files': discovery_result.invalid_files,
                    'discovery_time': discovery_result.discovery_time,
                    'total_estimated_processing_time_hours': total_estimated_time
                },
                'region_distribution': region_counts,
                'variable_type_distribution': variable_counts,
                'regions_discovered': discovery_result.regions_discovered,
                'variable_types_discovered': discovery_result.variable_types_discovered,
                'validation_errors': discovery_result.errors,
                'control_files_directory': str(self.control_files_dir),
                'directory_exists': self.control_files_dir.exists(),
                'generated_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error getting discovery statistics: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def update_database_tracking(self, discovery_result: DiscoveryResult) -> bool:
        """
        Update database with discovered control files for tracking.
        
        Args:
            discovery_result: Result from control file discovery
            
        Returns:
            True if database update was successful, False otherwise
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Create or update control_files_tracking table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS control_files_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT UNIQUE NOT NULL,
                        file_path TEXT NOT NULL,
                        region TEXT NOT NULL,
                        variable_type TEXT NOT NULL,
                        file_size INTEGER,
                        last_modified TEXT,
                        processing_priority INTEGER DEFAULT 1,
                        estimated_processing_time REAL DEFAULT 0.0,
                        is_valid BOOLEAN DEFAULT TRUE,
                        validation_errors TEXT,
                        processing_status TEXT DEFAULT 'pending',
                        request_index TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert or update control file records
                for file_info in discovery_result.files:
                    if file_info.is_valid:  # Only track valid files
                        cursor.execute("""
                            INSERT OR REPLACE INTO control_files_tracking 
                            (filename, file_path, region, variable_type, file_size, last_modified,
                             processing_priority, estimated_processing_time, is_valid, validation_errors,
                             updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            file_info.filename,
                            file_info.file_path,
                            file_info.region,
                            file_info.variable_type,
                            file_info.file_size,
                            file_info.last_modified,
                            file_info.processing_priority,
                            file_info.estimated_processing_time,
                            file_info.is_valid,
                            '; '.join(file_info.validation_errors) if file_info.validation_errors else None,
                            datetime.now().isoformat()
                        ))
                
                conn.commit()
                self.logger.info(f"Updated database tracking for {discovery_result.valid_files} control files")
                return True
        
        except Exception as e:
            self.logger.error(f"Error updating database tracking: {e}")
            return False


def create_control_file_discovery(control_files_dir: str = "src/python/control_files",
                                 db_path: str = "src/python/data/automation_state.db") -> ControlFileDiscovery:
    """
    Factory function to create a Control File Discovery utility.
    
    Args:
        control_files_dir: Directory containing control files
        db_path: Path to the SQLite database file
        
    Returns:
        Configured ControlFileDiscovery instance
    """
    return ControlFileDiscovery(control_files_dir, db_path)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Control File Discovery Utility')
    parser.add_argument('--discover', action='store_true',
                       help='Discover all control files')
    parser.add_argument('--region', type=str,
                       help='Filter by specific region')
    parser.add_argument('--variable', type=str,
                       help='Filter by specific variable type')
    parser.add_argument('--order', choices=['alphabetical', 'priority', 'region', 'variable'],
                       default='alphabetical', help='Processing order method')
    parser.add_argument('--stats', action='store_true',
                       help='Show discovery statistics')
    parser.add_argument('--include-invalid', action='store_true',
                       help='Include invalid files in results')
    parser.add_argument('--update-db', action='store_true',
                       help='Update database with discovered files')
    parser.add_argument('--control-files-dir', default='src/python/control_files',
                       help='Control files directory')
    
    args = parser.parse_args()
    
    # Create discovery utility
    discovery = create_control_file_discovery(args.control_files_dir)
    
    try:
        if args.discover:
            print("=== Control File Discovery ===")
            result = discovery.discover_control_files(include_invalid=args.include_invalid)
            
            print(f"Total files found: {result.total_files_found}")
            print(f"Valid files: {result.valid_files}")
            print(f"Invalid files: {result.invalid_files}")
            print(f"Regions: {', '.join(result.regions_discovered)}")
            print(f"Variable types: {', '.join(result.variable_types_discovered)}")
            
            if result.errors:
                print(f"Errors: {len(result.errors)}")
                for error in result.errors:
                    print(f"  - {error}")
            
            print("\nDiscovered files:")
            for file_info in result.files:
                status = "✅" if file_info.is_valid else "❌"
                print(f"  {status} {file_info.filename} ({file_info.region}_{file_info.variable_type}) "
                      f"- Priority: {file_info.processing_priority}, "
                      f"Est. time: {file_info.estimated_processing_time}h")
                
                if file_info.validation_errors:
                    for error in file_info.validation_errors:
                        print(f"    ⚠️ {error}")
            
            if args.update_db:
                print("\n=== Updating Database ===")
                success = discovery.update_database_tracking(result)
                print(f"Database update: {'✅ Success' if success else '❌ Failed'}")
        
        elif args.region:
            print(f"=== Files for Region: {args.region} ===")
            files = discovery.get_files_by_region(args.region, args.include_invalid)
            
            for file_info in files:
                status = "✅" if file_info.is_valid else "❌"
                print(f"  {status} {file_info.filename} ({file_info.variable_type}) "
                      f"- Priority: {file_info.processing_priority}")
        
        elif args.variable:
            print(f"=== Files for Variable Type: {args.variable} ===")
            files = discovery.get_files_by_variable_type(args.variable, args.include_invalid)
            
            for file_info in files:
                status = "✅" if file_info.is_valid else "❌"
                print(f"  {status} {file_info.filename} ({file_info.region}) "
                      f"- Priority: {file_info.processing_priority}")
        
        elif args.stats:
            print("=== Discovery Statistics ===")
            stats = discovery.get_discovery_statistics()
            print(json.dumps(stats, indent=2))
        
        else:
            print(f"=== Processing Order ({args.order}) ===")
            files = discovery.get_processing_order(args.order)
            
            total_time = sum(f.estimated_processing_time for f in files)
            print(f"Total files: {len(files)}")
            print(f"Estimated total processing time: {total_time:.1f} hours")
            print()
            
            for i, file_info in enumerate(files, 1):
                print(f"{i:3d}. {file_info.filename} ({file_info.region}_{file_info.variable_type}) "
                      f"- Priority: {file_info.processing_priority}, "
                      f"Est. time: {file_info.estimated_processing_time}h")
    
    except Exception as e:
        print(f"Error: {e}")