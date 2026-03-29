#!/usr/bin/env python3
"""
Unified Database Setup Script for CarbonCast RDA Automation System

This script provides a comprehensive database configuration solution that:
- Consolidates all database initialization into one place
- Creates both basic and enhanced schema tables
- Handles database migration from old to new schema
- Standardizes the database location to src/python/data/automation_state.db
- Includes proper error handling and logging
- Provides backward compatibility with existing data

Key Features:
- Unified database setup with both basic and enhanced schemas
- Safe migration with backup creation
- Comprehensive error handling and logging
- Schema validation and health checks
- Standardized database path configuration
- Support for multiple database locations during migration
"""

import os
import sys
import sqlite3
import logging
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import threading

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logger_utils import get_logger

# Import existing modules
try:
    from automation.enhanced_database_schema import EnhancedDatabaseSchema
    from automation.configuration_manager import ConfigurationManager
except ImportError as e:
    print(f"Warning: Could not import automation modules: {e}")
    EnhancedDatabaseSchema = None
    ConfigurationManager = None


class UnifiedDatabaseSetup:
    """
    Unified database setup manager for the CarbonCast RDA automation system.
    
    This class provides comprehensive database configuration including:
    - Standardized database location management
    - Basic and enhanced schema creation
    - Safe migration with backup
    - Schema validation and health checks
    - Configuration integration
    """
    
    # Standardized database path
    STANDARD_DB_PATH = "src/python/data/automation_state.db"
    
    # Legacy database paths to check during migration
    LEGACY_DB_PATHS = [
        "data/automation_state.db",
        "src/python/automation/data/automation_state.db",
        "automation_state.db"
    ]
    
    def __init__(self, db_path: Optional[str] = None, enable_enhanced_schema: bool = True):
        """
        Initialize the unified database setup manager.
        
        Args:
            db_path: Custom database path (uses standard path if None)
            enable_enhanced_schema: Whether to create enhanced schema tables
        """
        self.db_path = db_path or self.STANDARD_DB_PATH
        self.enable_enhanced_schema = enable_enhanced_schema
        self.logger = self._setup_logging()
        self.setup_lock = threading.Lock()
        
        # Ensure database directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize enhanced schema manager if available
        self.enhanced_schema = None
        if enable_enhanced_schema and EnhancedDatabaseSchema:
            self.enhanced_schema = EnhancedDatabaseSchema(self.db_path)
        
        self.logger.info(f"Unified Database Setup initialized for: {self.db_path}")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('unified_database_setup', level=logging.DEBUG)
    
    def _get_db_connection(self, db_path: Optional[str] = None) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        path = db_path or self.db_path
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _create_backup(self, source_path: str, backup_suffix: str = "setup_backup") -> Optional[str]:
        """
        Create a backup of the database before setup.
        
        Args:
            source_path: Path to the source database
            backup_suffix: Suffix for the backup file
            
        Returns:
            Path to the backup file or None if failed
        """
        try:
            if not os.path.exists(source_path):
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{source_path}.{backup_suffix}_{timestamp}"
            shutil.copy2(source_path, backup_path)
            
            self.logger.info(f"✅ Backup created: {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"❌ Error creating backup for {source_path}: {e}")
            return None
    
    def _create_basic_tables(self, conn: sqlite3.Connection) -> bool:
        """
        Create basic database tables for the RDA automation system.
        
        Args:
            conn: Database connection
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = conn.cursor()
            
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")
            
            self.logger.info("Creating basic database tables...")
            
            # RDA requests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rda_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT UNIQUE NOT NULL,
                    control_file_path TEXT NOT NULL,
                    region TEXT,
                    variable_type TEXT,
                    status TEXT DEFAULT 'submitted',
                    submission_time TEXT,
                    completion_time TEXT,
                    download_time TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    download_directory TEXT,
                    file_size INTEGER,
                    processing_duration REAL,
                    request_index INTEGER,
                    dsid TEXT,
                    date_rqst TEXT,
                    date_ready TEXT,
                    date_purge TEXT,
                    location TEXT,
                    ncar_contact TEXT,
                    rinfo TEXT,
                    subset_note TEXT,
                    raw_response TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Control files tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS control_files_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    region TEXT NOT NULL,
                    variable_type TEXT NOT NULL,
                    discovered_at TEXT NOT NULL,
                    file_size INTEGER,
                    last_modified TEXT,
                    status TEXT DEFAULT 'discovered',
                    request_id TEXT,
                    request_index INTEGER,
                    submission_time TEXT,
                    completion_time TEXT,
                    download_time TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    processing_duration REAL,
                    download_directory TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Regional progress table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS regional_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    region TEXT UNIQUE NOT NULL,
                    region_name TEXT,
                    total_control_files INTEGER DEFAULT 0,
                    discovered_files INTEGER DEFAULT 0,
                    queued_files INTEGER DEFAULT 0,
                    submitted_files INTEGER DEFAULT 0,
                    processing_files INTEGER DEFAULT 0,
                    completed_files INTEGER DEFAULT 0,
                    failed_files INTEGER DEFAULT 0,
                    downloaded_files INTEGER DEFAULT 0,
                    missing_files INTEGER DEFAULT 0,
                    variable_breakdown TEXT,
                    first_discovered TEXT,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    completion_percentage REAL DEFAULT 0.0,
                    success_rate REAL DEFAULT 0.0,
                    average_processing_time REAL DEFAULT 0.0,
                    common_errors TEXT,
                    retry_statistics TEXT
                )
            """)
            
            # File status table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    request_id TEXT,
                    submission_time TEXT,
                    completion_time TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Error tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    file_path TEXT,
                    error_type TEXT NOT NULL,
                    error_message TEXT,
                    error_context TEXT,
                    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TEXT,
                    resolution_method TEXT,
                    retry_count INTEGER DEFAULT 0
                )
            """)
            
            # Retry attempts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS retry_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_request_id INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    region TEXT NOT NULL,
                    parameter TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    attempted_time TEXT,
                    completed_time TEXT,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    new_request_id TEXT,
                    error_message TEXT,
                    retry_delay_seconds INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Retry metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS retry_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    total_retries_attempted INTEGER DEFAULT 0,
                    total_retries_successful INTEGER DEFAULT 0,
                    total_retries_failed INTEGER DEFAULT 0,
                    average_retry_delay REAL DEFAULT 0.0,
                    success_rate REAL DEFAULT 0.0,
                    last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Coverage reports table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coverage_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_control_files_discovered INTEGER,
                    total_regions INTEGER,
                    total_variables INTEGER,
                    coverage_percentage REAL,
                    missing_files TEXT,
                    unprocessed_files TEXT,
                    failed_files TEXT,
                    regional_coverage TEXT,
                    variable_coverage TEXT,
                    scan_duration REAL,
                    alerts TEXT,
                    generated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Dashboard metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value TEXT,
                    region TEXT,
                    variable_type TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Realtime ingestion events (idempotent by event_id)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS realtime_ingestion_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    request_id TEXT,
                    request_index TEXT,
                    status TEXT,
                    region TEXT,
                    variable_type TEXT,
                    event_time TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Sync checkpoints for restart-safe watermarking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS realtime_sync_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checkpoint_key TEXT UNIQUE NOT NULL,
                    checkpoint_value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Minimal model registry and retraining run tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_version TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    metrics_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    activated_at TEXT,
                    deactivated_at TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_retraining_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT UNIQUE NOT NULL,
                    trigger_reason TEXT NOT NULL,
                    event_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    model_version TEXT,
                    metadata_json TEXT,
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            """)

            # Scheduler-facing payload cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_inference_outputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    output_key TEXT UNIQUE NOT NULL,
                    payload_json TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    freshness_timestamp TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            self._create_basic_indexes(cursor)
            
            conn.commit()
            self.logger.info("✅ Basic database tables created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error creating basic tables: {e}")
            return False
    
    def _create_basic_indexes(self, cursor: sqlite3.Cursor):
        """Create indexes for basic tables."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_rda_requests_request_id ON rda_requests(request_id)",
            "CREATE INDEX IF NOT EXISTS idx_rda_requests_status ON rda_requests(status)",
            "CREATE INDEX IF NOT EXISTS idx_rda_requests_region ON rda_requests(region)",
            "CREATE INDEX IF NOT EXISTS idx_control_files_region ON control_files_tracking(region)",
            "CREATE INDEX IF NOT EXISTS idx_control_files_variable ON control_files_tracking(variable_type)",
            "CREATE INDEX IF NOT EXISTS idx_control_files_status ON control_files_tracking(status)",
            "CREATE INDEX IF NOT EXISTS idx_regional_progress_region ON regional_progress(region)",
            "CREATE INDEX IF NOT EXISTS idx_file_status_status ON file_status(status)",
            "CREATE INDEX IF NOT EXISTS idx_file_status_request_id ON file_status(request_id)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_request_id ON error_tracking(request_id)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_error_type ON error_tracking(error_type)",
            "CREATE INDEX IF NOT EXISTS idx_retry_attempts_status ON retry_attempts(status)",
            "CREATE INDEX IF NOT EXISTS idx_retry_attempts_scheduled_time ON retry_attempts(scheduled_time)",
            "CREATE INDEX IF NOT EXISTS idx_dashboard_metrics_name ON dashboard_metrics(metric_name)",
            "CREATE INDEX IF NOT EXISTS idx_dashboard_metrics_region ON dashboard_metrics(region)",
            "CREATE INDEX IF NOT EXISTS idx_realtime_events_event_time ON realtime_ingestion_events(event_time)",
            "CREATE INDEX IF NOT EXISTS idx_realtime_events_request_id ON realtime_ingestion_events(request_id)",
            "CREATE INDEX IF NOT EXISTS idx_realtime_events_status ON realtime_ingestion_events(status)",
            "CREATE INDEX IF NOT EXISTS idx_retraining_runs_started_at ON model_retraining_runs(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_scheduler_outputs_freshness ON scheduler_inference_outputs(freshness_timestamp)"
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except sqlite3.Error as e:
                self.logger.warning(f"Warning creating index: {e}")
    
    def _migrate_legacy_data(self) -> bool:
        """
        Migrate data from legacy database locations to the standard location.
        
        Returns:
            True if migration was successful or not needed, False otherwise
        """
        try:
            # Check if standard database already exists and has data
            if os.path.exists(self.db_path):
                with self._get_db_connection() as conn:
                    cursor = conn.execute("SELECT COUNT(*) as count FROM sqlite_master WHERE type='table'")
                    table_count = cursor.fetchone()['count']
                    
                    if table_count > 0:
                        self.logger.info(f"Standard database already exists with {table_count} tables")
                        return True
            
            # Look for legacy databases with data
            source_db = None
            max_tables = 0
            
            for legacy_path in self.LEGACY_DB_PATHS:
                if os.path.exists(legacy_path):
                    try:
                        with self._get_db_connection(legacy_path) as conn:
                            cursor = conn.execute("SELECT COUNT(*) as count FROM sqlite_master WHERE type='table'")
                            table_count = cursor.fetchone()['count']
                            
                            if table_count > max_tables:
                                max_tables = table_count
                                source_db = legacy_path
                                
                    except Exception as e:
                        self.logger.warning(f"Could not check legacy database {legacy_path}: {e}")
            
            if source_db and source_db != self.db_path:
                self.logger.info(f"Migrating data from legacy database: {source_db}")
                
                # Create backup of source
                backup_path = self._create_backup(source_db, "pre_migration")
                
                # Copy the database file
                shutil.copy2(source_db, self.db_path)
                self.logger.info(f"✅ Data migrated from {source_db} to {self.db_path}")
                
                return True
            
            self.logger.info("No legacy database migration needed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error during legacy data migration: {e}")
            return False
    
    def _migrate_rda_requests_schema(self) -> bool:
        """
        Migrate the rda_requests table to include missing columns.
        
        Returns:
            True if migration was successful, False otherwise
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rda_requests'")
                if not cursor.fetchone():
                    self.logger.info("rda_requests table doesn't exist, will be created fresh")
                    return True
                
                # Get current columns
                cursor.execute("PRAGMA table_info(rda_requests)")
                existing_columns = {row['name'] for row in cursor.fetchall()}
                
                # Define missing columns that need to be added
                missing_columns = {
                    'request_index': 'INTEGER',
                    'dsid': 'TEXT',
                    'date_rqst': 'TEXT',
                    'date_ready': 'TEXT',
                    'date_purge': 'TEXT',
                    'location': 'TEXT',
                    'ncar_contact': 'TEXT',
                    'rinfo': 'TEXT',
                    'subset_note': 'TEXT',
                    'raw_response': 'TEXT'
                }
                
                # Add missing columns
                columns_added = []
                for column_name, column_type in missing_columns.items():
                    if column_name not in existing_columns:
                        try:
                            cursor.execute(f"ALTER TABLE rda_requests ADD COLUMN {column_name} {column_type}")
                            columns_added.append(column_name)
                            self.logger.info(f"Added column: {column_name}")
                        except sqlite3.Error as e:
                            self.logger.error(f"Error adding column {column_name}: {e}")
                            return False
                
                if columns_added:
                    conn.commit()
                    self.logger.info(f"✅ Successfully added {len(columns_added)} columns to rda_requests table")
                else:
                    self.logger.info("✅ rda_requests table schema is already up to date")
                
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error migrating rda_requests schema: {e}")
            return False
    
    def _migrate_control_files_tracking_schema(self) -> bool:
        """
        Migrate the control_files_tracking table to include missing columns.
        
        Returns:
            True if migration was successful, False otherwise
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='control_files_tracking'")
                if not cursor.fetchone():
                    self.logger.info("control_files_tracking table doesn't exist, will be created fresh")
                    return True
                
                # Get current columns
                cursor.execute("PRAGMA table_info(control_files_tracking)")
                existing_columns = {row['name'] for row in cursor.fetchall()}
                
                # Define missing columns that need to be added
                missing_columns = {
                    'request_index': 'INTEGER'
                }
                
                # Add missing columns
                columns_added = []
                for column_name, column_type in missing_columns.items():
                    if column_name not in existing_columns:
                        try:
                            cursor.execute(f"ALTER TABLE control_files_tracking ADD COLUMN {column_name} {column_type}")
                            columns_added.append(column_name)
                            self.logger.info(f"Added column to control_files_tracking: {column_name}")
                        except sqlite3.Error as e:
                            self.logger.error(f"Error adding column {column_name} to control_files_tracking: {e}")
                            return False
                
                if columns_added:
                    conn.commit()
                    self.logger.info(f"✅ Successfully added {len(columns_added)} columns to control_files_tracking table")
                else:
                    self.logger.info("✅ control_files_tracking table schema is already up to date")
                
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error migrating control_files_tracking schema: {e}")
            return False
    
    def _validate_schema(self) -> Dict[str, bool]:
        """
        Validate the database schema completeness.
        
        Returns:
            Dictionary mapping table names to existence status
        """
        validation_results = {}
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = set(row['name'] for row in cursor.fetchall())
                
                # Basic tables
                basic_tables = {
                    'rda_requests', 'control_files_tracking', 'regional_progress',
                    'file_status', 'error_tracking', 'retry_attempts',
                    'retry_metrics', 'coverage_reports', 'dashboard_metrics'
                }
                
                for table in basic_tables:
                    validation_results[table] = table in existing_tables
                
                # Enhanced tables (if enabled)
                if self.enable_enhanced_schema:
                    enhanced_tables = {
                        'error_tracking_enhanced', 'retry_queue',
                        'progress_snapshots', 'system_health_metrics'
                    }
                    
                    for table in enhanced_tables:
                        validation_results[table] = table in existing_tables
                
        except Exception as e:
            self.logger.error(f"❌ Error validating schema: {e}")
        
        return validation_results
    
    def setup_database(self, force_recreate: bool = False) -> bool:
        """
        Set up the complete database with both basic and enhanced schemas.
        
        Args:
            force_recreate: Whether to force recreation of existing database
            
        Returns:
            True if setup was successful, False otherwise
        """
        try:
            with self.setup_lock:
                self.logger.info("🚀 Starting unified database setup...")
                
                # Create backup if database exists
                if os.path.exists(self.db_path) and not force_recreate:
                    backup_path = self._create_backup(self.db_path, "pre_setup")
                
                # Migrate legacy data if needed
                if not self._migrate_legacy_data():
                    self.logger.error("❌ Legacy data migration failed")
                    return False
                
                # Set up database connection
                with self._get_db_connection() as conn:
                    # Create basic tables
                    if not self._create_basic_tables(conn):
                        return False
                    
                    # Migrate rda_requests schema if needed
                    if not self._migrate_rda_requests_schema():
                        self.logger.error("❌ rda_requests schema migration failed")
                        return False
                    
                    # Migrate control_files_tracking schema if needed
                    if not self._migrate_control_files_tracking_schema():
                        self.logger.error("❌ control_files_tracking schema migration failed")
                        return False
                    
                    # Create enhanced tables if enabled
                    if self.enable_enhanced_schema and self.enhanced_schema:
                        self.logger.info("Creating enhanced database tables...")
                        if not self.enhanced_schema.create_enhanced_tables():
                            self.logger.error("❌ Enhanced tables creation failed")
                            return False
                    
                    conn.commit()
                
                # Validate schema
                validation_results = self._validate_schema()
                missing_tables = [table for table, exists in validation_results.items() if not exists]
                
                if missing_tables:
                    self.logger.error(f"❌ Schema validation failed. Missing tables: {missing_tables}")
                    return False
                
                self.logger.info("✅ Unified database setup completed successfully!")
                self.logger.info(f"📊 Database location: {self.db_path}")
                self.logger.info(f"📋 Tables created: {len(validation_results)}")
                
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Database setup failed: {e}")
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get comprehensive database information.
        
        Returns:
            Dictionary containing database information
        """
        info = {
            'database_path': self.db_path,
            'exists': os.path.exists(self.db_path),
            'size_bytes': 0,
            'tables': {},
            'schema_validation': {},
            'enhanced_schema_enabled': self.enable_enhanced_schema,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            if info['exists']:
                info['size_bytes'] = os.path.getsize(self.db_path)
                
                with self._get_db_connection() as conn:
                    # Get table information
                    cursor = conn.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    """)
                    
                    for row in cursor.fetchall():
                        table_name = row['name']
                        try:
                            count_cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                            record_count = count_cursor.fetchone()['count']
                            info['tables'][table_name] = record_count
                        except Exception as e:
                            info['tables'][table_name] = f"Error: {e}"
                
                # Get schema validation
                info['schema_validation'] = self._validate_schema()
        
        except Exception as e:
            info['error'] = str(e)
        
        return info
    
    def cleanup_legacy_databases(self, confirm: bool = False) -> List[str]:
        """
        Clean up legacy database files after successful migration.
        
        Args:
            confirm: Whether to actually delete the files
            
        Returns:
            List of files that were or would be cleaned up
        """
        cleanup_candidates = []
        
        for legacy_path in self.LEGACY_DB_PATHS:
            if legacy_path != self.db_path and os.path.exists(legacy_path):
                cleanup_candidates.append(legacy_path)
        
        if confirm:
            cleaned_files = []
            for file_path in cleanup_candidates:
                try:
                    # Create backup before deletion
                    backup_path = self._create_backup(file_path, "pre_cleanup")
                    os.remove(file_path)
                    cleaned_files.append(file_path)
                    self.logger.info(f"✅ Cleaned up legacy database: {file_path}")
                except Exception as e:
                    self.logger.error(f"❌ Error cleaning up {file_path}: {e}")
            
            return cleaned_files
        
        return cleanup_candidates


def main():
    """Main function for running the unified database setup."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Unified Database Setup for CarbonCast RDA Automation System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_database.py --setup                    # Set up database with standard configuration
  python setup_database.py --setup --enhanced         # Set up with enhanced schema tables
  python setup_database.py --info                     # Show database information
  python setup_database.py --validate                 # Validate database schema
  python setup_database.py --migrate                  # Migrate from legacy databases
  python setup_database.py --cleanup --confirm        # Clean up legacy database files

This script provides a unified solution for database configuration,
including migration from legacy locations and enhanced schema support.
        """
    )
    
    parser.add_argument('--setup', action='store_true',
                       help='Set up the complete database')
    parser.add_argument('--enhanced', action='store_true',
                       help='Enable enhanced schema tables')
    parser.add_argument('--info', action='store_true',
                       help='Show database information')
    parser.add_argument('--validate', action='store_true',
                       help='Validate database schema')
    parser.add_argument('--migrate', action='store_true',
                       help='Migrate from legacy databases')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up legacy database files')
    parser.add_argument('--confirm', action='store_true',
                       help='Confirm destructive operations')
    parser.add_argument('--force', action='store_true',
                       help='Force recreation of existing database')
    parser.add_argument('--db-path', 
                       help='Custom database path (default: src/python/data/automation_state.db)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Create database setup manager
    db_setup = UnifiedDatabaseSetup(
        db_path=args.db_path,
        enable_enhanced_schema=args.enhanced
    )
    
    if args.verbose:
        db_setup.logger.setLevel(logging.DEBUG)
    
    try:
        if args.setup:
            print("🚀 Setting up unified database...")
            success = db_setup.setup_database(force_recreate=args.force)
            
            if success:
                print("✅ Database setup completed successfully!")
                
                # Show database info
                info = db_setup.get_database_info()
                print(f"\n📊 Database Information:")
                print(f"  Path: {info['database_path']}")
                print(f"  Size: {info['size_bytes']:,} bytes")
                print(f"  Tables: {len(info['tables'])}")
                print(f"  Enhanced Schema: {'Enabled' if info['enhanced_schema_enabled'] else 'Disabled'}")
                
                exit(0)
            else:
                print("❌ Database setup failed!")
                exit(1)
        
        elif args.info:
            print("📊 Database Information:")
            info = db_setup.get_database_info()
            print(json.dumps(info, indent=2, default=str))
        
        elif args.validate:
            print("🔍 Validating database schema...")
            validation_results = db_setup._validate_schema()
            
            print("\nSchema Validation Results:")
            for table, exists in validation_results.items():
                status = "✅ EXISTS" if exists else "❌ MISSING"
                print(f"  {table}: {status}")
            
            missing_count = sum(1 for exists in validation_results.values() if not exists)
            if missing_count == 0:
                print("\n✅ All required tables exist")
                exit(0)
            else:
                print(f"\n❌ {missing_count} tables are missing")
                exit(1)
        
        elif args.migrate:
            print("🔄 Migrating from legacy databases...")
            success = db_setup._migrate_legacy_data()
            
            if success:
                print("✅ Migration completed successfully!")
                exit(0)
            else:
                print("❌ Migration failed!")
                exit(1)
        
        elif args.cleanup:
            print("🧹 Checking for legacy database files...")
            cleanup_candidates = db_setup.cleanup_legacy_databases(confirm=args.confirm)
            
            if cleanup_candidates:
                if args.confirm:
                    print(f"✅ Cleaned up {len(cleanup_candidates)} legacy database files")
                else:
                    print(f"Found {len(cleanup_candidates)} legacy database files:")
                    for file_path in cleanup_candidates:
                        print(f"  - {file_path}")
                    print("\nUse --confirm to actually delete these files")
            else:
                print("No legacy database files found")
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n⚠️ Operation interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Operation failed: {e}")
        db_setup.logger.error(f"Operation failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()