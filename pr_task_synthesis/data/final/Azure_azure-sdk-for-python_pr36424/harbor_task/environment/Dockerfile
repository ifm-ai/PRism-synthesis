# Final Dockerfile for Azure SDK for Python finetuning module benchmark
# Base image: python:3.11-slim

FROM python:3.11-slim

# Install system packages
RUN apt-get update -qq && apt-get install -y -qq git curl

# Copy build-context scripts to /opt/benchmark
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create the Python virtual environment and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set working directory to /workspace
WORKDIR /workspace

# Default command: activate venv and stay ready for tests
CMD ["bash", "-c", "source /opt/benchmark/venv/bin/activate && exec bash"]
