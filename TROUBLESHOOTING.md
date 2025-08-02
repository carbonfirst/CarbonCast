# RDA Automation System - Troubleshooting Guide

## System Overview

This troubleshooting guide covers both the **Individual Request Processing** system (`simple_automation.py`) and the **Batch Automation System** (`batch_automation_integrated.py`).

## Batch Automation System Issues

### 1. Batch Processing Won't Start

**Problem:** `python batch_automation_integrated.py --process-all-control-files` produces no output or errors

**Solutions:**

```bash
# Check if you're in the correct directory
cd src/python
pwd  # Should show: .../rda-apps-clients/src/python

# Verify batch automation files exist
ls -la batch_automation_integrated.py batch_automation.py batch_queue_manager.py batch_monitor.py

# Test basic functionality
python batch_automation_integrated.py --help

# Check dependencies
python -c "import flask, psutil, requests, json; print('All batch dependencies available')"
```

### 2. No Control Files Found

**Problem:** "No control files found" error when running batch processing

**Solutions:**

```bash
# Check control files directory exists
ls -la control_files/

# Verify .ctl files are present
ls control_files/*.ctl

# Create control files directory if missing
mkdir -p control_files

# Check configuration
cat automation_config.json | grep control_files_dir
```

### 3. Web Dashboard Not Loading

**Problem:** Cannot access web dashboard at http://localhost:5000

**Solutions:**

```bash
# Check if port 5000 is in use
lsof -i :5000

# Try different port (if port 5000 is busy)
# Edit batch_monitor.py to use different port

# Check firewall settings
# On macOS: System Preferences > Security & Privacy > Firewall
# On Linux: sudo ufw status

# Test dashboard separately
python batch_monitor.py
```

### 4. Authentication Errors in Batch Mode

**Problem:** RDA authentication failures during batch processing

**Solutions:**

```bash
# Check RDA token file
cat rdams_token.txt

# Verify token is valid (should be a long string without spaces)
wc -c rdams_token.txt  # Should show reasonable character count

# Test token with individual request
python rdams_client.py -get_status

# Update token if needed
echo "your_new_token_here" > rdams_token.txt
```

### 5. Batch Processing Stuck or Slow

**Problem:** Batch processing appears to hang or processes very slowly

**Solutions:**

```bash
# Check current status
python batch_automation_integrated.py --status

# Monitor system resources
top -p $(pgrep -f batch_automation)

# Check logs for errors
tail -f logs/integrated_system_*.log

# Reduce concurrent requests in automation_config.json
{
  "automation": {
    "max_concurrent_requests": 3,
    "check_interval_seconds": 180
  }
}

# Resume processing if interrupted
python batch_automation_integrated.py --resume
```

### 6. High Memory Usage in Batch Mode

**Problem:** System runs out of memory during batch processing

**Solutions:**

```bash
# Monitor memory usage
ps aux | grep batch_automation

# Reduce concurrent requests
# Edit automation_config.json:
{
  "automation": {
    "max_concurrent_requests": 2
  }
}

# Process smaller batches
# Move some control files to a separate directory temporarily

# Check available memory
free -h  # Linux
vm_stat  # macOS
```

### 7. Queue Manager Issues

**Problem:** Intelligent queue not working properly

**Solutions:**

```bash
# Check queue state file
ls -la queue_state.json

# Test queue manager separately
python batch_queue_manager.py

# Reset queue state if corrupted
rm queue_state.json batch_automation_state.json

# Restart batch processing
python batch_automation_integrated.py --process-all-control-files
```

### 8. Download Failures in Batch Mode

**Problem:** Files fail to download during batch processing

**Solutions:**

```bash
# Check disk space
df -h

# Check network connectivity
ping rda.ucar.edu

# Check RDA service status
curl -I https://rda.ucar.edu

# Check download directory permissions
ls -la downloaded_files/

# Resume processing (will retry failed downloads)
python batch_automation_integrated.py --resume
```

### 9. State File Corruption

**Problem:** Batch system won't resume due to corrupted state files

**Solutions:**

```bash
# Backup existing state files
cp batch_automation_state.json batch_automation_state.json.backup
cp queue_state.json queue_state.json.backup

# Check state file validity
python -c "import json; print(json.load(open('batch_automation_state.json')))"

# If corrupted, remove and restart (will lose progress)
rm batch_automation_state.json queue_state.json metrics_history.json

# Restart batch processing
python batch_automation_integrated.py --process-all-control-files
```

### 10. Flask/Dashboard Errors

**Problem:** Web dashboard shows errors or won't start

**Solutions:**

```bash
# Check Flask installation
python -c "import flask; print(flask.__version__)"

# Install/upgrade Flask if needed
pip install --upgrade flask

# Check template directory
ls -la templates/dashboard.html

# Run dashboard in debug mode
# Edit batch_monitor.py and set debug=True in app.run()

# Check for port conflicts
netstat -an | grep 5000
```

## Individual Request Processing Issues

### 1. System Not Running / No Output

### 1. System Not Running / No Output

**Problem:** Running the automation system produces no visible output

**Possible Causes:**
- Python path issues
- Missing dependencies
- Silent execution

**Solutions:**

```bash
# Check if you're in the correct directory
cd src/python
pwd  # Should show: .../rda-apps-clients/src/python

# Test basic functionality
python -c "import simple_automation; print('Import successful')"

# Run with explicit Python path
PYTHONPATH=. python simple_automation.py --help

# Check for missing dependencies
python -c "import requests, json, logging, pathlib; print('All dependencies available')"
```

### 2. Import Errors

**Problem:** `ModuleNotFoundError: No module named 'coordinate_utils'`

**Solution:**
```bash
# Ensure you're running from the correct directory
cd src/python
ls -la coordinate_utils.py  # Should exist
python simple_automation.py --help
```

### 3. Permission Denied Errors

**Problem:** Cannot create directories or write files

**Solutions:**
```bash
# Check current directory permissions
ls -la .

# Use a different output directory
python simple_automation.py --mode test --download-dir ~/my_automation_test

# Check disk space
df -h .
```

### 4. No Regions Detected (Everything goes to UNKNOWN/unknown)

**Problem:** All requests end up in UNKNOWN/unknown directories

**Debugging Steps:**

1. **Check coordinate format:**
   ```bash
   # Your rinfo should look like this:
   "rinfo": "nlat=42.0;slat=32.0;wlon=-124.75;elon=-113.5"
   ```

2. **Verify coordinates are in supported regions:**
   ```python
   # Test coordinate detection
   cd src/python
   python -c "
   from coordinate_utils import extract_coordinates_from_rinfo, map_coordinates_to_region
   coords = extract_coordinates_from_rinfo('nlat=42;slat=32;wlon=-124.75;elon=-113.5')
   print('Coordinates:', coords)
   region = map_coordinates_to_region(coords)
   print('Region:', region)
   "
   ```

3. **Check request format:**
   ```json
   {
     "request_index": "TEST_001",
     "rinfo": "nlat=42;slat=32;wlon=-124.75;elon=-113.5",
     "subset_info": {
       "note": "Parameter(s):\nDownward shortwave radiation flux"
     }
   }
   ```

### 5. Weather Variables Not Detected

**Problem:** All variables show as "unknown"

**Solutions:**

1. **Check parameter format in subset_info:**
   ```json
   "subset_info": {
     "note": "Parameter(s):\nTemperature"
   }
   ```

2. **Supported parameter names:**
   - Temperature, TMP, DPT → `temp`
   - Downward shortwave radiation flux, DSWRF → `dswrf`
   - u-component of wind, v-component of wind, UGRD, VGRD → `wind`
   - Total precipitation, A PCP, APCP → `rain`

3. **Test parameter detection:**
   ```python
   cd src/python
   python -c "
   from coordinate_utils import extract_parameter_from_subset_info, map_parameter_to_variable_type
   subset_info = {'note': 'Parameter(s):\nTemperature'}
   param = extract_parameter_from_subset_info(subset_info)
   print('Parameter:', param)
   var_type = map_parameter_to_variable_type(param)
   print('Variable type:', var_type)
   "
   ```

### 6. JSON File Errors

**Problem:** `json.decoder.JSONDecodeError` when using automated mode

**Solutions:**

1. **Validate JSON format:**
   ```bash
   python -c "import json; print(json.load(open('your_requests.json')))"
   ```

2. **Check file encoding:**
   ```bash
   file your_requests.json
   # Should show: ASCII text or UTF-8 Unicode text
   ```

3. **Use proper JSON structure:**
   ```json
   [
     {
       "request_index": "123456",
       "rinfo": "nlat=42;slat=32;wlon=-124.75;elon=-113.5",
       "subset_info": {
         "note": "Parameter(s):\nTemperature"
       }
     }
   ]
   ```

### 7. Virtual Environment Issues

**Problem:** Dependencies not found even after installation

**Solutions:**

1. **Verify virtual environment is activated:**
   ```bash
   which python  # Should point to your venv
   echo $VIRTUAL_ENV  # Should show venv path
   ```

2. **Reinstall dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Use system Python if needed:**
   ```bash
   deactivate  # Exit virtual environment
   python3 simple_automation.py --help
   ```

### 8. Directory Structure Validation Fails

**Problem:** Low compliance rate in validation

**Solutions:**

1. **Check directory naming:**
   - Regions should be UPPERCASE (CISO, PJM, ERCOT)
   - Variables should be lowercase (temp, dswrf, wind, rain)

2. **Fix directory structure:**
   ```bash
   # Example: rename incorrect directories
   mv downloaded_files/ciso downloaded_files/CISO
   mv downloaded_files/CISO/TEMP downloaded_files/CISO/temp
   ```

3. **Run validation to check:**
   ```bash
   python simple_automation.py --validate --download-dir downloaded_files
   ```

## Debugging Commands

### Enable Verbose Logging

```python
# Add to the beginning of simple_automation.py
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
```

### Test Individual Components

```bash
cd src/python

# Test coordinate extraction
python -c "
from coordinate_utils import extract_coordinates_from_rinfo
print(extract_coordinates_from_rinfo('nlat=42;slat=32;wlon=-124.75;elon=-113.5'))
"

# Test region mapping
python -c "
from coordinate_utils import map_coordinates_to_region
print(map_coordinates_to_region((42, 32, -124.75, -113.5)))
"

# Test parameter extraction
python -c "
from coordinate_utils import extract_parameter_from_subset_info
subset_info = {'note': 'Parameter(s):\nTemperature'}
print(extract_parameter_from_subset_info(subset_info))
"
```

### Check System Information

```bash
# Python version and path
python --version
which python

# Available modules
python -c "import sys; print('\n'.join(sys.path))"

# Current working directory
pwd

# File permissions
ls -la simple_automation.py coordinate_utils.py
```

## Performance Issues

### Large Request Files

**Problem:** Processing many requests is slow

**Solutions:**

1. **Process in batches:**
   ```bash
   # Split large JSON files
   python -c "
   import json
   with open('large_requests.json') as f:
       data = json.load(f)
   
   batch_size = 100
   for i in range(0, len(data), batch_size):
       batch = data[i:i+batch_size]
       with open(f'batch_{i//batch_size}.json', 'w') as f:
           json.dump(batch, f, indent=2)
   "
   ```

2. **Monitor progress:**
   ```bash
   # Add progress logging
   python simple_automation.py --mode automated --requests-file batch_0.json 2>&1 | tee processing.log
   ```

### Memory Issues

**Problem:** System runs out of memory with large files

**Solutions:**

1. **Process smaller batches**
2. **Use streaming JSON parsing for very large files**
3. **Monitor memory usage:**
   ```bash
   # On macOS/Linux
   top -p $(pgrep -f simple_automation)
   ```

## Getting Help

### Log Analysis

```bash
# Capture full output
python simple_automation.py --mode test 2>&1 | tee debug.log

# Search for errors
grep -i error debug.log
grep -i warning debug.log
```

### System Information for Support

```bash
# Gather system info
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo "Files present:"
ls -la simple_automation.py coordinate_utils.py
echo "Python path:"
python -c "import sys; print('\n'.join(sys.path))"
```

### Test Minimal Example

```bash
# Create minimal test
cat > minimal_test.json << EOF
[
  {
    "request_index": "TEST_001",
    "rinfo": "nlat=42;slat=32;wlon=-124.75;elon=-113.5",
    "subset_info": {
      "note": "Parameter(s):\nTemperature"
    }
  }
]
EOF

# Run test
python simple_automation.py --mode automated --requests-file minimal_test.json --download-dir test_output
```

## Contact and Support

If you continue to experience issues:

1. **Check the main documentation:** `RDA_AUTOMATION_USAGE_GUIDE.md`
2. **Review the enhanced system guide:** `docs/Enhanced_RDA_Automation_System_Guide.md`
3. **Run the built-in tests:** `python simple_automation.py --mode test`
4. **Validate your setup:** `python simple_automation.py --validate`

Include the following information when seeking help:
- Python version (`python --version`)
- Operating system
- Complete error messages
- Sample request data (anonymized)
- Output of `python simple_automation.py --mode test`