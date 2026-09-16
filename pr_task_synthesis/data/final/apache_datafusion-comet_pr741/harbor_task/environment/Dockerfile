# DataFusion Comet Benchmark Environment
# Base image: rust:1.79-slim-bookworm
FROM rust:1.79-slim-bookworm

# Install system packages required for the build
RUN apt-get update && apt-get install -y \
    git \
    curl \
    protobuf-compiler \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create the benchmark scripts directory
RUN mkdir -p /opt/benchmark

# Copy build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to set up the Rust environment
RUN /opt/benchmark/setup_runtime.sh

# Set the working directory
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
