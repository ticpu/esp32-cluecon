#!/bin/bash

# Deploy files to ESP32 via mpremote
# Usage: ./deploy.sh [-r] [files...]
# -r: Reset device after deployment

RESET=false
FILES=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--reset)
            RESET=true
            shift
            ;;
        *)
            FILES+=("$1")
            shift
            ;;
    esac
done

# Default files if none specified
if [ ${#FILES[@]} -eq 0 ]; then
    FILES=("boot.py" "main.py")
fi

echo "Deploying files to ESP32..."

# Deploy each file
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "Copying $file..."
        mpremote fs cp "$file" ":$file"
    else
        echo "Warning: $file not found, skipping..."
    fi
done

# Reset if requested
if [ "$RESET" = true ]; then
    echo "Resetting device..."
    mpremote reset
fi

echo "Deployment complete!"