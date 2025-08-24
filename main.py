from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import logging
import os
import secrets

from routes.requirement_agent import router as requirement_router
from routes.qa_admin import router as qa_admin_router
from routes.publish import router as publish_router
from routes.generate_post import router as generate_post_router
from routes.proposal_template import router as proposal_template_router
# Re-enable DB-related imports
from db import engine
from models import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import migration utility
from utils.migrate import run_migrations

# Run database migrations on startup
logger.info("🔄 Running database migrations...")
migration_success = run_migrations()

if migration_success:
    logger.info("✅ Database migrations completed successfully")
    db_available = True
else:
    logger.error("❌ Database migrations failed")
    logger.error("🚨 Application cannot start without successful database migration")
    logger.error("💡 Check your database connection and migration files")
    exit(1)

# Fallback table creation for local development only
if os.getenv("DEV_CREATE_TABLES", "false").lower() == "true":
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Development fallback: Database tables created successfully")
    except Exception as e:
        logger.warning(f"⚠️ Development fallback table creation failed: {str(e)}")
else:
    logger.info("🚀 Production mode: Skipping fallback table creation (using Alembic migrations)")

# Initialize FastAPI app
app = FastAPI(
    title="Requirement Agent API",
    description="API for parsing funding opportunities from URLs with database storage and QA review",
    version="2.0.0"
)

# Add session middleware for admin authentication
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(requirement_router)
app.include_router(qa_admin_router)
app.include_router(publish_router)
app.include_router(generate_post_router)
app.include_router(proposal_template_router)

# Log registered routes
logger.info("🚀 Routes registered:")
logger.info("   📋 API Routes: /api/requirement/*")
logger.info("   🔐 Admin Routes: /admin/login, /admin/logout, /admin/qa-review")
logger.info("   📝 WordPress Routes: /api/wordpress/*")
logger.info("   🤖 Blog Generation Routes: /api/generate-post")
logger.info("   📄 Proposal Template Routes: /admin/proposal-template/*")

@app.get("/")
async def root():
    return {"message": "Requirement Agent API is running with database integration and QA review"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "connected" if db_available else "not_available"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)