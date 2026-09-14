# Final Dockerfile for diffusers environment
# Base image: python:3.11-slim

FROM python:3.11-slim

# Set working directory
WORKDIR /workspace

# Install system packages - git and curl for repo_setup.sh
# Note: python3-venv is already included in the official Python image
RUN apt-get update -qq && \
    apt-get install -y -qq git curl && \
    rm -rf /var/lib/apt/lists/*

# Copy setup scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to install Python dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set final working directory
WORKDIR /workspace
