#!/bin/bash

# Deploy files to ESP32 via mpremote
# Usage: ./deploy.sh [-r] [-p] [files...]
# -r: Reset device after deployment
# -p: Install packages from requirements.txt

RESET=false
PACKAGES=false
FILES=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--reset)
            RESET=true
            shift
            ;;
        -p|--packages)
            PACKAGES=true
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

# Install packages if requested
if [ "$PACKAGES" = true ]; then
    if [ -f "requirements.txt" ]; then
        echo "Installing packages from requirements.txt..."
        while IFS= read -r line; do
            # Skip comments and empty lines
            if [[ ! "$line" =~ ^[[:space:]]*# ]] && [[ -n "${line// }" ]]; then
                package=$(echo "$line" | awk '{print $1}')
                if [[ -n "$package" ]]; then
                    echo "Installing $package..."
                    mpremote mip install "$package"
                fi
            fi
        done < requirements.txt
    else
        echo "Warning: requirements.txt not found, skipping package installation..."
    fi
fi

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