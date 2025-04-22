#!/bin/bash

# PhotoScanner Web Application Launcher
# This script starts the Flask web application with SocketIO support

# Navigate to the project root directory
cd "$(dirname "$0")"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found. Please install Python 3."
    exit 1
fi

# Check if the virtual environment exists, if not create it
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    
    echo "Installing dependencies..."
    ./venv/bin/pip install -e .
fi

# Activate the virtual environment
source venv/bin/activate

# Start the web application
echo "Starting PhotoScanner Web Application..."
python -m batchscan.web.app

# Deactivation happens automatically when the script ends

