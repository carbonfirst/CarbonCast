#!/usr/bin/env python3
"""
Configuration Manager for RDA Automation System

This module provides comprehensive configuration management capabilities,
including loading, validation, merging, and dynamic updating of system
configurations. It supports multiple configuration sources and formats.

Key Features:
- Multi-source configuration loading (files, environment, defaults)
- Configuration validation and schema enforcement
- Dynamic configuration updates and hot-reloading
- Environment-specific configuration profiles
- Configuration versioning and rollback
- Secure handling of sensitive configuration data
- Configuration change notifications and callbacks
"""

import os
import sys
import json
import yaml
import logging
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from copy import deepcopy
import hashlib

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger


class ConfigurationSource(Enum):
    """Enumeration for configuration sources."""
    DEFAULT = "default"
    FILE = "file"
    ENVIRONMENT = "environment"
    DATABASE = "database"
    REMOTE = "remote"
    OVERRIDE = "override"


class ConfigurationFormat(Enum):
    """Enumeration for configuration formats."""
    JSON = "json"
    YAML = "yaml"
    INI = "ini"
    ENV = "env"


@dataclass
class ConfigurationSchema:
    """Schema definition for configuration validation."""
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    field_types: Dict[str, type] = field(default_factory=dict)
    field_validators: Dict[str, Callable] = field(default_factory=dict)
    nested_schemas: Dict[str, 'ConfigurationSchema'] = field(default_factory=dict)


@dataclass
class ConfigurationProfile:
    """Configuration profile for different environments."""
    name: str
    description: str
    config_data: Dict[str, Any]
    source: ConfigurationSource
    format: ConfigurationFormat
    file_path: Optional[str] = None
    last_modified: Optional[str] = None
    checksum: Optional[str] = None


@dataclass
class ConfigurationChange:
    """Record of a configuration change."""
    timestamp: str
    profile_name: str
    field_path: str
    old_value: Any
    new_value: Any
    source: ConfigurationSource
    user: Optional[str] = None


class ConfigurationManager:
    """
    Advanced configuration management system.
    
    Provides comprehensive configuration management including loading from
    multiple sources, validation, dynamic updates, and change tracking.
    """
    
    def __init__(self, 
                 config_dir: str = "config",
                 enable_hot_reload: bool = True,
                 enable_change_tracking: bool = True):
        """
        Initialize the Configuration Manager.
        
        Args:
            config_dir: Directory containing configuration files
            enable_hot_reload: Whether to enable automatic reloading
            enable_change_tracking: Whether to track configuration changes
        """
        self.logger = self._setup_logging()
        self.config_dir = Path(config_dir)
        self.enable_hot_reload = enable_hot_reload
        self.enable_change_tracking = enable_change_tracking
        
        # Configuration storage
        self.profiles: Dict[str, ConfigurationProfile] = {}
        self.active_profile: Optional[str] = None
        self.merged_config: Dict[str, Any] = {}
        
        # Schema and validation
        self.schemas: Dict[str, ConfigurationSchema] = {}
        self.validation_enabled = True
        
        # Change tracking
        self.change_history: List[ConfigurationChange] = []
        self.max_change_history = 1000
        self.change_callbacks: List[Callable] = []
        
        # Hot reload
        self.file_watchers: Dict[str, float] = {}  # file_path -> last_modified
        self.reload_thread: Optional[threading.Thread] = None
        self.reload_active = False
        
        # Thread safety
        self.config_lock = threading.RLock()
        
        # Environment variables prefix
        self.env_prefix = "RDA_"
        
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("Configuration Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.configuration_manager', level=logging.INFO)
    
    def register_schema(self, profile_name: str, schema: ConfigurationSchema) -> bool:
        """
        Register a configuration schema for validation.
        
        Args:
            profile_name: Name of the configuration profile
            schema: Configuration schema
            
        Returns:
            True if registration was successful, False otherwise
        """
        try:
            with self.config_lock:
                self.schemas[profile_name] = schema
            
            self.logger.info(f"✅ Schema registered for profile: {profile_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to register schema for {profile_name}: {e}")
            return False
    
    def load_configuration_file(self, 
                              file_path: str, 
                              profile_name: Optional[str] = None,
                              format: Optional[ConfigurationFormat] = None) -> bool:
        """
        Load configuration from a file.
        
        Args:
            file_path: Path to the configuration file
            profile_name: Name for the configuration profile
            format: Configuration format (auto-detected if None)
            
        Returns:
            True if loading was successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                self.logger.error(f"❌ Configuration file not found: {file_path}")
                return False
            
            # Auto-detect format if not specified
            if format is None:
                format = self._detect_file_format(file_path)
            
            # Auto-generate profile name if not specified
            if profile_name is None:
                profile_name = file_path.stem
            
            # Load configuration data
            config_data = self._load_file_data(file_path, format)
            
            if config_data is None:
                return False
            
            # Create configuration profile
            profile = ConfigurationProfile(
                name=profile_name,
                description=f"Configuration loaded from {file_path}",
                config_data=config_data,
                source=ConfigurationSource.FILE,
                format=format,
                file_path=str(file_path),
                last_modified=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                checksum=self._calculate_file_checksum(file_path)
            )
            
            # Validate configuration if schema exists
            if self.validation_enabled and profile_name in self.schemas:
                if not self._validate_configuration(config_data, self.schemas[profile_name]):
                    self.logger.error(f"❌ Configuration validation failed for {profile_name}")
                    return False
            
            with self.config_lock:
                self.profiles[profile_name] = profile
                
                # Add to file watchers for hot reload
                if self.enable_hot_reload:
                    self.file_watchers[str(file_path)] = file_path.stat().st_mtime
            
            self.logger.info(f"✅ Configuration loaded from {file_path} as profile '{profile_name}'")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load configuration from {file_path}: {e}")
            return False
    
    def load_environment_configuration(self, profile_name: str = "environment") -> bool:
        """
        Load configuration from environment variables.
        
        Args:
            profile_name: Name for the environment configuration profile
            
        Returns:
            True if loading was successful, False otherwise
        """
        try:
            config_data = {}
            
            # Load environment variables with the specified prefix
            for key, value in os.environ.items():
                if key.startswith(self.env_prefix):
                    # Remove prefix and convert to lowercase
                    config_key = key[len(self.env_prefix):].lower()
                    
                    # Convert nested keys (e.g., RDA_DB_HOST -> db.host)
                    config_path = config_key.split('_')
                    
                    # Set nested value
                    current_dict = config_data
                    for path_part in config_path[:-1]:
                        if path_part not in current_dict:
                            current_dict[path_part] = {}
                        current_dict = current_dict[path_part]
                    
                    # Try to parse value as JSON, fall back to string
                    try:
                        parsed_value = json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        parsed_value = value
                    
                    current_dict[config_path[-1]] = parsed_value
            
            # Create configuration profile
            profile = ConfigurationProfile(
                name=profile_name,
                description="Configuration loaded from environment variables",
                config_data=config_data,
                source=ConfigurationSource.ENVIRONMENT,
                format=ConfigurationFormat.ENV,
                last_modified=datetime.now().isoformat()
            )
            
            with self.config_lock:
                self.profiles[profile_name] = profile
            
            self.logger.info(f"✅ Environment configuration loaded as profile '{profile_name}'")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load environment configuration: {e}")
            return False
    
    def create_default_configuration(self, profile_name: str = "default") -> bool:
        """
        Create a default configuration profile.
        
        Args:
            profile_name: Name for the default configuration profile
            
        Returns:
            True if creation was successful, False otherwise
        """
        try:
            # Default RDA automation configuration
            default_config = {
                "database": {
                    "path": "src/python/data/automation_state.db",
                    "backup_enabled": True,
                    "backup_interval": 3600,
                    "enable_enhanced_schema": True,
                    "auto_migrate": True,
                    "legacy_paths": [
                        "data/automation_state.db",
                        "src/python/automation/data/automation_state.db",
                        "automation_state.db"
                    ]
                },
                "file_system": {
                    "control_files_dir": "src/python/control_files",
                    "base_download_dir": "downloaded_files",
                    "temp_download_dir": "./temp_downloads",
                    "reports_dir": "reports",
                    "logs_dir": "logs"
                },
                "processing": {
                    "enable_sequential_processing": True,
                    "enable_smart_retry": True,
                    "enable_error_tracking": True,
                    "enable_dashboard": True,
                    "enable_completion_notifications": True,
                    "enable_capacity_management": True,
                    "enable_automated_requests": True,
                    "enable_data_sync": True,
                    "enable_workflow_orchestration": True
                },
                "timing": {
                    "main_cycle_interval": 300,
                    "status_check_interval": 60,
                    "data_sync_interval": 900,
                    "maintenance_interval": 3600
                },
                "performance": {
                    "max_concurrent_operations": 5,
                    "max_retry_attempts": 3,
                    "request_timeout": 1800,
                    "max_workers": 10
                },
                "features": {
                    "debug_mode": False,
                    "enable_detailed_logging": True,
                    "enable_performance_monitoring": True,
                    "enable_health_checks": True
                },
                "notifications": {
                    "enable_email_notifications": False,
                    "email_recipients": [],
                    "enable_console_notifications": True,
                    "enable_file_reports": True
                }
            }
            
            # Create configuration profile
            profile = ConfigurationProfile(
                name=profile_name,
                description="Default RDA automation configuration",
                config_data=default_config,
                source=ConfigurationSource.DEFAULT,
                format=ConfigurationFormat.JSON,
                last_modified=datetime.now().isoformat()
            )
            
            with self.config_lock:
                self.profiles[profile_name] = profile
            
            self.logger.info(f"✅ Default configuration created as profile '{profile_name}'")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create default configuration: {e}")
            return False
    
    def set_active_profile(self, profile_name: str) -> bool:
        """
        Set the active configuration profile.
        
        Args:
            profile_name: Name of the profile to activate
            
        Returns:
            True if activation was successful, False otherwise
        """
        try:
            with self.config_lock:
                if profile_name not in self.profiles:
                    self.logger.error(f"❌ Profile '{profile_name}' not found")
                    return False
                
                old_profile = self.active_profile
                self.active_profile = profile_name
                self._rebuild_merged_config()
            
            self.logger.info(f"✅ Active profile changed: {old_profile} -> {profile_name}")
            
            # Notify change callbacks
            self._notify_configuration_change("active_profile", old_profile, profile_name)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to set active profile to '{profile_name}': {e}")
            return False
    
    def merge_profiles(self, profile_names: List[str], target_profile: str = "merged") -> bool:
        """
        Merge multiple configuration profiles into a single profile.
        
        Args:
            profile_names: List of profile names to merge (in priority order)
            target_profile: Name for the merged profile
            
        Returns:
            True if merging was successful, False otherwise
        """
        try:
            merged_config = {}
            
            with self.config_lock:
                # Merge profiles in order (later profiles override earlier ones)
                for profile_name in profile_names:
                    if profile_name not in self.profiles:
                        self.logger.warning(f"⚠️ Profile '{profile_name}' not found, skipping")
                        continue
                    
                    profile_config = self.profiles[profile_name].config_data
                    merged_config = self._deep_merge_dicts(merged_config, profile_config)
                
                # Create merged profile
                merged_profile = ConfigurationProfile(
                    name=target_profile,
                    description=f"Merged configuration from: {', '.join(profile_names)}",
                    config_data=merged_config,
                    source=ConfigurationSource.OVERRIDE,
                    format=ConfigurationFormat.JSON,
                    last_modified=datetime.now().isoformat()
                )
                
                self.profiles[target_profile] = merged_profile
            
            self.logger.info(f"✅ Profiles merged into '{target_profile}': {profile_names}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to merge profiles: {e}")
            return False
    
    def get_configuration(self, key_path: Optional[str] = None, default: Any = None) -> Any:
        """
        Get configuration value by key path.
        
        Args:
            key_path: Dot-separated path to the configuration key (e.g., "database.path")
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        try:
            with self.config_lock:
                if not self.merged_config:
                    self._rebuild_merged_config()
                
                if key_path is None:
                    return deepcopy(self.merged_config)
                
                # Navigate through nested dictionaries
                current_value = self.merged_config
                for key in key_path.split('.'):
                    if isinstance(current_value, dict) and key in current_value:
                        current_value = current_value[key]
                    else:
                        return default
                
                return deepcopy(current_value)
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get configuration for '{key_path}': {e}")
            return default
    
    def set_configuration(self, key_path: str, value: Any, profile_name: Optional[str] = None) -> bool:
        """
        Set configuration value by key path.
        
        Args:
            key_path: Dot-separated path to the configuration key
            value: Value to set
            profile_name: Profile to update (uses active profile if None)
            
        Returns:
            True if setting was successful, False otherwise
        """
        try:
            with self.config_lock:
                target_profile = profile_name or self.active_profile
                
                if not target_profile or target_profile not in self.profiles:
                    self.logger.error(f"❌ Target profile '{target_profile}' not found")
                    return False
                
                profile = self.profiles[target_profile]
                
                # Get old value for change tracking
                old_value = self._get_nested_value(profile.config_data, key_path)
                
                # Set new value
                self._set_nested_value(profile.config_data, key_path, value)
                
                # Update profile metadata
                profile.last_modified = datetime.now().isoformat()
                
                # Rebuild merged configuration
                self._rebuild_merged_config()
                
                # Track change
                if self.enable_change_tracking:
                    change = ConfigurationChange(
                        timestamp=datetime.now().isoformat(),
                        profile_name=target_profile,
                        field_path=key_path,
                        old_value=old_value,
                        new_value=value,
                        source=profile.source
                    )
                    self.change_history.append(change)
                    
                    # Limit change history size
                    if len(self.change_history) > self.max_change_history:
                        self.change_history = self.change_history[-self.max_change_history:]
            
            self.logger.info(f"✅ Configuration updated: {key_path} = {value}")
            
            # Notify change callbacks
            self._notify_configuration_change(key_path, old_value, value)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to set configuration '{key_path}': {e}")
            return False
    
    def save_profile_to_file(self, profile_name: str, file_path: str, format: Optional[ConfigurationFormat] = None) -> bool:
        """
        Save a configuration profile to a file.
        
        Args:
            profile_name: Name of the profile to save
            file_path: Path where to save the configuration
            format: File format (auto-detected if None)
            
        Returns:
            True if saving was successful, False otherwise
        """
        try:
            with self.config_lock:
                if profile_name not in self.profiles:
                    self.logger.error(f"❌ Profile '{profile_name}' not found")
                    return False
                
                profile = self.profiles[profile_name]
                file_path = Path(file_path)
                
                # Auto-detect format if not specified
                if format is None:
                    format = self._detect_file_format(file_path)
                
                # Ensure directory exists
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Save configuration data
                if format == ConfigurationFormat.JSON:
                    with open(file_path, 'w') as f:
                        json.dump(profile.config_data, f, indent=2, default=str)
                elif format == ConfigurationFormat.YAML:
                    with open(file_path, 'w') as f:
                        yaml.dump(profile.config_data, f, default_flow_style=False)
                else:
                    raise ValueError(f"Unsupported format for saving: {format}")
                
                # Update profile metadata
                profile.file_path = str(file_path)
                profile.format = format
                profile.last_modified = datetime.now().isoformat()
                profile.checksum = self._calculate_file_checksum(file_path)
            
            self.logger.info(f"✅ Profile '{profile_name}' saved to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to save profile '{profile_name}' to {file_path}: {e}")
            return False
    
    def add_change_callback(self, callback: Callable[[str, Any, Any], None]):
        """
        Add a callback function to be called when configuration changes.
        
        Args:
            callback: Function to call with (key_path, old_value, new_value)
        """
        self.change_callbacks.append(callback)
        self.logger.info(f"✅ Configuration change callback added")
    
    def start_hot_reload(self):
        """Start hot reload monitoring for configuration files."""
        if not self.enable_hot_reload or self.reload_active:
            return
        
        self.reload_active = True
        self.reload_thread = threading.Thread(target=self._hot_reload_loop, daemon=True)
        self.reload_thread.start()
        
        self.logger.info("🔥 Hot reload monitoring started")
    
    def stop_hot_reload(self):
        """Stop hot reload monitoring."""
        self.reload_active = False
        
        if self.reload_thread and self.reload_thread.is_alive():
            self.reload_thread.join(timeout=5)
        
        self.logger.info("🔥 Hot reload monitoring stopped")
    
    def get_profile_info(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a configuration profile.
        
        Args:
            profile_name: Name of the profile
            
        Returns:
            Profile information dictionary or None if not found
        """
        with self.config_lock:
            if profile_name not in self.profiles:
                return None
            
            profile = self.profiles[profile_name]
            return {
                "name": profile.name,
                "description": profile.description,
                "source": profile.source.value,
                "format": profile.format.value,
                "file_path": profile.file_path,
                "last_modified": profile.last_modified,
                "checksum": profile.checksum,
                "config_keys": list(profile.config_data.keys()) if isinstance(profile.config_data, dict) else []
            }
    
    def list_profiles(self) -> List[str]:
        """
        Get list of all configuration profile names.
        
        Returns:
            List of profile names
        """
        with self.config_lock:
            return list(self.profiles.keys())
    
    def get_change_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent configuration change history.
        
        Args:
            limit: Maximum number of changes to return
            
        Returns:
            List of configuration changes
        """
        with self.config_lock:
            recent_changes = self.change_history[-limit:] if limit > 0 else self.change_history
            return [asdict(change) for change in recent_changes]
    
    def validate_configuration(self, profile_name: str) -> Tuple[bool, List[str]]:
        """
        Validate a configuration profile against its schema.
        
        Args:
            profile_name: Name of the profile to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            with self.config_lock:
                if profile_name not in self.profiles:
                    return False, [f"Profile '{profile_name}' not found"]
                
                if profile_name not in self.schemas:
                    return True, []  # No schema to validate against
                
                profile = self.profiles[profile_name]
                schema = self.schemas[profile_name]
                
                errors = []
                is_valid = self._validate_configuration_recursive(
                    profile.config_data, schema, "", errors
                )
                
                return is_valid, errors
                
        except Exception as e:
            return False, [f"Validation error: {e}"]
    
    def _detect_file_format(self, file_path: Path) -> ConfigurationFormat:
        """Detect configuration file format from extension."""
        extension = file_path.suffix.lower()
        
        if extension in ['.json']:
            return ConfigurationFormat.JSON
        elif extension in ['.yaml', '.yml']:
            return ConfigurationFormat.YAML
        elif extension in ['.ini', '.cfg']:
            return ConfigurationFormat.INI
        else:
            return ConfigurationFormat.JSON  # Default
    
    def _load_file_data(self, file_path: Path, format: ConfigurationFormat) -> Optional[Dict[str, Any]]:
        """Load configuration data from file."""
        try:
            if format == ConfigurationFormat.JSON:
                with open(file_path, 'r') as f:
                    return json.load(f)
            elif format == ConfigurationFormat.YAML:
                with open(file_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported format: {format}")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to load data from {file_path}: {e}")
            return None
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file."""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _deep_merge_dicts(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = deepcopy(dict1)
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge_dicts(result[key], value)
            else:
                result[key] = deepcopy(value)
        
        return result
    
    def _rebuild_merged_config(self):
        """Rebuild the merged configuration from active profile."""
        if self.active_profile and self.active_profile in self.profiles:
            self.merged_config = deepcopy(self.profiles[self.active_profile].config_data)
        else:
            self.merged_config = {}
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        current_value = data
        for key in key_path.split('.'):
            if isinstance(current_value, dict) and key in current_value:
                current_value = current_value[key]
            else:
                return None
        return current_value
    
    def _set_nested_value(self, data: Dict[str, Any], key_path: str, value: Any):
        """Set value in nested dictionary using dot notation."""
        keys = key_path.split('.')
        current_dict = data
        
        # Navigate to the parent dictionary
        for key in keys[:-1]:
            if key not in current_dict:
                current_dict[key] = {}
            current_dict = current_dict[key]
        
        # Set the final value
        current_dict[keys[-1]] = value
    
    def _validate_configuration(self, config_data: Dict[str, Any], schema: ConfigurationSchema) -> bool:
        """Validate configuration data against schema."""
        errors = []
        is_valid = self._validate_configuration_recursive(config_data, schema, "", errors)
        
        if not is_valid:
            for error in errors:
                self.logger.error(f"❌ Validation error: {error}")
        
        return is_valid
    
    def _validate_configuration_recursive(self, 
                                        data: Any, 
                                        schema: ConfigurationSchema, 
                                        path: str, 
                                        errors: List[str]) -> bool:
        """Recursively validate configuration data."""
        is_valid = True
        
        if not isinstance(data, dict):
            errors.append(f"Expected dictionary at {path or 'root'}")
            return False
        
        # Check required fields
        for field in schema.required_fields:
            if field not in data:
                errors.append(f"Required field missing: {path}.{field}" if path else field)
                is_valid = False
        
        # Check field types and validate values
        for field, value in data.items():
            field_path = f"{path}.{field}" if path else field
            
            # Check if field is allowed
            if field not in schema.required_fields and field not in schema.optional_fields:
                errors.append(f"Unknown field: {field_path}")
                is_valid = False
                continue
            
            # Check field type
            if field in schema.field_types:
                expected_type = schema.field_types[field]
                if not isinstance(value, expected_type):
                    errors.append(f"Field {field_path} should be {expected_type.__name__}, got {type(value).__name__}")
                    is_valid = False
            
            # Run custom validator
            if field in schema.field_validators:
                validator = schema.field_validators[field]
                try:
                    if not validator(value):
                        errors.append(f"Validation failed for field: {field_path}")
                        is_valid = False
                except Exception as e:
                    errors.append(f"Validator error for field {field_path}: {e}")
                    is_valid = False
            
            # Validate nested schemas
            if field in schema.nested_schemas and isinstance(value, dict):
                nested_schema = schema.nested_schemas[field]
                if not self._validate_configuration_recursive(value, nested_schema, field_path, errors):
                    is_valid = False
        
        return is_valid
    
    def _notify_configuration_change(self, key_path: str, old_value: Any, new_value: Any):
        """Notify all registered callbacks about configuration change."""
        for callback in self.change_callbacks:
            try:
                callback(key_path, old_value, new_value)
            except Exception as e:
                self.logger.error(f"❌ Error in configuration change callback: {e}")
    
    def _hot_reload_loop(self):
        """Hot reload monitoring loop."""
        while self.reload_active:
            try:
                with self.config_lock:
                    files_to_check = list(self.file_watchers.items())
                
                for file_path, last_modified in files_to_check:
                    try:
                        current_modified = Path(file_path).stat().st_mtime
                        
                        if current_modified > last_modified:
                            self.logger.info(f"🔥 Configuration file changed: {file_path}")
                            
                            # Find profile associated with this file
                            profile_to_reload = None
                            for profile_name, profile in self.profiles.items():
                                if profile.file_path == file_path:
                                    profile_to_reload = profile_name
                                    break
                            
                            if profile_to_reload:
                                # Reload the configuration file
                                self.load_configuration_file(file_path, profile_to_reload)
                                
                                # Update file watcher timestamp
                                self.file_watchers[file_path] = current_modified
                                
                                # Rebuild merged config if this is the active profile
                                if profile_to_reload == self.active_profile:
                                    self._rebuild_merged_config()
                                    self._notify_configuration_change("file_reload", None, file_path)
                    
                    except FileNotFoundError:
                        # File was deleted, remove from watchers
                        self.logger.warning(f"⚠️ Configuration file deleted: {file_path}")
                        if file_path in self.file_watchers:
                            del self.file_watchers[file_path]
                    
                    except Exception as e:
                        self.logger.error(f"❌ Error checking file {file_path}: {e}")
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                self.logger.error(f"❌ Error in hot reload loop: {e}")
                time.sleep(5)  # Wait longer on error
    
    def cleanup(self):
        """Clean up the configuration manager."""
        self.logger.info("🧹 Cleaning up Configuration Manager...")
        
        # Stop hot reload
        self.stop_hot_reload()
        
        # Clear all data
        with self.config_lock:
            self.profiles.clear()
            self.schemas.clear()
            self.change_history.clear()
            self.change_callbacks.clear()
            self.file_watchers.clear()
            self.merged_config.clear()
        
        self.logger.info("✅ Configuration Manager cleanup completed")


def create_configuration_manager(config_dir: str = "config",
                                enable_hot_reload: bool = True,
                                enable_change_tracking: bool = True) -> ConfigurationManager:
    """
    Create and return a ConfigurationManager instance.
    
    Args:
        config_dir: Directory containing configuration files
        enable_hot_reload: Whether to enable automatic reloading
        enable_change_tracking: Whether to track configuration changes
        
    Returns:
        ConfigurationManager instance
    """
    return ConfigurationManager(
        config_dir=config_dir,
        enable_hot_reload=enable_hot_reload,
        enable_change_tracking=enable_change_tracking
    )


if __name__ == "__main__":
    # Example usage
    manager = create_configuration_manager()
    
    # Create default configuration
    manager.create_default_configuration()
    
    # Set as active profile
    manager.set_active_profile("default")
    
    # Test configuration access
    db_path = manager.get_configuration("database.path")
    print(f"Database path: {db_path}")
    
    # Test configuration update
    manager.set_configuration("features.debug_mode", True)
    debug_mode = manager.get_configuration("features.debug_mode")
    print(f"Debug mode: {debug_mode}")
    
    # Save configuration to file
    manager.save_profile_to_file("default", "config/default.json")
    
    # Cleanup
    manager.cleanup()