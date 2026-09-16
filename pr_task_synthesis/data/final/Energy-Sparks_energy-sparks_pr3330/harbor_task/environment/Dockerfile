# Final Dockerfile for Ruby on Rails benchmark environment
# Base image: ruby:3.1-bookworm
# This Dockerfile is the authoritative packaging specification

FROM ruby:3.1-bookworm

# Install system packages required for the Ruby on Rails application
RUN apt-get update -qq && apt-get install -y -qq \
    git \
    curl \
    postgresql-client \
    libpq-dev \
    nodejs \
    npm \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libreadline-dev \
    libsqlite3-dev \
    libxml2-dev \
    libxslt1-dev \
    ruby-dev \
    && rm -rf /var/lib/apt/lists/*

# Create the benchmark directory structure
RUN mkdir -p /opt/benchmark

# Copy build-context scripts into the image
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/repo_setup.sh /opt/benchmark/setup_runtime.sh

# Run repo_setup.sh to materialize /workspace from the repository
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to install Ruby dependencies via bundler
# This must run after repo_setup.sh since it needs the Gemfile
RUN /opt/benchmark/setup_runtime.sh

# Set the working directory to /workspace
WORKDIR /workspace

# The image is now ready for RL agent use
# Note: eval.sh and test.patch are runtime-mounted verifier assets
# and are NOT baked into this image
