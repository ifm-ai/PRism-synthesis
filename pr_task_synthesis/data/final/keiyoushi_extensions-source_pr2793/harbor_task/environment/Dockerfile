# Dockerfile.final - VoyceMe Extension Benchmark Environment
# Base image: ubuntu:22.04
# Runtime: JDK 17 (Temurin), Gradle 8.7, Android SDK
# Repository: Keiyoushi extensions-source

FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install required system packages (from environment_request.json)
RUN apt-get update -qq && \
    apt-get install -y -qq git curl wget unzip apt-transport-https && \
    rm -rf /var/lib/apt/lists/*

# Create benchmark directory structure
RUN mkdir -p /opt/benchmark /opt/android-sdk/cmdline-tools /root/.gradle /workspace && \
    chmod 777 /workspace

# Copy build-context scripts into the image
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/repo_setup.sh /opt/benchmark/setup_runtime.sh

# Step 1: Materialize the repository using repo_setup.sh
# This clones the Keiyoushi extensions-source repo into /workspace
RUN /opt/benchmark/repo_setup.sh

# Step 2: Run setup_runtime.sh to install JDK 17, Gradle 8.7, and Android SDK
RUN /opt/benchmark/setup_runtime.sh

# Set environment variables for the runtime
ENV JAVA_HOME=/opt/benchmark/temurin-17
ENV GRADLE_HOME=/opt/benchmark/gradle-8.7
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH=$JAVA_HOME/bin:$GRADLE_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH

# Set working directory to /workspace
WORKDIR /workspace

# The image is now ready for use
# Note: eval.sh and hidden tests are runtime-mounted, not baked into the image
