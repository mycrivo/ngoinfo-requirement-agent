# Use Python 3.11 slim image as base
FROM python:3.11-slim

# 🧱 Phase 1: Base Setup & OS Dependencies
# Set environment variables for Playwright and app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOME=/home/appuser

# Install system dependencies required by Playwright and general operations
RUN apt-get update && apt-get install -y \
    # Basic tools
    curl \
    ca-certificates \
    git \
    wget \
    ffmpeg \
    # Playwright system dependencies
    libnss3 \
    libnspr4 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libgconf-2-4 \
    # X11 and rendering libraries
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcursor1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrender1 \
    libxtst6 \
    # Fonts for proper text rendering
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-noto-cjk \
    fonts-freefont-ttf \
    # Clean up to reduce image size
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 🔧 Phase 2: Python & Dependencies
# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies (including Playwright)
RUN pip install --no-cache-dir -r requirements.txt

# 🔐 Phase 3: Split Playwright Install Approach
# Install Playwright system dependencies as root (without browsers)
RUN playwright install-deps chromium

# Create non-root user with proper home directory
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser \
    && mkdir -p /ms-playwright \
    && chown -R appuser:appuser /ms-playwright \
    && chown -R appuser:appuser /home/appuser

# Switch to non-root user for browser installation
USER appuser

# Install Playwright browsers as appuser (no system deps needed)
RUN playwright install chromium

# Validate browser installation
RUN ls -la $PLAYWRIGHT_BROWSERS_PATH/ && \
    find $PLAYWRIGHT_BROWSERS_PATH -name "chromium-*" -type d | head -1 && \
    echo "✅ Chromium browser installed successfully at $PLAYWRIGHT_BROWSERS_PATH"

# ⚙️ Phase 4: Application Setup
# Copy application code with proper ownership
COPY --chown=appuser:appuser . .

# Expose port for FastAPI
EXPOSE 8000

# Health check for Railway deployment monitoring
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 🚀 Start the FastAPI application as appuser
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 