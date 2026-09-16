# ANTsPy Benchmark Environment - Final Dockerfile
# This Dockerfile creates a reproducible environment for ANTsPy benchmark testing.
# It uses a pre-built antspyx wheel from PyPI to avoid complex C++ compilation.

FROM python:3.11-slim-bookworm

# Set environment variables for non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for ANTsPy runtime
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        cmake \
        libblas-dev \
        liblapack-dev \
        gfortran \
        libpng-dev \
        python3-dev \
        git \
        curl \
        python3-pip \
        python3.11-venv \
    && rm -rf /var/lib/apt/lists/*

# Create directories for benchmark artifacts
RUN mkdir -p /opt/benchmark /workspace && chmod 777 /workspace

# Copy build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace from the repository
# This clones the ANTsPy repository at the specified commit
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create the Python virtual environment and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set the working directory to /workspace
WORKDIR /workspace

# Default command: activate the virtual environment and provide a shell
CMD ["bash"]
