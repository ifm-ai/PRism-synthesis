#!/usr/bin/env bash
# setup_runtime.sh - Build-time runtime creation for Ruby on Rails application
# This script creates the primary runtime environment and installs dependencies

set -e

echo "=== Setting up Ruby on Rails runtime environment ==="

# Verify Ruby is available
if ! command -v ruby &> /dev/null; then
    echo "ERROR: Ruby is not installed"
    exit 1
fi

# Bundler is pre-installed in ruby:3.1-bookworm (version 2.3.7)
# No network access needed for bundler installation
echo "Bundler version: $(bundler --version)"

# Prime gem is included as a default gem in Ruby 3.1-bookworm
# No network access needed for prime installation
ruby -e "require 'prime'; puts 'prime gem available'"

# Verify yarn is available (Node.js should be pre-installed)
if ! command -v yarn &> /dev/null; then
    echo "Installing yarn via npm..."
    npm install -g yarn 2>/dev/null || echo "Yarn install skipped"
fi

# Create a system-wide bundle path
BUNDLE_PATH="/opt/benchmark/vendor/bundle"
mkdir -p "$BUNDLE_PATH"

# Export bundle configuration
export BUNDLE_PATH="$BUNDLE_PATH"
export BUNDLE_APP_CONFIG="/opt/benchmark/.bundle"
mkdir -p "$BUNDLE_APP_CONFIG"

# Configure bundler to install gems to the common location
bundle config set path "$BUNDLE_PATH"

echo "=== Installing project dependencies ==="

# Install project dependencies using bundler
# This will be run after the workspace is copied
# Explicitly cd to /workspace to ensure Gemfile is found during Docker build
if [ -f "/workspace/Gemfile" ]; then
    cd /workspace
    # Add prime gem if not already present (required by distribution/statsample for Ruby 3.x)
    if ! grep -q "^gem 'prime'" Gemfile; then
        echo "gem 'prime'" >> Gemfile
        echo "Added 'prime' gem to Gemfile (required by distribution/statsample)"
    fi
    # Configure bundler to include test and development groups for full functionality
    bundle config set path "$BUNDLE_PATH"
    bundle config set with 'development test'
    bundle install --jobs=4 --retry=3 || {
        echo "WARNING: bundle install failed (network issue?)"
        echo "Dependencies will need to be installed when network is available"
    }
fi

echo "=== Runtime environment created ==="
echo "BUNDLE_PATH=$BUNDLE_PATH"
echo "BUNDLE_APP_CONFIG=$BUNDLE_APP_CONFIG"
