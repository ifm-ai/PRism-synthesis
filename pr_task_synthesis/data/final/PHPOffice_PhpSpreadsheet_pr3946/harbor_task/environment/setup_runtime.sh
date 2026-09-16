#!/bin/bash
set -e

# setup_runtime.sh - Runtime creation script for PHPSpreadsheet benchmark environment
# This script installs Composer and project dependencies
# It assumes PHP 8.2+ is already installed (from php:8.2-cli base image)
# and required extensions have been installed via docker-php-ext-install

echo "=== PHPSpreadsheet Runtime Setup ==="

# Check PHP availability
echo "Checking PHP installation..."
if ! command -v php &> /dev/null; then
    echo "ERROR: PHP is not installed. Please use php:8.2-cli base image."
    exit 1
fi

php --version
echo "PHP is available."

# Check/install Composer
echo "Checking Composer installation..."
if ! command -v composer &> /dev/null; then
    echo "ERROR: Composer is not installed. It should be installed in the Dockerfile."
    exit 1
else
    composer --version
fi
echo "Composer is available."

# Verify required PHP extensions
echo "Verifying required PHP extensions..."
REQUIRED_EXTENSIONS="ctype dom gd iconv fileinfo mbstring simplexml xml xmlreader xmlwriter zip"
MISSING_EXTENSIONS=""

for ext in $REQUIRED_EXTENSIONS; do
    if ! php -m | grep -qi "^${ext}$"; then
        MISSING_EXTENSIONS="${MISSING_EXTENSIONS} ${ext}"
    fi
done

if [ -n "$MISSING_EXTENSIONS" ]; then
    echo "WARNING: Missing PHP extensions:${MISSING_EXTENSIONS}"
    echo "These should be installed via docker-php-ext-install in the base image."
fi

echo "PHP extensions check complete."

# Install project dependencies in workspace
WORKSPACE="${WORKSPACE:-/workspace}"
echo "Installing project dependencies in ${WORKSPACE}..."

cd "${WORKSPACE}"

# Run composer install to install dependencies
composer install --no-progress --prefer-dist --optimize-autoloader

echo "=== Runtime setup complete ==="
echo "PHP version: $(php --version | head -1)"
echo "Composer version: $(composer --version)"
echo "Dependencies installed successfully."

exit 0
