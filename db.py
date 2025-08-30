from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Debug: Print all environment variables that start with PG or DATABASE (SAFE)
print("=== DATABASE ENVIRONMENT VARIABLES ===")
for key, value in os.environ.items():
    if key.startswith(('PG', 'DATABASE')):
        if 'PASSWORD' in key or 'DATABASE_URL' in key:
            print(f"{key}: ***")
        else:
            print(f"{key}: {value}")
print("=" * 40)

# Database URL from environment with Railway compatibility
DATABASE_URL = os.getenv("DATABASE_URL")

# If no DATABASE_URL, try individual components (Railway style)
if not DATABASE_URL:
    DB_HOST = os.getenv("PGHOST", "localhost")
    DB_PORT = os.getenv("PGPORT", "5432")
    DB_NAME = os.getenv("PGDATABASE", "requirement_agent")
    DB_USER = os.getenv("PGUSER", "username")
    DB_PASSWORD = os.getenv("PGPASSWORD", "password")
    
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    print("Built DATABASE_URL from individual components")

# Handle Railway's postgres:// vs postgresql:// URL format
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print("Converted postgres:// to postgresql://")

# Safe logging of connection string
if DATABASE_URL and '@' in DATABASE_URL:
    safe_url = DATABASE_URL.replace(DATABASE_URL.split('@')[0].split('//')[1], '***:***')
    print(f"Connecting to database: {safe_url}")
else:
    print(f"DATABASE_URL format: {DATABASE_URL[:20]}...")

# Create SQLAlchemy engine with connection pooling for production
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=300,    # Recycle connections every 5 minutes
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to get database URL (for migrations)
def get_url():
    """Get database URL from environment variables"""
    return DATABASE_URL 