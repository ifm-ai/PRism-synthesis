# Dockerfile.final - cilium/cilium Go 1.22 benchmark environment
# Base image: debian:bookworm-slim
# Runtime: Go 1.22.0
# Fix location: pkg/clustermesh/common/remote_cluster.go (line 270)

FROM debian:bookworm-slim

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system packages
RUN apt-get update -qq && apt-get install -y -qq \
    git \
    curl \
    build-essential \
    pkg-config \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Go 1.22.0 from official Google download server
RUN curl -sL https://dl.google.com/go/go1.22.0.linux-amd64.tar.gz -o /tmp/go1.22.0.linux-amd64.tar.gz \
    && rm -rf /usr/local/go \
    && tar -C /usr/local -xzf /tmp/go1.22.0.linux-amd64.tar.gz \
    && rm /tmp/go1.22.0.linux-amd64.tar.gz

# Set Go environment variables
ENV PATH=/usr/local/go/bin:/root/go/bin:$PATH
ENV GOPATH=/root/go
ENV GOROOT=/usr/local/go
ENV GOOS=linux
ENV GOARCH=amd64

# Create benchmark directory for build scripts
RUN mkdir -p /opt/benchmark

# Copy build-context scripts
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Execute repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Execute setup_runtime.sh to install Go dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
