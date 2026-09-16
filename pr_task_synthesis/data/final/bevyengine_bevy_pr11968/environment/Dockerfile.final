# Bevy Benchmark Environment - Final Dockerfile
# Base image: debian:bookworm
# Runtime: Rust stable via rustup
# Project: Bevy v0.13.0 (Rust game engine)

FROM debian:bookworm

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system packages required for Bevy development
RUN apt-get update && apt-get install -y \
    git \
    curl \
    pkg-config \
    libasound2-dev \
    libudev-dev \
    libwayland-dev \
    libxkbcommon-dev \
    ca-certificates \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace with the Bevy repository
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to install Rust toolchain
RUN /opt/benchmark/setup_runtime.sh

# Set environment variables for Rust
ENV RUSTUP_HOME=/opt/rustup
ENV CARGO_HOME=/opt/cargo
ENV PATH="$CARGO_HOME/bin:$PATH"

# Set working directory to /workspace
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
