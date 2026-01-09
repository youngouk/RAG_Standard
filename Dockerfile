# Python FastAPI build
FROM python:3.11-slim

# Install system dependencies (including Playwright requirements)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    python3-dev \
    # Playwright/Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy all files
COPY . .

# Install uv and dependencies (as root, WITHOUT Playwright browsers yet)
RUN pip install --no-cache-dir --upgrade pip uv && \
    uv pip install --system --no-cache -e .

# Create directories
RUN mkdir -p logs uploads/temp

# Create non-root user for running the application
RUN useradd --create-home --shell /bin/bash app

# Copy entrypoint script (as root for proper permissions)
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

# Set proper file permissions and ownership (after all installations)
RUN chown -R app:app /app && \
    chmod +x /app/docker-entrypoint.sh

# Switch to non-root user
USER app

# Install Playwright browsers as app user (in /home/app/.cache/ms-playwright/)
RUN playwright install chromium

# Set environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Start application with entrypoint script
# 진입점 스크립트가 환경변수를 올바르게 확장하고 uvicorn 실행
ENTRYPOINT ["/app/docker-entrypoint.sh"]