#!/usr/bin/env python3
"""
Playwright setup script for Railway deployment
This script installs the necessary browser binaries for Playwright
"""

import subprocess
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def install_playwright_browsers():
    """Install Playwright browser binaries"""
    try:
        logger.info("🚀 Installing Playwright browser binaries...")
        
        # Install Chromium browser for Playwright
        result = subprocess.run([
            sys.executable, "-m", "playwright", "install", "chromium"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info("✅ Playwright Chromium browser installed successfully")
            logger.info(f"Output: {result.stdout}")
        else:
            logger.error(f"❌ Failed to install Playwright browsers: {result.stderr}")
            return False
            
        # Install system dependencies for headless browsing
        logger.info("🔧 Installing system dependencies...")
        deps_result = subprocess.run([
            sys.executable, "-m", "playwright", "install-deps", "chromium"
        ], capture_output=True, text=True, timeout=300)
        
        if deps_result.returncode == 0:
            logger.info("✅ System dependencies installed successfully")
        else:
            logger.warning(f"⚠️ System dependencies installation had issues: {deps_result.stderr}")
            # Don't fail on this as it might not be critical
            
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("⏰ Playwright installation timed out")
        return False
    except Exception as e:
        logger.error(f"🔴 Error during Playwright setup: {str(e)}")
        return False

if __name__ == "__main__":
    success = install_playwright_browsers()
    if success:
        logger.info("🎉 Playwright setup completed successfully")
        sys.exit(0)
    else:
        logger.error("💥 Playwright setup failed")
        sys.exit(1) 