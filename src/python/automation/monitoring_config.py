#!/usr/bin/env python3
"""
Monitoring Configuration for RDA Automation System

This module provides comprehensive configuration management for the enhanced
request monitoring system, including adaptive monitoring intervals, threshold
management, and integration settings.

Key Features:
- Adaptive monitoring interval configuration
- Request count threshold management
- Event system configuration
- Integration settings for existing components
- Dynamic configuration updates
- Validation and schema enforcement
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MonitoringMode(Enum):
    """Enumeration for monitoring modes."""
    PASSIVE = "passive"          # Monitor only, no actions
    ACTIVE = "active"            # Monitor and take actions
    AGGRESSIVE = "aggressive"    # Aggressive monitoring and actions
    CRISIS = "crisis"           # Crisis mode with emergency actions


class ThresholdType(Enum):
    """Enumeration for threshold types."""
    REQUEST_COUNT = "request_count"
    CAPACITY_UTILIZATION = "capacity_utilization"
    PROCESSING_TIME = "processing_time"
    ERROR_RATE = "error_rate"
    QUEUE_SIZE = "queue_size"


class ActionType(Enum):
    """Enumeration for monitoring actions."""
    LOG_ONLY = "log_only"
    NOTIFY = "notify"
    TRIGGER_PROCESSING = "trigger_processing"
    ADJUST_INTERVALS = "adjust_intervals"
    EMERGENCY_ACTION = "emergency_action"


@dataclass
class ThresholdConfig:
    """Configuration for monitoring thresholds."""
    name: str
    threshold_type: ThresholdType
    value: Union[int, float]
    comparison: str  # "greater_than", "less_than", "equals", "not_equals"
    action: ActionType
    enabled: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdaptiveIntervalConfig:
    """Configuration for adaptive monitoring intervals."""
    base_interval: int = 30  # Base interval in seconds
    min_interval: int = 5    # Minimum interval in seconds
    max_interval: int = 300  # Maximum interval in seconds
    
    # Scaling factors based on request count
    low_activity_multiplier: float = 2.0    # When < 3 requests
    normal_activity_multiplier: float = 1.0  # When 3-7 requests
    high_activity_multiplier: float = 0.5   # When 8-9 requests
    critical_activity_multiplier: float = 0.2  # When >= 10 requests
    
    # Request count thresholds for interval adjustment
    low_activity_threshold: int = 3
    normal_activity_threshold: int = 7
    high_activity_threshold: int = 9
    critical_activity_threshold: int = 10
    
    # Enable adaptive behavior
    enabled: bool = True


@dataclass
class EventSystemConfig:
    """Configuration for event system integration."""
    enabled: bool = True
    max_event_history: int = 1000
    async_dispatch: bool = True
    event_persistence: bool = False
    event_persistence_path: Optional[str] = None
    
    # Event filtering
    enable_event_filtering: bool = True
    high_priority_events_only: bool = False
    
    # Event callbacks
    enable_logging_callback: bool = True
    enable_metrics_callback: bool = True
    enable_notification_callback: bool = False


@dataclass
class IntegrationConfig:
    """Configuration for integration with existing components."""
    # Batch system integration
    batch_system_enabled: bool = True
    batch_system_sync_interval: int = 60
    
    # Capacity manager integration
    capacity_manager_enabled: bool = True
    capacity_manager_sync_interval: int = 30
    
    # Status monitor integration
    status_monitor_enabled: bool = True
    status_monitor_sync_interval: int = 180
    
    # Database integration
    database_enabled: bool = True
    database_path: str = "src/python/data/automation_state.db"
    
    # RDA client integration
    rdams_client_enabled: bool = True
    rdams_client_timeout: int = 30


@dataclass
class NotificationConfig:
    """Configuration for notifications and alerts."""
    enabled: bool = True
    
    # Console notifications
    console_enabled: bool = True
    console_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # File notifications
    file_enabled: bool = True
    file_path: str = "logs/monitoring_alerts.log"
    file_level: str = "WARNING"
    
    # Email notifications (future enhancement)
    email_enabled: bool = False
    email_recipients: List[str] = field(default_factory=list)
    email_smtp_server: str = ""
    email_smtp_port: int = 587
    
    # Webhook notifications (future enhancement)
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_timeout: int = 10


@dataclass
class PerformanceConfig:
    """Configuration for performance optimization."""
    # Threading
    max_worker_threads: int = 5
    thread_pool_timeout: int = 30
    
    # Caching
    enable_caching: bool = True
    cache_ttl: int = 60  # Cache time-to-live in seconds
    max_cache_size: int = 1000
    
    # Rate limiting
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 60
    
    # Memory management
    max_memory_usage_mb: int = 512
    enable_memory_monitoring: bool = True


@dataclass
class EnhancedMonitoringConfig:
    """
    Comprehensive configuration for enhanced request monitoring.
    
    This is the main configuration class that combines all monitoring
    settings and provides validation and management capabilities.
    """
    # Core monitoring settings
    monitoring_mode: MonitoringMode = MonitoringMode.ACTIVE
    enabled: bool = True
    
    # Component configurations
    adaptive_intervals: AdaptiveIntervalConfig = field(default_factory=AdaptiveIntervalConfig)
    event_system: EventSystemConfig = field(default_factory=EventSystemConfig)
    integration: IntegrationConfig = field(default_factory=IntegrationConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    # Thresholds
    thresholds: List[ThresholdConfig] = field(default_factory=list)
    
    # Metadata
    config_version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    description: str = "Enhanced monitoring configuration for RDA automation"
    
    def __post_init__(self):
        """Initialize default thresholds if none provided."""
        if not self.thresholds:
            self.thresholds = self._create_default_thresholds()
    
    def _create_default_thresholds(self) -> List[ThresholdConfig]:
        """Create default monitoring thresholds."""
        return [
            ThresholdConfig(
                name="low_request_count",
                threshold_type=ThresholdType.REQUEST_COUNT,
                value=3,
                comparison="less_than",
                action=ActionType.TRIGGER_PROCESSING,
                description="Trigger processing when request count drops below 3"
            ),
            ThresholdConfig(
                name="approaching_capacity",
                threshold_type=ThresholdType.REQUEST_COUNT,
                value=8,
                comparison="greater_than",
                action=ActionType.ADJUST_INTERVALS,
                description="Adjust monitoring intervals when approaching capacity"
            ),
            ThresholdConfig(
                name="at_capacity",
                threshold_type=ThresholdType.REQUEST_COUNT,
                value=10,
                comparison="greater_than_or_equal",
                action=ActionType.EMERGENCY_ACTION,
                description="Emergency actions when at or over capacity"
            ),
            ThresholdConfig(
                name="high_capacity_utilization",
                threshold_type=ThresholdType.CAPACITY_UTILIZATION,
                value=0.9,
                comparison="greater_than",
                action=ActionType.NOTIFY,
                description="Notify when capacity utilization exceeds 90%"
            )
        ]
    
    def get_threshold_by_name(self, name: str) -> Optional[ThresholdConfig]:
        """Get threshold configuration by name."""
        for threshold in self.thresholds:
            if threshold.name == name:
                return threshold
        return None
    
    def add_threshold(self, threshold: ThresholdConfig) -> bool:
        """Add a new threshold configuration."""
        try:
            # Check if threshold with same name already exists
            if self.get_threshold_by_name(threshold.name):
                return False
            
            self.thresholds.append(threshold)
            self.updated_at = datetime.now().isoformat()
            return True
            
        except Exception:
            return False
    
    def remove_threshold(self, name: str) -> bool:
        """Remove threshold configuration by name."""
        try:
            self.thresholds = [t for t in self.thresholds if t.name != name]
            self.updated_at = datetime.now().isoformat()
            return True
            
        except Exception:
            return False
    
    def update_threshold(self, name: str, **kwargs) -> bool:
        """Update threshold configuration."""
        try:
            threshold = self.get_threshold_by_name(name)
            if not threshold:
                return False
            
            for key, value in kwargs.items():
                if hasattr(threshold, key):
                    setattr(threshold, key, value)
            
            self.updated_at = datetime.now().isoformat()
            return True
            
        except Exception:
            return False
    
    def get_active_thresholds(self) -> List[ThresholdConfig]:
        """Get list of enabled thresholds."""
        return [t for t in self.thresholds if t.enabled]
    
    def calculate_monitoring_interval(self, current_request_count: int) -> int:
        """
        Calculate adaptive monitoring interval based on current request count.
        
        Args:
            current_request_count: Current number of active requests
            
        Returns:
            Monitoring interval in seconds
        """
        if not self.adaptive_intervals.enabled:
            return self.adaptive_intervals.base_interval
        
        # Determine activity level and multiplier
        if current_request_count < self.adaptive_intervals.low_activity_threshold:
            multiplier = self.adaptive_intervals.low_activity_multiplier
        elif current_request_count < self.adaptive_intervals.normal_activity_threshold:
            multiplier = self.adaptive_intervals.normal_activity_multiplier
        elif current_request_count < self.adaptive_intervals.high_activity_threshold:
            multiplier = self.adaptive_intervals.high_activity_multiplier
        else:
            multiplier = self.adaptive_intervals.critical_activity_multiplier
        
        # Calculate interval
        interval = int(self.adaptive_intervals.base_interval * multiplier)
        
        # Apply bounds
        interval = max(self.adaptive_intervals.min_interval, interval)
        interval = min(self.adaptive_intervals.max_interval, interval)
        
        return interval
    
    def validate_configuration(self) -> tuple[bool, List[str]]:
        """
        Validate the configuration for consistency and correctness.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            # Validate adaptive intervals
            if self.adaptive_intervals.min_interval >= self.adaptive_intervals.max_interval:
                errors.append("Minimum interval must be less than maximum interval")
            
            if self.adaptive_intervals.base_interval < self.adaptive_intervals.min_interval:
                errors.append("Base interval must be >= minimum interval")
            
            if self.adaptive_intervals.base_interval > self.adaptive_intervals.max_interval:
                errors.append("Base interval must be <= maximum interval")
            
            # Validate thresholds
            threshold_names = set()
            for threshold in self.thresholds:
                if threshold.name in threshold_names:
                    errors.append(f"Duplicate threshold name: {threshold.name}")
                threshold_names.add(threshold.name)
                
                if threshold.comparison not in [
                    "greater_than", "less_than", "equals", "not_equals", 
                    "greater_than_or_equal", "less_than_or_equal"
                ]:
                    errors.append(f"Invalid comparison operator for threshold {threshold.name}: {threshold.comparison}")
            
            # Validate integration settings
            if self.integration.database_enabled and not self.integration.database_path:
                errors.append("Database path must be specified when database integration is enabled")
            
            # Validate performance settings
            if self.performance.max_worker_threads < 1:
                errors.append("Max worker threads must be at least 1")
            
            if self.performance.cache_ttl < 0:
                errors.append("Cache TTL must be non-negative")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedMonitoringConfig':
        """Create configuration from dictionary."""
        # Handle nested dataclasses
        if 'adaptive_intervals' in data:
            data['adaptive_intervals'] = AdaptiveIntervalConfig(**data['adaptive_intervals'])
        
        if 'event_system' in data:
            data['event_system'] = EventSystemConfig(**data['event_system'])
        
        if 'integration' in data:
            data['integration'] = IntegrationConfig(**data['integration'])
        
        if 'notifications' in data:
            data['notifications'] = NotificationConfig(**data['notifications'])
        
        if 'performance' in data:
            data['performance'] = PerformanceConfig(**data['performance'])
        
        # Handle thresholds
        if 'thresholds' in data:
            thresholds = []
            for threshold_data in data['thresholds']:
                if isinstance(threshold_data, dict):
                    # Convert string enums back to enum objects
                    if 'threshold_type' in threshold_data:
                        threshold_data['threshold_type'] = ThresholdType(threshold_data['threshold_type'])
                    if 'action' in threshold_data:
                        threshold_data['action'] = ActionType(threshold_data['action'])
                    thresholds.append(ThresholdConfig(**threshold_data))
                else:
                    thresholds.append(threshold_data)
            data['thresholds'] = thresholds
        
        # Handle enum fields
        if 'monitoring_mode' in data and isinstance(data['monitoring_mode'], str):
            data['monitoring_mode'] = MonitoringMode(data['monitoring_mode'])
        
        return cls(**data)
    
    def save_to_file(self, file_path: str) -> bool:
        """Save configuration to JSON file."""
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dict and handle enums
            config_dict = self.to_dict()
            
            # Convert enums to strings for JSON serialization
            def convert_enums(obj):
                if isinstance(obj, dict):
                    return {k: convert_enums(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_enums(item) for item in obj]
                elif hasattr(obj, 'value'):  # Enum
                    return obj.value
                else:
                    return obj
            
            config_dict = convert_enums(config_dict)
            
            with open(file_path, 'w') as f:
                json.dump(config_dict, f, indent=2, default=str)
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to save configuration to {file_path}: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, file_path: str) -> Optional['EnhancedMonitoringConfig']:
        """Load configuration from JSON file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            return cls.from_dict(data)
            
        except Exception as e:
            logging.error(f"Failed to load configuration from {file_path}: {e}")
            return None


class MonitoringConfigManager:
    """
    Manager for monitoring configurations with validation and persistence.
    """
    
    def __init__(self, config_dir: str = "config"):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory for configuration files
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.logger = self._setup_logging()
        
        # Current configuration
        self.current_config: Optional[EnhancedMonitoringConfig] = None
        self.config_file_path = self.config_dir / "enhanced_monitoring.json"
        
        self.logger.info("MonitoringConfigManager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the configuration manager."""
        logger = logging.getLogger('rda_automation.monitoring_config_manager')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    def create_default_config(self) -> EnhancedMonitoringConfig:
        """Create a default monitoring configuration."""
        return EnhancedMonitoringConfig()
    
    def load_config(self, file_path: Optional[str] = None) -> bool:
        """
        Load configuration from file.
        
        Args:
            file_path: Optional custom file path
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            config_path = Path(file_path) if file_path else self.config_file_path
            
            if not config_path.exists():
                self.logger.info(f"Configuration file not found: {config_path}, creating default")
                self.current_config = self.create_default_config()
                self.save_config()
                return True
            
            self.current_config = EnhancedMonitoringConfig.load_from_file(str(config_path))
            
            if self.current_config:
                # Validate configuration
                is_valid, errors = self.current_config.validate_configuration()
                if not is_valid:
                    self.logger.error(f"Configuration validation failed: {errors}")
                    return False
                
                self.logger.info(f"✅ Configuration loaded from {config_path}")
                return True
            else:
                self.logger.error(f"❌ Failed to load configuration from {config_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error loading configuration: {e}")
            return False
    
    def save_config(self, file_path: Optional[str] = None) -> bool:
        """
        Save current configuration to file.
        
        Args:
            file_path: Optional custom file path
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            if not self.current_config:
                self.logger.error("No configuration to save")
                return False
            
            config_path = Path(file_path) if file_path else self.config_file_path
            
            # Update timestamp
            self.current_config.updated_at = datetime.now().isoformat()
            
            success = self.current_config.save_to_file(str(config_path))
            
            if success:
                self.logger.info(f"✅ Configuration saved to {config_path}")
            else:
                self.logger.error(f"❌ Failed to save configuration to {config_path}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Error saving configuration: {e}")
            return False
    
    def get_config(self) -> Optional[EnhancedMonitoringConfig]:
        """Get current configuration."""
        return self.current_config
    
    def update_config(self, **kwargs) -> bool:
        """
        Update configuration with new values.
        
        Args:
            **kwargs: Configuration fields to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            if not self.current_config:
                self.logger.error("No configuration loaded")
                return False
            
            for key, value in kwargs.items():
                if hasattr(self.current_config, key):
                    setattr(self.current_config, key, value)
                else:
                    self.logger.warning(f"Unknown configuration field: {key}")
            
            # Validate updated configuration
            is_valid, errors = self.current_config.validate_configuration()
            if not is_valid:
                self.logger.error(f"Updated configuration is invalid: {errors}")
                return False
            
            self.current_config.updated_at = datetime.now().isoformat()
            self.logger.info("✅ Configuration updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error updating configuration: {e}")
            return False


def create_monitoring_config_manager(config_dir: str = "config") -> MonitoringConfigManager:
    """
    Factory function to create a MonitoringConfigManager.
    
    Args:
        config_dir: Directory for configuration files
        
    Returns:
        MonitoringConfigManager instance
    """
    return MonitoringConfigManager(config_dir=config_dir)


def create_default_monitoring_config() -> EnhancedMonitoringConfig:
    """
    Create a default enhanced monitoring configuration.
    
    Returns:
        EnhancedMonitoringConfig with default settings
    """
    return EnhancedMonitoringConfig()


if __name__ == "__main__":
    # Example usage and testing
    
    # Create configuration manager
    config_manager = create_monitoring_config_manager()
    
    # Load or create default configuration
    config_manager.load_config()
    
    # Get current configuration
    config = config_manager.get_config()
    
    if config:
        print("📊 Current monitoring configuration:")
        print(f"  Mode: {config.monitoring_mode.value}")
        print(f"  Enabled: {config.enabled}")
        print(f"  Base interval: {config.adaptive_intervals.base_interval}s")
        print(f"  Active thresholds: {len(config.get_active_thresholds())}")
        
        # Test adaptive interval calculation
        for count in [2, 5, 8, 10, 12]:
            interval = config.calculate_monitoring_interval(count)
            print(f"  Request count {count}: {interval}s interval")
        
        # Validate configuration
        is_valid, errors = config.validate_configuration()
        print(f"  Configuration valid: {is_valid}")
        if errors:
            print(f"  Errors: {errors}")
        
        # Save configuration
        config_manager.save_config()
        print("✅ Configuration saved")
    else:
        print("❌ Failed to load configuration")