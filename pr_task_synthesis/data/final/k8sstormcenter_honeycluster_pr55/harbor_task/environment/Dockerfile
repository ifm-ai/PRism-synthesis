# Dockerfile.final - Authoritative packaging spec for HoneyCluster benchmark
# Base image: debian:bookworm-slim

FROM debian:bookworm-slim

# Set non-interactive mode for apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Install system packages
RUN apt-get update && apt-get install -y \
    git \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy repo_setup.sh and execute it to materialize /workspace
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh && /opt/benchmark/repo_setup.sh

# Copy setup_runtime.sh and execute it
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh && /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
