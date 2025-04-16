#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "antenv" ]; then
    echo "Creating virtual environment..."
    python -m venv antenv
fi

# Activate virtual environment
source .venv/bin/activate

# Update pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Start the application
uvicorn main:app --host 0.0.0.0 --port 8000 --reload


playwright install chromium

