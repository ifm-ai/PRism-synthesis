# Final Dockerfile for confidential-containers/trustee
# Base image: rust:slim with Rust toolchain
FROM rust:slim

# Set non-interactive mode for apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Install system packages required for building the verifier with se-verifier feature
RUN apt-get update -qq && \
    apt-get install -y -qq \
        git \
        curl \
        ca-certificates \
        build-essential \
        protobuf-compiler \
        libprotobuf-dev \
        libtss2-dev \
        libssl-dev \
        pkg-config \
        cmake \
        clang \
        llvm && \
    rm -rf /var/lib/apt/lists/*

# Create the benchmark scripts directory
RUN mkdir -p /opt/benchmark

# Copy the build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to clone the repository and materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to set up the Rust toolchain
RUN /opt/benchmark/setup_runtime.sh

# Set the final working directory
WORKDIR /workspace

# Default command - the container is ready for runtime use with eval.sh mounted
CMD ["bash"]
