from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
import os
from contextlib import asynccontextmanager

# Import routers
from routes.requirement_agent import router as requirement_router
from routes.qa_admin import router as qa_admin_router
from routes.publish import router as publish_router
from routes.generate_post import router as generate_post_router
from routes.proposal_template import router as proposal_template_router
from routes.templates import router as templates_router
from routes.documents import router as documents_router
from routes.admin_logs import router as admin_logs_router
from routes.analytics import router as analytics_router
from routes.auth import router as auth_router

# Import security utilities
from utils.auth_enhanced import validate_configuration
from utils.rate_limiter import limiter, rate_limit_exceeded_handler
from utils.security_middleware import (
    create_cors_middleware,
    SecurityHeadersMiddleware,
    RequestValidationMiddleware,
    SecurityLoggingMiddleware
)

# Re-enable DB-related imports
from db import engine
from models import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create tables if they don't exist
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        # Skip heavy initialization in test mode
        if not os.getenv("TEST_MODE", "false").lower() == "true":
            # Validate security configuration
            validate_configuration()
            logger.info("✅ Security configuration validated")
            
            # Create tables
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables created/verified")
        else:
            logger.info("🔧 Test mode: Skipping heavy initialization")
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🔄 Shutting down ReqAgent...")

# Create FastAPI app
app = FastAPI(
    title="ReqAgent - Funding Opportunity Management",
    description="AI-powered funding opportunity discovery and management system",
    version="2.0.0",
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestValidationMiddleware)
app.add_middleware(SecurityLoggingMiddleware)

# Add CORS middleware with security configuration
app.add_middleware(create_cors_middleware())

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Add rate limiting
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(requirement_router)
app.include_router(qa_admin_router)
app.include_router(publish_router)
app.include_router(generate_post_router)
app.include_router(proposal_template_router)
app.include_router(templates_router)
app.include_router(documents_router)
app.include_router(admin_logs_router)
app.include_router(analytics_router)
app.include_router(auth_router)

# Log registered routes
logger.info("🚀 Routes registered:")
logger.info("   📋 API Routes: /api/requirement/*")
logger.info("   🔐 Admin Routes: /admin/login, /admin/logout, /admin/qa-review, /admin/analytics, /admin/logs")
logger.info("   📝 WordPress Routes: /api/wordpress/*")
logger.info("   🤖 Blog Generation Routes: /api/generate-post")
logger.info("   📄 Proposal Template Routes: /admin/proposal-template/*")
logger.info("   🆕 Template API Routes: /api/templates/*")
logger.info("   📚 Document Ingestion Routes: /api/documents/*")
logger.info("   🔧 Migration Routes: /admin/migrations")
logger.info("   📊 Admin Logs Routes: /admin/logs, /admin/api/logs/*")
logger.info("   📈 Analytics Routes: /admin/analytics, /admin/api/analytics/*")
logger.info("   🔑 Auth Routes: /api/auth/*")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ReqAgent",
        "version": "2.0.0",
        "timestamp": "2024-01-01T00:00:00Z"
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to ReqAgent",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Handle 404 errors"""
    return {
        "error": "Not Found",
        "message": "The requested resource was not found",
        "path": str(request.url)
    }

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {exc}")
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "path": str(request.url)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )