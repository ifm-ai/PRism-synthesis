# TileDB-Vector-Search Benchmark Environment
# Final Dockerfile for reproducible container builds
FROM python:3.11-slim-bookworm

# Install system packages required for building and runtime
RUN apt-get update && apt-get install -y \
    git \
    curl \
    python3.11-venv \
    python3.11-dev \
    libopenblas-dev \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Create benchmark directories
RUN mkdir -p /opt/benchmark /workspace && chmod 777 /workspace

# Copy repo_setup.sh from build context and execute it to materialize /workspace
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh && /opt/benchmark/repo_setup.sh

# Copy setup_runtime.sh from build context and execute it to create runtime
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh && /opt/benchmark/setup_runtime.sh

# Set working directory to /workspace for test execution
WORKDIR /workspace

# Default command: activate environment and run tests
# Note: eval.sh is mounted at runtime as a verifier asset
CMD ["/bin/bash"]
