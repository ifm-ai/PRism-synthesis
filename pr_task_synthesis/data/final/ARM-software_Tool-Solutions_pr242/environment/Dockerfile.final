# MLCommons RNNT Speech Recognition Benchmark Environment
# Base image: ubuntu:22.04
# Python 3.11 venv at /opt/benchmark/mlcommons-venv

FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install base system packages
RUN apt-get update -qq && apt-get install -y -qq \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set Python alternatives
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Create /opt/benchmark directory
RUN mkdir -p /opt/benchmark

# Copy repo_setup.sh from build context
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh

# Copy setup_runtime.sh from build context
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh

# Run repo_setup.sh to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create Python virtualenv and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set working directory to /workspace
WORKDIR /workspace

# Default command (eval.sh is runtime-mounted, not baked into image)
CMD ["/bin/bash"]
