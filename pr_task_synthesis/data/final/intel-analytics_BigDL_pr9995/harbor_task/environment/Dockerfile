# BigDL-LLM Benchmark Environment
# Final authoritative packaging specification
# Base image: python:3.11-slim-bookworm

FROM python:3.11-slim-bookworm

# Set non-interactive mode for apt
ENV DEBIAN_FRONTEND=noninteractive

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    python3.11-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Copy build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Execute repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Execute setup_runtime.sh to create Python venv and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set final working directory
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
