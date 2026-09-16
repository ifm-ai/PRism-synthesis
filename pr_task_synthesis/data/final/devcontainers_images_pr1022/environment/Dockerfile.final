# Dockerfile.final - Anaconda devcontainer environment for Pillow security fix verification
# Base image: continuumio/anaconda3:latest (Debian Bullseye)

FROM continuumio/anaconda3:latest

# Install system packages required for the environment
RUN apt-get update && apt-get install -y \
    git \
    curl \
    bzip2 \
    ca-certificates \
    libglib2.0-0 \
    libsm6 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxinerama1 \
    libxrandr2 \
    libxrender1 \
    mercurial \
    openssh-client \
    procps \
    subversion \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create the benchmark runtime directory
RUN mkdir -p /opt/benchmark

# Copy the build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace from the repository
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create the conda environment and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set working directory to /workspace
WORKDIR /workspace

# Default command: activate conda environment and provide shell
CMD ["bash", "-c", "source /opt/conda/etc/profile.d/conda.sh && conda activate benchmark && exec bash"]
