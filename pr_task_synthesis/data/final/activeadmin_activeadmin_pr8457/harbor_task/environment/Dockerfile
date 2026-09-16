# Final Dockerfile for activeadmin/activeadmin environment
# Based on environment_request.json specification

FROM ruby:3.2

# Install system packages required for Ruby/Rails development
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    pkg-config \
    libsqlite3-dev \
    ruby-dev \
    libyaml-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Create directory for benchmark scripts
RUN mkdir -p /opt/benchmark

# Copy repo_setup.sh and execute to materialize /workspace
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh && /opt/benchmark/repo_setup.sh

# Copy setup_runtime.sh and execute to install Ruby dependencies
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh && /opt/benchmark/setup_runtime.sh

# Set working directory to the materialized workspace
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
