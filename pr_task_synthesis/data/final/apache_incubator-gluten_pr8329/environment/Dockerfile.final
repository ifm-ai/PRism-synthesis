# Apache Gluten Benchmark Environment
# Base image: eclipse-temurin:17-jdk-jammy (Java 17 JDK on Ubuntu 22.04 with apt support)
# Ecosystem: Java/Scala Maven project

FROM eclipse-temurin:17-jdk-jammy

# Set environment variables for Java/Maven/Scala
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH=$JAVA_HOME/bin:$PATH
ENV MAVEN_HOME=/usr/share/maven
ENV MAVEN_OPTS="-Xmx2g -XX:MaxMetaspaceSize=512m"
ENV SCALA_HOME=/usr/share/scala

# Install system packages (Ubuntu uses apt)
# python3-pytest provides pytest-3 and py.test-3, so we create symlinks
RUN apt-get update && apt-get install -y git curl maven scala python3 python3-pytest && \
    ln -sf /usr/bin/pytest-3 /usr/bin/pytest && \
    ln -sf /usr/bin/py.test-3 /usr/bin/py.test && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create benchmark directory for runtime scripts
RUN mkdir -p /opt/benchmark

# Copy build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace from git repository
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh as a separate build step after repo is set up
RUN /opt/benchmark/setup_runtime.sh

# Set working directory to workspace
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
