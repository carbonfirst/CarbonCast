#!/bin/bash
# Enhanced Setup Script for CarbonCast Automation System
# This script ensures proper dependency installation and verification

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}\n"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python_version() {
    print_status "Checking Python version..."
    
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.8 or higher."
        exit 1
    fi
    
    python_version=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
    required_version="3.8"
    
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        print_success "Python $python_version detected (>= $required_version required)"
    else
        print_error "Python $python_version detected, but Python $required_version or higher is required"
        exit 1
    fi
}

# Function to create and activate virtual environment
setup_virtual_environment() {
    print_status "Setting up virtual environment..."
    
    if [ ! -d "venv" ]; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
        if [ $? -eq 0 ]; then
            print_success "Virtual environment created successfully"
        else
            print_error "Failed to create virtual environment"
            exit 1
        fi
    else
        print_warning "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    print_status "Activating virtual environment..."
    source venv/bin/activate
    
    if [ $? -eq 0 ]; then
        print_success "Virtual environment activated"
    else
        print_error "Failed to activate virtual environment"
        exit 1
    fi
    
    # Upgrade pip
    print_status "Upgrading pip..."
    pip install --upgrade pip
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing dependencies from root requirements.txt..."
    
    # Check if root requirements.txt exists
    if [ ! -f "../../requirements.txt" ]; then
        print_error "requirements.txt not found in root directory"
        print_error "Make sure the root requirements.txt file exists"
        exit 1
    fi
    
    # Install requirements from root directory
    pip install -r ../../requirements.txt
    
    if [ $? -eq 0 ]; then
        print_success "Dependencies installed successfully from root requirements.txt"
    else
        print_error "Failed to install dependencies from root requirements.txt"
        exit 1
    fi
}

# Function to verify critical imports
verify_imports() {
    print_status "Verifying critical imports..."
    
    # Test critical imports
    python3 -c "
import sys
import os
failed_imports = []

# Test core dependencies
try:
    import requests
    print('✅ requests - OK')
except ImportError as e:
    failed_imports.append(('requests', str(e)))
    print('❌ requests - FAILED')

try:
    import flask
    print('✅ flask - OK')
except ImportError as e:
    failed_imports.append(('flask', str(e)))
    print('❌ flask - FAILED')

try:
    import flask_cors
    print('✅ flask-cors - OK')
except ImportError as e:
    failed_imports.append(('flask_cors', str(e)))
    print('❌ flask-cors - FAILED')

try:
    import psutil
    print('✅ psutil - OK')
except ImportError as e:
    failed_imports.append(('psutil', str(e)))
    print('❌ psutil - FAILED')

try:
    import yaml
    print('✅ pyyaml - OK')
except ImportError as e:
    failed_imports.append(('yaml', str(e)))
    print('❌ pyyaml - FAILED')

try:
    import numpy
    print('✅ numpy - OK')
except ImportError as e:
    failed_imports.append(('numpy', str(e)))
    print('❌ numpy - FAILED')

try:
    import pandas
    print('✅ pandas - OK')
except ImportError as e:
    failed_imports.append(('pandas', str(e)))
    print('❌ pandas - FAILED')

# Test project-specific modules
try:
    import fix_completed_requests
    print('✅ fix_completed_requests - OK')
except ImportError as e:
    failed_imports.append(('fix_completed_requests', str(e)))
    print('❌ fix_completed_requests - FAILED')

if failed_imports:
    print(f'\n❌ {len(failed_imports)} import(s) failed:')
    for module, error in failed_imports:
        print(f'   - {module}: {error}')
    sys.exit(1)
else:
    print('\n✅ All critical imports verified successfully')
"
    
    if [ $? -eq 0 ]; then
        print_success "All critical imports verified"
    else
        print_error "Some imports failed. Please check the error messages above."
        exit 1
    fi
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    directories=("logs" "downloaded_files" "data" "templates")
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            print_success "Created directory: $dir"
        else
            print_warning "Directory already exists: $dir"
        fi
    done
}

# Function to set file permissions
set_permissions() {
    print_status "Setting file permissions..."
    
    # List of Python files that should be executable
    executable_files=(
        "batch_automation_integrated.py"
        "batch_automation.py"
        "batch_queue_manager.py"
        "batch_monitor.py"
        "start_automation.py"
        "fix_completed_requests.py"
    )
    
    for file in "${executable_files[@]}"; do
        if [ -f "$file" ]; then
            chmod +x "$file"
            print_success "Set executable permission: $file"
        else
            print_warning "File not found (skipping): $file"
        fi
    done
}

# Function to verify setup
verify_setup() {
    print_status "Running final setup verification..."
    
    # Check if we can import the main automation modules
    python3 -c "
try:
    # Test basic automation imports
    import sys
    import os
    
    # Add current directory to path
    sys.path.insert(0, os.getcwd())
    
    # Test key modules
    import fix_completed_requests
    print('✅ fix_completed_requests module can be imported')
    
    # Test if we can create basic objects
    from fix_completed_requests import setup_logging
    logger = setup_logging()
    print('✅ Logging setup works')
    
    print('✅ Setup verification completed successfully')
    
except Exception as e:
    print(f'❌ Setup verification failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"
    
    if [ $? -eq 0 ]; then
        print_success "Setup verification completed"
    else
        print_error "Setup verification failed"
        exit 1
    fi
}

# Function to display usage instructions
display_usage() {
    print_header "SETUP COMPLETED SUCCESSFULLY!"
    
    echo -e "${GREEN}Your CarbonCast automation environment is now ready!${NC}\n"
    
    echo -e "${BLUE}To get started:${NC}"
    echo -e "  1. Make sure you're in the src/python directory"
    echo -e "  2. Activate the virtual environment:"
    echo -e "     ${YELLOW}source venv/bin/activate${NC}"
    echo -e "  3. Set up your RDA token:"
    echo -e "     ${YELLOW}echo 'your_rda_token_here' > rdams_token.txt${NC}"
    echo -e "  4. Run the automation system:"
    echo -e "     ${YELLOW}python start_automation.py${NC}"
    echo -e "  5. Or run the integrated batch automation:"
    echo -e "     ${YELLOW}python batch_automation_integrated.py --process-all-control-files${NC}"
    echo -e "  6. To view the dashboard:"
    echo -e "     ${YELLOW}python batch_automation_integrated.py --monitor-dashboard${NC}"
    
    echo -e "\n${BLUE}Additional tools:${NC}"
    echo -e "  • Fix completed requests: ${YELLOW}python fix_completed_requests.py --help${NC}"
    echo -e "  • Verify dependencies: ${YELLOW}python verify_dependencies.py${NC}"
    echo -e "  • Check system status: ${YELLOW}python automation/sequential_file_processor.py --status${NC}"
    
    echo -e "\n${BLUE}For help and documentation:${NC}"
    echo -e "  • Setup guide: ${YELLOW}docs/Setup_Guide.md${NC}"
    echo -e "  • Troubleshooting: ${YELLOW}docs/Troubleshooting_Guide.md${NC}"
    echo -e "  • Main README: ${YELLOW}../../README.md${NC}"
    
    echo -e "\n${GREEN}Happy automating! 🚀${NC}\n"
}

# Main execution
main() {
    print_header "CarbonCast Automation System Setup"
    
    # Check if we're in the right directory
    if [ ! -f "fix_completed_requests.py" ]; then
        print_error "This script must be run from the src/python/ directory"
        print_error "Current directory: $(pwd)"
        print_error "Please navigate to the src/python/ directory and run: ./setup.sh"
        exit 1
    fi
    
    print_status "Starting enhanced setup process..."
    
    # Run setup steps
    check_python_version
    setup_virtual_environment
    install_dependencies
    verify_imports
    create_directories
    set_permissions
    verify_setup
    display_usage
    
    print_success "Setup completed successfully! 🎉"
}

# Handle script interruption
trap 'print_error "Setup interrupted by user"; exit 1' INT

# Run main function
main "$@"
