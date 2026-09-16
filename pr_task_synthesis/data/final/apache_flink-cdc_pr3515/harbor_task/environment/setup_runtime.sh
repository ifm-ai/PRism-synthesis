#!/bin/bash
set -e

# setup_runtime.sh - Runtime setup for Apache Flink CDC (Java 8 + Maven)
# This script installs Java 8 (Temurin) and Maven, and prepares the environment

echo "=== Starting runtime setup for Apache Flink CDC ==="

# Install base system packages including git and curl
echo "Installing base system packages..."
apt-get update
apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    gnupg \
    xmlstarlet \
    maven

# Create installation directory
INSTALL_DIR="/opt/java"
mkdir -p "$INSTALL_DIR"

# Check if Java 8 is already installed
if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | head -1 | cut -d'"' -f2 | cut -d'.' -f1)
    echo "Java already installed: version $JAVA_VERSION"
    if [ "$JAVA_VERSION" = "1" ] || [ "$JAVA_VERSION" = "8" ]; then
        CURRENT_JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
        echo "Current JAVA_HOME: $CURRENT_JAVA_HOME"
        # Check if it's Java 8
        if java -version 2>&1 | grep -q "1\.8"; then
            echo "Java 8 is already available, skipping installation"
            export JAVA_HOME="$CURRENT_JAVA_HOME"
        else
            echo "Installing Java 8 (Temurin)..."
            TEMURIN_VERSION="jdk8u412-b08"
            # Use retry logic and HTTP/1.1 to avoid transient network errors
            curl --retry 3 --retry-delay 10 --retry-max-time 60 --http1.1 -L \
                "https://github.com/adoptium/temurin8-binaries/releases/download/${TEMURIN_VERSION}/OpenJDK8U-jdk_x64_linux_hotspot_8u412b08.tar.gz" \
                -o /tmp/temurin8.tar.gz
            tar -xzf /tmp/temurin8.tar.gz -C "$INSTALL_DIR"
            rm /tmp/temurin8.tar.gz
            JAVA_HOME=$(find "$INSTALL_DIR" -maxdepth 1 -type d -name "jdk*" | head -1)
            export JAVA_HOME
            export PATH="$JAVA_HOME/bin:$PATH"
        fi
    else
        echo "Installing Java 8 (Temurin)..."
        TEMURIN_VERSION="jdk8u412-b08"
        # Use retry logic and HTTP/1.1 to avoid transient network errors
        curl --retry 3 --retry-delay 10 --retry-max-time 60 --http1.1 -L \
            "https://github.com/adoptium/temurin8-binaries/releases/download/${TEMURIN_VERSION}/OpenJDK8U-jdk_x64_linux_hotspot_8u412b08.tar.gz" \
            -o /tmp/temurin8.tar.gz
        tar -xzf /tmp/temurin8.tar.gz -C "$INSTALL_DIR"
        rm /tmp/temurin8.tar.gz
        JAVA_HOME=$(find "$INSTALL_DIR" -maxdepth 1 -type d -name "jdk*" | head -1)
        export JAVA_HOME
        export PATH="$JAVA_HOME/bin:$PATH"
    fi
else
    echo "Installing Java 8 (Temurin)..."
    TEMURIN_VERSION="jdk8u412-b08"
    # Use retry logic and HTTP/1.1 to avoid transient network errors
    curl --retry 3 --retry-delay 10 --retry-max-time 60 --http1.1 -L \
        "https://github.com/adoptium/temurin8-binaries/releases/download/${TEMURIN_VERSION}/OpenJDK8U-jdk_x64_linux_hotspot_8u412b08.tar.gz" \
        -o /tmp/temurin8.tar.gz
    tar -xzf /tmp/temurin8.tar.gz -C "$INSTALL_DIR"
    rm /tmp/temurin8.tar.gz
    JAVA_HOME=$(find "$INSTALL_DIR" -maxdepth 1 -type d -name "jdk*" | head -1)
    export JAVA_HOME
    export PATH="$JAVA_HOME/bin:$PATH"
fi

# Verify Java installation
echo "Verifying Java installation..."
java -version

# Set up Maven environment
export MAVEN_HOME=/usr/share/maven
export PATH="$MAVEN_HOME/bin:$PATH"

# Verify Maven installation
echo "Verifying Maven installation..."
mvn --version

# Configure Maven to use Mirror proxy for dependency resolution with fallback to Central
echo "=== Configuring Maven Mirror proxy with fallback ==="
MAVEN_SETTINGS_DIR="/root/.m2"
mkdir -p "$MAVEN_SETTINGS_DIR"

cat > "$MAVEN_SETTINGS_DIR/settings.xml" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.2.0 https://maven.apache.org/xsd/settings-1.2.0.xsd">
  <mirrors>
    <mirror>
      <id>mirror</id>
      <mirrorOf>external:*</mirrorOf>
      <url>http://mirror.proxy.hpc:8081/repository/maven-public/</url>
      <blocked>false</blocked>
    </mirror>
  </mirrors>
  <profiles>
    <profile>
      <id>mirror</id>
      <repositories>
        <repository>
          <id>central</id>
          <url>http://mirror.proxy.hpc:8081/repository/maven-public/</url>
          <releases>
            <enabled>true</enabled>
            <updatePolicy>daily</updatePolicy>
          </releases>
          <snapshots>
            <enabled>true</enabled>
            <updatePolicy>always</updatePolicy>
          </snapshots>
        </repository>
        <repository>
          <id>central-fallback</id>
          <url>https://repo.maven.apache.org/maven2/</url>
          <releases>
            <enabled>true</enabled>
            <updatePolicy>daily</updatePolicy>
          </releases>
          <snapshots>
            <enabled>false</enabled>
          </snapshots>
        </repository>
      </repositories>
      <pluginRepositories>
        <pluginRepository>
          <id>central</id>
          <url>http://mirror.proxy.hpc:8081/repository/maven-public/</url>
          <releases>
            <enabled>true</enabled>
            <updatePolicy>daily</updatePolicy>
          </releases>
          <snapshots>
            <enabled>true</enabled>
            <updatePolicy>always</updatePolicy>
          </snapshots>
        </pluginRepository>
        <pluginRepository>
          <id>central-fallback</id>
          <url>https://repo.maven.apache.org/maven2/</url>
          <releases>
            <enabled>true</enabled>
            <updatePolicy>daily</updatePolicy>
          </releases>
          <snapshots>
            <enabled>false</enabled>
          </snapshots>
        </pluginRepository>
      </pluginRepositories>
    </profile>
  </profiles>
  <activeProfiles>
    <activeProfile>mirror</activeProfile>
  </activeProfiles>
  <servers>
    <server>
      <id>mirror</id>
      <configuration>
        <httpConfiguration>
          <connectionTimeout>30000</connectionTimeout>
          <requestTimeout>60000</requestTimeout>
          <socketTimeout>30000</socketTimeout>
        </httpConfiguration>
      </configuration>
    </server>
  </servers>
</settings>
EOF

echo "Maven settings.xml created at $MAVEN_SETTINGS_DIR/settings.xml"
cat "$MAVEN_SETTINGS_DIR/settings.xml"

# Create profile.d script for persistent environment variables
mkdir -p /etc/profile.d
cat > /etc/profile.d/java-maven.sh << 'EOF'
export JAVA_HOME=/opt/java/jdk8u412-b08
export PATH="$JAVA_HOME/bin:$PATH"
export MAVEN_HOME=/usr/share/maven
export PATH="$MAVEN_HOME/bin:$PATH"
EOF

# Pre-cache Maven dependencies for the flink-cdc-runtime module
# This must be done during image construction when network access is available
echo "=== Pre-caching Maven dependencies for flink-cdc-runtime ==="

cd /workspace

# First, build and install all modules to create local SNAPSHOT artifacts
# This is critical for inter-module SNAPSHOT dependencies (e.g., flink-cdc-common:3.2-SNAPSHOT)
echo "Building and installing all modules to local repository..."
# Use -B for batch mode, -U for update snapshots, -DskipTests to skip tests
# Retry up to 3 times with 10 second delay between retries
for i in 1 2 3; do
    if mvn -B install -DskipTests -U -Dmaven.wagon.http.retryHandler.count=3 -Dmaven.wagon.http.retryHandler.delay_secs=10; then
        echo "Maven install succeeded on attempt $i"
        break
    else
        if [ $i -eq 3 ]; then
            echo "ERROR: Maven install failed after 3 attempts"
            exit 1
        fi
        echo "Maven install failed on attempt $i, retrying in 10 seconds..."
        sleep 10
    fi
done

# Now that inter-module SNAPSHOTs are available, cache external dependencies
# Use dependency:go-offline to download ALL dependencies (compile, test, runtime scopes)
# This is the canonical Maven command for pre-caching dependencies
echo "Downloading all Maven dependencies (go-offline)..."
# The -am flag ensures we also build dependent modules
# Use retry logic for network resilience
for i in 1 2 3; do
    if mvn -pl flink-cdc-runtime -am -B dependency:go-offline -U -Dmaven.wagon.http.retryHandler.count=3 -Dmaven.wagon.http.retryHandler.delay_secs=10; then
        echo "Maven go-offline succeeded on attempt $i"
        break
    else
        if [ $i -eq 3 ]; then
            echo "ERROR: Maven go-offline failed after 3 attempts"
            exit 1
        fi
        echo "Maven go-offline failed on attempt $i, retrying in 10 seconds..."
        sleep 10
    fi
done

# Also explicitly resolve test dependencies to ensure they're all cached
echo "Resolving test dependencies..."
mvn -pl flink-cdc-runtime -B dependency:resolve -DincludeScope=test -U -Dmaven.wagon.http.retryHandler.count=3 -Dmaven.wagon.http.retryHandler.delay_secs=10

# Compile test classes to ensure all test-scoped dependencies are also cached
echo "Compiling test classes..."
mvn -pl flink-cdc-runtime -B test-compile -U -q || true

echo "=== Maven dependency pre-caching completed ==="

# Verify the local repository has cached artifacts
echo "Verifying Maven local repository..."
if [ -d "/root/.m2/repository" ]; then
    CACHED_JARS=$(find /root/.m2/repository -type f -name "*.jar" | wc -l)
    CACHED_POMS=$(find /root/.m2/repository -type f -name "*.pom" | wc -l)
    LASTUPDATED=$(find /root/.m2/repository -type f -name "*.lastUpdated" | wc -l)
    echo "Cached JAR artifacts: $CACHED_JARS"
    echo "Cached POM artifacts: $CACHED_POMS"
    echo "Download status files (.lastUpdated): $LASTUPDATED"
    
    # Verify critical parent POM was cached
    if [ -f "/root/.m2/repository/org/apache/apache/20/apache-20.pom" ]; then
        echo "Parent POM org.apache:apache:20 successfully cached"
    else
        echo "WARNING: Parent POM org.apache:apache:20 NOT cached!"
    fi
    
    # Verify key Flink CDC dependencies were cached
    if [ -f "/root/.m2/repository/org/apache/flink/flink-cdc-common/3.2-SNAPSHOT/flink-cdc-common-3.2-SNAPSHOT.jar" ]; then
        echo "SNAPSHOT dependency flink-cdc-common:3.2-SNAPSHOT successfully cached"
    else
        echo "WARNING: SNAPSHOT dependency flink-cdc-common:3.2-SNAPSHOT NOT cached!"
    fi
    
    # Fail if no JARs were cached (indicates network or config issue)
    if [ "$CACHED_JARS" -eq 0 ]; then
        echo "ERROR: No JAR artifacts were cached. Maven dependency resolution failed."
        echo "This may indicate:"
        echo "  - Mirror proxy (http://mirror.proxy.hpc:8081) is unreachable"
        echo "  - Network connectivity issues during image build"
        echo "  - Maven settings.xml misconfiguration"
        exit 1
    fi
    
    # Warn if there are many .lastUpdated files (indicates failed download attempts)
    if [ "$LASTUPDATED" -gt 50 ]; then
        echo "WARNING: Many .lastUpdated files detected ($LASTUPDATED). Some downloads may have failed."
        echo "Check if Mirror proxy is reachable or if fallback to Maven Central is needed."
    fi
fi

echo "=== Runtime setup completed successfully ==="
