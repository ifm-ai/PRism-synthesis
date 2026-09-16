FROM python:3.11-slim

# Configure pip for proxy environment
ENV PIP_INDEX_URL=http://mirror.proxy.hpc:8081/repository/pypi-proxy/simple/
ENV PIP_TRUSTED_HOST=mirror.proxy.hpc
ENV PIP_DEFAULT_TIMEOUT=300

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libblas-dev \
    liblapack-dev \
    liblapacke-dev \
    git \
    curl \
    python3-venv \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create benchmark directory
RUN mkdir -p /opt/benchmark

# Create pip.conf with timeout configuration for large package downloads (e.g., torch ~2GB)
RUN mkdir -p /root/.pip && echo -e "[global]\nindex-url = http://mirror.proxy.hpc:8081/repository/pypi-proxy/simple/\ntrusted-host = mirror.proxy.hpc\ntimeout = 300" > /root/.pip/pip.conf

# Copy build-context scripts
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/repo_setup.sh /opt/benchmark/setup_runtime.sh

# Run repo_setup.sh first to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create the runtime environment
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace
