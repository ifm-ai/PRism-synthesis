# Final Dockerfile for gudhi-devel environment
# Base image: python:3.11-slim

FROM python:3.11-slim

# Set working directory early
WORKDIR /workspace

# Install system packages
RUN apt-get update -qq && \
    apt-get install -y -qq cmake build-essential pkg-config python3-venv git curl && \
    rm -rf /var/lib/apt/lists/*

# Copy build-context scripts to /opt/benchmark
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create Python venv and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set final working directory
WORKDIR /workspace

# Default command (eval.sh will be mounted at runtime)
CMD ["/bin/bash"]
