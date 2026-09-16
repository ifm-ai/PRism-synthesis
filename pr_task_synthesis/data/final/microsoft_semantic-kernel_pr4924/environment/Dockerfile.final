# Semantic Kernel Benchmark Environment
# Base image: python:3.10-slim

FROM python:3.10-slim

# Install system packages
RUN apt-get update -qq && \
    apt-get install -y -qq git curl python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

# Create benchmark scripts directory
RUN mkdir -p /opt/benchmark

# Copy setup scripts from build context
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh first to clone the repository
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to set up Python environment with poetry
RUN /opt/benchmark/setup_runtime.sh

# Set final working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
