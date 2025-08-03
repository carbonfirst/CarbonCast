#!/usr/bin/env python3
"""
Deployment Validation Tests for Enhanced RDA Automation System

This module provides comprehensive deployment validation testing to ensure that the enhanced
automation system can be properly configured, deployed, and started in various environments.

Key Deployment Areas:
- Configuration validation and loading
- System startup and initialization procedures
- Component integration during startup
- Environment-specific configuration handling
- Logging and monitoring setup validation
- Database initialization and migration
- Service health checks and readiness probes
"""

import os
import sys
import json
import time
import logging
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, asdict
from pathlib import Path
import yaml
import sqlite3
from enum import Enum

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import automation components
from automation.enhanced_request_monitor import (
    EnhancedRequestMonitor, create_enhanced_request_monitor
)
from automation.capacity_manager import (
    CapacityManager, CapacityConfig, create_capacity_manager
)
from automation.dynamic_trigger_system import (
    DynamicTriggerSystem, create_dynamic_trigger_system
)
from automation.batch_optimizer import (
    BatchOptimizer, OptimizationConfig, create_batch_optimizer
)
from automation.rate_limiter import (
    RateLimiter, RateLimitConfig, create_rate_limiter
)
from automation.error_handler import (
    ErrorHandler, ErrorHandlingConfig, create_error_handler
)
from automation.request_throttler import (
    RequestThrottler, ThrottlingConfig, create_request_throttler
)
from automation.event_system import (
    EventDispatcher, create_event_dispatcher
)
from automation.monitoring_config import (
    EnhancedMonitoringConfig, MonitoringConfigManager,
    create_default_monitoring_config, create_monitoring_config_manager
)


class DeploymentEnvironment(Enum):
    """Deployment environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DeploymentConfig:
    """Configuration for deployment testing."""
    environment: DeploymentEnvironment
    config_file_path: str
    database_path: str
    log_level: str
    enable_monitoring: bool
    enable_dynamic_processing: bool
    control_files_directory: str
    backup_directory: str


@dataclass
class ComponentStatus:
    """Status of a system component."""
    name: str
    initialized: bool
    healthy: bool
    startup_time: float
    error_message: Optional[str] = None
    configuration_valid: bool = True


@dataclass
class DeploymentTestResult:
    """Result of a deployment test."""
    test_name: str
    success: bool
    environment: DeploymentEnvironment
    component_statuses: List[ComponentStatus]
    startup_time: float
    configuration_issues: List[str]
    recommendations: List[str]
    health_check_passed: bool


class ConfigurationValidator:
    """Validates system configuration for deployment."""
    
    def __init__(self):
        self.logger = logging.getLogger('config_validator')
    
    def validate_monitoring_config(self, config: EnhancedMonitoringConfig) -> Tuple[bool, List[str]]:
        """Validate monitoring configuration."""
        issues = []
        
        # Check basic configuration
        if not config.enabled:
            issues.append("Monitoring is disabled")
        
        # Check adaptive intervals
        if config.adaptive_intervals.min_interval >= config.adaptive_intervals.max_interval:
            issues.append("Invalid adaptive interval configuration: min >= max")
        
        if config.adaptive_intervals.base_interval < 1:
            issues.append("Base monitoring interval too low (< 1 second)")
        
        # Check thresholds
        active_thresholds = config.get_active_thresholds()
        if len(active_thresholds) == 0:
            issues.append("No active monitoring thresholds configured")
        
        # Check event system
        if config.event_system.enabled and not config.event_system.enable_logging_callback:
            issues.append("Event system enabled but logging callback disabled")
        
        return len(issues) == 0, issues
    
    def validate_capacity_config(self, config: CapacityConfig) -> Tuple[bool, List[str]]:
        """Validate capacity management configuration."""
        issues = []
        
        # Check thresholds
        if config.normal_threshold >= config.approaching_threshold:
            issues.append("Invalid capacity thresholds: normal >= approaching")
        
        if config.approaching_threshold >= config.critical_threshold:
            issues.append("Invalid capacity thresholds: approaching >= critical")
        
        # Check upload automation
        if config.enable_upload_automation:
            if config.upload_batch_size <= 0:
                issues.append("Invalid upload batch size (<= 0)")
            
            if config.upload_rate_limit_delay < 0:
                issues.append("Invalid upload rate limit delay (< 0)")
            
            if not os.path.exists(config.control_files_dir):
                issues.append(f"Control files directory does not exist: {config.control_files_dir}")
        
        # Check monitoring interval
        if config.monitoring_interval < 1:
            issues.append("Monitoring interval too low (< 1 second)")
        
        return len(issues) == 0, issues
    
    def validate_rate_limit_config(self, config: RateLimitConfig) -> Tuple[bool, List[str]]:
        """Validate rate limiting configuration."""
        issues = []
        
        # Check rate limits
        if config.requests_per_minute <= 0:
            issues.append("Invalid requests per minute (<= 0)")
        
        if config.requests_per_hour <= 0:
            issues.append("Invalid requests per hour (<= 0)")
        
        # Check consistency
        if config.requests_per_hour < config.requests_per_minute * 60:
            issues.append("Inconsistent rate limits: hourly limit too low")
        
        # Check adaptive settings
        if config.adaptive_enabled:
            if config.min_requests_per_minute >= config.max_requests_per_minute:
                issues.append("Invalid adaptive rate limits: min >= max")
        
        # Check circuit breaker
        if config.circuit_breaker_enabled:
            if config.failure_threshold <= 0:
                issues.append("Invalid circuit breaker failure threshold (<= 0)")
            
            if config.recovery_timeout_seconds <= 0:
                issues.append("Invalid circuit breaker recovery timeout (<= 0)")
        
        # Check backoff settings
        if config.base_backoff_seconds <= 0:
            issues.append("Invalid base backoff seconds (<= 0)")
        
        if config.max_backoff_seconds <= config.base_backoff_seconds:
            issues.append("Invalid backoff settings: max <= base")
        
        return len(issues) == 0, issues
    
    def validate_database_config(self, db_path: str) -> Tuple[bool, List[str]]:
        """Validate database configuration and connectivity."""
        issues = []
        
        try:
            # Check if database directory exists
            db_dir = os.path.dirname(db_path)
            if not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                except Exception as e:
                    issues.append(f"Cannot create database directory: {e}")
                    return False, issues
            
            # Test database connectivity
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Test basic operations
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            if result[0] != 1:
                issues.append("Database connectivity test failed")
            
            conn.close()
            
        except Exception as e:
            issues.append(f"Database validation failed: {e}")
        
        return len(issues) == 0, issues


class SystemInitializer:
    """Handles system initialization and startup procedures."""
    
    def __init__(self, deployment_config: DeploymentConfig):
        self.deployment_config = deployment_config
        self.logger = logging.getLogger('system_initializer')
        self.component_statuses: List[ComponentStatus] = []
    
    def initialize_logging(self) -> ComponentStatus:
        """Initialize logging system."""
        start_time = time.time()
        
        try:
            # Configure logging based on environment
            log_level = getattr(logging, self.deployment_config.log_level.upper())
            
            # Create log directory if needed
            log_dir = os.path.join(os.path.dirname(self.deployment_config.database_path), "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            # Configure logging
            logging.basicConfig(
                level=log_level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(os.path.join(log_dir, 'automation.log'))
                ]
            )
            
            startup_time = time.time() - start_time
            
            return ComponentStatus(
                name="logging",
                initialized=True,
                healthy=True,
                startup_time=startup_time
            )
            
        except Exception as e:
            return ComponentStatus(
                name="logging",
                initialized=False,
                healthy=False,
                startup_time=time.time() - start_time,
                error_message=str(e),
                configuration_valid=False
            )
    
    def initialize_database(self) -> ComponentStatus:
        """Initialize database system."""
        start_time = time.time()
        
        try:
            # Validate database configuration
            validator = ConfigurationValidator()
            is_valid, issues = validator.validate_database_config(self.deployment_config.database_path)
            
            if not is_valid:
                return ComponentStatus(
                    name="database",
                    initialized=False,
                    healthy=False,
                    startup_time=time.time() - start_time,
                    error_message="; ".join(issues),
                    configuration_valid=False
                )
            
            # Initialize database connection
            conn = sqlite3.connect(self.deployment_config.database_path)
            
            # Create basic tables if they don't exist
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_status (
                    id INTEGER PRIMARY KEY,
                    component TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            
            # Insert initialization record
            cursor.execute("""
                INSERT INTO system_status (component, status, timestamp)
                VALUES (?, ?, ?)
            """, ("database", "initialized", datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            startup_time = time.time() - start_time
            
            return ComponentStatus(
                name="database",
                initialized=True,
                healthy=True,
                startup_time=startup_time
            )
            
        except Exception as e:
            return ComponentStatus(
                name="database",
                initialized=False,
                healthy=False,
                startup_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def initialize_monitoring_system(self) -> ComponentStatus:
        """Initialize monitoring system."""
        start_time = time.time()
        
        try:
            if not self.deployment_config.enable_monitoring:
                return ComponentStatus(
                    name="monitoring",
                    initialized=False,
                    healthy=True,
                    startup_time=time.time() - start_time,
                    error_message="Monitoring disabled by configuration"
                )
            
            # Create monitoring configuration
            config = create_default_monitoring_config()
            
            # Validate configuration
            validator = ConfigurationValidator()
            is_valid, issues = validator.validate_monitoring_config(config)
            
            if not is_valid:
                return ComponentStatus(
                    name="monitoring",
                    initialized=False,
                    healthy=False,
                    startup_time=time.time() - start_time,
                    error_message="; ".join(issues),
                    configuration_valid=False
                )
            
            # Create event dispatcher
            event_dispatcher = create_event_dispatcher()
            
            # Create enhanced request monitor
            monitor = create_enhanced_request_monitor(
                config=config,
                event_dispatcher=event_dispatcher,
                db_path=self.deployment_config.database_path
            )
            
            # Test monitor functionality
            snapshot = monitor.create_snapshot()
            if snapshot is None:
                raise Exception("Failed to create monitoring snapshot")
            
            startup_time = time.time() - start_time
            
            return ComponentStatus(
                name="monitoring",
                initialized=True,
                healthy=True,
                startup_time=startup_time
            )
            
        except Exception as e:
            return ComponentStatus(
                name="monitoring",
                initialized=False,
                healthy=False,
                startup_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def initialize_capacity_management(self) -> ComponentStatus:
        """Initialize capacity management system."""
        start_time = time.time()
        
        try:
            # Create capacity configuration
            config = CapacityConfig(
                control_files_dir=self.deployment_config.control_files_directory,
                enable_upload_automation=self.deployment_config.enable_dynamic_processing
            )
            
            # Validate configuration
            validator = ConfigurationValidator()
            is_valid, issues = validator.validate_capacity_config(config)
            
            if not is_valid:
                return ComponentStatus(
                    name="capacity_management",
                    initialized=False,
                    healthy=False,
                    startup_time=time.time() - start_time,
                    error_message="; ".join(issues),
                    configuration_valid=False
                )
            
            # Create capacity manager
            capacity_manager = create_capacity_manager(
                config=config,
                db_path=self.deployment_config.database_path
            )
            
            # Test capacity manager functionality
            status = capacity_manager.get_current_capacity_status()
            if status is None:
                raise Exception("Failed to get capacity status")
            
            startup_time = time.time() - start_time
            
            return ComponentStatus(
                name="capacity_management",
                initialized=True,
                healthy=True,
                startup_time=startup_time
            )
            
        except Exception as e:
            return ComponentStatus(
                name="capacity_management",
                initialized=False,
                healthy=False,
                startup_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def initialize_rate_limiting(self) -> ComponentStatus:
        """Initialize rate limiting system."""
        start_time = time.time()
        
        try:
            # Create rate limiting configuration
            config = RateLimitConfig(
                requests_per_minute=10,
                adaptive_enabled=True,
                circuit_breaker_enabled=True
            )
            
            # Validate configuration
            validator = ConfigurationValidator()
            is_valid, issues = validator.validate_rate_limit_config(config)
            
            if not is_valid:
                return ComponentStatus(
                    name="rate_limiting",
                    initialized=False,
                    healthy=False,
                    startup_time=time.time() - start_time,
                    error_message="; ".join(issues),
                    configuration_valid=False
                )
            
            # Create rate limiter
            rate_limiter = create_rate_limiter(config)
            
            # Test rate limiter functionality
            can_request, wait_time = rate_limiter.can_make_request()
            if can_request is None:
                raise Exception("Failed to check rate limit status")
            
            startup_time = time.time() - start_time
            
            return ComponentStatus(
                name="rate_limiting",
                initialized=True,
                healthy=True,
                startup_time=startup_time
            )
            
        except Exception as e:
            return ComponentStatus(
                name="rate_limiting",
                initialized=False,
                healthy=False,
                startup_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def run_full_initialization(self) -> List[ComponentStatus]:
        """Run full system initialization."""
        self.component_statuses = []
        
        # Initialize components in order
        initialization_order = [
            self.initialize_logging,
            self.initialize_database,
            self.initialize_monitoring_system,
            self.initialize_capacity_management,
            self.initialize_rate_limiting
        ]
        
        for init_func in initialization_order:
            status = init_func()
            self.component_statuses.append(status)
            
            # Stop initialization if critical component fails
            if not status.initialized and status.name in ["logging", "database"]:
                self.logger.error(f"Critical component {status.name} failed to initialize: {status.error_message}")
                break
        
        return self.component_statuses


class HealthChecker:
    """Performs health checks on system components."""
    
    def __init__(self):
        self.logger = logging.getLogger('health_checker')
    
    def check_component_health(self, component_name: str, **kwargs) -> Tuple[bool, str]:
        """Check health of a specific component."""
        try:
            if component_name == "database":
                return self._check_database_health(kwargs.get('db_path'))
            elif component_name == "monitoring":
                return self._check_monitoring_health(kwargs.get('monitor'))
            elif component_name == "capacity_management":
                return self._check_capacity_health(kwargs.get('capacity_manager'))
            elif component_name == "rate_limiting":
                return self._check_rate_limiting_health(kwargs.get('rate_limiter'))
            else:
                return False, f"Unknown component: {component_name}"
                
        except Exception as e:
            return False, f"Health check failed: {e}"
    
    def _check_database_health(self, db_path: str) -> Tuple[bool, str]:
        """Check database health."""
        if not db_path:
            return False, "Database path not provided"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            conn.close()
            
            if table_count > 0:
                return True, f"Database healthy with {table_count} tables"
            else:
                return False, "Database has no tables"
                
        except Exception as e:
            return False, f"Database health check failed: {e}"
    
    def _check_monitoring_health(self, monitor) -> Tuple[bool, str]:
        """Check monitoring system health."""
        if not monitor:
            return False, "Monitor not provided"
        
        try:
            status = monitor.get_current_status()
            if status and status.get('monitoring_active', False):
                return True, "Monitoring system healthy"
            else:
                return False, "Monitoring system not active"
                
        except Exception as e:
            return False, f"Monitoring health check failed: {e}"
    
    def _check_capacity_health(self, capacity_manager) -> Tuple[bool, str]:
        """Check capacity management health."""
        if not capacity_manager:
            return False, "Capacity manager not provided"
        
        try:
            status = capacity_manager.get_current_capacity_status()
            if status and hasattr(status, 'total_requests'):
                return True, f"Capacity management healthy (requests: {status.total_requests})"
            else:
                return False, "Capacity management status unavailable"
                
        except Exception as e:
            return False, f"Capacity health check failed: {e}"
    
    def _check_rate_limiting_health(self, rate_limiter) -> Tuple[bool, str]:
        """Check rate limiting health."""
        if not rate_limiter:
            return False, "Rate limiter not provided"
        
        try:
            status = rate_limiter.get_status()
            if status and hasattr(status, 'current_level'):
                return True, f"Rate limiting healthy (level: {status.current_level.value})"
            else:
                return False, "Rate limiting status unavailable"
                
        except Exception as e:
            return False, f"Rate limiting health check failed: {e}"


class DeploymentValidationTest(unittest.TestCase):
    """Deployment validation tests for the enhanced automation system."""
    
    def setUp(self):
        """Set up deployment testing environment."""
        self.test_start_time = time.time()
        self.temp_dir = tempfile.mkdtemp()
        
        # Set up logging
        self.logger = logging.getLogger('deployment_validation_test')
        self.logger.setLevel(logging.INFO)
        
        # Create test directories
        self.control_files_dir = os.path.join(self.temp_dir, "control_files")
        self.backup_dir = os.path.join(self.temp_dir, "backup")
        self.db_dir = os.path.join(self.temp_dir, "data")
        
        os.makedirs(self.control_files_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.db_dir, exist_ok=True)
        
        # Create test control files
        self._create_test_control_files()
        
        # Initialize components
        self.config_validator = ConfigurationValidator()
        self.health_checker = HealthChecker()
    
    def tearDown(self):
        """Clean up deployment testing environment."""
        try:
            # Clean up temporary directory
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            self.logger.error(f"Error in tearDown: {e}")
    
    def _create_test_control_files(self):
        """Create test control files for deployment testing."""
        for i in range(5):
            control_file_path = os.path.join(self.control_files_dir, f"deploy_test_control_{i:02d}.ctl")
            with open(control_file_path, 'w') as f:
                f.write(f"""# Deployment Test Control File {i}
dataset=ds084.1
startdate=2023010100
enddate=2023010200
param=TMP/UGRD/VGRD
level=2_m_above_ground
region=deploy_test_region_{i}
format=netCDF
""")
    
    def test_development_environment_deployment(self):
        """Test deployment in development environment."""
        self.logger.info("🧪 Testing development environment deployment")
        
        deployment_config = DeploymentConfig(
            environment=DeploymentEnvironment.DEVELOPMENT,
            config_file_path=os.path.join(self.temp_dir, "dev_config.json"),
            database_path=os.path.join(self.db_dir, "dev_automation.db"),
            log_level="DEBUG",
            enable_monitoring=True,
            enable_dynamic_processing=True,
            control_files_directory=self.control_files_dir,
            backup_directory=self.backup_dir
        )
        
        result = self._run_deployment_test(deployment_config)
        
        # Validate development deployment
        self.assertTrue(result.success, f"Development deployment failed: {result.configuration_issues}")
        self.assertTrue(result.health_check_passed, "Health checks failed in development")
        
        # Development should have all features enabled
        monitoring_status = next((s for s in result.component_statuses if s.name == "monitoring"), None)
        self.assertIsNotNone(monitoring_status, "Monitoring component not found")
        self.assertTrue(monitoring_status.initialized, "Monitoring not initialized in development")
        
        self.logger.info("✅ Development environment deployment test passed")
    
    def test_production_environment_deployment(self):
        """Test deployment in production environment."""
        self.logger.info("🧪 Testing production environment deployment")
        
        deployment_config = DeploymentConfig(
            environment=DeploymentEnvironment.PRODUCTION,
            config_file_path=os.path.join(self.temp_dir, "prod_config.json"),
            database_path=os.path.join(self.db_dir, "prod_automation.db"),
            log_level="INFO",
            enable_monitoring=True,
            enable_dynamic_processing=True,
            control_files_directory=self.control_files_dir,
            backup_directory=self.backup_dir
        )
        
        result = self._run_deployment_test(deployment_config)
        
        # Validate production deployment
        self.assertTrue(result.success, f"Production deployment failed: {result.configuration_issues}")
        self.assertTrue(result.health_check_passed, "Health checks failed in production")
        
        # Production should have stricter requirements
        self.assertLess(result.startup_time, 30, "Production startup time too slow")
        
        # All critical components should be healthy
        critical_components = ["database", "monitoring", "capacity_management"]
        for component_name in critical_components:
            component_status = next((s for s in result.component_statuses if s.name == component_name), None)
            self.assertIsNotNone(component_status, f"Critical component {component_name} not found")
            self.assertTrue(component_status.healthy, f"Critical component {component_name} not healthy")
        
        self.logger.info("✅ Production environment deployment test passed")
    
    def test_configuration_validation(self):
        """Test configuration validation for all components."""
        self.logger.info("🧪 Testing configuration validation")
        
        # Test monitoring configuration validation
        monitoring_config = create_default_monitoring_config()
        is_valid, issues = self.config_validator.validate_monitoring_config(monitoring_config)
        self.assertTrue(is_valid, f"Default monitoring config invalid: {issues}")
        
        # Test invalid monitoring configuration
        invalid_monitoring_config = create_default_monitoring_config()
        invalid_monitoring_config.adaptive_intervals.min_interval = 10
        invalid_monitoring_config.adaptive_intervals.max_interval = 5  # Invalid: min > max
        
        is_valid, issues = self.config_validator.validate_monitoring_config(invalid_monitoring_config)
        self.assertFalse(is_valid, "Invalid monitoring config should be rejected")
        self.assertGreater(len(issues), 0, "Should have validation issues")
        
        # Test capacity configuration validation
        capacity_config = CapacityConfig(control_files_dir=self.control_files_dir)
        is_valid, issues = self.config_validator.validate_capacity_config(capacity_config)
        self.assertTrue(is_valid, f"Default capacity config invalid: {issues}")
        
        # Test rate limiting configuration validation
        rate_config = RateLimitConfig()
        is_valid, issues = self.config_validator.validate_rate_limit_config(rate_config)
        self.assertTrue(is_valid, f"Default rate limit config invalid: {issues}")
        
        # Test database configuration validation
        db_path = os.path.join(self.db_dir, "test_validation.db")
        is_valid, issues = self.config_validator.validate_database_config(db_path)
        self.assertTrue(is_valid, f"Database config invalid: {issues}")
        
        self.logger.info("✅ Configuration validation test passed")
    
    def test_system_startup_procedures(self):
        """Test system startup and initialization procedures."""
        self.logger.info("🧪 Testing system startup procedures")
        
        deployment_config = DeploymentConfig(
            environment=DeploymentEnvironment.TESTING,
            config_file_path=os.path.join(self.temp_dir, "test_config.json"),
            database_path=os.path.join(self.db_dir, "test_automation.db"),
            log_level="INFO",
            enable_monitoring=True,
            enable_dynamic_processing=True,
            control_files_directory=self.control_files_dir,
            backup_directory=self.backup_dir
        )
        
        # Test system initialization
        initializer = SystemInitializer(deployment_config)
        component_statuses = initializer.run_full_initialization()
        
        # Validate initialization results
        self.assertGreater(len(component_statuses), 0, "No components initialized")
        
        # Check that critical components initialized successfully
        critical_components = ["logging", "database"]
        for component_name in critical_components:
            component_status = next((s for s in component_statuses if s.name == component_name), None)
            self.assertIsNotNone(component_status, f"Critical component {component_name} not initialized")
            self.assertTrue(component_status.initialized, f"Critical component {component_name} failed to initialize")
        
        # Check startup times are reasonable
        for status in component_statuses:
            if status.initialized:
                self.assertLess(status.startup_time, 10, f"Component {status.name} startup time too slow: {status.startup_time:.2f}s")
        
        self.logger.info("✅ System startup procedures test passed")
    
    def test_component_health_checks(self):
        """Test health checks for all system components."""
        self.logger.info("🧪 Testing component health checks")
        
        # Test database health check
        db_path = os.path.join(self.db_dir, "health_test.db")
        
        # Initialize database
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        
        is_healthy, message = self.health_checker.check_component_health("database", db_path=db_path)
        self.assertTrue(is_healthy, f"Database health check failed: {message}")
        
        # Test health check with non-existent database
        is_healthy, message = self.health_checker.check_component_health("database", db_path="/nonexistent/path.db")
        self.assertFalse(is_healthy, "Health check should fail for non-existent database")
        
        # Test monitoring health check (mock)
        mock_monitor = Mock()
        mock_monitor.get_current_status.return_value = {"monitoring_active": True}
        
        is_healthy, message = self.health_checker.check_component_health("monitoring", monitor=mock_monitor)
        self.assertTrue(is_healthy, f"Monitoring health check failed: {message}")
        
        # Test capacity management health check (mock)
        mock_capacity = Mock()
        mock_status = Mock()
        mock_status.total_requests = 5
        mock_capacity.get_current_capacity_status.return_value = mock_status
        
        is_healthy, message = self.health_checker.check_component_health("capacity_management", capacity_manager=mock_capacity)
        self.assertTrue(is_healthy, f"Capacity management health check failed: {message}")
        
        self.logger.info("✅ Component health checks test passed")
    
    def test_environment_specific_configurations(self):
        """Test environment-specific configuration handling."""
        self.logger.info("🧪 Testing environment-specific configurations")
        
        environments = [
            (DeploymentEnvironment.DEVELOPMENT, "DEBUG", True, True),
            (DeploymentEnvironment.TESTING, "INFO", True, True),
            (DeploymentEnvironment.STAGING, "INFO", True, False),
            (DeploymentEnvironment.PRODUCTION, "WARNING", True, False)
        ]
        
        for env, log_level, monitoring_enabled, dynamic_enabled in environments:
            deployment_config = DeploymentConfig(
                environment=env,
                config_file_path=os.path.join(self.temp_dir, f"{env.value}_config.json"),
                database_path=os.path.join(self.db_dir, f"{env.value}_automation.db"),
                log_level=log_level,
                enable_monitoring=monitoring_enabled,
                enable_dynamic_processing=dynamic_enabled,
                control_files_directory=self.control_files_dir,
                backup_directory=self.backup_dir
            )
            
            result = self._run_deployment_test(deployment_config)
            
            # Validate environment-specific requirements
            self.assertTrue(result.success, f"{env.value} deployment failed: {result.configuration_issues}")
            
            # Check log level configuration
            if env == DeploymentEnvironment.PRODUCTION:
                self.assertLessEqual(result.startup_time, 30, f"Production startup too slow: {result.startup_time:.2f}s")
            
            # Check monitoring configuration
            monitoring_status = next((s for s in result.component_statuses if s.name == "monitoring"), None)
            if monitoring_enabled:
                self.assertIsNotNone(monitoring_status, f"Monitoring component missing in {env.value}")
                self.assertTrue(monitoring_status.initialized, f"Monitoring not initialized in {env.value}")
        
        self.logger.info("✅ Environment-specific configurations test passed")
    
    def test_logging_and_monitoring_setup(self):
        """Test logging and monitoring system setup validation."""
        self.logger.info("🧪 Testing logging and monitoring setup")
        
        deployment_config = DeploymentConfig(
            environment=DeploymentEnvironment.TESTING,
            config_file_path=os.path.join(self.temp_dir, "logging_test_config.json"),
            database_path=os.path.join(self.db_dir, "logging_test_automation.db"),
            log_level="DEBUG",
            enable_monitoring=True,
            enable_dynamic_processing=True,
            control_files_directory=self.control_files_dir,
            backup_directory=self.backup_dir
        )
        
        # Test logging initialization
        initializer = SystemInitializer(deployment_config)
        logging_status = initializer.initialize_logging()
        
        self.assertTrue(logging_status.initialized, f"Logging initialization failed: {logging_status.error_message}")
        self.assertTrue(logging_status.healthy, "Logging system not healthy")
        
        # Test monitoring initialization
        monitoring_status = initializer.initialize_monitoring_system()
        
        self.assertTrue(monitoring_status.initialized, f"Monitoring initialization failed: {monitoring_status.error_message}")
        self.assertTrue(monitoring_status.healthy, "Monitoring system not healthy")
        
        self.logger.info("✅ Logging and monitoring setup test passed")
    
    def test_database_initialization_and_migration(self):
        """Test database initialization and migration procedures."""
        self.logger.info("🧪 Testing database initialization and migration")
        
        db_path = os.path.join(self.db_dir, "migration_test.db")
        
        deployment_config = DeploymentConfig(
            environment=DeploymentEnvironment.TESTING,
            config_file_path=os.path.join(self.temp_dir, "db_test_config.json"),
            database_path=db_path,
            log_level="INFO",
            enable_monitoring=True,
            enable_dynamic_processing=True,
            control_files_directory=self.control_files_dir,
            backup_directory=self.backup_dir
        )
        
        # Test database initialization
        initializer = SystemInitializer(deployment_config)
        db_status = initializer.initialize_database()
        
        self.assertTrue(db_status.initialized, f"Database initialization failed: {db_status.error_message}")
        self.assertTrue(db_status.healthy, "Database not healthy after initialization")
        
        # Verify database was created and has expected structure
        self.assertTrue(os.path.exists(db_path), "Database file not created")
        
        # Test database connectivity and structure
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if system_status table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_status'")
        table_exists = cursor.fetchone()
        self.assertIsNotNone(table_exists, "system_status table not created")
        
        # Check if initialization record exists
        cursor.execute("SELECT COUNT(*) FROM system_status WHERE component='database' AND status='initialized'")
        record_count = cursor.fetchone()[0]
        self.assertGreater(record_count, 0, "Database initialization record not found")
        
        conn.close()
        
        self.logger.info("✅ Database initialization and migration test passed")
    
    def _run_deployment_test(self, deployment_config: DeploymentConfig) -> DeploymentTestResult:
        """Run a complete deployment test with the given configuration."""
        start_time = time.time()
        
        # Initialize system
        initializer = SystemInitializer(deployment_config)
        component_statuses = initializer.run_full_initialization()
        
        # Run health checks
        health_checker = HealthChecker()
        health_check_passed = True
        
        for status in component_statuses:
            if status.initialized and status.healthy:
                # Run component-specific health check
                if status.name == "database":
                    is_healthy, _ = health_checker.check_component_health("database", db_path=deployment_config.database_path)
                    if not is_healthy:
                        health_check_passed = False
        
        # Collect configuration issues
        configuration_issues = []
        for status in component_statuses:
            if not status.configuration_valid and status.error_message:
                configuration_issues.append(f"{status.name}: {status.error_message}")
        
        # Generate recommendations
        recommendations = []
        if not health_check_passed:
            recommendations.append("Review component health check failures")
        
        failed_components = [s for s in component_statuses if not s.initialized]
        if failed_components:
            recommendations.append(f"Fix failed components: {', '.join(s.name for s in failed_components)}")
        
        startup_time = time.time() - start_time
        
        return DeploymentTestResult(
            test_name=f"{deployment_config.environment.value}_deployment",
            success=len(configuration_issues) == 0 and health_check_passed,
            environment=deployment_config.environment,
            component_statuses=component_statuses,
            startup_time=startup_time,
            configuration_issues=configuration_issues,
            recommendations=recommendations,
            health_check_passed=health_check_passed
        )


class DeploymentTestRunner:
    """Orchestrates deployment validation tests."""
    
    def __init__(self):
        self.logger = logging.getLogger('deployment_test_runner')
    
    def run_all_deployment_tests(self) -> Dict[str, Any]:
        """Run all deployment validation tests."""
        self.logger.info("🚀 Running all deployment validation tests")
        
        # Define all deployment tests
        test_methods = [
            'test_development_environment_deployment',
            'test_production_environment_deployment',
            'test_configuration_validation',
            'test_system_startup_procedures',
            'test_component_health_checks',
            'test_environment_specific_configurations',
            'test_logging_and_monitoring_setup',
            'test_database_initialization_and_migration'
        ]
        
        test_results = {}
        total_execution_time = 0
        
        for test_name in test_methods:
            self.logger.info(f"Running deployment test: {test_name}")
            
            # Create test suite with specific test
            suite = unittest.TestSuite()
            suite.addTest(DeploymentValidationTest(test_name))
            
            # Run test
            start_time = time.time()
            test_result = unittest.TextTestRunner(verbosity=1).run(suite)
            execution_time = time.time() - start_time
            total_execution_time += execution_time
            
            test_results[test_name] = {
                "success": test_result.wasSuccessful(),
                "execution_time": execution_time,
                "failures": len(test_result.failures),
                "errors": len(test_result.errors),
                "failure_messages": [str(failure[1]) for failure in test_result.failures],
                "error_messages": [str(error[1]) for error in test_result.errors]
            }
        
        # Calculate overall success metrics
        successful_tests = len([r for r in test_results.values() if r["success"]])
        total_tests = len(test_results)
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        
        return {
            "test_results": test_results,
            "overall_success": success_rate >= 90,  # 90% threshold
            "success_rate": success_rate,
            "successful_tests": successful_tests,
            "total_tests": total_tests,
            "total_execution_time": total_execution_time,
            "deployment_ready": success_rate >= 90 and successful_tests == total_tests,
            "timestamp": datetime.now().isoformat()
        }
    
    def run_deployment_readiness_check(self) -> Dict[str, Any]:
        """Run deployment readiness check with critical tests only."""
        self.logger.info("🔍 Running deployment readiness check")
        
        # Critical tests for deployment readiness
        readiness_tests = [
            'test_configuration_validation',
            'test_system_startup_procedures',
            'test_component_health_checks',
            'test_database_initialization_and_migration'
        ]
        
        readiness_results = {}
        
        for test_name in readiness_tests:
            self.logger.info(f"Running readiness test: {test_name}")
            
            # Create test suite with specific test
            suite = unittest.TestSuite()
            suite.addTest(DeploymentValidationTest(test_name))
            
            # Run test
            start_time = time.time()
            test_result = unittest.TextTestRunner(verbosity=1).run(suite)
            execution_time = time.time() - start_time
            
            readiness_results[test_name] = {
                "success": test_result.wasSuccessful(),
                "execution_time": execution_time,
                "failures": len(test_result.failures),
                "errors": len(test_result.errors)
            }
        
        # Calculate overall readiness score
        successful_tests = len([r for r in readiness_results.values() if r["success"]])
        total_tests = len(readiness_results)
        readiness_score = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        
        return {
            "readiness_results": readiness_results,
            "overall_readiness": readiness_score >= 90,  # 90% threshold
            "readiness_score": readiness_score,
            "total_execution_time": sum(r["execution_time"] for r in readiness_results.values()),
            "deployment_ready": readiness_score >= 90 and successful_tests == total_tests,
            "timestamp": datetime.now().isoformat()
        }


def main():
    """Main function for running deployment validation tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deployment Validation Tests')
    parser.add_argument('--test', type=str, help='Run specific deployment test')
    parser.add_argument('--readiness', action='store_true', help='Run deployment readiness check')
    parser.add_argument('--report', action='store_true', help='Generate detailed deployment report')
    parser.add_argument('--quick', action='store_true', help='Run quick deployment tests')
    parser.add_argument('--environment', type=str, choices=['development', 'testing', 'staging', 'production'],
                       help='Test specific environment deployment')
    
    args = parser.parse_args()
    
    runner = DeploymentTestRunner()
    
    try:
        if args.test:
            # Run specific test
            suite = unittest.TestSuite()
            suite.addTest(DeploymentValidationTest(args.test))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            
            print(f"Test {args.test}: {'✅ PASSED' if result.wasSuccessful() else '❌ FAILED'}")
        
        elif args.readiness:
            # Run readiness check
            result = runner.run_deployment_readiness_check()
            
            print("\n" + "="*60)
            print("DEPLOYMENT READINESS CHECK RESULTS")
            print("="*60)
            print(json.dumps(result, indent=2))
            print("="*60)
            
            if result["deployment_ready"]:
                print("🚀 System is ready for deployment!")
            else:
                print("⚠️ System is not ready for deployment. Please address issues above.")
        
        elif args.environment:
            # Test specific environment
            print(f"=== Testing {args.environment.title()} Environment Deployment ===")
            
            if args.environment == 'development':
                test_name = 'test_development_environment_deployment'
            elif args.environment == 'production':
                test_name = 'test_production_environment_deployment'
            else:
                test_name = 'test_environment_specific_configurations'
            
            suite = unittest.TestSuite()
            suite.addTest(DeploymentValidationTest(test_name))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            
            print(f"{args.environment.title()} deployment: {'✅ PASSED' if result.wasSuccessful() else '❌ FAILED'}")
        
        elif args.quick:
            # Run quick deployment tests
            print("=== Quick Deployment Test Suite ===")
            quick_tests = [
                'test_configuration_validation',
                'test_system_startup_procedures'
            ]
            
            for test_name in quick_tests:
                suite = unittest.TestSuite()
                suite.addTest(DeploymentValidationTest(test_name))
                result = unittest.TextTestRunner(verbosity=1).run(suite)
                print(f"{test_name}: {'✅ PASSED' if result.wasSuccessful() else '❌ FAILED'}")
        
        else:
            # Run all deployment tests
            result = runner.run_all_deployment_tests()
            
            if args.report:
                print("\n" + "="*60)
                print("DEPLOYMENT VALIDATION TEST REPORT")
                print("="*60)
                print(json.dumps(result, indent=2))
                print("="*60)
    
    except Exception as e:
        print(f"Error running deployment validation tests: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())