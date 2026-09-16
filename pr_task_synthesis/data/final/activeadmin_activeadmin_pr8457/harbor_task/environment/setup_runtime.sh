#!/usr/bin/env bash
# Setup runtime script for activeadmin Ruby on Rails project
# This script creates the Ruby environment and installs dependencies
set -e

echo "=== Setting up Ruby runtime environment ==="

# Ensure we're using the system Ruby from the base image
RUBY_VERSION=$(ruby --version 2>&1 | head -1)
echo "Using Ruby: $RUBY_VERSION"

# Check Bundler version
BUNDLER_VERSION=$(bundle --version 2>&1 | head -1)
echo "Using Bundler: $BUNDLER_VERSION"

# Configure Bundler settings for consistent behavior
# Use system path for gems (no vendor/bundle) for container environments
bundle config set --local path '' 2>/dev/null || true
bundle config set --local without 'development rubocop' 2>/dev/null || true
bundle config set --local suppress_suggestions true 2>/dev/null || true

echo "=== Installing gem dependencies ==="

# Install dependencies from Gemfile.lock
# The working directory should be /workspace where the Gemfile is located
cd /workspace

# Run bundle install to install all test dependencies
bundle install --jobs=4 --retry=3

echo "=== Verifying RSpec is available ==="
bundle exec rspec --version

echo "=== Runtime setup complete ==="
