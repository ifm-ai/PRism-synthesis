# Apache Arrow C++ Parquet Benchmark Environment
# Final reproducible image specification
# Base image: ubuntu:22.04

FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system packages required for the build environment
RUN apt-get update && \
    apt-get install -y \
        git \
        curl \
        build-essential \
        pkg-config \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Create benchmark artifacts directory for runtime scripts
RUN mkdir -p /opt/benchmark

# Copy setup scripts from build context
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Step 1: Materialize the workspace repository using repo_setup.sh
RUN /opt/benchmark/repo_setup.sh

# Step 2: Install Miniconda for conda package management
RUN curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh

# Step 3: Set up the conda runtime environment with C++ dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set the working directory to the workspace root
WORKDIR /workspace

# Default command: activate conda environment and provide shell
CMD ["bash", "-c", "source /opt/conda/etc/profile.d/conda.sh && conda activate arrow-cpp && exec bash"]
