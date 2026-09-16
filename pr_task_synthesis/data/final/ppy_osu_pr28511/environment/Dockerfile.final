FROM mcr.microsoft.com/dotnet/sdk:8.0

# Install system packages
RUN apt-get update -qq && \
    apt-get install -y -qq git curl wget apt-transport-https && \
    rm -rf /var/lib/apt/lists/*

# Copy build-context scripts
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Materialize the workspace using repo_setup.sh FIRST
RUN /opt/benchmark/repo_setup.sh

# Run runtime setup AFTER repo is materialized
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
