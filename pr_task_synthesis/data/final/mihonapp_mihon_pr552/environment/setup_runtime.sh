#!/bin/bash
# setup_runtime.sh - Runtime creation script for Mihon Android project
# This script sets up the Android development environment on Linux

set -e

echo "=== Setting up Android development environment ==="

# Export environment variables
export DEBIAN_FRONTEND=noninteractive
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/opt/android-sdk
export ANDROID_SDK_ROOT=/opt/android-sdk
export GRADLE_USER_HOME=/opt/gradle

# Ensure paths are in PATH
export PATH=$JAVA_HOME/bin:/opt/gradle/gradle-8.6/bin:$PATH

echo "JAVA_HOME: $JAVA_HOME"
echo "ANDROID_HOME: $ANDROID_HOME"
echo "GRADLE_USER_HOME: $GRADLE_USER_HOME"

# Install system packages (idempotent)
echo "=== Installing system packages ==="
apt-get update -qq
apt-get install -y -qq git curl wget unzip openjdk-17-jdk libstdc++6 libncurses5 libbz2-1.0 libzstd1 > /dev/null 2>&1 || true
rm -rf /var/lib/apt/lists/*

# Verify Java installation
echo "=== Verifying Java installation ==="
java -version 2>&1 | head -3

# Setup Android SDK
echo "=== Setting up Android SDK ==="
mkdir -p /opt/android-sdk/cmdline-tools

# Download and install Android command-line tools if not already present
if [ ! -d "/opt/android-sdk/cmdline-tools/latest" ]; then
    echo "Downloading Android command-line tools..."
    curl -fsSL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/cmdline-tools.zip
    unzip -q /tmp/cmdline-tools.zip -d /opt/android-sdk/cmdline-tools
    mv /opt/android-sdk/cmdline-tools/cmdline-tools /opt/android-sdk/cmdline-tools/latest
    rm /tmp/cmdline-tools.zip
    echo "Android command-line tools installed."
else
    echo "Android command-line tools already present."
fi

# Accept Android SDK licenses (idempotent)
echo "=== Accepting Android SDK licenses ==="
yes | /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager --licenses > /dev/null 2>&1 || true

# Install required SDK components using direct downloads (more reliable)
echo "=== Installing Android SDK components ==="

# Install platform-tools
if [ ! -d "/opt/android-sdk/platform-tools" ]; then
    echo "Downloading platform-tools..."
    curl -fsSL --connect-timeout 30 --max-time 300 "https://dl.google.com/android/repository/platform-tools-latest-linux.zip" -o /tmp/platform-tools.zip
    unzip -q /tmp/platform-tools.zip -d /opt/android-sdk/
    rm /tmp/platform-tools.zip
    echo "platform-tools installed."
else
    echo "platform-tools already present."
fi

# Install platforms;android-34
if [ ! -d "/opt/android-sdk/platforms/android-34" ]; then
    echo "Downloading platform-34..."
    curl -fsSL --connect-timeout 30 --max-time 300 "https://dl.google.com/android/repository/platform-34-ext7_r03.zip" -o /tmp/platform-34.zip
    mkdir -p /opt/android-sdk/platforms
    unzip -q /tmp/platform-34.zip -d /opt/android-sdk/platforms/
    rm /tmp/platform-34.zip
    echo "platform-34 installed."
else
    echo "platform-34 already present."
fi

# Install build-tools;29.0.3
if [ ! -d "/opt/android-sdk/build-tools/29.0.3" ]; then
    echo "Downloading build-tools-29.0.3..."
    curl -fsSL --connect-timeout 30 --max-time 300 "https://dl.google.com/android/repository/build-tools_r29.0.3-linux.zip" -o /tmp/build-tools.zip
    mkdir -p /opt/android-sdk/build-tools
    unzip -q /tmp/build-tools.zip -d /opt/android-sdk/build-tools/29.0.3/
    rm /tmp/build-tools.zip
    echo "build-tools-29.0.3 installed."
else
    echo "build-tools-29.0.3 already present."
fi

# Install ndk;26.1.10909125 (ndk-r26b) - Large file, may need pre-caching
if [ ! -d "/opt/android-sdk/ndk/26.1.10909125" ]; then
    echo "Downloading NDK 26.1.10909125 (r26b) - this may take several minutes..."
    if curl -fsSL --connect-timeout 30 --max-time 900 "https://dl.google.com/android/repository/android-ndk-r26b-linux.zip" -o /tmp/ndk.zip 2>/dev/null; then
        mkdir -p /opt/android-sdk/ndk/26.1.10909125
        unzip -q /tmp/ndk.zip -d /opt/android-sdk/ndk/26.1.10909125/
        rm /tmp/ndk.zip
        echo "ndk-26.1.10909125 installed."
    else
        echo "Warning: NDK download failed or timed out. NDK can be installed later via:"
        echo "  curl -fsSL https://dl.google.com/android/repository/android-ndk-r26b-linux.zip -o /tmp/ndk.zip"
        echo "  unzip -q /tmp/ndk.zip -d /opt/android-sdk/ndk/26.1.10909125/"
        echo "  rm /tmp/ndk.zip"
    fi
else
    echo "ndk-26.1.10909125 already present."
fi

# Setup Gradle
echo "=== Setting up Gradle ==="
mkdir -p /opt/gradle

# Download and install Gradle 8.6 if not already present
if [ ! -d "/opt/gradle/gradle-8.6" ]; then
    echo "Downloading Gradle 8.6..."
    curl -fsSL --connect-timeout 30 --max-time 300 https://services.gradle.org/distributions/gradle-8.6-bin.zip -o /tmp/gradle-8.6-bin.zip
    unzip -q /tmp/gradle-8.6-bin.zip -d /opt/gradle
    rm /tmp/gradle-8.6-bin.zip
    echo "Gradle 8.6 installed."
else
    echo "Gradle 8.6 already present."
fi

# Verify installations
echo "=== Verifying installations ==="
echo "Java version:"
java -version 2>&1 | head -1
echo "Gradle version:"
/opt/gradle/gradle-8.6/bin/gradle --version 2>&1 | head -2
echo "Android SDK components:"
ls -la /opt/android-sdk/

echo "=== Runtime setup complete ==="
echo "Environment variables set:"
echo "  JAVA_HOME=$JAVA_HOME"
echo "  ANDROID_HOME=$ANDROID_HOME"
echo "  ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT"
echo "  GRADLE_USER_HOME=$GRADLE_USER_HOME"
echo "  PATH includes: \$JAVA_HOME/bin and /opt/gradle/gradle-8.6/bin"
