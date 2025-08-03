# 🚀 CarbonCast Setup Guide

This comprehensive guide will walk you through setting up the CarbonCast automation tool from a fresh clone of the repository. Follow these steps to ensure a smooth, error-free installation.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Setup (Recommended)](#quick-setup-recommended)
- [Manual Setup](#manual-setup)
- [Dependency Management](#dependency-management)
- [Verification Steps](#verification-steps)
- [Common Issues & Solutions](#common-issues--solutions)
- [Advanced Configuration](#advanced-configuration)
- [Getting Help](#getting-help)

## 🔧 Prerequisites

### System Requirements

- **Python 3.8 or higher** (Python 3.9+ recommended)
- **pip** package manager (usually comes with Python)
- **Git** (for cloning the repository)
- **4GB+ RAM** (recommended for large batch processing)
- **10GB+ disk space** (for downloads and logs)
- **Stable internet connection** (for RDA API access)

### RDA Account Setup

1. **Create an RDA account** at [https://rda.ucar.edu/](https://rda.ucar.edu/)
2. **Get your authentication token**:
   - Log in to your RDA account
   - Go to [https://rda.ucar.edu/accounts/profile/](https://rda.ucar.edu/accounts/profile/)
   - Copy your "Authentication Token"
   - Keep this token secure - you'll need it during setup

### Check Your Python Version

```bash
python3 --version
# Should show Python 3.8.0 or higher
```

If you don't have Python 3.8+, install it:

**macOS (using Homebrew):**
```bash
brew install python@3.9
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.9 python3.9-venv python3.9-pip
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/) and install.

## 🚀 Quick Setup (Recommended)

This is the fastest and most reliable way to set up CarbonCast:

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd CarbonCast
```

### Step 2: Navigate to Python Directory

```bash
cd src/python
```

### Step 3: Run the Enhanced Setup Script

```bash
# Make the setup script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

The setup script will:
- ✅ Check your Python version
- ✅ Create and activate a virtual environment
- ✅ Install all required dependencies from the correct `requirements.txt`
- ✅ Verify all imports work correctly
- ✅ Check for the `fix_completed_requests.py` module
- ✅ Create necessary directories
- ✅ Set proper file permissions
- ✅ Provide clear success/failure messages

### Step 4: Set Up Your RDA Token

```bash
# Create the token file (replace with your actual token)
echo "your_rda_token_here" > rdams_token.txt
```

### Step 5: Test Your Installation

```bash
# Activate the virtual environment (if not already active)
source venv/bin/activate

# Run the dependency verification script
python verify_dependencies.py

# Start the automation system
python start_automation.py
```

**🎉 That's it! Your CarbonCast environment is ready!**

## 🔧 Manual Setup

If you prefer to set up manually or the automated script doesn't work for your system:

### Step 1: Clone and Navigate

```bash
git clone <repository-url>
cd CarbonCast/src/python
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Upgrade pip

```bash
pip install --upgrade pip
```

### Step 4: Install Dependencies

**⚠️ IMPORTANT:** Use the `requirements.txt` file in the root directory.

```bash
# Install from the root requirements file
pip install -r ../../requirements.txt
```

### Step 5: Verify Installation

```bash
python verify_dependencies.py --verbose
```

### Step 6: Create Directories

```bash
mkdir -p logs downloaded_files data templates
```

### Step 7: Set Permissions

```bash
chmod +x *.py
```

### Step 8: Set Up RDA Token

```bash
echo "your_rda_token_here" > rdams_token.txt
```

## 📦 Dependency Management

### Understanding the Requirements File

The project uses a single **`requirements.txt`** file in the root directory:

**`requirements.txt`** (root directory) ✅ **USE THIS ONE**
   - Contains all necessary dependencies for the project
   - Includes `flask-cors>=4.0.0` (critical for dashboard)
   - Includes both production and development dependencies
   - Properly versioned for compatibility

### Key Dependencies Explained

| Package | Version | Purpose | Critical? |
|---------|---------|---------|-----------|
| `requests` | ≥2.25.0 | RDA API communication | ✅ Yes |
| `flask` | ≥2.0.0 | Web dashboard | ✅ Yes |
| `flask-cors` | ≥4.0.0 | Dashboard CORS support | ✅ Yes |
| `psutil` | ≥5.8.0 | System monitoring | ✅ Yes |
| `pyyaml` | ≥5.4.0 | Configuration files | ✅ Yes |
| `numpy` | ≥1.21.0 | Data processing | ✅ Yes |
| `pandas` | ≥1.5.0 | Data analysis | ✅ Yes |
| `matplotlib` | ≥3.6.0 | Visualization | ✅ Yes |
| `pytest` | ≥7.0.0 | Testing framework | ⚠️ Optional |

### Dependency Verification

Always verify your dependencies after installation:

```bash
# Basic verification
python verify_dependencies.py

# Detailed verification
python verify_dependencies.py --verbose

# Auto-fix missing dependencies
python verify_dependencies.py --fix
```

## ✅ Verification Steps

### 1. Python Environment Check

```bash
# Check Python version
python3 --version

# Check if in virtual environment
python -c "import sys; print('Virtual env:', hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))"
```

### 2. Critical Import Test

```bash
python -c "
import requests
import flask
import flask_cors
import psutil
import yaml
import numpy
import pandas
import fix_completed_requests
print('✅ All critical imports successful!')
"
```

### 3. Module Availability Test

```bash
python -c "
from fix_completed_requests import setup_logging
logger = setup_logging()
print('✅ fix_completed_requests module works correctly!')
"
```

### 4. Dashboard Test

```bash
# Test dashboard creation (should not error)
python -c "
from automation.dashboard import create_dashboard
dashboard = create_dashboard()
print('✅ Dashboard can be created!')
"
```

### 5. Full System Test

```bash
# Run the automation starter (should show menu)
python start_automation.py
```

## 🚨 Common Issues & Solutions

### Issue 1: `ModuleNotFoundError: No module named 'flask_cors'`

**Cause:** Using wrong requirements.txt file or incomplete installation.

**Solution:**
```bash
# Make sure you're in src/python directory
cd src/python

# Install from correct requirements file
pip install flask-cors>=4.0.0

# Or reinstall all dependencies
pip install -r requirements.txt
```

### Issue 2: `ImportError: cannot import name 'fix_completed_requests'`

**Cause:** Not running from the correct directory or module not found.

**Solution:**
```bash
# Make sure you're in src/python directory
cd src/python

# Check if file exists
ls -la fix_completed_requests.py

# Test import
python -c "import fix_completed_requests; print('✅ Module found!')"
```

### Issue 3: `Permission denied` when running setup.sh

**Cause:** Setup script doesn't have execute permissions.

**Solution:**
```bash
chmod +x setup.sh
./setup.sh
```

### Issue 4: Python version too old

**Cause:** System has Python < 3.8.

**Solution:**
```bash
# Check available Python versions
python3 --version
python3.8 --version
python3.9 --version

# Use specific version if available
python3.9 -m venv venv
```

### Issue 5: Virtual environment not activating

**Cause:** Shell or path issues.

**Solution:**
```bash
# Try different activation methods
source venv/bin/activate
# OR
. venv/bin/activate
# OR (if using fish shell)
source venv/bin/activate.fish
```

### Issue 6: Dashboard won't start - "Port already in use"

**Cause:** Another process is using port 5001.

**Solution:**
```bash
# Find and kill process using port 5001
lsof -ti:5001 | xargs kill -9

# Or use a different port
python automation/dashboard.py --port 8080
```

### Issue 7: Database errors

**Cause:** Corrupted or missing database file.

**Solution:**
```bash
# Remove and recreate database
rm -f data/automation_state.db

# Run database initialization
python database_init.py
```

### Issue 8: RDA token not found

**Cause:** Token file missing or in wrong location.

**Solution:**
```bash
# Make sure you're in src/python directory
cd src/python

# Create token file
echo "your_actual_token_here" > rdams_token.txt

# Verify file exists
cat rdams_token.txt
```

## 🔧 Advanced Configuration

### Custom Virtual Environment Location

```bash
# Create venv in custom location
python3 -m venv /path/to/custom/venv

# Activate custom venv
source /path/to/custom/venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Development Setup

For development work, you may want additional tools:

```bash
# Install development dependencies
pip install black flake8 isort mypy pytest-cov

# Set up pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### Environment Variables

You can customize behavior with environment variables:

```bash
# Custom database path
export RDA_DB_PATH="custom/path/automation_state.db"

# Custom max concurrent requests
export RDA_MAX_CONCURRENT_REQUESTS="8"

# Enable debug mode
export RDA_DEBUG_MODE="true"
```

### Configuration File

Edit [`config/automation_config.json`](../config/automation_config.json) for advanced settings:

```json
{
  "automation": {
    "max_concurrent_requests": 8,
    "check_interval_seconds": 300
  },
  "dashboard": {
    "port": 5001,
    "auto_refresh_seconds": 30
  }
}
```

## 🆘 Getting Help

### Self-Diagnosis

1. **Run the verification script:**
   ```bash
   python verify_dependencies.py --verbose
   ```

2. **Check system status:**
   ```bash
   python automation/sequential_file_processor.py --status
   ```

3. **View logs:**
   ```bash
   tail -f logs/automation.log
   ```

### Documentation Resources

- **[Main README](../../README.md)** - Project overview and quick start
- **[Troubleshooting Guide](Troubleshooting_Guide.md)** - Detailed problem resolution
- **[API Reference](API_Reference.md)** - Complete API documentation
- **[Configuration Reference](Configuration_Reference.md)** - All configuration options

### Emergency Recovery

If everything breaks:

```bash
# Emergency cleanup
pkill -f "python.*automation"
rm -rf venv
rm -f data/*.lock
rm -f data/automation_state.db

# Fresh start
./setup.sh
```

### Getting Support

1. **Check existing documentation** in the `docs/` directory
2. **Search GitHub Issues** for similar problems
3. **Create a new issue** with:
   - Your operating system
   - Python version (`python3 --version`)
   - Error messages (full traceback)
   - Steps to reproduce

### Quick Diagnostic Commands

```bash
# System info
python -c "import sys, platform; print(f'Python: {sys.version}'); print(f'Platform: {platform.platform()}')"

# Dependency status
python verify_dependencies.py

# Virtual environment status
python -c "import sys; print('Virtual env:', hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))"

# Current directory check
pwd
ls -la fix_completed_requests.py
```

---

## 🎉 Success!

If you've followed this guide and all verification steps pass, your CarbonCast environment is ready! 

**Next steps:**
1. Run `python start_automation.py` to begin
2. Set up your date ranges and control files
3. Monitor progress via the web dashboard at `http://localhost:5001`

**Happy automating! 🚀**

---

*Last updated: January 2025*
*For the latest version of this guide, check the [GitHub repository](../../README.md).*