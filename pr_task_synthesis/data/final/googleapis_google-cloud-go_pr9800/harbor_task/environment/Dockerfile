# Final Dockerfile for Google Cloud Client Libraries for Go benchmark environment
# Base image: golang:1.21

FROM golang:1.21

# Install system packages
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy repo setup script and execute it to materialize /workspace
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh && /opt/benchmark/repo_setup.sh

# Copy runtime setup script and execute it to configure Go environment
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh && /opt/benchmark/setup_runtime.sh

# Set working directory to /workspace for test execution
WORKDIR /workspace

# Default command (eval.sh will be mounted at runtime)
CMD ["/bin/bash"]
