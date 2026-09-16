FROM python:3.11-slim

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install poetry via pip
RUN pip install --break-system-packages poetry

# Ensure poetry is in PATH
ENV PATH="/root/.local/bin:$PATH"

# Create benchmark directory for build scripts
RUN mkdir -p /opt/benchmark

# Copy repo_setup.sh to /opt/benchmark/ and make executable
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Copy setup_runtime.sh to /opt/benchmark/ and make executable
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh

# Run setup_runtime.sh to create Poetry environment
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace
