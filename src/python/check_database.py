#!/usr/bin/env python3
"""
Database Health Check Script for CarbonCast RDA Automation System

This script provides comprehensive database health checking capabilities:
- Verifies database schema completeness
- Checks for missing tables or columns
- Validates database connectivity
- Provides clear diagnostic output
- Identifies schema mismatches and inconsistencies
- Suggests remediation actions

Key Features:
- Comprehensive schema validation
- Database connectivity testing
- Performance diagnostics
- Data integrity checks
- Clear reporting with actionable recommendations
- Support for both basic and enhanced schemas
"""

import os
import sys
import sqlite3
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import threading

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logger_utils import get_logger

# Import existing modules
try:
    from automation.enhanced_database_schema import EnhancedDatabaseSchema
    from automation.configuration_manager import ConfigurationManager
    from setup_database import UnifiedDatabaseSetup
except ImportError as e:
    print(f"Warning: Could not import automation modules: {e}")
    EnhancedDatabaseSchema = None
    ConfigurationManager = None
    UnifiedDatabaseSetup = None


@dataclass
class DatabaseHealthResult:
    """Result of a database health check."""
    check_name: str
    status: str  # "pass", "fail", "warning", "info"
    message: str
    details: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[str]] = None


@dataclass
class DatabaseHealthReport:
    """Comprehensive database health report."""
    database_path: str
    check_timestamp: str
    overall_status: str  # "healthy", "issues", "critical"
    summary: Dict[str, int]
    results: List[DatabaseHealthResult]
    database_info: Dict[str, Any]
    recommendations: List[str]


class DatabaseHealthChecker:
    """
    Comprehensive database health checker for the CarbonCast RDA automation system.
    
    This class provides detailed health checking including:
    - Schema validation and completeness
    - Database connectivity testing
    - Performance diagnostics
    - Data integrity checks
    - Configuration validation
    """
    
    # Standard database path
    STANDARD_DB_PATH = "src/python/data/automation_state.db"
    
    # Expected basic tables
    BASIC_TABLES = {
        'rda_requests': [
            'id', 'request_id', 'control_file_path', 'region', 'variable_type',
            'status', 'submission_time', 'completion_time', 'download_time',
            'error_message', 'retry_count', 'download_directory', 'file_size',
            'processing_duration', 'request_index', 'dsid', 'date_rqst',
            'date_ready', 'date_purge', 'location', 'ncar_contact', 'rinfo',
            'subset_note', 'raw_response', 'created_at', 'updated_at'
        ],
        'control_files_tracking': [
            'id', 'file_path', 'filename', 'region', 'variable_type',
            'discovered_at', 'file_size', 'last_modified', 'status',
            'request_id', 'request_index', 'submission_time', 'completion_time', 'download_time',
            'error_message', 'retry_count', 'processing_duration',
            'download_directory', 'created_at', 'updated_at'
        ],
        'regional_progress': [
            'id', 'region', 'region_name', 'total_control_files',
            'discovered_files', 'queued_files', 'submitted_files',
            'processing_files', 'completed_files', 'failed_files',
            'downloaded_files', 'missing_files', 'variable_breakdown',
            'first_discovered', 'last_updated', 'completion_percentage',
            'success_rate', 'average_processing_time', 'common_errors',
            'retry_statistics'
        ],
        'file_status': [
            'id', 'file_path', 'status', 'request_id', 'submission_time',
            'completion_time', 'error_message', 'retry_count',
            'created_at', 'updated_at'
        ],
        'error_tracking': [
            'id', 'request_id', 'file_path', 'error_type', 'error_message',
            'error_context', 'detected_at', 'resolved_at', 'resolution_method',
            'retry_count'
        ],
        'retry_attempts': [
            'id', 'original_request_id', 'session_id', 'file_path', 'region',
            'parameter', 'attempt_number', 'scheduled_time', 'attempted_time',
            'completed_time', 'status', 'new_request_id', 'error_message',
            'retry_delay_seconds', 'created_at', 'updated_at'
        ],
        'retry_metrics': [
            'id', 'session_id', 'total_retries_attempted', 'total_retries_successful',
            'total_retries_failed', 'average_retry_delay', 'success_rate',
            'last_updated'
        ],
        'coverage_reports': [
            'id', 'total_control_files_discovered', 'total_regions',
            'total_variables', 'coverage_percentage', 'missing_files',
            'unprocessed_files', 'failed_files', 'regional_coverage',
            'variable_coverage', 'scan_duration', 'alerts', 'generated_at'
        ],
        'dashboard_metrics': [
            'id', 'metric_name', 'metric_value', 'region', 'variable_type',
            'timestamp'
        ]
    }
    
    # Expected enhanced tables
    ENHANCED_TABLES = {
        'error_tracking_enhanced': [
            'id', 'request_id', 'request_index', 'session_id', 'error_type',
            'error_category', 'error_severity', 'error_code', 'error_message',
            'error_details', 'stack_trace', 'context_data', 'region',
            'variable_type', 'file_path', 'retry_count', 'max_retries',
            'is_retryable', 'retry_strategy', 'first_occurrence',
            'last_occurrence', 'resolution_status', 'resolution_notes',
            'resolved_at', 'resolved_by', 'impact_score', 'frequency_count',
            'related_errors', 'metadata', 'created_at', 'updated_at'
        ],
        'retry_queue': [
            'id', 'original_request_id', 'error_tracking_id', 'queue_priority',
            'retry_attempt', 'max_retry_attempts', 'retry_strategy',
            'base_delay_seconds', 'current_delay_seconds', 'next_retry_time',
            'retry_window_start', 'retry_window_end', 'queue_status',
            'request_data', 'context_data', 'region', 'variable_type',
            'file_path', 'eligibility_score', 'success_probability',
            'resource_requirements', 'dependencies', 'retry_conditions',
            'failure_patterns', 'last_error_message', 'processing_node',
            'queue_position', 'estimated_duration', 'actual_duration',
            'retry_history', 'metrics_data', 'created_at', 'updated_at'
        ],
        'progress_snapshots': [
            'id', 'snapshot_type', 'snapshot_scope', 'scope_identifier',
            'snapshot_timestamp', 'total_requests', 'completed_requests',
            'failed_requests', 'pending_requests', 'retrying_requests',
            'success_rate', 'failure_rate', 'retry_rate',
            'average_processing_time', 'throughput_per_hour',
            'error_distribution', 'performance_metrics', 'resource_utilization',
            'trend_indicators', 'quality_metrics', 'regional_breakdown',
            'variable_breakdown', 'time_series_data', 'comparative_data',
            'anomaly_indicators', 'prediction_data', 'metadata', 'created_at'
        ],
        'system_health_metrics': [
            'id', 'metric_timestamp', 'metric_category', 'metric_name',
            'metric_value', 'metric_unit', 'metric_threshold_min',
            'metric_threshold_max', 'metric_status', 'component_name',
            'component_version', 'environment', 'data_source',
            'collection_method', 'aggregation_period', 'sample_count',
            'min_value', 'max_value', 'avg_value', 'std_deviation',
            'percentile_95', 'percentile_99', 'trend_direction',
            'trend_magnitude', 'alert_level', 'alert_message',
            'correlation_data', 'context_data', 'tags', 'metadata',
            'created_at'
        ]
    }
    
    def __init__(self, db_path: Optional[str] = None, check_enhanced: bool = True):
        """
        Initialize the database health checker.
        
        Args:
            db_path: Custom database path (uses standard path if None)
            check_enhanced: Whether to check enhanced schema tables
        """
        self.db_path = db_path or self.STANDARD_DB_PATH
        self.check_enhanced = check_enhanced
        self.logger = self._setup_logging()
        self.check_lock = threading.Lock()
        
        # Initialize enhanced schema manager if available
        self.enhanced_schema = None
        if check_enhanced and EnhancedDatabaseSchema:
            try:
                self.enhanced_schema = EnhancedDatabaseSchema(self.db_path)
            except Exception as e:
                self.logger.warning(f"Could not initialize enhanced schema manager: {e}")
        
        self.logger.info(f"Database Health Checker initialized for: {self.db_path}")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('database_health_checker', level=logging.INFO)
    
    def _get_db_connection(self, db_path: Optional[str] = None) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        path = db_path or self.db_path
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _check_database_exists(self) -> DatabaseHealthResult:
        """Check if the database file exists."""
        if os.path.exists(self.db_path):
            file_size = os.path.getsize(self.db_path)
            return DatabaseHealthResult(
                check_name="Database File Existence",
                status="pass",
                message=f"Database file exists at {self.db_path}",
                details={"file_size_bytes": file_size, "file_size_mb": round(file_size / 1024 / 1024, 2)}
            )
        else:
            return DatabaseHealthResult(
                check_name="Database File Existence",
                status="fail",
                message=f"Database file does not exist at {self.db_path}",
                recommendations=[
                    "Run 'python setup_database.py --setup' to create the database",
                    "Check if the database path is correct",
                    "Verify file system permissions"
                ]
            )
    
    def _check_database_connectivity(self) -> DatabaseHealthResult:
        """Check database connectivity."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("SELECT 1")
                cursor.fetchone()
            
            return DatabaseHealthResult(
                check_name="Database Connectivity",
                status="pass",
                message="Successfully connected to database"
            )
        except Exception as e:
            return DatabaseHealthResult(
                check_name="Database Connectivity",
                status="fail",
                message=f"Failed to connect to database: {e}",
                recommendations=[
                    "Check if the database file is corrupted",
                    "Verify file system permissions",
                    "Try recreating the database with setup_database.py"
                ]
            )
    
    def _check_table_schema(self, table_name: str, expected_columns: List[str]) -> DatabaseHealthResult:
        """Check if a table has the expected schema."""
        try:
            with self._get_db_connection() as conn:
                # Check if table exists
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                
                if not cursor.fetchone():
                    return DatabaseHealthResult(
                        check_name=f"Table Schema: {table_name}",
                        status="fail",
                        message=f"Table '{table_name}' does not exist",
                        recommendations=[
                            f"Create the missing table using setup_database.py",
                            f"Check if database migration is needed"
                        ]
                    )
                
                # Get table columns
                cursor = conn.execute(f"PRAGMA table_info({table_name})")
                actual_columns = [row['name'] for row in cursor.fetchall()]
                
                # Check for missing columns
                missing_columns = set(expected_columns) - set(actual_columns)
                extra_columns = set(actual_columns) - set(expected_columns)
                
                if missing_columns:
                    return DatabaseHealthResult(
                        check_name=f"Table Schema: {table_name}",
                        status="fail",
                        message=f"Table '{table_name}' is missing columns: {list(missing_columns)}",
                        details={
                            "missing_columns": list(missing_columns),
                            "extra_columns": list(extra_columns),
                            "actual_columns": actual_columns
                        },
                        recommendations=[
                            f"Run database migration to add missing columns",
                            f"Use setup_database.py --setup to recreate the table"
                        ]
                    )
                elif extra_columns:
                    return DatabaseHealthResult(
                        check_name=f"Table Schema: {table_name}",
                        status="warning",
                        message=f"Table '{table_name}' has extra columns: {list(extra_columns)}",
                        details={
                            "extra_columns": list(extra_columns),
                            "actual_columns": actual_columns
                        }
                    )
                else:
                    return DatabaseHealthResult(
                        check_name=f"Table Schema: {table_name}",
                        status="pass",
                        message=f"Table '{table_name}' schema is correct",
                        details={"column_count": len(actual_columns)}
                    )
                    
        except Exception as e:
            return DatabaseHealthResult(
                check_name=f"Table Schema: {table_name}",
                status="fail",
                message=f"Error checking table '{table_name}': {e}",
                recommendations=[
                    "Check database connectivity",
                    "Verify database is not corrupted"
                ]
            )
    
    def _check_data_integrity(self) -> List[DatabaseHealthResult]:
        """Check basic data integrity."""
        results = []
        
        try:
            with self._get_db_connection() as conn:
                # Check for orphaned records
                cursor = conn.execute("""
                    SELECT COUNT(*) as count 
                    FROM control_files_tracking 
                    WHERE request_id IS NOT NULL 
                    AND request_id NOT IN (SELECT request_id FROM rda_requests)
                """)
                orphaned_count = cursor.fetchone()['count']
                
                if orphaned_count > 0:
                    results.append(DatabaseHealthResult(
                        check_name="Data Integrity: Orphaned Records",
                        status="warning",
                        message=f"Found {orphaned_count} orphaned control file records",
                        details={"orphaned_records": orphaned_count},
                        recommendations=[
                            "Clean up orphaned records",
                            "Check data consistency"
                        ]
                    ))
                else:
                    results.append(DatabaseHealthResult(
                        check_name="Data Integrity: Orphaned Records",
                        status="pass",
                        message="No orphaned records found"
                    ))
                
                # Check for duplicate request IDs
                cursor = conn.execute("""
                    SELECT request_id, COUNT(*) as count 
                    FROM rda_requests 
                    GROUP BY request_id 
                    HAVING COUNT(*) > 1
                """)
                duplicates = cursor.fetchall()
                
                if duplicates:
                    results.append(DatabaseHealthResult(
                        check_name="Data Integrity: Duplicate Request IDs",
                        status="warning",
                        message=f"Found {len(duplicates)} duplicate request IDs",
                        details={"duplicate_count": len(duplicates)},
                        recommendations=[
                            "Investigate and resolve duplicate request IDs",
                            "Check data import processes"
                        ]
                    ))
                else:
                    results.append(DatabaseHealthResult(
                        check_name="Data Integrity: Duplicate Request IDs",
                        status="pass",
                        message="No duplicate request IDs found"
                    ))
                    
        except Exception as e:
            results.append(DatabaseHealthResult(
                check_name="Data Integrity Check",
                status="fail",
                message=f"Error checking data integrity: {e}",
                recommendations=[
                    "Check database connectivity",
                    "Verify required tables exist"
                ]
            ))
        
        return results
    
    def _check_performance_indicators(self) -> List[DatabaseHealthResult]:
        """Check database performance indicators."""
        results = []
        
        try:
            with self._get_db_connection() as conn:
                # Check database size
                cursor = conn.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor = conn.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                db_size = page_count * page_size
                
                results.append(DatabaseHealthResult(
                    check_name="Performance: Database Size",
                    status="info",
                    message=f"Database size: {db_size:,} bytes ({db_size/1024/1024:.2f} MB)",
                    details={
                        "size_bytes": db_size,
                        "size_mb": round(db_size / 1024 / 1024, 2),
                        "page_count": page_count,
                        "page_size": page_size
                    }
                ))
                
                # Check for missing indexes
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND name NOT LIKE 'sqlite_%'
                """)
                indexes = [row['name'] for row in cursor.fetchall()]
                
                expected_indexes = [
                    'idx_rda_requests_request_id', 'idx_rda_requests_status',
                    'idx_control_files_region', 'idx_control_files_status',
                    'idx_regional_progress_region', 'idx_file_status_status'
                ]
                
                missing_indexes = set(expected_indexes) - set(indexes)
                
                if missing_indexes:
                    results.append(DatabaseHealthResult(
                        check_name="Performance: Database Indexes",
                        status="warning",
                        message=f"Missing {len(missing_indexes)} expected indexes",
                        details={
                            "missing_indexes": list(missing_indexes),
                            "existing_indexes": indexes
                        },
                        recommendations=[
                            "Recreate missing indexes for better performance",
                            "Run setup_database.py to create all indexes"
                        ]
                    ))
                else:
                    results.append(DatabaseHealthResult(
                        check_name="Performance: Database Indexes",
                        status="pass",
                        message="All expected indexes are present",
                        details={"index_count": len(indexes)}
                    ))
                    
        except Exception as e:
            results.append(DatabaseHealthResult(
                check_name="Performance Check",
                status="fail",
                message=f"Error checking performance indicators: {e}"
            ))
        
        return results
    
    def _get_database_statistics(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        stats = {
            'timestamp': datetime.now().isoformat(),
            'database_path': self.db_path,
            'tables': {},
            'total_records': 0
        }
        
        try:
            with self._get_db_connection() as conn:
                # Get table statistics
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                
                for row in cursor.fetchall():
                    table_name = row['name']
                    try:
                        count_cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                        record_count = count_cursor.fetchone()['count']
                        stats['tables'][table_name] = record_count
                        stats['total_records'] += record_count
                    except Exception as e:
                        stats['tables'][table_name] = f"Error: {e}"
        
        except Exception as e:
            stats['error'] = str(e)
        
        return stats
    
    def run_health_check(self) -> DatabaseHealthReport:
        """
        Run comprehensive database health check.
        
        Returns:
            DatabaseHealthReport with all check results
        """
        with self.check_lock:
            self.logger.info("🔍 Starting database health check...")
            
            results = []
            
            # Basic checks
            results.append(self._check_database_exists())
            results.append(self._check_database_connectivity())
            
            # Only proceed with schema checks if database exists and is accessible
            if results[-1].status == "pass":
                # Check basic table schemas
                for table_name, expected_columns in self.BASIC_TABLES.items():
                    results.append(self._check_table_schema(table_name, expected_columns))
                
                # Check enhanced table schemas if enabled
                if self.check_enhanced:
                    for table_name, expected_columns in self.ENHANCED_TABLES.items():
                        results.append(self._check_table_schema(table_name, expected_columns))
                
                # Data integrity checks
                results.extend(self._check_data_integrity())
                
                # Performance checks
                results.extend(self._check_performance_indicators())
            
            # Calculate overall status
            status_counts = {"pass": 0, "fail": 0, "warning": 0, "info": 0}
            for result in results:
                status_counts[result.status] += 1
            
            if status_counts["fail"] > 0:
                overall_status = "critical"
            elif status_counts["warning"] > 0:
                overall_status = "issues"
            else:
                overall_status = "healthy"
            
            # Collect recommendations
            all_recommendations = []
            for result in results:
                if result.recommendations:
                    all_recommendations.extend(result.recommendations)
            
            # Remove duplicates while preserving order
            unique_recommendations = []
            for rec in all_recommendations:
                if rec not in unique_recommendations:
                    unique_recommendations.append(rec)
            
            # Get database info
            database_info = self._get_database_statistics()
            
            report = DatabaseHealthReport(
                database_path=self.db_path,
                check_timestamp=datetime.now().isoformat(),
                overall_status=overall_status,
                summary=status_counts,
                results=results,
                database_info=database_info,
                recommendations=unique_recommendations
            )
            
            self.logger.info(f"✅ Health check completed. Status: {overall_status}")
            return report
    
    def print_health_report(self, report: DatabaseHealthReport, verbose: bool = False):
        """
        Print a formatted health report.
        
        Args:
            report: DatabaseHealthReport to print
            verbose: Whether to include detailed information
        """
        print("\n" + "="*80)
        print("DATABASE HEALTH CHECK REPORT")
        print("="*80)
        print(f"Database: {report.database_path}")
        print(f"Check Time: {report.check_timestamp}")
        print(f"Overall Status: {report.overall_status.upper()}")
        print()
        
        # Summary
        print("SUMMARY:")
        print(f"  ✅ Passed: {report.summary['pass']}")
        print(f"  ⚠️  Warnings: {report.summary['warning']}")
        print(f"  ❌ Failed: {report.summary['fail']}")
        print(f"  ℹ️  Info: {report.summary['info']}")
        print()
        
        # Database statistics
        if report.database_info.get('tables'):
            print("DATABASE STATISTICS:")
            print(f"  Total Records: {report.database_info['total_records']:,}")
            print(f"  Tables: {len(report.database_info['tables'])}")
            
            if verbose:
                for table, count in report.database_info['tables'].items():
                    print(f"    {table}: {count:,}")
            print()
        
        # Check results
        print("CHECK RESULTS:")
        print("-" * 80)
        
        for result in report.results:
            status_icon = {
                "pass": "✅",
                "fail": "❌",
                "warning": "⚠️",
                "info": "ℹ️"
            }.get(result.status, "❓")
            
            print(f"{status_icon} {result.check_name}: {result.message}")
            
            if verbose and result.details:
                for key, value in result.details.items():
                    print(f"    {key}: {value}")
            
            if result.recommendations:
                for rec in result.recommendations:
                    print(f"    💡 {rec}")
            print()
        
        # Overall recommendations
        if report.recommendations:
            print("RECOMMENDATIONS:")
            print("-" * 80)
            for i, rec in enumerate(report.recommendations, 1):
                print(f"{i}. {rec}")
            print()
        
        print("="*80)


def main():
    """Main function for running the database health check."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Database Health Check for CarbonCast RDA Automation System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python check_database.py                    # Run basic health check
  python check_database.py --enhanced         # Include enhanced schema checks
  python check_database.py --verbose          # Show detailed output
  python check_database.py --json             # Output results as JSON
  python check_database.py --db-path /path    # Check specific database

This script provides comprehensive database health checking including
schema validation, connectivity testing, and performance diagnostics.
        """
    )
    
    parser.add_argument('--enhanced', action='store_true',
                       help='Check enhanced schema tables')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed output')
    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON')
    parser.add_argument('--db-path',
                       help='Custom database path to check')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress non-essential output')
    
    args = parser.parse_args()
    
    # Create health checker
    checker = DatabaseHealthChecker(
        db_path=args.db_path,
        check_enhanced=args.enhanced
    )
    
    if args.quiet:
        checker.logger.setLevel(logging.WARNING)
    
    try:
        # Run health check
        if not args.quiet:
            print("🔍 Running database health check...")
        
        report = checker.run_health_check()
        
        if args.json:
            # Output as JSON
            report_dict = asdict(report)
            print(json.dumps(report_dict, indent=2, default=str))
        else:
            # Print formatted report
            checker.print_health_report(report, verbose=args.verbose)
        
        # Exit with appropriate code
        if report.overall_status == "critical":
            exit(2)
        elif report.overall_status == "issues":
            exit(1)
        else:
            exit(0)
    
    except KeyboardInterrupt:
        print("\n⚠️ Health check interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Health check failed: {e}")
        checker.logger.error(f"Health check failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()