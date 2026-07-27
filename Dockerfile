FROM python:3.13-slim

# Metadata
LABEL org.opencontainers.image.source="https://github.com/zalaldex/Q"
LABEL maintainer="zalaldex <ptnium@gmail.com>"

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Create a non-root user for security
ARG APP_USER=bot
ARG APP_GROUP=bot
ARG APP_HOME=/app

RUN addgroup --system ${APP_GROUP} \
    && adduser --system --ingroup ${APP_GROUP} --home ${APP_HOME} --shell /bin/sh ${APP_USER}

# Set working directory
WORKDIR ${APP_HOME}

# Install system dependencies required to build some Python packages
# Add extra dev packages commonly needed for cryptography, Pillow, lxml, psycopg2, etc.
# Keep them minimal and remove apt caches after install to reduce image size.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       git \
       ca-certificates \
       libffi-dev \
       libssl-dev \
       curl \
       gcc \
       libc6-dev \
       libpq-dev \
       libxml2-dev \
       libxslt1-dev \
       zlib1g-dev \
       libjpeg-dev \
       libjpeg62-turbo-dev \
       libfreetype6-dev \
       libwebp-dev \
       cargo \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY ./requirements.txt ./requirements.txt
COPY . .

# Install Python dependencies
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Ensure the app directory ownership is the non-root user
RUN chown -R ${APP_USER}:${APP_GROUP} ${APP_HOME}

# Switch to non-root user
USER ${APP_USER}

# Runtime environment (BOT_TOKEN must be provided by the host / platform)
ENV BOT_TOKEN=""

# Expose if running a web server is desired by advanced deployments (not required by Telegram bot)
EXPOSE 8080

# Use a simple entrypoint to run the bot
# run.py will handle async event loop and graceful shutdown
CMD ["python", "run.py"]
