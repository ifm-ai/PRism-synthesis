# Dockerfile.final - Apache Arrow Rust (arrow-rs) benchmark environment
# Base image: rust:1.70-slim-bookworm

FROM rust:1.70-slim-bookworm

# Set environment variables for Rust toolchain
ENV CARGO_HOME=/root/.cargo
ENV RUSTUP_HOME=/root/.rustup
ENV PATH="/root/.cargo/bin:${PATH}"

# Install system packages required for building Rust projects
RUN apt-get update && apt-get install -y \
    git \
    curl \
    pkg-config \
    libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create the benchmark scripts directory
RUN mkdir -p /opt/benchmark

# Copy the colocated build-context scripts
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Step 1: Run repo_setup.sh to materialize /workspace from the Apache Arrow Rust repository
RUN /opt/benchmark/repo_setup.sh

# Step 2: Run setup_runtime.sh to install Rust toolchain and fetch dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set the working directory to /workspace
WORKDIR /workspace

# Default command - the image is ready for RL agent use
CMD ["/bin/bash"]
