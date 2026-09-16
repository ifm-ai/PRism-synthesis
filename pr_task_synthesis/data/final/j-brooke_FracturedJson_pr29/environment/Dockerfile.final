# Final Dockerfile for .NET JSON formatter with NumberListAlignment enum fix
# Base image: mcr.microsoft.com/dotnet/sdk:8.0

FROM mcr.microsoft.com/dotnet/sdk:8.0

# Install system packages (base image already has git and curl)
RUN apt-get update -qq && apt-get install -y -qq wget apt-transport-https && \
    wget -q https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb && \
    dpkg -i /tmp/packages-microsoft-prod.deb && \
    rm /tmp/packages-microsoft-prod.deb && \
    apt-get update -qq && apt-get install -y -qq dotnet-sdk-8.0 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Disable .NET telemetry
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

# Create benchmark directory for setup scripts
RUN mkdir -p /opt/benchmark

# Copy setup scripts from build context
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh first to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh as a separate build step
RUN /opt/benchmark/setup_runtime.sh

# Set working directory to /workspace
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
