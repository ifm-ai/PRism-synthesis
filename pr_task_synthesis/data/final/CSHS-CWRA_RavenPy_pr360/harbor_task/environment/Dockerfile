# RavenPy Dockerfile - Final Build Specification
# Base image: python:3.11-slim
# Purpose: Reproducible environment for RavenPy hydrological modeling package

FROM python:3.11-slim

# Set environment variables for non-interactive apt
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install system packages required for RavenPy
# GDAL dependencies, netcdf, hdf5, proj, geos for geospatial operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    python3-venv \
    python3-dev \
    libgdal-dev \
    gdal-bin \
    libnetcdf-dev \
    libhdf5-dev \
    libproj-dev \
    libgeos-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL include paths for compilation
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Create benchmark directory structure
RUN mkdir -p /opt/benchmark

# Copy build-context scripts
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/repo_setup.sh /opt/benchmark/setup_runtime.sh

# Run repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create Python venv and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set final working directory
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
