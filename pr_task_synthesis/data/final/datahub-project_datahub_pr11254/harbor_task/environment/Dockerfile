# DataHub metadata-ingestion benchmark environment
# Final Dockerfile for Buildah build

FROM python:3.11-slim

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    openjdk-21-jre-headless \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Set HOME for git config commands and ensure directory exists
ENV HOME=/root
RUN mkdir -p /root && chmod 700 /root

# Configure git for large repositories using explicit file path
RUN git config --file /root/.gitconfig http.proxyAuthMethod basic && \
    git config --file /root/.gitconfig http.lowSpeedLimit 0 && \
    git config --file /root/.gitconfig http.lowSpeedTime 999999 && \
    git config --file /root/.gitconfig http.version HTTP/1.1 && \
    git config --file /root/.gitconfig http.postBuffer 1048576000 && \
    git config --file /root/.gitconfig advice.defaultBranchName false

# Create workspace directory
RUN mkdir -p /workspace && chmod 777 /workspace
WORKDIR /workspace

# Copy build-context scripts
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize the repository
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create Python environment and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set final working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
