#!/bin/bash
# setup_runtime.sh - Runtime setup for Apache Gluten (Java/Scala Maven project)
# This script runs AFTER repo_setup.sh in the Dockerfile
# It sets up Java, Maven, Scala, and Python/pytest environment for the RL agent
# Base image: eclipse-temurin:17-jdk-jammy (Ubuntu 22.04, apt, JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64)

set -e

echo "=== Apache Gluten Runtime Setup ==="
echo "WORKSPACE: ${WORKSPACE:-/workspace}"
echo "Base image: eclipse-temurin:17-jdk-jammy (JAVA_HOME=/opt/java/openjdk)"

# Export Java environment variables
# Use the actual JDK path in the Temurin container
export JAVA_HOME=/opt/java/openjdk
export PATH=$JAVA_HOME/bin:$PATH

# Export Maven environment variables
export MAVEN_HOME=/usr/share/maven
export MAVEN_OPTS="-Xmx2g -XX:MaxMetaspaceSize=512m"

# Export Scala environment
export SCALA_HOME=/usr/share/scala

# Export Python environment
export PYTHONPATH="${WORKSPACE:-/workspace}:${PYTHONPATH}"

# Install pytest via apt if not already installed
# The python3-pytest apt package provides pytest-3 and py.test-3, so we create symlinks
echo "Installing pytest..."
if ! command -v pytest &> /dev/null; then
    apt-get update -qq && apt-get install -y python3-pytest -qq
    # Create symlinks for pytest and py.test commands
    ln -sf /usr/bin/pytest-3 /usr/bin/pytest 2>/dev/null || true
    ln -sf /usr/bin/py.test-3 /usr/bin/py.test 2>/dev/null || true
fi

# Verify installations
echo "Verifying Java installation..."
java -version

echo "Verifying Maven installation..."
mvn --version

echo "Verifying Scala installation..."
scala -version 2>&1 || echo "Scala CLI available via package manager"

echo "Verifying Python installation..."
python3 --version

echo "Verifying pytest installation..."
if command -v pytest &> /dev/null; then
    pytest --version
elif command -v py.test &> /dev/null; then
    py.test --version
else
    echo "Warning: pytest not found in PATH"
    exit 1
fi

# Set up workspace if it exists
if [ -d "${WORKSPACE:-/workspace}" ]; then
    cd "${WORKSPACE:-/workspace}"
    echo "Working directory: $(pwd)"

    # The .idea/vcs.xml fix is an IDE configuration file
    # No runtime code changes are needed for this fix
    # The environment is ready for Maven builds and ScalaTest execution

    echo "=== Runtime setup complete ==="
    echo "Environment is ready for:"
    echo "  - Maven builds: mvn clean package"
    echo "  - ScalaTest execution: mvn test"
    echo "  - IDE configuration validation"
else
    echo "Warning: WORKSPACE directory not found at ${WORKSPACE:-/workspace}"
fi

echo "=== Setup finished successfully ==="
