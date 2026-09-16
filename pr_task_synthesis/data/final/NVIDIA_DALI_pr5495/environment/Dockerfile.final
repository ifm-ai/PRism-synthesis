# NVIDIA DALI Benchmark Environment
# Base image: nvidia/cuda:12.0.1-devel-ubuntu22.04
# Purpose: GPU-accelerated data loading library build environment

FROM nvidia/cuda:12.0.1-devel-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set CUDA environment variables
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Copy build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create the runtime environment (installs git and system packages)
RUN /opt/benchmark/setup_runtime.sh

# Run repo_setup.sh to materialize /workspace from git repository
RUN /opt/benchmark/repo_setup.sh

# Set working directory to workspace
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
