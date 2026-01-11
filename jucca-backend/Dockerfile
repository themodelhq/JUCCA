# syntax=docker/dockerfile:1

# ============================================
# JUCCA Backend - Dockerfile
# ============================================
# This Dockerfile builds the JUCCA backend with
# GPU support and optimized performance settings
# ============================================

# -----------------------------------------------------------------------------
# Base Image
# -----------------------------------------------------------------------------
# Using Python 3.11-slim for balance between size and performance
FROM python:3.11-slim-bookworm AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set default shell
SHELL ["/bin/bash", "-e", "-c"]

# -----------------------------------------------------------------------------
# Dependencies Stage
# -----------------------------------------------------------------------------
FROM base AS dependencies

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY jucca-backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Model Download Stage
# -----------------------------------------------------------------------------
FROM base AS model-downloader

WORKDIR /app

# Install wget for downloading models
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create models directory
RUN mkdir -p /app/models

# Environment variables for model configuration
ENV GPT4ALL_MODEL_PATH=/app/models
ENV GPT4ALL_MODEL=mistral-7b-openorca.gguf

# Download the default model (Mistral 7B OpenOrca)
# This is approximately 4GB, may take some time
RUN echo "Downloading GPT4All model (this may take several minutes)..." && \
    wget -q --show-progress \
        -O /app/models/mistral-7b-openorca.gguf \
        "https://gpt4all.io/models/gguf/mistral-7b-openorca.gguf" || \
    echo "Model download failed or will be downloaded on first run"

# -----------------------------------------------------------------------------
# Final Stage
# -----------------------------------------------------------------------------
FROM base AS production

WORKDIR /app

# Copy Python dependencies from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code from jucca-backend directory
COPY jucca-backend/ .

# Copy models from model-downloader stage (if available)
COPY --from=model-downloader /app/models /app/models 2>/dev/null || \
    mkdir -p /app/models

# Set environment variables
# PYTHONPATH=/app ensures that "app.main:app" import works
ENV PYTHONPATH=/app
ENV GPT4ALL_MODEL_PATH=/app/models
ENV OPENAI_API_KEY=""

# Create non-root user for security
RUN groupadd -r jucca && useradd -r -g jucca jucca && \
    chown -R jucca:jucca /app
USER jucca

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
# Note: Using the module path "app.main:app" which works because PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
