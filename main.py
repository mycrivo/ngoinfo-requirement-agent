from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from routes.requirement_agent import router as requirement_router
# Re-enable DB-related imports
from db import engine
from models import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Re-enable DB table creation
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Requirement Agent API",
    description="API for parsing funding opportunities from URLs with database storage",
    version="2.0.0"
)

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

@app.get("/")
async def root():
    return {"message": "Requirement Agent API is running with database integration"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "connected"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)