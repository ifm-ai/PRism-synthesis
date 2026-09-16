# --- Stage 1: Source Runtimes ---
FROM golang:1.24 AS go-src
FROM rust:1-slim AS rust-src
FROM eclipse-temurin:17-jdk AS java-src
FROM dart:stable AS dart-src
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS dotnet-src
FROM julia:1.10 AS julia-src

# --- Stage 2: Final Multilingual Sandbox ---
FROM node:20-slim

# Arguments and Environment
ARG SANDBOX_NAME="agent-dist-installed-sandbox"
ENV SANDBOX="$SANDBOX_NAME"
ENV DEBIAN_FRONTEND="noninteractive"
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV HOME=/home/agent_sandbox
ENV WORKDIR=/workspaces
# Allow global pip installation on Debian Bookworm+
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Define Paths for all runtimes
# Updated JAVA_HOME for OpenJDK 17 directory structure
ENV JAVA_HOME=/opt/java/openjdk
ENV GOROOT=/usr/local/go
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV CONDA_DIR=/.environ/miniconda
ENV DOTNET_ROOT=/usr/share/dotnet
ENV JULIA_PATH=/usr/local/julia
ENV PATH=/usr/local/share/npm-global/bin:$GOROOT/bin:$JAVA_HOME/bin:$CARGO_HOME/bin:/usr/local/kotlinc/bin:$CONDA_DIR/bin:$JULIA_PATH/bin:/usr/lib/dart/bin:$DOTNET_ROOT:$PATH

# 1. Install system packages (C/C++, Python, and Tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    php \
    ruby-full \
    build-essential \
    g++ gcc libc6-dev \
    make \
    lua5.4 \
    luarocks \
    shellcheck \
    tidy \
    xz-utils \
    man-db curl dnsutils less jq bc gh unzip rsync ripgrep procps psmisc lsof socat ca-certificates vim wget \
    openssh-client \
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
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. Copy Runtimes from Stages
COPY --from=go-src /usr/local/go /usr/local/go
COPY --from=rust-src /usr/local/cargo /usr/local/cargo
COPY --from=rust-src /usr/local/rustup /usr/local/rustup
# Copy Java 17
COPY --from=java-src /opt/java/openjdk /opt/java/openjdk
# Copy Dart SDK
COPY --from=dart-src /usr/lib/dart /usr/lib/dart
# Copy .NET SDK (C#)
COPY --from=dotnet-src /usr/share/dotnet /usr/share/dotnet
# Copy Julia
COPY --from=julia-src /usr/local/julia /usr/local/julia

# 3. Install Scala (via Scala CLI)
# This allows running 'scala' commands and handles Scala 2/3 seamlessly
RUN curl -fL https://github.com/VirtusLab/scala-cli/releases/latest/download/scala-cli-x86_64-pc-linux.gz | gzip -d > /usr/local/bin/scala-cli \
    && chmod +x /usr/local/bin/scala-cli \
    && ln -s /usr/local/bin/scala-cli /usr/local/bin/scala

# 4. Install Kotlin
RUN wget -q https://github.com/JetBrains/kotlin/releases/download/v2.0.0/kotlin-compiler-2.0.0.zip \
    && unzip kotlin-compiler-2.0.0.zip -d /usr/local \
    && rm kotlin-compiler-2.0.0.zip

# 5. Install sbt
RUN wget -q https://github.com/sbt/sbt/releases/download/v1.10.7/sbt-1.10.7.tgz \
    && tar -zxf sbt-1.10.7.tgz -C /usr/local \
    && rm sbt-1.10.7.tgz \
    && ln -s /usr/local/sbt/bin/sbt /usr/local/bin/sbt

# 6. Configure Sandbox & Workspace
RUN mkdir -p /usr/local/share/npm-global /workspaces /tasks /home/agent_sandbox/.config/opencode /home/agent_sandbox/.codex \
    && mkdir -p /home/agent_sandbox/.local \
    && mkdir -p /home/agent_sandbox/.cache \
    && mkdir -p /home/agent_sandbox/.sbt \
    && rm -rf /root/.local /root/.config /root/.cache /root/.sbt \
    && ln -s /home/agent_sandbox/.local /root/.local \
    && ln -s /home/agent_sandbox/.config /root/.config \
    && ln -s /home/agent_sandbox/.cache /root/.cache \
    && ln -s /home/agent_sandbox/.sbt /root/.sbt 

# 7. Install opencode-ai
RUN npm install -g opencode-ai && npm cache clean --force

# 8. Install Codex
RUN npm install -g @openai/codex && npm cache clean --force

# 9. ADD the tmux, asciinema
RUN apt-get update && apt-get install -y --no-install-recommends tmux asciinema && apt-get clean && rm -rf /var/lib/apt/lists/*

# 10. Install Miniconda
# The original image pip-installed the whole agentdist package here. agent.py only ships a
# nested closure into the sandbox, which cloudpickle serialises by value, so cloudpickle is
# all the in-sandbox interpreter needs. The contract that matters is unchanged: a conda env
# named `venv` under /.environ/miniconda.
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh \
    && bash miniconda.sh -b -p $CONDA_DIR \
    && rm miniconda.sh \
    && $CONDA_DIR/bin/conda init bash \
    && $CONDA_DIR/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main \
    && $CONDA_DIR/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r \
    && $CONDA_DIR/bin/conda config --set auto_activate_base false \
    && $CONDA_DIR/bin/conda create -y -n venv python=3.10 \
       && $CONDA_DIR/bin/conda run -n venv pip install --upgrade pip setuptools wheel \
       && $CONDA_DIR/bin/conda run -n venv pip install cloudpickle


# 11. Install Jupyter Notebook into conda base
RUN $CONDA_DIR/bin/pip install jupyter notebook ipykernel

# 12. Install TypeScript
RUN npm install -g typescript

# 13. Install tooling for HTML, CSS, and Vue
RUN npm install -g html-validator-cli sass stylelint@16.7.0 @vue/cli create-vue

# 14. Install Starlark
RUN GOBIN=/usr/local/bin go install go.starlark.net/cmd/starlark@latest

# Adding the ENV PATH
ENV PATH=/usr/local/share/npm-global/bin:$GOROOT/bin:$JAVA_HOME/bin:$CARGO_HOME/bin:/usr/local/kotlinc/bin:$CONDA_DIR/bin:$JULIA_PATH/bin:/usr/lib/dart/bin:$DOTNET_ROOT:$PATH

# Verification
RUN node -v && python3 --version && go version && rustc --version && java -version \
    && scala --version && g++ --version && php -v && ruby -v && kotlinc -version \
    && sbt --version && conda --version \
    && dotnet --version && julia --version && lua5.4 -v && dart --version \
    && shellcheck --version && tidy --version && jupyter --version \
    && go version -m $(which starlark)

# 14. Expose all runtime paths to every bash -l session (sourced via /etc/profile.d)
RUN printf '%s\n' \
    'export JAVA_HOME=/opt/java/openjdk' \
    'export GOROOT=/usr/local/go' \
    'export CARGO_HOME=/usr/local/cargo' \
    'export RUSTUP_HOME=/usr/local/rustup' \
    'export CONDA_DIR=/.environ/miniconda' \
    'export DOTNET_ROOT=/usr/share/dotnet' \
    'export JULIA_PATH=/usr/local/julia' \
    'export PATH=/usr/local/share/npm-global/bin:${GOROOT}/bin:${JAVA_HOME}/bin:${CARGO_HOME}/bin:/usr/local/kotlinc/bin:${CONDA_DIR}/bin:${JULIA_PATH}/bin:/usr/lib/dart/bin:${DOTNET_ROOT}:/nix/var/nix/profiles/default/bin:/usr/local/bin:${PATH}' \
    > /etc/profile.d/sandbox-paths.sh \
    && chmod 644 /etc/profile.d/sandbox-paths.sh

WORKDIR /workspaces