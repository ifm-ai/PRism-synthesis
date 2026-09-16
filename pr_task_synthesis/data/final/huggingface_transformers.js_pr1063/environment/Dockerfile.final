FROM node:20-bookworm

# Install system packages
RUN apt-get update && apt-get install -y git curl git-lfs && git lfs install

# Copy build-context scripts to stable image paths
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/repo_setup.sh /opt/benchmark/setup_runtime.sh

# Materialize /workspace using repo_setup.sh BEFORE runtime setup
RUN /opt/benchmark/repo_setup.sh

# Run runtime setup AFTER repo is materialized
RUN /opt/benchmark/setup_runtime.sh

# Set working directory to /workspace
WORKDIR /workspace
