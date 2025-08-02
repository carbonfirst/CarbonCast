# Enhanced Configuration Templates for Real-Time Data Sync and Batch Processing

## Master Configuration Template

### `enhanced_automation_config.yaml`

```yaml
# Enhanced RDA Automation System Configuration
# Version: 2.0
# Description: Comprehensive configuration for real-time sync and automated batch processing

# =============================================================================
# SYSTEM IDENTIFICATION
# =============================================================================
system:
  name: "RDA Enhanced Automation System"
  version: "2.0.0"
  environment: "production"  # development, staging, production
  instance_id: "rda-automation-001"
  deployment_timestamp: "2025-01-01T00:00:00Z"

# =============================================================================
# REAL-TIME DATA SYNCHRONIZATION
# =============================================================================
real_time_sync:
  # Enable/disable real-time synchronization
  enabled: true
  
  # Sync trigger configuration
  triggers:
    # Dashboard access trigger (immediate sync when dashboard accessed)
    dashboard_access:
      enabled: true
      delay_seconds: 0
      
    # Scheduled sync intervals
    scheduled:
      enabled: true
      interval_seconds: 120  # 2 minutes
      
    # Event-driven sync triggers
    event_driven:
      enabled: true
      events:
        - "request_status_changed"
        - "capacity_threshold_reached"
        - "error_detected"
        
    # Stale data detection trigger
    stale_data:
      enabled: true
      check_interval_seconds: 60
      
  # Data freshness thresholds (seconds)
  freshness_thresholds:
    rda_requests: 60        # 1 minute
    regional_progress: 300  # 5 minutes
    control_files: 600      # 10 minutes
    error_statistics: 120   # 2 minutes
    retry_statistics: 180   # 3 minutes
    
  # Sync engine configuration
  engine:
    max_concurrent_syncs: 3
    sync_timeout_seconds: 30
    retry_attempts: 3
    retry_delay_seconds: 5
    batch_size: 100
    
  # Cache strategy
  cache:
    strategy: "smart_invalidation"  # none, time_based, smart_invalidation
    max_age_seconds: 60
    invalidation_events:
      - "data_updated"
      - "sync_completed"
      - "manual_refresh"
      
  # WebSocket configuration for live updates
  websocket:
    enabled: true
    host: "0.0.0.0"
    port: 8081
    max_connections: 100
    heartbeat_interval: 30
    message_queue_size: 1000

# =============================================================================
# AUTOMATED BATCH PROCESSING
# =============================================================================
batch_processing:
  # Enable/disable batch processing
  enabled: true
  
  # Workflow orchestration
  workflow:
    # Main processing loop interval
    check_interval_seconds: 60
    
    # Workflow timeouts
    timeouts:
      submission_timeout: 300      # 5 minutes
      download_timeout: 3600       # 1 hour
      organization_timeout: 600    # 10 minutes
      
    # Retry configuration
    retry:
      max_attempts: 3
      delay_seconds: 60
      exponential_backoff: true
      backoff_multiplier: 2.0
      max_delay_seconds: 300
      
    # Parallel processing
    concurrency:
      max_concurrent_submissions: 2
      max_concurrent_downloads: 3
      max_concurrent_organizations: 5
      
  # Capacity management (10-request limit handling)
  capacity_management:
    # Request limits
    limits:
      max_requests: 10
      safety_margin: 2
      crisis_threshold: 9
      warning_threshold: 8
      
    # Crisis resolution
    crisis_resolution:
      enabled: true
      auto_download_completed: true
      auto_purge_downloaded: true
      auto_purge_errors: true
      max_crisis_resolution_time: 1800  # 30 minutes
      
    # Monitoring intervals
    monitoring:
      capacity_check_interval: 30
      crisis_detection_interval: 15
      
  # Queue management
  queue_management:
    # Priority configuration
    priorities:
      regions:
        ERCOT: "high"
        CISO: "high"
        PJM: "high"
        NYISO: "normal"
        ISNE: "normal"
        MISO: "normal"
        SPP: "low"
      variables:
        dswrf: "high"
        wind: "high"
        temp: "normal"
        rain: "normal"
        
    # Queue limits
    limits:
      max_queue_size: 1000
      max_priority_queue_size: 100
      
    # Submission rate limiting
    rate_limiting:
      requests_per_minute: 10
      burst_allowance: 3
      
  # Auto-purging configuration
  auto_purge:
    enabled: true
    conditions:
      purge_downloaded_after_hours: 24
      purge_failed_after_retries: true
      purge_old_completed_hours: 48
    safety_checks:
      verify_download_before_purge: true
      backup_request_info: true

# =============================================================================
# ENHANCED REGION/VARIABLE DETECTION
# =============================================================================
region_detection:
  # Detection methods (in order of preference)
  methods:
    - method: "control_file_parsing"
      enabled: true
      confidence_weight: 0.9
      
    - method: "coordinate_analysis"
      enabled: true
      confidence_weight: 0.8
      
    - method: "metadata_extraction"
      enabled: true
      confidence_weight: 0.7
      
    - method: "pattern_matching"
      enabled: true
      confidence_weight: 0.6
      
  # Fallback configuration
  fallback:
    enabled: true
    default_region: "UNKNOWN"
    default_variable: "unknown"
    
  # Validation configuration
  validation:
    enabled: true
    strict_mode: false
    confidence_threshold: 0.7
    
  # Region definitions with enhanced coordinate bounds
  regions:
    ERCOT:
      name: "Electric Reliability Council of Texas"
      bounds:
        lat_min: 25.5
        lat_max: 36.5
        lon_min: -106.5
        lon_max: -93.5
      priority: 1
      
    CISO:
      name: "California Independent System Operator"
      bounds:
        lat_min: 32.0
        lat_max: 42.0
        lon_min: -125.0
        lon_max: -114.0
      priority: 1
      
    PJM:
      name: "PJM Interconnection"
      bounds:
        lat_min: 35.0
        lat_max: 48.0
        lon_min: -91.0
        lon_max: -66.0
      priority: 1
      
    # Additional regions...
    
  # Variable definitions
  variables:
    dswrf:
      name: "Downward Shortwave Radiation Flux"
      patterns:
        - "dswrf"
        - "solar"
        - "radiation"
        - "shortwave"
      priority: 1
      
    wind:
      name: "Wind Speed/Direction"
      patterns:
        - "wind"
        - "ugrd"
        - "vgrd"
        - "wspd"
      priority: 1
      
    temp:
      name: "Temperature"
      patterns:
        - "temp"
        - "temperature"
        - "tmp"
        - "2m"
      priority: 2
      
    rain:
      name: "Precipitation"
      patterns:
        - "rain"
        - "precip"
        - "apcp"
        - "precipitation"
      priority: 2

# =============================================================================
# FILE ORGANIZATION
# =============================================================================
file_organization:
  # Base directory for organized files
  base_directory: "./downloaded_files"
  
  # Directory structure pattern
  structure:
    pattern: "{region}/{variable}"
    create_missing_dirs: true
    
  # Organization rules
  rules:
    validate_before_move: true
    backup_before_reorganize: true
    preserve_original_structure: false
    
  # File naming conventions
  naming:
    preserve_original_names: true
    add_metadata_suffix: false
    timestamp_format: "%Y%m%d_%H%M%S"
    
  # Reorganization service
  reorganization:
    enabled: true
    scan_interval_hours: 6
    auto_fix_misplaced: true
    
# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
database:
  # SQLite configuration
  sqlite:
    path: "./data/automation_state.db"
    backup_enabled: true
    backup_interval_hours: 6
    backup_retention_days: 30
    
  # Connection settings
  connection:
    timeout_seconds: 30
    max_connections: 10
    connection_pool_size: 5
    
  # Performance settings
  performance:
    journal_mode: "WAL"
    synchronous: "NORMAL"
    cache_size: 10000
    temp_store: "MEMORY"

# =============================================================================
# ERROR HANDLING AND RECOVERY
# =============================================================================
error_handling:
  # Global error handling settings
  global:
    log_all_errors: true
    send_notifications: true
    auto_recovery_enabled: true
    
  # Recovery strategies
  recovery_strategies:
    api_errors:
      strategy: "retry_with_backoff"
      max_retries: 5
      base_delay: 10
      max_delay: 300
      
    sync_errors:
      strategy: "fallback_to_cache"
      cache_max_age: 600
      
    capacity_errors:
      strategy: "crisis_resolution"
      auto_resolve: true
      
    file_errors:
      strategy: "graceful_degradation"
      continue_processing: true
      
  # Circuit breaker configuration
  circuit_breaker:
    enabled: true
    failure_threshold: 5
    recovery_timeout: 300
    half_open_max_calls: 3
    
  # Error notification
  notifications:
    email:
      enabled: false
      smtp_server: "smtp.example.com"
      recipients: ["admin@example.com"]
      
    webhook:
      enabled: false
      url: "https://hooks.example.com/webhook"
      
    dashboard:
      enabled: true
      show_error_banner: true

# =============================================================================
# MONITORING AND OBSERVABILITY
# =============================================================================
monitoring:
  # Metrics collection
  metrics:
    enabled: true
    collection_interval: 30
    retention_days: 30
    
    # Metric types to collect
    types:
      - "sync_latency"
      - "sync_success_rate"
      - "data_freshness"
      - "capacity_utilization"
      - "request_throughput"
      - "download_success_rate"
      - "file_organization_accuracy"
      - "error_rate"
      - "workflow_completion_time"
      
  # Health checks
  health_checks:
    enabled: true
    interval_seconds: 60
    endpoints:
      - name: "rda_api"
        url: "https://rda.ucar.edu/api/"
        timeout: 10
        
      - name: "database"
        type: "sqlite"
        path: "./data/automation_state.db"
        
      - name: "file_system"
        type: "directory"
        path: "./downloaded_files"
        
  # Alerting
  alerting:
    enabled: true
    rules:
      - name: "high_error_rate"
        condition: "error_rate > 0.1"
        severity: "warning"
        
      - name: "capacity_crisis"
        condition: "active_requests >= 10"
        severity: "critical"
        
      - name: "sync_failure"
        condition: "sync_success_rate < 0.9"
        severity: "warning"

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging:
  # Global logging settings
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
  # Log destinations
  handlers:
    console:
      enabled: true
      level: "INFO"
      
    file:
      enabled: true
      level: "DEBUG"
      path: "./logs/automation.log"
      max_size_mb: 100
      backup_count: 5
      
    rotating_file:
      enabled: true
      level: "INFO"
      path: "./logs/automation_rotating.log"
      max_size_mb: 50
      backup_count: 10
      
  # Component-specific logging
  components:
    real_time_sync:
      level: "INFO"
      
    batch_processing:
      level: "INFO"
      
    capacity_management:
      level: "WARNING"
      
    region_detection:
      level: "DEBUG"
      
    file_organization:
      level: "INFO"

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================
security:
  # API security
  api:
    token_file: "./rdams_token.txt"
    token_refresh_hours: 24
    rate_limiting:
      enabled: true
      requests_per_minute: 60
      
  # File system security
  file_system:
    permissions:
      directories: "755"
      files: "644"
    restricted_paths:
      - "/etc"
      - "/var"
      - "/usr"
      
  # Network security
  network:
    allowed_hosts:
      - "rda.ucar.edu"
      - "localhost"
      - "127.0.0.1"
    ssl_verify: true

# =============================================================================
# DEVELOPMENT AND TESTING
# =============================================================================
development:
  # Debug settings
  debug:
    enabled: false
    verbose_logging: false
    save_api_responses: false
    
  # Testing configuration
  testing:
    mock_api_calls: false
    test_data_path: "./test_data"
    
  # Performance profiling
  profiling:
    enabled: false
    output_path: "./profiling"

# =============================================================================
# FEATURE FLAGS
# =============================================================================
feature_flags:
  # Real-time features
  websocket_notifications: true
  dashboard_auto_refresh: true
  live_sync_indicators: true
  
  # Batch processing features
  intelligent_queuing: true
  auto_crisis_resolution: true
  predictive_capacity_management: true
  
  # Detection features
  enhanced_region_detection: true
  machine_learning_classification: false
  auto_file_reorganization: true
  
  # Experimental features
  parallel_downloads: true
  advanced_error_recovery: true
  performance_optimization: true
```

## Environment-Specific Configuration Templates

### Development Environment (`config/development.yaml`)

```yaml
# Development Environment Overrides
system:
  environment: "development"
  
real_time_sync:
  freshness_thresholds:
    rda_requests: 30        # Faster refresh for development
    regional_progress: 60
    
batch_processing:
  workflow:
    check_interval_seconds: 30  # More frequent checks
    
  capacity_management:
    limits:
      max_requests: 5       # Lower limit for testing
      crisis_threshold: 4
      
logging:
  level: "DEBUG"
  handlers:
    console:
      level: "DEBUG"
      
development:
  debug:
    enabled: true
    verbose_logging: true
    save_api_responses: true
    
  testing:
    mock_api_calls: true    # Use mocked API calls
```

### Staging Environment (`config/staging.yaml`)

```yaml
# Staging Environment Overrides
system:
  environment: "staging"
  
real_time_sync:
  freshness_thresholds:
    rda_requests: 45
    
batch_processing:
  capacity_management:
    limits:
      max_requests: 8       # Slightly lower for staging
      crisis_threshold: 7
      
monitoring:
  alerting:
    enabled: false          # Disable alerts in staging
    
logging:
  level: "INFO"
```

### Production Environment (`config/production.yaml`)

```yaml
# Production Environment Overrides
system:
  environment: "production"
  
error_handling:
  notifications:
    email:
      enabled: true
      recipients: ["ops-team@company.com"]
      
    webhook:
      enabled: true
      url: "https://monitoring.company.com/webhook"
      
monitoring:
  alerting:
    enabled: true
    
security:
  network:
    ssl_verify: true
    
logging:
  level: "WARNING"
  handlers:
    console:
      level: "ERROR"
```

## Component-Specific Configuration Templates

### Real-Time Sync Configuration (`config/realtime_sync.yaml`)

```yaml
# Real-Time Synchronization Specific Configuration
sync_engine:
  # Performance tuning
  performance:
    max_concurrent_syncs: 3
    sync_timeout_seconds: 30
    batch_processing_size: 100
    memory_limit_mb: 512
    
  # Sync strategies
  strategies:
    dashboard_access:
      strategy: "immediate"
      cache_bypass: true
      
    scheduled:
      strategy: "incremental"
      delta_sync: true
      
    event_driven:
      strategy: "targeted"
      affected_data_only: true
      
  # Data sources priority
  data_sources:
    - source: "rda_api"
      priority: 1
      timeout: 30
      
    - source: "database_cache"
      priority: 2
      max_age: 300
      
# WebSocket configuration
websocket_server:
  # Server settings
  server:
    host: "0.0.0.0"
    port: 8081
    ssl_enabled: false
    
  # Connection management
  connections:
    max_connections: 100
    connection_timeout: 300
    heartbeat_interval: 30
    
  # Message handling
  messaging:
    max_message_size: 1048576  # 1MB
    message_queue_size: 1000
    compression_enabled: true
    
# Data freshness management
freshness_manager:
  # Freshness rules
  rules:
    critical_data:
      max_age_seconds: 60
      auto_refresh: true
      
    normal_data:
      max_age_seconds: 300
      auto_refresh: false
      
    background_data:
      max_age_seconds: 600
      auto_refresh: false
      
  # Staleness detection
  staleness:
    check_interval: 30
    notification_threshold: 0.8
```

### Batch Processing Configuration (`config/batch_processing.yaml`)

```yaml
# Batch Processing Specific Configuration
workflow_orchestrator:
  # State machine configuration
  state_machine:
    initial_state: "monitoring"
    transition_timeout: 300
    max_state_duration: 3600
    
  # Workflow execution
  execution:
    max_parallel_workflows: 3
    workflow_timeout: 7200
    checkpoint_interval: 300
    
# Capacity management detailed configuration
capacity_manager:
  # Monitoring configuration
  monitoring:
    check_interval: 30
    trend_analysis_window: 3600
    prediction_enabled: true
    
  # Crisis resolution protocols
  crisis_protocols:
    level_1:  # Warning level
      threshold: 8
      actions:
        - "notify_operators"
        - "increase_monitoring_frequency"
        
    level_2:  # Crisis level
      threshold: 9
      actions:
        - "auto_download_completed"
        - "prepare_purge_list"
        
    level_3:  # Emergency level
      threshold: 10
      actions:
        - "emergency_purge"
        - "halt_new_submissions"
        - "escalate_to_manual"
        
  # Safe purging rules
  purge_rules:
    safe_to_purge:
      - status: "completed"
        condition: "downloaded AND verified"
        
      - status: "error"
        condition: "retry_count >= max_retries"
        
    never_purge:
      - status: "processing"
      - status: "queued"
      - condition: "age < 1_hour"
      
# Queue management configuration
queue_manager:
  # Priority queues
  queues:
    critical:
      max_size: 50
      processing_weight: 3
      
    high:
      max_size: 100
      processing_weight: 2
      
    normal:
      max_size: 500
      processing_weight: 1
      
    low:
      max_size: 1000
      processing_weight: 0.5
      
  # Scheduling algorithms
  scheduling:
    algorithm: "weighted_round_robin"
    time_slice_seconds: 60
    starvation_prevention: true
```

### Region Detection Configuration (`config/region_detection.yaml`)

```yaml
# Region/Variable Detection Specific Configuration
detection_engine:
  # Detection methods configuration
  methods:
    control_file_parsing:
      enabled: true
      patterns:
        - regex: "^([A-Z]+)_([a-z]+)_control\.ctl$"
          groups: ["region", "variable"]
          
      validation:
        region_whitelist: true
        variable_whitelist: true
        
    coordinate_analysis:
      enabled: true
      precision: 0.1
      overlap_resolution: "highest_priority"
      
    metadata_extraction:
      enabled: true
      sources:
        - "rinfo_parameters"
        - "subset_note"
        - "request_title"
        
  # Machine learning configuration (if enabled)
  machine_learning:
    enabled: false
    model_path: "./models/region_classifier.pkl"
    confidence_threshold: 0.8
    training_data_path: "./training_data"
    
# Enhanced region definitions
regions:
  # US Grid Operators
  grid_operators:
    ERCOT:
      full_name: "Electric Reliability Council of Texas"
      type: "ISO"
      bounds:
        lat_min: 25.5
        lat_max: 36.5
        lon_min: -106.5
        lon_max: -93.5
      priority: 1
      aliases: ["TEXAS", "TX"]
      
    CISO:
      full_name: "California Independent System Operator"
      type: "ISO"
      bounds:
        lat_min: 32.0
        lat_max: 42.0
        lon_min: -125.0
        lon_max: -114.0
      priority: 1
      aliases: ["CALIFORNIA", "CA", "CAISO"]
      
  # Regional utilities
  utilities:
    AZPS:
      full_name: "Arizona Public Service"
      type: "Utility"
      bounds:
        lat_min: 31.0
        lat_max: 37.0
        lon_min: -115.0
        lon_max: -109.0
      priority: 2
      parent_region: "WECC"
      
# Variable definitions with enhanced patterns
variables:
  weather_variables:
    dswrf:
      full_name: "Downward Shortwave Radiation Flux"
      category: "solar"
      patterns:
        exact_match: ["dswrf"]
        partial_match: ["solar", "radiation", "shortwave"]
        regex_patterns: [".*solar.*", ".*radiation.*"]
      units: "W/m^2"
      priority: 1
      
    wind:
      full_name: "Wind Speed and Direction"
      category: "wind"
      patterns:
        exact_match: ["wind", "ugrd", "vgrd"]
        partial_match: ["wind speed", "wind direction"]
        regex_patterns: [".*wind.*", ".*grd$"]
      units: "m/s"
      priority: 1
```

## Configuration Validation Schema

### `config/validation_schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "RDA Enhanced Automation Configuration Schema",
  "type": "object",
  "required": ["system", "real_time_sync", "batch_processing"],
  "properties": {
    "system": {
      "type": "object",
      "required": ["name", "version", "environment"],
      "properties": {
        "name": {"type": "string"},
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "environment": {"enum": ["development", "staging", "production"]}
      }
    },
    "real_time_sync": {
      "type": "object",
      "required": ["enabled", "triggers", "freshness_thresholds"],
      "properties": {
        "enabled": {"type": "boolean"},
        "triggers": {
          "type": "object",
          "properties": {
            "dashboard_access": {
              "type": "object",
              "properties": {
                "enabled": {"type": "boolean"},
                "delay_seconds": {"type": "integer", "minimum": 0}
              }
            }
          }
        },
        "freshness_thresholds": {
          "type": "object",
          "patternProperties": {
            ".*": {"type": "integer", "minimum": 1}
          }
        }
      }
    },
    "batch_processing": {
      "type": "object",
      "required": ["enabled", "capacity_management"],
      "properties": {
        "enabled": {"type": "boolean"},
        "capacity_management": {
          "type": "object",
          "required": ["limits"],
          "properties": {
            "limits": {
              "type": "object",
              "required": ["max_requests"],
              "properties": {
                "max_requests": {"type": "integer", "minimum": 1, "maximum": 20}
              }
            }
          }
        }
      }
    }
  }
}
```

## Configuration Management Scripts

### `scripts/validate_config.py`

```python
#!/usr/bin/env python3
"""
Configuration validation script for RDA Enhanced Automation System.
"""

import json
import yaml
import jsonschema
from pathlib import Path
from typing import Dict, Any, List

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def load_schema(schema_path: str) -> Dict[str, Any]:
    """Load JSON schema."""
    with open(schema_path, 'r') as f:
        return json.load(f)

def validate_config(config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Validate configuration against schema."""
    errors = []
    try:
        jsonschema.validate(config, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"Validation error: {e.message}")
    except jsonschema.SchemaError as e:
        errors.append(f"Schema error: {e.message}")
    
    return errors

def main():
    """Main validation function."""
    config_path = "config/enhanced_automation_config.yaml"
    schema_path = "config/validation_schema.json"
    
    try:
        config = load_config(config_path)
        schema = load_schema(schema_path)
        
        errors = validate_config(config, schema)
        
        if errors:
            print("Configuration validation failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
        else:
            print("Configuration validation passed!")
            return 0
            
    except Exception as e:
        print(f"Error during validation: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
```

### `scripts/merge_configs.py`

```python
#!/usr/bin/env python3
"""
Configuration merging script for environment-specific overrides.
"""

import yaml
from pathlib import Path
from typing import Dict, Any

def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result

def merge_configs(base_config_path: str, override_config_path: str, 
                 output_path: str = None) -> Dict[str, Any]:
    """Merge base configuration with environment-specific overrides."""
    
    # Load base configuration
    with open(base_config_path, 'r') as f:
        base_config = yaml.safe_load(f)
    
    # Load override configuration
    with open(override_config_path, 'r') as f:
        override_config = yaml.safe_load(f)
    
    # Merge configurations
    merged_config = deep_merge(base_config, override_config)
    
    # Save merged configuration if output path provided
    if output_path:
        with open(output_path, 'w') as f:
            yaml.dump(merged_config, f, default_flow_style=False, indent=2)
    
    return merged_config

def main():
    """Main merging function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Merge configuration files')
    parser.add_argument('--base', required=True, help='Base configuration file')
    parser.add_argument('--override', required=True, help='Override configuration file')
    parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    try:
        merged_config = merge_configs(args.base, args.override, args.output)
        
        if args.output:
            print(f"Merged configuration saved to: {args.output}")
        else:
            print("Merged configuration:")
            print(yaml.dump(merged_config, default_flow_style=False, indent=2))
            
    except Exception as e:
        print(f"Error merging configurations: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
```

This comprehensive configuration template provides:

1. **Master Configuration**: Complete configuration with all options
2. **Environment-Specific Overrides**: Development, staging, and production variants
3. **Component-Specific Configs**: Detailed configurations for major components
4. **Validation Schema**: JSON schema for configuration validation
5. **Management Scripts**: Tools for validation and merging configurations

The configuration system supports:
- Environment-specific overrides
- Feature flags for gradual rollout
- Comprehensive error handling configuration
- Performance tuning parameters
- Security settings
- Monitoring and observability configuration
- Development and testing support