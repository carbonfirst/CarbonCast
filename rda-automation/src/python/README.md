# RDA Batch Automation System

## Overview

The RDA Batch Automation System is a comprehensive solution for processing large numbers of RDA (Research Data Archive) control files automatically. It provides intelligent queuing, progress monitoring, real-time web dashboard, and automatic file organization in the `REGION_NAME/weather_variable_type` structure.

## 🚀 Quick Start

### 1. Setup and Installation

```bash
# Navigate to the Python directory
cd src/python

# Install dependencies (if not already installed)
pip install requests flask psutil pyyaml jsonschema

# Verify your RDA token is configured
cat rdams_token.txt  # Should contain your valid RDA token
```

### 2. Prepare Control Files

Place all your `.ctl` control files in the `control_files/` directory:

```bash
# Create control files directory if it doesn't exist
mkdir -p control_files

# Copy your control files
cp /path/to/your/*.ctl control_files/
```

### 3. Start Batch Processing

```bash
# Process all control files automatically
python batch_automation_integrated.py --process-all-control-files
```

This single command will:
- Discover all control files
- Submit them to RDA with intelligent queuing
- Monitor progress automatically
- Download completed files
- Organize downloads by region and weather variable
- Provide a web dashboard at http://localhost:5000

## 📋 Command Reference

### Main Commands

#### Process All Control Files
```bash
python batch_automation_integrated.py --process-all-control-files
```
**Primary command** - Starts complete automated processing of all control files in the `control_files/` directory.

#### Resume Processing
```bash
python batch_automation_integrated.py --resume
```
Resumes processing from saved state after interruption. The system automatically saves progress and can continue from where it left off.

#### Monitor Dashboard Only
```bash
python batch_automation_integrated.py --monitor-dashboard
```
Runs only the monitoring system and web dashboard without starting new processing. Useful for monitoring existing requests.

#### Check Status
```bash
python batch_automation_integrated.py --status
```
Shows current status summary of all requests without starting processing or dashboard.

#### Custom Configuration
```bash
python batch_automation_integrated.py --config custom_config.json --process-all-control-files
```
Uses a custom configuration file instead of the default `automation_config.json`.

### Individual Component Commands

#### Core Batch System
```bash
# Process with core system only (no web dashboard)
python batch_automation.py --process-all-control-files

# Resume core processing
python batch_automation.py --resume

# Monitor existing requests only
python batch_automation.py --monitor-only
```

#### Queue Manager Testing
```bash
# Test intelligent queue management
python batch_queue_manager.py
```

#### Monitor and Dashboard
```bash
# Start monitoring and web dashboard
python batch_monitor.py
```

## 🌐 Web Dashboard

The web dashboard provides real-time monitoring and is automatically available at:
**http://localhost:5000**

### Dashboard Features

#### Progress Tracking
- **Overall Progress**: Total requests vs completed with percentage
- **Progress Charts**: Visual progress over time
- **Completion Rate**: Requests processed per hour
- **Success Rate**: Percentage of successful completions

#### Status Distribution
- **Pending**: Requests waiting to be submitted
- **Processing**: Currently active requests
- **Completed**: Finished requests ready for download
- **Downloaded**: Successfully downloaded and organized
- **Failed**: Requests that encountered errors

#### System Performance
- **CPU Usage**: System load monitoring
- **Memory Usage**: RAM consumption tracking
- **Queue Statistics**: Intelligent queue status and priorities
- **Resource Utilization**: Per-region and per-variable usage

#### Auto-Refresh
- Updates every 30 seconds automatically
- Manual refresh button available
- Real-time status updates

## 🧠 Intelligent Queuing System

### Priority Management

The system automatically assigns priorities based on:

#### Priority Levels
1. **URGENT** - Solar data (dswrf) for major ISOs
2. **HIGH** - Major grid operators (CISO, ERCOT, PJM, MISO, ISNE) and solar data
3. **NORMAL** - Standard requests
4. **LOW** - Retry attempts and less critical requests

#### Region Priority
High-priority regions include:
- **CISO** (California ISO)
- **ERCOT** (Electric Reliability Council of Texas)
- **PJM** (PJM Interconnection)
- **MISO** (Midcontinent ISO)
- **ISNE** (ISO New England)

#### Variable Priority
- **dswrf** (Solar radiation) - Highest priority
- **wind** (Wind components) - High priority
- **temp** (Temperature) - Normal priority
- **rain** (Precipitation) - Normal priority

### Resource Management

#### Concurrent Limits
- **Total Concurrent**: Maximum 5 requests processing simultaneously
- **Per Region**: Maximum 2 concurrent requests per region
- **Per Variable**: Maximum 3 concurrent requests per variable type

#### Load Balancing
- Distributes requests across different regions and variables
- Prevents overwhelming any single category
- Optimizes overall throughput

#### Smart Features
- **Dependency Handling**: Manages request dependencies
- **Automatic Retries**: Failed requests retry with lower priority
- **Queue Optimization**: Dynamically reorders based on system state
- **State Persistence**: Queue state survives system restarts

## 📁 File Organization

### Directory Structure

Downloaded files are automatically organized as:

```
downloaded_files/
├── CISO/                    # California ISO
│   ├── dswrf/              # Solar radiation data
│   │   ├── request_123456/
│   │   │   ├── data_file_1.nc
│   │   │   └── data_file_2.nc
│   │   └── request_789012/
│   ├── wind/               # Wind data
│   │   └── request_345678/
│   └── temp/               # Temperature data
├── ERCOT/                  # Electric Reliability Council of Texas
│   ├── rain/               # Precipitation data
│   └── wind/
├── PJM/                    # PJM Interconnection
│   ├── temp/
│   └── dswrf/
├── WACM/                   # Western Area Colorado Missouri
│   └── dswrf/
└── UNKNOWN/                # Fallback for undetected regions
    └── unknown/            # Fallback for undetected variables
```

### Region Detection

The system detects regions using multiple methods:

1. **Filename Analysis**: Extracts from `REGION_variable_control.ctl` pattern
2. **Coordinate Mapping**: Maps lat/lon coordinates to known regions
3. **Content Analysis**: Analyzes control file parameters
4. **Fallback**: Uses "UNKNOWN" for undetectable regions

### Variable Detection

Weather variables are detected from:
- Parameter names in control files
- Variable descriptions
- Standard meteorological abbreviations

Supported variables:
- **dswrf**: Downward shortwave radiation flux (solar)
- **wind**: Wind components (u-component, v-component)
- **temp**: Temperature data
- **rain**: Precipitation data

## ⚙️ Configuration

### Default Configuration

The system uses `automation_config.json`:

```json
{
  "automation": {
    "max_concurrent_requests": 5,
    "check_interval_seconds": 300,
    "retry_attempts": 3,
    "retry_delay_seconds": 60,
    "download_timeout_seconds": 3600
  },
  "directories": {
    "base_download_dir": "./downloaded_files",
    "logs_dir": "./logs",
    "control_files_dir": "./control_files"
  }
}
```

### Custom Configuration

Create a custom configuration file:

```json
{
  "automation": {
    "max_concurrent_requests": 8,
    "check_interval_seconds": 180,
    "retry_attempts": 5,
    "retry_delay_seconds": 120
  },
  "directories": {
    "base_download_dir": "/data/rda_downloads",
    "logs_dir": "/var/log/rda_automation",
    "control_files_dir": "/data/control_files"
  }
}
```

Use with:
```bash
python batch_automation_integrated.py --config custom_config.json --process-all-control-files
```

### Performance Tuning

#### Small Batches (< 50 files)
```json
{
  "automation": {
    "max_concurrent_requests": 3,
    "check_interval_seconds": 300
  }
}
```

#### Medium Batches (50-200 files)
```json
{
  "automation": {
    "max_concurrent_requests": 7,
    "check_interval_seconds": 240
  }
}
```

#### Large Batches (200+ files)
```json
{
  "automation": {
    "max_concurrent_requests": 10,
    "check_interval_seconds": 180
  }
}
```

## 📊 Monitoring and Logging

### Console Output

The system provides detailed console output:

```
============================================================
INTEGRATED BATCH AUTOMATION SYSTEM STATUS
============================================================

BATCH AUTOMATION STATUS SUMMARY
============================================================
Total Requests: 150
  Pending: 45 (30.0%)
  Processing: 5 (3.3%)
  Completed: 12 (8.0%)
  Downloaded: 88 (58.7%)
  Failed: 0 (0.0%)

Overall Progress: 88/150 (58.7%)

INTELLIGENT QUEUE MANAGER STATUS
============================================================
Queue Lengths:
  Pending: 45
  Processing: 5
  Completed: 88
  Failed: 0

Resource Utilization:
  Total Concurrent: 5/5
  Region Utilization:
    CISO: 2/2
    ERCOT: 1/2
    PJM: 2/2
  Variable Utilization:
    dswrf: 3/3
    wind: 1/3
    temp: 1/3

BATCH AUTOMATION PROGRESS REPORT
============================================================
Overall Progress: 88/150 (58.7%)
Estimated Completion: 2024-01-15 14:30:00
Completion Rate: 12.50 requests/hour

Performance Metrics:
  Success Rate: 100.0%
  Avg Processing Time: 2.30 hours
  System Load: 45.2%
  Memory Usage: 1250.5 MB
============================================================
```

### Log Files

Detailed logs are stored in the `logs/` directory:

#### Main System Logs
- `integrated_system_YYYYMMDD_HHMMSS.log`: Complete system activity
- `batch_automation_YYYYMMDD_HHMMSS.log`: Core automation events
- `queue_manager_YYYYMMDD_HHMMSS.log`: Queue management activities
- `batch_monitor_YYYYMMDD_HHMMSS.log`: Monitoring system events

#### Log Levels
- **INFO**: Normal operation events
- **WARNING**: Non-critical issues
- **ERROR**: Error conditions
- **DEBUG**: Detailed debugging information

### State Files

The system maintains state files for recovery:

- `batch_automation_state.json`: Core system state
- `queue_state.json`: Queue manager state
- `metrics_history.json`: Performance metrics history

## 🔧 Troubleshooting

### Common Issues

#### 1. No Control Files Found
```bash
# Check control files directory
ls -la control_files/

# Verify file extensions
ls control_files/*.ctl

# Solution: Ensure .ctl files are in control_files/ directory
```

#### 2. Authentication Errors
```bash
# Check RDA token
cat rdams_token.txt

# Verify token validity (should be a long string)
# Solution: Update rdams_token.txt with valid RDA token
```

#### 3. Web Dashboard Not Loading
```bash
# Check if port 5000 is in use
lsof -i :5000

# Check firewall settings
# Solution: Use different port or free up port 5000
```

#### 4. Processing Stuck
```bash
# Check current status
python batch_automation_integrated.py --status

# Check logs for errors
tail -f logs/integrated_system_*.log

# Solution: Resume processing or restart system
python batch_automation_integrated.py --resume
```

#### 5. Download Failures
```bash
# Check disk space
df -h

# Check network connectivity
ping rda.ucar.edu

# Check RDA service status
curl -I https://rda.ucar.edu

# Solution: Ensure adequate disk space and network connectivity
```

#### 6. High Memory Usage
```bash
# Monitor system resources
top -p $(pgrep -f batch_automation)

# Solution: Reduce max_concurrent_requests in configuration
```

### Recovery Procedures

#### System Crash Recovery
```bash
# 1. Check what was running
ps aux | grep batch_automation

# 2. Check state files
ls -la *.json

# 3. Resume from saved state
python batch_automation_integrated.py --resume
```

#### Corrupted State Recovery
```bash
# 1. Backup existing state
cp batch_automation_state.json batch_automation_state.json.backup

# 2. Start fresh (will lose progress)
rm batch_automation_state.json queue_state.json

# 3. Restart processing
python batch_automation_integrated.py --process-all-control-files
```

#### Partial Download Recovery
```bash
# 1. Check download directory
find downloaded_files/ -name "*.nc" -size 0

# 2. Remove incomplete downloads
find downloaded_files/ -name "*.nc" -size 0 -delete

# 3. Resume processing (will re-download)
python batch_automation_integrated.py --resume
```

## 🔍 Advanced Usage

### Custom Control File Naming

For optimal region/variable detection, name control files as:
```
REGION_variable_control.ctl
```

Examples:
- `CISO_dswrf_control.ctl`
- `ERCOT_wind_control.ctl`
- `PJM_temp_control.ctl`

### Selective Processing

To process only specific regions or variables:

1. **Create subdirectories** in `control_files/`:
```bash
mkdir control_files/solar_only
mv control_files/*dswrf*.ctl control_files/solar_only/
```

2. **Update configuration** to point to subdirectory:
```json
{
  "directories": {
    "control_files_dir": "./control_files/solar_only"
  }
}
```

### Integration with Other Systems

#### API Integration
The system provides internal APIs that can be integrated with other workflow management systems:

```python
from batch_automation_integrated import IntegratedBatchSystem

# Initialize system
system = IntegratedBatchSystem()

# Process specific files
system.batch_system.initialize_requests(['file1.ctl', 'file2.ctl'])
system.process_all_control_files()
```

#### Workflow Integration
Use with workflow managers like Airflow or Luigi:

```python
# Example Airflow DAG task
def run_batch_automation():
    import subprocess
    result = subprocess.run([
        'python', 'batch_automation_integrated.py', 
        '--process-all-control-files'
    ], capture_output=True, text=True)
    return result.returncode == 0
```

### Performance Monitoring

#### System Resource Monitoring
```bash
# Monitor CPU and memory usage
watch -n 5 'ps aux | grep batch_automation | head -10'

# Monitor disk I/O
iostat -x 5

# Monitor network usage
iftop -i eth0
```

#### Custom Metrics
The system exposes metrics that can be integrated with monitoring systems:

```python
from batch_monitor import BatchMonitor

monitor = BatchMonitor(batch_system, queue_manager)
metrics = monitor.collect_system_metrics()
print(f"Success rate: {metrics.success_rate}%")
```

## 📚 Additional Resources

### Related Documentation
- **Main README.md**: Overview and quick start guide
- **TROUBLESHOOTING.md**: Detailed troubleshooting guide
- **RDA_AUTOMATION_USAGE_GUIDE.md**: Complete usage examples

### RDA Resources
- **RDA Website**: https://rda.ucar.edu
- **RDA User Guide**: https://rda.ucar.edu/docs/
- **API Documentation**: https://rda.ucar.edu/docs/api/

### Support and Maintenance

#### Regular Maintenance
1. **Clean up old logs** (weekly):
```bash
find logs/ -name "*.log" -mtime +7 -delete
```

2. **Archive completed downloads** (monthly):
```bash
tar -czf downloads_$(date +%Y%m).tar.gz downloaded_files/
```

3. **Update RDA token** (as needed):
```bash
# Update token file
echo "new_token_here" > rdams_token.txt
```

#### Best Practices
1. **Before Starting**:
   - Verify RDA token validity
   - Check available disk space (estimate 1-5GB per request)
   - Review control files for accuracy
   - Test with small batch first

2. **During Processing**:
   - Monitor progress through web dashboard
   - Check logs for any errors
   - Avoid interrupting unless necessary
   - Monitor system resources

3. **After Completion**:
   - Verify all files downloaded correctly
   - Archive or backup downloaded data
   - Clean up temporary files
   - Review performance metrics

## 🆘 Getting Help

1. **Check Status**: `python batch_automation_integrated.py --status`
2. **Review Logs**: Check files in `logs/` directory
3. **Web Dashboard**: Monitor at http://localhost:5000
4. **Resume Processing**: `python batch_automation_integrated.py --resume`
5. **Start Fresh**: Remove state files and restart

For persistent issues, check the main troubleshooting documentation and ensure all dependencies are properly installed.
