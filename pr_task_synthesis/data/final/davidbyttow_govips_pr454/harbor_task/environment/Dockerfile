# Final Dockerfile for govips benchmark environment
# Base image: debian:bookworm
# Runtime: Go with libvips CGO bindings

FROM debian:bookworm

# Set environment variables early for consistent behavior
ENV DEBIAN_FRONTEND=noninteractive
ENV GOPATH=/root/go
ENV PATH=/usr/local/go/bin:$GOPATH/bin:$PATH
ENV CGO_CFLAGS_ALLOW=-Xpreprocessor

# Install system packages including Go and libvips with all transitive dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    curl \
    golang-go \
    libvips-dev \
    pkg-config \
    gcc \
    libexpat1-dev \
    libgsf-1-dev \
    libfftw3-dev \
    libcfitsio-dev \
    libimagequant-dev \
    libcgif-dev \
    libexif12 \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    libpango1.0-dev \
    libfontconfig-dev \
    libtiff-dev \
    librsvg2-dev \
    libcairo2-dev \
    libmatio-dev \
    liblcms2-dev \
    libopenexr-dev \
    libopenjp2-7-dev \
    liborc-0.4-dev \
    && rm -rf /var/lib/apt/lists/*

# Create the benchmark scripts directory
RUN mkdir -p /opt/benchmark

# Copy build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace from the repository
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create the Go runtime environment and install dependencies
RUN /opt/benchmark/setup_runtime.sh

# Set final working directory
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["/bin/bash"]
