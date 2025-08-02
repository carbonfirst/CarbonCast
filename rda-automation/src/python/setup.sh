#!/bin/bash
# Setup script for Batch Automation System

echo "Setting up Batch Automation System..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p logs
mkdir -p downloaded_files
mkdir -p templates

# Set permissions
chmod +x batch_automation_integrated.py
chmod +x batch_automation.py
chmod +x batch_queue_manager.py
chmod +x batch_monitor.py

echo "Setup complete!"
echo ""
echo "To run the system:"
echo "  source venv/bin/activate"
echo "  python batch_automation_integrated.py --process-all-control-files"
echo ""
echo "To view the dashboard:"
echo "  python batch_automation_integrated.py --monitor-dashboard"
