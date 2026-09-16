# LightGBM CI Environment - Final Dockerfile
# Base image: Ubuntu 22.04
# Purpose: Reproducible environment for testing LightGBM pip install --user fix

FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Set workspace directory
ENV WORKSPACE=/workspace

# Install system packages required for LightGBM build
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    cmake \
    build-essential \
    libomp-dev \
    libboost-dev \
    ocl-icd-opencl-dev \
    openmpi-bin \
    libopenmpi-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy build-context scripts into the image
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/repo_setup.sh /opt/benchmark/setup_runtime.sh

# Run repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create conda environment and build LightGBM
RUN /opt/benchmark/setup_runtime.sh

# Set working directory to workspace
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
