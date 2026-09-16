#!/bin/bash
# setup_runtime.sh - Build-time runtime setup for Keiyoushi extensions-source
# This script creates the primary runtime environment with JDK 17 and Android SDK

set -e

echo "=== Setting up runtime environment for Keiyoushi extensions-source ==="

# Create directories
mkdir -p /opt/benchmark
mkdir -p /opt/android-sdk/cmdline-tools
mkdir -p /root/.gradle

# Install required tools
apt-get update -qq
apt-get install -y -qq wget unzip

# Install JDK 17 (Temurin) using direct tarball
echo "Installing JDK 17 (Temurin)..."
cd /tmp

# Download Temurin JDK 17
wget -q --show-progress "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jdk_x64_linux_hotspot_17.0.11_9.tar.gz" -O temurin17.tar.gz
tar -xzf temurin17.tar.gz -C /opt/benchmark/
mv /opt/benchmark/jdk-* /opt/benchmark/temurin-17 2>/dev/null || true
rm temurin17.tar.gz

export JAVA_HOME=/opt/benchmark/temurin-17
export PATH=$JAVA_HOME/bin:$PATH

echo "Java installed: $(java -version 2>&1 | head -1)"

# Install Gradle 8.7
echo "Installing Gradle 8.7..."
wget -q --show-progress "https://services.gradle.org/distributions/gradle-8.7-bin.zip" -O gradle-8.7-bin.zip
unzip -q gradle-8.7-bin.zip -d /opt/benchmark/
rm gradle-8.7-bin.zip

export GRADLE_HOME=/opt/benchmark/gradle-8.7
export PATH=$GRADLE_HOME/bin:$PATH

echo "Gradle installed: $(gradle --version 2>&1 | head -1)"

# Install Android SDK command-line tools
echo "Installing Android SDK command-line tools..."
cd /tmp

# Download Android SDK command-line tools
wget -q --show-progress "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip" -O android-cmdline.zip
unzip -q android-cmdline.zip -d /opt/android-sdk/cmdline-tools
mv /opt/android-sdk/cmdline-tools/cmdline-tools /opt/android-sdk/cmdline-tools/latest 2>/dev/null || true
rm android-cmdline.zip

# Set ANDROID_HOME
export ANDROID_HOME=/opt/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH

# Accept licenses and install required SDK components (with retry logic for network issues)
echo "Installing Android SDK components..."
for i in 1 2 3; do
    if yes | sdkmanager --licenses > /dev/null 2>&1; then
        break
    fi
    echo "Retry $i of 3 for sdkmanager licenses..."
    sleep 5
done

for i in 1 2 3; do
    if sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0" 2>&1; then
        echo "Android SDK components installed successfully"
        break
    fi
    echo "Retry $i of 3 for sdkmanager components..."
    sleep 5
done

# Configure Gradle
echo "Configuring Gradle..."
cat > /root/.gradle/gradle.properties << 'EOF'
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.parallel=true
org.gradle.caching=true
android.useAndroidX=true
android.enableJetifier=true
EOF

# Verify Gradle wrapper works
cd /workspace
echo "Verifying Gradle wrapper..."
./gradlew --version || echo "Gradle verification completed"

# Install project dependencies (without building)
echo "Installing project dependencies..."
./gradlew dependencies --refresh-dependencies || echo "Dependency resolution completed"

echo "=== Runtime setup complete ==="
echo "JAVA_HOME=$JAVA_HOME"
echo "ANDROID_HOME=$ANDROID_HOME"
echo "GRADLE_HOME=$GRADLE_HOME"
