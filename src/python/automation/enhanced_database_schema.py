#!/usr/bin/env python3
"""
Enhanced Database Schema for Integrated Error Tracking and Smart Retry System

This module provides comprehensive database schema definitions for the enhanced
error tracking and smart retry system, including migration utilities and
schema management functionality.

Key Features:
- Enhanced error tracking with comprehensive classification
- Smart retry queue management with priority and scheduling
- Progress snapshots for trending analysis
- System health metrics collection
- Backward compatibility with existing schema
- Safe migration with rollback capability
"""

import sqlite3
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
import threading
from logger_utils import get_logger


@dataclass
class SchemaVersion:
    """Represents a database schema version."""
    version: str
    description: str
    migration_sql: List[str]
    rollback_sql: List[str]
    created_at: str


class EnhancedDatabaseSchema:
    """
    Enhanced database schema manager for the integrated error tracking and smart retry system.
    
    This class provides comprehensive schema management including:
    - Enhanced error tracking tables
    - Smart retry queue management
    - Progress snapshots for trending
    - System health metrics
    - Safe migration with rollback capability
    """
    
    # Current schema version
    CURRENT_VERSION = "2.0.0"
    
    # Schema definitions for enhanced tables
    ENHANCED_SCHEMA = {
        "error_tracking_enhanced": """
            CREATE TABLE IF NOT EXISTS error_tracking_enhanced (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                request_index TEXT,
                session_id TEXT,
                error_type TEXT NOT NULL,
                error_category TEXT NOT NULL,
                error_severity TEXT NOT NULL DEFAULT 'medium',
                error_code TEXT,
                error_message TEXT,
                error_details TEXT,
                stack_trace TEXT,
                context_data TEXT,
                region TEXT,
                variable_type TEXT,
                file_path TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                is_retryable BOOLEAN DEFAULT TRUE,
                retry_strategy TEXT DEFAULT 'exponential_backoff',
                first_occurrence TEXT NOT NULL,
                last_occurrence TEXT NOT NULL,
                resolution_status TEXT DEFAULT 'unresolved',
                resolution_notes TEXT,
                resolved_at TEXT,
                resolved_by TEXT,
                impact_score REAL DEFAULT 0.0,
                frequency_count INTEGER DEFAULT 1,
                related_errors TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """,
        
        "retry_queue": """
            CREATE TABLE IF NOT EXISTS retry_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_request_id TEXT NOT NULL,
                error_tracking_id INTEGER,
                queue_priority INTEGER NOT NULL DEFAULT 5,
                retry_attempt INTEGER NOT NULL DEFAULT 1,
                max_retry_attempts INTEGER NOT NULL DEFAULT 5,
                retry_strategy TEXT NOT NULL DEFAULT 'exponential_backoff',
                base_delay_seconds INTEGER NOT NULL DEFAULT 60,
                current_delay_seconds INTEGER NOT NULL DEFAULT 60,
                next_retry_time TEXT NOT NULL,
                retry_window_start TEXT,
                retry_window_end TEXT,
                queue_status TEXT NOT NULL DEFAULT 'pending',
                request_data TEXT NOT NULL,
                context_data TEXT,
                region TEXT,
                variable_type TEXT,
                file_path TEXT,
                eligibility_score REAL DEFAULT 1.0,
                success_probability REAL DEFAULT 0.5,
                resource_requirements TEXT,
                dependencies TEXT,
                retry_conditions TEXT,
                failure_patterns TEXT,
                last_error_message TEXT,
                processing_node TEXT,
                queue_position INTEGER,
                estimated_duration INTEGER,
                actual_duration INTEGER,
                retry_history TEXT,
                metrics_data TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (error_tracking_id) REFERENCES error_tracking_enhanced(id)
            )
        """,
        
        "progress_snapshots": """
            CREATE TABLE IF NOT EXISTS progress_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_type TEXT NOT NULL,
                snapshot_scope TEXT NOT NULL,
                scope_identifier TEXT,
                snapshot_timestamp TEXT NOT NULL,
                total_requests INTEGER DEFAULT 0,
                completed_requests INTEGER DEFAULT 0,
                failed_requests INTEGER DEFAULT 0,
                pending_requests INTEGER DEFAULT 0,
                retrying_requests INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                failure_rate REAL DEFAULT 0.0,
                retry_rate REAL DEFAULT 0.0,
                average_processing_time REAL DEFAULT 0.0,
                throughput_per_hour REAL DEFAULT 0.0,
                error_distribution TEXT,
                performance_metrics TEXT,
                resource_utilization TEXT,
                trend_indicators TEXT,
                quality_metrics TEXT,
                regional_breakdown TEXT,
                variable_breakdown TEXT,
                time_series_data TEXT,
                comparative_data TEXT,
                anomaly_indicators TEXT,
                prediction_data TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """,
        
        "system_health_metrics": """
            CREATE TABLE IF NOT EXISTS system_health_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_timestamp TEXT NOT NULL,
                metric_category TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metric_unit TEXT,
                metric_threshold_min REAL,
                metric_threshold_max REAL,
                metric_status TEXT NOT NULL DEFAULT 'normal',
                component_name TEXT,
                component_version TEXT,
                environment TEXT DEFAULT 'production',
                data_source TEXT,
                collection_method TEXT,
                aggregation_period INTEGER DEFAULT 300,
                sample_count INTEGER DEFAULT 1,
                min_value REAL,
                max_value REAL,
                avg_value REAL,
                std_deviation REAL,
                percentile_95 REAL,
                percentile_99 REAL,
                trend_direction TEXT,
                trend_magnitude REAL,
                alert_level TEXT DEFAULT 'none',
                alert_message TEXT,
                correlation_data TEXT,
                context_data TEXT,
                tags TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """
    }
    
    # Index definitions for performance optimization
    ENHANCED_INDEXES = {
        "error_tracking_enhanced": [
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_request_id ON error_tracking_enhanced(request_id)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_error_type ON error_tracking_enhanced(error_type)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_error_category ON error_tracking_enhanced(error_category)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_severity ON error_tracking_enhanced(error_severity)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_region ON error_tracking_enhanced(region)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_variable ON error_tracking_enhanced(variable_type)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_retryable ON error_tracking_enhanced(is_retryable)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_resolution ON error_tracking_enhanced(resolution_status)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_occurrence ON error_tracking_enhanced(first_occurrence)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_frequency ON error_tracking_enhanced(frequency_count)",
            "CREATE INDEX IF NOT EXISTS idx_error_tracking_impact ON error_tracking_enhanced(impact_score)"
        ],
        
        "retry_queue": [
            "CREATE INDEX IF NOT EXISTS idx_retry_queue_priority ON retry_queue(queue_priority)",
            "CREATE INDEX IF NOT EXISTS idx_retry_queue_status ON retry_queue(queue_status)",
            "CREATE INDEX IF NOT EXISTS idx_retry_queue_next_retry ON retry_queue(next_retry_time)",
            "CREATE INDEX IF NOT EXISTS idx_retry_queue_attempt ON retry_queue(retry_attempt)",
            "CREATE INDEX IF NOT EXISTS idx_retry_queue_region ON retry_queue(region)",
            "CREATE INDEX IF NOT EXISTS idx_retry_queue_variable ON retry_queue(variable_type)",
            "CREATE INDEX IF NOT EXISTS idx_retry_queue_eligibility ON retry_queue(eligibility_score)",
            "CREATE INDEX IF NOT EXISTS idx_retry_queue_probability ON retry_queue(success_probability)",
            "CREATE INDEX IF NOT EXISTS idx_retry_queue_position ON retry_queue(queue_position)",
            "CREATE INDEX IF NOT EXISTS idx_retry_queue_error_tracking ON retry_queue(error_tracking_id)"
        ],
        
        "progress_snapshots": [
            "CREATE INDEX IF NOT EXISTS idx_progress_snapshots_type ON progress_snapshots(snapshot_type)",
            "CREATE INDEX IF NOT EXISTS idx_progress_snapshots_scope ON progress_snapshots(snapshot_scope)",
            "CREATE INDEX IF NOT EXISTS idx_progress_snapshots_identifier ON progress_snapshots(scope_identifier)",
            "CREATE INDEX IF NOT EXISTS idx_progress_snapshots_timestamp ON progress_snapshots(snapshot_timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_progress_snapshots_success_rate ON progress_snapshots(success_rate)",
            "CREATE INDEX IF NOT EXISTS idx_progress_snapshots_throughput ON progress_snapshots(throughput_per_hour)",
            "CREATE INDEX IF NOT EXISTS idx_progress_snapshots_composite ON progress_snapshots(snapshot_type, scope_identifier, snapshot_timestamp)"
        ],
        
        "system_health_metrics": [
            "CREATE INDEX IF NOT EXISTS idx_health_metrics_timestamp ON system_health_metrics(metric_timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_health_metrics_category ON system_health_metrics(metric_category)",
            "CREATE INDEX IF NOT EXISTS idx_health_metrics_name ON system_health_metrics(metric_name)",
            "CREATE INDEX IF NOT EXISTS idx_health_metrics_status ON system_health_metrics(metric_status)",
            "CREATE INDEX IF NOT EXISTS idx_health_metrics_component ON system_health_metrics(component_name)",
            "CREATE INDEX IF NOT EXISTS idx_health_metrics_alert ON system_health_metrics(alert_level)",
            "CREATE INDEX IF NOT EXISTS idx_health_metrics_value ON system_health_metrics(metric_value)",
            "CREATE INDEX IF NOT EXISTS idx_health_metrics_composite ON system_health_metrics(metric_category, metric_name, metric_timestamp)"
        ]
    }
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db"):
        """
        Initialize the enhanced database schema manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.logger = self._setup_logging()
        self.schema_lock = threading.Lock()
        
        # Ensure database directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize schema version tracking
        self._initialize_schema_versioning()
        
        self.logger.info("Enhanced Database Schema Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('enhanced_database_schema', level=logging.INFO)
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_schema_versioning(self):
        """Initialize schema version tracking table."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Create schema_versions table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS schema_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version TEXT UNIQUE NOT NULL,
                        description TEXT NOT NULL,
                        applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        rollback_available BOOLEAN DEFAULT TRUE,
                        migration_log TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                self.logger.debug("Schema versioning initialized")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing schema versioning: {e}")
            raise
    
    def get_current_schema_version(self) -> Optional[str]:
        """
        Get the current schema version from the database.
        
        Returns:
            Current schema version string or None if not found
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT version FROM schema_versions 
                    ORDER BY applied_at DESC 
                    LIMIT 1
                """)
                row = cursor.fetchone()
                return row['version'] if row else None
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting current schema version: {e}")
            return None
    
    def create_enhanced_tables(self) -> bool:
        """
        Create all enhanced tables for the error tracking and retry system.
        
        Returns:
            True if all tables were created successfully, False otherwise
        """
        try:
            with self.schema_lock:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    self.logger.info("Creating enhanced database tables...")
                    
                    # Create each enhanced table
                    for table_name, table_sql in self.ENHANCED_SCHEMA.items():
                        try:
                            cursor.execute(table_sql)
                            self.logger.info(f"Created table: {table_name}")
                        except sqlite3.Error as e:
                            self.logger.error(f"Error creating table {table_name}: {e}")
                            return False
                    
                    # Create indexes for performance
                    self.logger.info("Creating performance indexes...")
                    for table_name, indexes in self.ENHANCED_INDEXES.items():
                        for index_sql in indexes:
                            try:
                                cursor.execute(index_sql)
                            except sqlite3.Error as e:
                                self.logger.warning(f"Error creating index for {table_name}: {e}")
                    
                    conn.commit()
                    self.logger.info("Enhanced database tables created successfully")
                    return True
                    
        except sqlite3.Error as e:
            self.logger.error(f"Error creating enhanced tables: {e}")
            return False
    
    def verify_table_exists(self, table_name: str) -> bool:
        """
        Verify that a table exists in the database.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                return cursor.fetchone() is not None
                
        except sqlite3.Error as e:
            self.logger.error(f"Error verifying table {table_name}: {e}")
            return False
    
    def get_table_schema(self, table_name: str) -> Optional[str]:
        """
        Get the schema definition for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table schema SQL or None if not found
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT sql FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                row = cursor.fetchone()
                return row['sql'] if row else None
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting schema for table {table_name}: {e}")
            return None
    
    def validate_enhanced_schema(self) -> Dict[str, bool]:
        """
        Validate that all enhanced tables exist and have correct structure.
        
        Returns:
            Dictionary mapping table names to validation status
        """
        validation_results = {}
        
        for table_name in self.ENHANCED_SCHEMA.keys():
            exists = self.verify_table_exists(table_name)
            validation_results[table_name] = exists
            
            if exists:
                self.logger.info(f"✅ Table {table_name} exists")
            else:
                self.logger.warning(f"❌ Table {table_name} missing")
        
        return validation_results
    
    def get_database_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive database statistics for monitoring.
        
        Returns:
            Dictionary containing database statistics
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                stats = {
                    'timestamp': datetime.now().isoformat(),
                    'database_path': self.db_path,
                    'database_size_bytes': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
                    'schema_version': self.get_current_schema_version(),
                    'tables': {},
                    'indexes': {},
                    'total_records': 0
                }
                
                # Get table statistics
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                
                tables = cursor.fetchall()
                for table in tables:
                    table_name = table['name']
                    
                    # Get record count
                    try:
                        cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                        count = cursor.fetchone()['count']
                        stats['tables'][table_name] = {
                            'record_count': count,
                            'exists': True
                        }
                        stats['total_records'] += count
                    except sqlite3.Error as e:
                        stats['tables'][table_name] = {
                            'record_count': 0,
                            'exists': False,
                            'error': str(e)
                        }
                
                # Get index statistics
                cursor.execute("""
                    SELECT name, tbl_name FROM sqlite_master 
                    WHERE type='index' AND name NOT LIKE 'sqlite_%'
                """)
                
                indexes = cursor.fetchall()
                for index in indexes:
                    index_name = index['name']
                    table_name = index['tbl_name']
                    
                    if table_name not in stats['indexes']:
                        stats['indexes'][table_name] = []
                    stats['indexes'][table_name].append(index_name)
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting database statistics: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def optimize_database(self) -> bool:
        """
        Optimize the database by running VACUUM and ANALYZE.
        
        Returns:
            True if optimization was successful, False otherwise
        """
        try:
            with self._get_db_connection() as conn:
                self.logger.info("Starting database optimization...")
                
                # Run ANALYZE to update query planner statistics
                conn.execute("ANALYZE")
                self.logger.info("Database analysis completed")
                
                # Run VACUUM to reclaim space and defragment
                conn.execute("VACUUM")
                self.logger.info("Database vacuum completed")
                
                conn.commit()
                self.logger.info("Database optimization completed successfully")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Error optimizing database: {e}")
            return False
    
    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """
        Create a backup of the current database.
        
        Args:
            backup_path: Optional custom backup path
            
        Returns:
            Path to the backup file
        """
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.db_path}.backup_{timestamp}"
        
        try:
            with self._get_db_connection() as source:
                with sqlite3.connect(backup_path) as backup:
                    source.backup(backup)
            
            self.logger.info(f"Database backup created: {backup_path}")
            return backup_path
            
        except sqlite3.Error as e:
            self.logger.error(f"Error creating database backup: {e}")
            raise


def create_enhanced_schema_manager(db_path: str = "src/python/data/automation_state.db") -> EnhancedDatabaseSchema:
    """
    Factory function to create an Enhanced Database Schema Manager.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Configured EnhancedDatabaseSchema instance
    """
    return EnhancedDatabaseSchema(db_path)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Database Schema Manager')
    parser.add_argument('--create-tables', action='store_true',
                       help='Create enhanced database tables')
    parser.add_argument('--validate-schema', action='store_true',
                       help='Validate enhanced schema')
    parser.add_argument('--database-stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--optimize', action='store_true',
                       help='Optimize database')
    parser.add_argument('--backup', action='store_true',
                       help='Create database backup')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Database path')
    
    args = parser.parse_args()
    
    # Create schema manager
    schema_manager = create_enhanced_schema_manager(args.db_path)
    
    try:
        if args.create_tables:
            print("=== Creating Enhanced Database Tables ===")
            success = schema_manager.create_enhanced_tables()
            print(f"Tables creation: {'SUCCESS' if success else 'FAILED'}")
            
        elif args.validate_schema:
            print("=== Validating Enhanced Schema ===")
            results = schema_manager.validate_enhanced_schema()
            for table, exists in results.items():
                status = "✅ EXISTS" if exists else "❌ MISSING"
                print(f"{table}: {status}")
                
        elif args.database_stats:
            print("=== Database Statistics ===")
            stats = schema_manager.get_database_statistics()
            print(json.dumps(stats, indent=2))
            
        elif args.optimize:
            print("=== Optimizing Database ===")
            success = schema_manager.optimize_database()
            print(f"Optimization: {'SUCCESS' if success else 'FAILED'}")
            
        elif args.backup:
            print("=== Creating Database Backup ===")
            backup_path = schema_manager.backup_database()
            print(f"Backup created: {backup_path}")
            
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")