# Final Dockerfile for Ministry of Justice Modernisation Platform
# Terraform infrastructure as code benchmark environment
# Base image: golang:1.23.2 (includes Go, git, curl, and debian base)

FROM golang:1.23.2

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set Go environment variables (Go is pre-installed in this image)
ENV GOROOT=/usr/local/go
ENV GOPATH=/home/agent_sandbox/go
ENV PATH=$GOROOT/bin:$GOPATH/bin:$PATH
ENV GOPROXY=http://mirror.proxy.hpc:8081/repository/go-proxy/,direct

# Install base system packages (git and curl are already included in golang base image)
RUN apt-get update && apt-get install -y \
    jq \
    unzip \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create workspace directory
RUN mkdir -p /workspace && chmod 777 /workspace

# Create opt/benchmark directory for setup scripts
RUN mkdir -p /opt/benchmark

# Copy setup scripts from build context
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/repo_setup.sh /opt/benchmark/setup_runtime.sh

# Run repo_setup.sh to materialize the repository at /workspace
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to install runtime dependencies (Go, conftest, Terraform)
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
