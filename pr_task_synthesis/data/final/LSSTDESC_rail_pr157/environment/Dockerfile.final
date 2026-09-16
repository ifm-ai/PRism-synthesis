# Final Dockerfile for pz-rail environment
# Base image: python:3.11-slim
# This image is built from structured environment artifacts

FROM python:3.11-slim

# Install system packages required for the environment
# Note: python3.11-venv and python3-pip are NOT needed - python:3.11-slim includes them
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    openmpi-bin \
    libopenmpi-dev \
    hdf5-tools \
    libhdf5-openmpi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh first to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create the Python virtual environment and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set the working directory to /workspace
WORKDIR /workspace

# Default command: activate the virtual environment
CMD ["/bin/bash"]
