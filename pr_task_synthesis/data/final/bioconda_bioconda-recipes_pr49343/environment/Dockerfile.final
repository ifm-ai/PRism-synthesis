FROM condaforge/mambaforge:latest

# Note: condaforge/mambaforge:latest already has:
# - Mambaforge/conda pre-installed at /opt/conda
# - Basic system tools including git, curl (Debian bookworm base)
# - conda-forge channel pre-configured
# System compilers (gcc, g++) may need to be installed via conda if apt-get is unavailable

# Copy setup scripts to stable paths
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create bioconda environment
# This installs gcc_linux-64 and gxx_linux-64 from conda for compilation
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
