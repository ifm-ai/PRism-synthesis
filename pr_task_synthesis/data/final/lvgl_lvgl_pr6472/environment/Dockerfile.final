# LVGL Build Environment - Final Dockerfile
# Base image: debian:bookworm
# Purpose: Reproducible build environment for LVGL C graphics library

FROM debian:bookworm

# Set non-interactive mode for apt
ENV DEBIAN_FRONTEND=noninteractive

# Copy build-context scripts to stable image paths
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to install system packages and configure runtime
RUN /opt/benchmark/setup_runtime.sh

# Run repo_setup.sh to materialize /workspace from source
RUN /opt/benchmark/repo_setup.sh

# Set final working directory
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
