# PHPSpreadsheet Benchmark Environment
# Base image: mirror.gcr.io/library/php:8.2-cli
# Runtime: PHP 8.2 with Composer

FROM mirror.gcr.io/library/php:8.2-cli

# Install Composer by downloading the phar from GitHub releases
RUN curl -sSL https://github.com/composer/composer/releases/download/2.7.7/composer.phar -o /usr/local/bin/composer && \
    chmod +x /usr/local/bin/composer

# Pin apt sources to Debian bookworm to avoid repository conflicts
RUN echo 'deb http://deb.debian.org/debian bookworm main' > /etc/apt/sources.list && \
    echo 'deb http://deb.debian.org/debian bookworm-updates main' >> /etc/apt/sources.list && \
    echo 'deb http://security.debian.org/debian-security bookworm-security main' >> /etc/apt/sources.list

# Install system packages required for PHP extensions and project
# System libraries needed for GD, ZIP, mbstring, and XML extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    libpng-dev \
    libjpeg62-turbo-dev \
    libfreetype-dev \
    libzip-dev \
    libonig-dev \
    libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PHP extensions
# Install dom and xml first, then backup dom headers BEFORE cleanup
# Manually compile xmlreader/xmlwriter/simplexml with restored dom headers
# Then install remaining extensions
RUN docker-php-source extract && \
    docker-php-ext-install dom xml && \
    cp -r /usr/src/php/ext/dom /tmp/dom_backup && \
    rm -rf /usr/src/php/ext/dom && \
    cp -r /tmp/dom_backup /usr/src/php/ext/dom && \
    cp /usr/src/php/ext/dom/dom_ce.h /usr/local/include/php/ext/dom/ 2>/dev/null || mkdir -p /usr/local/include/php/ext/dom && cp /usr/src/php/ext/dom/dom_ce.h /usr/local/include/php/ext/dom/ && \
    cd /usr/src/php/ext/xmlreader && phpize && ./configure --with-php-config=/usr/local/bin/php-config && make -j$(nproc) && make install && \
    cd /usr/src/php/ext/xmlwriter && phpize && ./configure --with-php-config=/usr/local/bin/php-config && make -j$(nproc) && make install && \
    cd /usr/src/php/ext/simplexml && phpize && ./configure --with-php-config=/usr/local/bin/php-config && make -j$(nproc) && make install && \
    docker-php-ext-configure gd --with-freetype --with-jpeg && \
    docker-php-ext-install fileinfo ctype iconv mbstring zip gd && \
    docker-php-source delete

# Verify PHP extensions are installed
RUN php -m

# Create benchmark scripts directory
RUN mkdir -p /opt/benchmark

# Copy repo_setup.sh from build context
COPY repo_setup.sh /opt/benchmark/repo_setup.sh
RUN chmod +x /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace with the repository
RUN /opt/benchmark/repo_setup.sh

# Copy setup_runtime.sh from build context
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
RUN chmod +x /opt/benchmark/setup_runtime.sh

# Run setup_runtime.sh to install project dependencies (Composer already installed above)
RUN /opt/benchmark/setup_runtime.sh

# Set working directory to workspace
WORKDIR /workspace

# Default command (can be overridden at runtime)
CMD ["bash"]
