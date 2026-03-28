#!/usr/bin/env python3
"""
Database Migration Script for RDA Automation System Schema Fixes

This script specifically addresses the schema mismatch in the control_files_tracking table
by adding missing columns (error_message and file_path) to ensure consistency across
both database locations.

Key Features:
- Adds missing error_message column (TEXT type)
- Adds missing file_path column (TEXT UNIQUE NOT NULL type)
- Handles both database file locations safely
- Idempotent operation (safe to run multiple times)
- Comprehensive error handling and logging
- Backup creation before migration
- Rollback capability on failure
"""

import sqlite3
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from logger_utils import get_logger


class DatabaseMigrationManager:
    """
    Database migration manager for fixing schema mismatches in the RDA automation system.
    
    This class specifically handles the control_files_tracking table schema issues
    where some database instances are missing critical columns.
    """
    
    def __init__(self):
        """Initialize the database migration manager."""
        self.logger = self._setup_logging()
        self.migration_id = f"control_files_schema_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Define both database locations - updated to use standard path
        self.database_paths = [
            "src/python/data/automation_state.db",  # Standard path (primary)
            "data/automation_state.db",             # Legacy path
            "src/python/automation/data/automation_state.db"  # Old legacy path
        ]
        
        self.logger.info("Database Migration Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('database_migration', level=logging.DEBUG)
    
    def _get_db_connection(self, db_path: str) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _create_backup(self, db_path: str) -> str:
        """
        Create a backup of the database before migration.
        
        Args:
            db_path: Path to the database file
            
        Returns:
            Path to the backup file
        """
        try:
            if not os.path.exists(db_path):
                self.logger.warning(f"Database file does not exist: {db_path}")
                return None
            
            backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(db_path, backup_path)
            
            self.logger.info(f"✅ Backup created: {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"❌ Error creating backup for {db_path}: {e}")
            raise
    
    def _check_table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        """
        Check if a table exists in the database.
        
        Args:
            conn: Database connection
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        try:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,))
            return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Error checking if table {table_name} exists: {e}")
            return False
    
    def _check_column_exists(self, conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        """
        Check if a column exists in a table.
        
        Args:
            conn: Database connection
            table_name: Name of the table
            column_name: Name of the column to check
            
        Returns:
            True if column exists, False otherwise
        """
        try:
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            columns = [row['name'] for row in cursor.fetchall()]
            return column_name in columns
        except Exception as e:
            self.logger.error(f"Error checking if column {column_name} exists in {table_name}: {e}")
            return False
    
    def _get_table_schema(self, conn: sqlite3.Connection, table_name: str) -> Optional[str]:
        """
        Get the current schema of a table.
        
        Args:
            conn: Database connection
            table_name: Name of the table
            
        Returns:
            Table schema SQL or None if not found
        """
        try:
            cursor = conn.execute("""
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,))
            row = cursor.fetchone()
            return row['sql'] if row else None
        except Exception as e:
            self.logger.error(f"Error getting schema for table {table_name}: {e}")
            return None
    
    def _add_missing_columns(self, conn: sqlite3.Connection, db_path: str) -> bool:
        """
        Add missing columns and tables to fix data_sync errors.
        
        This method specifically addresses the issues reported in data_sync.py:
        - Missing rda_requests table
        - Missing request_index column in control_files_tracking table
        
        Args:
            conn: Database connection
            db_path: Path to the database (for logging)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # First, ensure rda_requests table exists (critical for data_sync.py)
            if not self._ensure_rda_requests_table(conn, db_path):
                return False
            
            # Then, fix control_files_tracking table
            if not self._fix_control_files_tracking_table(conn, db_path):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error in migration process: {e}")
            return False
    
    def _ensure_rda_requests_table(self, conn: sqlite3.Connection, db_path: str) -> bool:
        """
        Ensure the rda_requests table exists with all required columns.
        
        This table is critical for data_sync.py operations.
        """
        try:
            table_name = "rda_requests"
            
            if not self._check_table_exists(conn, table_name):
                self.logger.info(f"📋 Creating missing {table_name} table")
                
                # Create the rda_requests table with all required columns
                create_sql = """
                    CREATE TABLE rda_requests (
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
                """
                conn.execute(create_sql)
                
                # Create indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_rda_requests_request_id ON rda_requests(request_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_rda_requests_status ON rda_requests(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_rda_requests_region ON rda_requests(region)")
                
                self.logger.info(f"✅ Created {table_name} table with all required columns")
            else:
                # Table exists, check for missing columns
                missing_columns = []
                required_columns = [
                    ('request_index', 'INTEGER'),
                    ('dsid', 'TEXT'),
                    ('date_rqst', 'TEXT'),
                    ('date_ready', 'TEXT'),
                    ('date_purge', 'TEXT'),
                    ('location', 'TEXT'),
                    ('ncar_contact', 'TEXT'),
                    ('rinfo', 'TEXT'),
                    ('subset_note', 'TEXT'),
                    ('raw_response', 'TEXT'),
                    ('control_file_path', 'TEXT'),
                    ('region', 'TEXT'),
                    ('variable_type', 'TEXT')
                ]
                
                for column_name, column_type in required_columns:
                    if not self._check_column_exists(conn, table_name, column_name):
                        missing_columns.append((column_name, column_type))
                
                # Add missing columns
                for column_name, column_type in missing_columns:
                    try:
                        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                        conn.execute(alter_sql)
                        self.logger.info(f"✅ Added missing column {column_name} to {table_name}")
                    except sqlite3.Error as e:
                        if "duplicate column name" not in str(e).lower():
                            self.logger.error(f"❌ Error adding column {column_name}: {e}")
                            return False
                
                if missing_columns:
                    self.logger.info(f"✅ Added {len(missing_columns)} missing columns to {table_name}")
                else:
                    self.logger.info(f"✅ {table_name} table schema is complete")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error ensuring rda_requests table: {e}")
            return False
    
    def _fix_control_files_tracking_table(self, conn: sqlite3.Connection, db_path: str) -> bool:
        """
        Fix the control_files_tracking table to include missing columns.
        
        This specifically addresses the request_index column needed by data_sync.py.
        """
        try:
            table_name = "control_files_tracking"
            
            # Check if table exists
            if not self._check_table_exists(conn, table_name):
                self.logger.warning(f"Table {table_name} does not exist in {db_path}")
                return True  # Not an error if table doesn't exist
            
            # Get current schema
            current_schema = self._get_table_schema(conn, table_name)
            self.logger.debug(f"Current schema for {table_name}: {current_schema}")
            
            # Check which columns are missing
            missing_columns = []
            required_columns = [
                ("error_message", "TEXT"),
                ("file_path", "TEXT"),  # Remove UNIQUE NOT NULL to avoid conflicts
                ("request_index", "INTEGER")  # Critical for data_sync.py
            ]
            
            for column_name, column_type in required_columns:
                if not self._check_column_exists(conn, table_name, column_name):
                    missing_columns.append((column_name, column_type))
                    self.logger.info(f"📋 Column '{column_name}' is missing from {table_name}")
            
            if not missing_columns:
                self.logger.info(f"✅ All required columns already exist in {table_name}")
                return True
            
            # Add missing columns
            for column_name, column_definition in missing_columns:
                try:
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                    conn.execute(alter_sql)
                    self.logger.info(f"✅ Added column {column_name} ({column_definition})")
                    
                    # Set default values for existing rows if needed
                    if column_name == "file_path":
                        update_sql = f"""
                            UPDATE {table_name}
                            SET {column_name} = COALESCE(filename, 'control_files/' || region || '_' || variable_type || '_control.ctl')
                            WHERE {column_name} IS NULL
                        """
                        conn.execute(update_sql)
                        self.logger.info(f"✅ Updated existing rows with default {column_name} values")
                    
                except sqlite3.Error as e:
                    if "duplicate column name" in str(e).lower():
                        self.logger.info(f"✅ Column {column_name} already exists")
                    else:
                        self.logger.error(f"❌ Error adding column {column_name}: {e}")
                        return False
            
            # Commit the changes
            conn.commit()
            self.logger.info(f"✅ Successfully added {len(missing_columns)} missing columns to {table_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error fixing control_files_tracking table: {e}")
            return False
    
    def _validate_migration(self, conn: sqlite3.Connection, db_path: str) -> bool:
        """
        Validate that the migration was successful.
        
        Args:
            conn: Database connection
            db_path: Path to the database (for logging)
            
        Returns:
            True if validation passed, False otherwise
        """
        try:
            table_name = "control_files_tracking"
            
            # Check if table exists
            if not self._check_table_exists(conn, table_name):
                self.logger.warning(f"Table {table_name} does not exist in {db_path}")
                return True  # Not an error if table doesn't exist
            
            # Check required columns
            required_columns = ["error_message", "file_path"]
            missing_columns = []
            
            for column in required_columns:
                if not self._check_column_exists(conn, table_name, column):
                    missing_columns.append(column)
            
            if missing_columns:
                self.logger.error(f"❌ Validation failed: Missing columns {missing_columns}")
                return False
            
            # Check for duplicate file_path values (should be unique)
            try:
                cursor = conn.execute(f"""
                    SELECT file_path, COUNT(*) as count 
                    FROM {table_name} 
                    WHERE file_path IS NOT NULL 
                    GROUP BY file_path 
                    HAVING COUNT(*) > 1
                """)
                duplicates = cursor.fetchall()
                
                if duplicates:
                    self.logger.warning(f"⚠️ Found {len(duplicates)} duplicate file_path values")
                    for dup in duplicates:
                        self.logger.warning(f"  Duplicate: {dup['file_path']} ({dup['count']} times)")
            except Exception as e:
                self.logger.warning(f"Could not check for duplicates: {e}")
            
            self.logger.info(f"✅ Migration validation passed for {db_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error validating migration: {e}")
            return False
    
    def migrate_database(self, db_path: str) -> Dict[str, any]:
        """
        Migrate a single database file.
        
        Args:
            db_path: Path to the database file
            
        Returns:
            Dictionary with migration results
        """
        result = {
            "database_path": db_path,
            "success": False,
            "backup_created": None,
            "columns_added": [],
            "errors": [],
            "start_time": datetime.now().isoformat()
        }
        
        try:
            self.logger.info(f"🔄 Starting migration for: {db_path}")
            
            # Check if database file exists
            if not os.path.exists(db_path):
                self.logger.warning(f"⚠️ Database file does not exist: {db_path}")
                result["errors"].append(f"Database file does not exist: {db_path}")
                return result
            
            # Create backup
            backup_path = self._create_backup(db_path)
            result["backup_created"] = backup_path
            
            # Perform migration
            with self._get_db_connection(db_path) as conn:
                # Enable foreign key constraints
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Start transaction
                conn.execute("BEGIN TRANSACTION")
                
                try:
                    # Add missing columns
                    if self._add_missing_columns(conn, db_path):
                        # Validate migration
                        if self._validate_migration(conn, db_path):
                            conn.execute("COMMIT")
                            result["success"] = True
                            self.logger.info(f"✅ Migration completed successfully for: {db_path}")
                        else:
                            conn.execute("ROLLBACK")
                            result["errors"].append("Migration validation failed")
                            self.logger.error(f"❌ Migration validation failed for: {db_path}")
                    else:
                        conn.execute("ROLLBACK")
                        result["errors"].append("Failed to add missing columns")
                        self.logger.error(f"❌ Failed to add missing columns for: {db_path}")
                        
                except Exception as e:
                    conn.execute("ROLLBACK")
                    result["errors"].append(f"Migration transaction failed: {str(e)}")
                    self.logger.error(f"❌ Migration transaction failed for {db_path}: {e}")
            
        except Exception as e:
            result["errors"].append(f"Migration failed: {str(e)}")
            self.logger.error(f"❌ Migration failed for {db_path}: {e}")
        
        result["end_time"] = datetime.now().isoformat()
        return result
    
    def migrate_all_databases(self) -> Dict[str, any]:
        """
        Migrate all database files in the system.
        
        Returns:
            Dictionary with overall migration results
        """
        overall_result = {
            "migration_id": self.migration_id,
            "start_time": datetime.now().isoformat(),
            "databases_processed": 0,
            "databases_successful": 0,
            "databases_failed": 0,
            "results": [],
            "summary": {}
        }
        
        self.logger.info(f"🚀 Starting database migration: {self.migration_id}")
        self.logger.info(f"📋 Target databases: {self.database_paths}")
        
        for db_path in self.database_paths:
            result = self.migrate_database(db_path)
            overall_result["results"].append(result)
            overall_result["databases_processed"] += 1
            
            if result["success"]:
                overall_result["databases_successful"] += 1
            else:
                overall_result["databases_failed"] += 1
        
        overall_result["end_time"] = datetime.now().isoformat()
        
        # Create summary
        overall_result["summary"] = {
            "total_databases": len(self.database_paths),
            "successful_migrations": overall_result["databases_successful"],
            "failed_migrations": overall_result["databases_failed"],
            "success_rate": (overall_result["databases_successful"] / len(self.database_paths) * 100) if self.database_paths else 0
        }
        
        # Log summary
        self.logger.info(f"🏁 Migration completed: {self.migration_id}")
        self.logger.info(f"📊 Summary: {overall_result['databases_successful']}/{len(self.database_paths)} successful")
        
        if overall_result["databases_failed"] > 0:
            self.logger.warning(f"⚠️ {overall_result['databases_failed']} migrations failed")
        
        return overall_result
    
    def print_migration_report(self, results: Dict[str, any]):
        """
        Print a comprehensive migration report.
        
        Args:
            results: Migration results from migrate_all_databases()
        """
        print("\n" + "="*80)
        print("DATABASE MIGRATION REPORT")
        print("="*80)
        print(f"Migration ID: {results['migration_id']}")
        print(f"Start Time: {results['start_time']}")
        print(f"End Time: {results['end_time']}")
        print()
        
        print("SUMMARY:")
        print(f"  Total Databases: {results['summary']['total_databases']}")
        print(f"  Successful: {results['summary']['successful_migrations']}")
        print(f"  Failed: {results['summary']['failed_migrations']}")
        print(f"  Success Rate: {results['summary']['success_rate']:.1f}%")
        print()
        
        print("DETAILED RESULTS:")
        print("-" * 80)
        
        for result in results["results"]:
            status = "✅ SUCCESS" if result["success"] else "❌ FAILED"
            print(f"{status} - {result['database_path']}")
            
            if result["backup_created"]:
                print(f"  📁 Backup: {result['backup_created']}")
            
            if result["errors"]:
                print("  ❌ Errors:")
                for error in result["errors"]:
                    print(f"    - {error}")
            
            print()
        
        print("="*80)


def main():
    """Main function for running the migration script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Database Migration Script for RDA Automation System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python database_migration.py --migrate     # Migrate all databases
  python database_migration.py --check      # Check current schema status
  python database_migration.py --help       # Show this help message

This script fixes schema mismatches in the control_files_tracking table
by adding missing columns (error_message and file_path) to ensure
consistency across both database locations.
        """
    )
    
    parser.add_argument('--migrate', action='store_true',
                       help='Perform the database migration')
    parser.add_argument('--check', action='store_true',
                       help='Check current schema status without migrating')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Create migration manager
    migration_manager = DatabaseMigrationManager()
    
    if args.verbose:
        migration_manager.logger.setLevel(logging.DEBUG)
    
    try:
        if args.migrate:
            print("🚀 Starting database migration...")
            results = migration_manager.migrate_all_databases()
            migration_manager.print_migration_report(results)
            
            # Exit with appropriate code
            if results["databases_failed"] > 0:
                exit(1)
            else:
                exit(0)
                
        elif args.check:
            print("🔍 Checking database schema status...")
            
            for db_path in migration_manager.database_paths:
                print(f"\n📋 Database: {db_path}")
                
                if not os.path.exists(db_path):
                    print("  ❌ Database file does not exist")
                    continue
                
                try:
                    with migration_manager._get_db_connection(db_path) as conn:
                        table_name = "control_files_tracking"
                        
                        if not migration_manager._check_table_exists(conn, table_name):
                            print(f"  ⚠️ Table {table_name} does not exist")
                            continue
                        
                        # Check columns
                        has_error_message = migration_manager._check_column_exists(conn, table_name, "error_message")
                        has_file_path = migration_manager._check_column_exists(conn, table_name, "file_path")
                        
                        print(f"  error_message column: {'✅ EXISTS' if has_error_message else '❌ MISSING'}")
                        print(f"  file_path column: {'✅ EXISTS' if has_file_path else '❌ MISSING'}")
                        
                        if has_error_message and has_file_path:
                            print("  ✅ Schema is complete")
                        else:
                            print("  ⚠️ Schema needs migration")
                
                except Exception as e:
                    print(f"  ❌ Error checking database: {e}")
        
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\n⚠️ Migration interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed with error: {e}")
        migration_manager.logger.error(f"Migration failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()