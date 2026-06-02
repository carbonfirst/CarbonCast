#!/usr/bin/env python3
"""
Database Initialization Script for RDA Automation System

This script ensures all required database tables exist and are properly initialized.
It creates missing tables and handles schema migrations.

DEPRECATED: This script is maintained for backward compatibility.
For new installations, use setup_database.py instead.
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the new unified setup
try:
    from setup_database import UnifiedDatabaseSetup
    UNIFIED_SETUP_AVAILABLE = True
except ImportError:
    UNIFIED_SETUP_AVAILABLE = False


def setup_logging() -> logging.Logger:
    """Setup logging for database initialization."""
    logger = logging.getLogger('database_init')
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def create_rda_requests_table(cursor):
    """Create the rda_requests table."""
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
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rda_requests_request_id ON rda_requests(request_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rda_requests_status ON rda_requests(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rda_requests_region ON rda_requests(region)")


def create_control_files_tracking_table(cursor):
    """Create the control_files_tracking table."""
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
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_control_files_region ON control_files_tracking(region)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_control_files_variable ON control_files_tracking(variable_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_control_files_status ON control_files_tracking(status)")


def create_regional_progress_table(cursor):
    """Create the regional_progress table."""
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
            variable_breakdown TEXT,  -- JSON
            first_discovered TEXT,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            completion_percentage REAL DEFAULT 0.0,
            success_rate REAL DEFAULT 0.0,
            average_processing_time REAL DEFAULT 0.0,
            common_errors TEXT,  -- JSON
            retry_statistics TEXT  -- JSON
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_regional_progress_region ON regional_progress(region)")


def create_file_status_table(cursor):
    """Create the file_status table for automation state tracking."""
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
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_status_status ON file_status(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_status_request_id ON file_status(request_id)")


def create_error_tracking_table(cursor):
    """Create the error_tracking table."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS error_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            file_path TEXT,
            error_type TEXT NOT NULL,
            error_message TEXT,
            error_context TEXT,  -- JSON
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            resolution_method TEXT,
            retry_count INTEGER DEFAULT 0
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_tracking_request_id ON error_tracking(request_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_tracking_error_type ON error_tracking(error_type)")


def create_retry_attempts_table(cursor):
    """Create the retry_attempts table to match retry_manager schema."""
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
    
    # Create retry_metrics table
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
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_retry_attempts_status ON retry_attempts(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_retry_attempts_scheduled_time ON retry_attempts(scheduled_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_retry_attempts_file_path ON retry_attempts(file_path)")


def create_coverage_reports_table(cursor):
    """Create the coverage_reports table."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coverage_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_control_files_discovered INTEGER,
            total_regions INTEGER,
            total_variables INTEGER,
            coverage_percentage REAL,
            missing_files TEXT,  -- JSON
            unprocessed_files TEXT,  -- JSON
            failed_files TEXT,  -- JSON
            regional_coverage TEXT,  -- JSON
            variable_coverage TEXT,  -- JSON
            scan_duration REAL,
            alerts TEXT,  -- JSON
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)


def create_dashboard_metrics_table(cursor):
    """Create the dashboard_metrics table for API endpoints."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_value TEXT,  -- JSON
            region TEXT,
            variable_type TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dashboard_metrics_name ON dashboard_metrics(metric_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dashboard_metrics_region ON dashboard_metrics(region)")


def initialize_database(db_path: str, logger: logging.Logger) -> bool:
    """
    Initialize the database with all required tables.
    
    Args:
        db_path: Path to the SQLite database file
        logger: Logger instance
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure database directory exists
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initializing database: {db_path}")
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # Create all required tables
            logger.info("Creating rda_requests table...")
            create_rda_requests_table(cursor)
            
            logger.info("Creating control_files_tracking table...")
            create_control_files_tracking_table(cursor)
            
            logger.info("Creating regional_progress table...")
            create_regional_progress_table(cursor)
            
            logger.info("Creating file_status table...")
            create_file_status_table(cursor)
            
            logger.info("Creating error_tracking table...")
            create_error_tracking_table(cursor)
            
            logger.info("Creating retry_attempts table...")
            create_retry_attempts_table(cursor)
            
            logger.info("Creating coverage_reports table...")
            create_coverage_reports_table(cursor)
            
            logger.info("Creating dashboard_metrics table...")
            create_dashboard_metrics_table(cursor)
            
            # Commit all changes
            conn.commit()
            
            # Verify tables were created
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = [
                'rda_requests', 'control_files_tracking', 'regional_progress',
                'file_status', 'error_tracking', 'retry_attempts',
                'coverage_reports', 'dashboard_metrics'
            ]
            
            missing_tables = set(expected_tables) - set(tables)
            if missing_tables:
                logger.error(f"Failed to create tables: {missing_tables}")
                return False
            
            logger.info(f"✅ Database initialization completed successfully!")
            logger.info(f"📊 Created tables: {', '.join(sorted(tables))}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        return False


def verify_database_schema(db_path: str, logger: logging.Logger) -> bool:
    """
    Verify that all required tables and indexes exist.
    
    Args:
        db_path: Path to the SQLite database file
        logger: Logger instance
        
    Returns:
        True if schema is valid, False otherwise
    """
    try:
        if not os.path.exists(db_path):
            logger.warning(f"Database file does not exist: {db_path}")
            return False
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = set(row[0] for row in cursor.fetchall())
            
            expected_tables = {
                'rda_requests', 'control_files_tracking', 'regional_progress',
                'file_status', 'error_tracking', 'retry_attempts',
                'coverage_reports', 'dashboard_metrics'
            }
            
            missing_tables = expected_tables - tables
            if missing_tables:
                logger.warning(f"Missing tables: {missing_tables}")
                return False
            
            # Check indexes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = set(row[0] for row in cursor.fetchall())
            
            required_indexes = {
                'idx_rda_requests_request_id', 'idx_rda_requests_status',
                'idx_control_files_region', 'idx_control_files_status',
                'idx_regional_progress_region', 'idx_file_status_status'
            }
            
            missing_indexes = required_indexes - indexes
            if missing_indexes:
                logger.warning(f"Missing indexes: {missing_indexes}")
                # Indexes are not critical, so we don't return False
            
            logger.info("✅ Database schema verification passed")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error verifying database schema: {e}")
        return False


def main():
    """Main function for database initialization."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Initialize RDA Automation Database',
        epilog="""
DEPRECATION NOTICE:
This script is maintained for backward compatibility.
For new installations and enhanced features, use setup_database.py instead:
  python setup_database.py --setup --enhanced
        """
    )
    parser.add_argument('--db-path',
                       default=os.path.join(os.path.dirname(__file__), 'data', 'automation_state.db'),
                       help='Path to database file')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify schema, do not initialize')
    parser.add_argument('--force-init', action='store_true',
                       help='Force initialization even if database exists')
    parser.add_argument('--use-unified', action='store_true',
                       help='Use the new unified database setup (recommended)')
    
    args = parser.parse_args()
    
    logger = setup_logging()
    
    # Show deprecation warning
    logger.warning("⚠️  DEPRECATION NOTICE: Consider using setup_database.py for enhanced features")
    
    try:
        # Use unified setup if available and requested
        if args.use_unified and UNIFIED_SETUP_AVAILABLE:
            logger.info("🔄 Using unified database setup...")
            unified_setup = UnifiedDatabaseSetup(db_path=args.db_path, enable_enhanced_schema=True)
            success = unified_setup.setup_database(force_recreate=args.force_init)
            
            if success:
                logger.info("🎉 Unified database setup completed successfully!")
                logger.info("💡 For future use, run: python setup_database.py --setup --enhanced")
                return 0
            else:
                logger.error("❌ Unified database setup failed!")
                return 1
        
        # Fall back to legacy initialization
        if args.verify_only:
            logger.info("🔍 Verifying database schema...")
            success = verify_database_schema(args.db_path, logger)
        else:
            if os.path.exists(args.db_path) and not args.force_init:
                logger.info("Database already exists. Verifying schema...")
                success = verify_database_schema(args.db_path, logger)
                if not success:
                    logger.info("Schema verification failed. Initializing database...")
                    success = initialize_database(args.db_path, logger)
            else:
                logger.info("Initializing database...")
                success = initialize_database(args.db_path, logger)
        
        if success:
            logger.info("🎉 Database operation completed successfully!")
            if not args.use_unified:
                logger.info("💡 For enhanced features, consider using: python setup_database.py --setup --enhanced")
            return 0
        else:
            logger.error("❌ Database operation failed!")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())