# Babylon.js WebGPU Shader Fix Environment
# Base image: node:20-bookworm
# Purpose: Build and test environment for WGSL shader fixes

FROM node:20-bookworm

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for native modules and headless testing
RUN apt-get update -qq && apt-get install -y -qq \
    build-essential \
    ca-certificates \
    curl \
    git \
    libcairo2-dev \
    libjpeg-dev \
    libpango1.0-dev \
    libgif-dev \
    openssl \
    pkg-config \
    wget \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Create benchmark directory for build scripts
RUN mkdir -p /opt/benchmark

# Copy repo_setup.sh to materialize the workspace
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to clone and prepare the Babylon.js repository
RUN /opt/benchmark/repo_setup.sh

# Copy setup_runtime.sh for runtime configuration
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh

# Run setup_runtime.sh to install Node.js and npm dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set working directory to workspace
WORKDIR /workspace

# Image is ready for use - verifier assets (eval.sh, tests/) are runtime-mounted
# Verifier will execute tests via /opt/benchmark/eval.sh with mounted assets
