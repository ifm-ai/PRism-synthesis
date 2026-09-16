# Final Dockerfile for Rust benchmark environment
# Base image: debian:bookworm-slim
# Rust toolchain: 1.75.0
# Target: firezone-relay package with proptest feature

FROM debian:bookworm-slim

# Install system packages required for Rust development
RUN apt-get update && apt-get install -y \
    git \
    curl \
    pkg-config \
    libssl-dev \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Rust 1.75.0 via rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init -o /tmp/rustup-init && \
    chmod +x /tmp/rustup-init && \
    /tmp/rustup-init --default-toolchain 1.75.0 -y --no-modify-path && \
    rm /tmp/rustup-init

# Set environment variables for Rust toolchain
ENV RUSTUP_HOME=/root/.rustup
ENV CARGO_HOME=/root/.cargo
ENV PATH="/root/.cargo/bin:$PATH"

# Verify Rust installation
RUN rustup default 1.75.0 && rustc --version && cargo --version

# Copy build-context scripts
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh first to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to prepare environment (Rust already installed)
RUN /opt/benchmark/setup_runtime.sh

# Set the working directory to /workspace
WORKDIR /workspace

# The image is now ready for the RL agent to run tests
# eval.sh and test.patch are runtime-mounted at /opt/benchmark/
# Test command: cd /workspace/rust && cargo test --package firezone-relay --features proptest ping_pong_ip6_relay
