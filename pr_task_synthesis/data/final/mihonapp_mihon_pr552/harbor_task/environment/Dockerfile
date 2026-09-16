# Mihon Android Project - Docker Image for DATE_MODIFIED Fix Verification
# Base image: ubuntu:22.04
# Runtime: JDK 17, Android SDK 34, Gradle 8.6

FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set environment variables
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV GRADLE_USER_HOME=/opt/gradle

# Install system packages
RUN apt-get update && \
    apt-get install -y git curl wget unzip openjdk-17-jdk libstdc++6 libncurses5 libbz2-1.0 libzstd1 && \
    rm -rf /var/lib/apt/lists/*

# Copy setup scripts to build context
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh first to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to set up Android SDK and Gradle
RUN /opt/benchmark/setup_runtime.sh

# Set up PATH for subsequent build steps and runtime
ENV PATH=$JAVA_HOME/bin:/opt/gradle/gradle-8.6/bin:$PATH

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
