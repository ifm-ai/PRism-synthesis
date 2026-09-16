# AutoGPTQ Benchmark Environment
# Base image: python:3.11-slim
# Purpose: RL agent benchmark environment for AutoGPTQ Marlin format support

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update -qq && apt-get install -y -qq \
    git \
    curl \
    python3-pip \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create benchmark directory
RUN mkdir -p /opt/benchmark

# Copy build-context scripts
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create Python venv and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set working directory for RL agent
WORKDIR /workspace

# Default command: activate venv and leave shell ready
CMD ["/bin/bash"]
