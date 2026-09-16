# Apache NuttX RTOS Benchmark Environment
# Base image: ubuntu:22.04
# This Dockerfile is the authoritative packaging spec for the container image

FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set workspace directory
ENV WORKSPACE=/workspace

# Install system packages required for NuttX build
RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    build-essential \
    gcc \
    g++ \
    make \
    cmake \
    bison \
    flex \
    gawk \
    gperf \
    libncurses5-dev \
    gcc-arm-none-eabi \
    git \
    curl \
    ninja-build \
    python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create benchmark directory for runtime scripts
RUN mkdir -p /opt/benchmark

# Copy repo_setup.sh from build context and execute it to materialize /workspace
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh && \
    /opt/benchmark/repo_setup.sh

# Copy setup_runtime.sh from build context and execute it
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh && \
    /opt/benchmark/setup_runtime.sh

# Set final working directory
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
