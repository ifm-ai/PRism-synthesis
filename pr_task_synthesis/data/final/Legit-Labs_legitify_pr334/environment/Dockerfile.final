FROM debian:bookworm

# Install system packages
RUN apt-get update -qq && apt-get install -y -qq git curl make golang-go

# Copy build-context scripts
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod 755 /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to set up Go runtime environment
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace
