# Final Dockerfile for uv (Rust-based Python package installer)
# Base image: debian:bookworm
# Runtime: Rust 1.79 toolchain

FROM debian:bookworm

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV CARGO_HOME=/root/.cargo
ENV PATH=/root/.cargo/bin:$PATH

# Install system dependencies
RUN apt-get update && \
    apt-get install -y build-essential cmake pkg-config libssl-dev git curl && \
    rm -rf /var/lib/apt/lists/*

# Copy build-context scripts
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Materialize the repository workspace
RUN /opt/benchmark/repo_setup.sh

# Set up Rust 1.79 toolchain and runtime
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
