#!/bin/bash

# Create directories for g4f
echo "Creating directories for g4f..."
mkdir -p har_and_cookies generated_media

# Set permissions (adjust based on your system)
# On macOS/Linux without sudo requirements:
chmod -R 777 har_and_cookies generated_media

echo "Directories created and permissions set."
echo ""
echo "Now you can run: docker-compose up --build"