# Apache Sedona Benchmark Environment
# Base image: debian:bookworm
# Runtime: JDK 17, Maven, Python venv with GEOS support

FROM debian:bookworm

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set JAVA_HOME and update PATH
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=$JAVA_HOME/bin:$PATH

# Install system packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        openjdk-17-jdk-headless \
        maven \
        build-essential \
        libgeos-dev \
        libgeos-c1v5 \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Verify Java and Maven installation
RUN java -version 2>&1 | head -3 && \
    mvn --version 2>&1 | head -3

# Copy build-context scripts to stable image paths
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/repo_setup.sh /opt/benchmark/setup_runtime.sh

# Run repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create Python venv and install base dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
