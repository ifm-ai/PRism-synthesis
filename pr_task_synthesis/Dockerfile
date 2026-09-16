FROM node:25-slim

# Arguments and Environment
ARG SANDBOX_NAME="agent-dist-installed-opencode-sandbox"
ENV SANDBOX="$SANDBOX_NAME"
ENV DEBIAN_FRONTEND="noninteractive"
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin
ENV HOME=/home/agent_sandbox
# 1. Install system packages and configure permissions in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    make \
    g++ \
    man-db \
    curl \
    dnsutils \
    less \
    jq \
    bc \
    gh \
    openssh-client \
    unzip \
    rsync \
    ripgrep \
    procps \
    psmisc \
    lsof \
    socat \
    ca-certificates \
    vim \
    wget \
    libcurl3-gnutls \
    libexpat1 \
    zlib1g \
    autoconf \
    dh-autoreconf \
    zlib1g-dev \
    libssl-dev \
    # changing for stable openssl download
    libcurl4-openssl-dev \ 
    libexpat1-dev \
    gettext \
    && wget https://www.kernel.org/pub/software/scm/git/git-2.50.0.tar.gz \
    && tar -zxf git-2.50.0.tar.gz \
    && cd git-2.50.0 \
    && make configure \
    && ./configure --prefix=/usr \
    && make all \
    && make install \
    && cd .. \
    && rm -rf git-2.50.0 git-2.50.0.tar.gz \
    && apt-get purge -y --auto-remove \
        autoconf \
        dh-autoreconf \
        zlib1g-dev \
        libssl-dev \
        libcurl4-gnutls-dev \
        libexpat1-dev \
        gettext \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /usr/local/share/npm-global \
    && mkdir -p /workspace \
    && mkdir -p /tasks \
    && mkdir -p /home/agent_sandbox
# 2. Install Apptainer
RUN apt-get update && apt-get install -y --no-install-recommends \
    libseccomp2 \
    squashfs-tools \
    fuse2fs \
    fuse-overlayfs \
    uidmap \
    && APPTAINER_VERSION=1.4.3 \
    && curl -fsSL \
        "https://github.com/apptainer/apptainer/releases/download/v${APPTAINER_VERSION}/apptainer_${APPTAINER_VERSION}_amd64.deb" \
        -o /tmp/apptainer.deb \
    && apt-get install -y /tmp/apptainer.deb \
    && rm /tmp/apptainer.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 3. Install Buildah
RUN echo "deb http://deb.debian.org/debian sid main" > /etc/apt/sources.list.d/sid.list && \
    apt-get update && \
    apt-get install -y -o Dpkg::Options::="--force-overwrite" --no-install-recommends \
    buildah \
    netavark \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Pre-create config directory
RUN mkdir -p /home/agent_sandbox/.config/opencode

#4. Install opencode via npm
RUN npm install -g opencode-ai && npm cache clean --force

#5. Set the root in the /etc/
# Write the mapping: user 'root' gets 655,326 IDs starting at 10,000
RUN echo "root:100000:65536" > /etc/subuid && \
    echo "root:100000:65536" > /etc/subgid

#6. Install opencode from pre-downloaded binaries (if available)
ARG OPENCODE_VERSION=1.4.6
RUN mkdir -p /.download_artifacts \
    && for target in \
        linux-x64 \
        linux-x64-baseline \
        linux-x64-musl \
        linux-x64-baseline-musl \
        linux-arm64 \
        linux-arm64-musl; do \
        echo "Downloading opencode-${target}.tar.gz ..." \
        && curl -fsSL \
            "https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/opencode-${target}.tar.gz" \
            -o "/.download_artifacts/opencode-${target}.tar.gz" \
        || echo "WARNING: opencode-${target}.tar.gz not available for v${OPENCODE_VERSION}, skipping"; \
    done
COPY install_opencode.sh /.download_artifacts/install_opencode.sh
RUN chmod +x /.download_artifacts/install_opencode.sh

#7. Copy the opencode agents and skills
# pipeline.py stages these into /root/.opencode and /home/agent_sandbox/.opencode per task, so
# baking them in is only a default for running the image by hand.
COPY prompts/agents /home/agent_sandbox/.opencode/agents
COPY prompts/skills /home/agent_sandbox/.opencode/skills
RUN chmod -R 777 /home/agent_sandbox/.opencode/agents && \
    chmod -R 777 /home/agent_sandbox/.opencode/skills

# 8. SETTING the PATH variables 
RUN printf '%s\n' \
    'export PATH=${PATH}' \
    > /etc/profile.d/sandbox-paths.sh \
    && chmod 644 /etc/profile.d/sandbox-paths.sh
# Default command
CMD ["opencode"]