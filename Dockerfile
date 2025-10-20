# ITH DICOM Proxy Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy project files
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/data/logs && \
    mkdir -p /app/data/studies && \
    mkdir -p /app/data/database && \
    mkdir -p /app/data/archives && \
    mkdir -p /app/data/config && \
    chmod -R 755 /app/data

# Collect static files (if needed for admin)
RUN python manage.py collectstatic --noinput || true

# Expose ports
# 8080 - Django HTTP server
# DICOM_PORT - DICOM SCP server (configurable via build arg/env)
ARG DICOM_PORT=11112
ENV DICOM_PORT=${DICOM_PORT}
EXPOSE 8080 ${DICOM_PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/api/health/', timeout=5)" || exit 1

# Run database migrations and start server
CMD python manage.py migrate --noinput && \
    python manage.py runserver 0.0.0.0:8080
