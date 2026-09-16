# Final Dockerfile for datadog-agent containerd workloadmeta collector benchmark
# Base image: golang:1.21

FROM golang:1.21

# Set environment variables for Go
ENV PATH=/usr/local/go/bin:$PATH
ENV GOPATH=/root/go
ENV GOROOT=/usr/local/go

# Install system packages required for building datadog-agent
RUN apt-get update -qq && \
    apt-get install -y -qq git curl cmake g++ python3 python3-dev libseccomp-dev python3.11-venv && \
    rm -rf /var/lib/apt/lists/*

# Create the benchmark directory for verifier assets
RUN mkdir -p /opt/benchmark

# Copy repo_setup.sh and execute it to materialize /workspace
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh && \
    /opt/benchmark/repo_setup.sh

# Copy setup_runtime.sh and execute it as a separate build step
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh && \
    /opt/benchmark/setup_runtime.sh

# Set the final working directory to /workspace
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
