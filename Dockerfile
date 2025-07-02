# Use Python 3.11 slim image as base
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for Playwright and general operations
RUN apt-get update && apt-get install -y \
    # Basic tools
    wget \
    curl \
    unzip \
    # Playwright system dependencies
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libxss1 \
    libgconf-2-4 \
    # Fonts and rendering
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-noto-cjk \
    # Shared libraries
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    ca-certificates \
    # Clean up
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Create Playwright cache directory with proper permissions
RUN mkdir -p /home/appuser/.cache/ms-playwright \
    && chown -R appuser:appuser /home/appuser/.cache

# Switch to non-root user before installing Playwright
USER appuser

# Install Playwright browsers and system dependencies as appuser
# This ensures browsers are installed in the user's cache directory
RUN playwright install --with-deps chromium

# Validate that Chromium was installed successfully
RUN ls -la /home/appuser/.cache/ms-playwright/ \
    && find /home/appuser/.cache/ms-playwright -name "chromium-*" -type d | head -1 \
    && echo "✅ Chromium browser installed successfully"

# Copy application code (this will be a separate layer for better caching)
COPY --chown=appuser:appuser . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 