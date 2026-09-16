# Microsoft Recognizers Text Benchmark Environment
# Final Dockerfile for reproducible container builds

FROM debian:bookworm

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system packages
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        python3 \
        python3-pip \
        python3-venv \
        nodejs \
        npm && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create benchmark directory for setup scripts
RUN mkdir -p /opt/benchmark

# Copy repo setup script from build context
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Copy runtime setup script from build context
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh

# Run setup_runtime.sh to create venv and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
