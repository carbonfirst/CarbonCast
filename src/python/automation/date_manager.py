#!/usr/bin/env python3
"""
Date Management Module for RDA Automation System

This module provides comprehensive date range parsing, validation, and control file
update capabilities with intuitive user input formats and robust error handling.

Key Features:
- Flexible date parsing (ISO, natural language, relative dates, etc.)
- Batch control file updates with rollback capability
- Comprehensive validation and error handling
- Backup and recovery mechanisms
- Integration with existing RDA automation workflow

Classes:
    DateManager: Main interface for date operations
    DateRange: Data class for date range representation
    FlexibleDateParser: Multi-strategy date parsing engine
    ControlFileUpdater: Batch file update with rollback
    BackupManager: File backup and recovery system

Usage Examples:
    # Basic usage
    date_manager = DateManager()
    date_range = date_manager.parse_date_range_string("2023-01-01 to 2023-12-31")
    result = date_manager.batch_modify_ctl_files(control_files, date_range)
    
    # With validation
    if date_manager.validate_date_range(date_range):
        result = date_manager.batch_modify_ctl_files(control_files, date_range)
"""

import os
import re
import json
import shutil
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import calendar


class DateFormat(Enum):
    """Enumeration of supported date input formats."""
    ISO_RANGE = "iso_range"              # "2023-01-01 to 2023-12-31"
    NATURAL_RANGE = "natural_range"      # "January 2023 to December 2023"
    YEAR_SHORTHAND = "year_shorthand"    # "2023"
    RELATIVE_DATES = "relative_dates"    # "last 30 days"
    QUARTER = "quarter"                  # "Q1 2023"
    MONTH = "month"                      # "2023-06"
    CTL_FORMAT = "ctl_format"           # "202301010000/to/202312310000"


class DateValidationError(Exception):
    """Raised when date parsing or validation fails."""
    pass


class FileUpdateError(Exception):
    """Raised when control file updates fail."""
    pass


class BackupError(Exception):
    """Raised when backup operations fail."""
    pass


class ValidationError(Exception):
    """Raised when post-update validation fails."""
    pass


@dataclass
class DateRange:
    """
    Data class representing a date range with metadata.
    
    Attributes:
        start_date: Start datetime
        end_date: End datetime
        original_input: Original user input string
        format_used: Format that was successfully parsed
        validation_warnings: List of validation warnings
    """
    start_date: datetime
    end_date: datetime
    original_input: str
    format_used: DateFormat
    validation_warnings: List[str] = None
    
    def __post_init__(self):
        if self.validation_warnings is None:
            self.validation_warnings = []
    
    def to_ctl_format(self) -> str:
        """Convert to CTL file format: YYYYMMDDHHMM/to/YYYYMMDDHHMM
        
        Both start and end dates always use 0000 for the time portion (HHMM)
        to strictly adhere to the CTL format requirements.
        """
        # Always use 0000 for time portion in CTL format
        start_str = self.start_date.strftime('%Y%m%d') + '0000'
        end_str = self.end_date.strftime('%Y%m%d') + '0000'
        return f"{start_str}/to/{end_str}"
    
    def to_readable_format(self) -> str:
        """Convert to human-readable format."""
        start_str = self.start_date.strftime('%Y-%m-%d')
        end_str = self.end_date.strftime('%Y-%m-%d')
        return f"{start_str} to {end_str}"
    
    def duration_days(self) -> int:
        """Get duration in days."""
        return (self.end_date - self.start_date).days
    
    def is_future_range(self) -> bool:
        """Check if range extends into the future."""
        return self.end_date > datetime.now()
    
    def is_valid_range(self) -> bool:
        """Basic validity check."""
        return self.start_date < self.end_date


@dataclass
class ValidationResult:
    """Result of date range validation."""
    is_valid: bool
    issues: List[str]
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class FileUpdateResult:
    """Result of updating a single control file."""
    file_path: str
    success: bool
    original_date: Optional[str] = None
    new_date: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class UpdateResult:
    """Result of batch control file updates."""
    success: bool
    files_updated: int
    total_files: int
    session_id: str
    error_message: Optional[str] = None
    file_results: List[FileUpdateResult] = None
    
    def __post_init__(self):
        if self.file_results is None:
            self.file_results = []


class FlexibleDateParser:
    """
    Multi-strategy date parsing engine that handles various input formats.
    
    Supports:
    - ISO date ranges: "2023-01-01 to 2023-12-31"
    - Natural language: "January 2023 to December 2023"
    - Year shorthand: "2023"
    - Relative dates: "last 30 days", "last 6 months"
    - Quarter notation: "Q1 2023", "Q4 2024"
    - Month notation: "2023-06", "June 2023"
    - CTL format: "202301010000/to/202312310000"
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.FlexibleDateParser')
        
        # Month name mappings
        self.month_names = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
            'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
            'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
            'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
    
    def parse(self, input_str: str) -> DateRange:
        """
        Parse date range from input string using multiple strategies.
        
        Args:
            input_str: User input string
            
        Returns:
            DateRange object
            
        Raises:
            DateValidationError: If parsing fails with all strategies
        """
        if not input_str or not input_str.strip():
            raise DateValidationError("Empty date input")
        
        input_str = input_str.strip()
        self.logger.debug(f"Parsing date input: '{input_str}'")
        
        # List of parsing strategies in order of preference
        strategies = [
            (self._parse_ctl_format, DateFormat.CTL_FORMAT),
            (self._parse_iso_range, DateFormat.ISO_RANGE),
            (self._parse_year_shorthand, DateFormat.YEAR_SHORTHAND),
            (self._parse_quarter, DateFormat.QUARTER),
            (self._parse_month, DateFormat.MONTH),
            (self._parse_relative_dates, DateFormat.RELATIVE_DATES),
            (self._parse_natural_range, DateFormat.NATURAL_RANGE),
        ]
        
        for strategy_func, date_format in strategies:
            try:
                start_date, end_date = strategy_func(input_str)
                
                date_range = DateRange(
                    start_date=start_date,
                    end_date=end_date,
                    original_input=input_str,
                    format_used=date_format
                )
                
                self.logger.info(f"Successfully parsed '{input_str}' using {date_format.value}")
                return date_range
                
            except (ValueError, AttributeError, KeyError) as e:
                self.logger.debug(f"Strategy {date_format.value} failed: {e}")
                continue
        
        # If all strategies fail, provide helpful error message
        raise DateValidationError(
            f"Unable to parse date input: '{input_str}'\n"
            f"Supported formats:\n"
            f"  • 2023-01-01 to 2023-12-31 (ISO range)\n"
            f"  • 2023 (full year)\n"
            f"  • Q1 2023 (quarter)\n"
            f"  • 2023-06 (month)\n"
            f"  • last 30 days (relative)\n"
            f"  • January 2023 to December 2023 (natural language)"
        )
    
    def _parse_ctl_format(self, input_str: str) -> Tuple[datetime, datetime]:
        """Parse CTL format: 202301010000/to/202312310000"""
        pattern = r'^(\d{12})/to/(\d{12})$'
        match = re.match(pattern, input_str)
        
        if not match:
            raise ValueError("Not CTL format")
        
        start_str, end_str = match.groups()
        
        start_date = datetime.strptime(start_str, '%Y%m%d%H%M')
        end_date = datetime.strptime(end_str, '%Y%m%d%H%M')
        
        return start_date, end_date
    
    def _parse_iso_range(self, input_str: str) -> Tuple[datetime, datetime]:
        """Parse ISO range: 2023-01-01 to 2023-12-31"""
        # Pattern for ISO date range with optional time
        pattern = r'^(\d{4}-\d{2}-\d{2})(?:\s+\d{2}:\d{2}(?::\d{2})?)?(?:\s+to\s+|\s*-\s*)(\d{4}-\d{2}-\d{2})(?:\s+\d{2}:\d{2}(?::\d{2})?)?$'
        match = re.match(pattern, input_str, re.IGNORECASE)
        
        if not match:
            raise ValueError("Not ISO range format")
        
        start_date_str, end_date_str = match.groups()
        
        # Parse dates (default to 00:00 time)
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Set end date to end of day (23:59)
        end_date = end_date.replace(hour=23, minute=59)
        
        return start_date, end_date
    
    def _parse_year_shorthand(self, input_str: str) -> Tuple[datetime, datetime]:
        """Parse year shorthand: 2023"""
        pattern = r'^(\d{4})$'
        match = re.match(pattern, input_str)
        
        if not match:
            raise ValueError("Not year shorthand format")
        
        year = int(match.group(1))
        
        # Validate year range
        if year < 1900 or year > 2100:
            raise ValueError(f"Year {year} is outside valid range (1900-2100)")
        
        start_date = datetime(year, 1, 1, 0, 0)
        end_date = datetime(year, 12, 31, 23, 59)
        
        return start_date, end_date
    
    def _parse_quarter(self, input_str: str) -> Tuple[datetime, datetime]:
        """Parse quarter: Q1 2023, Q4 2024"""
        pattern = r'^Q([1-4])\s+(\d{4})$'
        match = re.match(pattern, input_str, re.IGNORECASE)
        
        if not match:
            raise ValueError("Not quarter format")
        
        quarter = int(match.group(1))
        year = int(match.group(2))
        
        # Validate year
        if year < 1900 or year > 2100:
            raise ValueError(f"Year {year} is outside valid range")
        
        # Calculate quarter start and end months
        quarter_months = {
            1: (1, 3),   # Q1: Jan-Mar
            2: (4, 6),   # Q2: Apr-Jun
            3: (7, 9),   # Q3: Jul-Sep
            4: (10, 12)  # Q4: Oct-Dec
        }
        
        start_month, end_month = quarter_months[quarter]
        
        start_date = datetime(year, start_month, 1, 0, 0)
        
        # Get last day of end month
        last_day = calendar.monthrange(year, end_month)[1]
        end_date = datetime(year, end_month, last_day, 23, 59)
        
        return start_date, end_date
    
    def _parse_month(self, input_str: str) -> Tuple[datetime, datetime]:
        """Parse month: 2023-06, June 2023"""
        # Try YYYY-MM format first
        pattern1 = r'^(\d{4})-(\d{1,2})$'
        match1 = re.match(pattern1, input_str)
        
        if match1:
            year = int(match1.group(1))
            month = int(match1.group(2))
        else:
            # Try "Month YYYY" format
            pattern2 = r'^([a-zA-Z]+)\s+(\d{4})$'
            match2 = re.match(pattern2, input_str, re.IGNORECASE)
            
            if not match2:
                raise ValueError("Not month format")
            
            month_name = match2.group(1).lower()
            year = int(match2.group(2))
            
            if month_name not in self.month_names:
                raise ValueError(f"Unknown month name: {month_name}")
            
            month = self.month_names[month_name]
        
        # Validate inputs
        if year < 1900 or year > 2100:
            raise ValueError(f"Year {year} is outside valid range")
        
        if month < 1 or month > 12:
            raise ValueError(f"Month {month} is outside valid range (1-12)")
        
        start_date = datetime(year, month, 1, 0, 0)
        
        # Get last day of month
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59)
        
        return start_date, end_date
    
    def _parse_relative_dates(self, input_str: str) -> Tuple[datetime, datetime]:
        """Parse relative dates: last 30 days, last 6 months, etc."""
        now = datetime.now()
        
        # Pattern for "last X days/weeks/months/years"
        pattern = r'^last\s+(\d+)\s+(days?|weeks?|months?|years?)$'
        match = re.match(pattern, input_str, re.IGNORECASE)
        
        if not match:
            raise ValueError("Not relative date format")
        
        amount = int(match.group(1))
        unit = match.group(2).lower().rstrip('s')  # Remove plural 's'
        
        # Calculate start date based on unit
        if unit == 'day':
            start_date = now - timedelta(days=amount)
        elif unit == 'week':
            start_date = now - timedelta(weeks=amount)
        elif unit == 'month':
            # Approximate months as 30 days
            start_date = now - timedelta(days=amount * 30)
        elif unit == 'year':
            # Approximate years as 365 days
            start_date = now - timedelta(days=amount * 365)
        else:
            raise ValueError(f"Unknown time unit: {unit}")
        
        # Set to beginning of start day and end of current day
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=0)
        
        return start_date, end_date
    
    def _parse_natural_range(self, input_str: str) -> Tuple[datetime, datetime]:
        """Parse natural language: January 2023 to December 2023"""
        # Pattern for "Month YYYY to Month YYYY"
        pattern = r'^([a-zA-Z]+)\s+(\d{4})\s+to\s+([a-zA-Z]+)\s+(\d{4})$'
        match = re.match(pattern, input_str, re.IGNORECASE)
        
        if not match:
            raise ValueError("Not natural range format")
        
        start_month_name = match.group(1).lower()
        start_year = int(match.group(2))
        end_month_name = match.group(3).lower()
        end_year = int(match.group(4))
        
        # Validate month names
        if start_month_name not in self.month_names:
            raise ValueError(f"Unknown start month: {start_month_name}")
        
        if end_month_name not in self.month_names:
            raise ValueError(f"Unknown end month: {end_month_name}")
        
        start_month = self.month_names[start_month_name]
        end_month = self.month_names[end_month_name]
        
        # Validate years
        if start_year < 1900 or start_year > 2100:
            raise ValueError(f"Start year {start_year} is outside valid range")
        
        if end_year < 1900 or end_year > 2100:
            raise ValueError(f"End year {end_year} is outside valid range")
        
        start_date = datetime(start_year, start_month, 1, 0, 0)
        
        # Get last day of end month
        last_day = calendar.monthrange(end_year, end_month)[1]
        end_date = datetime(end_year, end_month, last_day, 23, 59)
        
        return start_date, end_date


class DateRangeValidator:
    """Validates date ranges with configurable rules."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.logger = logging.getLogger(__name__ + '.DateRangeValidator')
        
        # Default configuration
        self.config = {
            'max_range_years': 5,
            'min_range_days': 1,
            'allow_future_dates': True,
            'warn_future_dates': True,
            'earliest_allowed_year': 1900,
            'latest_allowed_year': 2100,
            'warn_large_ranges': True,
            'large_range_threshold_days': 1095  # 3 years
        }
        
        if config:
            self.config.update(config)
    
    def validate_date_range(self, date_range: DateRange) -> ValidationResult:
        """
        Comprehensive date range validation.
        
        Args:
            date_range: DateRange to validate
            
        Returns:
            ValidationResult with validation status and issues
        """
        issues = []
        warnings = []
        
        try:
            # 1. Basic date validation
            if not date_range.is_valid_range():
                issues.append("Start date must be before end date")
            
            # 2. Range duration validation
            duration_days = date_range.duration_days()
            
            if duration_days < self.config['min_range_days']:
                issues.append(f"Date range must be at least {self.config['min_range_days']} day(s)")
            
            max_days = self.config['max_range_years'] * 365
            if duration_days > max_days:
                issues.append(f"Date range exceeds maximum of {self.config['max_range_years']} years")
            
            # 3. Large range warning
            if (self.config['warn_large_ranges'] and 
                duration_days > self.config['large_range_threshold_days']):
                warnings.append(f"Large date range ({duration_days} days) may impact performance")
            
            # 4. Future date validation
            if date_range.is_future_range():
                if not self.config['allow_future_dates']:
                    issues.append("Future dates are not allowed")
                elif self.config['warn_future_dates']:
                    warnings.append("Date range extends into the future")
            
            # 5. Year range validation
            start_year = date_range.start_date.year
            end_year = date_range.end_date.year
            
            if start_year < self.config['earliest_allowed_year']:
                issues.append(f"Start year {start_year} is before earliest allowed year {self.config['earliest_allowed_year']}")
            
            if end_year > self.config['latest_allowed_year']:
                issues.append(f"End year {end_year} is after latest allowed year {self.config['latest_allowed_year']}")
            
            # 6. Data availability warnings (RDA-specific)
            if start_year < 2000:
                warnings.append("Data availability may be limited before year 2000")
            
            if end_year > datetime.now().year + 1:
                warnings.append("Forecast data may not be available for distant future dates")
            
        except Exception as e:
            issues.append(f"Validation error: {str(e)}")
            self.logger.error(f"Error during validation: {e}")
        
        is_valid = len(issues) == 0
        
        if is_valid:
            self.logger.info(f"Date range validation passed: {date_range.to_readable_format()}")
        else:
            self.logger.warning(f"Date range validation failed: {issues}")
        
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            warnings=warnings
        )


class BackupManager:
    """Manages file backups and rollback operations."""
    
    def __init__(self, backup_dir: Optional[str] = None):
        self.logger = logging.getLogger(__name__ + '.BackupManager')
        
        # Default backup directory
        if backup_dir is None:
            backup_dir = os.path.join(tempfile.gettempdir(), 'rda_date_manager_backups')
        
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"BackupManager initialized with backup directory: {self.backup_dir}")
    
    def create_session(self) -> str:
        """Create a new backup session."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session_id = f"session_{timestamp}"
        
        session_dir = self.backup_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Created backup session: {session_id}")
        return session_id
    
    def backup_files(self, file_paths: List[str], session_id: str) -> Dict[str, str]:
        """
        Backup files for a session.
        
        Args:
            file_paths: List of file paths to backup
            session_id: Session identifier
            
        Returns:
            Dictionary mapping original paths to backup paths
        """
        session_dir = self.backup_dir / session_id
        if not session_dir.exists():
            raise BackupError(f"Session directory not found: {session_id}")
        
        backup_mapping = {}
        
        for file_path in file_paths:
            try:
                original_path = Path(file_path)
                if not original_path.exists():
                    self.logger.warning(f"File not found for backup: {file_path}")
                    continue
                
                # Create backup filename with original path structure
                backup_name = original_path.name + '.backup'
                backup_path = session_dir / backup_name
                
                # Copy file to backup location
                shutil.copy2(original_path, backup_path)
                backup_mapping[file_path] = str(backup_path)
                
                self.logger.debug(f"Backed up {file_path} to {backup_path}")
                
            except Exception as e:
                self.logger.error(f"Failed to backup {file_path}: {e}")
                raise BackupError(f"Backup failed for {file_path}: {e}")
        
        # Save backup mapping
        mapping_file = session_dir / 'backup_mapping.json'
        with open(mapping_file, 'w') as f:
            json.dump(backup_mapping, f, indent=2)
        
        self.logger.info(f"Backed up {len(backup_mapping)} files for session {session_id}")
        return backup_mapping
    
    def rollback_session(self, session_id: str) -> bool:
        """
        Rollback all changes for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if rollback successful, False otherwise
        """
        try:
            session_dir = self.backup_dir / session_id
            if not session_dir.exists():
                raise BackupError(f"Session directory not found: {session_id}")
            
            # Load backup mapping
            mapping_file = session_dir / 'backup_mapping.json'
            if not mapping_file.exists():
                raise BackupError(f"Backup mapping not found for session: {session_id}")
            
            with open(mapping_file, 'r') as f:
                backup_mapping = json.load(f)
            
            # Restore each file
            restored_count = 0
            for original_path, backup_path in backup_mapping.items():
                try:
                    if Path(backup_path).exists():
                        shutil.copy2(backup_path, original_path)
                        restored_count += 1
                        self.logger.debug(f"Restored {original_path} from {backup_path}")
                    else:
                        self.logger.warning(f"Backup file not found: {backup_path}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to restore {original_path}: {e}")
                    # Continue with other files
            
            self.logger.info(f"Rollback completed for session {session_id}: {restored_count} files restored")
            return restored_count > 0
            
        except Exception as e:
            self.logger.error(f"Rollback failed for session {session_id}: {e}")
            return False
    
    def commit_session(self, session_id: str) -> bool:
        """
        Commit session (cleanup backup files).
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if commit successful, False otherwise
        """
        try:
            session_dir = self.backup_dir / session_id
            if session_dir.exists():
                shutil.rmtree(session_dir)
                self.logger.info(f"Committed session {session_id} (cleaned up backups)")
                return True
            else:
                self.logger.warning(f"Session directory not found for commit: {session_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to commit session {session_id}: {e}")
            return False
    
    def cleanup_old_sessions(self, max_age_days: int = 7) -> int:
        """
        Clean up old backup sessions.
        
        Args:
            max_age_days: Maximum age of sessions to keep
            
        Returns:
            Number of sessions cleaned up
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            cleaned_count = 0
            
            for session_dir in self.backup_dir.iterdir():
                if session_dir.is_dir() and session_dir.name.startswith('session_'):
                    try:
                        # Extract timestamp from session name
                        timestamp_str = session_dir.name.replace('session_', '')
                        session_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        
                        if session_time < cutoff_time:
                            shutil.rmtree(session_dir)
                            cleaned_count += 1
                            self.logger.debug(f"Cleaned up old session: {session_dir.name}")
                            
                    except (ValueError, OSError) as e:
                        self.logger.warning(f"Failed to process session directory {session_dir}: {e}")
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} old backup sessions")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old sessions: {e}")
            return 0


class ControlFileUpdater:
    """Handles batch updates of control files with rollback capability."""
    
    def __init__(self, backup_manager: Optional[BackupManager] = None):
        self.logger = logging.getLogger(__name__ + '.ControlFileUpdater')
        self.backup_manager = backup_manager or BackupManager()
    
    def batch_update_dates(self, file_paths: List[str], date_range: DateRange) -> UpdateResult:
        """
        Update date fields in multiple control files with rollback capability.
        
        Args:
            file_paths: List of control file paths
            date_range: New date range to apply
            
        Returns:
            UpdateResult with operation details
        """
        session_id = self.backup_manager.create_session()
        file_results = []
        
        try:
            self.logger.info(f"Starting batch update of {len(file_paths)} files")
            
            # 1. Validate all files exist and are readable
            valid_files = []
            for file_path in file_paths:
                if not Path(file_path).exists():
                    self.logger.warning(f"File not found: {file_path}")
                    file_results.append(FileUpdateResult(
                        file_path=file_path,
                        success=False,
                        error_message="File not found"
                    ))
                    continue
                
                if not os.access(file_path, os.R_OK | os.W_OK):
                    self.logger.warning(f"File not accessible: {file_path}")
                    file_results.append(FileUpdateResult(
                        file_path=file_path,
                        success=False,
                        error_message="File not accessible"
                    ))
                    continue
                
                valid_files.append(file_path)
            
            if not valid_files:
                return UpdateResult(
                    success=False,
                    files_updated=0,
                    total_files=len(file_paths),
                    session_id=session_id,
                    error_message="No valid files found to update",
                    file_results=file_results
                )
            
            # 2. Create backups
            self.logger.info(f"Creating backups for {len(valid_files)} files")
            backup_mapping = self.backup_manager.backup_files(valid_files, session_id)
            
            # 3. Update files
            new_date_str = date_range.to_ctl_format()
            success_count = 0
            
            for file_path in valid_files:
                try:
                    result = self._update_single_file(file_path, date_range)
                    file_results.append(result)
                    
                    if result.success:
                        success_count += 1
                        self.logger.debug(f"Successfully updated {file_path}")
                    else:
                        self.logger.error(f"Failed to update {file_path}: {result.error_message}")
                        # Rollback on any failure
                        self.backup_manager.rollback_session(session_id)
                        raise FileUpdateError(f"Failed to update {file_path}: {result.error_message}")
                        
                except Exception as e:
                    self.logger.error(f"Error updating {file_path}: {e}")
                    file_results.append(FileUpdateResult(
                        file_path=file_path,
                        success=False,
                        error_message=str(e)
                    ))
                    # Rollback on any failure
                    self.backup_manager.rollback_session(session_id)
                    raise FileUpdateError(f"Update failed for {file_path}: {e}")
            
            # 4. Validate all updates
            self.logger.info("Validating all file updates")
            if self._validate_all_updates(valid_files, date_range):
                # Commit changes (cleanup backups)
                self.backup_manager.commit_session(session_id)
                
                self.logger.info(f"Batch update completed successfully: {success_count}/{len(file_paths)} files updated")
                return UpdateResult(
                    success=True,
                    files_updated=success_count,
                    total_files=len(file_paths),
                    session_id=session_id,
                    file_results=file_results
                )
            else:
                # Validation failed, rollback
                self.backup_manager.rollback_session(session_id)
                raise ValidationError("Post-update validation failed")
                
        except Exception as e:
            self.logger.error(f"Batch update failed: {e}")
            # Ensure rollback on any error
            try:
                self.backup_manager.rollback_session(session_id)
            except Exception as rollback_error:
                self.logger.error(f"Rollback also failed: {rollback_error}")
            
            return UpdateResult(
                success=False,
                files_updated=0,
                total_files=len(file_paths),
                session_id=session_id,
                error_message=str(e),
                file_results=file_results
            )
    
    def _update_single_file(self, file_path: str, date_range: DateRange) -> FileUpdateResult:
        """
        Update date field in a single control file.
        
        Args:
            file_path: Path to control file
            date_range: New date range
            
        Returns:
            FileUpdateResult with operation details
        """
        try:
            # Read current content
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Find and update date line
            updated_lines = []
            date_updated = False
            original_date = None
            
            for line in lines:
                if line.startswith('date='):
                    # Extract original date for logging
                    original_date = line.strip().split('=', 1)[1] if '=' in line else None
                    
                    # Create new date line
                    new_line = f"date={date_range.to_ctl_format()}\n"
                    updated_lines.append(new_line)
                    date_updated = True
                    
                    self.logger.debug(f"Updated date in {file_path}: {original_date} -> {date_range.to_ctl_format()}")
                else:
                    updated_lines.append(line)
            
            if not date_updated:
                return FileUpdateResult(
                    file_path=file_path,
                    success=False,
                    error_message="No date field found in control file"
                )
            
            # Write updated content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)
            
            return FileUpdateResult(
                file_path=file_path,
                success=True,
                original_date=original_date,
                new_date=date_range.to_ctl_format()
            )
            
        except Exception as e:
            return FileUpdateResult(
                file_path=file_path,
                success=False,
                error_message=str(e)
            )
    
    def _validate_all_updates(self, file_paths: List[str], expected_date_range: DateRange) -> bool:
        """
        Validate that all files were updated correctly.
        
        Args:
            file_paths: List of file paths to validate
            expected_date_range: Expected date range
            
        Returns:
            True if all files have correct date, False otherwise
        """
        expected_date_str = expected_date_range.to_ctl_format()
        
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check if file contains expected date
                if f"date={expected_date_str}" not in content:
                    self.logger.error(f"Validation failed for {file_path}: expected date not found")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Validation error for {file_path}: {e}")
                return False
        
        return True


class DateManager:
    """
    Main interface for date management operations in RDA automation system.
    
    Provides high-level methods for parsing date ranges, validating them,
    and updating control files with comprehensive error handling and rollback.
    """
    
    def __init__(self, temp_dir: Optional[str] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize DateManager.
        
        Args:
            temp_dir: Optional temporary directory for backups
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__ + '.DateManager')
        
        # Initialize components
        self.parser = FlexibleDateParser()
        self.validator = DateRangeValidator()
        self.backup_manager = BackupManager(temp_dir)
        self.file_updater = ControlFileUpdater(self.backup_manager)
        
        self.logger.info("DateManager initialized")
    
    def parse_date_range_string(self, input_str: str) -> DateRange:
        """
        Parse date range from user input string.
        
        Args:
            input_str: User input string
            
        Returns:
            DateRange object
            
        Raises:
            DateValidationError: If parsing fails
        """
        return self.parser.parse(input_str)
    
    def parse_date_range(self, start_date: str, end_date: str) -> DateRange:
        """
        Parse date range from separate start and end date strings.
        
        Args:
            start_date: Start date string
            end_date: End date string
            
        Returns:
            DateRange object
            
        Raises:
            DateValidationError: If parsing fails
        """
        combined_input = f"{start_date} to {end_date}"
        return self.parse_date_range_string(combined_input)
    
    def validate_date_range(self, date_range: DateRange) -> bool:
        """
        Validate a date range.
        
        Args:
            date_range: DateRange to validate
            
        Returns:
            True if valid, False otherwise
        """
        result = self.validator.validate_date_range(date_range)
        
        # Add warnings to date range object
        if result.warnings:
            date_range.validation_warnings.extend(result.warnings)
        
        return result.is_valid
    
    def get_validation_result(self, date_range: DateRange) -> ValidationResult:
        """
        Get detailed validation result for a date range.
        
        Args:
            date_range: DateRange to validate
            
        Returns:
            ValidationResult with detailed information
        """
        return self.validator.validate_date_range(date_range)
    
    def batch_modify_ctl_files(self, file_paths: List[str], date_range: DateRange,
                              session_id: Optional[str] = None) -> UpdateResult:
        """
        Update date fields in multiple control files.
        
        Args:
            file_paths: List of control file paths
            date_range: New date range to apply
            session_id: Optional session ID for tracking
            
        Returns:
            UpdateResult with operation details
        """
        return self.file_updater.batch_update_dates(file_paths, date_range)
    
    def modify_ctl_file_dates(self, file_path: str, date_range: DateRange,
                             output_path: Optional[str] = None,
                             session_id: Optional[str] = None) -> str:
        """
        Update date field in a single control file.
        
        Args:
            file_path: Path to control file
            date_range: New date range
            output_path: Optional output path (if None, modifies in place)
            session_id: Optional session ID for tracking
            
        Returns:
            Path to modified file
            
        Raises:
            FileUpdateError: If update fails
        """
        if output_path and output_path != file_path:
            # Copy to output path first
            shutil.copy2(file_path, output_path)
            target_path = output_path
        else:
            target_path = file_path
        
        result = self.file_updater._update_single_file(target_path, date_range)
        
        if not result.success:
            raise FileUpdateError(f"Failed to update {file_path}: {result.error_message}")
        
        return target_path
    
    def extract_date_from_ctl(self, file_path: str) -> Optional[str]:
        """
        Extract current date range from a control file.
        
        Args:
            file_path: Path to control file
            
        Returns:
            Current date string or None if not found
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('date='):
                        return line.strip().split('=', 1)[1]
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting date from {file_path}: {e}")
            return None
    
    def get_date_suggestions(self) -> Dict[str, str]:
        """
        Get common date range suggestions.
        
        Returns:
            Dictionary of suggestion names to date strings
        """
        current_year = datetime.now().year
        
        return {
            'current_year': str(current_year),
            'last_year': str(current_year - 1),
            'last_6_months': 'last 6 months',
            'last_30_days': 'last 30 days',
            'q1_current': f'Q1 {current_year}',
            'q2_current': f'Q2 {current_year}',
            'q3_current': f'Q3 {current_year}',
            'q4_current': f'Q4 {current_year}',
            'q4_last': f'Q4 {current_year - 1}',
            'jan_current': f'January {current_year}',
            'dec_last': f'December {current_year - 1}'
        }
    
    def cleanup_temp_files(self) -> int:
        """
        Clean up old temporary files and backup sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        return self.backup_manager.cleanup_old_sessions()
    
    def save_modifications_log(self, log_file: str) -> bool:
        """
        Save modifications log to file.
        
        Args:
            log_file: Path to log file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # This would be implemented to save detailed modification logs
            # For now, just create a placeholder
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'manager_info': 'DateManager modifications log',
                'note': 'Detailed logging implementation pending'
            }
            
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save modifications log: {e}")
            return False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        try:
            self.cleanup_temp_files()
        except Exception as e:
            self.logger.warning(f"Cleanup during exit failed: {e}")


# Utility functions for backward compatibility with existing date_utils.py

def parse_date_input(date_str: str) -> datetime:
    """
    Parse a single date input string.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        Parsed datetime object
        
    Raises:
        DateValidationError: If parsing fails
    """
    # Try to parse as a single date first
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        pass
    
    # Try common single date formats
    formats = [
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y%m%d',
        '%Y%m%d%H%M',
        '%Y%m%d%H%M%S'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    raise DateValidationError(f"Unable to parse date: {date_str}")


# Factory function for easy instantiation
def create_date_manager(temp_dir: Optional[str] = None,
                       config: Optional[Dict[str, Any]] = None) -> DateManager:
    """
    Factory function to create a DateManager instance.
    
    Args:
        temp_dir: Optional temporary directory for backups
        config: Optional configuration dictionary
        
    Returns:
        Configured DateManager instance
    """
    logger = logging.getLogger('rda_automation.date_manager')
    return DateManager(temp_dir=temp_dir, logger=logger)


if __name__ == '__main__':
    # Simple command-line interface for testing
    import sys
    from logger_utils import configure_root_logging
    
    if len(sys.argv) < 2:
        print("Usage: python date_manager.py <date_range_string>")
        print("Example: python date_manager.py '2023-01-01 to 2023-12-31'")
        sys.exit(1)
    
    # Setup logging
    configure_root_logging(level=logging.INFO)
    
    try:
        date_manager = create_date_manager()
        date_range = date_manager.parse_date_range_string(sys.argv[1])
        
        print(f"Parsed date range: {date_range.to_readable_format()}")
        print(f"CTL format: {date_range.to_ctl_format()}")
        print(f"Format used: {date_range.format_used.value}")
        print(f"Duration: {date_range.duration_days()} days")
        
        # Validate
        validation = date_manager.get_validation_result(date_range)
        if validation.is_valid:
            print("✅ Date range is valid")
        else:
            print("❌ Date range validation failed:")
            for issue in validation.issues:
                print(f"  - {issue}")
        
        if validation.warnings:
            print("⚠️  Warnings:")
            for warning in validation.warnings:
                print(f"  - {warning}")
                
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)