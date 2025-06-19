from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Hardcoded admin credentials (in production, use environment variables)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Secret key for session signing (in production, use a strong random key)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")

# Session serializer
serializer = URLSafeTimedSerializer(SECRET_KEY)

def verify_admin_credentials(username: str, password: str) -> bool:
    """Verify admin username and password"""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def create_session_token(username: str) -> str:
    """Create a signed session token"""
    return serializer.dumps({"username": username})

def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode session token"""
    try:
        # Token expires after 24 hours
        data = serializer.loads(token, max_age=86400)
        return data
    except Exception:
        return None

def get_session_user(request: Request) -> Optional[str]:
    """Get the current authenticated user from session"""
    session_token = request.cookies.get("admin_session")
    if not session_token:
        return None
    
    session_data = verify_session_token(session_token)
    if not session_data:
        return None
    
    return session_data.get("username")

def require_admin_auth(request: Request):
    """Dependency to require admin authentication"""
    user = get_session_user(request)
    if not user:
        # Redirect to login page
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/admin/login"}
        )
    return user 