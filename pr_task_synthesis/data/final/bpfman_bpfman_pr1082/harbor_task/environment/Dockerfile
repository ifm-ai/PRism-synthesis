# bpfman benchmark environment
# Base image: rust:1-slim
# Platform: linux (x86_64)

FROM rust:1-slim

# Install system packages required for bpfman eBPF development
RUN apt-get update && apt-get install -y \
    git \
    curl \
    clang \
    llvm \
    libbpf-dev \
    libelf-dev \
    protobuf-compiler \
    cmake \
    libssl-dev \
    gcc-multilib \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchains (stable and nightly)
# Note: rust:1-slim already has Rust installed, so we just need to add nightly
SHELL ["/bin/bash", "-c"]
RUN source /usr/local/cargo/env && rustup toolchain install nightly --profile minimal
RUN source /usr/local/cargo/env && rustup component add rust-src --toolchain nightly
SHELL ["/bin/sh", "-c"]

# Copy build-context scripts to stable image paths
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to build the project
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
