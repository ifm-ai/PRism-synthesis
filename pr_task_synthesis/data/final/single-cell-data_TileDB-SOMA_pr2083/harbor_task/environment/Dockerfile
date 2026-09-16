# TileDB-SOMA Python Environment
# Base image: python:3.11-slim
# Purpose: Reproducible environment for testing df_to_arrow fix for all-null columns

FROM python:3.11-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV LD_LIBRARY_PATH=/workspace/dist/lib:/workspace/build/externals/install/lib
# Note: CXXFLAGS for dangling-reference suppression is handled conditionally in setup_runtime.sh
# to support both g++ 12 (no flag needed) and g++ 13+ (flag required for spdlog/fmt compatibility)

# Install system packages required for building native extensions
RUN apt-get update -qq && \
    apt-get install -y -qq \
        cmake \
        libssl-dev \
        pkg-config \
        python3-venv \
        patch \
        python3-dev \
        g++ \
        git \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Create directories for benchmark artifacts
RUN mkdir -p /opt/benchmark && chmod 755 /opt/benchmark

# Copy build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Step 1: Run repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Step 2: Run setup_runtime.sh to create the Python virtual environment and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set the final working directory
WORKDIR /workspace

# Default command: activate venv and run eval.sh
# The RL agent will run: cd /workspace && source /opt/benchmark/venv/bin/activate && /opt/benchmark/eval.sh
CMD ["/bin/bash", "-c", "source /opt/benchmark/venv/bin/activate && /opt/benchmark/eval.sh"]
