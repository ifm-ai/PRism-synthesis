# PlayCanvas Engine Benchmark Environment
# Base image: node:18-bookworm
# Repository: PlayCanvas engine at commit 1aac7ee7bcc6491e655804b94db4478743bb4e6b

FROM node:18-bookworm

# Install system packages
RUN apt-get update && \
    apt-get install -y git curl xvfb npm chromium && \
    rm -rf /var/lib/apt/lists/*

# Create benchmark directory for scripts
RUN mkdir -p /opt/benchmark && chmod 755 /opt/benchmark

# Copy build-context scripts
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/repo_setup.sh /opt/benchmark/setup_runtime.sh

# Run repo_setup.sh to clone and materialize the repository
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace

# Default command - eval.sh will be invoked at runtime
CMD ["/bin/bash"]
