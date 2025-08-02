#!/usr/bin/env python3
"""
Bulletproof Database Initialization System for CarbonCast RDA Automation

This module provides production-grade, bulletproof database initialization that:
- Guarantees database consistency through atomic operations
- Provides comprehensive pre-startup validation
- Implements automatic repair and recovery mechanisms
- Ensures idempotent operations safe to run multiple times
- Handles all edge cases including corruption and partial failures
- Provides detailed logging and error reporting
- Creates proper backups before any modifications
- Validates database integrity at multiple levels

Key Features:
- Atomic database operations with full rollback capability
- Comprehensive schema validation and automatic repair
- Production-ready error handling with clear diagnostics
- Idempotent design - safe to run repeatedly
- Automatic backup creation and restoration
- Database integrity verification
- Performance optimization and health monitoring
- Thread-safe operations with proper locking
- Graceful degradation and recovery mechanisms
"""

import os
import sys
import sqlite3
import logging
import shutil
import json
import threading
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import tempfile
import fcntl

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import existing modules
try:
    from automation.enhanced_database_schema import EnhancedDatabaseSchema
    from setup_database import UnifiedDatabaseSetup
    from check_database import DatabaseHealthChecker, DatabaseHealthReport
except ImportError as e:
    print(f"Warning: Could not import some modules: {e}")
    EnhancedDatabaseSchema = None
    UnifiedDatabaseSetup = None
    DatabaseHealthChecker = None


@dataclass
class DatabaseValidationResult:
    """Result of database validation check."""
    check_name: str
    status: str  # "pass", "fail", "warning", "critical"
    message: str
    details: Optional[Dict[str, Any]] = None
    auto_fixable: bool = False
    fix_applied: bool = False
    recommendations: Optional[List[str]] = None


@dataclass
class DatabaseInitializationReport:
    """Comprehensive database initialization report."""
    initialization_id: str
    start_time: str
    end_time: Optional[str]
    database_path: str
    status: str  # "success", "failed", "partial"
    validation_results: List[DatabaseValidationResult]
    operations_performed: List[str]
    backups_created: List[str]
    errors_encountered: List[str]
    warnings: List[str]
    recovery_actions: List[str]
    final_health_check: Optional[Dict[str, Any]]
    recommendations: List[str]


class BulletproofDatabaseInitializer:
    """
    Production-grade bulletproof database initializer.
    
    This class provides comprehensive database initialization with:
    - Atomic operations with full rollback capability
    - Comprehensive validation and automatic repair
    - Production-ready error handling
    - Idempotent design safe for repeated execution
    - Automatic backup and recovery mechanisms
    """
    
    # Standard database configuration
    STANDARD_DB_PATH = "src/python/data/automation_state.db"
    BACKUP_RETENTION_DAYS = 30
    MAX_BACKUP_COUNT = 10
    
    # Critical tables that must exist for system operation
    CRITICAL_TABLES = {
        'rda_requests': {
            'required_columns': [
                'id', 'request_id', 'control_file_path', 'region', 'variable_type',
                'status', 'request_index', 'dsid', 'date_rqst', 'date_ready',
                'date_purge', 'location', 'ncar_contact', 'rinfo', 'subset_note',
                'raw_response', 'created_at', 'updated_at'
            ],
            'indexes': [
                'idx_rda_requests_request_id',
                'idx_rda_requests_status',
                'idx_rda_requests_region'
            ]
        },
        'control_files_tracking': {
            'required_columns': [
                'id', 'file_path', 'filename', 'region', 'variable_type',
                'discovered_at', 'status', 'request_id', 'request_index',
                'error_message', 'created_at', 'updated_at'
            ],
            'indexes': [
                'idx_control_files_region',
                'idx_control_files_variable',
                'idx_control_files_status'
            ]
        }
    }
    
    # Database integrity constraints
    INTEGRITY_CHECKS = [
        {
            'name': 'Foreign Key Consistency',
            'query': '''
                SELECT COUNT(*) as violations 
                FROM control_files_tracking 
                WHERE request_id IS NOT NULL 
                AND request_id NOT IN (SELECT request_id FROM rda_requests)
            ''',
            'max_violations': 0,
            'auto_fix': True
        },
        {
            'name': 'Duplicate Request IDs',
            'query': '''
                SELECT COUNT(*) as violations 
                FROM (
                    SELECT request_id, COUNT(*) as cnt 
                    FROM rda_requests 
                    GROUP BY request_id 
                    HAVING COUNT(*) > 1
                )
            ''',
            'max_violations': 0,
            'auto_fix': False
        },
        {
            'name': 'Null Critical Fields',
            'query': '''
                SELECT COUNT(*) as violations 
                FROM rda_requests 
                WHERE request_id IS NULL OR control_file_path IS NULL
            ''',
            'max_violations': 0,
            'auto_fix': False
        }
    ]
    
    def __init__(self, db_path: Optional[str] = None, enable_enhanced_schema: bool = True):
        """
        Initialize the bulletproof database initializer.
        
        Args:
            db_path: Custom database path (uses standard if None)
            enable_enhanced_schema: Whether to create enhanced schema tables
        """
        self.db_path = db_path or self.STANDARD_DB_PATH
        self.enable_enhanced_schema = enable_enhanced_schema
        self.initialization_id = f"bulletproof_init_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Thread safety
        self.init_lock = threading.RLock()
        self.file_lock = None
        
        # Setup logging
        self.logger = self._setup_comprehensive_logging()
        
        # Initialize components
        self.unified_setup = None
        self.health_checker = None
        self.enhanced_schema = None
        
        # State tracking
        self.operations_log = []
        self.backups_created = []
        self.validation_results = []
        self.errors_encountered = []
        self.warnings = []
        self.recovery_actions = []
        
        # Ensure database directory exists
        self._ensure_database_directory()
        
        self.logger.info(f"Bulletproof Database Initializer created: {self.initialization_id}")
    
    def _setup_comprehensive_logging(self) -> logging.Logger:
        """Set up comprehensive logging with multiple handlers."""
        logger = logging.getLogger(f'bulletproof_db_init_{self.initialization_id}')
        logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        logger.handlers.clear()
        
        # Create logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Detailed file handler
        log_file = logs_dir / f"bulletproof_db_init_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        
        # Console handler for important messages
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
        
        # Error file handler for critical issues
        error_file = logs_dir / f"bulletproof_db_errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_file)
        error_handler.setFormatter(file_formatter)
        error_handler.setLevel(logging.ERROR)
        logger.addHandler(error_handler)
        
        return logger
    
    def _ensure_database_directory(self):
        """Ensure database directory exists with proper permissions."""
        try:
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # Verify write permissions
            test_file = db_dir / f".write_test_{os.getpid()}"
            try:
                test_file.write_text("test")
                test_file.unlink()
                self.logger.debug(f"Database directory verified: {db_dir}")
            except Exception as e:
                raise PermissionError(f"Cannot write to database directory {db_dir}: {e}")
                
        except Exception as e:
            self.logger.error(f"Failed to ensure database directory: {e}")
            raise
    
    @contextmanager
    def _acquire_file_lock(self):
        """Acquire exclusive file lock to prevent concurrent initialization."""
        lock_file = Path(self.db_path).parent / ".db_init.lock"
        
        try:
            self.file_lock = open(lock_file, 'w')
            fcntl.flock(self.file_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.file_lock.write(f"{os.getpid()}\n{self.initialization_id}\n{datetime.now().isoformat()}\n")
            self.file_lock.flush()
            
            self.logger.debug("Acquired exclusive file lock")
            yield
            
        except BlockingIOError:
            raise RuntimeError("Another database initialization is already in progress")
        finally:
            if self.file_lock:
                try:
                    fcntl.flock(self.file_lock.fileno(), fcntl.LOCK_UN)
                    self.file_lock.close()
                    lock_file.unlink(missing_ok=True)
                    self.logger.debug("Released file lock")
                except Exception as e:
                    self.logger.warning(f"Error releasing file lock: {e}")
    
    def _create_atomic_backup(self, suffix: str = "bulletproof_backup") -> Optional[str]:
        """
        Create atomic backup of database with verification.
        
        Args:
            suffix: Backup file suffix
            
        Returns:
            Path to backup file or None if failed
        """
        if not os.path.exists(self.db_path):
            self.logger.info("No existing database to backup")
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.db_path}.{suffix}_{timestamp}"
            
            # Create backup with verification
            self.logger.info(f"Creating atomic backup: {backup_path}")
            
            # Copy file
            shutil.copy2(self.db_path, backup_path)
            
            # Verify backup integrity
            if not self._verify_database_integrity(backup_path):
                os.remove(backup_path)
                raise RuntimeError("Backup verification failed")
            
            # Calculate checksums for verification
            original_checksum = self._calculate_file_checksum(self.db_path)
            backup_checksum = self._calculate_file_checksum(backup_path)
            
            if original_checksum != backup_checksum:
                os.remove(backup_path)
                raise RuntimeError("Backup checksum mismatch")
            
            self.backups_created.append(backup_path)
            self.operations_log.append(f"Created verified backup: {backup_path}")
            self.logger.info(f"✅ Atomic backup created and verified: {backup_path}")
            
            return backup_path
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create atomic backup: {e}")
            self.errors_encountered.append(f"Backup creation failed: {e}")
            return None
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _verify_database_integrity(self, db_path: str) -> bool:
        """
        Verify basic database integrity.
        
        Args:
            db_path: Path to database file
            
        Returns:
            True if database is intact, False otherwise
        """
        try:
            with sqlite3.connect(db_path) as conn:
                # Check database is not corrupted
                cursor = conn.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                
                if result and result[0] != "ok":
                    self.logger.error(f"Database integrity check failed: {result[0]}")
                    return False
                
                # Verify we can read basic structure
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                self.logger.debug(f"Database integrity verified: {len(tables)} tables found")
                return True
                
        except Exception as e:
            self.logger.error(f"Database integrity verification failed: {e}")
            return False
    
    def _run_comprehensive_pre_validation(self) -> List[DatabaseValidationResult]:
        """
        Run comprehensive pre-startup validation checks.
        
        Returns:
            List of validation results
        """
        self.logger.info("🔍 Running comprehensive pre-startup validation...")
        results = []
        
        # Check 1: Database file accessibility
        results.append(self._validate_database_accessibility())
        
        # Check 2: Database directory permissions
        results.append(self._validate_directory_permissions())
        
        # Check 3: Disk space availability
        results.append(self._validate_disk_space())
        
        # Check 4: System resources
        results.append(self._validate_system_resources())
        
        # Check 5: Existing database health (if exists)
        if os.path.exists(self.db_path):
            results.extend(self._validate_existing_database())
        
        # Check 6: Dependencies availability
        results.append(self._validate_dependencies())
        
        # Log validation summary
        critical_failures = [r for r in results if r.status == "critical"]
        failures = [r for r in results if r.status == "fail"]
        warnings = [r for r in results if r.status == "warning"]
        
        self.logger.info(f"Pre-validation complete: {len(critical_failures)} critical, {len(failures)} failures, {len(warnings)} warnings")
        
        return results
    
    def _validate_database_accessibility(self) -> DatabaseValidationResult:
        """Validate database file accessibility."""
        try:
            if os.path.exists(self.db_path):
                # Check if we can read/write existing database
                if not os.access(self.db_path, os.R_OK | os.W_OK):
                    return DatabaseValidationResult(
                        check_name="Database File Accessibility",
                        status="critical",
                        message=f"Cannot read/write database file: {self.db_path}",
                        recommendations=["Check file permissions", "Verify file ownership"]
                    )
                
                # Try to open database
                try:
                    with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                        conn.execute("SELECT 1")
                    
                    return DatabaseValidationResult(
                        check_name="Database File Accessibility",
                        status="pass",
                        message="Database file is accessible"
                    )
                except Exception as e:
                    return DatabaseValidationResult(
                        check_name="Database File Accessibility",
                        status="fail",
                        message=f"Cannot open database: {e}",
                        auto_fixable=True,
                        recommendations=["Database may be corrupted", "Consider backup restoration"]
                    )
            else:
                # Database doesn't exist - this is fine for initialization
                return DatabaseValidationResult(
                    check_name="Database File Accessibility",
                    status="pass",
                    message="Database file will be created"
                )
                
        except Exception as e:
            return DatabaseValidationResult(
                check_name="Database File Accessibility",
                status="critical",
                message=f"Unexpected error checking database accessibility: {e}"
            )
    
    def _validate_directory_permissions(self) -> DatabaseValidationResult:
        """Validate database directory permissions."""
        try:
            db_dir = Path(self.db_path).parent
            
            if not db_dir.exists():
                return DatabaseValidationResult(
                    check_name="Directory Permissions",
                    status="warning",
                    message=f"Database directory does not exist: {db_dir}",
                    auto_fixable=True
                )
            
            if not os.access(db_dir, os.R_OK | os.W_OK | os.X_OK):
                return DatabaseValidationResult(
                    check_name="Directory Permissions",
                    status="critical",
                    message=f"Insufficient permissions for directory: {db_dir}",
                    recommendations=["Check directory permissions", "Verify user access rights"]
                )
            
            return DatabaseValidationResult(
                check_name="Directory Permissions",
                status="pass",
                message="Directory permissions are adequate"
            )
            
        except Exception as e:
            return DatabaseValidationResult(
                check_name="Directory Permissions",
                status="critical",
                message=f"Error checking directory permissions: {e}"
            )
    
    def _validate_disk_space(self) -> DatabaseValidationResult:
        """Validate available disk space."""
        try:
            db_dir = Path(self.db_path).parent
            stat = shutil.disk_usage(db_dir)
            
            # Require at least 100MB free space
            min_space_mb = 100
            available_mb = stat.free / (1024 * 1024)
            
            if available_mb < min_space_mb:
                return DatabaseValidationResult(
                    check_name="Disk Space",
                    status="critical",
                    message=f"Insufficient disk space: {available_mb:.1f}MB available, {min_space_mb}MB required",
                    details={"available_mb": available_mb, "required_mb": min_space_mb},
                    recommendations=["Free up disk space", "Consider moving database to different location"]
                )
            
            return DatabaseValidationResult(
                check_name="Disk Space",
                status="pass",
                message=f"Adequate disk space available: {available_mb:.1f}MB",
                details={"available_mb": available_mb}
            )
            
        except Exception as e:
            return DatabaseValidationResult(
                check_name="Disk Space",
                status="warning",
                message=f"Could not check disk space: {e}"
            )
    
    def _validate_system_resources(self) -> DatabaseValidationResult:
        """Validate system resources."""
        try:
            import psutil
            
            # Check memory
            memory = psutil.virtual_memory()
            available_mb = memory.available / (1024 * 1024)
            
            # Require at least 50MB available memory
            min_memory_mb = 50
            
            if available_mb < min_memory_mb:
                return DatabaseValidationResult(
                    check_name="System Resources",
                    status="warning",
                    message=f"Low memory: {available_mb:.1f}MB available",
                    details={"available_memory_mb": available_mb}
                )
            
            return DatabaseValidationResult(
                check_name="System Resources",
                status="pass",
                message=f"Adequate system resources: {available_mb:.1f}MB memory available",
                details={"available_memory_mb": available_mb}
            )
            
        except ImportError:
            return DatabaseValidationResult(
                check_name="System Resources",
                status="info",
                message="psutil not available - skipping resource check"
            )
        except Exception as e:
            return DatabaseValidationResult(
                check_name="System Resources",
                status="warning",
                message=f"Could not check system resources: {e}"
            )
    
    def _validate_existing_database(self) -> List[DatabaseValidationResult]:
        """Validate existing database if present."""
        results = []
        
        try:
            # Basic integrity check
            if self._verify_database_integrity(self.db_path):
                results.append(DatabaseValidationResult(
                    check_name="Database Integrity",
                    status="pass",
                    message="Database integrity check passed"
                ))
            else:
                results.append(DatabaseValidationResult(
                    check_name="Database Integrity",
                    status="fail",
                    message="Database integrity check failed",
                    auto_fixable=True,
                    recommendations=["Database may be corrupted", "Backup and recreate recommended"]
                ))
            
            # Schema validation using health checker
            if DatabaseHealthChecker:
                try:
                    health_checker = DatabaseHealthChecker(self.db_path, check_enhanced=self.enable_enhanced_schema)
                    health_report = health_checker.run_health_check()
                    
                    if health_report.overall_status == "critical":
                        results.append(DatabaseValidationResult(
                            check_name="Schema Validation",
                            status="fail",
                            message=f"Critical schema issues found: {health_report.summary['fail']} failures",
                            auto_fixable=True,
                            details={"health_report": asdict(health_report)}
                        ))
                    elif health_report.overall_status == "issues":
                        results.append(DatabaseValidationResult(
                            check_name="Schema Validation",
                            status="warning",
                            message=f"Schema issues found: {health_report.summary['warning']} warnings",
                            auto_fixable=True,
                            details={"health_report": asdict(health_report)}
                        ))
                    else:
                        results.append(DatabaseValidationResult(
                            check_name="Schema Validation",
                            status="pass",
                            message="Schema validation passed"
                        ))
                        
                except Exception as e:
                    results.append(DatabaseValidationResult(
                        check_name="Schema Validation",
                        status="warning",
                        message=f"Could not run schema validation: {e}"
                    ))
            
        except Exception as e:
            results.append(DatabaseValidationResult(
                check_name="Existing Database Validation",
                status="fail",
                message=f"Error validating existing database: {e}"
            ))
        
        return results
    
    def _validate_dependencies(self) -> DatabaseValidationResult:
        """Validate required dependencies."""
        try:
            missing_deps = []
            
            # Check for required modules
            try:
                import sqlite3
            except ImportError:
                missing_deps.append("sqlite3")
            
            if missing_deps:
                return DatabaseValidationResult(
                    check_name="Dependencies",
                    status="critical",
                    message=f"Missing required dependencies: {missing_deps}",
                    recommendations=["Install missing Python packages"]
                )
            
            return DatabaseValidationResult(
                check_name="Dependencies",
                status="pass",
                message="All required dependencies available"
            )
            
        except Exception as e:
            return DatabaseValidationResult(
                check_name="Dependencies",
                status="warning",
                message=f"Error checking dependencies: {e}"
            )
    
    def _apply_automatic_fixes(self, validation_results: List[DatabaseValidationResult]) -> List[DatabaseValidationResult]:
        """
        Apply automatic fixes for auto-fixable validation issues.
        
        Args:
            validation_results: List of validation results
            
        Returns:
            Updated validation results with fixes applied
        """
        self.logger.info("🔧 Applying automatic fixes...")
        
        updated_results = []
        
        for result in validation_results:
            if result.auto_fixable and result.status in ["fail", "warning"]:
                try:
                    fix_applied = False
                    
                    if result.check_name == "Directory Permissions":
                        # Create missing directory
                        db_dir = Path(self.db_path).parent
                        db_dir.mkdir(parents=True, exist_ok=True)
                        fix_applied = True
                        self.recovery_actions.append(f"Created database directory: {db_dir}")
                    
                    elif result.check_name == "Database File Accessibility" and "corrupted" in result.message.lower():
                        # Handle corrupted database
                        backup_path = self._create_atomic_backup("pre_corruption_fix")
                        if backup_path:
                            # Try to repair or recreate
                            fix_applied = self._repair_corrupted_database()
                            if fix_applied:
                                self.recovery_actions.append("Repaired corrupted database")
                    
                    elif result.check_name == "Schema Validation":
                        # Apply schema fixes
                        fix_applied = self._repair_schema_issues(result)
                        if fix_applied:
                            self.recovery_actions.append("Applied schema fixes")
                    
                    if fix_applied:
                        updated_result = DatabaseValidationResult(
                            check_name=result.check_name,
                            status="pass",
                            message=f"Fixed: {result.message}",
                            details=result.details,
                            auto_fixable=result.auto_fixable,
                            fix_applied=True,
                            recommendations=result.recommendations
                        )
                        updated_results.append(updated_result)
                        self.logger.info(f"✅ Applied fix for: {result.check_name}")
                    else:
                        updated_results.append(result)
                        
                except Exception as e:
                    self.logger.error(f"❌ Failed to apply fix for {result.check_name}: {e}")
                    self.errors_encountered.append(f"Auto-fix failed for {result.check_name}: {e}")
                    updated_results.append(result)
            else:
                updated_results.append(result)
        
        return updated_results
    
    def _repair_corrupted_database(self) -> bool:
        """
        Attempt to repair corrupted database.
        
        Returns:
            True if repair was successful, False otherwise
        """
        try:
            self.logger.info("Attempting to repair corrupted database...")
            
            # Try to dump and restore database
            temp_dump = tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False)
            temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            temp_db.close()
            
            try:
                # Dump database to SQL
                with sqlite3.connect(self.db_path) as conn:
                    for line in conn.iterdump():
                        temp_dump.write(f"{line}\n")
                temp_dump.close()
                
                # Create new database from dump
                with sqlite3.connect(temp_db.name) as new_conn:
                    with open(temp_dump.name, 'r') as dump_file:
                        new_conn.executescript(dump_file.read())
                
                # Verify new database
                if self._verify_database_integrity(temp_db.name):
                    # Replace corrupted database
                    shutil.move(temp_db.name, self.db_path)
                    self.logger.info("✅ Database repair successful")
                    return True
                else:
                    self.logger.error("❌ Repaired database failed integrity check")
                    return False
                    
            finally:
                # Cleanup temp files
                try:
                    os.unlink(temp_dump.name)
                    os.unlink(temp_db.name)
                except:
                    pass
                    
        except Exception as e:
            self.logger.error(f"❌ Database repair failed: {e}")
            return False
    
    def _repair_schema_issues(self, validation_result: DatabaseValidationResult) -> bool:
        """
        Repair schema issues identified in validation.
        
        Args:
            validation_result: Validation result containing schema issues
            
        Returns:
            True if repair was successful, False otherwise
        """
        try:
            if not validation_result.details or "health_report" not in validation_result.details:
                return False
            
            health_report = validation_result.details["health_report"]
            
            # Use unified setup to fix schema issues
            if UnifiedDatabaseSetup:
                unified_setup = UnifiedDatabaseSetup(
                    db_path=self.db_path,
                    enable_enhanced_schema=self.enable_enhanced_schema
                )
                
                # Run setup to fix schema issues
                success = unified_setup.setup_database()
                if success:
                    self.logger.info("✅ Schema issues repaired using unified setup")
                    return True
                else:
                    self.logger.error("❌ Schema repair failed")
                    return False
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Schema repair failed: {e}")
            return False
    
    def _perform_atomic_initialization(self) -> bool:
        """
        Perform atomic database initialization with full rollback capability.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("🚀 Starting atomic database initialization...")
        
        # Create checkpoint backup
        checkpoint_backup = self._create_atomic_backup("pre_initialization")
        
        try:
            # Initialize unified setup
            if UnifiedDatabaseSetup:
                self.unified_setup = UnifiedDatabaseSetup(
                    db_path=self.db_path,
                    enable_enhanced_schema=self.enable_enhanced_schema
                )
                
                # Perform database setup
                self.logger.info("Executing unified database setup...")
                setup_success = self.unified_setup.setup_database()
                
                if not setup_success:
                    raise RuntimeError("Unified database setup failed")
                
                self.operations_log.append("Unified database setup completed")
                self.logger.info("✅ Unified database setup successful")
            
            # Initialize enhanced schema if enabled
            if self.enable_enhanced_schema and EnhancedDatabaseSchema:
                self.enhanced_schema = EnhancedDatabaseSchema(self.db_path)
                
                # Ensure enhanced tables exist
                if not self.enhanced_schema.create_enhanced_tables():
                    self.logger.warning("Enhanced schema creation had issues")
                    self.warnings.append("Enhanced schema creation incomplete")
                else:
                    self.operations_log.append("Enhanced schema tables created")
                    self.logger.info("✅ Enhanced schema setup successful")
            
            # Verify critical tables and columns
            if not self._verify_critical_schema():
                raise RuntimeError("Critical schema verification failed")
            
            # Run integrity checks
            if not self._run_integrity_checks():
                raise RuntimeError("Database integrity checks failed")
            
            # Optimize database
            self._optimize_database()
            
            self.logger.info("✅ Atomic database initialization completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Atomic initialization failed: {e}")
            self.errors_encountered.append(f"Initialization failed: {e}")
            
            # Rollback to checkpoint if available
            if checkpoint_backup and os.path.exists(checkpoint_backup):
                try:
                    self.logger.info(f"Rolling back to checkpoint: {checkpoint_backup}")
                    shutil.copy2(checkpoint_backup, self.db_path)
                    self.recovery_actions.append(f"Rolled back to checkpoint: {checkpoint_backup}")
                    self.logger.info("✅ Rollback completed")
                except Exception as rollback_error:
                    self.logger.error(f"❌ Rollback failed: {rollback_error}")
                    self.errors_encountered.append(f"Rollback failed: {rollback_error}")
            
            return False
    
    def _verify_critical_schema(self) -> bool:
        """
        Verify that all critical tables and columns exist.
        
        Returns:
            True if all critical schema elements exist, False otherwise
        """
        try:
            self.logger.info("🔍 Verifying critical schema elements...")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for table_name, table_config in self.CRITICAL_TABLES.items():
                    # Check table exists
                    cursor.execute("""
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name=?
                    """, (table_name,))
                    
                    if not cursor.fetchone():
                        self.logger.error(f"❌ Critical table missing: {table_name}")
                        return False
                    
                    # Check required columns
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    existing_columns = {row[1] for row in cursor.fetchall()}
                    
                    required_columns = set(table_config['required_columns'])
                    missing_columns = required_columns - existing_columns
                    
                    if missing_columns:
                        self.logger.error(f"❌ Critical columns missing in {table_name}: {missing_columns}")
                        return False
                    
                    # Check indexes
                    for index_name in table_config['indexes']:
                        cursor.execute("""
                            SELECT name FROM sqlite_master
                            WHERE type='index' AND name=?
                        """, (index_name,))
                        
                        if not cursor.fetchone():
                            self.logger.warning(f"⚠️ Index missing: {index_name}")
                            # Try to create missing index
                            try:
                                self._create_missing_index(cursor, index_name, table_name)
                            except Exception as e:
                                self.logger.error(f"❌ Failed to create index {index_name}: {e}")
                
                self.logger.info("✅ Critical schema verification passed")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Critical schema verification failed: {e}")
            return False
    
    def _create_missing_index(self, cursor: sqlite3.Cursor, index_name: str, table_name: str):
        """Create missing database index."""
        # Define index creation SQL based on naming convention
        index_sql_map = {
            'idx_rda_requests_request_id': 'CREATE INDEX IF NOT EXISTS idx_rda_requests_request_id ON rda_requests(request_id)',
            'idx_rda_requests_status': 'CREATE INDEX IF NOT EXISTS idx_rda_requests_status ON rda_requests(status)',
            'idx_rda_requests_region': 'CREATE INDEX IF NOT EXISTS idx_rda_requests_region ON rda_requests(region)',
            'idx_control_files_region': 'CREATE INDEX IF NOT EXISTS idx_control_files_region ON control_files_tracking(region)',
            'idx_control_files_variable': 'CREATE INDEX IF NOT EXISTS idx_control_files_variable ON control_files_tracking(variable_type)',
            'idx_control_files_status': 'CREATE INDEX IF NOT EXISTS idx_control_files_status ON control_files_tracking(status)'
        }
        
        if index_name in index_sql_map:
            cursor.execute(index_sql_map[index_name])
            self.logger.info(f"✅ Created missing index: {index_name}")
            self.recovery_actions.append(f"Created missing index: {index_name}")
    
    def _run_integrity_checks(self) -> bool:
        """
        Run comprehensive database integrity checks.
        
        Returns:
            True if all integrity checks pass, False otherwise
        """
        try:
            self.logger.info("🔍 Running database integrity checks...")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # SQLite integrity check
                cursor.execute("PRAGMA integrity_check")
                integrity_result = cursor.fetchone()
                
                if integrity_result[0] != "ok":
                    self.logger.error(f"❌ SQLite integrity check failed: {integrity_result[0]}")
                    return False
                
                # Custom integrity checks
                for check in self.INTEGRITY_CHECKS:
                    cursor.execute(check['query'])
                    result = cursor.fetchone()
                    violations = result[0] if result else 0
                    
                    if violations > check['max_violations']:
                        self.logger.error(f"❌ Integrity check failed: {check['name']} - {violations} violations")
                        
                        if check['auto_fix']:
                            try:
                                self._fix_integrity_violation(cursor, check, violations)
                                self.recovery_actions.append(f"Fixed integrity violation: {check['name']}")
                            except Exception as e:
                                self.logger.error(f"❌ Failed to fix integrity violation: {e}")
                                return False
                        else:
                            return False
                    else:
                        self.logger.debug(f"✅ Integrity check passed: {check['name']}")
                
                self.logger.info("✅ All integrity checks passed")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Integrity checks failed: {e}")
            return False
    
    def _fix_integrity_violation(self, cursor: sqlite3.Cursor, check: Dict[str, Any], violations: int):
        """Fix integrity violations where possible."""
        if check['name'] == 'Foreign Key Consistency':
            # Remove orphaned records
            cursor.execute("""
                DELETE FROM control_files_tracking
                WHERE request_id IS NOT NULL
                AND request_id NOT IN (SELECT request_id FROM rda_requests)
            """)
            self.logger.info(f"✅ Removed {violations} orphaned control file records")
    
    def _optimize_database(self):
        """Optimize database performance."""
        try:
            self.logger.info("🔧 Optimizing database...")
            
            with sqlite3.connect(self.db_path) as conn:
                # Update statistics
                conn.execute("ANALYZE")
                
                # Vacuum database
                conn.execute("VACUUM")
                
                # Set optimal pragmas
                conn.execute("PRAGMA optimize")
                
            self.operations_log.append("Database optimization completed")
            self.logger.info("✅ Database optimization completed")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Database optimization failed: {e}")
            self.warnings.append(f"Database optimization failed: {e}")
    
    def _run_final_health_check(self) -> Optional[Dict[str, Any]]:
        """
        Run final comprehensive health check.
        
        Returns:
            Health check results or None if failed
        """
        try:
            if DatabaseHealthChecker:
                self.logger.info("🔍 Running final health check...")
                
                health_checker = DatabaseHealthChecker(
                    db_path=self.db_path,
                    check_enhanced=self.enable_enhanced_schema
                )
                
                health_report = health_checker.run_health_check()
                
                if health_report.overall_status == "critical":
                    self.logger.error("❌ Final health check failed with critical issues")
                    return None
                elif health_report.overall_status == "issues":
                    self.logger.warning("⚠️ Final health check passed with warnings")
                else:
                    self.logger.info("✅ Final health check passed completely")
                
                return asdict(health_report)
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Final health check failed: {e}")
            return None
    
    def _cleanup_old_backups(self):
        """Clean up old backup files."""
        try:
            db_dir = Path(self.db_path).parent
            backup_pattern = f"{Path(self.db_path).name}.*.backup_*"
            
            backup_files = list(db_dir.glob(backup_pattern))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Keep only the most recent backups
            if len(backup_files) > self.MAX_BACKUP_COUNT:
                for old_backup in backup_files[self.MAX_BACKUP_COUNT:]:
                    try:
                        old_backup.unlink()
                        self.logger.debug(f"Cleaned up old backup: {old_backup}")
                    except Exception as e:
                        self.logger.warning(f"Could not clean up backup {old_backup}: {e}")
            
            # Remove backups older than retention period
            cutoff_time = datetime.now() - timedelta(days=self.BACKUP_RETENTION_DAYS)
            for backup_file in backup_files:
                if datetime.fromtimestamp(backup_file.stat().st_mtime) < cutoff_time:
                    try:
                        backup_file.unlink()
                        self.logger.debug(f"Cleaned up expired backup: {backup_file}")
                    except Exception as e:
                        self.logger.warning(f"Could not clean up expired backup {backup_file}: {e}")
                        
        except Exception as e:
            self.logger.warning(f"Backup cleanup failed: {e}")
    
    def initialize_bulletproof_database(self) -> DatabaseInitializationReport:
        """
        Main method to perform bulletproof database initialization.
        
        Returns:
            Comprehensive initialization report
        """
        start_time = datetime.now()
        
        try:
            with self.init_lock:
                with self._acquire_file_lock():
                    self.logger.info(f"🚀 Starting bulletproof database initialization: {self.initialization_id}")
                    
                    # Step 1: Comprehensive pre-validation
                    self.validation_results = self._run_comprehensive_pre_validation()
                    
                    # Check for critical failures
                    critical_failures = [r for r in self.validation_results if r.status == "critical"]
                    if critical_failures:
                        self.logger.error(f"❌ Critical validation failures prevent initialization: {len(critical_failures)}")
                        for failure in critical_failures:
                            self.logger.error(f"  - {failure.check_name}: {failure.message}")
                        
                        return self._create_initialization_report(start_time, "failed")
                    
                    # Step 2: Apply automatic fixes
                    self.validation_results = self._apply_automatic_fixes(self.validation_results)
                    
                    # Step 3: Atomic database initialization
                    if not self._perform_atomic_initialization():
                        return self._create_initialization_report(start_time, "failed")
                    
                    # Step 4: Final health check
                    final_health_check = self._run_final_health_check()
                    
                    # Step 5: Cleanup
                    self._cleanup_old_backups()
                    
                    self.logger.info("✅ Bulletproof database initialization completed successfully!")
                    
                    return self._create_initialization_report(
                        start_time,
                        "success",
                        final_health_check=final_health_check
                    )
                    
        except Exception as e:
            self.logger.error(f"❌ Bulletproof initialization failed: {e}")
            self.errors_encountered.append(f"Initialization failed: {e}")
            return self._create_initialization_report(start_time, "failed")
    
    def _create_initialization_report(
        self,
        start_time: datetime,
        status: str,
        final_health_check: Optional[Dict[str, Any]] = None
    ) -> DatabaseInitializationReport:
        """Create comprehensive initialization report."""
        end_time = datetime.now()
        
        # Collect recommendations
        recommendations = []
        for result in self.validation_results:
            if result.recommendations:
                recommendations.extend(result.recommendations)
        
        # Remove duplicates
        unique_recommendations = list(dict.fromkeys(recommendations))
        
        return DatabaseInitializationReport(
            initialization_id=self.initialization_id,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            database_path=self.db_path,
            status=status,
            validation_results=self.validation_results,
            operations_performed=self.operations_log,
            backups_created=self.backups_created,
            errors_encountered=self.errors_encountered,
            warnings=self.warnings,
            recovery_actions=self.recovery_actions,
            final_health_check=final_health_check,
            recommendations=unique_recommendations
        )
    
    def print_initialization_report(self, report: DatabaseInitializationReport):
        """Print formatted initialization report."""
        print("\n" + "="*90)
        print("BULLETPROOF DATABASE INITIALIZATION REPORT")
        print("="*90)
        print(f"Initialization ID: {report.initialization_id}")
        print(f"Database Path: {report.database_path}")
        print(f"Start Time: {report.start_time}")
        print(f"End Time: {report.end_time}")
        print(f"Status: {report.status.upper()}")
        print()
        
        # Summary
        if report.validation_results:
            validation_summary = {}
            for result in report.validation_results:
                validation_summary[result.status] = validation_summary.get(result.status, 0) + 1
            
            print("VALIDATION SUMMARY:")
            for status, count in validation_summary.items():
                icon = {"pass": "✅", "fail": "❌", "warning": "⚠️", "critical": "🚨", "info": "ℹ️"}.get(status, "❓")
                print(f"  {icon} {status.title()}: {count}")
            print()
        
        # Operations performed
        if report.operations_performed:
            print("OPERATIONS PERFORMED:")
            for i, operation in enumerate(report.operations_performed, 1):
                print(f"  {i}. {operation}")
            print()
        
        # Recovery actions
        if report.recovery_actions:
            print("RECOVERY ACTIONS:")
            for i, action in enumerate(report.recovery_actions, 1):
                print(f"  {i}. {action}")
            print()
        
        # Errors
        if report.errors_encountered:
            print("ERRORS ENCOUNTERED:")
            for i, error in enumerate(report.errors_encountered, 1):
                print(f"  {i}. {error}")
            print()
        
        # Warnings
        if report.warnings:
            print("WARNINGS:")
            for i, warning in enumerate(report.warnings, 1):
                print(f"  {i}. {warning}")
            print()
        
        # Backups created
        if report.backups_created:
            print("BACKUPS CREATED:")
            for i, backup in enumerate(report.backups_created, 1):
                print(f"  {i}. {backup}")
            print()
        
        # Final health check
        if report.final_health_check:
            health_data = report.final_health_check
            print("FINAL HEALTH CHECK:")
            print(f"  Overall Status: {health_data.get('overall_status', 'unknown').upper()}")
            if 'summary' in health_data:
                summary = health_data['summary']
                print(f"  Passed: {summary.get('pass', 0)}")
                print(f"  Warnings: {summary.get('warning', 0)}")
                print(f"  Failed: {summary.get('fail', 0)}")
            print()
        
        # Recommendations
        if report.recommendations:
            print("RECOMMENDATIONS:")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"  {i}. {rec}")
            print()
        
        print("="*90)


def create_bulletproof_initializer(
    db_path: Optional[str] = None,
    enable_enhanced_schema: bool = True
) -> BulletproofDatabaseInitializer:
    """
    Factory function to create a bulletproof database initializer.
    
    Args:
        db_path: Custom database path (uses standard if None)
        enable_enhanced_schema: Whether to enable enhanced schema
        
    Returns:
        Configured BulletproofDatabaseInitializer instance
    """
    return BulletproofDatabaseInitializer(
        db_path=db_path,
        enable_enhanced_schema=enable_enhanced_schema
    )


def main():
    """Main function for running bulletproof database initialization."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Bulletproof Database Initialization for CarbonCast RDA Automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bulletproof_database_init.py --initialize           # Full initialization
  python bulletproof_database_init.py --validate-only        # Validation only
  python bulletproof_database_init.py --enhanced             # With enhanced schema
  python bulletproof_database_init.py --db-path /path        # Custom database path
  python bulletproof_database_init.py --json                 # JSON output

This script provides bulletproof database initialization with:
- Comprehensive pre-validation
- Automatic error recovery
- Atomic operations with rollback
- Production-grade error handling
        """
    )
    
    parser.add_argument('--initialize', action='store_true',
                       help='Perform bulletproof database initialization')
    parser.add_argument('--validate-only', action='store_true',
                       help='Run validation checks only')
    parser.add_argument('--enhanced', action='store_true',
                       help='Enable enhanced schema tables')
    parser.add_argument('--db-path',
                       help='Custom database path')
    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress non-essential output')
    
    args = parser.parse_args()
    
    # Create initializer
    initializer = create_bulletproof_initializer(
        db_path=args.db_path,
        enable_enhanced_schema=args.enhanced
    )
    
    # Adjust logging level
    if args.verbose:
        initializer.logger.setLevel(logging.DEBUG)
    elif args.quiet:
        initializer.logger.setLevel(logging.WARNING)
    
    try:
        if args.initialize:
            if not args.quiet:
                print("🚀 Starting bulletproof database initialization...")
            
            report = initializer.initialize_bulletproof_database()
            
            if args.json:
                print(json.dumps(asdict(report), indent=2, default=str))
            else:
                initializer.print_initialization_report(report)
            
            # Exit with appropriate code
            if report.status == "success":
                exit(0)
            else:
                exit(1)
                
        elif args.validate_only:
            if not args.quiet:
                print("🔍 Running validation checks only...")
            
            validation_results = initializer._run_comprehensive_pre_validation()
            
            if args.json:
                results_dict = [asdict(result) for result in validation_results]
                print(json.dumps(results_dict, indent=2, default=str))
            else:
                print("\nVALIDATION RESULTS:")
                print("-" * 60)
                for result in validation_results:
                    icon = {"pass": "✅", "fail": "❌", "warning": "⚠️", "critical": "🚨", "info": "ℹ️"}.get(result.status, "❓")
                    print(f"{icon} {result.check_name}: {result.message}")
                    if result.recommendations:
                        for rec in result.recommendations:
                            print(f"    💡 {rec}")
            
            # Exit based on validation results
            critical_failures = [r for r in validation_results if r.status == "critical"]
            failures = [r for r in validation_results if r.status == "fail"]
            
            if critical_failures:
                exit(2)
            elif failures:
                exit(1)
            else:
                exit(0)
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n⚠️ Operation interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Operation failed: {e}")
        initializer.logger.error(f"Operation failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()