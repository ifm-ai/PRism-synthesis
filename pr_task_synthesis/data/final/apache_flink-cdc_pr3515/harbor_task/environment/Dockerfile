# Apache Flink CDC Benchmark Environment
# Base image: debian:bookworm
# Runtime: Java 8 (Temurin JDK 8u412) + Maven 3.8.7
# Test: PostTransformOperatorTest#testDataChangeEventTransformWithDuplicateColumns

FROM debian:bookworm

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system packages
RUN apt-get update && \
    apt-get install -y \
        git \
        curl \
        wget \
        ca-certificates \
        gnupg \
        xmlstarlet \
        maven && \
    rm -rf /var/lib/apt/lists/*

# Create directories for runtime setup and repo setup
RUN mkdir -p /opt/benchmark

# Copy build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Execute repo_setup.sh to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Execute setup_runtime.sh for Java 8 installation and Maven dependency pre-caching
RUN /opt/benchmark/setup_runtime.sh

# Set environment variables for Java and Maven
ENV JAVA_HOME=/opt/java/jdk8u412-b08
ENV PATH=$JAVA_HOME/bin:/usr/share/maven/bin:$PATH
ENV MAVEN_HOME=/usr/share/maven

# Set working directory to /workspace
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
